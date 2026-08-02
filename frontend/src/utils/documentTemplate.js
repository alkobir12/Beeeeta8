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

const amount = (value) => safeNumber(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const unique = (values) => [...new Set(values.map((value) => String(value).trim()).filter(Boolean))];

export const findUnresolvedTemplateVariables = (html = '') => {
  const source = String(html || '');
  const matches = [
    ...source.matchAll(/{{\s*([^{}]+?)\s*}}/g),
    ...source.matchAll(/\[\[\s*([^\]]+?)\s*\]\]/g),
    ...source.matchAll(/<%=?\s*([\s\S]*?)\s*%>/g),
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
  return cleanText(item.kindLabel || item.category || 'أجرة');
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
      total,
    };
  });

const isUuidLike = (value = '') => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || '').trim());
const humanId = (value) => {
  const text = cleanText(value);
  if (!text || isUuidLike(text)) return '—';
  return text;
};

const docTitle = (docType) => ({
  invoice: ['فاتورة مبيعات', 'SALES INVOICE'],
  diagnosis: ['تقرير تشخيص', 'DIAGNOSTIC REPORT'],
  quote: ['عرض سعر', 'QUOTATION'],
  receipt: ['سند زيارة', 'VISIT RECEIPT'],
}[docType] || ['مستند', 'DOCUMENT']);

const paymentLabel = (method = '', total = 0, paid = 0) => {
  const key = String(method || '').trim().toLowerCase();
  const mapped = {
    cash: 'نقد',
    pos: 'نقاط بيع',
    bank: 'تحويل بنكي',
    bank_transfer: 'تحويل بنكي',
    transfer: 'تحويل بنكي',
    credit: 'آجل — غير مسدد',
    deferred: 'آجل — غير مسدد',
    ajel: 'آجل — غير مسدد',
    'آجل': 'آجل — غير مسدد',
  }[key];
  if (mapped) return mapped;
  if (!key && safeNumber(total) > safeNumber(paid)) return 'آجل — غير مسدد';
  return cleanText(method);
};

const splitPlate = (plate = '') => {
  const text = cleanText(plate);
  const digits = (text.match(/[0-9٠-٩]+/g) || []).join(' ');
  const letters = text.replace(/[0-9٠-٩\s/\-_.]+/g, ' ').trim();
  return { digits, lettersAr: letters, lettersEn: '', digitsEn: digits };
};

const parseDtc = (value) => {
  if (Array.isArray(value)) return value.map(cleanText).filter(Boolean);
  return String(value || '').split(/[،,\s]+/).map(cleanText).filter(Boolean);
};

const setText = (root, field, value) => {
  root.querySelectorAll(`[data-field="${field}"]`).forEach((node) => {
    node.textContent = cleanText(value);
    node.removeAttribute('data-placeholder');
  });
};

const setHtml = (root, field, html) => {
  root.querySelectorAll(`[data-field="${field}"]`).forEach((node) => {
    node.innerHTML = html || '';
    node.removeAttribute('data-placeholder');
  });
};

const fillRowField = (row, field, value) => {
  row.querySelectorAll(`[data-field="${field}"]`).forEach((node) => { node.textContent = cleanText(value); });
};

