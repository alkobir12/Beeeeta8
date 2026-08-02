"""Iteration 323 — unified reference template + visit-selection contract.

Modules/features covered:
- Auth login contract (manager quick PIN)
- Document template resolve returns raw unified reference HTML
- Vehicle visit source-data contract for specified vehicle/visit IDs
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

TARGET_VEHICLE_ID = "ce2e776e-d750-4e34-b20a-ef21f49cad63"
TARGET_VISIT_SECOND = "5f3b0fd2-b225-407c-8c8d-d3e82c9a129a"
TARGET_VISIT_FIRST = "77a3d80a-70be-4274-b646-b9aff8b80e55"
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')


def _extract_items_from_notes(notes: Any) -> List[Dict[str, Any]]:
    if not isinstance(notes, str):
        return []
    txt = notes.strip()
    if not txt.startswith("{"):
        return []
    try:
        parsed = json.loads(txt)
    except Exception:
        return []
    rows = parsed.get("items")
    return rows if isinstance(rows, list) else []


def _item_name(item: Dict[str, Any]) -> str:
    return str(item.get("name") or item.get("description") or item.get("itemName") or "").strip()


def _is_uuid_like(value: str) -> bool:
    return bool(re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", value.strip(), re.I))


@pytest.fixture(scope="module")
def auth_session() -> requests.Session:
    """Auth module: manager quick PIN login session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    if RATE_BYPASS:
        session.headers["x-ratelimit-bypass"] = RATE_BYPASS

    login = session.post(
        f"{API}/auth/login",
        json={"username": "مدير", "pin": "123123"},
        timeout=30,
    )
    if login.status_code != 200:
        pytest.skip(f"Manager login unavailable: {login.status_code} {login.text[:180]}")

    payload = login.json() if isinstance(login.json(), dict) else {}
    token = payload.get("access_token")
    if not token:
        pytest.skip("access_token missing in login response")

    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def test_resolve_invoice_returns_raw_reference_contract(auth_session: requests.Session):
    """Template module: resolver returns raw reference HTML signatures unchanged."""
    response = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:220]

    data = response.json() if isinstance(response.json(), dict) else {}
    content = str(data.get("content") or "")

    assert 'data-field="doc-no"' in content
    assert 'id="row-template"' in content
    assert 'id="items-body"' in content
    assert ".crow>div" in content
    assert ".crow&gt;div" not in content
    assert "data:font/woff2;base64," in content
    assert "class=\"pbtn\"" not in content


def test_resolve_diagnosis_uses_same_reference_template_shape(auth_session: requests.Session):
    """Template module: diagnosis type resolves using the same unified reference structure."""
    invoice_response = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    diagnosis_response = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"document_type": "diagnosis", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert invoice_response.status_code == 200
    assert diagnosis_response.status_code == 200

    invoice_html = str((invoice_response.json() or {}).get("content") or "")
    diagnosis_html = str((diagnosis_response.json() or {}).get("content") or "")

    assert diagnosis_html == invoice_html
    assert 'data-field="doc-kind"' in diagnosis_html
    assert 'data-field="doc-no"' in diagnosis_html


def test_vehicle_contains_required_visits(auth_session: requests.Session):
    """Vehicle module: target vehicle exposes both requested visits."""
    response = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)
    assert response.status_code == 200, response.text[:220]

    visits = response.json() if isinstance(response.json(), list) else []
    visit_ids = {str(v.get("id")) for v in visits}

    assert TARGET_VISIT_SECOND in visit_ids
    assert TARGET_VISIT_FIRST in visit_ids


def test_second_visit_matches_requested_date_items_and_amount(auth_session: requests.Session):
    """Visit module: second visit content/date/workshop amount match requested contract."""
    response = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)
    assert response.status_code == 200, response.text[:220]
    visits = response.json() if isinstance(response.json(), list) else []

    visit = next((v for v in visits if str(v.get("id")) == TARGET_VISIT_SECOND), None)
    assert visit is not None

    date_value = str(visit.get("entryDate") or visit.get("entry_date") or visit.get("created_at") or "")[:10]
    assert date_value == "2026-06-23"

    total_workshop = float(visit.get("total_workshop") or visit.get("workshop_total") or visit.get("total") or 0)
    assert total_workshop == pytest.approx(2350.0)

    source_items = _extract_items_from_notes(visit.get("notes"))
    names = [_item_name(item) for item in source_items]
    joined = " | ".join(names)
    assert "فك وتركيب بخاخات" in joined
    assert "فك صدر المكينه" in joined
    assert "تبديل زيت الجير" in joined

    payment_method = str(visit.get("payment_method") or visit.get("paymentMethod") or "").strip()
    assert payment_method == ""
    assert total_workshop > 0


def test_first_visit_print_scope_has_its_own_date_and_zero_total(auth_session: requests.Session):
    """Visit module: first visit has independent data (date/total) and no second-visit items."""
    response = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)
    assert response.status_code == 200, response.text[:220]
    visits = response.json() if isinstance(response.json(), list) else []

    visit = next((v for v in visits if str(v.get("id")) == TARGET_VISIT_FIRST), None)
    assert visit is not None

    date_value = str(visit.get("entryDate") or visit.get("entry_date") or visit.get("created_at") or "")[:10]
    assert date_value == "2026-07-12"

    total_workshop = float(visit.get("total_workshop") or visit.get("workshop_total") or visit.get("total") or 0)
    assert total_workshop == pytest.approx(0.0)

    source_items = _extract_items_from_notes(visit.get("notes"))
    names = " | ".join(_item_name(item) for item in source_items)
    assert "فك وتركيب بخاخات" not in names
    assert "فك صدر المكينه" not in names
    assert "تبديل زيت الجير" not in names


@pytest.mark.parametrize("visit_id", [TARGET_VISIT_SECOND, TARGET_VISIT_FIRST])
def test_doc_number_and_job_order_do_not_store_uuid_values(auth_session: requests.Session, visit_id: str):
    """Visit module: printable doc/job references should not be UUID-like human ids."""
    response = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)
    assert response.status_code == 200, response.text[:220]
    visits = response.json() if isinstance(response.json(), list) else []
    visit = next((v for v in visits if str(v.get("id")) == visit_id), None)
    assert visit is not None

    doc_number = str(visit.get("invoiceNumber") or visit.get("invoice_number") or visit.get("documentNumber") or visit.get("document_number") or "").strip()
    job_order = str(visit.get("jobOrder") or visit.get("job_order") or visit.get("workOrderNumber") or visit.get("work_order_number") or "").strip()

    if doc_number:
        assert not _is_uuid_like(doc_number)
    if job_order:
        assert not _is_uuid_like(job_order)
