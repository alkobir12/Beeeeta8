"""اختبار سلامة وترابط النظام المحاسبي v1.0 — تدقيق آلي مقابل القواعد الـ13."""
import json
import os
import sys

import requests

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

API = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API = line.split("=", 1)[1].strip()
WID = "finmodule-sync"

_tok = requests.post(f"{API}/api/auth/login", json={"username": "مدير"}, timeout=30).json()["access_token"]
HDRS = {"Authorization": f"Bearer {_tok}"}

from supabase_service import SupabaseService
supa = SupabaseService().client

results = []


def check(num, name, ok, detail):
    results.append({"rule": num, "name": name, "pass": bool(ok), "detail": detail})
    print(f"{'✅' if ok else '❌'} [{num}] {name} — {detail}")


ops = supa.table("operations").select("*").execute().data or []
jes = supa.table("journal_entries").select("*").execute().data or []
accounts = supa.table("accounts").select("code,name,type").execute().data or []
acc_codes = {str(a["code"]).strip() for a in accounts}
acc_names = {str(a["code"]).strip(): str(a["name"]).strip() for a in accounts}
acc_types = {str(a["code"]).strip(): str(a["type"]).strip() for a in accounts}

# ── 1) مصدر حقيقة واحد: alerts == firewall dashboard ──
r1 = requests.get(f"{API}/api/finance/alerts", params={"workshop_id": WID}, timeout=30, headers=HDRS).json()
d1 = r1.get("data") or r1
r2 = requests.get(f"{API}/api/firewall/dashboard", params={"workshop_id": WID}, timeout=30, headers=HDRS).json()
d2 = r2.get("data") or r2
a1 = sorted(a.get("id", "") for a in (d1.get("alerts") or []))
a2 = sorted(a.get("id", "") for a in (d2.get("alerts") or []))
h1 = (d1.get("health") or {}).get("score")
h2 = (d2.get("health") or {}).get("score")
check(1, "مصدر حقيقة واحد (alerts == firewall)", a1 == a2 and h1 == h2,
      f"alerts {len(a1)}=={len(a2)}, health {h1}=={h2}")

# ── 2) كل عملية مالية لها قيد ──
refs = {str(e.get("reference_id") or "") for e in jes}
fin_types = {"sale", "service", "instant_sale", "purchase", "expense"}
missing = [o for o in ops if str(o.get("type")).lower() in fin_types
           and float(o.get("total") or 0) > 0 and str(o.get("id")) not in refs]
check(2, "كل عملية مالية لها قيد يومية", not missing, f"{len(missing)} عملية بدون قيد من {len(ops)}")

# ── 3) توازن كل قيد (مدين=دائن) ──
unbalanced = []
for e in jes:
    dsum = sum(float(l.get("debit") or 0) for l in (e.get("lines") or []))
    csum = sum(float(l.get("credit") or 0) for l in (e.get("lines") or []))
    if abs(dsum - csum) > 0.01:
        unbalanced.append(e["id"])
check(3, "توازن القيد المزدوج لكل قيد", not unbalanced, f"{len(unbalanced)} قيد غير متوازن من {len(jes)}")

# ── 4) لا قيود يتيمة (كل reference_id يشير لعملية موجودة) ──
op_ids = {str(o.get("id")) for o in ops}
orphans = [e["id"] for e in jes
           if e.get("reference_id") and str(e["reference_id"]) not in op_ids
           and not str(e["reference_id"]).startswith("reversal::")]
check(4, "لا قيود يتيمة (مرجعية سليمة)", not orphans, f"{len(orphans)} قيد يتيم")

# ── 5) دورة الآجل: بيع آجل → مدين ذمم (وليس نقد) ──
ar_code, cash_codes = "005", {"003", "004", "006"}
bad_credit = []
for o in ops:
    if str(o.get("payment_method") or "").lower() != "credit":
        continue
    ejs = [e for e in jes if str(e.get("reference_id")) == str(o.get("id"))]
    for e in ejs:
        for l in (e.get("lines") or []):
            if float(l.get("debit") or 0) > 0 and str(l.get("account")).strip() in cash_codes:
                bad_credit.append(e["id"])
check(5, "الآجل → ذمم مدينة وليس نقد", not bad_credit, f"{len(bad_credit)} قيد آجل يمس النقد")

# ── 6) التدفق النقدي يستثني الآجل ──
cf = d1.get("cash_flow") or {}
credit_total = sum(float(o.get("total") or 0) for o in ops
                   if str(o.get("payment_method") or "").lower() == "credit")
check(6, "التدفق النقدي يستثني الآجل", float(cf.get("inflow") or 0) == 0 and credit_total > 0,
      f"inflow={cf.get('inflow')} رغم آجل={credit_total}")

