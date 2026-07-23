import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  BadgeCheck,
  CalendarDays,
  Car,
  CheckCircle2,
  CircleDollarSign,
  Download,
  Eye,
  FileText,
  Maximize2,
  Minus,
  Phone,
  Plus,
  Printer,
  RefreshCw,
  Share2,
  ShieldCheck,
  Trash2,
  UserRound,
  Wrench,
} from 'lucide-react';
import { api } from '../services/api';
import { downloadPDF } from '../utils/pdfGenerator';
import { loadWorkshopPrintInfo } from '../utils/workshopPrintInfo';
import { useWhatsAppShare } from '../hooks/useWhatsAppShare';
import WhatsAppSharePreview from '../components/WhatsAppSharePreview';

const SAR = (value) => `${Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ر.س`;
const today = () => new Date().toISOString().slice(0, 10);
const docLabels = {
  invoice: 'فاتورة الورشة — ختم إلكتروني',
  diagnosis: 'تقرير تشخيص إلكتروني',
  quote: 'عرض سعر مختوم',
  receipt: 'سند زيارة مختوم',
};
const statusLabels = {
  draft: 'مسودة',
  unpaid: 'غير مدفوعة',
  partial: 'مدفوعة جزئياً',
  paid: 'مدفوعة',
  deferred: 'آجلة',
  cancelled: 'ملغي',
  superseded: 'مستبدل',
};
const emptyItem = { description: '', quantity: 1, unit_price: 0, discount: 0, vatRate: 0, type: 'service' };

const safeNumber = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizeItem = (item = {}) => {
  const quantity = safeNumber(item.quantity || item.qty || 1, 1);
  const unit = safeNumber(item.unit_price || item.price || item.amount || item.total || 0);
  return {
    description: item.description || item.name || item.serviceName || item.title || 'بند ورشة',
    quantity,
    unit_price: unit,
    discount: safeNumber(item.discount || 0),
    vatRate: safeNumber(item.vatRate || item.tax_rate || item.vat || 0),
    type: item.type || item.itemType || 'service',
  };
};

const getRows = (data, keys = []) => {
  if (Array.isArray(data)) return data;
  for (const key of keys) if (Array.isArray(data?.[key])) return data[key];
  return [];
};

const buildSealCode = (number, date) => {
  const seed = `${number || 'INV'}-${date || today()}`;
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = ((hash << 5) - hash) + seed.charCodeAt(i);
  return `ES-${Math.abs(hash).toString(16).slice(0, 8).toUpperCase()}`;
};

const approvedStatuses = new Set(['approved', 'accepted', 'approval_accepted']);

const normalizeApproval = (approval, fallbackName = '') => {
  if (!approval) return null;
  const approved = approvedStatuses.has(String(approval.status || '').toLowerCase());
  if (!approved) return null;
  return {
    name: approval.responderName || approval.responder_name || approval.approverName || approval.approver_name || approval.approved_by || fallbackName || 'معتمد',
    at: approval.respondedAt || approval.responded_at || approval.approvedAt || approval.approved_at || approval.updatedAt || approval.updated_at || '',
    id: approval.id || approval.token || approval.approvalId || approval.approval_id || '',
  };
};

