"""Install the approved unified A4/mobile document template for invoice, diagnosis and quote."""
import asyncio, os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / '.env')
HTML = '''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>
@page{size:A4;margin:10mm}*{box-sizing:border-box}body{font-family:Tahoma,Arial,sans-serif;margin:0;color:#16233d}.sheet{max-width:794px;margin:auto;background:#fff}.head{border-bottom:2px solid #142d56;padding:12px 0;display:flex;justify-content:space-between}.brand b{font-size:22px;color:#142d56}.brand span,.meta{display:block;font-size:11px;color:#64748b;margin-top:4px}.badge{background:#142d56;color:#fff;padding:7px 12px;border-radius:5px;font-weight:bold}.info{display:grid;grid-template-columns:1fr 1fr 1fr;border:1px solid #dbe3ee;border-radius:8px;margin:14px 0}.box{padding:12px;border-left:1px solid #e5eaf1}.box:last-child{border:0}.box h3{font-size:13px;margin:0 0 8px;color:#142d56}.box p{font-size:11px;margin:5px 0}.items{width:100%;border-collapse:collapse}.items th{background:#142d56;color:#fff;padding:9px;font-size:12px}.items td{border:1px solid #dbe3ee;padding:8px;font-size:11px}.n{text-align:center}.after{display:grid;grid-template-columns:1.25fr .75fr;gap:14px;margin-top:14px}.notes,.totals{border:1px solid #dbe3ee;border-radius:8px;padding:12px;font-size:11px}.totals div{display:flex;justify-content:space-between;padding:5px 0}.grand{background:#142d56;color:#fff;padding:9px!important;font-size:16px;font-weight:bold;margin-top:5px}.approvals{display:grid;grid-template-columns:1fr 1fr;border:1px solid #dbe3ee;border-radius:8px;margin-top:14px}.approval{min-height:155px;padding:12px;text-align:center;border-left:1px solid #dbe3ee}.approval:last-child{border:0}.approval h3{margin:0;color:#142d56}.barcode{margin-top:14px;border:1px solid #dbe3ee;border-radius:8px;padding:12px;text-align:center}.bars{height:38px;background:repeating-linear-gradient(90deg,#111 0 2px,#fff 2px 4px,#111 4px 5px,#fff 5px 8px)}.barcode small{display:block;direction:ltr;margin-top:5px}@media(max-width:600px){.head,.info,.after,.approvals{display:block}.box,.approval{border:0;border-bottom:1px solid #e5eaf1}.head{gap:8px}.items{font-size:10px}.items th,.items td{padding:5px}.sheet{padding:6px}}
</style></head><body><main class="sheet"><header class="head"><div class="brand"><b>{{WORKSHOP_NAME}}</b><span>{{WORKSHOP_ADDRESS}} · {{WORKSHOP_PHONE}}</span><span>سجل الورشة: {{COMPANY_CR}}</span></div><div class="meta"><span class="badge">{{DOCUMENT_TITLE}}</span><b>{{INVOICE_NO}}</b><span>{{DATE}}</span></div></header><section class="info"><div class="box"><h3>بيانات العميل</h3><p>{{CUSTOMER_NAME}}</p><p>{{CUSTOMER_PHONE}}</p></div><div class="box"><h3>بيانات المركبة</h3><p>{{VEHICLE_INFO}}</p><p>اللوحة: {{PLATE_NO}}</p></div><div class="box"><h3>ملخص المستند</h3><p>الحالة: {{STATUS_LABEL}}</p><p>المتبقي: {{REMAINING}}</p></div></section><table class="items"><thead><tr><th>#</th><th>البيان</th><th>الكمية</th><th>سعر الوحدة</th><th>الخصم</th><th>الإجمالي</th></tr></thead><tbody><!--{{ITEMS_ROWS}}--></tbody></table><section class="after"><div class="notes"><b>ملاحظات</b><p>{{NOTES}}</p></div><div class="totals"><div><span>المجموع</span><b>{{SUBTOTAL}}</b></div>{{TAX_ROW}}<div class="grand"><span>الإجمالي الكلي</span><b>{{TOTAL}}</b></div></div></section><section class="approvals"><div class="approval"><h3>اعتماد العميل</h3>{{CUSTOMER_APPROVAL_STAMP}}</div><div class="approval"><h3>اعتماد الورشة</h3>{{WORKSHOP_APPROVAL_STAMP}}</div></section><section class="barcode"><div class="bars"></div><small>{{BARCODE_VALUE}}</small><span>نسخة إلكترونية معتمدة وغير قابلة للتعديل</span></section></main></body></html>'''

async def run():
    client=AsyncIOMotorClient(os.environ['MONGO_URL']); db=client[os.environ['DB_NAME']]; now=datetime.now(timezone.utc).isoformat()
    await db.document_templates.delete_many({})
    docs=[]
    for doc_type,title in [('invoice','فاتورة مبيعات'),('diagnosis','تقرير تشخيص'),('quote','عرض سعر')]:
        docs.append({'id':f'unified-{doc_type}-a4-mobile-v1','tenant_id':'default','document_type':doc_type,'locale':'ar-SA','name':f'{title} موحد A4 وجوال','version':1,'status':'valid','active':True,'is_default':True,'file_type':'html','is_builtin':False,'source':'approved_workflow_design','inline_content':HTML,'created_at':now,'updated_at':now})
    await db.document_templates.insert_many(docs)
    print({'template_ids':[d['id'] for d in docs]}); client.close()
if __name__=='__main__':
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).parent))
    from core.destructive_guard import require_destructive_cli
    require_destructive_cli("adopt_unified_workflow_template")
    asyncio.run(run())