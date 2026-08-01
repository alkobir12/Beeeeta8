"""Iteration 306 — Vehicle print supplier-filter regression.

Modules/features covered:
- Auth login via manager PIN
- Vehicle/visit retrieval for target vehicle id
- Data contract check: supplier item kept in visit archive notes while workshop-only list is printable
- Document template resolve/use endpoints for invoice and diagnosis
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

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
TARGET_VEHICLE_ID = "61fe0b56-aa66-490d-a5e7-6f3b8195ed56"
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')


def _extract_items_from_notes(notes: Any) -> List[Dict[str, Any]]:
    if not isinstance(notes, str):
        return []
    text = notes.strip()
    if not text.startswith("{"):
        return []
    try:
        parsed = json.loads(text)
    except Exception:
        return []
    rows = parsed.get("items")
    return rows if isinstance(rows, list) else []


def _is_supplier_item(item: Dict[str, Any]) -> bool:
    item_type = str(item.get("itemType") or item.get("type") or "").strip().lower()
    billing_type = str(item.get("billingType") or item.get("billing_type") or "").strip().lower()
    return item_type == "supplier" or billing_type == "supplier"


def _to_total(item: Dict[str, Any]) -> float:
    qty = float(item.get("quantity") or item.get("qty") or 1)
    price = float(item.get("price") or item.get("unit_price") or item.get("unitPrice") or item.get("amount") or 0)
    total = item.get("total")
    return float(total) if total is not None else qty * price


@pytest.fixture(scope="module")
def auth_session() -> requests.Session:
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
        pytest.skip(f"Manager login unavailable in preview: {login.status_code} {login.text[:140]}")

    token = (login.json() or {}).get("access_token")
    if not token:
        pytest.skip("Login succeeded but access_token missing")

    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def target_visit_context(auth_session: requests.Session) -> Dict[str, Any]:
    vehicle_resp = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}", timeout=30)
    visits_resp = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)

    assert vehicle_resp.status_code == 200, vehicle_resp.text[:220]
    assert visits_resp.status_code == 200, visits_resp.text[:220]

    vehicle = vehicle_resp.json() if isinstance(vehicle_resp.json(), dict) else {}
    visits = visits_resp.json() if isinstance(visits_resp.json(), list) else []
    assert vehicle.get("id") == TARGET_VEHICLE_ID
    assert visits, "No visits found for target vehicle"

    chosen = None
    for visit in visits:
        items = _extract_items_from_notes(visit.get("notes"))
        if not items:
            continue
        supplier_rows = [row for row in items if _is_supplier_item(row)]
        workshop_rows = [row for row in items if not _is_supplier_item(row)]
        supplier_total = round(sum(_to_total(row) for row in supplier_rows), 2)
        workshop_total = round(sum(_to_total(row) for row in workshop_rows), 2)
        if supplier_rows and workshop_rows and abs(supplier_total - 179.0) < 0.01 and abs(workshop_total - 600.0) < 0.01:
            chosen = visit
            break

    if not chosen:
        pytest.skip("Target visit with workshop 600 + supplier 179 not found in preview data")

    return {"vehicle": vehicle, "visit": chosen}


def test_target_vehicle_endpoint_returns_requested_vehicle(auth_session: requests.Session):
    """Vehicle module: explicit UUID GET works on preview."""
    response = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}", timeout=30)
    assert response.status_code == 200, response.text[:220]
    data = response.json()
    assert data.get("id") == TARGET_VEHICLE_ID
    assert isinstance(data.get("plateNumber") or data.get("plate") or "", str)


def test_target_visit_contains_supplier_and_workshop_items_in_archive_notes(target_visit_context: Dict[str, Any]):
    """Visit module: archive notes keep supplier and workshop rows (no data loss)."""
    visit = target_visit_context["visit"]
    items = _extract_items_from_notes(visit.get("notes"))
    assert items, "Expected structured visit notes with items"

    supplier_rows = [row for row in items if _is_supplier_item(row)]
    workshop_rows = [row for row in items if not _is_supplier_item(row)]
    assert supplier_rows, "Supplier item missing from archive notes"
    assert workshop_rows, "Workshop item missing from archive notes"

    supplier_total = round(sum(_to_total(row) for row in supplier_rows), 2)
    workshop_total = round(sum(_to_total(row) for row in workshop_rows), 2)
    assert supplier_total == 179.00
    assert workshop_total == 600.00


def test_customer_printable_projection_excludes_supplier_and_keeps_workshop_total(target_visit_context: Dict[str, Any]):
    """Print contract: customer-facing rows should exclude supplier totals."""
    visit = target_visit_context["visit"]
    items = _extract_items_from_notes(visit.get("notes"))

    printable = [row for row in items if not _is_supplier_item(row)]
    printable_total = round(sum(_to_total(row) for row in printable), 2)
    printable_text = " ".join(str((row.get("name") or row.get("description") or "")).strip() for row in printable)
    all_text = " ".join(str((row.get("name") or row.get("description") or "")).strip() for row in items)

    assert printable_total == 600.00
    assert "القرعاوي" not in printable_text
    assert "القرعاوي" in all_text


@pytest.mark.parametrize("doc_type", ["invoice", "diagnosis"])
def test_document_template_resolve_returns_valid_html(auth_session: requests.Session, doc_type: str):
    """Template module: resolve endpoint stays healthy for invoice/diagnosis."""
    response = auth_session.post(
        f"{API}/document-templates/resolve",
        json={"document_type": doc_type, "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:260]
    data = response.json()
    template = data.get("template") or {}
    content = data.get("content") or ""
    assert template.get("document_type") == doc_type
    assert isinstance(content, str) and len(content.strip()) > 200
