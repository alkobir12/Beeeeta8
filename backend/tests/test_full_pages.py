"""
اختبار شامل: لوحة التحكم، العمليات، دفتر اليومية، متابعة الذمم، القسم المالي
"""
import requests, json, time
from datetime import datetime

BASE = "https://finance-overhaul-7.preview.emergentagent.com/api"
WID  = "finmodule-sync"

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"
results = []

OLD_CODES = {'1101','1102','1103','1104','4001','4000','4100','6100','5000','50021','600102','600103','11030003','21010054'}

def chk(label, ok, detail=""):
    icon = PASS if ok else FAIL
    results.append({"ok": ok, "label": label})
    print(f"  {icon} {label}" + (f"  →  {detail}" if detail else ""))
    return ok

# ─── 1. لوحة التحكم ─────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  [1] لوحة التحكم")
print("="*65)

r = requests.get(f"{BASE}/vehicles?limit=10", timeout=20)
chk("GET /api/vehicles → 200", r.status_code == 200, f"status={r.status_code}")
if r.ok:
    vehicles = r.json() if isinstance(r.json(), list) else r.json().get('data', r.json().get('vehicles', []))
    chk("مركبات موجودة", len(vehicles) > 0, f"عدد={len(vehicles)}")
    # تحقق من حقل fileNumber
    has_fn = any(v.get('fileNumber') or v.get('file_number') for v in vehicles[:5])
    chk("حقل fileNumber موجود في المركبات", has_fn)

# ─── 2. العمليات ─────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  [2] العمليات")
print("="*65)

r2 = requests.get(f"{BASE}/operations?limit=100", timeout=20)
chk("GET /api/operations → 200", r2.status_code == 200)
if r2.ok:
    ops = r2.json() if isinstance(r2.json(), list) else r2.json().get('data', r2.json().get('operations', []))
    chk("عمليات موجودة", len(ops) > 0, f"عدد={len(ops)}")
    # عمليات آجل
    credit_ops = [o for o in ops if 'credit' in str(o.get('paymentMethod', '')) or 'credit' in str(o.get('paymentStatus', ''))]
    chk("يوجد عمليات آجل قابلة للسداد", len(credit_ops) > 0, f"عدد={len(credit_ops)}")
    
    # اختبار confirm-payment
    if credit_ops:
        op_id = credit_ops[0]['id']
        r_cp = requests.post(f"{BASE}/operations/{op_id}/confirm-payment", 
                             json={"workshopId": WID, "payment_method": "bank", "date": "2026-04-27"},
                             timeout=20)
        chk("confirm-payment يعمل", r_cp.status_code in (200, 201), f"status={r_cp.status_code}")

# ─── 3. دفتر اليومية ─────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  [3] دفتر اليومية — فحص الأكواد")
print("="*65)

r3 = requests.get(f"{BASE}/finance/journal-entries?workshop_id={WID}&limit=200", timeout=20)
chk("GET /api/finance/journal-entries → 200", r3.status_code == 200)
if r3.ok:
    entries = r3.json() if isinstance(r3.json(), list) else r3.json().get('entries', r3.json().get('data', []))
    chk("قيود يومية موجودة", len(entries) > 0, f"عدد={len(entries)}")
    
    old_found = {}
    unbalanced = []
    for e in entries:
        lines = e.get('lines', [])
        td = sum(float(l.get('debit', 0) or 0) for l in lines)
        tc = sum(float(l.get('credit', 0) or 0) for l in lines)
        if abs(td - tc) > 0.5 and td > 0:
            unbalanced.append(e.get('id', '?')[:12])
        for l in lines:
            acc = str(l.get('account', ''))
            if acc in OLD_CODES or (len(acc) > 6 and acc.isdigit() and not acc.startswith('2101')):
                old_found[acc] = old_found.get(acc, 0) + 1
    
    chk("لا أكواد قديمة في القيود", len(old_found) == 0, 
        f"أكواد: {dict(list(old_found.items())[:5])}" if old_found else "نظيف")
    chk("جميع القيود متوازنة", len(unbalanced) == 0,
        f"غير متوازن: {unbalanced[:3]}" if unbalanced else "✓")
    
    # تحقق من حساب 042
    has_042 = any(l.get('account') == '042' for e in entries for l in e.get('lines', []))
    chk("حساب 042 (ايراد قطع الورشه) موجود في القيود", has_042)
    
    # توزيع الإيرادات
    rev_map = {}
    for e in entries:
        for l in e.get('lines', []):
            acc = l.get('account', '')
            cr = float(l.get('credit', 0) or 0)
            if cr > 0 and acc in ('027', '028', '042', '025', '026'):
                rev_map[acc] = rev_map.get(acc, 0) + cr
    print(f"\n  توزيع الإيرادات في القيود:")
    names = {'027': 'خدمات ميكانيكية', '028': 'إصلاح محركات/توضيب', '042': 'قطع الورشه', '025': 'إيرادات عامة', '026': 'إيرادات الخدمات'}
    for acc, amt in sorted(rev_map.items()):
        print(f"    [{acc}] {names.get(acc, acc):30s}  {amt:>10,.2f} ر.س")

