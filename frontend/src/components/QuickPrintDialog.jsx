import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API_BASE, api } from '../services/api';
import { downloadPDF } from '../utils/pdfGenerator';
import { loadWorkshopPrintInfo } from '../utils/workshopPrintInfo';
import { useWhatsAppShare } from '../hooks/useWhatsAppShare';
import WhatsAppSharePreview from './WhatsAppSharePreview';

const DOC_TYPE_LABELS = { invoice: 'فاتورة', diagnosis: 'تقرير تشخيص', quote: 'عرض سعر', receipt: 'سند زيارة' };
const money = (value) => `${Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ر.س`;
const escapeHtml = (value) => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
const sealCode = (number) => {
  const seed = `${number || 'DOC'}-${new Date().toISOString().slice(0, 10)}`;
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = ((hash << 5) - hash) + seed.charCodeAt(i);
  return `ES-${Math.abs(hash).toString(16).slice(0, 8).toUpperCase()}`;
};
const normalizeRows = (items = []) => (Array.isArray(items) ? items : []).map((item) => {
  const quantity = Number(item.quantity || item.qty || 1);
  const price = Number(item.unit_price || item.price || item.amount || 0);
  const discount = Number(item.discount || 0);
  const total = Number(item.total || (quantity * price) - discount);
  return { ...item, quantity, price, discount, total, description: item.description || item.name || item.itemName || 'بند' };
});
const renderTemplateHtml = (templateHtml, payload = {}, workshop = {}) => {
  const settings = payload.settings || {};
  const customer = payload.customer || payload.client || {};
  const supplier = payload.supplier || {};
  const party = customer.name ? customer : supplier;
  const vehicle = payload.vehicle || {};
  const rows = normalizeRows(payload.items || []);
  const subtotal = rows.reduce((sum, item) => sum + (item.quantity * item.price), 0);
  const discount = rows.reduce((sum, item) => sum + item.discount, 0);
  const total = rows.reduce((sum, item) => sum + item.total, 0);
  const paid = Number(settings?.totals?.paid || payload?.payment?.paid || 0);
  const remaining = total - paid;
  const docNumber = settings.document_number || payload.document_number || `DOC-${Date.now().toString().slice(-6)}`;
  const itemsRows = rows.length ? rows.map((item, idx) => `<tr><td>${idx + 1}</td><td class="desc">${escapeHtml(item.description)}</td><td>${escapeHtml(item.quantity)}</td><td>${money(item.price)}</td><td>${item.discount ? money(item.discount) : '—'}</td><td><b>${money(item.total)}</b></td></tr>`).join('') : '<tr><td colspan="6" style="text-align:center;padding:18px;color:#94a3b8">لا توجد بنود</td></tr>';
  const values = {
    WORKSHOP_NAME: workshop.name || workshop.business_name || 'الورشة', WORKSHOP_ADDRESS: workshop.address || '', WORKSHOP_PHONE: workshop.phone || workshop.whatsapp || '', WORKSHOP_EMAIL: workshop.email || '', COMPANY_CR: workshop.commercial_register || workshop.commercialRegister || '', COMPANY_TAX: workshop.tax_number || workshop.taxNumber || '', TAX_NUMBER: workshop.tax_number || workshop.taxNumber || '', CUSTOMER_NAME: party.name || party.customerName || 'عميل نقدي', CUSTOMER_PHONE: party.phone || party.customerPhone || '', VEHICLE_INFO: `${vehicle.brand || ''} ${vehicle.model || ''} ${vehicle.year || ''}`.trim(), PLATE_NO: vehicle.plateNumber || vehicle.plate || '', VEHICLE_PLATE: vehicle.plateNumber || vehicle.plate || '', STATUS_LABEL: settings.status || 'مسودة', INVOICE_NO: docNumber, INVOICE_DATE: settings.date || payload.date || new Date().toISOString().slice(0, 10), DATE: settings.date || payload.date || new Date().toISOString().slice(0, 10), ITEMS_ROWS: itemsRows, SUBTOTAL: money(subtotal), DISCOUNT: money(discount), TAX: money(0), TOTAL: money(total), PAID: money(paid), REMAINING: money(remaining), NOTES: settings.notes || payload.notes || '', AMOUNT_WORDS: `فقط ${money(total)} لا غير`, SEAL_CODE: sealCode(docNumber),
  };
  let html = templateHtml || '';
  Object.entries(values).forEach(([key, value]) => { html = html.replaceAll(`{{${key}}}`, String(value)); });
  return html.replace(/{{[^}]+}}/g, '');
};

