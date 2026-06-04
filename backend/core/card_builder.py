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
    return {
        "type": "CustomerCard",
        "id": _short(cid, 12),
        "title": name,
        "data": {
            "id": cid,
            "code": _short(cid, 8).upper(),
            "name": name,
            "phone": customer.get("phone") or "",
            "balance": float(customer.get("ajelBalance") or customer.get("balance") or 0),
            "balance_formatted": _sar(customer.get("ajelBalance") or customer.get("balance") or 0),
            "open_invoices": customer.get("openInvoices") or 0,
            "vehicles_count": customer.get("vehiclesCount") or customer.get("totalVisits") or 0,
            "vehicle_plate": customer.get("vehiclePlate"),
        },
        "actions": [
            {"id": "open", "label": "فتح ملف العميل", "intent": "navigate", "target": f"/customer/{cid}"},
            {"id": "statement", "label": "كشف حساب", "intent": "tool", "tool": "customers.search", "args": {"query": name}},
            {"id": "whatsapp", "label": "واتساب", "intent": "deferred", "phase": "3D"},
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
            {"id": "create_visit", "label": "زيارة جديدة", "intent": "deferred", "phase": "3C"},
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
            {"id": "pdf", "label": "PDF", "intent": "deferred", "phase": "3D"},
            {"id": "whatsapp", "label": "واتساب", "intent": "deferred", "phase": "3D"},
            {"id": "receive_payment", "label": "تحصيل", "intent": "deferred", "phase": "3C"},
        ],
    }


def operation_card(operation: Dict[str, Any]) -> Dict[str, Any]:
    """Generic operation card (for non-sale operations: purchases, expenses, …)."""
    op_id = operation.get("id") or ""
    op_type = operation.get("type") or "operation"
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
        "title": f"{type_label} — {_sar(operation.get('total'))}",
        "data": {
            "id": op_id,
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
            {"id": "statement", "label": "كشف حساب", "intent": "deferred", "phase": "3B.2"},
            {"id": "whatsapp", "label": "واتساب", "intent": "deferred", "phase": "3D"},
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
            {"id": "reserve", "label": "حجز", "intent": "deferred", "phase": "3C"},
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
