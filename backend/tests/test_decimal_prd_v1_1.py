"""حزمة الاختبارات الإلزامية — PRD Decimal Accounting Validation v1.1

التشغيل: cd /app/backend && python3 -m pytest tests/test_decimal_prd_v1_1.py -v
كل اختبارات post() تعمل على محرك مرقّع (بلا كتابة حقيقية للدفتر).
Hash Regression: بصمات قيود حقيقية من دفتر الأستاذ مثبتة كثوابت — أي تغيير
في خوارزمية tx_hash يكسر هذه الاختبارات فوراً (PRD §9).
"""
import time
import random
from decimal import Decimal

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from core.accounting_engine import (  # noqa: E402
    CENT, MAX_AMOUNT, AccountingEngine, _dec, _line_amount, _normalize_lines,
)
from core import vat_policy  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# fixture: محرك بلا IO حقيقي (identity بالذاكرة + إدراج مُلتقط)
# ─────────────────────────────────────────────────────────────────────────────

class MemIdentity:
    def __init__(self):
        self.seen = {}

    def claim(self, tx_hash, meta):
        if tx_hash in self.seen:
            return {"claimed": False, "existing": self.seen[tx_hash]}
        self.seen[tx_hash] = {"journal_id": None, **(meta or {})}
        return {"claimed": True}

    def mark_posted(self, tx_hash, journal_id):
        self.seen[tx_hash]["journal_id"] = journal_id

    def release(self, tx_hash):
        self.seen.pop(tx_hash, None)


@pytest.fixture
def engine(monkeypatch):
    eng = AccountingEngine.__new__(AccountingEngine)
    eng.identity = MemIdentity()
    eng.inserted = []

    def fake_insert(payload):
        eng.inserted.append(payload)
        return [payload]

    monkeypatch.setattr(eng, "_insert_adaptive", fake_insert)
    monkeypatch.setattr(eng, "_audit", lambda *a, **k: None)
    return eng


def _bal(amount, acc_d="005", acc_c="026"):
    return [
        {"account": acc_d, "debit": amount, "credit": 0},
        {"account": acc_c, "debit": 0, "credit": amount},
    ]


# ═════════════════════════════════════════════════════════════════════════════
# A) Decimal Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestDecimalPrecision:
    def test_float_artifact_eliminated(self):
        assert _dec(0.1) + _dec(0.2) == Decimal("0.30")

    def test_ten_dimes_equal_one(self):
        total = sum((_dec("0.10") for _ in range(10)), Decimal("0.00"))
        assert total == Decimal("1.00")

    def test_rounding_half_up(self):
        assert _dec("1.005") == Decimal("1.01")   # ROUND_HALF_UP
        assert _dec("1.004") == Decimal("1.00")
        assert _dec("1.5075") == Decimal("1.51")

    def test_quantized_to_cent(self):
        assert _dec(1006.25).as_tuple().exponent == -2


class TestDecimalParsing:
    @pytest.mark.parametrize("raw,expected", [
        ("1,006.25", Decimal("1006.25")),
        ("500", Decimal("500.00")),
        (500, Decimal("500.00")),
        (500.0, Decimal("500.00")),
        (Decimal("500"), Decimal("500.00")),
        ("  2500.5 ", Decimal("2500.50")),
    ])
    def test_valid_inputs(self, raw, expected):
        assert _dec(raw) == expected


class TestDecimalValidation:
    """Rule 6/7 — رفض صريح للقيم التالفة، لا صفر صامت، الرسالة تتضمن القيمة."""

    @pytest.mark.parametrize("bad", [
        "abc", None, True, False, "", "  ",
        float("nan"), float("inf"), float("-inf"),
        "NaN", "Infinity", "-Infinity", "undefined", "null",
    ])
    def test_corrupt_values_rejected(self, bad):
        with pytest.raises(ValueError) as e:
            _dec(bad)
        assert "Invalid monetary value" in str(e.value)

    def test_error_message_contains_value(self):
        with pytest.raises(ValueError, match="abc"):
            _dec("abc")

    def test_missing_side_is_structural_zero(self):
        # جانب مفقود في بند ثنائي العمود = صفر بنيوي (ليس تحويلاً صامتاً)
        assert _line_amount(None) == Decimal("0.00")
        assert _line_amount("") == Decimal("0.00")
        with pytest.raises(ValueError):
            _line_amount("abc")

    def test_post_rejects_corrupt_line(self, engine):
        res = engine.post(lines=[
            {"account": "005", "debit": "abc", "credit": 0},
            {"account": "026", "debit": 0, "credit": 100},
        ])
        assert res["posted"] is False
        assert res["error"] == "invalid_value"
        assert "abc" in res["detail"]


