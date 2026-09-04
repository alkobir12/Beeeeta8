"""Iteration 374: Preview login + representative read-only endpoint regression."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests


# Module: environment resolution for preview URL/workshop id
def _read_frontend_env(key: str) -> str:
    env_path = Path("/app/frontend/.env")
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def _base_url() -> str:
    return (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env("REACT_APP_BACKEND_URL")).strip().rstrip("/")


def _workshop_id() -> str:
    return (os.environ.get("REACT_APP_WORKSHOP_ID") or _read_frontend_env("REACT_APP_WORKSHOP_ID")).strip()


BASE_URL = _base_url()
WORKSHOP_ID = _workshop_id()
MANAGER_USERNAME = "مدير"
MANAGER_PASSWORD = "010101"


@pytest.fixture(scope="session")
def api_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    return BASE_URL


@pytest.fixture()
def api_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture()
def auth_header(api_session: requests.Session, api_url: str) -> dict[str, str]:
    # Module: admin password login regression (no PIN-only path)
    resp = api_session.post(
        f"{api_url}/api/auth/login",
        json={"username": MANAGER_USERNAME, "password": MANAGER_PASSWORD},
        timeout=30,
    )
    assert resp.status_code == 200, resp.text[:400]
    data = resp.json()
    assert data.get("username") == MANAGER_USERNAME
    assert data.get("role") == "admin"
    token = data.get("access_token")
    assert isinstance(token, str) and token
    return {"Authorization": f"Bearer {token}"}


# Module: read-only representative data endpoints after successful login
@pytest.mark.parametrize(
    "path,params,expected_type",
    [
        ("/api/users", None, list),
        ("/api/vehicles", None, list),
        ("/api/customers", None, list),
        ("/api/accounts", None, list),
        ("/api/finance/journal-entries", {"workshop_id": WORKSHOP_ID, "limit": 100}, (list, dict)),
        ("/api/finance/reports/income-statement", {"workshop_id": WORKSHOP_ID}, dict),
    ],
)
def test_representative_read_endpoints_no_500(
    api_session: requests.Session,
    api_url: str,
    auth_header: dict[str, str],
    path: str,
    params: dict | None,
    expected_type: type | tuple[type, ...],
):
    if "workshop_id" in (params or {}) and not WORKSHOP_ID:
        pytest.skip("REACT_APP_WORKSHOP_ID missing")
    response = api_session.get(
        f"{api_url}{path}",
        params=params,
        headers=auth_header,
        timeout=45,
    )
    assert response.status_code == 200, f"{path} -> {response.status_code}: {response.text[:300]}"
    payload = response.json()
    assert isinstance(payload, expected_type)
    if path == "/api/finance/journal-entries" and isinstance(payload, dict):
        assert payload.get("success") is True
        assert isinstance(payload.get("data"), list)
        return
    if isinstance(payload, list):
        assert len(payload) >= 0
    if isinstance(payload, dict):
        assert len(payload.keys()) > 0
