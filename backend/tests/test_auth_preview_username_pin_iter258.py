"""Iteration 258 — Preview auth checks for editable username + per-user quick PIN.

Scope:
- احمد quick PIN (6 digits) works on a new device and resolves accountant role
- مدير quick PIN still works and resolves admin role
- auth_credentials stores احمد pin_hash as bcrypt and never plaintext pin
- Device mismatch across usernames does not reuse wrong device_id
"""

from __future__ import annotations

import os

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

MANAGER_USERNAME = "مدير"
AHMED_USERNAME = "احمد"
QUICK_PIN = os.environ.get("MANAGER_QUICK_PIN", "")
MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    bypass = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')
    if bypass:
        s.headers["x-ratelimit-bypass"] = bypass
    return s


# Quick PIN login (new device) for preview users
def test_quick_pin_manager_and_ahmed_new_device_roles():
    s = _session()

    manager = s.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": QUICK_PIN, "remember_device": True},
        timeout=30,
    )
    assert manager.status_code == 200, manager.text[:250]
    manager_body = manager.json()
    assert manager_body.get("username") == MANAGER_USERNAME
    assert manager_body.get("role") == "admin"
    assert isinstance(manager_body.get("device_id"), str) and manager_body["device_id"].startswith("dev_")

    ahmed = s.post(
        f"{API}/auth/login",
        json={"username": AHMED_USERNAME, "pin": QUICK_PIN, "remember_device": True},
        timeout=30,
    )
    assert ahmed.status_code == 200, ahmed.text[:250]
    ahmed_body = ahmed.json()
    assert ahmed_body.get("username") == AHMED_USERNAME
    assert ahmed_body.get("role") == "accountant"
    assert isinstance(ahmed_body.get("device_id"), str) and ahmed_body["device_id"].startswith("dev_")


# Credential persistence format (bcrypt hash only; no plaintext pin)
def test_auth_credentials_has_ahmed_pin_hash_without_plain_pin_field():
    if not (MONGO_URL and DB_NAME):
        pytest.skip("MONGO_URL/DB_NAME missing")

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    doc = db.auth_credentials.find_one({"username": AHMED_USERNAME}, {"_id": 0})
    client.close()

    assert isinstance(doc, dict)
    pin_hash = doc.get("pin_hash", "")
    assert isinstance(pin_hash, str) and pin_hash.startswith("$2b$")
    assert pin_hash != QUICK_PIN
    assert "pin" not in doc


# Device-id isolation across usernames (wrong trusted device must not be reused)
def test_wrong_username_device_id_not_reused_and_new_device_issued_for_ahmed():
    s = _session()

    manager = s.post(
        f"{API}/auth/login",
        json={"username": MANAGER_USERNAME, "pin": QUICK_PIN, "remember_device": True},
        timeout=30,
    )
    assert manager.status_code == 200
    manager_device = manager.json().get("device_id")
    assert isinstance(manager_device, str) and manager_device.startswith("dev_")

    # Use manager device_id while authenticating as احمد; backend should not trust/reuse it.
    ahmed = s.post(
        f"{API}/auth/login",
        json={
            "username": AHMED_USERNAME,
            "pin": QUICK_PIN,
            "device_id": manager_device,
            "remember_device": True,
        },
        timeout=30,
    )
    assert ahmed.status_code == 200, ahmed.text[:250]
    body = ahmed.json()
    assert body.get("username") == AHMED_USERNAME
    assert body.get("role") == "accountant"
    assert isinstance(body.get("device_id"), str) and body["device_id"].startswith("dev_")
    assert body.get("device_id") != manager_device
