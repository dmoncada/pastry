"""Token storage: OS keychain via ``keyring``, falling back to the XDG config dir.

Per ``spec.md``, the *refresh* token is what we persist; the short-lived access JWT is
held only in memory and re-minted on demand. ``PASTRY_TOKEN`` (env) overrides everything.
"""

from __future__ import annotations

import keyring
from keyring.errors import KeyringError

from pastry_cli.config import config_dir

_SERVICE = "pastry"
_REFRESH_KEY = "refresh_token"


def _fallback_path() -> str:
    return str(config_dir() / "refresh_token")


def save_refresh_token(token: str) -> None:
    """Persist the refresh token in the keychain (fallback: XDG config file)."""
    try:
        keyring.set_password(_SERVICE, _REFRESH_KEY, token)
    except KeyringError:
        path = config_dir()
        path.mkdir(parents=True, exist_ok=True)
        (path / "refresh_token").write_text(token, encoding="utf-8")


def load_refresh_token() -> str | None:
    """Return the stored refresh token, or None if not logged in."""
    try:
        token = keyring.get_password(_SERVICE, _REFRESH_KEY)
        if token is not None:
            return token
    except KeyringError:
        pass
    from pathlib import Path

    file = Path(_fallback_path())
    return file.read_text(encoding="utf-8").strip() if file.exists() else None


def clear_refresh_token() -> None:
    """Remove any stored refresh token (used by ``pastry logout``)."""
    try:
        keyring.delete_password(_SERVICE, _REFRESH_KEY)
    except KeyringError:
        pass
    from pathlib import Path

    file = Path(_fallback_path())
    file.unlink(missing_ok=True)
