"""Iter341: Income Statement revenue source safety filtering."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from routes_finance import classify_journal_entry_for_income_statement


def _classify(entry, revenue=0.0, expense=0.0, ar=0.0):
    return classify_journal_entry_for_income_statement(
        entry,
        {"revenue": revenue, "expense": expense, "ar": ar, "lines": []},
    )


def test_income_statement_excludes_legacy_alignment_and_repairs():
    assert _classify({"source": "fin_engine_align_v1", "description": "محاذاة"}, revenue=3181) == "LEGACY_ALIGNMENT"
    assert _classify({"source": "active_vehicle_ar_repair", "description": "إصلاح روابط"}, revenue=500) == "HISTORICAL_REPAIR"
    assert _classify({"source": "hist_vehicle_ar_repair", "description": "استرجاع تاريخي"}, revenue=150) == "HISTORICAL_REPAIR"


def test_income_statement_excludes_temporary_operation_postings():
    entry = {"source": "operation", "transaction_type": "sale", "description": "[قيد مؤقت — بيع آجل] عملية من الزيارة 2635ecf1"}
    assert _classify(entry, revenue=2300, ar=2300) == "TEMPORARY"


def test_income_statement_accepts_only_clear_canonical_business_and_expense_entries():
    assert _classify({"source": "operation", "transaction_type": "sale", "description": "عملية نهائية"}, revenue=2300) == "CANONICAL_BUSINESS"
    assert _classify({"source": "operation", "transaction_type": "purchase", "description": "شراء ديزل"}, expense=104) == "EXPENSE"
    assert _classify({"source": "ajel_supplier_purchase", "transaction_type": "purchase"}, expense=420) == "EXPENSE"


def test_income_statement_classifies_payment_closing_migration_and_unknown():
    assert _classify({"source": "operation_payment", "transaction_type": "payment"}, ar=-300) == "PAYMENT"
    assert _classify({"source": "period_close", "description": "إقفال الفترة"}, revenue=-1000, expense=-50) == "CLOSING"
    assert _classify({"source": "opening_balance", "reference_id": "opening-1"}, revenue=100) == "MIGRATION"
    assert _classify({"source": "manual_adjustment", "description": "تعديل يدوي"}, revenue=100) == "UNKNOWN"


def test_income_statement_endpoint_does_not_use_live_vehicle_filter():
    src = Path("/app/backend/routes_finance.py").read_text(encoding="utf-8")
    start = src.index('@router.get("/reports/income-statement")')
    end = src.index('@router.get("/reports/cash-flow")', start)
    fn = src[start:end]
    assert "_filter_live_journal_entries" not in fn
    assert '"vehicle_status_affects_income_statement": False' in fn
