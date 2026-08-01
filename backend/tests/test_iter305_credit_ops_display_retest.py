"""
Iteration 305 — RETEST after fixes:
 (1) operation snapshot no longer misclassifies partial/credit as 'cash immediate'
     and operations_list uses max(journal_paid, visit_notes_paid).
 (2) customers.ajelBalance freshness after visit_sync perf_cache invalidation.
 (3) visit_sync prioritizes paymentMethod/paymentStatus from notes JSON.
Baseline: ledger_ar_total == stored_balances_total == 51735, gap 0.
"""
import os
import time
import uuid
import json as _json
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
BYPASS = "c68b2b87386db82cb541d78d584a821fa4809f2afb53a45e"
TEST_LABEL = "TEST - DO NOT USE"


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "x-ratelimit-bypass": BYPASS})
    r = s.post(f"{BASE}/api/auth/login", json={"username": "مدير", "pin": "123123"})
    assert r.status_code == 200, r.text[:200]
    tok = r.json().get("access_token") or r.json().get("token")
    s.headers["Authorization"] = f"Bearer {tok}"
    return s


def _ledger(s):
    r = s.get(f"{BASE}/api/finance/ar-ledger")
    assert r.status_code == 200
    j = r.json()
    return j["data"] if isinstance(j, dict) and "data" in j and isinstance(j["data"], dict) else j


def _cust_by_id(s, cid):
    r = s.get(f"{BASE}/api/customers")
    assert r.status_code == 200
    d = r.json()
    lst = d if isinstance(d, list) else (d.get("customers") or d.get("items") or [])
    return next((c for c in lst if (c.get("id") or c.get("_id")) == cid), None)


def _jes(s, vid):
    r = s.get(f"{BASE}/api/finance/journal-entries", params={"workshop_id": "finmodule-sync", "limit": 500})
    if r.status_code != 200:
        return []
    d = r.json()
    entries = d if isinstance(d, list) else (d.get("entries") or d.get("items") or d.get("data") or [])
    return [e for e in entries if str(e.get("reference_id") or "") == str(vid)]


def _op_for_visit(s, vehicle_id, vid):
    r = s.get(f"{BASE}/api/operations", params={"vehicle_id": vehicle_id})
    assert r.status_code == 200
    d = r.json()
    ops = d if isinstance(d, list) else (d.get("operations") or d.get("items") or [])
    return next((o for o in ops if str(o.get("visitId") or o.get("visit_id") or o.get("reference_id") or "") == str(vid)), None)


# ---------- ACCEPTANCE ----------
def test_00_baseline(sess):
    L = _ledger(sess)
    print("LEDGER:", {k: L.get(k) for k in ("ledger_ar_total","stored_balances_total","reconciliation_gap","pending_unjournalized_total")})
    assert abs(float(L["ledger_ar_total"]) - float(L["stored_balances_total"])) < 0.01
    assert abs(float(L["reconciliation_gap"])) < 0.01
    assert float(L.get("pending_unjournalized_total") or 0) == 0
    negs = [n for n in (L.get("negative_parties") or []) if float((n or {}).get("balance", 0)) < -0.01]
    assert not negs, f"neg parties: {negs}"


@pytest.fixture(scope="module")
def baseline(sess):
    return _ledger(sess)


@pytest.fixture(scope="module")
def ctx(sess):
    c = {"customer_id": None, "vehicle_id": None, "visit_id": None}
    r = sess.post(f"{BASE}/api/customers", json={
        "name": f"{TEST_LABEL} عميل 305", "phone": "0590000777", "type": "individual"
    })
    print("CREATE CUSTOMER:", r.status_code, r.text[:200])
    assert r.status_code in (200, 201)
    j = r.json()
    c["customer_id"] = j.get("id") or j.get("_id") or j.get("customer_id")

    r = sess.post(f"{BASE}/api/vehicles", json={
        "plateNumber": f"T305-{uuid.uuid4().hex[:4]}",
        "brand": "TEST", "model": TEST_LABEL, "year": 2020,
        "customerName": f"{TEST_LABEL} عميل 305", "customerPhone": "0590000777",
        "status": "diagnosis",
    })
    print("CREATE VEHICLE:", r.status_code, r.text[:200])
    assert r.status_code in (200, 201)
    j = r.json()
    c["vehicle_id"] = j.get("id") or j.get("_id") or j.get("vehicle_id")

    yield c

    # cleanup
    if c.get("visit_id"):
        sess.delete(f"{BASE}/api/visits/{c['visit_id']}")
        time.sleep(1)
    if c.get("vehicle_id"):
        sess.delete(f"{BASE}/api/vehicles/{c['vehicle_id']}")
    if c.get("customer_id"):
        sess.delete(f"{BASE}/api/customers/{c['customer_id']}")


