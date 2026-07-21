"""Auth endpoints — GitHub OAuth (web auth-code, CLI device flow) + token lifecycle.

The web callback returns the token pair as JSON for the MVP (a production web client would
instead receive an HttpOnly refresh cookie + a redirect). CSRF ``state`` is generated and
returned but full round-trip validation is a web-client concern deferred to slice 4."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pastry_shared.models import DeviceAuthResponse, TokenPair
from pydantic import BaseModel

from pastry_api import auth_repo, auth_service
from pastry_api.config import Settings, get_settings
from pastry_api.deps import CurrentUserId
from pastry_api.github import GitHubAuth, GitHubClient, GitHubError
from pastry_api.security import InvalidToken

router = APIRouter(prefix="/auth", tags=["auth"])


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
def github_login(github: GitHub) -> dict[str, str]:
    """Web: begin the GitHub authorization-code flow (returns the redirect URL + state)."""
    state = secrets.token_urlsafe(16)
    return {"authorize_url": github.build_authorize_url(state), "state": state}


@router.get("/github/callback")
def github_callback(
    code: str, state: str, github: GitHub, settings: Config
) -> TokenPair:
    """Web: exchange the auth code, verify identity, issue our token pair."""
    try:
        gh_token = github.exchange_code(code)
        profile = github.fetch_user(gh_token)
    except GitHubError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _authenticate(profile, settings)


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


@router.post("/refresh")
def refresh(body: RefreshRequest, settings: Config) -> TokenPair:
    """Rotate the refresh token (single-use) and mint a fresh access JWT."""
    try:
        return auth_service.rotate_refresh(body.refresh_token, settings)
    except InvalidToken as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid refresh token"
        ) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest) -> Response:
    """Revoke the refresh token server-side (delete its row)."""
    auth_service.revoke_refresh(body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user_id: CurrentUserId) -> dict[str, str]:
    """Return the authenticated user's identity (for the web app's sign-in state)."""
    user = auth_repo.get_user(user_id)
    return {"github_id": user_id, "login": user.login if user else user_id}
