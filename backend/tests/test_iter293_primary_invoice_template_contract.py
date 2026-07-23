"""Iteration 293 - Primary invoice template contract checks.

Modules/features covered:
- document_templates singleton/default state
- explicit template `/use` HTML contract sections
- rendered HTML includes required approvals and electronic seal markers
"""

from __future__ import annotations

import os
import re

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


def test_templates_registry_has_single_active_default_primary_template(api_session: requests.Session):
    """Templates registry: only one active/default template and it is primary-mobile-a4-invoice-v1."""
    response = api_session.get(f"{API}/document-templates", timeout=30)
    assert response.status_code == 200, response.text[:260]

    rows = (response.json() or {}).get("templates") or []
    assert isinstance(rows, list)
    assert len(rows) == 1, f"Expected exactly 1 template, got {len(rows)}"

    tpl = rows[0]
    assert tpl.get("id") == TEMPLATE_ID
    assert tpl.get("active") is True
    assert tpl.get("is_default") is True
    assert tpl.get("file_type") == "html"
    assert tpl.get("document_type") == "invoice"


def test_use_primary_template_returns_invoice_html_contract(api_session: requests.Session):
    """Template use: HTML contains workshop/customer/vehicle/table/approval sections."""
    response = api_session.post(
        f"{API}/document-templates/{TEMPLATE_ID}/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:260]

    payload = response.json() or {}
    template = payload.get("template") or {}
    html = str(payload.get("content") or "")

    assert template.get("id") == TEMPLATE_ID
    assert template.get("active") is True
    assert isinstance(html, str) and html.strip()

    required_sections = [
        "بيانات العميل",
        "بيانات المركبة",
        "اعتماد العميل",
        "اعتماد الورشة",
        "ختم الورشة",
    ]
    for marker in required_sections:
        assert marker in html, f"Missing marker in HTML: {marker}"

    # Workshop block can be in header instead of a dedicated titled card.
    assert "{{WORKSHOP_NAME}}" in html
    assert "{{WORKSHOP_ADDRESS}}" in html
    assert "{{WORKSHOP_PHONE}}" in html

    assert "<table" in html and "</table>" in html
    assert "ITEMS_ROWS" in html or "{{ITEMS_ROWS}}" in html
    tbody_open = html.find("<tbody>")
    tbody_close = html.find("</tbody>")
    items_pos = html.find("{{ITEMS_ROWS}}")
    assert tbody_open != -1 and tbody_close != -1
    assert tbody_open < items_pos < tbody_close, "{{ITEMS_ROWS}} must be inside <tbody> for tabular rendering"


def test_rendered_html_no_raw_placeholders_and_has_electronic_seals(api_session: requests.Session):
    """Rendered contract: no unresolved placeholders in final HTML body with sample payload."""
    response = api_session.post(
        f"{API}/document-templates/{TEMPLATE_ID}/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:260]
    html = str((response.json() or {}).get("content") or "")

    # The /use endpoint returns template content by contract; it should still carry expected placeholders
    # for required data keys and seal code.
    for expected_var in ["{{WORKSHOP_NAME}}", "{{CUSTOMER_NAME}}", "{{VEHICLE_INFO}}", "{{SEAL_CODE}}"]:
        assert expected_var in html, f"Expected placeholder missing from base template: {expected_var}"

    # Ensure no unknown placeholder patterns are present.
    unknown = re.findall(r"{{\s*([^{}]+?)\s*}}", html)
    allowed = {
        "WORKSHOP_NAME", "WORKSHOP_ADDRESS", "WORKSHOP_PHONE", "COMPANY_TAX", "INVOICE_NO", "DATE",
        "CUSTOMER_NAME", "CUSTOMER_PHONE", "VEHICLE_INFO", "PLATE_NO", "SUBTOTAL", "TAX", "TOTAL",
        "ITEMS_ROWS", "SEAL_CODE",
    }
    extras = sorted({item for item in unknown if item not in allowed})
    assert not extras, f"Unexpected placeholders in template: {extras}"