const QuickPrintDialog = ({
  open,
  title = 'إجراء الطباعة',
  description = 'معاينة المستند قبل الطباعة أو الإرسال.',
  payloadBuilder,
  initialPhone = '',
  onClose,
}) => {
  const [loading, setLoading] = useState(false);
  const [html, setHtml] = useState('');
  const [error, setError] = useState('');
  const [phone, setPhone] = useState(initialPhone || '');
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [templateLoading, setTemplateLoading] = useState(false);
  const iframeRef = useRef(null);
  const payloadBuilderRef = useRef(payloadBuilder);
  const generationStartedRef = useRef(false);
  const lastPayloadRef = useRef(null);
  const { share, prepare: prepareShare, reset: resetShare, logEvent: logShareEvent } = useWhatsAppShare();

  useEffect(() => {
    payloadBuilderRef.current = payloadBuilder;
  }, [payloadBuilder]);

  const runWithTimeout = useCallback((promise, timeoutMs = 15000) => {
    return Promise.race([
      promise,
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('timeout')), timeoutMs)
      ),
    ]);
  }, []);

  const currentDocType = useMemo(() => {
    const text = String(title || '');
    if (text.includes('تشخيص')) return 'diagnosis';
    if (text.includes('عرض')) return 'quote';
    if (text.includes('سند') || text.includes('زيارة') || text.includes('إيصال')) return 'receipt';
    return 'invoice';
  }, [title]);

  const filteredTemplates = useMemo(() => templates.filter((tpl) => (tpl.type || 'invoice') === currentDocType && tpl.file_type === 'html'), [currentDocType, templates]);
  const selectedTemplate = useMemo(() => filteredTemplates.find((tpl) => tpl.id === selectedTemplateId) || filteredTemplates[0] || null, [filteredTemplates, selectedTemplateId]);

  const loadTemplates = useCallback(async () => {
    setTemplateLoading(true);
    try {
      const response = await api.get('/templates');
      const rows = Array.isArray(response.data?.templates) ? response.data.templates : [];
      setTemplates(rows);
      const sameType = rows.filter((tpl) => (tpl.type || 'invoice') === currentDocType && tpl.file_type === 'html');
      const preferred = sameType.find((tpl) => tpl.is_default || tpl.isActive) || sameType[0];
      setSelectedTemplateId(preferred?.id || '');
    } catch (e) {
      setTemplates([]);
      setSelectedTemplateId('');
    } finally {
      setTemplateLoading(false);
    }
  }, [currentDocType]);

  useEffect(() => {
    if (open) {
      setPhone(initialPhone || '');
      loadTemplates();
    } else {
      generationStartedRef.current = false;
      setLoading(false);
      setHtml('');
      setError('');
    }
  }, [open, initialPhone, loadTemplates]);

  const loadWorkshop = useCallback(async () => {
    // يستخدم الأداة المساعدة الموحَّدة لجلب بيانات الورشة (اسم/شعار/ضريبي/ت.تجاري/…)
    // ⚠️ المفتاح الصحيح هو `logo` (Base64) وليس `logo_url`. تم تصحيحه هنا.
    return await loadWorkshopPrintInfo(async (path) => {
      const response = await api.get(path);
      return { ok: true, json: async () => response.data };
    });
  }, []);

  const printStabilityCss = `
    <style id="quick-print-stability-css">
      @page { size: A4; margin: 10mm; }
      * { box-sizing: border-box; }
      html, body { margin: 0; padding: 0; background: #f8fafc; color: #0f172a; }
      body, button, input, table, div, span, p, h1, h2, h3, h4, th, td {
        font-family: "Tahoma", "Arial", "Segoe UI", sans-serif !important;
        letter-spacing: normal !important;
        word-spacing: normal !important;
        font-kerning: normal !important;
        text-rendering: optimizeLegibility !important;
        -webkit-font-smoothing: antialiased !important;
        direction: rtl;
      }
      body { font-size: 13px; line-height: 1.7; }
      table { width: 100% !important; border-collapse: collapse !important; table-layout: fixed; }
      th, td { word-break: break-word; overflow-wrap: anywhere; line-height: 1.65; }
      img { max-width: 100%; height: auto; }
      .container, .quotation-container, .document, .page, .invoice-container, .quotation-wrapper { max-width: 190mm !important; margin-left: auto !important; margin-right: auto !important; }
      [style*="letter-spacing"] { letter-spacing: normal !important; }
      [style*="font-family"] { font-family: "Tahoma", "Arial", "Segoe UI", sans-serif !important; }
      @media print { html, body { background: #fff; } }
    </style>`;

  const statusWatermarkBlock = (status) => {
    const raw = String(status || '').trim().toLowerCase();
    const label = ['draft', 'مسودة'].includes(raw)
      ? 'مسودة'
      : (['cancelled', 'canceled', 'ملغي', 'ملغاة'].includes(raw) ? 'ملغي' : '');
    if (!label) return '';
    return `<div class="qp-status-watermark" data-testid="quick-print-status-watermark">${label}</div><style>.qp-status-watermark{position:fixed;top:45%;left:50%;transform:translate(-50%,-50%) rotate(-24deg);font-size:110px;font-weight:900;color:rgba(190,18,60,.15);z-index:9999;pointer-events:none;white-space:nowrap}</style>`;
  };

  const wrapPrintableHtml = useCallback((rawHtml, status = '') => {
    if (!rawHtml) return '';
    const watermark = statusWatermarkBlock(status);
    if (/<html[\s>]/i.test(rawHtml)) {
      let full = rawHtml;
      if (!full.includes('quick-print-stability-css')) {
        if (/<head[\s>]/i.test(full)) {
          full = full.replace(/<head([^>]*)>/i, `<head$1>${printStabilityCss}`);
        } else {
          full = full.replace(/<html([^>]*)>/i, `<html$1><head>${printStabilityCss}</head>`);
        }
      }
      if (watermark && !full.includes('qp-status-watermark')) {
        full = /<\/body>/i.test(full) ? full.replace(/<\/body>/i, `${watermark}</body>`) : full + watermark;
      }
      return full;
    }
    return `<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  ${printStabilityCss}
</head>
<body><main class="print-shell">${rawHtml}</main>${watermark}</body></html>`;
  }, []);

  const htmlToCanvasWrapper = (htmlContent) => {
    const doc = new DOMParser().parseFromString(htmlContent, 'text/html');
    const wrapper = document.createElement('div');
    wrapper.innerHTML = doc.body?.innerHTML || htmlContent;
    wrapper.style.position = 'fixed';
    wrapper.style.left = '-10000px';
    wrapper.style.top = '0';
    wrapper.style.width = '794px';
    wrapper.style.background = '#ffffff';
    wrapper.style.direction = 'rtl';
    document.body.appendChild(wrapper);
    return wrapper;
  };

  const generateHtml = useCallback(async (builderOverride = null) => {
    const currentPayloadBuilder = builderOverride || payloadBuilderRef.current;
    if (!currentPayloadBuilder) {
      setLoading(false);
      setError('بيانات الطباعة غير جاهزة — أعد فتح المستند');
      return '';
    }
    setLoading(true);
    setError('');
    try {
      const basePayload = await runWithTimeout(currentPayloadBuilder(), 15000);
      if (!basePayload) {
        throw new Error('missing-payload');
      }
      const workshop = { ...(await loadWorkshop()), ...(basePayload.workshop || {}) };
      lastPayloadRef.current = { payload: basePayload, workshop };
      let rawHtml = '';
      if (selectedTemplate?.id) {
        const templateResponse = await runWithTimeout(api.post(`/templates/${selectedTemplate.id}/use`, {}, { timeout: 15000 }), 15000);
        rawHtml = renderTemplateHtml(templateResponse.data?.content || '', basePayload, workshop);
      } else {
        const response = await runWithTimeout(
          api.post('/documents/generate', { ...basePayload, workshop }, { timeout: 15000 }),
          15000
        );
        const data = response.data;
        if (!data?.success) {
          throw new Error(data?.error || 'failed');
        }
        rawHtml = data?.html || data?.data?.html || '';
      }
      const nextHtml = wrapPrintableHtml(rawHtml, basePayload?.settings?.status || basePayload?.status || '');
      if (!nextHtml) {
        throw new Error('empty');
      }
      setHtml(nextHtml);
      return nextHtml;
    } catch (e) {
      const message = e?.message === 'timeout' ? 'انتهت مهلة إنشاء المعاينة' : 'تعذر إنشاء المعاينة';
      setError(message);
      return '';
    } finally {
      setLoading(false);
    }
  }, [loadWorkshop, runWithTimeout, selectedTemplate?.id, wrapPrintableHtml]);

  useEffect(() => {
    if (!open) return;
    let isActive = true;
    setHtml('');
    setError('');
    setLoading(true);
    (async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
      const nextHtml = await generateHtml(payloadBuilderRef.current || payloadBuilder);
      if (!isActive) return;
      if (nextHtml) {
        setHtml(nextHtml);
      }
    })();
    return () => {
      isActive = false;
    };
  }, [open, payloadBuilder, generateHtml]);

  useEffect(() => {
    if (!open || !selectedTemplateId) return;
    generateHtml(payloadBuilderRef.current || payloadBuilder);
  }, [open, payloadBuilder, selectedTemplateId, generateHtml]);

  useEffect(() => {
    if (!open || !html || !iframeRef.current) return;
    try {
      const doc = iframeRef.current.contentDocument || iframeRef.current.contentWindow.document;
      doc.open();
      doc.write(html);
      doc.close();
    } catch (e) {
      // ignore
    }
  }, [open, html]);

  const getPrintableElement = async () => {
    const htmlContent = html || (await generateHtml());
    if (!htmlContent) return null;
    const wrapper = htmlToCanvasWrapper(htmlContent);
    return { wrapper, htmlContent };
  };

  const handlePrint = async () => {
    const htmlContent = html || (await generateHtml());
    if (!htmlContent) return;
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      alert('يبدو أن المتصفح منع فتح نافذة جديدة. الرجاء السماح بالنوافذ المنبثقة مؤقتًا.');
      return;
    }
    printWindow.document.open();
    printWindow.document.write(htmlContent);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => printWindow.print(), 600);
  };

  const handleDownloadPdf = async () => {
    const printable = await getPrintableElement();
    if (!printable) return;
    try {
      await downloadPDF(printable.wrapper, `${title.replace(/\s+/g, '_')}.pdf`, {
        backgroundColor: '#ffffff',
        scale: 1.6,
      });
    } finally {
      printable.wrapper.remove();
    }
  };

  const handlePdfWhatsApp = async () => {
    const htmlContent = html || (await generateHtml());
    if (!htmlContent) return;
    const meta = lastPayloadRef.current || {};
    await prepareShare({
      docType: currentDocType,
      payload: meta.payload || {},
      workshop: meta.workshop || {},
      templateId: selectedTemplate?.id || 'unified-generator',
      templateVersion: selectedTemplate?.created_at || selectedTemplate?.updated_at || 'v1',
      phone,
      fileBaseName: `${title.replace(/\s+/g, '_')}`,
      context: 'quick-print-dialog',
      getElement: async () => {
        const wrapper = htmlToCanvasWrapper(htmlContent);
        return { element: wrapper, cleanup: () => wrapper.remove() };
      },
    });
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" data-testid="quick-print-dialog">
      <div className="w-full max-w-5xl rounded-3xl border border-white/10 bg-slate-950/90 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-white" data-testid="quick-print-dialog-title">{title}</h3>
            <p className="mt-1 text-sm text-slate-300" data-testid="quick-print-dialog-description">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-white/10 px-4 py-2 text-sm text-slate-200"
            data-testid="quick-print-action-cancel"
          >
            إغلاق
          </button>
        </div>

        <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-4" data-testid="quick-print-template-selector">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-bold text-white" data-testid="quick-print-template-selector-title">اختر نموذج الطباعة</div>
              <div className="text-xs text-slate-400" data-testid="quick-print-template-selector-subtitle">{DOC_TYPE_LABELS[currentDocType]} · يظهر هذا الخيار عند كل زر طباعة</div>
            </div>
            <button
              type="button"
              onClick={loadTemplates}
              className="rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-white/10"
              data-testid="quick-print-reload-templates"
            >
              تحديث النماذج
            </button>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {templateLoading && <div className="text-sm text-slate-300" data-testid="quick-print-templates-loading">جارٍ تحميل النماذج...</div>}
            {!templateLoading && filteredTemplates.map((tpl) => (
              <button
                key={tpl.id}
                type="button"
                onClick={() => setSelectedTemplateId(tpl.id)}
                className={`rounded-xl border p-3 text-right transition ${selectedTemplateId === tpl.id ? 'border-sky-300 bg-sky-400/15' : 'border-white/10 bg-black/20 hover:bg-white/10'}`}
                data-testid={`quick-print-template-option-${tpl.id}`}
              >
                <div className="text-sm font-bold text-white">{tpl.name}</div>
                <div className="mt-1 text-xs text-slate-400">{tpl.is_builtin ? 'افتراضي جديد' : 'مرفوع'} {tpl.is_default || tpl.isActive ? '· مستخدم حالياً' : ''}</div>
              </button>
            ))}
          </div>
          {!templateLoading && filteredTemplates.length === 0 && <div className="text-sm text-amber-200" data-testid="quick-print-no-templates">لا يوجد نموذج HTML لهذا النوع، سيتم استخدام مولد المستندات.</div>}
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handlePrint}
            className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-400"
            data-testid="quick-print-action-print"
            disabled={loading}
          >
            طباعة فورية
          </button>
          <button
            type="button"
            onClick={handlePdfWhatsApp}
            className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-400"
            data-testid="quick-print-action-whatsapp"
            disabled={loading || share.stage === 'preparing'}
          >
            {share.stage === 'preparing' ? 'جارٍ التجهيز...' : 'PDF وواتساب'}
          </button>
          <button
            type="button"
            onClick={handleDownloadPdf}
            className="rounded-lg bg-white/10 px-4 py-2 text-sm font-semibold text-slate-100 hover:bg-white/15"
            data-testid="quick-print-action-download-pdf"
            disabled={loading}
          >
            تحميل PDF
          </button>
          <div className="flex items-center gap-2 text-sm text-slate-300">
            <span>رقم الجوال</span>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white"
              placeholder="05xxxxxxxx"
              data-testid="quick-print-phone-input"
            />
          </div>
        </div>

        <div className="mt-5 rounded-2xl border border-white/10 bg-black/40 p-3">
          {loading && <div className="text-sm text-slate-300" data-testid="quick-print-loading">جارٍ تجهيز المعاينة...</div>}
          {error && (
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-rose-300" data-testid="quick-print-error">
              <span>{error}</span>
              <button
                type="button"
                onClick={generateHtml}
                className="rounded-lg border border-rose-200/30 px-3 py-1 text-xs text-rose-200"
                data-testid="quick-print-retry"
              >
                إعادة المحاولة
              </button>
            </div>
          )}
          {!loading && !error && html && (
            <iframe
              ref={iframeRef}
              title="print-preview"
              className="h-[420px] w-full rounded-xl bg-white"
              data-testid="quick-print-preview"
              srcDoc={html}
            />
          )}
        </div>
      </div>
      <WhatsAppSharePreview share={share} onClose={resetShare} logEvent={logShareEvent} />
    </div>
  );
};

export default QuickPrintDialog;