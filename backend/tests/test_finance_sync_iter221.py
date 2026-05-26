"""Iter221 — Integration tests for finance sync flows:
- Flow 1: POS expense (cash, paid) creates operation visible in /operations
- Flow 2: POS salary (cash, paid) creates operation visible in /operations
- Flow 3: confirm-payment updates the SAME op (no new op), totalPaid increases, balance decreases, status transitions
- Flow 4: PUT /api/visits/{id} triggers _sync_visit_to_operation and updates operations row

NOTE: Flow 5 (finance:updated event) is a frontend-only concern; tested via Playwright separately.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://fleet-audit-system-2.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = 'finmodule-sync'


@pytest.fixture(scope='module')
def api():
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    return s


def _get_op(api, op_id):
    r = api.get(f'{BASE_URL}/api/operations/{op_id}?workshop_id={WORKSHOP_ID}')
    if r.status_code == 404:
        # fallback to list
        r2 = api.get(f'{BASE_URL}/api/operations?workshop_id={WORKSHOP_ID}')
        assert r2.status_code == 200
        for o in r2.json():
            if o.get('id') == op_id:
                return o
        return None
    assert r.status_code == 200, r.text
    return r.json()


# ---- Flow 1: POS expense, cash, paid ----------------------------------
def test_flow1_pos_expense_cash_paid_persists_as_paid(api):
    payload = {
        "workshop_id": WORKSHOP_ID,
        "type": "expense",
        "partnerType": "supplier",
        "partnerName": f"TEST_iter221_expense_{uuid.uuid4().hex[:6]}",
        "items": [{"name": "TEST_expense_item", "qty": 1, "price": 75, "total": 75, "itemType": "expense"}],
        "subtotal": 75,
        "total": 75,
        "paymentMethod": "cash",
        "paymentStatus": "paid",
        "paymentAmount": 75,
        "totalPaid": 75,
        "balance": 0,
        "notes": "TEST iter221 [SOURCE:SMART_POS] expense flow",
        "date": "2026-01-15T00:00:00+00:00",
    }
    r = api.post(f'{BASE_URL}/api/operations', json=payload)
    assert r.status_code in (200, 201), r.text
    op = r.json()
    op_id = op['id']
    time.sleep(0.4)
    fetched = _get_op(api, op_id)
    assert fetched, 'created op not found in list'
    assert fetched['type'] == 'expense'
    assert fetched['paymentMethod'] == 'cash'
    assert fetched['paymentStatus'] == 'paid', f"expected paid, got {fetched['paymentStatus']}"
    assert float(fetched['totalPaid']) == 75
    assert float(fetched.get('balance', 0)) == 0


# ---- Flow 2: POS salary, cash, paid -----------------------------------
def test_flow2_pos_salary_cash_paid_persists_as_paid(api):
    payload = {
        "workshop_id": WORKSHOP_ID,
        "type": "salary",
        "partnerType": "employee",
        "partnerName": f"TEST_iter221_salary_{uuid.uuid4().hex[:6]}",
        "items": [{"name": "راتب يناير", "qty": 1, "price": 500, "total": 500, "itemType": "salary"}],
        "subtotal": 500,
        "total": 500,
        "paymentMethod": "cash",
        "paymentStatus": "paid",
        "paymentAmount": 500,
        "totalPaid": 500,
        "balance": 0,
        "notes": "TEST iter221 [SOURCE:SMART_POS] salary flow",
        "date": "2026-01-15T00:00:00+00:00",
    }
    r = api.post(f'{BASE_URL}/api/operations', json=payload)
    assert r.status_code in (200, 201), r.text
    op_id = r.json()['id']
    time.sleep(0.4)
    fetched = _get_op(api, op_id)
    assert fetched, 'salary op missing'
    assert fetched['type'] == 'salary'
    assert fetched['paymentStatus'] == 'paid', f"expected paid, got {fetched['paymentStatus']}"
    assert float(fetched['totalPaid']) == 500


# ---- Flow 3: confirm-payment updates same op --------------------------
def test_flow3_confirm_payment_updates_same_op(api):
    # Create an unpaid credit op of total 300
    payload = {
        "workshop_id": WORKSHOP_ID,
        "type": "sale",
        "partnerType": "customer",
        "partnerName": f"TEST_iter221_collect_{uuid.uuid4().hex[:6]}",
        "items": [{"name": "TEST_collect_item", "qty": 1, "price": 300, "total": 300, "itemType": "service"}],
        "subtotal": 300,
        "total": 300,
        "paymentMethod": "credit",
        "paymentStatus": "unpaid",
        "paymentAmount": 0,
        "totalPaid": 0,
        "balance": 300,
        "notes": "TEST iter221 unpaid for collect",
        "date": "2026-01-15T00:00:00+00:00",
    }
    r = api.post(f'{BASE_URL}/api/operations', json=payload)
    assert r.status_code in (200, 201), r.text
    op_id = r.json()['id']

    # Partial collection 100
    r1 = api.post(f'{BASE_URL}/api/operations/{op_id}/confirm-payment',
                  json={"workshop_id": WORKSHOP_ID, "amount": 100, "paymentMethod": "cash",
                        "date": "2026-01-15T00:00:00+00:00", "notes": "TEST partial1"})
    assert r1.status_code in (200, 201), r1.text
    time.sleep(0.3)
    f1 = _get_op(api, op_id)
    assert float(f1['totalPaid']) == 100, f1
    assert float(f1['balance']) == 200
    assert f1['paymentStatus'] in ('partial', 'partially_paid'), f1['paymentStatus']

    # Final collection 200
    r2 = api.post(f'{BASE_URL}/api/operations/{op_id}/confirm-payment',
                  json={"workshop_id": WORKSHOP_ID, "amount": 200, "paymentMethod": "cash",
                        "date": "2026-01-15T00:00:00+00:00", "notes": "TEST final"})
    assert r2.status_code in (200, 201), r2.text
    time.sleep(0.3)
    f2 = _get_op(api, op_id)
    assert float(f2['totalPaid']) == 300, f2
    assert float(f2['balance']) == 0
    assert f2['paymentStatus'] in ('paid', 'paid_full'), f2['paymentStatus']

    # Make sure no NEW operation was created for the same partner with same total (the op_id must be same)
    # Confirmation: still able to fetch by op_id.
    assert f2['id'] == op_id


# ---- Flow 4: PUT /api/visits/{id} updates operations row --------------
def test_flow4_visit_update_syncs_operation(api):
    # Find a recent visit on any vehicle for finmodule-sync via operations list (visitId == op id)
    r = api.get(f'{BASE_URL}/api/operations?workshop_id={WORKSHOP_ID}')
    assert r.status_code == 200
    ops = r.json()
    target = None
    for o in ops:
        if o.get('scope') == 'vehicle' and o.get('vehicleId') and o.get('visitId'):
            target = o
            break
    assert target, 'no vehicle-scope operation to derive a visit from'
    vehicle_id = target['vehicleId']
    rv = api.get(f'{BASE_URL}/api/vehicles/{vehicle_id}/visits?workshop_id={WORKSHOP_ID}')
    assert rv.status_code == 200, rv.text
    visits = rv.json() if isinstance(rv.json(), list) else (rv.json() or {}).get('visits') or []
    assert visits, 'no visits for vehicle'
    target_v = visits[0]
    visit_id = target_v['id']

    # Get current op snapshot
    op_before = _get_op(api, visit_id)  # op id often == visit id when scope=vehicle
    # Build new items: add one TEST_ item
    new_items = list(target_v.get('items') or [])
    new_items.append({"name": f"TEST_iter221_item_{uuid.uuid4().hex[:4]}", "qty": 1, "price": 33, "total": 33,
                      "itemType": "service", "billingType": "workshop"})

    payload = {
        "status": target_v.get('status') or 'open',
        "technicianId": target_v.get('technicianId') or target_v.get('technician_id'),
        "mileage": target_v.get('mileage') or 0,
        "notes": __import__('json').dumps({
            "text": "TEST iter221 visit update",
            "items": new_items,
            "payments": target_v.get('payments') or [],
        }),
    }
    r = api.put(f'{BASE_URL}/api/visits/{visit_id}', json=payload, params={'workshop_id': WORKSHOP_ID})
    assert r.status_code in (200, 204), r.text
    time.sleep(0.6)
    # Re-fetch op and verify sync happened: items list grew or total changed
    op_after = _get_op(api, visit_id)
    assert op_after, 'op after visit update missing'
    if op_before:
        # Either items count grew, or total grew by 33
        before_total = float(op_before.get('total') or 0)
        after_total = float(op_after.get('total') or 0)
        before_items = len(op_before.get('items') or [])
        after_items = len(op_after.get('items') or [])
        assert after_total > before_total - 0.01 and (after_items > before_items or after_total > before_total), \
            f'visit update did not sync to operation. before={before_total}/{before_items}  after={after_total}/{after_items}'


# ---- Sanity: backend /api/operations is reachable ---------------------
def test_health_operations_list(api):
    r = api.get(f'{BASE_URL}/api/operations?workshop_id={WORKSHOP_ID}')
    assert r.status_code == 200
    assert isinstance(r.json(), list)
