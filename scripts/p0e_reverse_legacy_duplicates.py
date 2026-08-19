"""P0-E: عكس 3 قيود محاذاة مكررة عبر AccountingEngine (باعتماد المستخدم الصريح)."""
import json
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from supabase_service import SupabaseService
from core import accounting_engine

DUPES = [
    {"id": "d87d711e-a660-44c7-a93a-31b06dccdce9", "ref": "f5813fbd", "amount": 800.0, "source": "fin_engine_align_v1"},
    {"id": "1a721f64-e481-4152-a0ae-d9d450d065d8", "ref": "ca32e1a6", "amount": 150.0, "source": "hist_vehicle_ar_repair"},
    {"id": "4601b6e8-46a5-4a09-8fd5-f78a506f29ad", "ref": "0fd379c7", "amount": 2500.0, "source": "fin_engine_align_v1"},
]

sb = SupabaseService().client


def snapshot():
    rows = sb.table("journal_entries").select("id,lines,source").execute().data
    count = len(rows)
    td = sum(float(ln.get("debit") or 0) for r in rows for ln in (r.get("lines") or []))
    tc = sum(float(ln.get("credit") or 0) for r in rows for ln in (r.get("lines") or []))
    ar_raw = 0.0
    for r in rows:
        for ln in (r.get("lines") or []):
            code = str(ln.get("account_code") or ln.get("accountCode") or "")
            name = str(ln.get("account_name") or ln.get("accountName") or "")
            if code == "005" or "عملاء" in name or "ذمم" in name.replace("ذمم الموردين", ""):
                ar_raw += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return {"journal_count": count, "total_debit": round(td, 2), "total_credit": round(tc, 2), "raw_ar_net": round(ar_raw, 2)}


before = snapshot()
print("BEFORE:", json.dumps(before, ensure_ascii=False))

results = []
for d in DUPES:
    res = accounting_engine.reverse_entry(
        journal_id=d["id"],
        reason=f"P0E_legacy_duplicate_cleanup: قيد محاذاة مكرر ({d['source']}) للزيارة {d['ref']} — اعتماد المالك 2026-06",
        actor={"user_id": "p0e_cleanup_approved_by_owner"},
    )
    results.append({"target": d["id"], "amount": d["amount"], "reversed": res.get("reversed"), "entries": res.get("entries")})
    print(f"REVERSE {d['id'][:8]} ({d['amount']}):", json.dumps(res, ensure_ascii=False, default=str)[:300])

after = snapshot()
print("AFTER:", json.dumps(after, ensure_ascii=False))
print("DELTA raw_ar_net:", round(after["raw_ar_net"] - before["raw_ar_net"], 2), "(expected -3450.0)")
print("BALANCED:", abs(after["total_debit"] - after["total_credit"]) < 0.01)

# idempotency re-run
print("\n--- IDEMPOTENCY RE-RUN ---")
for d in DUPES:
    res = accounting_engine.reverse_entry(journal_id=d["id"], reason="P0E rerun check", actor={"user_id": "p0e_cleanup"})
    idem = any(e.get("idempotent") for e in (res.get("entries") or []))
    print(f"{d['id'][:8]}: reversed={res.get('reversed')} idempotent={idem}")

with open("/app/test_reports/p0e_cleanup_result.json", "w", encoding="utf-8") as f:
    json.dump({"before": before, "after": after, "results": results}, f, ensure_ascii=False, indent=2, default=str)
print("\nSaved /app/test_reports/p0e_cleanup_result.json")
