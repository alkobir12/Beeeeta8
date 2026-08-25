"""
📊 Accounts / Chart of Accounts Router (extracted from routes_extended.py)

Domain: All endpoints under /api/accounts/* — listing, CRUD, tree view, status
overrides, display-code reindex, transactions, sparkline, usage tracking,
reconciliation report, export, and default initialization.

Extracted from routes_extended.py (lines 5094-7059) on 2026-02-11.
URL paths preserved as-is.
"""

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request

try:
    import openpyxl
except Exception:
    openpyxl = None

from mem_store import _mem_read, _mem_write
from supabase_service import SupabaseService

router = APIRouter(prefix="/api", tags=["accounts"])

# Injected by server.py via set_db(database)
db = None


def set_db(database):
    global db
    db = database


# --------------------- Chart of Accounts APIs ---------------------
async def _account_status_overrides_map() -> Dict[str, bool]:
    try:
        if db is not None:
            rows = await db.account_status_overrides.find({}, {"_id": 0}).to_list(5000)
            return {
                str(row.get("accountId")): bool(row.get("isActive", True))
                for row in rows
                if row.get("accountId")
            }

        rows = _mem_read("account_status_overrides")
        return {
            str(row.get("accountId")): bool(row.get("isActive", True))
            for row in rows
            if row.get("accountId")
        }
    except Exception:
        return {}


