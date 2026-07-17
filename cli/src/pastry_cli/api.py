"""Thin HTTP client wrapping the Pastry API."""

from __future__ import annotations

from types import TracebackType
from typing import Any, cast

import httpx

from pastry_cli.config import Config


class ApiError(Exception):
    """A non-2xx response or a transport failure, carrying an optional status code."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _error_detail(resp: httpx.Response) -> str:
    """Extract a human message from an error response (FastAPI's ``detail``, else text)."""
    if resp.status_code == 404:
        return "paste not found"
    try:
        detail = resp.json().get("detail")
    except Exception:
        detail = None
    if isinstance(detail, str):
        return detail
    return f"request failed with status {resp.status_code}"


class ApiClient:
    """HTTP client bound to a resolved :class:`Config`.

    Attaches ``Authorization: Bearer`` when a token is configured (dev-mode backend
    ignores it; real tokens arrive in slice 3). Raises :class:`ApiError` on any failure.
    """

    def __init__(self, config: Config, access_token: str | None = None) -> None:
        token = access_token or config.token
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=config.api_url, headers=headers, timeout=10.0
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            resp = self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise ApiError(
                f"could not reach API at {self._client.base_url}: {exc}"
            ) from exc
        if resp.status_code >= 400:
            raise ApiError(_error_detail(resp), resp.status_code)
        return resp

    def create(self, content: str, expire: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"content": content}
        if expire is not None:
            body["expires_in"] = expire
        return cast(dict[str, Any], self._request("POST", "/pastes", json=body).json())

    def list(self) -> list[dict[str, Any]]:  # ty: ignore[invalid-type-form]
        return cast(list[dict[str, Any]], self._request("GET", "/pastes").json())

    def get(self, slug: str) -> dict[str, Any]:
        return cast(dict[str, Any], self._request("GET", f"/p/{slug}").json())

    def get_raw(self, slug: str) -> str:
        return self._request("GET", f"/p/{slug}/raw").text

    def edit(self, slug: str, content: str) -> dict[str, Any]:
        resp = self._request("PATCH", f"/p/{slug}", json={"content": content})
        return cast(dict[str, Any], resp.json())

    def delete(self, slug: str) -> None:
        self._request("DELETE", f"/p/{slug}")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
