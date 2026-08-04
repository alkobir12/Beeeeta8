from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ENV = ROOT / "frontend" / ".env"
OUTPUT_JSON = ROOT / "test_reports" / "financial_system_all_pages_proof.json"
OUTPUT_MD = ROOT / "memory" / "FINANCIAL_SYSTEM_ALL_PAGES_PROOF.md"
READINESS_JSON = ROOT / "test_reports" / "financial_engine_readiness_audit.json"


def read_backend_url() -> str:
    for line in FRONTEND_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL missing")


def money(value: Any) -> str:
    return f"{float(value or 0):,.2f}"


def call(session: requests.Session, method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
    start = time.time()
    response = session.request(method, url, timeout=20, **kwargs)
    elapsed = round(time.time() - start, 2)
    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text[:500]}
    return {"status": response.status_code, "elapsed_seconds": elapsed, "payload": payload}


def pick_vehicle_id(readiness: Dict[str, Any]) -> str:
    rows = readiness.get("rows") or []
    positive = [row for row in rows if float(row.get("file_remaining") or 0) > 0]
    return (positive[0] if positive else rows[0])["vehicle_id"]


def extract_total_ar(result: Dict[str, Any]) -> Optional[float]:
    return (result.get("payload") or {}).get("data", {}).get("total_ar")


def main() -> None:
    backend = read_backend_url()
    base = f"{backend}/api"
    readiness = json.loads(READINESS_JSON.read_text(encoding="utf-8"))
    expected_total = float(readiness["totals"]["vehicle_file_remaining_total"])
    vehicle_id = pick_vehicle_id(readiness)

    session = requests.Session()
    login = call(session, "POST", f"{base}/auth/login", json={"username": "مدير", "pin": "123123"})
    token = login["payload"].get("access_token")
    if not token:
        raise RuntimeError(f"login failed: {login}")
    session.headers.update({"Authorization": f"Bearer {token}"})

    checks = {}
    checks["ar_customers"] = call(session, "GET", f"{base}/finance/ar/customers", params={"workshop_id": "finmodule-sync", "as_of": "2026-08-04", "include_today": "true"})
    checks["ar_ledger"] = call(session, "GET", f"{base}/finance/ar/ledger", params={"workshop_id": "finmodule-sync"})
    checks["ar_layers"] = call(session, "GET", f"{base}/finance/ar-ledger", params={"workshop_id": "finmodule-sync"})
    checks["vehicle_financial_summary"] = call(session, "GET", f"{base}/vehicles/{vehicle_id}/financial-summary")
    checks["dashboard_summaries"] = call(session, "POST", f"{base}/vehicles/dashboard/summaries", json={"vehicle_ids": [vehicle_id]})
    checks["operations"] = call(session, "GET", f"{base}/operations", params={"limit": 200})
    checks["journal_entries"] = call(session, "GET", f"{base}/finance/journal-entries", params={"workshop_id": "finmodule-sync", "limit": 100})
    checks["customers"] = call(session, "GET", f"{base}/customers")

    ar_customers_total = checks["ar_customers"]["payload"].get("data", {}).get("total_ar")
    ar_ledger_ending = checks["ar_ledger"]["payload"].get("data", {}).get("ending_balance")
    ar_layers_current = checks["ar_layers"]["payload"].get("data", {}).get("current_vehicle_ar_total")
    vehicle_summary = checks["vehicle_financial_summary"]["payload"]
    vehicle_remaining = vehicle_summary.get("display_remaining") or vehicle_summary.get("balance")

    pass_conditions = {
        "login_ok": login["status"] == 200,
        "readiness_zero_mismatch": readiness.get("mismatch_count") == 0 and readiness.get("abnormal_status_count") == 0,
        "ar_customers_matches_file": round(float(ar_customers_total or 0), 2) == round(expected_total, 2),
        "ar_ledger_matches_file": round(float(ar_ledger_ending or 0), 2) == round(expected_total, 2),
        "ar_layers_current_matches_file": round(float(ar_layers_current or 0), 2) == round(expected_total, 2),
        "vehicle_summary_ok": checks["vehicle_financial_summary"]["status"] == 200 and float(vehicle_remaining or 0) >= 0,
        "dashboard_summaries_ok": checks["dashboard_summaries"]["status"] == 200,
        "operations_ok": checks["operations"]["status"] == 200,
        "journal_entries_ok": checks["journal_entries"]["status"] == 200,
        "customers_ok": checks["customers"]["status"] == 200,
    }

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend": backend,
        "sample_vehicle_id": vehicle_id,
        "expected_total": expected_total,
        "readiness_totals": readiness.get("totals"),
        "readiness_counts": readiness.get("counts"),
        "checks_summary": {
            "ar_customers_total": ar_customers_total,
            "ar_ledger_ending": ar_ledger_ending,
            "ar_layers_current": ar_layers_current,
            "vehicle_remaining_sample": vehicle_remaining,
        },
        "pass_conditions": pass_conditions,
        "overall_pass": all(pass_conditions.values()),
        "checks": checks,
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    render(result)
    print(json.dumps({"report": str(OUTPUT_MD), "overall_pass": result["overall_pass"], "pass_conditions": pass_conditions, "checks_summary": result["checks_summary"]}, ensure_ascii=False, indent=2))