# ── 7) ميزان المراجعة متوازن ──
tb = requests.get(f"{API}/api/finance/reports/trial-balance", params={"workshop_id": WID}, timeout=30, headers=HDRS).json()
tbd = tb.get("data") or tb
tb_rows = tbd if isinstance(tbd, list) else (tbd.get("accounts") or tbd.get("rows") or [])
tb_d = sum(float(r.get("debit") or 0) for r in tb_rows)
tb_c = sum(float(r.get("credit") or 0) for r in tb_rows)
check(7, "ميزان المراجعة متوازن", abs(tb_d - tb_c) < 0.05, f"مدين={tb_d:,.2f} دائن={tb_c:,.2f}")

# ── 8) قائمة الدخل: الإيراد=13550 والتصنيف صحيح ──
inc = requests.get(f"{API}/api/finance/reports/income-statement", params={"workshop_id": WID}, timeout=30, headers=HDRS).json()
incd = inc.get("data") or inc
rev = float(incd.get("total_revenue") or incd.get("revenue") or (incd.get("totals") or {}).get("revenue") or 0)
check(8, "قائمة الدخل تعكس الإيراد المستحق", abs(rev - 13550.0) < 0.05, f"revenue={rev:,.2f} (متوقع 13,550)")

# ── 9) دفتر الذمم == إجمالي الآجل ──
ar = requests.get(f"{API}/api/finance/reports/ar-customers", params={"workshop_id": WID}, timeout=30, headers=HDRS).json()
ard = ar.get("data") or ar
ar_total = None
if isinstance(ard, dict):
    ar_total = ard.get("total_balance") or ard.get("total") or (ard.get("totals") or {}).get("balance")
    if ar_total is None and isinstance(ard.get("customers"), list):
        ar_total = sum(float(c.get("balance") or 0) for c in ard["customers"])
elif isinstance(ard, list):
    ar_total = sum(float(c.get("balance") or 0) for c in ard)
ar_total = float(ar_total or 0)
check(9, "دفتر ذمم العملاء == إجمالي الآجل", abs(ar_total - 13550.0) < 0.05, f"AR={ar_total:,.2f} (متوقع 13,550)")

# ── 10) اتساق الدليل: كل كود في القيود موجود بالدليل والاسم مطابق ──
bad_codes, bad_names = [], []
for e in jes:
    for l in (e.get("lines") or []):
        c = str(l.get("account") or "").strip()
        if c not in acc_codes:
            bad_codes.append(c)
        else:
            ln = str(l.get("account_name") or "").strip()
            an = acc_names.get(c, "")
            if ln and an and an not in ln and ln not in an:
                bad_names.append((c, ln, an))
check(10, "أكواد القيود موجودة في الدليل الحي", not bad_codes, f"أكواد غير معروفة: {sorted(set(bad_codes))}")

# ── 11) الميزانية العمومية متوازنة ──
bs = requests.get(f"{API}/api/finance/reports/balance-sheet", params={"workshop_id": WID}, timeout=30, headers=HDRS).json()
bst = (bs.get("data") or {}).get("totals") or {}
assets = float(bst.get("assets") or 0)
liab_eq = float(bst.get("liabilities_plus_equity") or 0)
check(11, "الميزانية: أصول = خصوم + حقوق", assets > 0 and abs(assets - liab_eq) < 0.05,
      f"أصول={assets:,.2f} خصوم+حقوق={liab_eq:,.2f}")

# ── 12) منع التكرار (Idempotency): إعادة fix-all لا تكرر ──
fx = requests.post(f"{API}/api/operations/integrity/fix-all", json={}, timeout=60, headers=HDRS).json()
fxd = fx.get("data") or {}
check(12, "إعادة التشغيل لا تكرر القيود (Idempotency)",
      int(fxd.get("missing_before") or 0) == 0 and int(fxd.get("fixed") or 0) == 0,
      f"missing={fxd.get('missing_before')}, fixed={fxd.get('fixed')}")

# ── 13) سلامة قاعدة البيانات: لا تكرار قيود لنفس العملية + مبلغ القيد == مبلغ العملية ──
from collections import Counter
ref_counts = Counter(str(e.get("reference_id")) for e in jes if e.get("reference_id"))
dups = {k: v for k, v in ref_counts.items() if v > 1}
amount_mismatch = []
op_by_id = {str(o["id"]): o for o in ops}
for e in jes:
    o = op_by_id.get(str(e.get("reference_id")))
    if o and abs(float(e.get("total") or 0) - float(o.get("total") or 0)) > 0.01:
        amount_mismatch.append(e["id"])
check(13, "سلامة قاعدة البيانات (لا تكرار + تطابق المبالغ)", not dups and not amount_mismatch,
      f"تكرار={len(dups)}, عدم تطابق مبلغ={len(amount_mismatch)}")

passed = sum(1 for r in results if r["pass"])
print(f"\n===== النتيجة: {passed}/13 =====")
with open("/app/test_reports/accounting_integrity_v1_audit.json", "w", encoding="utf-8") as f:
    json.dump({"passed": passed, "total": 13, "results": results}, f, ensure_ascii=False, indent=1)
