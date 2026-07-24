"""Auth integration tests: refresh-token rotation/revocation against the moto table, plus
the auth endpoints with a faked GitHub.

No network or real OAuth app — the GitHub client is overridden via FastAPI dependency
injection, and the JWT/refresh logic runs against the moto-mocked table. The pure
token-crypto unit tests live in unit/test_auth_tokens.py."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pastry_api import auth_repo, auth_service
from pastry_api.config import Settings, get_settings
from pastry_api.github import GitHubError
from pastry_api.main import app
from pastry_api.routers.auth import get_github_client
from pastry_api.security import InvalidToken, create_access_token, decode_access_token

pytestmark = pytest.mark.integration


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


# --- refresh-token lifecycle (service level, moto-backed) ----------------------------


def test_rotate_invalidates_old_refresh(table: None) -> None:
    settings = Settings(jwt_signing_key="k")
    pair = auth_service.issue_tokens("42", settings)

    rotated = auth_service.rotate_refresh(pair.refresh_token, settings)
    assert rotated.refresh_token != pair.refresh_token
    # the original (rotated-away) token is now dead
    with pytest.raises(InvalidToken):
        auth_service.rotate_refresh(pair.refresh_token, settings)


def test_concurrent_refresh_consumes_token_once(
    table: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(jwt_signing_key="k")
    pair = auth_service.issue_tokens("42", settings)
    _get_refresh = auth_repo.get_refresh
    barrier = Barrier(2)

    def sync_get_refresh(github_id: str, jti: str) -> auth_repo.Item | None:
        item = _get_refresh(github_id, jti)
        barrier.wait()
        return item

    monkeypatch.setattr(auth_repo, "get_refresh", sync_get_refresh)

    def rotate() -> bool:
        try:
            auth_service.rotate_refresh(pair.refresh_token, settings)
        except InvalidToken:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: rotate(), range(2)))

    assert sorted(outcomes) == [False, True]


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
    code = client.post("/api/auth/device/code")
    assert code.status_code == 200
    assert code.json()["user_code"] == "WDJB-MJHT"

    resp = client.post("/api/auth/device/token", json={"device_code": "DC-123"})
    assert resp.status_code == 200
    tokens = resp.json()
    assert decode_access_token(tokens["access_token"], get_settings()) == "12345"
    assert auth_repo.get_user("12345") is not None


def test_device_flow_pending_returns_428(
    client: TestClient, github: FakeGitHub
) -> None:
    github.pending = True
    resp = client.post("/api/auth/device/token", json={"device_code": "DC-123"})
    assert resp.status_code == 428


def test_github_callback_success(client: TestClient, github: FakeGitHub) -> None:
    resp = client.get("/api/auth/github/callback", params={"code": "ok", "state": "s"})
    assert resp.status_code == 200
    assert decode_access_token(resp.json()["access_token"], get_settings()) == "12345"


def test_github_callback_bad_code_400(client: TestClient, github: FakeGitHub) -> None:
    resp = client.get("/api/auth/github/callback", params={"code": "bad", "state": "s"})
    assert resp.status_code == 400


def test_refresh_endpoint_rotates(client: TestClient, github: FakeGitHub) -> None:
    pair = client.post("/api/auth/device/token", json={"device_code": "DC-123"}).json()

    rotated = client.post(
        "/api/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )
    assert rotated.status_code == 200
    # old refresh token no longer works
    reused = client.post(
        "/api/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )
    assert reused.status_code == 401


def test_logout_revokes_refresh(client: TestClient, github: FakeGitHub) -> None:
    pair = client.post("/api/auth/device/token", json={"device_code": "DC-123"}).json()
    assert (
        client.post(
            "/api/auth/logout", json={"refresh_token": pair["refresh_token"]}
        ).status_code
        == 204
    )
    after = client.post(
        "/api/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )
    assert after.status_code == 401


# --- web cookie transport (browser client, /api mount) -------------------------------


def test_callback_sets_refresh_cookie_and_hides_it_from_body(
    client: TestClient, github: FakeGitHub
) -> None:
    resp = client.get("/api/auth/github/callback", params={"code": "ok", "state": "s"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" not in body  # rides in the cookie, never the web body
    set_cookie = resp.headers["set-cookie"]
    assert "pastry_refresh=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/auth" in set_cookie


def test_refresh_via_cookie_rotates_and_omits_refresh_from_body(
    client: TestClient, github: FakeGitHub
) -> None:
    # Sign in via the callback so the client's cookie jar holds the refresh cookie.
    client.get("/api/auth/github/callback", params={"code": "ok", "state": "s"})

    rotated = client.post("/api/auth/refresh")  # no body: refresh comes from the cookie
    assert rotated.status_code == 200
    assert "refresh_token" not in rotated.json()
    assert "pastry_refresh=" in rotated.headers["set-cookie"]  # rotated cookie re-set


def test_logout_via_cookie_clears_cookie_and_revokes(
    client: TestClient, github: FakeGitHub
) -> None:
    client.get("/api/auth/github/callback", params={"code": "ok", "state": "s"})

    resp = client.post("/api/auth/logout")  # no body: cookie transport
    assert resp.status_code == 204
    # Deletion re-sets the cookie with an immediate expiry.
    assert (
        'pastry_refresh=""' in resp.headers["set-cookie"]
        or "Max-Age=0" in (resp.headers["set-cookie"])
    )
    # The revoked token can no longer be rotated (the jar cleared it, so send none → 401).
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_without_cookie_or_body_is_401(
    client: TestClient, github: FakeGitHub
) -> None:
    assert client.post("/api/auth/refresh").status_code == 401


# --- auth dependency in github mode --------------------------------------------------


def test_protected_route_requires_valid_jwt(client: TestClient) -> None:
    gh_settings = Settings(auth_mode="github", jwt_signing_key="prod-key")
    app.dependency_overrides[get_settings] = lambda: gh_settings

    assert client.post("/api/pastes", json={"content": "x"}).status_code == 401
    assert (
        client.post(
            "/api/pastes",
            json={"content": "x"},
            headers={"Authorization": "Bearer garbage"},
        ).status_code
        == 401
    )

    token = create_access_token("user-1", gh_settings)
    ok = client.post(
        "/api/pastes",
        json={"content": "mine"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 201
    assert ok.json()["owner_github_id"] == "user-1"