class TestStrictBalance:
    """Rule 5 — توازن صارم بلا أي سماحية."""

    def test_one_halala_imbalance_rejected(self, engine):
        res = engine.post(lines=[
            {"account": "005", "debit": "100.00", "credit": 0},
            {"account": "026", "debit": 0, "credit": "99.99"},
        ])
        assert res["posted"] is False
        assert res["error"] == "unbalanced"

    def test_exact_balance_accepted(self, engine):
        res = engine.post(lines=_bal("1006.25"), description="متوازن")
        assert res["posted"] is True
        assert res["debit"] == res["credit"] == 1006.25

    def test_old_tolerance_no_longer_accepted(self, engine):
        # القديم كان يقبل فرق 0.01 — الآن يُرفض
        res = engine.post(lines=[
            {"account": "005", "debit": "500.00", "credit": 0},
            {"account": "026", "debit": 0, "credit": "500.01"},
        ])
        assert res["posted"] is False


class TestHashRegression:
    """PRD §9 — بصمات قيود حقيقية من دفتر الأستاذ العام (مثبتة 2026-07-02).

    أي تعديل يغيّر خوارزمية tx_hash أو تمثيل الأرقام داخلها يكسر هذه الاختبارات.
    """

    REAL_ENTRIES = [
        {  # قيد آجل 300 — 2026-06-17
            "date": "2026-06-17", "total": 300.0,
            "reference_id": "2a7ff792-4f4f-4c7a-aa8f-d752304efd82",
            "lines": [{"account": "005", "debit": 300.0, "credit": 0.0},
                      {"account": "026", "debit": 0.0, "credit": 300.0}],
            "hash": "8fe57941223f44e9b4b27c403e689fc852f0ace6d9d7ee1ab56478006a7ec94c",
        },
        {  # قيد آجل 4500 — 2026-06-29
            "date": "2026-06-29", "total": 4500.0,
            "reference_id": "15b9dfb5-0366-41cd-bc0a-4b024ff301b0",
            "lines": [{"account": "005", "debit": 4500.0, "credit": 0.0},
                      {"account": "027", "debit": 0.0, "credit": 4500.0}],
            "hash": "8cd62a03ac7c9f2cd60dbbf3a661377c6a5fcf5efd1f507e1d38b27eea7c7d2e",
        },
        {  # INV001214 قيد 2500 — 2026-07-01
            "date": "2026-07-01", "total": 2500.0,
            "reference_id": "33e1066e-0a1e-46e3-870a-bcb2e3b62059",
            "lines": [{"account": "005", "debit": 2500.0, "credit": 0.0},
                      {"account": "027", "debit": 0.0, "credit": 2500.0}],
            "hash": "18b1636bfdf4d5c2b732dd6dafc585eb053bb02fb280ebbe309f2809eb289ebc",
        },
        {  # قيد 150 — 2026-07-01
            "date": "2026-07-01", "total": 150.0,
            "reference_id": "ca32e1a6-a0d5-46f0-b2c0-ede7439c1da0",
            "lines": [{"account": "005", "debit": 150.0, "credit": 0.0},
                      {"account": "026", "debit": 0.0, "credit": 150.0}],
            "hash": "3befcca73915b056aab5907ae76c1526e4afac3a24da21b6f8901d901a55d042",
        },
    ]

    def test_real_fingerprints_stable(self, engine):
        for e in self.REAL_ENTRIES:
            h = engine.compute_tx_hash(
                party="", date=e["date"], lines=e["lines"],
                total=e["total"], reference_id=e["reference_id"])
            assert h == e["hash"], f"Hash regression! ref={e['reference_id']}"

    def test_hash_input_representation_stable_across_types(self, engine):
        """float و str و Decimal لنفس القيمة يجب أن تنتج نفس البصمة (عبر _norm_amount)."""
        base = dict(party="عميل", date="2026-07-02T10:00", reference_id="x-1")
        h_float = engine.compute_tx_hash(
            lines=[{"account": "005", "debit": 500.0, "credit": 0.0}], total=500.0, **base)
        h_str = engine.compute_tx_hash(
            lines=[{"account": "005", "debit": "500", "credit": "0"}], total="500", **base)
        h_dec = engine.compute_tx_hash(
            lines=[{"account": "005", "debit": Decimal("500.00"), "credit": Decimal("0.00")}],
            total=Decimal("500.00"), **base)
        assert h_float == h_str == h_dec


