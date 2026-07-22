"""API key authentication middleware."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import get_settings

settings = get_settings()

# Exact-match public paths that don't need auth
PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/api/me", "/favicon.ico"}

# Any request whose path starts with one of these prefixes is public
PUBLIC_PREFIXES = ("/ui/",)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow browser CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return JSONResponse(
                status_code=401, content={"detail": "Missing X-API-Key header"}
            )
        if api_key != settings.api_secret_key:
            return JSONResponse(status_code=403, content={"detail": "Invalid API key"})

        return await call_next(request)
