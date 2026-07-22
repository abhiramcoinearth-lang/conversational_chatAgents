from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from datetime import datetime

from app.config import get_settings
from app.routers import chat, agents, documents, analytics, tenants
from app.routers.persona import router as persona_router
from app.services.llm_client import llm_client
from app.services.memory_manager import memory_manager
from app.models.db_session import init_db, shutdown_db
from app.middleware.auth import AuthMiddleware
from app.models.schemas import HealthResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await memory_manager.connect()
    await init_db()
    yield
    await memory_manager.disconnect()
    await shutdown_db()


app = FastAPI(
    title="Chat Agent Platform",
    description="Multi-sector AI chat agents powered by local LLM",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

app.include_router(chat.router)
app.include_router(agents.router)
app.include_router(documents.router)
app.include_router(analytics.router)
app.include_router(tenants.router)
app.include_router(persona_router)


@app.get("/")
async def root():
    return RedirectResponse(url="/ui/test-ui.html")


@app.get("/api/me")
async def me():
    """Stub endpoint to silence browser-extension polling. Not used by the chat."""
    return {"authenticated": False}


@app.get("/health", response_model=HealthResponse)
async def health():
    llm_ok = await llm_client.health_check()
    return HealthResponse(
        status="ok" if llm_ok else "degraded",
        llm_status="connected" if llm_ok else "disconnected",
        timestamp=datetime.utcnow(),
    )


app.mount("/ui", StaticFiles(directory="frontend", html=True), name="ui")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=settings.debug)
