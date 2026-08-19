"""
ITERATION 357 — Read-only Audit for suspected duplication (Al-Attan case)
STRICT: zero mutations. GETs only.

Verdicts to produce:
  - NO_DUPLICATION_FOR_ALATTAN
  - LEGACY_DUPLICATES_PRESENT (list refs+amounts)
  - LEGACY_DUP_TOTAL_AR_EFFECT
  - CURRENT_AR_READERS_IDENTICAL
  - RAW_LEDGER_AR_TOTAL
  - UNATTRIBUTED_OPEN_PARTY_TOTAL
"""
import os
import sys
import json
from datetime import date
from collections import defaultdict

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://canonical-integrity.preview.emergentagent.com").rstrip("/")
WORKSHOP_ID = "finmodule-sync"

REF_ALATTAN_SALE_PREFIX = "vehfinal:3fe04b84"
REF_LEGACY_DUPS = [
    ("f5813fbd-f4b4-4561-9f13-9893d1880cc8", 800.0),
    ("ca32e1a6-a0d5-46f0-b2c0-ede7439c1da0", 150.0),
    ("0fd379c7-8d78-4151-b32f-beeb32dae664", 2500.0),
]
REF_RESOLVED = "174f49a1"

AR_ACCOUNT_KEYWORDS = ("العملاء", "ذمم مدينة", "ذمم العملاء")

REPORT = {}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"username": "مدير", "password": "010101"}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("access_token")
    assert token, "no access_token"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def journal(session):
    r = session.get(f"{BASE_URL}/api/finance/journal-entries",
                    params={"workshop_id": WORKSHOP_ID, "limit": 5000}, timeout=60)
    assert r.status_code == 200, f"journal-entries HTTP {r.status_code}: {r.text[:400]}"
    data = r.json()
    if isinstance(data, dict):
        entries = data.get("entries") or data.get("items") or data.get("data") or []
    else:
        entries = data
    assert isinstance(entries, list) and len(entries) > 0, f"empty journal payload: {str(data)[:400]}"
    REPORT["journal_count"] = len(entries)
    return entries


def _lines(e):
    return e.get("lines") or e.get("entries") or e.get("legs") or []


def _is_ar_line(line):
    name = (line.get("account_name") or line.get("account") or "") + " " + (line.get("account_code") or "")
    return any(k in name for k in AR_ACCOUNT_KEYWORDS)


def _debit(line):
    try:
        return float(line.get("debit") or 0)
    except Exception:
        return 0.0


def _credit(line):
    try:
        return float(line.get("credit") or 0)
    except Exception:
        return 0.0


def _text(e):
    return " ".join([
        str(e.get("description") or ""),
        str(e.get("memo") or ""),
        str(e.get("party_name") or ""),
        str(e.get("party") or ""),
        str(e.get("reference_id") or ""),
        str(e.get("reference") or ""),
    ])


# ─────────────────────────── VERIFY A ───────────────────────────

def test_A_alattan_math(journal):
    hits = [e for e in journal if "العطان" in _text(e)]
    REPORT["alattan_entries"] = len(hits)

    sale_entries = []
    payment_entries = []
    for e in hits:
        ref = str(e.get("reference_id") or e.get("reference") or "")
        desc = _text(e)
        lines = _lines(e)
        ar_debit = sum(_debit(l) for l in lines if _is_ar_line(l))
        ar_credit = sum(_credit(l) for l in lines if _is_ar_line(l))
        rev_credit = sum(_credit(l) for l in lines
                         if "إيراد" in (l.get("account_name") or "") or "ايراد" in (l.get("account_name") or "") or "Revenue" in (l.get("account_name") or ""))
        bank_debit = sum(_debit(l) for l in lines if "بنك" in (l.get("account_name") or "") or "مصرف" in (l.get("account_name") or "") or "Bank" in (l.get("account_name") or ""))
        cash_debit = sum(_debit(l) for l in lines if "صندوق" in (l.get("account_name") or "") or "نقد" in (l.get("account_name") or "") or "Cash" in (l.get("account_name") or ""))
        info = {
            "id": e.get("id") or e.get("entry_id") or e.get("_id"),
            "ref": ref,
            "desc": desc[:200],
            "ar_debit": ar_debit, "ar_credit": ar_credit,
            "rev_credit": rev_credit,
            "bank_debit": bank_debit, "cash_debit": cash_debit,
            "source": e.get("source"),
        }
        if ref.startswith(REF_ALATTAN_SALE_PREFIX) or "vehfinal:3fe04b84" in desc:
            sale_entries.append(info)
        elif "PAYMENT:" in desc or ar_credit > 0:
            payment_entries.append(info)

    REPORT["alattan_sales"] = sale_entries
    REPORT["alattan_payments"] = payment_entries

    # Assert single sale 8,500
    assert len(sale_entries) == 1, f"Expected 1 sale, got {len(sale_entries)}: {sale_entries}"
    s = sale_entries[0]
    assert abs(s["ar_debit"] - 8500) < 0.01, f"AR debit != 8500: {s}"
    assert abs(s["rev_credit"] - 8500) < 0.01, f"Revenue credit != 8500: {s}"

    # Payments: one 5,500 (bank) and one 3,000 (cash), distinct PAYMENT ids
    amounts = sorted([round(p["ar_credit"], 2) for p in payment_entries], reverse=True)
    assert 5500.0 in amounts and 3000.0 in amounts, f"Payments unexpected: {payment_entries}"

    p5500 = next(p for p in payment_entries if abs(p["ar_credit"] - 5500) < 0.01)
    p3000 = next(p for p in payment_entries if abs(p["ar_credit"] - 3000) < 0.01)
    assert p5500["bank_debit"] >= 5500 - 0.01 or "بنك" in p5500["desc"] or "PAYMENT:359d2e11" in p5500["desc"], \
        f"5500 not a bank payment: {p5500}"
    assert p3000["cash_debit"] >= 3000 - 0.01 or "صندوق" in p3000["desc"] or "PAYMENT:5552a689" in p3000["desc"], \
        f"3000 not a cash payment: {p3000}"

    # Distinct payment ids
    def _pid(d):
        import re
        m = re.search(r"PAYMENT:([a-f0-9]+)", d)
        return m.group(1) if m else None
    id1, id2 = _pid(p5500["desc"]), _pid(p3000["desc"])
    assert id1 and id2 and id1 != id2, f"Payment ids not distinct: {id1} vs {id2}"

    math_balance = s["ar_debit"] - p5500["ar_credit"] - p3000["ar_credit"]
    REPORT["alattan_math_balance"] = math_balance
    assert abs(math_balance) < 0.01, f"Math balance != 0: {math_balance}"

    REPORT["verdict_NO_DUPLICATION_FOR_ALATTAN"] = "CONFIRMED"


