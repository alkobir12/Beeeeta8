"""L14 Evaluator — يقارن L14_RESULTS.json مع L14_GOLDEN_DATASET.json (pass/fail آلي).

الاستخدام: python3 l14_evaluate.py [results_path]
Exit code 0 = 6/6 نجاح، 1 = رسوب أي سيناريو.
"""
from __future__ import annotations

import json
import re
import sys

HERE = "/app/docs/diagnostics"
RESULTS = sys.argv[1] if len(sys.argv) > 1 else f"{HERE}/L14_RESULTS.json"
GOLDEN = f"{HERE}/L14_GOLDEN_DATASET.json"

FIN_THRESHOLD = 100.0


def numbers_in(text: str):
    vals = set()
    for s in re.findall(r"[0-9][0-9,]*(?:\.[0-9]+)?", text or ""):
        try:
            vals.add(float(s.replace(",", "")))
        except ValueError:
            pass
    return vals


def main() -> int:
    results = json.load(open(RESULTS, encoding="utf-8"))
    golden = json.load(open(GOLDEN, encoding="utf-8"))
    scenarios = results.get("scenarios") or {}
    failures = []
    checks = 0

    def fail(sc, msg):
        failures.append(f"{sc}: {msg}")

    for sc, spec in golden["scenarios"].items():
        turns = scenarios.get(sc)
        if not isinstance(turns, list):
            fail(sc, "لا توجد نتائج للسيناريو")
            continue
        by_n = {t.get("turn"): t for t in turns}
        for n_str, tspec in spec.get("turns", {}).items():
            n = int(n_str)
            rec = by_n.get(n)
            if not rec:
                fail(sc, f"T{n} مفقودة من النتائج")
                continue
            if not rec.get("trace_id"):
                fail(sc, f"T{n} بلا trace_id — النتيجة مرفوضة (قاعدة حاكمة)")
            reply = rec.get("reply") or ""
            tools = [x.get("tool") for x in (rec.get("tools_executed") or [])]
            for tool in tspec.get("expected_tools_any", []):
                checks += 1
                if tool not in tools:
                    fail(sc, f"T{n}: الأداة المتوقعة {tool} لم تُنفَّذ (نُفِّذ: {tools})")
            for phrase in tspec.get("forbidden_phrases", []):
                checks += 1
                if phrase in reply:
                    fail(sc, f"T{n}: عبارة محظورة ظهرت: «{phrase}»")
            req_any = tspec.get("required_phrases_any", [])
            if req_any:
                checks += 1
                if not any(p in reply for p in req_any):
                    fail(sc, f"T{n}: لا توجد أي عبارة مطلوبة من {req_any}")
            num_any = tspec.get("required_numbers_any", [])
            if num_any:
                checks += 1
                if not any(x in reply for x in num_any):
                    fail(sc, f"T{n}: الرقم المطلوب غائب {num_any}")

    # S3 cross-check: الرقم المسؤول عنه ظهر فعلاً في رد T1
    figure = str(scenarios.get("S3_figure_asked") or "")
    s3 = scenarios.get("S3") or []
    if figure and s3:
        checks += 1
        t1_reply = next((t.get("reply") or "" for t in s3 if t.get("turn") == 1), "")
        if figure not in t1_reply:
            fail("S3", f"الرقم المسؤول عنه ({figure}) غير موجود في رد T1")

    # S6 cross-check: ثبات الأرقام المالية بين الدورتين
    s6 = scenarios.get("S6") or []
    if len(s6) >= 2:
        checks += 1
        n1 = {v for v in numbers_in(s6[0].get("reply") or "") if v >= FIN_THRESHOLD}
        n2 = {v for v in numbers_in(s6[1].get("reply") or "") if v >= FIN_THRESHOLD}
        if n1 != n2:
            fail("S6", f"الأرقام المالية غير ثابتة: T1={sorted(n1)} vs T2={sorted(n2)}")

    print("=" * 60)
    print(f"L14 Evaluation — {RESULTS}")
    print(f"فحوصات: {checks} | إخفاقات: {len(failures)}")
    if failures:
        for f_msg in failures:
            print(f"  ❌ {f_msg}")
        print("النتيجة: ❌ رسوب L14 — راجع الإخفاقات أعلاه")
        return 1
    print("النتيجة: ✅ L14 PASS — كل السيناريوهات مطابقة للـ Golden Dataset")
    return 0


if __name__ == "__main__":
    sys.exit(main())
