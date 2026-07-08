import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, RefreshCw, Check, X, Bot, ScanLine, ExternalLink, Clock } from 'lucide-react';
import { ACTION_LABELS, PayloadDetails } from '../KatrinaApprovalsTab';

/**
 * 🛡️ ControlCenterTab — مركز التحكم المالي داخل كاترينا (بأسلوب Kodee Bento)
 * • مؤشرات التدقيق (KPIs) — /api/financial-control/findings/summary
 * • اعتمادات كاترينا المعلقة — اعتماد/رفض (Four-Eyes عبر /api/runtime)
 * • أحدث الاكتشافات المفتوحة — قراءة فقط
 */

const BASE = process.env.REACT_APP_BACKEND_URL || '';
const FC_API = `${BASE}/api/financial-control`;
const RUNTIME_API = `${BASE}/api/runtime`;

const SEV_LABEL = { critical: '🔴 حرجة', high: '🟠 مرتفعة', medium: '🟡 متوسطة', low: '🔵 منخفضة', info: '⚪ معلومة' };

const fmtTs = (ts) => {
  if (!ts) return '—';
  try { return new Date(ts * 1000).toLocaleString('ar-SA', { dateStyle: 'short', timeStyle: 'short' }); }
  catch { return '—'; }
};

const proposerLabel = (p) => {
  const s = String(p || '').trim();
  if (!s || s === 'auto:llm' || s === 'auto:policy') return 'كاترينا (طلب آلي)';
  return s;
};

const currentUsername = () => {
  try {
    const u = JSON.parse(localStorage.getItem('user') || 'null');
    return (u?.name || u?.username || '').trim();
  } catch (e) { return ''; }
};

function MiniKPI({ title, value, tone, testid }) {
  const tones = {
    rose: 'text-rose-600 dark:text-rose-400',
    amber: 'text-amber-600 dark:text-amber-400',
    emerald: 'text-emerald-600 dark:text-emerald-400',
    indigo: 'text-violet-600 dark:text-violet-400',
  };
  return (
    <div data-testid={testid} className="bg-white dark:bg-zinc-900 p-3.5 rounded-2xl border border-zinc-200/70 dark:border-zinc-800 flex flex-col gap-1 hover:shadow-sm transition-shadow">
      <div className="text-[10px] font-bold text-zinc-500 dark:text-zinc-400">{title}</div>
      <div className={`text-xl font-black tracking-tight ${tones[tone] || tones.indigo}`}>{value}</div>
    </div>
  );
}

