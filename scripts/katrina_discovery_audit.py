"""KATRINA CAPABILITY DISCOVERY AUDIT — READ ONLY (no fixes, no writes)."""
import asyncio
import json
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

import core.tool_router as tr
from core.assistant_kernel import detect_tools, _extract_query
from core import action_runtime

OUT = {}


def section(name):
    print(f"\n{'='*60}\n{name}\n{'='*60}")


async def main():
    # ---------- 2: TOOL INVENTORY ----------
    tools = tr.list_tools()
    OUT["total_registered_tools"] = len(tools)
    OUT["write_tools"] = [t["name"] for t in tools if t["write"]]

    # ---------- 8: INTENT ROUTING MATRIX (deterministic layer, no LLM) ----------
    section("INTENT ROUTING MATRIX")
    questions = [
        ("كم إجمالي الذمم؟", "finance.ar_summary"),
        ("كم ذمة سعد العقيلي؟", "customers.search|finance.ar_summary"),
        ("من أكثر عميل عليه؟", "nl.search"),
        ("كم دخلنا هذا الشهر؟", "finance.sales_report"),
        ("كم المصروف؟", "firewall.cash_flow"),
        ("كم صافي الدخل؟", "?"),
        ("هل الميزانية متوازنة؟", "?"),
        ("كم عندنا نقد؟", "?"),
        ("اعرض آخر قيد", "accounting.journal_entries"),
        ("كم زيارة لهذه المركبة؟", "vehicles.search|workshop.active_visits"),
        ("وش باقي عليها؟", "?"),
        ("كم دفعت؟", "?"),
        ("من الموردين؟", "suppliers.search|finance.payables_summary"),
        ("وش يحتاج قراري اليوم؟", "runtime.pending_approvals"),
        ("اعرض سيارة فارس", "vehicles.search"),
        ("وش باقي على ح ق م 5520؟", "vehicles.search"),
        ("آخر زيارة لمحمد", "customers.search|operations.search"),
        ("اعرض كامري صالح", "vehicles.search"),
        ("كم دفع العميل؟", "customers.search"),
        ("قيود مؤقتة", "finance.ar_summary"),
    ]
    matrix = []
    for q, expected in questions:
        detected = detect_tools(q)
        row = {"question": q, "expected": expected, "detected": detected,
               "query_extracted": {t: _extract_query(q, t) for t in detected if t in
                                   {"customers.search", "vehicles.search", "suppliers.search", "operations.search"}}}
        matrix.append(row)
        print(f"Q: {q:35s} → {detected}")
    OUT["intent_matrix"] = matrix

    # ---------- 7: ENTITY RESOLUTION (read-only resolvers) ----------
    section("ENTITY RESOLUTION")
    er = {}
    er["exact_name"] = action_runtime.resolve_customer_target({"name": "سعد العقيلي"})
    er["partial_name"] = action_runtime.resolve_customer_target({"name": "العقيلي"})
    er["duplicate_first_name"] = action_runtime.resolve_customer_target({"name": "محمد"})
    er["unknown_entity"] = action_runtime.resolve_customer_target({"name": "شخصيه خيالية غير موجودة اطلاقا"})
    er["vehicle_by_plate"] = action_runtime.resolve_vehicle_target({"plate": "د س ا 3313"})
    er["vehicle_unknown"] = action_runtime.resolve_vehicle_target({"plate": "غ غ غ 99999"})
    for k, v in er.items():
        if v.get("row"):
            print(f"{k}: RESOLVED → {v['row'].get('name') or v['row'].get('plate_number')}")
        else:
            print(f"{k}: {v.get('error')} candidates={len(v.get('candidates') or [])}")
    OUT["entity_resolution"] = {
        k: ({"resolved": v["row"].get("name") or v["row"].get("plate_number")} if v.get("row")
            else {"error": v.get("error"), "candidates_count": len(v.get("candidates") or [])})
        for k, v in er.items()}

    # ---------- 3+12: READ CAPABILITY + FAILURE MODES (direct tool calls) ----------
    section("READ TOOLS LIVE VALUES")
    reads = {}
    for tool, kwargs in [
        ("finance.ar_summary", {}),
        ("finance.payables_summary", {}),
        ("finance.sales_report", {"query": "كل المدة"}),
        ("firewall.cash_flow", {}),
        ("accounting.journal_entries", {"limit": 5}),
        ("vehicles.status_summary", {}),
        ("workshop.active_visits", {}),
        ("operations.recent", {"limit": 5}),
        ("runtime.pending_approvals", {}),
        ("customers.search", {"query": "سعد العقيلي"}),
        ("suppliers.search", {"query": "العوفي"}),
        ("firewall.operation_integrity", {"limit": 20}),
    ]:
        r = await tr.call_tool(tool, **kwargs)
        ok = r.get("success")
        res = r.get("result") or {}
        err = (res.get("error") if isinstance(res, dict) else None) or r.get("error")
        reads[tool] = {"success": ok, "error": err}
        if tool == "finance.ar_summary":
            reads[tool].update({"total_ar": res.get("total_ar"), "debtors": res.get("total_customers_with_debt"), "source": res.get("ar_source")})
        elif tool == "finance.payables_summary":
            reads[tool].update({"total_ap": res.get("total_ap"), "suppliers": res.get("total_suppliers_with_balance")})
        elif tool == "finance.sales_report":
            reads[tool].update({"keys": list(res.keys())[:8] if isinstance(res, dict) else None})
        elif tool == "firewall.cash_flow":
            reads[tool].update({"keys": list(res.keys())[:8] if isinstance(res, dict) else None})
        elif tool == "accounting.journal_entries":
            reads[tool].update({"count": res.get("count"), "balanced": res.get("balanced")})
        elif tool == "vehicles.status_summary":
            reads[tool].update({"summary": {k: v for k, v in res.items() if not isinstance(v, (list, dict))}})
        elif tool == "operations.recent":
            reads[tool].update({"count": len(res.get("operations") or res.get("items") or []) if isinstance(res, dict) else None, "keys": list(res.keys())[:6] if isinstance(res, dict) else None})
        elif tool == "runtime.pending_approvals":
            reads[tool].update({"pending": len(res.get("approvals") or res.get("items") or []) if isinstance(res, dict) else None, "keys": list(res.keys())[:6] if isinstance(res, dict) else None})
        elif tool == "customers.search":
            reads[tool].update({"matches": res.get("count")})
        elif tool == "suppliers.search":
            reads[tool].update({"keys": list(res.keys())[:6] if isinstance(res, dict) else None})
        elif tool == "firewall.operation_integrity":
            reads[tool].update({"with_warnings": res.get("with_warnings")})
        print(f"{tool:32s} success={ok} err={str(err)[:60] if err else '-'} {json.dumps({k:v for k,v in reads[tool].items() if k not in ('success','error')}, ensure_ascii=False, default=str)[:140]}")
    OUT["read_tools"] = reads

    # missing tool failure mode
    r = await tr.call_tool("nonexistent.tool")
    OUT["missing_tool_behavior"] = r
    print("missing tool →", r)

    # ---------- 4: WRITE PATH (registry check only — no execution) ----------
    section("WRITE PATH (no execution)")
    from core import unified_executor as ux
    OUT["risky_actions"] = sorted(ux.RISKY_ACTIONS)
    OUT["read_only_actions"] = sorted(ux.READ_ONLY_ACTIONS) if hasattr(ux, "READ_ONLY_ACTIONS") else []
    OUT["financial_actions_runtime"] = sorted(action_runtime.FINANCIAL_ACTIONS) if hasattr(action_runtime, "FINANCIAL_ACTIONS") else []
    OUT["four_eyes_enforced"] = action_runtime._enforce_4eyes()
    print("RISKY_ACTIONS:", OUT["risky_actions"])
    print("FINANCIAL_ACTIONS:", OUT["financial_actions_runtime"])
    print("FOUR_EYES:", OUT["four_eyes_enforced"])

    # ---------- 6: pending approvals snapshot (read-only) ----------
    pend = action_runtime.list_approvals(status="pending", limit=100)
    OUT["pending_approvals"] = [{"id": p.get("approval_id") or p.get("id"), "action": (p.get("draft") or {}).get("action") or p.get("action"),
                                 "classification": p.get("source_classification") or (p.get("draft") or {}).get("source_classification")}
                                for p in pend]
    print("pending approvals:", len(pend))

    # ---------- 10: PARITY — panel vs tools ----------
    section("CHAT/TOOL vs PANEL PARITY")
    import httpx
    from core.tool_router import _int_headers
    async with httpx.AsyncClient(timeout=60.0, headers=_int_headers()) as client:
        d = await client.get("http://localhost:8001/api/assistant/dashboard")
        panels = {p["id"]: p.get("value") for p in ((d.json().get("data") or {}).get("panels") or [])}
    OUT["panel_values"] = panels
    OUT["parity"] = {
        "total_ar_tool": reads["finance.ar_summary"].get("total_ar"),
        "total_ar_panel": panels.get("total_ar"),
        "delta": (reads["finance.ar_summary"].get("total_ar") or 0) - (panels.get("total_ar") or 0),
    }
    print("panel:", json.dumps(panels, ensure_ascii=False))
    print("parity AR:", OUT["parity"])

    with open("/app/test_reports/katrina_discovery_raw.json", "w", encoding="utf-8") as f:
        json.dump(OUT, f, ensure_ascii=False, indent=2, default=str)
    print("\nSaved /app/test_reports/katrina_discovery_raw.json")


asyncio.run(main())
