"""P0 RED FINDINGS REPAIR — verification (read-only checks + immutability proof)."""
import asyncio
import json
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

import core.tool_router as tr

OUT = {}


async def main():
    # ---------- IMMUTABILITY SNAPSHOT ----------
    from supabase_service import SupabaseService
    sb = SupabaseService().client
    rows = sb.table("journal_entries").select("id,lines").execute().data
    td = sum(float(ln.get("debit") or 0) for r in rows for ln in (r.get("lines") or []))
    ops_count = len(sb.table("operations").select("id").execute().data)
    OUT["immutability"] = {"journal_count": len(rows), "journal_total_debit": round(td, 2), "operations_count": ops_count}
    print("IMMUTABILITY:", OUT["immutability"], "(expected journal=106, debit=177834.06)")

    # ---------- 1: PERMISSION GATE ----------
    print("\n--- PERMISSION GATE (server-side) ---")
    gate = {}
    for tool in ["finance.sales_report", "operations.top_services", "firewall.cash_flow"]:
        r_tech = await tr.call_tool(tool, actor_role="technician")
        r_none = await tr.call_tool(tool)  # no role → fail-closed
        r_admin = await tr.call_tool(tool, actor_role="admin")
        gate[tool] = {
            "technician": r_tech.get("error"),
            "no_role": r_none.get("error"),
            "admin_ok": bool(r_admin.get("success")),
        }
        print(f"{tool:28s} tech={r_tech.get('error')} none={r_none.get('error')} admin_success={r_admin.get('success')}")
    # allowed tools for technician (operational + financial non-revenue)
    for tool, kw in [("finance.ar_summary", {}), ("finance.payables_summary", {}), ("accounting.journal_entries", {"limit": 3}),
                     ("vehicles.status_summary", {}), ("operations.recent", {"limit": 3}), ("customers.search", {"query": "سعد العقيلي"})]:
        r = await tr.call_tool(tool, actor_role="technician", **kw)
        res = r.get("result") or {}
        err = res.get("error") if isinstance(res, dict) else None
        gate[f"tech_allowed:{tool}"] = {"success": r.get("success"), "error": err}
        print(f"tech allowed {tool:28s} success={r.get('success')} err={err}")
    OUT["gate"] = gate

    # sensitivity metadata on all 26
    tools = tr.list_tools()
    OUT["sensitivity_map"] = {t["name"]: t["sensitivity"] for t in tools}
    rev = [t["name"] for t in tools if t["sensitivity"] == "revenue"]
    print("revenue tools:", rev)

    # ---------- 2: SALES_REPORT PAID ----------
    print("\n--- SALES_REPORT PAID ---")
    sr = await tr.call_tool("finance.sales_report", actor_role="admin", query="كل المدة")
    res = sr["result"]
    OUT["sales_report"] = {k: res.get(k) for k in ("period", "count", "total_sales", "paid_amount", "unpaid_amount",
                                                   "paid_count", "partial_count", "unpaid_count", "paid_unknown_count", "paid_source")}
    print(json.dumps(OUT["sales_report"], ensure_ascii=False))
    # cross-check against raw ops
    ops = SupabaseService().operations_list(limit=500)
    sales_ops = [o for o in ops if str(o.get("type") or "").lower() in ("sale", "service")]
    raw_paid = sum(float(o.get("totalPaid") or 0) for o in sales_ops)
    print("raw totalPaid sum over sale/service ops:", round(raw_paid, 2), "| tool paid:", res.get("paid_amount"))
    OUT["sales_report"]["raw_cross_check_paid"] = round(raw_paid, 2)
    # sample paid / partial / unpaid items
    smp = {"paid": None, "partial": None, "unpaid": None}
    for o in sales_ops:
        st = str(o.get("paymentStatus") or "").lower()
        if st in smp and smp[st] is None:
            smp[st] = {"partner": o.get("partnerName"), "total": o.get("total"), "totalPaid": o.get("totalPaid")}
    print("samples:", json.dumps(smp, ensure_ascii=False))
    OUT["sales_report"]["samples"] = smp
    # month report (paid should reflect month ops)
    srm = await tr.call_tool("finance.sales_report", actor_role="admin", query="هذا الشهر")
    OUT["sales_report_month"] = {k: srm["result"].get(k) for k in ("period", "count", "total_sales", "paid_amount", "unpaid_amount")}
    print("month:", json.dumps(OUT["sales_report_month"], ensure_ascii=False))

    # ---------- 3: PAYABLES SSOT ----------
    print("\n--- PAYABLES SSOT ---")
    ap = await tr.call_tool("finance.payables_summary", actor_role="admin")
    apr = ap["result"]
    OUT["payables"] = {k: apr.get(k) for k in ("total_ap", "total_suppliers_with_balance", "ap_source", "top_creditors")}
    print(json.dumps(OUT["payables"], ensure_ascii=False))
    # specific supplier = العوفي (expect 420)
    q1 = await tr.call_tool("finance.payables_summary", actor_role="admin", query="العوفي")
    OUT["payables_awfi"] = q1["result"]
    print("العوفي:", json.dumps(q1["result"], ensure_ascii=False)[:300])
    # supplier with true zero — pick a registry supplier without ledger account
    import httpx
    from core.tool_router import _int_headers
    async with httpx.AsyncClient(timeout=30.0, headers=_int_headers()) as client:
        regs = (await client.get("http://localhost:8001/api/suppliers")).json()
    awfi_like = [s.get("name") for s in regs]
    print("registry suppliers:", awfi_like[:8])
    zero_target = next((n for n in awfi_like if "العوفي" not in str(n)), None)
    if zero_target:
        q2 = await tr.call_tool("finance.payables_summary", actor_role="admin", query=zero_target)
        OUT["payables_true_zero"] = {"supplier": zero_target, "result": q2["result"]}
        print("true-zero supplier:", zero_target, "→", json.dumps(q2["result"], ensure_ascii=False)[:250])
    # unknown supplier
    q3 = await tr.call_tool("finance.payables_summary", actor_role="admin", query="مورد خيالي غير موجود اطلاقا")
    OUT["payables_not_found"] = q3["result"]
    print("unknown:", json.dumps(q3["result"], ensure_ascii=False)[:200])

    # ---------- 4: CHAT/PANEL/CANONICAL PARITY ----------
    print("\n--- PARITY ---")
    async with httpx.AsyncClient(timeout=60.0, headers=_int_headers()) as client:
        d = await client.get("http://localhost:8001/api/assistant/dashboard")
        panels = {p["id"]: p.get("value") for p in ((d.json().get("data") or {}).get("panels") or [])}
    canonical_ap = 420.0  # trial-balance liability account 2101
    OUT["parity"] = {
        "chat_tool_ap": apr.get("total_ap"),
        "panel_ap": panels.get("total_ap"),
        "canonical_ap": canonical_ap,
        "delta_tool": round((apr.get("total_ap") or 0) - canonical_ap, 2),
        "delta_panel": round((panels.get("total_ap") or 0) - canonical_ap, 2),
        "panel_keys": list(panels.keys()),
    }
    print(json.dumps(OUT["parity"], ensure_ascii=False))

    # ---------- IMMUTABILITY AFTER ----------
    rows2 = sb.table("journal_entries").select("id,lines").execute().data
    td2 = sum(float(ln.get("debit") or 0) for r in rows2 for ln in (r.get("lines") or []))
    ops2 = len(sb.table("operations").select("id").execute().data)
    OUT["immutability_after"] = {"journal_count": len(rows2), "journal_total_debit": round(td2, 2), "operations_count": ops2}
    same = OUT["immutability"] == OUT["immutability_after"]
    print("\nIMMUTABILITY AFTER:", OUT["immutability_after"], "| UNCHANGED =", same)

    with open("/app/test_reports/p0_red_findings_repair_verification.json", "w", encoding="utf-8") as f:
        json.dump(OUT, f, ensure_ascii=False, indent=2, default=str)
    print("Saved /app/test_reports/p0_red_findings_repair_verification.json")


asyncio.run(main())
