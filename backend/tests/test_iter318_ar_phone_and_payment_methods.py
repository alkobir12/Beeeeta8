"""Iter-318 targeted regression for AR customer phone + payment methods constraints."""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

import pytest
import requests


# Module: environment bootstrap (preview URL from frontend/.env)
BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_ENV_PATH = BASE_DIR / "frontend" / ".env"
WORKSHOP_ID = "finmodule-sync"


def _read_frontend_env_base_url() -> str:
    raw = FRONTEND_ENV_PATH.read_text(encoding="utf-8")
    for line in raw.splitlines():
        if line.strip().startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found in frontend/.env")


BASE_URL = _read_frontend_env_base_url()
AS_OF = datetime.utcnow().strftime("%Y-%m-%d")


@pytest.fixture(scope="session")
def api_client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def auth_headers(api_client: requests.Session) -> Dict[str, str]:
    # Module: auth login contract (manager PIN)
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "مدير", "pin": "123123"},
        timeout=30,
    )
    assert response.status_code == 200, f"Manager login failed: {response.status_code} {response.text[:250]}"
    payload = response.json()
    token = payload.get("access_token") or payload.get("token")
    assert isinstance(token, str) and token.strip(), "Missing login access token"

    set_cookie = response.headers.get("set-cookie", "")
    assert set_cookie, "Expected Set-Cookie on login"
    assert "httponly" in set_cookie.lower(), "Login cookie is not HttpOnly"

    return {"Authorization": f"Bearer {token}"}


def _api_get(
    api_client: requests.Session,
    path: str,
    *,
    headers: Dict[str, str] | None = None,
    params: Dict[str, Any] | None = None,
) -> Any:
    response = api_client.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=45)
    assert response.status_code == 200, f"GET {path} failed: {response.status_code} {response.text[:400]}"
    return response.json()


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _compact_name(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().lower()


# Module: /api/finance/ar/customers contract for phone + id fields
def test_ar_customers_has_customer_identity_and_phone_fields(api_client: requests.Session, auth_headers: Dict[str, str]):
    payload = _api_get(
        api_client,
        "/api/finance/ar/customers",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID, "as_of": AS_OF, "include_today": "true"},
    )
    assert payload.get("success") is True

    data = payload.get("data") or {}
    customers: List[Dict[str, Any]] = data.get("customers") or []
    assert isinstance(customers, list) and len(customers) > 0

    # Every customer row should expose at least one identity key for UI row mapping.
    missing_identity = [row for row in customers if not (str(row.get("id") or "").strip() or str(row.get("customer_id") or "").strip())]
    assert not missing_identity, f"Found AR customer rows missing id/customer_id: {missing_identity[:3]}"

    # Phone key should be present in schema (may be empty for some legacy rows).
    assert all("phone" in row or "customer_phone" in row for row in customers), "Some AR rows missing phone/customer_phone key"


def test_ar_customers_contains_abdulkarim_with_expected_phone(api_client: requests.Session, auth_headers: Dict[str, str]):
    payload = _api_get(
        api_client,
        "/api/finance/ar/customers",
        headers=auth_headers,
        params={"workshop_id": WORKSHOP_ID, "as_of": AS_OF, "include_today": "true"},
    )
    customers: List[Dict[str, Any]] = (payload.get("data") or {}).get("customers") or []

    target = None
    for row in customers:
        name = _compact_name(row.get("customer") or row.get("name"))
        if "عبد الكريم" in name and "الشايعي" in name:
            target = row
            break

    assert target is not None, "Customer عبد الكريم الشايعي not found in /api/finance/ar/customers"
    phone = str(target.get("phone") or target.get("customer_phone") or "").strip()
    assert phone == "0505175565", f"Unexpected phone for عبد الكريم الشايعي: {phone}"
    assert str(target.get("id") or target.get("customer_id") or "").strip(), "Target customer row missing id/customer_id"
    assert _to_float(target.get("balance")) > 0, "Target customer should have positive AR balance in follow-up list"
