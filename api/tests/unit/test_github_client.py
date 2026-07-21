"""The real :class:`GitHubClient`: endpoint URLs and response handling.

Everything else in the auth suite injects a fake ``GitHubAuth``, so nothing exercises the
concrete client — a wrong endpoint or an unhandled error body passes unnoticed there. (It
did: the device-code URL was ``/login/oauth/device/code``, which GitHub answers with a 422
HTML page, and the fake-backed tests stayed green.)
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pastry_api.config import Settings
from pastry_api.github import GitHubClient, GitHubError

pytestmark = pytest.mark.unit


@pytest.fixture
def client() -> GitHubClient:
    return GitHubClient(
        Settings(github_oauth_client_id="cid", github_oauth_client_secret="secret")
    )


def _capture(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    *,
    status: int = 200,
    payload: Any = None,
    text: str | None = None,
) -> dict[str, Any]:
    """Replace ``httpx.<method>`` with a stub, returning a dict that records the call."""
    seen: dict[str, Any] = {}

    def fake(url: str, **kwargs: Any) -> httpx.Response:
        seen["url"] = url
        seen["data"] = kwargs.get("data")
        request = httpx.Request(method.upper(), url)
        if text is not None:
            return httpx.Response(status, text=text, request=request)
        return httpx.Response(status, json=payload, request=request)

    monkeypatch.setattr(httpx, method, fake)
    return seen


# --- endpoint URLs (the layer the fake can't cover) ---


def test_authorize_url_is_under_login_oauth(client: GitHubClient) -> None:
    url = client.build_authorize_url("state-123")
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=cid" in url
    assert "state=state-123" in url


def test_device_flow_posts_to_login_device_code(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: this endpoint is NOT under /login/oauth/, unlike the other two."""
    seen = _capture(
        monkeypatch, "post", payload={"device_code": "DC-1", "user_code": "WDJB"}
    )

    assert client.start_device_flow()["device_code"] == "DC-1"
    assert seen["url"] == "https://github.com/login/device/code"
    assert seen["data"]["client_id"] == "cid"


def test_exchange_code_posts_to_access_token(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _capture(monkeypatch, "post", payload={"access_token": "gh-token"})

    assert client.exchange_code("the-code") == "gh-token"
    assert seen["url"] == "https://github.com/login/oauth/access_token"
    assert seen["data"]["code"] == "the-code"
    assert seen["data"]["client_secret"] == "secret"


def test_poll_device_token_posts_to_access_token(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _capture(monkeypatch, "post", payload={"access_token": "gh-token"})

    assert client.poll_device_token("DC-1") == "gh-token"
    assert seen["url"] == "https://github.com/login/oauth/access_token"
    assert seen["data"]["grant_type"] == "urn:ietf:params:oauth:grant-type:device_code"


def test_fetch_user_gets_api_user(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _capture(monkeypatch, "get", payload={"id": 1, "login": "octocat"})

    assert client.fetch_user("gh-token")["login"] == "octocat"
    assert seen["url"] == "https://api.github.com/user"


# --- error translation: GitHub failures must not leak httpx exceptions (-> opaque 500s) ---


def test_html_error_page_raises_github_error(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GitHub answers a malformed device request with a 422 *HTML* page, not JSON."""
    _capture(
        monkeypatch, "post", status=422, text="<!DOCTYPE html><title>Oh no</title>"
    )

    with pytest.raises(GitHubError, match="422"):
        client.start_device_flow()


def test_non_json_success_body_raises_github_error(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture(monkeypatch, "post", status=200, text="not json")

    with pytest.raises(GitHubError, match="non-JSON"):
        client.start_device_flow()


def test_fetch_user_error_raises_github_error(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture(monkeypatch, "get", status=401, payload={"message": "Bad credentials"})

    with pytest.raises(GitHubError, match="401"):
        client.fetch_user("stale-token")


def test_pending_device_grant_is_not_an_error(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 200 carrying authorization_pending means 'keep polling', not a failure."""
    _capture(monkeypatch, "post", payload={"error": "authorization_pending"})

    assert client.poll_device_token("DC-1") is None


def test_denied_device_grant_raises_github_error(
    client: GitHubClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _capture(
        monkeypatch,
        "post",
        payload={"error": "access_denied", "error_description": "denied"},
    )

    with pytest.raises(GitHubError, match="denied"):
        client.poll_device_token("DC-1")
