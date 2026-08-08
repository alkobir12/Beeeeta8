"""Iteration 335 probe: login + operations list availability on public preview URL."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import requests


def _load_base_url() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if base:
        return base.rstrip("/")

    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    pytest.fail("REACT_APP_BACKEND_URL missing (env + frontend/.env).")


def _load_test_credential(field: str) -> str:
    env_key = f"TEST_MANAGER_{field.upper()}"
    value = os.environ.get(env_key, "").strip()
    if value:
        return value

    path = Path("/app/memory/test_credentials.md")
    if not path.exists():
        pytest.fail(f"{env_key} missing and /app/memory/test_credentials.md unavailable.")
    text = path.read_text(encoding="utf-8")
    if field == "username":
        match = re.search(r"\| `([^`]+)`\s+\| admin\s+\|", text)
    else:
        match = re.search(r"admin\s+\|[^\n]+quick PIN `([^`]+)`", text)
    if not match:
        pytest.fail(f"Unable to load manager {field} from test_credentials.md")
    return match.group(1).strip()


BASE_URL = _load_base_url()


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth_headers(api_client: requests.Session) -> dict:
    username = _load_test_credential("username")
    pin = _load_test_credential("pin")
    resp = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "pin": pin, "remember_device": False},
        timeout=20,
    )
    assert resp.status_code == 200, f"manager login failed: {resp.status_code} {resp.text[:200]}"
    data = resp.json()
    token = data.get("access_token")
    assert isinstance(token, str) and token, "access_token missing"
    return {"Authorization": f"Bearer {token}"}


# operations list probe for preview data availability
def test_operations_list_endpoint_returns_array(api_client: requests.Session, auth_headers: dict):
    resp = api_client.get(
        f"{BASE_URL}/api/operations",
        params={"limit": 200},
        headers=auth_headers,
        timeout=25,
    )
    assert resp.status_code == 200, f"operations endpoint failed: {resp.status_code} {resp.text[:180]}"
    payload = resp.json()
    assert isinstance(payload, list), "operations response must be an array"
    assert len(payload) > 0, "operations endpoint returned empty list on preview"
