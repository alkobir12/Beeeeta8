import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../services/api';
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
    }
  }, [open, initialPhone]);

  const loadWorkshop = useCallback(async () => {
    // يستخدم الأداة المساعدة الموحَّدة لجلب بيانات الورشة (اسم/شعار/ضريبي/ت.تجاري/…)
    // ⚠️ المفتاح الصحيح هو `logo` (Base64) وليس `logo_url`. تم تصحيحه هنا.
    return await loadWorkshopPrintInfo(async (path) => {
      return await fetch(`${API_BASE}${path}`);
    });
  }, []);

  const generateHtml = useCallback(async () => {
    if (!payloadBuilder) return '';
    setLoading(true);
    setError('');
    try {
      const basePayload = await runWithTimeout(payloadBuilder(), 15000);
      if (!basePayload) {
        throw new Error('missing-payload');
      }
      const workshop = await loadWorkshop();
      const response = await runWithTimeout(fetch(`${API_BASE}/documents/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...basePayload, workshop }),
      }), 15000);
      const data = await response.json();
      if (!data?.success) {
        throw new Error(data?.error || 'failed');
      }
      const nextHtml = data?.html || data?.data?.html || '';
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
  }, [payloadBuilder, loadWorkshop]);

  useEffect(() => {
    if (!open || !payloadBuilder) return;
    let isActive = true;
    (async () => {
      const nextHtml = await generateHtml();
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

  const handleWhatsApp = async () => {
    const htmlContent = html || (await generateHtml());
    if (!htmlContent) return;
    const wrapper = document.createElement('div');
    wrapper.innerHTML = htmlContent;
    wrapper.style.position = 'fixed';
    wrapper.style.left = '-10000px';
    wrapper.style.top = '0';
    wrapper.style.width = '794px';
    document.body.appendChild(wrapper);
    await downloadPDF(wrapper, title.replace(/\s+/g, '_'), {
      backgroundColor: '#ffffff',
      scale: 1.4,
    });
    document.body.removeChild(wrapper);
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
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default QuickPrintDialog;