"""Config resolution with clig.dev precedence: flags > env > config file > defaults.

Config file lives under the XDG config dir (``~/.config/pastry/config.toml``).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_API_URL = "http://localhost:5173/api"


def config_dir() -> Path:
    """Return the XDG config directory for pastry (``$XDG_CONFIG_HOME/pastry``)."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "pastry"


def _config_file() -> Path:
    """Path to the persisted config file (``<config dir>/config.toml``)."""
    return config_dir() / "config.toml"


def _read_config_file() -> dict[str, str]:
    """Parse ``config.toml`` into a flat str->str map (empty if absent or unreadable)."""
    try:
        text = _config_file().read_text()
    except OSError:
        return {}
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}
    return {key: value for key, value in data.items() if isinstance(value, str)}


def _escape_toml_str(value: str) -> str:
    """Escape a value for a TOML basic string (backslash and double-quote)."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def save_api_url(api_url: str) -> None:
    """Persist ``api_url`` as the CLI's default endpoint in ``config.toml``.

    Merges into any existing keys so unrelated settings survive a rewrite.
    """
    data = _read_config_file()
    data["api_url"] = api_url
    body = "".join(
        f'{key} = "{_escape_toml_str(value)}"\n' for key, value in sorted(data.items())
    )
    path = _config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


@dataclass(frozen=True)
class Config:
    """Resolved runtime configuration for a CLI invocation."""

    api_url: str
    token: str | None  # explicit PASTRY_TOKEN override; None -> use keychain

    @classmethod
    def resolve(cls, *, api_url_flag: str | None = None) -> Config:
        """Resolve config from (in priority order) flags, env, config file, defaults."""
        file_config = _read_config_file()
        api_url = (
            api_url_flag
            or os.environ.get("PASTRY_API_URL")
            or file_config.get("api_url")
            or _DEFAULT_API_URL
        )
        token = os.environ.get("PASTRY_TOKEN")
        return cls(api_url=api_url, token=token)
