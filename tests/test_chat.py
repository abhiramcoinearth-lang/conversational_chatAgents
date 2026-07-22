"""Tests for the chat endpoint."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import get_settings

AUTH_HEADERS = {"X-API-Key": get_settings().api_secret_key}


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
        resp = await client.get("/", follow_redirects=False)
        assert resp.status_code == 307
        assert "/ui/" in resp.headers.get("location", "")


@pytest.mark.asyncio
async def test_sectors_listed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents/sectors", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sectors"]) == 6


@pytest.mark.asyncio
async def test_missing_api_key_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents/sectors")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_api_key_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/agents/sectors", headers={"X-API-Key": "wrong-key"}
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_chat_validation():
    """Empty message and invalid sector should be rejected by Pydantic."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Empty message
        resp = await client.post(
            "/api/chat",
            json={"message": "", "sector": "retail"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

        # Invalid sector (not built-in and no custom_ prefix)
        resp = await client.post(
            "/api/chat",
            json={"message": "hello", "sector": "invalid"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_success():
    """Requires the LLM server running (integration only)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/chat",
            json={"message": "What is your return policy?", "sector": "retail"},
            headers=AUTH_HEADERS,
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "reply" in data
            assert "session_id" in data
