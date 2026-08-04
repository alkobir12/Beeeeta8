"""📒 L14-D6 (الشق التقني فقط) — SSOT الذمم: القيود هي المرجع، والأرصدة تُشتق.

قراءة واشتقاق فقط — لا يلمس أي بيانات (مصير 3,450 وقيود الاختبار قرار المالك،
أمر علاج L14 بند 4). الطبقات:
  1. ledger_ar_total   — رصيد حسابات الذمم (005/1103/113) من القيود = SSOT
  2. pending_unjournalized — عمليات آجلة بلا قيود (مفردة — بانتظار قرار المالك)
  3. stored_balances   — الأرصدة المخزنة القديمة (تُعرض للمصالحة فقط)
"""
from __future__ import annotations

import re
from typing import Any, Dict

AR_ACCOUNT_CODES = {"005", "1103", "113"}
CREDIT_METHODS = {"credit", "deferred", "اجل", "آجل", "ذمة", "ذمم"}
UNPAID_STATUSES = {"unpaid", "credit", "partial", "deferred", "pending"}
_PARTY_RE = re.compile(r"\[PARTY:([^\]]+)\]")


async def summary(workshop_id: str = "finmodule-sync") -> Dict[str, Any]:
    from financial_reconciliation import table_fetch_all
    from supabase_service import SupabaseService

    supa = SupabaseService()
    if supa.mock_mode:
        raise RuntimeError("AR ledger requires real database data")

    entries = table_fetch_all(supa.client, "journal_entries")
    entries = [row for row in entries if str(row.get("workshop_id") or workshop_id) == workshop_id]
    ops = table_fetch_all(supa.client, "operations")
    customers = table_fetch_all(supa.client, "customers")

    # 1) SSOT — رصيد الذمم من القيود
    ledger_total = 0.0
    per_party: Dict[str, float] = {}
    for e in entries:
        desc = str(e.get("description") or "")
        pm = _PARTY_RE.search(desc)
        party = (pm.group(1).strip() if pm else "") or str(e.get("party_label") or "").strip()
        for ln in (e.get("lines") or []):
            code = str(ln.get("account") or ln.get("code") or ln.get("account_code") or "").strip()
            if code in AR_ACCOUNT_CODES:
                delta = float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
                ledger_total += delta
                key = party or "غير منسوب"
                per_party[key] = per_party.get(key, 0.0) + delta

    # 2) عمليات آجلة بلا قيود (مفردة — مجمّدة بانتظار قرار المالك)
    refs = {str(e.get("reference_id") or "").strip() for e in entries}
    pending = []
    for op in ops:
        m = str(op.get("paymentMethod") or "").strip().lower()
        ps = str(op.get("paymentStatus") or "").strip().lower()
        if m not in CREDIT_METHODS and ps not in UNPAID_STATUSES:
            continue
        if str(op.get("id") or "") in refs:
            continue
        if str(op.get("type") or "").lower() not in {"sale", "service", "instant_sale"}:
            continue
        pending.append({
            "op_id": str(op.get("id"))[:8],
            "customer": (op.get("customerName") or op.get("customer_name") or "")[:40],
            "total": float(op.get("total") or 0),
            "date": str(op.get("date") or op.get("createdAt") or "")[:10],
        })
    pending_total = round(sum(p["total"] for p in pending), 2)

    # 3) الأرصدة المخزنة (Legacy — للمصالحة فقط، لا تُعدَّل)
    stored = [{"name": c.get("name"), "balance": float(c.get("ajelBalance") or 0)}
              for c in customers if float(c.get("ajelBalance") or 0) > 0]
    stored_total = round(sum(s["balance"] for s in stored), 2)
    ledger_total = round(ledger_total, 2)

    current_vehicle_ar_total = 0.0
    try:
        from core.unified_financial_engine import build_current_ar_snapshot
        current_snapshot = build_current_ar_snapshot(supa.client, workshop_id=workshop_id)
        current_vehicle_ar_total = round(float(current_snapshot.get("total_ar") or 0), 2)
    except Exception:
        current_vehicle_ar_total = 0.0

    # 4) 🕒 القيود المؤقتة للبيع الآجل (قاعدة المالك — موسومة حتى التحصيل)
    op_names = {str(o.get("id") or ""): (o.get("customerName") or o.get("customer_name")
                or o.get("partnerName") or o.get("partner_name") or "") for o in ops}
    temp_entries = []
    for e in entries:
        desc = str(e.get("description") or "")
        if "[قيد مؤقت — بيع آجل" not in desc:
            continue
        ref = str(e.get("reference_id") or "")
        pm = _PARTY_RE.search(desc)
        temp_entries.append({
            "entry_id": str(e.get("id"))[:8],
            "reference_id": ref[:8],
            "party": ((pm.group(1).strip() if pm else "") or op_names.get(ref) or str(e.get("party_label") or ""))[:40],
            "total": float(e.get("total") or 0),
            "date": str(e.get("date") or "")[:10],
            "partially_collected": "مُحصَّل جزئياً" in desc,
        })
    temp_total = round(sum(t["total"] for t in temp_entries), 2)

    return {
        "ssot": "journal_entries",
        "current_vehicle_ar_total": current_vehicle_ar_total,
        "ledger_ar_total": ledger_total,
        "ledger_by_party": sorted(
            [{"party": k, "balance": round(v, 2)} for k, v in per_party.items() if abs(v) >= 0.01],
            key=lambda x: -x["balance"],
        ),
        "pending_unjournalized_total": pending_total,
        "pending_unjournalized_ops": pending,
        "effective_ar": round(ledger_total + pending_total, 2),
        "stored_balances_total": stored_total,
        "stored_top_debtors": sorted(stored, key=lambda x: -x["balance"]),
        "temporary_deferred_entries": temp_entries,
        "temporary_deferred_total": temp_total,
        "temporary_deferred_note": (
            "قيود مؤقتة لبيع آجل (مدين ذمم/دائن إيرادات) — تبقى موسومة حتى التحصيل، "
            "وعند السداد يُحدَّث الوسم إلى مُسوَّى مع قيد تحصيل (مدين نقدية/بنك، دائن ذمم)."
        ),
        "reconciliation_gap": round(stored_total - ledger_total, 2),
        "data_freeze_note": (
            "الأرقام كما هي — مصير العمليات الآجلة بلا قيود وقيود الاختبار قرار للمالك "
            "(أمر علاج L14 بند 4). SSOT المرجعي = دفتر القيود."
        ),
    }
