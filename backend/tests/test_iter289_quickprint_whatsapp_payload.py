"""Iteration 289 — QuickPrint WhatsApp payload/resolve contract checks.

Modules/features covered:
- outbound resolve-message happy path with valid customer phone + vehicle plate
- outbound resolve-message behavior with missing phone (backend returns invalid phone)
"""

from __future__ import annotations

import os
import uuid

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


@pytest.fixture(scope="module")
def auth_session() -> requests.Session:
    """Authenticated session using manager quick PIN."""
    session = requests.Session()
    if RATE_BYPASS:
        session.headers["x-ratelimit-bypass"] = RATE_BYPASS

    login = session.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    if login.status_code != 200:
        pytest.skip(f"Manager login unavailable in preview: {login.status_code} {login.text[:120]}")

    payload = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
    token = payload.get("access_token")
    assert token, "access_token missing from login response"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def test_outbound_resolve_happy_path_no_missing_variables(auth_session: requests.Session):
    """Valid phone + plate path should return resolved message without missing variables."""
    payload = {
        "doc_type": "invoice",
        "status": "draft",
        "payload": {
            "settings": {
                "document_number": f"ITER289-{uuid.uuid4().hex[:6]}",
                "date": "2026-02-16",
            },
            "workshop": {
                "name": "ورشة الاختبار",
                "phone": "0555555555",
            },
            "customer": {
                "name": "عميل تجربة",
                "phone": "0501234567",
            },
            "vehicle": {
                "plateNumber": "أ ب ج 1234",
            },
            "items": [{"description": "فحص", "quantity": 1, "unit_price": 120}],
        },
    }

    response = auth_session.post(f"{API}/outbound/resolve-message", json=payload, timeout=30)
    assert response.status_code == 200, response.text[:300]
    data = response.json()

    assert data.get("success") is True
    assert isinstance(data.get("message"), str) and len(data.get("message", "")) > 0
    assert data.get("missing_variables") == []

    phone = data.get("phone") or {}
    assert phone.get("valid") is True
    assert phone.get("e164") == "+966501234567"


def test_outbound_resolve_missing_phone_marks_phone_invalid(auth_session: requests.Session):
    """Missing customer phone should keep backend resolve successful but phone.valid must be false."""
    payload = {
        "doc_type": "invoice",
        "status": "draft",
        "payload": {
            "settings": {
                "document_number": f"ITER289-{uuid.uuid4().hex[:6]}",
                "date": "2026-02-16",
            },
            "workshop": {
                "name": "ورشة الاختبار",
            },
            "customer": {
                "name": "عميل بدون جوال",
            },
            "vehicle": {
                "plate": "د هـ و 5678",
            },
            "items": [{"description": "فحص", "quantity": 1, "unit_price": 120}],
        },
    }

    response = auth_session.post(f"{API}/outbound/resolve-message", json=payload, timeout=30)
    assert response.status_code == 200, response.text[:300]
    data = response.json()

    assert data.get("success") is True
    assert isinstance(data.get("missing_variables"), list)
    assert "PLATE_NO" not in data.get("missing_variables")

    phone = data.get("phone") or {}
    assert phone.get("valid") is False
    assert phone.get("e164") is None
