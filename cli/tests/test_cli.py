"""CLI tests: arg/stdin parsing, stdout/stderr split, exit codes, aliases.

The API client is faked so these exercise CLI behavior only (no network). End-to-end
against the real backend is covered by the live smoke in the slice-2 verification."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from click.testing import CliRunner
from pastry_cli import cli
from pastry_cli.api import ApiError
from pastry_shared.models import Paste

_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


def make_paste(slug: str, content: str, expires_at: datetime | None = None) -> Paste:
    """Build a fully-populated :class:`Paste`, as the real API would return."""
    return Paste(
        slug=slug,
        content=content,
        owner_github_id="42",
        created_at=_EPOCH,
        updated_at=_EPOCH,
        expires_at=expires_at,
        size=len(content),
    )


class FakeClient:
    def __init__(self) -> None:
        self.created: tuple[str, str | None] | None = None
        self.edited: tuple[str, str] | None = None
        self.deleted: str | None = None
        self.raw = "raw paste body"
        self.listing: list[Paste] = [
            make_paste("AAA", "first line\nsecond"),
            make_paste(
                "BBB", "ephemeral", expires_at=datetime(2026, 7, 17, tzinfo=UTC)
            ),
        ]
        self.error: ApiError | None = None

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def _maybe_raise(self) -> None:
        if self.error is not None:
            raise self.error

    def create(self, content: str, expire: str | None = None) -> Paste:
        self._maybe_raise()
        self.created = (content, expire)
        return make_paste("NEWSLUG", content)

    def get_raw(self, slug: str) -> str:
        self._maybe_raise()
        return self.raw

    def list(self) -> list[Paste]:  # ty: ignore[invalid-type-form]
        self._maybe_raise()
        return self.listing

    def edit(self, slug: str, content: str) -> Paste:
        self._maybe_raise()
        self.edited = (slug, content)
        return make_paste(slug, content)

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
    assert json.loads(result.stdout) == [
        p.model_dump(mode="json") for p in fake.listing
    ]


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
