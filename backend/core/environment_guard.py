from __future__ import annotations

import os
from urllib.parse import urlparse


TEST_ENV_NAMES = {"test", "testing"}


def _project_ref(url: str) -> str:
    return (urlparse(url).hostname or "").split(".")[0].strip().lower()


def configure_database_environment() -> str:
    app_env = os.environ.get("APP_ENV")
    if not app_env:
        return "production"

    normalized = app_env.strip().lower()
    if normalized not in TEST_ENV_NAMES:
        return normalized

    production_url = os.environ.get("SUPABASE_URL")
    production_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    test_url = os.environ.get("SUPABASE_TEST_URL") or os.environ.get("SUPABASE_URL_TEST")
    test_key = (
        os.environ.get("SUPABASE_TEST_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY_TEST")
    )

    missing = [
        name
        for name, value in (
            ("SUPABASE_TEST_URL", test_url),
            ("SUPABASE_TEST_SERVICE_ROLE_KEY", test_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"test_database_credentials_missing:{','.join(missing)}")
    if not production_url or not production_key:
        raise RuntimeError("production_database_credentials_missing")
    if test_url == production_url or _project_ref(test_url) == _project_ref(production_url):
        raise RuntimeError("test_database_matches_production")
    if test_key == production_key:
        raise RuntimeError("test_service_role_key_matches_production")

    os.environ["SUPABASE_URL"] = test_url
    os.environ["SUPABASE_SERVICE_ROLE_KEY"] = test_key
    os.environ["DATABASE_ENVIRONMENT"] = "test"
    return "test"