"""GitHub OAuth client: authorization-code (web) and device-flow (CLI) + user lookup.

Isolated behind :class:`GitHubAuth` so routes depend on the protocol and tests inject a
fake — no network, no real OAuth app needed to exercise the endpoints.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from pastry_api.config import Settings

# On Lambda there is no console to watch, so a failed OAuth exchange leaves no trace
# beyond the 4xx the caller sees. These are the only calls that depend on a third party.
logger = logging.getLogger(__name__)

_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
# Note: the device-code endpoint is NOT under /login/oauth/, unlike the two above.
_DEVICE_CODE_URL = "https://github.com/login/device/code"
_USER_URL = "https://api.github.com/user"
_DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"

# GitHub device-flow errors that mean "keep polling" rather than a hard failure.
_PENDING_ERRORS = {"authorization_pending", "slow_down"}


class GitHubError(Exception):
    """A hard failure from GitHub (bad code, denied/expired device grant, etc.)."""


class GitHubAuth(Protocol):
    def build_authorize_url(self, state: str) -> str: ...
    def exchange_code(self, code: str) -> str: ...
    def start_device_flow(self) -> dict[str, Any]: ...
    def poll_device_token(self, device_code: str) -> str | None: ...
    def fetch_user(self, access_token: str) -> dict[str, Any]: ...


class GitHubClient:
    """Concrete :class:`GitHubAuth` backed by httpx calls to github.com."""

    def __init__(self, settings: Settings) -> None:
        self._client_id = settings.github_oauth_client_id
        self._client_secret = settings.github_oauth_client_secret

    def build_authorize_url(self, state: str) -> str:
        query = urlencode(
            {"client_id": self._client_id, "scope": "read:user", "state": state}
        )
        return f"{_AUTHORIZE_URL}?{query}"

    def exchange_code(self, code: str) -> str:
        data = self._post_form(
            _ACCESS_TOKEN_URL,
            {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
            },
        )
        token = data.get("access_token")
        if not token:
            raise GitHubError(data.get("error_description", "code exchange failed"))
        return str(token)

    def start_device_flow(self) -> dict[str, Any]:
        return self._post_form(
            _DEVICE_CODE_URL, {"client_id": self._client_id, "scope": "read:user"}
        )

    def poll_device_token(self, device_code: str) -> str | None:
        """Return the GitHub access token, or None while the user hasn't approved yet."""
        data = self._post_form(
            _ACCESS_TOKEN_URL,
            {
                "client_id": self._client_id,
                "device_code": device_code,
                "grant_type": _DEVICE_GRANT,
            },
        )
        if token := data.get("access_token"):
            return str(token)
        error = data.get("error")
        if error in _PENDING_ERRORS:
            return None
        raise GitHubError(data.get("error_description", error or "device grant failed"))

    def fetch_user(self, access_token: str) -> dict[str, Any]:
        resp = httpx.get(
            _USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10.0,
        )
        return _parse(resp)

    @staticmethod
    def _post_form(url: str, data: dict[str, str]) -> dict[str, Any]:
        resp = httpx.post(
            url, data=data, headers={"Accept": "application/json"}, timeout=10.0
        )
        return _parse(resp)


def _parse(resp: httpx.Response) -> dict[str, Any]:
    """Return the decoded JSON body, or raise :class:`GitHubError` describing the failure.

    GitHub answers some malformed requests with an HTML error page rather than JSON, so a
    non-2xx status and an undecodable body both surface as GitHubError instead of leaking
    an httpx exception (which the routes would turn into an opaque 500).
    """
    if resp.is_error:
        # Body deliberately not logged: token endpoints echo back credentials.
        logger.warning(
            "GitHub returned %s for %s", resp.status_code, resp.request.url.path
        )
        raise GitHubError(
            f"GitHub returned {resp.status_code} for {resp.request.url.path}"
        )
    try:
        body: Any = resp.json()
    except ValueError as exc:
        logger.warning("GitHub sent a non-JSON body for %s", resp.request.url.path)
        raise GitHubError(
            f"GitHub sent a non-JSON response for {resp.request.url.path}"
        ) from exc
    if not isinstance(body, dict):
        logger.warning(
            "GitHub sent a %s, expected an object, for %s",
            type(body).__name__,
            resp.request.url.path,
        )
        raise GitHubError(
            f"GitHub sent an unexpected response for {resp.request.url.path}"
        )
    return body
