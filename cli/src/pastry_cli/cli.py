"""The ``pastry`` command group.

clig.dev conventions (see ``spec.md``):
- stdout is data only (pipeable); errors/notices go to stderr with meaningful exit codes.
- Human output by default; ``--json`` for machines. Color only on a TTY; respect NO_COLOR.
- Config precedence flags > env > file > defaults, resolved in :mod:`pastry_cli.config`.

"""

from __future__ import annotations

import functools
import os
import sys
from collections.abc import Callable
from typing import ClassVar, NoReturn

import click
from pydantic import ValidationError

from pastry_cli import session
from pastry_cli.api import PASTE_LIST, ApiClient, ApiError
from pastry_cli.config import Config
from pastry_cli.session import LoginError


def _fail(message: str, code: int = 1) -> NoReturn:
    """Print an error to stderr and exit non-zero."""
    click.echo(f"pastry: {message}", err=True)
    raise SystemExit(code)


def _color_enabled() -> bool:
    """Color only when stdout is a TTY and NO_COLOR is unset (clig.dev)."""
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _styled_slug(slug: str) -> str:
    return click.style(slug, fg="cyan") if _color_enabled() else slug


def _read_content(text: str | None) -> str:
    """Resolve paste content from an argument or piped stdin, or fail."""
    if text is not None:
        return text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    _fail("no content provided (pass an argument or pipe via stdin)")


def _client(config: Config) -> ApiClient:
    return ApiClient(config, access_token=session.resolve_access_token(config))


def _share_url(api_url: str, slug: str) -> str:
    """Map a canonical frontend ``/api`` endpoint to its viewer URL."""
    endpoint = api_url.rstrip("/")
    return f"{endpoint.removesuffix('/api')}/{slug}"


def handle_api_errors[**P, T](fn: Callable[P, T]) -> Callable[P, T]:
    """Turn an :class:`ApiError` into a clean stderr message + non-zero exit."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return fn(*args, **kwargs)
        except ApiError as exc:
            _fail(str(exc))
        except ValidationError as exc:
            # Request models are built client-side, so bounds like the paste size limit
            # reject here rather than at the API. Report the reason, not a traceback.
            reasons = "; ".join(e["msg"] for e in exc.errors())
            _fail(reasons or str(exc))

    return wrapper


class AliasedGroup(click.Group):
    """Group that resolves command aliases (e.g. ``ls`` -> ``list``, ``rm`` -> ``delete``)."""

    _ALIASES: ClassVar[dict[str, str]] = {"ls": "list", "rm": "delete"}

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        return super().get_command(ctx, self._ALIASES.get(cmd_name, cmd_name))


@click.group(cls=AliasedGroup)
@click.option(
    "--api-url",
    envvar="PASTRY_API_URL",
    default=None,
    help="Override the API endpoint (also PASTRY_API_URL).",
)
@click.version_option()
@click.pass_context
def main(ctx: click.Context, api_url: str | None) -> None:
    """pastry — a pastebin at your terminal."""
    ctx.obj = Config.resolve(api_url_flag=api_url)


@main.command()
@click.pass_obj
def login(config: Config) -> None:
    """Authenticate via the GitHub device flow."""
    try:
        session.device_login(config)
    except LoginError as exc:
        _fail(str(exc))
    click.echo("logged in", err=True)


@main.command()
@click.pass_obj
def logout(config: Config) -> None:
    """Log out and revoke the stored refresh token server-side."""
    session.logout(config)
    click.echo("logged out", err=True)


@main.command()
@click.argument("text", required=False)
@click.option(
    "--expire",
    type=click.Choice(["1h", "1d", "1w"]),
    default=None,
    help="Optional TTL; omit for never.",
)
@click.pass_obj
@handle_api_errors
def create(config: Config, text: str | None, expire: str | None) -> None:
    """Create a paste from TEXT or stdin; prints the new slug."""
    content = _read_content(text)
    with _client(config) as api:
        paste = api.create(content, expire)
    slug = paste.slug
    click.echo(slug)  # stdout: the data (pipeable)
    if sys.stdout.isatty():
        click.echo(f"→ {_share_url(config.api_url, slug)}", err=True)


@main.command()
@click.argument("id")
@click.pass_obj
@handle_api_errors
def get(config: Config, id: str) -> None:
    """Print a paste by slug to stdout (pipeable)."""
    with _client(config) as api:
        content = api.get_raw(id)
    sys.stdout.write(content)  # faithful: no extra newline


@main.command()
@click.argument("id")
@click.argument("text", required=False)
@click.pass_obj
@handle_api_errors
def edit(config: Config, id: str, text: str | None) -> None:
    """Replace a paste's content from TEXT or stdin (owner only)."""
    content = _read_content(text)
    with _client(config) as api:
        api.edit(id, content)
    click.echo(f"edited {id}", err=True)


@main.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON for scripting.")
@click.pass_obj
@handle_api_errors
def list_(config: Config, as_json: bool) -> None:
    """List your pastes (alias: ls)."""
    with _client(config) as api:
        pastes = api.list()
    if as_json:
        click.echo(PASTE_LIST.dump_json(pastes, indent=2).decode())
        return
    if not pastes:
        click.echo("no pastes yet", err=True)
        return
    for paste in pastes:
        preview = paste.content.splitlines()[0] if paste.content else ""
        if len(preview) > 50:
            preview = preview[:49] + "…"
        line = f'{_styled_slug(paste.slug)}  "{preview}"'
        if paste.expires_at is not None:
            line += f"  (expires {paste.expires_at:%Y-%m-%d %H:%M})"
        click.echo(line)


@main.command()
@click.argument("id")
@click.option("--force", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_obj
@handle_api_errors
def delete(config: Config, id: str, force: bool) -> None:
    """Delete a paste by slug (alias: rm; owner only)."""
    if not force:
        click.confirm(f"Delete {id}?", abort=True, err=True)
    with _client(config) as api:
        api.delete(id)
    click.echo(f"deleted {id}", err=True)


if __name__ == "__main__":
    main()