export const ControlCenterTab = ({ onCountChange }) => {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [findings, setFindings] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [sres, ares, fres] = await Promise.all([
        axios.get(`${FC_API}/findings/summary`).catch(() => ({ data: null })),
        axios.get(`${RUNTIME_API}/approvals`, { params: { status: 'pending', limit: 30 } }).catch(() => ({ data: null })),
        axios.get(`${FC_API}/findings`, { params: { status: 'open', limit: 5 } }).catch(() => ({ data: null })),
      ]);
      setSummary(sres.data?.data || null);
      const pend = ares.data?.data || [];
      setApprovals(pend);
      setFindings(fres.data?.data || []);
      if (onCountChange) onCountChange(pend.length);
    } finally { setBusy(false); setLoaded(true); }
  }, [onCountChange]);

  useEffect(() => { load(); }, [load]);

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
    if (kind === 'approve' && !window.confirm('سيتم اعتماد هذه العملية وتنفيذها فوراً في السجلات. هل أنت متأكد؟\n\nملاحظة: لا يمكنك اعتماد طلبٍ اقترحتَه بنفسك (مبدأ الأربع أعين).')) return;
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
      try {
        window.dispatchEvent(new CustomEvent('runtime:changed', { detail: { source: 'control_center' } }));
        window.dispatchEvent(new CustomEvent('finance:updated', { detail: { source: 'control_center' } }));
      } catch (e) { /* noop */ }
      await load();
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      const errKey = typeof detail === 'object' ? detail?.error : detail;
      if (errKey === 'approval_not_found' || status === 404) {
        setMsg({ type: 'err', text: 'ℹ️ هذا الطلب لم يعد موجوداً (اعتُمد أو رُفض سابقاً) — حدّثتُ القائمة' });
        await load();
        return;
      }
      setMsg({
        type: 'err',
        text: errKey === 'four_eyes_violation'
          ? '⛔ أربع أعين: لا يمكنك اعتماد طلبٍ اقترحتَه بنفسك — يلزم مستخدم آخر'
          : `فشل التنفيذ: ${typeof errKey === 'string' ? errKey : 'خطأ غير متوقع'}`,
      });
    } finally { setBusy(false); }
  };

  return (
    <div className="p-4 space-y-4 animate-fadeIn" data-testid="control-center-tab" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-black text-zinc-900 dark:text-zinc-100">
          <div className="h-8 w-8 rounded-xl bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center text-violet-600 dark:text-violet-300">
            <ShieldAlert size={16} />
          </div>
          مركز التحكم المالي
        </div>
        <div className="flex items-center gap-1">
          <button
            data-testid="control-center-refresh"
            onClick={load}
            disabled={busy}
            className="h-8 w-8 rounded-lg flex items-center justify-center text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-600 transition-colors"
            title="تحديث"
          >
            <RefreshCw size={14} className={busy ? 'animate-spin' : ''} />
          </button>
          <button
            data-testid="control-center-open-full"
            onClick={() => navigate('/financial-control')}
            className="h-8 w-8 rounded-lg flex items-center justify-center text-violet-500 hover:bg-violet-50 dark:hover:bg-violet-900/30 transition-colors"
            title="فتح الصفحة الكاملة"
          >
            <ExternalLink size={14} />
          </button>
        </div>
      </div>

      {!loaded ? (
        <div className="space-y-2.5" data-testid="cc-loading-skeleton">
          <div className="grid grid-cols-2 gap-2.5">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-[72px] rounded-2xl bg-zinc-100 dark:bg-zinc-900 animate-pulse" />
            ))}
          </div>
          <div className="h-24 rounded-2xl bg-zinc-100 dark:bg-zinc-900 animate-pulse" />
          <div className="h-24 rounded-2xl bg-zinc-100 dark:bg-zinc-900 animate-pulse" />
          <div className="text-center text-[11px] text-zinc-400 font-medium">جارِ تحميل بيانات مركز التحكم…</div>
        </div>
      ) : (
      <>
      {/* KPIs — Bento grid */}
      <div className="grid grid-cols-2 gap-2.5">
        <MiniKPI title="اكتشافات مفتوحة" value={summary?.open_count ?? '—'} tone="rose" testid="cc-kpi-open" />
        <MiniKPI title="حرجة" value={summary?.by_severity?.critical ?? 0} tone="rose" testid="cc-kpi-critical" />
        <MiniKPI title="بانتظار الاعتماد" value={approvals.length} tone="amber" testid="cc-kpi-pending" />
        <MiniKPI title="الأثر المالي" value={`${(summary?.open_financial_impact ?? 0).toLocaleString('en-US')} ر.س`} tone="indigo" testid="cc-kpi-impact" />
      </div>

      {msg && (
        <div
          data-testid="control-center-msg"
          className={`px-3.5 py-2.5 rounded-xl text-xs font-bold animate-fadeIn ${msg.type === 'ok'
            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-200 dark:border-emerald-800'
            : 'bg-rose-50 text-rose-800 border border-rose-200 dark:bg-rose-900/20 dark:text-rose-200 dark:border-rose-800'}`}
        >
          {msg.text}
        </div>
      )}

      {/* Pending approvals */}
      <div>
        <div className="text-xs font-black text-zinc-600 dark:text-zinc-300 mb-2 flex items-center gap-1.5">
          <Bot size={13} className="text-violet-500" /> اعتمادات كاترينا المعلقة (أربع أعين)
        </div>
        {approvals.length === 0 ? (
          <div className="text-center py-5 text-xs text-zinc-400 border border-dashed border-zinc-300 dark:border-zinc-700 rounded-2xl" data-testid="cc-approvals-empty">
            لا توجد عمليات بانتظار الاعتماد ✓
          </div>
        ) : (
          <div className="space-y-2.5">
            {approvals.map((a) => {
              const me = currentUsername();
              const isMine = me && String(a.proposer || a.requester || '').trim() === me;
              return (
              <div
                key={a.id}
                data-testid={`cc-approval-${a.id}`}
                className="rounded-2xl border border-amber-200/70 dark:border-amber-900/40 bg-amber-50/40 dark:bg-amber-900/10 overflow-hidden hover:shadow-sm transition-shadow"
              >
                <div className="px-3.5 pt-3 pb-1 flex items-center justify-between gap-2">
                  <span className="text-sm font-black text-zinc-900 dark:text-zinc-100">
                    {ACTION_LABELS[a.action] || a.action || 'عملية'}
                  </span>
                  <span className="text-[10px] font-bold bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800 px-2 py-0.5 rounded-full shrink-0">معلّقة</span>
                </div>
                <div className="px-3.5 pb-2">
                  <PayloadDetails payload={a.payload} />
                  <div className="text-[10px] text-zinc-400 mt-2 flex items-center gap-1">
                    <Clock size={10} /> {fmtTs(a.created_at)} · المُقترِح: {proposerLabel(a.proposer || a.requester)}
                  </div>
                </div>
                <div className="px-3 pb-3 flex gap-2">
                  {isMine ? (
                    <div
                      data-testid={`cc-awaiting-other-${a.id}`}
                      className="flex-1 inline-flex items-center justify-center gap-1 py-2 rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 text-xs font-bold cursor-not-allowed"
                      title="مبدأ الأربع أعين: أنت المُقترِح — الاعتماد يتطلب مستخدماً آخر"
                    >
                      👁️👁️ بانتظار معتمدٍ آخر (أنت المُقترِح)
                    </div>
                  ) : (
                    <button
                      data-testid={`cc-approve-${a.id}`}
                      onClick={() => act(a.id, 'approve')}
                      disabled={busy}
                      className="flex-1 inline-flex items-center justify-center gap-1 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold disabled:opacity-50 transition-colors active:scale-[0.98]"
                    >
                      <Check size={13} /> اعتماد وتنفيذ
                    </button>
                  )}
                  <button
                    data-testid={`cc-reject-${a.id}`}
                    onClick={() => act(a.id, 'reject')}
                    disabled={busy}
                    className="flex-1 inline-flex items-center justify-center gap-1 py-2 rounded-xl bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-700 text-xs font-bold disabled:opacity-50 transition-colors active:scale-[0.98]"
                  >
                    <X size={13} /> رفض
                  </button>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Open findings (read-only) */}
      <div>
        <div className="text-xs font-black text-zinc-600 dark:text-zinc-300 mb-2 flex items-center gap-1.5">
          <ScanLine size={13} className="text-violet-500" /> أحدث الاكتشافات المفتوحة
        </div>
        {findings.length === 0 ? (
          <div className="text-center py-5 text-xs text-zinc-400 border border-dashed border-zinc-300 dark:border-zinc-700 rounded-2xl" data-testid="cc-findings-empty">
            لا توجد اكتشافات مفتوحة ✓
          </div>
        ) : (
          <div className="space-y-2">
            {findings.map((f) => (
              <div
                key={f.id}
                data-testid={`cc-finding-${f.id}`}
                className="rounded-2xl border border-zinc-200/70 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3.5 py-2.5 hover:shadow-sm transition-shadow"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-bold shrink-0">{SEV_LABEL[f.severity] || f.severity}</span>
                  <span className="text-[10px] text-zinc-400 shrink-0">{f.detected_at?.slice(0, 10)}</span>
                </div>
                <div className="text-xs font-bold text-zinc-800 dark:text-zinc-100 mt-1 leading-snug">{f.title}</div>
                {Number(f.financial_impact || 0) > 0 && (
                  <div className="text-[11px] text-rose-600 dark:text-rose-400 font-bold mt-0.5">
                    الأثر: {Number(f.financial_impact).toLocaleString('en-US')} ر.س
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      </>
      )}
    </div>
  );
};

export default ControlCenterTab;