const barcodeValue = (workshop = {}) => [workshop.name, workshop.tax_number || workshop.taxNumber, workshop.phone].filter(Boolean).join(' | ');

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
  const { share, prepare: prepareShare, reset: resetShare, logEvent: logShareEvent } = useWhatsAppShare();

  const [zoom, setZoom] = useState(0.76);
  const [showPreview, setShowPreview] = useState(true);
  const [loading, setLoading] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [saveState, setSaveState] = useState('جاهز');
  const [alertMessage, setAlertMessage] = useState('');
  const [sealInvalidated, setSealInvalidated] = useState(false);
  const [docType, setDocType] = useState(searchParams.get('type') || 'invoice');
  const [formData, setFormData] = useState({
    workshop: {
      name: 'ورشة داش برو لصيانة السيارات',
      name_en: 'Dash Pro Auto Care',
      phone: '',
      email: '',
      address: '',
      tax_number: '',
      commercial_register: '',
      website: '',
      logo: '',
      tagline: 'ميكانيكا عامة · كهرباء · برمجة · فحص كمبيوتر',
    },
    customer: { name: '', phone: '', email: '', address: '', taxNo: '' },
    vehicle: { brand: '', model: '', year: '', plateNumber: '', vin: '', color: '', mileage: '', notes: '' },
    items: [emptyItem],
    settings: {
      document_number: `INV-${new Date().toISOString().slice(2, 10).replace(/-/g, '')}-${Math.floor(100 + Math.random() * 900)}`,
      date: today(),
      receivedTime: '09:00',
      status: 'draft',
      notes: '',
      warranty: 'ضمان الإصلاح 30 يوماً أو 1,000 كم من تاريخ التسليم، ولا يشمل سوء الاستخدام أو القطع المستعملة.',
    },
    payment: { method: 'cash', paid: 0 },
    approvals: { customer: null, workshop: null },
  });

  const totals = useMemo(() => {
    const rows = (formData.items || []).filter((item) => item.description || Number(item.unit_price) > 0).map((item) => {
      const subtotal = safeNumber(item.quantity) * safeNumber(item.unit_price);
      const discount = safeNumber(item.discount);
      const afterDiscount = Math.max(subtotal - discount, 0);
      const tax = Math.round(afterDiscount * safeNumber(item.vatRate)) / 100;
      return { ...item, subtotal, discount, tax, total: afterDiscount + tax };
    });
    const subtotal = rows.reduce((sum, item) => sum + item.subtotal, 0);
    const discount = rows.reduce((sum, item) => sum + item.discount, 0);
    const tax = rows.reduce((sum, item) => sum + item.tax, 0);
    const total = rows.reduce((sum, item) => sum + item.total, 0);
    const paid = safeNumber(formData.payment?.paid);
    return { rows, subtotal, discount, tax, total, paid, remain: total - paid };
  }, [formData.items, formData.payment?.paid]);

  const sealCode = useMemo(() => buildSealCode(formData.settings.document_number, formData.settings.date), [formData.settings.date, formData.settings.document_number]);

  const patchForm = useCallback((patch) => {
    setSealInvalidated(true);
    setFormData((prev) => ({ ...prev, ...patch }));
  }, []);
  const patchNested = useCallback((section, key, value) => {
    setSealInvalidated(true);
    setFormData((prev) => ({ ...prev, [section]: { ...prev[section], [key]: value } }));
  }, []);

  const loadApprovalLogs = useCallback(async () => {
    if (!vehicleId) return;
    try {
      const { data } = await api.get(`/vehicles/${vehicleId}/approval-logs`);
      const approved = (Array.isArray(data) ? data : []).find((item) => approvedStatuses.has(String(item.status || '').toLowerCase()));
      const customer = normalizeApproval(approved, formData.customer.name);
      if (customer) setFormData((prev) => ({ ...prev, approvals: { ...prev.approvals, customer } }));
    } catch (e) {
      // غياب سجل اعتماد لا يمنع عرض المستند، لكنه يعني عدم إظهار ختم العميل.
    }
  }, [formData.customer.name, vehicleId]);

  const loadWorkshop = useCallback(async () => {
    const ws = await loadWorkshopPrintInfo(async (path) => {
      const response = await api.get(path);
      return { ok: true, json: async () => response.data };
    });
    setFormData((prev) => ({
      ...prev,
      workshop: {
        ...prev.workshop,
        ...ws,
        tagline: ws.slogan || ws.tagline || prev.workshop.tagline,
      },
    }));
  }, []);

  const loadCustomer = useCallback(async (customerId) => {
    if (!customerId) return;
    try {
      const response = await api.get('/customers');
      const rows = getRows(response.data, ['customers', 'data']);
      const match = rows.find((c) => c.id === customerId || c.customerId === customerId);
      if (!match) return;
      setFormData((prev) => ({
        ...prev,
        customer: {
          ...prev.customer,
          name: match.name || prev.customer.name,
          phone: match.phone || prev.customer.phone,
          email: match.email || prev.customer.email,
          address: match.address || match.company || prev.customer.address,
          taxNo: match.taxNo || match.tax_number || prev.customer.taxNo,
        },
      }));
    } catch (e) {
      setAlertMessage('تعذر جلب بيانات العميل، يمكنك إكمالها يدوياً.');
    }
  }, []);

  const loadVehicle = useCallback(async (id, preserveItems = false) => {
    if (!id) return;
    try {
      const { data } = await api.get(`/vehicles/${id}`);
      if (!data) return;
      setFormData((prev) => ({
        ...prev,
        customer: {
          ...prev.customer,
          name: data.customerName || data.customer_name || prev.customer.name,
          phone: data.customerPhone || data.customer_phone || prev.customer.phone,
        },
        vehicle: {
          ...prev.vehicle,
          brand: data.brand || data.vehicleBrand || prev.vehicle.brand,
          model: data.model || data.vehicleModel || prev.vehicle.model,
          year: data.year || data.vehicleYear || prev.vehicle.year,
          plateNumber: data.plateNumber || data.plate || prev.vehicle.plateNumber,
          vin: data.vin || data.chassisNumber || prev.vehicle.vin,
          color: data.color || prev.vehicle.color,
          mileage: data.mileage || prev.vehicle.mileage,
          notes: data.notes || prev.vehicle.notes,
        },
        items: preserveItems ? prev.items : (Array.isArray(data.parts) && data.parts.length ? data.parts.map(normalizeItem) : prev.items),
      }));
      if (data.customerId || data.customer_id) await loadCustomer(data.customerId || data.customer_id);
    } catch (e) {
      setAlertMessage('تعذر جلب بيانات المركبة، يمكنك إكمالها يدوياً.');
    }
  }, [loadCustomer]);

  const loadVisit = useCallback(async () => {
    if (!visitId) return;
    try {
      const opsResponse = await api.get(`/visits/${visitId}/operations`).catch(() => ({ data: [] }));
      const ops = getRows(opsResponse.data, ['operations', 'data']);
      if (ops.length) {
        const op = ops[0];
        const items = typeof op.items === 'string' ? JSON.parse(op.items || '[]') : (op.items || []);
        setFormData((prev) => ({
          ...prev,
          items: items.length ? items.map(normalizeItem) : [normalizeItem({ description: op.description || op.notes || 'زيارة ورشة', price: op.total || op.amount || 0 })],
          customer: {
            ...prev.customer,
            name: op.customerName || op.customer_name || op.partnerName || prev.customer.name,
            phone: op.customerPhone || op.customer_phone || prev.customer.phone,
          },
          settings: {
            ...prev.settings,
            document_number: op.invoiceNumber || op.invoice_number || prev.settings.document_number,
            date: String(op.date || op.createdAt || today()).slice(0, 10),
            notes: op.notes || prev.settings.notes,
          },
          approvals: { ...prev.approvals, workshop: normalizeApproval(op.workshopApproval || op.workshop_approval || { status: op.approval_status, approved_by: op.approved_by, approved_at: op.approved_at }) },
        }));
        return;
      }
      if (!vehicleId) return;
      const visitsResponse = await api.get(`/vehicles/${vehicleId}/visits`).catch(() => ({ data: [] }));
      const visits = getRows(visitsResponse.data, ['visits', 'data']);
      const visit = visits.find((v) => v.id === visitId || v.visitId === visitId);
      if (!visit) return;
      let parsed = [];
      if (String(visit.notes || '').trim().startsWith('{')) {
        try { parsed = JSON.parse(visit.notes).items || []; } catch (e) { parsed = []; }
      }
      setFormData((prev) => ({
        ...prev,
        items: parsed.length ? parsed.map(normalizeItem) : [normalizeItem({ description: docType === 'diagnosis' ? 'تقرير تشخيص' : 'زيارة ورشة', price: visit.total_workshop || visit.total || 0 })],
        settings: {
          ...prev.settings,
          document_number: visit.invoiceNumber || visit.id || prev.settings.document_number,
          date: String(visit.created_at || visit.createdAt || today()).slice(0, 10),
          notes: typeof visit.notes === 'string' && !visit.notes.trim().startsWith('{') ? visit.notes : prev.settings.notes,
        },
      }));
    } catch (e) {
      setAlertMessage('تعذر جلب بيانات الزيارة، يمكنك إكمالها يدوياً.');
    }
  }, [docType, vehicleId, visitId]);

  const loadOperation = useCallback(async (id) => {
    if (!id) return;
    try {
      const { data: op } = await api.get(`/operations/${id}`);
      if (!op) return;
      const opItems = typeof op.items === 'string' ? JSON.parse(op.items || '[]') : (op.items || []);
      setFormData((prev) => ({
        ...prev,
        items: opItems.length ? opItems.map(normalizeItem) : [normalizeItem({ description: op.description || op.notes || 'عملية ورشة', price: op.total || op.amount || 0 })],
        customer: {
          ...prev.customer,
          name: op.customerName || op.customer_name || op.partnerName || prev.customer.name,
          phone: op.customerPhone || op.customer_phone || prev.customer.phone,
        },
        settings: {
          ...prev.settings,
          document_number: op.invoiceNumber || op.invoice_number || `OP-${op.id || ''}`,
          date: String(op.date || op.createdAt || today()).slice(0, 10),
          notes: op.notes || prev.settings.notes,
        },
      }));
      if (op.vehicleId || op.vehicle_id) await loadVehicle(op.vehicleId || op.vehicle_id, true);
    } catch (e) {
      setAlertMessage('تعذر جلب بيانات العملية، يمكنك إكمالها يدوياً.');
    }
  }, [loadVehicle]);

  const loadInvoice = useCallback(async (id) => {
    if (!id) return;
    try {
      const { data } = await api.get(`/invoices/${id}`);
      if (!data) return;
      const items = typeof data.items === 'string' ? JSON.parse(data.items || '[]') : (data.items || []);
      setFormData((prev) => ({
        ...prev,
        items: items.length ? items.map(normalizeItem) : prev.items,
        customer: { ...prev.customer, name: data.partner_name || data.partnerName || prev.customer.name },
        settings: {
          ...prev.settings,
          document_number: data.invoice_number || data.invoiceNumber || prev.settings.document_number,
          date: String(data.created_at || data.createdAt || today()).slice(0, 10),
          notes: data.notes || prev.settings.notes,
        },
        approvals: { ...prev.approvals, workshop: normalizeApproval(data.workshopApproval || data.workshop_approval || { status: data.approval_status, approved_by: data.approved_by, approved_at: data.approved_at }) },
      }));
      if (data.vehicleId || data.vehicle_id) await loadVehicle(data.vehicleId || data.vehicle_id, true);
    } catch (e) {
      setAlertMessage('تعذر جلب بيانات الفاتورة، يمكنك إكمالها يدوياً.');
    }
  }, [loadVehicle]);

  const refreshData = useCallback(async () => {
    setLoading(true);
    setAlertMessage('');
    setSaveState('تحديث البيانات...');
    try {
      await loadWorkshop();
      if (vehicleId) await loadVehicle(vehicleId, Boolean(visitId || operationId || invoiceId));
      if (visitId) await loadVisit();
      if (operationId) await loadOperation(operationId);
      if (invoiceId) await loadInvoice(invoiceId);
      await loadApprovalLogs();
      setSealInvalidated(false);
      setSaveState('محفوظ');
    } finally {
      setLoading(false);
      setTimeout(() => setSaveState('جاهز'), 1200);
    }
  }, [invoiceId, loadApprovalLogs, loadInvoice, loadOperation, loadVehicle, loadVisit, loadWorkshop, operationId, vehicleId, visitId]);

  useEffect(() => { refreshData(); }, [refreshData]);

  const numberToWords = (value) => value <= 0 ? 'فقط صفر ريال لا غير' : `فقط ${SAR(value)} لا غير`;

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
    setAlertMessage('');
    if (!showPreview) {
      setShowPreview(true);
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
    const payload = {
      doc_type: docType,
      document_number: formData.settings.document_number,
      customer: formData.customer,
      vehicle: formData.vehicle,
      items: formData.items,
      payment: formData.payment,
      settings: { ...formData.settings, seal_code: sealCode, totals: { paid: totals.paid } },
    };
    await prepareShare({
      docType,
      payload,
      workshop: formData.workshop,
      templateId: 'dash-pro-electronic-sheet',
      templateVersion: 'v1',
      phone: formData.customer.phone,
      fileBaseName: `${docType}_${formData.settings.document_number || 'document'}`,
      context: 'document-print-page',
      getElement: async () => ({ element: previewRef.current, cleanup: null }),
    });
  };

  useEffect(() => {
    if ((!autoPrint && !autoWhatsApp) || autoActionRef.current) return;
    autoActionRef.current = true;
    setTimeout(() => { autoPrint ? printCurrent() : sendWhatsApp(); }, 900);
  }, [autoPrint, autoWhatsApp]);

  const updateItem = (index, key, value) => {
    setSealInvalidated(true);
    setFormData((prev) => ({
      ...prev,
      items: prev.items.map((item, i) => i === index ? { ...item, [key]: key === 'description' || key === 'type' ? value : safeNumber(value) } : item),
    }));
  };

  const removeItem = (index) => {
    setSealInvalidated(true);
    setFormData((prev) => ({ ...prev, items: prev.items.length > 1 ? prev.items.filter((_, i) => i !== index) : [emptyItem] }));
  };

  return (
    <div className="document-print-page" dir="rtl" data-testid="document-print-page">
      <style>{styles}</style>
      <style>{printOverrides}</style>
      <header className="doc-shell-header" data-testid="document-shell-header">
        <div className="doc-brand-block">
          <div className="doc-brand-icon"><ShieldCheck size={24} /></div>
          <div>
            <p className="doc-kicker" data-testid="document-page-kicker">داش برو · مستندات الورشة</p>
            <h1 data-testid="document-page-title">فاتورة الورشة — ختم إلكتروني</h1>
          </div>
        </div>
        <div className="doc-header-actions">
          {alertMessage && <div className="doc-alert" data-testid="document-alert-message">{alertMessage}</div>}
          <div className={`doc-save-pill ${loading ? 'is-loading' : ''}`} data-testid="document-save-state"><span />{saveState}</div>
          <button type="button" className="doc-icon-button" onClick={refreshData} data-testid="document-refresh-button" aria-label="تحديث"><RefreshCw size={19} /></button>
          <button type="button" className="doc-icon-button" onClick={() => setShowPreview((v) => !v)} data-testid="document-toggle-preview-button" aria-label="إظهار المعاينة"><Eye size={19} /></button>
        </div>
      </header>

      <main className={`doc-workspace ${showPreview ? 'with-preview' : 'editor-only'}`} data-testid="document-workspace">
        <section className="doc-editor" data-testid="document-editor-panel">
          <Panel title="نوع المستند" icon={<FileText size={18} />} testId="document-type-section">
            <div className="doc-type-grid">
              {Object.entries(docLabels).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={`doc-type-card ${docType === key ? 'active' : ''}`}
                  onClick={() => { setSealInvalidated(true); setDocType(key); }}
                  data-testid={`document-type-${key}`}
                >
                  <span>{label}</span>
                  {docType === key && <CheckCircle2 size={18} />}
                </button>
              ))}
            </div>
          </Panel>

          <Panel title="بيانات المستند" icon={<CalendarDays size={18} />} testId="document-settings-section">
            <div className="doc-grid two">
              <Field testId="document-number-input" label="رقم المستند" value={formData.settings.document_number} onChange={(v) => patchNested('settings', 'document_number', v)} />
              <Field testId="document-date-input" label="التاريخ" type="date" value={formData.settings.date} onChange={(v) => patchNested('settings', 'date', v)} />
              <Field testId="document-time-input" label="وقت الاستلام" type="time" value={formData.settings.receivedTime} onChange={(v) => patchNested('settings', 'receivedTime', v)} />
              <SelectField testId="document-status-select" label="الحالة" value={formData.settings.status} onChange={(v) => patchNested('settings', 'status', v)} options={statusLabels} />
            </div>
          </Panel>

          <Panel title="العميل والمركبة" icon={<Car size={18} />} testId="document-party-section">
            <div className="doc-grid two">
              <Field testId="document-customer-name-input" label="اسم العميل" value={formData.customer.name} onChange={(v) => patchNested('customer', 'name', v)} />
              <Field testId="document-customer-phone-input" label="جوال العميل" value={formData.customer.phone} onChange={(v) => patchNested('customer', 'phone', v)} />
              <Field testId="document-plate-input" label="رقم اللوحة" value={formData.vehicle.plateNumber} onChange={(v) => patchNested('vehicle', 'plateNumber', v)} />
              <Field testId="document-mileage-input" label="العداد" value={formData.vehicle.mileage} onChange={(v) => patchNested('vehicle', 'mileage', v)} />
              <Field testId="document-vehicle-brand-input" label="الماركة" value={formData.vehicle.brand} onChange={(v) => patchNested('vehicle', 'brand', v)} />
              <Field testId="document-vehicle-model-input" label="الموديل" value={formData.vehicle.model} onChange={(v) => patchNested('vehicle', 'model', v)} />
              <Field testId="document-vehicle-year-input" label="السنة" value={formData.vehicle.year} onChange={(v) => patchNested('vehicle', 'year', v)} />
              <Field testId="document-vin-input" label="VIN" value={formData.vehicle.vin} onChange={(v) => patchNested('vehicle', 'vin', v)} />
            </div>
          </Panel>

          <Panel title="بنود الورشة" icon={<Wrench size={18} />} testId="document-items-section">
            <div className="doc-items-list" data-testid="document-items-list">
              {formData.items.map((item, index) => (
                <div className="doc-item-row" key={`item-${index}`} data-testid={`document-item-row-${index}`}>
                  <Field testId={`document-item-description-${index}`} label="الوصف" value={item.description} onChange={(v) => updateItem(index, 'description', v)} />
                  <Field testId={`document-item-quantity-${index}`} label="الكمية" type="number" value={item.quantity} onChange={(v) => updateItem(index, 'quantity', v)} />
                  <Field testId={`document-item-price-${index}`} label="السعر" type="number" value={item.unit_price} onChange={(v) => updateItem(index, 'unit_price', v)} />
                  <Field testId={`document-item-discount-${index}`} label="الخصم" type="number" value={item.discount} onChange={(v) => updateItem(index, 'discount', v)} />
                  <button type="button" className="doc-remove-button" onClick={() => removeItem(index)} data-testid={`document-remove-item-${index}`} aria-label="حذف البند"><Trash2 size={17} /></button>
                </div>
              ))}
            </div>
            <button type="button" className="doc-action primary" onClick={() => patchForm({ items: [...formData.items, emptyItem] })} data-testid="document-add-item-button"><Plus size={18} /> إضافة بند</button>
          </Panel>

          <Panel title="الدفع والملاحظات" icon={<CircleDollarSign size={18} />} testId="document-payment-section">
            <div className="doc-grid two">
              <Field testId="document-paid-input" label="المدفوع" type="number" value={formData.payment.paid} onChange={(v) => patchForm({ payment: { ...formData.payment, paid: safeNumber(v) } })} />
              <Field testId="document-warranty-input" label="الضمان" value={formData.settings.warranty} onChange={(v) => patchNested('settings', 'warranty', v)} />
            </div>
            <label className="doc-field wide" data-testid="document-notes-field">
              <span>ملاحظات</span>
              <textarea value={formData.settings.notes} onChange={(e) => patchNested('settings', 'notes', e.target.value)} data-testid="document-notes-input" />
            </label>
            <div className="doc-summary-strip">
              <SummaryItem label="الإجمالي" value={SAR(totals.total)} testId="document-editor-total" />
              <SummaryItem label="المدفوع" value={SAR(totals.paid)} testId="document-editor-paid" />
              <SummaryItem label="المتبقي" value={SAR(totals.remain)} testId="document-editor-remaining" />
            </div>
          </Panel>

          <Panel title="الإجراءات" icon={<ShieldCheck size={18} />} testId="document-actions-section">
            <div className="doc-actions-grid">
              <button type="button" className="doc-action primary" onClick={printCurrent} data-testid="document-print-button"><Printer size={18} /> طباعة</button>
              <button type="button" className="doc-action" onClick={downloadCurrentPdf} disabled={pdfBusy} data-testid="document-download-button"><Download size={18} /> تحميل PDF</button>
              <button type="button" className="doc-action whatsapp" onClick={sendWhatsApp} disabled={pdfBusy} data-testid="document-whatsapp-button"><Share2 size={18} /> واتساب</button>
              <button type="button" className="doc-action" onClick={() => setZoom(0.76)} data-testid="document-fit-button"><Maximize2 size={18} /> ملاءمة</button>
            </div>
          </Panel>
        </section>

        {showPreview && (
          <section className="doc-preview-panel" data-testid="document-preview-panel">
            <div className="doc-preview-toolbar" data-testid="document-preview-toolbar">
              <button type="button" className="doc-icon-button" onClick={() => setZoom((z) => Math.max(0.38, z - 0.08))} data-testid="document-zoom-out-button" aria-label="تصغير"><Minus size={18} /></button>
              <span className="doc-zoom" data-testid="document-zoom-value">{Math.round(zoom * 100)}%</span>
              <button type="button" className="doc-icon-button" onClick={() => setZoom((z) => Math.min(1.45, z + 0.08))} data-testid="document-zoom-in-button" aria-label="تكبير"><Plus size={18} /></button>
              <button type="button" className="doc-icon-button" onClick={printCurrent} data-testid="document-preview-print-button" aria-label="طباعة"><Printer size={18} /></button>
              <button type="button" className="doc-icon-button" onClick={downloadCurrentPdf} data-testid="document-preview-download-button" aria-label="تحميل"><Download size={18} /></button>
              <button type="button" className="doc-icon-button" onClick={sendWhatsApp} data-testid="document-preview-whatsapp-button" aria-label="واتساب"><Share2 size={18} /></button>
            </div>
            <div className="doc-preview-viewport" data-testid="document-preview-viewport">
              <div className="doc-sheet-scale" style={{ transform: `scale(${zoom})`, height: `${1124 * zoom}px` }}>
                <InvoiceSheet
                  ref={previewRef}
                  docType={docType}
                  formData={formData}
                  totals={totals}
                  sealCode={sealCode}
                  numberToWords={numberToWords}
                  sealInvalidated={sealInvalidated}
                />
              </div>
            </div>
          </section>
        )}
      </main>
      <WhatsAppSharePreview share={share} onClose={resetShare} logEvent={logShareEvent} />
    </div>
  );
}