# ═════════════════════════════════════════════════════════════════════════════
# B) Workshop Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestMixedInvoice:
    def test_parts_services_discount_invoice(self, engine):
        # قطع 450.75 + خدمة 875.50 − خصم 100.25 = صافي 1226.00
        res = engine.post(lines=[
            {"account": "005", "debit": "1226.00", "credit": 0},   # ذمم (الصافي)
            {"account": "048", "debit": "100.25", "credit": 0},    # خصم مسموح به
            {"account": "025", "debit": 0, "credit": "450.75"},    # إيرادات قطع
            {"account": "026", "debit": 0, "credit": "875.50"},    # إيرادات خدمات
        ], description="فاتورة مختلطة")
        assert res["posted"] is True
        stored = engine.inserted[0]
        assert stored["total"] == 1326.25            # إجمالي المدين (ذمم + خصم)
        for ln in stored["lines"]:
            assert isinstance(ln["debit"], float) and isinstance(ln["credit"], float)
            assert round(ln["debit"], 2) == ln["debit"]  # مُكمّم للهللة


class TestVatRoundingSettlement:
    def test_distribution_produces_settlement_diff(self):
        r = vat_policy.distribute_vat(["10.05", "10.05", "10.05"])
        assert r["per_line"] == [Decimal("1.51")] * 3
        assert r["vat_total"] == Decimal("4.52")     # 30.15 × 15% = 4.5225 → 4.52
        assert r["settlement"] == Decimal("0.01")    # التحليلي 4.53 > الرسمي 4.52

    def test_single_settlement_line_to_configured_account(self):
        r = vat_policy.distribute_vat(["10.05", "10.05", "10.05"])
        line = vat_policy.build_settlement_line(r["settlement"], n_lines=3)
        assert line is not None
        assert line["account"] == "179"              # الحساب المعتمد من admin
        assert line["account_name"] == "فروق تقريب ضريبية"
        assert line["debit"] == Decimal("0.01") and line["credit"] == 0

    def test_no_settlement_when_exact(self):
        r = vat_policy.distribute_vat(["100.00", "200.00"])
        assert r["settlement"] == Decimal("0.00")
        assert vat_policy.build_settlement_line(r["settlement"], 2) is None

    def test_settlement_cap_rejects_calc_errors(self):
        with pytest.raises(ValueError, match="exceeds rounding cap"):
            vat_policy.build_settlement_line("5.00", n_lines=3)

    def test_balanced_entry_with_settlement_line(self, engine):
        r = vat_policy.distribute_vat(["10.05", "10.05", "10.05"])
        lines = [{"account": "005", "debit": r["total_base"] + r["vat_total"], "credit": 0},
                 {"account": "026", "debit": 0, "credit": r["total_base"]}]
        lines += [{"account": "030", "debit": 0, "credit": v} for v in r["per_line"]]
        st = vat_policy.build_settlement_line(r["settlement"], 3)
        lines.append(st)
        res = engine.post(lines=lines, description="فاتورة VAT + بند تسوية")
        assert res["posted"] is True                 # التوازن الصارم تحقق ببند التسوية


class TestDiscountBeforeVat:
    def test_prd_example_1000_minus_12_5_percent(self):
        subtotal = _dec("1000.00")
        discount = (subtotal * Decimal("0.125")).quantize(CENT)
        net = subtotal - discount
        vat = (net * vat_policy.VAT_RATE).quantize(CENT)
        total = net + vat
        assert discount == Decimal("125.00")
        assert net == Decimal("875.00")
        assert vat == Decimal("131.25")
        assert total == Decimal("1006.25")           # مثال الوثيقة §6 حرفياً


