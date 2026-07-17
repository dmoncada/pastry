"""Session logic: device-flow login, logout, and access-token resolution.

The CLI persists only the refresh token. On each authenticated call it exchanges that
refresh token for a short-lived access JWT via ``POST /auth/refresh`` — which rotates the
refresh token, so the new one is written back to the keychain."""

from __future__ import annotations

import time

import click
import httpx

from pastry_cli.auth import clear_refresh_token, load_refresh_token, save_refresh_token
from pastry_cli.config import Config, save_api_url


class LoginError(Exception):
    """Raised when the device-authorization flow fails or times out."""


def resolve_access_token(config: Config) -> str | None:
    """Return a usable access token, or None when not logged in.

    ``PASTRY_TOKEN`` (config.token) wins. Otherwise, if a refresh token is stored, rotate
    it for a fresh access token; a rejected refresh token is cleared (session is dead).
    """
    if config.token:
        return config.token
    raw = load_refresh_token()
    if raw is None:
        return None
    try:
        resp = httpx.post(
            f"{config.api_url.rstrip('/')}/auth/refresh",
            json={"refresh_token": raw},
            timeout=10.0,
        )
    except httpx.RequestError:
        return None
    if resp.status_code != 200:
        clear_refresh_token()
        return None
    data = resp.json()
    save_refresh_token(data["refresh_token"])
    return str(data["access_token"])


def device_login(config: Config) -> None:
    """Run the GitHub device-authorization grant and store the resulting refresh token."""
    base = config.api_url.rstrip("/")
    with httpx.Client(base_url=base, timeout=15.0) as client:
        try:
            start = client.post("/auth/device/code")
        except httpx.RequestError as exc:
            raise LoginError(f"could not reach the API at {base}") from exc
        if start.status_code != 200:
            raise LoginError(_detail(start))
        flow = start.json()

        click.echo(
            f"Open {flow['verification_uri']} and enter code: "
            f"{click.style(flow['user_code'], bold=True)}",
            err=True,
        )
        click.launch(flow["verification_uri"])

        interval = int(flow.get("interval", 5))
        deadline = time.monotonic() + int(flow.get("expires_in", 900))
        while time.monotonic() < deadline:
            time.sleep(interval)
            resp = client.post(
                "/auth/device/token", json={"device_code": flow["device_code"]}
            )
            if resp.status_code == 200:
                save_refresh_token(resp.json()["refresh_token"])
                save_api_url(
                    config.api_url
                )  # make this endpoint the default for next time
                return
            if resp.status_code == 428:  # authorization_pending
                continue
            raise LoginError(_detail(resp))
        raise LoginError("device code expired before authorization")


def logout(config: Config) -> None:
    """Revoke the stored refresh token server-side (best effort) and clear it locally."""
    raw = load_refresh_token()
    if raw is not None:
        try:
            httpx.post(
                f"{config.api_url.rstrip('/')}/auth/logout",
                json={"refresh_token": raw},
                timeout=10.0,
            )
        except httpx.RequestError:
            pass  # revoke is best-effort; always clear locally
    clear_refresh_token()


def _detail(resp: httpx.Response) -> str:
    try:
        detail = resp.json().get("detail")
    except Exception:
        detail = None
    return detail if isinstance(detail, str) else f"login failed ({resp.status_code})"
