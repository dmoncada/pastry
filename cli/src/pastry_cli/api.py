"""Thin HTTP client wrapping the Pastry API."""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx
from pastry_shared.models import Paste, PasteCreate, PasteUpdate
from pydantic import TypeAdapter, ValidationError

from pastry_cli.config import Config

PASTE_LIST = TypeAdapter(list[Paste])


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


def _parse[T](model: type[T] | TypeAdapter[T], resp: httpx.Response) -> T:
    """Validate a response body into a shared model, or raise :class:`ApiError`.

    A 2xx whose shape we don't recognise means the CLI and API disagree; surface that as
    a normal API error rather than letting a pydantic traceback reach the user.
    """
    adapter = model if isinstance(model, TypeAdapter) else TypeAdapter(model)
    try:
        return adapter.validate_json(resp.content)
    except ValidationError as exc:
        raise ApiError(
            f"unexpected response from {resp.request.url} "
            f"({exc.error_count()} field(s) invalid)"
        ) from exc


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

    def _request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> httpx.Response:
        try:
            resp = self._client.request(method, path, json=json)
        except httpx.RequestError as exc:
            raise ApiError(
                f"could not reach API at {self._client.base_url}: {exc}"
            ) from exc
        if resp.status_code >= 400:
            raise ApiError(_error_detail(resp), resp.status_code)
        return resp

    def create(self, content: str, expire: str | None = None) -> Paste:
        body = PasteCreate(content=content, expires_in=expire)
        resp = self._request("POST", "/pastes", json=body.model_dump(mode="json"))
        return _parse(Paste, resp)

    def list(self) -> list[Paste]:  # ty: ignore[invalid-type-form]
        return _parse(PASTE_LIST, self._request("GET", "/pastes"))

    def get(self, slug: str) -> Paste:
        return _parse(Paste, self._request("GET", f"/pastes/{slug}"))

    def get_raw(self, slug: str) -> str:
        # The configured endpoint ends in /api, but raw content intentionally lives at
        # the frontend origin's sibling /raw namespace.
        api_url = str(self._client.base_url).rstrip("/")
        raw_url = f"{api_url.removesuffix('/api')}/raw/{slug}"
        return self._request("GET", raw_url).text

    def edit(self, slug: str, content: str) -> Paste:
        body = PasteUpdate(content=content)
        resp = self._request(
            "PATCH", f"/pastes/{slug}", json=body.model_dump(mode="json")
        )
        return _parse(Paste, resp)

    def delete(self, slug: str) -> None:
        self._request("DELETE", f"/pastes/{slug}")

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
