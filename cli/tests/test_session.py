"""Tests for access-token resolution (the per-call refresh-rotation dance)."""

from __future__ import annotations

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
            200, {"access_token": "AT", "refresh_token": "NEW"}
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
