from datetime import datetime, timezone
import json as _json
import uuid
import re


def _sync_visit_journal(supa_service, visit_id: str, op_data: dict, cash_paid: float, total_discount: float, payment_method: str):
    """قيد تلقائي للبيع الآجل + قيود تحصيل — idempotent لكل زيارة (reference_id = visit_id)."""
    from routes_extended import (
        _build_operation_journal_entry,
        _safe_insert_journal_entry,
        _sem_code,
        ACCOUNT_NAME_MAP,
    )
    import os as _os

    workshop_id = _os.environ.get("DEFAULT_WORKSHOP_ID", "finmodule-sync")
    total = float(op_data.get("total") or 0)
    if total <= 0:
        return

    op_view = {
        "id": visit_id,
        "type": op_data.get("type") or "service",
        "vehicleId": op_data.get("vehicle_id"),
        "scope": "vehicle",
        "items": op_data.get("items") or [],
        "total": total,
        "paymentMethod": op_data.get("payment_method"),
        "paymentStatus": op_data.get("payment_status"),
        "partnerName": op_data.get("partner_name"),
        "notes": op_data.get("notes"),
        "date": op_data.get("op_date"),
        "source": op_data.get("source"),
    }

    client = supa_service.client
    existing = (
        client.table("journal_entries").select("id,total,source,lines")
        .eq("reference_id", visit_id).execute().data or []
    )
    accrual_rows = [e for e in existing if str(e.get("source") or "") == "operation"]
    payment_rows = [e for e in existing if str(e.get("source") or "") in {"operation_payment", "visit_receipt_voucher"}]

    _AR_CODES = {"005", "1103", "113"}

    def _ar_debit_of(rows):
        total_ar = 0.0
        for e in rows:
            lines = e.get("lines")
            if isinstance(lines, str):
                try:
                    lines = _json.loads(lines)
                except Exception:
                    lines = []
            for ln in lines or []:
                code = str(ln.get("code") or ln.get("account") or "")
                if code in _AR_CODES:
                    total_ar += float(ln.get("debit") or 0)
        return round(total_ar, 2)

    def _post_accrual():
        entry = _build_operation_journal_entry(op_view, workshop_id)
        if isinstance(entry, list):
            for e in entry:
                _safe_insert_journal_entry(supa_service, e)
        elif entry:
            _safe_insert_journal_entry(supa_service, entry)

    if not accrual_rows:
        _post_accrual()
        existing = (
            client.table("journal_entries").select("id,total,source,lines")
            .eq("reference_id", visit_id).execute().data or []
        )
        accrual_rows = [e for e in existing if str(e.get("source") or "") == "operation"]
    else:
        prev_total = round(sum(float(e.get("total") or 0) for e in accrual_rows), 2)
        if abs(prev_total - round(total, 2)) > 0.009:
            raise RuntimeError(
                f"visit_accrual_mismatch_requires_review:{visit_id}:existing={prev_total}:new={round(total, 2)}"
            )

    # ⛔ قيد التحصيل فقط إن كان قيد البيع مديناً بالذمم (بيع آجل) — وبسقف مدين الذمم
    ar_debit = _ar_debit_of(accrual_rows)
    if ar_debit <= 0.009:
        return

    target_reduction = round(max(float(cash_paid or 0), 0.0) + max(float(total_discount or 0), 0.0), 2)
    already_journaled = round(sum(float(e.get("total") or 0) for e in payment_rows), 2)
    delta = round(min(target_reduction, ar_debit) - already_journaled, 2)
    if delta > 0.009:
        m = str(payment_method or "").strip().lower()
        if float(cash_paid or 0) <= 0 and float(total_discount or 0) > 0:
            debit_code = _sem_code("sales_discount", "035")
        elif m in ("transfer", "bank"):
            debit_code = _sem_code("bank", "004")
        elif m in ("pos", "card", "mada", "visa", "mastercard"):
            debit_code = _sem_code("pos", "006")
        else:
            debit_code = _sem_code("cash", "003")
        ar_code = _sem_code("ar", "005")
        entry = {
            "id": str(uuid.uuid4()),
            "date": datetime.now(timezone.utc).isoformat(),
            "description": f"تحصيل دفعة زيارة — {op_data.get('partner_name') or 'عميل'}",
            "lines": [
                {"account": debit_code, "account_name": ACCOUNT_NAME_MAP.get(debit_code, debit_code), "debit": delta, "credit": 0},
                {"account": ar_code, "account_name": ACCOUNT_NAME_MAP.get(ar_code, "ذمم مدينة"), "debit": 0, "credit": delta},
            ],
            "total": delta,
            "source": "operation_payment",
            "reference_id": visit_id,
            "transaction_type": "payment",
            "workshop_id": workshop_id,
        }
        _safe_insert_journal_entry(supa_service, entry)