def render(result: Dict[str, Any]) -> None:
    summary = result["checks_summary"]
    checks = result["checks"]
    lines = [
        "# FINANCIAL_SYSTEM_ALL_PAGES_PROOF",
        "",
        f"- generated_at: `{result['generated_at']}`",
        "- mode: إثبات قراءة/تحقق — لا يعدّل البيانات.",
        f"- overall_pass: **{result['overall_pass']}**",
        "",
        "## 1) إثبات تطابق الأرقام الأساسية",
        "",
        "| المصدر | الرقم | الحالة |",
        "|---|---:|---|",
        f"| ملف المركبة / المحرك الموحد | {money(result['expected_total'])} | مرجع المقارنة |",
        f"| متابعة الذمم AR Customers | {money(summary['ar_customers_total'])} | {'مطابق' if result['pass_conditions']['ar_customers_matches_file'] else 'غير مطابق'} |",
        f"| دفتر الذمم AR Ledger | {money(summary['ar_ledger_ending'])} | {'مطابق' if result['pass_conditions']['ar_ledger_matches_file'] else 'غير مطابق'} |",
        f"| طبقة المحرك المالي الحالية | {money(summary['ar_layers_current'])} | {'مطابق' if result['pass_conditions']['ar_layers_current_matches_file'] else 'غير مطابق'} |",
        "",
        "## 2) حالة الصفحات/المصادر المالية",
        "",
        "| الصفحة | Endpoint مثبت | HTTP | الزمن | الدليل |",
        "|---|---|---:|---:|---|",
        f"| متابعة الذمم والتحصيل | `/finance/ar/customers` | {checks['ar_customers']['status']} | {checks['ar_customers']['elapsed_seconds']}s | total_ar={money(summary['ar_customers_total'])} |",
        f"| دفتر الذمم | `/finance/ar/ledger` | {checks['ar_ledger']['status']} | {checks['ar_ledger']['elapsed_seconds']}s | ending={money(summary['ar_ledger_ending'])} |",
        f"| ملف المركبة | `/vehicles/{{id}}/financial-summary` | {checks['vehicle_financial_summary']['status']} | {checks['vehicle_financial_summary']['elapsed_seconds']}s | remaining={money(summary['vehicle_remaining_sample'])} |",
        f"| لوحة التحكم | `/vehicles/dashboard/summaries` | {checks['dashboard_summaries']['status']} | {checks['dashboard_summaries']['elapsed_seconds']}s | sample vehicle OK |",
        f"| العمليات | `/operations` | {checks['operations']['status']} | {checks['operations']['elapsed_seconds']}s | list OK |",
        f"| دفتر اليومية | `/finance/journal-entries` | {checks['journal_entries']['status']} | {checks['journal_entries']['elapsed_seconds']}s | journal list OK |",
        f"| صفحة العميل | `/customers` | {checks['customers']['status']} | {checks['customers']['elapsed_seconds']}s | customer list OK |",
        f"| شريط طبقات المحرك | `/finance/ar-ledger` | {checks['ar_layers']['status']} | {checks['ar_layers']['elapsed_seconds']}s | current={money(summary['ar_layers_current'])} |",
        "",
        "## 3) شروط النجاح",
        "",
    ]
    for key, passed in result["pass_conditions"].items():
        lines.append(f"- {'✅' if passed else '❌'} `{key}`")
    lines.extend([
        "",
        "## 4) ملفات الإثبات",
        "",
        "- `/app/memory/FINANCIAL_ENGINE_READINESS_AUDIT.md`",
        f"- `{OUTPUT_JSON}`",
        "",
    ])
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()