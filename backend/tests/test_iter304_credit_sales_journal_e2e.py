"""
Iteration 304 — Credit sales journal & AR ledger consistency E2E
Covers: acceptance, new credit sale, payment, idempotency, delete cascade.
"""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://canonical-integrity.preview.emergentagent.com").rstrip("/")
BYPASS = "c68b2b87386db82cb541d78d584a821fa4809f2afb53a45e"

TEST_LABEL = "TEST - DO NOT USE"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "x-ratelimit-bypass": BYPASS,
    })
    r = s.post(f"{BASE}/api/auth/login", json={"username": "مدير", "pin": "123123"})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text[:300]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    s.headers["Authorization"] = f"Bearer {tok}"
    return s


def _ledger(sess):
    r = sess.get(f"{BASE}/api/finance/ar-ledger")
    assert r.status_code == 200, r.text[:200]
    j = r.json()
    if isinstance(j, dict) and "data" in j and isinstance(j["data"], dict):
        return j["data"]
    return j


def _customers_total(sess):
    r = sess.get(f"{BASE}/api/customers")
    assert r.status_code == 200
    data = r.json()
    lst = data if isinstance(data, list) else (data.get("customers") or data.get("items") or [])
    total = 0.0
    for c in lst:
        try:
            total += float(c.get("ajelBalance") or c.get("ajel_balance") or 0)
        except Exception:
            pass
    return total, lst


# ---------- Acceptance ----------
def test_acceptance_ledger_consistency(sess):
    L = _ledger(sess)
    print("LEDGER KEYS:", list(L.keys()))
    print("LEDGER:", {k: L.get(k) for k in ("ledger_ar_total", "stored_balances_total",
                                            "reconciliation_gap", "pending_unjournalized_total",
                                            "negative_parties")})
    lat = float(L.get("ledger_ar_total", 0))
    sbt = float(L.get("stored_balances_total", 0))
    gap = float(L.get("reconciliation_gap", 0))
    pen = float(L.get("pending_unjournalized_total", 0))
    negs = L.get("negative_parties") or []
    assert abs(lat - sbt) < 0.01, f"ledger vs stored mismatch {lat} vs {sbt}"
    assert abs(gap) < 0.01, f"gap={gap}"
    assert pen == 0, f"pending_unjournalized_total={pen}"
    assert len([n for n in negs if float((n or {}).get("balance", 0)) < -0.01]) == 0, f"negatives={negs}"

    ctot, _ = _customers_total(sess)
    print("CUSTOMERS AJEL SUM:", ctot, "LEDGER:", lat)
    assert abs(ctot - lat) < 0.5, f"customers ajel {ctot} vs ledger {lat}"


# ---------- New credit sale E2E + payment + idempotency + delete cascade ----------
@pytest.fixture(scope="module")
def baseline(sess):
    return _ledger(sess)


@pytest.fixture(scope="module")
def test_ctx(sess):
    """Create TEST customer + vehicle. Cleanup at end."""
    ctx = {"customer_id": None, "vehicle_id": None, "visit_id": None}

    # Create customer
    cust_payload = {
        "name": f"{TEST_LABEL} عميل",
        "phone": "0500000000",
        "type": "individual",
    }
    r = sess.post(f"{BASE}/api/customers", json=cust_payload)
    print("CREATE CUSTOMER:", r.status_code, r.text[:250])
    assert r.status_code in (200, 201), r.text[:300]
    c = r.json()
    ctx["customer_id"] = c.get("id") or c.get("_id") or c.get("customer_id")

    # Create vehicle
    veh_payload = {
        "plateNumber": f"TST-{uuid.uuid4().hex[:4]}",
        "brand": "TEST",
        "model": TEST_LABEL,
        "year": 2020,
        "customerName": cust_payload["name"],
        "customerPhone": "0500000000",
        "status": "diagnosis",
    }
    r = sess.post(f"{BASE}/api/vehicles", json=veh_payload)
    print("CREATE VEHICLE:", r.status_code, r.text[:250])
    assert r.status_code in (200, 201), r.text[:300]
    v = r.json()
    ctx["vehicle_id"] = v.get("id") or v.get("_id") or v.get("vehicle_id")

    yield ctx

    # Cleanup
    if ctx.get("visit_id"):
        sess.delete(f"{BASE}/api/visits/{ctx['visit_id']}")
    if ctx.get("vehicle_id"):
        sess.delete(f"{BASE}/api/vehicles/{ctx['vehicle_id']}")
    if ctx.get("customer_id"):
        sess.delete(f"{BASE}/api/customers/{ctx['customer_id']}")


