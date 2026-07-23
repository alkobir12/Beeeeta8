"""Destructive, confirmed reset: replace all document templates with the primary invoice template."""
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / '.env')
TEMPLATE_ID = 'primary-mobile-a4-invoice-v1'
HTML = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>
@page{size:A4;margin:12mm}*{box-sizing:border-box}body{font-family:Tahoma,Arial,sans-serif;color:#172033;background:#fff;margin:0}.invoice{max-width:794px;margin:auto}.head{display:flex;justify-content:space-between;gap:18px;border-bottom:3px solid #175a9e;padding-bottom:16px}.brand h1{margin:0;color:#175a9e;font-size:25px}.muted{color:#64748b;font-size:12px}.doc{text-align:left}.doc b{display:block;font-size:18px}.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin:16px 0}.box{border:1px solid #d8e2ee;border-radius:8px;padding:12px}.box h3{margin:0 0 8px;color:#175a9e;font-size:14px}.box p{margin:4px 0;font-size:12px}table{width:100%;border-collapse:collapse;margin-top:12px}th{background:#175a9e;color:white;padding:9px;font-size:12px}td{border:1px solid #d8e2ee;padding:8px;font-size:12px}.total{display:flex;justify-content:flex-start;margin-top:14px}.total .box{min-width:250px}.grand{font-size:18px;font-weight:bold;color:#175a9e}.approvals{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:22px}.seal{border:2px solid #b91c1c;color:#b91c1c;border-radius:50%;width:90px;height:90px;display:grid;place-items:center;text-align:center;font-weight:bold;font-size:11px;margin-top:8px}.foot{border-top:1px solid #d8e2ee;margin-top:18px;padding-top:10px;font-size:10px;color:#64748b;display:flex;justify-content:space-between}@media(max-width:600px){.head,.grid,.approvals{display:block}.box{margin-bottom:9px}.doc{text-align:right;margin-top:10px}table{font-size:11px}.invoice{padding:8px}}
</style></head><body><main class="invoice"><header class="head"><div class="brand"><h1>{{WORKSHOP_NAME}}</h1><div class="muted">{{WORKSHOP_ADDRESS}} · {{WORKSHOP_PHONE}}</div><div class="muted">الرقم الضريبي: {{COMPANY_TAX}}</div></div><div class="doc"><b>فاتورة ضريبية</b><div>رقم: {{INVOICE_NO}}</div><div>{{DATE}}</div></div></header><section class="grid"><div class="box"><h3>بيانات العميل</h3><p>{{CUSTOMER_NAME}}</p><p>{{CUSTOMER_PHONE}}</p></div><div class="box"><h3>بيانات المركبة</h3><p>{{VEHICLE_INFO}}</p><p>اللوحة: {{PLATE_NO}}</p></div><div class="box"><h3>ملخص الفاتورة</h3><p>الإجمالي قبل الضريبة: {{SUBTOTAL}}</p><p>الضريبة: {{TAX}}</p><p class="grand">الإجمالي: {{TOTAL}}</p></div></section><table><thead><tr><th>#</th><th>البيان</th><th>الكمية</th><th>سعر الوحدة</th><th>الإجمالي</th></tr></thead><tbody><!--{{ITEMS_ROWS}}--></tbody></table><section class="approvals"><div class="box"><h3>اعتماد العميل</h3><p>توقيع إلكتروني</p><div class="seal">اعتماد العميل<br>{{SEAL_CODE}}</div></div><div class="box"><h3>اعتماد الورشة</h3><p>مستند إلكتروني معتمد</p><div class="seal">ختم الورشة<br>{{SEAL_CODE}}</div></div></section><footer class="foot"><span>معرّف المستند: {{INVOICE_NO}}</span><span>تم الإصدار إلكترونيًا</span></footer></main></body></html>'''

async def reset():
    client=AsyncIOMotorClient(os.environ['MONGO_URL']); db=client[os.environ['DB_NAME']]; now=datetime.now(timezone.utc).isoformat()
    await db.document_templates.delete_many({})
    await db.document_templates.insert_one({'id':TEMPLATE_ID,'tenant_id':'default','document_type':'invoice','locale':'ar-SA','name':'فاتورة رئيسية A4 وجوال','version':1,'status':'valid','active':True,'is_default':True,'file_type':'html','is_builtin':False,'source':'approved_pdf_rebuild','inline_content':HTML,'created_at':now,'updated_at':now})
    print({'template_id':TEMPLATE_ID,'deleted_all_templates':True})
    client.close()
if __name__=='__main__': asyncio.run(reset())