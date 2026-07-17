"""Runtime configuration, loaded from environment variables (12-factor)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    aws_region: str = "us-east-1"

    # Browser origins allowed to call the API (the web app). Prod adds the CloudFront domain.
    # From env, provide as JSON, e.g. PASTRY_CORS_ORIGINS='["https://pastry.example.com"]'.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Auth: "dev" injects a fixed stub user; "github" uses the real OAuth flows (slice 3).
    auth_mode: str = "dev"
    jwt_signing_key: str = "dev-insecure-key"
    access_token_ttl: int = 900  # seconds (~15 min)
    refresh_token_ttl: int = 2_592_000  # seconds (30 days)

    # GitHub's conventional env-var names, exempt from the PASTRY_ prefix.
    github_oauth_client_id: str = Field(
        default="", validation_alias=AliasChoices("GITHUB_OAUTH_CLIENT_ID")
    )
    github_oauth_client_secret: str = Field(
        default="", validation_alias=AliasChoices("GITHUB_OAUTH_CLIENT_SECRET")
    )


@lru_cache
def get_settings() -> Settings:
    """Return process-wide settings (cached; Lambda reuses across warm invocations)."""
    return Settings()