const InvoiceSheet = React.forwardRef(({ docType, formData, totals, sealCode, numberToWords, sealInvalidated }, ref) => {
  const w = formData.workshop || {};
  const c = formData.customer || {};
  const v = formData.vehicle || {};
  const settings = formData.settings || {};
  const title = docLabels[docType] || docLabels.invoice;
  const workshopInitial = String(w.name || 'د').trim().slice(0, 1);
  const customerSeal = !sealInvalidated ? formData.approvals?.customer : null;
  const workshopSeal = !sealInvalidated ? formData.approvals?.workshop : null;
  const barcode = barcodeValue(w);

  return (
    <article className="electronic-invoice-sheet" ref={ref} data-testid="document-sheet">
      <div className={`invoice-watermark ${['draft', 'cancelled', 'superseded'].includes(settings.status) ? 'strong' : ''}`} data-testid="document-watermark">
        {settings.status === 'draft' ? 'مسودة' : settings.status === 'cancelled' ? 'ملغي' : settings.status === 'superseded' ? 'مستبدل' : 'مختوم'}
      </div>
      <header className="invoice-hero" data-testid="document-invoice-header">
        <div className="invoice-identity">
          <div className="invoice-logo" data-testid="document-workshop-logo">
            {w.logo ? <img src={w.logo} alt="شعار الورشة" /> : <span>{workshopInitial}</span>}
          </div>
          <div>
            <p className="invoice-overline" data-testid="document-invoice-overline">ELECTRONICALLY SEALED INVOICE</p>
            <h2 data-testid="document-workshop-name">{w.name || 'ورشة داش برو لصيانة السيارات'}</h2>
            <p data-testid="document-workshop-tagline">{w.tagline || 'ميكانيكا عامة · كهرباء · فحص كمبيوتر'}</p>
          </div>
        </div>
        <div className="invoice-header-meta" data-testid="document-header-meta">
          <strong data-testid="document-title-kind">{docType === 'invoice' ? 'فاتورة ضريبية' : title}</strong>
          <span data-testid="document-header-tax">الرقم الضريبي: {w.tax_number || w.taxNumber || '—'}</span>
        </div>
      </header>

      <section className="invoice-title-band" data-testid="document-title-band">
        <div>
          <p data-testid="document-title-label">{title}</p>
          <h1 data-testid="document-invoice-number">{settings.document_number || '—'}</h1>
        </div>
        <div className="invoice-status-block">
          <span className={`invoice-status ${settings.status || 'draft'}`} data-testid="document-status-label">{statusLabels[settings.status] || 'مسودة'}</span>
          <small data-testid="document-date-value">{settings.date || today()} · {settings.receivedTime || '09:00'}</small>
        </div>
      </section>

      <section className="invoice-contact-grid" data-testid="document-contact-grid">
        <InfoCard icon={<UserRound size={18} />} title="بيانات العميل" testId="document-customer-card">
          <InfoLine label="الاسم" value={c.name || 'عميل نقدي'} testId="document-customer-name" />
          <InfoLine label="الجوال" value={c.phone || '—'} testId="document-customer-phone" />
          <InfoLine label="العنوان" value={c.address || '—'} testId="document-customer-address" />
          <InfoLine label="الرقم الضريبي" value={c.taxNo || '—'} testId="document-customer-tax" />
        </InfoCard>
        <InfoCard icon={<Car size={18} />} title="بيانات المركبة" testId="document-vehicle-card">
          <InfoLine label="المركبة" value={`${v.brand || '—'} ${v.model || ''}`.trim()} testId="document-vehicle-name" />
          <InfoLine label="اللوحة" value={v.plateNumber || '—'} testId="document-vehicle-plate" />
          <InfoLine label="السنة" value={v.year || '—'} testId="document-vehicle-year" />
          <InfoLine label="العداد" value={v.mileage || '—'} testId="document-vehicle-mileage" />
        </InfoCard>
        <InfoCard icon={<Phone size={18} />} title="بيانات الورشة" testId="document-workshop-card">
          <InfoLine label="الجوال" value={w.phone || '—'} testId="document-workshop-phone" />
          <InfoLine label="العنوان" value={w.address || '—'} testId="document-workshop-address" />
          <InfoLine label="السجل" value={w.commercial_register || w.commercialRegister || '—'} testId="document-workshop-cr" />
          <InfoLine label="الضريبي" value={w.tax_number || w.taxNumber || '—'} testId="document-workshop-tax" />
        </InfoCard>
      </section>

      <section className="invoice-table-section" data-testid="document-table-section">
        <div className="section-heading"><Wrench size={17} /><span data-testid="document-items-heading">بنود الإصلاح والخدمات</span></div>
        <table className="invoice-items-table" data-testid="document-items-table">
          <thead>
            <tr>
              <th>#</th>
              <th>البيان</th>
              <th>الكمية</th>
              <th>السعر</th>
              <th>الخصم</th>
              <th>الضريبة</th>
              <th>الإجمالي</th>
            </tr>
          </thead>
          <tbody>
            {totals.rows.length ? totals.rows.map((item, idx) => (
              <tr key={`${item.description}-${idx}`} data-testid={`document-table-row-${idx}`}>
                <td data-testid={`document-table-index-${idx}`}>{idx + 1}</td>
                <td className="item-desc" data-testid={`document-table-description-${idx}`}>{item.description}</td>
                <td data-testid={`document-table-quantity-${idx}`}>{item.quantity}</td>
                <td data-testid={`document-table-price-${idx}`}>{SAR(item.unit_price)}</td>
                <td data-testid={`document-table-discount-${idx}`}>{item.discount ? SAR(item.discount) : '—'}</td>
                <td data-testid={`document-table-tax-${idx}`}>{item.tax ? SAR(item.tax) : '—'}</td>
                <td className="strong" data-testid={`document-table-total-${idx}`}>{SAR(item.total)}</td>
              </tr>
            )) : (
              <tr><td colSpan="7" className="empty-table" data-testid="document-empty-items">لا توجد بنود</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="invoice-bottom-grid" data-testid="document-bottom-grid">
        <div className="invoice-notes" data-testid="document-notes-box">
          <h3 data-testid="document-warranty-title">شروط الضمان</h3>
          <p data-testid="document-warranty-text">{settings.warranty || '—'}</p>
          <h3 data-testid="document-notes-title">ملاحظات</h3>
          <p data-testid="document-notes-text">{settings.notes || 'لا توجد ملاحظات إضافية.'}</p>
          <div className="amount-words" data-testid="document-amount-words"><strong>المبلغ كتابةً:</strong> {numberToWords(totals.total)}</div>
        </div>
        <div className="invoice-totals-card" data-testid="document-totals-card">
          <TotalLine label="المجموع قبل الخصم" value={SAR(totals.subtotal)} testId="document-subtotal" />
          <TotalLine label="إجمالي الخصومات" value={`− ${SAR(totals.discount)}`} testId="document-discount" />
          <TotalLine label="الضريبة" value={SAR(totals.tax)} testId="document-tax" />
          <TotalLine label="الإجمالي النهائي" value={SAR(totals.total)} accent testId="document-grand-total" />
        </div>
      </section>

      <section className="invoice-approval-area" data-testid="document-approval-area">
        {sealInvalidated && (formData.approvals?.customer || formData.approvals?.workshop) && (
          <p className="seal-invalidated" data-testid="document-seals-invalidated">تم تعديل المستند بعد الاعتماد — الأختام بحاجة لاعتماد جديد.</p>
        )}
        {!sealInvalidated && (customerSeal || workshopSeal) && (
          <div className="invoice-seal-row" data-testid="document-dynamic-seals">
            {customerSeal && <ElectronicSeal label="تمت الموافقة" approval={customerSeal} testId="document-customer-electronic-seal" />}
            {workshopSeal && <ElectronicSeal label="معتمد" approval={workshopSeal} testId="document-workshop-electronic-seal" />}
          </div>
        )}
      </section>

      <footer className="invoice-footer" data-testid="document-footer">
        <span data-testid="document-footer-contact">{w.phone || ''} {w.website ? `· ${w.website}` : ''}</span>
        <strong data-testid="document-footer-message">تم إصدار هذا المستند إلكترونياً عبر نظام داش برو</strong>
        <div className="invoice-barcode" data-value={barcode} data-testid="document-single-barcode">
          <div className="barcode-bars" aria-hidden="true">{Array.from({ length: 42 }, (_, index) => <i key={index} style={{ width: `${1 + ((barcode.charCodeAt(index % Math.max(barcode.length, 1)) || index) % 3)}px` }} />)}</div>
          <span data-testid="document-barcode-value">{barcode || 'بيانات الورشة غير مكتملة'}</span>
        </div>
      </footer>
    </article>
  );
});

InvoiceSheet.displayName = 'InvoiceSheet';

function Panel({ title, icon, children, testId }) {
  return <section className="doc-panel" data-testid={testId}><h2 data-testid={`${testId}-title`}>{icon}{title}</h2>{children}</section>;
}

function Field({ label, value, onChange, type = 'text', testId }) {
  return <label className="doc-field" data-testid={`${testId}-field`}><span>{label}</span><input type={type} value={value ?? ''} onChange={(e) => onChange(e.target.value)} data-testid={testId} /></label>;
}

function SelectField({ label, value, onChange, options, testId }) {
  return <label className="doc-field" data-testid={`${testId}-field`}><span>{label}</span><select value={value} onChange={(e) => onChange(e.target.value)} data-testid={testId}>{Object.entries(options).map(([key, labelText]) => <option value={key} key={key}>{labelText}</option>)}</select></label>;
}

function SummaryItem({ label, value, testId }) {
  return <div className="doc-summary-item" data-testid={testId}><span>{label}</span><strong>{value}</strong></div>;
}

function InfoCard({ icon, title, children, testId }) {
  return <div className="invoice-info-card" data-testid={testId}><h3 data-testid={`${testId}-title`}>{icon}{title}</h3>{children}</div>;
}

function InfoLine({ label, value, testId }) {
  return <div className="invoice-info-line" data-testid={testId}><span>{label}</span><strong>{value}</strong></div>;
}

function TotalLine({ label, value, accent = false, testId }) {
  return <div className={`invoice-total-line ${accent ? 'accent' : ''}`} data-testid={testId}><span>{label}</span><strong>{value}</strong></div>;
}

function ElectronicSeal({ label, approval, testId }) {
  const date = approval.at ? new Date(approval.at) : null;
  const dateText = date && !Number.isNaN(date.getTime()) ? date.toLocaleDateString('ar-SA') : '—';
  const timeText = date && !Number.isNaN(date.getTime()) ? date.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }) : '—';
  return <div className="dynamic-electronic-seal" data-testid={testId}><BadgeCheck size={16} /><strong>{label}</strong><span>{approval.name}</span><small>{dateText} · {timeText}</small><em>{String(approval.id || '—').slice(0, 14)}</em></div>;
}