async def _sync_visit_to_operation(visit_id: str, visit_data: dict, supa_service=None):
    """
    Sync visit items to a financial operation (Invoice).
    If items exist in visit.notes, create/update an operation so it appears in Finance.
    """
    try:
        # 1. Parse items from notes
        notes_raw = visit_data.get("notes")
        items = []
        payments = []
        visit_number = None
        notes_payment_method = None
        notes_payment_status = None
        if notes_raw:
            try:
                if isinstance(notes_raw, str) and notes_raw.strip().startswith("{"):
                    import json
                    parsed = json.loads(notes_raw)
                    items = parsed.get("items", [])
                    payments = parsed.get("payments", []) or []
                    visit_number = parsed.get("visitNumberDisplay") or parsed.get("visitNumber") or parsed.get("visit_number")
                    notes_payment_method = parsed.get("paymentMethod") or parsed.get("payment_method")
                    notes_payment_status = parsed.get("paymentStatus") or parsed.get("payment_status")
                elif isinstance(notes_raw, dict):
                    items = notes_raw.get("items", [])
                    payments = notes_raw.get("payments", []) or []
                    visit_number = notes_raw.get("visitNumberDisplay") or notes_raw.get("visitNumber") or notes_raw.get("visit_number")
                    notes_payment_method = notes_raw.get("paymentMethod") or notes_raw.get("payment_method")
                    notes_payment_status = notes_raw.get("paymentStatus") or notes_raw.get("payment_status")
            except Exception:
                pass
        
        if not items:
            return # No items to sync

        # 2. Calculate totals with strict separation
        total_workshop = 0.0
        total_suppliers = 0.0
        for i in items:
            line_total = float(i.get("total", 0) or 0) or (float(i.get("price", 0) or 0) * float(i.get("quantity", 1) or 1))
            item_type = str(i.get("itemType") or i.get("type") or "").strip().lower()
            if item_type == "supplier":
                total_suppliers += line_total
            else:
                total_workshop += line_total

        total = total_workshop

        # 2.b. Calculate total paid from payments (including discount entries which reduce customer debt)
        total_paid = 0.0
        total_discount = 0.0
        for p in (payments or []):
            try:
                amount = float(p.get("amount", 0) or 0)
            except Exception:
                amount = 0.0
            if amount <= 0:
                continue
            kind = str(p.get("kind") or p.get("type") or "payment").strip().lower()
            if kind in {"refund", "return"}:
                total_paid -= amount
            elif kind == "discount":
                total_discount += amount
            else:
                total_paid += amount

        # رصيد الورشة المتبقي بعد الدفعات + الخصم
        net_paid = total_paid + total_discount  # كلاهما يخفض ذمم العميل
        remaining_balance = max(0.0, total - net_paid)

        # 3. Prepare Operation Data
        vehicle_id = visit_data.get("vehicleId") or visit_data.get("vehicle_id")
        
        # We need vehicle info for partner name (Customer)
        partner_name = "عميل"
        if supa_service and vehicle_id:
            try:
                # Try to fetch vehicle to get customer name
                v_res = supa_service.client.table("vehicles").select("customer_name").eq("id", vehicle_id).single().execute()
                if v_res.data:
                    partner_name = v_res.data.get("customer_name") or "عميل"
            except Exception:
                pass

        # FIX: حساب payment_status من المدفوعات الفعلية (وليس من قيمة الحقل المفقود في الزيارة)
        if total <= 0.01:
            computed_payment_status = "paid"
        elif net_paid >= total - 0.01:
            computed_payment_status = "paid"
        elif net_paid > 0.01:
            computed_payment_status = "partial"
        else:
            computed_payment_status = "unpaid"

        explicit_status = visit_data.get("payment_status") or visit_data.get("paymentStatus") or notes_payment_status
        # نُعطي الأولوية للحساب الفعلي عند توفر مدفوعات
        if net_paid > 0.01:
            payment_status = computed_payment_status
        else:
            payment_status = explicit_status or computed_payment_status

        raw_payment_method = (
            visit_data.get("payment_method")
            or visit_data.get("paymentMethod")
            or notes_payment_method
            or ((payments or [])[-1].get("method") if payments else None)
            or ((payments or [])[-1].get("payment_method") if payments else None)
        )

        normalized_method = str(raw_payment_method or "").strip().lower()
        if normalized_method in {"تحويل", "bank_transfer", "transfer", "bank"}:
            payment_method = "transfer"
        elif normalized_method in {"بطاقة", "card", "pos", "mada", "visa", "mastercard"}:
            payment_method = "card"
        elif normalized_method in {"نقد", "نقدي", "cash"}:
            payment_method = "cash"
        elif normalized_method == "discount":
            # خصم فقط بدون دفع نقدي
            payment_method = "cash" if payment_status == "paid" else "credit"
        else:
            payment_method = "cash" if payment_status == "paid" else "credit"

        op_data = {
            "id": visit_id,
            "type": "service",
            "items": items,
            "total": total,
            "subtotal": total,
            "workshop_total": total_workshop,
            "supplier_archive_total": total_suppliers,
            "total_combined": total_workshop + total_suppliers,
            "total_paid": round(net_paid, 2),
            "remaining_balance": round(remaining_balance, 2),
            "total_discount": round(total_discount, 2),
            "vehicle_id": vehicle_id,
            "visit_id": visit_id,
            "partner_name": partner_name,
            "partner_type": "customer",
            "payment_method": payment_method,
            "payment_status": payment_status,
            "scope": "vehicle",
            "source": "vehicle_visit_sync",
            "business_unit": "workshop",
            "notes": f"عملية من الزيارة {str(visit_number or '').zfill(3) if visit_number else visit_id[:8]}",
            "op_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # 4. Upsert Operation
        if supa_service:
            # Upsert using visit_id as operation id.
            # Some preview/prod Supabase schemas may miss optional columns.
            # Retry safely by removing unknown columns reported by PostgREST.
            payload = dict(op_data)
            for _ in range(12):
                try:
                    supa_service.client.table("operations").upsert(payload).execute()
                    print(f"✅ Synced Visit {visit_id} -> Upsert Operation {visit_id}")
                    break
                except Exception as sync_error:
                    message = str(sync_error)
                    missing_match = re.search(r"Could not find the '([^']+)' column", message)
                    if not missing_match:
                        raise
                    missing_column = missing_match.group(1)
                    if missing_column not in payload:
                        raise
                    payload.pop(missing_column, None)
                    print(f"⚠️ Sync retry without missing column: {missing_column}")
            # 🏦 مسار كتابة موحد: كل زيارة ببنود تُنشئ/تحدّث قيودها (بيع آجل + تحصيلات)
            try:
                _sync_visit_journal(supa_service, visit_id, op_data, total_paid, total_discount, payment_method)
            except Exception as je_error:
                print(f"⚠️ Visit journal sync failed for {visit_id}: {je_error}")
                raise
            # 🧹 إبطال كاش الحسابات المالية فوراً حتى تعكس الصفحات الأرقام الجديدة
            try:
                import perf_cache
                for ns in ("ops_for_partner_fin", "op_payment_map", "partner_fin_map", "vehicle_customer_lookup", "visits_for_financials"):
                    perf_cache.invalidate(ns)
            except Exception:
                pass
        
        # MongoDB support (Legacy)
        else:
            global db
            if db:
                existing = await db.operations.find_one({"visitId": visit_id})
                if existing:
                    await db.operations.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {
                            "items": items,
                            "total": total,
                            "subtotal": total,
                            "totalPaid": round(net_paid, 2),
                            "remainingBalance": round(remaining_balance, 2),
                            "totalDiscount": round(total_discount, 2),
                            "paymentMethod": payment_method,
                            "paymentStatus": payment_status,
                            "updatedAt": datetime.utcnow()
                        }}
                    )
                else:
                    op_data["id"] = str(uuid.uuid4())
                    op_data["visitId"] = visit_id
                    op_data["vehicleId"] = vehicle_id
                    op_data["visitId"] = visit_id
                    op_data["partnerName"] = partner_name
                    op_data["partnerType"] = "customer"
                    op_data["paymentMethod"] = payment_method
                    op_data["paymentStatus"] = payment_status
                    op_data["totalPaid"] = round(net_paid, 2)
                    op_data["remainingBalance"] = round(remaining_balance, 2)
                    op_data["totalDiscount"] = round(total_discount, 2)
                    op_data["scope"] = "vehicle"
                    op_data["source"] = "vehicle_visit_sync"
                    op_data["businessUnit"] = "workshop"
                    op_data["date"] = datetime.utcnow()
                    op_data["createdAt"] = datetime.utcnow()
                    # Remove snake_case keys for Mongo if needed, or keep for compatibility
                    await db.operations.insert_one(op_data)

    except Exception as e:
        print(f"⚠️ Failed to sync visit to operation: {e}")
        raise

