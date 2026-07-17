"""Test the /auth/me identity endpoint (dev mode)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_me_returns_dev_user(client: TestClient) -> None:
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"github_id": "dev-user", "login": "dev-user"}
