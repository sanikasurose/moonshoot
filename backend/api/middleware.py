"""JWT validation middleware — auth on every /api/* route (docs/TRD.md section 8)."""
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config.settings import JWT_SECRET

PUBLIC_PATHS = {"/api/health", "/api/auth/verify"}


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in PUBLIC_PATHS:
            auth = request.headers.get("Authorization", "")
            token = auth.removeprefix("Bearer ").strip()
            try:
                jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            except jwt.InvalidTokenError:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)
