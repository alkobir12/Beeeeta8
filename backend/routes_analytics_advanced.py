"""
مسارات التحليلات المالية المتقدمة
Advanced Financial Analytics Routes
"""

from fastapi import APIRouter
from typing import Optional
from datetime import datetime
import os

from analytics_service import financial_analytics

router = APIRouter(prefix="/api/analytics-advanced")

# سنربط مع قاعدة البيانات لاحقاً
DB_PROVIDER = os.environ.get("DB_PROVIDER", "mongo").lower()
_db = None


def set_db(database):
    global _db
    _db = database


@router.get("/dashboard")
async def get_advanced_dashboard(
    date_from: Optional[str] = None, date_to: Optional[str] = None
):
    """
    لوحة التحكم المالية المتقدمة
    """

    # في الوقت الحالي، نستخدم بيانات تجريبية
    # لاحقاً سنجلب من قاعدة البيانات

    # بيانات تجريبية
    from routes_accounts_chart import accounts_db, _initialize_accounts

    _initialize_accounts()

    operations = []  # سنجلبها من DB
    parts = []
    services = []
    customers = []
    suppliers = []

    try:
        # محاولة جلب البيانات الحقيقية (إذا كانت متوفرة)
        # هذا placeholder - سيتم تحديثه لاحقاً
        pass
    except Exception:
        pass

    report = financial_analytics.generate_analytics_report(
        operations=operations,
        accounts=accounts_db,
        parts=parts,
        services=services,
        customers=customers,
        suppliers=suppliers,
    )

    return report


@router.get("/financial-ratios")
async def get_financial_ratios():
    """
    الحصول على النسب المالية فقط
    """

    from routes_accounts_chart import accounts_db, _initialize_accounts

    _initialize_accounts()

    # حساب الأرصدة
    cash = sum(a["balance"] for a in accounts_db if a["code"] in ["1001", "1002"])
    receivables = sum(a["balance"] for a in accounts_db if a["code"] == "2001")
    inventory = sum(a["balance"] for a in accounts_db if a["code"] == "3001")

    total_assets = sum(a["balance"] for a in accounts_db if a["type"] == "asset")
    total_liabilities = sum(
        a["balance"] for a in accounts_db if a["type"] == "liability"
    )
    current_assets = cash + receivables + inventory
    current_liabilities = sum(a["balance"] for a in accounts_db if a["code"] == "6001")

    revenue = sum(a["balance"] for a in accounts_db if a["type"] == "revenue")
    expenses = sum(a["balance"] for a in accounts_db if a["type"] == "expense")
    cogs = sum(a["balance"] for a in accounts_db if a["code"] == "5001")

    ratios = financial_analytics.calculate_financial_ratios(
        assets=total_assets,
        current_assets=current_assets,
        inventory=inventory,
        liabilities=total_liabilities,
        current_liabilities=current_liabilities,
        revenue=revenue,
        expenses=expenses,
        cogs=cogs,
    )

    return {
        "ratios": ratios,
        "summary": {
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "revenue": revenue,
            "expenses": expenses,
            "net_profit": revenue - expenses,
        },
    }


@router.get("/top-performers")
async def get_top_performers(days: int = 30):
    """
    الحصول على أفضل الخدمات والقطع أداءً
    """

    # بيانات تجريبية - سيتم استبدالها بقاعدة البيانات
    top_services = [
        {"name": "تغيير زيت", "revenue": 4500, "count": 30},
        {"name": "فحص كمبيوتر", "revenue": 3000, "count": 20},
        {"name": "تغيير فرامل", "revenue": 2500, "count": 10},
    ]

    top_parts = [
        {"name": "فلتر زيت", "revenue": 1500, "quantity": 30},
        {"name": "فرامل أمامية", "revenue": 2500, "quantity": 10},
        {"name": "بطارية سيارة", "revenue": 4500, "quantity": 10},
    ]

    return {
        "period": f"آخر {days} يوم",
        "top_services": top_services,
        "top_parts": top_parts,
    }


@router.get("/profit-loss")
async def get_profit_loss_statement(
    month: Optional[int] = None, year: Optional[int] = None
):
    """
    قائمة الدخل (الأرباح والخسائر)
    """

    from routes_accounts_chart import accounts_db, _initialize_accounts

    _initialize_accounts()

    # إيرادات
    service_revenue = sum(a["balance"] for a in accounts_db if a["code"] == "4001")
    parts_revenue = sum(a["balance"] for a in accounts_db if a["code"] == "4002")
    total_revenue = service_revenue + parts_revenue

    # تكلفة البضاعة المباعة
    cogs = sum(a["balance"] for a in accounts_db if a["code"] == "5001")

    # مجمل الربح
    gross_profit = total_revenue - cogs

    # مصروفات التشغيل
    salaries = sum(a["balance"] for a in accounts_db if a["code"] == "5002")
    operating_exp = sum(
        a["balance"] for a in accounts_db if a["code"] in ["5003", "5004", "5005"]
    )
    total_operating_exp = salaries + operating_exp

    # صافي الربح
    net_profit = gross_profit - total_operating_exp

    return {
        "period": f"{year or datetime.now().year}/{month or datetime.now().month}",
        "revenue": {
            "services": service_revenue,
            "parts": parts_revenue,
            "total": total_revenue,
        },
        "cost_of_goods_sold": cogs,
        "gross_profit": gross_profit,
        "gross_margin_percentage": round(
            (gross_profit / total_revenue * 100) if total_revenue > 0 else 0, 2
        ),
        "operating_expenses": {
            "salaries": salaries,
            "other": operating_exp,
            "total": total_operating_exp,
        },
        "net_profit": net_profit,
        "net_margin_percentage": round(
            (net_profit / total_revenue * 100) if total_revenue > 0 else 0, 2
        ),
    }


@router.get("/cash-flow")
async def get_cash_flow(days: int = 30):
    """
    تحليل التدفق النقدي
    """

    # بيانات تجريبية
    return {
        "period": f"آخر {days} يوم",
        "cash_inflows": {"sales_cash": 15000, "collections": 5000, "total": 20000},
        "cash_outflows": {
            "purchases": 8000,
            "salaries": 5000,
            "operating_expenses": 2000,
            "total": 15000,
        },
        "net_cash_flow": 5000,
        "opening_balance": 45000,
        "closing_balance": 50000,
    }


@router.get("/inventory-analysis")
async def get_inventory_analysis():
    """
    تحليل المخزون
    """

    # بيانات تجريبية - سيتم جلبها من قاعدة البيانات
    return {
        "total_value": 75000,
        "total_items": 155,
        "low_stock_items": [
            {"name": "فلتر هواء", "current": 8, "min": 10, "reorder": 20},
            {"name": "سير مكينة", "current": 3, "min": 5, "reorder": 15},
        ],
        "fast_moving": [
            {"name": "فلتر زيت", "sales_per_month": 30},
            {"name": "زيت محرك", "sales_per_month": 25},
        ],
        "slow_moving": [
            {"name": "رادياتير", "sales_per_month": 2},
            {"name": "كمبروسر AC", "sales_per_month": 1},
        ],
    }
