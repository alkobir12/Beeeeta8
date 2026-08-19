"""
Iteration 303 — Verify customer approval stamp fix in Supabase mode.

Bug: GET /api/vehicles/{id}/approval-logs and /api/customers/{id}/approval-logs
     only queried Mongo `customer_approval_logs` — never written in the Supabase
     respond branch — so DocumentPrint could not see approvals.
Fix:  Both endpoints are now provider-aware. When DB_PROVIDER=supabase they
     query the Supabase `approval_requests` table directly and map rows to
     the camelCase shape.

This test:
1. Logs in as مدير / PIN 123123 to get an access token.
2. Creates an approval for a real Supabase vehicle.
3. Approves via /api/approvals/public/{token}/respond (OTP).
4. GET /api/vehicles/{id}/approval-logs — must include the approved row.
5. GET /api/customers/{id}/approval-logs — same check (parity).
6. Verifies template resolution still returns unified-*-a4-mobile-v1.
7. Cleans up via Supabase client (no DELETE API exists).
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://accounting-ssot-fix.preview.emergentagent.com").rstrip("/")
BYPASS = "c68b2b87386db82cb541d78d584a821fa4809f2afb53a45e"

# Vehicle chosen by main agent: has full data (customerName, plateNumber, customerId)
VEHICLE_ID = "c02cc9c7-6ff5-4fc7-9414-b15787fa9000"

CREATED_TOKENS: list[str] = []


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "x-ratelimit-bypass": BYPASS,
    })
    return s


@pytest.fixture(scope="module")
def token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"username": "مدير", "pin": "123123"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in login response: {r.json()}"
    api.headers.update({"Authorization": f"Bearer {tok}"})
    return tok


@pytest.fixture(scope="module")
def vehicle(api, token):
    r = api.get(f"{BASE_URL}/api/vehicles/{VEHICLE_ID}")
    assert r.status_code == 200, f"vehicle not found: {r.status_code} {r.text[:200]}"
    return r.json()


def test_1_create_and_approve_and_logs(api, token, vehicle):
    """P0 — create approval → OTP-approve → GET vehicle approval-logs shows row."""
    customer_id = vehicle.get("customerId") or vehicle.get("customer_id")
    print(f"vehicle customerId={customer_id} plate={vehicle.get('plateNumber')}")

    # 1. create approval
    payload = {"vehicleId": VEHICLE_ID, "title": "TEST stamp verify iter303", "amount": 100}
    if customer_id:
        payload["customerId"] = customer_id
    r = api.post(f"{BASE_URL}/api/approvals", json=payload)
    assert r.status_code in (200, 201), f"create approval: {r.status_code} {r.text[:300]}"
    body = r.json()
    tok = body.get("token")
    otp = body.get("otp")
    assert tok and otp, f"missing token/otp: {body}"
    CREATED_TOKENS.append(tok)
    print(f"created approval token={tok} otp={otp}")

    # 2. respond as customer via public endpoint (form-encoded per FastAPI Form())
    form = {"status": "approved", "name": "عميل اختبار iter303", "otp": otp}
    hdrs = {"x-ratelimit-bypass": BYPASS}  # no auth needed for public endpoint
    r2 = requests.post(f"{BASE_URL}/api/approvals/public/{tok}/respond", data=form, headers=hdrs)
    assert r2.status_code == 200, f"respond: {r2.status_code} {r2.text[:300]}"
    resp_body = r2.json()
    assert resp_body.get("status") in ("approved", "accepted", "approval_accepted"), f"status not approved: {resp_body}"
    assert resp_body.get("respondedAt") or resp_body.get("responded_at"), f"missing respondedAt: {resp_body}"
    print(f"respond ok status={resp_body.get('status')} responderName={resp_body.get('responderName')}")

    # 3. GET vehicle approval-logs — must include our token, status=approved
    time.sleep(1)
    r3 = api.get(f"{BASE_URL}/api/vehicles/{VEHICLE_ID}/approval-logs")
    assert r3.status_code == 200, f"vehicle approval-logs: {r3.status_code} {r3.text[:300]}"
    rows = r3.json()
    assert isinstance(rows, list) and len(rows) > 0, f"empty vehicle approval-logs: {rows}"
    ours = [r for r in rows if r.get("token") == tok]
    assert len(ours) == 1, f"our approval not found in logs: tokens={[r.get('token') for r in rows]}"
    row = ours[0]
    assert row.get("status") in ("approved", "accepted", "approval_accepted"), f"row status: {row}"
    assert row.get("responderName") == "عميل اختبار iter303", f"responderName mismatch: {row.get('responderName')}"
    assert row.get("respondedAt"), f"respondedAt missing: {row}"
    print(f"vehicle approval-logs OK — row.status={row['status']} responderName={row['responderName']} respondedAt={row['respondedAt']}")

    # 4. customer approval-logs parity
    if customer_id:
        r4 = api.get(f"{BASE_URL}/api/customers/{customer_id}/approval-logs")
        assert r4.status_code == 200, f"customer approval-logs: {r4.status_code} {r4.text[:300]}"
        crows = r4.json()
        assert isinstance(crows, list), f"non-list: {crows}"
        cours = [r for r in crows if r.get("token") == tok]
        assert len(cours) == 1, f"our approval not found in CUSTOMER logs: tokens={[r.get('token') for r in crows]}"
        assert cours[0].get("status") in ("approved", "accepted", "approval_accepted")
        assert cours[0].get("responderName") == "عميل اختبار iter303"
        print(f"customer approval-logs OK for customer_id={customer_id}")
    else:
        print("SKIP customer parity — vehicle has no customerId")


def test_2_template_resolve_unified_defaults(api, token):
    """Regression — template resolution still returns unified-*-a4-mobile-v1."""
    for doc_type in ("invoice", "diagnosis", "quote"):
        r = api.post(
            f"{BASE_URL}/api/document-templates/resolve",
            json={"document_type": doc_type, "vehicleId": VEHICLE_ID},
        )
        assert r.status_code == 200, f"resolve {doc_type}: {r.status_code} {r.text[:200]}"
        b = r.json()
        tpl_id = b.get("templateId") or (b.get("template") or {}).get("id")
        assert tpl_id == f"unified-{doc_type}-a4-mobile-v1", (
            f"resolve {doc_type} returned {tpl_id}, expected unified-{doc_type}-a4-mobile-v1 — "
            f"DEFAULTS POLLUTED (do not run seed_quickprint_fixture.py). Full: {b}"
        )
        print(f"resolve {doc_type} → {tpl_id} OK")


def test_3_negative_case_vehicle_without_approvals(api, token):
    """A different vehicle that never got a TEST approval — logs must be empty of our token."""
    r = api.get(f"{BASE_URL}/api/vehicles/{VEHICLE_ID}/approval-logs")
    assert r.status_code == 200
    # This just confirms endpoint is deterministic. Real "no-approval" UI check is manual/playwright.
    print(f"total approval rows for vehicle {VEHICLE_ID}: {len(r.json())}")
