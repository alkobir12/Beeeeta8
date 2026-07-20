"""Iteration 263 — Quick print preview regression (invoice/diagnosis).

Modules/features covered:
- Auth login for preview manager PIN
- Vehicle + visits fetch used by VehicleDetails print payload
- /api/documents/generate invoice and diagnosis HTML integrity
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
    items = parsed.get("items")
    return items if isinstance(items, list) else []


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    qty = float(item.get("quantity") or item.get("qty") or 1)
    price = float(item.get("price") or item.get("unit_price") or item.get("unitPrice") or item.get("amount") or 0)
    name = item.get("name") or item.get("description") or item.get("serviceName") or "بند"
    return {
        "name": name,
        "description": name,
        "quantity": qty,
        "qty": qty,
        "price": price,
        "unit_price": price,
        "total": float(item.get("total") or (qty * price)),
    }


@pytest.fixture(scope="module")
def auth_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if RATE_BYPASS:
        s.headers["x-ratelimit-bypass"] = RATE_BYPASS

    login = s.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": MANAGER_PIN},
        timeout=30,
    )
    if login.status_code != 200:
        pytest.skip(f"Manager login unavailable in shared preview: {login.status_code} {login.text[:120]}")

    token = login.json().get("access_token")
    if not token:
        pytest.skip("Login succeeded but access_token missing")

    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def seed_context(auth_session: requests.Session) -> Dict[str, Any]:
    profile_r = auth_session.get(f"{API}/profile", timeout=30)
    settings_r = auth_session.get(f"{API}/settings", timeout=30)
    vehicles_r = auth_session.get(f"{API}/vehicles", timeout=30)

    assert profile_r.status_code == 200, profile_r.text[:200]
    assert settings_r.status_code == 200, settings_r.text[:200]
    assert vehicles_r.status_code == 200, vehicles_r.text[:200]

    profile = profile_r.json() if isinstance(profile_r.json(), dict) else {}
    settings = settings_r.json() if isinstance(settings_r.json(), dict) else {}
    vehicles = vehicles_r.json() if isinstance(vehicles_r.json(), list) else []
    assert vehicles, "No vehicles returned from /api/vehicles"

    preferred = next(
        (v for v in vehicles if "1854" in str(v.get("plateNumber") or v.get("plate") or "")),
        vehicles[0],
    )
    vehicle_id = preferred.get("id")
    assert vehicle_id, "Vehicle missing id"

    visits_r = auth_session.get(f"{API}/vehicles/{vehicle_id}/visits", timeout=30)
    assert visits_r.status_code == 200, visits_r.text[:200]
    visits = visits_r.json() if isinstance(visits_r.json(), list) else []
    assert visits, "No visits returned for selected vehicle"

    active_visit = next((v for v in visits if (v.get("status") or "") == "in_progress"), visits[0])

    return {
        "profile": profile,
        "settings": settings,
        "vehicle": preferred,
        "visit": active_visit,
    }


def _build_workshop(profile: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, Any]:
    name = profile.get("business_name") or profile.get("name") or settings.get("workshopName") or "الورشة"
    phone = profile.get("phone") or profile.get("phone_number") or profile.get("whatsapp") or settings.get("workshopPhone") or ""
    commercial = profile.get("commercialRegister") or profile.get("commercial_register") or settings.get("commercialRegister") or ""
    tax = profile.get("taxNumber") or profile.get("tax_number") or settings.get("taxNumber") or ""
    return {
        "name": name,
        "business_name": name,
        "phone": phone,
        "address": profile.get("address") or settings.get("workshopAddress") or "",
        "commercial_register": commercial,
        "commercialRegister": commercial,
        "tax_number": tax,
        "taxNumber": tax,
        "email": profile.get("email") or settings.get("workshopEmail") or "",
        "logo": profile.get("logo") or profile.get("logo_url") or "",
    }


def _build_payload(doc_type: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    visit = ctx["visit"]
    vehicle = ctx["vehicle"]
    profile = ctx["profile"]
    settings = ctx["settings"]

    notes_items = _extract_items_from_notes(visit.get("notes"))
    items = [_normalize_item(i) for i in notes_items] if notes_items else [
        _normalize_item(
            {
                "name": visit.get("diagnosis") or visit.get("issue") or "فحص",
                "quantity": 1,
                "price": visit.get("total_workshop") or visit.get("workshop_total") or visit.get("total") or 0,
            }
        )
    ]

    return {
        "doc_type": doc_type,
        "workshop": _build_workshop(profile, settings),
        "items": items,
        "customer": {
            "name": vehicle.get("customerName") or vehicle.get("ownerName") or "",
            "phone": vehicle.get("customerPhone") or vehicle.get("ownerPhone") or "",
        },
        "vehicle": {
            "plate": vehicle.get("plateNumber") or vehicle.get("plate") or "",
            "plateNumber": vehicle.get("plateNumber") or vehicle.get("plate") or "",
            "model": vehicle.get("vehicleModel") or vehicle.get("model") or "",
            "brand": vehicle.get("vehicleBrand") or vehicle.get("brand") or "",
            "year": vehicle.get("year") or vehicle.get("vehicleYear") or "",
            "vin": vehicle.get("vin") or vehicle.get("chassisNumber") or "",
            "mileage": vehicle.get("mileage") or visit.get("mileage") or "",
            "notes": "",
        },
        "settings": {
            "document_number": visit.get("invoiceNumber") or visit.get("id") or "",
            "document_title": "فاتورة" if doc_type == "invoice" else "تقرير تشخيص",
            "date": str(visit.get("created_at") or visit.get("createdAt") or "")[:10],
            "description": "خدمات صيانة وإصلاح" if doc_type == "invoice" else "تقرير تشخيص للمركبة",
        },
    }


def test_profile_and_settings_are_accessible_after_login(auth_session: requests.Session):
    profile_r = auth_session.get(f"{API}/profile", timeout=30)
    settings_r = auth_session.get(f"{API}/settings", timeout=30)

    assert profile_r.status_code == 200
    assert settings_r.status_code == 200

    profile = profile_r.json()
    assert isinstance(profile, dict)
    assert "name" in profile or "business_name" in profile


def test_dashboard_summaries_endpoint_returns_data_for_existing_vehicles(auth_session: requests.Session, seed_context: Dict[str, Any]):
    vehicle_id = seed_context["vehicle"]["id"]
    r = auth_session.post(
        f"{API}/vehicles/dashboard/summaries",
        json={"vehicle_ids": [vehicle_id]},
        timeout=30,
    )
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert isinstance(data, dict)
    assert isinstance(data.get("summaries"), list)


def test_invoice_document_generation_contains_workshop_and_context(auth_session: requests.Session, seed_context: Dict[str, Any]):
    payload = _build_payload("invoice", seed_context)
    r = auth_session.post(f"{API}/documents/generate", json=payload, timeout=40)
    assert r.status_code == 200, r.text[:300]

    body = r.json()
    assert body.get("success") is True
    html = body.get("html") or ""
    assert isinstance(html, str) and len(html) > 200

    # Workshop identity checks requested by user
    assert "ورشة عبدالله الكبير" in html
    assert "0553280100" in html
    assert "1131051365" in html

    # Invoice + context checks
    assert ("فاتورة مبيعات" in html) or ("فاتورة" in html)
    assert ("العميل" in html) or ("عميل" in html)
    assert ("اللوحة" in html) or (str(seed_context["vehicle"].get("plateNumber") or "") in html)


def test_diagnosis_document_generation_contains_workshop_and_vehicle_context(auth_session: requests.Session, seed_context: Dict[str, Any]):
    payload = _build_payload("diagnosis", seed_context)
    r = auth_session.post(f"{API}/documents/generate", json=payload, timeout=40)
    assert r.status_code == 200, r.text[:300]

    body = r.json()
    assert body.get("success") is True
    html = body.get("html") or ""
    assert isinstance(html, str) and len(html) > 200

    assert "تقرير تشخيص" in html
    assert "ورشة عبدالله الكبير" in html
    assert "0553280100" in html
    assert ("اللوحة" in html) or (str(seed_context["vehicle"].get("plateNumber") or "") in html)
