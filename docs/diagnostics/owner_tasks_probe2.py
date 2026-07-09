"""READ-ONLY probe #2 — raw rows + AR balances + unjournalized ops. No writes."""
import json, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from supabase_service import SupabaseService

sb = SupabaseService().client
AR_CODES = {"005", "1103", "113"}
CREDIT_METHODS = {"credit", "deferred", "اجل", "آجل", "ذمة", "ذمم"}
UNPAID_STATUSES = {"unpaid", "credit", "partial", "deferred", "pending"}

def jload(x):
    if isinstance(x, str):
        try: return json.loads(x)
        except Exception: return x
    return x

entries = sb.table("journal_entries").select("*").execute().data or []
refs = {str(e.get("reference_id") or "").strip() for e in entries}

# current journal AR balance
ar = 0.0
for e in entries:
    for ln in (jload(e.get("lines")) or []):
        if isinstance(ln, dict) and str(ln.get("code") or ln.get("account") or "") in AR_CODES:
            ar += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
print("== JOURNAL AR BALANCE (005/1103/113):", round(ar, 2), "| entries:", len(entries))

# source field of entries after cutoff
print("\n== ENTRIES AFTER 2026-07-07 11:52 (source/transaction_type):")
for e in sorted(entries, key=lambda x: str(x.get("created_at"))):
    if str(e.get("created_at") or "").replace("T", " ")[:16] > "2026-07-07 11:52":
        print("   ", str(e["id"])[:8], "|", str(e.get("created_at"))[:19], "| src:", e.get("source"),
              "| type:", e.get("transaction_type"), "| total:", e.get("total"))

# raw visits
print("\n== RAW VISITS:")
for pref in ["29b88c69", "e10a7a9e", "ef6f0f88", "7ce2e6dd"]:
    rows = [r for r in (sb.table("vehicle_visits").select("*").execute().data or []) if str(r["id"]).startswith(pref)]
    if not rows: print(pref, "NOT FOUND"); continue
    v = rows[0]
    notes = jload(v.get("notes"))
    print(f"\n-- visit {pref} raw keys:", sorted(v.keys()))
    for k in v:
        if k == "notes": continue
        print("   ", k, "=", str(v[k])[:100])
    print("    notes =", json.dumps(notes, ensure_ascii=False)[:1500] if notes else None)

# raw ops for those visits
print("\n== RAW OPS for target visits:")
for pref in ["29b88c69", "e10a7a9e", "ef6f0f88", "7ce2e6dd"]:
    ops = [o for o in (sb.table("operations").select("*").execute().data or []) if str(o.get("visit_id") or "").startswith(pref)]
    for o in ops:
        print(f"\n-- op for {pref}:")
        for k in o:
            if k in ("notes", "items"): continue
            print("   ", k, "=", str(o[k])[:90])
        print("    items =", json.dumps(jload(o.get("items")), ensure_ascii=False)[:1200])
        print("    notes =", json.dumps(jload(o.get("notes")), ensure_ascii=False)[:800])

# global unjournalized credit ops (firewall filter)
ops_all = sb.table("operations").select("*").execute().data or []
print("\n== GLOBAL UNJOURNALIZED CREDIT OPS (firewall filter):")
tot = 0.0
for op in ops_all:
    m = str(op.get("payment_method") or "").strip().lower()
    ps = str(op.get("payment_status") or "").strip().lower()
    if m not in CREDIT_METHODS and ps not in UNPAID_STATUSES: continue
    if str(op.get("id") or "") in refs: continue
    t = str(op.get("type") or "").lower()
    if t in {"sale", "service", "instant_sale"}:
        amt = float(op.get("total") or 0); tot += amt
        print("   ", str(op["id"])[:8], "|", t, "|", amt, "|", str(op.get("customer_name") or "")[:30],
              "| visit:", str(op.get("visit_id") or "")[:8], "|", str(op.get("date") or "")[:10])
print("   TOTAL:", round(tot, 2))
