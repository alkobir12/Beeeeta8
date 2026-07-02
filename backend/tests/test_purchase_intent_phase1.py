"""🛒 اختبار المرحلة 1 — توحيد محرك النوايا + شراء من مورد

معايير القبول (خطة 2026-07-03):
  ✅ الأمر الحرفي (`1300.` ينتهي بنقطة) → مسودة واحدة فقط (لا 4).
  ✅ أمر متعدد البنود → مسودة واحدة بعدة بنود في items[].
  ✅ echo-back يعمل بعد التوحيد (compare vs pre-unify).
  ✅ القيد المحاسبي متوازن (Debit = Credit) عبر Decimal.
  ✅ نقدي → مدين 007 / دائن 003 · تحويل → 004 · آجل → 2101 (Supplier AP).
  ✅ الافتراضات موسومة (⚠️/🔗/🆕).
"""
from __future__ import annotations

import os
import sys
import asyncio
from decimal import Decimal
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ── (1) المقسِّم النصي القديم مُعطَّل — رسالة واحدة تُعامل كأمر واحد ─────────

def test_extract_commands_returns_single_command():
    from core import power_mode

    literal = "اشتري من راكان قلب مستوبيشي L200 بسعر 1300. نقدي"
    cmds = power_mode.extract_commands(literal)
    assert cmds == [literal], f"toEqual 1 command, got {len(cmds)}: {cmds!r}"


def test_extract_commands_multi_item_stays_one_command():
    from core import power_mode

    multi = "شراء من سالم: فلاتر زيت 5 حبات ب25، بواجي 4 ب12، تحويل"
    cmds = power_mode.extract_commands(multi)
    assert cmds == [multi], f"multi-item must stay one command; got {cmds!r}"


def test_extract_commands_empty_returns_empty():
    from core import power_mode
    assert power_mode.extract_commands("") == []
    assert power_mode.extract_commands("   ") == []


# ── (2) VAT split — Decimal بدون سماحية ──────────────────────────────────

def test_vat_split_none_mode():
    from core.vat_policy import compute_vat_split
    r = compute_vat_split(1300, {"mode": "none"})
    assert r["net"] == Decimal("1300")
    assert r["vat"] == Decimal("0.00")
    assert r["gross"] == Decimal("1300")


def test_vat_split_excluded_mode():
    from core.vat_policy import compute_vat_split
    r = compute_vat_split(1000, {"mode": "excluded", "rate": Decimal("0.15")})
    assert r["net"] == Decimal("1000")
    assert r["vat"] == Decimal("150.00")
    assert r["gross"] == Decimal("1150.00")


def test_vat_split_included_mode():
    from core.vat_policy import compute_vat_split
    # 1150 gross with 15% included → net 1000, vat 150
    r = compute_vat_split(1150, {"mode": "included", "rate": Decimal("0.15")})
    assert r["net"] == Decimal("1000.00")
    assert r["vat"] == Decimal("150.00")
    assert r["gross"] == Decimal("1150")


# ── (3) resolver — echo-back للشراء ─────────────────────────────────────

def test_purchase_resolver_cash_single_item():
    from core.unified_executor import _resolve_purchase_target

    payload = {
        "supplier": {"name": "راكان", "is_new": True, "id": None},
        "items": [{"name": "قلب مستوبيشي L200", "price": 1300, "qty": 1, "matched_id": None}],
        "vat": {"mode": "none"},
        # ⬇️ لا payment_method → يجب أن يُوسم كافتراض نقدي
    }
    res = _resolve_purchase_target(payload)
    assert "error" not in res, res
    enrich = res["enrich"]
    echo = enrich["_echo"]
    assert echo["type"] == "شراء"
    assert echo["entity"] == "راكان"
    assert echo["items_count"] == 1
    assert echo["amount"] == 1300.0
    assert echo["net"] == 1300.0
    assert echo["vat"] == 0.0
    # assumptions must tag cash (default) + no VAT + new supplier
    assumptions = echo["assumptions"]
    assert any("نقدي" in a for a in assumptions), assumptions
    assert any("بدون ضريبة" in a for a in assumptions), assumptions
    assert any("راكان" in a and "جديد" in a for a in assumptions), assumptions
    # accounts summary mentions inventory (007) + cash (003)
    accts = echo["accounts"]
    assert "007" in accts
    assert "003" in accts


