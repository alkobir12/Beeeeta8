"""Iteration 326 - Read-only production audit for unified finance + permissions + removed routes."""

import os
import time
from datetime import datetime
from typing import Any, Dict, List

import pytest
import requests
from pymongo import MongoClient


# Module: auth/playbook checks + read-only endpoint integrity + unified-v1 financial flow.


def _read_frontend_env_backend_url() -> str:
    env_path = "/app/frontend/.env"
    if not os.path.exists(env_path):
        return ""
    with open(env_path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _extract_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("count", "total", "totalCount"):
            if isinstance(payload.get(key), int):
                return int(payload[key])
        for key in ("items", "rows", "data", "entries", "results", "customers", "vehicles", "templates"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
    return 0


@pytest.fixture(scope="session")
def base_url() -> str:
    value = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip().rstrip("/")
    if not value:
        value = (_read_frontend_env_backend_url() or "").rstrip("/")
    if not value:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    return value


@pytest.fixture(scope="session")
def bypass_token() -> str:
    raw = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip()
    return raw.strip('"').strip("'")


@pytest.fixture(scope="session")
def manager_session(base_url: str, bypass_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    if bypass_token:
        session.headers["x-ratelimit-bypass"] = bypass_token

    response = session.post(
        f"{base_url}/api/auth/login",
        json={"username": "مدير", "pin": "123123"},
        timeout=30,
    )
    assert response.status_code == 200, f"Manager login failed: {response.status_code} {response.text}"
    token = (response.json() or {}).get("access_token")
    assert isinstance(token, str) and token
    session.headers["Authorization"] = f"Bearer {token}"
    return session


@pytest.fixture(scope="session")
def limited_session(base_url: str, bypass_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    if bypass_token:
        session.headers["x-ratelimit-bypass"] = bypass_token

    response = session.post(
        f"{base_url}/api/auth/login",
        json={"username": "احمد", "pin": "123123"},
        timeout=30,
    )
    assert response.status_code == 200, f"Ahmad login failed: {response.status_code} {response.text}"
    token = (response.json() or {}).get("access_token")
    assert isinstance(token, str) and token
    session.headers["Authorization"] = f"Bearer {token}"
    return session


@pytest.fixture(scope="session")
def sample_vehicle_id() -> str:
    return "f6590225-aef6-452b-af39-e0e42061fd81"


def test_auth_login_sets_httponly_cookie(base_url: str, bypass_token: str):
    session = requests.Session()
    headers = {"Content-Type": "application/json"}
    if bypass_token:
        headers["x-ratelimit-bypass"] = bypass_token
    response = session.post(
        f"{base_url}/api/auth/login",
        headers=headers,
        json={"username": "مدير", "pin": "123123"},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie


def test_auth_cors_credentials_origin_echo_on_login(base_url: str, bypass_token: str):
    headers = {
        "Content-Type": "application/json",
        "Origin": base_url,
    }
    if bypass_token:
        headers["x-ratelimit-bypass"] = bypass_token
    response = requests.post(
        f"{base_url}/api/auth/login",
        headers=headers,
        json={"username": "مدير", "pin": "123123"},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    allow_origin = response.headers.get("Access-Control-Allow-Origin", "")
    allow_credentials = response.headers.get("Access-Control-Allow-Credentials", "")
    assert allow_origin == base_url
    assert allow_credentials.lower() == "true"


def test_manager_pin_hash_stored_as_bcrypt_2b_prefix():
    mongo_url = (os.environ.get("MONGO_URL") or "").strip().strip('"')
    db_name = (os.environ.get("DB_NAME") or "").strip().strip('"')
    manager_username = (os.environ.get("MANAGER_QUICK_USERNAME") or "مدير").strip().strip('"')
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME missing")

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    try:
        doc = client[db_name].auth_credentials.find_one(
            {"username": manager_username},
            {"_id": 0, "pin_hash": 1},
        )
    finally:
        client.close()
    assert doc and isinstance(doc.get("pin_hash"), str)
    assert doc["pin_hash"].startswith("$2b$")


def test_bruteforce_lockout_after_five_failed_attempts(base_url: str):
    username = f"iter326-lockout-{int(time.time())}"
    statuses: List[int] = []
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    for _ in range(6):
        response = session.post(
            f"{base_url}/api/auth/login",
            json={"username": username, "pin": "000000"},
            timeout=30,
        )
        statuses.append(response.status_code)

    assert statuses[-1] == 429, f"Expected 429 on 6th attempt, got {statuses}"


def test_seed_admin_pin_wiring_exists_in_startup_code():
    with open("/app/backend/server.py", "r", encoding="utf-8") as handle:
        source = handle.read()
    assert "MANAGER_QUICK_USERNAME" in source
    assert "MANAGER_QUICK_PIN" in source
    assert "auth_store.ensure_pin" in source


@pytest.mark.parametrize(
    "key,path,query,min_count",
    [
        ("vehicles", "/api/vehicles", None, 50),
        ("customers", "/api/customers", None, 50),
        ("technicians", "/api/technicians", None, 1),
        ("suppliers", "/api/suppliers", None, 1),
        ("parts", "/api/parts", None, 1),
        ("services", "/api/services", None, 1),
        ("operations", "/api/operations", {"limit": 120}, 1),
        ("journal_entries", "/api/finance/journal-entries", {"workshop_id": "finmodule-sync", "limit": 150}, 1),
        ("templates", "/api/document-templates", None, 1),
        ("users", "/api/users", None, 2),
        ("invoices", "/api/invoices", {"limit": 300}, 1),
    ],
)
def test_core_counts_and_non_placeholder_data(
    manager_session: requests.Session,
    base_url: str,
    key: str,
    path: str,
    query: Dict[str, Any],
    min_count: int,
):
    response = manager_session.get(f"{base_url}{path}", params=query, timeout=60)
    assert response.status_code == 200, f"{key}: {response.status_code} {response.text}"
    payload = response.json()
    count = _extract_count(payload)
    print(f"{key}_count={count}")
    assert count >= min_count, f"{key} count below threshold: {count}"


def test_inventory_dashboard_returns_real_aggregates(manager_session: requests.Session, base_url: str):
    response = manager_session.get(f"{base_url}/api/inventory/dashboard", timeout=45)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload, dict)
    assert len(payload.keys()) >= 3
    as_text = str(payload)
    assert "mock" not in as_text.lower()
    assert "placeholder" not in as_text.lower()


def test_unified_financial_summary_formula_and_engine(
    manager_session: requests.Session,
    base_url: str,
    sample_vehicle_id: str,
):
    response = manager_session.get(
        f"{base_url}/api/vehicles/{sample_vehicle_id}/financial-summary",
        timeout=45,
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data.get("engine_version") == "unified-v1"
    workshop = float(data.get("total_workshop") or 0)
    parts = float(data.get("parts_charge_total") or 0)
    customer_total = float(data.get("customer_total") or 0)
    applied = float(data.get("applied_paid") or 0)
    remaining = float(data.get("display_remaining") or 0)

    assert abs(customer_total - (workshop + parts)) < 0.01
    assert abs(remaining - (customer_total - applied)) < 0.01


def test_ar_customers_and_ledger_status_200(manager_session: requests.Session, base_url: str):
    as_of = datetime.utcnow().strftime("%Y-%m-%d")

    customers_response = manager_session.get(
        f"{base_url}/api/finance/ar/customers",
        params={"workshop_id": "finmodule-sync", "as_of": as_of},
        timeout=45,
    )
    assert customers_response.status_code == 200, customers_response.text
    customers_payload = customers_response.json()
    assert (customers_payload.get("success") is True) or isinstance(customers_payload.get("data"), dict)

    ledger_response = manager_session.get(
        f"{base_url}/api/finance/ar/ledger",
        params={"workshop_id": "finmodule-sync"},
        timeout=45,
    )
    assert ledger_response.status_code == 200, ledger_response.text
    ledger_payload = ledger_response.json()
    assert (ledger_payload.get("success") is True) or isinstance(ledger_payload.get("data"), dict)


def test_dry_run_confirm_payment_returns_preview_without_mutation(
    manager_session: requests.Session,
    base_url: str,
    sample_vehicle_id: str,
):
    summary_before = manager_session.get(
        f"{base_url}/api/vehicles/{sample_vehicle_id}/financial-summary",
        timeout=45,
    )
    assert summary_before.status_code == 200
    before_payload = summary_before.json()
    visits = before_payload.get("visits") or []
    assert isinstance(visits, list) and len(visits) > 0

    target_visit = next((v for v in visits if float(v.get("display_remaining") or 0) > 0), visits[0])
    visit_id = str(target_visit.get("visit_id") or "").strip()
    assert visit_id

    confirmed_before = float(before_payload.get("confirmed_paid") or 0)
    remaining_before = float(before_payload.get("display_remaining") or 0)

    response = manager_session.post(
        f"{base_url}/api/finance-engine/visits/{visit_id}/payments/confirm",
        json={
            "amount": 150,
            "method": "cash",
            "dry_run": True,
            "workshop_id": "finmodule-sync",
            "reference": "iter326-readonly",
        },
        timeout=45,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("dry_run") is True
    assert (payload.get("payment") or {}).get("confirmed") is True
    assert isinstance(payload.get("journal_preview"), dict)

    summary_after = manager_session.get(
        f"{base_url}/api/vehicles/{sample_vehicle_id}/financial-summary",
        timeout=45,
    )
    assert summary_after.status_code == 200
    after_payload = summary_after.json()
    assert abs(float(after_payload.get("confirmed_paid") or 0) - confirmed_before) < 0.01
    assert abs(float(after_payload.get("display_remaining") or 0) - remaining_before) < 0.01


def test_removed_apis_return_404(manager_session: requests.Session, base_url: str):
    removed_paths = [
        "/api/injectors/engines",
        "/api/fault-knowledge",
        "/api/moltbot/pages",
        "/api/moltbot",
    ]
    for path in removed_paths:
        response = manager_session.get(f"{base_url}{path}", timeout=30)
        assert response.status_code == 404, f"{path} expected 404, got {response.status_code}"


def test_limited_user_forbidden_on_delete_operations_and_biz_account(
    limited_session: requests.Session,
    base_url: str,
):
    op_delete = limited_session.delete(f"{base_url}/api/operations/non-existent-op-id", timeout=30)
    assert op_delete.status_code == 403, f"operations delete expected 403, got {op_delete.status_code}"

    biz_delete = limited_session.delete(f"{base_url}/api/biz-accounts/non-existent-account-id", timeout=30)
    assert biz_delete.status_code == 403, f"biz-account delete expected 403, got {biz_delete.status_code}"


def test_limited_user_dry_run_payment_permission_probe(
    limited_session: requests.Session,
    manager_session: requests.Session,
    base_url: str,
    sample_vehicle_id: str,
):
    summary = manager_session.get(f"{base_url}/api/vehicles/{sample_vehicle_id}/financial-summary", timeout=45)
    assert summary.status_code == 200
    visits = (summary.json() or {}).get("visits") or []
    visit_id = str((visits[0] if visits else {}).get("visit_id") or "").strip()
    if not visit_id:
        pytest.skip("No visit available for limited-user payment probe")

    response = limited_session.post(
        f"{base_url}/api/finance-engine/visits/{visit_id}/payments/confirm",
        json={
            "amount": 25,
            "method": "cash",
            "dry_run": True,
            "workshop_id": "finmodule-sync",
            "reference": "iter326-ahmad-dry-run",
        },
        timeout=45,
    )
    assert response.status_code in {200, 403}, response.text
