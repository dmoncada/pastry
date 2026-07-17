"""Test isolation: the suite must never see the developer's local configuration.

Both packages read ambient config by design (12-factor): the backend's ``Settings`` loads
``PASTRY_*`` env vars *and* a ``.env`` file, and the CLI's ``Config`` reads ``PASTRY_API_URL``
/ ``PASTRY_TOKEN``. So a machine configured per e2e.md — ``PASTRY_AUTH_MODE=github``,
``PASTRY_DDB_ENDPOINT`` pointing at dynamodb-local, an exported ``PASTRY_API_URL`` — would
silently change what the tests exercise, and fail suites that assume the defaults. CI only
passes because it has no ``.env``.

Both sources are neutralized here, at import time, before any Settings instance is built.
"""

from __future__ import annotations

import os

# Drop inherited config so os.environ looks like CI's.
for _name in [k for k in os.environ if k.startswith(("PASTRY_", "GITHUB_OAUTH_"))]:
    del os.environ[_name]

from pastry_api.config import Settings, get_settings  # noqa: E402

# Stop pydantic-settings reading the repo-root .env (see the module docstring).
Settings.model_config["env_file"] = None
get_settings.cache_clear()
