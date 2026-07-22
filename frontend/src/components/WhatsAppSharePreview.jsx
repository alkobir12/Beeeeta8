import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Copy, Download, Loader2, MessageCircle, Save, Share2, X } from 'lucide-react';
import { downloadBlob, normalizePhoneLocal, saveCustomerPhone } from '../services/outboundShare';

const WhatsAppSharePreview = ({ share, onClose, logEvent }) => {
  const [phone, setPhone] = useState('');
  const [message, setMessage] = useState('');
  const [notice, setNotice] = useState('');
  const [savingPhone, setSavingPhone] = useState(false);

  useEffect(() => {
    if (share.stage === 'ready') {
      setPhone(share.initialPhone || share.phone?.raw || '');
      setMessage(share.message || '');
      setNotice('');
    }
  }, [share.stage, share.initialPhone, share.message, share.phone]);

  const norm = useMemo(() => normalizePhoneLocal(phone), [phone]);

  const files = useMemo(() => {
    const list = [];
    if (share.pdfBlob) list.push(new File([share.pdfBlob], `${share.fileBaseName || 'document'}.pdf`, { type: 'application/pdf' }));
    if (share.imageBlob) list.push(new File([share.imageBlob], `${share.fileBaseName || 'document'}.jpg`, { type: 'image/jpeg' }));
    return list;
  }, [share.pdfBlob, share.imageBlob, share.fileBaseName]);

  const canShareFiles = useMemo(() => {
    try {
      return Boolean(typeof navigator !== 'undefined' && navigator.canShare && files.length && navigator.canShare({ files }));
    } catch (e) {
      return false;
    }
  }, [files]);

  if (!share.stage || share.stage === 'idle') return null;

  const handleShareFiles = async () => {
    if (!files.length) return;
    logEvent('share_sheet_opened', { files: String(files.length) });
    try {
      await navigator.share({ files, text: message });
      setNotice('فُتحت نافذة المشاركة — اختر واتساب لإرفاق الملفات. لا يعني هذا تأكيد التسليم.');
    } catch (error) {
      if (error?.name === 'AbortError') logEvent('user_cancelled', { at: 'share_sheet' });
    }
  };

  const handleOpenWaMe = () => {
    if (!norm.valid) return;
    logEvent('whatsapp_opened', { phone: norm.e164 });
    window.open(`https://wa.me/${norm.wa}?text=${encodeURIComponent(message)}`, '_blank');
    setNotice('فُتح واتساب بنص الرسالة فقط — أرفق ملف PDF يدوياً داخل المحادثة.');
  };

  const handleDownload = () => {
    if (share.pdfBlob) downloadBlob(share.pdfBlob, `${share.fileBaseName || 'document'}.pdf`);
    if (share.imageBlob) downloadBlob(share.imageBlob, `${share.fileBaseName || 'document'}.jpg`);
    logEvent('files_downloaded', {});
    setNotice('تم تنزيل الملفات — أرفقها يدوياً في محادثة واتساب.');
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message);
      logEvent('text_copied', {});
      setNotice('تم نسخ نص الرسالة.');
    } catch (e) {
      setNotice('تعذر النسخ التلقائي — انسخ النص يدوياً.');
    }
  };

  const handleSavePhone = async () => {
    if (!share.customerId || !norm.valid) return;
    if (!window.confirm(`حفظ الرقم ${norm.e164} في ملف العميل بشكل دائم؟`)) return;
    setSavingPhone(true);
    try {
      await saveCustomerPhone(share.customerId, norm.e164);
      logEvent('phone_saved_to_customer', { phone: norm.e164 });
      setNotice('تم حفظ الرقم في ملف العميل.');
    } catch (e) {
      setNotice('تعذر حفظ الرقم في ملف العميل — تحقق من الصلاحية.');
    } finally {
      setSavingPhone(false);
    }
  };

  const handleClose = () => {
    if (share.stage === 'ready') logEvent('user_cancelled', { at: 'preview' });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 p-3 sm:p-5" dir="rtl" data-testid="whatsapp-share-preview">
      <div className="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl border border-white/10 bg-slate-950 shadow-2xl">
        <div className="flex items-center justify-between gap-3 border-b border-white/10 bg-gradient-to-l from-emerald-600/25 to-transparent px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-2xl bg-emerald-500/20 text-emerald-300"><MessageCircle size={22} /></span>
            <div>
              <h3 className="text-base font-bold text-white" data-testid="whatsapp-share-title">معاينة الإرسال — PDF وواتساب</h3>
              <p className="text-xs text-slate-400" data-testid="whatsapp-share-subtitle">
                {share.documentNumber ? `مستند ${share.documentNumber}` : 'مستند الورشة'}
                {share.cached ? ' · ♻️ أُعيد استخدام الملف من الكاش (نفس البصمة)' : ''}
              </p>
            </div>
          </div>
          <button type="button" onClick={handleClose} className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 text-slate-300 hover:bg-white/10" data-testid="whatsapp-share-close">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {share.stage === 'preparing' && (
            <div className="flex flex-col items-center gap-3 py-14 text-slate-300" data-testid="whatsapp-share-preparing">
              <Loader2 size={34} className="animate-spin text-emerald-400" />
              <span className="text-sm font-semibold">جارٍ تجهيز PDF وصورة المعاينة والرسالة...</span>
            </div>
          )}

          {share.stage === 'error' && (
            <div className="flex flex-col items-center gap-3 py-10 text-center" data-testid="whatsapp-share-error">
              <span className="grid h-14 w-14 place-items-center rounded-2xl bg-rose-500/15 text-rose-300"><AlertTriangle size={28} /></span>
              <p className="max-w-sm text-sm font-bold text-rose-200" data-testid="whatsapp-share-error-message">{share.message}</p>
              <button type="button" onClick={handleClose} className="rounded-xl border border-white/15 px-5 py-2 text-sm font-semibold text-slate-200 hover:bg-white/10" data-testid="whatsapp-share-error-close">إغلاق</button>
            </div>
          )}

          {share.stage === 'ready' && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-amber-400/25 bg-amber-500/10 px-4 py-3 text-xs font-semibold leading-6 text-amber-200" data-testid="whatsapp-share-honesty-note">
                ⚠️ واتساب لا يستقبل المرفقات تلقائياً عبر الرابط. على الجوال استخدم «مشاركة الملفات» لإرفاق PDF والصورة عبر نافذة النظام، وعلى الكمبيوتر نزّل الملفات وأرفقها يدوياً في المحادثة.
              </div>

              <div className="grid gap-4 sm:grid-cols-[150px_minmax(0,1fr)]">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-2" data-testid="whatsapp-share-thumbnail-box">
                  {share.imageDataUrl ? (
                    <img src={share.imageDataUrl} alt="معاينة المستند" className="h-44 w-full rounded-xl bg-white object-contain object-top" data-testid="whatsapp-share-thumbnail" />
                  ) : (
                    <div className="grid h-44 place-items-center text-xs text-slate-400">لا توجد صورة معاينة</div>
                  )}
                  <p className="mt-2 text-center text-[11px] font-semibold text-slate-400">PDF + صورة معاينة جاهزان</p>
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="mb-1 flex items-center justify-between text-xs font-bold text-slate-300">
                      <span>نص الرسالة {share.allowEdit ? '(قابل للتعديل)' : '(قالب ثابت — التعديل معطل)'}</span>
                      {share.template?.action_key && <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-300" data-testid="whatsapp-share-template-key">{share.template.action_key} · v{share.template.version}</span>}
                    </label>
                    <textarea
                      value={message}
                      onChange={(e) => share.allowEdit && setMessage(e.target.value)}
                      readOnly={!share.allowEdit}
                      rows={7}
                      className="w-full rounded-2xl border border-white/10 bg-black/40 p-3 text-sm leading-7 text-slate-100 outline-none focus:border-emerald-400/50"
                      data-testid="whatsapp-share-message-input"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-bold text-slate-300">رقم الجوال (تعديل مؤقت — لا يغيّر ملف العميل)</label>
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="05xxxxxxxx"
                        className="min-w-[160px] flex-1 rounded-xl border border-white/10 bg-black/40 px-3 py-2.5 text-sm text-white outline-none focus:border-emerald-400/50"
                        data-testid="whatsapp-share-phone-input"
                      />
                      {share.customerId && (
                        <button type="button" onClick={handleSavePhone} disabled={!norm.valid || savingPhone} className="inline-flex items-center gap-1.5 rounded-xl border border-sky-400/30 bg-sky-500/10 px-3 py-2.5 text-xs font-bold text-sky-200 hover:bg-sky-500/20 disabled:opacity-40" data-testid="whatsapp-share-save-phone-button">
                          <Save size={14} /> حفظ الرقم في ملف العميل
                        </button>
                      )}
                    </div>
                    {norm.valid ? (
                      <p className="mt-1 text-[11px] font-semibold text-emerald-300" data-testid="whatsapp-share-phone-normalized">الرقم بعد التطبيع: {norm.e164}</p>
                    ) : (
                      <p className="mt-1 text-[11px] font-semibold text-rose-300" data-testid="whatsapp-share-phone-invalid">رقم غير صالح — المشاركة عبر واتساب معطلة حتى إدخال رقم سعودي/دولي صحيح</p>
                    )}
                  </div>
                </div>
              </div>

              {notice && <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-200" data-testid="whatsapp-share-notice">{notice}</div>}

              <div className="grid gap-2 sm:grid-cols-2">
                {canShareFiles && (
                  <button type="button" onClick={handleShareFiles} className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-2xl bg-emerald-500 px-4 text-sm font-black text-white hover:bg-emerald-400" data-testid="whatsapp-share-files-button">
                    <Share2 size={18} /> مشاركة الملفات (PDF + صورة)
                  </button>
                )}
                <button type="button" onClick={handleOpenWaMe} disabled={!norm.valid} className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-2xl border border-emerald-400/40 bg-emerald-500/15 px-4 text-sm font-black text-emerald-200 hover:bg-emerald-500/25 disabled:cursor-not-allowed disabled:opacity-40" data-testid="whatsapp-share-wame-button">
                  <MessageCircle size={18} /> فتح واتساب (النص فقط)
                </button>
                <button type="button" onClick={handleDownload} className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-2xl border border-white/15 bg-white/5 px-4 text-sm font-bold text-slate-100 hover:bg-white/10" data-testid="whatsapp-share-download-button">
                  <Download size={18} /> تنزيل PDF والصورة
                </button>
                <button type="button" onClick={handleCopy} className="inline-flex min-h-[48px] items-center justify-center gap-2 rounded-2xl border border-white/15 bg-white/5 px-4 text-sm font-bold text-slate-100 hover:bg-white/10" data-testid="whatsapp-share-copy-button">
                  <Copy size={18} /> نسخ نص الرسالة
                </button>
              </div>

              <button type="button" onClick={handleClose} className="w-full rounded-2xl border border-white/10 px-4 py-3 text-sm font-semibold text-slate-300 hover:bg-white/5" data-testid="whatsapp-share-cancel-button">
                إلغاء
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default WhatsAppSharePreview;
