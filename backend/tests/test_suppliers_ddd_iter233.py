"""DDD Suppliers domain — end-to-end CRUD regression (iter 233)."""
from __future__ import annotations
import os
import time

import pytest
import requests

BASE = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")


@pytest.fixture(scope="module")
def created_supplier_id():
    payload = {
        "name": f"DDD-TEST-{int(time.time())}",
        "phone": "0555000000",
        "contactPerson": "Test Person",
        "city": "الرياض",
        "category": "اختبار",
        "rating": 4.5,
    }
    r = requests.post(f"{BASE}/api/suppliers", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    sid = r.json().get("id")
    assert sid
    yield sid
    # cleanup
    requests.delete(f"{BASE}/api/suppliers/{sid}", timeout=10)


def test_list_returns_enriched_suppliers():
    r = requests.get(f"{BASE}/api/suppliers", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) > 0
    sample = body[0]
    # Financial enrichment fields must be present
    for key in ("balance", "debitBalance", "creditBalance", "ajelBalance", "netBalance"):
        assert key in sample, f"missing {key} in supplier payload"


def test_create_returns_full_supplier(created_supplier_id):
    assert created_supplier_id


def test_get_single_supplier(created_supplier_id):
    r = requests.get(f"{BASE}/api/suppliers/{created_supplier_id}", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("id") == created_supplier_id


def test_update_supplier(created_supplier_id):
    r = requests.put(
        f"{BASE}/api/suppliers/{created_supplier_id}",
        json={"phone": "0555111111", "rating": 5.0},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("phone") == "0555111111"


def test_404_for_unknown_supplier():
    r = requests.get(f"{BASE}/api/suppliers/non-existent-id", timeout=10)
    assert r.status_code == 404
