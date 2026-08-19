"""Read-only verification for signed balance-sheet fix (iteration 355)."""
import os
import hashlib
import re
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://accounting-ssot-fix.preview.emergentagent.com").rstrip("/")
WS = "finmodule-sync"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": "مدير", "password": "010101"}, timeout=15)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def bs(auth_headers):
    r = requests.get(f"{BASE_URL}/api/finance/reports/balance-sheet",
                     params={"workshop_id": WS, "as_of_date": "2099-12-31"},
                     headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def tb(auth_headers):
    r = requests.get(f"{BASE_URL}/api/finance/reports/trial-balance",
                     params={"workshop_id": WS, "start_date": "2000-01-01", "end_date": "2099-12-31"},
                     headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def journal(auth_headers):
    r = requests.get(f"{BASE_URL}/api/finance/journal-entries",
                     params={"workshop_id": WS, "limit": 1000},
                     headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# CHECK 1: BALANCE_GAP
def test_balance_gap_zero(bs):
    d = bs["data"]["totals"]
    gap = abs(d["assets"] - d["liabilities_plus_equity"])
    print(f"assets={d['assets']} liab+eq={d['liabilities_plus_equity']} gap={gap}")
    assert gap < 0.01, f"BALANCE_GAP FAIL gap={gap}"


# CHECK 2: SIGNED_BALANCES_PRESERVED
def test_account_006_signed(bs):
    assets = bs["data"]["sections"]["assets"]
    acc006 = next((a for a in assets if a["code"] == "006"), None)
    assert acc006 is not None, "account 006 missing from assets"
    print(f"006: {acc006}")
    assert acc006["balance"] == -569.0, f"expected -569, got {acc006['balance']}"
    assert acc006.get("is_contra") is True
    assert acc006.get("balance_nature") == "رصيد دائن / عكسي"


def test_signed_balances_match_trial_balance(bs, tb):
    # Build tb map
    tb_rows = tb.get("data", {}).get("accounts") or tb.get("data", {}).get("rows") or tb.get("accounts") or []
    if not tb_rows and isinstance(tb.get("data"), list):
        tb_rows = tb["data"]
    print(f"tb keys: {list(tb.get('data', {}).keys()) if isinstance(tb.get('data'), dict) else type(tb.get('data'))}")
    tb_map = {}
    for row in tb_rows:
        code = row.get("code") or row.get("account_code") or row.get("id")
        if code:
            tb_map[str(code)] = (float(row.get("debit", 0) or 0), float(row.get("credit", 0) or 0))
    sections = bs["data"]["sections"]
    mismatches = []
    for section, sign in [("assets", 1), ("liabilities", -1), ("equity", -1)]:
        for acc in sections[section]:
            code = acc["code"]
            if code == "023":  # net income synthesized
                continue
            if code not in tb_map:
                continue
            debit, credit = tb_map[code]
            signed = (debit - credit) if section == "assets" else (credit - debit)
            if abs(signed - acc["balance"]) > 0.01:
                mismatches.append((section, code, signed, acc["balance"]))
    print(f"mismatches: {mismatches}")
    assert not mismatches, f"sign mismatches: {mismatches}"


# CHECK 3: ABS_USAGE_IN_BALANCE_SHEET == 0
def test_no_abs_in_get_balance_sheet():
    with open("/app/backend/routes_finance.py") as f:
        src = f.read()
    m = re.search(r'@router\.get\("/reports/balance-sheet"\).*?(?=\n@router\.)', src, re.DOTALL)
    assert m, "could not locate function"
    body = m.group(0)
    count = len(re.findall(r'\babs\(', body))
    print(f"abs( occurrences in get_balance_sheet: {count}")
    assert count == 0, f"found {count} abs() calls"


# CHECK 4: TRIAL_BALANCE totals
def test_trial_balance_totals(tb):
    totals = tb.get("data", {}).get("totals") or tb.get("totals") or {}
    print(f"tb totals: {totals}")
    td = float(totals.get("total_debit", 0) or totals.get("debit", 0))
    tc = float(totals.get("total_credit", 0) or totals.get("credit", 0))
    assert abs(td - 105887.06) < 0.01, f"total_debit={td}"
    assert abs(tc - 105887.06) < 0.01, f"total_credit={tc}"


# CHECK 5: JOURNAL_UNCHANGED
def test_journal_unchanged(journal):
    entries = journal.get("data") or journal.get("entries") or journal.get("items") or []
    if isinstance(journal, list):
        entries = journal
    print(f"journal type: {type(journal)}, count={len(entries)}")
    assert len(entries) == 92, f"count={len(entries)}"
    total_sum = 0.0
    ids = []
    for e in entries:
        total_sum += float(e.get("total_debit") or e.get("total") or e.get("amount") or 0)
        ids.append(str(e.get("id") or e.get("_id") or e.get("entry_id")))
    print(f"total_sum={total_sum}")
    assert abs(total_sum - 144513.06) < 0.5, f"total_sum={total_sum}"
    h = hashlib.sha256("|".join(sorted(ids)).encode()).hexdigest()[:16]
    print(f"ids_hash={h}")
    assert h == "d136f996227a9d44", f"hash mismatch: {h}"