const styles = `
.document-print-page{--dp-bg:#f6f7fb;--dp-card:#ffffff;--dp-navy:#172033;--dp-blue:#2563eb;--dp-blue2:#0ea5e9;--dp-text:#172033;--dp-muted:#64748b;--dp-line:#e2e8f0;--dp-green:#10b981;--dp-orange:#f59e0b;min-height:100vh;background:linear-gradient(180deg,#f6f7fb 0%,#eef3f8 100%);color:var(--dp-text);font-family:Parastoo,Tahoma,Arial,sans-serif;direction:rtl;padding:18px}.document-print-page *{box-sizing:border-box;letter-spacing:0}.doc-shell-header{position:sticky;top:10px;z-index:15;display:flex;align-items:center;justify-content:space-between;gap:16px;margin:0 auto 18px;max-width:1480px;padding:16px 18px;background:rgba(255,255,255,.88);border:1px solid rgba(226,232,240,.9);border-radius:20px;box-shadow:0 16px 40px rgba(15,23,42,.08);backdrop-filter:blur(16px)}.doc-brand-block{display:flex;align-items:center;gap:14px;min-width:0}.doc-brand-icon{width:54px;height:54px;display:grid;place-items:center;border-radius:16px;background:linear-gradient(135deg,#1e3a5f,#172033);color:#fff;box-shadow:0 16px 34px rgba(30,58,95,.24)}.doc-kicker{margin:0 0 2px;font-size:12px;font-weight:800;color:var(--dp-blue)!important}.doc-shell-header h1{margin:0;font-size:24px;font-weight:900;color:var(--dp-text)!important}.doc-header-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}.doc-alert{max-width:360px;padding:9px 12px;border-radius:12px;background:#fff7ed;border:1px solid #fed7aa;color:#9a3412!important;font-size:12px;font-weight:800}.doc-save-pill{display:inline-flex;align-items:center;gap:7px;padding:8px 12px;border-radius:999px;background:#ecfdf5;color:#047857!important;border:1px solid #bbf7d0;font-size:12px;font-weight:900}.doc-save-pill span{width:8px;height:8px;border-radius:50%;background:#10b981}.doc-save-pill.is-loading{background:#fffbeb;color:#92400e!important;border-color:#fde68a}.doc-save-pill.is-loading span{background:#f59e0b}.doc-icon-button{width:42px;height:42px;display:grid;place-items:center;border-radius:12px;border:1px solid var(--dp-line);background:#fff;color:var(--dp-text);cursor:pointer;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}.doc-icon-button:hover{transform:translateY(-1px);border-color:#bfdbfe;box-shadow:0 10px 24px rgba(37,99,235,.14);color:var(--dp-blue)}.doc-workspace{max-width:1480px;margin:0 auto;display:grid;grid-template-columns:minmax(0,1fr) minmax(440px,570px);gap:18px;align-items:start}.doc-workspace.editor-only{grid-template-columns:minmax(0,920px);justify-content:center}.doc-editor{min-width:0}.doc-panel{background:var(--dp-card);border:1px solid var(--dp-line);border-radius:20px;padding:18px;margin-bottom:14px;box-shadow:0 10px 28px rgba(15,23,42,.06);animation:docRise .28s ease both}.doc-panel h2{margin:0 0 14px;display:flex;align-items:center;gap:9px;font-size:16px;font-weight:900;color:var(--dp-text)!important}.doc-panel h2 svg{color:var(--dp-blue)}.doc-grid.two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.doc-field{display:block;min-width:0}.doc-field span{display:block;margin-bottom:6px;font-size:12px;font-weight:900;color:var(--dp-muted)!important}.doc-field input,.doc-field select,.doc-field textarea{width:100%;min-height:46px;border:1px solid var(--dp-line);border-radius:12px;background:#fff;color:var(--dp-text);font-size:14px;font-weight:700;padding:10px 12px;outline:none;transition:border-color .18s ease,box-shadow .18s ease}.doc-field textarea{min-height:92px;resize:vertical;line-height:1.7}.doc-field input:focus,.doc-field select:focus,.doc-field textarea:focus{border-color:#93c5fd;box-shadow:0 0 0 4px rgba(37,99,235,.10)}.doc-type-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.doc-type-card{min-height:72px;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px;border:1px solid var(--dp-line);border-radius:16px;background:#fff;color:var(--dp-text);font-size:13px;font-weight:900;text-align:right;cursor:pointer;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}.doc-type-card:hover{transform:translateY(-1px);border-color:#bfdbfe;box-shadow:0 12px 26px rgba(37,99,235,.10)}.doc-type-card.active{background:linear-gradient(135deg,#2563eb,#0ea5e9);border-color:transparent;color:#fff}.doc-type-card.active span,.doc-type-card.active svg{color:#fff!important}.doc-items-list{display:grid;gap:10px;margin-bottom:12px}.doc-item-row{display:grid;grid-template-columns:minmax(180px,2fr) minmax(76px,.7fr) minmax(90px,.9fr) minmax(80px,.8fr) 46px;gap:10px;align-items:end;padding:12px;border-radius:16px;background:#f8fafc;border:1px solid #edf2f7}.doc-remove-button{height:46px;border:1px solid #fecdd3;background:#fff1f2;color:#be123c;border-radius:12px;display:grid;place-items:center;cursor:pointer}.doc-action{min-height:48px;display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:10px 14px;border:1px solid var(--dp-line);border-radius:14px;background:#fff;color:var(--dp-text);font-size:14px;font-weight:900;cursor:pointer;transition:transform .18s ease,box-shadow .18s ease}.doc-action:hover{transform:translateY(-1px);box-shadow:0 12px 25px rgba(15,23,42,.10)}.doc-action.primary{background:linear-gradient(135deg,#2563eb,#1d4ed8);border-color:transparent;color:#fff}.doc-action.primary svg,.doc-action.whatsapp svg{color:#fff!important}.doc-action.whatsapp{background:linear-gradient(135deg,#10b981,#059669);border-color:transparent;color:#fff}.doc-action:disabled{opacity:.58;cursor:not-allowed;transform:none}.doc-summary-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:12px}.doc-summary-item{padding:12px;border-radius:15px;background:#f8fafc;border:1px solid var(--dp-line)}.doc-summary-item span{display:block;font-size:12px;color:var(--dp-muted)!important;font-weight:800}.doc-summary-item strong{display:block;margin-top:4px;font-size:16px;color:var(--dp-text)!important;font-weight:950}.doc-actions-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.doc-preview-panel{position:sticky;top:96px;height:calc(100vh - 116px);overflow:hidden;border-radius:22px;background:#172033;border:1px solid rgba(255,255,255,.12);box-shadow:0 24px 60px rgba(15,23,42,.18)}.doc-preview-toolbar{display:flex;align-items:center;gap:8px;padding:10px;background:linear-gradient(135deg,#1e3a5f,#172033);border-bottom:1px solid rgba(255,255,255,.10)}.doc-preview-toolbar .doc-icon-button{background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.12);color:#e2e8f0}.doc-preview-toolbar .doc-icon-button:hover{color:#fff;border-color:rgba(125,211,252,.5)}.doc-zoom{min-width:58px;text-align:center;color:#e2e8f0!important;font-size:13px;font-weight:900}.doc-preview-viewport{height:calc(100% - 63px);overflow:auto;padding:22px;display:flex;justify-content:center;align-items:flex-start}.doc-sheet-scale{transform-origin:top center;flex:none}.electronic-invoice-sheet{position:relative;width:210mm;min-height:297mm;overflow:hidden;background:#fff;color:#172033;padding:13mm;box-shadow:0 24px 70px rgba(0,0,0,.34);font-family:Parastoo,Tahoma,Arial,sans-serif;direction:rtl}.electronic-invoice-sheet:before{content:'';position:absolute;inset:0 0 auto;height:8mm;background:linear-gradient(90deg,#172033 0%,#1e3a5f 48%,#2563eb 73%,#0ea5e9 100%)}.invoice-watermark{position:absolute;top:122mm;left:18mm;transform:rotate(-28deg);font-size:74px;font-weight:950;color:rgba(37,99,235,.045)!important;pointer-events:none}.invoice-watermark.strong{color:rgba(190,18,60,.16)!important;font-size:60px}.invoice-status.cancelled{background:#fee2e2;color:#b91c1c}.invoice-status.superseded{background:#f1f5f9;color:#475569}.invoice-hero{position:relative;margin-top:6mm;display:flex;align-items:flex-start;justify-content:space-between;gap:8mm;padding-bottom:7mm;border-bottom:1px solid #dbe4ee}.invoice-identity{display:flex;align-items:flex-start;gap:4mm;min-width:0}.invoice-logo{width:19mm;height:19mm;border-radius:6mm;background:linear-gradient(135deg,#172033,#1e3a5f);display:grid;place-items:center;color:#fff;overflow:hidden;flex:none}.invoice-logo img{width:100%;height:100%;object-fit:contain;background:#fff;padding:2mm}.invoice-logo span{font-size:22px;font-weight:950;color:#fff!important}.invoice-overline{margin:0 0 1mm;font-size:8px;font-weight:950;color:#2563eb!important}.invoice-identity h2{margin:0;font-size:19px;line-height:1.35;font-weight:950;color:#172033!important}.invoice-identity p:last-child{margin:1mm 0 0;font-size:9.5px;color:#64748b!important}.invoice-seal{width:34mm;height:34mm;border:1.4px dashed #2563eb;border-radius:50%;display:grid;place-items:center;text-align:center;color:#1d4ed8;background:#eff6ff}.seal-ring{width:13mm;height:13mm;border-radius:50%;display:grid;place-items:center;color:#2563eb}.invoice-seal strong{font-size:9px;color:#1d4ed8!important}.invoice-seal span{font-size:7.5px;font-weight:900;color:#0f172a!important}.invoice-title-band{margin-top:5mm;display:flex;align-items:center;justify-content:space-between;gap:6mm;padding:5mm;border-radius:5mm;background:linear-gradient(135deg,#f8fafc,#eef6ff);border:1px solid #dbeafe}.invoice-title-band p{margin:0;color:#64748b!important;font-size:10px;font-weight:900}.invoice-title-band h1{margin:1mm 0 0;font-size:23px;font-weight:950;color:#172033!important}.invoice-status-block{text-align:left}.invoice-status{display:inline-flex;align-items:center;justify-content:center;padding:2mm 4mm;border-radius:999px;font-size:9px;font-weight:950}.invoice-status.draft{background:#f1f5f9;color:#475569}.invoice-status.unpaid{background:#fee2e2;color:#b91c1c}.invoice-status.partial{background:#fef3c7;color:#92400e}.invoice-status.paid{background:#d1fae5;color:#047857}.invoice-status.deferred{background:#dbeafe;color:#1d4ed8}.invoice-status-block small{display:block;margin-top:2mm;color:#64748b!important;font-size:8.5px;font-weight:800}.invoice-contact-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:3.5mm;margin-top:5mm}.invoice-info-card{border:1px solid #e2e8f0;border-radius:4mm;padding:3.5mm;background:#fff}.invoice-info-card h3{display:flex;align-items:center;gap:1.5mm;margin:0 0 2.5mm;font-size:10.5px;font-weight:950;color:#172033!important}.invoice-info-card h3 svg{color:#2563eb}.invoice-info-line{display:flex;justify-content:space-between;gap:3mm;padding:1.5mm 0;border-bottom:1px dashed #edf2f7;font-size:9px}.invoice-info-line:last-child{border-bottom:0}.invoice-info-line span{color:#64748b!important;font-weight:800}.invoice-info-line strong{color:#172033!important;font-weight:950;text-align:left;word-break:break-word}.invoice-table-section{margin-top:5mm}.section-heading{display:flex;align-items:center;gap:2mm;margin-bottom:2mm;color:#172033;font-size:11px;font-weight:950}.section-heading svg{color:#2563eb}.invoice-items-table{width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed;overflow:hidden;border:1px solid #dbe4ee;border-radius:3mm;font-size:8.7px}.invoice-items-table th{background:#172033;color:#fff!important;padding:2.2mm;border-left:1px solid rgba(255,255,255,.12);font-weight:950}.invoice-items-table td{padding:2.2mm;border-left:1px solid #e2e8f0;border-top:1px solid #e2e8f0;text-align:center;vertical-align:top;color:#172033!important;word-break:break-word}.invoice-items-table th:nth-child(2),.invoice-items-table td:nth-child(2){width:34%;text-align:right}.invoice-items-table tbody tr:nth-child(even) td{background:#f8fafc}.invoice-items-table .item-desc{font-weight:850}.invoice-items-table .strong{font-weight:950;color:#0f172a!important}.empty-table{text-align:center!important;color:#94a3b8!important;padding:8mm!important}.invoice-bottom-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:4mm;margin-top:5mm}.invoice-notes{padding:4mm;border-radius:4mm;border:1px solid #e2e8f0;background:#f8fafc}.invoice-notes h3{margin:0 0 1mm;font-size:10.5px;font-weight:950;color:#172033!important}.invoice-notes p{margin:0 0 3mm;font-size:9px;line-height:1.8;color:#475569!important}.amount-words{margin-top:2mm;padding:2.5mm;border-radius:3mm;background:#fff;border:1px dashed #bfdbfe;color:#172033!important;font-size:9px}.amount-words strong{color:#1d4ed8!important}.invoice-totals-card{border:1px solid #dbe4ee;border-radius:4mm;overflow:hidden;background:#fff}.invoice-total-line{display:flex;align-items:center;justify-content:space-between;gap:3mm;padding:2.3mm 3mm;border-bottom:1px solid #edf2f7;font-size:9.5px}.invoice-total-line:last-child{border-bottom:0}.invoice-total-line span{color:#64748b!important;font-weight:850}.invoice-total-line strong{color:#172033!important;font-weight:950}.invoice-total-line.accent{background:linear-gradient(135deg,#172033,#1e3a5f)}.invoice-total-line.accent span,.invoice-total-line.accent strong{color:#fff!important}.invoice-total-line.accent strong{font-size:13px}.invoice-signature-grid{display:grid;grid-template-columns:1fr 1fr 28mm;gap:4mm;margin-top:6mm;align-items:stretch}.signature-box{height:22mm;border:1px dashed #94a3b8;border-radius:3mm;background:#fff;display:flex;align-items:flex-end;justify-content:center;padding-bottom:2mm}.signature-box span{font-size:9px;font-weight:900;color:#64748b!important}.qr-box{height:22mm;border:1px solid #dbe4ee;border-radius:3mm;display:grid;place-items:center;background:#f8fafc}.qr-box div{width:13mm;height:13mm;background:repeating-linear-gradient(45deg,#172033 0 2px,#fff 2px 4px)}.qr-box span{font-size:7px;font-weight:900;color:#64748b!important}.invoice-footer{position:absolute;left:13mm;right:13mm;bottom:9mm;display:flex;justify-content:space-between;align-items:center;gap:4mm;padding-top:3mm;border-top:1px solid #dbe4ee;font-size:8.2px;color:#64748b!important}.invoice-footer strong{color:#172033!important}.invoice-footer span{color:#64748b!important}@keyframes docRise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}@media(max-width:1180px){.doc-workspace{grid-template-columns:1fr}.doc-preview-panel{position:relative;top:0;height:76vh}.doc-type-grid,.doc-actions-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:720px){.document-print-page{padding:10px}.doc-shell-header{position:relative;top:0;align-items:flex-start;flex-direction:column}.doc-header-actions{width:100%;justify-content:flex-start}.doc-grid.two,.doc-summary-strip,.doc-type-grid,.doc-actions-grid{grid-template-columns:1fr}.doc-item-row{grid-template-columns:1fr}.doc-remove-button{width:100%}.doc-preview-viewport{padding:12px;justify-content:flex-start}.doc-preview-panel{height:70vh}.doc-shell-header h1{font-size:20px}.doc-brand-icon{width:46px;height:46px}}@media print{.document-print-page{background:#fff!important;padding:0!important}.doc-shell-header,.doc-editor,.doc-preview-toolbar{display:none!important}.doc-workspace{display:block;margin:0;max-width:none}.doc-preview-panel{position:static;height:auto;border:0;border-radius:0;box-shadow:none;background:#fff;overflow:visible}.doc-preview-viewport{height:auto;overflow:visible;padding:0;display:block}.doc-sheet-scale{transform:none!important;height:auto!important}.electronic-invoice-sheet{width:210mm;min-height:297mm;box-shadow:none;margin:0;padding:13mm;page-break-after:always}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}@page{size:A4;margin:0}}
`;

