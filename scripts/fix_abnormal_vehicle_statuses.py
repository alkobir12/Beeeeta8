from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from financial_reconciliation import table_fetch_all  # noqa: E402
from supabase_service import SupabaseService  # noqa: E402

OUTPUT_JSON = ROOT / "test_reports" / "abnormal_vehicle_status_fix_result.json"
OUTPUT_MD = ROOT / "memory" / "ABNORMAL_VEHICLE_STATUS_FIX_RESULT.md"


def text(value: Any) -> str:
    return str(value or "").strip()


def status_label(value: Any) -> str:
    return text(value) if value is not None else "NULL"


def target_status(value: Any) -> str | None:
    raw = status_label(value)
    if raw in {"NULL", "تشخيص"}:
        return "diagnosis"
    return None


def run(commit: bool) -> Dict[str, Any]:
    supa = SupabaseService()
    before = table_fetch_all(supa.client, "vehicles")
    candidates: List[Dict[str, Any]] = []
    for row in before:
        target = target_status(row.get("status"))
        if target:
            candidates.append({
                "vehicle_id": row.get("id"),
                "customer": row.get("customer_name"),
                "plate": row.get("plate_number"),
                "old_status": status_label(row.get("status")),
                "new_status": target,
            })
    rows = []
    if commit:
        for candidate in candidates:
            supa.client.table("vehicles").update({"status": candidate["new_status"]}).eq("id", candidate["vehicle_id"]).execute()
            rows.append({**candidate, "result": "updated"})
    else:
        rows = [{**candidate, "result": "dry_run"} for candidate in candidates]
    after = table_fetch_all(supa.client, "vehicles")
    archived_rows = [
        {
            "vehicle_id": row.get("id"),
            "customer": row.get("customer_name"),
            "plate": row.get("plate_number"),
            "status": status_label(row.get("status")),
            "note": "حالة أرشيف صحيحة كبيانات، والخطأ كان ظهورها في لوحة التحكم إذا لم تستبعد الواجهة archived.",
        }
        for row in after
        if status_label(row.get("status")) == "archived"
    ]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "COMMIT" if commit else "DRY_RUN",
        "before_status_counts": dict(Counter(status_label(row.get("status")) for row in before)),
        "after_status_counts": dict(Counter(status_label(row.get("status")) for row in after)),
        "updated_count": len([row for row in rows if row["result"] == "updated"]),
        "rows": rows,
        "archived_rows": archived_rows,
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    render(result)
    return result


def render(result: Dict[str, Any]) -> None:
    lines = [
        "# ABNORMAL_VEHICLE_STATUS_FIX_RESULT",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- mode: **{result['mode']}**",
        f"- updated_count: **{result['updated_count']}**",
        f"- before_status_counts: `{result['before_status_counts']}`",
        f"- after_status_counts: `{result['after_status_counts']}`",
        "",
        "## الحالات المصححة",
        "",
        "| العميل | اللوحة | vehicle_id | من | إلى | النتيجة |",
        "|---|---|---|---|---|---|",
    ]
    for row in result["rows"]:
        lines.append(f"| {row['customer']} | {row['plate']} | `{row['vehicle_id']}` | {row['old_status']} | {row['new_status']} | {row['result']} |")
    lines.extend(["", "## مركبات غير طبيعية/تحتاج قراراً", ""])
    if result.get("archived_rows"):
        lines.extend(["| العميل | اللوحة | vehicle_id | الحالة | الملاحظة |", "|---|---|---|---|---|"])
        for row in result["archived_rows"]:
            lines.append(f"| {row['customer']} | {row['plate']} | `{row['vehicle_id']}` | {row['status']} | {row['note']} |")
    else:
        lines.append("- لا توجد مركبات archived متبقية.")
    lines.extend(["", "## ملف JSON", "", f"- `{OUTPUT_JSON}`", ""])
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    result = run(args.commit)
    print(json.dumps({"mode": result["mode"], "updated_count": result["updated_count"], "before": result["before_status_counts"], "after": result["after_status_counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()