"""Auth endpoints — GitHub OAuth (web auth-code, CLI device flow) + token lifecycle.

Two transports for the refresh token, one set of handlers:

* **Web** presents the refresh token via an ``HttpOnly; Secure; SameSite=Lax`` cookie and
  receives an access-only body, so its refresh token is never readable by JS. The callback
  and the cookie-path refresh set/rotate the cookie.
* **CLI** carries the refresh token in the request body and gets the full ``TokenPair``
  back, which it persists in the OS keychain.

``refresh``/``logout`` branch on which transport is present (body → CLI, otherwise cookie)."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pastry_shared.models import AccessTokenResponse, DeviceAuthResponse, TokenPair
from pydantic import BaseModel

from pastry_api import auth_repo, auth_service
from pastry_api.config import Settings, get_settings
from pastry_api.deps import CurrentUserId
from pastry_api.github import GitHubAuth, GitHubClient, GitHubError
from pastry_api.security import InvalidToken

router = APIRouter(prefix="/auth", tags=["auth"])

# The web client's refresh token lives in this cookie. Path-scoped to the auth endpoints so
# it is never sent on ordinary /api/pastes calls. Both browser and CLI use the /api mount;
# the CLI carries the refresh token in its request body instead of a cookie.
REFRESH_COOKIE_NAME = "pastry_refresh"
REFRESH_COOKIE_PATH = "/api/auth"
OAUTH_STATE_COOKIE_NAME = "pastry_oauth_state"
OAUTH_STATE_COOKIE_PATH = "/api/auth/github/callback"
OAUTH_STATE_TTL = 600


def _set_refresh_cookie(response: Response, raw: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw,
        max_age=settings.refresh_token_ttl,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


def _set_oauth_state_cookie(response: Response, state: str, settings: Settings) -> None:
    """Bind a short-lived OAuth state value to the browser that started login."""
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=state,
        max_age=OAUTH_STATE_TTL,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=OAUTH_STATE_COOKIE_PATH,
    )


def _clear_oauth_state_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        path=OAUTH_STATE_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _access_only(pair: TokenPair) -> AccessTokenResponse:
    """Drop the refresh token from a pair — it goes in the cookie, never the web body."""
    return AccessTokenResponse(
        access_token=pair.access_token,
        token_type=pair.token_type,
        expires_in=pair.expires_in,
    )


def get_github_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GitHubAuth:
    return GitHubClient(settings)


GitHub = Annotated[GitHubAuth, Depends(get_github_client)]
Config = Annotated[Settings, Depends(get_settings)]


class RefreshRequest(BaseModel):
    refresh_token: str


class DeviceTokenRequest(BaseModel):
    device_code: str


def _authenticate(profile: dict[str, object], settings: Settings) -> TokenPair:
    """Upsert the GitHub profile and issue our own token pair."""
    github_id = str(profile["id"])
    login = str(profile["login"])
    name = profile.get("name")
    auth_repo.upsert_user(github_id, login, str(name) if name is not None else None)
    return auth_service.issue_tokens(github_id, settings)


@router.get("/github/login")
def github_login(
    github: GitHub, settings: Config, response: Response
) -> dict[str, str]:
    """Web: begin the GitHub authorization-code flow (returns the redirect URL + state)."""
    state = secrets.token_urlsafe(16)
    _set_oauth_state_cookie(response, state, settings)
    return {"authorize_url": github.build_authorize_url(state), "state": state}


@router.get("/github/callback", response_model=AccessTokenResponse)
def github_callback(
    code: str,
    state: str,
    request: Request,
    github: GitHub,
    settings: Config,
    response: Response,
) -> AccessTokenResponse:
    """Validate browser-bound state, exchange the code, and issue web tokens."""
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE_NAME)
    _clear_oauth_state_cookie(response, settings)
    if expected_state is None or not secrets.compare_digest(expected_state, state):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "invalid OAuth state",
            headers={"Set-Cookie": response.headers["set-cookie"]},
        )
    try:
        gh_token = github.exchange_code(code)
        profile = github.fetch_user(gh_token)
    except GitHubError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            str(exc),
            headers={"Set-Cookie": response.headers["set-cookie"]},
        ) from exc
    pair = _authenticate(profile, settings)
    _set_refresh_cookie(response, pair.refresh_token, settings)
    return _access_only(pair)


@router.post("/device/code")
def device_code(github: GitHub) -> DeviceAuthResponse:
    """CLI: start the device-authorization grant; returns device + user codes."""
    try:
        return DeviceAuthResponse(**github.start_device_flow())
    except GitHubError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


@router.post("/device/token")
def device_token(
    body: DeviceTokenRequest, github: GitHub, settings: Config
) -> TokenPair:
    """CLI: poll for authorization; 428 while pending, token pair once approved."""
    try:
        gh_token = github.poll_device_token(body.device_code)
        if gh_token is None:
            raise HTTPException(
                status.HTTP_428_PRECONDITION_REQUIRED, "authorization_pending"
            )
        profile = github.fetch_user(gh_token)
    except GitHubError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _authenticate(profile, settings)


@router.post("/refresh", response_model=None)
def refresh(
    request: Request,
    response: Response,
    settings: Config,
    body: RefreshRequest | None = None,
) -> AccessTokenResponse | TokenPair:
    """Rotate the refresh token (single-use) and mint a fresh access JWT.

    CLI (body present) gets the full rotated pair back; web (cookie present) gets an
    access-only body plus the rotated cookie. A dead cookie is left as-is — it is a spent
    token, and the client drops its in-memory session on the 401.
    """
    from_cookie = body is None
    raw = (
        request.cookies.get(REFRESH_COOKIE_NAME) if from_cookie else body.refresh_token
    )
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing refresh token")
    try:
        pair = auth_service.rotate_refresh(raw, settings)
    except InvalidToken as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid refresh token"
        ) from exc
    if from_cookie:
        _set_refresh_cookie(response, pair.refresh_token, settings)
        return _access_only(pair)
    return pair


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, body: RefreshRequest | None = None) -> Response:
    """Revoke the refresh token server-side (delete its row); web clients also get the
    cookie cleared.
    """
    from_cookie = body is None
    raw = (
        request.cookies.get(REFRESH_COOKIE_NAME) if from_cookie else body.refresh_token
    )
    if raw:
        auth_service.revoke_refresh(raw)
    result = Response(status_code=status.HTTP_204_NO_CONTENT)
    if from_cookie:
        _clear_refresh_cookie(result)
    return result


@router.get("/me")
def me(user_id: CurrentUserId) -> dict[str, str]:
    """Return the authenticated user's identity (for the web app's sign-in state)."""
    user = auth_repo.get_user(user_id)
    return {"github_id": user_id, "login": user.login if user else user_id}