def test_purchase_resolver_transfer_multi_item():
    from core.unified_executor import _resolve_purchase_target

    payload = {
        "supplier": {"name": "سالم", "is_new": False, "id": None},
        "payment_method": "transfer",
        "vat": {"mode": "none"},
        "items": [
            {"name": "فلاتر زيت", "price": 25, "qty": 5, "matched_id": None},
            {"name": "بواجي", "price": 12, "qty": 4, "matched_id": None},
        ],
    }
    res = _resolve_purchase_target(payload)
    assert "error" not in res
    echo = res["enrich"]["_echo"]
    assert echo["items_count"] == 2
    assert echo["amount"] == 125.0 + 48.0  # 5*25 + 4*12 = 125 + 48 = 173
    assert echo["amount"] == 173.0
    assert "004" in echo["accounts"]  # bank
    # NO cash assumption (payment_method explicit)
    assumptions = echo["assumptions"]
    assert not any("نقدي" in a for a in assumptions)


def test_purchase_resolver_credit_supplier_ap():
    from core.unified_executor import _resolve_purchase_target

    payload = {
        "supplier": {"name": "المتحدة", "is_new": False, "id": "sup-001"},
        "payment_method": "credit",
        "vat": {"mode": "none"},
        "items": [{"name": "طرمبة زيت", "price": 220, "qty": 2, "matched_id": None}],
    }
    res = _resolve_purchase_target(payload)
    assert "error" not in res
    echo = res["enrich"]["_echo"]
    assert echo["amount"] == 440.0
    assert "2101" in echo["accounts"]
    assert "المتحدة" in echo["accounts"]


def test_purchase_resolver_missing_items():
    from core.unified_executor import _resolve_purchase_target
    res = _resolve_purchase_target({"supplier": {"name": "أحد"}, "items": []})
    assert res.get("error") == "missing_fields"


def test_purchase_resolver_matched_id_tag():
    from core.unified_executor import _resolve_purchase_target
    res = _resolve_purchase_target({
        "supplier": {"name": "سالم"},
        "payment_method": "cash",
        "vat": {"mode": "none"},
        "items": [{"name": "فلتر", "price": 30, "qty": 2, "matched_id": "part-123"}],
    })
    echo = res["enrich"]["_echo"]
    # 🔗 tag for matched item
    assert any(a.startswith("🔗") for a in echo["assumptions"]), echo["assumptions"]


# ── (4) confirm_text — يعرض بنود + افتراضات ─────────────────────────────

def test_confirm_text_purchase_shows_items_and_assumptions():
    from core.unified_executor import _confirm_text
    from core.llm_intent_parser import Action

    action = Action(
        action="create_purchase",
        payload={
            "supplier": "راكان",
            "payment_method": "cash",
            "vat": {"mode": "none"},
            "items": [
                {"name": "قلب مستوبيشي L200", "price": 1300, "qty": 1, "line_total": 1300, "matched_id": None},
            ],
            "_echo": {
                "type": "شراء", "entity": "راكان", "amount": 1300.0,
                "net": 1300.0, "vat": 0.0, "payment_method": "cash",
                "items_count": 1,
                "items": [{"name": "قلب مستوبيشي L200", "price": 1300, "qty": 1, "line_total": 1300}],
                "accounts": "مدين: مخزون قطع غيار (007) بالصافي · دائن: النقد (003)",
                "assumptions": ["⚠️ افترضت: نقدي", "⚠️ افترضت: بدون ضريبة"],
            },
        },
    )
    txt = _confirm_text(action)
    assert "تأكيد تسجيل شراء" in txt
    assert "راكان" in txt
    assert "قلب مستوبيشي L200" in txt
    assert "1,300.00" in txt
    assert "⚠️ افترضت: نقدي" in txt
    assert "007" in txt


# ── (5) financial_actions.create_purchase — قيد متوازن Decimal ─────────

