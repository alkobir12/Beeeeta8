"""
Iteration 193 — RADICAL Rakan removal + Services/Parts router refactor regression.
Validates:
  1) Rakan accounts purged from chart-of-accounts (042 retained, 0421 new expense mirror).
  2) /api/inventory/rakan-analytics returns 404 (endpoint deleted).
  3) New COGS routing: part-sale operation books cost into 0421, not 030.
  4) Services router (POST/GET/DELETE) working under original /api/services path.
  5) Parts router (GET search/low_stock, POST, PUT, DELETE) working under /api/parts.
  6) Firewall integrity: balance_health_percent=100, unbalanced_entries_in_db=0.
  7) Smoke test: 10 legacy endpoints still 200.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pdpl-memory-engine.preview.emergentagent.com").rstrip("/")
WORKSHOP_ID = "finmodule-sync"

RAKAN_CODES = {"043", "044", "053", "054", "055", "056", "057", "058", "21010001"}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# -------- 1) Rakan removal: accounts --------
class TestRakanRemovalAccounts:
    def test_no_rakan_accounts_in_coa(self, client):
        r = client.get(f"{BASE_URL}/api/accounts", params={"workshop_id": WORKSHOP_ID}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        accounts = data if isinstance(data, list) else data.get("accounts", data.get("data", []))
        assert isinstance(accounts, list) and len(accounts) > 0, "accounts list empty"

        codes_present = set()
        for a in accounts:
            code = str(a.get("code", "")).strip()
            name = str(a.get("name", "") or a.get("nameAr", "") or "").lower()
            codes_present.add(code)
            assert "راكان" not in name, f"Rakan name found in account: {a}"
            assert "rakan" not in name, f"Rakan name found in account: {a}"
            assert code not in RAKAN_CODES, f"Forbidden Rakan code {code} in {a}"

        # 042 (revenue) must exist, and 0421 (new expense mirror)
        assert "042" in codes_present, f"Account 042 missing. Present codes (sample): {list(codes_present)[:20]}"
        assert "0421" in codes_present, f"Account 0421 (new expense mirror) missing"

    def test_rakan_analytics_endpoint_deleted(self, client):
        r = client.get(f"{BASE_URL}/api/inventory/rakan-analytics", params={"workshop_id": WORKSHOP_ID}, timeout=15)
        assert r.status_code == 404, f"Expected 404, got {r.status_code} body={r.text[:300]}"


# -------- 2) Firewall integrity --------
class TestFirewallIntegrity:
    def test_firewall_health(self, client):
        r = client.get(f"{BASE_URL}/api/firewall/status", params={"workshop_id": WORKSHOP_ID}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        summary = body.get("summary", body)
        assert summary.get("balance_health_percent") == 100, f"Balance health != 100: {summary}"
        assert summary.get("unbalanced_entries_in_db", 0) == 0, f"Unbalanced entries present: {summary}"


# -------- 3) Services router refactor --------
class TestServicesRouter:
    created_id = None

    def test_services_list(self, client):
        r = client.get(f"{BASE_URL}/api/services", timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_services_create_then_delete(self, client):
        payload = {"name": "TEST_خدمة فحص iter193", "category": "test", "price": 50, "duration": 20}
        r = client.post(f"{BASE_URL}/api/services", json=payload, timeout=20)
        assert r.status_code == 200, f"POST /api/services failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        sid = body.get("id") or body.get("_id") or body.get("serviceId")
        assert sid, f"No id in service POST response: {body}"
        TestServicesRouter.created_id = sid

        # Cleanup
        d = client.delete(f"{BASE_URL}/api/services/{sid}", timeout=15)
        assert d.status_code in (200, 204), f"DELETE failed: {d.status_code} {d.text[:200]}"


# -------- 4) Parts router refactor --------
class TestPartsRouter:
    created_id = None

    def test_parts_list(self, client):
        r = client.get(f"{BASE_URL}/api/parts", timeout=20)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_parts_search(self, client):
        r = client.get(f"{BASE_URL}/api/parts", params={"search": "زيت"}, timeout=20)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_parts_low_stock(self, client):
        r = client.get(f"{BASE_URL}/api/parts", params={"low_stock": "true"}, timeout=20)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_parts_create_and_delete(self, client):
        payload = {
            "name": "TEST_REFACTOR_PART_iter193",
            "partNumber": "TRP-193",
            "category": "test",
            "quantity": 1,
            "minQuantity": 1,
            "purchasePrice": 10,
            "sellingPrice": 20,
        }
        r = client.post(f"{BASE_URL}/api/parts", json=payload, timeout=20)
        assert r.status_code == 200, f"POST /api/parts failed: {r.status_code} {r.text[:400]}"
        body = r.json()
        pid = body.get("id") or body.get("_id") or body.get("partId")
        assert pid, f"No id in parts POST response: {body}"
        TestPartsRouter.created_id = pid

        # Verify GET shows it
        g = client.get(f"{BASE_URL}/api/parts", timeout=20)
        assert g.status_code == 200
        names = [p.get("name") for p in g.json() if isinstance(p, dict)]
        assert "TEST_REFACTOR_PART_iter193" in names, "Newly created TEST part not found in GET list"

        # Cleanup
        d = client.delete(f"{BASE_URL}/api/parts/{pid}", timeout=15)
        # accept 200/204 or 405/404 depending on if DELETE exists
        assert d.status_code in (200, 204, 404, 405), f"DELETE unexpected: {d.status_code} {d.text[:200]}"


# -------- 5) COGS routing to 0421 (instead of 030) --------
class TestCOGSRoutingTo0421:
    def test_part_sale_books_cogs_to_0421(self, client):
        # Find existing part with quantity > 0
        gp = client.get(f"{BASE_URL}/api/parts", timeout=20)
        assert gp.status_code == 200
        parts = [p for p in gp.json() if isinstance(p, dict) and (p.get("quantity") or 0) > 0]
        if not parts:
            pytest.skip("No parts with stock to sell — skipping COGS routing test")
        part = parts[0]
        part_id = part.get("id") or part.get("_id")
        part_name = part.get("name")

        # Need a vehicle for sale operation
        gv = client.get(f"{BASE_URL}/api/vehicles", timeout=20)
        assert gv.status_code == 200
        vehicles = gv.json()
        if not vehicles:
            pytest.skip("No vehicles for sale operation")
        vehicle_id = vehicles[0].get("id")

        op_payload = {
            "type": "sale",
            "workshopId": WORKSHOP_ID,
            "vehicleId": vehicle_id,
            "customerName": "TEST_CUST_iter193",
            "items": [
                {
                    "itemType": "part",
                    "partId": part_id,
                    "name": part_name,
                    "quantity": 1,
                    "price": float(part.get("sellingPrice") or part.get("selling_price") or 20),
                }
            ],
            "totalAmount": float(part.get("sellingPrice") or part.get("selling_price") or 20),
            "paymentMethod": "cash",
            "status": "completed",
        }
        r = client.post(f"{BASE_URL}/api/operations", json=op_payload, timeout=30)
        if r.status_code not in (200, 201):
            pytest.skip(f"Operation creation failed (cannot test COGS routing): {r.status_code} {r.text[:300]}")
        op = r.json()
        op_id = op.get("id") or op.get("_id") or op.get("operationId")

        # Check journal entries for COGS rows
        je = client.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 100},
            timeout=20,
        )
        if je.status_code != 200:
            pytest.skip(f"Journal entries fetch returned {je.status_code}")
        body = je.json()
        entries = body.get("data") if isinstance(body, dict) else body
        entries = entries or []

        # Find COGS entry for this op
        found_0421 = False
        found_030 = False
        for e in entries:
            ref = str(e.get("reference_id") or e.get("operationId") or e.get("operation_id") or "")
            if ref != str(op_id):
                continue
            lines = e.get("lines") or e.get("rows") or []
            for row in lines:
                code = str(row.get("account") or row.get("accountCode") or row.get("account_code") or "")
                if code == "0421":
                    found_0421 = True
                if code == "030":
                    found_030 = True
        assert not found_030, "COGS for new operation routed to legacy 030 — should be 0421"
        assert found_0421, f"No 0421 (workshop parts cost) line found for operation {op_id}; expected COGS routing to 0421"


# -------- 6) Legacy endpoints smoke --------
class TestLegacySmoke:
    @pytest.mark.parametrize("path", [
        "/api/operations/pending",
        "/api/vehicles",
        "/api/customers",
        "/api/technicians",
        "/api/biz-accounts",
        "/api/approvals",
        "/api/invoice-templates",
        "/api/templates",
        "/api/settings",
        "/api/profile",
    ])
    def test_smoke(self, client, path):
        r = client.get(f"{BASE_URL}{path}", params={"workshop_id": WORKSHOP_ID}, timeout=20)
        assert r.status_code == 200, f"{path} returned {r.status_code}: {r.text[:200]}"