# ─── 4. متابعة الذمم ─────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  [4] متابعة الذمم")
print("="*65)

# chart of accounts لصفحة الذمم
r4 = requests.get(f"{BASE}/finance/chart-of-accounts?workshop_id={WID}", timeout=20)
chk("GET /api/finance/chart-of-accounts → 200", r4.status_code == 200)
if r4.ok:
    d = r4.json()
    accounts_data = d.get('data', d) if isinstance(d, dict) else d
    account_rows = accounts_data if isinstance(accounts_data, list) else accounts_data.get('accounts', [])
    chk("حسابات الدليل موجودة", len(account_rows) > 0, f"عدد={len(account_rows)}")
    
    # فحص وجود حسابات AR (005)
    ar_accounts = [a for a in account_rows if a.get('code') == '005' or a.get('legacy_code') in ('1103',)]
    chk("حساب العملاء 005 موجود", len(ar_accounts) > 0)

# اختبار إنشاء أمر سداد من الذمم
r4b = requests.post(f"{BASE}/operations", json={
    "workshopId": WID, "workshop_id": WID,
    "type": "payment_order",
    "total": 100, "amount": 100,
    "paymentAmount": 100,
    "paymentMethod": "bank",
    "paymentStatus": "paid",
    "status": "issued",
    "date": datetime.now().strftime("%Y-%m-%d"),
    "accountingAccountCode": "004",
    "partnerName": "اختبار متابعة الذمم",
    "partnerType": "customer",
    "notes": "اختبار أمر سداد"
}, timeout=20)
chk("إنشاء أمر سداد من الذمم", r4b.status_code in (200, 201), f"status={r4b.status_code}")
if r4b.ok:
    # حذف الاختبار
    op_test_id = r4b.json().get('id', '')
    if op_test_id:
        requests.delete(f"{BASE}/operations/{op_test_id}", timeout=10)

# ─── 5. القسم المالي ─────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  [5] القسم المالي")
print("="*65)

# income statement
r5a = requests.get(f"{BASE}/finance/reports/income-statement", timeout=30)
chk("income-statement → 200", r5a.status_code == 200)
if r5a.ok:
    d = r5a.json().get('data', r5a.json())
    totals = d.get('totals', {})
    rev = float(totals.get('revenue', 0) or 0)
    net = float(totals.get('net_income', 0) or 0)
    chk("revenue > 0", rev > 0, f"{rev:,.2f} ر.س")
    chk("net_income > 0", net > 0, f"{net:,.2f} ر.س")

# accounts/tree
r5b = requests.get(f"{BASE}/accounts/tree", timeout=30)
chk("accounts/tree → 200", r5b.status_code == 200)
if r5b.ok:
    d = r5b.json().get('data', r5b.json())
    summary = d.get('summary', {}) if isinstance(d, dict) else {}
    chk("assets > 0 في الدليل", float(summary.get('assets', 0) or 0) > 0,
        f"{summary.get('assets', 0):,.2f} ر.س")
    chk("revenue > 0 في الدليل", float(summary.get('revenue', 0) or 0) > 0,
        f"{summary.get('revenue', 0):,.2f} ر.س")

# trial balance
r5c = requests.get(f"{BASE}/finance/reports/trial-balance?workshop_id={WID}", timeout=20)
if r5c.ok:
    tb = r5c.json().get('data', r5c.json())
    totals_tb = tb.get('totals', {})
    td_tb = float(totals_tb.get('total_debit', 0) or 0)
    tc_tb = float(totals_tb.get('total_credit', 0) or 0)
    diff = abs(td_tb - tc_tb)
    chk("ميزان المراجعة متوازن", diff < 1, f"D={td_tb:,.2f} C={tc_tb:,.2f} فرق={td_tb-tc_tb:,.2f}")
else:
    print(f"  {WARN} trial-balance: {r5c.status_code}")

# ─── ملخص ────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  النتيجة النهائية")
print("="*65)

passed = sum(1 for r in results if r["ok"])
failed = sum(1 for r in results if not r["ok"])
total  = len(results)
print(f"\n  {PASS} نجح  : {passed}/{total}")
print(f"  {FAIL} فشل  : {failed}/{total}")
print(f"  نسبة النجاح: {passed/total*100:.0f}%")

if failed:
    print(f"\n  بنود فاشلة:")
    for r in results:
        if not r["ok"]: print(f"    {FAIL} {r['label']}")

# حفظ
import json as J
with open("/app/test_reports/iteration_167.json", "w", encoding="utf-8") as f:
    J.dump({"timestamp": datetime.now().isoformat(), "passed": passed, "failed": failed,
            "total": total, "revenue_distribution": rev_map if r3.ok else {}, "details": results}, f, ensure_ascii=False, indent=2)
print(f"\n  تقرير: /app/test_reports/iteration_167.json")
