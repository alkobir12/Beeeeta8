"""Iteration 298 - unified templates contract checks.

Modules/features covered:
- document_templates registry for unified invoice/diagnosis/quote defaults
- frontend renderDocumentTemplate output contract (title, tax optionality, approvals, barcode, tbody rows)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap

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

EXPECTED_IDS = {
    "unified-invoice-a4-mobile-v1": "invoice",
    "unified-diagnosis-a4-mobile-v1": "diagnosis",
    "unified-quote-a4-mobile-v1": "quote",
}


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


def _run_node(script: str) -> str:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd="/app",
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _render_html(template_html: str, payload: dict, workshop: dict | None = None) -> str:
    script = textwrap.dedent(
        f"""
        import {{ renderDocumentTemplate }} from './frontend/src/utils/documentTemplate.js';
        const template = {json.dumps(template_html)};
        const payload = {json.dumps(payload, ensure_ascii=False)};
        const workshop = {json.dumps(workshop or {}, ensure_ascii=False)};
        const html = renderDocumentTemplate(template, payload, workshop);
        console.log(html);
        """
    )
    return _run_node(script)


def test_registry_has_only_three_unified_templates_and_single_default_per_type(api_session: requests.Session):
    response = api_session.get(f"{API}/document-templates", timeout=30)
    assert response.status_code == 200, response.text[:260]

    templates = (response.json() or {}).get("templates") or []
    assert len(templates) == 3, f"Expected exactly 3 templates, got {len(templates)}"

    ids = {row.get("id") for row in templates}
    assert ids == set(EXPECTED_IDS.keys())

    defaults_by_type = {}
    for row in templates:
        assert row.get("active") is True
        assert row.get("is_default") is True
        doc_type = row.get("document_type")
        assert EXPECTED_IDS[row["id"]] == doc_type
        defaults_by_type[doc_type] = defaults_by_type.get(doc_type, 0) + 1

    assert defaults_by_type == {"invoice": 1, "diagnosis": 1, "quote": 1}


@pytest.mark.parametrize(
    "doc_type,expected_title",
    [
        ("invoice", "فاتورة مبيعات"),
        ("diagnosis", "تقرير تشخيص"),
        ("quote", "عرض سعر"),
    ],
)
def test_renderer_sets_document_title_and_workshop_fields_in_header_and_third_box(doc_type: str, expected_title: str):
    template_html = (
        "<header><b>{{WORKSHOP_NAME}}</b><span>سجل الورشة: {{COMPANY_CR}}</span><i>{{DOCUMENT_TITLE}}</i></header>"
        "<section class='info'><div class='box'></div><div class='box'></div>"
        "<div class='box'><p>الورشة: {{WORKSHOP_NAME}}</p><p>السجل: {{COMPANY_CR}}</p></div></section>"
    )
    payload = {"doc_type": doc_type, "items": [{"description": "فحص", "quantity": 1, "price": 10}]}
    workshop = {"name": "ورشة الاختبار", "commercial_register": "CR-12345"}
    html = _render_html(template_html, payload, workshop)

    assert expected_title in html
    assert html.count("ورشة الاختبار") >= 2
    assert html.count("CR-12345") >= 2


def test_tax_is_optional_and_grand_total_single_without_tax_then_single_tax_row_when_present():
    template_html = (
        "<div class='totals'>"
        "<div><span>المجموع</span><b>{{SUBTOTAL}}</b></div>"
        "{{TAX_ROW}}"
        "<div class='grand'><span>الإجمالي الكلي</span><b>{{TOTAL}}</b></div>"
        "</div>"
    )

    payload_no_tax = {
        "doc_type": "invoice",
        "items": [{"description": "زيت", "quantity": 2, "price": 50}],
        "settings": {"totals": {"tax": 0}},
    }
    html_no_tax = _render_html(template_html, payload_no_tax, {"name": "ورشة"})
    assert "الضريبة" not in html_no_tax
    assert html_no_tax.count("الإجمالي الكلي") == 1

    payload_with_tax = {
        "doc_type": "invoice",
        "items": [{"description": "زيت", "quantity": 2, "price": 50}],
        "settings": {"totals": {"tax": 15}},
    }
    html_with_tax = _render_html(template_html, payload_with_tax, {"name": "ورشة"})
    assert html_with_tax.count("الضريبة") == 1
    assert html_with_tax.count("الإجمالي الكلي") == 1


def test_final_html_has_single_barcode_and_no_qr_or_barcode_duplication(api_session: requests.Session):
    response = api_session.post(
        f"{API}/document-templates/unified-invoice-a4-mobile-v1/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:260]
    template_html = str((response.json() or {}).get("content") or "")
    assert template_html

    payload = {
        "doc_type": "invoice",
        "items": [{"description": "فلتر", "quantity": 1, "price": 120}],
        "settings": {"document_number": "INV-298"},
    }
    html = _render_html(template_html, payload, {"name": "ورشة", "commercial_register": "CR-1"})

    assert html.count('<section class="barcode">') == 1
    assert html.count('<div class="bars"></div>') == 1
    assert "QR" not in html and "qr" not in html


def test_approval_stamps_are_conditional_and_inside_approval_boxes():
    template_html = (
        "<section class='approvals'>"
        "<div class='approval customer'><h3>اعتماد العميل</h3>{{CUSTOMER_APPROVAL_STAMP}}</div>"
        "<div class='approval workshop'><h3>اعتماد الورشة</h3>{{WORKSHOP_APPROVAL_STAMP}}</div>"
        "</section>"
    )

    none_html = _render_html(template_html, {"approvals": {}, "items": []}, {"name": "ورشة"})
    assert "approved-stamp" not in none_html

    both_html = _render_html(
        template_html,
        {
            "approvals": {
                "customer": {"name": "عميل", "at": "2026-02-01T10:00:00Z", "id": "CUS-123456"},
                "workshop": {"name": "مدير", "at": "2026-02-01T10:05:00Z", "id": "WS-654321"},
            },
            "items": [],
        },
        {"name": "ورشة"},
    )
    assert both_html.count("approved-stamp") == 2
    assert both_html.count("width:92px") == 2
    assert "class='approval customer'><h3>اعتماد العميل</h3><div class=\"approved-stamp\"" in both_html
    assert "class='approval workshop'><h3>اعتماد الورشة</h3><div class=\"approved-stamp\"" in both_html


def test_no_raw_placeholders_or_demo_seed_data_and_items_rows_render_inside_tbody(api_session: requests.Session):
    response = api_session.post(
        f"{API}/document-templates/unified-quote-a4-mobile-v1/use",
        json={"document_type": "quote", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:260]
    template_html = str((response.json() or {}).get("content") or "")

    payload = {
        "doc_type": "quote",
        "customer": {"name": "شركة الاختبار", "phone": "0500000000"},
        "vehicle": {"brand": "Toyota", "model": "Corolla", "year": "2020", "plate": "أ ب ج 1234"},
        "items": [{"description": "صيانة دورية", "quantity": 1, "price": 300}],
        "settings": {"document_number": "Q-298", "status": "مسودة", "notes": "ملاحظة"},
    }
    workshop = {"name": "ورشة النخبة", "commercial_register": "CR-888", "address": "الرياض", "phone": "0551111111"}
    html = _render_html(template_html, payload, workshop)

    unresolved = re.findall(r"{{\s*[^{}]+\s*}}|\[\[\s*[^\]]+\s*\]\]|<%=?\s*[^%]+\s*%>", html)
    assert unresolved == [], f"Found unresolved placeholders: {unresolved[:5]}"
    assert "lorem ipsum" not in html.lower()
    assert "test data" not in html.lower()

    tbody_open = html.find("<tbody")
    tbody_close = html.find("</tbody>")
    assert tbody_open != -1 and tbody_close != -1
    tbody_html = html[tbody_open:tbody_close]
    assert "<tr>" in tbody_html