def _find_journals_for_visit(sess, visit_id):
    """Find journal entries referencing this visit_id via /api/journal-entries."""
    params = {"workshop_id": "finmodule-sync", "limit": 500}
    r = sess.get(f"{BASE}/api/finance/journal-entries", params=params)
    if r.status_code != 200:
        return []
    data = r.json()
    entries = data if isinstance(data, list) else (data.get("entries") or data.get("items") or data.get("data") or [])
    return [e for e in entries if str(e.get("reference_id") or "") == str(visit_id)]


def test_02_create_credit_visit(sess, test_ctx, baseline):
    payload = {
        "entryDate": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "in_progress",
        "notes": {
            "items": [{"name": "TEST item", "price": 200, "qty": 1}],
            "payments": [],
            "paymentMethod": "credit",
            "paymentStatus": "deferred",
        },
    }
    r = sess.post(f"{BASE}/api/vehicles/{test_ctx['vehicle_id']}/visits", json=payload)
    print("CREATE VISIT:", r.status_code, r.text[:400])
    assert r.status_code in (200, 201), r.text[:400]
    v = r.json()
    vid = v.get("id") or v.get("visit_id") or v.get("_id")
    assert vid
    test_ctx["visit_id"] = vid

    # Allow sync to run
    time.sleep(2.0)

    # (a) operation exists
    r = sess.get(f"{BASE}/api/operations", params={"vehicle_id": test_ctx["vehicle_id"]})
    assert r.status_code == 200
    ops = r.json() if isinstance(r.json(), list) else (r.json().get("operations") or r.json().get("items") or [])
    print("OPS COUNT:", len(ops))
    matching = [o for o in ops if str(o.get("visitId") or o.get("visit_id") or o.get("reference_id") or "") == str(vid)]
    print("MATCHING OPS:", matching[:2])
    assert matching, f"No op found for visit {vid}. Ops sample: {ops[:2]}"

    # (b) journal entry Dr 005 = 200
    time.sleep(1.0)
    jes = _find_journals_for_visit(sess, vid)
    print("JES for visit:", jes)
    assert jes, "No journal entry created for credit visit"
    accrual = [j for j in jes if (j.get("source") == "operation") or ("operation_payment" not in str(j.get("source", "")))]
    assert accrual, f"No accrual JE, got: {jes}"
    # Check Dr 005 = 200
    found_dr = False
    for je in accrual:
        for line in (je.get("lines") or je.get("entries") or []):
            code = str(line.get("account") or line.get("account_code") or "")
            if code == "005" and float(line.get("debit") or 0) >= 199.9:
                found_dr = True
                break
    assert found_dr, f"Dr 005=200 not found in accrual JE: {accrual}"

    # (c) customer ajel
    _, custs = _customers_total(sess)
    ours = next((c for c in custs if (c.get("id") or c.get("_id")) == test_ctx["customer_id"]), None)
    print("OUR CUSTOMER:", ours)
    assert ours is not None
    bal = float(ours.get("ajelBalance") or ours.get("ajel_balance") or 0)
    assert abs(bal - 200) < 0.5, f"customer ajel {bal} != 200"

    # (d) ledger +200 gap 0
    L2 = _ledger(sess)
    assert abs(float(L2["reconciliation_gap"])) < 0.01
    delta = float(L2["ledger_ar_total"]) - float(baseline["ledger_ar_total"])
    print("LEDGER DELTA:", delta)
    assert abs(delta - 200) < 0.5, f"ledger delta {delta} != 200"


