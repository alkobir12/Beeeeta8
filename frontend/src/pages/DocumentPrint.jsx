import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Download, Eye, FileText, Maximize2, Minus, Plus, Printer, RefreshCw, Share2, Settings, ShieldCheck, X } from 'lucide-react';
import { api } from '../services/api';
import { downloadPDF } from '../utils/pdfGenerator';
import { getWhatsAppLink } from '../utils/constants';
import { loadWorkshopPrintInfo } from '../utils/workshopPrintInfo';

const SAR = (value) => `${Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ر.س`;
const today = () => new Date().toISOString().slice(0, 10);
const docLabels = { invoice: 'فاتورة إصلاح مركبة', diagnosis: 'تقرير تشخيص', quote: 'عرض سعر', receipt: 'طباعة زيارة' };

const emptyItem = { description: '', quantity: 1, unit_price: 0, discount: 0, vatRate: 0, type: 'service' };

const normalizeItem = (item = {}) => {
  const quantity = Number(item.quantity || item.qty || 1);
  const unit = Number(item.unit_price || item.price || item.amount || 0);
  const discount = Number(item.discount || 0);
  return {
    description: item.description || item.name || item.serviceName || 'بند',
    quantity,
    unit_price: unit,
    discount,
    vatRate: Number(item.vatRate || item.tax_rate || 0),
    type: item.type || item.itemType || 'service',
  };
};

const getResponseRows = (data, keys = []) => {
  if (Array.isArray(data)) return data;
  for (const key of keys) if (Array.isArray(data?.[key])) return data[key];
  return [];
};

