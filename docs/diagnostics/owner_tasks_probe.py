"""READ-ONLY probe for owner's 3 tasks (2026-07). No writes whatsoever."""
import json, os, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from supabase_service import SupabaseService

sb = SupabaseService().client

VISITS = {
    "29b88c69": None, "e10a7a9e": None, "ef6f0f88": None, "7ce2e6dd": None,
}

out = {"visits": {}, "entries_after_cutoff": []}

# resolve full visit ids
rows = sb.table("vehicle_visits").select("*").execute().data or []
for r in rows:
    vid = str(r.get("id") or "")
    for pref in VISITS:
        if vid.startswith(pref):
            VISITS[pref] = r

# all journal entries (for ref matching + task 3)
entries = sb.table("journal_entries").select("*").execute().data or []
refs = {str(e.get("reference_id") or "").strip() for e in entries}

def entry_total(e):
    lines = e.get("lines") or []
    if isinstance(lines, str):
        try: lines = json.loads(lines)
        except Exception: lines = []
    return round(sum(float(l.get("debit") or 0) for l in lines), 2), lines

# Task 3: entries after 2026-07-07 11:52
CUT = "2026-07-07 11:52"
for e in entries:
    created = str(e.get("created_at") or e.get("date") or "")
    key = created.replace("T", " ")[:16]
    if key > CUT:
        tot, lines = entry_total(e)
        out["entries_after_cutoff"].append({
            "entry_id": str(e.get("id"))[:8],
            "created_at": created[:19],
            "description": (e.get("description") or "")[:80],
            "amount": tot,
            "status": e.get("status"),
            "created_by": e.get("created_by"),
            "proposer": e.get("proposer") or e.get("proposed_by"),
            "approver": e.get("approver") or e.get("approved_by"),
            "reference_id": str(e.get("reference_id") or "")[:12],
            "lines": [{"code": l.get("code") or l.get("account"), "debit": l.get("debit"), "credit": l.get("credit")} for l in lines],
        })
out["entries_after_cutoff"].sort(key=lambda x: x["created_at"])

# sample entry keys for schema visibility
out["entry_schema_keys"] = sorted(entries[0].keys()) if entries else []

# Tasks 1+2: visit details + linked ops + journalized status
for pref, v in VISITS.items():
    if not v:
        out["visits"][pref] = {"error": "VISIT NOT FOUND"}
        continue
    vid = str(v["id"])
    ops = sb.table("operations").select("*").eq("visit_id", vid).execute().data or []
    ops_view = []
    for op in ops:
        oid = str(op.get("id") or "")
        journalized = oid in refs
        ops_view.append({
            "op_id": oid[:8],
            "type": op.get("type"),
            "description": (op.get("description") or "")[:70],
            "total": float(op.get("total") or 0),
            "payment_method": op.get("payment_method") or op.get("paymentMethod"),
            "payment_status": op.get("payment_status") or op.get("paymentStatus"),
            "date": str(op.get("date") or op.get("created_at") or "")[:19],
            "journalized": journalized,
        })
    # entries referencing this visit id (receipts etc.)
    visit_entries = []
    for e in entries:
        ref = str(e.get("reference_id") or "")
        desc = e.get("description") or ""
        if ref.startswith(vid[:8]) or vid[:8] in desc:
            tot, _ = entry_total(e)
            visit_entries.append({"entry_id": str(e.get("id"))[:8], "desc": desc[:70],
                                  "amount": tot, "created_at": str(e.get("created_at") or "")[:19],
                                  "status": e.get("status")})
    # entries referencing any op of this visit
    op_ids = {str(op.get("id") or "") for op in ops}
    for e in entries:
        ref = str(e.get("reference_id") or "").strip()
        if ref in op_ids:
            tot, _ = entry_total(e)
            rec = {"entry_id": str(e.get("id"))[:8], "desc": (e.get("description") or "")[:70],
                   "amount": tot, "created_at": str(e.get("created_at") or "")[:19],
                   "status": e.get("status"), "via": "op_ref:" + ref[:8]}
            if rec["entry_id"] not in [x["entry_id"] for x in visit_entries]:
                visit_entries.append(rec)

    unj = [o for o in ops_view if not o["journalized"]]
    out["visits"][pref] = {
        "visit_id_full": vid,
        "status": v.get("status"),
        "customer": v.get("customer_name") or v.get("customerName"),
        "vehicle": v.get("plate_number") or v.get("plateNumber") or v.get("vehicle_id"),
        "opened_at": str(v.get("entry_date") or v.get("created_at") or "")[:19],
        "closed_at": str(v.get("exit_date") or v.get("closed_at") or "")[:19],
        "visit_total_field": v.get("total") or v.get("total_amount"),
        "ops_count": len(ops),
        "operations": ops_view,
        "ops_total": round(sum(o["total"] for o in ops_view), 2),
        "unjournalized_ops": unj,
        "unjournalized_total": round(sum(o["total"] for o in unj), 2),
        "journal_entries_linked": visit_entries,
    }

print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
