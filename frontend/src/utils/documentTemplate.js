const escapeHtml = (value) => String(value ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const cleanText = (value) => {
  const text = String(value ?? '').trim();
  return ['undefined', 'null', 'nan'].includes(text.toLowerCase()) ? '' : text;
};

const safeNumber = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const money = (value) => `${safeNumber(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ر.س`;
const amount = (value) => safeNumber(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const unique = (values) => [...new Set(values.map((value) => String(value).trim()).filter(Boolean))];

export const findUnresolvedTemplateVariables = (html = '') => {
  const source = String(html || '');
  const matches = [
    ...source.matchAll(/{{\s*([^{}]+?)\s*}}/g),
    ...source.matchAll(/\[\[\s*([^\]]+?)\s*\]\]/g),
    ...source.matchAll(/<%=?\s*([\s\S]*?)\s*%>/g),
    ...source.matchAll(/\{([A-Z][A-Z0-9_]*)\}/g),
  ].map((match) => match[1]);
  return unique(matches);
};

export const createTemplateCompletenessError = (variables = []) => {
  const error = new Error(`القالب غير مكتمل. المتغيرات الناقصة: ${variables.join('، ')}`);
  error.code = 'template_incomplete';
  error.variables = variables;
  return error;
};

export const assertTemplateComplete = (html = '') => {
  const variables = findUnresolvedTemplateVariables(html);
  if (variables.length) throw createTemplateCompletenessError(variables);
  return true;
};

const isSupplierItem = (item = {}) => {
  const rawType = String(item.itemType || item.type || '').trim().toLowerCase();
  const billingType = String(item.billingType || item.billing_type || '').trim().toLowerCase();
  return rawType === 'supplier' || billingType === 'supplier';
};

const itemKindLabel = (item = {}) => {
  const type = String(item.type || item.itemType || item.kind || '').trim().toLowerCase();
  if (['part', 'parts', 'spare', 'spare_part', 'قطعة', 'قطع'].includes(type)) return 'قطعة';
  if (['labor', 'service', 'work', 'أجرة', 'اجرة', 'خدمة'].includes(type)) return 'أجرة';
  return cleanText(item.kindLabel || item.category || '');
};

const normalizeRows = (rows = []) => (Array.isArray(rows) ? rows : [])
  .filter((item) => !isSupplierItem(item))
  .map((item) => {
    const quantity = safeNumber(item.quantity || item.qty || 1, 1);
    const price = safeNumber(item.unit_price || item.price || item.amount || 0);
    const discount = safeNumber(item.discount || 0);
    const total = safeNumber(item.total, (quantity * price) - discount);
    return {
      ...item,
      kind: itemKindLabel(item),
      code: cleanText(item.code || item.sku || item.partNumber || item.part_number || item.itemCode || ''),
      description: cleanText(item.description || item.name || item.itemName || item.serviceName || item.title || ''),
      quantity,
      price,
      discount,
      total,
    };
  });

const docTitle = (docType) => ({
  invoice: ['فاتورة مبيعات', 'SALES INVOICE'],
  diagnosis: ['تقرير تشخيص', 'DIAGNOSTIC REPORT'],
  quote: ['عرض سعر', 'QUOTATION'],
  receipt: ['سند زيارة', 'VISIT RECEIPT'],
}[docType] || ['مستند', 'DOCUMENT']);

const paymentLabel = (method = '') => ({
  cash: 'نقد',
  pos: 'نقاط بيع',
  bank: 'تحويل بنكي',
  bank_transfer: 'تحويل بنكي',
  transfer: 'تحويل بنكي',
}[String(method || '').toLowerCase()] || cleanText(method));

const splitPlate = (plate = '') => {
  const text = cleanText(plate);
  const digits = (text.match(/[0-9٠-٩]+/g) || []).join(' ');
  const letters = text.replace(/[0-9٠-٩\s/\-_.]+/g, ' ').trim();
  return { digits, lettersAr: letters, lettersEn: '', digitsEn: digits };
};

const dtcHtml = (value) => {
  const raw = Array.isArray(value) ? value : String(value || '').split(/[،,\s]+/);
  return raw.map(cleanText).filter(Boolean).map((code) => `<span class="dtc">${escapeHtml(code)}</span>`).join('');
};

const approvalStamp = (approval, label) => approval?.name && approval?.at
  ? `<div class="approved-stamp" style="border:2px solid #15803d;color:#15803d;border-radius:50%;width:92px;height:92px;display:grid;place-items:center;text-align:center;font-weight:900;font-size:11px;line-height:1.3;margin-top:8px">تمت الموافقة<br><small>${escapeHtml(label)}</small><small>${escapeHtml(approval.name)}</small><small>${escapeHtml(new Date(approval.at).toLocaleDateString('ar-SA'))}</small><small>${escapeHtml(String(approval.id || '').slice(0, 12))}</small></div>`
  : '';

const replaceToken = (html, key, value) => {
  const escaped = String(value ?? '');
  return html
    .replace(new RegExp(`{{\\s*${key}\\s*}}`, 'g'), escaped)
    .replace(new RegExp(`\\[\\[\\s*${key}\\s*\\]\\]`, 'g'), escaped)
    .replace(new RegExp(`<%=\\s*${key}\\s*%>`, 'g'), escaped)
    .replaceAll(`{${key}}`, escaped)
    .replaceAll(`<!--{{${key}}}-->`, escaped);
};

export const renderDocumentTemplate = (templateHtml, payload = {}, workshop = {}) => {
  const settings = payload.settings || {};
  const customer = payload.customer || payload.client || {};
  const vehicle = payload.vehicle || {};
  const rows = normalizeRows(payload.items || []);
  const subtotal = rows.reduce((sum, item) => sum + (item.quantity * item.price), 0);
  const discount = rows.reduce((sum, item) => sum + item.discount, 0);
  const itemsTotal = rows.reduce((sum, item) => sum + item.total, 0);
  const taxAmount = safeNumber(settings?.totals?.tax || payload.tax || 0);
  const total = itemsTotal + taxAmount;
  const paid = safeNumber(settings?.totals?.paid || payload?.payment?.paid || 0);
  const docType = payload.doc_type || payload.docType || settings.doc_type || 'invoice';
  const [titleAr, titleEn] = docTitle(docType);
  const documentNumber = cleanText(settings.document_number || payload.document_number || '');
  const plateRaw = cleanText(vehicle.plateNumber || vehicle.plate || '');
  const plate = splitPlate(plateRaw);
  const approvals = payload.approvals || {};
  const partsTotal = rows.filter((item) => item.kind === 'قطعة').reduce((sum, item) => sum + item.total, 0);
  const laborTotal = rows.filter((item) => item.kind !== 'قطعة').reduce((sum, item) => sum + item.total, 0);
  const vehicleName = cleanText(`${vehicle.brand || vehicle.vehicleBrand || ''} ${vehicle.model || vehicle.vehicleModel || ''}`);
  const values = {
    WORKSHOP_NAME: cleanText(workshop.name || workshop.business_name || ''),
    WORKSHOP_TAGLINE: cleanText(workshop.slogan || workshop.tagline || workshop.sloganEnglish || ''),
    WORKSHOP_ADDRESS: cleanText(workshop.address || ''),
    WORKSHOP_PHONE: cleanText(workshop.phone || workshop.whatsapp || ''),
    WORKSHOP_EMAIL: cleanText(workshop.email || ''),
    COMPANY_CR: cleanText(workshop.commercial_register || workshop.commercialRegister || ''),
    COMPANY_TAX: cleanText(workshop.tax_number || workshop.taxNumber || ''),
    TAX_NUMBER: cleanText(workshop.tax_number || workshop.taxNumber || ''),
    CUSTOMER_NAME: cleanText(customer.name || customer.customerName || ''),
    CUSTOMER_PHONE: cleanText(customer.phone || customer.customerPhone || ''),
    VEHICLE_INFO: cleanText(`${vehicleName} ${vehicle.year || vehicle.vehicleYear || ''}`),
    VEHICLE_MODEL: vehicleName,
    VEHICLE_YEAR: cleanText(vehicle.year || vehicle.vehicleYear || ''),
    VEHICLE_VIN: cleanText(vehicle.vin || vehicle.chassisNumber || ''),
    PLATE_NO: plateRaw,
    VEHICLE_PLATE: plateRaw,
    PLATE_LETTERS_AR: plate.lettersAr,
    PLATE_LETTERS_EN: plate.lettersEn,
    PLATE_DIGITS_AR: plate.digits,
    PLATE_DIGITS_EN: plate.digitsEn,
    STATUS_LABEL: cleanText(settings.status || ''),
    INVOICE_NO: documentNumber,
    INVOICE_DATE: cleanText(settings.date || payload.date || ''),
    DATE: cleanText(settings.date || payload.date || ''),
    ENTRY_DATE: cleanText(settings.entry_date || settings.entryDate || settings.date || payload.entry_date || payload.entryDate || payload.date || ''),
    DELIVERY_DATE: cleanText(settings.delivery_date || settings.deliveryDate || payload.delivery_date || payload.deliveryDate || ''),
    JOB_ORDER: cleanText(settings.job_order || settings.jobOrder || payload.job_order || payload.jobOrder || payload.visit_id || payload.visitId || ''),
    PAYMENT_METHOD: paymentLabel(settings.payment_method || settings.paymentMethod || payload?.payment?.method || ''),
    ODOMETER: cleanText(vehicle.mileage || vehicle.odometer || settings.mileage || ''),
    COMPLAINT: cleanText(settings.complaint || payload.complaint || vehicle.complaint || ''),
    INSPECTION: cleanText(settings.inspection || settings.diagnosis || payload.inspection || payload.diagnosis || ''),
    DTC_LIST: dtcHtml(settings.dtc || settings.dtc_codes || payload.dtc || payload.dtc_codes || vehicle.dtc || ''),
    ITEMS_ROWS: rows.map((item, index) => `<tr data-testid="document-item-row-${index}"><td class="c-no" data-testid="document-item-no-${index}">${index + 1}</td><td class="c-kind" data-testid="document-item-kind-${index}">${escapeHtml(item.kind)}</td><td class="c-code" data-testid="document-item-code-${index}">${escapeHtml(item.code)}</td><td class="c-desc" data-testid="document-item-desc-${index}">${escapeHtml(item.description)}</td><td class="c-qty" data-testid="document-item-qty-${index}">${escapeHtml(item.quantity)}</td><td class="c-unit" data-testid="document-item-unit-${index}">${amount(item.price)}</td><td class="c-sum" data-testid="document-item-sum-${index}">${amount(item.total)}</td></tr>`).join(''),
    PARTS_TOTAL: amount(partsTotal),
    LABOR_TOTAL: amount(laborTotal),
    ITEM_COUNT: String(rows.length),
    SUBTOTAL: money(subtotal),
    DISCOUNT: money(discount),
    TAX: money(taxAmount),
    TOTAL: money(total),
    TOTAL_AMOUNT: amount(total),
    PAID: money(paid),
    REMAINING: money(total - paid),
    NOTES: cleanText(settings.notes || payload.notes || ''),
    AMOUNT_WORDS: total > 0 ? `فقط ${money(total)} لا غير` : '',
    RECOMMENDATION: cleanText(settings.recommendation || payload.recommendation || settings.recommendations || payload.recommendations || ''),
    WARRANTY: cleanText(settings.warranty || payload.warranty || ''),
    TECHNICIAN: cleanText(settings.technician || payload.technician || payload.technicianName || ''),
    SEAL_CODE: cleanText(settings.seal_code || settings.sealCode || ''),
    DOCUMENT_TITLE: cleanText(settings.document_title || titleAr),
    DOCUMENT_TITLE_EN: titleEn,
    TAX_ROW: taxAmount ? `<div><span>الضريبة</span><b>${money(taxAmount)}</b></div>` : '',
    BARCODE_VALUE: documentNumber,
    CUSTOMER_APPROVAL_STAMP: approvalStamp(approvals.customer, 'اعتماد العميل'),
    WORKSHOP_APPROVAL_STAMP: approvalStamp(approvals.workshop, 'اعتماد الورشة'),
  };
  let html = String(templateHtml || '');
  Object.entries(values).forEach(([key, value]) => {
    html = replaceToken(html, key, value);
  });
  return html.replace(/>\s*(undefined|null|NaN)\s*</gi, '><');
};

export const splitTemplateHtml = (html = '') => {
  const documentNode = new DOMParser().parseFromString(html, 'text/html');
  return { body: documentNode.body?.innerHTML || html, styles: Array.from(documentNode.head?.querySelectorAll('style') || []).map((node) => node.textContent).join('\n') };
};