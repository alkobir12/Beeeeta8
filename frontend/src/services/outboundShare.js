import { api } from './api';

const AR_DIGITS = { '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9' };

export const normalizePhoneLocal = (raw) => {
  const text = String(raw || '').replace(/[٠-٩]/g, (d) => AR_DIGITS[d] || d).trim();
  const digits = text.replace(/\D/g, '');
  let e164 = null;
  if (digits.startsWith('00966') && digits.length === 14) e164 = `+${digits.slice(2)}`;
  else if (digits.startsWith('966') && digits.length === 12) e164 = `+${digits}`;
  else if (digits.startsWith('05') && digits.length === 10) e164 = `+966${digits.slice(1)}`;
  else if (digits.startsWith('5') && digits.length === 9) e164 = `+966${digits}`;
  else if (text.startsWith('+') && digits.length >= 10 && digits.length <= 15) e164 = `+${digits}`;
  return { raw: String(raw || ''), e164, wa: e164 ? e164.slice(1) : null, valid: Boolean(e164) };
};

export const computeSealCode = (number, date) => {
  const seed = `${number || 'DOC'}-${date || new Date().toISOString().slice(0, 10)}`;
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = ((hash << 5) - hash) + seed.charCodeAt(i);
  return `ES-${Math.abs(hash).toString(16).slice(0, 8).toUpperCase()}`;
};

const pick = (obj = {}, keys = []) => keys.reduce((acc, key) => {
  if (obj?.[key] !== undefined && obj?.[key] !== null && obj?.[key] !== '') acc[key] = obj[key];
  return acc;
}, {});

const normalizeLineItems = (items = []) => (Array.isArray(items) ? items : [])
  .filter((item) => item && (item.description || item.name || Number(item.unit_price || item.price || 0) > 0))
  .map((item) => ({
    description: item.description || item.name || item.itemName || 'بند',
    quantity: Number(item.quantity || item.qty || 1),
    unit_price: Number(item.unit_price || item.price || item.amount || 0),
    discount: Number(item.discount || 0),
    vat_rate: Number(item.vatRate || item.tax_rate || item.vat || 0),
  }));

export const buildShareMaterial = ({ docType, payload = {}, workshop = {}, templateId, templateVersion, tenantId = 'default' }) => {
  const settings = payload.settings || {};
  const lineItems = normalizeLineItems(payload.items);
  let subtotal = 0; let discount = 0; let tax = 0; let total = 0;
  lineItems.forEach((item) => {
    const lineSub = item.quantity * item.unit_price;
    const after = Math.max(lineSub - item.discount, 0);
    const lineTax = Math.round(after * item.vat_rate) / 100;
    subtotal += lineSub; discount += item.discount; tax += lineTax; total += after + lineTax;
  });
  const paid = Number(settings?.totals?.paid || payload?.payment?.paid || 0);
  return {
    tenant_id: tenantId,
    document_id: payload.document_id || settings.document_id || null,
    document_number: settings.document_number || payload.document_number || '',
    document_version: settings.document_version || payload.document_version || 1,
    doc_type: docType,
    status: settings.status || payload.status || 'draft',
    locale: 'ar',
    template_id: templateId || 'unified-generator',
    template_version: templateVersion || 'v1',
    workshop_snapshot: pick(workshop, ['name', 'phone', 'address', 'email', 'tax_number', 'commercial_register']),
    customer_snapshot: pick(payload.customer || payload.client || {}, ['id', 'name', 'phone', 'email', 'address']),
    vehicle_snapshot: pick(payload.vehicle || {}, ['id', 'brand', 'model', 'year', 'plateNumber', 'plate', 'vin']),
    line_items: lineItems,
    totals: { subtotal, discount, total, paid, remaining: total - paid },
    taxes: { tax },
  };
};

export const getFingerprint = (material) => api.post('/outbound/fingerprint', { material }).then((r) => r.data);
export const uploadOutputAsset = (body) => api.post('/outbound/assets', body).then((r) => r.data);
export const getOutputAsset = (fingerprint, tenantId = 'default') =>
  api.get(`/outbound/assets/${fingerprint}`, { params: { tenant_id: tenantId } }).then((r) => r.data);
export const resolveOutboundMessage = (body) => api.post('/outbound/resolve-message', body).then((r) => r.data);
export const createShareAttempt = (body) => api.post('/outbound/share-attempts', body).then((r) => r.data);
export const logShareEvent = (attemptId, event, meta = {}) =>
  api.post(`/outbound/share-attempts/${attemptId}/events`, { event, meta }).then((r) => r.data).catch(() => null);
export const listOutboundTemplates = (params = {}) => api.get('/outbound/templates', { params }).then((r) => r.data);
export const updateOutboundTemplate = (id, body) => api.put(`/outbound/templates/${id}`, body).then((r) => r.data);
export const restoreOutboundTemplate = (id) => api.post(`/outbound/templates/${id}/restore-default`).then((r) => r.data);
export const listOutboundVariables = () => api.get('/outbound/variables').then((r) => r.data);
export const saveCustomerPhone = (customerId, phone) => api.put(`/customers/${customerId}`, { phone }).then((r) => r.data);

export const base64ToBlob = (base64, mime) => {
  const bytes = atob(base64);
  const buffer = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i += 1) buffer[i] = bytes.charCodeAt(i);
  return new Blob([buffer], { type: mime });
};

export const downloadBlob = (blob, fileName) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
};
