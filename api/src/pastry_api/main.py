"""FastAPI application entrypoint. Served locally by uvicorn, in AWS by Mangum/Lambda."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from pastry_api.config import get_settings
from pastry_api.routers import auth, pastes

app = FastAPI(title="Pastry API", version="0.1.0")

# Bearer tokens (not cookies) → allow_credentials stays False, which permits "*" headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(pastes.router)
app.include_router(auth.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


# Lambda entrypoint (API Gateway HTTP API -> Mangum -> ASGI app).
handler = Mangum(app)
