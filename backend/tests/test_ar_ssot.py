"""AR SSOT identity checks — iteration 356 (READ-ONLY)."""
import os
import sys
import asyncio
import json
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://accounting-ssot-fix.preview.emergentagent.com").rstrip("/")
WS = "finmodule-sync"
from datetime import date
TODAY = date.today().isoformat()


def _login():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"username": "مدير", "password": "010101"}, timeout=30)
    r.raise_for_status()
    tok = r.json().get("token") or r.json().get("access_token") or r.json().get("data", {}).get("token")
    return tok


def test_ar_readers_identity():
    tok = _login()
    h = {"Authorization": f"Bearer {tok}"} if tok else {}

    # (a/b) vehicle files + engine
    r1 = requests.get(f"{BASE}/api/finance/ar/customers",
                      params={"workshop_id": WS, "as_of": TODAY, "include_today": "true"},
                      headers=h, timeout=60)
    r1.raise_for_status()
    d1 = r1.json().get("data", r1.json())
    engine_total_ar = float(d1.get("total_ar") or 0)
    vehicles = d1.get("vehicles") or []
    customers = d1.get("customers") or []
    vehicles_sum = round(sum(float(v.get("receivable") or 0) for v in vehicles), 2)
    n_customers = len(customers)
    print(f"[a/b] /ar/customers total_ar={engine_total_ar} vehicles_sum={vehicles_sum} n_customers={n_customers}")

    # (c) ar ledger
    r2 = requests.get(f"{BASE}/api/finance/ar/ledger",
                      params={"workshop_id": WS, "start_date": "2000-01-01", "end_date": TODAY},
                      headers=h, timeout=60)
    ledger_end = None
    if r2.status_code == 200:
        d2 = r2.json().get("data", r2.json())
        ledger_end = float(d2.get("ending_balance") or 0)
        print(f"[c] /ar/ledger ending_balance={ledger_end}")
    else:
        print(f"[c] /ar/ledger HTTP {r2.status_code}")

    # (d) debt follow-up
    r3 = requests.get(f"{BASE}/api/finance/ar-ledger",
                      params={"workshop_id": WS}, headers=h, timeout=60)
    debt_total = None
    if r3.status_code == 200:
        d3 = r3.json().get("data", r3.json())
        debt_total = float(d3.get("current_vehicle_ar_total") or 0)
        print(f"[d] /ar-ledger current_vehicle_ar_total={debt_total}")
    else:
        print(f"[d] /ar-ledger HTTP {r3.status_code}")

    # (e) assistant dashboard (long timeout)
    r4 = requests.get(f"{BASE}/api/assistant/dashboard",
                      params={"workshop_id": WS}, headers=h, timeout=180)
    r4.raise_for_status()
    d4 = r4.json().get("data", r4.json())
    panels = d4.get("panels") or []
    total_ar_panel = next((p for p in panels if p.get("id") == "total_ar"), {})
    dash_total = float(total_ar_panel.get("value") or 0)
    dash_secondary = total_ar_panel.get("secondary") or total_ar_panel.get("subtitle") or ""
    print(f"[e] assistant dashboard total_ar value={dash_total} secondary={dash_secondary!r}")

    # Assertions
    assert engine_total_ar > 0, "engine total_ar zero"
    assert abs(engine_total_ar - vehicles_sum) < 1.0, f"engine vs vehicles sum mismatch {engine_total_ar} != {vehicles_sum}"
    if ledger_end is not None:
        assert abs(engine_total_ar - ledger_end) < 1.0, f"engine vs ledger mismatch {engine_total_ar} != {ledger_end}"
    if debt_total is not None:
        assert abs(engine_total_ar - debt_total) < 1.0, f"engine vs debt_total mismatch {engine_total_ar} != {debt_total}"
    assert abs(engine_total_ar - dash_total) < 1.0, f"engine vs dashboard mismatch {engine_total_ar} != {dash_total}"

    # secondary count check
    import re
    m = re.search(r"(\d+)", str(dash_secondary))
    if m:
        assert int(m.group(1)) == n_customers, f"dashboard count {m.group(1)} != n_customers {n_customers}"

    # save context
    ctx = {"engine_total_ar": engine_total_ar, "vehicles_sum": vehicles_sum,
           "n_customers": n_customers, "ledger_end": ledger_end,
           "debt_total": debt_total, "dash_total": dash_total,
           "customers_top5": customers[:5] if customers else []}
    with open("/tmp/ar_ctx.json", "w") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)


def test_katrina_tool_ar_summary():
    sys.path.insert(0, "/app/backend")
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from core import tool_router
    envelope = asyncio.run(tool_router.call_tool("finance.ar_summary", workshop_id=WS))
    res = envelope.get("result", envelope) if isinstance(envelope, dict) else envelope
    print(f"[f] katrina finance.ar_summary total_ar={res.get('total_ar')} n={res.get('total_customers_with_debt')} src={res.get('ar_source')}")
    assert res.get("ar_source") == "unified_financial_engine.build_current_ar_snapshot"
    assert (res.get("total_ar") or 0) > 0
    assert "error" not in res

    # compare vs engine snapshot captured previously
    with open("/tmp/ar_ctx.json") as f:
        ctx = json.load(f)
    k_total = float(res.get("total_ar") or 0)
    e_total = float(ctx["engine_total_ar"])
    # allow drift due to live user activity but check equal-magnitude
    diff = abs(k_total - e_total)
    print(f"[compare] katrina={k_total} engine={e_total} diff={diff}")
    assert diff < 2000.0, f"katrina drift too high {diff}"

    # per-customer identity CHECK 2 — top Katrina debtor must exist in engine customers list with same balance
    tok = _login()
    h = {"Authorization": f"Bearer {tok}"} if tok else {}
    r = requests.get(f"{BASE}/api/finance/ar/customers",
                     params={"workshop_id": WS, "as_of": TODAY, "include_today": "true"},
                     headers=h, timeout=60)
    engine_customers = r.json().get("data", {}).get("customers") or []
    engine_map = {(c.get("customer") or c.get("name") or "").strip(): float(c.get("balance") or 0) for c in engine_customers}

    top = (res.get("top_debtors") or [])[:1]
    assert top, "katrina returned no top_debtors"
    top_k = top[0]
    n_k = (top_k.get("name") or "").strip()
    b_k = float(top_k.get("balance") or 0)
    engine_b = engine_map.get(n_k)
    print(f"[check2] katrina_top=({n_k!r},{b_k}) engine_balance_for_same_name={engine_b}")
    assert engine_b is not None, f"katrina top debtor {n_k!r} not found in engine customers list"
    assert abs(engine_b - b_k) < 1.0, f"balance mismatch for {n_k}: katrina={b_k} engine={engine_b}"


def test_no_stored_balance_leak():
    with open("/app/backend/core/tool_router.py", encoding="utf-8") as f:
        src = f.read()
    assert '"total_ar": s.get("stored_balances_total")' not in src
    assert "build_current_ar_snapshot" in src
    assert 'ar_source": "unified_financial_engine.build_current_ar_snapshot"' in src
    # fail-closed check
    assert 'canonical AR read unavailable' in src
