"""READ-ONLY final report — 4 visits: items, payments, invoice-side vs receipt-side entries."""
import json, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from supabase_service import SupabaseService

sb = SupabaseService().client
entries = sb.table("journal_entries").select("*").execute().data or []
visits = sb.table("vehicle_visits").select("*").execute().data or []
ops = sb.table("operations").select("*").execute().data or []

def jl(x):
    if isinstance(x, str):
        try: return json.loads(x)
        except Exception: return {}
    return x or {}

for pref in ["29b88c69", "e10a7a9e", "ef6f0f88", "7ce2e6dd"]:
    v = next(r for r in visits if str(r["id"]).startswith(pref))
    vid = str(v["id"])
    notes = jl(v.get("notes"))
    print(f"\n{'='*70}\nVISIT {pref} | status={v['status']} | in={str(v['entry_date'])[:16]} out={str(v['exit_date'])[:16]}")
    it_tot = 0.0
    print(" ITEMS:")
    for it in notes.get("items", []):
        t = float(it.get("total") or 0); it_tot += t
        print(f"   [{it.get('itemType')}/{it.get('billingType')}] {str(it.get('name','')).strip()[:45]} = {t}")
    print(f" ITEMS TOTAL = {round(it_tot,2)}")
    pay_tot = 0.0
    print(" PAYMENTS (from visit):")
    for p in notes.get("payments", []):
        a = float(p.get("amount") or 0); pay_tot += a
        print(f"   {str(p.get('date'))[:10]} | {a} | {p.get('method')} | je={str(p.get('journalEntryId'))[:8]}")
    print(f" PAYMENTS TOTAL = {round(pay_tot,2)}")
    op = next((o for o in ops if str(o.get("visit_id") or "") == vid), None)
    if op:
        print(f" OPERATION: id={str(op['id'])[:8]} total={op.get('total')} method={op.get('payment_method')} inv={op.get('invoice_number')} created={str(op.get('created_at'))[:16]}")
    else:
        print(" OPERATION: NONE")
    inv_tot, rec_tot = 0.0, 0.0
    print(" JOURNAL ENTRIES (ref=visit/op id):")
    for e in entries:
        if str(e.get("reference_id") or "") != vid:
            continue
        tt = str(e.get("transaction_type") or "")
        tot = float(e.get("total") or 0)
        kind = "INVOICE" if tt in ("sale", "service") else ("RECEIPT" if tt == "payment" else tt.upper())
        if kind == "INVOICE": inv_tot += tot
        elif kind == "RECEIPT": rec_tot += tot
        print(f"   [{kind}] {str(e['id'])[:8]} | {tot} | src={e.get('source')} | {str(e.get('created_at'))[:16]}")
    print(f" >> INVOICE-SIDE JOURNALIZED = {round(inv_tot,2)} | RECEIPTS = {round(rec_tot,2)}")
    print(f" >> UNJOURNALIZED (items {round(it_tot,2)} - invoiced {round(inv_tot,2)}) = {round(it_tot-inv_tot,2)}")
