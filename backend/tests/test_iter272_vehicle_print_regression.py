"""Iteration 272 — Vehicle quick print regression checks.

Modules/features covered:
- Manager PIN authentication on preview
- Vehicle details data fetch for target vehicle
- /api/documents/generate for invoice/diagnosis/quote with workshop identity assertions
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
TARGET_VEHICLE_ID = "ffcf800c-d1bb-40df-8df3-effa59bc05cd"


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
        pytest.skip(f"Manager login unavailable in preview: {login.status_code} {login.text[:120]}")

    token = login.json().get("access_token")
    if not token:
        pytest.skip("Login succeeded but access_token missing")

    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def vehicle_context(auth_session: requests.Session) -> Dict[str, Any]:
    profile_r = auth_session.get(f"{API}/profile", timeout=30)
    settings_r = auth_session.get(f"{API}/settings", timeout=30)
    vehicle_r = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}", timeout=30)
    visits_r = auth_session.get(f"{API}/vehicles/{TARGET_VEHICLE_ID}/visits", timeout=30)

    assert profile_r.status_code == 200, profile_r.text[:200]
    assert settings_r.status_code == 200, settings_r.text[:200]
    assert vehicle_r.status_code == 200, vehicle_r.text[:200]
    assert visits_r.status_code == 200, visits_r.text[:200]

    vehicle = vehicle_r.json() if isinstance(vehicle_r.json(), dict) else {}
    visits = visits_r.json() if isinstance(visits_r.json(), list) else []
    assert vehicle.get("id") == TARGET_VEHICLE_ID
    assert visits, "No visits found for target vehicle"

    preferred_visit = next((v for v in visits if (v.get("status") or "") == "in_progress"), visits[0])

    return {
        "profile": profile_r.json() if isinstance(profile_r.json(), dict) else {},
        "settings": settings_r.json() if isinstance(settings_r.json(), dict) else {},
        "vehicle": vehicle,
        "visit": preferred_visit,
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

    title_map = {
        "invoice": "فاتورة",
        "diagnosis": "تقرير تشخيص",
        "quote": "عرض سعر",
    }

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
            "document_title": title_map.get(doc_type, "مستند"),
            "date": str(visit.get("created_at") or visit.get("createdAt") or "")[:10],
            "description": "خدمات صيانة وإصلاح",
        },
    }


@pytest.mark.parametrize(
    "doc_type,required_title",
    [
        ("invoice", "فاتورة"),
        ("diagnosis", "تقرير تشخيص"),
        ("quote", "عرض سعر"),
    ],
)
def test_documents_generate_for_vehicle_print_flow(
    auth_session: requests.Session,
    vehicle_context: Dict[str, Any],
    doc_type: str,
    required_title: str,
):
    payload = _build_payload(doc_type, vehicle_context)
    response = auth_session.post(f"{API}/documents/generate", json=payload, timeout=40)

    assert response.status_code == 200, response.text[:300]
    body = response.json()
    assert body.get("success") is True

    html = body.get("html") or ""
    assert isinstance(html, str) and len(html) > 200

    # Requested workshop identity checks
    assert "ورشة عبدالله الكبير" in html
    assert "0553280100" in html
    assert "1131051365" in html

    # Document type + core context checks
    assert required_title in html
    assert ("العميل" in html) or ("عميل" in html)
    assert ("اللوحة" in html) or (str(vehicle_context["vehicle"].get("plateNumber") or "") in html)
