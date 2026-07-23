"""Idempotent P0 fixture for the mobile QuickPrint acceptance flow."""
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")
TENANT = "default"
VEHICLE_ID = "fixture-quickprint-vehicle-001"
CUSTOMER_ID = "fixture-quickprint-customer-001"
VISIT_ID = "fixture-quickprint-visit-001"
TEMPLATE_ID = "fixture-quickprint-template-001"

HTML = """<!doctype html><html dir='rtl'><head><style>body{font-family:sans-serif;padding:28px;color:#172033}table{width:100%;border-collapse:collapse}th,td{border:1px solid #cbd5e1;padding:9px}.total{font-size:20px;font-weight:bold}</style></head><body><h1>{{WORKSHOP_NAME}}</h1><p>فاتورة {{INVOICE_NO}} — {{DATE}}</p><p>العميل: {{CUSTOMER_NAME}} | الجوال: {{CUSTOMER_PHONE}}</p><p>المركبة: {{VEHICLE_INFO}} | {{PLATE_NO}}</p><table><thead><tr><th>البند</th><th>الكمية</th><th>السعر</th><th>الإجمالي</th></tr></thead><tbody>{{ITEMS_ROWS}}</tbody></table><p class='total'>الإجمالي: {{TOTAL}}</p><p>الختم: {{SEAL_CODE}}</p></body></html>"""

async def seed():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc).isoformat()
    await db.workshop_profile.update_one({"tenant_id": TENANT}, {"$set": {"tenant_id": TENANT, "name": "ورشة P0 للاختبار", "business_name": "ورشة P0 للاختبار", "phone": "0500000000", "whatsapp": "0500000000", "address": "الرياض", "tax_number": "300000000000003", "updated_at": now}}, upsert=True)
    await db.customers.update_one({"id": CUSTOMER_ID}, {"$set": {"id": CUSTOMER_ID, "tenant_id": TENANT, "name": "عميل اختبار QuickPrint", "phone": "0500000000", "email": "fixture@example.com", "updated_at": now}}, upsert=True)
    await db.vehicles.update_one({"id": VEHICLE_ID}, {"$set": {"id": VEHICLE_ID, "tenant_id": TENANT, "customerId": CUSTOMER_ID, "customerName": "عميل اختبار QuickPrint", "customerPhone": "0500000000", "plateNumber": "P0 2026", "brand": "Toyota", "model": "Camry", "year": 2024, "status": "in_progress", "updated_at": now}}, upsert=True)
    await db.vehicle_visits.update_one({"id": VISIT_ID}, {"$set": {"id": VISIT_ID, "tenant_id": TENANT, "vehicleId": VEHICLE_ID, "visitNumber": 1, "status": "in_progress", "entryDate": now, "notes": "تغيير زيت", "items": [{"name": "تغيير زيت", "quantity": 1, "price": 100, "total": 100}], "tax": 15, "total": 115, "updated_at": now}}, upsert=True)
    await db.document_templates.update_one({"id": TEMPLATE_ID}, {"$set": {"id": TEMPLATE_ID, "tenant_id": TENANT, "document_type": "invoice", "locale": "ar-SA", "name": "قالب QuickPrint P0", "version": 1, "status": "valid", "active": True, "is_default": True, "file_type": "html", "is_builtin": False, "source": "p0_fixture", "inline_content": HTML, "updated_at": now}}, upsert=True)
    await db.document_templates.update_many({"tenant_id": TENANT, "document_type": "invoice", "locale": "ar-SA", "id": {"$ne": TEMPLATE_ID}}, {"$set": {"is_default": False}})
    print({"vehicle_id": VEHICLE_ID, "visit_id": VISIT_ID, "template_id": TEMPLATE_ID})
    client.close()

if __name__ == "__main__": asyncio.run(seed())