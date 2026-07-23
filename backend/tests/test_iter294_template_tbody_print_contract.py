"""Iteration 294 - primary invoice tbody placeholder contract.

Modules/features covered:
- document_templates singleton registry
- `/use` must keep ITEMS_ROWS placeholder inside tbody (comment placeholder accepted)
"""

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
TEMPLATE_ID = "primary-mobile-a4-invoice-v1"
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')


@pytest.fixture(scope="module")
def api_session() -> requests.Session:
    """Authenticated API client using manager quick PIN."""
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
        pytest.skip(f"Manager login unavailable: {login.status_code} {login.text[:160]}")

    token = (login.json() or {}).get("access_token")
    if not token:
        pytest.skip("access_token missing from login response")

    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _extract_table_window(html: str) -> tuple[int, int, int, int]:
    table_open = html.find("<table")
    table_close = html.find("</table>")
    tbody_open = html.find("<tbody")
    tbody_close = html.find("</tbody>")
    return table_open, table_close, tbody_open, tbody_close


def test_templates_registry_singleton_primary(api_session: requests.Session):
    """Registry remains exactly one active/default template: primary-mobile-a4-invoice-v1."""
    response = api_session.get(f"{API}/document-templates", timeout=30)
    assert response.status_code == 200, response.text[:260]
    rows = (response.json() or {}).get("templates") or []
    assert isinstance(rows, list)
    assert len(rows) == 1, f"Expected exactly 1 template, got {len(rows)}"
    row = rows[0]
    assert row.get("id") == TEMPLATE_ID
    assert row.get("active") is True
    assert row.get("is_default") is True


def test_use_keeps_items_rows_placeholder_inside_tbody(api_session: requests.Session):
    """/use must return invoice html where ITEMS_ROWS placeholder stays in tbody (comment accepted)."""
    response = api_session.post(
        f"{API}/document-templates/{TEMPLATE_ID}/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:260]

    html = str((response.json() or {}).get("content") or "")
    assert html.strip(), "Empty HTML content from /use"

    table_open, table_close, tbody_open, tbody_close = _extract_table_window(html)
    assert table_open != -1 and table_close != -1, "Missing table section"
    assert tbody_open != -1 and tbody_close != -1, "Missing tbody section"
    assert table_open < tbody_open < tbody_close < table_close, "tbody must remain inside table"

    placeholder_comment = "<!--{{ITEMS_ROWS}}-->"
    placeholder_raw = "{{ITEMS_ROWS}}"
    pos_comment = html.find(placeholder_comment)
    pos_raw = html.find(placeholder_raw)
    candidate_pos = pos_comment if pos_comment != -1 else pos_raw
    assert candidate_pos != -1, "ITEMS_ROWS placeholder missing from /use content"
    assert tbody_open < candidate_pos < tbody_close, "ITEMS_ROWS placeholder must stay inside tbody"


def test_use_contains_customer_workshop_approvals_and_seal(api_session: requests.Session):
    """Template html still includes customer/workshop approval markers and electronic seal labels."""
    response = api_session.post(
        f"{API}/document-templates/{TEMPLATE_ID}/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:260]
    html = str((response.json() or {}).get("content") or "")
    for marker in ["اعتماد العميل", "اعتماد الورشة", "ختم الورشة", "{{SEAL_CODE}}"]:
        assert marker in html, f"Missing marker in template html: {marker}"
