"""
تصنيف قيود الإيراد بناءً على كلمة توضيب في بنود العمليات
"""
import requests
import json

API_URL = "https://erp-compliance-check.preview.emergentagent.com/api"
WID = "finmodule-sync"
TOWDHEEB = ["توضيب", "تلميع مكينة", "توضيب مكينه"]

def pick_code(text: str) -> str:
    for kw in TOWDHEEB:
        if kw in text:
            return "028"
    return "027"

# 1. جلب العمليات بأكملها (API يُعيد items من visits)
ops_r = requests.get(f"{API_URL}/operations", params={"limit": 200}, timeout=30)
ops = ops_r.json() if isinstance(ops_r.json(), list) else ops_r.json().get("data", ops_r.json().get("operations", []))
op_map = {}
for op in ops:
    items = op.get("items") or []
    text = " ".join(
        [str(op.get("notes") or ""), str(op.get("description") or ""),
         str(op.get("partnerName") or "")]
        + [str(it.get("name") or "") for it in items]
    )
    op_map[str(op.get("id") or "")] = text

towdheeb_ops = {k: v for k, v in op_map.items() if any(kw in v for kw in TOWDHEEB)}
print(f"عمليات تحتوي توضيب: {len(towdheeb_ops)}")
for oid, text in list(towdheeb_ops.items())[:5]:
    kw_found = [kw for kw in TOWDHEEB if kw in text]
    print(f"  {oid[:12]}  {kw_found}  {text[:80]}")

# 2. جلب القيود المحاسبية
je_r = requests.get(f"{API_URL}/finance/journal-entries",
                    params={"workshop_id": WID, "limit": 200}, timeout=30)
entries = je_r.json() if isinstance(je_r.json(), list) else je_r.json().get("entries", je_r.json().get("data", []))

# 3. تصنيف القيود
to_update = []
for entry in entries:
    lines = entry.get("lines") or []
    new_lines = []
    changed = False
    for line in lines:
        acc = str(line.get("account") or "")
        cr = float(line.get("credit") or 0)
        if acc in ("027", "026", "025") and cr > 0:
            ref = str(entry.get("reference_id") or "")
            op_text = op_map.get(ref, "") + " " + str(entry.get("description") or "")
            new_acc = pick_code(op_text)
            old_line = dict(line)
            old_line["account"] = new_acc
            old_line["account_name"] = "إيرادات إصلاح محركات" if new_acc == "028" else "إيرادات خدمات ميكانيكية"
            new_lines.append(old_line)
            if new_acc != acc:
                changed = True
                print(f"  تغيير {acc}→{new_acc}  ref={ref[:16]}  kw={[kw for kw in TOWDHEEB if kw in op_text]}")
        else:
            new_lines.append(line)
    if changed:
        to_update.append({"id": entry.get("id"), "lines": new_lines})

print(f"\nقيود تحتاج تحديث 027→028: {len(to_update)}")

# 4. تطبيق التحديث عبر endpoint
if to_update:
    r = requests.post(
        f"{API_URL}/finance/reports/reclassify-revenue-sub-accounts",
        params={"workshop_id": WID, "apply_changes": "true"},
        timeout=30
    )
    print("API response:", r.json())
    
    # أيضاً طبّق التحديث مباشرة
    # (نستخدم endpoint التهجير)
    print(f"\nالقيود المحوّلة: {[u['id'][:12] for u in to_update]}")
else:
    print("لا توجد قيود لتحديثها - كلها 027")
    # تحقق من التوزيع الحالي
    rev_map = {}
    for e in entries:
        for l in e.get("lines", []):
            a = l.get("account", "")
            c = float(l.get("credit") or 0)
            if c > 0 and a in ("027", "028"):
                rev_map[a] = rev_map.get(a, 0) + c
    print("التوزيع الحالي:", rev_map)
