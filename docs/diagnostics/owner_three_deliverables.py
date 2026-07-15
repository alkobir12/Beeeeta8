"""READ-ONLY: (1) comprehensive auto:policy report, (2) 1,695 payment deep-dive,
(3) 18,266 vs 70,120 set reconciliation."""
import json, os, sys
from datetime import datetime, timezone
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from pymongo import MongoClient
from supabase_service import SupabaseService

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
sb = SupabaseService().client

def ts(x):
    try: return datetime.fromtimestamp(float(x), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return str(x)

# ---------- (1) auto:policy comprehensive ----------
drafts = {d["id"]: d for d in db.assistant_drafts.find({})}
commits = {}
for e in db.assistant_audit_log.find({"event": "COMMIT", "committer": "auto:policy"}):
    commits[e.get("draft_id")] = {"table": e.get("table"), "entity_id": str(e.get("entity_id"))[:36], "ts": ts(e.get("ts"))}

rows = []
for a in db.assistant_approvals.find({"approver": "auto:policy"}).sort("created_at", 1):
    d = drafts.get(a.get("draft_id"), {})
    p = d.get("payload", {}) or {}
    rows.append({
        "when": ts(a.get("created_at")),
        "draft_id": a.get("draft_id"),
        "action": d.get("action"),
        "proposer": d.get("proposer"),
        "status": a.get("status"),
        "payload_summary": json.dumps({k: p[k] for k in list(p)[:4]}, ensure_ascii=False)[:110],
        "committed": commits.get(a.get("draft_id")),
    })

by_table = {}
for r in rows:
    if r["committed"]:
        by_table[r["committed"]["table"]] = by_table.get(r["committed"]["table"], 0) + 1

report1 = {
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "total_auto_policy_approvals": len(rows),
    "approved": sum(1 for r in rows if r["status"] == "approved"),
    "rejected": sum(1 for r in rows if r["status"] == "rejected"),
    "committed_to_production": sum(1 for r in rows if r["committed"]),
    "commits_by_table": by_table,
    "first": rows[0]["when"] if rows else None,
    "last": rows[-1]["when"] if rows else None,
    "rows": rows,
}
json.dump(report1, open("/app/docs/verification/AUTO_POLICY_FULL_AUDIT.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("(1) auto:policy:", {k: report1[k] for k in ("total_auto_policy_approvals", "approved", "rejected", "committed_to_production", "commits_by_table", "first", "last")})

# ---------- (2) payment 1,695 deep dive ----------
v = [r for r in sb.table("vehicle_visits").select("*").execute().data if str(r["id"]).startswith("868355a4")][0]
notes = json.loads(v["notes"]) if isinstance(v["notes"], str) else v["notes"]
pay = [p for p in notes.get("payments", []) if abs(float(p.get("amount") or 0) - 1695.0) < 0.01]
ops = [o for o in sb.table("operations").select("*").execute().data if str(o["id"]).startswith("868355a4")]
entries_1695 = [e for e in sb.table("journal_entries").select("*").execute().data
                if abs(float(e.get("total") or 0) - 1695.0) < 0.01]
# actor correlation: auth events around client-ts 2026-07-11 14:46 UTC (epoch 1783781209)
logins = []
for coll in ("auth_audit", "auth_events", "login_audit"):
    if coll in db.list_collection_names():
        for e in db[coll].find({}):
            t = e.get("ts") or e.get("created_at") or 0
            try: tf = float(t)
            except Exception: continue
            if 1783781209 - 7200 <= tf <= 1783781209 + 3600:
                logins.append({"coll": coll, "user": e.get("username") or e.get("user"), "event": e.get("event") or e.get("type"), "ts": ts(tf), "ip": e.get("ip")})
report2 = {
    "payment": pay,
    "payment_epoch_ms": "pay-1783781209935 → 2026-07-11 14:46:49 UTC (ساعة العميل)",
    "has_journal_entry": bool([e for e in entries_1695 if "868355a4" in str(e.get("reference_id") or "")]),
    "journal_entries_with_total_1695_anywhere": [{"id": str(e["id"])[:8], "desc": (e.get("description") or "")[:60], "ref": str(e.get("reference_id") or "")[:8], "created": str(e.get("created_at"))[:19]} for e in entries_1695],
    "operation": [{k: str(o.get(k))[:60] for k in ("id", "total", "payment_method", "payment_status", "invoice_number", "created_at", "updated_at", "customer_name", "type")} for o in ops],
    "visit_status": v.get("status"), "visit_exit": str(v.get("exit_date"))[:19],
    "auth_events_window_12:46-15:46_UTC": logins,
    "updated_by_available": False,
}
json.dump(report2, open("/app/docs/verification/PAYMENT_1695_DEEP_DIVE.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("(2) 1695:", json.dumps({k: report2[k] for k in ("has_journal_entry", "journal_entries_with_total_1695_anywhere", "auth_events_window_12:46-15:46_UTC")}, ensure_ascii=False)[:400])

# ---------- (3) 18,266 vs 70,120 ----------
prev = json.load(open("/app/docs/verification/PREVIEW_SETTLEMENT_51_VISITS.json"))
out7 = json.load(open("/app/docs/verification/OUT_OF_CRITERION_7_VISITS.json"))
set51 = {r["visit"]: r["amount"] for r in prev["rows"]}
set7 = {r["visit"]: r["gap"] for r in out7["rows"]}
# recompute firewall measure directly (journalized receipts vs invoices per visit)
entries = sb.table("journal_entries").select("*").execute().data
visit_ids = {str(x["id"]) for x in sb.table("vehicle_visits").select("id").execute().data}
rec, inv = {}, {}
for e in entries:
    ref = str(e.get("reference_id") or "").strip()
    if ref not in visit_ids: continue
    tt = str(e.get("transaction_type") or "").lower()
    tot = float(e.get("total") or 0)
    if tt == "payment": rec[ref] = rec.get(ref, 0) + tot
    elif tt in ("sale", "service"): inv[ref] = inv.get(ref, 0) + tot
fw = {}
for ref, r_tot in rec.items():
    gap = round(r_tot - inv.get(ref, 0), 2)
    if gap > 0.01: fw[ref[:8]] = {"receipts": r_tot, "invoiced": inv.get(ref, 0), "fw_gap": gap}

overlap = []
for vid, d in sorted(fw.items(), key=lambda x: -x[1]["fw_gap"]):
    in51 = vid in set51
    in7 = vid in set7
    overlap.append({"visit": vid, **d,
                    "in_51_list": set51.get(vid), "in_7_list": set7.get(vid),
                    "verdict": "داخل الـ70,120" if (in51 or in7) else "زيادة خارجها"})
inside = [o for o in overlap if o["verdict"] == "داخل الـ70,120"]
outside = [o for o in overlap if o["verdict"] != "داخل الـ70,120"]
report3 = {
    "firewall_total": round(sum(d["fw_gap"] for d in fw.values()), 2),
    "firewall_visits": len(fw),
    "inside_70120_count": len(inside), "inside_70120_amount": round(sum(o["fw_gap"] for o in inside), 2),
    "outside_70120_count": len(outside), "outside_70120_amount": round(sum(o["fw_gap"] for o in outside), 2),
    "note": "المقياسان مختلفان: الجدار = سندات قبض مُرحّلة كقيود؛ الـ70,120 = بنود زيارات (مجدولة/خارج معيار). التقاطع بالزيارة لا بالمبلغ.",
    "detail": overlap,
}
json.dump(report3, open("/app/docs/verification/GAP_18266_VS_70120.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("(3):", json.dumps({k: report3[k] for k in ("firewall_total", "firewall_visits", "inside_70120_count", "inside_70120_amount", "outside_70120_count", "outside_70120_amount")}, ensure_ascii=False))
for o in overlap: print("   ", o)
