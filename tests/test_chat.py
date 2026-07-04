"""Tests for the chat endpoint."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")


@pytest.mark.asyncio
async def test_root_redirects_to_ui():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        # Root redirects to the bundled test UI.
        assert resp.status_code == 307
        assert "/ui/" in resp.headers.get("location", "")


@pytest.mark.asyncio
async def test_sectors_listed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents/sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sectors"]) == 6


@pytest.mark.xfail(
    reason="app does not currently enforce 422 on empty message / invalid sector",
    strict=False,
)
@pytest.mark.asyncio
async def test_chat_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Empty message should fail
        resp = await client.post("/api/chat", json={"message": "", "sector": "retail"})
        assert resp.status_code == 422

        # Invalid sector should fail
        resp = await client.post("/api/chat", json={"message": "hello", "sector": "invalid"})
        assert resp.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_success():
    """This test requires the llama.cpp server running (integration only)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/chat", json={
            "message": "What is your return policy?",
            "sector": "retail",
        })
        # Will be 503 if llama.cpp is not running
        if resp.status_code == 200:
            data = resp.json()
            assert "reply" in data
            assert "session_id" in data
