"""A6 Reconciliation Probe — L14 (READ-ONLY, pure diagnostics).

يحسب قيمة «الذمم» من كل مصدر حقيقة على حدة، ويبني الجسر الحسابي بين
القيم الثلاث التاريخية: 9,850 / 8,905 / 11,150.
النتائج: /app/docs/diagnostics/A6_RECONCILIATION.json
"""
from __future__ import annotations

import itertools
import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
BYP = (os.environ.get("RATE_LIMIT_BYPASS_TOKEN") or "").strip().strip('"')
OUT = "/app/docs/diagnostics/A6_RECONCILIATION.json"

S = requests.Session()
S.headers["x-ratelimit-bypass"] = BYP
tok = S.post(f"{API}/auth/login", json={"username": "مدير"}, timeout=30).json()["access_token"]
S.headers["Authorization"] = f"Bearer {tok}"

AR_CODES = {"005", "1103", "113"}
CREDIT_METHODS = {"credit", "deferred", "اجل", "آجل", "ذمة", "ذمم"}
UNPAID_STATUSES = {"unpaid", "credit", "partial", "deferred", "pending"}
TARGETS = [9850.0, 8905.0, 11150.0]

res = {"ran_at": time.strftime("%Y-%m-%d %H:%M:%S"), "targets": TARGETS, "sources": {}, "bridges": {}}

# ── SRC-A: أرصدة العملاء المخزنة (ajelBalance>0) = ar_summary = صفحة متابعة الذمم ──
customers = S.get(f"{API}/customers", timeout=30).json()
debtors = [{"name": c.get("name"), "balance": float(c.get("ajelBalance") or 0)}
           for c in customers if float(c.get("ajelBalance") or 0) > 0]
neg = [{"name": c.get("name"), "balance": float(c.get("ajelBalance") or 0)}
       for c in customers if float(c.get("ajelBalance") or 0) < 0]
src_a = round(sum(d["balance"] for d in debtors), 2)
res["sources"]["A_customer_balances"] = {
    "value": src_a, "debtors_count": len(debtors), "debtors": sorted(debtors, key=lambda x: -x["balance"]),
    "negative_balances": neg,
    "consumers": ["finance.ar_summary (أداة كاترينا)", "صفحة متابعة الذمم DebtFollowUp (نفس الفلتر >0)"],
}

# ── SRC-B: القيود — رصيد حسابات الذمم (مدين−دائن) ──
entries = S.get(f"{API}/finance/journal-entries",
                params={"workshop_id": "finmodule-sync", "limit": 1000}, timeout=60).json()
if isinstance(entries, dict):
    entries = entries.get("data") or entries.get("entries") or []
ar_j = 0.0
ar_lines = []
for e in entries:
    for ln in (e.get("lines") or []):
        if str(ln.get("code") or ln.get("account") or "") in AR_CODES:
            d, c = float(ln.get("debit") or 0), float(ln.get("credit") or 0)
            ar_j += d - c
            ar_lines.append({"entry_id": str(e.get("id"))[:8], "desc": (e.get("description") or "")[:60],
                             "debit": d, "credit": c, "ref": str(e.get("reference_id") or "")[:12]})
res["sources"]["B_journal_ar_balance"] = {
    "value": round(ar_j, 2), "entries_scanned": len(entries), "ar_lines_count": len(ar_lines),
    "ar_lines": ar_lines,
    "consumers": ["دفتر الأستاذ/ميزان المراجعة (حسابات 005/1103/113)"],
}

# ── SRC-C: عمليات آجلة غير مقيّدة (فلتر الجدار الناري حرفياً) ──
ops = S.get(f"{API}/operations", params={"limit": 1000}, timeout=60).json()
if isinstance(ops, dict):
    ops = ops.get("data") or ops.get("items") or []
refs = {str(e.get("reference_id") or "").strip() for e in entries}
ar_ops, ar_ops_list = 0.0, []
for op in ops:
    method = str(op.get("paymentMethod") or op.get("payment_method") or "").strip().lower()
    ps = str(op.get("paymentStatus") or op.get("payment_status") or "").strip().lower()
    if method not in CREDIT_METHODS and ps not in UNPAID_STATUSES:
        continue
    if str(op.get("id") or "") in refs:
        continue
    t = str(op.get("type") or "").lower()
    amount = float(op.get("total") or 0)
    if t in {"sale", "service", "instant_sale"}:
        ar_ops += amount
        ar_ops_list.append({"op_id": str(op.get("id"))[:8], "type": t, "total": amount,
                            "customer": (op.get("customerName") or op.get("customer_name") or "")[:40],
                            "date": str(op.get("date") or op.get("createdAt") or "")[:10]})
