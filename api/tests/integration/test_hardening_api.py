"""Integration regression tests for hardening defects at the API surface.

Each test here pins a specific defect: an oversized body reaching DynamoDB, and protected
routes missing from the OpenAPI security document. The model/config/security-layer
regressions live in unit/test_hardening.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pastry_shared.models import MAX_CONTENT_BYTES

pytestmark = pytest.mark.integration

# --- Content size limit --------------------------------------------------------------


def test_oversized_paste_is_rejected_with_422(client: TestClient) -> None:
    """Previously reached put_item and raised a botocore ClientError -> 500."""
    resp = client.post("/api/pastes", json={"content": "x" * (MAX_CONTENT_BYTES + 1)})
    assert resp.status_code == 422


def test_paste_at_the_limit_is_accepted(client: TestClient) -> None:
    resp = client.post("/api/pastes", json={"content": "x" * MAX_CONTENT_BYTES})
    assert resp.status_code == 201


def test_oversized_edit_is_rejected(client: TestClient) -> None:
    slug = client.post("/api/pastes", json={"content": "seed"}).json()["slug"]
    resp = client.patch(
        f"/api/pastes/{slug}", json={"content": "x" * (MAX_CONTENT_BYTES + 1)}
    )
    assert resp.status_code == 422


# --- OpenAPI security document -------------------------------------------------------


def test_openapi_declares_the_bearer_scheme(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    schemes = schema["components"]["securitySchemes"]
    assert any(s.get("scheme") == "bearer" for s in schemes.values())


def test_protected_routes_carry_a_security_requirement(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/api/pastes"]["get"]["security"]
    assert schema["paths"]["/api/pastes"]["post"]["security"]


def test_public_read_stays_unauthenticated(client: TestClient) -> None:
    """The unlisted-link model depends on slug reads requiring no credentials."""
    schema = client.get("/openapi.json").json()
    assert "security" not in schema["paths"]["/api/pastes/{slug}"]["get"]
    assert "security" not in schema["paths"]["/raw/{slug}"]["get"]
