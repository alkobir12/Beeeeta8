from fastapi import APIRouter, HTTPException, Body, Request, Query
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from collections import defaultdict
import json
import uuid
import os
import io
import re
import base64
import mimetypes

# Optional deps used in some endpoints
try:
    import openpyxl
except Exception:
    openpyxl = None
try:
    import xlsxwriter
except Exception:
    xlsxwriter = None
try:
    import pdfplumber
except Exception:
    pdfplumber = None

from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from bulk_delete_audit import record_bulk_delete_event
from supabase_service import SupabaseService
import firewall_state
import perf_cache as _perf_cache


def _request_actor_name(request: Optional[Request]) -> str:
    if request is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        from core import rbac
        ident = rbac.extract_identity(request)
        if not ident.get("user_id"):
            raise HTTPException(status_code=401, detail="Not authenticated")
        return str(ident.get("name") or ident.get("user_id"))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Not authenticated") from exc


def _external_approval_response(*, action: str, payload: Dict[str, Any], proposer: str) -> JSONResponse:
    from core import action_runtime
    draft = action_runtime.create_draft(
        action=action,
        payload=payload,
        proposer=proposer,
        original_input=payload.get("notes") or payload.get("description"),
        entry_channel="system_page",
    )
    approval = action_runtime.request_approval(draft_id=draft["id"], requester=proposer)
    return JSONResponse(
        status_code=202,
        content={
            "success": True,
            "status": "pending_approval",
            "message": "بانتظار اعتماد طرف ثانٍ قبل الترحيل",
            "draft_id": draft["id"],
            "approval_id": approval.get("approval_id"),
        },
    )


def _external_draft_is_approved(payload: Dict[str, Any]) -> Optional[str]:
    draft_id = str(payload.pop("_approved_external_draft", "") or "").strip()
    if not draft_id:
        return None
    from core import action_runtime
    if not action_runtime.has_human_approval(draft_id):
        raise HTTPException(status_code=403, detail="human approval required")
    return draft_id


def _invalidate_ops_caches() -> None:
    """Drop all caches that depend on operations data, called after any operation mutation."""
    _perf_cache.invalidate("ops_list")
    _perf_cache.invalidate("ops_for_partner_fin")
    _perf_cache.invalidate("op_payment_map")
    _perf_cache.invalidate("partner_fin_map")

from visit_sync import _sync_visit_to_operation
router = APIRouter(prefix="/api")

db = None
templates_bucket: Optional[AsyncIOMotorGridFSBucket] = None


# --------------------- Memory Helper ---------------------
def _mem_read(name: str) -> list:
    try:
        p = os.path.join(os.path.dirname(__file__), "uploads", f"{name}.json")
        if not os.path.exists(p):
            return []
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _mem_write(name: str, items: list):
    try:
        d = os.path.join(os.path.dirname(__file__), "uploads")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{name}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _safe_filename(value: str) -> str:
    raw = re.sub(r"[^\w.\-]+", "_", str(value or "").strip())
    return raw[:120] or f"receipt_{uuid.uuid4().hex[:8]}.bin"


def _save_operation_payment_receipt(op_id: str, receipt_payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if not isinstance(receipt_payload, dict):
        return None

    base64_value = str(receipt_payload.get("base64") or receipt_payload.get("data") or "").strip()
    if not base64_value:
        return None

    mime_type = str(receipt_payload.get("mimeType") or receipt_payload.get("type") or "application/octet-stream")
    original_name = str(receipt_payload.get("name") or "receipt.bin")

    if base64_value.startswith("data:"):
        try:
            header, body = base64_value.split(",", 1)
            if ";base64" in header:
                mime_candidate = header.split(";")[0].replace("data:", "").strip()
                if mime_candidate:
                    mime_type = mime_candidate
            base64_value = body
        except Exception:
            return None

    try:
        binary = base64.b64decode(base64_value, validate=False)
    except Exception:
        return None

    if not binary:
        return None

    # 6MB hard cap for safety
    if len(binary) > 6 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="receipt file too large (max 6MB)")

    ext = os.path.splitext(original_name)[1].strip().lower()
    if not ext:
        ext = mimetypes.guess_extension(mime_type) or ".bin"
    filename = _safe_filename(f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}")

    base_dir = os.path.join(os.path.dirname(__file__), "uploads", "operation_payment_receipts", op_id)
    os.makedirs(base_dir, exist_ok=True)
    file_path = os.path.join(base_dir, filename)

    with open(file_path, "wb") as f:
        f.write(binary)

    return {
        "filename": filename,
        "mime_type": mime_type,
        "url": f"/api/operations/{op_id}/payment-receipts/{filename}",
    }


# --------------------- DB bind ---------------------


def set_db(database):
    global db, templates_bucket
    db = database
    # Only initialize GridFS bucket when we have a valid MongoDB database.
    try:
        if db is not None:
            templates_bucket = AsyncIOMotorGridFSBucket(
                db, bucket_name="invoice_templates"
            )
        else:
            templates_bucket = None
    except Exception as e:
        templates_bucket = None
        print(f"GridFS bucket init failed: {e}")


def _extract_request_actor(request: Optional[Request]) -> Dict[str, str]:
    # 🔐 سمات التدقيق تُشتقّ من JWT الموقَّع (لا الترويسات القابلة للانتحال)
    ident = {}
    try:
        from auth_jwt import identity_from_request
        ident = identity_from_request(request) if request else {}
    except Exception:
        ident = {}
    user_id = str(ident.get("username") or "system").strip() or "system"
    user_role = str(ident.get("role") or "unknown").strip() or "unknown"
    return {"user_id": user_id, "user_role": user_role}


async def _require_request_permission(request: Request, module: str, action: str):
    from core import rbac

    ident = rbac.extract_identity(request)
    actor = await rbac.resolve_actor(
        user_id=ident.get("user_id"),
        name=ident.get("name"),
        role_hint=ident.get("role_hint"),
    )
    if not actor.found or not actor.active:
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "msg": "المستخدم غير موجود أو غير نشط"})
    rbac.require(rbac.check_permission(actor, module, action))
    return actor


async def _require_finance_payment_permission(request: Request):
    from core import rbac

    ident = rbac.extract_identity(request)
    actor = await rbac.resolve_actor(
        user_id=ident.get("user_id"),
        name=ident.get("name"),
        role_hint=ident.get("role_hint"),
    )
    if not actor.found or not actor.active:
        raise HTTPException(status_code=403, detail={"error": "permission_denied", "msg": "المستخدم غير موجود أو غير نشط"})
    allowed = (
        actor.can("debts", "settle")
        or actor.can("operations", "settle")
        or actor.can("journal_entries", "create")
        or actor.can("journal_entries", "pos")
    )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={"error": "permission_denied", "msg": "لا تملك صلاحية تأكيد الدفعات", "role": actor.role},
        )
    return actor