def test_01_credit_visit_300(sess, ctx, baseline):
    payload = {
        "entryDate": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "in_progress",
        "notes": {
            "items": [{"name": "TEST item 305", "price": 300, "qty": 1}],
            "payments": [],
            "paymentMethod": "credit",
            "paymentStatus": "unpaid",
        },
    }
    r = sess.post(f"{BASE}/api/vehicles/{ctx['vehicle_id']}/visits", json=payload)
    print("CREATE VISIT:", r.status_code, r.text[:300])
    assert r.status_code in (200, 201)
    vid = r.json().get("id") or r.json().get("visit_id")
    ctx["visit_id"] = vid
    time.sleep(2.5)

    # Operation snapshot expectations
    op = _op_for_visit(sess, ctx["vehicle_id"], vid)
    print("OP:", op)
    assert op is not None, "operation not created"
    total_paid = float(op.get("totalPaid") or op.get("total_paid") or 0)
    balance = float(op.get("balance") or op.get("remaining") or op.get("remaining_amount") or 0)
    pstatus = str(op.get("paymentStatus") or op.get("payment_status") or "").lower()
    pmethod = str(op.get("paymentMethod") or op.get("payment_method") or "").lower()
    print(f"OP snapshot: totalPaid={total_paid} balance={balance} pstatus={pstatus} pmethod={pmethod}")

    assert total_paid == 0, f"totalPaid should be 0, got {total_paid}"
    assert abs(balance - 300) < 0.5, f"balance should be 300, got {balance}"
    assert pstatus in ("unpaid", "credit", "deferred", "unconfirmed", "partial"), f"unexpected pstatus={pstatus}"
    # KEY REGRESSION FIX from iter304: MUST NOT be 'paid' or reflect cash-immediate for a credit visit with remaining balance
    assert pstatus != "paid", f"credit visit with balance was misclassified as paid: {op}"
    assert pmethod != "cash", f"paymentMethod should not be cash for credit visit, got {pmethod}"

    # customer ajel IMMEDIATE freshness (<= 1s tolerance)
    t0 = time.time()
    cust = _cust_by_id(sess, ctx["customer_id"])
    dt = time.time() - t0
    bal = float((cust or {}).get("ajelBalance") or (cust or {}).get("ajel_balance") or 0)
    print(f"CUSTOMER ajel={bal} fetched_in={dt:.2f}s")
    assert abs(bal - 300) < 0.5, f"customer.ajelBalance should be 300 immediately, got {bal}"

    # ledger +300 gap 0
    L = _ledger(sess)
    delta = float(L["ledger_ar_total"]) - float(baseline["ledger_ar_total"])
    print("LEDGER DELTA:", delta, "gap:", L["reconciliation_gap"])
    assert abs(delta - 300) < 0.5
    assert abs(float(L["reconciliation_gap"])) < 0.01


