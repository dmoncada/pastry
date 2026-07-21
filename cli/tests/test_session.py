"""Tests for access-token resolution (the per-call refresh-rotation dance)."""

from __future__ import annotations

import json as _json
from typing import Any

import pytest
from pastry_cli import session
from pastry_cli.config import Config


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload

    @property
    def content(self) -> bytes:
        """Mirror ``httpx.Response.content`` — the models parse raw bytes."""
        return _json.dumps(self._payload).encode()


def _config() -> Config:
    return Config(api_url="http://localhost:8080", token=None)


def test_env_token_wins_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("should not hit the network")

    monkeypatch.setattr(session.httpx, "post", boom)
    cfg = Config(api_url="http://localhost:8080", token="env-token")
    assert session.resolve_access_token(cfg) == "env-token"


def test_no_refresh_token_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session, "load_refresh_token", lambda: None)
    assert session.resolve_access_token(_config()) is None


def test_rotates_and_persists_new_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: list[str] = []
    monkeypatch.setattr(session, "load_refresh_token", lambda: "gid.jti.secret")
    monkeypatch.setattr(session, "save_refresh_token", lambda t: saved.append(t))
    monkeypatch.setattr(
        session.httpx,
        "post",
        lambda *a, **k: FakeResponse(
            200, {"access_token": "AT", "refresh_token": "NEW", "expires_in": 900}
        ),
    )
    assert session.resolve_access_token(_config()) == "AT"
    assert saved == ["NEW"]  # rotated refresh token written back


def test_rejected_refresh_is_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    cleared: list[bool] = []
    monkeypatch.setattr(session, "load_refresh_token", lambda: "gid.jti.secret")
    monkeypatch.setattr(session, "clear_refresh_token", lambda: cleared.append(True))
    monkeypatch.setattr(session.httpx, "post", lambda *a, **k: FakeResponse(401))
    assert session.resolve_access_token(_config()) is None
    assert cleared == [True]


class FakeDeviceClient:
    """Stand-in for httpx.Client covering the two device-flow POSTs."""

    def __init__(self, *_a: Any, **_k: Any) -> None:
        pass

    def __enter__(self) -> FakeDeviceClient:
        return self

    def __exit__(self, *_a: Any) -> bool:
        return False

    def post(self, path: str, json: dict[str, Any] | None = None) -> FakeResponse:
        if path == "/auth/device/code":
            return FakeResponse(
                200,
                {
                    "device_code": "dev",
                    "user_code": "USER-CODE",
                    "verification_uri": "https://github.com/login/device",
                    "interval": 0,
                    "expires_in": 900,
                },
            )
        return FakeResponse(
            200, {"access_token": "AT", "refresh_token": "RT", "expires_in": 900}
        )


def test_device_login_persists_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    persisted: list[str] = []
    monkeypatch.setattr(session, "save_refresh_token", lambda _t: None)
    monkeypatch.setattr(session, "save_api_url", lambda url: persisted.append(url))
    monkeypatch.setattr(session.click, "launch", lambda *_a, **_k: 0)
    monkeypatch.setattr(session.click, "echo", lambda *_a, **_k: None)
    monkeypatch.setattr(session.time, "sleep", lambda *_a: None)
    monkeypatch.setattr(session.httpx, "Client", FakeDeviceClient)

    session.device_login(Config(api_url="https://prod.example", token=None))

    assert persisted == [
        "https://prod.example"
    ]  # login records the endpoint as default
