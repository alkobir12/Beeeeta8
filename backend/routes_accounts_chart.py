"""
مسارات دليل الحسابات
Chart of Accounts Routes
"""

from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime
import uuid
import os

from models_financial import Account, AccountBase
from supabase_service import SupabaseService

router = APIRouter(prefix="/api/accounts-chart")

DB_PROVIDER = os.environ.get("DB_PROVIDER", "mongo").lower()
SUPABASE_ACCOUNTS_TABLE = "chart_of_accounts"
CHART_TABLE_AVAILABLE = True
supabase_service = SupabaseService()

# قاعدة بيانات مؤقتة (ستُستبدل بـ MongoDB/Supabase)
accounts_db = []

# بيانات افتراضية
DEFAULT_ACCOUNTS = [
    {"code": "1001", "name": "الصندوق", "type": "asset", "balance": 50000},
    {"code": "1002", "name": "البنك", "type": "asset", "balance": 100000},
    {"code": "1103", "name": "حساب العملاء (ذمم)", "type": "asset", "balance": 25000},
    {"code": "3001", "name": "مخزون قطع الغيار", "type": "asset", "balance": 75000},
    {"code": "4001", "name": "إيرادات خدمات الصيانة", "type": "revenue", "balance": 0},
    {"code": "4002", "name": "إيرادات بيع قطع الغيار", "type": "revenue", "balance": 0},
    {
        "code": "5001",
        "name": "تكلفة قطع الغيار المباعة",
        "type": "expense",
        "balance": 0,
    },
    {"code": "5002", "name": "رواتب الموظفين", "type": "expense", "balance": 0},
    {"code": "5003", "name": "مصاريف التشغيل", "type": "expense", "balance": 0},
    {"code": "5004", "name": "إيجار الورشة", "type": "expense", "balance": 0},
    {"code": "5005", "name": "كهرباء وماء", "type": "expense", "balance": 0},
    {"code": "6001", "name": "حسابات الموردين", "type": "liability", "balance": 15000},
]

NOISE_ACCOUNT_TOKENS = ["test", "raw", "experimental", "تجريبي", "اختبار", "خام"]


def _is_chart_table_missing(err: Exception) -> bool:
    message = str(err)
    return "PGRST205" in message and "chart_of_accounts" in message


def _map_supabase_account(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "code": row.get("code"),
        "name": row.get("name"),
        "type": row.get("type"),
        "balance": row.get("balance", 0),
        "parentAccount": row.get("parent_account") or row.get("parentAccount"),
        "createdAt": row.get("created_at") or row.get("createdAt"),
        "active": row.get("active", True),
    }


def _is_noise_account(name: str, code: str) -> bool:
    text = f"{name} {code}".lower()
    return any(token in text for token in NOISE_ACCOUNT_TOKENS)


def _fetch_supabase_accounts():
    global CHART_TABLE_AVAILABLE
    if DB_PROVIDER != "supabase":
        return None
    if not supabase_service.client or supabase_service.mock_mode:
        return None
    if not CHART_TABLE_AVAILABLE:
        return None
    try:
        res = supabase_service.client.table(SUPABASE_ACCOUNTS_TABLE).select("*").execute()
        rows = res.data or []
        return [_map_supabase_account(r) for r in rows]
    except Exception as e:
        if _is_chart_table_missing(e):
            CHART_TABLE_AVAILABLE = False
        else:
            print(f"Supabase accounts-chart fetch error: {e}")
        return None


def _initialize_accounts():
    """تهيئة الحسابات الافتراضية"""
    if not accounts_db:
        supabase_rows = _fetch_supabase_accounts()
        if supabase_rows is not None and len(supabase_rows) > 0:
            accounts_db.extend(supabase_rows)
            return
        for acc_data in DEFAULT_ACCOUNTS:
            account = Account(
                id=str(uuid.uuid4()),
                code=acc_data["code"],
                name=acc_data["name"],
                type=acc_data["type"],
                balance=acc_data["balance"],
                parentAccount=None,
                createdAt=datetime.now(),
                active=True,
            )
            accounts_db.append(account.dict())


