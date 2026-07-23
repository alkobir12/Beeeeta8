"""Iteration 297 - document approval stamps render contract.

Modules/features covered:
- frontend renderDocumentTemplate stamp placeholder replacement behavior
- customer/workshop approval stamp visibility matrix
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path


def _run_node(script: str) -> str:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd="/app",
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _render_html(payload: dict) -> str:
    template = (
        "<section class='approvals'>"
        "<div class='customer'>{CUSTOMER_APPROVAL_STAMP}</div>"
        "<div class='workshop'>{WORKSHOP_APPROVAL_STAMP}</div>"
        "</section>"
    )
    script = textwrap.dedent(
        f"""
        import {{ renderDocumentTemplate }} from './frontend/src/utils/documentTemplate.js';

        const template = {json.dumps(template)};
        const payload = {json.dumps(payload, ensure_ascii=False)};
        const html = renderDocumentTemplate(template, payload, {{ name: 'ورشة' }});
        console.log(html);
        """
    )
    return _run_node(script)


def test_render_without_approvals_has_no_stamps_or_raw_placeholders():
    payload = {
        "approvals": {},
        "items": [],
        "settings": {"document_number": "INV-TEST"},
    }
    html = _render_html(payload)
    assert "approved-stamp" not in html
    assert "CUSTOMER_APPROVAL_STAMP" not in html
    assert "WORKSHOP_APPROVAL_STAMP" not in html


def test_render_customer_only_shows_customer_stamp_not_workshop():
    payload = {
        "approvals": {
            "customer": {"name": "عميل اختبار", "at": "2026-02-01T10:00:00Z", "id": "CUS-1234567890"},
            "workshop": None,
        },
        "items": [],
        "settings": {"document_number": "INV-TEST"},
    }
    html = _render_html(payload)
    assert html.count("approved-stamp") == 1
    assert "اعتماد العميل" in html
    assert "عميل اختبار" in html
    assert "اعتماد الورشة" not in html


def test_render_workshop_only_shows_workshop_stamp_not_customer():
    payload = {
        "approvals": {
            "customer": None,
            "workshop": {"name": "مدير الورشة", "at": "2026-02-01T12:30:00Z", "id": "WS-1234567890"},
        },
        "items": [],
        "settings": {"document_number": "INV-TEST"},
    }
    html = _render_html(payload)
    assert html.count("approved-stamp") == 1
    assert "اعتماد الورشة" in html
    assert "مدير الورشة" in html
    assert "اعتماد العميل" not in html


def test_render_both_approvals_shows_two_independent_stamps_no_raw_placeholders():
    payload = {
        "approvals": {
            "customer": {"name": "عميل اختبار", "at": "2026-02-01T10:00:00Z", "id": "CUS-1234567890"},
            "workshop": {"name": "مدير الورشة", "at": "2026-02-01T12:30:00Z", "id": "WS-1234567890"},
        },
        "items": [],
        "settings": {"document_number": "INV-TEST"},
    }
    html = _render_html(payload)
    assert html.count("approved-stamp") == 2
    assert "اعتماد العميل" in html
    assert "اعتماد الورشة" in html
    assert "CUSTOMER_APPROVAL_STAMP" not in html
    assert "WORKSHOP_APPROVAL_STAMP" not in html


def test_document_print_template_payload_includes_form_approvals():
    source = Path("/app/frontend/src/pages/DocumentPrint.jsx").read_text(encoding="utf-8")
    assert "approvals: formData.approvals" in source


def test_document_print_print_and_pdf_paths_use_rendered_template_contract():
    source = Path("/app/frontend/src/pages/DocumentPrint.jsx").read_text(encoding="utf-8")
    # print path must directly use renderedTemplate
    assert "frame.srcdoc = renderedTemplate" in source
    # preview path (PDF source element) must be built from renderedTemplate
    assert "renderDocumentTemplate(templateContent, templatePayload, formData.workshop)" in source
    assert "<ResolvedTemplateSheet ref={previewRef} html={renderedTemplate} />" in source
