"""Iteration 277 — DocumentPrint + generate API regression.

Modules/features covered:
- Manager PIN login smoke for print flow
- Auth cookie/CORS/lockout quick checks (playbook-aligned)
- /api/documents/generate status/data checks for all document types
"""

from __future__ import annotations

import os
from typing import Dict, Any

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
EXPLICIT_CORS_ORIGINS = [
    origin.strip()
    for origin in (os.environ.get("CORS_ORIGINS") or "").split(",")
    if origin.strip()
]


def _headers(include_bypass: bool = True) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if include_bypass and RATE_BYPASS:
        h["x-ratelimit-bypass"] = RATE_BYPASS
    return h


@pytest.fixture(scope="module")
def manager_session() -> requests.Session:
    """Authenticated session for print-related endpoints."""
    session = requests.Session()
    session.headers.update(_headers(include_bypass=True))

    login = session.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    if login.status_code != 200:
        pytest.skip(f"Manager login unavailable in preview: {login.status_code} {login.text[:120]}")

    data = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
    token = data.get("access_token")
    if not token:
        pytest.skip("Login succeeded but access_token missing")

    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _sample_payload(doc_type: str = "invoice") -> Dict[str, Any]:
    return {
        "doc_type": doc_type,
        "workshop": {
            "name": "ورشة اختبار الطباعة",
            "phone": "0500000000",
            "commercial_register": "1131051365",
            "tax_number": "300000000000003",
            "address": "الرياض",
        },
        "customer": {
            "name": "عميل اختبار",
            "phone": "0555555555",
        },
        "vehicle": {
            "brand": "تويوتا",
            "model": "كامري",
            "year": "2022",
            "plateNumber": "أ ب ج 1234",
            "mileage": "120000",
        },
        "items": [
            {
                "description": "فحص كمبيوتر",
                "quantity": 1,
                "unit_price": 100,
                "discount": 0,
            }
        ],
        "settings": {
            "document_number": "TEST-PRINT-277",
            "date": "2026-02-01",
        },
    }


def test_auth_login_sets_secure_http_only_cookies_and_token():
    """Auth login should return token and set secure, httpOnly cookies."""
    r = requests.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        headers=_headers(include_bypass=True),
        timeout=30,
    )
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    assert isinstance(body.get("access_token"), str) and len(body["access_token"]) > 20

    set_cookie = ", ".join(r.headers.get_all("Set-Cookie") if hasattr(r.headers, "get_all") else [r.headers.get("Set-Cookie", "")])
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie


def test_cors_origin_is_explicit_not_wildcard_on_auth_login():
    """Credentialed auth response should not use wildcard origin."""
    origin = EXPLICIT_CORS_ORIGINS[0] if EXPLICIT_CORS_ORIGINS else BASE_URL
    r = requests.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        headers={**_headers(include_bypass=True), "Origin": origin},
        timeout=30,
    )
    assert r.status_code == 200, r.text[:200]
    allow_origin = r.headers.get("Access-Control-Allow-Origin", "")
    assert allow_origin != "*"
    if allow_origin:
        assert allow_origin in EXPLICIT_CORS_ORIGINS or allow_origin == origin


def test_bruteforce_lockout_after_five_failed_attempts_fake_user():
    """Best-effort brute-force check using fake username to avoid mutating real users."""
    username = "zz_lock_probe_iter277"
    got_429 = False
    for _ in range(6):
        r = requests.post(
            f"{API}/auth/login",
            json={"username": username, "pin": "000000"},
            headers=_headers(include_bypass=False),
            timeout=30,
        )
        if r.status_code == 429:
            got_429 = True
            break
    assert got_429, "Expected 429 lockout not observed within 6 attempts"


@pytest.mark.parametrize(
    "doc_type,expected_text",
    [
        ("invoice", "فاتورة"),
        ("diagnosis", "تقرير تشخيص"),
        ("quote", "عرض سعر"),
        ("receipt", "إيصال استلام"),
    ],
)
def test_documents_generate_returns_200_and_html_for_types(
    manager_session: requests.Session,
    doc_type: str,
    expected_text: str,
):
    """Core backend regression: /api/documents/generate remains healthy for all print types."""
    payload = _sample_payload(doc_type)
    r = manager_session.post(f"{API}/documents/generate", json=payload, timeout=40)
    assert r.status_code == 200, r.text[:300]

    body = r.json()
    assert body.get("success") is True
    assert body.get("doc_type") == doc_type

    html = body.get("html") or ""
    assert isinstance(html, str) and len(html) > 200
    assert "ورشة اختبار الطباعة" in html
    assert expected_text in html
