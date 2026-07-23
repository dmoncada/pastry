"""Tests for config resolution precedence (flags > env > file > defaults) and persistence."""

from __future__ import annotations

from pathlib import Path

import pytest
from pastry_cli import config
from pastry_cli.config import Config


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the XDG config dir at a temp path and clear env overrides for each test."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("PASTRY_API_URL", raising=False)
    monkeypatch.delenv("PASTRY_TOKEN", raising=False)


def test_default_when_nothing_set() -> None:
    assert Config.resolve().api_url == "http://localhost:5173/api"


def test_env_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PASTRY_API_URL", "https://env.example")
    assert Config.resolve().api_url == "https://env.example"


def test_flag_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PASTRY_API_URL", "https://env.example")
    assert (
        Config.resolve(api_url_flag="https://flag.example").api_url
        == "https://flag.example"
    )


def test_file_layer_sits_between_env_and_default() -> None:
    config.save_api_url("https://file.example")
    assert Config.resolve().api_url == "https://file.example"


def test_env_beats_file(monkeypatch: pytest.MonkeyPatch) -> None:
    config.save_api_url("https://file.example")
    monkeypatch.setenv("PASTRY_API_URL", "https://env.example")
    assert Config.resolve().api_url == "https://env.example"


def test_save_api_url_overwrites_previous() -> None:
    config.save_api_url("https://one.example")
    config.save_api_url("https://two.example")
    assert Config.resolve().api_url == "https://two.example"


def test_save_api_url_preserves_other_keys() -> None:
    cfg_path = config.config_dir() / "config.toml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text('other = "keep-me"\napi_url = "https://old.example"\n')
    config.save_api_url("https://new.example")
    assert 'other = "keep-me"' in cfg_path.read_text()
    assert Config.resolve().api_url == "https://new.example"


def test_malformed_config_file_falls_back_to_default() -> None:
    cfg_path = config.config_dir() / "config.toml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text("this is not = valid = toml ===")
    assert Config.resolve().api_url == "http://localhost:5173/api"