const printOverrides = `
.invoice-header-meta{min-width:42mm;text-align:left;display:grid;gap:2mm;padding-top:2mm}.invoice-header-meta strong{font-size:12px;color:#172033!important}.invoice-header-meta span{font-size:8.5px;color:#64748b!important}.invoice-approval-area{margin-top:5mm;min-height:4mm}.invoice-seal-row{display:flex;justify-content:flex-start;gap:5mm}.dynamic-electronic-seal{width:27mm;height:27mm;border:1.2px solid #0f766e;border-radius:50%;background:#f0fdfa;color:#115e59;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:2mm;line-height:1.15}.dynamic-electronic-seal svg{color:#0f766e}.dynamic-electronic-seal strong{font-size:8px;color:#115e59!important}.dynamic-electronic-seal span{font-size:7px;font-weight:950;color:#172033!important;max-width:22mm;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.dynamic-electronic-seal small,.dynamic-electronic-seal em{font-size:5.8px;font-style:normal;color:#475569!important;direction:rtl}.seal-invalidated{margin:0;padding:2.5mm 3mm;background:#fff7ed;border:1px solid #fdba74;border-radius:2mm;color:#9a3412!important;font-size:8px;font-weight:900}.invoice-footer{bottom:7mm;display:grid;grid-template-columns:1fr auto 1fr;align-items:end;gap:4mm;font-size:7.4px}.invoice-footer strong{text-align:center}.invoice-footer>span:first-child{text-align:right}.invoice-barcode{justify-self:end;display:grid;gap:1mm;max-width:48mm;text-align:left}.barcode-bars{height:8mm;display:flex;align-items:stretch;gap:1px;background:#fff;padding:1px}.barcode-bars i{display:block;height:100%;background:#172033}.invoice-barcode span{font-size:5.4px;line-height:1.1;word-break:break-all;direction:ltr}@media print{.invoice-approval-area{break-inside:avoid}.invoice-footer{display:grid}}
`;