class TestReverseEntry:
    def test_reverse_swaps_all_lines_and_new_hash(self, engine, monkeypatch):
        res1 = engine.post(lines=_bal("2500.00"), description="أصل",
                           reference_id="op-rev-1", party="عميل")
        assert res1["posted"] is True
        original = dict(engine.inserted[0])
        monkeypatch.setattr(engine, "_fetch_originals", lambda **k: [original])
        monkeypatch.setattr(engine, "_reversal_exists", lambda oid: False)
        rev = engine.reverse(journal_id=original["id"], reason="خطأ إدخال",
                             actor={"user_id": "مدير"})
        assert rev["reversed"] is True
        entry = rev["entries"][0]
        assert entry["tx_hash"] != res1["tx_hash"]   # بصمة جديدة (PRD §7/§9)
        stored_rev = engine.inserted[1]
        assert stored_rev["lines"][0]["credit"] == 2500.0   # مدين↔دائن
        assert stored_rev["lines"][1]["debit"] == 2500.0
        assert stored_rev["reversed_of"] == original["id"]  # المرجع
        assert stored_rev["original_date"] == original["date"]  # التاريخ المرجعي
        assert stored_rev["reversal_reason"] == "خطأ إدخال"     # السبب

    def test_reversal_not_negative(self, engine, monkeypatch):
        engine.post(lines=_bal("100.00"), reference_id="op-rev-2")
        original = dict(engine.inserted[0])
        monkeypatch.setattr(engine, "_fetch_originals", lambda **k: [original])
        monkeypatch.setattr(engine, "_reversal_exists", lambda oid: False)
        rev = engine.reverse(journal_id=original["id"])
        for ln in engine.inserted[1]["lines"]:
            assert ln["debit"] >= 0 and ln["credit"] >= 0


class TestPartialPayment:
    def test_balance_decimal_exact(self):
        invoice = _dec("1006.25")
        payments = [_dec("500.00"), _dec("506.25")]
        remaining = invoice - sum(payments, Decimal("0.00"))
        assert remaining == Decimal("0.00")          # لا فرق تقريب إطلاقاً

    def test_uneven_partials(self):
        invoice = _dec("100.00")
        payments = [_dec("33.33"), _dec("33.33"), _dec("33.34")]
        assert invoice - sum(payments, Decimal("0.00")) == Decimal("0.00")


# ═════════════════════════════════════════════════════════════════════════════
# C) Security Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestSecurity:
    def test_duplicate_posting_idempotent(self, engine):
        kw = dict(lines=_bal("300.00"), date="2026-07-02T10:00",
                  reference_id="dup-1", party="عميل")
        r1 = engine.post(**kw)
        r2 = engine.post(**kw)
        assert r1["posted"] is True
        assert r2["posted"] is False and r2["idempotent"] is True
        assert len(engine.inserted) == 1             # قيد واحد فقط في الدفتر

    def test_negative_amount_rejected(self, engine):
        res = engine.post(lines=[
            {"account": "005", "debit": "-100.00", "credit": 0},
            {"account": "026", "debit": 0, "credit": "-100.00"},
        ])
        assert res["posted"] is False
        assert res["error"] == "negative_amount"
        assert "Negative posting amounts are not allowed" in res["detail"]

    def test_zero_posting_rejected(self, engine):
        res = engine.post(lines=[
            {"account": "005", "debit": 0, "credit": 0},
            {"account": "026", "debit": "100", "credit": 0},
            {"account": "027", "debit": 0, "credit": "100"},
        ])
        assert res["posted"] is False
        assert res["error"] == "zero_posting"
        assert "Zero posting amount is not allowed" in res["detail"]

    def test_memo_zero_line_allowed(self, engine):
        res = engine.post(lines=[
            {"account": "005", "debit": "100", "credit": 0},
            {"account": "026", "debit": 0, "credit": "100"},
            {"account": "", "debit": 0, "credit": 0, "is_memo": True,
             "description": "ملاحظة توضيحية"},
        ])
        assert res["posted"] is True
        assert res["debit"] == 100.0                 # Memo لا يدخل الترحيل

    def test_memo_only_entry_rejected(self, engine):
        res = engine.post(lines=[{"account": "", "debit": 0, "credit": 0, "is_memo": True}])
        assert res["posted"] is False

    def test_large_amount_within_range(self, engine):
        res = engine.post(lines=_bal("9999999.99"))
        assert res["posted"] is True

    def test_amount_beyond_range_rejected(self, engine):
        res = engine.post(lines=_bal("10000000.00"))
        assert res["posted"] is False
        assert res["error"] == "amount_out_of_range"

    def test_legacy_float_read_compatibility(self):
        # قيمة float قديمة من قاعدة البيانات → Decimal عند القراءة (PRD §10)
        legacy = 2500.0
        assert _dec(legacy) == Decimal("2500.00")
        assert _dec(1006.25) == Decimal("1006.25")


