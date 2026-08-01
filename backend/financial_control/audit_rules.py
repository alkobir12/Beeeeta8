"""
🔍 Audit Rules Engine — 7 enterprise audit rules.

Rules produced (each emits zero or more Finding instances):
  1. duplicate_payment       — same op_id paid twice via journal_entries
  2. duplicate_invoice       — two invoices for the same vehicle/visit/period
  3. missing_reference       — operation exists but no journal_entry references it
  4. negative_inventory      — parts.stock < 0 OR negative on_hand
  5. unbalanced_journal      — journal_entry where sum(debit) ≠ sum(credit)
  6. backdated_transaction   — created_at - date > 30 days
  7. future_dated_transaction — date > now + 1 day

Each rule is idempotent: re-running on the same data yields the same signature
→ the FindingsEngine treats it as an update, not a new finding.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from .findings_engine import make_signature
from .models import Finding, FindingSeverity, _now_iso


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dec(v: Any) -> Decimal:
    try:
        return Decimal(str(v if v is not None else 0))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _round_2(v: Any) -> float:
    return float(_to_dec(v).quantize(Decimal("0.01")))


def _parse_iso(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        if isinstance(s, datetime):
            return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
        s2 = str(s).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


class AuditRulesEngine:
    """Pluggable 7-rule audit engine that emits Finding objects."""

    def __init__(self, *, workshop_id: str = "finmodule-sync"):
        self.workshop_id = workshop_id

    # ---------- public ----------
    def run_all(self, ctx: Dict[str, Any]) -> List[Finding]:
        """Run all 7 rules against the provided context dict.

        ctx keys (all optional, default to empty list):
          journals, operations, parts, invoices, visits
        """
        findings: List[Finding] = []
        findings.extend(self.rule_duplicate_payments(ctx.get("journals", [])))
        findings.extend(self.rule_duplicate_invoices(ctx.get("invoices", [])))
        findings.extend(self.rule_missing_reference(ctx.get("operations", []), ctx.get("journals", [])))
        findings.extend(self.rule_negative_inventory(ctx.get("parts", [])))
        findings.extend(self.rule_unbalanced_journal(ctx.get("journals", [])))
        findings.extend(self.rule_backdated(ctx.get("operations", [])))
        findings.extend(self.rule_future_dated(ctx.get("operations", [])))
        return findings

    # ---------- 1. duplicate payments ----------
    def rule_duplicate_payments(self, journals: List[Dict[str, Any]]) -> List[Finding]:
        out: List[Finding] = []
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for j in journals:
            src = str(j.get("source") or "").lower()
            if src not in {"operation_payment"}:
                continue
            ref = str(j.get("reference_id") or "")
            if not ref:
                continue
            groups[ref].append(j)
        for ref, items in groups.items():
            if len(items) < 2:
                continue
            total = sum(_to_dec(j.get("total")) for j in items)
            sig = make_signature(rule_code="duplicate_payment", entity_type="operation", entity_id=ref)
            out.append(Finding(
                workshop_id=self.workshop_id,
                rule_code="duplicate_payment",
                severity=FindingSeverity.CRITICAL,
                title=f"دفعة مكررة لنفس العملية #{ref[:8]}",
                description=f"تم تسجيل {len(items)} قيود دفع لنفس reference_id={ref} بمجموع {_round_2(total)} ر.س.",
                root_cause="إرسال مزدوج لطلب الدفع أو إعادة محاولة قبل تأكيد المعاملة.",
                financial_impact=_round_2(total),
                entity_type="operation",
                entity_id=ref,
                evidence={
                    "operation_id": ref,
                    "journal_ids": [j.get("id") for j in items],
                    "occurrences": len(items),
                    "total_amount": _round_2(total),
                },
                related_entries=[j.get("id") for j in items if j.get("id")],
                signature=sig,
            ))
        return out

    # ---------- 2. duplicate invoices ----------
    def rule_duplicate_invoices(self, invoices: List[Dict[str, Any]]) -> List[Finding]:
        out: List[Finding] = []
        groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        for inv in invoices:
            key = (
                str(inv.get("vehicleId") or inv.get("vehicle_id") or ""),
                str(inv.get("visitId") or inv.get("visit_id") or ""),
                _round_2(inv.get("total") or 0),
            )
            if not (key[0] or key[1]):
                continue
            groups[key].append(inv)
        for key, items in groups.items():
            if len(items) < 2:
                continue
            sig = make_signature(rule_code="duplicate_invoice", entity_type="invoice", entity_id=f"{key[0]}|{key[1]}|{key[2]}")
            out.append(Finding(
                workshop_id=self.workshop_id,
                rule_code="duplicate_invoice",
                severity=FindingSeverity.HIGH,
                title=f"فاتورتان متطابقتان لنفس المركبة/الزيارة بمبلغ {key[2]} ر.س",
                description=f"تم العثور على {len(items)} فواتير بنفس (المركبة، الزيارة، المجموع).",
                root_cause="إعادة إنشاء الفاتورة بعد الحفظ الأول دون حذف الأصلية.",
                financial_impact=key[2],
                entity_type="invoice",
                entity_id=items[0].get("id"),
                evidence={
                    "vehicle_id": key[0],
                    "visit_id": key[1],
                    "amount": key[2],
                    "invoice_ids": [i.get("id") for i in items],
                    "occurrences": len(items),
                },
                related_entries=[i.get("id") for i in items if i.get("id")],
                signature=sig,
            ))
        return out

    # ---------- 3. missing reference ----------
    def rule_missing_reference(self, operations: List[Dict[str, Any]], journals: List[Dict[str, Any]]) -> List[Finding]:
        out: List[Finding] = []
        journal_refs = {str(j.get("reference_id") or "") for j in journals if j.get("reference_id")}
        for op in operations:
            op_id = str(op.get("id") or "")
            if not op_id:
                continue
            t = str(op.get("type") or "").lower()
            if t in {"draft", "quote", "cancelled"}:
                continue
            amount = _to_dec(op.get("total") or 0)
            if amount <= 0:
                continue
            if op_id in journal_refs:
                continue
            sig = make_signature(rule_code="missing_reference", entity_type="operation", entity_id=op_id)
            out.append(Finding(
                workshop_id=self.workshop_id,
                rule_code="missing_reference",
                severity=FindingSeverity.HIGH,
                title=f"عملية بدون قيد محاسبي مرجعي — {t} #{op_id[:8]}",
                description=f"العملية {op_id} من نوع '{t}' بمبلغ {_round_2(amount)} ر.س لا يوجد لها قيد يومية مرتبط.",
                root_cause="انقطاع في pipeline الإرسال إلى ledger، أو إنشاء العملية يدوياً قبل تفعيل القيد.",
                financial_impact=_round_2(amount),
                entity_type="operation",
                entity_id=op_id,
                evidence={
                    "operation_id": op_id,
                    "type": t,
                    "total": _round_2(amount),
                    "created_at": op.get("created_at"),
                    "partner_name": op.get("partner_name"),
                },
                signature=sig,
            ))
        return out

    # ---------- 4. negative inventory ----------
    def rule_negative_inventory(self, parts: List[Dict[str, Any]]) -> List[Finding]:
        out: List[Finding] = []
        for p in parts:
            stock_raw = p.get("stock") if p.get("stock") is not None else p.get("on_hand")
            try:
                stock = float(stock_raw or 0)
            except (ValueError, TypeError):
                continue
            if stock >= 0:
                continue
            sig = make_signature(rule_code="negative_inventory", entity_type="part", entity_id=str(p.get("id") or ""))
            out.append(Finding(
                workshop_id=self.workshop_id,
                rule_code="negative_inventory",
                severity=FindingSeverity.HIGH,
                title=f"مخزون سالب — {p.get('name') or p.get('code') or 'قطعة'}",
                description=f"الرصيد الحالي = {stock}. يدل على بيع بدون استلام أو نقص في تسجيل المشتريات.",
                root_cause="بيع قطعة قبل تسجيل دخولها للمخزن، أو خطأ في صياغة كميات.",
                financial_impact=_round_2(abs(stock) * float(p.get("cost") or p.get("price") or 0)),
                entity_type="part",
                entity_id=str(p.get("id") or ""),
                evidence={
                    "part_id": p.get("id"),
                    "name": p.get("name"),
                    "code": p.get("code"),
                    "stock": stock,
                    "cost": p.get("cost"),
                },
                signature=sig,
            ))
        return out

    # ---------- 5. unbalanced journal ----------
    def rule_unbalanced_journal(self, journals: List[Dict[str, Any]]) -> List[Finding]:
        out: List[Finding] = []
        for j in journals:
            lines = j.get("lines") or []
            if not isinstance(lines, list) or not lines:
                continue
            d = sum(_to_dec(ln.get("debit")) for ln in lines if isinstance(ln, dict))
            c = sum(_to_dec(ln.get("credit")) for ln in lines if isinstance(ln, dict))
            drift = (d - c).copy_abs()
            if drift <= Decimal("0.009"):
                continue
            sig = make_signature(rule_code="unbalanced_journal", entity_type="journal_entry", entity_id=str(j.get("id") or ""))
            out.append(Finding(
                workshop_id=self.workshop_id,
                rule_code="unbalanced_journal",
                severity=FindingSeverity.CRITICAL,
                title=f"قيد غير متوازن — درج {_round_2(drift)} ر.س",
                description=f"مجموع المدين {_round_2(d)} ≠ مجموع الدائن {_round_2(c)}. القيد لا يحترم قاعدة القيد المزدوج.",
                root_cause="تجاوز جدار الحماية أو إدخال يدوي خطأ.",
                financial_impact=_round_2(drift),
                entity_type="journal_entry",
                entity_id=str(j.get("id") or ""),
                evidence={
                    "journal_id": j.get("id"),
                    "debit_total": _round_2(d),
                    "credit_total": _round_2(c),
                    "drift": _round_2(drift),
                    "date": j.get("date"),
                },
                affected_accounts=[str(ln.get("account_name") or ln.get("account") or "?") for ln in lines if isinstance(ln, dict)],
                signature=sig,
            ))
        return out

    # ---------- 6. backdated ----------
    def rule_backdated(self, operations: List[Dict[str, Any]], *, threshold_days: int = 30) -> List[Finding]:
        out: List[Finding] = []
        now = _now()
        for op in operations:
            created = _parse_iso(op.get("created_at"))
            dated = _parse_iso(op.get("date"))
            if not created or not dated:
                continue
            delta = (created - dated).days
            if delta < threshold_days:
                continue
            op_id = str(op.get("id") or "")
            sig = make_signature(rule_code="backdated", entity_type="operation", entity_id=op_id, extra=str(delta))
            out.append(Finding(
                workshop_id=self.workshop_id,
                rule_code="backdated",
                severity=FindingSeverity.MEDIUM,
                title=f"عملية مؤرَّخة قديماً — {delta} يوماً قبل التسجيل",
                description=f"تاريخ العملية {op.get('date')} والإنشاء الفعلي {op.get('created_at')}. الفارق {delta} يوم.",
                root_cause="إدخال متأخر قد يخفي مشكلة في الالتزام بأقفال فترات محاسبية.",
                financial_impact=_round_2(op.get("total") or 0),
                entity_type="operation",
                entity_id=op_id,
                evidence={
                    "operation_id": op_id,
                    "date": op.get("date"),
                    "created_at": op.get("created_at"),
                    "delta_days": delta,
                    "current_now": now.isoformat(),
                },
                signature=sig,
            ))
        return out

    # ---------- 7. future-dated ----------
    def rule_future_dated(self, operations: List[Dict[str, Any]]) -> List[Finding]:
        out: List[Finding] = []
        cutoff = _now() + timedelta(days=1)
        for op in operations:
            dated = _parse_iso(op.get("date"))
            if not dated or dated <= cutoff:
                continue
            op_id = str(op.get("id") or "")
            sig = make_signature(rule_code="future_dated", entity_type="operation", entity_id=op_id)
            future_days = (dated - _now()).days
            out.append(Finding(
                workshop_id=self.workshop_id,
                rule_code="future_dated",
                severity=FindingSeverity.HIGH,
                title=f"عملية بتاريخ مستقبلي — {future_days} يوم من الآن",
                description=f"تاريخ العملية {op.get('date')} يقع في المستقبل. القيد المحاسبي يجب ألا يكون بتاريخ مستقبلي.",
                root_cause="خطأ إدخال أو محاولة تأجيل دفع الإثبات.",
                financial_impact=_round_2(op.get("total") or 0),
                entity_type="operation",
                entity_id=op_id,
                evidence={
                    "operation_id": op_id,
                    "date": op.get("date"),
                    "future_days": future_days,
                },
                signature=sig,
            ))
        return out