def test_03_payment_flow(sess, test_ctx):
    vid = test_ctx["visit_id"]
    assert vid
    # Get current visit via vehicle visits list (no single-visit GET endpoint)
    r = sess.get(f"{BASE}/api/vehicles/{test_ctx['vehicle_id']}/visits")
    assert r.status_code == 200, r.text[:300]
    visits = r.json() if isinstance(r.json(), list) else (r.json().get("visits") or [])
    visit = next((v for v in visits if v.get("id") == vid), None)
    assert visit, f"Visit {vid} not in list"
    notes = visit.get("notes") or {}
    if isinstance(notes, str):
        import json as _j
        try:
            notes = _j.loads(notes)
        except Exception:
            notes = {}
    notes["items"] = [{"name": "TEST item", "price": 200, "qty": 1}]
    notes["payments"] = [{"id": str(uuid.uuid4()), "amount": 80, "method": "cash",
                          "date": time.strftime("%Y-%m-%d"), "kind": "collection"}]
    notes["paymentMethod"] = "credit"
    notes["paymentStatus"] = "partial"

    r = sess.put(f"{BASE}/api/visits/{vid}", json={"notes": __import__("json").dumps(notes, ensure_ascii=False)})
    print("PUT VISIT (payment):", r.status_code, r.text[:300])
    assert r.status_code in (200, 201), r.text[:400]
    time.sleep(2.5)

    # (a) collection JE
    jes = _find_journals_for_visit(sess, vid)
    pays = [j for j in jes if j.get("source") == "operation_payment"]
    print("PAYMENT JES:", pays)
    assert pays, f"No operation_payment JE, all: {jes}"
    total_paid = 0.0
    for je in pays:
        for line in (je.get("lines") or je.get("entries") or []):
            code = str(line.get("account") or line.get("account_code") or "")
            if code == "005":
                total_paid += float(line.get("credit") or 0)
    assert abs(total_paid - 80) < 0.5, f"collection Cr 005 total {total_paid} != 80"

    # (b) operation remaining 120
    r = sess.get(f"{BASE}/api/operations", params={"vehicle_id": test_ctx["vehicle_id"]})
    ops = r.json() if isinstance(r.json(), list) else (r.json().get("operations") or [])
    ours = [o for o in ops if str(o.get("visitId") or o.get("visit_id") or "") == str(vid)]
    print("OP AFTER PAY:", ours[:1])
    if ours:
        rem = float(ours[0].get("balance") or ours[0].get("remaining") or ours[0].get("remaining_amount") or 0)
        print("REMAINING:", rem)
        # Note: docs say remaining=120
        assert abs(rem - 120) < 1.0, f"remaining {rem} != 120"

    # (c) customer ajel 120
    _, custs = _customers_total(sess)
    ours = next((c for c in custs if (c.get("id") or c.get("_id")) == test_ctx["customer_id"]), None)
    bal = float((ours or {}).get("ajelBalance") or 0)
    assert abs(bal - 120) < 0.5, f"customer ajel {bal} != 120"

    # (d) gap still 0
    L = _ledger(sess)
    assert abs(float(L["reconciliation_gap"])) < 0.01


def test_04_idempotency(sess, test_ctx):
    vid = test_ctx["visit_id"]
    before = _find_journals_for_visit(sess, vid)
    before_count = len(before)
    r = sess.get(f"{BASE}/api/vehicles/{test_ctx['vehicle_id']}/visits")
    visits = r.json() if isinstance(r.json(), list) else (r.json().get("visits") or [])
    visit = next((v for v in visits if v.get("id") == vid), None)
    assert visit
    notes = visit.get("notes")
    r = sess.put(f"{BASE}/api/visits/{vid}", json={"notes": notes if isinstance(notes, str) else __import__("json").dumps(notes, ensure_ascii=False)})
    assert r.status_code in (200, 201)
    time.sleep(2.5)
    after = _find_journals_for_visit(sess, vid)
    print(f"IDEMPOTENCY: before={before_count} after={len(after)}")
    assert len(after) == before_count, f"duplicated JE created: {len(after)} vs {before_count}"


def test_05_delete_cascade(sess, test_ctx, baseline):
    vid = test_ctx["visit_id"]
    r = sess.delete(f"{BASE}/api/visits/{vid}")
    print("DELETE VISIT:", r.status_code, r.text[:200])
    assert r.status_code in (200, 204)
    time.sleep(2.5)

    jes = _find_journals_for_visit(sess, vid)
    print("JES AFTER DELETE:", jes)
    assert not jes, f"Journal entries not cascade-deleted: {jes}"

    r = sess.get(f"{BASE}/api/operations", params={"vehicle_id": test_ctx["vehicle_id"]})
    ops = r.json() if isinstance(r.json(), list) else (r.json().get("operations") or [])
    remaining = [o for o in ops if str(o.get("visitId") or o.get("visit_id") or "") == str(vid)]
    assert not remaining, f"Operation not removed: {remaining}"

    # customer ajel back to 0
    _, custs = _customers_total(sess)
    ours = next((c for c in custs if (c.get("id") or c.get("_id")) == test_ctx["customer_id"]), None)
    bal = float((ours or {}).get("ajelBalance") or 0)
    assert abs(bal) < 0.5, f"customer ajel after delete {bal} != 0"

    # ledger back to baseline
    L = _ledger(sess)
    delta = float(L["ledger_ar_total"]) - float(baseline["ledger_ar_total"])
    print("FINAL DELTA vs baseline:", delta)
    assert abs(delta) < 0.5, f"ledger not restored: delta={delta}"
    assert abs(float(L["reconciliation_gap"])) < 0.01

    test_ctx["visit_id"] = None
