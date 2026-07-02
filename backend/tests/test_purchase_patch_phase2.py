"""🛠️ اختبار المرحلة 2 — Backend Endpoints للتعديل السياقي على مسودات الشراء.

المُختبَر:
  ✅ patch_draft: set_payment_method, set_vat_mode, add_item, remove_item.
  ✅ إعادة تشغيل الـ resolver بعد التعديل → تحديث _echo و _assumptions.
  ✅ رفض التعديل بعد الاعتماد/الالتزام (immutable_state).
  ✅ رفض عمليات غير معروفة.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _make_purchase_draft():
    from core import action_runtime
    payload = {
        "supplier": {"name": "راكان", "is_new": True, "id": None},
        "payment_method": "cash",
        "vat": {"mode": "none", "rate": 0.15, "inclusive": False},
        "items": [{"name": "قلب مستوبيشي L200", "price": 1300, "qty": 1, "matched_id": None}],
    }
    return action_runtime.create_draft(
        action="purchase", payload=payload,
        proposer="test:phase2", session_id="ph2-sess",
    )


def test_patch_switch_payment_method_updates_echo():
    from core import action_runtime
    draft = _make_purchase_draft()
    action_runtime.request_approval(draft_id=draft["id"], requester="test:phase2")

    res = action_runtime.patch_draft(
        draft_id=draft["id"],
        ops=[{"op": "set_payment_method", "value": "transfer"}],
        actor="test:phase2",
    )
    assert "error" not in res, res
    updated = res["draft"]["payload"]
    assert updated["payment_method"] == "transfer"
    # echo re-run → dain now 004 (bank), not 003 (cash)
    echo = updated["_echo"]
    assert "004" in echo["accounts"], echo["accounts"]
    assert "003" not in echo["accounts"]


def test_patch_add_vat_recalculates_gross():
    from core import action_runtime
    draft = _make_purchase_draft()
    action_runtime.request_approval(draft_id=draft["id"], requester="test:phase2")

    res = action_runtime.patch_draft(
        draft_id=draft["id"],
        ops=[{"op": "set_vat_mode", "value": "excluded", "rate": 0.15}],
        actor="test:phase2",
    )
    updated = res["draft"]["payload"]
    echo = updated["_echo"]
    # 1300 * 0.15 = 195, gross = 1495
    assert echo["net"] == 1300.0
    assert echo["vat"] == 195.0
    assert echo["amount"] == 1495.0


def test_patch_add_item_appends_and_recomputes():
    from core import action_runtime
    draft = _make_purchase_draft()
    action_runtime.request_approval(draft_id=draft["id"], requester="test:phase2")

    res = action_runtime.patch_draft(
        draft_id=draft["id"],
        ops=[{"op": "add_item",
              "item": {"name": "فلاتر زيت", "price": 25, "qty": 4, "matched_id": None}}],
        actor="test:phase2",
    )
    updated = res["draft"]["payload"]
    assert len(updated["items"]) == 2
    echo = updated["_echo"]
    # 1300 + 25*4 = 1400
    assert echo["amount"] == 1400.0
    assert echo["items_count"] == 2


def test_patch_remove_item_recomputes():
    from core import action_runtime
    draft = _make_purchase_draft()
    action_runtime.request_approval(draft_id=draft["id"], requester="test:phase2")
    action_runtime.patch_draft(
        draft_id=draft["id"],
        ops=[{"op": "add_item",
              "item": {"name": "فلاتر", "price": 25, "qty": 4}}],
        actor="test:phase2",
    )
    res = action_runtime.patch_draft(
        draft_id=draft["id"],
        ops=[{"op": "remove_item", "index": 0}],  # removes original L200
        actor="test:phase2",
    )
    updated = res["draft"]["payload"]
    assert len(updated["items"]) == 1
    assert updated["items"][0]["name"] == "فلاتر"
    assert updated["_echo"]["amount"] == 100.0  # 25*4


def test_patch_rejected_after_commit():
    """المسودة الملتزمة (committed) لا تقبل التعديل."""
    from core import action_runtime
    draft = _make_purchase_draft()
    # simulate committed state directly
    action_runtime.STATE["drafts"][draft["id"]]["status"] = "committed"
    res = action_runtime.patch_draft(
        draft_id=draft["id"],
        ops=[{"op": "set_payment_method", "value": "cash"}],
        actor="test:phase2",
    )
    assert res.get("error") == "immutable_state"


def test_patch_unknown_op_rejected():
    from core import action_runtime
    draft = _make_purchase_draft()
    res = action_runtime.patch_draft(
        draft_id=draft["id"],
        ops=[{"op": "do_bad_stuff"}],
        actor="test:phase2",
    )
    assert res.get("error") == "unknown_op"


def test_patch_only_on_purchase_action():
    """PATCH لا يعمل على مسودات غير الشراء (customer/vehicle/etc)."""
    from core import action_runtime
    d = action_runtime.create_draft(
        action="customer",
        payload={"name": "test"},
        proposer="t", session_id="s",
    )
    res = action_runtime.patch_draft(
        draft_id=d["id"],
        ops=[{"op": "set_payment_method", "value": "cash"}],
        actor="t",
    )
    assert res.get("error") == "unsupported_action"


def test_approval_card_has_contextual_actions():
    """بطاقة الاعتماد للشراء تحوي الأزرار السياقية (5 أزرار)."""
    from core.assistant_kernel import _build_approval_actions

    payload = {
        "supplier": {"name": "راكان", "is_new": True, "id": None},
        "payment_method": "cash",
        "vat": {"mode": "none", "rate": 0.15},
        "items": [{"name": "قطعة", "price": 100, "qty": 1}],
    }
    echo = {"payment_method": "cash"}
    actions = _build_approval_actions(
        "create_purchase", "draft-x", "app-y", payload, echo,
    )
    ids = [a["id"] for a in actions]
    assert "approve" in ids
    assert "reject" in ids
    assert "switch_transfer" in ids
    assert "add_vat" in ids
    assert "add_supplier" in ids


def test_approval_card_non_purchase_only_2_actions():
    """بطاقات الاعتماد لغير الشراء (فاتورة/تحصيل...) لا تحوي أزرار السياق."""
    from core.assistant_kernel import _build_approval_actions
    actions = _build_approval_actions(
        "create_invoice", "d-1", "a-1", {"customer": "test"}, {},
    )
    ids = [a["id"] for a in actions]
    assert ids == ["approve", "reject"]


def test_approval_card_credit_offers_switch_to_cash():
    from core.assistant_kernel import _build_approval_actions
    payload = {"supplier": {"name": "س"}, "payment_method": "credit",
               "vat": {"mode": "none"}, "items": [{"name": "x", "price": 1, "qty": 1}]}
    echo = {"payment_method": "credit"}
    actions = _build_approval_actions("create_purchase", "d", "a", payload, echo)
    ids = [a["id"] for a in actions]
    assert "switch_cash" in ids


def test_approval_card_vat_present_shows_remove_vat_button():
    from core.assistant_kernel import _build_approval_actions
    payload = {"supplier": {"name": "س"}, "payment_method": "cash",
               "vat": {"mode": "excluded", "rate": 0.15},
               "items": [{"name": "x", "price": 1, "qty": 1}]}
    echo = {"payment_method": "cash"}
    actions = _build_approval_actions("create_purchase", "d", "a", payload, echo)
    ids = [a["id"] for a in actions]
    assert "remove_vat" in ids
    assert "add_vat" not in ids