@router.get("")
async def get_accounts():
    """الحصول على جميع الحسابات"""
    supabase_rows = _fetch_supabase_accounts()
    if supabase_rows is not None and len(supabase_rows) > 0:
        return {"accounts": supabase_rows}
    _initialize_accounts()
    return {"accounts": accounts_db}


@router.post("/init-defaults")
async def init_default_accounts():
    """تهيئة الحسابات الافتراضية"""
    _initialize_accounts()
    return {"accounts": accounts_db}


@router.delete("/reset")
async def reset_accounts_chart(request: Request, confirm: str = Query(None)):
    """إعادة تهيئة دليل الحسابات الافتراضي — مسار هدّام مالي، fail-closed."""
    from core.destructive_guard import require_destructive_authorization

    await require_destructive_authorization(request, action="reset_accounts_chart", confirm=confirm)
    global CHART_TABLE_AVAILABLE
    try:
        if DB_PROVIDER == "supabase" and supabase_service.client and not supabase_service.mock_mode and CHART_TABLE_AVAILABLE:
            try:
                # delete all rows then seed defaults
                supabase_service.client.table(SUPABASE_ACCOUNTS_TABLE).delete().neq("id", "").execute()

                defaults_payload = []
                now_iso = datetime.now().isoformat()
                for acc in DEFAULT_ACCOUNTS:
                    defaults_payload.append(
                        {
                            "id": str(uuid.uuid4()),
                            "code": acc["code"],
                            "name": acc["name"],
                            "type": acc["type"],
                            "balance": acc.get("balance", 0),
                            "parent_account": None,
                            "created_at": now_iso,
                            "active": True,
                        }
                    )
                supabase_service.client.table(SUPABASE_ACCOUNTS_TABLE).insert(defaults_payload).execute()

                # remove noisy accounts if any were re-added externally
                rows = (
                    supabase_service.client.table(SUPABASE_ACCOUNTS_TABLE).select("id,name,code").execute().data
                    or []
                )
                for row in rows:
                    if _is_noise_account(str(row.get("name") or ""), str(row.get("code") or "")):
                        supabase_service.client.table(SUPABASE_ACCOUNTS_TABLE).delete().eq("id", row.get("id")).execute()

                refreshed = _fetch_supabase_accounts() or []
                accounts_db.clear()
                accounts_db.extend(refreshed)
                return {"success": True, "message": "تمت إعادة ضبط دليل الحسابات", "accounts": refreshed}
            except Exception as supa_error:
                if _is_chart_table_missing(supa_error):
                    CHART_TABLE_AVAILABLE = False
                else:
                    raise

        accounts_db.clear()
        for acc_data in DEFAULT_ACCOUNTS:
            account = Account(
                id=str(uuid.uuid4()),
                code=acc_data["code"],
                name=acc_data["name"],
                type=acc_data["type"],
                balance=acc_data["balance"],
                parentAccount=None,
                createdAt=datetime.now(),
                active=True,
            )
            accounts_db.append(account.dict())

        accounts_db[:] = [
            a
            for a in accounts_db
            if not _is_noise_account(str(a.get("name") or ""), str(a.get("code") or ""))
        ]
        return {"success": True, "message": "تمت إعادة ضبط دليل الحسابات", "accounts": accounts_db}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في إعادة ضبط الحسابات: {str(e)}")


