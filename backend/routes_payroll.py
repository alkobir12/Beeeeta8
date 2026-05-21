from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
from datetime import datetime
import uuid
import os

from supabase_service import SupabaseService

router = APIRouter(prefix="/api")
db = None
supabase_service = SupabaseService()
DB_PROVIDER = os.environ.get("DB_PROVIDER", "mongo").lower()


def set_db(database):
    global db
    db = database


# ============ Employee Performance ============
@router.post("/employee-performance")
async def log_employee_performance(payload: Dict[str, Any]):
    """تسجيل أداء موظف"""
    try:
        record = {
            "id": str(uuid.uuid4()),
            "employeeId": payload.get("employeeId"),
            "workDate": datetime.utcnow(),
            "hoursWorked": float(payload.get("hoursWorked", 0)),
            "vehicleId": payload.get("vehicleId"),
            "notes": payload.get("notes", ""),
            "createdAt": datetime.utcnow(),
        }

        await db.employee_performance.insert_one(record)
        record.pop("_id", None)
        return record
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/employee-performance")
async def get_employee_performance(employee_id: str = None, vehicle_id: str = None):
    """الحصول على سجلات الأداء"""
    try:
        query = {}
        if employee_id:
            query["employeeId"] = employee_id
        if vehicle_id:
            query["vehicleId"] = vehicle_id

        records = (
            await db.employee_performance.find(query)
            .sort("workDate", -1)
            .to_list(length=100)
        )
        for r in records:
            r.pop("_id", None)
            if r.get("workDate"):
                r["workDate"] = r["workDate"].isoformat()
            if r.get("createdAt"):
                r["createdAt"] = r["createdAt"].isoformat()

        return {"records": records, "count": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Salary Records ============
@router.post("/salary-records")
async def create_salary_record(payload: Dict[str, Any]):
    """إضافة سجل راتب"""
    try:
        basic_salary = float(payload.get("basicSalary", 0))
        allowances = float(payload.get("allowances", 0))
        deductions = float(payload.get("deductions", 0))
        total = basic_salary + allowances - deductions

        record = {
            "id": str(uuid.uuid4()),
            "employeeId": payload.get("employeeId"),
            "month": int(payload.get("month")),
            "year": int(payload.get("year")),
            "basicSalary": basic_salary,
            "allowances": allowances,
            "deductions": deductions,
            "totalSalary": total,
            "paymentDate": payload.get("paymentDate"),
            "paymentStatus": payload.get("paymentStatus", "pending"),
            "notes": payload.get("notes", ""),
            "createdAt": datetime.utcnow(),
        }

        await db.salary_records.insert_one(record)

        # Auto-create expense transaction
        if record["paymentStatus"] == "paid":
            transaction = {
                "id": str(uuid.uuid4()),
                "accountId": payload.get("accountId", ""),
                "type": "expense",
                "category": "salary",
                "amount": total,
                "description": f"راتب - {payload.get('employeeName', 'موظف')} - {record['month']}/{record['year']}",
                "date": datetime.utcnow(),
                "reference": record["id"],
                "createdAt": datetime.utcnow(),
            }
            try:
                await db.transactions.insert_one(transaction)
            except Exception:
                pass

        record.pop("_id", None)
        return record
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/salary-records")
async def get_salary_records(
    employee_id: str = None, year: int = None, month: int = None
):
    """الحصول على سجلات الرواتب"""
    try:
        query = {}
        if employee_id:
            query["employeeId"] = employee_id
        if year:
            query["year"] = year
        if month:
            query["month"] = month

        records = (
            await db.salary_records.find(query)
            .sort("year", -1)
            .sort("month", -1)
            .to_list(length=100)
        )
        for r in records:
            r.pop("_id", None)
            if r.get("createdAt"):
                r["createdAt"] = r["createdAt"].isoformat()

        return {"records": records, "count": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/salary-records/{record_id}")
async def update_salary_record(record_id: str, payload: Dict[str, Any]):
    """تحديث سجل راتب"""
    try:
        update_data = {}

        if "paymentStatus" in payload:
            update_data["paymentStatus"] = payload["paymentStatus"]

            # If marking as paid, create transaction
            if payload["paymentStatus"] == "paid":
                record = await db.salary_records.find_one({"id": record_id})
                if record:
                    transaction = {
                        "id": str(uuid.uuid4()),
                        "accountId": payload.get("accountId", ""),
                        "type": "expense",
                        "category": "salary",
                        "amount": record.get("totalSalary", 0),
                        "description": f"راتب - {record['month']}/{record['year']}",
                        "date": datetime.utcnow(),
                        "reference": record_id,
                        "createdAt": datetime.utcnow(),
                    }
                    await db.transactions.insert_one(transaction)

        if update_data:
            await db.salary_records.update_one({"id": record_id}, {"$set": update_data})

        updated = await db.salary_records.find_one({"id": record_id})
        updated.pop("_id", None)
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Compatibility Endpoints for Frontend
@router.get("/employees")
async def get_employees(active_only: bool = False):
    try:
        provider = os.environ.get("DB_PROVIDER", "mongo").lower()
        if provider == "supabase":
            from supabase_service import SupabaseService

            supa = SupabaseService()
            techs = supa.technicians_list()
            return [
                {
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "role": t.get("specialty") or "Technician",
                    "salary": 5000,
                    "phone": t.get("phone"),
                }
                for t in techs
            ]

        if db is None:
            return []
        techs = await db.technicians.find().to_list(1000)
        return [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "role": t.get("specialty") or "Technician",
                "salary": 5000,
                "phone": t.get("phone"),
            }
            for t in techs
        ]
    except Exception:
        return []


@router.get("/salaries")
async def get_salaries_alias():
    res = await get_salary_records()
    # flatten structure for frontend if needed or just return list
    # Frontend expects array directly
    return res.get("records", [])


@router.post("/salaries")
async def create_salary_alias(payload: Dict[str, Any] = Body(...)):
    p = payload.copy()
    if "month" in p and isinstance(p["month"], str) and "-" in p["month"]:
        parts = p["month"].split("-")
        p["year"] = int(parts[0])
        p["month"] = int(parts[1])
    elif "month" not in p:
        p["month"] = datetime.utcnow().month
        p["year"] = datetime.utcnow().year

    p["allowances"] = float(p.get("bonus", 0))
    return await create_salary_record(p)
