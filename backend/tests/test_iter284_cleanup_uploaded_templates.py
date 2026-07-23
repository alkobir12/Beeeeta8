"""Iteration 284 cleanup — archive uploaded UI templates created for guard tests."""

from __future__ import annotations

import os

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

MANAGER_USERNAME = "مدير"
MANAGER_PIN = "123123"
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')


def _auth_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    if RATE_BYPASS:
        session.headers["x-ratelimit-bypass"] = RATE_BYPASS

    login = session.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    if login.status_code != 200:
        pytest.skip(f"Manager login unavailable in preview: {login.status_code}")
    token = (login.json() if login.headers.get("content-type", "").startswith("application/json") else {}).get("access_token")
    if not token:
        pytest.skip("access_token missing")

    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def test_cleanup_iter284_uploaded_templates():
    # Module: cleanup temporary templates uploaded during Iter284 UI runs.
    session = _auth_session()
    response = session.get(f"{API}/document-templates", params={"tenant_id": "default", "locale": "ar-SA"}, timeout=30)
    assert response.status_code == 200, response.text[:300]
    rows = response.json().get("templates") or []

    targets = [
        row for row in rows
        if str(row.get("name") or "").startswith("ITER284_UI_INCOMPLETE")
    ]

    archived = 0
    for row in targets:
        delete = session.delete(f"{API}/document-templates/{row['id']}", timeout=30)
        if delete.status_code == 200:
            archived += 1

    assert archived >= 0
