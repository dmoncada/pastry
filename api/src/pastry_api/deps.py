"""FastAPI dependencies — primarily authentication.

In ``auth_mode == "dev"`` a fixed stub user is injected so routes can be exercised without
GitHub. In "github" mode the Bearer access JWT is verified and its ``github_id`` returned.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from pastry_api.config import Settings, get_settings
from pastry_api.security import InvalidToken, decode_access_token

_DEV_USER_GITHUB_ID = "dev-user"


def current_user_id(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Return the authenticated user's ``github_id``, or raise 401."""
    if settings.auth_mode == "dev":
        return _DEV_USER_GITHUB_ID

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(authorization.removeprefix("Bearer "), settings)
    except InvalidToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


CurrentUserId = Annotated[str, Depends(current_user_id)]
