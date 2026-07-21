"""Smoke test proving the app wires up. Real paste/auth tests arrive with each slice."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pastry_api.main import app

pytestmark = pytest.mark.smoke

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
