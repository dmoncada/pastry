"""Canonical request paths used by the CLI HTTP client."""

from __future__ import annotations

from typing import Any, ClassVar

import httpx
import pytest
from pastry_cli.api import ApiClient
from pastry_cli.config import Config


class RecordingClient:
    paths: ClassVar[list[tuple[str, str]]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.base_url = kwargs["base_url"]

    def request(self, method: str, path: str, **_kwargs: Any) -> httpx.Response:
        self.paths.append((method, path))
        request = httpx.Request(method, f"https://pastry.example/api{path}")
        if "/raw/" in path:
            return httpx.Response(200, content=b"raw", request=request)
        if method == "DELETE":
            return httpx.Response(204, request=request)
        return httpx.Response(
            200,
            json={
                "slug": "0123456789ABCDEFGHJK",
                "content": "body",
                "owner_github_id": "user",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "expires_at": None,
                "size": 4,
            },
            request=request,
        )

    def close(self) -> None:
        pass


def test_cli_uses_api_and_raw_canonical_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    RecordingClient.paths = []
    monkeypatch.setattr("pastry_cli.api.httpx.Client", RecordingClient)
    client = ApiClient(Config(api_url="https://pastry.example/api", token=None))

    client.get("0123456789ABCDEFGHJK")
    assert client.get_raw("0123456789ABCDEFGHJK") == "raw"
    client.edit("0123456789ABCDEFGHJK", "changed")
    client.delete("0123456789ABCDEFGHJK")

    assert RecordingClient.paths == [
        ("GET", "/pastes/0123456789ABCDEFGHJK"),
        ("GET", "https://pastry.example/raw/0123456789ABCDEFGHJK"),
        ("PATCH", "/pastes/0123456789ABCDEFGHJK"),
        ("DELETE", "/pastes/0123456789ABCDEFGHJK"),
    ]