export default function DocumentPrint() {
  const [searchParams] = useSearchParams();
  const vehicleId = searchParams.get('vehicleId');
  const visitId = searchParams.get('visitId');
  const operationId = searchParams.get('operationId');
  const invoiceId = searchParams.get('invoiceId');
  const autoPrint = searchParams.get('autoPrint') === '1';
  const autoWhatsApp = searchParams.get('autoWhatsApp') === '1';
  const previewRef = useRef(null);
  const autoActionRef = useRef(false);

  const [zoom, setZoom] = useState(0.72);
  const [modePreview, setModePreview] = useState(true);
  const [loading, setLoading] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [saveState, setSaveState] = useState('جاهز');
  const [docType, setDocType] = useState(searchParams.get('type') || 'invoice');
  const [formData, setFormData] = useState({
    workshop: { name: '', name_en: '', phone: '', email: '', address: '', tax_number: '', commercial_register: '', website: '', logo: '', tagline: 'ميكانيكا عامة — كهرباء — سمكرة ودهان — فحص كمبيوتر' },
    customer: { name: '', phone: '', email: '', address: '', taxNo: '' },
    vehicle: { brand: '', model: '', year: '', plateNumber: '', vin: '', color: '', mileage: '', notes: '' },
    items: [emptyItem],
    settings: { document_number: `INV-${new Date().toISOString().slice(2,10).replace(/-/g,'')}-${Math.floor(100 + Math.random() * 900)}`, date: today(), receivedTime: '09:00', status: 'draft', notes: '', warranty: 'ضمان الإصلاح 30 يوماً أو 1,000 كم من تاريخ التسليم، ولا يشمل سوء الاستخدام.', approval_token: '' },
    payment: { method: 'cash', paid: 0 },
  });

  const totals = useMemo(() => {
    const rows = (formData.items || []).filter((item) => item.description).map((item) => {
      const subtotal = Number(item.quantity || 0) * Number(item.unit_price || 0);
      const discount = Number(item.discount || 0);
      const afterDiscount = Math.max(subtotal - discount, 0);
      const tax = Math.round(afterDiscount * Number(item.vatRate || 0)) / 100;
      return { ...item, subtotal, discount, tax, total: afterDiscount + tax };
    });
    const subtotal = rows.reduce((sum, item) => sum + item.subtotal, 0);
    const discount = rows.reduce((sum, item) => sum + item.discount, 0);
    const tax = rows.reduce((sum, item) => sum + item.tax, 0);
    const total = rows.reduce((sum, item) => sum + item.total, 0);
    const paid = Number(formData.payment?.paid || 0);
    return { rows, subtotal, discount, tax, total, paid, remain: total - paid };
  }, [formData.items, formData.payment?.paid]);

  const patchForm = useCallback((patch) => setFormData((prev) => ({ ...prev, ...patch })), []);
  const patchNested = useCallback((section, key, value) => setFormData((prev) => ({ ...prev, [section]: { ...prev[section], [key]: value } })), []);

  const loadWorkshop = useCallback(async () => {
    const ws = await loadWorkshopPrintInfo(async (path) => {
      const response = await api.get(path);
      return { ok: true, json: async () => response.data };
    });
    patchForm({ workshop: { ...formData.workshop, ...ws, tagline: ws.slogan || ws.tagline || formData.workshop.tagline } });
  }, [formData.workshop, patchForm]);

  const loadCustomer = useCallback(async (customerId) => {
    if (!customerId) return;
    try {
      const response = await api.get('/customers');
      const rows = getResponseRows(response.data, ['customers', 'data']);
      const match = rows.find((c) => c.id === customerId || c.customerId === customerId);
      if (match) patchForm({ customer: { name: match.name || '', phone: match.phone || '', email: match.email || '', address: match.address || match.company || '', taxNo: match.taxNo || match.tax_number || '' } });
    } catch (_) {}
  }, [patchForm]);

  const loadVehicle = useCallback(async (id, preserveItems = false) => {
    if (!id) return;
    try {
      const { data } = await api.get(`/vehicles/${id}`);
      if (!data) return;
      patchForm({
        customer: { ...formData.customer, name: data.customerName || data.customer_name || formData.customer.name, phone: data.customerPhone || data.customer_phone || formData.customer.phone },
        vehicle: { brand: data.brand || data.vehicleBrand || '', model: data.model || data.vehicleModel || '', year: data.year || data.vehicleYear || '', plateNumber: data.plateNumber || data.plate || '', vin: data.vin || data.chassisNumber || '', color: data.color || '', mileage: data.mileage || '', notes: data.notes || '' },
        items: preserveItems ? formData.items : (Array.isArray(data.parts) && data.parts.length ? data.parts.map(normalizeItem) : formData.items),
      });
      if (data.customerId || data.customer_id) loadCustomer(data.customerId || data.customer_id);
    } catch (_) {}
  }, [formData.customer, formData.items, loadCustomer, patchForm]);

  const loadVisit = useCallback(async () => {
    if (!visitId) return;
    try {
      const opsResponse = await api.get(`/visits/${visitId}/operations`).catch(() => ({ data: [] }));
      const ops = getResponseRows(opsResponse.data, ['operations', 'data']);
      if (ops.length) {
        const op = ops[0];
        const items = typeof op.items === 'string' ? JSON.parse(op.items || '[]') : (op.items || []);
        patchForm({
          items: items.length ? items.map(normalizeItem) : [normalizeItem({ description: op.description || op.notes || 'زيارة ورشة', price: op.total || 0 })],
          customer: { ...formData.customer, name: op.customerName || op.customer_name || op.partnerName || formData.customer.name, phone: op.customerPhone || op.customer_phone || formData.customer.phone },
          settings: { ...formData.settings, document_number: op.invoiceNumber || op.invoice_number || formData.settings.document_number, date: String(op.date || op.createdAt || today()).slice(0, 10), notes: op.notes || formData.settings.notes },
        });
        return;
      }
      if (!vehicleId) return;
      const visitsResponse = await api.get(`/vehicles/${vehicleId}/visits`).catch(() => ({ data: [] }));
      const visits = getResponseRows(visitsResponse.data, ['visits', 'data']);
      const visit = visits.find((v) => v.id === visitId || v.visitId === visitId);
      if (!visit) return;
      let parsed = [];
      if (String(visit.notes || '').trim().startsWith('{')) {
        try { parsed = JSON.parse(visit.notes).items || []; } catch (_) { parsed = []; }
      }
      patchForm({
        items: parsed.length ? parsed.map(normalizeItem) : [normalizeItem({ description: docType === 'diagnosis' ? 'تقرير تشخيص' : 'زيارة ورشة', price: visit.total_workshop || visit.total || 0 })],
        settings: { ...formData.settings, document_number: visit.invoiceNumber || visit.id || formData.settings.document_number, date: String(visit.created_at || visit.createdAt || today()).slice(0, 10), notes: typeof visit.notes === 'string' && !visit.notes.trim().startsWith('{') ? visit.notes : formData.settings.notes },
      });
    } catch (_) {}
  }, [docType, formData.customer, formData.settings, patchForm, vehicleId, visitId]);

  const loadOperation = useCallback(async (id) => {
    if (!id) return;
    try {
      const { data: op } = await api.get(`/operations/${id}`);
      if (!op) return;
      const opItems = typeof op.items === 'string' ? JSON.parse(op.items || '[]') : (op.items || []);
      patchForm({
        items: opItems.length ? opItems.map(normalizeItem) : [normalizeItem({ description: op.description || op.notes || 'عملية', price: op.total || op.amount || 0 })],
        customer: { ...formData.customer, name: op.customerName || op.customer_name || op.partnerName || formData.customer.name, phone: op.customerPhone || op.customer_phone || formData.customer.phone },
        settings: { ...formData.settings, document_number: op.invoiceNumber || op.invoice_number || `OP-${op.id || ''}`, date: String(op.date || op.createdAt || today()).slice(0, 10), notes: op.notes || formData.settings.notes },
      });
      if (op.vehicleId || op.vehicle_id) loadVehicle(op.vehicleId || op.vehicle_id, true);
    } catch (_) {}
  }, [formData.customer, formData.settings, loadVehicle, patchForm]);

  const loadInvoice = useCallback(async (id) => {
    if (!id) return;
    try {
      const { data } = await api.get(`/invoices/${id}`);
      if (!data) return;
      const items = typeof data.items === 'string' ? JSON.parse(data.items || '[]') : (data.items || []);
      patchForm({
        items: items.length ? items.map(normalizeItem) : formData.items,
        customer: { ...formData.customer, name: data.partner_name || data.partnerName || formData.customer.name },
        settings: { ...formData.settings, document_number: data.invoice_number || data.invoiceNumber || formData.settings.document_number, date: String(data.created_at || data.createdAt || today()).slice(0, 10), notes: data.notes || formData.settings.notes },
      });
      if (data.vehicleId || data.vehicle_id) loadVehicle(data.vehicleId || data.vehicle_id, true);
    } catch (_) {}
  }, [formData.customer, formData.items, formData.settings, loadVehicle, patchForm]);

  const refreshData = useCallback(async () => {
    setLoading(true);
    setSaveState('تحديث البيانات...');
    try {
      await loadWorkshop();
      if (vehicleId) await loadVehicle(vehicleId, Boolean(visitId || operationId || invoiceId));
      if (visitId) await loadVisit();
      if (operationId) await loadOperation(operationId);
      if (invoiceId) await loadInvoice(invoiceId);
      setSaveState('محفوظ');
    } finally {
      setLoading(false);
      setTimeout(() => setSaveState('جاهز'), 1200);
    }
  }, [invoiceId, loadInvoice, loadOperation, loadVehicle, loadVisit, loadWorkshop, operationId, vehicleId, visitId]);

  useEffect(() => { refreshData(); }, []);

  const numberToWords = (value) => value <= 0 ? 'فقط صفر ريال لا غير' : `فقط ${SAR(value)} لا غير`;
  const statusClass = formData.settings.status === 'paid' ? 'st-paid' : formData.settings.status === 'partial' ? 'st-partial' : formData.settings.status === 'deferred' ? 'st-deferred' : formData.settings.status === 'unpaid' ? 'st-unpaid' : 'st-draft';

  const buildSheetHtml = useCallback(() => {
    const w = formData.workshop;
    const c = formData.customer;
    const v = formData.vehicle;
    const title = formData.settings.document_title || docLabels[docType] || 'فاتورة إصلاح مركبة';
    return `<div class="doc-sheet" dir="rtl">
      <div class="p-top"></div>
      <header class="p-head">
        <aside class="p-meta">
          <span class="p-doctype">${title}</span>
          <div class="p-mrow"><span>رقم المستند</span><b>${formData.settings.document_number || '—'}</b></div>
          <div class="p-mrow"><span>تاريخ الإصدار</span><b>${formData.settings.date || today()}</b></div>
          <div class="p-mrow"><span>وقت الاستلام</span><b>${formData.settings.receivedTime || '09:00'}</b></div>
          <div class="p-mrow"><span>الحالة</span><b><span class="pill ${statusClass}">${formData.settings.status === 'paid' ? 'مدفوعة' : formData.settings.status === 'deferred' ? 'آجلة' : formData.settings.status === 'partial' ? 'مدفوعة جزئياً' : formData.settings.status === 'unpaid' ? 'غير مدفوعة' : 'مسودة'}</span></b></div>
          <div class="p-chip">الإجمالي المستحق<b>${SAR(totals.total)}</b></div>
        </aside>
        <section class="p-brand">
          <div class="p-logo">✺</div>
          <h1>${w.name || 'ورشة النخبة لصيانة السيارات'}</h1>
          <div class="p-tag">${w.tagline || w.slogan || 'ميكانيكا عامة — كهرباء — فحص كمبيوتر'}</div>
          <div class="p-contact">${w.phone || ''} • ${w.email || ''} • ${w.address || ''}</div>
          <div class="p-contact">الرقم الضريبي: ${w.tax_number || w.taxNumber || ''} • س.ت: ${w.commercial_register || w.commercialRegister || ''} • ${w.website || ''}</div>
        </section>
      </header>
      <section class="p-parties">
        <div class="p-box"><h3>بيانات المركبة</h3>${row('الماركة', v.brand)}${row('الموديل', v.model)}${row('سنة الصنع', v.year)}${row('اللوحة', v.plateNumber || v.plate)}${row('VIN', v.vin)}${row('العداد', v.mileage)}</div>
        <div class="p-box"><h3>بيانات العميل</h3>${row('الاسم', c.name || 'عميل نقدي')}${row('الجوال', c.phone)}${row('البريد', c.email)}${row('العنوان', c.address)}${row('الرقم الضريبي', c.taxNo)}</div>
      </section>
      <table class="p-table"><thead><tr><th>#</th><th>البيان</th><th>الكمية</th><th>السعر</th><th>الخصم</th><th>الضريبة</th><th>الإجمالي</th></tr></thead><tbody>${totals.rows.length ? totals.rows.map((item, idx) => `<tr><td class="n">${idx + 1}</td><td>${item.description}</td><td class="n">${item.quantity}</td><td class="n">${SAR(item.unit_price)}</td><td class="n">${item.discount ? SAR(item.discount) : '—'}</td><td class="n">${item.tax ? SAR(item.tax) : '—'}</td><td class="n"><b>${SAR(item.total)}</b></td></tr>`).join('') : '<tr><td colspan="7" class="empty-row">لا توجد بنود</td></tr>'}</tbody></table>
      <section class="p-after"><div class="p-notes"><h4>شروط الضمان</h4><p>${formData.settings.warranty || 'ضمان الإصلاح 30 يوماً أو 1,000 كم من تاريخ التسليم، ولا يشمل سوء الاستخدام.'}</p>${formData.settings.notes ? `<h4>ملاحظات</h4><p>${formData.settings.notes}</p>` : ''}</div><div class="p-totals"><div class="p-trow"><span>المجموع قبل الخصم</span><b>${SAR(totals.subtotal)}</b></div><div class="p-trow"><span>إجمالي الخصومات</span><b>− ${SAR(totals.discount)}</b></div><div class="p-trow"><span>الضريبة</span><b>${SAR(totals.tax)}</b></div><div class="p-trow grand"><span>الإجمالي النهائي</span><b>${SAR(totals.total)}</b></div><div class="p-trow"><span>المدفوع</span><b>${SAR(totals.paid)}</b></div><div class="p-trow"><span>المتبقي</span><b>${SAR(totals.remain)}</b></div></div></section>
      <div class="p-words"><b>المبلغ كتابةً:</b> ${numberToWords(totals.total)}</div>
      <section class="p-signs"><div class="p-sig"><h4>توقيع الورشة</h4><div class="p-sigbox"></div><div class="p-auth">عند الموافقة، الورشة مخولة لتبديل وشراء كل ما يتطلب للصيانة.</div></div><div class="p-sig"><h4>توقيع العميل</h4><div class="p-sigbox"></div></div></section>
      <footer class="p-foot"><span>${w.website || ''} • ${w.phone || ''}</span><span class="mid">شكراً لثقتكم — سلامتكم أولويتنا</span><span>${formData.settings.document_number || ''}</span></footer>
    </div>`;
  }, [docType, formData, totals, statusClass]);

  const row = (label, value) => value ? `<div class="row"><span>${label}</span><b>${value}</b></div>` : '';

  const downloadCurrentPdf = async () => {
    if (!previewRef.current) return;
    setPdfBusy(true);
    try {
      await downloadPDF(previewRef.current, `${docType}_${formData.settings.document_number || 'document'}.pdf`, { scale: 2, backgroundColor: '#ffffff' });
    } finally {
      setPdfBusy(false);
    }
  };

  const printCurrent = () => window.print();

  const sendWhatsApp = async () => {
    const phone = formData.customer.phone;
    if (!phone) {
      alert('أضف رقم جوال العميل أولاً');
      return;
    }
    await downloadCurrentPdf();
    const message = `تم تجهيز المستند ${formData.settings.document_number || ''}\nالعميل: ${formData.customer.name || ''}\nالإجمالي: ${SAR(totals.total)}\nيرجى إرفاق ملف PDF الذي تم تحميله.`;
    window.open(getWhatsAppLink(phone, message), '_blank');
  };

  useEffect(() => {
    if ((!autoPrint && !autoWhatsApp) || autoActionRef.current) return;
    autoActionRef.current = true;
    setTimeout(() => { autoPrint ? printCurrent() : sendWhatsApp(); }, 900);
  }, [autoPrint, autoWhatsApp]);

  const updateItem = (index, key, value) => setFormData((prev) => ({ ...prev, items: prev.items.map((item, i) => i === index ? { ...item, [key]: key === 'description' ? value : Number(value || 0) } : item) }));

  return <div className="doc-page" dir="rtl">
    <style>{styles}</style>
    <header className="doc-topbar">
      <div className="brand"><FileText size={22}/> فاتورة الورشة</div>
      <div className={`save-pill ${loading ? 'saving' : 'ok'}`}><span className="dot"/><span>{saveState}</span></div>
      <div className="top-actions">
        <button className="icon-btn" onClick={refreshData} title="تحديث" data-testid="document-refresh-button"><RefreshCw size={20}/></button>
        <button className="icon-btn" onClick={() => setModePreview((v) => !v)} title="معاينة" data-testid="document-toggle-preview-button"><Eye size={20}/></button>
      </div>
    </header>
    <main className="doc-app">
      <section className="editor">
        <section className="sec"><h2><span className="chip">1</span> نوع المستند</h2><div className="doc-type-grid">{Object.entries(docLabels).map(([key, label]) => <button key={key} className={`doc-type ${docType === key ? 'active' : ''}`} onClick={() => setDocType(key)} data-testid={`document-type-${key}`}>{label}</button>)}</div></section>
        <section className="sec"><h2><span className="chip">2</span> بيانات الفاتورة</h2><div className="grid2"><Field label="رقم المستند" value={formData.settings.document_number} onChange={(v) => patchNested('settings','document_number',v)}/><Field label="التاريخ" type="date" value={formData.settings.date} onChange={(v) => patchNested('settings','date',v)}/><Field label="وقت الاستلام" type="time" value={formData.settings.receivedTime} onChange={(v) => patchNested('settings','receivedTime',v)}/><SelectField label="الحالة" value={formData.settings.status} onChange={(v) => patchNested('settings','status',v)} options={{draft:'مسودة', unpaid:'غير مدفوعة', partial:'مدفوعة جزئياً', paid:'مدفوعة', deferred:'آجلة'}} /></div></section>
        <section className="sec"><h2><span className="chip">3</span> العميل والمركبة</h2><div className="grid2"><Field label="اسم العميل" value={formData.customer.name} onChange={(v) => patchNested('customer','name',v)}/><Field label="جوال العميل" value={formData.customer.phone} onChange={(v) => patchNested('customer','phone',v)}/><Field label="رقم اللوحة" value={formData.vehicle.plateNumber} onChange={(v) => patchNested('vehicle','plateNumber',v)}/><Field label="المركبة" value={`${formData.vehicle.brand || ''} ${formData.vehicle.model || ''}`.trim()} onChange={() => {}} disabled/><Field label="VIN" value={formData.vehicle.vin} onChange={(v) => patchNested('vehicle','vin',v)}/><Field label="العداد" value={formData.vehicle.mileage} onChange={(v) => patchNested('vehicle','mileage',v)}/></div></section>
        <section className="sec"><h2><span className="chip">4</span> البنود</h2><div className="items-list">{formData.items.map((item, index) => <div className="item-card" key={index}><Field label="الوصف" value={item.description} onChange={(v) => updateItem(index,'description',v)}/><Field label="الكمية" type="number" value={item.quantity} onChange={(v) => updateItem(index,'quantity',v)}/><Field label="السعر" type="number" value={item.unit_price} onChange={(v) => updateItem(index,'unit_price',v)}/><Field label="الخصم" type="number" value={item.discount} onChange={(v) => updateItem(index,'discount',v)}/></div>)}</div><button className="btn gold" onClick={() => patchForm({ items: [...formData.items, emptyItem] })} data-testid="document-add-item-button"><Plus size={18}/> إضافة بند</button></section>
        <section className="sec"><h2><span className="chip">5</span> الدفع والملاحظات</h2><div className="grid2"><Field label="المدفوع" type="number" value={formData.payment.paid} onChange={(v) => patchForm({ payment: { ...formData.payment, paid: Number(v || 0) } })}/><Field label="الملاحظات" value={formData.settings.notes} onChange={(v) => patchNested('settings','notes',v)}/></div><div className="summary"><div><span>الإجمالي</span><b>{SAR(totals.total)}</b></div><div><span>المتبقي</span><b>{SAR(totals.remain)}</b></div></div></section>
        <section className="sec"><h2><span className="chip">6</span> إجراءات</h2><div className="btn-row"><button className="btn gold" onClick={printCurrent} data-testid="document-print-button"><Printer size={18}/> طباعة / PDF</button><button className="btn" onClick={downloadCurrentPdf} disabled={pdfBusy} data-testid="document-download-button"><Download size={18}/> تحميل PDF</button><button className="btn" onClick={sendWhatsApp} disabled={pdfBusy} data-testid="document-whatsapp-button"><Share2 size={18}/> واتساب PDF</button><button className="btn" onClick={() => setZoom(0.72)} data-testid="document-fit-button"><Maximize2 size={18}/> ملاءمة</button></div></section>
      </section>
      <section className="preview-panel ${modePreview ? 'show' : ''}" data-testid="document-preview-panel">
        <div className="preview-bar"><button className="icon-btn" onClick={() => setZoom((z) => Math.max(0.35, z - 0.08))}><Minus size={18}/></button><span className="zoom-val">{Math.round(zoom * 100)}%</span><button className="icon-btn" onClick={() => setZoom((z) => Math.min(1.5, z + 0.08))}><Plus size={18}/></button><button className="icon-btn" onClick={printCurrent} data-testid="document-preview-print-button"><Printer size={18}/></button><button className="icon-btn" onClick={downloadCurrentPdf} data-testid="document-preview-download-button"><Download size={18}/></button><button className="icon-btn" onClick={sendWhatsApp} data-testid="document-preview-whatsapp-button"><Share2 size={18}/></button></div>
        <div className="viewport"><div className="sheet-scale" style={{ transform: `scale(${zoom})`, height: `${1123 * zoom}px` }}><article ref={previewRef} className="sheet" data-testid="document-sheet" dangerouslySetInnerHTML={{ __html: buildSheetHtml() }} /></div></div>
      </section>
    </main>
  </div>;
}