export const renderDocumentTemplate = (templateHtml, payload = {}, workshop = {}) => {
  const parser = new DOMParser();
  const doc = parser.parseFromString(String(templateHtml || ''), 'text/html');
  const settings = payload.settings || {};
  const customer = payload.customer || payload.client || {};
  const vehicle = payload.vehicle || {};
  const rows = normalizeRows(payload.items || []);
  const partsTotal = rows.filter((item) => item.kind === 'قطعة').reduce((sum, item) => sum + item.total, 0);
  const laborTotal = rows.filter((item) => item.kind !== 'قطعة').reduce((sum, item) => sum + item.total, 0);
  const total = rows.reduce((sum, item) => sum + item.total, 0) + safeNumber(settings?.totals?.tax || payload.tax || 0);
  const paid = safeNumber(settings?.totals?.paid || payload?.payment?.paid || 0);
  const docType = payload.doc_type || payload.docType || settings.doc_type || 'invoice';
  const [titleAr, titleEn] = docTitle(docType);
  const plateRaw = cleanText(vehicle.plateNumber || vehicle.plate || '');
  const plate = splitPlate(plateRaw);
  const vehicleName = cleanText(`${vehicle.brand || vehicle.vehicleBrand || ''} ${vehicle.model || vehicle.vehicleModel || ''}`);
  const documentNumber = humanId(settings.document_number || payload.document_number || payload.invoiceNumber || payload.invoice_number);
  const jobOrder = humanId(settings.job_order || settings.jobOrder || payload.job_order || payload.jobOrder || payload.workOrderNumber || payload.work_order_number);

  const values = {
    'ws-name': cleanText(workshop.name || workshop.business_name || ''),
    'ws-tagline': cleanText(workshop.slogan || workshop.tagline || workshop.sloganEnglish || ''),
    'doc-kind': cleanText(settings.document_title || titleAr),
    'doc-kind-en': titleEn,
    'ws-cr': cleanText(workshop.commercial_register || workshop.commercialRegister || ''),
    'ws-phone': cleanText(workshop.phone || workshop.whatsapp || ''),
    'ws-address': cleanText(workshop.address || ''),
    'doc-no': documentNumber,
    'job-order': jobOrder,
    'date-in': cleanText(settings.entry_date || settings.entryDate || settings.date || payload.entry_date || payload.entryDate || payload.date || ''),
    'date-out': cleanText(settings.delivery_date || settings.deliveryDate || payload.delivery_date || payload.deliveryDate || ''),
    'payment-method': paymentLabel(settings.payment_method || settings.paymentMethod || payload?.payment?.method || '', total, paid),
    'customer-name': cleanText(customer.name || customer.customerName || ''),
    'customer-phone': cleanText(customer.phone || customer.customerPhone || ''),
    odometer: cleanText(vehicle.mileage || vehicle.odometer || settings.mileage || ''),
    'vehicle-model': vehicleName,
    'vehicle-year': cleanText(vehicle.year || vehicle.vehicleYear || ''),
    'vehicle-vin': cleanText(vehicle.vin || vehicle.chassisNumber || ''),
    'plate-letters-ar': plate.lettersAr,
    'plate-letters-en': plate.lettersEn,
    'plate-digits-ar': plate.digits,
    'plate-digits-en': plate.digitsEn,
    complaint: cleanText(settings.complaint || payload.complaint || vehicle.complaint || ''),
    inspection: cleanText(settings.inspection || settings.diagnosis || payload.inspection || payload.diagnosis || ''),
    'parts-total': amount(partsTotal),
    'labor-total': amount(laborTotal),
    'item-count': String(rows.length),
    'total-sar': amount(total),
    'total-words': total > 0 ? `فقط ${amount(total)} ريال سعودي لا غير` : '',
    recommendation: cleanText(settings.recommendation || payload.recommendation || settings.recommendations || payload.recommendations || ''),
    warranty: cleanText(settings.warranty || payload.warranty || ''),
    technician: cleanText(settings.technician || payload.technician || payload.technicianName || ''),
  };

  Object.entries(values).forEach(([field, value]) => setText(doc, field, value));
  const dtcCodes = parseDtc(settings.dtc || settings.dtc_codes || payload.dtc || payload.dtc_codes || vehicle.dtc || '');
  setHtml(doc, 'dtc-list', dtcCodes.map((code) => `<span class="dtc">${escapeHtml(code)}</span>`).join(''));

  const template = doc.getElementById('row-template');
  const body = doc.getElementById('items-body');
  if (template && body) {
    body.innerHTML = '';
    rows.forEach((item, index) => {
      const row = template.content?.firstElementChild?.cloneNode(true) || doc.createElement('tr');
      fillRowField(row, 'row-no', String(index + 1));
      fillRowField(row, 'row-kind', item.kind);
      fillRowField(row, 'row-code', item.code);
      fillRowField(row, 'row-desc', item.description);
      fillRowField(row, 'row-qty', String(item.quantity));
      fillRowField(row, 'row-unit', amount(item.price));
      fillRowField(row, 'row-sum', amount(item.total));
      body.appendChild(row);
    });
  }

  doc.querySelectorAll('[data-placeholder]').forEach((node) => node.removeAttribute('data-placeholder'));
  doc.querySelectorAll('button.pbtn, script').forEach((node) => node.remove());
  return `<!doctype html>${doc.documentElement.outerHTML}`.replace(/>\s*(undefined|null|NaN)\s*</gi, '><');
};

export const splitTemplateHtml = (html = '') => {
  const documentNode = new DOMParser().parseFromString(html, 'text/html');
  return { body: documentNode.body?.innerHTML || html, styles: Array.from(documentNode.head?.querySelectorAll('style, link[rel="stylesheet"]') || []).map((node) => node.outerHTML || node.textContent).join('\n') };
};