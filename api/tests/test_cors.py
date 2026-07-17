"""The web app calls the API cross-origin, so CORS must allow its origin."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_cors_preflight_allows_web_origin(client: TestClient) -> None:
    resp = client.options(
        "/pastes",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    resp = client.options(
        "/pastes",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers.get("access-control-allow-origin") is None
