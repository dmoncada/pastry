"""Auth tests: token lifecycle (unit + service) and endpoints with a faked GitHub.

No network or real OAuth app — the GitHub client is overridden via FastAPI dependency
injection, and the JWT/refresh logic runs against the moto-mocked table."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pastry_api import auth_repo, auth_service
from pastry_api.config import Settings, get_settings
from pastry_api.github import GitHubError
from pastry_api.main import app
from pastry_api.routers.auth import get_github_client
from pastry_api.security import InvalidToken, create_access_token, decode_access_token


class FakeGitHub:
    """Deterministic stand-in for :class:`GitHubAuth`."""

    def __init__(self) -> None:
        self.pending = False
        self.profile: dict[str, Any] = {
            "id": 12345,
            "login": "octocat",
            "name": "The Octocat",
        }

    def build_authorize_url(self, state: str) -> str:
        return f"https://github.com/login/oauth/authorize?state={state}"

    def exchange_code(self, code: str) -> str:
        if code == "bad":
            raise GitHubError("bad verification code")
        return "gh-access-token"

    def start_device_flow(self) -> dict[str, Any]:
        return {
            "device_code": "DC-123",
            "user_code": "WDJB-MJHT",
            "verification_uri": "https://github.com/login/device",
            "interval": 0,
            "expires_in": 900,
        }

    def poll_device_token(self, device_code: str) -> str | None:
        return None if self.pending else "gh-access-token"

    def fetch_user(self, access_token: str) -> dict[str, Any]:
        return self.profile


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def github() -> FakeGitHub:
    fake = FakeGitHub()
    app.dependency_overrides[get_github_client] = lambda: fake
    return fake


# --- token lifecycle (service level) -------------------------------------------------


def test_access_token_roundtrip() -> None:
    settings = Settings(jwt_signing_key="k")
    token = create_access_token("42", settings)
    assert decode_access_token(token, settings) == "42"


def test_decode_rejects_wrong_key() -> None:
    token = create_access_token("42", Settings(jwt_signing_key="right"))
    with pytest.raises(InvalidToken):
        decode_access_token(token, Settings(jwt_signing_key="wrong"))


def test_rotate_invalidates_old_refresh(table: None) -> None:
    settings = Settings(jwt_signing_key="k")
    pair = auth_service.issue_tokens("42", settings)

    rotated = auth_service.rotate_refresh(pair.refresh_token, settings)
    assert rotated.refresh_token != pair.refresh_token
    # the original (rotated-away) token is now dead
    with pytest.raises(InvalidToken):
        auth_service.rotate_refresh(pair.refresh_token, settings)


def test_rotate_rejects_tampered_token(table: None) -> None:
    settings = Settings(jwt_signing_key="k")
    pair = auth_service.issue_tokens("42", settings)
    with pytest.raises(InvalidToken):
        auth_service.rotate_refresh(pair.refresh_token + "x", settings)


def test_revoke_then_rotate_fails(table: None) -> None:
    settings = Settings(jwt_signing_key="k")
    pair = auth_service.issue_tokens("42", settings)
    auth_service.revoke_refresh(pair.refresh_token)
    with pytest.raises(InvalidToken):
        auth_service.rotate_refresh(pair.refresh_token, settings)


# --- endpoints -----------------------------------------------------------------------


def test_device_flow_success(client: TestClient, github: FakeGitHub) -> None:
    code = client.post("/auth/device/code")
    assert code.status_code == 200
    assert code.json()["user_code"] == "WDJB-MJHT"

    resp = client.post("/auth/device/token", json={"device_code": "DC-123"})
    assert resp.status_code == 200
    tokens = resp.json()
    assert decode_access_token(tokens["access_token"], get_settings()) == "12345"
    assert auth_repo.get_user("12345") is not None


def test_device_flow_pending_returns_428(
    client: TestClient, github: FakeGitHub
) -> None:
    github.pending = True
    resp = client.post("/auth/device/token", json={"device_code": "DC-123"})
    assert resp.status_code == 428


def test_github_callback_success(client: TestClient, github: FakeGitHub) -> None:
    resp = client.get("/auth/github/callback", params={"code": "ok", "state": "s"})
    assert resp.status_code == 200
    assert decode_access_token(resp.json()["access_token"], get_settings()) == "12345"


def test_github_callback_bad_code_400(client: TestClient, github: FakeGitHub) -> None:
    resp = client.get("/auth/github/callback", params={"code": "bad", "state": "s"})
    assert resp.status_code == 400


def test_refresh_endpoint_rotates(client: TestClient, github: FakeGitHub) -> None:
    pair = client.post("/auth/device/token", json={"device_code": "DC-123"}).json()

    rotated = client.post(
        "/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )
    assert rotated.status_code == 200
    # old refresh token no longer works
    reused = client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert reused.status_code == 401


def test_logout_revokes_refresh(client: TestClient, github: FakeGitHub) -> None:
    pair = client.post("/auth/device/token", json={"device_code": "DC-123"}).json()
    assert (
        client.post(
            "/auth/logout", json={"refresh_token": pair["refresh_token"]}
        ).status_code
        == 204
    )
    after = client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert after.status_code == 401


# --- auth dependency in github mode --------------------------------------------------


def test_protected_route_requires_valid_jwt(client: TestClient) -> None:
    gh_settings = Settings(auth_mode="github", jwt_signing_key="prod-key")
    app.dependency_overrides[get_settings] = lambda: gh_settings

    assert client.post("/pastes", json={"content": "x"}).status_code == 401
    assert (
        client.post(
            "/pastes",
            json={"content": "x"},
            headers={"Authorization": "Bearer garbage"},
        ).status_code
        == 401
    )

    token = create_access_token("user-1", gh_settings)
    ok = client.post(
        "/pastes",
        json={"content": "mine"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 201
    assert ok.json()["owner_github_id"] == "user-1"
