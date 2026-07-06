"""Iteration 253 — Security re-audit hotfixes (isolated diffs).

SEC-002 (High) Broken function-level authorization on runtime reads + a direct
             finance-write endpoint. Fix: approver-role gate on the org-wide
             runtime read endpoints, and a finance-write permission gate on
             POST /api/vehicles/{id}/save-parts-and-create-journal.
  1. no token            → 401
  2. technician/accountant→ 403 (non-approver)
  3. admin               → 200 (200/404 for /db/{unknown-table})
  4. save-parts write    → technician 403, no-token 401

SEC-001 (High) Stored XSS in the document print flow. Fix: server-side
             HTML-escape of all user-controlled fields in arabic_quotation
             before templating (covers every /api/documents/generate path).
  5. <img onerror>/<script> in customer name + item description come back
     HTML-escaped (&lt;...), NOT as live tags.

SEC-005 (Medium) PII not redacted in llm_traces. Fix: run redact() over
             stored messages/tool payloads.
  6. A chat message with a phone + email is stored masked (***4567,
     a***@domain) in the persisted trace; raw values absent.

DATA SAFETY: read-only probes + create-then-nothing. The finance-write test
uses a non-existent vehicle id and a non-approver token so it is REJECTED
before any DB write. Document generation persists nothing.
"""
from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"


def _login(username: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"username": username}, timeout=30)
    assert r.status_code == 200, f"login {username}: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def admin():
    return _login("مدير")


@pytest.fixture(scope="module")
def technician():
    return _login("مستخدم اختبار")


@pytest.fixture(scope="module")
def accountant():
    return _login("فرج1")


READ_ENDPOINTS = ["audit", "drafts", "approvals", "executions", "stats"]


# ---- SEC-002: runtime read RBAC ------------------------------------------

@pytest.mark.parametrize("ep", READ_ENDPOINTS)
def test_runtime_read_no_token_401(ep):
    r = requests.get(f"{API}/runtime/{ep}", timeout=30)
    assert r.status_code == 401, f"/runtime/{ep} no-token expected 401, got {r.status_code}"


@pytest.mark.parametrize("ep", READ_ENDPOINTS)
def test_runtime_read_technician_403(ep, technician):
    r = requests.get(f"{API}/runtime/{ep}", headers={"Authorization": f"Bearer {technician}"}, timeout=30)
    assert r.status_code == 403, f"/runtime/{ep} technician expected 403, got {r.status_code}"


@pytest.mark.parametrize("ep", READ_ENDPOINTS)
def test_runtime_read_accountant_403(ep, accountant):
    r = requests.get(f"{API}/runtime/{ep}", headers={"Authorization": f"Bearer {accountant}"}, timeout=30)
    assert r.status_code == 403, f"/runtime/{ep} accountant expected 403, got {r.status_code}"


@pytest.mark.parametrize("ep", READ_ENDPOINTS)
def test_runtime_read_admin_200(ep, admin):
    r = requests.get(f"{API}/runtime/{ep}", headers={"Authorization": f"Bearer {admin}"}, timeout=30)
    assert r.status_code == 200, f"/runtime/{ep} admin expected 200, got {r.status_code}"


def test_save_parts_journal_technician_403(technician):
    r = requests.post(
        f"{API}/vehicles/DOESNOTEXIST/save-parts-and-create-journal",
        headers={"Authorization": f"Bearer {technician}"},
        json=[{"price": 1, "quantity": 1}],
        timeout=30,
    )
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text[:200]}"


def test_save_parts_journal_no_token_401():
    r = requests.post(
        f"{API}/vehicles/DOESNOTEXIST/save-parts-and-create-journal",
        json=[{"price": 1, "quantity": 1}],
        timeout=30,
    )
    assert r.status_code == 401


# ---- SEC-001: stored XSS in print ----------------------------------------

def test_document_generate_escapes_user_fields(admin):
    payload = {
        "doc_type": "invoice",
        "customer": {"name": "<img src=x onerror=alert(1)>عميل", "phone": "0551112222"},
        "vehicle": {},
        "items": [{"description": "<script>steal()</script>بند", "quantity": 1, "unit_price": 100, "discount": 0}],
        "settings": {"theme": "أزرق", "style": "حديث", "tax_rate": 0},
    }
    r = requests.post(f"{API}/documents/generate", headers={"Authorization": f"Bearer {admin}"}, json=payload, timeout=60)
    assert r.status_code == 200
    html = r.json().get("html", "")
    assert "<img src=x onerror=" not in html, "live <img onerror> tag must not appear"
    assert "<script>steal()" not in html, "live <script> must not appear"
    assert "&lt;img src=x onerror=" in html
    assert "&lt;script&gt;steal()" in html


# ---- SEC-005: PII redaction in traces ------------------------------------

def test_trace_redacts_phone_and_email(admin):
    sid = f"sec5-pytest-{int(time.time())}"
    r = requests.post(
        f"{API}/assistant/chat",
        headers={"Authorization": f"Bearer {admin}"},
        json={"message": "رقم العميل 0551234567 وبريده qa.tester@example.com", "use_ai": True, "session_id": sid},
        timeout=120,
    )
    assert r.status_code == 200
    trace_id = r.json().get("data", {}).get("trace_id")
    assert trace_id, "chat must return a trace_id"
    time.sleep(1)
    tr = requests.get(f"{API}/traces/{trace_id}", headers={"Authorization": f"Bearer {admin}"}, timeout=30)
    assert tr.status_code == 200
    blob = tr.text
    assert "0551234567" not in blob, "raw phone must be masked in stored trace"
    assert "***4567" in blob, "phone should be masked keeping last 4"
    assert "qa.tester@" not in blob, "raw email local part must be masked"
