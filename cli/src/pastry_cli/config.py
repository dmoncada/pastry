"""Config resolution with clig.dev precedence: flags > env > config file > defaults.

Config file lives under the XDG config dir (``~/.config/pastry/config.toml``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_API_URL = "http://localhost:8080"


def config_dir() -> Path:
    """Return the XDG config directory for pastry (``$XDG_CONFIG_HOME/pastry``)."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "pastry"


@dataclass(frozen=True)
class Config:
    """Resolved runtime configuration for a CLI invocation."""

    api_url: str
    token: str | None  # explicit PASTRY_TOKEN override; None -> use keychain

    @classmethod
    def resolve(cls, *, api_url_flag: str | None = None) -> Config:
        """Resolve config from (in priority order) flags, env, config file, defaults.

        TODO: read the config file layer (``config_dir()/config.toml``) between env and
        defaults once login persists a default api_url there.
        """
        api_url = api_url_flag or os.environ.get("PASTRY_API_URL") or _DEFAULT_API_URL
        token = os.environ.get("PASTRY_TOKEN")
        return cls(api_url=api_url, token=token)
