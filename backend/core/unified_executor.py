"""
⚙️ Unified Execution Engine — Phase 3C.4 (Policy Layer)

Sits on top of `core.action_runtime` to apply write-safety policy:
  • WRITE actions   → require a distinct human approver before commit
  • UNKNOWN actions → rejected

Read-only actions (`get_active_visits`, `get_*`) short-circuit and never
create a draft.

Automated identities cannot approve or commit any write action.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core import action_runtime
from core.llm_intent_parser import Action, parse_intent_with_llm
from core.log_utils import get_logger

_log = get_logger("unified_executor")


# ─────────────────────────────────────────────────────────────────────────────
# Risk policy
# ─────────────────────────────────────────────────────────────────────────────

# Actions that ALWAYS require a human reviewer (bulk + destructive ops).
RISKY_ACTIONS = {
    "close_visits",
    "delete_customer",
    "delete_vehicle",
    "delete_operation",
    "bulk_update",
    "bulk_delete",
    # 🏦 Financial actions — ALWAYS Four-Eyes, NEVER auto-commit (governance red line)
    "create_invoice",
    "collect_payment",
    "create_expense",
    "reverse_entry",
    "create_purchase",       # 🛒 شراء من مورد — إجراء مالي كامل بأربع أعين
}

# Read-only actions — no draft created, no approval needed.
READ_ONLY_ACTIONS = {
    "get_active_visits",
    "get_customers",
    "get_vehicles",
}

# LLM action name → runtime action token (what action_runtime.commit expects).
_ACTION_TO_RUNTIME = {
    "create_customer": "customer",
    "create_vehicle": "vehicle",
    "create_visit": "visit",
    "create_supplier": "supplier",
    "close_visits": "close_visits",
    "delete_operation": "delete_operation",
    "delete_customer": "delete_customer",
    "delete_vehicle": "delete_vehicle",
    "update_customer": "update_customer",
    "update_vehicle": "update_vehicle",
    "update_visit": "update_visit",
    "create_invoice": "invoice",
    "collect_payment": "payment",
    "create_expense": "expense",
    "reverse_entry": "reverse",
    "create_purchase": "purchase",
}

# Actions whose target must be resolved (to a concrete DB row) before we act.
_RESOLVE_TARGET_ACTIONS = {
    "delete_customer", "update_customer",
    "delete_vehicle", "update_vehicle",
    "update_visit",
    # 🏦 financial: resolve the real party / original entry + build echo-back
    "create_invoice", "collect_payment", "create_expense", "reverse_entry",
    "create_purchase",   # 🛒 حساب الإجمالي + اقتراح توجيه محاسبي + وسم الافتراضات
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def requires_approval(action: Action) -> bool:
    """Policy: should this action wait for a human reviewer?"""
    return action.action not in READ_ONLY_ACTIONS and action.action != "unknown"


async def execute_text(
    text: str,
    *,
    proposer: Optional[str] = None,
    session_id: Optional[str] = None,
    auto_approver: Optional[str] = None,
) -> Dict[str, Any]:
    """End-to-end orchestrator: text → LLM → policy decision → runtime.

    Returns one of these shapes:
      • status="rejected"          — unknown action, nothing happened
      • status="read_only"         — read query, includes result
      • status="pending_approval"  — risky action, draft + approval created
      • status="committed"         — safe action, written to DB
    """
    text = (text or "").strip()
    if not text:
        return {"status": "rejected", "reason": "empty_text"}

    action = await parse_intent_with_llm(text, session_id=session_id)

    # 🆕 Phase 3C.10 — Fallback: if LLM said "unknown" but the regex catches
    # a clear action verb, build a minimal payload from extracted entities
    # and proceed. This rescues the bot from over-strict LLM rejections.
    if action.action == "unknown":
        action = _regex_fallback_action(text)

    # 🛡️ Governance: no guessing — a creation without its essential identity
    # field goes back to the user instead of committing junk rows ("بدون اسم").
    if action.action in ("create_customer", "create_supplier"):
        if not str((action.payload or {}).get("name") or "").strip():
            is_cust = action.action == "create_customer"
            return {
                "status": "needs_clarification",
                "reason": "missing_fields",
                "entity": "customer" if is_cust else "supplier",
                "candidates": [],
                "ask": ("👤 ما اسم " + ("العميل" if is_cust else "المورّد")
                        + "؟ الاسم مطلوب قبل الإضافة — زوّدني به وسأجهّز التأكيد."),
                "action": action.model_dump(),
            }

    # 🆕 Resolve the target row for delete/update BEFORE acting, so the
    # approval card shows the real entity and commits never run blind.
    if action.action in _RESOLVE_TARGET_ACTIONS:
        resolved = _resolve_target(action)
        if resolved.get("error"):
            return {
                "status": "needs_clarification",
                "reason": resolved["error"],            # not_found | ambiguous | missing_fields
                "entity": resolved.get("entity") or ("customer" if "customer" in action.action else "vehicle"),
                "candidates": resolved.get("candidates") or [],
                "ask": resolved.get("ask"),
                "action": action.model_dump(),
            }
        # Enrich payload with the concrete id + a human label for the card.
        action.payload.update(resolved["enrich"])

    return await execute_action(
        action,
        proposer=proposer,
        session_id=session_id,
        auto_approver=auto_approver,
    )


def _regex_fallback_action(text: str) -> Action:
    """Convert regex-detected intents to an Action when the LLM gives up."""
    import re as _re
    # Check for delete intent first (handles Arabic suffixes + Qassimi dialect)
    delete_match = _re.search(r"(?:احذف|أحذف|امسح|أمسح|شيل|delete|remove)(?:ها|ه|هم|هن|وا|وه)?", text, _re.IGNORECASE)
    if delete_match:
        # Try to extract an operation ID from the text
        id_match = _re.search(r"(?:رقم|معرف|id)\s*[:#]?\s*(\S+)", text, _re.IGNORECASE)
        payload = {}
        if id_match:
            payload["operation_id"] = id_match.group(1)
        return Action(action="delete_operation", payload=payload)

    from core import power_mode
    intent_kind = power_mode.detect_intent_kind(text)
    if intent_kind == "unknown":
        return Action(action="unknown")
    entities = power_mode.extract_entities(text, intent_kind)
    # Map regex intent_kind → LLM action_name
    kind_to_action = {
        "customer": "create_customer",
        "vehicle": "create_vehicle",
        "visit": "create_visit",
        "supplier": "create_supplier",
        "operation": "create_visit",  # operation = visit-with-service in this domain
    }
    action_name = kind_to_action.get(intent_kind)
    if not action_name:
        return Action(action="unknown")
    # Build a clean payload — drop _resolved_from/raw noise
    payload: Dict[str, Any] = {}
    for key in ("name", "plate", "phone", "amount", "year", "vehicle_type", "service"):
        if entities.get(key) is not None:
            # Translate field names: amount→price, phone→customer_phone for visits
            tgt = "price" if (key == "amount" and action_name == "create_visit") else \
                  "customer_phone" if (key == "phone" and action_name in ("create_vehicle", "create_visit")) else \
                  key
            payload[tgt] = entities[key]
    return Action(action=action_name, payload=payload)


def _resolve_target(action: Action) -> Dict[str, Any]:
    """Resolve a delete/update/financial target to a concrete DB row / echo-back.

    Returns either:
      • {"enrich": {<id_field>: <id>, "_target_label": <name/plate>, "_echo": {...}, "set": {...}}}
      • {"error": "not_found"|"ambiguous"|"missing_fields", "entity": ..., "candidates": [...], "ask": ...}
    """
    # 🏦 Financial actions resolve the real party / original entry + build echo-back.
    if action.action in ("create_invoice", "collect_payment", "create_expense", "reverse_entry", "create_purchase"):
        return _resolve_financial_target(action)

    payload = action.payload or {}

    # 🛠️ update_visit — حلّ الزيارة المفتوحة من اسم العميل/اللوحة
    if action.action == "update_visit":
        res = action_runtime.resolve_visit_target(payload.get("match") or payload)
        if res.get("error"):
            return res
        row = res["row"]
        return {"enrich": {
            "visit_id": row.get("id"),
            "_target_label": row.get("customer_name") or row.get("plate_number") or row.get("id"),
            "set": payload.get("set") or {},
        }}

    is_customer = "customer" in action.action
    is_update = action.action.startswith("update_")
    # For updates the matcher lives under `match`; for deletes the payload IS the matcher.
    criteria = (payload.get("match") if is_update else None) or payload

    if is_customer:
        res = action_runtime.resolve_customer_target(criteria)
    else:
        res = action_runtime.resolve_vehicle_target(criteria)

    if res.get("error"):
        return res
    row = res["row"]
    if is_customer:
        enrich = {"customer_id": row.get("id"), "_target_label": row.get("name") or row.get("phone") or row.get("id")}
    else:
        enrich = {"vehicle_id": row.get("id"),
                  "_target_label": row.get("plate_number") or row.get("plate") or row.get("id")}
    if is_update:
        enrich["set"] = payload.get("set") or {}
    return {"enrich": enrich}


def _resolve_purchase_target(payload: Dict[str, Any]) -> Dict[str, Any]:
    """🛒 يحسب إجمالي الشراء + يقترح التوجيه المحاسبي + يوسم الافتراضات.

    منطق:
      - المورد اختياري: بدون اسم → دائن حساب "مورد — مفتوح" (لا يوقف الدفع النقدي/التحويل).
      - `items[]`: يجب أن يحوي بنداً واحداً على الأقل بسعر > 0. وإلا يُطلب توضيح.
      - `payment_method` افتراضياً 'cash' (يُوسم كافتراض).
      - `vat.mode` افتراضياً 'none' (يُوسم كافتراض).
    """
    supplier_raw = payload.get("supplier")
    if isinstance(supplier_raw, dict):
        supplier_name = str(supplier_raw.get("name") or "").strip()
        supplier_is_new = bool(supplier_raw.get("is_new"))
        supplier_id = supplier_raw.get("id")
    else:
        supplier_name = str(supplier_raw or "").strip()
        supplier_is_new = False
        supplier_id = None

    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        return {"error": "missing_fields", "entity": "purchase",
                "ask": "🛒 ما البنود المشتراة؟ زوّدني بقائمة: اسم القطعة، السعر، الكمية."}

    # 1) حساب الإجمالي بـ Decimal (توازن نهائي عبر AccountingEngine)
    from decimal import Decimal
    try:
        from core.vat_policy import compute_vat_split
    except Exception:
        compute_vat_split = None  # type: ignore

    net_dec = Decimal("0.00")
    normalized_items = []
    for it in items:
        try:
            price = Decimal(str(it.get("price") or 0))
            qty = Decimal(str(it.get("qty") or it.get("quantity") or 1))
        except Exception:
            price, qty = Decimal("0"), Decimal("1")
        line = (price * qty)
        net_dec += line
        normalized_items.append({
            "name": str(it.get("name") or "").strip(),
            "price": float(price), "qty": float(qty),
            "line_total": float(line), "matched_id": it.get("matched_id"),
        })
    if net_dec <= 0:
        return {"error": "missing_fields", "entity": "purchase",
                "ask": "💰 لا أستطيع حساب إجمالي الشراء — تأكد من ذكر السعر والكمية لكل بند."}

    vat_cfg = payload.get("vat") or {"mode": "none"}
    if compute_vat_split:
        split = compute_vat_split(net_dec, vat_cfg)
        net_amt = float(split["net"])
        vat_amt = float(split["vat"])
        gross_amt = float(split["gross"])
    else:
        net_amt = float(net_dec)
        vat_amt = 0.0
        gross_amt = net_amt

    # 2) بناء التوجيه المحاسبي (echo-back)
    try:
        from core.chart_resolver import semantic_codes
        sem = semantic_codes()
    except Exception:
        sem = {"inventory_parts": "007", "cash": "003", "bank": "004", "ap": "2101"}
    pm = str(payload.get("payment_method") or "cash").strip().lower()
    if pm in ("credit", "اجل", "آجل", "deferred"):
        credit_line = f"دائن: الموردون ({sem.get('ap', '2101')} — {supplier_name or 'مفتوح'})"
    elif pm in ("bank", "transfer", "bank_transfer", "تحويل", "بنك"):
        credit_line = f"دائن: البنك ({sem.get('bank', '004')})"
    else:
        credit_line = f"دائن: النقد ({sem.get('cash', '003')})"
    debit_line = f"مدين: مخزون قطع غيار ({sem.get('inventory_parts', '007')}) بالصافي"
    if vat_amt > 0:
        debit_line += f" + ضريبة المدخلات {vat_amt:,.2f}"
    accounts_summary = f"{debit_line} · {credit_line}"

    # 3) وسوم الافتراضات (⚠️/🔗/🆕) — بدون تكرار حتى لو أضاف LLM بعضاً منها
    assumptions: List[str] = list(payload.get("assumptions") or [])

    def _add(msg: str) -> None:
        # منع التكرار بمقارنة النص المطبَّع (بعد إزالة الرموز/الفراغات الزائدة)
        key = re.sub(r"[\W_]+", "", str(msg)).lower()
        for existing in assumptions:
            if re.sub(r"[\W_]+", "", str(existing)).lower() == key:
                return
        assumptions.append(msg)

    if not payload.get("payment_method"):
        _add("⚠️ افترضت: نقدي")
    if not payload.get("vat") or str((payload.get("vat") or {}).get("mode") or "none") == "none":
        _add("⚠️ افترضت: بدون ضريبة")
    if supplier_is_new and supplier_name:
        _add(f"🆕 مورد جديد: {supplier_name} (سيُنشأ بالإضافة)")
    for it in normalized_items:
        if it.get("matched_id"):
            _add(f"🔗 طابقت البند: {it['name']}")

    echo = {
        "type": "شراء",
        "entity": supplier_name or "مورد مفتوح",
        "amount": gross_amt,
        "net": net_amt,
        "vat": vat_amt,
        "vat_mode": str(vat_cfg.get("mode") or "none"),
        "payment_method": pm,
        "items_count": len(normalized_items),
        "items": normalized_items,
        "accounts": accounts_summary,
        "assumptions": assumptions,
    }
    enrich = {
        "supplier": supplier_name or None,
        "supplier_id": supplier_id,
        "supplier_is_new": supplier_is_new,
        "items": normalized_items,
        "payment_method": pm,
        "vat": vat_cfg,
        "_target_label": supplier_name or "مورد مفتوح",
        "_echo": echo,
        "_assumptions": assumptions,
    }
    return {"enrich": enrich}


def _resolve_financial_target(action: Action) -> Dict[str, Any]:
    """🏦 Resolve the real party / original entry for a financial action and build
    the echo-back summary (type + entity + amount + affected accounts). Enforces
    Principle ①: no guessing — missing/ambiguous data → ask the user."""

    def _sem() -> Dict[str, str]:
        fallback = {"ar": "005", "revenue_mech": "026", "admin_expense": "035"}
        try:
            from core.chart_resolver import semantic_codes
            sem = semantic_codes()
            return {k: sem.get(k) or v for k, v in fallback.items()}
        except Exception:
            return fallback

    payload = action.payload or {}
    act = action.action

    if act == "reverse_entry":
        jid = str(payload.get("journal_id") or "").strip()
        ref = str(payload.get("reference_id") or "").strip()
        if not jid and not ref:
            return {"error": "missing_fields", "entity": "financial",
                    "ask": ("🔒 القيود المرحّلة غير قابلة للتعديل أو الحذف (مبدأ الدفتر غير القابل للتغيير "
                            "Immutable Ledger) — التصحيح يكون **بقيد عكسي** فقط.\n"
                            "🔁 لعكس قيد، زوّدني برقم القيد (journal_id) أو المرجع (reference_id).")}
        label = jid or ref
        return {"enrich": {"_target_label": label, "_echo": {
            "type": "قيد عكسي", "entity": label, "amount": None,
            "accounts": "عكس القيد الأصلي (مدين↔دائن) — الأصل محفوظ"}}}

    if act == "create_purchase":
        return _resolve_purchase_target(payload)

    if act == "create_expense":
        desc = str(payload.get("description") or payload.get("category") or "").strip()
        amount = payload.get("amount") or payload.get("total")
        if not desc:
            return {"error": "missing_fields", "entity": "financial",
                    "ask": "🧾 وضّح وصف المصروف (مثال: إيجار، رواتب، قطع غيار)."}
        if not amount:
            return {"error": "missing_fields", "entity": "financial",
                    "ask": f"💰 كم مبلغ المصروف «{desc}»؟"}
        sem = _sem()
        return {"enrich": {"_target_label": desc, "_echo": {
            "type": "مصروف", "entity": payload.get("supplier") or desc, "amount": amount,
            "accounts": f"مدين: مصروفات عامة وإدارية ({sem['admin_expense']}) / دائن: النقد أو البنك"}}}

    # create_invoice / collect_payment → resolve the customer
    name = str(payload.get("customer") or payload.get("customer_name") or payload.get("name") or "").strip()
    phone = str(payload.get("customer_phone") or payload.get("phone") or "").strip()
    if not name and not phone:
        return {"error": "missing_fields", "entity": "financial",
                "ask": "👤 لمن الفاتورة/الدفعة؟ زوّدني باسم العميل أو رقم جواله."}
    res = action_runtime.resolve_customer_target({"name": name, "phone": phone})
    if res.get("error"):
        res["entity"] = "customer"
        return res
    row = res["row"]
    cust_name = row.get("name") or row.get("phone") or row.get("id")
    sem = _sem()
    if act == "collect_payment":
        amount = payload.get("amount") or payload.get("total")
        if not amount:
            return {"error": "missing_fields", "entity": "financial",
                    "ask": f"💰 كم مبلغ الدفعة المُحصّلة من «{cust_name}»؟"}
        echo = {"type": "تحصيل دفعة", "entity": cust_name, "amount": amount,
                "accounts": f"مدين: النقد/البنك / دائن: ذمم العملاء ({sem['ar']})"}
    else:  # create_invoice
        amount = payload.get("total") or payload.get("amount")
        if not amount and not payload.get("items"):
            return {"error": "missing_fields", "entity": "financial",
                    "ask": f"💰 ما إجمالي الفاتورة للعميل «{cust_name}»؟"}
        pm = payload.get("payment_method") or "credit"
        accounts = (f"مدين: ذمم العملاء ({sem['ar']}) / دائن: إيرادات خدمات ({sem['revenue_mech']})" if pm == "credit"
                    else f"مدين: النقد/الشبكة / دائن: إيرادات خدمات ({sem['revenue_mech']})")
        echo = {"type": "فاتورة", "entity": cust_name, "amount": amount, "accounts": accounts}
    return {"enrich": {"customer": cust_name, "customer_id": row.get("id"),
                       "_target_label": cust_name, "_echo": echo}}


def _find_duplicate_pending(runtime_action: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """🛡️ منع تكرار طلبات الاعتماد: يرجع مسودة معلقة مطابقة (نفس الإجراء + الجهة + المبلغ)."""
    from core.draft_audit import _amount_of, _entity_of
    amt = _amount_of(payload)
    ent = _entity_of(payload)
    if amt <= 0 and not ent:
        return None
    for d in action_runtime.list_drafts(status="pending_approval", limit=30):
        if d.get("action") != runtime_action:
            continue
        p2 = d.get("payload") or {}
        if abs(_amount_of(p2) - amt) < 0.01 and _entity_of(p2) == ent:
            return d
    return None


async def execute_action(
    action: Action,
    *,
    proposer: Optional[str] = None,
    session_id: Optional[str] = None,
    auto_approver: Optional[str] = None,
) -> Dict[str, Any]:
    """Drive a pre-parsed Action through the runtime + policy gates."""

    # 1) Unknown guard
    if action.action == "unknown":
        return {
            "status": "rejected",
            "reason": "unknown_action",
            "action": action.model_dump(),
        }

    # 2) Read-only short-circuit
    if action.action in READ_ONLY_ACTIONS:
        if action.action == "get_active_visits":
            return {
                "status": "read_only",
                "action": action.model_dump(),
                "result": action_runtime.get_active_visits(
                    limit=int(action.payload.get("limit") or 50),
                ),
            }
        # Generic read-only marker — caller plugs the right query elsewhere
        return {"status": "read_only", "action": action.model_dump(), "result": None}

    # 3) Map LLM action_name → runtime token
    runtime_action = _ACTION_TO_RUNTIME.get(action.action)
    if not runtime_action:
        return {
            "status": "rejected",
            "reason": "no_runtime_handler",
            "action": action.model_dump(),
        }

    # 4) Create draft (always — even for auto-committed actions)
    proposer_id = proposer or "auto:llm"
    needs_manual_approval = requires_approval(action)

    # 🛡️ طلب مطابق معلق بالفعل → نعيد بطاقته بدل إنشاء نسخة مكررة
    if needs_manual_approval:
        dup = _find_duplicate_pending(runtime_action, action.payload)
        if dup is not None:
            return {
                "status": "pending_approval",
                "duplicate": True,
                "action": action.model_dump(),
                "draft": dup,
                "approval": {"approval_id": dup.get("last_approval_id")},
                "policy": "duplicate_pending",
            }

    draft = action_runtime.create_draft(
        action=runtime_action,
        payload=action.payload,
        proposer=proposer_id,
        session_id=session_id,
    )

    # 5) Risky → manual approval gate (+ 🕵️ مدقق المسودات قبل الاعتماد)
    if needs_manual_approval:
        approval = action_runtime.request_approval(
            draft_id=draft["id"], requester=proposer_id,
        )
        try:
            from core.draft_audit import audit_draft_with_findings
            audit_notes = await audit_draft_with_findings(
                runtime_action, action.payload, draft_id=draft["id"])
        except Exception:
            audit_notes = []
        return {
            "status": "pending_approval",
            "action": action.model_dump(),
            "draft": draft,
            "approval": approval,
            "policy": "manual_review_required",
            "audit_notes": audit_notes,
        }

    # 6) Safe → echo-back + explicit user confirmation (Phase C governance).
    #    The draft + approval exist but NOTHING is committed until the user
    #    replies «نعم» (kernel routes that to confirm_pending below).
    req = action_runtime.request_approval(
        draft_id=draft["id"], requester=proposer_id,
    )
    if "error" in req:
        return {"status": "error", "reason": req["error"], "draft": draft}

    pending = {
        "draft_id": draft["id"],
        "approval_id": req["approval_id"],
        "action": action.action,
        "proposer": proposer_id,
    }
    if session_id:
        try:
            from core import shared_memory
            shared_memory.set_context(session_id, "pending_confirm", pending)
        except Exception:
            pass

    return {
        "status": "awaiting_confirmation",
        "action": action.model_dump(),
        "draft": draft,
        "approval": req,
        "confirm_text": _confirm_text(action),
        "policy": "confirm_first",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase C — user confirmation helpers («نعم» / «لا»)
# ─────────────────────────────────────────────────────────────────────────────

_CONFIRM_LABELS = {
    "create_customer": "إضافة عميل", "create_vehicle": "إضافة مركبة",
    "create_visit": "فتح زيارة", "create_supplier": "إضافة مورّد",
    "update_customer": "تعديل عميل", "update_vehicle": "تعديل مركبة",
    "update_visit": "تعديل زيارة",
    "create_purchase": "تسجيل شراء",
}

_FIELD_LABELS = {
    "name": "الاسم", "phone": "الجوال", "customer_phone": "جوال العميل",
    "customer_name": "اسم العميل", "plate": "اللوحة", "brand": "الماركة",
    "model": "الموديل", "year": "السنة", "vehicle_type": "نوع المركبة",
    "service": "الخدمة", "price": "السعر", "amount": "المبلغ", "reason": "السبب",
    "category": "التخصص", "payment_terms": "شروط الدفع", "email": "البريد",
    "address": "العنوان", "status": "الحالة", "vehicle_plate": "لوحة المركبة",
}


def _confirm_text(action: Action) -> str:
    payload = action.payload or {}
    label = _CONFIRM_LABELS.get(action.action, action.action)

    # 🛒 صياغة مضغوطة خاصة بالشراء — يعرض جدول البنود + الافتراضات
    if action.action == "create_purchase":
        echo = payload.get("_echo") or {}
        items = echo.get("items") or payload.get("items") or []
        supplier = echo.get("entity") or payload.get("supplier") or "مورد مفتوح"
        gross = echo.get("amount")
        net = echo.get("net")
        vat = echo.get("vat")
        pm_ar = {"cash": "نقدي", "bank": "تحويل", "transfer": "تحويل",
                 "credit": "آجل", "آجل": "آجل"}.get(str(echo.get("payment_method") or "cash").lower(), "نقدي")
        lines = [
            f"🛒 **تأكيد {label}** — من: **{supplier}** · دفع: **{pm_ar}**",
            "",
            "📦 البنود:",
        ]
        for it in items:
            n = it.get("name") or "—"
            p = it.get("price") or 0
            q = it.get("qty") or 1
            tl = it.get("line_total") or (float(p) * float(q))
            match_tag = " 🔗" if it.get("matched_id") else ""
            lines.append(f"  • {n} — {p:,.2f} × {q} = {tl:,.2f}{match_tag}")
        lines.append("")
        if vat and float(vat) > 0:
            lines.append(f"💰 الصافي: {net:,.2f} · ضريبة: {vat:,.2f} · **الإجمالي: {gross:,.2f}**")
        else:
            lines.append(f"💰 **الإجمالي: {gross:,.2f} ر.س**")
        acc = echo.get("accounts")
        if acc:
            lines.append(f"🧾 القيد: {acc}")
        for a in (echo.get("assumptions") or payload.get("_assumptions") or []):
            lines.append(a)
        lines += ["", "✋ لن يُحفظ أي شيء قبل موافقة المُعتمِد الثاني — سيظهر ضمن «اعتمادات كاترينا»."]
        return "\n".join(lines)

    def _fmt(d: Dict[str, Any]) -> list:
        rows = []
        for k, v in (d or {}).items():
            if v in (None, "", []) or str(k).startswith("_") or k in ("match", "set", "raw"):
                continue
            rows.append(f"• {_FIELD_LABELS.get(k, k)}: {v}")
        return rows

    lines = [f"📋 **تأكيد {label}** — راجع البيانات قبل الحفظ:"]
    if action.action.startswith("update_"):
        tgt = payload.get("_target_label")
        if tgt:
            lines.append(f"• الهدف: {tgt}")
        lines += _fmt(payload.get("match") or {})
        st = payload.get("set") or {}
        if st:
            lines.append("التعديلات الجديدة:")
            lines += _fmt(st)
    else:
        lines += _fmt(payload)
    lines.append("")
    lines.append("✋ لن يُحفظ أي شيء قبل موافقتك — رد بـ «نعم» للتنفيذ أو «لا» للإلغاء.")
    return "\n".join(lines)


def confirm_pending(pending: Dict[str, Any], *, approver: Optional[str] = None) -> Dict[str, Any]:
    """يبقي التأكيد بانتظار اعتماد بشري؛ لا اعتماد آلي ولا تثبيت مباشر."""
    return {
        "status": "pending_approval",
        "action": {"action": pending.get("action"), "payload": {}},
        "draft": action_runtime.get_draft(pending["draft_id"]),
        "approval": {"approval_id": pending["approval_id"]},
        "policy": "human_review_required",
    }


def cancel_pending(pending: Dict[str, Any], *, approver: Optional[str] = None) -> Dict[str, Any]:
    """يرفض/يلغي مسودة آمنة بعد رفض المستخدم («لا»)."""
    try:
        action_runtime.reject_approval(
            approval_id=pending["approval_id"], approver=approver or pending.get("proposer"), reason="user_cancelled",
        )
    except Exception:
        pass
    return {"status": "cancelled", "action": {"action": pending.get("action")}}


# ─────────────────────────────────────────────────────────────────────────────
# Class wrapper (matches the L16 spec shape)
# ─────────────────────────────────────────────────────────────────────────────


class UnifiedExecutionEngine:
    """Class form for callers that prefer the spec's object-oriented shape.

    The functional `execute_text` is the preferred entrypoint inside our
    backend; this class is a thin adapter for the L16 spec.
    """

    def __init__(self, llm=None, supabase=None, runtime=None):
        # llm/supabase/runtime are kept for spec parity but ignored — we
        # delegate to the global core modules so the audit trail stays unified.
        self.llm = llm
        self.supabase = supabase
        self.runtime = runtime or action_runtime

    async def execute(self, text: str, **kwargs) -> Dict[str, Any]:
        return await execute_text(text, **kwargs)

    @staticmethod
    def requires_approval(action: Action) -> bool:
        return requires_approval(action)