# ═════════════════════════════════════════════════════════════════════════════
# D) Configuration Tests (v1.1)
# ═════════════════════════════════════════════════════════════════════════════

class TestConfiguration:
    def test_missing_vat_rounding_account_is_explicit_error(self, monkeypatch):
        def _raiser(*a, **k):
            raise RuntimeError("unavailable")
        monkeypatch.setattr("supabase_service.SupabaseService", _raiser)
        monkeypatch.setattr("pymongo.MongoClient", _raiser)
        with pytest.raises(vat_policy.VatConfigError, match="not configured"):
            vat_policy.get_vat_rounding_account()

    def test_configured_account_resolves_to_179(self):
        # تكامل حقيقي: الإعداد المخزن يعيد الحساب المعتمد
        assert vat_policy.get_vat_rounding_account() == "179"


# ═════════════════════════════════════════════════════════════════════════════
# E) Stress Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestStress:
    def test_10k_journal_lines_balanced(self, engine):
        random.seed(42)
        lines = []
        for _ in range(5000):
            amt = Decimal(random.randrange(1, 10_000_000)) / 100  # قيم عشوائية بالهللة
            lines.append({"account": "005", "debit": str(amt), "credit": 0})
            lines.append({"account": "026", "debit": 0, "credit": str(amt)})
        t0 = time.time()
        res = engine.post(lines=lines, description="اختبار ضغط 10k")
        elapsed = time.time() - t0
        assert res["posted"] is True
        assert res["debit"] == res["credit"]
        assert elapsed < 5.0, f"10k lines took {elapsed:.2f}s"

    def test_10k_random_decimals_no_precision_loss(self):
        random.seed(7)
        vals = [Decimal(random.randrange(1, 99_999_999)) / 100 for _ in range(10_000)]
        total = sum(vals, Decimal("0.00"))
        assert total == sum(reversed(vals), Decimal("0.00"))  # ترتيب الجمع لا يغيّر النتيجة
        assert total.as_tuple().exponent == -2

    def test_validation_speed_kpi_under_50ms(self, engine):
        # KPI: متوسط زمن التحقق من قيد نموذجي < 50ms
        t0 = time.time()
        n = 100
        for i in range(n):
            engine.post(lines=_bal("500.00"), date=f"2026-07-02T10:{i % 60:02d}",
                        reference_id=f"kpi-{i}")
        avg_ms = (time.time() - t0) / n * 1000
        assert avg_ms < 50, f"avg validation {avg_ms:.1f}ms"

    def test_hash_stability_repeated(self, engine):
        hashes = {
            engine.compute_tx_hash(party="عميل", date="2026-07-02T10:00",
                                   lines=[{"account": "005", "debit": 500.0, "credit": 0.0}],
                                   total=500.0, reference_id="stab-1")
            for _ in range(500)
        }
        assert len(hashes) == 1                      # بصمة واحدة دائماً

    def test_concurrent_duplicate_claims(self, engine):
        import threading
        results = []
        kw = dict(lines=_bal("750.00"), date="2026-07-02T11:00",
                  reference_id="conc-1", party="عميل")
        def worker():
            results.append(engine.post(**kw))
        threads = [threading.Thread(target=worker) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        posted = [r for r in results if r.get("posted")]
        assert len(posted) == 1                      # قيد واحد فقط رغم 8 محاولات
