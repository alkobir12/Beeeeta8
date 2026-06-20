"""
💰 routes_financial_actions.py — واجهة REST لأوامر الكتابة المالية عبر المحرك المركزي

كل المسارات تفرض RBAC وتمرّ عبر AccountingEngine (توازن + منع تكرار).

Endpoints
─────────
  POST /api/finance-actions/invoice   — إصدار فاتورة      (RBAC: invoices/journal_entries create)
  POST /api/finance-actions/payment   — تحصيل من عميل     (RBAC: debts.settle / operations.settle)
  POST /api/finance-actions/expense   — تسجيل مصروف       (RBAC: journal_entries create)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Request

from core import financial_actions, rbac
from core.log_utils import get_logger

_log = get_logger("routes.finance_actions")

router = APIRouter(prefix="/api/finance-actions", tags=["finance-actions"])


async def _actor(request: Request, body: Dict[str, Any]) -> rbac.Actor:
    ident = rbac.extract_identity(request, body)
    return await rbac.resolve_actor(user_id=ident["user_id"], name=ident["name"], role_hint=ident["role_hint"])


def _result_or_raise(result: Dict[str, Any]) -> Dict[str, Any]:
    if result.get("posted"):
        return {"success": True, "data": result}
    if result.get("idempotent"):
        # مكرر — نعيد 200 مع توضيح أنه لم يُكرَّر
        return {"success": True, "data": result, "message": result.get("message")}
    raise HTTPException(status_code=400, detail={"error": result.get("error", "post_failed"),
                                                "msg": result.get("detail") or "تعذّر ترحيل القيد"})


@router.post("/invoice")
async def post_invoice(request: Request, payload: Dict[str, Any] = Body(...)):
    actor = await _actor(request, payload)
    allowed = rbac.check_permission(actor, "invoices", "create")
    if not allowed.allowed:
        allowed = rbac.check_permission(actor, "journal_entries", "create")
    rbac.require(allowed)
    customer = (payload.get("customer") or payload.get("party") or "").strip()
    if not customer:
        raise HTTPException(status_code=400, detail={"error": "missing_customer", "msg": "اسم العميل مطلوب"})
    result = financial_actions.create_invoice(
        customer=customer,
        items=payload.get("items"),
        total=payload.get("total"),
        payment_method=payload.get("payment_method") or "credit",
        date=payload.get("date"),
        reference_id=payload.get("reference_id"),
        actor=actor.to_dict(),
    )
    return _result_or_raise(result)


@router.post("/payment")
async def post_payment(request: Request, payload: Dict[str, Any] = Body(...)):
    actor = await _actor(request, payload)
    allowed = rbac.check_permission(actor, "debts", "settle")
    if not allowed.allowed:
        allowed = rbac.check_permission(actor, "operations", "settle")
    rbac.require(allowed)
    customer = (payload.get("customer") or payload.get("party") or "").strip()
    if not customer:
        raise HTTPException(status_code=400, detail={"error": "missing_customer", "msg": "اسم العميل مطلوب"})
    result = financial_actions.collect_payment(
        customer=customer,
        amount=payload.get("amount") or payload.get("total"),
        payment_method=payload.get("payment_method") or "cash",
        date=payload.get("date"),
        reference_id=payload.get("reference_id"),
        actor=actor.to_dict(),
    )
    return _result_or_raise(result)


@router.post("/expense")
async def post_expense(request: Request, payload: Dict[str, Any] = Body(...)):
    actor = await _actor(request, payload)
    rbac.require(rbac.check_permission(actor, "journal_entries", "create"))
    desc = (payload.get("description") or payload.get("desc") or "مصروف").strip()
    result = financial_actions.create_expense(
        description=desc,
        amount=payload.get("amount") or payload.get("total"),
        category=payload.get("category"),
        supplier=payload.get("supplier"),
        payment_method=payload.get("payment_method") or "cash",
        date=payload.get("date"),
        reference_id=payload.get("reference_id"),
        actor=actor.to_dict(),
    )
    return _result_or_raise(result)