function Field({ label, value, onChange, type = 'text', disabled = false }) {
  return <label className="fld"><span>{label}</span><input className="inp" type={type} value={value ?? ''} disabled={disabled} onChange={(e) => onChange(e.target.value)} /></label>;
}

function SelectField({ label, value, onChange, options }) {
  return <label className="fld"><span>{label}</span><select className="inp" value={value} onChange={(e) => onChange(e.target.value)}>{Object.entries(options).map(([k, v]) => <option value={k} key={k}>{v}</option>)}</select></label>;
}

const styles = `
.doc-page{min-height:100vh;background:#101318;color:#eceef1;font-family:Almarai,Tahoma,Arial,sans-serif;direction:rtl}.doc-page:before{content:'';position:fixed;inset:-20%;z-index:0;pointer-events:none;background:radial-gradient(620px 420px at 85% 0%,rgba(247,166,0,.10),transparent 60%),radial-gradient(700px 520px at 8% 100%,rgba(247,166,0,.05),transparent 55%),radial-gradient(520px 320px at 50% 45%,rgba(70,90,115,.10),transparent 60%)}.doc-topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:10px;padding:10px 14px;background:rgba(16,19,24,.86);backdrop-filter:blur(10px);border-bottom:1px solid #2a3038}.brand{display:flex;align-items:center;gap:8px;font-weight:800;font-size:18px}.save-pill{display:flex;align-items:center;gap:6px;font-size:11px;color:#98a1ac;background:#12151b;border:1px solid #2a3038;padding:4px 10px;border-radius:99px}.save-pill .dot{width:8px;height:8px;border-radius:50%;background:#3dd68c}.save-pill.saving .dot{background:#f7a600}.top-actions{margin-inline-start:auto;display:flex;gap:6px}.icon-btn{width:44px;height:44px;display:grid;place-items:center;background:#12151b;border:1px solid #2a3038;border-radius:10px;color:#98a1ac}.icon-btn:hover{color:#f7a600;border-color:#f7a600}.doc-app{position:relative;z-index:1;max-width:1280px;margin:0 auto;padding:14px;display:grid;grid-template-columns:minmax(0,1fr) minmax(420px,520px);gap:16px}.editor{min-width:0}.sec{background:linear-gradient(180deg,#1a1e25,#171b21);border:1px solid #2a3038;border-radius:12px;padding:14px;margin-bottom:12px}.sec h2{font-size:16px;margin:0 0 12px;display:flex;gap:8px;align-items:center}.chip{width:22px;height:22px;display:grid;place-items:center;border-radius:7px;background:linear-gradient(135deg,#f7a600,#ffc751);color:#171204;font-weight:800}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}.fld span{display:block;font-size:12px;font-weight:700;color:#98a1ac;margin-bottom:4px}.inp{width:100%;min-height:44px;padding:8px 12px;background:#12151b;color:#eceef1;border:1px solid #2a3038;border-radius:9px;font-size:14px}.inp:focus{border-color:#f7a600;outline:none;box-shadow:0 0 0 3px rgba(247,166,0,.15)}.doc-type-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.doc-type{min-height:54px;border-radius:12px;border:1px solid #2a3038;background:#12151b;color:#eceef1;font-weight:800}.doc-type.active{background:linear-gradient(135deg,#f7a600,#ffc751);color:#171204}.item-card{display:grid;grid-template-columns:2fr .7fr .8fr .8fr;gap:8px;padding:10px;border:1px solid #2a3038;border-radius:10px;background:#12151b;margin-bottom:8px}.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:8px 16px;border-radius:10px;border:1px solid #2a3038;background:#1a1e25;color:#eceef1;font-weight:800}.btn.gold{background:linear-gradient(135deg,#f7a600,#ffc751);border:none;color:#171204}.btn-row{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.summary{margin-top:12px;display:grid;gap:6px}.summary div{display:flex;justify-content:space-between;padding:8px 10px;border-radius:8px;background:#12151b}.preview-panel{position:sticky;top:76px;height:calc(100vh - 96px);border:1px solid #2a3038;border-radius:12px;overflow:hidden;background:#0b0d10}.preview-bar{display:flex;align-items:center;gap:6px;padding:8px;background:#0f1114;border-bottom:1px solid #2a3038}.zoom-val{min-width:52px;text-align:center;color:#98a1ac;font-weight:800}.viewport{height:calc(100% - 62px);overflow:auto;padding:18px;display:flex;justify-content:center}.sheet-scale{transform-origin:top center;flex:none}.sheet{width:210mm;min-height:296mm;background:#fff;color:#1a1a1a;padding:12mm;box-shadow:0 24px 70px rgba(0,0,0,.55);font-size:11px}.p-top{height:5px;margin-bottom:6mm;background:linear-gradient(90deg,#15181d 0%,#454b54 55%,#f7a600 100%)}.p-head{display:flex;justify-content:space-between;gap:6mm;padding-bottom:5mm;border-bottom:1px solid #ddd}.p-brand{flex:1;text-align:right}.p-logo{width:14mm;height:14mm;border:1.5px solid #15181d;border-radius:50%;display:grid;place-items:center;margin-bottom:2mm;margin-inline-start:auto}.p-brand h1{font-size:20px;margin:0;color:#111;font-weight:900}.p-tag{font-size:10px;color:#555;margin:2px 0 5px}.p-contact{font-size:9.5px;color:#444;line-height:1.8}.p-meta{width:58mm;border:1px solid #ccc;padding:3mm}.p-doctype{display:block;text-align:center;background:#15181d;color:#fff;font-weight:900;font-size:12px;padding:4px 6px;margin-bottom:6px}.p-mrow{display:flex;justify-content:space-between;gap:8px;font-size:10px;color:#555;padding:3px 0;border-bottom:1px dashed #e5e5e5}.p-mrow b{color:#111}.p-chip{margin-top:7px;background:#f5f5f5;border:1px solid #ddd;text-align:center;padding:5px;font-size:9.5px;font-weight:900}.p-chip b{display:block;font-size:16px}.p-parties{display:grid;grid-template-columns:1fr 1fr;gap:4mm;margin-top:5mm}.p-box{border:1px solid #ccc}.p-box h3{font-size:11.5px;margin:0;padding:5px 8px;background:#f5f5f5;border-bottom:1px solid #ccc}.row{display:flex;justify-content:space-between;gap:8px;padding:4px 8px;border-bottom:1px dashed #eee;font-size:10px}.row span{color:#777}.row b{color:#111;text-align:left}.p-table{width:100%;border-collapse:collapse;margin-top:5mm;font-size:10px;table-layout:fixed}.p-table th{background:#f0f0f0;border:1px solid #bbb;padding:6px;font-weight:900}.p-table td{border:1px solid #ddd;padding:6px;vertical-align:top;word-break:break-word}.p-table .n{text-align:center;white-space:nowrap}.empty-row{text-align:center!important;color:#999;padding:14px!important}.p-after{display:grid;grid-template-columns:1.1fr .9fr;gap:4mm;margin-top:5mm}.p-notes h4{font-size:11px;margin:8px 0 2px;color:#111}.p-notes p{margin:0;font-size:9.5px;color:#333;line-height:1.8}.p-totals{border:1px solid #ccc}.p-trow{display:flex;justify-content:space-between;padding:6px 9px;font-size:10.5px;border-bottom:1px solid #e5e5e5}.p-trow.grand{background:#15181d;color:#fff}.p-trow.grand b{font-size:14px}.p-words{margin-top:4mm;background:#f7f7f7;border:1px dashed #ccc;padding:6px 9px;font-size:10px}.p-signs{display:grid;grid-template-columns:1fr 1fr;gap:6mm;margin-top:7mm}.p-sig h4{font-size:11.5px;margin:0 0 2mm}.p-sigbox{height:18mm;border:1px dashed #aaa}.p-auth{margin-top:2mm;border:1px solid #ccc;border-inline-start:3px solid #15181d;padding:5px 8px;font-size:9.5px;font-weight:700;color:#333}.p-foot{margin-top:7mm;border-top:1px solid #ddd;padding-top:3mm;display:flex;justify-content:space-between;gap:4mm;font-size:9px;color:#777}.p-foot .mid{font-weight:900;color:#111}.pill{display:inline-block;font-size:10px;font-weight:900;padding:2px 10px;border-radius:99px;border:1px solid}.st-draft{color:#555;border-color:#bbb;background:#f0f0f0}.st-unpaid{color:#b3261e;border-color:#e0a8a5;background:#fdeceb}.st-partial{color:#8a6100;border-color:#e8cf8a;background:#fff6dd}.st-paid{color:#116932;border-color:#9ad3b0;background:#e7f6ee}.st-deferred{color:#1a56a8;border-color:#a8c3e6;background:#eaf1fb}@media(max-width:980px){.doc-app{display:block}.preview-panel{position:relative;top:0;height:70vh;margin-top:12px}.grid2,.doc-type-grid,.btn-row{grid-template-columns:1fr 1fr}.item-card{grid-template-columns:1fr}.sheet{transform-origin:top center}}@media print{.doc-topbar,.editor,.preview-bar{display:none!important}.doc-app{display:block;padding:0}.preview-panel{position:static;height:auto;border:0}.viewport{overflow:visible;padding:0}.sheet-scale{transform:none!important;height:auto!important}.sheet{width:auto;min-height:auto;box-shadow:none;margin:0;padding:0}.doc-page{background:#fff}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
`;
