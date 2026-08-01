import os, json, requests
from collections import defaultdict

API = "https://stamp-approval-flow.preview.emergentagent.com/api"
tok = requests.post(f"{API}/auth/login", json={"username": "مدير", "pin": "123123"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

def get(path, **params):
    r = requests.get(f"{API}{path}", headers=H, params=params, timeout=60)
    r.raise_for_status()
    d = r.json()
    return d

customers = get("/customers")
if isinstance(customers, dict): customers = customers.get("customers") or customers.get("data") or []
ops = get("/operations", limit=2000)
if isinstance(ops, dict): ops = ops.get("data") or ops.get("items") or []
ar = get("/finance/ar-ledger", workshop_id="finmodule-sync").get("data", {})

# 1) متابعة الذمم: مجموع ajelBalance للعملاء
cust_ajel = {c.get("name"): round(float(c.get("ajelBalance") or 0), 2) for c in customers if float(c.get("ajelBalance") or 0) > 0}
total_cust_ajel = round(sum(cust_ajel.values()), 2)

# 2) العمليات: المتبقي من عمليات البيع/الخدمة الآجلة
CREDIT = {"credit"}
UNPAID = {"credit", "unpaid", "pending", "partial"}
op_remaining = defaultdict(float)
for op in ops:
    t = str(op.get("type") or "").lower()
    if t not in {"sale", "service", "instant_sale"}: continue
    pm = str(op.get("paymentMethod") or op.get("payment_method") or "").lower()
    ps = str(op.get("paymentStatus") or op.get("payment_status") or "").lower()
    if pm not in CREDIT and ps not in UNPAID: continue
    total = float(op.get("total") or 0)
    paid = float(op.get("paidAmount") or op.get("paid_amount") or 0)
    rem = max(0.0, total - paid)
    name = op.get("customerName") or op.get("customer_name") or op.get("partnerName") or op.get("partner_name") or "غير معروف"
    op_remaining[name] += rem
op_remaining = {k: round(v, 2) for k, v in op_remaining.items() if v > 0.009}
total_ops = round(sum(op_remaining.values()), 2)

print("=== دفتر الذمم (ar-ledger SSOT) ===")
print(json.dumps({k: v for k, v in ar.items() if not isinstance(v, list)}, ensure_ascii=False, indent=1))
for k in ar:
    if isinstance(ar[k], list) and ar[k]:
        print(f"  {k}: {len(ar[k])} rows, sample: {json.dumps(ar[k][:2], ensure_ascii=False)[:300]}")

print("\n=== متابعة الذمم (customers.ajelBalance) ===")
print("total:", total_cust_ajel, "| count:", len(cust_ajel))
print(json.dumps(cust_ajel, ensure_ascii=False))

print("\n=== العمليات (remaining على البيع الآجل) ===")
print("total:", total_ops, "| count:", len(op_remaining))
print(json.dumps(op_remaining, ensure_ascii=False))

print("\n=== المقارنة بالاسم ===")
names = set(cust_ajel) | set(op_remaining)
mismatches = []
for n in sorted(names):
    a, b = cust_ajel.get(n, 0), op_remaining.get(n, 0)
    if abs(a - b) > 0.01:
        mismatches.append((n, a, b))
for n, a, b in mismatches:
    print(f"MISMATCH: {n}: ذمم={a} vs عمليات={b} (فرق {round(a-b,2)})")
print("mismatch count:", len(mismatches))
