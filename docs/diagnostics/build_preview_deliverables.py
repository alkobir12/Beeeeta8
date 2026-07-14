"""Deliverable 2+3 builder — preview table (52→51 after excluding 868355a4) + 7 visits file."""
import json
from datetime import datetime, timedelta

d = json.load(open("/app/docs/diagnostics/CLOSED_VISITS_MISSING_INVOICES.json"))
match = [r for r in d["match"] if r["visit"] != "868355a4"]
excluded = [r for r in d["match"] if r["visit"] == "868355a4"]
anoms = d["anomalies"]

def classify(items):
    buckets = {}
    for i in items:
        t = str(i.get("type") or "").lower()
        cls = "خدمات ورشة" if t == "service" else ("قطع" if t == "part" else "موردون")
        buckets.setdefault(cls, 0.0)
        buckets[cls] += float(i.get("total") or 0)
    return buckets

rows = []
for r in match:
    b = classify(r["items"])
    if len(b) == 1:
        cls = next(iter(b))
        split = f"مسودة واحدة ({cls})"
        n_drafts = 1
    else:
        parts = " + ".join(f"{k} {round(v,2):g}" for k, v in b.items())
        split = f"تقسيم {len(b)} مسودات: {parts}"
        n_drafts = len(b)
    rows.append({
        "visit": r["visit"], "customer": r["customer"].strip(), "plate": r["plate"],
        "closed": r["closed"], "amount": r["items_total"], "items_count": len(r["items"]),
        "classes": b, "proposed_split": split, "proposed_drafts": n_drafts,
    })

rows.sort(key=lambda x: -x["amount"])
today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
last7 = [r for r in rows if r["closed"] and datetime.strptime(r["closed"], "%Y-%m-%d") >= today - timedelta(days=7)]
last14 = [r for r in rows if r["closed"] and datetime.strptime(r["closed"], "%Y-%m-%d") >= today - timedelta(days=14)]

out = {
    "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    "criterion": "زيارات مغلقة: المقبوضات = البنود، صفر قيود فواتير",
    "excluded_permanently": [{"visit": e["visit"], "reason": "سجل اختبار كاترينا بتاريخ مستقبلي — TICKET_TEST_ISOLATION", "amount": e["items_total"]} for e in excluded],
    "visits_count": len(rows),
    "total_amount": round(sum(r["amount"] for r in rows), 2),
    "total_proposed_drafts": sum(r["proposed_drafts"] for r in rows),
    "closed_last_7_days": {"count": len(last7), "amount": round(sum(r["amount"] for r in last7), 2),
                           "visits": [r["visit"] for r in last7]},
    "closed_last_14_days": {"count": len(last14), "amount": round(sum(r["amount"] for r in last14), 2)},
    "split_rule": "افتراضي: مسودة واحدة لكل زيارة؛ تُقسَّم فقط عند تعدد فئات الإيراد (خدمات/قطع/موردون) — نمط يوسف",
    "rows": rows,
}
json.dump(out, open("/app/docs/verification/PREVIEW_SETTLEMENT_51_VISITS.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# markdown table
lines = ["# جدول معاينة التسوية — الزيارات المغلقة بلا فواتير مقابلة",
         f"\n> المعيار: مقبوضات = بنود، صفر قيود فواتير · مستبعَد نهائياً: 868355a4 (اختبار، تذكرة العزل)",
         f"\n**{len(rows)} زيارة · إجمالي {out['total_amount']:g} ر.س · مسودات مقترحة: {out['total_proposed_drafts']}**",
         f"\n**🩸 نزيف حديث: {len(last7)} زيارة أُغلقت خلال آخر 7 أيام ({out['closed_last_7_days']['amount']:g} ر.س) · {len(last14)} خلال 14 يوماً ({out['closed_last_14_days']['amount']:g} ر.س)**\n",
         "| # | الزيارة | العميل | اللوحة | أُغلقت | المبلغ | بنود | التقسيم المقترح |",
         "|---|---------|--------|--------|--------|--------|------|------------------|"]
for i, r in enumerate(rows, 1):
    lines.append(f"| {i} | `{r['visit']}` | {r['customer'][:28]} | {r['plate']} | {r['closed']} | {r['amount']:g} | {r['items_count']} | {r['proposed_split']} |")
open("/app/docs/verification/PREVIEW_SETTLEMENT_51_VISITS.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")

# 7 visits out-of-criterion — same format
out7 = {
    "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    "criterion": "خارج المعيار: قيود الفواتير أقل من البنود لكن المقبوضات ≠ البنود",
    "visits_count": len(anoms),
    "gap_total": round(sum(r["gap"] for r in anoms), 2),
    "note_yousef": "زيارة 29b88c69 (فجوة 6,474) لها 5 مسودات معلّقة بالفعل — VISIT_29b88c69_SETTLEMENT_DRAFTS.json",
    "rows": anoms,
}
json.dump(out7, open("/app/docs/verification/OUT_OF_CRITERION_7_VISITS.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("preview rows:", len(rows), "| total:", out["total_amount"], "| drafts:", out["total_proposed_drafts"])
print("last7:", len(last7), out["closed_last_7_days"]["amount"], "| last14:", len(last14), out["closed_last_14_days"]["amount"])
print("anomalies:", len(anoms), "| gap:", out7["gap_total"])
print("combined gap:", round(out["total_amount"] + out7["gap_total"], 2), "across", len(rows) + len(anoms), "visits")
