"""Iter217 — Approvals OTP regression tests.

Validates: POST /api/approvals returns otp; public GET does not leak otp;
public respond rejects bad OTP (400) and accepts correct OTP (200).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Read from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

assert BASE_URL, "REACT_APP_BACKEND_URL not set"


@pytest.fixture(scope="module")
def vehicle():
    r = requests.get(f"{BASE_URL}/api/vehicles", timeout=20)
    assert r.status_code == 200, r.text
    items = r.json()
    assert items, "no vehicles seeded"
    v = items[0]
    return {"vehicleId": v["id"], "customerId": v.get("customerId")}


@pytest.fixture(scope="module")
def approval(vehicle):
    payload = {
        "title": "TEST_iter217_OTP",
        "amount": 321.5,
        "expiryDays": 3,
        "vehicleId": vehicle["vehicleId"],
        "customerId": vehicle["customerId"],
        "serviceItems": [
            {"name": "تشخيص", "quantity": 1, "price": 321.5, "itemType": "service"}
        ],
    }
    r = requests.post(f"{BASE_URL}/api/approvals", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("token"), "token missing"
    assert data.get("otp"), "otp missing in create response"
    assert str(data["otp"]).isdigit() and len(str(data["otp"])) == 4
    return data


def test_create_returns_otp(approval):
    assert approval["otp"]
    assert approval["status"] == "pending"
    assert approval["amount"] == 321.5


def test_public_get_does_not_leak_otp(approval):
    r = requests.get(f"{BASE_URL}/api/approvals/public/{approval['token']}", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "otp" not in body
    assert "otp_code" not in body
    assert body.get("title") == "TEST_iter217_OTP"
    assert body.get("status") == "pending"


def test_respond_wrong_otp_rejected(approval):
    r = requests.post(
        f"{BASE_URL}/api/approvals/public/{approval['token']}/respond",
        data={"status": "approved", "name": "QA", "phone": "0500000000", "otp": "0000"},
        timeout=20,
    )
    assert r.status_code == 400, r.text
    assert "OTP" in r.text or "رمز" in r.text


def test_respond_correct_otp_accepted(approval):
    r = requests.post(
        f"{BASE_URL}/api/approvals/public/{approval['token']}/respond",
        data={
            "status": "approved",
            "name": "QA",
            "phone": "0500000000",
            "otp": str(approval["otp"]),
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "approved"
    assert body.get("responderName") == "QA"