@router.get("/{account_id}")
async def get_account(account_id: str):
    """الحصول على حساب معين"""
    _initialize_accounts()
    account = next((a for a in accounts_db if a["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")
    return account


@router.post("")
async def create_account(account: AccountBase):
    """إنشاء حساب جديد"""
    global CHART_TABLE_AVAILABLE
    _initialize_accounts()

    # التحقق من عدم تكرار الرمز
    if any(a["code"] == account.code for a in accounts_db):
        raise HTTPException(status_code=400, detail="رمز الحساب موجود مسبقاً")

    new_account = Account(
        id=str(uuid.uuid4()),
        code=account.code,
        name=account.name,
        type=account.type,
        parentAccount=account.parentAccount,
        balance=0,
        createdAt=datetime.now(),
        active=True,
    )

    if DB_PROVIDER == "supabase" and supabase_service.client and not supabase_service.mock_mode and CHART_TABLE_AVAILABLE:
        try:
            supabase_payload = {
                "id": new_account.id,
                "code": new_account.code,
                "name": new_account.name,
                "type": new_account.type,
                "parent_account": new_account.parentAccount,
                "balance": 0,
                "created_at": new_account.createdAt.isoformat(),
                "active": True,
            }
            res = supabase_service.client.table(SUPABASE_ACCOUNTS_TABLE).insert(supabase_payload).execute()
            row = (res.data or [supabase_payload])[0]
            mapped = _map_supabase_account(row)
            accounts_db.append(mapped)
            return {"success": True, "account": mapped}
        except Exception as e:
            if _is_chart_table_missing(e):
                CHART_TABLE_AVAILABLE = False
            else:
                print(f"Supabase accounts-chart insert error: {e}")

    accounts_db.append(new_account.dict())
    return {"success": True, "account": new_account}


@router.put("/{account_id}")
async def update_account(account_id: str, updates: dict):
    """تحديث حساب"""
    global CHART_TABLE_AVAILABLE
    _initialize_accounts()

    account = next((a for a in accounts_db if a["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")

    # تحديث الحقول المسموحة
    allowed_fields = ["name", "type", "parentAccount", "active"]
    for field in allowed_fields:
        if field in updates:
            account[field] = updates[field]

    if DB_PROVIDER == "supabase" and supabase_service.client and not supabase_service.mock_mode and CHART_TABLE_AVAILABLE:
        try:
            supabase_payload = {
                "name": account.get("name"),
                "type": account.get("type"),
                "parent_account": account.get("parentAccount"),
                "active": account.get("active", True),
            }
            supabase_service.client.table(SUPABASE_ACCOUNTS_TABLE).update(supabase_payload).eq("id", account_id).execute()
        except Exception as e:
            if _is_chart_table_missing(e):
                CHART_TABLE_AVAILABLE = False
            else:
                print(f"Supabase accounts-chart update error: {e}")

    return {"success": True, "account": account}


@router.delete("/{account_id}")
async def delete_account(account_id: str):
    """حذف حساب"""
    global CHART_TABLE_AVAILABLE
    _initialize_accounts()
    idx = next((i for i, a in enumerate(accounts_db) if a["id"] == account_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")
    if DB_PROVIDER == "supabase" and supabase_service.client and not supabase_service.mock_mode and CHART_TABLE_AVAILABLE:
        try:
            supabase_service.client.table(SUPABASE_ACCOUNTS_TABLE).delete().eq("id", account_id).execute()
        except Exception as e:
            if _is_chart_table_missing(e):
                CHART_TABLE_AVAILABLE = False
            else:
                print(f"Supabase accounts-chart delete error: {e}")

    accounts_db.pop(idx)
    return {"success": True}


@router.post("/{account_id}/adjust")
async def adjust_balance(account_id: str, amount: float, description: str):
    """
    تعديل رصيد حساب (للتسويات)
    """
    _initialize_accounts()

    account = next((a for a in accounts_db if a["id"] == account_id), None)
    if not account:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")

    account["balance"] += amount

    return {
        "success": True,
        "account": account,
        "adjustment": {
            "amount": amount,
            "description": description,
            "new_balance": account["balance"],
        },
    }


@router.get("/balance-sheet/summary")
async def get_balance_sheet():
    """
    الحصول على ملخص الميزانية
    """
    _initialize_accounts()

    assets = sum(a["balance"] for a in accounts_db if a["type"] == "asset")
    liabilities = sum(a["balance"] for a in accounts_db if a["type"] == "liability")
    equity = assets - liabilities
    revenue = sum(a["balance"] for a in accounts_db if a["type"] == "revenue")
    expenses = sum(a["balance"] for a in accounts_db if a["type"] == "expense")

    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "revenue": revenue,
        "expenses": expenses,
        "net_income": revenue - expenses,
        "balanced": abs((assets - liabilities - equity)) < 0.01,
    }
