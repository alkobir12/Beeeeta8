"""Iteration 285 — CUSTOMER_NAME placeholder guard backend checks.

Modules/features covered:
- Upload valid HTML template containing {CUSTOMER_NAME}
- Explicit use endpoint returns uploaded template content
- /api/document-templates/events persists template_incomplete with CUSTOMER_NAME
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

MANAGER_USERNAME = "مدير"
MANAGER_PIN = "123123"
RATE_BYPASS = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')

RUNTIME_PATH = Path("/app/test_reports/iter285_runtime.json")


@pytest.fixture(scope="module")
def auth_session() -> requests.Session:
    # Module: authenticated session for template APIs.
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
        pytest.skip(f"Manager login unavailable: {login.status_code} {login.text[:120]}")
    body = login.json() if login.headers.get("content-type", "").startswith("application/json") else {}
    token = body.get("access_token")
    if not token:
        pytest.skip("access_token missing")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def mongo_collection():
    # Module: persistence check in Mongo audit collection.
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL/DB_NAME missing; cannot validate Mongo persistence")
    client = MongoClient(MONGO_URL)
    collection = client[DB_NAME]["document_template_resolution_audit"]
    try:
        yield collection
    finally:
        client.close()


@pytest.fixture(scope="module")
def uploaded_template(auth_session: requests.Session):
    # Module: upload template with CUSTOMER_NAME placeholder only.
    template_name = f"ITER285_UI_CUSTOMER_NAME_ONLY_{int(time.time())}"
    html = """<!doctype html>
<html lang=\"ar\" dir=\"rtl\"><head><meta charset=\"utf-8\" /><title>Iter285</title></head>
<body>
  <h1>اختبار اكتمال القالب</h1>
  <p data-testid=\"iter285-customer\">العميل: {CUSTOMER_NAME}</p>
  <p>التاريخ: {DATE}</p>
</body></html>"""

    files = {"file": (f"{template_name}.html", html.encode("utf-8"), "text/html")}
    data = {
        "name": template_name,
        "description": "Iter285 CUSTOMER_NAME unresolved guard",
        "document_type": "invoice",
        "tenant_id": "default",
        "locale": "ar-SA",
    }

    previous_content_type = auth_session.headers.pop("Content-Type", None)
    try:
        response = auth_session.post(f"{API}/document-templates/upload", files=files, data=data, timeout=30)
    finally:
        if previous_content_type:
            auth_session.headers["Content-Type"] = previous_content_type

    assert response.status_code == 200, response.text[:300]
    template = response.json().get("template") or {}
    assert template.get("id")
    assert template.get("name") == template_name
    assert template.get("document_type") == "invoice"
    assert template.get("file_type") == "html"
    assert template.get("status") == "valid"

    payload = {"template_id": template["id"], "template_name": template_name}
    RUNTIME_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return template


def test_uploaded_template_is_explicitly_usable(
    auth_session: requests.Session,
    uploaded_template,
):
    # Module: /use returns uploaded template content with CUSTOMER_NAME placeholder.
    response = auth_session.post(
        f"{API}/document-templates/{uploaded_template['id']}/use",
        json={"document_type": "invoice", "tenant_id": "default", "locale": "ar-SA"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    data = response.json()
    content = data.get("content") or ""
    assert data.get("template", {}).get("id") == uploaded_template["id"]
    assert data.get("selection_reason") == "explicit_document_template"
    assert "{CUSTOMER_NAME}" in content


def test_events_persist_template_incomplete_with_customer_name(
    auth_session: requests.Session,
    uploaded_template,
    mongo_collection,
):
    # Module: /events stores template_incomplete with missing CUSTOMER_NAME.
    response = auth_session.post(
        f"{API}/document-templates/events",
        json={
            "event": "template_incomplete",
            "template_id": uploaded_template["id"],
            "document_type": "invoice",
            "missing_variables": ["CUSTOMER_NAME"],
            "reason": "iter285_customer_name_missing",
            "tenant_id": "default",
            "locale": "ar-SA",
        },
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    body = response.json()
    assert body.get("success") is True
    event_id = body.get("event_id")
    assert isinstance(event_id, str) and len(event_id) > 10

    saved = mongo_collection.find_one({"id": event_id})
    assert isinstance(saved, dict)
    assert saved.get("event") == "template_incomplete"
    assert saved.get("template_id") == uploaded_template["id"]
    assert "CUSTOMER_NAME" in (saved.get("missing_variables") or [])


def test_create_vehicle_without_customer_name_for_quickprint_ui(auth_session: requests.Session):
    # Module: create a real vehicle with blank customer name so QuickPrint should surface CUSTOMER_NAME missing.
    unique = str(int(time.time()))[-8:]
    payload = {
        "plateNumber": f"ITER285-{unique}",
        "brand": "Toyota",
        "model": "Corolla",
        "year": 2022,
        "color": "Silver",
        "customerName": "",
        "customerPhone": "0500000000",
        "services": [],
    }
    response = auth_session.post(f"{API}/vehicles", json=payload, timeout=30)
    assert response.status_code in {200, 201}, response.text[:300]
    body = response.json()
    vehicle_id = body.get("id")
    assert isinstance(vehicle_id, str) and vehicle_id

    runtime = {}
    if RUNTIME_PATH.exists():
        runtime = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
    runtime["vehicle_id"] = vehicle_id
    runtime["vehicle_plate"] = payload["plateNumber"]
    RUNTIME_PATH.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")

    fetched = auth_session.get(f"{API}/vehicles/{vehicle_id}", timeout=30)
    assert fetched.status_code == 200, fetched.text[:300]
    fetched_body = fetched.json()
    customer_name = str(fetched_body.get("customerName") or fetched_body.get("customer_name") or "")
    assert customer_name.strip() == ""
