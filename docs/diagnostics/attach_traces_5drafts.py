"""Mint trace records for the 5 settlement drafts + attach trace_id (Mongo).
Backend restart afterwards re-hydrates STATE with trace_id."""
import json, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from pymongo import MongoClient
import os
from core import llm_traces

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
drafts = json.load(open("/app/docs/diagnostics/VISIT_29b88c69_SETTLEMENT_DRAFTS.json"))

result = []
for d in drafts:
    tid = llm_traces.start_trace(
        session_id=None, user="كاترينا", channel="runtime",
        message=f"draft:invoice — تسوية زيارة 29b88c69 — {d['item']} ({d['amount']} ر.س)")
    llm_traces.add_tool_call(
        tool="runtime.create_draft:invoice",
        tool_input={"draft_id": d["draft_id"], "total": d["amount"],
                    "customer": "يوسف عبد الرحمن الكبير",
                    "basis": "بنود زيارة 29b88c69 غير المقيّدة = 6,474.00 بالضبط (شرط المالك)"},
        write=True)
    llm_traces.finish_trace(
        final_response=f"draft {d['draft_id']} registered (pending Four-Eyes approval {d['approval_id']})",
        intent="invoice", status="draft_created",
        executed={"draft_id": d["draft_id"], "approval_id": d["approval_id"]})
    r = db.assistant_drafts.update_one({"id": d["draft_id"]}, {"$set": {"trace_id": tid}})
    d["trace_id"] = tid
    result.append({"draft_id": d["draft_id"], "trace_id": tid, "mongo_matched": r.matched_count})
    print(d["draft_id"], "->", tid, "| mongo:", r.matched_count)

json.dump(drafts, open("/app/docs/diagnostics/VISIT_29b88c69_SETTLEMENT_DRAFTS.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("OK")
