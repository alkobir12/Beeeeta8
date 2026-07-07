#!/usr/bin/env bash
# 🏆 L14 Unified Regression — تجميدة ما بعد إغلاق L14 (امتحان المالك ناجح 2026-07-07)
# 1) اختبارات الوحدة السريعة (D1..D9 + سيناريوهات كاترينا)
# 2) التشغيلة الحية الكاملة (l14_runner) ضد بنك L14 الستة
# 3) التقييم الآلي ضد Golden Dataset
set -uo pipefail

export REACT_APP_BACKEND_URL="${REACT_APP_BACKEND_URL:-$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)}"
RESULTS=/app/docs/diagnostics/L14_RESULTS.json
ARCHIVE=/app/docs/diagnostics/L14_RESULTS_regression_$(date +%Y%m%d_%H%M%S).json

echo "══════════════════════════════════════════════════"
echo "🏆 L14 Regression — $(date '+%Y-%m-%d %H:%M:%S')"
echo "   Backend: $REACT_APP_BACKEND_URL"
echo "══════════════════════════════════════════════════"

FAIL=0

echo ""
echo "🧪 [1/3] اختبارات الوحدة (pytest)…"
cd /app/backend
python -m pytest tests/test_l14_remediation_iter258.py tests/test_katrina_scenarios_iter257.py -q --no-header 2>&1 | tail -5 || FAIL=1

echo ""
echo "🤖 [2/3] التشغيلة الحية (بنك L14 الستة — ~8 دقائق، تشمل انتظار 60 ثانية لـ S6)…"
# أرشفة نتيجة الشهادة قبل الكتابة فوقها
if [ -f "$RESULTS" ]; then cp "$RESULTS" "$ARCHIVE"; echo "   (أُرشفت النتيجة السابقة → $ARCHIVE)"; fi
python3 /app/docs/diagnostics/l14_runner.py || FAIL=1

echo ""
echo "📏 [3/3] التقييم الآلي ضد Golden Dataset…"
python3 /app/docs/diagnostics/l14_evaluate.py "$RESULTS" || FAIL=1

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "✅✅ L14 REGRESSION PASS — الخط القاعدي سليم"
else
  echo "❌❌ L14 REGRESSION FAIL — راجع المخرجات أعلاه (لا تُعدّل الـ prompt المجمّد بلا أمر مالك)"
fi
exit $FAIL
