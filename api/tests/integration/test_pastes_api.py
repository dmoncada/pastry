"""End-to-end tests for the paste API against a moto-mocked DynamoDB."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_create_returns_slug_and_metadata(client: TestClient) -> None:
    resp = client.post("/api/pastes", json={"content": "hello world"})
    assert resp.status_code == 201

    body = resp.json()
    assert body["content"] == "hello world"
    assert body["size"] == len("hello world")
    assert body["expires_at"] is None
    assert len(body["slug"]) == 20  # 100-bit Crockford slug


def test_get_by_slug_is_public(client: TestClient) -> None:
    slug = client.post("/api/pastes", json={"content": "public read"}).json()["slug"]

    resp = client.get(f"/api/pastes/{slug}")
    assert resp.status_code == 200
    assert resp.json()["content"] == "public read"

    raw = client.get(f"/raw/{slug}")
    assert raw.status_code == 200
    assert raw.text == "public read"
    assert raw.headers["content-type"].startswith("text/plain")


def test_get_missing_slug_404(client: TestClient) -> None:
    assert client.get("/api/pastes/NOPENOPENOPENOPENOPE").status_code == 404
    assert client.get("/raw/NOPENOPENOPENOPENOPE").status_code == 404


def test_list_returns_all_created(client: TestClient) -> None:
    # Same-second creations tie on the KSUID timestamp prefix, so assert membership,
    # not order. Deterministic ordering is covered in test_repository.py.
    first = client.post("/api/pastes", json={"content": "one"}).json()["slug"]
    second = client.post("/api/pastes", json={"content": "two"}).json()["slug"]
    slugs = {p["slug"] for p in client.get("/api/pastes").json()}
    assert slugs == {first, second}


def test_edit_updates_content_and_size(client: TestClient) -> None:
    slug = client.post("/api/pastes", json={"content": "before"}).json()["slug"]
    resp = client.patch(f"/api/pastes/{slug}", json={"content": "after!"})
    assert resp.status_code == 200
    assert resp.json()["content"] == "after!"
    assert resp.json()["size"] == len("after!")
    assert client.get(f"/api/pastes/{slug}").json()["content"] == "after!"


def test_delete_then_404(client: TestClient) -> None:
    slug = client.post("/api/pastes", json={"content": "temporary"}).json()["slug"]
    assert client.delete(f"/api/pastes/{slug}").status_code == 204
    assert client.get(f"/api/pastes/{slug}").status_code == 404
    assert client.get(f"/raw/{slug}").status_code == 404
    assert client.delete(f"/api/pastes/{slug}").status_code == 404


def test_expiry_shorthand_sets_expires_at(client: TestClient) -> None:
    body = client.post(
        "/api/pastes", json={"content": "ephemeral", "expires_in": "1h"}
    ).json()
    assert body["expires_at"] is not None


def test_invalid_expiry_is_422(client: TestClient) -> None:
    resp = client.post("/api/pastes", json={"content": "x", "expires_in": "1y"})
    assert resp.status_code == 422


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/healthz"),
        ("GET", "/auth/me"),
        ("GET", "/auth/github/login"),
        ("GET", "/auth/github/callback"),
        ("POST", "/auth/device/code"),
        ("POST", "/auth/device/token"),
        ("POST", "/auth/refresh"),
        ("POST", "/auth/logout"),
        ("GET", "/pastes"),
        ("POST", "/pastes"),
        ("GET", "/p/ABCDEFGHIJKLMNOPQRST"),
        ("GET", "/p/ABCDEFGHIJKLMNOPQRST/raw"),
        ("PATCH", "/p/ABCDEFGHIJKLMNOPQRST"),
        ("DELETE", "/p/ABCDEFGHIJKLMNOPQRST"),
    ],
)
def test_removed_root_api_routes_are_404(
    client: TestClient, method: str, path: str
) -> None:
    assert client.request(method, path).status_code == 404
