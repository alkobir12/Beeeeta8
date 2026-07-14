"""READ-ONLY comprehensive scan — ALL closed visits:
receipts == items AND zero invoice-side journal entries."""
import json, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from supabase_service import SupabaseService

sb = SupabaseService().client
entries = sb.table("journal_entries").select("*").execute().data or []
visits = sb.table("vehicle_visits").select("*").execute().data or []
vehicles = {str(v["id"]): v for v in (sb.table("vehicles").select("*").execute().data or [])}

def jl(x):
    if isinstance(x, str):
        try: return json.loads(x)
        except Exception: return {}
    return x or {}

# index entries by reference_id, split invoice vs receipt
inv_by_ref, rec_by_ref = {}, {}
for e in entries:
    ref = str(e.get("reference_id") or "").strip()
    if not ref: continue
    tt = str(e.get("transaction_type") or "")
    tot = float(e.get("total") or 0)
    if tt in ("sale", "service"):
        inv_by_ref.setdefault(ref, []).append((str(e["id"])[:8], tot))
    elif tt == "payment":
        rec_by_ref.setdefault(ref, []).append((str(e["id"])[:8], tot))

match, anomalies = [], []
for v in visits:
    status = str(v.get("status") or "")
    if status not in ("completed", "closed"): continue
    vid = str(v["id"])
    notes = jl(v.get("notes"))
    items = notes.get("items") or []
    pays = notes.get("payments") or []
    items_total = round(sum(float(i.get("total") or 0) for i in items), 2)
    pays_total = round(sum(float(p.get("amount") or 0) for p in pays), 2)
    inv_total = round(sum(t for _, t in inv_by_ref.get(vid, [])), 2)
    rec_total = round(sum(t for _, t in rec_by_ref.get(vid, [])), 2)
    veh = vehicles.get(str(v.get("vehicle_id") or ""), {})
    row = {
        "visit": vid[:8],
        "customer": (veh.get("name") or veh.get("customer_name") or "")[:35],
        "plate": (veh.get("plate_number") or veh.get("plate") or "")[:15],
        "closed": str(v.get("exit_date") or "")[:10],
        "items_total": items_total,
        "receipts_total": pays_total,
        "invoiced": inv_total,
        "items": [{"name": str(i.get("name","")).strip()[:40], "type": i.get("itemType"),
                   "billing": i.get("billingType"), "total": float(i.get("total") or 0)} for i in items],
    }
    if items_total <= 0 and pays_total <= 0:
        continue
    if abs(pays_total - items_total) < 0.01 and inv_total == 0 and items_total > 0:
        match.append(row)
    elif inv_total < items_total:
        row["gap"] = round(items_total - inv_total, 2)
        row["pay_vs_items"] = round(pays_total - items_total, 2)
        anomalies.append(row)

match.sort(key=lambda r: -r["items_total"])
anomalies.sort(key=lambda r: -r["gap"])

print(f"== MATCH (receipts==items, invoice=0): {len(match)} visits, total={round(sum(r['items_total'] for r in match),2)}")
for r in match:
    print(f"  {r['visit']} | {r['closed']} | {r['customer']} | {r['plate']} | items={r['items_total']} receipts={r['receipts_total']} invoiced=0")
    for i in r["items"]:
        print(f"      - [{i['type']}/{i['billing']}] {i['name']} = {i['total']}")

print(f"\n== OUT-OF-CRITERion anomalies (invoiced < items but receipts != items): {len(anomalies)}, gap total={round(sum(r['gap'] for r in anomalies),2)}")
for r in anomalies:
    print(f"  {r['visit']} | {r['closed']} | {r['customer']} | items={r['items_total']} receipts={r['receipts_total']} invoiced={r['invoiced']} gap={r['gap']}")

with open("/app/docs/diagnostics/CLOSED_VISITS_MISSING_INVOICES.json", "w", encoding="utf-8") as f:
    json.dump({"match": match, "anomalies": anomalies}, f, ensure_ascii=False, indent=1)
print("\nsaved: /app/docs/diagnostics/CLOSED_VISITS_MISSING_INVOICES.json")