async def _set_account_status_override(account_id: str, is_active: bool):
    doc = {
        "accountId": account_id,
        "isActive": bool(is_active),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if db is not None:
        await db.account_status_overrides.update_one(
            {"accountId": account_id}, {"$set": doc}, upsert=True
        )
        return

    rows = _mem_read("account_status_overrides")
    replaced = False
    for i, row in enumerate(rows):
        if row.get("accountId") == account_id:
            rows[i] = doc
            replaced = True
            break
    if not replaced:
        rows.append(doc)
    _mem_write("account_status_overrides", rows)


async def _remove_account_status_override(account_id: str):
    if db is not None:
        await db.account_status_overrides.delete_one({"accountId": account_id})
        return

    rows = _mem_read("account_status_overrides")
    rows = [row for row in rows if row.get("accountId") != account_id]
    _mem_write("account_status_overrides", rows)


async def _account_usage_map() -> Dict[str, str]:
    global _USAGE_MAP_CACHE, _USAGE_MAP_CACHE_AT
    now_ts = time.time()
    if _USAGE_MAP_CACHE is not None and (now_ts - _USAGE_MAP_CACHE_AT) < _USAGE_MAP_CACHE_TTL:
        return _USAGE_MAP_CACHE
    try:
        if db is not None:
            rows = await db.account_usage.find({}, {"_id": 0}).to_list(5000)
            result = {
                str(row.get("accountId")): str(row.get("lastUsedAt"))
                for row in rows
                if row.get("accountId")
            }
            _USAGE_MAP_CACHE = result
            _USAGE_MAP_CACHE_AT = now_ts
            return result
        rows = _mem_read("account_usage")
        result = {
            str(row.get("accountId")): str(row.get("lastUsedAt"))
            for row in rows
            if row.get("accountId")
        }
        _USAGE_MAP_CACHE = result
        _USAGE_MAP_CACHE_AT = now_ts
        return result
    except Exception:
        return {}


async def _account_display_codes_map() -> Dict[str, str]:
    try:
        if db is not None:
            rows = await db.account_display_codes.find({}, {"_id": 0}).to_list(5000)
            return {
                str(row.get("accountId")): str(row.get("displayCode"))
                for row in rows
                if row.get("accountId") and row.get("displayCode")
            }

        rows = _mem_read("account_display_codes")
        return {
            str(row.get("accountId")): str(row.get("displayCode"))
            for row in rows
            if row.get("accountId") and row.get("displayCode")
        }
    except Exception:
        return {}


async def _set_account_display_code(account_id: str, display_code: str):
    doc = {
        "accountId": account_id,
        "displayCode": display_code,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if db is not None:
        await db.account_display_codes.update_one(
            {"accountId": account_id}, {"$set": doc}, upsert=True
        )
        return

    rows = _mem_read("account_display_codes")
    replaced = False
    for i, row in enumerate(rows):
        if row.get("accountId") == account_id:
            rows[i] = doc
            replaced = True
            break
    if not replaced:
        rows.append(doc)
    _mem_write("account_display_codes", rows)


async def _account_code_aliases_map() -> Dict[str, str]:
    """Map account_id -> legacy/original code before reindexing."""
    try:
        if db is not None:
            rows = await db.account_code_aliases.find({}, {"_id": 0}).to_list(5000)
            return {
                str(row.get("accountId")): str(row.get("legacyCode"))
                for row in rows
                if row.get("accountId") and row.get("legacyCode")
            }
        rows = _mem_read("account_code_aliases")
        return {
            str(row.get("accountId")): str(row.get("legacyCode"))
            for row in rows
            if row.get("accountId") and row.get("legacyCode")
        }
    except Exception:
        return {}


async def _set_account_code_alias(account_id: str, legacy_code: str):
    doc = {
        "accountId": account_id,
        "legacyCode": legacy_code,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    if db is not None:
        await db.account_code_aliases.update_one(
            {"accountId": account_id}, {"$set": doc}, upsert=True
        )
        return

    rows = _mem_read("account_code_aliases")
    replaced = False
    for i, row in enumerate(rows):
        if row.get("accountId") == account_id:
            rows[i] = doc
            replaced = True
            break
    if not replaced:
        rows.append(doc)
    _mem_write("account_code_aliases", rows)


async def _set_account_usage(account_id: str, last_used_at: str):
    doc = {"accountId": account_id, "lastUsedAt": last_used_at}
    if db is not None:
        await db.account_usage.update_one({"accountId": account_id}, {"$set": doc}, upsert=True)
        return

    rows = _mem_read("account_usage")
    replaced = False
    for i, row in enumerate(rows):
        if row.get("accountId") == account_id:
            rows[i] = doc
            replaced = True
            break
    if not replaced:
        rows.append(doc)
    _mem_write("account_usage", rows)


def _normalize_account_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(raw.get("id") or ""),
        "code": str(raw.get("code") or ""),
        "legacy_code": str(raw.get("legacy_code") or raw.get("legacyCode") or ""),
        "name": raw.get("name") or raw.get("name_ar") or raw.get("code") or "",
        "type": raw.get("type") or "asset",
        "parent_id": raw.get("parent_id") or raw.get("parentId") or None,
        "balance": float(raw.get("balance") or raw.get("current_balance") or 0),
        "active": bool(raw.get("active", True)),
        "is_system": bool(raw.get("is_system") or raw.get("isSystem") or False),
        "last_used_at": raw.get("last_used_at") or raw.get("lastUsedAt"),
    }


def _line_account_code(
    line: Dict[str, Any],
    id_to_code: Dict[str, str],
    legacy_to_current: Optional[Dict[str, str]] = None,
) -> str:
    raw = str(line.get("account") or line.get("account_code") or "").strip()
    if raw in id_to_code:
        return id_to_code[raw]
    if legacy_to_current and raw in legacy_to_current:
        return legacy_to_current[raw]
    return raw


def _apply_account_filters(
    account: Dict[str, Any],
    type_filter: str,
    hide_zero: bool,
    search_q: str,
) -> bool:
    if type_filter and type_filter != "all" and account.get("type") != type_filter:
        return False
    if hide_zero and abs(float(account.get("balance") or 0)) < 0.0001:
        return False
    if search_q:
        hay = f"{account.get('code','')} {account.get('name','')}".lower()
        if search_q not in hay:
            return False
    return True


_LIST_ACCOUNTS_CACHE = None
_LIST_ACCOUNTS_CACHE_AT = 0.0
_LIST_ACCOUNTS_CACHE_TTL = 10.0  # seconds

_USAGE_MAP_CACHE = None
_USAGE_MAP_CACHE_AT = 0.0
_USAGE_MAP_CACHE_TTL = 30.0  # seconds (usage timestamps can be slightly stale)
_ACCOUNT_WRITABLE_FIELDS = {"code", "name", "nameEn", "type", "parentId"}
_ACCOUNT_FORBIDDEN_FIELDS = {
    "id", "_id", "createdAt", "created_at", "updatedAt", "updated_at",
    "balance", "isSystem", "is_system", "ownerId", "owner_id", "workshop_id",
    "createdBy", "created_by", "audit", "permissions", "role", "status",
}


def invalidate_accounts_cache():
    """Called after any account mutation (create/update/delete) to bust caches."""
    global _LIST_ACCOUNTS_CACHE_AT, _USAGE_MAP_CACHE_AT
    _LIST_ACCOUNTS_CACHE_AT = 0.0
    _USAGE_MAP_CACHE_AT = 0.0


def _sanitize_account_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    forbidden = [k for k in (payload or {}).keys() if k in _ACCOUNT_FORBIDDEN_FIELDS]
    if forbidden:
        raise HTTPException(status_code=422, detail={"error": "forbidden_account_fields", "fields": forbidden})
    return {k: v for k, v in (payload or {}).items() if k in _ACCOUNT_WRITABLE_FIELDS}


@router.get("/accounts")
async def list_accounts():
    """Get all accounts in the chart of accounts (cached for short TTL)."""
    global _LIST_ACCOUNTS_CACHE, _LIST_ACCOUNTS_CACHE_AT
    now_ts = time.time()
    if _LIST_ACCOUNTS_CACHE is not None and (now_ts - _LIST_ACCOUNTS_CACHE_AT) < _LIST_ACCOUNTS_CACHE_TTL:
        return _LIST_ACCOUNTS_CACHE
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        overrides = await _account_status_overrides_map()
        code_aliases = await _account_code_aliases_map()

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()
            res = supa.client.table("accounts").select("*").order("code").execute()
            items = res.data or []
            for item in items:
                base_active = item.get("is_active")
                if base_active is None:
                    base_active = item.get("active")
                item["active"] = bool(
                    overrides.get(str(item.get("id")), True if base_active is None else base_active)
                )
                legacy_code = code_aliases.get(str(item.get("id")))
                if legacy_code:
                    item["legacy_code"] = legacy_code
            _LIST_ACCOUNTS_CACHE = items
            _LIST_ACCOUNTS_CACHE_AT = now_ts
            return items

        # MongoDB fallback
        docs = (
            await db.accounts.find({}, {"_id": 0}).sort("code", 1).to_list(length=1000)
        )
        for doc in docs:
            base_active = doc.get("active")
            doc["active"] = bool(
                overrides.get(str(doc.get("id")), True if base_active is None else base_active)
            )
            legacy_code = code_aliases.get(str(doc.get("id")))
            if legacy_code:
                doc["legacyCode"] = legacy_code
        return docs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts")
async def create_account(payload: Dict[str, Any] = Body(...)):
    """Create a new account"""
    try:
        payload = _sanitize_account_payload(payload)
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        account_id = str(uuid.uuid4())

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()
            row = {
                "id": account_id,
                "code": payload.get("code"),
                "name": payload.get("name"),
                "name_en": payload.get("nameEn", ""),
                "type": payload.get("type", "expense"),
                "parent_id": payload.get("parentId"),
                "is_system": False,
                "balance": 0.0,
            }
            res = supa.client.table("accounts").insert(row).execute()
            r = (res.data or [{}])[0]
            return {
                "id": r.get("id"),
                "code": r.get("code"),
                "name": r.get("name"),
                "nameEn": r.get("name_en"),
                "type": r.get("type"),
                "parentId": r.get("parent_id"),
                "isSystem": r.get("is_system"),
                "balance": r.get("balance"),
                "createdAt": r.get("created_at"),
            }

        # MongoDB fallback
        doc = {
            "id": account_id,
            "code": payload.get("code"),
            "name": payload.get("name"),
            "nameEn": payload.get("nameEn", ""),
            "type": payload.get("type", "expense"),
            "parentId": payload.get("parentId"),
            "isSystem": False,
            "balance": 0.0,
            "createdAt": datetime.now(timezone.utc),
        }
        await db.accounts.insert_one(doc)
        doc.pop("_id", None)
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/accounts/{account_id}")
async def update_account(account_id: str, payload: Dict[str, Any] = Body(...)):
    """Update an existing account"""
    try:
        payload = _sanitize_account_payload(payload)
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()
            upd = {}
            if "code" in payload:
                upd["code"] = payload["code"]
            if "name" in payload:
                upd["name"] = payload["name"]
            if "nameEn" in payload:
                upd["name_en"] = payload["nameEn"]
            if "type" in payload:
                upd["type"] = payload["type"]
            if "parentId" in payload:
                upd["parent_id"] = payload["parentId"]
            res = (
                supa.client.table("accounts").update(upd).eq("id", account_id).execute()
            )
            r = (res.data or [{}])[0]
            return {
                "id": r.get("id"),
                "code": r.get("code"),
                "name": r.get("name"),
                "nameEn": r.get("name_en"),
                "type": r.get("type"),
                "parentId": r.get("parent_id"),
                "isSystem": r.get("is_system"),
                "balance": r.get("balance"),
                "createdAt": r.get("created_at"),
            }

        # MongoDB fallback
        upd = dict(payload)
        await db.accounts.update_one({"id": account_id}, {"$set": upd})
        doc = await db.accounts.find_one({"id": account_id}, {"_id": 0})
        return doc or {}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/status-overrides")
async def get_account_status_overrides():
    """Returns account active overrides map for UI state merge."""
    return {"overrides": await _account_status_overrides_map()}


@router.patch("/accounts/{account_id}/active")
async def set_account_active(
    account_id: str, payload: Dict[str, Any] = Body(...), request: Request = None
):
    """Enable/disable account without relying on DB schema columns."""
    try:
        from auth_jwt import identity_from_request
        role = (identity_from_request(request).get("role") or "").lower() if request else ""
        if role not in ["admin", "manager"]:
            raise HTTPException(status_code=403, detail="هذه العملية متاحة للمدير فقط")

        is_active = bool(payload.get("isActive", True))
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        # Ensure account exists
        if provider == "supabase":
            supa = SupabaseService()
            acc_res = (
                supa.client.table("accounts")
                .select("id,is_system")
                .eq("id", account_id)
                .limit(1)
                .execute()
            )
            acc = (acc_res.data or [None])[0]
            if not acc:
                raise HTTPException(status_code=404, detail="الحساب غير موجود")
            if acc.get("is_system") and not is_active:
                raise HTTPException(status_code=400, detail="لا يمكن تعطيل حساب نظام")
        else:
            acc = await db.accounts.find_one({"id": account_id}, {"_id": 0})
            if not acc:
                raise HTTPException(status_code=404, detail="الحساب غير موجود")
            if acc.get("isSystem") and not is_active:
                raise HTTPException(status_code=400, detail="لا يمكن تعطيل حساب نظام")

        await _set_account_status_override(account_id, is_active)
        return {"success": True, "accountId": account_id, "isActive": is_active}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: str, request: Request = None):
    """Delete an account (only if not system and has no children)"""
    try:
        from auth_jwt import identity_from_request
        role = (identity_from_request(request).get("role") or "").lower() if request else ""
        if role not in ["admin", "manager"]:
            raise HTTPException(status_code=403, detail="هذه العملية متاحة للمدير فقط")

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()

            # Check if account exists and is system
            res = (
                supa.client.table("accounts").select("*").eq("id", account_id).execute()
            )
            acc = (res.data or [None])[0]
            if not acc:
                raise HTTPException(status_code=404, detail="الحساب غير موجود")
            if acc.get("is_system"):
                raise HTTPException(status_code=400, detail="لا يمكن حذف حساب نظام")

            # Check if has children
            children_res = (
                supa.client.table("accounts")
                .select("id")
                .eq("parent_id", account_id)
                .limit(1)
                .execute()
            )
            if children_res.data:
                raise HTTPException(
                    status_code=400, detail="لا يمكن حذف حساب يحتوي على حسابات فرعية"
                )

            # Delete account
            supa.client.table("accounts").delete().eq("id", account_id).execute()
            # cleanup status override
            await _remove_account_status_override(account_id)
            return {"success": True}

        # MongoDB fallback
        acc = await db.accounts.find_one({"id": account_id}, {"_id": 0})
        if not acc:
            raise HTTPException(status_code=404, detail="الحساب غير موجود")
        if acc.get("isSystem"):
            raise HTTPException(status_code=400, detail="لا يمكن حذف حساب نظام")

        children = await db.accounts.find_one({"parentId": account_id}, {"_id": 0})
        if children:
            raise HTTPException(
                status_code=400, detail="لا يمكن حذف حساب يحتوي على حسابات فرعية"
            )

        await db.accounts.delete_one({"id": account_id})
        await _remove_account_status_override(account_id)
        return {"success": True}
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/tree")
async def accounts_tree(
    workshop_id: str = Query("finmodule-sync"),
    type: str = Query("all"),
    hideZero: bool = Query(False),
    search: str = Query(""),
):
    """شجرة الحسابات مع إحصائيات النشاط والملخصات المالية."""
    try:
        raw_accounts = await list_accounts()
        normalized = [_normalize_account_row(acc) for acc in (raw_accounts or [])]
        usage_map = await _account_usage_map()

        for acc in normalized:
            usage_ts = usage_map.get(acc["id"])
            if usage_ts:
                acc["last_used_at"] = usage_ts
            acc["transaction_count"] = 0
            acc["total_debit"] = 0.0
            acc["total_credit"] = 0.0
            acc["activity_volume"] = 0.0
            acc["warning_negative"] = acc["balance"] < 0 and acc["type"] in {"asset", "expense"}

        id_to_code = {acc["id"]: acc["code"] for acc in normalized if acc.get("id") and acc.get("code")}
        code_to_acc = {acc["code"]: acc for acc in normalized if acc.get("code")}
        legacy_to_current = {
            str(acc.get("legacy_code") or "").strip(): str(acc.get("code") or "").strip()
            for acc in normalized
            if str(acc.get("legacy_code") or "").strip() and str(acc.get("code") or "").strip()
        }

        def _pick_code_by_name(keywords: List[str], acc_type: Optional[str] = None) -> str:
            for acc in normalized:
                code = str(acc.get("code") or "").strip()
                if not code:
                    continue
                if acc_type and str(acc.get("type") or "").strip().lower() != acc_type:
                    continue
                name = str(acc.get("name") or "").strip().lower()
                if any(k in name for k in keywords):
                    return code
            return ""

        ar_code = _pick_code_by_name(["عميل", "ذمم"], "asset")
        ap_code = _pick_code_by_name(["مورد", "دائن"], "liability")
        revenue_code = _pick_code_by_name(["إيراد", "ايراد"], "revenue")
        expense_code = _pick_code_by_name(["مصروف"], "expense")
        cost_code = _pick_code_by_name(["تكلفة"], "cost")

        def _map_legacy_code(code: str) -> str:
            raw = str(code or "").strip()
            if not raw:
                return raw
            mapped = legacy_to_current.get(raw)
            if mapped:
                return mapped
            if raw.startswith("1103") and ar_code:
                return ar_code
            if raw.startswith("2101") and ap_code:
                return ap_code
            if raw.startswith("400") or raw.startswith("410"):
                return revenue_code or raw
            if raw.startswith("500") or raw.startswith("510"):
                return cost_code or expense_code or raw
            if raw.startswith("600") or raw.startswith("610"):
                return expense_code or raw
            return raw

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        # Reuse the routes_finance TTL cache for journal entries to avoid
        # double-fetching (accounts/tree + internal income statement call).
        rows = []
        try:
            from routes_finance import _fetch_journal_entries as _finance_fetch_je
            rows = _finance_fetch_je(workshop_id, limit=5000, include_rakan=True)
        except Exception:
            if provider == "supabase":
                supa = SupabaseService()
                jres = (
                    supa.client.table("journal_entries")
                    .select("date,lines")
                    .eq("workshop_id", workshop_id)
                    .limit(5000)
                    .execute()
                )
                rows = jres.data or []
            else:
                rows = await db.journal_entries.find({"workshop_id": workshop_id}, {"_id": 0, "date": 1, "lines": 1}).to_list(length=5000)

        for entry in rows:
            for line in entry.get("lines", []) or []:
                code = _line_account_code(line, id_to_code)
                code = _map_legacy_code(code)
                acc = code_to_acc.get(code)
                if not acc:
                    continue
                debit = float(line.get("debit") or 0)
                credit = float(line.get("credit") or 0)
                acc["transaction_count"] += 1
                acc["total_debit"] += debit
                acc["total_credit"] += credit
                acc["activity_volume"] = acc["total_debit"] + acc["total_credit"]

        # اعتماد الرصيد من القيود الفعلية لضمان التطابق (بدل الاعتماد على قيمة مخزنة قديمة)
        for acc in normalized:
            debit = float(acc.get("total_debit") or 0)
            credit = float(acc.get("total_credit") or 0)
            acc_type = str(acc.get("type") or "").strip().lower()
            if acc_type in {"asset", "expense"}:
                computed_balance = debit - credit
            else:
                computed_balance = credit - debit
            acc["balance"] = round(computed_balance, 2)
            acc["warning_negative"] = acc["balance"] < 0 and acc_type in {"asset", "expense"}

        type_filter = str(type or "all").strip().lower()
        search_q = str(search or "").strip().lower()
        visible_accounts = [
            acc for acc in normalized if _apply_account_filters(acc, type_filter, hideZero, search_q)
        ]

        summary = {
            "assets": round(sum(a["balance"] for a in visible_accounts if a["type"] == "asset"), 2),
            "liabilities": round(sum(a["balance"] for a in visible_accounts if a["type"] == "liability"), 2),
            "equity": round(sum(a["balance"] for a in visible_accounts if a["type"] == "equity"), 2),
            "revenue": round(sum(a["balance"] for a in visible_accounts if a["type"] == "revenue"), 2),
            "expense": round(sum(a["balance"] for a in visible_accounts if a["type"] == "expense"), 2),
            "purchase": round(sum(a["balance"] for a in visible_accounts if a["type"] in {"cost", "purchase"}), 2),
        }
        summary["net_profit"] = round(summary["revenue"] - (summary["expense"] + summary["purchase"]), 2)

        # توحيد مرجع الربحية مع تقرير الدخل لتجنب اختلاف الصفحات المالية
        try:
            from routes_finance import get_income_statement

            income_payload = await get_income_statement(
                workshop_id=workshop_id,
                start_date="2000-01-01",
                end_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            )
            income_totals = (income_payload.get("data") or {}).get("totals") or {}
            summary["revenue"] = round(float(income_totals.get("revenue") or 0), 2)
            summary["expense"] = round(float(income_totals.get("expenses") or 0), 2)
            summary["purchase"] = 0.0
            summary["net_profit"] = round(float(income_totals.get("net_income") or 0), 2)
            summary["financial_source"] = "income_statement"
        except Exception:
            pass

        visible_ids = {a["id"] for a in visible_accounts}
        by_parent: Dict[str, list] = {}
        for acc in visible_accounts:
            parent = str(acc.get("parent_id") or "")
            by_parent.setdefault(parent, []).append(acc)

        def _sort_key(acc: Dict[str, Any]):
            code = str(acc.get("code") or "").strip()
            if code.isdigit():
                return (0, int(code), code)
            return (1, code)

        def build_node(acc: Dict[str, Any], level: int = 0) -> Dict[str, Any]:
            children = by_parent.get(acc["id"], [])
            children = sorted(children, key=_sort_key)
            return {
                **acc,
                "level": level,
                "children": [build_node(child, level + 1) for child in children],
            }

        # Flatten on active search (as requested)
        if search_q:
            flat_nodes = sorted(visible_accounts, key=_sort_key)
            return {
                "success": True,
                "data": {
                    "mode": "flat",
                    "summary": summary,
                    "accounts": flat_nodes,
                },
            }

        roots = [
            acc
            for acc in visible_accounts
            if not acc.get("parent_id") or str(acc.get("parent_id")) not in visible_ids
        ]
        roots = sorted(roots, key=_sort_key)

        return {
            "success": True,
            "data": {
                "mode": "tree",
                "summary": summary,
                "accounts": [build_node(root, 0) for root in roots],
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/reindex-display-codes")
async def reindex_account_display_codes():
    """إعادة ترقيم كود الحساب نفسه بشكل متسلسل يبدأ من 001 مع حفظ الكود الأصلي كـ legacy alias."""
    try:
        raw_accounts = await list_accounts()
        normalized = [_normalize_account_row(acc) for acc in (raw_accounts or [])]
        candidates = [acc for acc in normalized if acc.get("id")]
        alias_map = await _account_code_aliases_map()

        def sort_key(acc: Dict[str, Any]):
            code = str(acc.get("code") or "").strip()
            if code.isdigit():
                return (0, int(code), code)
            return (1, code)

        candidates.sort(key=sort_key)

        changed = []
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        for idx, acc in enumerate(candidates, start=1):
            account_id = str(acc.get("id"))
            old_code = str(acc.get("code") or "").strip()
            new_code = f"{idx:03d}"
            legacy_code = str(alias_map.get(account_id) or old_code)

            await _set_account_code_alias(account_id, legacy_code)

            if old_code != new_code:
                if provider == "supabase":
                    supa = SupabaseService()
                    supa.client.table("accounts").update({"code": new_code}).eq("id", account_id).execute()
                elif db is not None:
                    await db.accounts.update_one({"id": account_id}, {"$set": {"code": new_code}})

            changed.append(
                {
                    "account_id": account_id,
                    "old_code": old_code,
                    "new_code": new_code,
                    "legacy_code": legacy_code,
                    "name": acc.get("name"),
                }
            )

        return {
            "success": True,
            "data": {
                "count": len(changed),
                "first_code": changed[0]["new_code"] if changed else None,
                "last_code": changed[-1]["new_code"] if changed else None,
                "sample": changed[:50],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/transactions")
async def account_transactions(
    account_id: str,
    workshop_id: str = Query("finmodule-sync"),
    limit: int = Query(10, ge=1, le=200),
):
    """آخر عمليات الحساب."""
    try:
        raw_accounts = await list_accounts()
        normalized = [_normalize_account_row(acc) for acc in (raw_accounts or [])]
        target = next((a for a in normalized if a["id"] == account_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="الحساب غير موجود")

        id_to_code = {acc["id"]: acc["code"] for acc in normalized if acc.get("id") and acc.get("code")}
        target_code = target["code"]
        legacy_to_current = {
            str(acc.get("legacy_code") or "").strip(): str(acc.get("code") or "").strip()
            for acc in normalized
            if str(acc.get("legacy_code") or "").strip() and str(acc.get("code") or "").strip()
        }

        def _pick_code_by_name(keywords: List[str], acc_type: Optional[str] = None) -> str:
            for acc in normalized:
                code = str(acc.get("code") or "").strip()
                if not code:
                    continue
                if acc_type and str(acc.get("type") or "").strip().lower() != acc_type:
                    continue
                name = str(acc.get("name") or "").strip().lower()
                if any(k in name for k in keywords):
                    return code
            return ""

        ar_code = _pick_code_by_name(["عميل", "ذمم"], "asset")
        ap_code = _pick_code_by_name(["مورد", "دائن"], "liability")
        revenue_code = _pick_code_by_name(["إيراد", "ايراد"], "revenue")
        expense_code = _pick_code_by_name(["مصروف"], "expense")
        cost_code = _pick_code_by_name(["تكلفة"], "cost")

        def _map_legacy_code(code: str) -> str:
            raw = str(code or "").strip()
            if not raw:
                return raw
            mapped = legacy_to_current.get(raw)
            if mapped:
                return mapped
            if raw.startswith("1103") and ar_code:
                return ar_code
            if raw.startswith("2101") and ap_code:
                return ap_code
            if raw.startswith("400") or raw.startswith("410"):
                return revenue_code or raw
            if raw.startswith("500") or raw.startswith("510"):
                return cost_code or expense_code or raw
            if raw.startswith("600") or raw.startswith("610"):
                return expense_code or raw
            return raw

        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            supa = SupabaseService()
            rows = (
                supa.client.table("journal_entries")
                .select("id,date,description,lines")
                .eq("workshop_id", workshop_id)
                .order("date", desc=True)
                .limit(20000)
                .execute()
                .data
                or []
            )
        else:
            rows = await db.journal_entries.find({"workshop_id": workshop_id}, {"_id": 0, "id": 1, "date": 1, "description": 1, "lines": 1}).sort("date", -1).to_list(length=20000)

        tx = []
        for row in rows:
            debit = 0.0
            credit = 0.0
            for line in row.get("lines", []) or []:
                code = _line_account_code(line, id_to_code)
                code = _map_legacy_code(code)
                if code == target_code:
                    debit += float(line.get("debit") or 0)
                    credit += float(line.get("credit") or 0)
            if debit == 0 and credit == 0:
                continue
            tx.append(
                {
                    "id": row.get("id"),
                    "date": row.get("date"),
                    "description": row.get("description") or "",
                    "debit": round(debit, 2),
                    "credit": round(credit, 2),
                }
            )

        tx = tx[: max(limit, 1)]
        running = float(target.get("balance") or 0)
        for item in tx:
            item["balance"] = round(running, 2)
            running -= item["debit"] - item["credit"]

        return {"success": True, "data": {"account": target, "transactions": tx}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/sparkline")
async def account_sparkline(
    account_id: str,
    workshop_id: str = Query("finmodule-sync"),
    days: int = Query(30, ge=7, le=120),
):
    """حركة الرصيد اليومية للحساب."""
    try:
        tx_res = await account_transactions(account_id=account_id, workshop_id=workshop_id, limit=2000)
        payload = tx_res.get("data", {})
        transactions = payload.get("transactions", [])
        start_date = datetime.now(timezone.utc) - timedelta(days=days - 1)

        daily_map: Dict[str, float] = {}
        for item in transactions:
            raw_date = str(item.get("date") or "")
            try:
                dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00")) if raw_date else datetime.now(timezone.utc)
            except Exception:
                dt = datetime.now(timezone.utc)
            key = dt.strftime("%Y-%m-%d")
            daily_map[key] = daily_map.get(key, 0.0) + float(item.get("debit") or 0) - float(item.get("credit") or 0)

        points = []
        balance = 0.0
        for i in range(days):
            day = start_date + timedelta(days=i)
            key = day.strftime("%Y-%m-%d")
            balance += daily_map.get(key, 0.0)
            points.append({"date": key, "balance": round(balance, 2)})

        return {"success": True, "data": {"days": days, "points": points}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/accounts/{account_id}/touch")
async def touch_account(account_id: str):
    """تحديث وقت آخر استخدام للحساب."""
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        await _set_account_usage(account_id, now_iso)
        try:
            provider = os.environ.get("DB_PROVIDER", "mongo").lower()
            if provider == "supabase":
                supa = SupabaseService()
                # best effort: may fail if column not available
                supa.client.table("accounts").update({"last_used_at": now_iso}).eq("id", account_id).execute()
            else:
                await db.accounts.update_one({"id": account_id}, {"$set": {"last_used_at": now_iso}})
        except Exception:
            pass
        return {"success": True, "account_id": account_id, "last_used_at": now_iso}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/export")
async def export_accounts(
    workshop_id: str = Query("finmodule-sync"),
    type: str = Query("all"),
    hideZero: bool = Query(False),
    search: str = Query(""),
):
    """تصدير الحسابات المرئية بعد التصفية (JSON للواجهة لاستخدام Excel)."""
    payload = await accounts_tree(
        workshop_id=workshop_id,
        type=type,
        hideZero=hideZero,
        search=search,
    )
    data = payload.get("data", {})
    mode = data.get("mode")
    rows = []

    if mode == "flat":
        rows = data.get("accounts", [])
    else:
        def flatten(nodes):
            for node in nodes:
                rows.append({k: v for k, v in node.items() if k != "children"})
                flatten(node.get("children", []))

        flatten(data.get("accounts", []))

    export_rows = [
        {
            "code": r.get("code"),
            "name": r.get("name"),
            "type": r.get("type"),
            "balance": r.get("balance"),
            "total_debit": r.get("total_debit"),
            "total_credit": r.get("total_credit"),
            "transaction_count": r.get("transaction_count"),
        }
        for r in rows
    ]

    return {"success": True, "data": {"summary": data.get("summary", {}), "rows": export_rows}}


@router.get("/accounts/reconciliation-report")
async def accounts_reconciliation_report(
    workshop_id: str = Query("finmodule-sync"),
):
    """تقرير تدقيق ربط المبالغ: مقارنة الرصيد مع (مدين-دائن) أو (دائن-مدين) حسب نوع الحساب."""
    try:
        payload = await accounts_tree(
            workshop_id=workshop_id,
            type="all",
            hideZero=False,
            search="",
        )
        data = payload.get("data", {})
        mode = data.get("mode")

        rows: List[Dict[str, Any]] = []
        if mode == "flat":
            rows = list(data.get("accounts", []) or [])
        else:
            def flatten(nodes: List[Dict[str, Any]]):
                for node in nodes or []:
                    rows.append({k: v for k, v in node.items() if k != "children"})
                    flatten(node.get("children", []) or [])

            flatten(data.get("accounts", []) or [])

        report_rows = []
        matched = 0
        mismatched = 0
        max_abs_diff = 0.0

        for row in rows:
            debit = float(row.get("total_debit") or 0)
            credit = float(row.get("total_credit") or 0)
            balance = float(row.get("balance") or 0)
            acc_type = str(row.get("type") or "").strip().lower()

            if acc_type in {"asset", "expense"}:
                expected_balance = debit - credit
            else:
                expected_balance = credit - debit

            difference = round(balance - expected_balance, 2)
            is_matched = abs(difference) <= 0.01
            if is_matched:
                matched += 1
            else:
                mismatched += 1
            max_abs_diff = max(max_abs_diff, abs(difference))

            report_rows.append(
                {
                    "account_id": row.get("id"),
                    "code": row.get("code"),
                    "name": row.get("name"),
                    "type": acc_type,
                    "balance": round(balance, 2),
                    "total_debit": round(debit, 2),
                    "total_credit": round(credit, 2),
                    "expected_balance": round(expected_balance, 2),
                    "difference": difference,
                    "matched": is_matched,
                }
            )

        report_rows.sort(key=lambda r: abs(float(r.get("difference") or 0)), reverse=True)

        return {
            "success": True,
            "data": {
                "summary": {
                    "accounts_count": len(report_rows),
                    "matched_count": matched,
                    "mismatched_count": mismatched,
                    "max_abs_difference": round(max_abs_diff, 2),
                },
                "rows": report_rows,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/init-defaults")
async def init_default_accounts():
    """Initialize default chart of accounts if empty"""
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()

        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()

            # Check if accounts exist
            res = supa.client.table("accounts").select("id").limit(1).execute()
            if res.data:
                return {"message": "الحسابات موجودة بالفعل", "count": len(res.data)}

            # Insert default accounts
            default_accounts = [
                # 1000 - Assets
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
                    "id": "acc-1104",
                    "code": "1104",
                    "name": "نقاط بيع",
                    "name_en": "POS",
                    "type": "asset",
                    "parent_id": "acc-1102",
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
                # 2000 - Liabilities
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
                # 3000 - Equity
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
                # 4000 - Revenue
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
                # 5000 - Cost of Services
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
                # 6000 - Operating Expenses
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

            supa.client.table("accounts").insert(default_accounts).execute()
            return {
                "message": "تم إنشاء شجرة الحسابات الافتراضية",
                "count": len(default_accounts),
            }

        # MongoDB fallback
        count = await db.accounts.count_documents({})
        if count > 0:
            return {"message": "الحسابات موجودة بالفعل", "count": count}

        default_accounts = [
            # 1000 - Assets
            {
                "id": "acc-1000",
                "code": "1000",
                "name": "الأصول",
                "nameEn": "Assets",
                "type": "asset",
                "parentId": None,
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1100",
                "code": "1100",
                "name": "الأصول المتداولة",
                "nameEn": "Current Assets",
                "type": "asset",
                "parentId": "acc-1000",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1101",
                "code": "1101",
                "name": "النقد",
                "nameEn": "Cash",
                "type": "asset",
                "parentId": "acc-1100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1102",
                "code": "1102",
                "name": "البنك",
                "nameEn": "Bank",
                "type": "asset",
                "parentId": "acc-1100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1104",
                "code": "1104",
                "name": "نقاط بيع",
                "nameEn": "POS",
                "type": "asset",
                "parentId": "acc-1102",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1103",
                "code": "1103",
                "name": "العملاء",
                "nameEn": "Accounts Receivable",
                "type": "asset",
                "parentId": "acc-1100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1105",
                "code": "1105",
                "name": "مخزون قطع غيار",
                "nameEn": "Spare Parts Inventory",
                "type": "asset",
                "parentId": "acc-1100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1106",
                "code": "1106",
                "name": "مخزون مستهلكات",
                "nameEn": "Consumables Inventory",
                "type": "asset",
                "parentId": "acc-1100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1200",
                "code": "1200",
                "name": "الأصول الثابتة",
                "nameEn": "Fixed Assets",
                "type": "asset",
                "parentId": "acc-1000",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1201",
                "code": "1201",
                "name": "معدات ميكانيكية",
                "nameEn": "Mechanical Equipment",
                "type": "asset",
                "parentId": "acc-1200",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1202",
                "code": "1202",
                "name": "رافعات سيارات",
                "nameEn": "Car Lifts",
                "type": "asset",
                "parentId": "acc-1200",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1203",
                "code": "1203",
                "name": "أجهزة فحص",
                "nameEn": "Diagnostic Tools",
                "type": "asset",
                "parentId": "acc-1200",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-1207",
                "code": "1207",
                "name": "مجمع الإهلاك",
                "nameEn": "Accumulated Depreciation",
                "type": "asset",
                "parentId": "acc-1200",
                "isSystem": True,
                "balance": 0.0,
            },
            # 2000 - Liabilities
            {
                "id": "acc-2000",
                "code": "2000",
                "name": "الخصوم",
                "nameEn": "Liabilities",
                "type": "liability",
                "parentId": None,
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-2100",
                "code": "2100",
                "name": "الخصوم المتداولة",
                "nameEn": "Current Liabilities",
                "type": "liability",
                "parentId": "acc-2000",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-2101",
                "code": "2101",
                "name": "الموردون",
                "nameEn": "Accounts Payable",
                "type": "liability",
                "parentId": "acc-2100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-2102",
                "code": "2102",
                "name": "مصروفات مستحقة",
                "nameEn": "Accrued Expenses",
                "type": "liability",
                "parentId": "acc-2100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-2103",
                "code": "2103",
                "name": "رواتب مستحقة",
                "nameEn": "Accrued Salaries",
                "type": "liability",
                "parentId": "acc-2100",
                "isSystem": True,
                "balance": 0.0,
            },
            # 3000 - Equity
            {
                "id": "acc-3000",
                "code": "3000",
                "name": "حقوق الملكية",
                "nameEn": "Equity",
                "type": "equity",
                "parentId": None,
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-3100",
                "code": "3100",
                "name": "حقوق المالك",
                "nameEn": "Owner's Equity",
                "type": "equity",
                "parentId": "acc-3000",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-3101",
                "code": "3101",
                "name": "رأس المال",
                "nameEn": "Owner Capital",
                "type": "equity",
                "parentId": "acc-3100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-3102",
                "code": "3102",
                "name": "مسحوبات المالك",
                "nameEn": "Owner Drawings",
                "type": "equity",
                "parentId": "acc-3100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-3103",
                "code": "3103",
                "name": "أرباح محتجزة",
                "nameEn": "Retained Earnings",
                "type": "equity",
                "parentId": "acc-3100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-3104",
                "code": "3104",
                "name": "صافي الربح/الخسارة",
                "nameEn": "Net Profit/Loss",
                "type": "equity",
                "parentId": "acc-3100",
                "isSystem": True,
                "balance": 0.0,
            },
            # 4000 - Revenue
            {
                "id": "acc-4000",
                "code": "4000",
                "name": "الإيرادات",
                "nameEn": "Revenue",
                "type": "revenue",
                "parentId": None,
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-4100",
                "code": "4100",
                "name": "إيرادات الخدمات",
                "nameEn": "Service Revenue",
                "type": "revenue",
                "parentId": "acc-4000",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-4101",
                "code": "4101",
                "name": "إيرادات خدمات ميكانيكية",
                "nameEn": "Mechanical Service Revenue",
                "type": "revenue",
                "parentId": "acc-4100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-4102",
                "code": "4102",
                "name": "إيرادات إصلاح محركات",
                "nameEn": "Engine Repair Revenue",
                "type": "revenue",
                "parentId": "acc-4100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-4103",
                "code": "4103",
                "name": "إيرادات فرامل وتعليق",
                "nameEn": "Brake & Suspension Revenue",
                "type": "revenue",
                "parentId": "acc-4100",
                "isSystem": True,
                "balance": 0.0,
            },
            # 5000 - Cost of Services
            {
                "id": "acc-5000",
                "code": "5000",
                "name": "تكلفة الخدمات",
                "nameEn": "Cost of Services",
                "type": "expense",
                "parentId": None,
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-5100",
                "code": "5100",
                "name": "تكاليف مباشرة",
                "nameEn": "Direct Costs",
                "type": "expense",
                "parentId": "acc-5000",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-5101",
                "code": "5101",
                "name": "أجور فنيين مباشرة",
                "nameEn": "Technicians Wages - Direct",
                "type": "expense",
                "parentId": "acc-5100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-5102",
                "code": "5102",
                "name": "قطع غيار مستخدمة",
                "nameEn": "Spare Parts Used",
                "type": "expense",
                "parentId": "acc-5100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-5103",
                "code": "5103",
                "name": "مستهلكات مستخدمة",
                "nameEn": "Consumables Used",
                "type": "expense",
                "parentId": "acc-5100",
                "isSystem": True,
                "balance": 0.0,
            },
            # 6000 - Operating Expenses
            {
                "id": "acc-6000",
                "code": "6000",
                "name": "المصروفات التشغيلية",
                "nameEn": "Operating Expenses",
                "type": "expense",
                "parentId": None,
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-6100",
                "code": "6100",
                "name": "مصروفات عامة وإدارية",
                "nameEn": "General & Administrative",
                "type": "expense",
                "parentId": "acc-6000",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-6101",
                "code": "6101",
                "name": "رواتب إدارية",
                "nameEn": "Administrative Salaries",
                "type": "expense",
                "parentId": "acc-6100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-6102",
                "code": "6102",
                "name": "إيجار المركز",
                "nameEn": "Workshop Rent",
                "type": "expense",
                "parentId": "acc-6100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-6103",
                "code": "6103",
                "name": "كهرباء ومياه",
                "nameEn": "Electricity & Water",
                "type": "expense",
                "parentId": "acc-6100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-6104",
                "code": "6104",
                "name": "صيانة معدات",
                "nameEn": "Equipment Maintenance",
                "type": "expense",
                "parentId": "acc-6100",
                "isSystem": True,
                "balance": 0.0,
            },
            {
                "id": "acc-6105",
                "code": "6105",
                "name": "ملابس وسلامة مهنية",
                "nameEn": "Uniforms & Safety",
                "type": "expense",
                "parentId": "acc-6100",
                "isSystem": True,
                "balance": 0.0,
            },
        ]

        for acc in default_accounts:
            acc["createdAt"] = datetime.now(timezone.utc)

        await db.accounts.insert_many(default_accounts)
        return {
            "message": "تم إنشاء شجرة الحسابات الافتراضية",
            "count": len(default_accounts),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