# --------------------- Business Accounts ---------------------
@router.get("/biz-accounts")
async def list_biz_accounts():
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            return supa.accounts_list()
        if provider == "memory" or db is None:
            # وضع معاينة بدون قاعدة بيانات حقيقية – الحفظ في ملف JSON داخل uploads
            return _mem_read("business_accounts")

        # استخدام Projection وحد لعدد النتائج لتحسين الأداء
        docs = (
            await db.business_accounts.find(
                {},
                {
                    "_id": 0,
                    "id": 1,
                    "name": 1,
                    "code": 1,
                    "currency": 1,
                    "createdAt": 1,
                },
            )
            .sort("createdAt", -1)
            .limit(500)
            .to_list(500)
        )
        out = []
        for d in docs:
            created_at = d.get("createdAt")
            out.append(
                {
                    "id": d.get("id"),
                    "name": d.get("name"),
                    "code": d.get("code"),
                    "currency": d.get("currency") or "SAR",
                    "createdAt": (
                        created_at.isoformat()
                        if hasattr(created_at, "isoformat")
                        else created_at
                    ),
                }
            )
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/biz-accounts")
async def create_biz_account(payload: Dict[str, Any] = Body(...)):
    try:
        name = (payload or {}).get("name")
        code = (payload or {}).get("code") or (name or "")[:4].upper()
        currency = (payload or {}).get("currency") or "SAR"
        if not name:
            raise HTTPException(status_code=400, detail="name required")

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            return supa.accounts_create(name=name, code=code, currency=currency)
        if provider == "memory" or db is None:
            # وضع معاينة: حفظ في ملف JSON داخل uploads/business_accounts.json
            doc = {
                "id": str(uuid.uuid4()),
                "name": name,
                "code": code,
                "currency": currency,
                "createdAt": datetime.utcnow().isoformat(),
            }
            items = _mem_read("business_accounts")
            items.append(doc)
            _mem_write("business_accounts", items)
            return doc

        # ensure unique code if exists (Mongo)
        exist = await db.business_accounts.find_one({"code": code})
        if exist:
            code = f"{code}-{str(uuid.uuid4())[:4].upper()}"
        doc = {
            "id": str(uuid.uuid4()),
            "name": name,
            "code": code,
            "currency": currency,
            "createdAt": datetime.utcnow(),
        }
        await db.business_accounts.insert_one(doc)
        doc.pop("_id", None)
        doc["createdAt"] = doc["createdAt"].isoformat()
        return doc
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------- Budgets ---------------------
@router.get("/budgets")
async def list_budgets(account_id: Optional[str] = None, period: Optional[str] = None):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            return supa.budgets_list(account_id, period)

        q = {}
        if account_id:
            q["accountId"] = account_id
        if period:
            q["period"] = period
        items = await db.budgets.find(q).sort("period", -1).to_list(1000)
        for it in items:
            it.pop("_id", None)
        return items
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budgets")
async def create_budget(payload: Dict[str, Any] = Body(...)):
    try:
        account_id = payload.get("accountId")
        if not account_id:
            raise HTTPException(status_code=400, detail="accountId required")

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            return supa.budgets_create(payload)

        doc = {
            "id": str(uuid.uuid4()),
            "accountId": account_id,
            "period": payload.get("period") or datetime.utcnow().strftime("%Y-%m"),
            "incomeTarget": float(payload.get("incomeTarget") or 0),
            "expenseTarget": float(payload.get("expenseTarget") or 0),
            "notes": payload.get("notes") or "",
            "createdAt": datetime.utcnow(),
        }
        await db.budgets.insert_one(doc)
        doc.pop("_id", None)
        return doc
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------- Branch Cleanup (Keep only 2) ---------------------
@router.post("/biz-accounts/cleanup")
async def cleanup_biz_accounts(request: Request, keep: int = 2, mode: str = "hard"):
    """Delete all branches and keep only N (default 2) most recent.
    mode: 'hard' = physical delete, 'soft' = set {'archived': True, 'active': False}
    Ensures at least 2 accounts exist by creating defaults if needed.
    """
    try:
        await _require_request_permission(request, "settings", "edit")
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        keep = max(0, int(keep or 2))

        if provider == "supabase":
            supa = SupabaseService()
            # لجعل السلوك بسيط في Supabase: نحذف كل شيء ونحتفظ بعدد N الأحدث
            rows = supa.accounts_list()
            to_keep = [r["id"] for r in rows[:keep] if r.get("id")]
            to_drop = [r["id"] for r in rows[keep:] if r.get("id")]
            if to_drop:
                if mode == "soft":
                    # لا يوجد archived في السكيمة الحالية، نستخدم active=False كبديل
                    supa.client.table("business_accounts").update(
                        {"active": False}
                    ).in_("id", to_drop).execute()
                else:
                    supa.client.table("business_accounts").delete().in_(
                        "id", to_drop
                    ).execute()
            # ضمان وجود فرعين على الأقل
            created = []
            remain_count = len(to_keep)
            while remain_count < 2:
                base_code = "ACC" if remain_count == 0 else f"BR{remain_count+1:02d}"
                doc = {
                    "name": (
                        "Main Workshop"
                        if remain_count == 0
                        else f"Branch {remain_count+1}"
                    ),
                    "code": base_code,
                    "currency": "SAR",
                }
                res = supa.client.table("business_accounts").insert(doc).execute()
                row = (res.data or [{}])[0]
                created.append({"id": row.get("id"), "name": row.get("name")})
                to_keep.append(row.get("id"))
                remain_count += 1
            return {"status": "ok", "kept": to_keep, "created": created, "final": []}

        if provider == "memory" or db is None:
            # في وضع المعاينة لا نقوم بأي حذف حقيقي
            return {"status": "ok", "kept": [], "created": [], "final": []}

        # Mongo behavior (قديم)
        # Sort by updatedAt desc then createdAt desc
        docs = (
            await db.business_accounts.find({})
            .sort([("updatedAt", -1), ("createdAt", -1)])
            .to_list(length=5000)
        )
        to_keep = [d.get("id") for d in docs[:keep] if d.get("id")]
        to_drop = [d.get("id") for d in docs[keep:] if d.get("id")]
        if to_drop:
            if mode == "soft":
                await db.business_accounts.update_many(
                    {"id": {"$in": to_drop}},
                    {
                        "$set": {
                            "archived": True,
                            "active": False,
                            "updatedAt": datetime.utcnow(),
                        }
                    },
                )
            else:
                await db.business_accounts.delete_many({"id": {"$in": to_drop}})
        # Ensure at least 2 exist
        remain_count = await db.business_accounts.count_documents(
            {"archived": {"$ne": True}}
        )
        created = []
        while remain_count < 2:
            base_code = "ACC" if remain_count == 0 else f"BR{remain_count+1:02d}"
            doc = {
                "id": str(uuid.uuid4()),
                "name": (
                    "Main Workshop" if remain_count == 0 else f"Branch {remain_count+1}"
                ),
                "code": base_code,
                "currency": "SAR",
                "createdAt": datetime.utcnow(),
            }
            await db.business_accounts.insert_one(doc)
            created.append({"id": doc["id"], "name": doc["name"]})
            remain_count += 1
        # return final state (2 accounts)
        final_docs = (
            await db.business_accounts.find({"archived": {"$ne": True}})
            .sort([("updatedAt", -1), ("createdAt", -1)])
            .to_list(length=10)
        )
        for d in final_docs:
            d.pop("_id", None)
            if d.get("createdAt") and hasattr(d["createdAt"], "isoformat"):
                d["createdAt"] = d["createdAt"].isoformat()
            if d.get("updatedAt") and hasattr(d["updatedAt"], "isoformat"):
                d["updatedAt"] = d["updatedAt"].isoformat()
        return {
            "status": "ok",
            "kept": to_keep,
            "created": created,
            "final": final_docs[:2],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------- Pending Operations (Vehicles awaiting action) ---------------------
@router.get("/operations/pending")
async def operations_pending(
    status: Optional[str] = None, technician_id: Optional[str] = None
):
    """Return list of vehicles considered 'pending' = not ready/delivered.
    Optional filter by single status or technician_id.
    """
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            vehs = supa.vehicles_list()
            pending_statuses = ["diagnosis", "quotation", "repair"]
            vehs = [v for v in vehs if v.get("status") in pending_statuses]
            if status and status != "all":
                vehs = [v for v in vehs if v.get("status") == status]
            if technician_id:
                vehs = [v for v in vehs if v.get("technicianId") == technician_id]
            return {"count": len(vehs), "items": vehs}

        if provider == "memory" or db is None:
            vrows = _mem_read("vehicles")
            pending = [
                v
                for v in vrows
                if v.get("status") in ["diagnosis", "quotation", "repair"]
            ]
            return {"count": len(pending), "items": pending}

        pending_statuses = ["diagnosis", "quotation", "repair"]
        q: Dict[str, Any] = {"status": {"$in": pending_statuses}}
        if status:
            if status == "all":
                pass
            else:
                q["status"] = status
        if technician_id:
            q["technicianId"] = technician_id
        fields = {
            "_id": 0,
            "id": 1,
            "plateNumber": 1,
            "brand": 1,
            "model": 1,
            "year": 1,
            "status": 1,
            "technicianId": 1,
            "technicianName": 1,
            "entryDate": 1,
            "estimatedCompletion": 1,
            "customerName": 1,
            "customerPhone": 1,
        }
        docs = (
            await db.vehicles.find(q, fields).sort("entryDate", -1).to_list(length=2000)
        )
        for d in docs:
            for k in ("entryDate", "estimatedCompletion"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
        return {"count": len(docs), "items": docs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations/analytics/pending")
async def operations_pending_analytics():
    """Summary counts for pending vehicles and overdue stats."""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            vehs = supa.vehicles_list()
            pending_statuses = ["diagnosis", "quotation", "repair"]
            vehs = [v for v in vehs if v.get("status") in pending_statuses]
            by_status = {s: 0 for s in pending_statuses}
            overdue = 0
            now = datetime.utcnow()
            for v in vehs:
                st = v.get("status")
                if st in by_status:
                    by_status[st] += 1
                est = v.get("estimatedCompletion")
                if est:
                    try:
                        dt = datetime.fromisoformat(est.replace("Z", "+00:00"))
                        if dt.tzinfo:
                            dt = dt.replace(tzinfo=None)
                        if dt < now:
                            overdue += 1
                    except Exception:
                        pass
            return {"total": len(vehs), "byStatus": by_status, "overdue": overdue}

        if provider == "memory" or db is None:
            vrows = _mem_read("vehicles")
            by = {"diagnosis": 0, "quotation": 0, "repair": 0}
            for v in vrows:
                st = v.get("status")
                if st in by:
                    by[st] += 1
            return {"total": sum(by.values()), "byStatus": by, "overdue": 0}

        pending_statuses = ["diagnosis", "quotation", "repair"]
        now = datetime.utcnow()
        fields = {"_id": 0, "status": 1, "estimatedCompletion": 1}
        docs = await db.vehicles.find(
            {"status": {"$in": pending_statuses}}, fields
        ).to_list(length=20000)
        by_status: Dict[str, int] = {s: 0 for s in pending_statuses}
        overdue = 0
        for d in docs:
            st = d.get("status")
            if st in by_status:
                by_status[st] += 1
            est = d.get("estimatedCompletion")
            if est and hasattr(est, "isoformat"):
                # est is datetime
                if est < now:
                    overdue += 1
        total = len(docs)
        return {"total": total, "byStatus": by_status, "overdue": overdue}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/biz-accounts/{aid}")
async def update_biz_account(aid: str, payload: Dict[str, Any] = Body(...)):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()

            upd = {}
            for k in ("name", "currency", "isActive", "code"):
                if (payload or {}).get(k) is not None:
                    upd[k] = payload[k]

            if not upd:
                return {"status": "no_changes"}

            res = (
                supa.client.table("business_accounts")
                .update(upd)
                .eq("id", aid)
                .execute()
            )
            if not res.data:
                raise HTTPException(status_code=404, detail="not found")

            return res.data[0]

        # MongoDB fallback
        upd = {}
        for k in ("name", "currency"):
            if (payload or {}).get(k) is not None:
                upd[k] = payload[k]
        if not upd:
            return {"status": "no_changes"}
        await db.business_accounts.update_one(
            {"id": aid}, {"$set": {**upd, "updatedAt": datetime.utcnow()}}
        )
        d = await db.business_accounts.find_one({"id": aid})
        if not d:
            raise HTTPException(status_code=404, detail="not found")
        d.pop("_id", None)
        if d.get("createdAt") and hasattr(d["createdAt"], "isoformat"):
            d["createdAt"] = d["createdAt"].isoformat()
        if d.get("updatedAt") and hasattr(d["updatedAt"], "isoformat"):
            d["updatedAt"] = d["updatedAt"].isoformat()
        return d
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/biz-accounts/{aid}")
async def delete_biz_account(aid: str, request: Request):
    try:
        await _require_request_permission(request, "settings", "edit")
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()
            existing = (
                supa.client.table("business_accounts")
                .select("id")
                .eq("id", aid)
                .limit(1)
                .execute()
                .data
                or []
            )
            if not existing:
                raise HTTPException(status_code=404, detail="not found")

            supa.client.table("business_accounts").delete().eq("id", aid).execute()
            return {"status": "ok", "deleted": 1}

        if provider == "memory" or db is None:
            return {"status": "ok", "deleted": 0}

        res = await db.business_accounts.delete_one({"id": aid})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="not found")
        return {"status": "ok", "deleted": int(res.deleted_count)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------- COA ---------------------
DEFAULT_COA = {
    "Assets": {"Current Assets": ["Cash", "Bank"], "Fixed Assets": ["Equipment"]},
    "Liabilities": {"Current Liabilities": ["Accounts Payable"]},
    "Equity": {"Owner Equity": []},
    "Income": {"Sales": ["Services Income", "Parts Income"], "Other Income": []},
    "Expenses": {
        "Operating Expenses": [
            "Electricity",
            "Water",
            "Fuel",
            "Rent",
            "Salaries",
            "Utilities",
            "Marketing",
            "Misc",
        ],
        "Personal Expenses": ["Personal"],
    },
}


@router.get("/coa/tree")
async def coa_tree():
    try:
        doc = await db.coa.find_one({"id": "root_tree"})
    except Exception:
        doc = None
    if not doc:
        doc = {"id": "root_tree", "tree": DEFAULT_COA, "createdAt": datetime.utcnow()}
        await db.coa.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/coa/tree")
async def save_coa_tree(payload: Dict[str, Any] = Body(...)):
    try:
        tree = (payload or {}).get("tree")
        if not isinstance(tree, dict):
            raise HTTPException(status_code=400, detail="tree invalid")
        await db.coa.update_one(
            {"id": "root_tree"},
            {"$set": {"tree": tree, "updatedAt": datetime.utcnow()}},
            upsert=True,
        )
        doc = await db.coa.find_one({"id": "root_tree"})
        doc.pop("_id", None)
        return doc
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------- Operations & Analytics ---------------------
# NOTE: This app uses a modern chart of accounts (e.g., 1101 cash, 1102 bank, 1103 customers, 2101 suppliers).
# Legacy codes (101/113/211/411/514) caused misclassification in reports.
ACCOUNT_NAME_MAP = {
    # ─── أكواد جديدة (مطابقة لجدول accounts الحي) ───
    "003": "النقد",
    "004": "البنك",
    "005": "العملاء (ذمم مدينة)",
    "006": "نقاط بيع",
    "007": "مخزون قطع غيار",
    "008": "مخزون مستهلكات",
    "010": "معدات ميكانيكية",
    "021": "مسحوبات المالك",
    "024": "الإيرادات",
    "025": "إيرادات الخدمات",
    "026": "إيرادات خدمات ميكانيكية",
    "027": "إيرادات إصلاح محركات",
    "028": "إيرادات فرامل وتعليق",
    "029": "تكلفة الخدمات",
    "030": "تكاليف مباشرة",
    "031": "أجور فنيين مباشرة",
    "032": "قطع غيار مستخدمة",
    "033": "مستهلكات مستخدمة",
    "034": "المصروفات التشغيلية",
    "035": "مصروفات عامة وإدارية",
    "036": "رواتب إدارية",
    "037": "إيجار المركز",
    "041": "ايراد قطع الورشه",
    "166": "حساب فروقات ترحيل",
    "167": "تكلفة قطع الورشة",
    "2101": "الموردون (ذمم دائنة)",
    # ─── أكواد قديمة (للتوافق مع القيود التاريخية) ───
    "1101": "النقد",
    "1102": "البنك",
    "1103": "العملاء (ذمم مدينة)",
    "1104": "نقاط بيع",
    "1105": "مخزون قطع غيار",
    "4100": "إيرادات الخدمات",
    "4000": "الإيرادات",
    "6101": "رواتب إدارية",
    "3102": "مسحوبات المالك",
    "1201": "معدات ميكانيكية",
    "6100": "مصروفات عامة وإدارية",
    "6000": "المصروفات التشغيلية",
    "042": "ايراد قطع الورشه",
    "0421": "تكلفة قطع الورشة",
    "211":  "حساب فروقات ترحيل",
}

IDEMPOTENCY_NOTE_PREFIX = "[IDEMP:"


def _sem_code(key: str, fallback: str) -> str:
    """الكود الحالي من الدليل الحي (chart_resolver) مع fallback ثابت."""
    try:
        from core.chart_resolver import semantic_codes
        return semantic_codes().get(key) or fallback
    except Exception:
        return fallback


def _extract_idempotency_key(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""

    meta = payload.get("transaction_metadata")
    if isinstance(meta, dict):
        key = str(meta.get("transaction_id") or "").strip()
        if key:
            return key

    for field in (
        "transaction_id",
        "transactionId",
        "reference_id",
        "referenceId",
        "reference",
        "idempotency_key",
        "idempotencyKey",
    ):
        key = str(payload.get(field) or "").strip()
        if key:
            return key
    return ""


def _append_idempotency_tag(notes: Any, idem_key: str) -> str:
    key = str(idem_key or "").strip()
    if not key:
        return str(notes or "")
    token = f"{IDEMPOTENCY_NOTE_PREFIX}{key}]"
    return _append_note_token(str(notes or ""), token)


def _map_supabase_operation_row(row: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    return {
        "id": row.get("id"),
        "type": row.get("type"),
        "accountId": row.get("account_id") or row.get("accountId"),
        "accountingAccountId": row.get("accounting_account_id") or row.get("accountingAccountId"),
        "vehicleId": row.get("vehicle_id") or row.get("vehicleId"),
        "visitId": row.get("visit_id") or row.get("visitId"),
        "partnerType": row.get("partner_type") or row.get("partnerType"),
        "partnerId": row.get("partner_id") or row.get("partnerId"),
        "partnerName": row.get("partner_name") or row.get("partnerName"),
        "items": row.get("items") or [],
        "subtotal": row.get("subtotal") or 0,
        "total": row.get("total") or 0,
        "paymentMethod": row.get("payment_method") or row.get("paymentMethod"),
        "paymentStatus": row.get("payment_status") or row.get("paymentStatus"),
        "notes": row.get("notes") or "",
        "date": row.get("op_date") or row.get("date"),
        "createdAt": row.get("created_at") or row.get("createdAt"),
        "updatedAt": row.get("updated_at") or row.get("updatedAt"),
        "invoiceNumber": row.get("invoice_number") or row.get("invoiceNumber"),
        "scope": row.get("scope") or ("vehicle" if (row.get("vehicle_id") or row.get("vehicleId")) else "workshop"),
        "source": row.get("source"),
        "businessUnit": row.get("business_unit") or row.get("businessUnit"),
    }


def _find_existing_supabase_operation_by_idempotency(
    supa: SupabaseService,
    workshop_id: Optional[str],
    idem_key: str,
) -> Optional[Dict[str, Any]]:
    key = str(idem_key or "").strip()
    if not key:
        return None

    token = f"{IDEMPOTENCY_NOTE_PREFIX}{key}]"
    try:
        q = supa.client.table("operations").select("*")
        if workshop_id:
            q = q.eq("workshop_id", workshop_id)
        q = q.ilike("notes", f"%{token}%").order("created_at", desc=True).limit(1)
        rows = q.execute().data or []
        if rows:
            return _map_supabase_operation_row(rows[0])
    except Exception:
        # Fallback for schemas without workshop_id/notes filters support
        try:
            rows = supa.operations_list(limit=400)
            for row in rows:
                notes = str((row or {}).get("notes") or "")
                if token in notes:
                    if workshop_id:
                        row_workshop = str(
                            (row or {}).get("workshopId")
                            or (row or {}).get("workshop_id")
                            or ""
                        )
                        if row_workshop and row_workshop != str(workshop_id):
                            continue
                    return row
        except Exception:
            pass
    return None


def _invalidate_finance_caches_safe() -> None:
    try:
        from routes_finance import invalidate_finance_caches

        invalidate_finance_caches()
    except Exception:
        pass


def _adjust_supabase_inventory_and_build_cogs_entries(
    supa: SupabaseService,
    op: Dict[str, Any],
    workshop_id: Optional[str],
) -> List[Dict[str, Any]]:
    if not isinstance(op, dict):
        return []

    op_type = str(op.get("type") or "").lower()
    if op_type not in {"sale", "purchase", "sale_return", "purchase_return", "service"}:
        return []

    items = op.get("items") or []
    if not isinstance(items, list) or not items:
        return []

    cogs_total = 0.0
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("itemType") or item.get("item_type") or "").lower() != "part":
            continue

        part_id = str(item.get("itemId") or item.get("partId") or "").strip()
        if not part_id:
            continue

        qty = _safe_amount(item.get("quantity") or item.get("qty") or 0)
        if qty <= 0:
            continue

        try:
            part_rows = (
                supa.client.table("parts")
                .select("id,quantity,purchase_price,name")
                .eq("id", part_id)
                .limit(1)
                .execute()
                .data
                or []
            )
        except Exception:
            part_rows = []

        if not part_rows:
            continue

        part = part_rows[0]
        current_qty = int(float(part.get("quantity") or 0))
        qty_int = int(round(qty))

        delta = qty_int
        if op_type in {"sale", "service", "purchase_return"}:
            delta = -qty_int

        new_qty = current_qty + delta
        if new_qty < 0:
            new_qty = 0

        try:
            supa.parts_update(part_id, {"quantity": new_qty})
        except Exception as inv_error:
            print(f"Inventory update skipped for part {part_id}: {inv_error}")

        if op_type in {"sale", "service"} and delta < 0:
            part_cost = _safe_amount(part.get("purchase_price") or 0)
            if part_cost > 0:
                cogs_total += part_cost * qty_int

    cogs_total = round(cogs_total, 2)
    if cogs_total <= 0 or not workshop_id:
        return []

    return [
        {
            "id": str(uuid.uuid4()),
            "workshop_id": workshop_id,
            "date": op.get("date") or op.get("op_date") or datetime.now(timezone.utc).isoformat(),
            "description": f"تكلفة قطع الورشة - عملية {op.get('id')}",
            "lines": [
                {
                    "account": _sem_code("parts_cogs", "167"),
                    "account_name": "تكلفة قطع الورشة",
                    "debit": cogs_total,
                    "credit": 0,
                },
                {
                    "account": _sem_code("inventory_parts", "007"),
                    "account_name": "مخزون قطع غيار",
                    "debit": 0,
                    "credit": cogs_total,
                },
            ],
            "total": cogs_total,
            "source": "operation_cogs",
            "transaction_type": "cogs",
            "reference_id": op.get("id"),
        }
    ]


# الكلمات الدالة على نوع الإيراد
_TOWDHEEB_KEYWORDS = ["توضيب", "تلميع مكينة", "غسيل مكينة", "تنظيف مكينة"]


def _infer_revenue_code(op: Dict[str, Any]) -> str:
    """
    يستنتج كود حساب الإيراد الصحيح من بنود العملية (الأكواد الحالية من الدليل الحي):
    - توضيب → إيرادات إصلاح محركات
    - غير ذلك → إيرادات خدمات ميكانيكية
    """
    try:
        from core.chart_resolver import semantic_codes
        sem = semantic_codes()
    except Exception:
        sem = {}
    items = op.get("items") or []
    all_text = " ".join(
        [str(op.get("notes") or ""), str(op.get("description") or "")]
        + [str(it.get("name") or "") for it in items
           if str(it.get("itemType") or "").lower() not in ("supplier",)]
    )
    for kw in _TOWDHEEB_KEYWORDS:
        if kw in all_text:
            return sem.get("revenue_engine") or "027"
    return sem.get("revenue_mech") or "026"

# خريطة تحويل الأكواد القديمة → الجديدة
LEGACY_TO_NEW_CODE = {
    "1101": "003", "acc-1101": "003",
    "1102": "004", "acc-1102": "004",
    "1103": "005", "acc-1103": "005",
    "1104": "006", "acc-1104": "006",
    "4000": "025", "acc-4000": "025",
    "4100": "026", "acc-4100": "026",
    "5000": "030", "acc-5000": "030",
    "5100": "031", "acc-5100": "031",
    "6000": "034", "acc-6000": "034",
    "6100": "035", "acc-6100": "035",
    "6101": "036", "acc-6101": "036",
    "3102": "022", "acc-3102": "022",
    "1201": "010", "acc-1201": "010",
}

# Fallback mapping: if an entry stores account as an internal id like acc-1101, map it to the numeric code.
ACCOUNT_ID_TO_CODE = {
    "acc-1101": "003", "acc-1102": "004", "acc-1103": "005", "acc-1104": "006",
    "acc-2101": "2101", "acc-4100": "026", "acc-4000": "025",
    "acc-6101": "036", "acc-3102": "022", "acc-1201": "010", "acc-6100": "035",
    "acc-6000": "034",
}

RAKAN_ACCOUNT_CODE_PREFIX = "5000"


def _normalize_account_code(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    # تحويل acc-XXXX أو acc-legacy
    if raw in ACCOUNT_ID_TO_CODE:
        return ACCOUNT_ID_TO_CODE[raw]
    if raw.startswith("acc-") and raw[4:].isdigit():
        code = raw[4:]
        return LEGACY_TO_NEW_CODE.get(code, code)
    # تحويل الأكواد القديمة للجديدة
    if raw in LEGACY_TO_NEW_CODE:
        return LEGACY_TO_NEW_CODE[raw]
    return raw


def _is_rakan_account_code(value: Any) -> bool:
    # 🔥 Rakan logic permanently removed (Feb 2026) — always returns False.
    return False


def _is_rakan_business_account_doc(account: Dict[str, Any]) -> bool:
    # 🔥 Rakan logic permanently removed (Feb 2026) — always returns False.
    return False


def _build_chart_account_ref_map(chart_accounts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    ref_map: Dict[str, Dict[str, Any]] = {}
    for account in chart_accounts or []:
        code = _normalize_account_code(account.get("code"))
        if not code:
            continue
        account_type = str(account.get("type") or "").strip().lower()
        account_name = (
            account.get("name_ar")
            or account.get("name")
            or account.get("name_en")
            or code
        )
        meta = {
            "code": code,
            "type": account_type,
            "name": account_name,
            "is_rakan": _is_rakan_account_code(code),
        }
        refs = {
            str(account.get("id") or "").strip(),
            str(account.get("code") or "").strip(),
            code,
        }
        for ref in refs:
            if ref:
                ref_map[ref] = meta
    return ref_map


def _resolve_chart_account_meta(
    account_ref: Optional[str],
    chart_account_ref_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    ref = str(account_ref or "").strip()
    if not ref:
        return {"code": "", "type": "", "name": "", "is_rakan": False}
    normalized = _normalize_account_code(ref)
    return (
        chart_account_ref_map.get(ref)
        or chart_account_ref_map.get(normalized)
        or {
            "code": normalized or ref,
            "type": "",
            "name": normalized or ref,
            "is_rakan": _is_rakan_account_code(normalized or ref),
        }
    )


def _infer_operation_type_from_account(
    requested_type: Optional[str],
    account_type: Optional[str],
) -> str:
    req = str(requested_type or "").strip().lower()
    if req in {
        "purchase",
        "sale",
        "expense",
        "service",
        "payment_order",
        "sale_return",
        "purchase_return",
    }:
        return req
    acc_type = str(account_type or "").strip().lower()
    if acc_type == "revenue":
        return "sale"
    if acc_type == "expense":
        return "purchase" if req == "purchase" else "expense"
    if acc_type in {"asset", "liability"}:
        return "purchase"
    if acc_type == "equity":
        return "expense"
    return req or "purchase"


def _append_note_token(notes: str, token: str) -> str:
    base = str(notes or "").strip()
    if token in base:
        return base
    return f"{base} {token}".strip()


def _enrich_operation_notes(
    notes: Any,
    is_rakan: bool,
    accounting_code: Optional[str],
    accounting_name: Optional[str] = None,
) -> str:
    enriched = str(notes or "").strip()
    if accounting_code:
        enriched = _append_note_token(enriched, f"ACCOUNT_CODE:{accounting_code}")
    if accounting_name:
        enriched = _append_note_token(enriched, f"ACCOUNTING_TARGET:{accounting_name}")
    if is_rakan:
        enriched = _append_note_token(enriched, "[RAKAN_PARTS]")
    return enriched


def _safe_amount(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


_UNCONFIRMED_PAYMENT_STATUSES = {
    "unconfirmed",
    "not_confirmed",
    "not_billed",
    "draft",
    "quotation",
    "غير مؤكد",
    "غير_مؤكد",
    "بانتظار تأكيد",
    "بانتظار_تأكيد",
}
_UNCONFIRMED_PAYMENT_METHODS = {
    "unconfirmed",
    "not_selected",
    "none",
    "غير محدد",
    "غير_محدد",
}
_EXPLICIT_CREDIT_PAYMENT_METHODS = {"credit", "deferred", "اجل", "آجل", "ذمة", "ذمم"}
_EXPLICIT_CASH_PAYMENT_METHODS = {
    "cash", "نقد", "نقدي", "كاش", "transfer", "bank", "تحويل", "بنك",
    "pos", "card", "mada", "visa", "mastercard", "نقاط بيع", "نقاط_بيع",
    "point_of_sale", "بطاقة", "بطاقه", "شبكة",
}


def _normalize_unconfirmed_vehicle_payment(payload: Dict[str, Any], kind: str) -> None:
    if kind != "VEHICLE_OPERATION":
        return
    op_type = str(payload.get("type") or "").strip().lower()
    if op_type not in {"sale", "service"}:
        return
    raw_method = payload.get("paymentMethod") if "paymentMethod" in payload else payload.get("payment_method")
    raw_status = payload.get("paymentStatus") if "paymentStatus" in payload else payload.get("payment_status")
    method = str(raw_method or "").strip().lower()
    status = str(raw_status or "").strip().lower()

    if method in _EXPLICIT_CREDIT_PAYMENT_METHODS or method in _EXPLICIT_CASH_PAYMENT_METHODS:
        return
    if status in {"paid", "paid_full", "settled", "مدفوع", "مسدد", "credit", "deferred"}:
        return
    if (not method and status in {"", "unpaid", "pending"}) or method in _UNCONFIRMED_PAYMENT_METHODS or status in _UNCONFIRMED_PAYMENT_STATUSES:
        payload["paymentMethod"] = "unconfirmed"
        payload["payment_method"] = "unconfirmed"
        payload["paymentStatus"] = "unconfirmed"
        payload["payment_status"] = "unconfirmed"


def _is_unconfirmed_vehicle_financial_state(op: Dict[str, Any]) -> bool:
    op_type = str(op.get("type") or "").strip().lower()
    if op_type not in {"sale", "service"}:
        return False
    has_vehicle_context = bool(
        op.get("vehicleId")
        or op.get("vehicle_id")
        or str(op.get("scope") or "").strip().lower() == "vehicle"
        or str(op.get("operationKind") or "").strip().upper() == "VEHICLE_OPERATION"
    )
    if not has_vehicle_context:
        return False
    raw_method = op.get("paymentMethod") if "paymentMethod" in op else op.get("payment_method")
    raw_status = op.get("paymentStatus") if "paymentStatus" in op else op.get("payment_status")
    method = str(raw_method or "").strip().lower()
    status = str(raw_status or "").strip().lower()
    if method in _EXPLICIT_CREDIT_PAYMENT_METHODS or method in _EXPLICIT_CASH_PAYMENT_METHODS:
        return False
    return method in _UNCONFIRMED_PAYMENT_METHODS or status in _UNCONFIRMED_PAYMENT_STATUSES


def _split_operation_totals(op: Dict[str, Any]) -> Dict[str, float]:
    total = _safe_amount(op.get("total"))
    items = op.get("items") or []
    if not isinstance(items, list) or not items:
        supplier_total = _safe_amount(op.get("supplier_archive_total") or op.get("total_suppliers"))
        return {
            "combined_total": total,
            "workshop_total": max(total - supplier_total, 0.0) if supplier_total > 0 else total,
            "supplier_total": supplier_total,
        }

    workshop = 0.0
    suppliers = 0.0
    for item in items:
        if not isinstance(item, dict):
            continue
        line_total = _safe_amount(item.get("total"))
        if line_total <= 0:
            line_total = _safe_amount(item.get("price")) * _safe_amount(item.get("quantity") or item.get("qty") or 1)
        item_type = str(item.get("itemType") or item.get("type") or "").strip().lower()
        if item_type == "supplier":
            suppliers += line_total
        else:
            workshop += line_total

    if workshop <= 0 and total > 0:
        workshop = max(total - suppliers, 0.0)

    combined = total if total > 0 else (workshop + suppliers)
    return {
        "combined_total": round(combined, 2),
        "workshop_total": round(workshop, 2),
        "supplier_total": round(suppliers, 2),
    }


def _build_operation_journal_entry(
    op: Dict[str, Any],
    workshop_id: Optional[str],
    chart_account_ref_map: Optional[Dict[str, Dict[str, Any]]] = None,
):
    """Build an accrual journal entry for an operation.

    Rules (Accrual basis):
    - Sale (cash):   Dr Cash/Bank,   Cr Revenue
    - Sale (credit): Dr AR,          Cr Revenue
    - Purchase/Expense (cash):   Dr Selected account (or 6100), Cr Cash/Bank
    - Purchase/Expense (credit): Dr Selected account (or 6100), Cr AP

    Note: In this codebase, Operations form provides `accountId` which refers to the *debit* account
    for purchases/expenses (e.g., equipment asset 1201, materials expense 5103, salaries 6101, owner draw 3102).
    """

    if not workshop_id:
        return None

    if _is_unconfirmed_vehicle_financial_state(op):
        return None

    op_type = (op.get("type") or "").lower()
    payment_method = (op.get("paymentMethod") or op.get("payment_method") or "cash").lower()
    totals = _split_operation_totals(op)
    total = _safe_amount(op.get("total"))
    workshop_total = totals.get("workshop_total", total)
    supplier_total = totals.get("supplier_total", 0.0)

    if total <= 0:
        total = workshop_total
    if total <= 0:
        return None

    # 🕒 قاعدة المالك: كل الصيغ الآجلة (عربي/إنجليزي) + حالات السداد المعلّقة = آجل
    pay_status = str(op.get("paymentStatus") or op.get("payment_status") or "").strip().lower()
    is_credit = (
        payment_method in _EXPLICIT_CREDIT_PAYMENT_METHODS
        or pay_status in ("unpaid", "credit", "partial", "deferred", "pending")
    )

    # Choose cash/bank/pos code for non-credit payments (أكواد حالية من الدليل الحي)
    cash_code = _sem_code("cash", "003")
    if payment_method in ("transfer", "bank", "تحويل", "بنك"):
        cash_code = _sem_code("bank", "004")
    elif payment_method in ("pos", "card", "mada", "visa", "mastercard", "نقاط بيع", "نقاط_بيع", "point_of_sale", "بطاقة", "بطاقه", "شبكة"):
        cash_code = _sem_code("pos", "006")

    ar_code = _sem_code("ar", "005")
    ap_code = _sem_code("ap", "2101")
    admin_exp_code = _sem_code("admin_expense", "035")

    chart_account_ref_map = chart_account_ref_map or {}

    def _to_meta(account_ref: Optional[str]) -> Dict[str, Any]:
        if not account_ref:
            return {"code": "", "type": "", "name": "", "is_rakan": False}
        v = str(account_ref).strip()
        if not v:
            return {"code": "", "type": "", "name": "", "is_rakan": False}
        return _resolve_chart_account_meta(v, chart_account_ref_map)

    selected_meta = _to_meta(
        op.get("accountingAccountId")
        or op.get("accounting_account_id")
        or op.get("accountId")
        or op.get("account_id")
    )
    selected_code = selected_meta.get("code") or ""

    scope = str(op.get("scope") or "").strip().lower()
    business_unit = str(op.get("businessUnit") or op.get("business_unit") or "").strip().lower()
    source = str(op.get("source") or "").strip().lower()
    notes_text = str(op.get("notes") or "")
    notes_lower = notes_text.lower()
    is_rakan_operation = (
        selected_meta.get("is_rakan")
        or scope == "rakan_parts"
        or business_unit == "rakan_parts"
        or "rakan_parts" in source
        or "[rakan_parts]" in notes_lower
    )

    lines = []
    transaction_type = None

    # 🚫 Rakan business unit is independent from the workshop ledger.
    # Skip ALL Rakan operations — no journal entry. Rakan analytics live
    # under the parts dashboard ("تحليلات قطع راكان") only.
    if is_rakan_operation:
        return None

    # Detect parts sale (vs service sale) by inspecting items.
    items_for_check = op.get("items") or []
    has_part_item = any(
        str(it.get("itemType") or it.get("item_type") or "").lower() == "part"
        for it in items_for_check
        if isinstance(it, dict)
    )
    has_service_item = any(
        str(it.get("itemType") or it.get("item_type") or "").lower() == "service"
        for it in items_for_check
        if isinstance(it, dict)
    )

    if op_type in ("sale", "service"):
        total = workshop_total
        if total <= 0:
            return None

        if (
            op_type == "sale"
            and has_part_item
            and not has_service_item
            and workshop_total <= 0
        ):
            return None

        transaction_type = "sale"
        debit_code = ar_code if is_credit else cash_code
        _valid_rev_code = (
            selected_code
            if selected_code and len(selected_code) <= 12 and "-" not in selected_code
            else None
        )
        if _valid_rev_code:
            _valid_rev_code = LEGACY_TO_NEW_CODE.get(_valid_rev_code, _valid_rev_code)
        revenue_code = _valid_rev_code or _infer_revenue_code(op)

        lines = [
            {
                "account": debit_code,
                "account_name": ACCOUNT_NAME_MAP.get(debit_code, debit_code),
                "debit": total,
                "credit": 0,
            },
            {
                "account": revenue_code,
                "account_name": ACCOUNT_NAME_MAP.get(revenue_code, revenue_code),
                "debit": 0,
                "credit": total,
            },
        ]

    elif op_type in ("purchase", "expense"):
        transaction_type = "purchase" if op_type == "purchase" else "expense"

        # enforce purchases/expenses into expense/asset accounts (الأكواد الحالية: 029-048 مصروفات، 007/008/010 أصول قابلة للشراء)
        def _is_expense_code(c):
            if not c:
                return False
            try:
                n = int(c)
                if n in (7, 8, 10) or (29 <= n <= 48) or n == 167:
                    return True
            except (ValueError, TypeError):
                pass
            return str(c or "").startswith(("5", "6", "1201"))
        if op_type == "purchase":
            debit_code = selected_code if (selected_code and len(selected_code) <= 12 and "-" not in selected_code and _is_expense_code(selected_code)) else admin_exp_code
        else:
            debit_code = selected_code if (selected_code and len(selected_code) <= 12 and "-" not in selected_code and _is_expense_code(selected_code)) else admin_exp_code
        if debit_code:
            debit_code = LEGACY_TO_NEW_CODE.get(debit_code, debit_code)
        credit_code = ap_code if is_credit else cash_code

        lines = [
            {
                "account": debit_code,
                "account_name": ACCOUNT_NAME_MAP.get(debit_code, debit_code),
                "debit": total,
                "credit": 0,
            },
            {
                "account": credit_code,
                "account_name": ACCOUNT_NAME_MAP.get(credit_code, credit_code),
                "debit": 0,
                "credit": total,
            },
        ]

    elif op_type == "sale_return":
        transaction_type = "sale_return"
        _valid_dr_code = (
            selected_code
            if selected_code and len(selected_code) <= 12 and "-" not in selected_code
            else None
        )
        debit_code = _valid_dr_code or _sem_code("revenue_mech", "026")
        credit_code = ar_code if is_credit else cash_code
        lines = [
            {
                "account": debit_code,
                "account_name": ACCOUNT_NAME_MAP.get(debit_code, debit_code),
                "debit": total,
                "credit": 0,
            },
            {
                "account": credit_code,
                "account_name": ACCOUNT_NAME_MAP.get(credit_code, credit_code),
                "debit": 0,
                "credit": total,
            },
        ]

    elif op_type == "purchase_return":
        transaction_type = "purchase_return"
        debit_code = ap_code if is_credit else cash_code
        credit_code = selected_code if str(selected_code or "").startswith(("5", "6")) else admin_exp_code
        lines = [
            {
                "account": debit_code,
                "account_name": ACCOUNT_NAME_MAP.get(debit_code, debit_code),
                "debit": total,
                "credit": 0,
            },
            {
                "account": credit_code,
                "account_name": ACCOUNT_NAME_MAP.get(credit_code, credit_code),
                "debit": 0,
                "credit": total,
            },
        ]

    elif op_type == "payment_order":
        transaction_type = "payment_order"
        partner_type = str(op.get("partnerType") or op.get("partner_type") or "").strip().lower()

        if partner_type == "customer":
            # تحصيل من عميل: Dr نقدية/بنك, Cr ذمم مدينة
            lines = [
                {
                    "account": cash_code,
                    "account_name": ACCOUNT_NAME_MAP.get(cash_code, cash_code),
                    "debit": total,
                    "credit": 0,
                },
                {
                    "account": ar_code,
                    "account_name": ACCOUNT_NAME_MAP.get(ar_code, "العملاء (ذمم مدينة)"),
                    "debit": 0,
                    "credit": total,
                },
            ]
        else:
            # سداد لمورد: Dr ذمم دائنة, Cr نقدية/بنك
            lines = [
                {
                    "account": ap_code,
                    "account_name": ACCOUNT_NAME_MAP.get(ap_code, "الموردون (ذمم دائنة)"),
                    "debit": total,
                    "credit": 0,
                },
                {
                    "account": cash_code,
                    "account_name": ACCOUNT_NAME_MAP.get(cash_code, cash_code),
                    "debit": 0,
                    "credit": total,
                },
            ]

    else:
        return None

    description = (
        op.get("notes")
        or f"عملية {transaction_type} - {op.get('partnerName') or op.get('partner_name') or ''}"
    )
    if is_rakan_operation and "[RAKAN_PARTS]" not in str(description):
        description = f"[RAKAN_PARTS] {description}".strip()

    # 🕒 قيد مؤقت للبيع الآجل — يبقى موسوماً حتى التحصيل (مدين ذمم/دائن إيرادات)
    if is_credit and transaction_type == "sale" and not is_rakan_operation and "قيد مؤقت" not in str(description):
        description = f"[قيد مؤقت — بيع آجل] {description}".strip()

    primary_entry = {
        "id": str(uuid.uuid4()),
        "workshop_id": workshop_id,
        "date": op.get("date") or op.get("op_date") or datetime.utcnow().isoformat(),
        "description": description,
        "lines": lines,
        "total": total,
        "operation_total": totals.get("combined_total", total),
        "workshop_total": workshop_total,
        "supplier_archive_total": supplier_total,
        "source": "operation_rakan_parts" if is_rakan_operation else "operation",
        "transaction_type": transaction_type,
        "reference_id": op.get("id"),
    }

    return primary_entry


def _safe_insert_journal_entry(supa: SupabaseService, entry: Dict[str, Any]):
    if not entry:
        return None
    # 🏦 المسار المركزي: كل القيود تمرّ عبر AccountingEngine (توازن + منع تكرار + تدقيق)
    try:
        from core import accounting_engine
        result = accounting_engine.post_entry(entry, fallback=False)
        if not result:
            raise RuntimeError("accounting_engine_rejected_entry")
        return result
    except Exception as error:
        print(f"AccountingEngine post_entry failed; no direct journal fallback: {error}")
        raise
@router.get("/operations")
async def list_operations(
    workshop_id: Optional[str] = None,
    account_id: Optional[str] = None,
    type: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    limit: Optional[int] = Query(default=None, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
):
    try:
        # 🚀 TTL cache (10s) — operations list is the heaviest GET on most pages
        cache_key = f"{workshop_id or '_'}|{account_id or '_'}|{type or '_'}|{vehicle_id or '_'}|{limit or '_'}|{offset}"
        cached = _perf_cache.get_cached("ops_list", cache_key, ttl=10.0)
        if cached is not None:
            return cached

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            ops = supa.operations_list(
                workshop_id=workshop_id,
                account_id=account_id,
                type=type,
                vehicle_id=vehicle_id,
                limit=limit,
                offset=offset,
            )
            if not vehicle_id:
                try:
                    live_vehicle_rows = supa.client.table("vehicles").select("id,status").execute().data or []
                    live_vehicle_ids = {
                        str(row.get("id") or "").strip()
                        for row in live_vehicle_rows
                        if str(row.get("id") or "").strip()
                        and str(row.get("status") or "").strip().lower() != "delivered"
                    }
                    ops = [
                        op for op in ops
                        if not str(op.get("vehicle_id") or op.get("vehicleId") or "").strip()
                        or str(op.get("vehicle_id") or op.get("vehicleId") or "").strip() in live_vehicle_ids
                    ]
                except Exception as scope_error:
                    print(f"operations live scope filter skipped: {scope_error}")
            _perf_cache.set_cached("ops_list", ops, cache_key)
            return ops

        if provider == "memory" or db is None:
            ops = _mem_read("operations")
            if workshop_id:
                ops = [
                    o for o in ops if str(o.get("workshopId") or o.get("workshop_id") or "") == str(workshop_id)
                ]
            if account_id:
                ops = [o for o in ops if o.get("accountId") == account_id]
            if type:
                ops = [o for o in ops if o.get("type") == type]
            if vehicle_id:
                ops = [o for o in ops if o.get("vehicleId") == vehicle_id]
            ops = sorted(
                ops,
                key=lambda o: str(o.get("date") or o.get("op_date") or o.get("createdAt") or o.get("created_at") or o.get("updatedAt") or o.get("updated_at") or ""),
                reverse=True,
            )
            if offset:
                ops = ops[offset:]
            if limit:
                ops = ops[:limit]
            for o in ops:
                if not o.get("scope"):
                    o["scope"] = "vehicle" if o.get("vehicleId") else "workshop"
            _perf_cache.set_cached("ops_list", ops, cache_key)
            return ops

        q: Dict[str, Any] = {}
        if workshop_id:
            q["workshopId"] = workshop_id
        if account_id:
            q["accountId"] = account_id
        if type:
            q["type"] = type
        if vehicle_id:
            q["vehicleId"] = vehicle_id
        ops = (
            await db.operations.find(
                q,
                {
                    "_id": 0,
                    "id": 1,
                    "type": 1,
                    "partnerName": 1,
                    "total": 1,
                    "items": 1,
                    "date": 1,
                    "vehicleId": 1,
                    "accountId": 1,
                    "accountingAccountId": 1,
                    "partnerId": 1,
                    "notes": 1,
                    "paymentStatus": 1,
                    "paymentMethod": 1,
                    "scope": 1,
                    "source": 1,
                    "businessUnit": 1,
                },
            )
            .sort("date", -1)
            .skip(offset)
            .to_list(length=limit or 2000)
        )
        for o in ops:
            o.pop("_id", None)
            if o.get("date") and hasattr(o["date"], "isoformat"):
                o["date"] = o["date"].isoformat()
            o["scope"] = o.get("scope") or ("vehicle" if o.get("vehicleId") else "workshop")
        _perf_cache.set_cached("ops_list", ops, cache_key)
        return ops
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _operation_date_key(op: Dict[str, Any]) -> str:
    return str(
        op.get("date")
        or op.get("op_date")
        or op.get("createdAt")
        or op.get("created_at")
        or ""
    )[:10]


def _operation_integrity_signature(op: Dict[str, Any]) -> str:
    op_type = str(op.get("type") or "").strip().lower()
    partner = str(op.get("partnerId") or op.get("partner_id") or op.get("partnerName") or op.get("partner_name") or "").strip().lower()
    vehicle = str(op.get("vehicleId") or op.get("vehicle_id") or "").strip().lower()
    date_key = _operation_date_key(op)
    try:
        total = round(float(op.get("total") or 0), 2)
    except Exception:
        total = 0.0
    return f"{op_type}|{partner}|{vehicle}|{total}|{date_key}"


@router.post("/operations/integrity/check")
async def operations_integrity_check(payload: Dict[str, Any] = Body(...)):
    """
    كشف ترابط العملية بين:
    - operations
    - vehicle/visit
    - journal_entries(reference_id)
    مع تحذيرات التكرار المحتمل.
    """
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        raw_op_ids = payload.get("op_ids") or payload.get("operation_ids") or []
        op_ids = [str(x).strip() for x in raw_op_ids if str(x).strip()]
        vehicle_id = str(payload.get("vehicle_id") or payload.get("vehicleId") or "").strip()
        workshop_id = str(payload.get("workshop_id") or payload.get("workshopId") or "").strip()

        operations_rows: List[Dict[str, Any]] = []
        journal_rows: List[Dict[str, Any]] = []
        visits_rows: List[Dict[str, Any]] = []
        vehicles_rows: List[Dict[str, Any]] = []

        if provider == "supabase":
            supa = SupabaseService()
            if supa.mock_mode:
                base_ops = _mem_read("operations")
                if workshop_id:
                    base_ops = [o for o in base_ops if str(o.get("workshopId") or o.get("workshop_id") or "") == workshop_id]
                if vehicle_id:
                    base_ops = [o for o in base_ops if str(o.get("vehicleId") or o.get("vehicle_id") or "") == vehicle_id]
                if op_ids:
                    op_set = set(op_ids)
                    base_ops = [o for o in base_ops if str(o.get("id") or "") in op_set]
                operations_rows = base_ops[:500]
                if not op_ids:
                    op_ids = [str(o.get("id") or "") for o in operations_rows if str(o.get("id") or "")]
                journal_rows = [
                    j for j in _mem_read("journal_entries")
                    if str(j.get("reference_id") or j.get("referenceId") or "") in set(op_ids)
                ]
                visit_ids = {
                    str(o.get("visitId") or o.get("visit_id") or "")
                    for o in operations_rows
                    if str(o.get("visitId") or o.get("visit_id") or "")
                }
                vehicle_ids = {
                    str(o.get("vehicleId") or o.get("vehicle_id") or "")
                    for o in operations_rows
                    if str(o.get("vehicleId") or o.get("vehicle_id") or "")
                }
                visits_rows = [v for v in _mem_read("vehicle_visits") if str(v.get("id") or "") in visit_ids]
                vehicles_rows = [v for v in _mem_read("vehicles") if str(v.get("id") or "") in vehicle_ids]
            else:
                q = supa.client.table("operations").select("*")
                if vehicle_id:
                    q = q.eq("vehicle_id", vehicle_id)
                if op_ids:
                    q = q.in_("id", op_ids)
                q = q.order("created_at", desc=True).limit(500)
                operations_rows = q.execute().data or []

                if not op_ids:
                    op_ids = [str(o.get("id") or "") for o in operations_rows if str(o.get("id") or "")]

                if op_ids:
                    try:
                        journal_rows = (
                            supa.client.table("journal_entries")
                            .select("id,reference_id,total,source,date")
                            .in_("reference_id", op_ids)
                            .execute()
                            .data
                            or []
                        )
                    except Exception:
                        journal_rows = []

                visit_ids = list({str(o.get("visit_id") or "") for o in operations_rows if str(o.get("visit_id") or "")})
                vehicle_ids = list({str(o.get("vehicle_id") or "") for o in operations_rows if str(o.get("vehicle_id") or "")})

                if visit_ids:
                    visits_rows = (
                        supa.client.table("vehicle_visits")
                        .select("*")
                        .in_("id", visit_ids)
                        .execute()
                        .data
                        or []
                    )
                if vehicle_ids:
                    vehicles_rows = (
                        supa.client.table("vehicles")
                        .select("*")
                        .in_("id", vehicle_ids)
                        .execute()
                        .data
                        or []
                    )

        elif provider == "memory" or db is None:
            base_ops = _mem_read("operations")
            if workshop_id:
                base_ops = [o for o in base_ops if str(o.get("workshopId") or o.get("workshop_id") or "") == workshop_id]
            if vehicle_id:
                base_ops = [o for o in base_ops if str(o.get("vehicleId") or o.get("vehicle_id") or "") == vehicle_id]
            if op_ids:
                op_set = set(op_ids)
                base_ops = [o for o in base_ops if str(o.get("id") or "") in op_set]
            operations_rows = base_ops[:500]
            if not op_ids:
                op_ids = [str(o.get("id") or "") for o in operations_rows if str(o.get("id") or "")]
            journal_rows = [
                j for j in _mem_read("journal_entries")
                if str(j.get("reference_id") or j.get("referenceId") or "") in set(op_ids)
            ]
            visit_ids = {
                str(o.get("visitId") or o.get("visit_id") or "")
                for o in operations_rows
                if str(o.get("visitId") or o.get("visit_id") or "")
            }
            vehicle_ids = {
                str(o.get("vehicleId") or o.get("vehicle_id") or "")
                for o in operations_rows
                if str(o.get("vehicleId") or o.get("vehicle_id") or "")
            }
            visits_rows = [v for v in _mem_read("vehicle_visits") if str(v.get("id") or "") in visit_ids]
            vehicles_rows = [v for v in _mem_read("vehicles") if str(v.get("id") or "") in vehicle_ids]
        else:
            q: Dict[str, Any] = {}
            if workshop_id:
                q["workshopId"] = workshop_id
            if vehicle_id:
                q["vehicleId"] = vehicle_id
            if op_ids:
                q["id"] = {"$in": op_ids}

            operations_rows = await db.operations.find(
                q,
                {
                    "_id": 0,
                    "id": 1,
                    "type": 1,
                    "total": 1,
                    "partnerId": 1,
                    "partnerName": 1,
                    "vehicleId": 1,
                    "visitId": 1,
                    "scope": 1,
                    "date": 1,
                    "createdAt": 1,
                    "notes": 1,
                },
            ).to_list(length=500)

            if not op_ids:
                op_ids = [str(o.get("id") or "") for o in operations_rows if str(o.get("id") or "")]

            journal_rows = await db.journal_entries.find(
                {"reference_id": {"$in": op_ids}},
                {"_id": 0, "id": 1, "reference_id": 1, "total": 1, "source": 1, "date": 1},
            ).to_list(length=2000)

            visit_ids = list({str(o.get("visitId") or "") for o in operations_rows if str(o.get("visitId") or "")})
            vehicle_ids = list({str(o.get("vehicleId") or "") for o in operations_rows if str(o.get("vehicleId") or "")})

            if visit_ids:
                visits_rows = await db.vehicle_visits.find(
                    {"id": {"$in": visit_ids}},
                    {"_id": 0, "id": 1, "vehicleId": 1, "status": 1},
                ).to_list(length=1000)
            if vehicle_ids:
                vehicles_rows = await db.vehicles.find(
                    {"id": {"$in": vehicle_ids}},
                    {"_id": 0, "id": 1, "plateNumber": 1, "status": 1},
                ).to_list(length=1000)

        if not operations_rows:
            return {
                "success": True,
                "data": {"items": [], "summary": {"total": 0, "ok": 0, "warnings": 0, "duplicates": 0}},
            }

        op_norm = []
        for op in operations_rows:
            op_norm.append({
                "id": str(op.get("id") or ""),
                "type": op.get("type"),
                "total": op.get("total"),
                "partnerId": op.get("partnerId") or op.get("partner_id"),
                "partnerName": op.get("partnerName") or op.get("partner_name"),
                "vehicleId": op.get("vehicleId") or op.get("vehicle_id"),
                "visitId": op.get("visitId") or op.get("visit_id"),
                "scope": op.get("scope"),
                "date": op.get("date") or op.get("createdAt") or op.get("created_at"),
            })

        journal_count_by_ref = defaultdict(int)
        for row in journal_rows:
            ref = str(row.get("reference_id") or row.get("referenceId") or "").strip()
            if ref:
                journal_count_by_ref[ref] += 1

        visit_map: Dict[str, Dict[str, Any]] = {}
        for v in visits_rows:
            v_id = str(v.get("id") or "").strip()
            if not v_id:
                continue
            visit_map[v_id] = {
                "id": v_id,
                "vehicleId": v.get("vehicleId") or v.get("vehicle_id"),
                "status": v.get("status"),
            }

        vehicle_ids_existing = {
            str(v.get("id") or "").strip()
            for v in vehicles_rows
            if str(v.get("id") or "").strip()
        }

        signature_count = defaultdict(int)
        for op in op_norm:
            signature_count[_operation_integrity_signature(op)] += 1

        items = []
        ok_count = 0
        warn_count = 0
        duplicate_count = 0

        for op in op_norm:
            op_id = op.get("id")
            warnings = []
            journal_count = int(journal_count_by_ref.get(op_id, 0))
            if journal_count == 0:
                warnings.append("missing_journal_entry")

            op_vehicle_id = str(op.get("vehicleId") or "").strip()
            op_visit_id = str(op.get("visitId") or "").strip()

            if op_vehicle_id and op_vehicle_id not in vehicle_ids_existing:
                warnings.append("vehicle_not_found")

            visit_row = visit_map.get(op_visit_id) if op_visit_id else None
            if op_visit_id and not visit_row:
                warnings.append("visit_not_found")
            if visit_row and op_vehicle_id and str(visit_row.get("vehicleId") or "") != op_vehicle_id:
                warnings.append("visit_vehicle_mismatch")

            if str(op.get("scope") or "").lower() == "vehicle" and not op_vehicle_id:
                warnings.append("vehicle_scope_without_vehicle")

            sign = _operation_integrity_signature(op)
            dup_size = int(signature_count.get(sign, 0))
            if dup_size > 1:
                warnings.append("potential_duplicate")
                duplicate_count += 1

            status = "ok" if not warnings else "warning"
            if status == "ok":
                ok_count += 1
            else:
                warn_count += 1

            items.append(
                {
                    "op_id": op_id,
                    "invoice_number": op.get("invoiceNumber") or op.get("invoice_number") or "",
                    "display_label": op.get("invoiceNumber") or op.get("invoice_number") or (str(op_id or "")[:8] if op_id else ""),
                    "status": status,
                    "warnings": warnings,
                    "links": {
                        "journal_count": journal_count,
                        "has_vehicle": bool(op_vehicle_id),
                        "has_visit": bool(op_visit_id),
                        "visit_vehicle_match": False if (visit_row and op_vehicle_id and str(visit_row.get("vehicleId") or "") != op_vehicle_id) else True,
                    },
                    "duplicate_group_size": dup_size,
                }
            )

        return {
            "success": True,
            "data": {
                "items": items,
                "summary": {
                    "total": len(items),
                    "ok": ok_count,
                    "warnings": warn_count,
                    "duplicates": duplicate_count,
                },
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/operations/integrity/fix-all")
async def operations_integrity_fix_all(payload: Dict[str, Any] = Body(default={})):
    """تصحيح تلقائي للقيود المفقودة — يُنشئ journal entries للعمليات التي ليس لها قيد محاسبي."""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider != "supabase":
            raise HTTPException(status_code=400, detail="يعمل فقط مع Supabase")
        supa = SupabaseService()
        if supa.mock_mode:
            raise HTTPException(status_code=400, detail="Supabase في وضع المحاكاة")

        # 1) Get all operations
        ops = supa.client.table("operations").select("*").order("created_at", desc=True).limit(500).execute().data or []
        op_ids = [str(o.get("id") or "") for o in ops if o.get("id")]

        # 2) Get existing journal entries
        existing_je = set()
        if op_ids:
            try:
                je_rows = supa.client.table("journal_entries").select("reference_id").in_("reference_id", op_ids).execute().data or []
                existing_je = {str(j.get("reference_id") or "") for j in je_rows}
            except Exception:
                # table might use referenceId
                try:
                    je_rows = supa.client.table("journal_entries").select("\"referenceId\"").in_("referenceId", op_ids).execute().data or []
                    existing_je = {str(j.get("referenceId") or "") for j in je_rows}
                except Exception:
                    existing_je = set()

        # 3) Find operations missing journal entries
        missing = [o for o in ops if str(o.get("id") or "") not in existing_je and float(o.get("total") or 0) > 0]

        dry_run = bool(payload.get("dry_run") or payload.get("preview"))

        # 4) Build entries via the canonical builder (SSOT — نفس منطق إنشاء العمليات):
        #    accrual basis + new chart codes (005 العملاء / 026 إيرادات / 003 النقد / 2101 موردون)
        preview = []
        fixed = []
        errors = []
        skipped = []
        for op in missing[:50]:
            op_id = str(op.get("id") or "")
            op_type = (op.get("type") or "").lower()
            total = round(float(op.get("total") or 0), 2)
            workshop_id = op.get("workshopId") or op.get("workshop_id") or "finmodule-sync"

            built = _build_operation_journal_entry(op, workshop_id)
            entries = built if isinstance(built, list) else ([built] if built else [])
            if not entries:
                skipped.append({"op_id": op_id, "type": op_type, "total": total,
                                "reason": "لا يتطلب قيدًا (Rakan/قطع فقط)"})
                continue

            for entry in entries:
                entry["source"] = "integrity_auto_fix"
                entry.setdefault("reference_id", op_id)

            if dry_run:
                method = str(op.get("payment_method") or op.get("paymentMethod") or "").strip().lower()
                is_credit = method == "credit"
                for entry in entries:
                    lines = entry.get("lines") or []
                    debit_lines = [ln for ln in lines if float(ln.get("debit") or 0) > 0]
                    credit_lines = [ln for ln in lines if float(ln.get("credit") or 0) > 0]
                    preview.append({
                        "op_id": op_id,
                        "invoice_number": op.get("invoice_number") or op.get("invoiceNumber"),
                        "type": op_type,
                        "payment_method": method or None,
                        "partner_name": op.get("partner_name") or op.get("partnerName"),
                        "date": entry.get("date"),
                        "nature": ("بيع آجل" if is_credit else "بيع نقدي") if op_type in ("sale", "service") else op_type,
                        "total": round(float(entry.get("total") or 0), 2),
                        "description": entry.get("description"),
                        "entry": {
                            "debit": [{"account": ln.get("account"), "name": ln.get("account_name"),
                                       "amount": round(float(ln.get("debit") or 0), 2)} for ln in debit_lines],
                            "credit": [{"account": ln.get("account"), "name": ln.get("account_name"),
                                        "amount": round(float(ln.get("credit") or 0), 2)} for ln in credit_lines],
                        },
                        "balanced": abs(sum(float(ln.get("debit") or 0) for ln in lines)
                                        - sum(float(ln.get("credit") or 0) for ln in lines)) < 0.01,
                    })
                continue

            for entry in entries:
                try:
                    result = _safe_insert_journal_entry(supa, entry)
                    if result:
                        fixed.append({"op_id": op_id, "type": op_type,
                                      "total": round(float(entry.get("total") or 0), 2),
                                      "je_id": result[0].get("id")})
                    else:
                        errors.append({"op_id": op_id, "error": "insert_failed"})
                except Exception as fix_err:
                    errors.append({"op_id": op_id, "error": str(fix_err)[:100]})

        if dry_run:
            total_impact = round(sum(p["total"] for p in preview), 2)
            by_nature: Dict[str, float] = {}
            for p in preview:
                by_nature[p["nature"]] = round(by_nature.get(p["nature"], 0) + p["total"], 2)
            return {
                "success": True,
                "data": {
                    "dry_run": True,
                    "total_operations": len(ops),
                    "missing_count": len(missing),
                    "preview_entries": preview,
                    "skipped": skipped,
                    "total_impact": total_impact,
                    "summary_by_nature": by_nature,
                    "note": "معاينة فقط — لم يُحفظ أي قيد في قاعدة البيانات.",
                }
            }

        try:
            _invalidate_finance_caches_safe()
        except Exception:
            pass

        return {
            "success": True,
            "data": {
                "total_operations": len(ops),
                "missing_before": len(missing),
                "fixed": len(fixed),
                "errors": len(errors),
                "skipped": skipped,
                "fixed_items": fixed,
                "error_items": errors[:10],
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])



def _extract_visit_items_for_dashboard(visit_row: Dict[str, Any]) -> List[Dict[str, Any]]:
    notes_payload = _parse_notes_json(visit_row.get("notes"))
    financial = _calc_visit_financial(notes_payload)
    items = financial.get("items") or notes_payload.get("items") or []
    if not items and (notes_payload.get("services") or notes_payload.get("parts")):
        items = [*(notes_payload.get("services") or []), *(notes_payload.get("parts") or [])]
    return items if isinstance(items, list) else []


def _build_dashboard_vehicle_summary(vehicle_id: str, visits: List[Dict[str, Any]]) -> Dict[str, Any]:
    latest_visit = None
    latest_key = ""

    for row in visits:
        row_key = str(row.get("entryDate") or row.get("entry_date") or row.get("createdAt") or row.get("created_at") or "")
        if not latest_visit or row_key > latest_key:
            latest_visit = row
            latest_key = row_key

    items = _extract_visit_items_for_dashboard(latest_visit or {})
    names = []
    for item in items:
        name = str(item.get("name") or item.get("description") or "").strip()
        if name:
            names.append(name)

    service_type = "، ".join(names[:3]) if names else "غير محدد"
    estimated_total = 0.0
    for item in items:
        try:
            quantity = float(item.get("quantity") or 1)
        except Exception:
            quantity = 1.0
        try:
            price = float(item.get("price") or item.get("unit_price") or 0)
        except Exception:
            price = 0.0
        try:
            line_total = float(item.get("total") or (quantity * price))
        except Exception:
            line_total = quantity * price
        estimated_total += line_total

    return {
        "vehicleId": vehicle_id,
        "visitsCount": len(visits),
        "estimatedTotal": round(estimated_total, 2),
        "serviceType": service_type,
    }


@router.post("/vehicles/dashboard/summaries")
async def vehicle_dashboard_summaries(payload: Dict[str, Any] = Body(...)):
    try:
        raw_ids = payload.get("vehicle_ids") or payload.get("vehicleIds") or []
        vehicle_ids = [str(v).strip() for v in raw_ids if str(v).strip()]
        if not vehicle_ids:
            return {"summaries": []}

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        grouped: Dict[str, List[Dict[str, Any]]] = {vid: [] for vid in vehicle_ids}

        if provider == "supabase":
            supa = SupabaseService()
            if supa.mock_mode:
                rows = [
                    row
                    for row in _mem_read("vehicle_visits")
                    if str(row.get("vehicleId") or "") in grouped
                ]
                for row in rows:
                    vid = str(row.get("vehicleId") or "")
                    grouped.setdefault(vid, []).append(row)
            else:
                chunk_size = 100
                for i in range(0, len(vehicle_ids), chunk_size):
                    chunk_ids = vehicle_ids[i : i + chunk_size]
                    res = (
                        supa.client.table("vehicle_visits")
                        .select("id,vehicle_id,entry_date,created_at,notes")
                        .in_("vehicle_id", chunk_ids)
                        .execute()
                    )
                    for row in res.data or []:
                        vid = str(row.get("vehicle_id") or "")
                        grouped.setdefault(vid, []).append(row)

        elif provider == "memory" or db is None:
            rows = [
                row
                for row in _mem_read("vehicle_visits")
                if str(row.get("vehicleId") or "") in grouped
            ]
            for row in rows:
                vid = str(row.get("vehicleId") or "")
                grouped.setdefault(vid, []).append(row)
        else:
            rows = await db.vehicle_visits.find(
                {"vehicleId": {"$in": vehicle_ids}},
                {
                    "_id": 0,
                    "id": 1,
                    "vehicleId": 1,
                    "entryDate": 1,
                    "createdAt": 1,
                    "notes": 1,
                },
            ).to_list(length=5000)
            for row in rows:
                vid = str(row.get("vehicleId") or "")
                grouped.setdefault(vid, []).append(row)

        summaries = [
            _build_dashboard_vehicle_summary(vehicle_id=vid, visits=grouped.get(vid, []))
            for vid in vehicle_ids
        ]
        return {"summaries": summaries}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations/{op_id}")
async def get_operation(op_id: str):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            # TODO: implement get one in supabase service
            supa = SupabaseService()
            o = supa.operations_get(op_id)
            if not o:
                raise HTTPException(status_code=404, detail="not found")
            return o

        if provider == "memory" or db is None:
            ops = _mem_read("operations")
            for o in ops:
                if o.get("id") == op_id:
                    return o
            raise HTTPException(status_code=404, detail="not found")

        o = await db.operations.find_one({"id": op_id})
        if not o:
            raise HTTPException(status_code=404, detail="not found")
        o.pop("_id", None)
        if o.get("date") and hasattr(o["date"], "isoformat"):
            o["date"] = o["date"].isoformat()
        return o
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/operations/{op_id}")
async def update_operation(op_id: str, payload: Dict[str, Any] = Body(...)):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            existing = supa.operations_get(op_id)
            if not existing:
                raise HTTPException(status_code=404, detail="not found")
            result = supa.operations_update(op_id, payload)
            _invalidate_ops_caches()
            return result

        if provider == "memory" or db is None:
            ops = _mem_read("operations")
            for i, o in enumerate(ops):
                if o.get("id") == op_id:
                    ops[i] = {
                        **o,
                        **payload,
                        "updatedAt": datetime.utcnow().isoformat(),
                    }
                    _mem_write("operations", ops)
                    _invalidate_ops_caches()
                    return ops[i]
            raise HTTPException(status_code=404, detail="not found")

        await db.operations.update_one(
            {"id": op_id}, {"$set": {**payload, "updatedAt": datetime.utcnow()}}
        )
        o = await db.operations.find_one({"id": op_id})
        if not o:
            raise HTTPException(status_code=404, detail="not found")
        o.pop("_id", None)
        if o.get("date") and hasattr(o["date"], "isoformat"):
            o["date"] = o["date"].isoformat()
        _invalidate_ops_caches()
        return o
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/operations/{op_id}")
async def delete_operation(op_id: str, request: Request):
    """Delete a single operation + cascade delete any linked journal entries (source=operation, reference_id=op_id)."""
    try:
        await _require_request_permission(request, "operations", "delete")
        await _require_request_permission(request, "journal_entries", "delete")
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()

            # 1) reverse linked journal entries first (No Hard Delete)
            try:
                from core import accounting_engine
                reverse_result = accounting_engine.reverse_entry(
                    reference_id=op_id,
                    reason="operation_delete_requested",
                    actor={"user_id": "routes_extended.delete_operation"},
                )
                if reverse_result.get("error") and reverse_result.get("error") != "original_not_found":
                    raise HTTPException(status_code=409, detail=reverse_result)
            except Exception as e:
                raise HTTPException(status_code=409, detail={"error": "journal_reverse_failed", "detail": str(e)}) from e

            # 2) delete operation
            supa.operations_delete(op_id)
            _invalidate_ops_caches()
            return {"success": True}

        if provider == "memory" or db is None:
            ops = _mem_read("operations")
            ops = [o for o in ops if o.get("id") != op_id]
            _mem_write("operations", ops)
            _invalidate_ops_caches()
            return {"success": True}

        await db.operations.delete_one({"id": op_id})
        _invalidate_ops_caches()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/operations")
async def delete_all_operations(request: Request):
    """Delete all operations - for cleanup/reset"""
    try:
        actor_obj = await _require_request_permission(request, "operations", "delete")
        await _require_request_permission(request, "journal_entries", "delete")
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        actor = _extract_request_actor(request)
        actor["user_id"] = actor_obj.name or actor_obj.id or actor["user_id"]
        actor["user_role"] = actor_obj.role or actor["user_role"]
        if provider == "supabase":
            supa = SupabaseService()
            # Delete all operations - use gt filter instead of neq
            try:
                # Get all operations first
                all_ops = supa.operations_list()
                deleted_count = len(all_ops or [])
                # Delete each one
                for op in all_ops:
                    try:
                        supa.client.table("operations").delete().eq(
                            "id", op["id"]
                        ).execute()
                    except Exception:
                        pass
                audit_event = record_bulk_delete_event(
                    action="delete_all_operations",
                    source_endpoint="/api/operations",
                    user_id=actor["user_id"],
                    user_role=actor["user_role"],
                    items={"operations_deleted": deleted_count},
                    meta={"provider": provider},
                )
                _invalidate_ops_caches()
                return {
                    "success": True,
                    "message": f"Deleted {len(all_ops)} operations",
                    "audit_event": audit_event,
                }
            except Exception as e:
                audit_event = record_bulk_delete_event(
                    action="delete_all_operations",
                    source_endpoint="/api/operations",
                    user_id=actor["user_id"],
                    user_role=actor["user_role"],
                    items={"operations_deleted": "all"},
                    meta={"provider": provider, "note": str(e)},
                )
                return {
                    "success": True,
                    "message": "Operations table cleared",
                    "note": str(e),
                    "audit_event": audit_event,
                }

        if provider == "memory" or db is None:
            _mem_write("operations", [])
            audit_event = record_bulk_delete_event(
                action="delete_all_operations",
                source_endpoint="/api/operations",
                user_id=actor["user_id"],
                user_role=actor["user_role"],
                items={"operations_deleted": "all"},
                meta={"provider": provider},
            )
            _invalidate_ops_caches()
            return {"success": True, "message": "All operations deleted", "audit_event": audit_event}

        result = await db.operations.delete_many({})
        audit_event = record_bulk_delete_event(
            action="delete_all_operations",
            source_endpoint="/api/operations",
            user_id=actor["user_id"],
            user_role=actor["user_role"],
            items={"operations_deleted": result.deleted_count},
            meta={"provider": provider},
        )
        _invalidate_ops_caches()
        return {
            "success": True,
            "message": f"Deleted {result.deleted_count} operations",
            "audit_event": audit_event,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup/keep-debts-only")
async def cleanup_keep_debts_only(request: Request, confirm: str = Query(...)):
    """Delete journal entries + non-debt operations, keep debt operations only."""
    raise HTTPException(
        status_code=410,
        detail={
            "error": "legacy_keep_debts_only_disabled",
            "msg": "تم تعطيل زر keep-debts-only القديم. استخدم Financial Reset Engine: /api/finance/reset/dry-run ثم /api/finance/reset/execute.",
        },
    )
    if confirm != "KEEP_DEBTS_ONLY":
        raise HTTPException(status_code=400, detail="confirm=KEEP_DEBTS_ONLY مطلوب")

    actor_obj = await _require_request_permission(request, "operations", "delete")
    await _require_request_permission(request, "journal_entries", "delete")

    def _is_debt_related(op: Dict[str, Any]) -> bool:
        op_type = str(op.get("type") or "").strip().lower()
        payment_method = str(op.get("payment_method") or op.get("paymentMethod") or "").strip().lower()
        payment_status = str(op.get("payment_status") or op.get("paymentStatus") or "").strip().lower()
        if op_type == "payment_order":
            return True
        if payment_method == "credit":
            return True
        if payment_status in {"credit", "unpaid", "pending", "partial"}:
            return True
        return False

    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        actor = _extract_request_actor(request)
        actor["user_id"] = actor_obj.name or actor_obj.id or actor["user_id"]
        actor["user_role"] = actor_obj.role or actor["user_role"]
        result = {
            "operations_kept": 0,
            "operations_deleted": 0,
            "journal_entries_deleted": 0,
        }

        if provider == "supabase":
            supa = SupabaseService()
            all_ops = supa.operations_list() or []
            keep_ids = []
            delete_ids = []
            for op in all_ops:
                op_id = str(op.get("id") or "").strip()
                if not op_id:
                    continue
                if _is_debt_related(op):
                    keep_ids.append(op_id)
                else:
                    delete_ids.append(op_id)

            for op_id in delete_ids:
                try:
                    supa.client.table("operations").delete().eq("id", op_id).execute()
                except Exception as op_del_error:
                    print(f"Cleanup operation delete failed for {op_id}: {op_del_error}")

            journal_ids = []
            try:
                journal_rows = supa.client.table("journal_entries").select("id").range(0, 9999).execute().data or []
                journal_ids = [str(row.get("id") or "").strip() for row in journal_rows if row.get("id")]
            except Exception as journal_read_error:
                print(f"Cleanup journal fetch failed: {journal_read_error}")

            for journal_id in journal_ids:
                raise HTTPException(status_code=410, detail="legacy_cleanup_disabled_no_direct_journal_delete")

            result["operations_kept"] = len(keep_ids)
            result["operations_deleted"] = len(delete_ids)
            result["journal_entries_deleted"] = len(journal_ids)
            audit_event = record_bulk_delete_event(
                action="cleanup_keep_debts_only",
                source_endpoint="/api/cleanup/keep-debts-only",
                user_id=actor["user_id"],
                user_role=actor["user_role"],
                items=result,
                meta={"confirm": confirm, "provider": provider},
            )
            return {"success": True, "data": result, "audit_event": audit_event}

        if provider == "memory" or db is None:
            operations = _mem_read("operations")
            kept_ops = [op for op in operations if _is_debt_related(op)]
            deleted_count = max(0, len(operations) - len(kept_ops))
            _mem_write("operations", kept_ops)
            journals = _mem_read("journal_entries")
            _mem_write("journal_entries", [])
            result["operations_kept"] = len(kept_ops)
            result["operations_deleted"] = deleted_count
            result["journal_entries_deleted"] = len(journals)
            audit_event = record_bulk_delete_event(
                action="cleanup_keep_debts_only",
                source_endpoint="/api/cleanup/keep-debts-only",
                user_id=actor["user_id"],
                user_role=actor["user_role"],
                items=result,
                meta={"confirm": confirm, "provider": provider},
            )
            return {"success": True, "data": result, "audit_event": audit_event}

        operations = await db.operations.find({}, {"_id": 0, "id": 1, "type": 1, "payment_method": 1, "paymentMethod": 1, "payment_status": 1, "paymentStatus": 1}).to_list(length=50000)
        keep_ids = []
        delete_ids = []
        for op in operations:
            op_id = str(op.get("id") or "").strip()
            if not op_id:
                continue
            if _is_debt_related(op):
                keep_ids.append(op_id)
            else:
                delete_ids.append(op_id)

        if delete_ids:
            await db.operations.delete_many({"id": {"$in": delete_ids}})
        raise HTTPException(status_code=410, detail="legacy_cleanup_disabled_no_direct_journal_delete")

        result["operations_kept"] = len(keep_ids)
        result["operations_deleted"] = len(delete_ids)
        audit_event = record_bulk_delete_event(
            action="cleanup_keep_debts_only",
            source_endpoint="/api/cleanup/keep-debts-only",
            user_id=actor["user_id"],
            user_role=actor["user_role"],
            items=result,
            meta={"confirm": confirm, "provider": provider},
        )
        return {"success": True, "data": result, "audit_event": audit_event}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations/{op_id}/payment-receipts/{filename}")
async def get_operation_payment_receipt(op_id: str, filename: str):
    safe_name = _safe_filename(filename)
    file_path = os.path.join(
        os.path.dirname(__file__),
        "uploads",
        "operation_payment_receipts",
        op_id,
        safe_name,
    )
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="receipt not found")

    guessed_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    with open(file_path, "rb") as f:
        payload = f.read()
    headers = {"Content-Disposition": f'inline; filename="{safe_name}"'}
    return StreamingResponse(io.BytesIO(payload), media_type=guessed_type, headers=headers)


@router.post("/operations/{op_id}/confirm-payment")
async def confirm_operation_payment(op_id: str, request: Request, payload: Dict[str, Any] = Body(None)):
    """تأكيد سداد عملية آجل.

    - الآجل يُسجَّل في operations (Accrual) فقط.
    - عند التحصيل/السداد يتم إنشاء قيد يومية يعكس حركة النقد:
      * بيع: مدين نقدية 101 / دائن ذمم 113
      * شراء: مدين ذمم دائنة 211 / دائن نقدية 101

    يدعم الدفعات الجزئية عبر payload.amount.
    🔒 Idempotency: يدعم header `Idempotency-Key` لمنع التكرار خلال 24 ساعة.
    """
    payload = dict(payload or {})
    approved_external_draft_id = _external_draft_is_approved(payload)
    if not approved_external_draft_id:
        approval_payload = {**payload, "_operation_id": op_id}
        return _external_approval_response(
            action="external_operation_payment",
            payload=approval_payload,
            proposer=_request_actor_name(request),
        )

    # 🔒 Idempotency check - يمنع تكرار نفس الدفعة (مفتاح من header أو تلقائي من المحتوى)
    from idempotency import get_idempotency_key, get_cached_response, store_response, make_idempotency_key
    _idem_key = get_idempotency_key(request)
    if not _idem_key:
        _wid = (payload or {}).get("workshopId") or (payload or {}).get("workshop_id") or "default"
        _idem_key = make_idempotency_key(_wid, f"confirm-payment:{op_id}", payload or {})
    _cached = get_cached_response(_idem_key)
    if _cached is not None:
        return {**_cached, "idempotent_replay": True}

    try:
        try:
            uuid.UUID(str(op_id))
        except Exception:
            raise HTTPException(status_code=400, detail="invalid operation id")

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider != "supabase":
            raise HTTPException(status_code=400, detail="confirm-payment supported only for supabase provider")

        supa = SupabaseService()
        workshop_id = (payload or {}).get("workshopId") or (payload or {}).get("workshop_id")

        op_rows = (
            supa.client.table("operations").select("*").eq("id", op_id).execute().data
            or []
        )
        if not op_rows:
            raise HTTPException(status_code=404, detail="operation not found")
        op_row = op_rows[0]

        # إذا لم يُرسَل workshopId من الفرونت، استخدم الـ workshop_id من العملية نفسها
        if not workshop_id:
            workshop_id = (
                op_row.get("workshopId")
                or op_row.get("workshop_id")
                or os.environ.get("DEFAULT_WORKSHOP_ID", "finmodule-sync")
            )
        if not workshop_id:
            raise HTTPException(status_code=400, detail="workshopId required")

        payment_methods = {
            str(op_row.get("payment_method") or "").lower(),
            str(op_row.get("paymentMethod") or "").lower(),
        }
        payment_statuses = {
            str(op_row.get("payment_status") or "").lower(),
            str(op_row.get("paymentStatus") or "").lower(),
        }

        is_credit_flow = (
            len(payment_methods.intersection({"credit", "deferred", "اجل", "آجل", "ذمة", "ذمم"})) > 0
            or len(payment_statuses.intersection({"credit", "unpaid", "pending", "partial"})) > 0
        )

        if not is_credit_flow:
            return {"success": True, "message": "operation is not credit"}

        op_type = (op_row.get("type") or "").lower()
        # Normalize instant_sale → sale for confirm-payment compatibility (iter221 fix)
        if op_type == "instant_sale":
            op_type = "sale"
        total = float(op_row.get("total") or 0)
        if total <= 0:
            raise HTTPException(status_code=400, detail="invalid operation total")

        amount = None
        if (payload or {}).get("amount") is not None:
            try:
                amount = float((payload or {}).get("amount"))
            except Exception:
                raise HTTPException(status_code=400, detail="invalid amount")

        pay_amount = amount if amount is not None else total
        if pay_amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be > 0")

        # FIX: قبول حقل الخصم (يُقلِّل من رصيد العميل دون أن يكون دفعة نقدية)
        discount_amount = 0.0
        if (payload or {}).get("discount") is not None:
            try:
                discount_amount = float((payload or {}).get("discount") or 0)
            except Exception:
                discount_amount = 0.0
            if discount_amount < 0:
                discount_amount = 0.0

        already_paid = 0.0
        try:
            prev = (
                supa.client.table("journal_entries")
                .select("total")
                .in_("source", ["operation_payment", "supplier_balance_payment"])
                .eq("reference_id", op_id)
                .execute()
                .data
                or []
            )
            for je in prev:
                already_paid += float(je.get("total") or 0)
        except Exception as e:
            print(f"Payment lookup failed: {e}")

        try:
            visit_id_for_paid = str(op_row.get("visit_id") or op_row.get("visitId") or "").strip()
            if visit_id_for_paid:
                visit_rows = (
                    supa.client.table("vehicle_visits")
                    .select("notes")
                    .eq("id", visit_id_for_paid)
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                if visit_rows:
                    visit_fin = _calc_visit_financial(_parse_notes_json(visit_rows[0].get("notes")))
                    already_paid += float(visit_fin.get("totalPaid") or visit_fin.get("total_paid") or 0)
        except Exception as e:
            print(f"Visit payment lookup failed: {e}")

        remaining = max(0.0, total - already_paid)
        # حد الخصم لا يتجاوز المتبقي
        if discount_amount > remaining:
            discount_amount = remaining
        # الدفعة الفعلية لا تتجاوز المتبقي - الخصم
        max_payable = max(0.0, remaining - discount_amount)
        if pay_amount > max_payable + 0.0001:
            pay_amount = max_payable
        if pay_amount <= 0 and discount_amount <= 0:
            return {"success": True, "message": "no remaining amount to confirm"}

        # Choose cash/bank account for settlement based on explicit selected method
        requested_method_raw = str(
            (payload or {}).get("payment_method")
            or (payload or {}).get("paymentMethod")
            or "cash"
        ).strip().lower()

        bank_aliases = {"bank", "transfer", "bank_transfer", "تحويل", "بنك"}
        cash_aliases = {"cash", "نقد", "نقدي", "كاش"}
        pos_aliases  = {"pos", "card", "mada", "visa", "mastercard", "بطاقة", "بطاقه", "شبكة", "نقاط بيع", "نقاط_بيع", "point_of_sale"}

        if requested_method_raw in pos_aliases:
            settlement_method = "pos"
        elif requested_method_raw in bank_aliases:
            settlement_method = "bank"
        elif requested_method_raw in cash_aliases:
            settlement_method = "cash"
        else:
            raise HTTPException(status_code=400, detail="payment_method must be cash, bank, or pos")

        # الأكواد الجديدة: 003=نقد، 004=بنك، 006=نقاط بيع
        if settlement_method == "bank":
            cash_code = "004"
        elif settlement_method == "pos":
            cash_code = "006"
        else:
            cash_code = "003"

        op_account_code = str(op_row.get("account") or op_row.get("accountCode") or "").strip()
        if not op_account_code:
            # الأكواد الحالية: إيرادات خدمات ميكانيكية للخدمات، مصروفات عامة وإدارية لغيرها
            op_account_code = _sem_code("revenue_mech", "026") if op_type in ("sale", "service") else _sem_code("admin_expense", "035")
        else:
            # تحويل أي كود قديم إلى الجديد
            op_account_code = LEGACY_TO_NEW_CODE.get(op_account_code, op_account_code)
        op_account_name = (
            op_row.get("account_name")
            or op_row.get("accountName")
            or ACCOUNT_NAME_MAP.get(op_account_code, op_account_code)
        )

        has_base_operation_entry = False
        try:
            base_entries = (
                supa.client.table("journal_entries")
                .select("id,source")
                .eq("reference_id", op_id)
                .neq("source", "operation_payment")
                .limit(1)
                .execute()
                .data
                or []
            )
            has_base_operation_entry = len(base_entries) > 0
        except Exception:
            has_base_operation_entry = False

        if has_base_operation_entry:
            if op_type in ("sale", "service"):
                # Accrual settlement: Dr Cash/Bank/POS, Cr AR
                lines = [
                    {
                        "account": cash_code,
                        "account_name": ACCOUNT_NAME_MAP.get(cash_code, cash_code),
                        "debit": pay_amount,
                        "credit": 0,
                    },
                    {
                        "account": "005",
                        "account_name": ACCOUNT_NAME_MAP.get("005", "العملاء"),
                        "debit": 0,
                        "credit": pay_amount,
                    },
                ]
                desc = f"تحصيل آجل - {op_row.get('partner_name') or ''}"
            elif op_type in ("purchase", "expense"):
                # Accrual settlement: Dr AP, Cr Cash/Bank/POS
                lines = [
                    {
                        "account": "2101",
                        "account_name": ACCOUNT_NAME_MAP.get("2101", "الموردون"),
                        "debit": pay_amount,
                        "credit": 0,
                    },
                    {
                        "account": cash_code,
                        "account_name": ACCOUNT_NAME_MAP.get(cash_code, cash_code),
                        "debit": 0,
                        "credit": pay_amount,
                    },
                ]
                desc = f"سداد آجل - {op_row.get('partner_name') or ''}"
            else:
                raise HTTPException(status_code=400, detail="unsupported operation type")
        else:
            # Missing-base fallback: never recognize revenue/expense during settlement.
            # Settlement only moves cash/bank/POS against AR/AP; missing base must be
            # reconciled separately instead of duplicating revenue.
            if op_type in ("sale", "service"):
                lines = [
                    {
                        "account": cash_code,
                        "account_name": ACCOUNT_NAME_MAP.get(cash_code, cash_code),
                        "debit": pay_amount,
                        "credit": 0,
                    },
                    {
                        "account": "005",
                        "account_name": ACCOUNT_NAME_MAP.get("005", "العملاء"),
                        "debit": 0,
                        "credit": pay_amount,
                    },
                ]
                desc = f"تحصيل آجل بدون قيد أساس مراجع - {op_row.get('partner_name') or ''}"
            elif op_type in ("purchase", "expense"):
                lines = [
                    {
                        "account": "2101",
                        "account_name": ACCOUNT_NAME_MAP.get("2101", "الموردون"),
                        "debit": pay_amount,
                        "credit": 0,
                    },
                    {
                        "account": cash_code,
                        "account_name": ACCOUNT_NAME_MAP.get(cash_code, cash_code),
                        "debit": 0,
                        "credit": pay_amount,
                    },
                ]
                desc = f"سداد آجل بدون قيد أساس مراجع - {op_row.get('partner_name') or ''}"
            else:
                raise HTTPException(status_code=400, detail="unsupported operation type")

        pay_date = (payload or {}).get("date")
        receipt_info = _save_operation_payment_receipt(op_id, (payload or {}).get("receipt") or {})
        if receipt_info and receipt_info.get("url"):
            desc = f"{desc} | إيصال: {receipt_info.get('filename')}"
        entry_source = "operation_payment"
        entry = {
            "id": str(uuid.uuid4()),
            "workshop_id": workshop_id,
            "date": pay_date or datetime.utcnow().isoformat(),
            "description": desc,
            "lines": lines,
            "total": pay_amount,
            "source": entry_source,
            "transaction_type": "payment",
            "reference_id": op_id,
        }
        if receipt_info:
            entry["receipt_url"] = receipt_info.get("url")
            entry["receipt_name"] = receipt_info.get("filename")
        _safe_insert_journal_entry(supa, entry)

        # FIX: قيد الخصم منفصل — مدين "الإيرادات" (خصم مسموح/contra-revenue) / دائن "العملاء"
        if discount_amount > 0 and op_type in ("sale", "service") and has_base_operation_entry:
            try:
                _disc_code = _sem_code("revenue_parent", "024")
                _disc_ar = _sem_code("ar", "005")
                discount_entry = {
                    "id": str(uuid.uuid4()),
                    "workshop_id": workshop_id,
                    "date": pay_date or datetime.utcnow().isoformat(),
                    "description": f"خصم ممنوح للعميل - {op_row.get('partner_name') or ''}".strip(),
                    "lines": [
                        {
                            "account": _disc_code,
                            "account_name": ACCOUNT_NAME_MAP.get(_disc_code, "الإيرادات"),
                            "debit": discount_amount,
                            "credit": 0,
                        },
                        {
                            "account": _disc_ar,
                            "account_name": ACCOUNT_NAME_MAP.get(_disc_ar, "العملاء"),
                            "debit": 0,
                            "credit": discount_amount,
                        },
                    ],
                    "total": discount_amount,
                    "source": "operation_discount",
                    "transaction_type": "discount",
                    "reference_id": op_id,
                }
                _safe_insert_journal_entry(supa, discount_entry)
            except Exception as disc_err:
                print(f"discount entry insert failed: {disc_err}")

        remaining_after = max(0.0, remaining - pay_amount - discount_amount)
        new_status = "paid" if remaining_after <= 0.0001 else "partial"
        new_method = settlement_method if new_status == "paid" else "credit"

        try:
            update_payload = {
                "payment_method": new_method,
                "paymentMethod": new_method,
                "payment_status": new_status,
                "paymentStatus": new_status,
            }
            if receipt_info and receipt_info.get("url"):
                prev_notes = str(op_row.get("notes") or "").strip()
                receipt_line = f"[PAYMENT_RECEIPT] {receipt_info.get('url')}"
                update_payload["notes"] = f"{prev_notes}\n{receipt_line}".strip()
            try:
                supa.client.table("operations").update(update_payload).eq("id", op_id).execute()
            except Exception as update_error:
                retry_payload = dict(update_payload)
                for _ in range(10):
                    match = re.search(r"Could not find the '([^']+)' column", str(update_error))
                    if not match:
                        break
                    missing_col = match.group(1)
                    if missing_col not in retry_payload:
                        break
                    retry_payload.pop(missing_col, None)
                    try:
                        supa.client.table("operations").update(retry_payload).eq("id", op_id).execute()
                        update_error = None
                        break
                    except Exception as retry_error:
                        update_error = retry_error
                if update_error:
                    print(f"confirm-payment operation update skipped: {update_error}")
        except Exception:
            pass

        # P0: no direct cleanup/delete for legacy journal rows; accounting fixes must use AccountingEngine.reverse().

        # 🕒 قاعدة القيد المؤقت للبيع الآجل: بعد التحصيل يُحدَّث وسم القيد الأساسي
        try:
            from core.financial_actions import mark_temp_deferred_settled
            mark_temp_deferred_settled(op_id, fully=(new_status == "paid"))
        except Exception as tag_err:
            print(f"temp deferred tag update skipped: {tag_err}")

        result = {
            "success": True,
            "data": {
                "paid": round(pay_amount, 2),
                "discount": round(discount_amount, 2),
                "remaining": round(remaining_after, 2),
                "status": new_status,
                "payment_method": new_method,
                "settlement_method": settlement_method,
                "receipt_url": receipt_info.get("url") if receipt_info else None,
                "receipt_name": receipt_info.get("filename") if receipt_info else None,
            },
        }
        # 🔒 Idempotency: خزِّن الاستجابة لاستجابة التكرار خلال 24h
        try:
            store_response(_idem_key, result)
        except Exception:
            pass
        _invalidate_ops_caches()
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ AutoProfit Pro Integration: Apply Accounting Entries ============


def _normalize_operation_kind(payload: Dict[str, Any]) -> str:
    raw = str(payload.get("operationKind") or payload.get("scope") or "").strip().upper()
    if raw in ["WORKSHOP_OPERATION", "WORKSHOP"]:
        return "WORKSHOP_OPERATION"
    if raw in ["VEHICLE_OPERATION", "VEHICLE"]:
        return "VEHICLE_OPERATION"
    # 🔥 Rakan logic removed: RAKAN_PARTS_OPERATION → WORKSHOP_OPERATION
    if raw in ["RAKAN_PARTS_OPERATION", "RAKAN_PARTS", "RAKAN"]:
        return "WORKSHOP_OPERATION"

    scope = str(payload.get("scope") or "").strip().lower()
    if scope == "vehicle":
        return "VEHICLE_OPERATION"
    # 🔥 Rakan logic removed: scope "rakan_parts" → WORKSHOP_OPERATION
    if scope == "rakan_parts":
        return "WORKSHOP_OPERATION"
    if payload.get("vehicleId") or payload.get("vehicle_id"):
        return "VEHICLE_OPERATION"
    return "WORKSHOP_OPERATION"


def _is_rakan_text(value: Any) -> bool:
    # 🔥 Rakan logic permanently removed (Feb 2026) — always returns False.
    return False


def _pick_business_account(
    kind: str,
    provided_id: Optional[str],
    biz_accounts: List[Dict[str, Any]],
) -> Optional[str]:
    if not biz_accounts:
        return None

    by_id = {str(b.get("id")): b for b in biz_accounts if b.get("id")}
    if provided_id and str(provided_id) in by_id:
        provided = by_id[str(provided_id)]
        provided_is_rakan = _is_rakan_business_account_doc(provided)
        if (kind == "RAKAN_PARTS_OPERATION" and provided_is_rakan) or (
            kind != "RAKAN_PARTS_OPERATION" and not provided_is_rakan
        ):
            return str(provided_id)

    if kind == "RAKAN_PARTS_OPERATION":
        rakan = next(
            (b for b in biz_accounts if _is_rakan_business_account_doc(b)),
            None,
        )
        return str(rakan.get("id")) if rakan else None

    non_rakan = [
        b for b in biz_accounts if not _is_rakan_business_account_doc(b)
    ]
    if non_rakan:
        preferred = next(
            (
                b
                for b in non_rakan
                if any(
                    key in f"{str(b.get('name') or '').lower()} {str(b.get('code') or '').lower()}"
                    for key in ["main", "workshop", "الرئيس", "الرئيسي", "default"]
                )
            ),
            None,
        )
        return str((preferred or non_rakan[0]).get("id"))

    return str(biz_accounts[0].get("id"))


def _apply_operation_kind_defaults(
    payload: Dict[str, Any],
    kind: str,
    vehicle_doc: Optional[Dict[str, Any]],
) -> None:
    payload["operationKind"] = kind

    if kind == "WORKSHOP_OPERATION":
        payload["scope"] = "workshop"
        payload["source"] = payload.get("source") or "workshop_operation"
        payload["businessUnit"] = payload.get("businessUnit") or "workshop"
        payload["vehicleId"] = None
        payload["visitId"] = None
        payload["partnerType"] = payload.get("partnerType") or (
            "supplier" if payload.get("type") == "purchase" else "customer"
        )
        return

    if kind == "VEHICLE_OPERATION":
        if not payload.get("vehicleId"):
            raise HTTPException(status_code=400, detail="VEHICLE_OPERATION requires vehicleId")
        payload["scope"] = "vehicle"
        payload["source"] = payload.get("source") or "vehicle_operation"
        payload["businessUnit"] = payload.get("businessUnit") or "workshop"
        payload["partnerType"] = "customer"
        if vehicle_doc:
            payload["partnerId"] = (
                vehicle_doc.get("customerId")
                or vehicle_doc.get("customer_id")
                or payload.get("partnerId")
            )
            payload["partnerName"] = (
                vehicle_doc.get("customerName")
                or vehicle_doc.get("customer_name")
                or payload.get("partnerName")
            )
        return

    if kind == "RAKAN_PARTS_OPERATION":
        op_type = str(payload.get("type") or "").strip().lower()
        has_link = bool(
            payload.get("vehicleId")
            or payload.get("partnerId")
            or str(payload.get("partnerName") or "").strip()
        )
        if op_type in {"sale", "service"} and not has_link:
            raise HTTPException(status_code=400, detail="RAKAN_PARTS_OPERATION requires customer or vehicle")
        payload["scope"] = "rakan_parts"
        payload["source"] = payload.get("source") or "rakan_parts_operation"
        payload["businessUnit"] = payload.get("businessUnit") or "rakan_parts"
        if payload.get("vehicleId") and vehicle_doc:
            payload["partnerType"] = "customer"
            payload["partnerId"] = (
                vehicle_doc.get("customerId")
                or vehicle_doc.get("customer_id")
                or payload.get("partnerId")
            )
            payload["partnerName"] = (
                vehicle_doc.get("customerName")
                or vehicle_doc.get("customer_name")
                or payload.get("partnerName")
            )
        return


@router.post("/operations")
async def create_operation(request: Request, payload: Dict[str, Any] = Body(...)):
    try:
        payload = dict(payload or {})
        idempotency_key = _extract_idempotency_key(payload)
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        kind = _normalize_operation_kind(payload)

        vehicle_doc = None
        biz_accounts: List[Dict[str, Any]] = []
        chart_accounts: List[Dict[str, Any]] = []

        if provider == "supabase":
            supa_for_meta = SupabaseService()
            try:
                biz_accounts = supa_for_meta.accounts_list() or []
            except Exception:
                biz_accounts = []

            try:
                chart_res = (
                    supa_for_meta.client.table("accounts")
                    .select("*")
                    .execute()
                )
                chart_accounts = chart_res.data or []
            except Exception:
                chart_accounts = []

            if payload.get("vehicleId"):
                try:
                    vehicles = supa_for_meta.vehicles_list() or []
                    vehicle_doc = next(
                        (v for v in vehicles if str(v.get("id")) == str(payload.get("vehicleId"))),
                        None,
                    )
                except Exception:
                    vehicle_doc = None

        elif provider == "memory" or db is None:
            biz_accounts = _mem_read("business_accounts")
            chart_accounts = _mem_read("accounts") or _mem_read("chart_of_accounts")
            if payload.get("vehicleId"):
                vehicles = _mem_read("vehicles")
                vehicle_doc = next(
                    (v for v in vehicles if str(v.get("id")) == str(payload.get("vehicleId"))),
                    None,
                )
        else:
            biz_accounts = await db.business_accounts.find({}, {"_id": 0}).to_list(1000)
            chart_accounts = await db.accounts.find({}, {"_id": 0}).to_list(5000)
            if payload.get("vehicleId"):
                vehicle_doc = await db.vehicles.find_one(
                    {"id": str(payload.get("vehicleId"))}, {"_id": 0}
                )

        chart_account_ref_map = _build_chart_account_ref_map(chart_accounts)
        accounting_ref = (
            payload.get("accountingAccountId")
            or payload.get("accounting_account_id")
            or payload.get("accountId")
            or payload.get("account_id")
        )
        accounting_meta = _resolve_chart_account_meta(accounting_ref, chart_account_ref_map)
        accounting_code = accounting_meta.get("code") or ""
        is_rakan_by_account = _is_rakan_account_code(accounting_code)

        if is_rakan_by_account:
            kind = "RAKAN_PARTS_OPERATION"
        elif kind == "RAKAN_PARTS_OPERATION":
            kind = "VEHICLE_OPERATION" if payload.get("vehicleId") else "WORKSHOP_OPERATION"

        payload["type"] = _infer_operation_type_from_account(
            payload.get("type"), accounting_meta.get("type")
        )

        op_type = str(payload.get("type") or "").lower()
        original_type = str(payload.get("originalType") or payload.get("original_type") or "").lower()
        partner_type = str(payload.get("partnerType") or payload.get("partner_type") or "").lower()
        has_partner = bool(payload.get("partnerId") or payload.get("partner_id") or payload.get("partnerName") or payload.get("partner_name"))
        has_vehicle = bool(payload.get("vehicleId") or payload.get("vehicle_id"))

        if op_type in {"sale", "sale_return"} and not (has_vehicle or has_partner):
            raise HTTPException(status_code=400, detail="عمليات البيع/مرتجع البيع تتطلب ربطاً بمركبة أو عميل")

        if op_type in {"purchase", "purchase_return"} and not has_partner:
            raise HTTPException(status_code=400, detail="عمليات الشراء/مرتجع الشراء تتطلب اختيار مورد")

        if op_type == "payment_order" and original_type == "receipt_voucher":
            if not has_vehicle:
                raise HTTPException(status_code=400, detail="سند القبض يجب أن يكون مرتبطاً بمركبة")
            payload["partnerType"] = "customer"
            payload["partner_type"] = "customer"

        if op_type == "payment_order" and original_type == "settlement":
            if not has_partner or partner_type not in {"customer", "supplier"}:
                raise HTTPException(status_code=400, detail="التسوية يجب أن تكون مرتبطة بعميل أو مورد")

        payload["notes"] = _enrich_operation_notes(
            payload.get("notes"),
            is_rakan=is_rakan_by_account,
            accounting_code=accounting_code,
            accounting_name=accounting_meta.get("name"),
        )
        if idempotency_key:
            payload["notes"] = _append_idempotency_tag(payload.get("notes"), idempotency_key)
        if accounting_code:
            payload["accountingAccountCode"] = accounting_code

        if kind == "RAKAN_PARTS_OPERATION" and not any(
            _is_rakan_business_account_doc(x) for x in biz_accounts
        ):
            if provider == "supabase":
                try:
                    supa_for_meta = SupabaseService()
                    created_rakan = supa_for_meta.accounts_create(
                        name="قطع راكان", code="RAKAN_PARTS", currency="SAR"
                    )
                    if created_rakan:
                        biz_accounts = [created_rakan, *biz_accounts]
                except Exception:
                    pass

        _apply_operation_kind_defaults(payload, kind, vehicle_doc)
        _normalize_unconfirmed_vehicle_payment(payload, kind)

        approved_external_draft_id = _external_draft_is_approved(payload)
        is_receipt_voucher = op_type == "payment_order" and original_type == "receipt_voucher"
        is_smart_pos_instant_sale = (
            op_type == "sale"
            and "[SOURCE:SMART_POS]" in str(payload.get("notes") or "").upper()
        )
        if (is_receipt_voucher or is_smart_pos_instant_sale) and not approved_external_draft_id:
            return _external_approval_response(
                action="external_operation",
                payload=payload,
                proposer=_request_actor_name(request),
            )

        if (
            provider == "supabase"
            and str(payload.get("type") or "").lower() == "payment_order"
            and str(payload.get("partnerType") or payload.get("partner_type") or "").lower() == "customer"
            and str(payload.get("vehicleId") or payload.get("vehicle_id") or "").strip()
            and original_type in {"collect_customer", "receipt_voucher", "settlement"}
        ):
            try:
                vehicle_ref = str(payload.get("vehicleId") or payload.get("vehicle_id") or "").strip()
                collection_amount = float(payload.get("total") or payload.get("amount") or 0)
                open_ops = (
                    supa_for_meta.client.table("operations")
                    .select("id,type,total,created_at")
                    .eq("vehicle_id", vehicle_ref)
                    .in_("type", ["sale", "service"])
                    .order("created_at", desc=False)
                    .execute()
                    .data
                    or []
                )
                target_open_op = None
                for existing_op in open_ops:
                    existing_id = str(existing_op.get("id") or "").strip()
                    if not existing_id:
                        continue
                    existing_total = float(existing_op.get("total") or 0)
                    paid_rows = (
                        supa_for_meta.client.table("journal_entries")
                        .select("total,source")
                        .eq("reference_id", existing_id)
                        .in_("source", ["operation_payment", "supplier_balance_payment"])
                        .execute()
                        .data
                        or []
                    )
                    existing_paid = sum(float(row.get("total") or 0) for row in paid_rows)
                    if existing_total - existing_paid > 0.01:
                        target_open_op = existing_op
                        break
                if target_open_op and collection_amount > 0:
                    settlement_result = await confirm_operation_payment(
                        str(target_open_op.get("id")),
                        request,
                        {
                            "amount": collection_amount,
                            "paymentMethod": payload.get("paymentMethod") or payload.get("payment_method") or "pos",
                            "payment_method": payload.get("paymentMethod") or payload.get("payment_method") or "pos",
                            "workshopId": payload.get("workshopId") or payload.get("workshop_id"),
                            "notes": payload.get("notes") or "تحصيل مرتبط من POS بدون إنشاء عملية مكررة",
                            "_approved_external_draft": approved_external_draft_id,
                        },
                    )
                    return {
                        "success": True,
                        "preventedDuplicateOperation": True,
                        "settledOperationId": str(target_open_op.get("id")),
                        "data": settlement_result,
                    }
            except HTTPException:
                raise
            except Exception as duplicate_guard_error:
                print(f"POS duplicate collection guard warning: {duplicate_guard_error}")

        visit_data = None
        if payload.get("vehicleId"):
            if payload.get("visitId"):
                visit_data = await _get_vehicle_visit_by_id(provider, payload.get("visitId"), db)
            if not visit_data:
                visit_data = await _get_latest_vehicle_visit(provider, payload.get("vehicleId"))
                if visit_data:
                    payload["visitId"] = visit_data.get("id")

        resolved_account_id = _pick_business_account(
            kind, payload.get("accountId"), biz_accounts
        )
        if not resolved_account_id:
            raise HTTPException(
                status_code=400,
                detail="تعذر تحديد حساب الأعمال المناسب للعملية. تحقق من إعداد حسابات الفروع.",
            )
        payload["accountId"] = resolved_account_id

        if provider == "supabase":
            supa = SupabaseService()
            workshop_id = payload.get("workshopId") or payload.get("workshop_id")

            # Idempotency guard (by transaction/reference key)
            if idempotency_key:
                existing = _find_existing_supabase_operation_by_idempotency(
                    supa,
                    workshop_id,
                    idempotency_key,
                )
                if existing:
                    firewall_state.log_event(
                        "idempotency_hit",
                        {
                            "key": idempotency_key,
                            "workshop_id": workshop_id,
                            "operation_id": existing.get("id"),
                            "partner": existing.get("partnerName"),
                            "amount": existing.get("total") or existing.get("amount"),
                        },
                    )
                    return existing

            op = supa.operations_create(payload)

            is_unconfirmed_vehicle_financial = _is_unconfirmed_vehicle_financial_state(op)

            # Auto-create invoice record linked to this operation (best-effort)
            try:
                if op.get("invoiceNumber") and not is_unconfirmed_vehicle_financial:
                    supa.invoices_create(
                        {
                            "invoiceNumber": op.get("invoiceNumber"),
                            "workshopId": workshop_id,
                            "operationId": op.get("id"),
                            "partnerName": op.get("partnerName"),
                            "vehicleId": op.get("vehicleId"),
                            "items": op.get("items") or [],
                            "subtotal": op.get("subtotal") or 0,
                            "tax": 0,
                            "discount": 0,
                            "total": op.get("total") or 0,
                            "status": "issued",
                            "type": "invoice",
                            "paymentMethod": op.get("paymentMethod"),
                            "notes": f"Linked to operation {op.get('id')}",
                        }
                    )
            except Exception as e:
                print(f"Warning: auto-invoice create failed: {e}")
            # ✅ Accrual basis: always create a journal entry for sale/purchase/expense
            # - Credit operations will hit AR/AP
            # - Cash/transfer operations will hit Cash/Bank
            try:
                entry = None if is_unconfirmed_vehicle_financial else _build_operation_journal_entry(
                    op,
                    workshop_id,
                    chart_account_ref_map=chart_account_ref_map,
                )
                # قد يُعيد list من القيود (في حالة موردي الآجل)
                if isinstance(entry, list):
                    for e in entry:
                        _safe_insert_journal_entry(supa, e)
                else:
                    _safe_insert_journal_entry(supa, entry)

                # Inventory decrement/increment + COGS entries for part-linked lines
                cogs_entries = _adjust_supabase_inventory_and_build_cogs_entries(
                    supa,
                    op,
                    workshop_id,
                )
                for cogs_entry in cogs_entries:
                    _safe_insert_journal_entry(supa, cogs_entry)
                    firewall_state.log_event(
                        "cogs_generated",
                        {
                            "operation_id": op.get("id"),
                            "workshop_id": workshop_id,
                            "amount": cogs_entry.get("total"),
                            "reference_id": cogs_entry.get("reference_id"),
                        },
                    )

                _invalidate_finance_caches_safe()
            except Exception as je_error:
                print(f"Failed to create journal entry for operation: {je_error}")
                raise HTTPException(status_code=500, detail={
                    "error": "journal_post_failed",
                    "msg": "تعذّر ترحيل القيد عبر المحرك المحاسبي؛ لم يتم اعتبار العملية مكتملة مالياً.",
                })
            await _append_operation_to_visit(payload, op, provider, db, visit_data)
            _invalidate_ops_caches()
            return op

        if provider == "memory" or db is None:
            rows = _mem_read("operations")
            items = payload.get("items") or []
            subtotal = sum(
                (float(it.get("price", 0)) * float(it.get("qty", 1))) for it in items
            )
            doc = {
                "id": str(uuid.uuid4()),
                "type": payload.get("type", "service"),
                "accountId": payload.get("accountId"),
                "accountingAccountId": payload.get("accountingAccountId"),
                "vehicleId": payload.get("vehicleId"),
                "partnerType": payload.get("partnerType"),
                "partnerId": payload.get("partnerId"),
                "partnerName": payload.get("partnerName"),
                "items": items,
                "subtotal": subtotal,
                "total": subtotal,
                "paymentMethod": payload.get("paymentMethod", "cash"),
                "paymentStatus": payload.get("paymentStatus", "paid"),
                "paymentAmount": payload.get("paymentAmount"),
                "notes": payload.get("notes"),
                "scope": payload.get("scope") or ("vehicle" if payload.get("vehicleId") else "workshop"),
                "source": payload.get("source"),
                "businessUnit": payload.get("businessUnit") or payload.get("business_unit"),
                "date": datetime.utcnow().isoformat(),
                "createdAt": datetime.utcnow().isoformat(),
            }
            rows.append(doc)
            _mem_write("operations", rows)
            await _append_operation_to_visit(payload, doc, provider, db, visit_data)
            _invalidate_ops_caches()
            return doc

        items = payload.get("items", [])
        subtotal = 0.0
        for it in items:
            qty = float(it.get("quantity", 1))
            price = float(it.get("price", 0))
            it["total"] = qty * price
            subtotal += it["total"]
        op = {
            "id": str(uuid.uuid4()),
            "accountId": payload.get("accountId", ""),
            "accountingAccountId": payload.get("accountingAccountId"),
            "vehicleId": payload.get("vehicleId"),
            "type": payload.get("type", "purchase"),
            "partnerType": payload.get("partnerType", "supplier"),
            "partnerId": payload.get("partnerId"),
            "partnerName": payload.get("partnerName"),
            "items": items,
            "subtotal": subtotal,
            "total": subtotal,
            "paymentMethod": payload.get("paymentMethod", "cash"),
            "paymentStatus": payload.get("paymentStatus", "paid"),
            "paymentAmount": payload.get("paymentAmount"),
            "notes": payload.get("notes"),
            "scope": payload.get("scope") or ("vehicle" if payload.get("vehicleId") else "workshop"),
            "source": payload.get("source"),
            "businessUnit": payload.get("businessUnit") or payload.get("business_unit"),
            "date": datetime.utcnow(),
            "createdAt": datetime.utcnow(),
        }
        await db.operations.insert_one(op)

        # inventory adjust for parts
        if op["type"] in ("purchase", "sale", "sale_return", "purchase_return"):
            for it in items:
                if it.get("itemType") == "part" and it.get("itemId"):
                    delta = int(float(it.get("quantity", 0)))
                    if op["type"] in ("sale", "purchase_return"):
                        delta = -delta
                    await db.parts.update_one(
                        {"id": it["itemId"]}, {"$inc": {"quantity": delta}}
                    )
        # transaction record (income/expense)
        tx = {
            "id": str(uuid.uuid4()),
            "accountId": op["accountId"],
            "vehicleId": op.get("vehicleId"),
            "type": "income" if op["type"] in ("sale", "purchase_return") else "expense",
            "category": f"operation_{op['type']}",
            "amount": subtotal,
            "description": f"{op['type']} - {op.get('partnerName') or ''}",
            "date": op["date"],
            "reference": op["id"],
            "createdAt": datetime.utcnow(),
        }
        try:
            await db.transactions.insert_one(tx)
        except Exception:
            pass
        op.pop("_id", None)
        if hasattr(op["date"], "isoformat"):
            op["date"] = op["date"].isoformat()
        await _append_operation_to_visit(payload, op, provider, db, visit_data)
        _invalidate_ops_caches()
        return op
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operations/analytics/summary")
async def operations_analytics(account_id: Optional[str] = None):
    try:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        month_start = today.replace(day=1)

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        ops = []

        if provider == "supabase":
            supa = SupabaseService()
            ops = supa.operations_list()
            if account_id:
                ops = [o for o in ops if o.get("accountId") == account_id]
        elif provider == "memory" or db is None:
            ops = _mem_read("operations")
            if account_id:
                ops = [o for o in ops if o.get("accountId") == account_id]
        else:
            q: Dict[str, Any] = {}
            if account_id:
                q["accountId"] = account_id
            ops = await db.operations.find(
                q, {"_id": 0, "type": 1, "total": 1, "date": 1}
            ).to_list(length=100000)

        def parse_date(x):
            d = x.get("date")
            if isinstance(d, str):
                try:
                    return datetime.fromisoformat(d.replace("Z", "+00:00"))
                except Exception:
                    return today
            return d or today

            return d or today

        def agg(start):
            sales = 0.0
            expenses = 0.0
            sales_count = 0
            expenses_count = 0
            for o in ops:
                d = parse_date(o)
                # naive comparison fix
                if d.tzinfo is not None and start.tzinfo is None:
                    d = d.replace(tzinfo=None)

                if d >= start:
                    t = float(o.get("total", 0))
                    if o.get("type") == "sale":
                        sales += t
                        sales_count += 1
                    elif o.get("type") == "purchase":
                        expenses += t
                        expenses_count += 1
            return sales, expenses, sales - expenses, sales_count, expenses_count

        tS, tE, tP, tSc, tEc = agg(today)
        wS, wE, wP, wSc, wEc = agg(week_ago)
        mS, mE, mP, mSc, mEc = agg(month_start)
        return {
            "today": {
                "sales": tS,
                "expenses": tE,
                "profit": tP,
                "salesCount": tSc,
                "expensesCount": tEc,
            },
            "week": {
                "sales": wS,
                "expenses": wE,
                "profit": wP,
                "salesCount": wSc,
                "expensesCount": wEc,
            },
            "month": {
                "sales": mS,
                "expenses": mE,
                "profit": mP,
                "salesCount": mSc,
                "expensesCount": mEc,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------- Transactions & Expenses ---------------------
@router.get("/transactions")
async def list_transactions(
    type: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    account_id: Optional[str] = None,
):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            return supa.transactions_list(type=type, account_id=account_id)

        if provider == "memory" or db is None:
            return []

        q: Dict[str, Any] = {}
        if type:
            q["type"] = type
        if vehicle_id:
            q["vehicleId"] = vehicle_id
        if account_id:
            q["accountId"] = account_id
        docs = await db.transactions.find(q).sort("date", -1).to_list(length=5000)
        for d in docs:
            d.pop("_id", None)
            if d.get("date") and hasattr(d["date"], "isoformat"):
                d["date"] = d["date"].isoformat()
        return docs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses")
async def create_expense(payload: Dict[str, Any] = Body(...)):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            return supa.transactions_create(payload)

        if provider == "memory" or db is None:
            return {
                "id": str(uuid.uuid4()),
                "accountId": payload.get("accountId", ""),
                "vehicleId": payload.get("vehicleId"),
                "type": "expense",
                "category": payload.get("category", "Operating Expenses"),
                "amount": float(payload.get("amount") or 0),
                "description": payload.get("description", ""),
                "date": datetime.utcnow().isoformat(),
                "reference": payload.get("reference"),
                "createdAt": datetime.utcnow().isoformat(),
            }

        tx = {
            "id": str(uuid.uuid4()),
            "accountId": payload.get("accountId", ""),
            "vehicleId": payload.get("vehicleId"),
            "type": "expense",
            "category": payload.get("category", "Operating Expenses"),
            "amount": float(payload.get("amount") or 0),
            "description": payload.get("description", ""),
            "date": datetime.utcnow(),
            "reference": payload.get("reference"),
            "createdAt": datetime.utcnow(),
        }
        await db.transactions.insert_one(tx)
        tx.pop("_id", None)
        if hasattr(tx["date"], "isoformat"):
            tx["date"] = tx["date"].isoformat()
        return tx
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




# --------------------- Visits APIs ---------------------


def _parse_notes_json(notes: Any) -> Dict[str, Any]:
    if not notes:
        return {}
    if isinstance(notes, dict):
        return notes
    if isinstance(notes, str):
        s = notes.strip()
        if s.startswith('{') and s.endswith('}'):
            try:
                import json

                return json.loads(s)
            except Exception:
                return {}
    return {}


def _format_visit_number(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return f"{int(float(raw)):03d}"
    except Exception:
        digits = re.sub(r"\D+", "", raw)
        return f"{int(digits):03d}" if digits else raw


def _extract_visit_number(row: Dict[str, Any], fallback_index: Optional[int] = None) -> Dict[str, Any]:
    parsed = _parse_notes_json((row or {}).get("notes"))
    raw = (
        (row or {}).get("visit_number")
        or (row or {}).get("visitNumber")
        or parsed.get("visitNumber")
        or parsed.get("visit_number")
        or parsed.get("visitNumberDisplay")
    )
    if not raw and fallback_index is not None:
        raw = fallback_index
    display = _format_visit_number(raw)
    try:
        sequence = int(float(raw or fallback_index or 0))
    except Exception:
        sequence = int(fallback_index or 0)
    return {"visitNumber": display, "visitNumberDisplay": display, "visitSequence": sequence}


def _with_visit_number_in_notes(notes: Any, visit_number: str) -> str:
    parsed = _parse_notes_json(notes)
    if not parsed:
        text = str(notes or "").strip()
        parsed = {"text": text} if text else {}
    parsed["visitNumber"] = visit_number
    parsed["visitNumberDisplay"] = visit_number
    try:
        parsed["visitSequence"] = int(visit_number)
    except Exception:
        pass
    return json.dumps(parsed, ensure_ascii=False)


async def _next_visit_number(provider: str, vehicle_id: str) -> str:
    rows: List[Dict[str, Any]] = []
    if provider == "supabase":
        try:
            supa = SupabaseService()
            rows = (
                supa.client.table("vehicle_visits")
                .select("id,notes,entry_date,created_at")
                .eq("vehicle_id", vehicle_id)
                .execute()
                .data
                or []
            )
        except Exception:
            rows = []
    elif provider == "memory" or db is None:
        rows = [row for row in _mem_read("vehicle_visits") if str(row.get("vehicleId") or row.get("vehicle_id") or "") == str(vehicle_id)]
    else:
        rows = await db.vehicle_visits.find({"vehicleId": vehicle_id}, {"_id": 0, "notes": 1, "visitNumber": 1, "createdAt": 1, "entryDate": 1}).to_list(10000)

    max_number = 0
    for idx, row in enumerate(sorted(rows, key=lambda r: str(r.get("entry_date") or r.get("entryDate") or r.get("created_at") or r.get("createdAt") or "")), start=1):
        info = _extract_visit_number(row, idx)
        max_number = max(max_number, int(info.get("visitSequence") or idx))
    return _format_visit_number(max_number + 1)


def _apply_visit_numbers(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    numbered: Dict[str, Dict[str, Any]] = {}
    sorted_rows = sorted(
        rows or [],
        key=lambda r: str(r.get("entry_date") or r.get("entryDate") or r.get("created_at") or r.get("createdAt") or ""),
    )
    for idx, row in enumerate(sorted_rows, start=1):
        row_id = str((row or {}).get("id") or "").strip()
        if not row_id:
            continue
        numbered[row_id] = _extract_visit_number(row, idx)
    return numbered


def _calc_visit_financial(parsed_notes: Dict[str, Any]) -> Dict[str, Any]:
    items = parsed_notes.get('items') or []
    payments = parsed_notes.get('payments') or []

    def _num(x, default=0.0):
        try:
            return float(x)
        except Exception:
            return default

    total_workshop = 0.0
    total_suppliers = 0.0
    for it in items:
        # Backward compatibility: default to workshop (support itemType)
        raw_type = it.get('billingType') or it.get('type') or it.get('itemType') or 'workshop'
        billing_type = str(raw_type).lower()
        qty = _num(it.get('quantity', 1), 1.0)
        price = _num(it.get('price', it.get('unit_price', 0)), 0.0)
        line_total = _num(it.get('total'), qty * price)
        if billing_type == 'supplier':
            total_suppliers += line_total
        else:
            total_workshop += line_total

    advance_paid = 0.0
    paid_on_account = 0.0
    pending_payment_total = 0.0
    total_paid = 0.0
    for p in payments:
        amt = _num(p.get('amount'), 0.0)
        if amt <= 0:
            continue
        kind = str(p.get('kind') or '').strip().lower()
        status = str(p.get('status') or p.get('paymentStatus') or p.get('payment_status') or '').strip().lower()
        confirmed_flag = p.get('confirmed')
        is_pending = (
            confirmed_flag is False
            or status in {'pending', 'pending_confirmation', 'awaiting_confirmation', 'unconfirmed', 'بانتظار التأكيد', 'بانتظار_التأكيد'}
        )
        if is_pending:
            pending_payment_total += amt
        else:
            total_paid += amt
            paid_on_account += amt
            if kind in {'advance', 'prepayment', 'customer_advance', 'دفعة مقدمة', 'مقدم', 'مقدمة'}:
                advance_paid += amt

    total_amount = total_workshop
    applied_paid = min(total_paid, total_amount)
    balance = max(total_amount - applied_paid, 0.0)
    customer_credit = max(total_paid - total_amount, 0.0)

    if total_paid == 0:
        payment_status = 'unconfirmed'
    elif balance > 0:
        payment_status = 'partial'
    elif balance == 0:
        payment_status = 'paid_full'
    else:
        payment_status = 'credit'

    return {
        'items': items,
        'payments': payments,
        'total_workshop': round(total_workshop, 2),
        'total_suppliers': round(total_suppliers, 2),
        'supplier_archive_total': round(total_suppliers, 2),
        'supplier_cost_total': round(total_suppliers, 2),
        'parts_charge_total': round(total_suppliers, 2),
        'current_customer_due': round(total_workshop, 2),
        'workshop_service_total': round(total_workshop, 2),
        'final_customer_total': None,
        'customer_charge_total': round(total_amount, 2),
        'customer_total': round(total_amount, 2),
        'total_amount': round(total_amount, 2),
        'total_paid': round(total_paid, 2),
        'advance_paid': round(advance_paid, 2),
        'paid_on_account': round(paid_on_account, 2),
        'pending_payment_total': round(pending_payment_total, 2),
        'applied_paid': round(applied_paid, 2),
        'customer_credit': round(customer_credit, 2),
        'balance': round(balance, 2),
        'payment_status': payment_status,
    }


ARCHIVE_SEARCH_DIGITS_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
ARCHIVE_SEARCH_STOP_WORDS = {
    "السياره",
    "سياره",
    "السيارة",
    "سيارة",
    "المركبه",
    "مركبه",
    "المركبة",
    "مركبة",
    "عميل",
    "العميل",
    "لوحه",
    "لوحة",
    "زياره",
    "زيارة",
    "اخر",
    "آخر",
    "تفاصيل",
    "ماهي",
    "وش",
    "ايش",
    "عن",
    "ابحث",
    "بحث",
    "اريد",
    "أريد",
    "اعطني",
    "اعرض",
    "متى",
    "تم",
}


def _normalize_archive_search_text(value: Any, keep_spaces: bool = False) -> str:
    text = str(value or "").strip().lower().translate(ARCHIVE_SEARCH_DIGITS_MAP)
    if not text:
        return ""
    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
    }
    for src, dest in replacements.items():
        text = text.replace(src, dest)
    text = re.sub(r"[^0-9a-z\u0600-\u06FF\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if keep_spaces else text.replace(" ", "")


def _extract_archive_search_terms(query: str) -> Dict[str, Any]:
    spaced = _normalize_archive_search_text(query, keep_spaces=True)
    raw_tokens = [token for token in spaced.split(" ") if token]
    filtered_tokens = [
        token for token in raw_tokens if token not in ARCHIVE_SEARCH_STOP_WORDS
    ]
    compact = "".join(filtered_tokens) or _normalize_archive_search_text(query)
    return {
        "raw": query,
        "spaced": spaced,
        "tokens": filtered_tokens or raw_tokens,
        "compact": compact,
    }


def _build_archive_vehicle_fields(vehicle: Dict[str, Any]) -> Dict[str, str]:
    plate = str(vehicle.get("plateNumber") or vehicle.get("plate_number") or "")
    customer = str(vehicle.get("customerName") or vehicle.get("customer_name") or "")
    brand = str(vehicle.get("brand") or "")
    model = str(vehicle.get("model") or "")
    year = str(vehicle.get("year") or "")
    file_number = str(vehicle.get("fileNumber") or vehicle.get("file_number") or "")
    vin = str(vehicle.get("vin") or "")
    vehicle_title = " ".join(part for part in [brand, model, year] if part).strip()
    combined = " ".join(
        part for part in [plate, customer, vehicle_title, file_number, vin] if part
    )
    return {
        "plate": _normalize_archive_search_text(plate),
        "customer": _normalize_archive_search_text(customer),
        "vehicle": _normalize_archive_search_text(vehicle_title),
        "combined": _normalize_archive_search_text(combined),
    }


def _score_archive_vehicle_match(
    vehicle: Dict[str, Any], compact_query: str, tokens: List[str]
) -> Dict[str, Any]:
    fields = _build_archive_vehicle_fields(vehicle)
    score = 0
    reasons: List[str] = []
    matched_tokens = 0

    if compact_query:
        if fields["plate"] and (compact_query in fields["plate"] or fields["plate"] in compact_query):
            score += 140
            reasons.append("مطابقة رقم اللوحة")
        if fields["customer"] and compact_query in fields["customer"]:
            score += 110
            reasons.append("مطابقة اسم العميل")
        if fields["vehicle"] and compact_query in fields["vehicle"]:
            score += 95
            reasons.append("مطابقة المركبة")
        if fields["combined"] and compact_query in fields["combined"]:
            score += 70

    for token in tokens:
        if len(token) < 1:
            continue
        if fields["plate"] and token in fields["plate"]:
            score += 28
            matched_tokens += 1
        elif fields["customer"] and token in fields["customer"]:
            score += 24
            matched_tokens += 1
        elif fields["vehicle"] and token in fields["vehicle"]:
            score += 20
            matched_tokens += 1
        elif fields["combined"] and token in fields["combined"]:
            score += 10
            matched_tokens += 1

    if tokens and matched_tokens == len(tokens):
        score += 35
        reasons.append("مطابقة كل أجزاء البحث")
    elif matched_tokens:
        reasons.append(f"مطابقة {matched_tokens} من {len(tokens)} أجزاء البحث")

    return {"score": score, "reasons": reasons}


def _payment_method_label(method: Optional[str], payment_status: Optional[str], total_paid: float) -> str:
    normalized = str(method or "").strip().lower()
    labels = {
        "cash": "نقدًا",
        "credit": "آجل",
        "transfer": "تحويل",
        "bank": "تحويل بنكي",
        "card": "بطاقة",
        "mada": "مدى",
    }
    if payment_status == "unpaid":
        return "غير مسددة بعد"
    if payment_status == "unconfirmed":
        return "بانتظار تأكيد السداد"
    if payment_status == "partial":
        return "دفعة جزئية / تحت الحساب"
    if normalized in labels:
        label = labels[normalized]
    elif total_paid > 0:
        label = "دفعات زيارة"
    else:
        label = "غير محددة"

    if normalized == "credit" and payment_status == "paid_full":
        return "آجل تم سداده"
    return label


def _humanize_archive_date(value: Any) -> str:
    if not value:
        return "غير محدد"
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return str(value)
    return dt.strftime("%Y-%m-%d %H:%M")


def _build_repair_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    cleaned_items: List[Dict[str, Any]] = []
    for item in items or []:
        name = str(item.get("name") or item.get("title") or "").strip()
        if not name:
            continue
        quantity = item.get("quantity") or 1
        try:
            quantity = int(quantity)
        except Exception:
            quantity = 1
        cleaned_items.append(
            {
                "name": name,
                "quantity": quantity,
                "price": float(item.get("price") or item.get("unit_price") or 0),
            }
        )

    if not cleaned_items:
        return {
            "items": [],
            "summary": "لا توجد بنود إصلاح مسجلة في آخر زيارة",
        }

    summary_parts = []
    for item in cleaned_items[:4]:
        qty_suffix = f" ×{item['quantity']}" if item["quantity"] > 1 else ""
        summary_parts.append(f"{item['name']}{qty_suffix}")
    extra_count = max(0, len(cleaned_items) - 4)
    summary = "، ".join(summary_parts)
    if extra_count:
        summary += f" +{extra_count} أخرى"

    return {"items": cleaned_items, "summary": summary}


async def _list_archive_search_vehicles(provider: str) -> List[Dict[str, Any]]:
    if provider == "supabase":
        supa = SupabaseService()
        if supa.mock_mode:
            return _mem_read("vehicles")
        return supa.vehicles_list()

    if provider == "memory" or db is None:
        return _mem_read("vehicles")

    return await db.vehicles.find(
        {},
        {
            "_id": 0,
            "id": 1,
            "plateNumber": 1,
            "brand": 1,
            "model": 1,
            "year": 1,
            "customerName": 1,
            "customerPhone": 1,
            "fileNumber": 1,
            "vin": 1,
        },
    ).to_list(3000)


async def _get_latest_vehicle_visit(provider: str, vehicle_id: str) -> Optional[Dict[str, Any]]:
    if provider == "supabase":
        supa = SupabaseService()
        if supa.mock_mode:
            visits = [
                row for row in _mem_read("vehicle_visits") if row.get("vehicleId") == vehicle_id
            ]
            visits.sort(
                key=lambda row: str(
                    row.get("entryDate") or row.get("exitDate") or row.get("createdAt") or ""
                ),
                reverse=True,
            )
            return visits[0] if visits else None

        res = (
            supa.client.table("vehicle_visits")
            .select("*")
            .eq("vehicle_id", vehicle_id)
            .order("entry_date", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        return {
            "id": row.get("id"),
            "vehicleId": row.get("vehicle_id"),
            "entryDate": row.get("entry_date"),
            "exitDate": row.get("exit_date"),
            "status": row.get("status"),
            "mileage": row.get("mileage"),
            "notes": row.get("notes"),
            "createdAt": row.get("created_at"),
        }

    if provider == "memory" or db is None:
        visits = [row for row in _mem_read("vehicle_visits") if row.get("vehicleId") == vehicle_id]
        visits.sort(
            key=lambda row: str(
                row.get("entryDate") or row.get("exitDate") or row.get("createdAt") or ""
            ),
            reverse=True,
        )
        return visits[0] if visits else None

    rows = await db.vehicle_visits.find(
        {"vehicleId": vehicle_id}, {"_id": 0}
    ).sort("entryDate", -1).limit(1).to_list(1)
    if not rows:
        return None
    row = rows[0]
    for key in ("entryDate", "exitDate", "createdAt"):
        if row.get(key) and hasattr(row[key], "isoformat"):
            row[key] = row[key].isoformat()
    return row


async def _get_vehicle_visit_by_id(provider: str, visit_id: str, db=None):
    if not visit_id:
        return None
    if provider == "supabase":
        supa = SupabaseService()
        if supa.mock_mode:
            for visit in _mem_read("vehicle_visits"):
                if str(visit.get("id")) == str(visit_id):
                    return visit
            return None
        res = supa.client.table("vehicle_visits").select("*").eq("id", visit_id).limit(1).execute()
        rows = res.data or []
        return rows[0] if rows else None
    if provider == "memory" or db is None:
        visits = _mem_read("vehicle_visits")
        for visit in visits:
            if str(visit.get("id")) == str(visit_id):
                return visit
        return None
    row = await db.vehicle_visits.find_one({"id": visit_id}, {"_id": 0})
    if row:
        for key in ("entryDate", "exitDate", "createdAt"):
            if row.get(key) and hasattr(row[key], "isoformat"):
                row[key] = row[key].isoformat()
    return row


async def _append_operation_to_visit(payload: dict, operation: dict, provider: str, db=None, visit_data: dict = None):
    vehicle_id = payload.get("vehicleId") or payload.get("vehicle_id") or operation.get("vehicle_id")
    if not vehicle_id:
        return
    visit = visit_data or await _get_vehicle_visit_by_id(provider, payload.get("visitId"), db) or await _get_latest_vehicle_visit(provider, vehicle_id)
    if not visit:
        return

    notes_payload = _parse_notes_json(visit.get("notes"))
    items = notes_payload.get("items", [])
    payment_status = payload.get("paymentStatus") or payload.get("payment_status")

    for item in payload.get("items", []) or []:
        quantity = float(item.get("quantity") or 1)
        price = float(item.get("price") or item.get("unit_price") or item.get("unitPrice") or 0)
        total = float(item.get("total") or item.get("total_price") or (quantity * price))
        name = item.get("name") or item.get("description") or item.get("label") or item.get("itemName") or "عنصر"
        items.append({
            "name": name,
            "description": item.get("description") or name,
            "quantity": quantity,
            "price": price,
            "total": total,
            "itemType": item.get("itemType") or item.get("type") or payload.get("itemType"),
            "paymentStatus": payment_status,
            "operationId": operation.get("id"),
            "operationNumber": operation.get("operation_number") or operation.get("operationNumber"),
            "source": "operation",
            "createdAt": datetime.utcnow().isoformat(),
        })

    notes_payload["items"] = items
    notes_payload.setdefault("payments", [])
    notes_payload.setdefault("technicians", [])
    updated_notes = json.dumps(notes_payload, ensure_ascii=False)
    visit_id = visit.get("id")

    if provider == "supabase":
        supa = SupabaseService()
        if supa.mock_mode:
            visits = _mem_read("vehicle_visits")
            for row in visits:
                if str(row.get("id")) == str(visit_id):
                    row["notes"] = updated_notes
            _mem_write("vehicle_visits", visits)
        else:
            supa.client.table("vehicle_visits").update({"notes": updated_notes}).eq("id", visit_id).execute()
    elif provider == "memory" or db is None:
        visits = _mem_read("vehicle_visits")
        for row in visits:
            if str(row.get("id")) == str(visit_id):
                row["notes"] = updated_notes
        _mem_write("vehicle_visits", visits)
    else:
        await db.vehicle_visits.update_one({"id": visit_id}, {"$set": {"notes": updated_notes}})


async def _get_visit_archive_operations(provider: str, visit_id: str) -> List[Dict[str, Any]]:
    if not visit_id:
        return []

    if provider == "supabase":
        supa = SupabaseService()
        if supa.mock_mode:
            rows = [row for row in _mem_read("operations") if row.get("visitId") == visit_id]
            rows.sort(
                key=lambda row: str(row.get("createdAt") or row.get("date") or ""),
                reverse=True,
            )
            return rows
        res = (
            supa.client.table("operations")
            .select("*")
            .eq("visit_id", visit_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        rows = res.data or []
        return [
            {
                "id": row.get("id"),
                "items": row.get("items") or [],
                "paymentMethod": row.get("payment_method"),
                "total": row.get("total"),
                "date": row.get("op_date"),
                "createdAt": row.get("created_at"),
            }
            for row in rows
        ]

    if provider == "memory" or db is None:
        rows = [row for row in _mem_read("operations") if row.get("visitId") == visit_id]
        rows.sort(
            key=lambda row: str(row.get("createdAt") or row.get("date") or ""),
            reverse=True,
        )
        return rows

    rows = await db.operations.find(
        {"visitId": visit_id}, {"_id": 0}
    ).sort("createdAt", -1).limit(10).to_list(10)
    for row in rows:
        for key in ("date", "createdAt"):
            if row.get(key) and hasattr(row[key], "isoformat"):
                row[key] = row[key].isoformat()
    return rows


def _format_archive_response_text(vehicle: Dict[str, Any], latest_visit: Optional[Dict[str, Any]]) -> str:
    plate = vehicle.get("plateNumber") or vehicle.get("plate_number") or "-"
    vehicle_name = " ".join(
        str(part).strip()
        for part in [vehicle.get("brand"), vehicle.get("model"), vehicle.get("year")]
        if str(part or "").strip()
    )
    customer_name = vehicle.get("customerName") or vehicle.get("customer_name") or "-"

    if not latest_visit:
        return (
            f"تم العثور على المركبة {plate} ({vehicle_name or 'بدون وصف'}) للعميل {customer_name}، "
            "لكن لا توجد زيارة سابقة مسجلة لها."
        )

    visit_date = _humanize_archive_date(
        latest_visit.get("entryDate") or latest_visit.get("exitDate") or latest_visit.get("createdAt")
    )
    repairs = latest_visit.get("repairsSummary") or "لا توجد بنود إصلاح مسجلة"
    total_amount = latest_visit.get("totalAmount") or 0
    payment_method = latest_visit.get("paymentMethodLabel") or "غير محددة"
    return (
        f"آخر زيارة للمركبة {plate} ({vehicle_name or 'بدون وصف'}) كانت بتاريخ {visit_date}.\n"
        f"العميل: {customer_name}.\n"
        f"ما تم إصلاحه: {repairs}.\n"
        f"القيمة: {round(float(total_amount), 2)} ر.س.\n"
        f"طريقة الدفع: {payment_method}."
    )


@router.get("/vehicles/archive-search")
async def archive_search_latest_visit(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=10),
):
    """بحث أرشيفي سريع عن آخر زيارة عبر اسم العميل أو المركبة أو اللوحة."""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        search_terms = _extract_archive_search_terms(query)
        compact_query = search_terms.get("compact") or ""
        tokens = search_terms.get("tokens") or []

        if not compact_query and not tokens:
            return {
                "query": query,
                "interpretedQuery": "",
                "resultsCount": 0,
                "bestMatch": None,
                "results": [],
            }

        vehicles = await _list_archive_search_vehicles(provider)
        scored = []
        for vehicle in vehicles:
            match = _score_archive_vehicle_match(vehicle, compact_query, tokens)
            if match["score"] <= 0:
                continue
            scored.append({**match, "vehicle": vehicle})

        scored.sort(key=lambda row: row["score"], reverse=True)
        results = []
        for candidate in scored[: limit * 2]:
            vehicle = candidate["vehicle"]
            latest_visit = await _get_latest_vehicle_visit(provider, str(vehicle.get("id") or ""))
            operations = await _get_visit_archive_operations(
                provider, str((latest_visit or {}).get("id") or "")
            )
            parsed_notes = _parse_notes_json((latest_visit or {}).get("notes"))
            visit_financial = _calc_visit_financial(parsed_notes)

            repair_source = visit_financial.get("items") or []
            if not repair_source and operations:
                repair_source = operations[0].get("items") or []
            repair_data = _build_repair_summary(repair_source)

            latest_operation = operations[0] if operations else {}
            total_amount = visit_financial.get("total_amount") or float(
                latest_operation.get("total") or 0
            )
            payment_method = latest_operation.get("paymentMethod")
            payment_method_label = _payment_method_label(
                payment_method,
                visit_financial.get("payment_status"),
                float(visit_financial.get("total_paid") or 0),
            )

            latest_visit_payload = None
            if latest_visit:
                latest_visit_payload = {
                    "id": latest_visit.get("id"),
                    "entryDate": latest_visit.get("entryDate") or latest_visit.get("entry_date"),
                    "exitDate": latest_visit.get("exitDate") or latest_visit.get("exit_date"),
                    "status": latest_visit.get("status") or "-",
                    "repairs": repair_data["items"],
                    "repairsSummary": repair_data["summary"],
                    "totalAmount": round(float(total_amount or 0), 2),
                    "totalPaid": round(float(visit_financial.get("total_paid") or 0), 2),
                    "balance": round(float(visit_financial.get("balance") or 0), 2),
                    "paymentStatus": visit_financial.get("payment_status") or "unknown",
                    "paymentMethod": payment_method or "",
                    "paymentMethodLabel": payment_method_label,
                }

            vehicle_payload = {
                "id": vehicle.get("id"),
                "plateNumber": vehicle.get("plateNumber") or vehicle.get("plate_number"),
                "brand": vehicle.get("brand"),
                "model": vehicle.get("model"),
                "year": vehicle.get("year"),
                "customerName": vehicle.get("customerName") or vehicle.get("customer_name"),
                "customerPhone": vehicle.get("customerPhone") or vehicle.get("customer_phone"),
                "fileNumber": vehicle.get("fileNumber") or vehicle.get("file_number"),
            }

            result_item = {
                "matchScore": candidate["score"],
                "matchReasons": candidate.get("reasons") or [],
                "vehicle": vehicle_payload,
                "latestVisit": latest_visit_payload,
                "responseText": _format_archive_response_text(vehicle_payload, latest_visit_payload),
            }
            results.append(result_item)
            if len(results) >= limit:
                break

        return {
            "query": query,
            "interpretedQuery": search_terms.get("spaced") or compact_query,
            "resultsCount": len(results),
            "bestMatch": results[0] if results else None,
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vehicles/{vehicle_id}/financial-summary")
async def vehicle_financial_summary(vehicle_id: str):
    """Aggregate financial totals for a vehicle across all visits.

    Reads visit items/payments from visit.notes JSON (no schema changes).
    Returns workshop/suppliers/paid/balance + advance_paid.
    """
    try:
        try:
            uuid.UUID(str(vehicle_id))
        except Exception:
            raise HTTPException(status_code=404, detail="vehicle not found")

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider == "supabase":
            from supabase_service import SupabaseService
            from core.unified_financial_engine import fetch_vehicle_summary

            supa = SupabaseService()
            try:
                return fetch_vehicle_summary(supa.client, vehicle_id, os.environ.get("DEFAULT_WORKSHOP_ID", "finmodule-sync"))
            except ValueError:
                raise HTTPException(status_code=404, detail="vehicle not found")

        total_workshop = 0.0
        total_suppliers = 0.0
        total_paid = 0.0
        total_advance = 0.0
        total_paid_on_account = 0.0
        total_pending_payments = 0.0

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()
            vehicle_check = (
                supa.client.table("vehicles")
                .select("id")
                .eq("id", vehicle_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if not vehicle_check:
                raise HTTPException(status_code=404, detail="vehicle not found")

            res = (
                supa.client.table("vehicle_visits")
                .select("id, notes")
                .eq("vehicle_id", vehicle_id)
                .execute()
            )
            for r in (res.data or []):
                parsed = _parse_notes_json(r.get('notes'))
                fin = _calc_visit_financial(parsed)
                total_workshop += fin['total_workshop']
                total_suppliers += fin['total_suppliers']
                total_paid += fin['total_paid']
                total_advance += fin['advance_paid']
                total_paid_on_account += fin.get('paid_on_account', 0.0)
                total_pending_payments += fin.get('pending_payment_total', 0.0)

            try:
                operation_rows = (
                    supa.client.table("operations")
                    .select("id,type,total,items")
                    .eq("vehicle_id", vehicle_id)
                    .execute()
                    .data
                    or []
                )
                operation_ids = [str(row.get("id") or "").strip() for row in operation_rows if row.get("id")]
                operation_workshop_total = 0.0
                operation_supplier_total = 0.0
                for op_row in operation_rows:
                    op_type = str(op_row.get("type") or "").strip().lower()
                    if op_type in {"payment_order", "receipt_voucher", "settlement"}:
                        continue
                    parsed_items = op_row.get("items") or []
                    if isinstance(parsed_items, str):
                        try:
                            parsed_items = json.loads(parsed_items)
                        except Exception:
                            parsed_items = []
                    split = _split_operation_totals({**op_row, "items": parsed_items})
                    operation_workshop_total += split.get("workshop_total", 0.0)
                    operation_supplier_total += split.get("supplier_total", 0.0)

                if operation_workshop_total > total_workshop:
                    total_workshop = operation_workshop_total
                if operation_supplier_total > total_suppliers:
                    total_suppliers = operation_supplier_total

                if operation_ids:
                    payment_rows = (
                        supa.client.table("journal_entries")
                        .select("total,source,reference_id")
                        .in_("reference_id", operation_ids)
                        .in_("source", ["operation_payment", "supplier_balance_payment"])
                        .execute()
                        .data
                        or []
                    )
                    operation_paid = sum(float(row.get("total") or 0) for row in payment_rows)
                    if operation_paid > 0:
                        total_paid = max(total_paid, operation_paid)
                        total_paid_on_account = max(total_paid_on_account, operation_paid)
            except Exception as summary_link_error:
                print(f"Vehicle financial summary operation-link warning: {summary_link_error}")

        else:
            exists = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0, "id": 1})
            if not exists:
                raise HTTPException(status_code=404, detail="vehicle not found")

            docs = await db.vehicle_visits.find({"vehicleId": vehicle_id}, {"_id": 0, "notes": 1}).to_list(2000)
            for d in docs:
                parsed = _parse_notes_json(d.get('notes'))
                fin = _calc_visit_financial(parsed)
                total_workshop += fin['total_workshop']
                total_suppliers += fin['total_suppliers']
                total_paid += fin['total_paid']
                total_advance += fin['advance_paid']
                total_paid_on_account += fin.get('paid_on_account', 0.0)
                total_pending_payments += fin.get('pending_payment_total', 0.0)

        total_amount = total_workshop
        applied_paid = min(total_paid, total_amount)
        balance = max(total_amount - applied_paid, 0.0)
        customer_credit = max(total_paid - total_amount, 0.0)
        workshop_receivable_balance = max(total_amount - applied_paid, 0.0)
        customer_advance_liability = customer_credit

        return {
            "total_workshop": round(total_workshop, 2),
            "total_suppliers": round(total_suppliers, 2),
            "supplier_archive_total": round(total_suppliers, 2),
            "supplier_cost_total": round(total_suppliers, 2),
            "parts_charge_total": round(total_suppliers, 2),
            "current_customer_due": round(total_workshop, 2),
            "workshop_service_total": round(total_workshop, 2),
            "final_customer_total": None,
            "customer_charge_total": round(total_amount, 2),
            "customer_total": round(total_amount, 2),
            "total_paid": round(total_paid, 2),
            "advance_paid": round(total_advance, 2),
            "paid_on_account": round(total_paid_on_account, 2),
            "confirmed_paid": round(total_paid_on_account, 2),
            "pending_payment_total": round(total_pending_payments, 2),
            "applied_paid": round(applied_paid, 2),
            "customer_credit": round(customer_credit, 2),
            "total_amount": round(total_amount, 2),
            "total_items": round(total_amount, 2),
            "balance": round(balance, 2),
            "display_remaining": round(balance, 2),
            "workshop_receivable_balance": round(workshop_receivable_balance, 2),
            "customer_advance_liability": round(customer_advance_liability, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finance-engine/visits/{visit_id}/payments/confirm")
async def unified_confirm_visit_payment(request: Request, visit_id: str, payload: Dict[str, Any] = Body(None)):
    """Unified SSOT path for new confirmed visit payments.

    New payments are confirmed immediately, written once to visit notes with the
    linked journal entry id, and posted to journal_entries as a confirmed cash/bank/POS receipt.
    Historical payments are not migrated or modified by this endpoint.
    """
    payload = dict(payload or {})
    try:
        uuid.UUID(str(visit_id))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid visit id")

    provider = os.environ.get("DB_PROVIDER", "mongo").lower()
    if provider != "supabase":
        raise HTTPException(status_code=400, detail="unified finance engine supports supabase provider only")

    actor = await _require_finance_payment_permission(request)

    try:
        from supabase_service import SupabaseService
        from core.unified_financial_engine import (
            build_visit_payment_journal_entry,
            fetch_vehicle_summary,
            normalize_method,
            parse_notes,
            round2,
            serialize_notes,
        )

        amount = round2(payload.get("amount"))
        if amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be greater than zero")
        max_payment_amount = float(os.environ.get("MAX_UNIFIED_PAYMENT_AMOUNT", "1000000"))
        if amount > max_payment_amount:
            raise HTTPException(status_code=400, detail="amount exceeds allowed limit")
        method = normalize_method(payload.get("method") or payload.get("payment_method") or "cash")
        idempotency_key = str(
            request.headers.get("Idempotency-Key")
            or request.headers.get("X-Idempotency-Key")
            or payload.get("payment_id")
            or payload.get("id")
            or ""
        ).strip()
        payment_id = idempotency_key or str(uuid.uuid4())
        date_value = payload.get("date") or datetime.now(timezone.utc).date().isoformat()
        reference = str(payload.get("reference") or "").strip()
        # Tenant/workshop scope is server-derived only; ignore caller-supplied workshop_id.
        workshop_id = os.environ.get("DEFAULT_WORKSHOP_ID", "finmodule-sync")

        supa = SupabaseService()
        visit_rows = (
            supa.client.table("vehicle_visits")
            .select("id,vehicle_id,notes,status,entry_date,created_at")
            .eq("id", visit_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not visit_rows:
            raise HTTPException(status_code=404, detail="visit not found")
        visit = visit_rows[0]
        vehicle_id = str(visit.get("vehicle_id") or "").strip()
        vehicle_rows = (
            supa.client.table("vehicles")
            .select("*")
            .eq("id", vehicle_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not vehicle_rows:
            raise HTTPException(status_code=404, detail="vehicle not found")
        vehicle = vehicle_rows[0]

        parsed = parse_notes(visit.get("notes"))
        payments = parsed.setdefault("payments", [])
        for existing in payments:
            if str((existing or {}).get("id") or (existing or {}).get("payment_id") or "") == payment_id:
                summary = fetch_vehicle_summary(supa.client, vehicle_id, workshop_id)
                return {"success": True, "idempotent_replay": True, "payment": existing, "summary": summary}

        journal_entry = build_visit_payment_journal_entry(
            visit=visit,
            vehicle=vehicle,
            amount=amount,
            method=method,
            date_value=date_value,
            payment_id=payment_id,
            workshop_id=workshop_id,
        )
        if payload.get("dry_run") is True:
            current_summary = fetch_vehicle_summary(supa.client, vehicle_id, workshop_id)
            customer_total = float(current_summary.get("customer_total") or 0)
            confirmed_after = float(current_summary.get("confirmed_paid") or 0) + amount
            applied_after = min(confirmed_after, customer_total)
            preview_summary = {
                **current_summary,
                "confirmed_paid": round(confirmed_after, 2),
                "total_paid": round(confirmed_after, 2),
                "applied_paid": round(applied_after, 2),
                "display_remaining": round(max(customer_total - applied_after, 0), 2),
                "balance": round(max(customer_total - applied_after, 0), 2),
                "customer_credit": round(max(confirmed_after - customer_total, 0), 2),
                "customer_advance_liability": round(max(confirmed_after - customer_total, 0), 2),
            }
            return {
                "success": True,
                "dry_run": True,
                "payment": {
                    "id": payment_id,
                    "status": "confirmed",
                    "confirmed": True,
                    "amount": amount,
                    "method": method,
                    "source": "unified_financial_engine",
                },
                "journal_preview": journal_entry,
                "summary": preview_summary,
                "engine_version": "unified-v1",
            }
        inserted = _safe_insert_journal_entry(supa, journal_entry)
        inserted_row = (inserted or [{}])[0] if isinstance(inserted, list) else (inserted or journal_entry)
        journal_id = inserted_row.get("id") or journal_entry["id"]

        payment_row = {
            "id": payment_id,
            "payment_id": payment_id,
            "kind": "payment",
            "status": "confirmed",
            "confirmed": True,
            "amount": amount,
            "date": date_value,
            "method": method,
            "paymentMethod": method,
            "reference": reference,
            "journalEntryId": journal_id,
            "journal_entry_id": journal_id,
            "source": "unified_financial_engine",
            "confirmed_by": actor.name or actor.id,
            "confirmed_role": actor.role,
        }
        payments.append(payment_row)
        try:
            supa.client.table("vehicle_visits").update({"notes": serialize_notes(parsed)}).eq("id", visit_id).execute()
        except Exception as update_error:
            try:
                from core import accounting_engine
                accounting_engine.reverse_entry(
                    journal_id=journal_id,
                    reason="vehicle_payment_notes_update_failed",
                    actor={"user_id": actor.name or actor.id, "role": actor.role},
                    workshop_id=workshop_id,
                )
            except Exception as reverse_error:
                print(f"unified payment reverse compensation failed: {reverse_error}")
            raise update_error

        summary = fetch_vehicle_summary(supa.client, vehicle_id, workshop_id)
        return {
            "success": True,
            "payment": payment_row,
            "journal_entry_id": journal_id,
            "summary": summary,
            "engine_version": "unified-v1",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vehicles/{vehicle_id}/visits")
async def get_vehicle_visits(vehicle_id: str):
    """Get all visits for a vehicle"""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()
            res = (
                supa.client.table("vehicle_visits")
                .select("*")
                .eq("vehicle_id", vehicle_id)
                .order("entry_date", desc=True)
                .execute()
            )
            rows = res.data or []
            visit_numbers = _apply_visit_numbers(rows)
            paid_by_visit: Dict[str, float] = {}
            try:
                visit_ids = [str(r.get("id") or "").strip() for r in rows if r.get("id")]
                if visit_ids:
                    op_rows = (
                        supa.client.table("operations")
                        .select("id,visit_id")
                        .in_("visit_id", visit_ids)
                        .execute()
                        .data
                        or []
                    )
                    op_to_visit = {
                        str(row.get("id") or "").strip(): str(row.get("visit_id") or "").strip()
                        for row in op_rows
                        if row.get("id") and row.get("visit_id")
                    }
                    if op_to_visit:
                        payment_rows = (
                            supa.client.table("journal_entries")
                            .select("reference_id,total,source")
                            .in_("reference_id", list(op_to_visit.keys()))
                            .in_("source", ["operation_payment", "supplier_balance_payment"])
                            .execute()
                            .data
                            or []
                        )
                        for payment_row in payment_rows:
                            visit_ref = op_to_visit.get(str(payment_row.get("reference_id") or "").strip())
                            if visit_ref:
                                paid_by_visit[visit_ref] = paid_by_visit.get(visit_ref, 0.0) + float(payment_row.get("total") or 0)
            except Exception as visit_payment_error:
                print(f"Vehicle visits payment-link warning: {visit_payment_error}")
            enriched = []
            for r in rows:
                parsed = _parse_notes_json(r.get('notes'))
                fin = _calc_visit_financial(parsed)
                extra_paid = paid_by_visit.get(str(r.get("id") or "").strip(), 0.0)
                if extra_paid:
                    fin["total_paid"] = round(float(fin.get("total_paid") or 0) + extra_paid, 2)
                    fin["balance"] = round(max(float(fin.get("total_amount") or 0) - float(fin.get("total_paid") or 0), 0), 2)
                    fin["payment_status"] = "paid_full" if fin["balance"] <= 0.01 else "partial"
                number_info = visit_numbers.get(str(r.get("id") or ""), {})

                out = {
                    "id": r.get("id"),
                    "vehicleId": r.get("vehicle_id"),
                    "entryDate": r.get("entry_date"),
                    "exitDate": r.get("exit_date"),
                    "status": r.get("status"),
                    "mileage": r.get("mileage"),
                    "notes": r.get("notes"),
                    "technicianId": r.get("technician_id"),
                    "createdAt": r.get("created_at"),
                    **number_info,
                    **fin,
                }
                enriched.append(out)
            return enriched

        # MongoDB fallback
        docs = (
            await db.vehicle_visits.find({"vehicleId": vehicle_id}, {"_id": 0})
            .sort("entryDate", -1)
            .to_list(length=1000)
        )
        visit_numbers = _apply_visit_numbers(docs)
        enriched = []
        for d in docs:
            for k in ("entryDate", "exitDate", "createdAt"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            parsed = _parse_notes_json(d.get('notes'))
            fin = _calc_visit_financial(parsed)
            d.update(fin)
            d.update(visit_numbers.get(str(d.get("id") or ""), {}))

            # previous unpaid (older open visit with positive balance)
            try:
                vn = int(d.get('visitNumber') or d.get('visit_number') or 0)
            except Exception:
                vn = 0
            if vn:
                prev = await db.vehicle_visits.find_one(
                    {
                        "vehicleId": vehicle_id,
                        "$expr": {"$lt": ["$visitNumber", vn]},
                    },
                    {"_id": 0},
                )
                if prev:
                    prev_parsed = _parse_notes_json(prev.get('notes'))
                    prev_fin = _calc_visit_financial(prev_parsed)
                    if prev_fin.get('balance', 0) > 0:
                        d['previous_unpaid'] = {
                            'visit_number': prev.get('visitNumber') or prev.get('visit_number'),
                            'balance': prev_fin.get('balance'),
                        }
            enriched.append(d)

        return enriched
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vehicles/{vehicle_id}/visits")
async def create_visit(vehicle_id: str, payload: Dict[str, Any] = Body(...)):
    """Create a new visit for a vehicle"""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        visit_id = str(uuid.uuid4())
        visit_number = await _next_visit_number(provider, vehicle_id)
        notes_with_number = _with_visit_number_in_notes(payload.get("notes", ""), visit_number)

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()

            row = {
                "id": visit_id,
                "vehicle_id": vehicle_id,
                "entry_date": payload.get("entryDate")
                or datetime.now(timezone.utc).isoformat(),
                "exit_date": payload.get("exitDate"),
                "status": payload.get("status", "in_progress"),
                "mileage": payload.get("mileage"),
                "notes": notes_with_number,
                "technician_id": payload.get("technicianId"),
            }

            res = supa.client.table("vehicle_visits").insert(row).execute()
            r = (res.data or [{}])[0]

            # --- SYNC TO OPERATIONS (FINANCE) ---
            if "notes" in payload:
                await _sync_visit_to_operation(visit_id, r, supa_service=supa)
            # ------------------------------------

            return {
                "id": r.get("id"),
                "vehicleId": r.get("vehicle_id"),
                "entryDate": r.get("entry_date"),
                "exitDate": r.get("exit_date"),
                "status": r.get("status"),
                "mileage": r.get("mileage"),
                "notes": r.get("notes"),
                "technicianId": r.get("technician_id"),
                "createdAt": r.get("created_at"),
                "visitNumber": visit_number,
                "visitNumberDisplay": visit_number,
            }

        # MongoDB fallback
        doc = {
            "id": visit_id,
            "vehicleId": vehicle_id,
            "visitNumber": int(visit_number),
            "visitNumberDisplay": visit_number,
            "entryDate": payload.get("entryDate") or datetime.now(timezone.utc),
            "exitDate": payload.get("exitDate"),
            "status": payload.get("status", "in_progress"),
            "mileage": payload.get("mileage"),
            "notes": notes_with_number,
            "technicianId": payload.get("technicianId"),
            "createdAt": datetime.now(timezone.utc),
        }

        await db.vehicle_visits.insert_one(doc)
        
        # --- SYNC TO OPERATIONS (MONGO) ---
        if "notes" in payload:
             doc_norm = {**doc, "vehicleId": vehicle_id}
             await _sync_visit_to_operation(visit_id, doc_norm, supa_service=None)
        # ----------------------------------

        doc.pop("_id", None)
        for k in ("entryDate", "exitDate", "createdAt"):
            if doc.get(k) and hasattr(doc[k], "isoformat"):
                doc[k] = doc[k].isoformat()
        doc["visitNumber"] = visit_number
        return doc
    except Exception as e:
        import traceback
        print(f"❌ Create Visit Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create visit: {str(e)}")


@router.get("/visits/{visit_id}/operations")
async def get_visit_operations(visit_id: str):
    """Get all operations for a specific visit"""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()
            res = (
                supa.client.table("operations")
                .select("*")
                .eq("visit_id", visit_id)
                # In Supabase schema the operation date column is `op_date` (not `date`).
                .order("op_date", desc=True)
                .execute()
            )
            return res.data or []

        # MongoDB fallback
        docs = (
            await db.operations.find({"visitId": visit_id}, {"_id": 0})
            .sort("date", -1)
            .to_list(length=1000)
        )
        for d in docs:
            if d.get("date") and hasattr(d["date"], "isoformat"):
                d["date"] = d["date"].isoformat()
        return docs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/visits/{visit_id}")
async def update_visit(visit_id: str, payload: Dict[str, Any] = Body(...)):
    """Update a visit"""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        print(f"📝 Update Visit {visit_id[:8]}: keys={list(payload.keys())} status={payload.get('status','--')}")

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()

            upd = {}
            if "exitDate" in payload:
                upd["exit_date"] = payload["exitDate"]
            if "status" in payload:
                upd["status"] = payload["status"]
            if "mileage" in payload:
                upd["mileage"] = payload["mileage"]
            if "notes" in payload:
                upd["notes"] = payload["notes"]
            if "technicianId" in payload:
                upd["technician_id"] = payload["technicianId"]

            res = (
                supa.client.table("vehicle_visits")
                .update(upd)
                .eq("id", visit_id)
                .execute()
            )
            if not res.data:
                raise HTTPException(status_code=404, detail="Visit not found")
            r = res.data[0]
            print(f"   Visit updated in DB: status={r.get('status')} notes_len={len(r.get('notes','') or '')}")
            
            # --- Balance check (non-blocking): log only if workshop balance unpaid ---
            if payload.get("status") == "completed":
                parsed_notes = _parse_notes_json(upd.get("notes") or r.get("notes"))
                fin = _calc_visit_financial(parsed_notes)
                # الموردون وحدة أرشيفية منفصلة — الفحص على رصيد الورشة فقط
                workshop_balance = round(fin.get('total_workshop', 0) - fin.get('total_paid', 0), 2)
                if workshop_balance > 0.01:
                    print(f"   [INFO] Visit closed with outstanding workshop balance: {workshop_balance:.2f} SAR")

            # Make sure we return 4xx properly (Cloudflare 520 appears when unhandled)
            if payload.get("status") == "completed":
                # validation already done above
                pass

            # --- SYNC TO OPERATIONS (FINANCE) ---
            if "notes" in payload or "status" in payload:
                sync_payload = {**payload, "id": visit_id}
                if r:
                    sync_payload = {**sync_payload, **r}
                if not sync_payload.get("vehicle_id") and not sync_payload.get("vehicleId"):
                    try:
                        existing = (
                            supa.client.table("vehicle_visits")
                            .select("vehicle_id")
                            .eq("id", visit_id)
                            .limit(1)
                            .execute()
                        )
                        row = (existing.data or [None])[0]
                        if row and row.get("vehicle_id"):
                            sync_payload["vehicle_id"] = row.get("vehicle_id")
                    except Exception:
                        pass
                await _sync_visit_to_operation(visit_id, sync_payload, supa_service=supa)
            # ------------------------------------

            result = {
                "id": r.get("id"),
                "vehicleId": r.get("vehicle_id"),
                "entryDate": r.get("entry_date"),
                "exitDate": r.get("exit_date"),
                "status": r.get("status"),
                "mileage": r.get("mileage"),
                "notes": r.get("notes"),
                "technicianId": r.get("technician_id"),
            }

            # --- AUTO WHATSAPP NOTIFICATION on completion ---
            if payload.get("status") == "completed":
                try:
                    vehicle_id = r.get("vehicle_id")
                    v_res = supa.client.table("vehicles").select("plate_number,customer_name,customer_phone").eq("id", vehicle_id).single().execute()
                    if v_res.data:
                        phone = v_res.data.get("customer_phone", "")
                        customer_name = v_res.data.get("customer_name", "عميل")
                        plate = v_res.data.get("plate_number", "")
                        # Parse items total
                        total = 0
                        try:
                            notes_raw = r.get("notes", "")
                            if notes_raw and isinstance(notes_raw, str) and notes_raw.strip().startswith("{"):
                                parsed = json.loads(notes_raw)
                                items = parsed.get("items", [])
                                total = sum(float(it.get("price", 0)) * float(it.get("quantity", 1)) for it in items)
                        except Exception:
                            pass
                        total_str = f"{total:,.0f}" if total else ""
                        msg = (
                            f"السلام عليكم {customer_name}\n\n"
                            f"نفيدكم بأن مركبتكم ({plate}) جاهزة للاستلام.\n"
                        )
                        if total_str:
                            msg += f"المبلغ المستحق: {total_str} ر.س\n"
                        msg += "\nشاكرين ثقتكم بنا."
                        if phone:
                            import urllib.parse
                            norm = "".join([c for c in phone if c.isdigit()])
                            if norm.startswith("05"):
                                norm = "966" + norm[1:]
                            elif norm.startswith("5") and len(norm) == 9:
                                norm = "966" + norm
                            elif not norm.startswith("966"):
                                norm = "966" + norm
                            encoded = urllib.parse.quote(msg)
                            result["whatsappNotification"] = {
                                "url": f"https://api.whatsapp.com/send?phone={norm}&text={encoded}",
                                "phone": norm,
                                "message": msg,
                                "customerName": customer_name,
                            }
                            print(f"   WhatsApp notification prepared for {customer_name} ({norm})")
                except Exception as e:
                    print(f"   WhatsApp notification prep failed: {e}")
            # ------------------------------------------------

            return result

        # MongoDB fallback
        upd = {}
        if "exitDate" in payload:
            upd["exitDate"] = payload["exitDate"]
        if "status" in payload:
            upd["status"] = payload["status"]
        if "mileage" in payload:
            upd["mileage"] = payload["mileage"]
        if "notes" in payload:
            upd["notes"] = payload["notes"]
        if "technicianId" in payload:
            upd["technicianId"] = payload["technicianId"]

        await db.vehicle_visits.update_one({"id": visit_id}, {"$set": upd})
        doc = await db.vehicle_visits.find_one({"id": visit_id}, {"_id": 0})
        
        # --- SYNC TO OPERATIONS (MONGO) ---
        if "notes" in payload or "status" in payload:
             # Normalize doc for helper
             doc_norm = {**doc, "vehicleId": doc.get("vehicleId")}
             await _sync_visit_to_operation(visit_id, doc_norm, supa_service=None)
        # ----------------------------------

        for k in ("entryDate", "exitDate", "createdAt"):
            if doc.get(k) and hasattr(doc[k], "isoformat"):
                doc[k] = doc[k].isoformat()
        return doc or {}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------- Database Initialization Endpoint ---------------------


@router.delete("/visits/{visit_id}")
async def delete_visit(visit_id: str):
    """Delete a visit (including closed visits)"""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        # Supabase implementation
        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()

            # Reverse related journals first (No Hard Delete)
            try:
                from core import accounting_engine
                reverse_result = accounting_engine.reverse_entry(
                    reference_id=visit_id,
                    reason="visit_delete_requested",
                    actor={"user_id": "routes_extended.delete_visit"},
                )
                if reverse_result.get("error") and reverse_result.get("error") != "original_not_found":
                    raise HTTPException(status_code=409, detail=reverse_result)
            except Exception as je:
                raise HTTPException(status_code=409, detail={"error": "visit_journal_reverse_failed", "detail": str(je)}) from je
            try:
                supa.client.table("operations").delete().eq("visit_id", visit_id).execute()
            except Exception:
                pass

            res = supa.client.table("vehicle_visits").delete().eq("id", visit_id).execute()
            if not (res.data and len(res.data) > 0):
                raise HTTPException(status_code=404, detail="Visit not found")
            return {"success": True}

        # MongoDB implementation (legacy)
        await db.operations.delete_many({"visitId": visit_id})
        result = await db.vehicle_visits.delete_one({"id": visit_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Visit not found")
        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/init-database")
async def init_database():
    """Initialize database tables and default data"""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()

            results = {
                "images_column": False,
                "accounts_table": False,
                "default_accounts": False,
                "errors": [],
            }

            # Step 1: Add images column to approval_requests
            try:
                # Check if column exists
                supa.client.table("approval_requests").select("images").limit(1).execute()
                results["images_column"] = True
                results["messages"] = ["images column already exists"]
            except Exception as e:
                error_msg = str(e)
                if "images" in error_msg and "column" in error_msg.lower():
                    # Column doesn't exist, need to add it manually
                    results["errors"].append(
                        "images column needs manual addition in Supabase Dashboard"
                    )
                else:
                    results["images_column"] = True

            # Step 2: Create accounts table by trying to insert
            try:
                # Try to query accounts table
                existing_accounts = (
                    supa.client.table("accounts").select("*").limit(1).execute()
                )
                results["accounts_table"] = True

                # Check if we need to insert default accounts
                if not existing_accounts.data:
                    # Insert default accounts
                    default_accounts = [
                        {
                            "id": "acc-1000",
                            "code": "1000",
                            "name": "الأصول",
                            "name_en": "Assets",
                            "type": "asset",
                            "parent_id": None,
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1100",
                            "code": "1100",
                            "name": "الأصول المتداولة",
                            "name_en": "Current Assets",
                            "type": "asset",
                            "parent_id": "acc-1000",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1101",
                            "code": "1101",
                            "name": "النقد",
                            "name_en": "Cash",
                            "type": "asset",
                            "parent_id": "acc-1100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1102",
                            "code": "1102",
                            "name": "البنك",
                            "name_en": "Bank",
                            "type": "asset",
                            "parent_id": "acc-1100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1103",
                            "code": "1103",
                            "name": "العملاء",
                            "name_en": "Accounts Receivable",
                            "type": "asset",
                            "parent_id": "acc-1100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1105",
                            "code": "1105",
                            "name": "مخزون قطع غيار",
                            "name_en": "Spare Parts Inventory",
                            "type": "asset",
                            "parent_id": "acc-1100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1106",
                            "code": "1106",
                            "name": "مخزون مستهلكات",
                            "name_en": "Consumables Inventory",
                            "type": "asset",
                            "parent_id": "acc-1100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1200",
                            "code": "1200",
                            "name": "الأصول الثابتة",
                            "name_en": "Fixed Assets",
                            "type": "asset",
                            "parent_id": "acc-1000",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1201",
                            "code": "1201",
                            "name": "معدات ميكانيكية",
                            "name_en": "Mechanical Equipment",
                            "type": "asset",
                            "parent_id": "acc-1200",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1202",
                            "code": "1202",
                            "name": "رافعات سيارات",
                            "name_en": "Car Lifts",
                            "type": "asset",
                            "parent_id": "acc-1200",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1203",
                            "code": "1203",
                            "name": "أجهزة فحص",
                            "name_en": "Diagnostic Tools",
                            "type": "asset",
                            "parent_id": "acc-1200",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-1207",
                            "code": "1207",
                            "name": "مجمع الإهلاك",
                            "name_en": "Accumulated Depreciation",
                            "type": "asset",
                            "parent_id": "acc-1200",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-2000",
                            "code": "2000",
                            "name": "الخصوم",
                            "name_en": "Liabilities",
                            "type": "liability",
                            "parent_id": None,
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-2100",
                            "code": "2100",
                            "name": "الخصوم المتداولة",
                            "name_en": "Current Liabilities",
                            "type": "liability",
                            "parent_id": "acc-2000",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-2101",
                            "code": "2101",
                            "name": "الموردون",
                            "name_en": "Accounts Payable",
                            "type": "liability",
                            "parent_id": "acc-2100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-2102",
                            "code": "2102",
                            "name": "مصروفات مستحقة",
                            "name_en": "Accrued Expenses",
                            "type": "liability",
                            "parent_id": "acc-2100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-2103",
                            "code": "2103",
                            "name": "رواتب مستحقة",
                            "name_en": "Accrued Salaries",
                            "type": "liability",
                            "parent_id": "acc-2100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-3000",
                            "code": "3000",
                            "name": "حقوق الملكية",
                            "name_en": "Equity",
                            "type": "equity",
                            "parent_id": None,
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-3100",
                            "code": "3100",
                            "name": "حقوق المالك",
                            "name_en": "Owner's Equity",
                            "type": "equity",
                            "parent_id": "acc-3000",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-3101",
                            "code": "3101",
                            "name": "رأس المال",
                            "name_en": "Owner Capital",
                            "type": "equity",
                            "parent_id": "acc-3100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-3102",
                            "code": "3102",
                            "name": "مسحوبات المالك",
                            "name_en": "Owner Drawings",
                            "type": "equity",
                            "parent_id": "acc-3100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-3103",
                            "code": "3103",
                            "name": "أرباح محتجزة",
                            "name_en": "Retained Earnings",
                            "type": "equity",
                            "parent_id": "acc-3100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-3104",
                            "code": "3104",
                            "name": "صافي الربح/الخسارة",
                            "name_en": "Net Profit/Loss",
                            "type": "equity",
                            "parent_id": "acc-3100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-4000",
                            "code": "4000",
                            "name": "الإيرادات",
                            "name_en": "Revenue",
                            "type": "revenue",
                            "parent_id": None,
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-4100",
                            "code": "4100",
                            "name": "إيرادات الخدمات",
                            "name_en": "Service Revenue",
                            "type": "revenue",
                            "parent_id": "acc-4000",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-4101",
                            "code": "4101",
                            "name": "إيرادات خدمات ميكانيكية",
                            "name_en": "Mechanical Service Revenue",
                            "type": "revenue",
                            "parent_id": "acc-4100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-4102",
                            "code": "4102",
                            "name": "إيرادات إصلاح محركات",
                            "name_en": "Engine Repair Revenue",
                            "type": "revenue",
                            "parent_id": "acc-4100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-4103",
                            "code": "4103",
                            "name": "إيرادات فرامل وتعليق",
                            "name_en": "Brake & Suspension Revenue",
                            "type": "revenue",
                            "parent_id": "acc-4100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-5000",
                            "code": "5000",
                            "name": "تكلفة الخدمات",
                            "name_en": "Cost of Services",
                            "type": "expense",
                            "parent_id": None,
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-5100",
                            "code": "5100",
                            "name": "تكاليف مباشرة",
                            "name_en": "Direct Costs",
                            "type": "expense",
                            "parent_id": "acc-5000",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-5101",
                            "code": "5101",
                            "name": "أجور فنيين مباشرة",
                            "name_en": "Technicians Wages - Direct",
                            "type": "expense",
                            "parent_id": "acc-5100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-5102",
                            "code": "5102",
                            "name": "قطع غيار مستخدمة",
                            "name_en": "Spare Parts Used",
                            "type": "expense",
                            "parent_id": "acc-5100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-5103",
                            "code": "5103",
                            "name": "مستهلكات مستخدمة",
                            "name_en": "Consumables Used",
                            "type": "expense",
                            "parent_id": "acc-5100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-6000",
                            "code": "6000",
                            "name": "المصروفات التشغيلية",
                            "name_en": "Operating Expenses",
                            "type": "expense",
                            "parent_id": None,
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-6100",
                            "code": "6100",
                            "name": "مصروفات عامة وإدارية",
                            "name_en": "General & Administrative",
                            "type": "expense",
                            "parent_id": "acc-6000",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-6101",
                            "code": "6101",
                            "name": "رواتب إدارية",
                            "name_en": "Administrative Salaries",
                            "type": "expense",
                            "parent_id": "acc-6100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-6102",
                            "code": "6102",
                            "name": "إيجار المركز",
                            "name_en": "Workshop Rent",
                            "type": "expense",
                            "parent_id": "acc-6100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-6103",
                            "code": "6103",
                            "name": "كهرباء ومياه",
                            "name_en": "Electricity & Water",
                            "type": "expense",
                            "parent_id": "acc-6100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-6104",
                            "code": "6104",
                            "name": "صيانة معدات",
                            "name_en": "Equipment Maintenance",
                            "type": "expense",
                            "parent_id": "acc-6100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                        {
                            "id": "acc-6105",
                            "code": "6105",
                            "name": "ملابس وسلامة مهنية",
                            "name_en": "Uniforms & Safety",
                            "type": "expense",
                            "parent_id": "acc-6100",
                            "is_system": True,
                            "balance": 0.0,
                        },
                    ]

                    try:
                        supa.client.table("accounts").insert(default_accounts).execute()
                        results["default_accounts"] = True
                        results["accounts_created"] = len(default_accounts)
                    except Exception as e:
                        results["errors"].append(
                            f"Failed to insert accounts: {str(e)[:100]}"
                        )
                else:
                    results["default_accounts"] = True
                    results["accounts_created"] = len(existing_accounts.data)
                    results["message"] = "Accounts already exist"

            except Exception as e:
                error_msg = str(e)
                if "accounts" in error_msg and "schema cache" in error_msg.lower():
                    results["errors"].append(
                        "accounts table does not exist - needs manual creation in Supabase Dashboard"
                    )
                else:
                    results["errors"].append(
                        f"Error with accounts table: {str(e)[:100]}"
                    )

            return results

        # MongoDB - just return success
        return {
            "message": "MongoDB does not require initialization",
            "provider": "mongo",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