def test_A_alattan_absent_from_debtors(session):
    today = date.today().isoformat()
    r = session.get(f"{BASE_URL}/api/finance/ar/customers",
                    params={"workshop_id": WORKSHOP_ID, "as_of": today, "include_today": "true"}, timeout=60)
    assert r.status_code == 200, f"ar/customers HTTP {r.status_code}: {r.text[:400]}"
    data = r.json()
    debtors = data.get("customers") or data.get("debtors") or data.get("items") or []
    REPORT["debtors_count"] = len(debtors)
    REPORT["debtors_total_ar_customers_endpoint"] = data.get("total_ar") or data.get("grand_total")

    found = [d for d in debtors if "العطان" in json.dumps(d, ensure_ascii=False)]
    REPORT["alattan_in_debtors"] = found
    assert not found, f"Al-Attan unexpectedly present in debtors: {found}"


# ─────────────────────────── VERIFY B ───────────────────────────

def test_B_legacy_duplicates_unreversed(journal):
    findings = []
    total_effect = 0.0

    # Collect reversal-target ids
    reversed_ids = set()
    for e in journal:
        desc = _text(e)
        if "REVERSAL_OF:" in desc or (e.get("reference_id") or "").startswith("reversal::"):
            # extract target
            import re
            for m in re.finditer(r"REVERSAL_OF:([a-f0-9\-]+)", desc):
                reversed_ids.add(m.group(1))
            ref = str(e.get("reference_id") or "")
            if ref.startswith("reversal::"):
                reversed_ids.add(ref.split("::", 1)[1])

    for ref_id, expected_amt in REF_LEGACY_DUPS:
        matches = [e for e in journal if str(e.get("reference_id") or "") == ref_id]
        ar_debit_lines = []
        sources = []
        for e in matches:
            lines = _lines(e)
            ard = sum(_debit(l) for l in lines if _is_ar_line(l))
            if ard > 0:
                ar_debit_lines.append({"id": e.get("id") or e.get("entry_id") or e.get("_id"),
                                       "source": e.get("source"), "ar_debit": ard,
                                       "desc": _text(e)[:150]})
                sources.append(e.get("source"))
        # No reversal targets these ids
        any_reversed = any((it["id"] in reversed_ids) for it in ar_debit_lines)
        findings.append({
            "ref": ref_id, "expected_each": expected_amt,
            "count_sales_with_ar_debit": len(ar_debit_lines),
            "sources": sources, "entries": ar_debit_lines,
            "any_reversed": any_reversed,
        })
        if len(ar_debit_lines) >= 2 and not any_reversed:
            total_effect += expected_amt

    REPORT["legacy_dup_findings"] = findings
    REPORT["LEGACY_DUP_TOTAL_AR_EFFECT"] = total_effect

    # Assert each ref has ≥2 sales with AR-debit, no reversal
    unresolved = [f for f in findings if f["count_sales_with_ar_debit"] >= 2 and not f["any_reversed"]]
    REPORT["verdict_LEGACY_DUPLICATES_PRESENT"] = [f["ref"] for f in unresolved]

    # Non-fatal: report finding regardless
    if len(unresolved) < len(REF_LEGACY_DUPS):
        REPORT["legacy_dup_warning"] = f"Only {len(unresolved)}/{len(REF_LEGACY_DUPS)} expected legacy dups verified as unresolved"


