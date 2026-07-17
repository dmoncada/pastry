"""End-to-end tests for the paste API against a moto-mocked DynamoDB."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_returns_slug_and_metadata(client: TestClient) -> None:
    resp = client.post("/pastes", json={"content": "hello world"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["content"] == "hello world"
    assert body["size"] == len("hello world")
    assert body["expires_at"] is None
    assert len(body["slug"]) == 25  # 125-bit Crockford slug


def test_get_by_slug_is_public(client: TestClient) -> None:
    slug = client.post("/pastes", json={"content": "public read"}).json()["slug"]

    resp = client.get(f"/p/{slug}")
    assert resp.status_code == 200
    assert resp.json()["content"] == "public read"

    raw = client.get(f"/p/{slug}/raw")
    assert raw.status_code == 200
    assert raw.text == "public read"
    assert raw.headers["content-type"].startswith("text/plain")


def test_get_missing_slug_404(client: TestClient) -> None:
    assert client.get("/p/NOPENOPENOPENOPENOPENOPE0").status_code == 404


def test_list_returns_all_created(client: TestClient) -> None:
    # Same-second creations tie on the KSUID timestamp prefix, so assert membership,
    # not order. Deterministic ordering is covered in test_repository.py.
    first = client.post("/pastes", json={"content": "one"}).json()["slug"]
    second = client.post("/pastes", json={"content": "two"}).json()["slug"]

    slugs = {p["slug"] for p in client.get("/pastes").json()}
    assert slugs == {first, second}


def test_edit_updates_content_and_size(client: TestClient) -> None:
    slug = client.post("/pastes", json={"content": "before"}).json()["slug"]

    resp = client.patch(f"/p/{slug}", json={"content": "after!"})
    assert resp.status_code == 200
    assert resp.json()["content"] == "after!"
    assert resp.json()["size"] == len("after!")
    assert client.get(f"/p/{slug}").json()["content"] == "after!"


def test_delete_then_404(client: TestClient) -> None:
    slug = client.post("/pastes", json={"content": "temporary"}).json()["slug"]

    assert client.delete(f"/p/{slug}").status_code == 204
    assert client.get(f"/p/{slug}").status_code == 404
    assert client.delete(f"/p/{slug}").status_code == 404


def test_expiry_shorthand_sets_expires_at(client: TestClient) -> None:
    body = client.post(
        "/pastes", json={"content": "ephemeral", "expires_in": "1h"}
    ).json()
    assert body["expires_at"] is not None


def test_invalid_expiry_is_422(client: TestClient) -> None:
    resp = client.post("/pastes", json={"content": "x", "expires_in": "1y"})
    assert resp.status_code == 422
