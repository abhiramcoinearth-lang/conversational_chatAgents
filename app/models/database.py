"""Phase 3: SQLAlchemy database models for PostgreSQL.

Stores: conversation logs, agent configs, tenant info.
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class ConversationLogDB(Base):
    __tablename__ = "conversation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), index=True, nullable=False)
    tenant_id = Column(String(64), index=True, nullable=True)
    sector = Column(String(32), index=True, nullable=False)
    user_message = Column(Text, nullable=False)
    bot_reply = Column(Text, nullable=False)
    intent = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=False)
    tokens_used = Column(Integer, default=0)
    rag_chunks = Column(Integer, default=0)
    escalated = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)


class AgentConfigDB(Base):
    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), index=True, nullable=False)
    sector = Column(String(32), nullable=False)
    name = Column(String(128), nullable=False)
    system_prompt = Column(Text, nullable=False)
    intents = Column(JSON, default=[])
    guardrail_rules = Column(JSON, default=[])
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TenantDB(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), unique=True, nullable=False)
    name = Column(String(256), nullable=False)
    api_key = Column(String(128), unique=True, nullable=False)
    sectors = Column(JSON, default=[])  # Which sectors this tenant uses
    rate_limit = Column(Integer, default=60)  # Requests per minute
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