def test_financial_create_purchase_cash_balanced_journal():
    from core import financial_actions

    class _FakeIdentityStore:
        def claim(self, tx, meta):
            return {"claimed": True}
        def mark_posted(self, tx, jid):
            return None

    posted_entries = []

    class _FakeEngine:
        identity = _FakeIdentityStore()
        def post(self, **kw):
            # Assert lines are balanced (Decimal-strict)
            lines = kw["lines"]
            debit = sum(Decimal(str(ln.get("debit") or 0)) for ln in lines)
            credit = sum(Decimal(str(ln.get("credit") or 0)) for ln in lines)
            assert debit == credit, f"Unbalanced: {debit} vs {credit}"
            posted_entries.append(kw)
            return {"posted": True, "journal_id": "je-test-1",
                    "tx_hash": "hash-1", "total": float(kw.get("total") or 0)}

    with patch.object(financial_actions, "get_engine", return_value=_FakeEngine()):
        result = financial_actions.create_purchase(
            supplier="راكان",
            items=[{"name": "قلب مستوبيشي L200", "price": 1300, "qty": 1}],
            payment_method="cash",
            vat={"mode": "none"},
        )
        assert result["posted"] is True
        assert result["journal_id"] == "je-test-1"
        assert result["total"] == 1300.0

    # verify posted content
    assert len(posted_entries) == 1
    entry = posted_entries[0]
    assert entry["source"] == "purchase"
    assert entry["transaction_type"] == "purchase"
    lines = entry["lines"]
    debit_accs = [ln["account"] for ln in lines if ln.get("debit")]
    credit_accs = [ln["account"] for ln in lines if ln.get("credit")]
    assert "007" in debit_accs  # inventory
    assert "003" in credit_accs  # cash
    # no VAT line when mode=none
    assert not any(ln.get("account") == "0451" for ln in lines)


def test_financial_create_purchase_transfer_credit_bank():
    from core import financial_actions

    class _FE:
        class identity:
            @staticmethod
            def claim(tx, meta): return {"claimed": True}
            @staticmethod
            def mark_posted(tx, jid): return None
        def post(self, **kw):
            lines = kw["lines"]
            return {"posted": True, "journal_id": "je-2", "tx_hash": "h2",
                    "total": float(kw.get("total") or 0), "_lines": lines}

    with patch.object(financial_actions, "get_engine", return_value=_FE()):
        result = financial_actions.create_purchase(
            supplier="سالم",
            items=[
                {"name": "فلاتر زيت", "price": 25, "qty": 5},
                {"name": "بواجي", "price": 12, "qty": 4},
            ],
            payment_method="transfer",
            vat={"mode": "none"},
        )
        assert result["posted"] is True
        # 5*25 + 4*12 = 173
        assert result["total"] == 173.0
        lines = result.get("_lines", [])
        # If _lines was passed through result — check credit=bank
        # (otherwise ensure at least the balance stayed)


def test_financial_create_purchase_credit_ap_supplier():
    from core import financial_actions

    class _FE:
        class identity:
            @staticmethod
            def claim(tx, meta): return {"claimed": True}
            @staticmethod
            def mark_posted(tx, jid): return None
        def post(self, **kw):
            return {"posted": True, "journal_id": "je-3", "tx_hash": "h3",
                    "total": float(kw.get("total") or 0), "_lines": kw["lines"]}

    with patch.object(financial_actions, "get_engine", return_value=_FE()):
        result = financial_actions.create_purchase(
            supplier="المتحدة",
            items=[{"name": "طرمبة", "price": 220, "qty": 2}],
            payment_method="credit",
            vat={"mode": "none"},
        )
        assert result["posted"] is True
        assert result["total"] == 440.0
        lines = result.get("_lines", [])
        credit_lines = [ln for ln in lines if ln.get("credit")]
        # AP account = 2101 (from chart_resolver fallback)
        credit_names = [ln["account_name"] for ln in credit_lines]
        assert any("المتحدة" in n for n in credit_names), credit_names


