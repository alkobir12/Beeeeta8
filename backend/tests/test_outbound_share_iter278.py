"""اختبارات القنوات الصادرة (PDF وواتساب) — iter278.

تغطي: القوالب المزروعة، اختيار paid/partial/unpaid، حظر superseded،
البصمة (ثبات/إبطال/عزل المستأجرين)، كاش الأصول، سجل التدقيق الصارم
(رفض sent/delivered/read)، idempotency، versioning/restore/validation،
وعدم تراجع /api/documents/generate.
"""

import base64
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE = os.environ.get("TEST_API_BASE", "http://localhost:8001")
BYPASS = os.environ.get("RATE_LIMIT_BYPASS_TOKEN", "")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers["x-ratelimit-bypass"] = BYPASS
    r = s.post(f"{BASE}/api/auth/login", json={"username": "مدير", "pin": "123123"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("access_token") or r.json().get("token")
    assert token
    s.headers["Authorization"] = f"Bearer {token}"
    s.cookies.clear()
    return s


def _payload(status="paid", doc_number="INV-TEST-278", phone="0555555555"):
    return {
        "workshop": {"name": "ورشة الاختبار", "phone": "0501001220"},
        "customer": {"name": "عميل الاختبار", "phone": phone},
        "vehicle": {"brand": "تويوتا", "model": "كامري", "year": "2022", "plateNumber": "أ ب ج 1234"},
        "items": [{"description": "تغيير زيت", "quantity": 1, "unit_price": 150, "discount": 0}],
        "payment": {"paid": 150 if status == "paid" else (50 if status == "partial" else 0)},
        "settings": {"document_number": doc_number, "date": "2026-06-01",
                     "status": status, "seal_code": "ES-TEST1234",
                     "totals": {"paid": 150 if status == "paid" else (50 if status == "partial" else 0)}},
    }


def _material(doc_number="INV-FP-278", version=1, tenant="default"):
    return {
        "tenant_id": tenant,
        "document_number": doc_number,
        "document_version": version,
        "doc_type": "invoice",
        "status": "paid",
        "locale": "ar",
        "template_id": "builtin-dash-sealed-invoice",
        "template_version": "v1",
        "workshop_snapshot": {"name": "ورشة الاختبار"},
        "customer_snapshot": {"name": "عميل الاختبار", "phone": "0555555555"},
        "vehicle_snapshot": {"plateNumber": "أ ب ج 1234"},
        "line_items": [{"description": "تغيير زيت", "quantity": 1, "unit_price": 150, "discount": 0}],
        "totals": {"subtotal": 150, "discount": 0, "total": 150, "paid": 150, "remaining": 0},
        "taxes": {"tax": 0},
    }


# ---------- 1. القوالب المزروعة ----------

def test_seed_templates_exist(session):
    r = session.get(f"{BASE}/api/outbound/templates")
    assert r.status_code == 200
    keys = {t["action_key"] for t in r.json()["templates"]}
    for expected in ("invoice_paid", "invoice_partial", "invoice_unpaid",
                     "invoice_default", "quote_default", "diagnosis_default", "receipt_default"):
        assert expected in keys, f"missing seed {expected}"


def test_variables_registry(session):
    r = session.get(f"{BASE}/api/outbound/variables")
    assert r.status_code == 200
    keys = {v["key"] for v in r.json()["variables"]}
    assert {"CUSTOMER_NAME", "TOTAL", "SEAL_CODE", "REMAINING"} <= keys


# ---------- 2. اختيار القالب حسب الحالة ----------

@pytest.mark.parametrize("status,expected_key,needle", [
    ("paid", "invoice_paid", "مدفوعة بالكامل"),
    ("partial", "invoice_partial", "المتبقي"),
    ("unpaid", "invoice_unpaid", "سداد المبلغ المستحق"),
    ("draft", "invoice_default", "مستندكم رقم"),
])
def test_resolve_picks_correct_template(session, status, expected_key, needle):
    r = session.post(f"{BASE}/api/outbound/resolve-message", json={
        "doc_type": "invoice", "status": status, "payload": _payload(status)})
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data["template"]["action_key"] == expected_key
    assert needle in data["message"]
    assert "عميل الاختبار" in data["message"]
    assert "ES-TEST1234" in data["message"]
    assert "{{" not in data["message"]


def test_resolve_superseded_blocked(session):
    r = session.post(f"{BASE}/api/outbound/resolve-message", json={
        "doc_type": "invoice", "status": "superseded", "payload": _payload("superseded")})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "superseded_document"


def test_resolve_invalid_phone_flagged(session):
    r = session.post(f"{BASE}/api/outbound/resolve-message", json={
        "doc_type": "invoice", "status": "paid", "payload": _payload("paid", phone="123")})
    assert r.status_code == 200
    assert r.json()["phone"]["valid"] is False


def test_resolve_phone_normalized_e164(session):
    r = session.post(f"{BASE}/api/outbound/resolve-message", json={
        "doc_type": "invoice", "status": "paid", "payload": _payload("paid", phone="٠٥٥٥٥٥٥٥٥٥")})
    assert r.status_code == 200
    assert r.json()["phone"]["e164"] == "+966555555555"


# ---------- 3. البصمة ----------

def test_fingerprint_stable_and_version_invalidation(session):
    m = _material(doc_number=f"INV-FP-{uuid.uuid4().hex[:6]}")
    fp1 = session.post(f"{BASE}/api/outbound/fingerprint", json={"material": m}).json()["fingerprint"]
    fp2 = session.post(f"{BASE}/api/outbound/fingerprint", json={"material": m}).json()["fingerprint"]
    assert fp1 == fp2
    m2 = dict(m, document_version=2)
    fp3 = session.post(f"{BASE}/api/outbound/fingerprint", json={"material": m2}).json()["fingerprint"]
    assert fp3 != fp1
    m3 = dict(m, template_version="v2")
    fp4 = session.post(f"{BASE}/api/outbound/fingerprint", json={"material": m3}).json()["fingerprint"]
    assert fp4 != fp1


def test_fingerprint_tenant_isolation(session):
    doc = f"INV-TEN-{uuid.uuid4().hex[:6]}"
    fp_a = session.post(f"{BASE}/api/outbound/fingerprint",
                        json={"material": _material(doc, tenant="tenant_a")}).json()["fingerprint"]
    fp_b = session.post(f"{BASE}/api/outbound/fingerprint",
                        json={"material": _material(doc, tenant="tenant_b")}).json()["fingerprint"]
    assert fp_a != fp_b


# ---------- 4. الأصول والكاش ----------

def test_asset_cache_roundtrip(session):
    doc = f"INV-AST-{uuid.uuid4().hex[:6]}"
    m = _material(doc)
    fp_res = session.post(f"{BASE}/api/outbound/fingerprint", json={"material": m}).json()
    assert fp_res["cached"] is False
    pdf_b64 = base64.b64encode(b"%PDF-1.4 test-pdf-bytes").decode()
    img_b64 = base64.b64encode(b"jpeg-preview-bytes").decode()
    up = session.post(f"{BASE}/api/outbound/assets", json={
        "material": m, "pdf_base64": pdf_b64, "preview_image_base64": img_b64})
    assert up.status_code == 200
    body = up.json()
    assert body["reused"] is False
    assert body.get("trace_id", "").startswith("tr-")
    fingerprint = body["fingerprint"]
    # second fingerprint check → cached
    fp_res2 = session.post(f"{BASE}/api/outbound/fingerprint", json={"material": m}).json()
    assert fp_res2["cached"] is True and fp_res2["has_pdf"] is True
    # second upload same material → reused, no duplicate
    up2 = session.post(f"{BASE}/api/outbound/assets", json={
        "material": m, "pdf_base64": pdf_b64, "preview_image_base64": img_b64})
    assert up2.json()["reused"] is True
    # retrieve full asset
    got = session.get(f"{BASE}/api/outbound/assets/{fingerprint}")
    assert got.status_code == 200
    assert got.json()["asset"]["pdf_base64"] == pdf_b64


def test_asset_tenant_isolation_on_read(session):
    doc = f"INV-ISO-{uuid.uuid4().hex[:6]}"
    m = _material(doc, tenant="tenant_a")
    pdf_b64 = base64.b64encode(b"%PDF isolated").decode()
    up = session.post(f"{BASE}/api/outbound/assets", json={"material": m, "pdf_base64": pdf_b64})
    fingerprint = up.json()["fingerprint"]
    ok = session.get(f"{BASE}/api/outbound/assets/{fingerprint}", params={"tenant_id": "tenant_a"})
    assert ok.status_code == 200
    denied = session.get(f"{BASE}/api/outbound/assets/{fingerprint}", params={"tenant_id": "tenant_b"})
    assert denied.status_code == 404


# ---------- 5. سجل محاولات المشاركة ----------

def test_share_attempt_lifecycle_and_forbidden_events(session):
    idem = f"idem-{uuid.uuid4().hex[:10]}"
    r = session.post(f"{BASE}/api/outbound/share-attempts", json={
        "doc_type": "invoice", "document_number": "INV-AUDIT-278",
        "fingerprint": "fp-test", "action_key": "invoice_paid",
        "phone": "0555555555", "message_text": "رسالة اختبار",
        "initial_event": "message_prepared", "idempotency_key": idem})
    assert r.status_code == 200
    attempt = r.json()["attempt"]
    assert attempt["trace_id"].startswith("tr-")
    assert attempt["status"] == "message_prepared"
    assert attempt["phone_e164"] == "+966555555555"
    aid = attempt["id"]
    # allowed events
    for ev in ("pdf_generated", "preview_image_generated", "whatsapp_opened", "files_downloaded"):
        er = session.post(f"{BASE}/api/outbound/share-attempts/{aid}/events", json={"event": ev})
        assert er.status_code == 200, f"{ev}: {er.text[:200]}"
    # forbidden events strictly rejected
    for ev in ("sent", "delivered", "read"):
        er = session.post(f"{BASE}/api/outbound/share-attempts/{aid}/events", json={"event": ev})
        assert er.status_code == 422, f"{ev} must be forbidden"
        assert er.json()["detail"]["code"] == "forbidden_event"
    # idempotency: same key returns same attempt
    r2 = session.post(f"{BASE}/api/outbound/share-attempts", json={
        "doc_type": "invoice", "document_number": "INV-AUDIT-278",
        "initial_event": "message_prepared", "idempotency_key": idem})
    assert r2.json()["reused"] is True
    assert r2.json()["attempt"]["id"] == aid
    # audit listing shows the events without any sent/delivered
    lst = session.get(f"{BASE}/api/outbound/share-attempts",
                      params={"document_number": "INV-AUDIT-278"})
    events = [e["event"] for a in lst.json()["attempts"] for e in a["events"]]
    assert "whatsapp_opened" in events
    assert not {"sent", "delivered", "read"} & set(events)


def test_share_attempt_rejects_forbidden_initial_event(session):
    r = session.post(f"{BASE}/api/outbound/share-attempts", json={
        "doc_type": "invoice", "initial_event": "sent"})
    assert r.status_code == 422


# ---------- 6. حوكمة القوالب ----------

def test_template_update_validation_and_versioning(session):
    tpl = session.get(f"{BASE}/api/outbound/templates").json()["templates"]
    target = next(t for t in tpl if t["action_key"] == "receipt_default")
    version_before = target["version"]
    # unknown variable rejected
    bad = session.put(f"{BASE}/api/outbound/templates/{target['id']}",
                      json={"body": "مرحبا {{NOT_A_VAR}}"})
    assert bad.status_code == 422
    assert "NOT_A_VAR" in bad.json()["detail"]["unknown_variables"]
    # empty body rejected
    empty = session.put(f"{BASE}/api/outbound/templates/{target['id']}", json={"body": "  "})
    assert empty.status_code == 422
    # valid update bumps version
    ok = session.put(f"{BASE}/api/outbound/templates/{target['id']}",
                     json={"body": "سند {{INVOICE_NO}} للعميل {{CUSTOMER_NAME}} — {{WORKSHOP_NAME}}"})
    assert ok.status_code == 200
    assert ok.json()["template"]["version"] == version_before + 1
    # restore default
    rest = session.post(f"{BASE}/api/outbound/templates/{target['id']}/restore-default")
    assert rest.status_code == 200
    restored = rest.json()["template"]
    assert restored["body"] == restored["default_body"]
    assert restored["version"] == version_before + 2


def test_template_duplicate_active_action_key_blocked(session):
    tpl = session.get(f"{BASE}/api/outbound/templates").json()["templates"]
    default = next(t for t in tpl if t["action_key"] == "invoice_default")
    dup = session.put(f"{BASE}/api/outbound/templates/{default['id']}",
                      json={"action_key": "invoice_paid"})
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "duplicate_active_action_key"


def test_template_disable_enable_cycle(session):
    tpl = session.get(f"{BASE}/api/outbound/templates").json()["templates"]
    target = next(t for t in tpl if t["action_key"] == "quote_default")
    off = session.put(f"{BASE}/api/outbound/templates/{target['id']}", json={"enabled": False})
    assert off.status_code == 200 and off.json()["template"]["enabled"] is False
    # resolve quote now fails (no active template)
    r = session.post(f"{BASE}/api/outbound/resolve-message", json={
        "doc_type": "quote", "status": "draft", "payload": _payload("draft")})
    assert r.status_code == 404
    on = session.put(f"{BASE}/api/outbound/templates/{target['id']}", json={"enabled": True})
    assert on.status_code == 200 and on.json()["template"]["enabled"] is True


# ---------- 7. عدم تراجع الطباعة ----------

def test_documents_generate_regression(session):
    r = session.post(f"{BASE}/api/documents/generate", json=_payload("paid") | {"doc_type": "invoice"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True and "<html" in body["html"].lower()


def test_outbound_requires_auth():
    r = requests.get(f"{BASE}/api/outbound/templates",
                     headers={"x-ratelimit-bypass": BYPASS})
    assert r.status_code == 401
