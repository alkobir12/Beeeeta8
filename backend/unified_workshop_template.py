"""القالب النظامي الموحّد لفاتورة الورشة وتقرير التشخيص."""


def unified_workshop_template(doc_type: str = "invoice") -> str:
    titles = {
        "invoice": ("فاتورة مبيعات", "SALES INVOICE"),
        "diagnosis": ("تقرير تشخيص", "DIAGNOSTIC REPORT"),
        "quote": ("عرض سعر", "QUOTATION"),
        "receipt": ("سند زيارة", "VISIT RECEIPT"),
    }
    title_ar, title_en = titles.get(doc_type, titles["invoice"])
    return f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>قالب موحّد — ورشة سيارات</title>
<style>
  :root{{--fb:"IBM Plex Sans Arabic","Segoe UI",Tahoma,sans-serif;--fm:"IBM Plex Mono",ui-monospace,monospace;--sand:#F3F0E8;--surface:#FFFEFB;--ink:#17191C;--ink2:#687078;--petrol:#0B6B63;--orange:#F36B2B;--danger:#C43D3D;--line:#DFDACE;--line2:#EDE9DF}}
  *{{box-sizing:border-box;margin:0;padding:0;letter-spacing:0}}
  html{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  body{{font-family:var(--fb);font-size:12.5px;line-height:1.55;color:var(--ink);background:var(--sand);margin:0;padding:14mm 0 24mm;display:flex;justify-content:center}}
  .page{{width:210mm;min-height:297mm;background:var(--surface);box-shadow:0 2px 18px -8px rgba(23,25,28,.25);display:flex;justify-content:center;padding-top:10mm;box-sizing:border-box;page-break-after:always}}
  .sheet{{width:190mm;background:var(--surface)}}
  .head{{background:var(--ink);color:var(--surface);padding:11px 16px 10px;display:table;width:100%;table-layout:fixed;border-radius:11px 11px 0 0}}
  .head>div{{display:table-cell;vertical-align:middle}}
  .ws-name{{font-weight:700;font-size:19px;line-height:1.3;min-height:25px}}
  .ws-sub{{font-size:10.5px;color:#A9AFB4;margin-top:2px;min-height:14px}}
  .doc{{text-align:left}}
  .doc-kind{{font-weight:700;font-size:17px;line-height:1.25;color:var(--surface);min-height:22px}}
  .doc-en{{font-family:var(--fm);font-size:8.5px;letter-spacing:1.8px;color:#7C848A;direction:ltr;margin-top:3px}}
  .rule{{height:3px;background:var(--petrol)}}
  .cards{{padding:9px 0 0}}
  .crow{{display:table;width:100%;table-layout:fixed;border-spacing:8px 0;margin:0 -8px 8px}}
  .crow>div{{display:table-cell;vertical-align:top;width:50%}}
  .card{{border:1px solid var(--line);border-radius:11px;background:var(--surface);padding:8px 11px 9px;height:100%;break-inside:avoid}}
  .cap{{font-size:10px;font-weight:600;color:var(--petrol);padding-bottom:5px;margin-bottom:7px;border-bottom:1px solid var(--line2)}}
  .f,.f2{{display:table;width:100%;margin-bottom:4px}}
  .f2{{table-layout:fixed}}
  .f:last-child{{margin-bottom:0}}
  .f>span,.f2>span{{display:table-cell;vertical-align:bottom}}
  .k{{font-size:11px;color:var(--ink2);width:82px;white-space:nowrap}}
  .f2 .k{{width:80px}}
  .f2 .k.b{{width:62px;padding-right:10px}}
  .v{{font-size:12.5px;font-weight:600;color:var(--ink);min-height:16px}}
  .v.line{{border-bottom:1px solid var(--line2);height:17px}}
  .v.key{{color:var(--petrol);font-weight:700}}
  .ltr{{font-family:var(--fm);font-weight:500;direction:ltr;unicode-bidi:isolate}}
  .odo{{display:inline-block;font-family:var(--fm);font-weight:600;font-size:13px;background:var(--sand);border:1px solid var(--line);border-radius:7px;padding:2px 9px;direction:ltr;min-width:34mm;text-align:center}}
  .odo em{{font-style:normal;font-size:8.5px;color:var(--ink2);margin-right:4px;font-family:var(--fb)}}
  .plate{{display:table;border:1.5px solid var(--ink);border-radius:6px;background:var(--surface);overflow:hidden;min-width:36mm}}
  .plate>span{{display:table-cell;vertical-align:middle;padding:2px 9px;text-align:center;line-height:1.15;min-width:36px}}
  .plate .ltrs{{font-weight:700;font-size:14.5px;letter-spacing:3px;border-left:1.5px solid var(--ink)}}
  .plate .num{{font-family:var(--fm);font-weight:600;font-size:15px;letter-spacing:1.2px;direction:ltr}}
  .plate em{{display:block;font-family:var(--fm);font-style:normal;font-size:7px;letter-spacing:1.4px;color:var(--ink2);direction:ltr}}
  .diag{{border:1px solid var(--line);border-radius:11px;margin-bottom:8px;overflow:hidden;break-inside:avoid}}
  .diag-h{{background:var(--sand);padding:5px 11px;font-size:10px;font-weight:600;color:var(--petrol);border-bottom:1px solid var(--line)}}
  .diag-b{{display:table;width:100%;table-layout:fixed}}
  .diag-b>div{{display:table-cell;vertical-align:top;padding:7px 11px 8px;border-right:1px solid var(--line2)}}
  .diag-b>div:first-child{{border-right:none}}
  .dlab{{font-size:9.5px;color:var(--ink2);margin-bottom:3px}}
  .dval{{font-size:11.5px;line-height:1.6;min-height:30px;font-weight:500}}
  .codes{{min-height:30px}}
  .codes .dtc{{display:inline-block;font-family:var(--fm);font-weight:600;font-size:11px;color:var(--danger);border:1px solid var(--danger);border-radius:6px;padding:1px 8px;margin:0 0 3px 4px;direction:ltr}}
  table{{width:100%;border-collapse:collapse;break-inside:auto}}
  thead th{{font-size:10px;font-weight:600;color:var(--ink2);text-align:right;padding:0 7px 6px;border-bottom:1.5px solid var(--ink);white-space:nowrap}}
  tbody td{{padding:4.6px 7px;font-size:12px;border-bottom:1px solid var(--line2)}}
  tbody tr{{break-inside:avoid;page-break-inside:avoid}}
  tbody tr:nth-child(even){{background:var(--sand)}}
  .c-no{{width:24px;text-align:center;font-family:var(--fm);font-size:10.5px;color:var(--ink2)}}
  .c-kind{{width:60px;font-size:10.5px;color:var(--ink2)}}
  .c-code{{width:98px;font-family:var(--fm);font-size:11px;font-weight:500;direction:ltr;text-align:left;unicode-bidi:isolate}}
  .c-desc{{font-weight:600}}
  .c-desc u{{text-decoration:none;font-family:var(--fm);font-weight:400;font-size:9.5px;color:var(--ink2);direction:ltr;unicode-bidi:isolate;margin-right:6px}}
  .c-qty{{width:44px;text-align:center;font-family:var(--fm);font-weight:500;font-size:12px}}
  .c-unit,.c-sum{{font-family:var(--fm);font-weight:500;direction:ltr;text-align:left;font-size:12px}}
  .c-unit{{width:72px;color:var(--ink2)}}
  .c-sum{{width:78px}}
  th.c-no,th.c-kind,th.c-code,th.c-desc,th.c-qty,th.c-unit,th.c-sum{{font-family:var(--fb);font-weight:600}}
  th.c-code,th.c-unit,th.c-sum{{text-align:left}}
  th.c-no,th.c-qty{{text-align:center}}
  .foot{{display:table;width:100%;table-layout:fixed;border-spacing:8px 0;margin:9px -8px 0;break-inside:avoid}}
  .foot>div{{display:table-cell;vertical-align:bottom;width:50%}}
  .chip{{border:1px solid var(--line);border-radius:8px;padding:5px 10px;font-size:10.5px;color:var(--ink2);background:var(--surface);display:inline-block;margin:0 0 5px 5px}}
  .chip b{{font-family:var(--fm);font-weight:600;color:var(--ink);font-size:12px}}
  .total{{background:var(--ink);color:var(--surface);border-radius:11px;padding:9px 14px;border-right:4px solid var(--petrol)}}
  .total .tk{{font-size:13px;font-weight:700;color:#E8E4DA}}
  .total .tn{{font-family:var(--fm);font-weight:600;font-size:24px;margin-top:2px;direction:ltr;text-align:left;min-height:29px}}
  .total .tn em{{font-family:var(--fb);font-style:normal;font-size:11px;font-weight:600;color:#B9BEC2;margin-right:7px}}
  .total .tw{{font-size:10px;color:#A9AFB4;margin-top:5px;border-top:1px solid rgba(255,254,251,.16);padding-top:5px;min-height:13px}}
  .strip{{border:1px solid var(--line);border-radius:11px;padding:6px 11px;margin-top:8px;font-size:10.5px;line-height:1.6;color:var(--ink2);break-inside:avoid}}
  .strip b{{color:var(--ink);font-weight:600}}
  .strip.urgent{{border-right:4px solid var(--orange);background:#FEF6F1}}
  .strip.urgent b{{color:var(--orange)}}
  .sign{{display:table;width:100%;table-layout:fixed;border-spacing:8px 0;margin:8px -8px 0;break-inside:avoid}}
  .sign>div{{display:table-cell;width:50%;vertical-align:top}}
  .sbox{{border:1px solid var(--line);border-radius:11px;padding:8px 11px 9px;break-inside:avoid}}
  .slab{{font-size:11px;font-weight:600;color:var(--ink);margin-bottom:3px}}
  .sname{{font-size:10.5px;color:var(--ink2);min-height:15px;margin-bottom:4px}}
  .sarea{{height:26px;position:relative}}
  .stampbox{{position:absolute;left:0;top:-2px;width:50px;height:26px;border:1px solid var(--line2);border-radius:7px;font-size:8px;color:#A8A296;text-align:center;line-height:26px}}
  .sline{{border-top:1.2px solid var(--ink);margin-top:2px}}
  .scap{{font-size:9px;color:var(--ink2);margin-top:4px}}
  .tail{{background:var(--ink);color:#A9AFB4;font-size:10px;padding:7px 16px;margin-top:8px;display:table;width:100%;table-layout:fixed;border-radius:0 0 11px 11px}}
  .tail>span{{display:table-cell}}
  .tail .r{{text-align:left;font-family:var(--fm);direction:ltr}}
  @page{{size:A4;margin:10mm}}
  @media print{{body{{background:#fff;padding:0;display:block}}.page{{width:auto;min-height:0;background:none;box-shadow:none;padding-top:0;display:block}}.sheet{{width:auto}}thead{{display:table-header-group}}}}
</style>
</head>
<body>
<div class="page" data-testid="document-a4-page">
<div class="sheet" data-testid="document-a4-sheet">
  <div class="head" data-testid="document-header">
    <div>
      <div class="ws-name" data-testid="document-workshop-name">{{{{WORKSHOP_NAME}}}}</div>
      <div class="ws-sub" data-testid="document-workshop-tagline">{{{{WORKSHOP_TAGLINE}}}}</div>
    </div>
    <div class="doc">
      <div class="doc-kind" data-testid="document-title">{title_ar}</div>
      <div class="doc-en" data-testid="document-title-en">{title_en}</div>
    </div>
  </div>
  <div class="rule"></div>
  <div class="cards">
    <div class="crow">
      <div><div class="card" data-testid="document-workshop-card"><div class="cap">بيانات الورشة</div><div class="f"><span class="k">السجل التجاري</span><span class="v ltr" data-testid="document-workshop-cr">{{{{COMPANY_CR}}}}</span></div><div class="f"><span class="k">رقم التواصل</span><span class="v ltr" data-testid="document-workshop-phone">{{{{WORKSHOP_PHONE}}}}</span></div><div class="f"><span class="k">العنوان</span><span class="v" data-testid="document-workshop-address">{{{{WORKSHOP_ADDRESS}}}}</span></div></div></div>
      <div><div class="card" data-testid="document-meta-card"><div class="cap">بيانات المستند</div><div class="f2"><span class="k">رقم المستند</span><span class="v ltr key line" data-testid="document-number">{{{{INVOICE_NO}}}}</span><span class="k b">أمر التشغيل</span><span class="v ltr line" data-testid="document-job-order">{{{{JOB_ORDER}}}}</span></div><div class="f2"><span class="k">تاريخ الدخول</span><span class="v line" data-testid="document-entry-date">{{{{ENTRY_DATE}}}}</span><span class="k b">تاريخ التسليم</span><span class="v line" data-testid="document-delivery-date">{{{{DELIVERY_DATE}}}}</span></div><div class="f"><span class="k">طريقة الدفع</span><span class="v line" data-testid="document-payment-method">{{{{PAYMENT_METHOD}}}}</span></div></div></div>
    </div>
    <div class="crow">
      <div><div class="card" data-testid="document-customer-card"><div class="cap">بيانات العميل</div><div class="f"><span class="k">اسم العميل</span><span class="v line" data-testid="document-customer-name">{{{{CUSTOMER_NAME}}}}</span></div><div class="f"><span class="k">رقم الجوال</span><span class="v ltr line" data-testid="document-customer-phone">{{{{CUSTOMER_PHONE}}}}</span></div><div class="f"><span class="k">قراءة العداد</span><span class="v"><span class="odo" data-testid="document-odometer"><span>{{{{ODOMETER}}}}</span><em>كم</em></span></span></div></div></div>
      <div><div class="card" data-testid="document-vehicle-card"><div class="cap">بيانات المركبة</div><div class="f2"><span class="k">الماركة والطراز</span><span class="v key line" data-testid="document-vehicle-model">{{{{VEHICLE_MODEL}}}}</span><span class="k b">سنة الصنع</span><span class="v ltr line" data-testid="document-vehicle-year">{{{{VEHICLE_YEAR}}}}</span></div><div class="f"><span class="k">رقم الهيكل</span><span class="v ltr line" data-testid="document-vehicle-vin">{{{{VEHICLE_VIN}}}}</span></div><div class="f"><span class="k">رقم اللوحة</span><span class="v"><span class="plate" data-testid="document-plate"><span class="ltrs"><span>{{{{PLATE_LETTERS_AR}}}}</span><em>{{{{PLATE_LETTERS_EN}}}}</em></span><span class="num"><span>{{{{PLATE_DIGITS_AR}}}}</span><em>{{{{PLATE_DIGITS_EN}}}}</em></span></span></span></div></div></div>
    </div>
  </div>
  <div class="diag" data-testid="document-diagnosis-section"><div class="diag-h">الفحص والتشخيص</div><div class="diag-b"><div style="width:34%"><div class="dlab">شكوى العميل</div><div class="dval" data-testid="document-complaint">{{{{COMPLAINT}}}}</div></div><div style="width:41%"><div class="dlab">نتيجة الفحص</div><div class="dval" data-testid="document-inspection">{{{{INSPECTION}}}}</div></div><div style="width:25%"><div class="dlab">أكواد الأعطال (DTC)</div><div class="codes" data-testid="document-dtc-list">{{{{DTC_LIST}}}}</div></div></div></div>
  <table data-testid="document-items-table"><thead><tr><th class="c-no">م</th><th class="c-kind">النوع</th><th class="c-code">رقم الصنف</th><th class="c-desc">البيان / الوصف</th><th class="c-qty">الكمية</th><th class="c-unit">السعر</th><th class="c-sum">الإجمالي (ر.س)</th></tr></thead><tbody>{{{{ITEMS_ROWS}}}}</tbody></table>
  <div class="foot"><div><span class="chip">قطع الغيار <b data-testid="document-parts-total">{{{{PARTS_TOTAL}}}}</b></span><span class="chip">أجور العمل <b data-testid="document-labor-total">{{{{LABOR_TOTAL}}}}</b></span><span class="chip">عدد البنود <b data-testid="document-item-count">{{{{ITEM_COUNT}}}}</b></span></div><div><div class="total" data-testid="document-total-card"><div class="tk">الإجمالي النهائي المستحق</div><div class="tn"><span data-testid="document-total">{{{{TOTAL_AMOUNT}}}}</span> <em>ريال سعودي</em></div><div class="tw" data-testid="document-amount-words">{{{{AMOUNT_WORDS}}}}</div></div></div></div>
  <div class="strip urgent" data-testid="document-recommendation"><b>توصيات تحتاج متابعة:</b> <span>{{{{RECOMMENDATION}}}}</span></div>
  <div class="strip" data-testid="document-warranty"><b>الضمان:</b> <span>{{{{WARRANTY}}}}</span></div>
  <div class="sign"><div><div class="sbox" data-testid="document-technician-signature"><div class="slab">الفني المسؤول</div><div class="sname">{{{{TECHNICIAN}}}}</div><div class="sarea"><span class="stampbox">الختم</span></div><div class="sline"></div><div class="scap">التوقيع والختم</div></div></div><div><div class="sbox" data-testid="document-customer-signature"><div class="slab">استلام العميل</div><div class="sname">&nbsp;</div><div class="sarea"></div><div class="sline"></div><div class="scap">أقر باستلام المركبة والأعمال الموضحة أعلاه</div></div></div></div>
  <div class="tail"><span data-testid="document-footer-workshop">{{{{WORKSHOP_NAME}}}}</span><span class="r" data-testid="document-footer-meta">CR {{{{COMPANY_CR}}}} · {{{{WORKSHOP_PHONE}}}}</span></div>
</div>
</div>
</body>
</html>'''.replace("{{DOCUMENT_TITLE_DEFAULT}}", title_ar).replace("{{DOCUMENT_TITLE_EN_DEFAULT}}", title_en)