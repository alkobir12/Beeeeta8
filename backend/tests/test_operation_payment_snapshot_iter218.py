"""
Iter218 — Verify _operation_payment_snapshot fix:
- Cash/immediate operations (cash/pos/transfer/bank/card/mada/visa/mastercard)
  with paymentStatus NOT in {unpaid,credit,partial,deferred,pending} should remain
  paymentStatus='paid' and balance=0 after GET /api/operations.
- Credit/unpaid purchases should remain paymentStatus='unpaid' with full balance.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://erp-compliance-check.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "مدير"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


def _find_op(client, op_id):
    r = client.get(f"{BASE_URL}/api/operations", timeout=60)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else (data.get("items") or data.get("operations") or [])
    return next((o for o in items if str(o.get("id")) == str(op_id)), None)


# ---- Test 1: POS expense (cash-immediate) should stay 'paid' with balance=0
def test_pos_expense_cash_immediate_remains_paid(client):
    inv = f"TEST_iter218_pos_{uuid.uuid4().hex[:6]}"
    payload = {
        "type": "expense",
        "scope": "workshop",
        "partnerType": "supplier",
        "partnerName": "TEST_iter218_POS_supplier",
        "items": [{"name": "TEST قطعة POS نقدية", "price": 50, "quantity": 1, "total": 50.0, "itemType": "service"}],
        "subtotal": 50.0,
        "total": 50.0,
        "paymentMethod": "pos",
        "paymentStatus": "paid",
        "paymentAmount": 50.0,
        "totalPaid": 50.0,
        "balance": 0.0,
        "source": "SMART_POS",
        "notes": f"TEST_iter218 POS expense {inv}",
    }
    create = client.post(f"{BASE_URL}/api/operations", json=payload, timeout=60)
    assert create.status_code in (200, 201), f"create failed: {create.status_code} {create.text[:500]}"
    created = create.json()
    op_id = created.get("id") or (created.get("operation") or {}).get("id")
    assert op_id, f"no id in response: {created}"

    # Note: create response may not reflect snapshot; verify GET instead
    # GET to verify persistence + snapshot
    fetched = _find_op(client, op_id)
    assert fetched is not None, "operation not found in GET /api/operations"
    ps = str(fetched.get("paymentStatus") or fetched.get("payment_status") or "").lower()
    bal = float(fetched.get("balance") or 0)
    assert ps in ("paid", "paid_full"), f"BUG: paymentStatus={ps} for cash-immediate POS expense; expected paid"
    assert bal <= 0.01, f"BUG: balance={bal} for cash-immediate POS expense; expected 0"


# ---- Test 2: Cash expense (cash_expense) should stay 'paid' with balance=0
def test_cash_expense_remains_paid(client):
    payload = {
        "type": "expense",
        "scope": "workshop",
        "partnerType": "supplier",
        "partnerName": "TEST_iter218_cash_supplier",
        "items": [{"name": "TEST مصروف نقدي", "price": 30, "quantity": 1, "total": 30.0, "itemType": "service"}],
        "subtotal": 30.0,
        "total": 30.0,
        "paymentMethod": "cash",
        "paymentStatus": "paid",
        "paymentAmount": 30.0,
        "totalPaid": 30.0,
        "balance": 0.0,
        "notes": "TEST_iter218 cash expense",
    }
    r = client.post(f"{BASE_URL}/api/operations", json=payload, timeout=60)
    assert r.status_code in (200, 201), r.text[:500]
    op_id = r.json().get("id") or (r.json().get("operation") or {}).get("id")
    assert op_id
    fetched = _find_op(client, op_id)
    assert fetched is not None
    ps = str(fetched.get("paymentStatus") or "").lower()
    bal = float(fetched.get("balance") or 0)
    assert ps in ("paid", "paid_full"), f"BUG: paymentStatus={ps} for cash expense"
    assert bal <= 0.01, f"BUG: balance={bal} for cash expense"


# ---- Test 3: Credit/unpaid purchase should remain unpaid
def test_credit_purchase_remains_unpaid(client):
    payload = {
        "type": "purchase",
        "scope": "workshop",
        "partnerType": "supplier",
        "partnerName": "TEST_iter218_credit_supplier",
        "items": [{"name": "TEST قطعة آجلة", "price": 200, "quantity": 1, "total": 200.0, "itemType": "part"}],
        "subtotal": 200.0,
        "total": 200.0,
        "paymentMethod": "credit",
        "paymentStatus": "unpaid",
        "paymentAmount": 0,
        "totalPaid": 0,
        "balance": 200.0,
        "notes": "TEST_iter218 credit purchase",
    }
    r = client.post(f"{BASE_URL}/api/operations", json=payload, timeout=60)
    assert r.status_code in (200, 201), r.text[:500]
    op_id = r.json().get("id") or (r.json().get("operation") or {}).get("id")
    assert op_id
    fetched = _find_op(client, op_id)
    assert fetched is not None
    ps = str(fetched.get("paymentStatus") or "").lower()
    bal = float(fetched.get("balance") or 0)
    assert ps in ("unpaid", "credit", "deferred", "partial"), \
        f"REGRESSION: credit purchase shows as {ps}; expected unpaid"
    assert bal >= 199.0, f"REGRESSION: credit purchase balance={bal}; expected ~200"
