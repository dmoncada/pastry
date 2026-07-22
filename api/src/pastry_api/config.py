"""Runtime configuration, loaded from environment variables (12-factor)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SIGNING_KEY = "dev-insecure-key"


class Settings(BaseSettings):
    """Backend settings. All fields are overridable via ``PASTRY_*`` env vars."""

    # populate_by_name: the aliased github_* fields below are otherwise settable only by
    # their alias, so Settings(github_oauth_client_id=...) would silently no-op.
    model_config = SettingsConfigDict(
        env_prefix="PASTRY_", env_file=".env", extra="ignore", populate_by_name=True
    )

    table_name: str = "pastry"
    # None -> use the real AWS endpoint; set to http://localhost:8000 for dynamodb-local.
    ddb_endpoint: str | None = None
    aws_region: str = "us-west-2"

    # Browser origins allowed to call the API (the web app). Prod adds the CloudFront domain.
    # From env, provide as JSON, e.g. PASTRY_CORS_ORIGINS='["https://pastry.example.com"]'.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Auth: "dev" injects a fixed stub user; "github" uses the real OAuth flows (slice 3).
    # Literal, not str: a typo'd PASTRY_AUTH_MODE=githb would otherwise fall through to
    # the "not dev" branch quietly, or worse, a typo'd "dev" would disable auth outright.
    auth_mode: Literal["dev", "github"] = "dev"
    jwt_signing_key: str = _DEV_SIGNING_KEY
    access_token_ttl: int = 900  # seconds (~15 min)
    refresh_token_ttl: int = 2_592_000  # seconds (30 days)

    # Refresh-token cookie (web client only; the CLI carries the token in the request body).
    # Secure is off for local http and set true in prod (HTTPS). SameSite=Lax is safe because
    # the API is served same-origin with the SPA (under /api via CloudFront), so the cookie
    # is first-party — no third-party-cookie fragility, and Lax blocks cross-site POSTs.
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # GitHub's conventional env-var names, exempt from the PASTRY_ prefix.
    github_oauth_client_id: str = Field(
        default="", validation_alias=AliasChoices("GITHUB_OAUTH_CLIENT_ID")
    )
    github_oauth_client_secret: str = Field(
        default="", validation_alias=AliasChoices("GITHUB_OAUTH_CLIENT_SECRET")
    )

    @model_validator(mode="after")
    def _reject_dev_defaults_in_github_mode(self) -> Self:
        """Fail fast rather than serving real traffic with development credentials.

        The defaults here are deliberately permissive so tests and local work need no
        setup, which means a deploy that forgets ``PASTRY_JWT_SIGNING_KEY`` would sign
        tokens with a key published in this repo. Crashing at startup is the only
        failure mode that cannot be missed.
        """
        if self.auth_mode == "github" and self.jwt_signing_key == _DEV_SIGNING_KEY:
            raise ValueError(
                "PASTRY_JWT_SIGNING_KEY is still the development default; "
                "set a real secret when PASTRY_AUTH_MODE=github"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return process-wide settings (cached; Lambda reuses across warm invocations)."""
    return Settings()
