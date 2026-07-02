"""card_builder — produce structured "cards" in tool results so the frontend
can render them as interactive components inline with the chat reply.

A card is a plain dict with this shape:
    {
        "type": "CustomerCard" | "VehicleCard" | ...,
        "title": "اسم العميل" (string, short),
        "data": {...domain fields...},
        "actions": [
            {"id": "open", "label": "فتح", "intent": "navigate", "target": "/customers/<id>"},
            {"id": "statement", "label": "كشف حساب", "intent": "tool", "tool": "...", "args": {...}},
            ...
        ],
    }

Every read-only tool can attach a list of cards to its result. The kernel
collects them and surfaces them in the final response payload, so the drawer
can render them next to the markdown text.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------- Helpers ----------

def _short(v: Optional[str], n: int = 8) -> str:
    if not v:
        return ""
    return str(v)[:n]


def _sar(amount: Optional[float]) -> str:
    """Format amount in SAR with thousands separator."""
    try:
        return f"{float(amount or 0):,.2f} ر.س"
    except Exception:
        return "0 ر.س"


# ---------- Card factories ----------

def customer_card(customer: Dict[str, Any]) -> Dict[str, Any]:
    cid = customer.get("id") or ""
    name = customer.get("name") or "(بدون اسم)"
    phone = customer.get("phone") or ""
    return {
        "type": "CustomerCard",
        "id": _short(cid, 12),
        "title": name,
        "data": {
            "id": cid,
            "code": _short(cid, 8).upper(),
            "name": name,
            "phone": phone,
            "balance": float(customer.get("ajelBalance") or customer.get("balance") or 0),
            "balance_formatted": _sar(customer.get("ajelBalance") or customer.get("balance") or 0),
            "open_invoices": customer.get("openInvoices") or 0,
            "vehicles_count": customer.get("vehiclesCount") or customer.get("totalVisits") or 0,
            "vehicle_plate": customer.get("vehiclePlate"),
        },
        "actions": [
            {"id": "open", "label": "فتح ملف العميل", "intent": "navigate", "target": f"/customer/{cid}"},
            {"id": "statement", "label": "كشف حساب", "intent": "tool", "tool": "customers.search", "args": {"query": name}},
            {"id": "edit", "label": "تعديل", "intent": "runtime",
             "endpoint": f"/api/customers/{cid}", "method": "PUT"},
            {"id": "collect", "label": "تحصيل", "intent": "navigate", "target": f"/operations?pos=collect&customer={cid}"},
            {"id": "whatsapp", "label": "واتساب", "intent": "runtime",
             "endpoint": "/api/runtime/execute", "method": "POST",
             "body": {"text": f"أرسل واتساب {phone} رسالة تذكير بالمبالغ المستحقة"}},
        ],
    }


def vehicle_card(vehicle: Dict[str, Any]) -> Dict[str, Any]:
    vid = vehicle.get("id") or ""
    plate = vehicle.get("plateNumber") or vehicle.get("plate") or ""
    return {
        "type": "VehicleCard",
        "id": _short(vid, 12),
        "title": f"{plate} — {vehicle.get('brand') or ''} {vehicle.get('model') or ''}".strip(),
        "data": {
            "id": vid,
            "plate": plate,
            "vin": vehicle.get("vin"),
            "brand": vehicle.get("brand"),
            "model": vehicle.get("model"),
            "year": vehicle.get("year"),
            "mileage": vehicle.get("mileage") or vehicle.get("odometer"),
            "owner": vehicle.get("customerName") or vehicle.get("ownerName"),
            "status": vehicle.get("status") or vehicle.get("visitStatus"),
            "last_visit": vehicle.get("lastVisitDate") or vehicle.get("lastVisit"),
        },
        "actions": [
            {"id": "open", "label": "فتح ملف المركبة", "intent": "navigate", "target": f"/vehicle/{vid}"},
            {"id": "visits", "label": "زياراتها", "intent": "navigate", "target": f"/vehicle/{vid}"},
            {"id": "create_visit", "label": "زيارة جديدة", "intent": "runtime",
             "endpoint": "/api/runtime/execute", "method": "POST",
             "body": {"text": f"افتح زيارة للمركبة {plate}"}},
            {"id": "edit", "label": "تعديل", "intent": "runtime",
             "endpoint": f"/api/vehicles/{vid}", "method": "PUT"},
        ],
    }


def invoice_card(operation: Dict[str, Any]) -> Dict[str, Any]:
    """Operation that represents a sale (invoice). Same shape as InvoiceCard."""
    op_id = operation.get("id") or ""
    inv_no = operation.get("invoiceNumber") or operation.get("invoice_no") or f"OP-{_short(op_id,6).upper()}"
    return {
        "type": "InvoiceCard",
        "id": _short(op_id, 12),
        "title": f"فاتورة {inv_no}",
        "data": {
            "id": op_id,
            "invoice_number": inv_no,
            "customer": operation.get("partnerName") or operation.get("customerName") or "",
            "date": operation.get("createdAt") or operation.get("created_at") or operation.get("date"),
            "amount": float(operation.get("total") or 0),
            "amount_formatted": _sar(operation.get("total")),
            "balance": float(operation.get("balance") or operation.get("remainingBalance") or 0),
            "balance_formatted": _sar(operation.get("balance") or operation.get("remainingBalance") or 0),
            "status": operation.get("paymentStatus") or operation.get("payment_status") or "unknown",
            "payment_method": operation.get("paymentMethod") or operation.get("payment_method"),
        },
        "actions": [
            {"id": "preview", "label": "معاينة", "intent": "navigate", "target": f"/operations?focus={op_id}"},
            {"id": "pdf", "label": "PDF", "intent": "navigate", "target": f"/operations?focus={op_id}&print=1"},
            {"id": "receive_payment", "label": "تحصيل", "intent": "runtime",
             "endpoint": f"/api/operations/{op_id}/confirm-payment", "method": "POST",
             "body": {"status": "paid"}},
            {"id": "whatsapp", "label": "واتساب", "intent": "runtime",
             "endpoint": "/api/runtime/execute", "method": "POST",
             "body": {"text": f"أرسل واتساب للعميل فاتورة {inv_no}"}},
        ],
    }


def operation_card(operation: Dict[str, Any]) -> Dict[str, Any]:
    """Generic operation card (for non-sale operations: purchases, expenses, …)."""
    op_id = operation.get("id") or ""
    op_type = operation.get("type") or "operation"
    inv_no = operation.get("invoiceNumber") or operation.get("invoice_number") or ""
    type_label = {
        "sale": "بيع",
        "purchase": "شراء",
        "expense": "مصروف",
        "collection": "تحصيل",
        "payment": "دفع",
    }.get(op_type, op_type)
    return {
        "type": "OperationCard",
        "id": _short(op_id, 12),
        "title": f"{inv_no + ' — ' if inv_no else ''}{type_label} — {_sar(operation.get('total'))}",
        "data": {
            "id": op_id,
            "invoice_number": inv_no,
            "type": op_type,
            "type_label": type_label,
            "amount": float(operation.get("total") or 0),
            "amount_formatted": _sar(operation.get("total")),
            "partner": operation.get("partnerName") or operation.get("customerName") or operation.get("supplierName") or "",
            "date": operation.get("createdAt") or operation.get("created_at") or operation.get("date"),
            "payment_status": operation.get("paymentStatus") or operation.get("payment_status"),
            "payment_method": operation.get("paymentMethod") or operation.get("payment_method"),
        },
        "actions": [
            {"id": "open", "label": "فتح", "intent": "navigate", "target": f"/operations?focus={op_id}"},
            {"id": "audit", "label": "تدقيق", "intent": "tool", "tool": "firewall.operation_integrity"},
            {"id": "delete", "label": "حذف", "intent": "runtime",
             "endpoint": "/api/runtime/execute", "method": "POST",
             "body": {"text": f"احذف العملية {op_id[:8]}"},
             "confirm": "هل أنت متأكد من حذف هذه العملية؟"},
        ],
    }


def supplier_card(supplier: Dict[str, Any]) -> Dict[str, Any]:
    sid = supplier.get("id") or ""
    name = supplier.get("name") or "(بدون اسم)"
    return {
        "type": "SupplierCard",
        "id": _short(sid, 12),
        "title": name,
        "data": {
            "id": sid,
            "name": name,
            "phone": supplier.get("phone"),
            "balance": float(supplier.get("ajelBalance") or supplier.get("balance") or 0),
            "balance_formatted": _sar(supplier.get("ajelBalance") or supplier.get("balance") or 0),
            "category": supplier.get("category"),
            "city": supplier.get("city"),
        },
        "actions": [
            {"id": "open", "label": "فتح ملف المورد", "intent": "navigate", "target": "/suppliers"},
            {"id": "statement", "label": "كشف حساب", "intent": "tool", "tool": "finance.payables_summary"},
            {"id": "whatsapp", "label": "واتساب", "intent": "runtime",
             "endpoint": "/api/runtime/execute", "method": "POST",
             "body": {"text": f"أرسل واتساب {supplier.get('phone') or ''} كشف حساب المورد {name}"}},
        ],
    }


def inventory_card(part: Dict[str, Any]) -> Dict[str, Any]:
    name = part.get("name") or part.get("partName") or "(بدون اسم)"
    sku = part.get("sku") or part.get("partNumber") or ""
    qty = float(part.get("quantity") or part.get("stock") or 0)
    minq = float(part.get("min_quantity") or part.get("minQuantity") or 0)
    in_stock = qty > 0
    return {
        "type": "InventoryCard",
        "id": sku or name,
        "title": f"{name} ({sku})",
        "data": {
            "name": name,
            "sku": sku,
            "category": part.get("category"),
            "quantity": qty,
            "min_quantity": minq,
            "in_stock": in_stock,
            "selling_price": float(part.get("selling_price") or part.get("sellingPrice") or 0),
            "selling_price_formatted": _sar(part.get("selling_price") or part.get("sellingPrice")),
            "shortage": max(0.0, minq - qty),
        },
        "actions": [
            {"id": "open", "label": "فتح القطعة", "intent": "navigate", "target": "/parts"},
            {"id": "reserve", "label": "حجز للعملية", "intent": "navigate", "target": f"/operations?part={sku}"},
        ],
    }


def report_card(report: Dict[str, Any]) -> Dict[str, Any]:
    """Generic report card — used by dashboard items."""
    return {
        "type": "ReportCard",
        "id": report.get("id") or report.get("title") or "report",
        "title": report.get("title") or "تقرير",
        "data": report,
        "actions": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 🆕 Phase 3C.5 — 7 new card types (Visit / Payment / Approval / Audit /
#                                  WhatsApp / Report-detail / Finding)
# ─────────────────────────────────────────────────────────────────────────────


def visit_card(visit: Dict[str, Any]) -> Dict[str, Any]:
    """Visit = vehicle that is currently active (not delivered)."""
    vid = visit.get("id") or "v"
    return {
        "type": "VisitCard",
        "id": str(vid),
        "title": f"زيارة — {visit.get('plate_number') or visit.get('plate') or '?'}",
        "data": {
            "plate": visit.get("plate_number") or visit.get("plate"),
            "status": visit.get("status"),
            "customer_name": visit.get("customer_name"),
            "brand": visit.get("brand"),
            "model": visit.get("model"),
            "entry_date": visit.get("entry_date"),
        },
        "actions": [
            {"id": "open", "label": "فتح", "intent": "navigate", "target": f"/vehicle/{vid}"},
            {"id": "close", "label": "إغلاق الزيارة", "intent": "runtime",
             "endpoint": "/api/runtime/execute", "method": "POST",
             "body": {"text": f"أغلق الزيارة {vid}"}},
        ],
    }


def payment_card(payment: Dict[str, Any]) -> Dict[str, Any]:
    """Payment = a single ledger movement (سند قبض/صرف)."""
    pid = payment.get("id") or "p"
    direction = (payment.get("direction") or payment.get("type") or "").lower()
    return {
        "type": "PaymentCard",
        "id": str(pid),
        "title": f"{'سند قبض' if direction in ('in','receipt','collection') else 'سند صرف'} — {_sar(payment.get('amount'))}",
        "data": {
            "amount": payment.get("amount"),
            "amount_formatted": _sar(payment.get("amount")),
            "direction": direction,
            "party": payment.get("party_name") or payment.get("customer_name") or payment.get("supplier_name"),
            "date": payment.get("date") or payment.get("created_at"),
            "method": payment.get("method"),
            "reference": payment.get("reference"),
        },
        "actions": [
            {"id": "open", "label": "عرض", "intent": "navigate", "target": f"/operations?focus={pid}"},
        ],
    }


def approval_card(approval: Dict[str, Any]) -> Dict[str, Any]:
    """Approval = a runtime approval awaiting (or having received) a decision."""
    aid = approval.get("id") or approval.get("approval_id") or "a"
    status = approval.get("status") or "pending"
    return {
        "type": "ApprovalCard",
        "id": str(aid),
        "title": f"موافقة — {status}",
        "status": status,
        "data": {
            "approval_id": aid,
            "draft_id": approval.get("draft_id"),
            "status": status,
            "requester": approval.get("requester"),
            "approver": approval.get("approver"),
            "created_at": approval.get("created_at"),
        },
        "actions": [
            {"id": "approve", "label": "اعتماد", "intent": "runtime",
             "endpoint": f"/api/runtime/approvals/{aid}/approve", "method": "POST",
             "disabled_when": ["approved", "rejected"]},
            {"id": "reject", "label": "رفض", "intent": "runtime",
             "endpoint": f"/api/runtime/approvals/{aid}/reject", "method": "POST",
             "disabled_when": ["approved", "rejected"]},
            {"id": "view_audit", "label": "تدقيق", "intent": "runtime",
             "endpoint": "/api/runtime/audit", "method": "GET"},
        ],
    }


def audit_card(audit_event: Dict[str, Any]) -> Dict[str, Any]:
    """Audit event = one row from the audit trail."""
    return {
        "type": "AuditCard",
        "id": f"audit-{int((audit_event.get('ts') or 0) * 1000)}",
        "title": f"📜 {audit_event.get('event') or 'AUDIT'}",
        "data": {
            "event": audit_event.get("event"),
            "ts": audit_event.get("ts"),
            "draft_id": audit_event.get("draft_id"),
            "execution_id": audit_event.get("execution_id"),
            "approval_id": audit_event.get("approval_id"),
            "approver": audit_event.get("approver"),
            "proposer": audit_event.get("proposer"),
            "table": audit_event.get("table"),
            "entity_id": audit_event.get("entity_id"),
        },
        "actions": [],
    }


def whatsapp_card(message: Dict[str, Any]) -> Dict[str, Any]:
    """WhatsApp message = preview of an outbound (or MOCKED) WhatsApp send."""
    return {
        "type": "WhatsAppCard",
        "id": message.get("id") or "wa",
        "title": f"📲 واتساب — {message.get('to') or 'غير محدد'}",
        "status": message.get("status") or "queued",
        "data": {
            "to": message.get("to"),
            "message": (message.get("message") or "")[:280],
            "status": message.get("status"),
            "channel": message.get("channel") or "whatsapp",
            "provider": message.get("provider") or "infobip",
            "sent_at": message.get("sent_at") or message.get("ts"),
        },
        "actions": [
            {"id": "view", "label": "تفاصيل", "intent": "navigate", "target": "/debts-followup"},
        ],
    }


def finding_card(finding: Dict[str, Any]) -> Dict[str, Any]:
    """Finding = a single issue surfaced by the AI Auditor / Firewall."""
    severity = (finding.get("severity") or "info").lower()
    return {
        "type": "FindingCard",
        "id": finding.get("id") or f"f-{severity}",
        "title": f"⚠️ {finding.get('title') or 'مشكلة'}",
        "data": {
            "severity": severity,
            "title": finding.get("title"),
            "detail": finding.get("detail") or finding.get("description"),
            "entity_type": finding.get("entity_type"),
            "entity_id": finding.get("entity_id"),
            "suggested_action": finding.get("suggested_action"),
            "discovered_at": finding.get("discovered_at") or finding.get("ts"),
        },
        "actions": (
            [
                {"id": "view", "label": "فتح", "intent": "navigate",
                 "target": finding.get("link") or "/accounting/firewall"},
                {"id": "fix", "label": "تصحيح تلقائي", "intent": "runtime",
                 "endpoint": "/api/operations/integrity/fix-all", "method": "POST",
                 "body": {},
                 "confirm": "سيتم إنشاء قيود محاسبية تلقائية للعمليات المفقودة. متأكد؟"},
            ]
        ),
    }


def detailed_report_card(report: Dict[str, Any]) -> Dict[str, Any]:
    """Rich version of report_card — for assistant-driven analyses."""
    rows = report.get("rows") or []
    return {
        "type": "ReportDetailCard",
        "id": report.get("id") or report.get("title") or "report-detail",
        "title": report.get("title") or "تقرير تفصيلي",
        "data": {
            "title": report.get("title"),
            "summary": report.get("summary"),
            "rows": rows[:10],
            "total_rows": len(rows),
            "kpis": report.get("kpis") or [],
            "period": report.get("period"),
        },
        "actions": [
            {"id": "open", "label": "تقرير كامل", "intent": "navigate",
             "target": report.get("link") or "/accounting/comprehensive"},
        ],
    }


def service_card(service: Dict[str, Any]) -> Dict[str, Any]:
    """🔧 Service card — one row from the services catalog."""
    sid = service.get("id") or "s"
    price = service.get("price")
    duration = service.get("duration_minutes")
    return {
        "type": "ServiceCard",
        "id": str(sid),
        "title": f"🔧 {service.get('name') or 'خدمة'}",
        "data": {
            "name": service.get("name"),
            "category": service.get("category"),
            "price": price,
            "price_formatted": _sar(price) if price is not None else None,
            "duration_minutes": duration,
            "active": service.get("active", True),
        },
        "actions": [
            {"id": "use", "label": "استخدم في زيارة", "intent": "navigate",
             "target": f"/operations?service_id={sid}"},
        ],
    }


# ---------- High-level helpers used by tool handlers ----------

def cards_from_customers(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return [customer_card(r) for r in (rows or [])[:limit]]


def cards_from_vehicles(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return [vehicle_card(r) for r in (rows or [])[:limit]]


def cards_from_operations(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    out = []
    for r in (rows or [])[:limit]:
        if (r.get("type") or "").lower() == "sale":
            out.append(invoice_card(r))
        else:
            out.append(operation_card(r))
    return out


def cards_from_parts(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return [inventory_card(r) for r in (rows or [])[:limit]]


def cards_from_suppliers(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return [supplier_card(r) for r in (rows or [])[:limit]]


# 🆕 Phase 3C.5 — bulk helpers for the new card types
def cards_from_visits(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return [visit_card(r) for r in (rows or [])[:limit]]


def cards_from_payments(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return [payment_card(r) for r in (rows or [])[:limit]]


def cards_from_approvals(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return [approval_card(r) for r in (rows or [])[:limit]]


def cards_from_audit(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return [audit_card(r) for r in (rows or [])[:limit]]


def cards_from_findings(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return [finding_card(r) for r in (rows or [])[:limit]]
