"""CLI tests: arg/stdin parsing, stdout/stderr split, exit codes, aliases.

The API client is faked so these exercise CLI behavior only (no network). End-to-end
against the real backend is covered by the live smoke in the slice-2 verification."""

from __future__ import annotations

from typing import Any

import pytest
from click.testing import CliRunner
from pastry_cli import cli
from pastry_cli.api import ApiError


class FakeClient:
    def __init__(self) -> None:
        self.created: tuple[str, str | None] | None = None
        self.edited: tuple[str, str] | None = None
        self.deleted: str | None = None
        self.raw = "raw paste body"
        self.listing: list[dict[str, Any]] = [
            {"slug": "AAA", "content": "first line\nsecond", "expires_at": None},
            {
                "slug": "BBB",
                "content": "ephemeral",
                "expires_at": "2026-07-17T00:00:00+00:00",
            },
        ]
        self.error: ApiError | None = None

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def _maybe_raise(self) -> None:
        if self.error is not None:
            raise self.error

    def create(self, content: str, expire: str | None = None) -> dict[str, Any]:
        self._maybe_raise()
        self.created = (content, expire)
        return {"slug": "NEWSLUG", "content": content}

    def get_raw(self, slug: str) -> str:
        self._maybe_raise()
        return self.raw

    def list(self) -> list[dict[str, Any]]:  # ty: ignore[invalid-type-form]
        self._maybe_raise()
        return self.listing

    def edit(self, slug: str, content: str) -> dict[str, Any]:
        self._maybe_raise()
        self.edited = (slug, content)
        return {"slug": slug, "content": content}

    def delete(self, slug: str) -> None:
        self._maybe_raise()
        self.deleted = slug


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    client = FakeClient()
    monkeypatch.setattr(cli, "_client", lambda config: client)
    return client


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_create_from_arg_prints_slug(fake: FakeClient, runner: CliRunner) -> None:
    result = runner.invoke(cli.main, ["create", "hello"])
    assert result.exit_code == 0
    assert result.stdout == "NEWSLUG\n"  # stdout is data only
    assert fake.created == ("hello", None)


def test_create_from_stdin(fake: FakeClient, runner: CliRunner) -> None:
    result = runner.invoke(cli.main, ["create"], input="piped body")
    assert result.exit_code == 0
    assert fake.created == ("piped body", None)


def test_create_with_expire(fake: FakeClient, runner: CliRunner) -> None:
    runner.invoke(cli.main, ["create", "x", "--expire", "1d"])
    assert fake.created == ("x", "1d")


def test_get_writes_raw_without_extra_newline(
    fake: FakeClient, runner: CliRunner
) -> None:
    result = runner.invoke(cli.main, ["get", "AAA"])
    assert result.exit_code == 0
    assert result.stdout == "raw paste body"


def test_list_json(fake: FakeClient, runner: CliRunner) -> None:
    import json

    result = runner.invoke(cli.main, ["list", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == fake.listing


def test_list_human_shows_slugs_and_preview(
    fake: FakeClient, runner: CliRunner
) -> None:
    result = runner.invoke(cli.main, ["list"])
    assert result.exit_code == 0
    assert "AAA" in result.stdout
    assert "first line" in result.stdout
    assert "second" not in result.stdout  # only the first line previews
    assert "expires 2026-07-17" in result.stdout


def test_ls_alias(fake: FakeClient, runner: CliRunner) -> None:
    assert runner.invoke(cli.main, ["ls", "--json"]).exit_code == 0


def test_edit(fake: FakeClient, runner: CliRunner) -> None:
    result = runner.invoke(cli.main, ["edit", "AAA", "updated"])
    assert result.exit_code == 0
    assert fake.edited == ("AAA", "updated")
    assert "edited AAA" in result.stderr


def test_delete_force_skips_prompt(fake: FakeClient, runner: CliRunner) -> None:
    result = runner.invoke(cli.main, ["delete", "AAA", "--force"])
    assert result.exit_code == 0
    assert fake.deleted == "AAA"


def test_delete_confirm_abort_does_not_delete(
    fake: FakeClient, runner: CliRunner
) -> None:
    result = runner.invoke(cli.main, ["delete", "AAA"], input="n\n")
    assert result.exit_code != 0
    assert fake.deleted is None


def test_rm_alias_force(fake: FakeClient, runner: CliRunner) -> None:
    assert runner.invoke(cli.main, ["rm", "AAA", "--force"]).exit_code == 0
    assert fake.deleted == "AAA"


def test_api_error_goes_to_stderr_with_exit_1(
    fake: FakeClient, runner: CliRunner
) -> None:
    fake.error = ApiError("paste not found", 404)
    result = runner.invoke(cli.main, ["get", "MISSING"])
    assert result.exit_code == 1
    assert "paste not found" in result.stderr
    assert result.stdout == ""  # nothing on stdout for errors