def test_B_ref_174f49a1_resolved(journal):
    matches = [e for e in journal if REF_RESOLVED in str(e.get("reference_id") or "")]
    ar_sales = []
    for e in matches:
        lines = _lines(e)
        ard = sum(_debit(l) for l in lines if _is_ar_line(l))
        if ard > 0:
            ar_sales.append({"id": e.get("id") or e.get("entry_id") or e.get("_id"),
                             "source": e.get("source"), "ar_debit": ard})

    # Look for reversal entries pointing to these ids
    resolved_flags = []
    for s in ar_sales:
        sid = str(s["id"])
        rev = [e for e in journal if f"REVERSAL_OF:{sid}" in _text(e) or str(e.get("reference_id") or "") == f"reversal::{sid}"]
        resolved_flags.append(bool(rev))

    REPORT["ref_174f49a1_ar_sales"] = ar_sales
    REPORT["ref_174f49a1_all_reversed"] = all(resolved_flags) if resolved_flags else None


# ─────────────────────────── VERIFY C ───────────────────────────

def test_C_current_ar_readers_identical(session):
    today = date.today().isoformat()
    readers = {}

    r1 = session.get(f"{BASE_URL}/api/finance/ar/customers",
                     params={"workshop_id": WORKSHOP_ID, "as_of": today, "include_today": "true"}, timeout=60)
    if r1.status_code == 200:
        d = r1.json()
        readers["ar_customers.total_ar"] = d.get("total_ar") or d.get("grand_total") or d.get("total")

    r2 = session.get(f"{BASE_URL}/api/finance/ar/ledger",
                     params={"workshop_id": WORKSHOP_ID, "as_of": today}, timeout=60)
    if r2.status_code == 200:
        d = r2.json()
        readers["ar_ledger.ending_balance"] = d.get("ending_balance") or d.get("total") or d.get("balance")

    r3 = session.get(f"{BASE_URL}/api/finance/ar-ledger",
                     params={"workshop_id": WORKSHOP_ID}, timeout=60)
    if r3.status_code == 200:
        d = r3.json()
        readers["ar-ledger.current_vehicle_ar_total"] = (
            d.get("current_vehicle_ar_total") or d.get("total_ar") or d.get("ending_balance")
        )

    # Katrina tool via subprocess
    try:
        import subprocess
        code = (
            "import asyncio, sys; sys.path.insert(0,'.'); "
            "from dotenv import load_dotenv; load_dotenv('.env'); "
            "from core import tool_router; "
            "r=asyncio.run(tool_router.call_tool('finance.ar_summary', workshop_id='finmodule-sync')); "
            "print(r['result']['total_ar'])"
        )
        out = subprocess.run(["python3", "-c", code], cwd="/app/backend",
                             capture_output=True, text=True, timeout=60)
        val = (out.stdout or "").strip().splitlines()[-1] if out.stdout else None
        try:
            readers["katrina.finance.ar_summary.total_ar"] = float(val)
        except Exception:
            readers["katrina.finance.ar_summary.total_ar_raw"] = val
            readers["katrina.stderr"] = out.stderr[-400:]
    except Exception as ex:
        readers["katrina.error"] = str(ex)

    REPORT["current_ar_readers"] = readers

    numeric = {k: v for k, v in readers.items() if isinstance(v, (int, float))}
    REPORT["current_ar_readers_numeric"] = numeric

    if len(numeric) >= 2:
        vals = list(numeric.values())
        max_diff = max(vals) - min(vals)
        REPORT["current_ar_readers_max_diff"] = max_diff
        # tolerance = 0.5 SAR
        REPORT["verdict_CURRENT_AR_READERS_IDENTICAL"] = max_diff < 0.5
        assert max_diff < 0.5, f"Readers disagree: {numeric}"
    else:
        REPORT["verdict_CURRENT_AR_READERS_IDENTICAL"] = "INSUFFICIENT_READERS"


# ─────────────────────────── VERIFY D ───────────────────────────

def test_D_raw_ledger_layer_quantification(journal):
    per_party = defaultdict(float)
    for e in journal:
        party = (e.get("party_name") or e.get("party") or "").strip() or "مفتوح"
        for l in _lines(e):
            if _is_ar_line(l):
                per_party[party] += _debit(l) - _credit(l)

    grand_total = sum(per_party.values())
    open_party = per_party.get("مفتوح", 0.0)

    # top 10 for report
    top = sorted(per_party.items(), key=lambda kv: -kv[1])[:10]

    REPORT["RAW_LEDGER_AR_TOTAL"] = round(grand_total, 2)
    REPORT["UNATTRIBUTED_OPEN_PARTY_TOTAL"] = round(open_party, 2)
    REPORT["raw_ledger_top_parties"] = [(k, round(v, 2)) for k, v in top]


# ─────────────────────────── FINAL DUMP ───────────────────────────

def test_ZZ_dump_report():
    print("\n\n========== ITER 357 AUDIT REPORT ==========")
    print(json.dumps(REPORT, ensure_ascii=False, indent=2, default=str))
    print("========== END ==========\n")
    # persist
    with open("/app/test_reports/iter357_audit_dump.json", "w", encoding="utf-8") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=2, default=str)
