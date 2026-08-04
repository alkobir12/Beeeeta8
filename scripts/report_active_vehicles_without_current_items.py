from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSON = ROOT / "test_reports" / "active_vehicles_current_receivables_30_days_read_only.json"
OUTPUT_MD = ROOT / "memory" / "ACTIVE_VEHICLES_WITHOUT_CURRENT_ITEMS_30_DAYS_READ_ONLY.md"
OUTPUT_JSON = ROOT / "test_reports" / "active_vehicles_without_current_items_30_days_read_only.json"


def money(value) -> str:
    return f"{float(value or 0):,.2f}"


def main() -> None:
    data = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    rows = [row for row in data["rows"] if float(row.get("current_items_total") or 0) <= 0]
    rows = sorted(rows, key=lambda row: (row.get("visit_date") or "9999", row.get("customer") or ""))
    total_displayed = sum(float(row.get("displayed_receivable") or 0) for row in rows)
    review_rows = [row for row in rows if float(row.get("displayed_receivable") or 0) > 0 or float(row.get("pending_payments_total") or 0) > 0]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "scope": data.get("scope"),
        "count": len(rows),
        "displayed_receivable_total": total_displayed,
        "manual_review_count": len(review_rows),
        "rows": rows,
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# ACTIVE_VEHICLES_WITHOUT_CURRENT_ITEMS_30_DAYS_READ_ONLY",
        "",
        f"- generated_at: `{result['generated_at']}`",
        "- mode: **READ ONLY** — لم يتم حذف أو إنشاء أو تعديل أي سجل.",
        "- النطاق: المركبات النشطة فقط، من 2026-07-05 إلى 2026-08-04 بتوقيت الرياض.",
        "- التعريف: مركبة نشطة لا تحتوي على خدمات أو قطع/بنود مؤهلة داخل النطاق.",
        "",
        "## النتائج",
        "",
        f"- عدد المركبات النشطة بدون بنود حالية: **{len(rows)}**",
        f"- إجمالي الذمة المعروضة لهذه المركبات: **{money(total_displayed)}**",
        f"- حالات تحتاج مراجعة: **{len(review_rows)}**",
        "",
        "| vehicle_id | العميل | المركبة/اللوحة | visit_id | تاريخ الزيارة | ذمة معروضة حالياً | دفعات معلقة | الحكم |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        vehicle_label = f"{row.get('vehicle') or '—'} / {row.get('plate') or '—'}"
        lines.append(
            f"| `{row.get('vehicle_id')}` | {row.get('customer') or '—'} | {vehicle_label} | `{row.get('visit_id') or '—'}` | {row.get('visit_date') or '—'} | {money(row.get('displayed_receivable'))} | {money(row.get('pending_payments_total'))} | {row.get('final_judgment') or row.get('classification')} |"
        )
    if review_rows:
        lines.extend(["", "## ملاحظات مراجعة", ""])
        for row in review_rows:
            lines.append(f"- `{row.get('vehicle_id')}` / {row.get('customer')}: تظهر ذمة أو دفعة معلقة رغم عدم وجود بنود حالية داخل النطاق.")
    lines.extend(["", "## ملف JSON", "", f"- `{OUTPUT_JSON}`", ""])
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"report": str(OUTPUT_MD), "json": str(OUTPUT_JSON), "count": len(rows), "manual_review_count": len(review_rows), "displayed_receivable_total": total_displayed}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()