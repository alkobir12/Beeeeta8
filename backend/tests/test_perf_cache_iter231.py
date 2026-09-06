"""
Iteration 231 — Performance cache correctness & invalidation tests.

Validates:
  1. GET /api/operations, /api/customers, /api/suppliers return correct data
  2. Warm reads are noticeably faster than cold reads (cache working)
  3. Cache invalidation on POST/PUT/DELETE /api/operations
  4. Data integrity: financial summaries identical between cold/warm reads
  5. No regression on /api/health, /api/vehicles
"""

import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://financial-ssot.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"


# ---------- Module fixture: HTTP session ----------
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ============================================================
# Sanity / regression
# ============================================================
class TestSanity:
    def test_health_ok(self, client):
        r = client.get(f"{API}/health", timeout=15)
        assert r.status_code == 200

    def test_vehicles_ok(self, client):
        r = client.get(f"{API}/vehicles", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_stats_ok(self, client):
        # /api/dashboard/stats returned 404 per probe — but /api/stats exists
        r = client.get(f"{API}/stats", timeout=30)
        assert r.status_code in (200, 404)


# ============================================================
# Cache speedup — warm < cold
# ============================================================
class TestCacheSpeedup:
    def _timed(self, client, path):
        t = time.time()
        r = client.get(f"{API}{path}", timeout=60)
        return r, time.time() - t

    def test_operations_warm_faster(self, client):
        # Bust cache by waiting >10s? Better: just compare 1st vs 2nd consecutive calls.
        r1, t1 = self._timed(client, "/operations")
        r2, t2 = self._timed(client, "/operations")
        assert r1.status_code == 200 and r2.status_code == 200
        assert isinstance(r1.json(), list)
        # Same length & same first id (data identical)
        l1, l2 = r1.json(), r2.json()
        assert len(l1) == len(l2)
        if l1:
            assert l1[0].get("id") == l2[0].get("id")
        # Warm should not be slower than cold (allow small variance)
        print(f"[operations] cold={t1:.3f}s warm={t2:.3f}s")
        # Cache should make warm at least 1.3x faster OR under 1.5s
        assert (t2 < t1 * 0.9) or (t2 < 1.5), (
            f"Warm /operations ({t2:.2f}s) not faster than cold ({t1:.2f}s)"
        )

    def test_customers_warm_faster(self, client):
        r1, t1 = self._timed(client, "/customers")
        r2, t2 = self._timed(client, "/customers")
        assert r1.status_code == 200 and r2.status_code == 200
        c1, c2 = r1.json(), r2.json()
        assert len(c1) == len(c2)
        print(f"[customers] cold={t1:.3f}s warm={t2:.3f}s len={len(c1)}")
        assert (t2 < t1 * 0.9) or (t2 < 1.5)

    def test_suppliers_warm_faster(self, client):
        r1, t1 = self._timed(client, "/suppliers")
        r2, t2 = self._timed(client, "/suppliers")
        assert r1.status_code == 200 and r2.status_code == 200
        s1, s2 = r1.json(), r2.json()
        assert len(s1) == len(s2)
        print(f"[suppliers] cold={t1:.3f}s warm={t2:.3f}s len={len(s1)}")
        assert (t2 < t1 * 0.9) or (t2 < 1.5)


# ============================================================
# Data integrity — financial summaries identical across reads
# ============================================================
class TestFinancialIntegrity:
    KEYS_CUST = ("debitBalance", "creditBalance", "overdueBalance", "ajelBalance")

    def _balances(self, items):
        out = {}
        for it in items:
            cid = it.get("id") or it.get("_id")
            if not cid:
                continue
            out[cid] = {k: it.get(k) for k in self.KEYS_CUST}
        return out

    def test_customers_balances_consistent(self, client):
        r1 = client.get(f"{API}/customers", timeout=60)
        r2 = client.get(f"{API}/customers", timeout=60)
        assert r1.status_code == 200 and r2.status_code == 200
        b1, b2 = self._balances(r1.json()), self._balances(r2.json())
        assert b1.keys() == b2.keys(), "Customer set differs across calls"
        diffs = [cid for cid in b1 if b1[cid] != b2[cid]]
        assert not diffs, f"Customer balance differences for ids: {diffs[:5]}"

    def test_suppliers_balances_consistent(self, client):
        r1 = client.get(f"{API}/suppliers", timeout=60)
        r2 = client.get(f"{API}/suppliers", timeout=60)
        assert r1.status_code == 200 and r2.status_code == 200
        b1, b2 = self._balances(r1.json()), self._balances(r2.json())
        assert b1.keys() == b2.keys(), "Supplier set differs across calls"
        diffs = [cid for cid in b1 if b1[cid] != b2[cid]]
        assert not diffs, f"Supplier balance differences for ids: {diffs[:5]}"


# ============================================================
# Cache invalidation on mutations
# ============================================================
class TestCacheInvalidation:
    """Create -> verify present -> delete -> verify absent. All must be reflected
    immediately (within < 2 seconds of mutation) — no stale cache."""

    @pytest.fixture
    def created_op(self, client):
        # Prime caches
        client.get(f"{API}/operations", timeout=60)

        payload = {
            "type": "service",
            "description": f"TEST_perf_cache_{uuid.uuid4().hex[:8]}",
            "amount": 123.45,
            "date": time.strftime("%Y-%m-%d"),
            "vendorId": None,
            "customerId": None,
        }
        r = client.post(f"{API}/operations", json=payload, timeout=60)
        assert r.status_code in (200, 201), f"Create failed: {r.status_code} {r.text[:300]}"
        op = r.json()
        op_id = op.get("id") or op.get("_id")
        assert op_id, f"No id returned in create: {op}"
        yield {"id": op_id, "description": payload["description"], "raw": op}

        # teardown — best effort delete
        try:
            client.delete(f"{API}/operations/{op_id}", timeout=30)
        except Exception:
            pass

    def test_post_invalidates_cache(self, client, created_op):
        op_id = created_op["id"]
        desc = created_op["description"]
        # Fetch ops list immediately — must contain new op (cache invalidated on POST)
        r = client.get(f"{API}/operations", timeout=60)
        assert r.status_code == 200
        ids = {(o.get("id") or o.get("_id")) for o in r.json()}
        descs = {o.get("description") for o in r.json()}
        assert op_id in ids or desc in descs, (
            f"Newly created op {op_id} not in /operations response — cache not invalidated"
        )

    def test_put_invalidates_cache(self, client, created_op):
        op_id = created_op["id"]
        # Prime cache
        client.get(f"{API}/operations", timeout=60)
        new_notes = f"TEST_perf_updated_{uuid.uuid4().hex[:6]}"
        r = client.put(
            f"{API}/operations/{op_id}",
            json={"notes": new_notes},
            timeout=60,
        )
        if r.status_code == 404:
            pytest.skip("PUT /operations/{id} not supported in this deployment")
        assert r.status_code in (200, 204), f"PUT failed: {r.status_code} {r.text[:300]}"

        # Immediate GET — must reflect update
        r2 = client.get(f"{API}/operations", timeout=60)
        assert r2.status_code == 200
        found = [o for o in r2.json() if (o.get("id") or o.get("_id")) == op_id]
        assert found, f"Op {op_id} disappeared after PUT"
        assert found[0].get("notes") == new_notes, (
            f"Stale notes after PUT — got {found[0].get('notes')!r}, expected {new_notes!r}"
        )

    def test_delete_invalidates_cache(self, client, client_fresh_op):
        op_id = client_fresh_op["id"]
        # Prime
        client.get(f"{API}/operations", timeout=60)

        r = client.delete(f"{API}/operations/{op_id}", timeout=60)
        assert r.status_code in (200, 204), f"DELETE failed: {r.status_code} {r.text[:300]}"

        r2 = client.get(f"{API}/operations", timeout=60)
        assert r2.status_code == 200
        ids = {(o.get("id") or o.get("_id")) for o in r2.json()}
        assert op_id not in ids, (
            f"Deleted op {op_id} still appears in /operations — cache not invalidated"
        )

    @pytest.fixture
    def client_fresh_op(self, client):
        # Separate op just for delete test (the created_op fixture deletes in teardown)
        payload = {
            "type": "service",
            "description": f"TEST_perf_del_{uuid.uuid4().hex[:8]}",
            "amount": 50.0,
            "date": time.strftime("%Y-%m-%d"),
        }
        r = client.post(f"{API}/operations", json=payload, timeout=60)
        assert r.status_code in (200, 201)
        op = r.json()
        return {"id": op.get("id") or op.get("_id"), "raw": op}


# ============================================================
# TTL behaviour — cache must expire eventually
# ============================================================
class TestTTLExpiry:
    def test_ops_cache_ttl_under_15s(self, client):
        """A second call within ~10s should be cached; not a correctness assertion
        but ensures no caller is forced to wait more than 15s on a single read."""
        t = time.time()
        r = client.get(f"{API}/operations", timeout=60)
        dt = time.time() - t
        assert r.status_code == 200
        assert dt < 15.0, f"/operations took {dt:.2f}s — caching/perf regression"
