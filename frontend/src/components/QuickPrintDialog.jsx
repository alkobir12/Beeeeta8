import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE, api } from '../services/api';
import { downloadPDF } from '../utils/pdfGenerator';
import { getWhatsAppLink } from '../utils/constants';
import { loadWorkshopPrintInfo } from '../utils/workshopPrintInfo';

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
  const iframeRef = useRef(null);
  const payloadBuilderRef = useRef(payloadBuilder);
  const generationStartedRef = useRef(false);

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

  useEffect(() => {
    if (open) {
      setPhone(initialPhone || '');
    } else {
      generationStartedRef.current = false;
      setLoading(false);
      setHtml('');
      setError('');
    }
  }, [open, initialPhone]);

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

  const wrapPrintableHtml = useCallback((rawHtml) => {
    if (!rawHtml) return '';
    if (/<html[\s>]/i.test(rawHtml)) {
      if (rawHtml.includes('quick-print-stability-css')) return rawHtml;
      if (/<head[\s>]/i.test(rawHtml)) {
        return rawHtml.replace(/<head([^>]*)>/i, `<head$1>${printStabilityCss}`);
      }
      return rawHtml.replace(/<html([^>]*)>/i, `<html$1><head>${printStabilityCss}</head>`);
    }
    return `<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  ${printStabilityCss}
</head>
<body><main class="print-shell">${rawHtml}</main></body></html>`;
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
      const response = await runWithTimeout(
        api.post('/documents/generate', { ...basePayload, workshop }, { timeout: 15000 }),
        15000
      );
      const data = response.data;
      if (!data?.success) {
        throw new Error(data?.error || 'failed');
      }
      const nextHtml = wrapPrintableHtml(data?.html || data?.data?.html || '');
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
  }, [loadWorkshop, runWithTimeout, wrapPrintableHtml]);

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

  const handleWhatsApp = async () => {
    await handleDownloadPdf();
    if (!phone) {
      alert('يرجى إدخال رقم الجوال لإرسال واتس اب');
      return;
    }
    const message = `تم تجهيز المستند: ${title}. الرجاء إرفاق ملف PDF.`;
    window.open(getWhatsAppLink(phone, message), '_blank');
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
            onClick={handleWhatsApp}
            className="rounded-lg bg-emerald-500/20 px-4 py-2 text-sm font-semibold text-emerald-200 hover:bg-emerald-500/30"
            data-testid="quick-print-action-whatsapp"
            disabled={loading}
          >
            إرسال PDF عبر واتس اب
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
    </div>
  );
};

export default QuickPrintDialog;