res["sources"]["C_unjournalized_credit_ops"] = {
    "value": round(ar_ops, 2), "ops": ar_ops_list,
    "consumers": ["جزء من تنبيه الجدار الناري (ar_from_unjournalized_credit_ops)"],
}

# ── SRC-D: تنبيه الجدار الناري الحي «ذمم مدينة مفتوحة» ──
alerts = S.get(f"{API}/firewall/alerts", params={"workshop_id": "finmodule-sync"}, timeout=60).json()
alist = alerts if isinstance(alerts, list) else alerts.get("data") or alerts.get("alerts") or []
fw = next((a for a in alist if "ذمم مدينة" in str(a.get("title") or "")), None)
res["sources"]["D_firewall_alert"] = {
    "value": float(fw.get("financial_impact") or 0) if fw else None,
    "evidence": (fw or {}).get("evidence"),
    "formula": "B (قيود) + C (عمليات آجلة غير مقيّدة)",
    "consumers": ["سياق النظام المحقون في كل جلسة كاترينا (top_alerts)"],
}

# ── SRC-E: nl.search top_debtors (أعلى 5 فقط — جزئي بالتصميم) ──
r = S.post(f"{API}/assistant/tool/nl.search", json={"query": "أكثر العملاء مديونية"}, timeout=60)
nl = r.json().get("result") if r.status_code == 200 else {}
nl_rows = (nl or {}).get("rows") or (nl or {}).get("items") or (nl or {}).get("top_debtors") or []
nl_sum = 0.0
try:
    nl_sum = sum(float(x.get("balance") or x.get("ajel_balance") or x.get("value") or 0) for x in nl_rows)
except Exception:
    pass
res["sources"]["E_nl_search_top5"] = {"value": round(nl_sum, 2), "rows": nl_rows[:6],
                                      "consumers": ["إجابات «أكثر العملاء مديونية» في الشات — جزئي (أعلى 5)"]}

# ── الجسور الحسابية بين القيم الثلاث ──
balances = [d["balance"] for d in debtors]
names = [d["name"] for d in debtors]

def subset_hits(target, tol=0.01, max_k=None):
    hits = []
    n = len(balances)
    for k in range(1, (max_k or n) + 1):
        for combo in itertools.combinations(range(n), k):
            if abs(sum(balances[i] for i in combo) - target) <= tol:
                hits.append([{"name": names[i], "balance": balances[i]} for i in combo])
                if len(hits) >= 3:
                    return hits
    return hits

for t in TARGETS:
    res["bridges"][f"subset_of_current_debtors={t:g}"] = subset_hits(t)

diffs = {}
vals = {"A": src_a, "B": round(ar_j, 2), "C": round(ar_ops, 2),
        "D": res["sources"]["D_firewall_alert"]["value"], "E": round(nl_sum, 2)}
for (k1, v1), (k2, v2) in itertools.combinations(vals.items(), 2):
    if v1 is not None and v2 is not None:
        diffs[f"{k1}-{k2}"] = round(v1 - v2, 2)
res["bridges"]["pairwise_diffs"] = diffs
res["bridges"]["historic_deltas"] = {
    "11150-9850": 1300.0, "11150-8905": 2245.0, "9850-8905": 945.0,
    "note": "ابحث عن عمليات/قيود بهذه المبالغ ضمن C وB لتفسير اللقطات التاريخية",
}
match_ops = [o for o in ar_ops_list if abs(o["total"] - 1300) <= 0.01 or abs(o["total"] - 2245) <= 0.01 or abs(o["total"] - 945) <= 0.01]
match_debt = [d for d in debtors if abs(d["balance"] - 1300) <= 0.01 or abs(d["balance"] - 2245) <= 0.01 or abs(d["balance"] - 945) <= 0.01]
res["bridges"]["ops_matching_historic_deltas"] = match_ops
res["bridges"]["debtors_matching_historic_deltas"] = match_debt

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print(json.dumps({"A": vals["A"], "B": vals["B"], "C": vals["C"], "D": vals["D"], "E": vals["E"]}, ensure_ascii=False))
print("saved:", OUT)
