"""FastAPI dependencies — primarily authentication.

In ``auth_mode == "dev"`` a fixed stub user is injected so routes can be exercised without
GitHub. In "github" mode the Bearer access JWT is verified and its ``github_id`` returned.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pastry_api.config import Settings, get_settings
from pastry_api.security import InvalidToken, decode_access_token

_DEV_USER_GITHUB_ID = "dev-user"

# auto_error=False so dev mode can skip credentials entirely; the 401 for a missing token
# is raised below instead. Declaring the scheme is what puts the bearer requirement into
# the OpenAPI document, so /docs can authorize against protected routes.
_bearer = HTTPBearer(auto_error=False, description="Access JWT from /auth/*.")


def current_user_id(
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> str:
    """Return the authenticated user's ``github_id``, or raise 401."""
    if settings.auth_mode == "dev":
        return _DEV_USER_GITHUB_ID

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials, settings)
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUserId = Annotated[str, Depends(current_user_id)]