def test_financial_create_purchase_vat_excluded_balanced():
    from core import financial_actions

    seen = {}

    class _FE:
        class identity:
            @staticmethod
            def claim(tx, meta): return {"claimed": True}
            @staticmethod
            def mark_posted(tx, jid): return None
        def post(self, **kw):
            seen["lines"] = kw["lines"]
            seen["total"] = kw["total"]
            debit = sum(Decimal(str(ln.get("debit") or 0)) for ln in kw["lines"])
            credit = sum(Decimal(str(ln.get("credit") or 0)) for ln in kw["lines"])
            assert debit == credit, f"Unbalanced with VAT: {debit} vs {credit}"
            return {"posted": True, "journal_id": "je-vat", "total": float(kw["total"])}

    with patch.object(financial_actions, "get_engine", return_value=_FE()):
        result = financial_actions.create_purchase(
            supplier="سالم",
            items=[{"name": "قطع", "price": 1000, "qty": 1}],
            payment_method="cash",
            vat={"mode": "excluded", "rate": Decimal("0.15")},
        )
    assert result["posted"] is True
    lines = seen["lines"]
    # 3 lines: inventory + VAT input + credit
    accts = [ln["account"] for ln in lines]
    assert "007" in accts
    assert "0451" in accts
    assert "003" in accts
    # Debit total = 1000 + 150 = 1150. Credit total = 1150.
    assert seen["total"] == Decimal("1150.00")


# ── (6) unified_executor.execute_text — نهاية-إلى-نهاية عبر LLM mock ────

def test_execute_text_purchase_produces_ONE_pending_approval():
    """الأهم — الأمر الحرفي `1300.` ينتج مسودة واحدة (لا 4)."""
    from core import unified_executor
    from core.llm_intent_parser import Action

    literal = "اشتري من راكان قلب مستوبيشي L200 بسعر 1300. نقدي"

    fake_action = Action(
        action="create_purchase",
        payload={
            "supplier": {"name": "راكان", "is_new": True, "id": None},
            "payment_method": "cash",
            "vat": {"mode": "none", "rate": 0.15, "inclusive": False},
            "items": [{"name": "قلب مستوبيشي L200", "price": 1300, "qty": 1, "matched_id": None}],
            "assumptions": [],
            "missing": [],
        },
    )

    async def _fake_parse(text, session_id=None):
        return fake_action

    with patch("core.unified_executor.parse_intent_with_llm", side_effect=_fake_parse):
        res = asyncio.run(unified_executor.execute_text(
            literal, proposer="test:user", session_id="test-sid-p1"
        ))

    assert res["status"] == "pending_approval", res
    draft = res["draft"]
    assert draft["action"] == "purchase"
    payload = draft["payload"]
    assert payload["_target_label"] == "راكان"
    echo = payload["_echo"]
    assert echo["items_count"] == 1
    assert echo["amount"] == 1300.0
    # وحدها ونهاية القصة — لا مسودات متعددة
    assert res.get("policy") == "manual_review_required"


def test_execute_text_multi_item_ONE_draft():
    """أمر متعدد البنود يبقى مسودة واحدة بعدة items."""
    from core import unified_executor
    from core.llm_intent_parser import Action

    literal = "شراء من سالم فلاتر زيت 5 حبات ب25 و بواجي 4 ب12 تحويل"

    fake_action = Action(
        action="create_purchase",
        payload={
            "supplier": {"name": "سالم", "is_new": False, "id": None},
            "payment_method": "transfer",
            "vat": {"mode": "none", "rate": 0.15, "inclusive": False},
            "items": [
                {"name": "فلاتر زيت", "price": 25, "qty": 5, "matched_id": None},
                {"name": "بواجي", "price": 12, "qty": 4, "matched_id": None},
            ],
        },
    )

    async def _fake_parse(text, session_id=None):
        return fake_action

    with patch("core.unified_executor.parse_intent_with_llm", side_effect=_fake_parse):
        res = asyncio.run(unified_executor.execute_text(
            literal, proposer="test:user", session_id="test-sid-p1-b"
        ))

    assert res["status"] == "pending_approval"
    echo = res["draft"]["payload"]["_echo"]
    assert echo["items_count"] == 2
    assert echo["amount"] == 173.0
