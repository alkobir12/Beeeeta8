const escapeHtml = (value) => String(value ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

const money = (value) => `${Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ر.س`;

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

export const renderDocumentTemplate = (templateHtml, payload = {}, workshop = {}) => {
  const settings = payload.settings || {};
  const customer = payload.customer || payload.client || {};
  const vehicle = payload.vehicle || {};
  const rows = Array.isArray(payload.items) ? payload.items : [];
  const normalized = rows.map((item) => {
    const quantity = Number(item.quantity || item.qty || 1);
    const price = Number(item.unit_price || item.price || item.amount || 0);
    const discount = Number(item.discount || 0);
    return { description: item.description || item.name || 'بند', quantity, price, discount, total: Number(item.total || (quantity * price) - discount) };
  });
  const subtotal = normalized.reduce((sum, item) => sum + (item.quantity * item.price), 0);
  const discount = normalized.reduce((sum, item) => sum + item.discount, 0);
  const total = normalized.reduce((sum, item) => sum + item.total, 0);
  const paid = Number(settings?.totals?.paid || payload?.payment?.paid || 0);
  const documentNumber = settings.document_number || payload.document_number || '—';
  const approvalStamp = (approval, label) => approval?.name && approval?.at ? `<div class="approved-stamp" style="border:2px solid #15803d;color:#15803d;border-radius:50%;width:92px;height:92px;display:grid;place-items:center;text-align:center;font-weight:900;font-size:11px;line-height:1.3;margin-top:8px">تمت الموافقة<br><small>${escapeHtml(label)}</small><small>${escapeHtml(approval.name)}</small><small>${escapeHtml(new Date(approval.at).toLocaleDateString('ar-SA'))}</small><small>${escapeHtml(String(approval.id || '').slice(0, 12))}</small></div>` : '';
  const approvals = payload.approvals || {};
  const values = {
    WORKSHOP_NAME: workshop.name || workshop.business_name || '', WORKSHOP_ADDRESS: workshop.address || '—', WORKSHOP_PHONE: workshop.phone || workshop.whatsapp || '—', WORKSHOP_EMAIL: workshop.email || '—', COMPANY_CR: workshop.commercial_register || workshop.commercialRegister || '—', COMPANY_TAX: workshop.tax_number || workshop.taxNumber || '—',
    CUSTOMER_NAME: customer.name || customer.customerName || '', CUSTOMER_PHONE: customer.phone || customer.customerPhone || '—', VEHICLE_INFO: `${vehicle.brand || ''} ${vehicle.model || ''} ${vehicle.year || ''}`.trim() || '—', PLATE_NO: vehicle.plateNumber || vehicle.plate || '—', STATUS_LABEL: settings.status || 'مسودة', INVOICE_NO: documentNumber, DATE: settings.date || payload.date || new Date().toISOString().slice(0, 10),
    ITEMS_ROWS: normalized.length ? normalized.map((item, index) => `<tr><td>${index + 1}</td><td class="desc">${escapeHtml(item.description)}</td><td>${escapeHtml(item.quantity)}</td><td>${money(item.price)}</td><td>${item.discount ? money(item.discount) : '—'}</td><td><b>${money(item.total)}</b></td></tr>`).join('') : '<tr><td colspan="6">لا توجد بنود</td></tr>',
    SUBTOTAL: money(subtotal), DISCOUNT: money(discount), TAX: money(0), TOTAL: money(total), PAID: money(paid), REMAINING: money(total - paid), NOTES: settings.notes || payload.notes || '—', AMOUNT_WORDS: `فقط ${money(total)} لا غير`, SEAL_CODE: settings.seal_code || '—', CUSTOMER_APPROVAL_STAMP: approvalStamp(approvals.customer, 'اعتماد العميل'), WORKSHOP_APPROVAL_STAMP: approvalStamp(approvals.workshop, 'اعتماد الورشة'),
  };
  let html = String(templateHtml || '');
  Object.entries(values).forEach(([key, value]) => {
    if ((key === 'WORKSHOP_NAME' || key === 'CUSTOMER_NAME') && !String(value).trim()) return;
    html = html.replaceAll(`<!--{{${key}}}-->`, String(value));
    html = html.replaceAll(`{{${key}}}`, String(value));
    html = html.replaceAll(`[[${key}]]`, String(value));
    html = html.replaceAll(`<%=${key}%>`, String(value));
    html = html.replaceAll(`<%= ${key} %>`, String(value));
    html = html.replaceAll(`{${key}}`, String(value));
  });
  return html;
};

export const splitTemplateHtml = (html = '') => {
  const documentNode = new DOMParser().parseFromString(html, 'text/html');
  return { body: documentNode.body?.innerHTML || html, styles: Array.from(documentNode.head?.querySelectorAll('style') || []).map((node) => node.textContent).join('\n') };
};