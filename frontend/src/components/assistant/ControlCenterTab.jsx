import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, RefreshCw, Check, X, Bot, ScanLine, ExternalLink, Clock } from 'lucide-react';
import { ACTION_LABELS, PayloadDetails } from '../KatrinaApprovalsTab';

/**
 * 🛡️ ControlCenterTab — مركز التحكم المالي مدمجاً داخل كاترينا (P3 Phase A+B)
 * • مؤشرات التدقيق (KPIs) — قراءة من /api/financial-control/findings/summary
 * • اعتمادات كاترينا المعلقة — اعتماد/رفض مباشرة (Four-Eyes عبر /api/runtime)
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

function MiniKPI({ title, value, tone, testid }) {
  const tones = {
    rose: 'border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40',
    amber: 'border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40',
    emerald: 'border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40',
    indigo: 'border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40',
  };
  return (
    <div data-testid={testid} className={`rounded-lg border p-2 ${tones[tone] || tones.indigo}`}>
      <div className="text-[10px] font-bold opacity-80">{title}</div>
      <div className="text-base font-black mt-0.5">{value}</div>
    </div>
  );
}

export const ControlCenterTab = ({ onCountChange }) => {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [findings, setFindings] = useState([]);
  const [busy, setBusy] = useState(false);
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
    } finally { setBusy(false); }
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
    <div className="p-3 space-y-3" data-testid="control-center-tab" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-sm font-black text-slate-800 dark:text-slate-100">
          <ShieldAlert size={16} className="text-indigo-600" /> مركز التحكم المالي
        </div>
        <div className="flex items-center gap-1.5">
          <button
            data-testid="control-center-refresh"
            onClick={load}
            disabled={busy}
            className="p-1.5 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            title="تحديث"
          >
            <RefreshCw size={13} className={busy ? 'animate-spin' : ''} />
          </button>
          <button
            data-testid="control-center-open-full"
            onClick={() => navigate('/financial-control')}
            className="p-1.5 rounded-lg border border-indigo-300 dark:border-indigo-700 text-indigo-600 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-900/40"
            title="فتح الصفحة الكاملة"
          >
            <ExternalLink size={13} />
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-2">
        <MiniKPI title="اكتشافات مفتوحة" value={summary?.open_count ?? '—'} tone="rose" testid="cc-kpi-open" />
        <MiniKPI title="حرجة" value={summary?.by_severity?.critical ?? 0} tone="rose" testid="cc-kpi-critical" />
        <MiniKPI title="بانتظار الاعتماد" value={approvals.length} tone="amber" testid="cc-kpi-pending" />
        <MiniKPI title="الأثر المالي" value={`${(summary?.open_financial_impact ?? 0).toLocaleString('en-US')} ر.س`} tone="indigo" testid="cc-kpi-impact" />
      </div>

      {msg && (
        <div
          data-testid="control-center-msg"
          className={`px-3 py-2 rounded-lg text-xs font-bold ${msg.type === 'ok'
            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200'
            : 'bg-rose-50 text-rose-800 border border-rose-200 dark:bg-rose-900/30 dark:text-rose-200'}`}
        >
          {msg.text}
        </div>
      )}

      {/* Pending approvals */}
      <div>
        <div className="text-xs font-black text-slate-600 dark:text-slate-300 mb-1.5 flex items-center gap-1">
          <Bot size={13} /> اعتمادات كاترينا المعلقة (أربع أعين)
        </div>
        {approvals.length === 0 ? (
          <div className="text-center py-4 text-xs text-slate-400 border border-dashed border-slate-300 dark:border-slate-700 rounded-xl" data-testid="cc-approvals-empty">
            لا توجد عمليات بانتظار الاعتماد ✓
          </div>
        ) : (
          <div className="space-y-2">
            {approvals.map((a) => (
              <div
                key={a.id}
                data-testid={`cc-approval-${a.id}`}
                className="rounded-xl border border-amber-200 dark:border-amber-800 bg-white dark:bg-slate-900 overflow-hidden"
              >
                <div className="bg-gradient-to-l from-amber-500 to-orange-500 text-white px-3 py-1.5 flex items-center justify-between">
                  <span className="text-[13px] font-black" style={{ textShadow: '0 1px 2px rgba(0,0,0,0.4)' }}>
                    {ACTION_LABELS[a.action] || a.action || 'عملية'}
                  </span>
                  <span className="text-[10px] font-bold bg-black/25 border border-white/50 px-2 py-0.5 rounded-full">معلّقة</span>
                </div>
                <div className="px-3 py-2">
                  <PayloadDetails payload={a.payload} />
                  <div className="text-[10px] text-slate-400 mt-1.5 flex items-center gap-1">
                    <Clock size={10} /> {fmtTs(a.created_at)} · المُقترِح: {proposerLabel(a.proposer || a.requester)}
                  </div>
                </div>
                <div className="px-2 pb-2 flex gap-1.5">
                  <button
                    data-testid={`cc-approve-${a.id}`}
                    onClick={() => act(a.id, 'approve')}
                    disabled={busy}
                    className="flex-1 inline-flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold disabled:opacity-50"
                  >
                    <Check size={13} /> اعتماد وتنفيذ
                  </button>
                  <button
                    data-testid={`cc-reject-${a.id}`}
                    onClick={() => act(a.id, 'reject')}
                    disabled={busy}
                    className="flex-1 inline-flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg border border-rose-300 dark:border-rose-700 text-rose-700 dark:text-rose-300 hover:bg-rose-50 dark:hover:bg-rose-900/30 text-xs font-bold disabled:opacity-50"
                  >
                    <X size={13} /> رفض
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Open findings (read-only) */}
      <div>
        <div className="text-xs font-black text-slate-600 dark:text-slate-300 mb-1.5 flex items-center gap-1">
          <ScanLine size={13} /> أحدث الاكتشافات المفتوحة
        </div>
        {findings.length === 0 ? (
          <div className="text-center py-4 text-xs text-slate-400 border border-dashed border-slate-300 dark:border-slate-700 rounded-xl" data-testid="cc-findings-empty">
            لا توجد اكتشافات مفتوحة ✓
          </div>
        ) : (
          <div className="space-y-1.5">
            {findings.map((f) => (
              <div
                key={f.id}
                data-testid={`cc-finding-${f.id}`}
                className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] font-bold shrink-0">{SEV_LABEL[f.severity] || f.severity}</span>
                  <span className="text-[10px] text-slate-400 shrink-0">{f.detected_at?.slice(0, 10)}</span>
                </div>
                <div className="text-xs font-bold text-slate-800 dark:text-slate-100 mt-0.5 leading-snug">{f.title}</div>
                {Number(f.financial_impact || 0) > 0 && (
                  <div className="text-[11px] text-rose-600 dark:text-rose-300 font-bold mt-0.5">
                    الأثر: {Number(f.financial_impact).toLocaleString('en-US')} ر.س
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ControlCenterTab;
