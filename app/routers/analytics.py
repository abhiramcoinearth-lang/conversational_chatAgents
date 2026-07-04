"""Phase 4: Analytics and monitoring router."""

from fastapi import APIRouter, Query
from app.utils.logger import get_logger

logger = get_logger("analytics")
router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Phase 4: These queries would run against PostgreSQL conversation_logs table.
# For now, return mock structure showing what the API shape looks like.


@router.get("/summary")
async def get_summary(
    tenant_id: str | None = None,
    sector: str | None = None,
    days: int = Query(default=7, ge=1, le=90),
):
    """Get analytics summary for the last N days.

    In production, this queries the conversation_logs table in PostgreSQL.
    """
    # Phase 4: Replace with actual DB query
    # SELECT COUNT(*), AVG(latency_ms), sector
    # FROM conversation_logs
    # WHERE created_at > NOW() - INTERVAL '{days} days'
    # GROUP BY sector

    return {
        "period_days": days,
        "tenant_id": tenant_id,
        "sector": sector,
        "metrics": {
            "total_conversations": 0,
            "total_messages": 0,
            "avg_latency_ms": 0.0,
            "escalation_rate": 0.0,
            "top_intents": [],
            "by_sector": {},
            "daily_volume": [],
        },
        "note": "Connect PostgreSQL and run migrations to enable real analytics",
    }


@router.get("/conversations")
async def list_conversations(
    tenant_id: str | None = None,
    sector: str | None = None,
    session_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List conversation logs with filtering."""
    return {
        "conversations": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "note": "Connect PostgreSQL to enable conversation history",
    }


@router.get("/intents")
async def intent_analytics(
    sector: str | None = None,
    days: int = Query(default=7, ge=1, le=90),
):
    """Get intent distribution analytics."""
    return {
        "period_days": days,
        "sector": sector,
        "intent_distribution": [],
        "low_confidence_rate": 0.0,
        "unclassified_rate": 0.0,
    }
