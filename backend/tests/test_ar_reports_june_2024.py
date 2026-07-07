"""Acceptance test for AR logic using June 2024 scenario.

Scenario (June 2024):
- Ahmed: invoice 780 on 2024-06-01, cash collected 400 same day, partial collection 200 on 2024-06-15 → remaining 180
- Mohammed: invoice 720 on 2024-06-05, collected 720 on 2024-06-20 → remaining 0
- Sara: cash sale 330 on 2024-06-10 → should not affect AR

Expected as of 2024-06-30:
- Total AR = 180
- Only debtor: Ahmed (180)

These tests are designed to validate:
- Accrual recorded in operations (credit invoices)
- Cash movements recorded via journal entries (operation_payment)
- AR reports derived from operations + payment entries
"""

import os
import uuid
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://accounting-engine-6.preview.emergentagent.com"
).rstrip("/")
WORKSHOP_ID = "finmodule-sync"


def _create_op(type_: str, partner_name: str, total: float, date: str, payment_method: str):
    payload = {
        "workshopId": WORKSHOP_ID,
        "type": type_,
        "partnerType": "customer",
        "partnerName": partner_name,
        "items": [
            {
                "itemType": "service",
                "name": f"TEST_{uuid.uuid4().hex[:6]}",
                "quantity": 1,
                "price": float(total),
            }
        ],
        "paymentMethod": payment_method,
        "notes": f"TEST_JUNE_2024_{partner_name}",
        "date": date,
    }
    res = requests.post(f"{BASE_URL}/api/operations", json=payload, timeout=30)
    assert res.status_code == 200
    data = res.json()
    assert data.get("id")
    return data["id"]


def _confirm(op_id: str, amount: float, date: str):
    res = requests.post(
        f"{BASE_URL}/api/operations/{op_id}/confirm-payment",
        json={"workshopId": WORKSHOP_ID, "amount": float(amount), "date": date},
        timeout=30,
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    return data


def _delete_op(op_id: str):
    requests.delete(f"{BASE_URL}/api/operations/{op_id}", timeout=30)


class TestARJune2024:
    def test_june_2024_ar_expected(self):
        created_ops = []
        try:
            # Ahmed credit invoice 780 on day 1
            ahmed_op = _create_op(
                type_="sale",
                partner_name="أحمد العتيبي",
                total=780,
                date="2024-06-01",
                payment_method="credit",
            )
            created_ops.append(ahmed_op)
            _confirm(ahmed_op, 400, "2024-06-01")
            _confirm(ahmed_op, 200, "2024-06-15")

            # Mohammed credit invoice 720 on day 5
            moh_op = _create_op(
                type_="sale",
                partner_name="محمد القحطاني",
                total=720,
                date="2024-06-05",
                payment_method="credit",
            )
            created_ops.append(moh_op)
            _confirm(moh_op, 720, "2024-06-20")

            # Sara cash sale 330 on day 10
            sara_op = _create_op(
                type_="sale",
                partner_name="سارة الشمري",
                total=330,
                date="2024-06-10",
                payment_method="cash",
            )
            created_ops.append(sara_op)

            # Verify AR customers as of end of month
            resp = requests.get(
                f"{BASE_URL}/api/finance/ar/customers",
                params={"workshop_id": WORKSHOP_ID, "as_of": "2024-06-30"},
                timeout=30,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("success") is True
            total_ar = float((data.get("data") or {}).get("total_ar") or 0)
            assert total_ar == 180.0

            customers = (data.get("data") or {}).get("customers") or []
            # Only Ahmed should be present with 180
            assert any(c.get("customer") == "أحمد العتيبي" and float(c.get("balance")) == 180.0 for c in customers)
            assert all((c.get("customer") == "أحمد العتيبي") for c in customers)

            # Aging should show 180 in 0-30 bucket
            aging = requests.get(
                f"{BASE_URL}/api/finance/ar/aging",
                params={"workshop_id": WORKSHOP_ID, "as_of": "2024-06-30"},
                timeout=30,
            ).json()
            assert aging.get("success") is True
            buckets = (aging.get("data") or {}).get("buckets") or {}
            assert float(buckets.get("0_30") or 0) == 180.0
            assert float((aging.get("data") or {}).get("total_ar") or 0) == 180.0

            # Turnover (given credit sales total 1500)
            turnover = requests.get(
                f"{BASE_URL}/api/finance/ar/turnover",
                params={
                    "workshop_id": WORKSHOP_ID,
                    "start_date": "2024-06-01",
                    "end_date": "2024-06-30",
                    "credit_sales_total": 1500,
                },
                timeout=30,
            ).json()
            assert turnover.get("success") is True
            assert float((turnover.get("data") or {}).get("closing_receivables") or 0) == 180.0

        finally:
            for op_id in created_ops:
                try:
                    _delete_op(op_id)
                except Exception:
                    pass


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "--tb=short"])
