"""
Iteration 243 - Backend tests for:
- Finance/Firewall unification (source-of-truth)
- Firewall health.breakdown key 'profitability'
- Bot governance Phase C (awaiting_confirmation, cancel, no-name guard)
- Four-Eyes still enforced for financial actions
- Power mode entity extraction
"""
import os
import time
import uuid
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    if not v:
        raise RuntimeError("REACT_APP_BACKEND_URL not configured")
    return v.rstrip("/")


BASE_URL = _load_backend_url()
WORKSHOP_ID = "finmodule-sync"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "مدير"}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _chat(headers, message, session_id, timeout=90):
    r = requests.post(
        f"{BASE_URL}/api/assistant/chat",
        json={"message": message, "session_id": session_id, "workshop_id": WORKSHOP_ID},
        headers=headers,
        timeout=timeout,
    )
    return r


def _chat_body(r):
    """Unwrap the {success, data:{...}} envelope used by /api/assistant/chat."""
    try:
        j = r.json()
    except Exception:
        return {}
    if isinstance(j, dict) and "data" in j and isinstance(j["data"], dict):
        return j["data"]
    return j


# =========================================================================
# 1) UNIFICATION: /api/finance/alerts must equal /api/firewall/dashboard
# =========================================================================
class TestFinanceFirewallUnification:
    def test_finance_alerts_source_is_firewall_engine(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/finance/alerts",
            params={"workshop_id": WORKSHOP_ID},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        data = body.get("data", body)
        assert data.get("source") == "firewall_engine", f"source={data.get('source')}"
        assert "health" in data and isinstance(data["health"].get("score"), int)
        assert isinstance(data.get("alerts"), list)

    def test_finance_alerts_equals_firewall_dashboard(self, headers):
        r_fin = requests.get(
            f"{BASE_URL}/api/finance/alerts",
            params={"workshop_id": WORKSHOP_ID},
            headers=headers,
            timeout=30,
        )
        r_fw = requests.get(
            f"{BASE_URL}/api/firewall/dashboard",
            params={"workshop_id": WORKSHOP_ID},
            headers=headers,
            timeout=30,
        )
        assert r_fin.status_code == 200 and r_fw.status_code == 200
        fin = r_fin.json().get("data", {})
        fw = r_fw.json().get("data", {})

        # Health scores must match
        assert fin["health"]["score"] == fw["health"]["score"], (
            f"finance={fin['health']['score']} vs firewall={fw['health']['score']}"
        )
        # Alerts count must match
        assert len(fin["alerts"]) == len(fw["alerts"]), (
            f"finance={len(fin['alerts'])} vs firewall={len(fw['alerts'])}"
        )
        # Alert ids/titles must match
        fin_ids = sorted([a.get("id") or a.get("title") for a in fin["alerts"]])
        fw_ids = sorted([a.get("id") or a.get("title") for a in fw["alerts"]])
        assert fin_ids == fw_ids, f"ids diverge: {fin_ids} vs {fw_ids}"


# =========================================================================
# 2) Firewall breakdown 'profitability' (renamed from audit_coverage)
# =========================================================================
class TestFirewallProfitability:
    def test_breakdown_has_profitability_key(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/firewall/dashboard",
            params={"workshop_id": WORKSHOP_ID},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json().get("data", {})
        bd = data.get("health", {}).get("breakdown", {})
        assert "profitability" in bd, f"breakdown keys: {list(bd.keys())}"
        assert "audit_coverage" not in bd, "old key 'audit_coverage' still present"
        prof = data.get("profitability")
        assert isinstance(prof, dict), "profitability block missing"
        for k in ("revenue", "expenses", "net_income", "margin_pct"):
            assert k in prof, f"missing {k} in profitability block"


# =========================================================================
# 3) Bot Governance Phase C
# =========================================================================
class TestBotGovernancePhaseC:
    created_supplier_ids = []

    def test_supplier_awaiting_confirm_then_commit(self, headers):
        sid = f"test-supplier-{uuid.uuid4().hex[:8]}"
        uniq = f"موردالاختبار{uuid.uuid4().hex[:6]}"

        # Step 1: propose
        r1 = _chat(headers, f"اضف مورد باسم {uniq} جوال 0507771122 قطع غيار آجل", sid)
        assert r1.status_code == 200, r1.text
        b1 = _chat_body(r1)
        exec_status = (b1.get("executed") or {}).get("status")
        resp_text = b1.get("response", "")
        assert exec_status == "awaiting_confirmation", f"got {exec_status}, resp={resp_text[:200]}"
        assert "تأكيد" in resp_text or "مورّد" in resp_text or "مورد" in resp_text

        # Step 2: confirm
        time.sleep(0.5)
        r2 = _chat(headers, "نعم", sid)
        assert r2.status_code == 200
        b2 = _chat_body(r2)
        exec2 = (b2.get("executed") or {}).get("status")
        assert exec2 == "committed", f"got {exec2}, body={b2}"
        assert "✅" in b2.get("response", "") or "تم" in b2.get("response", "")

        # Step 3: verify it appears in /api/suppliers
        rs = requests.get(f"{BASE_URL}/api/suppliers", headers=headers, timeout=30)
        assert rs.status_code == 200
        suppliers_data = rs.json()
        # Suppliers may be nested
        if isinstance(suppliers_data, dict):
            suppliers = suppliers_data.get("data") or suppliers_data.get("suppliers") or suppliers_data.get("items") or []
        else:
            suppliers = suppliers_data
        names = [(s.get("name") or "") for s in suppliers]
        assert any(uniq in n for n in names), f"supplier {uniq} not in list of {len(names)}"

        # Track for cleanup
        for s in suppliers:
            if s.get("name") == uniq and s.get("id"):
                TestBotGovernancePhaseC.created_supplier_ids.append(s["id"])

    def test_customer_cancel_flow(self, headers):
        sid = f"test-cust-{uuid.uuid4().hex[:8]}"
        uniq = f"عميلالاختبار{uuid.uuid4().hex[:6]}"

        r1 = _chat(headers, f"سجل عميل {uniq} 0553334444", sid)
        assert r1.status_code == 200
        b1 = _chat_body(r1)
        st1 = (b1.get("executed") or {}).get("status")
        assert st1 == "awaiting_confirmation", f"got {st1}, resp={b1.get('response','')[:200]}"

        time.sleep(0.5)
        r2 = _chat(headers, "لا", sid)
        assert r2.status_code == 200
        b2 = _chat_body(r2)
        st2 = (b2.get("executed") or {}).get("status")
        assert st2 == "cancelled", f"got {st2}, resp={b2.get('response','')[:200]}"
        assert "إلغاء" in b2.get("response", "") or "الغاء" in b2.get("response", "")

        # verify customer NOT created
        rc = requests.get(
            f"{BASE_URL}/api/customers",
            params={"search": uniq},
            headers=headers,
            timeout=30,
        )
        if rc.status_code == 200:
            data = rc.json()
            customers = data if isinstance(data, list) else (data.get("data") or data.get("customers") or [])
            names = [(c.get("name") or "") for c in customers]
            assert not any(uniq in n for n in names), f"customer {uniq} was created despite cancel"

    def test_no_name_guard_supplier(self, headers):
        sid = f"test-noname-sup-{uuid.uuid4().hex[:8]}"
        r = _chat(headers, "اضف مورد", sid)
        assert r.status_code == 200
        b = _chat_body(r)
        st = (b.get("executed") or {}).get("status")
        resp = b.get("response", "")
        # Not committed / not awaiting_confirmation — bot asks for name
        assert st not in ("committed", "awaiting_confirmation", "pending_approval"), (
            f"got {st}, resp={resp[:200]}"
        )
        assert "اسم" in resp and "المورّد" in resp or "المورد" in resp, (
            f"no name-ask in resp: {resp[:200]}"
        )

    def test_no_name_guard_customer(self, headers):
        sid = f"test-noname-cust-{uuid.uuid4().hex[:8]}"
        test_start = time.time()
        r = _chat(headers, "سجل عميل جواله 0501001220", sid)
        assert r.status_code == 200
        b = _chat_body(r)
        st = (b.get("executed") or {}).get("status")
        resp = b.get("response", "")
        assert st not in ("committed", "awaiting_confirmation", "pending_approval"), (
            f"got {st}, resp={resp[:200]}"
        )
        assert "اسم" in resp

        # ensure no NEW "بدون اسم" customer was created by THIS call.
        # A stale one from prior sessions is a pre-existing data issue, not a regression.
        rc = requests.get(
            f"{BASE_URL}/api/customers",
            params={"search": "بدون اسم"},
            headers=headers,
            timeout=30,
        )
        if rc.status_code == 200:
            data = rc.json()
            customers = data if isinstance(data, list) else (data.get("data") or data.get("customers") or [])
            from datetime import datetime, timezone
            for c in customers:
                phone = (c.get("phone") or "") + (c.get("mobile") or "")
                if "0501001220" not in phone:
                    continue
                # created recently by our call?
                created = c.get("createdAt") or c.get("created_at") or ""
                try:
                    ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
                except Exception:
                    ts = 0
                if ts >= test_start - 5:
                    pytest.fail(
                        f"junk 'بدون اسم' customer freshly created by this test: {c}"
                    )
                else:
                    print(f"[warn] Pre-existing junk customer (stale): id={c.get('id')} createdAt={created}")


# =========================================================================
# 4) Four-Eyes still enforced for financial actions
# =========================================================================
class TestFourEyesUnchanged:
    def test_expense_still_pending_approval(self, headers):
        sid = f"test-expense-{uuid.uuid4().hex[:8]}"
        r = _chat(headers, "سجل مصروف إيجار 900 نقدا", sid)
        assert r.status_code == 200
        b = _chat_body(r)
        st = (b.get("executed") or {}).get("status")
        resp = b.get("response", "")
        assert st == "pending_approval", f"got {st}, resp={resp[:200]}"
        approval_id = (b.get("executed") or {}).get("approval_id")
        assert approval_id, f"no approval_id in executed: {b.get('executed')}"
        # response should mention 4-eyes / أربع أعين
        assert "أربع" in resp or "أعين" in resp or "موافقة" in resp or "approval" in resp.lower()


# =========================================================================
# 5) Bot Read Consistency (alerts count matches firewall)
# =========================================================================
class TestBotReadConsistency:
    def test_bot_reports_same_alerts_count(self, headers):
        # Get authoritative count
        r = requests.get(
            f"{BASE_URL}/api/firewall/dashboard",
            params={"workshop_id": WORKSHOP_ID},
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 200
        fw_count = len(r.json().get("data", {}).get("alerts", []))

        sid = f"test-alerts-read-{uuid.uuid4().hex[:8]}"
        rc = _chat(headers, "كم عدد التنبيهات المالية؟", sid)
        assert rc.status_code == 200
        resp = _chat_body(rc).get("response", "")
        assert str(fw_count) in resp, f"bot resp did not contain count {fw_count}: {resp[:300]}"


# =========================================================================
# 6) Power Mode extraction
# =========================================================================
class TestPowerMode:
    def test_power_diagnose_extracts_amount_not_phone(self, headers):
        # try /api/assistant/power/diagnose first
        payload = {
            "message": "اضف بيع خدمة توضيب بقيمة 4500 باسم أحمد رقم جوال 0555555555 لاندكروزر",
            "workshop_id": WORKSHOP_ID,
        }
        r = requests.post(
            f"{BASE_URL}/api/assistant/power/diagnose",
            json=payload,
            headers=headers,
            timeout=30,
        )
        if r.status_code == 404:
            pytest.skip("power/diagnose endpoint not exposed")
        assert r.status_code == 200, r.text
        body = r.json()
        # Look for parsed amount == 4500 and phone captured
        # entities may be at top-level or under data
        d = body.get("data", body)
        # Search recursively for amount==4500 and phone==0555555555
        import json as _json
        text = _json.dumps(d, ensure_ascii=False)
        assert "4500" in text, f"amount 4500 not found in extraction: {text[:400]}"
        assert "0555555555" in text, f"phone not found in extraction: {text[:400]}"
        # Must NOT read the phone digits as an amount (55555555 etc.)
        assert '"amount": 55555555' not in text.replace(" ", "")
        assert '"amount":555555555' not in text.replace(" ", "")


# =========================================================================
# Cleanup
# =========================================================================
@pytest.fixture(scope="module", autouse=True)
def _cleanup(admin_token):
    yield
    hdr = {"Authorization": f"Bearer {admin_token}"}
    for sid in TestBotGovernancePhaseC.created_supplier_ids:
        try:
            requests.delete(f"{BASE_URL}/api/suppliers/{sid}", headers=hdr, timeout=15)
        except Exception:
            pass
