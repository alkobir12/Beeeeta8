from __future__ import annotations

import ast
import asyncio
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

load_dotenv(BACKEND / ".env")

from core import tool_router  # noqa: E402
from core.unified_financial_engine import (  # noqa: E402
    build_current_ar_snapshot,
    is_supplier_item,
    item_amount,
    vehicle_finalization,
)
from financial_reconciliation import (  # noqa: E402
    AR_CODES,
    EXPENSE_CODES,
    REVENUE_CODES,
    journal_lines,
    table_fetch_all,
)
from supabase_service import SupabaseService  # noqa: E402

CENT = Decimal("0.01")
WORKSHOP_ID = os.environ.get("DEFAULT_WORKSHOP_ID") or "finmodule-sync"
OUTPUT_JSON = ROOT / "test_reports" / "financial_consistency_readonly_audit.json"
OUTPUT_MD = ROOT / "memory" / "FINANCIAL_CONSISTENCY_READONLY_AUDIT.md"
HIDDEN_STATUSES = {
    "delivered", "archived", "cancelled", "canceled", "ملغي", "ملغى",
    "مؤرشف", "مسلم", "تم التسليم",
}


def dec(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        return Decimal("0.00")
    try:
        return Decimal(str(value).replace(",", "").strip() or "0").quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def money(value: Any) -> str:
    return f"{dec(value):,.2f}"


def text(value: Any) -> str:
    return str(value or "").strip()


def entry_date(row: Dict[str, Any]) -> str:
    return text(row.get("date") or row.get("created_at"))[:10]


def line_code(line: Dict[str, Any]) -> str:
    return text(line.get("account") or line.get("code") or line.get("account_code"))


def entry_impact(rows: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    out = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        for line in journal_lines(row):
            code = line_code(line)
            debit = dec(line.get("debit"))
            credit = dec(line.get("credit"))
            out["debit"] += debit
            out["credit"] += credit
            if code in AR_CODES:
                out["ar"] += debit - credit
            if code in REVENUE_CODES:
                out["revenue"] += credit - debit
            if code in EXPENSE_CODES:
                out["expenses"] += debit - credit
    return {key: float(value) for key, value in out.items()}


def load_preview_url() -> str:
    value = os.environ.get("AUDIT_BASE_URL")
    if value:
        return value.rstrip("/")
    for line in (ROOT / "frontend" / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("AUDIT_BASE_URL/REACT_APP_BACKEND_URL missing")


class Api:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.session = requests.Session()
        login = self.session.post(
            f"{base_url}/api/auth/login",
            json={"username": username, "password": password},
            timeout=30,
        )
        login.raise_for_status()
        token = (login.json() or {}).get("access_token")
        if not token:
            raise RuntimeError("login returned no access token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def get(self, path: str, params: Dict[str, Any] | None = None, timeout: int = 90) -> Dict[str, Any]:
        response = self.session.get(f"{self.base_url}/api{path}", params=params, timeout=timeout)
        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {"status": response.status_code, "payload": payload}


def api_data(result: Dict[str, Any], fallback: Any = None) -> Any:
    payload = result.get("payload") or {}
    if isinstance(payload, dict):
        return payload.get("data", payload)
    if isinstance(payload, list):
        return payload
    return fallback


def table_counts(client: Any) -> Dict[str, int]:
    return {
        table: len(table_fetch_all(client, table, "id"))
        for table in ("vehicles", "vehicle_visits", "operations", "journal_entries")
    }


def scan_single_writer_contract() -> Dict[str, Any]:
    direct_mutations = []
    post_entry_default_fallback = []
    mutation_rx = re.compile(r"table\([\"']journal_entries[\"']\).*?\.(insert|update|delete|upsert)\(")
    for path in BACKEND.rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel.startswith(("tests/", "scripts/")) or rel == "core/accounting_engine.py":
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(source.splitlines(), 1):
            if mutation_rx.search(line.replace(" ", "")):
                direct_mutations.append({"file": rel, "line": lineno, "code": line.strip()[:220]})
            if "accounting_engine.post_entry(" in line and "fallback=" not in line:
                post_entry_default_fallback.append({"file": rel, "line": lineno, "code": line.strip()[:220]})

    unified_path = BACKEND / "core" / "unified_financial_engine.py"
    tree = ast.parse(unified_path.read_text(encoding="utf-8"))
    end_date_loads = 0
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "build_current_ar_snapshot":
            end_date_loads = sum(
                1 for child in ast.walk(node)
                if isinstance(child, ast.Name) and child.id == "end_date" and isinstance(child.ctx, ast.Load)
            )

    tool_source = (BACKEND / "core" / "tool_router.py").read_text(encoding="utf-8")
    vehicle_ui = (ROOT / "frontend" / "src" / "components" / "VehicleFinancialSummary.jsx").read_text(encoding="utf-8")
    debt_ui = (ROOT / "frontend" / "src" / "pages" / "DebtFollowUp.jsx").read_text(encoding="utf-8")
    journal_ui = (ROOT / "frontend" / "src" / "pages" / "JournalEntries.jsx").read_text(encoding="utf-8")
    dashboard_backend = (BACKEND / "routes_extended.py").read_text(encoding="utf-8")

    return {
        "direct_journal_mutations_outside_engine": direct_mutations,
        "post_entry_calls_using_default_fallback": post_entry_default_fallback,
        "current_ar_end_date_is_effectively_used": end_date_loads > 0,
        "current_ar_end_date_load_count": end_date_loads,
        "katrina_total_ar_uses_stored_balances": '"total_ar": s.get("stored_balances_total")' in tool_source,
        "vehicle_final_default_adds_supplier_archive": "serviceTotal + supplierPreview" in vehicle_ui and "currentFinalTotal" in vehicle_ui,
        "debt_page_can_synthesize_ledger_totals_from_engine": "ledger_ar_total: arTotalFromEngine" in debt_ui,
        "debt_page_can_keep_higher_stale_cache": "hydratedTotal >= currentTotal ? hydratedRows : current" in debt_ui,
        "journal_page_fetch_limit_50": "limit: 50" in journal_ui,
        "dashboard_summaries_use_unified_engine": "vehicle_dashboard_summaries" in dashboard_backend
        and "build_vehicle_summary" in dashboard_backend[dashboard_backend.find("vehicle_dashboard_summaries"):dashboard_backend.find("vehicle_dashboard_summaries") + 4000],
    }


async def katrina_tools() -> Dict[str, Any]:
    ar = await tool_router.call_tool("finance.ar_summary", workshop_id=WORKSHOP_ID)
    journal = await tool_router.call_tool("accounting.journal_entries", workshop_id=WORKSHOP_ID, limit=100)
    return {"ar_summary": ar, "journal_entries": journal}


def main() -> None:
    username = os.environ.get("AUDIT_USERNAME")
    password = os.environ.get("AUDIT_PASSWORD")
    if not username or not password:
        raise RuntimeError("AUDIT_USERNAME and AUDIT_PASSWORD are required")

    now = datetime.now(timezone.utc)
    period_start = os.environ.get("AUDIT_PERIOD_START") or f"{now.year:04d}-{now.month:02d}-01"
    period_end = os.environ.get("AUDIT_PERIOD_END") or now.date().isoformat()
    preview_url = load_preview_url()
    api = Api(preview_url, username, password)

    supa = SupabaseService()
    if supa.mock_mode:
        raise RuntimeError("Audit requires real Supabase data")
    counts_before = table_counts(supa.client)
    vehicles = table_fetch_all(supa.client, "vehicles")
    visits = table_fetch_all(supa.client, "vehicle_visits")
    operations = table_fetch_all(supa.client, "operations")
    journals = table_fetch_all(supa.client, "journal_entries")
    accounts = table_fetch_all(supa.client, "accounts")

    current_journals = [row for row in journals if period_start <= entry_date(row) <= period_end]
    historical_journals = [row for row in journals if entry_date(row) and entry_date(row) < period_start]
    opening_journals = [row for row in journals if text(row.get("source")).lower() in {"financial_reset_opening_receivable", "opening_balance_correction"}]
    archived_journals = [row for row in journals if text(row.get("source")).lower() == "archived_financial_period"]

    snapshot = build_current_ar_snapshot(supa.client, WORKSHOP_ID, end_date=f"{period_end}T23:59:59Z")
    active_vehicle_ids = [text(row.get("vehicle_id")) for row in snapshot.get("vehicles") or [] if text(row.get("vehicle_id"))]
    vehicle_api_rows = []
    for vehicle_id in active_vehicle_ids:
        result = api.get(f"/vehicles/{vehicle_id}/financial-summary")
        row = api_data(result, {}) or {}
        vehicle_api_rows.append({
            "vehicle_id": vehicle_id,
            "status": result["status"],
            "customer_total": float(dec(row.get("customer_total"))),
            "confirmed_paid": float(dec(row.get("confirmed_paid"))),
            "remaining": float(dec(row.get("display_remaining"))),
            "supplier_archive_total": float(dec(row.get("supplier_archive_total"))),
            "engine_version": row.get("engine_version"),
        })

    as_of_today = api.get("/finance/ar/customers", {"workshop_id": WORKSHOP_ID, "as_of": period_end, "include_today": "true"})
    as_of_period_start = api.get("/finance/ar/customers", {"workshop_id": WORKSHOP_ID, "as_of": period_start, "include_today": "true"})
    ar_ledger = api.get("/finance/ar/ledger", {"workshop_id": WORKSHOP_ID, "start_date": period_start, "end_date": period_end})
    ar_layers = api.get("/finance/ar-ledger", {"workshop_id": WORKSHOP_ID})
    operations_api = api.get("/operations", {"limit": 200})
    journal_page = api.get("/finance/journal-entries", {"workshop_id": WORKSHOP_ID, "limit": 50})
    journal_period = api.get("/finance/journal-entries", {"workshop_id": WORKSHOP_ID, "start_date": period_start, "end_date": period_end, "limit": 10000})
    income = api.get("/finance/reports/income-statement", {"workshop_id": WORKSHOP_ID, "start_date": period_start, "end_date": period_end})
    trial = api.get("/finance/reports/trial-balance", {"workshop_id": WORKSHOP_ID, "start_date": period_start, "end_date": period_end})
    balance = api.get("/finance/reports/balance-sheet", {"workshop_id": WORKSHOP_ID, "as_of_date": period_end})
    reconciliation = api.get("/finance/reports/reconciliation", {"workshop_id": WORKSHOP_ID, "start_date": period_start, "end_date": period_end})
    operation_trace = api.get("/finance/reports/operation-trace", {"workshop_id": WORKSHOP_ID, "start_date": period_start, "end_date": period_end})
    assistant_dashboard = api.get("/assistant/dashboard", {"workshop_id": WORKSHOP_ID}, timeout=120)
    katrina = asyncio.run(katrina_tools())

    ar_today_data = api_data(as_of_today, {}) or {}
    ar_start_data = api_data(as_of_period_start, {}) or {}
    ar_ledger_data = api_data(ar_ledger, {}) or {}
    ar_layers_data = api_data(ar_layers, {}) or {}
    income_data = api_data(income, {}) or {}
    trial_data = api_data(trial, {}) or {}
    balance_data = api_data(balance, {}) or {}
    reconciliation_data = api_data(reconciliation, {}) or {}
    operation_trace_data = api_data(operation_trace, {}) or {}
    assistant_data = api_data(assistant_dashboard, {}) or {}

    katrina_ar_result = ((katrina.get("ar_summary") or {}).get("result") or {})
    assistant_ar_panel = next((row for row in assistant_data.get("panels") or [] if row.get("id") == "total_ar"), {})

    trial_accounts = trial_data.get("accounts") or trial_data.get("rows") or []
    trial_debit = sum(dec(row.get("debit") or row.get("total_debit")) for row in trial_accounts)
    trial_credit = sum(dec(row.get("credit") or row.get("total_credit")) for row in trial_accounts)
    balance_totals = balance_data.get("totals") or {}
    assets = dec(balance_totals.get("assets"))
    liabilities_plus_equity = dec(balance_totals.get("liabilities_plus_equity"))
    if liabilities_plus_equity == 0:
        liabilities_plus_equity = dec(balance_totals.get("liabilities")) + dec(balance_totals.get("equity"))

    journal_ids = [text(row.get("id")) for row in journals if text(row.get("id"))]
    duplicate_journal_ids = [key for key, count in Counter(journal_ids).items() if count > 1]
    unbalanced = []
    for row in journals:
        impact = entry_impact([row])
        if dec(impact.get("debit")) != dec(impact.get("credit")):
            unbalanced.append({"id": row.get("id"), "difference": float(dec(impact.get("debit")) - dec(impact.get("credit")))})

    journals_by_ref = defaultdict(list)
    for row in journals:
        journals_by_ref[text(row.get("reference_id"))].append(row)

    finalization_mismatches = []
    finalized_count = 0
    for vehicle in vehicles:
        finalized = vehicle_finalization(vehicle)
        final_total = finalized.get("final_customer_total")
        if final_total is None:
            continue
        finalized_count += 1
        ref = f"vehfinal:{text(vehicle.get('id'))}"
        rows = journals_by_ref.get(ref, [])
        if len(rows) != 1 or (rows and dec(rows[0].get("total")) != dec(final_total)):
            finalization_mismatches.append({
                "vehicle_id": vehicle.get("id"),
                "final_customer_total": float(dec(final_total)),
                "canonical_entries": len(rows),
                "canonical_total": float(sum((dec(row.get("total")) for row in rows), Decimal("0.00"))),
            })

    supplier_only_refs = []
    supplier_policy_violations = []
    for operation in operations:
        items = [item for item in (operation.get("items") or []) if isinstance(item, dict)]
        positive = [item for item in items if dec(item_amount(item)) > 0]
        if not positive or not all(is_supplier_item(item) for item in positive):
            continue
        op_id = text(operation.get("id"))
        supplier_only_refs.append(op_id)
        linked = journals_by_ref.get(op_id, [])
        impact = entry_impact(linked)
        if abs(dec(impact.get("ar"))) > 0 or abs(dec(impact.get("revenue"))) > 0:
            supplier_policy_violations.append({"operation_id": op_id, "impact": impact, "journal_ids": [row.get("id") for row in linked]})

    journal_page_rows = api_data(journal_page, []) or []
    journal_period_rows = api_data(journal_period, []) or []
    operations_rows = api_data(operations_api, []) or []
    income_totals = income_data.get("totals") or {}
    statement_safety = income_data.get("statement_safety") or {}
    revenue_audit = income_data.get("revenue_source_audit") or {}
    recon_summary = reconciliation_data.get("summary") or {}
    trace_summary = operation_trace_data.get("summary") or {}

    vehicle_remaining_total = sum(dec(row.get("remaining")) for row in vehicle_api_rows if row.get("status") == 200)
    ar_today_total = dec(ar_today_data.get("total_ar"))
    ar_ledger_total = dec(ar_ledger_data.get("ending_balance"))
    ar_engine_total = dec(snapshot.get("total_ar"))
    current_impact = entry_impact(current_journals)
    all_impact = entry_impact(journals)
    opening_impact = entry_impact(opening_journals)
    historical_impact = entry_impact(historical_journals)

    checks = {
        "all_journal_entries_balanced": not unbalanced,
        "no_duplicate_journal_ids": not duplicate_journal_ids,
        "vehicle_files_match_current_ar": vehicle_remaining_total == ar_engine_total,
        "ar_customers_matches_engine": ar_today_total == ar_engine_total,
        "ar_ledger_matches_engine": ar_ledger_total == ar_engine_total,
        "ar_layers_current_matches_engine": dec(ar_layers_data.get("current_vehicle_ar_total")) == ar_engine_total,
        "trial_balance_balanced_current_period": trial_debit == trial_credit,
        "balance_sheet_equation_balanced": assets == liabilities_plus_equity,
        "income_statement_has_no_unknown_entries": int(statement_safety.get("unknown_entries_count") or 0) == 0,
        "operations_reconciliation_matched": bool(recon_summary.get("matched")),
        "no_missing_operation_journals": int((recon_summary.get("missing_operation_journals") or {}).get("count") or 0) == 0,
        "canonical_finalizations_unique_and_equal": not finalization_mismatches,
        "supplier_only_operations_do_not_touch_ar_or_revenue": not supplier_policy_violations,
        "katrina_ar_matches_current_ar": dec(katrina_ar_result.get("total_ar")) == ar_engine_total,
        "assistant_dashboard_ar_matches_current_ar": dec(assistant_ar_panel.get("value")) == ar_engine_total,
        "journal_page_contains_full_ledger": len(journal_page_rows) == len(journals),
        "journal_period_endpoint_count_matches_raw": len(journal_period_rows) == len(current_journals),
    }

    production_url = (os.environ.get("AUDIT_PRODUCTION_URL") or "https://car-repair-sys.emergent.host").rstrip("/")
    try:
        production_health = requests.get(f"{production_url}/api/health", timeout=30)
        production_status = {"health_status": production_health.status_code, "data_audit": "not_run_no_production_credentials_or_environment_access"}
    except Exception as error:
        production_status = {"health_status": None, "error": str(error)[:160], "data_audit": "not_run_no_production_credentials_or_environment_access"}

    static_contract = scan_single_writer_contract()
    counts_after = table_counts(supa.client)
    findings = [
        {
            "id": "FIN-P0-01",
            "severity": "P0",
            "title": "كاترينا لا تستخدم رصيد الذمم الحالي",
            "evidence": f"current_ar={money(ar_engine_total)} vs katrina={money(katrina_ar_result.get('total_ar'))}",
            "root_cause": "finance.ar_summary يعرض stored_balances_total في total_ar رغم إعلانه أن journal_entries هو SSOT.",
            "recommendation": "اجعل total_ar/current dashboard من current_vehicle_ar_total، واعرض ledger/history كطبقات مستقلة بأسماء صريحة.",
        },
        {
            "id": "FIN-P0-02",
            "severity": "P0",
            "title": "قيد تاريخي لمشتريات مورد أثّر في ذمم العملاء والإيراد",
            "evidence": f"violations={len(supplier_policy_violations)}; AR/revenue impact={money(sum(dec(v.get('impact', {}).get('ar')) for v in supplier_policy_violations))}",
            "root_cause": "قيد fin_engine_align_v1 قديم صُنّف بيعًا لعملية تحتوي supplier items فقط.",
            "recommendation": "عكس القيد الخاطئ عبر AccountingEngine بعد اعتماد المالك؛ لا تحذفه ولا تعدله مباشرة.",
        },
        {
            "id": "FIN-P0-03",
            "severity": "P0",
            "title": "إجمالي نهائي محفوظ بلا قيد canonical مطابق",
            "evidence": f"mismatches={len(finalization_mismatches)}; details={finalization_mismatches[:3]}",
            "root_cause": "حفظ المركبة يسبق posting؛ عند فشل posting يمكن أن يبقى financial_finalization محفوظًا بلا vehfinal entry.",
            "recommendation": "اجعل الحفظ/posting ذريًا أو أضف outbox/retry idempotent، ثم عالج السجل الحالي بموافقة صريحة.",
        },
        {
            "id": "FIN-P0-04",
            "severity": "P0",
            "title": "عقد الكاتب الواحد غير مطبق بالكامل",
            "evidence": f"direct journal mutations={len(static_contract['direct_journal_mutations_outside_engine'])}; default fallback calls={len(static_contract['post_entry_calls_using_default_fallback'])}",
            "root_cause": "مسارات إصلاح/إقفال قديمة تحدّث journal_entries مباشرة وبعض callers لا تستخدم fallback=False.",
            "recommendation": "مرّر كل mutation عبر AccountingEngine reverse/replace APIs، وأغلق fallback الافتراضي.",
        },
        {
            "id": "FIN-P1-01",
            "severity": "P1",
            "title": "الميزانية العمومية غير متوازنة بمقدار 908",
            "evidence": f"assets={money(assets)}; liabilities+equity={money(liabilities_plus_equity)}; gap={money(assets-liabilities_plus_equity)}",
            "root_cause": "الحساب 006 رصيده دائن 454 لكن balance-sheet يستخدم abs(balance)، فيحوّل -454 إلى +454 ويضاعف الفرق إلى 908.",
            "recommendation": "احتفظ بإشارة الرصيد أو صنّف contra/overdraft صراحة بدل abs().",
        },
        {
            "id": "FIN-P1-02",
            "severity": "P1",
            "title": "تقرير مطابقة العمليات غير متوافق مع نموذج canonical الحالي",
            "evidence": f"difference={money(recon_summary.get('total_absolute_difference'))}; missing={int((recon_summary.get('missing_operation_journals') or {}).get('count') or 0)}",
            "root_cause": "التقرير يتوقع قيدًا لكل operation ويجمع عمليات delivered/قديمة، بينما النموذج الحالي يعتمد قيد vehfinal واحدًا ويستبعد القيود المؤقتة دلاليًا.",
            "recommendation": "أعد بناء reconciliation حول business_event_id/accounting_identity والتصنيف الدلالي، ولا تنفذ backfill الحالي آليًا.",
        },
        {
            "id": "FIN-P1-03",
            "severity": "P1",
            "title": "تاريخ as_of في الذمم غير مطبق فعليًا",
            "evidence": f"period_start={money(ar_start_data.get('total_ar'))}; today={money(ar_today_total)}; end_date load count={static_contract['current_ar_end_date_load_count']}",
            "root_cause": "build_current_ar_snapshot يقبل end_date لكنه لا يستخدمه لتصفية الزيارات أو القيود.",
            "recommendation": "طبّق cutoff موحدًا على visits/payments/journals واختبر نقاطًا تاريخية مختلفة.",
        },
        {
            "id": "FIN-P1-04",
            "severity": "P1",
            "title": "افتراضي اعتماد إجمالي المركبة يضيف مشتريات المورد",
            "evidence": "VehicleFinancialSummary: itemsTotal = serviceTotal + supplierPreview",
            "root_cause": "حقل finalCustomerTotal يبدأ من إجمالي البنود المرئي بدل customer_total/serviceTotal فقط.",
            "recommendation": "اجعل القيمة الافتراضية customer_total فقط مع إبقاء المورد للمعاينة.",
        },
        {
            "id": "FIN-P1-05",
            "severity": "P1",
            "title": "متابعة الذمم تحتوي fallback صامتًا وcache قديمًا",
            "evidence": "عند فشل ar-ledger تُنسخ قيمة engine إلى ledger، وhydrate يبقي القيمة الأعلى حتى لو انخفض الرصيد الحي.",
            "root_cause": "منطق UX يخفي فشل المصدر ويمنع انخفاض الرصيد بعد السداد في بعض السباقات.",
            "recommendation": "اعرض حالة source unavailable صراحة واستبدل cache دائمًا بالبيانات الحية ذات الإصدار الأحدث.",
        },
        {
            "id": "FIN-P1-06",
            "severity": "P1",
            "title": "ملخص لوحة المركبات لا يستخدم المحرك الموحد",
            "evidence": f"dashboard_summaries_use_unified_engine={static_contract['dashboard_summaries_use_unified_engine']}",
            "root_cause": "vehicles/dashboard/summaries يحسب estimatedTotal من notes محليًا.",
            "recommendation": "اجعله يستهلك batch summary من نفس read model المستخدم في ملف المركبة.",
        },
        {
            "id": "FIN-P2-01",
            "severity": "P2",
            "title": "دفتر اليومية سيعرض KPI جزئيًا بعد 50 قيدًا",
            "evidence": f"current rows={len(journals)}; frontend limit=50",
            "root_cause": "KPI يُحسب من safeEntries المحملة فقط وليس total/count server-side.",
            "recommendation": "أضف totals endpoint أو pagination metadata قبل تجاوز 50 قيدًا.",
        },
    ]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "environment": {"preview": preview_url, "production": production_url, "production_status": production_status},
        "period": {"start": period_start, "end": period_end, "opening_and_historical_separated": True},
        "mutation_guard": {"before": counts_before, "after": counts_after, "unchanged": counts_before == counts_after},
        "counts": {
            "vehicles": len(vehicles), "active_vehicle_files": len(active_vehicle_ids), "visits": len(visits),
            "operations": len(operations), "operations_api": len(operations_rows), "journal_entries": len(journals),
            "journal_current_period": len(current_journals), "journal_historical": len(historical_journals),
            "journal_opening": len(opening_journals), "journal_archived": len(archived_journals),
            "accounts": len(accounts), "finalized_vehicles": finalized_count, "supplier_only_operations": len(supplier_only_refs),
        },
        "numbers": {
            "current_ar": {
                "vehicle_file_remaining_total": float(vehicle_remaining_total),
                "unified_engine_total": float(ar_engine_total),
                "ar_customers_total": float(ar_today_total),
                "ar_ledger_ending": float(ar_ledger_total),
                "ar_layers_current": float(dec(ar_layers_data.get("current_vehicle_ar_total"))),
                "ledger_all_entries_ar": float(dec(ar_layers_data.get("ledger_ar_total"))),
                "katrina_tool_total_ar": float(dec(katrina_ar_result.get("total_ar"))),
                "katrina_tool_ledger_ar": float(dec(katrina_ar_result.get("ledger_ar_total"))),
                "assistant_dashboard_total_ar": float(dec(assistant_ar_panel.get("value"))),
                "as_of_period_start_total": float(dec(ar_start_data.get("total_ar"))),
            },
            "current_period": {
                "journal_debit": current_impact.get("debit", 0.0),
                "journal_credit": current_impact.get("credit", 0.0),
                "journal_ar": current_impact.get("ar", 0.0),
                "journal_revenue_raw": current_impact.get("revenue", 0.0),
                "journal_expenses_raw": current_impact.get("expenses", 0.0),
                "income_revenue_canonical": float(dec(income_totals.get("revenue"))),
                "income_expenses": float(dec(income_totals.get("expenses"))),
                "income_net": float(dec(income_totals.get("net_income"))),
                "income_unknown_entries": int(statement_safety.get("unknown_entries_count") or 0),
                "income_excluded_entries": int(statement_safety.get("excluded_entries_count") or 0),
                "income_excluded_legacy_revenue": float(dec(revenue_audit.get("excluded_legacy_revenue"))),
                "operations_reconciliation_difference": float(dec(recon_summary.get("total_absolute_difference"))),
                "missing_operation_journals": recon_summary.get("missing_operation_journals") or {},
                "operation_trace": trace_summary,
            },
            "opening": opening_impact,
            "historical_before_period": historical_impact,
            "all_ledger": all_impact,
            "trial_balance": {"debit": float(trial_debit), "credit": float(trial_credit), "difference": float(trial_debit - trial_credit)},
            "balance_sheet": {"assets": float(assets), "liabilities_plus_equity": float(liabilities_plus_equity), "difference": float(assets - liabilities_plus_equity)},
        },
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "findings": findings,
        "details": {
            "unbalanced_entries": unbalanced,
            "duplicate_journal_ids": duplicate_journal_ids,
            "finalization_mismatches": finalization_mismatches,
            "supplier_policy_violations": supplier_policy_violations,
            "vehicle_api_rows": vehicle_api_rows,
            "reconciliation_rows": reconciliation_data.get("rows") or [],
            "katrina_ar_summary": katrina_ar_result,
        },
        "single_writer_contract": static_contract,
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    render(result)
    print(json.dumps({
        "report": str(OUTPUT_MD), "mutation_guard": result["mutation_guard"],
        "failed_checks": result["failed_checks"], "numbers": result["numbers"]["current_ar"],
    }, ensure_ascii=False, indent=2))


def render(result: Dict[str, Any]) -> None:
    numbers = result["numbers"]
    ar = numbers["current_ar"]
    current = numbers["current_period"]
    static = result["single_writer_contract"]
    lines = [
        "# تدقيق الاتساق المالي الشامل — قراءة فقط",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- الفترة الحالية: `{result['period']['start']}` → `{result['period']['end']}`",
        f"- mutation_guard: **{'PASS' if result['mutation_guard']['unchanged'] else 'FAIL'}**",
        f"- فحوص ناجحة: **{sum(result['checks'].values())}/{len(result['checks'])}**",
        "",
        "## تطابق الذمم الحالية",
        "",
        "| المصدر | الرقم |",
        "|---|---:|",
        f"| ملفات المركبات | {money(ar['vehicle_file_remaining_total'])} |",
        f"| Unified engine | {money(ar['unified_engine_total'])} |",
        f"| متابعة الذمم | {money(ar['ar_customers_total'])} |",
        f"| دفتر الذمم | {money(ar['ar_ledger_ending'])} |",
        f"| طبقات AR — الحالي | {money(ar['ar_layers_current'])} |",
        f"| دفتر القيود — كل التاريخ | {money(ar['ledger_all_entries_ar'])} |",
        f"| كاترينا — finance.ar_summary | {money(ar['katrina_tool_total_ar'])} |",
        f"| كاترينا — ledger_ar_total | {money(ar['katrina_tool_ledger_ar'])} |",
        f"| لوحة كاترينا | {money(ar['assistant_dashboard_total_ar'])} |",
        "",
        "## الفترة الحالية",
        "",
        f"- دفتر اليومية: مدين **{money(current['journal_debit'])}** = دائن **{money(current['journal_credit'])}**.",
        f"- قائمة الدخل canonical: إيراد **{money(current['income_revenue_canonical'])}**، مصروف **{money(current['income_expenses'])}**، صافي **{money(current['income_net'])}**.",
        f"- قيود غير مصنفة: **{current['income_unknown_entries']}**، قيود مستبعدة: **{current['income_excluded_entries']}**.",
        f"- فرق مطابقة العمليات/القيود: **{money(current['operations_reconciliation_difference'])}**.",
        "",
        "## الافتتاحي والتاريخي منفصلان",
        "",
        f"- افتتاحي: AR **{money(numbers['opening'].get('ar'))}**، إيراد **{money(numbers['opening'].get('revenue'))}**.",
        f"- تاريخي قبل الفترة: AR **{money(numbers['historical_before_period'].get('ar'))}**، إيراد **{money(numbers['historical_before_period'].get('revenue'))}**.",
        "",
        "## نتائج الفحوص",
        "",
    ]
    for name, passed in result["checks"].items():
        lines.append(f"- {'✅' if passed else '❌'} `{name}`")
    lines.extend(["", "## سجل التعارضات والأخطاء", ""])
    for finding in result["findings"]:
        lines.extend([
            f"### {finding['id']} — {finding['severity']} — {finding['title']}",
            f"- الدليل: {finding['evidence']}",
            f"- السبب: {finding['root_cause']}",
            f"- التوصية: {finding['recommendation']}",
            "",
        ])
    lines.extend([
        "",
        "## عقد المحرك الواحد — فحص الكود",
        "",
        f"- كتابات مباشرة على journal_entries خارج AccountingEngine: **{len(static['direct_journal_mutations_outside_engine'])}**.",
        f"- استدعاءات post_entry بدون fallback=False: **{len(static['post_entry_calls_using_default_fallback'])}**.",
        f"- end_date مستخدم فعليًا في current AR engine: **{static['current_ar_end_date_is_effectively_used']}**.",
        f"- كاترينا تعرض stored balances بدل current AR: **{static['katrina_total_ar_uses_stored_balances']}**.",
        f"- افتراضي تسعير المركبة يضيف مشتريات المورد: **{static['vehicle_final_default_adds_supplier_archive']}**.",
        f"- متابعة الذمم قد تصنع تطابق ledger fallback: **{static['debt_page_can_synthesize_ledger_totals_from_engine']}**.",
        f"- متابعة الذمم قد تُبقي cache أعلى من الرصيد الحي: **{static['debt_page_can_keep_higher_stale_cache']}**.",
        f"- دفتر اليومية مقيد بـ50 صفًا في الصفحة: **{static['journal_page_fetch_limit_50']}**.",
        f"- dashboard summaries يستخدم unified engine: **{static['dashboard_summaries_use_unified_engine']}**.",
        "",
        "## حدود فحص الإنتاج",
        "",
        f"- health: `{result['environment']['production_status'].get('health_status')}`.",
        "- لم يُنفذ تدقيق بيانات Production لعدم توفر وصول/اعتماد إنتاجي داخل بيئة Preview؛ نتائج الأرقام أعلاه تخص Preview.",
        "",
        f"- JSON: `{OUTPUT_JSON}`",
    ])
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()