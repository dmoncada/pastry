"""FastAPI application entrypoint. Served locally by uvicorn, in AWS by Mangum/Lambda."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from pastry_api.config import get_settings
from pastry_api.routers import auth, pastes

app = FastAPI(title="Pastry API", version="0.1.0")

# The web app is served same-origin with the API (CloudFront routes /api/* to this app, and
# the dev vite server proxies /api), so browser calls need no CORS at all. This stays only
# for direct cross-origin dev hits; allow_credentials=False keeps the "*" wildcards valid.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# All JSON and authentication operations are canonical under /api. The refresh cookie is
# deliberately scoped to /api/auth, while raw content has its own public /raw namespace.
app.include_router(pastes.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(pastes.raw_router)


@app.get("/api/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


# Lambda entrypoint (API Gateway HTTP API -> Mangum -> ASGI app).
handler = Mangum(app)