def test_02_partial_payment_100(sess, ctx):
    vid = ctx["visit_id"]
    r = sess.get(f"{BASE}/api/vehicles/{ctx['vehicle_id']}/visits")
    visits = r.json() if isinstance(r.json(), list) else (r.json().get("visits") or [])
    visit = next((v for v in visits if v.get("id") == vid), None)
    assert visit
    notes = visit.get("notes") or {}
    if isinstance(notes, str):
        try:
            notes = _json.loads(notes)
        except Exception:
            notes = {}
    notes["items"] = [{"name": "TEST item 305", "price": 300, "qty": 1}]
    notes["payments"] = [{"id": str(uuid.uuid4()), "amount": 100, "method": "cash",
                          "date": time.strftime("%Y-%m-%d"), "kind": "collection"}]
    notes["paymentMethod"] = "credit"
    notes["paymentStatus"] = "partial"

    r = sess.put(f"{BASE}/api/visits/{vid}", json={"notes": _json.dumps(notes, ensure_ascii=False)})
    print("PUT PAYMENT:", r.status_code, r.text[:300])
    assert r.status_code in (200, 201)
    time.sleep(2.5)

    # Journal: expect operation (300 Dr 005) + operation_payment (100 Cr 005)
    jes = _jes(sess, vid)
    print("JES:", [{"src": j.get("source"), "lines": j.get("lines") or j.get("entries")} for j in jes])
    accrual_dr = 0.0
    payment_cr = 0.0
    for je in jes:
        src = str(je.get("source") or "")
        for ln in (je.get("lines") or je.get("entries") or []):
            code = str(ln.get("account") or ln.get("account_code") or "")
            if code != "005":
                continue
            if src == "operation":
                accrual_dr += float(ln.get("debit") or 0)
            elif src == "operation_payment":
                payment_cr += float(ln.get("credit") or 0)
    print(f"Dr005(accrual)={accrual_dr} Cr005(payment)={payment_cr}")
    assert abs(accrual_dr - 300) < 0.5, f"accrual Dr 005 should be 300, got {accrual_dr}"
    assert abs(payment_cr - 100) < 0.5, f"payment Cr 005 should be 100, got {payment_cr}"

    # Operation snapshot: totalPaid=100 balance=200 status partial
    op = _op_for_visit(sess, ctx["vehicle_id"], vid)
    tp = float(op.get("totalPaid") or op.get("total_paid") or 0)
    bal = float(op.get("balance") or op.get("remaining") or op.get("remaining_amount") or 0)
    pstatus = str(op.get("paymentStatus") or op.get("payment_status") or "").lower()
    print(f"OP after payment: totalPaid={tp} balance={bal} pstatus={pstatus}")
    assert abs(tp - 100) < 0.5, f"op.totalPaid should be 100 (max of journal 100 vs notes 100), got {tp}"
    assert abs(bal - 200) < 0.5, f"op.balance should be 200, got {bal}"
    assert pstatus in ("partial", "partially_paid"), f"op.paymentStatus should be partial, got {pstatus}"

    # Customer ajel = 200 immediately (perf_cache invalidated by visit_sync)
    t0 = time.time()
    cust = _cust_by_id(sess, ctx["customer_id"])
    dt = time.time() - t0
    ajel = float((cust or {}).get("ajelBalance") or 0)
    print(f"CUSTOMER ajel after payment={ajel} fetched_in={dt:.2f}s")
    assert abs(ajel - 200) < 0.5, f"customer.ajelBalance should be 200 after 100 payment on 300 credit, got {ajel}"

    # Ledger gap still 0
    L = _ledger(sess)
    assert abs(float(L["reconciliation_gap"])) < 0.01


def test_03_idempotent_repost(sess, ctx):
    vid = ctx["visit_id"]
    before = _jes(sess, vid)
    r = sess.get(f"{BASE}/api/vehicles/{ctx['vehicle_id']}/visits")
    visits = r.json() if isinstance(r.json(), list) else (r.json().get("visits") or [])
    visit = next((v for v in visits if v.get("id") == vid), None)
    assert visit
    notes = visit.get("notes")
    body = {"notes": notes if isinstance(notes, str) else _json.dumps(notes, ensure_ascii=False)}
    r = sess.put(f"{BASE}/api/visits/{vid}", json=body)
    assert r.status_code in (200, 201)
    time.sleep(2.5)
    after = _jes(sess, vid)
    print(f"IDEMPOTENT: before={len(before)} after={len(after)}")
    assert len(after) == len(before), f"duplicate JE created {len(after)} vs {len(before)}"


def test_04_delete_cascade(sess, ctx, baseline):
    vid = ctx["visit_id"]
    r = sess.delete(f"{BASE}/api/visits/{vid}")
    print("DELETE VISIT:", r.status_code, r.text[:200])
    assert r.status_code in (200, 204)
    time.sleep(2.5)
    assert not _jes(sess, vid), "JEs not cascade-removed"
    op = _op_for_visit(sess, ctx["vehicle_id"], vid)
    assert op is None, f"operation still present: {op}"

    cust = _cust_by_id(sess, ctx["customer_id"])
    ajel = float((cust or {}).get("ajelBalance") or 0)
    assert abs(ajel) < 0.5, f"customer.ajelBalance should be 0 after delete, got {ajel}"

    L = _ledger(sess)
    delta = float(L["ledger_ar_total"]) - float(baseline["ledger_ar_total"])
    print("FINAL DELTA:", delta, "gap:", L["reconciliation_gap"])
    assert abs(delta) < 0.5
    assert abs(float(L["reconciliation_gap"])) < 0.01
    ctx["visit_id"] = None
