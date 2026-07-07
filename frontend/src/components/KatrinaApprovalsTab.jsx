/**
 * 🤖 اعتمادات كاترينا — صندوق اعتمادات الأربع أعين (Action Runtime)
 * يعرض العمليات المعلقة من البوت ويتيح اعتمادها/رفضها (المُعتمِد ≠ المُقترِح).
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Bot, RefreshCw, Check, X, Clock, AlertTriangle } from 'lucide-react';

const RUNTIME_API = (process.env.REACT_APP_BACKEND_URL || '') + '/api/runtime';

const ACTION_LABELS = {
  customer: 'إنشاء عميل', vehicle: 'إنشاء مركبة', visit: 'فتح زيارة',
  supplier: 'إنشاء مورد', close_visits: 'إغلاق زيارات',
  delete_operation: 'حذف عملية', delete_customer: 'حذف عميل', delete_vehicle: 'حذف مركبة',
  update_customer: 'تعديل عميل', update_vehicle: 'تعديل مركبة',
  invoice: 'فاتورة', payment: 'تحصيل دفعة', expense: 'مصروف', reverse: 'قيد عكسي',
  purchase: 'شراء من مورد',
};
export { ACTION_LABELS };

const STATUS_BADGE = {
  pending: 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/40 dark:text-amber-200',
  approved: 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-900/40 dark:text-emerald-200',
  rejected: 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-900/40 dark:text-rose-200',
};

const fmtDate = (ts) => {
  if (!ts) return '—';
  try { return new Date(ts * 1000).toLocaleString('ar-SA', { dateStyle: 'short', timeStyle: 'short' }); }
  catch { return '—'; }
};

// 🏷️ تسميات عربية واضحة لحقول المسودة — بدل عرض JSON خام
const FIELD_LABELS = {
  name: 'الاسم', customer: 'العميل', customer_name: 'العميل', supplier: 'المورد',
  phone: 'الجوال', plate: 'اللوحة', plate_number: 'اللوحة',
  payment_method: 'طريقة الدفع', category: 'البيان', description: 'البيان',
  reason: 'السبب', date: 'التاريخ', brand: 'الماركة', model: 'الموديل',
  year: 'السنة', notes: 'ملاحظات', vat: 'الضريبة', journal_id: 'رقم القيد',
  reference_id: 'المرجع', quantity: 'الكمية', qty: 'الكمية', price: 'السعر',
};
const PAY_LABELS = {
  cash: '💵 نقدي', credit: '⏳ آجل (ذمم)', deferred: '⏳ آجل (ذمم)',
  bank: '🏦 تحويل بنكي', transfer: '🏦 تحويل بنكي', pos: '💳 شبكة / نقاط بيع',
};

export function PayloadDetails({ payload = {} }) {
  const amount = payload.amount ?? payload.total;
  const rows = Object.entries(payload).filter(([k, v]) =>
    !k.startsWith('_') && !['amount', 'total'].includes(k)
    && !(/(^id$|_id$|Id$)/.test(k) && k !== 'journal_id')
    && v !== null && v !== '' && typeof v !== 'object' && typeof v !== 'boolean');
  if (rows.length === 0 && (amount === undefined || amount === null)) {
    return <span className="text-xs text-slate-400" data-testid="payload-empty">بدون تفاصيل إضافية</span>;
  }
  return (
    <div className="mt-1.5 space-y-1" data-testid="payload-details">
      {(amount !== undefined && amount !== null) && (
        <div className="text-sm">
          <span className="text-slate-500 dark:text-slate-400 text-xs">المبلغ: </span>
          <span className="font-black text-indigo-700 dark:text-indigo-300">{Number(amount).toLocaleString('en-US')} ر.س</span>
        </div>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1">
        {rows.map(([k, v]) => {
          let display = String(v);
          if (k === 'payment_method') display = PAY_LABELS[display] || display;
          if (k === 'date') display = display.slice(0, 10);
          if (['journal_id', 'reference_id'].includes(k)) display = display.slice(0, 12);
          return (
            <div key={k} className="text-xs">
              <span className="text-slate-500 dark:text-slate-400">{FIELD_LABELS[k] || k}: </span>
              <span className="font-bold text-slate-800 dark:text-slate-100">{display.slice(0, 60)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// الأثر المحاسبي المتوقع (من echo البوت إن وُجد)
const accountingEffect = (p = {}) => p?._echo?.accounts || null;

// تسمية ودّية للمُقترِح — الاعتمادات السابقة قبل ربط الهوية تظهر auto:llm
const proposerLabel = (proposer) => {
  const s = String(proposer || '').trim();
  if (!s || s === 'auto:llm' || s === 'auto:policy') return 'كاترينا (طلب آلي)';
  return s;
};

export function KatrinaApprovalsTab({ onCountChange }) {
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState('pending');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const { data } = await axios.get(`${RUNTIME_API}/approvals`, { params: { limit: 100, status: filter || undefined } });
      const items = data?.data || [];
      setRows(items);
      if (onCountChange) onCountChange(items.filter((a) => a.status === 'pending').length);
    } catch {
      setMsg({ type: 'err', text: 'تعذر تحميل الاعتمادات' });
    } finally { setBusy(false); }
  }, [filter, onCountChange]);

  useEffect(() => { load(); }, [load]);

  // 🔗 ترابط حي — مسودة جديدة/إلغاء من شات كاترينا يحدّث القائمة فوراً
  useEffect(() => {
    const handler = () => load();
    window.addEventListener('finance:updated', handler);
    window.addEventListener('runtime:changed', handler);
    return () => {
      window.removeEventListener('finance:updated', handler);
      window.removeEventListener('runtime:changed', handler);
    };
  }, [load]);

  const act = async (id, kind) => {
    if (kind === 'approve') {
      const ok = window.confirm('سيتم اعتماد هذه العملية وتنفيذها فوراً في السجلات. هل أنت متأكد؟\n\nملاحظة: لا يمكنك اعتماد طلبٍ اقترحتَه بنفسك (مبدأ الأربع أعين).');
      if (!ok) return;
    }
    setBusy(true); setMsg(null);
    try {
      if (kind === 'approve') {
        await axios.post(`${RUNTIME_API}/approvals/${id}/approve`, {});
        setMsg({ type: 'ok', text: '✅ اعتُمدت ونُفِّذت العملية' });
      } else {
        const reason = window.prompt('سبب الرفض (اختياري):') || '';
        await axios.post(`${RUNTIME_API}/approvals/${id}/reject`, { reason });
        setMsg({ type: 'ok', text: '🚫 رُفضت العملية' });
      }
      await load();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const errKey = typeof detail === 'object' ? detail?.error : detail;
      setMsg({
        type: 'err',
        text: errKey === 'four_eyes_violation'
          ? '⛔ أربع أعين: لا يمكنك اعتماد طلبٍ اقترحتَه بنفسك — يلزم مستخدم آخر'
          : `فشل التنفيذ: ${typeof errKey === 'string' ? errKey : 'خطأ غير متوقع'}`,
      });
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="katrina-approvals-tab">
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <select
          data-testid="katrina-approvals-filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="text-sm px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
        >
          <option value="pending">بانتظار الاعتماد</option>
          <option value="approved">معتمدة</option>
          <option value="rejected">مرفوضة</option>
          <option value="">الكل</option>
        </select>
        <button
          data-testid="katrina-approvals-refresh"
          onClick={load}
          disabled={busy}
          className="inline-flex items-center gap-1 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-sm text-slate-700 dark:text-slate-200"
        >
          <RefreshCw size={14} className={busy ? 'animate-spin' : ''} /> تحديث
        </button>
        <span className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
          <AlertTriangle size={13} /> الاعتماد يُنفِّذ العملية فوراً — والمُعتمِد يجب أن يكون غير المُقترِح
        </span>
      </div>

      {msg && (
        <div
          data-testid="katrina-approvals-msg"
          className={`mb-4 px-4 py-2.5 rounded-lg text-sm font-bold ${msg.type === 'ok'
            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200'
            : 'bg-rose-50 text-rose-800 border border-rose-200 dark:bg-rose-900/30 dark:text-rose-200'}`}
        >
          {msg.text}
        </div>
      )}

      {rows.length === 0 ? (
        <div className="p-10 text-center text-slate-500" data-testid="katrina-approvals-empty">
          <Bot size={36} className="mx-auto mb-2 opacity-40" />
          لا توجد عمليات {filter === 'pending' ? 'بانتظار الاعتماد' : ''} من كاترينا
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map((a) => (
            <div
              key={a.id}
              data-testid={`katrina-approval-${a.id}`}
              className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 flex flex-wrap items-center gap-3"
            >
              <div className="flex-1 min-w-[240px]">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-extrabold text-slate-900 dark:text-white">
                    {ACTION_LABELS[a.action] || a.action || 'عملية'}
                  </span>
                  <span className={`text-[11px] px-2 py-0.5 rounded-full border font-bold ${STATUS_BADGE[a.status] || ''}`}>
                    {a.status === 'pending' ? 'معلّقة' : a.status === 'approved' ? 'معتمدة' : 'مرفوضة'}
                  </span>
                </div>
                <div data-testid={`katrina-payload-${a.id}`}><PayloadDetails payload={a.payload} /></div>
                {accountingEffect(a.payload) && (
                  <div className="text-xs text-indigo-600 dark:text-indigo-300 mt-1 font-mono" data-testid={`katrina-effect-${a.id}`}>
                    🧾 {accountingEffect(a.payload)}
                  </div>
                )}
                <div className="text-xs text-slate-400 mt-1 flex items-center gap-2">
                  <Clock size={12} /> {fmtDate(a.created_at)} · المُقترِح: {proposerLabel(a.proposer || a.requester)}
                </div>
              </div>
              {a.status === 'pending' && (
                <div className="flex gap-2">
                  <button
                    data-testid={`katrina-approve-${a.id}`}
                    onClick={() => act(a.id, 'approve')}
                    disabled={busy}
                    className="inline-flex items-center gap-1 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold disabled:opacity-50"
                  >
                    <Check size={15} /> اعتماد وتنفيذ
                  </button>
                  <button
                    data-testid={`katrina-reject-${a.id}`}
                    onClick={() => act(a.id, 'reject')}
                    disabled={busy}
                    className="inline-flex items-center gap-1 px-4 py-2 rounded-lg border border-rose-300 text-rose-700 dark:text-rose-300 hover:bg-rose-50 dark:hover:bg-rose-900/30 text-sm font-bold disabled:opacity-50"
                  >
                    <X size={15} /> رفض
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
