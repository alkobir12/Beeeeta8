import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { getStoredToken } from '../../utils/authToken';
import { AlertTriangle, Bot, Check, Clock, ExternalLink, FileSearch, RefreshCw, ShieldAlert, Sparkles, X } from 'lucide-react';

const BASE = process.env.NODE_ENV === 'production' ? '' : (process.env.REACT_APP_BACKEND_URL || '');
const FC_API = `${BASE}/api/financial-control`;
const RUNTIME_API = `${BASE}/api/runtime`;

const authConfig = (extra = {}) => {
  const token = getStoredToken();
  const base = { ...extra, withCredentials: true };
  return token ? { ...base, headers: { ...(extra.headers || {}), Authorization: `Bearer ${token}` } } : base;
};

const unwrapArray = (res) => {
  if (Array.isArray(res?.data)) return res.data;
  if (Array.isArray(res?.data?.data)) return res.data.data;
  return [];
};

const unwrapObject = (res) => {
  if (res?.data?.data && !Array.isArray(res.data.data)) return res.data.data;
  if (res?.data && !Array.isArray(res.data)) return res.data;
  return null;
};

const fetchJson = async (url) => {
  const token = getStoredToken();
  const res = await fetch(url, {
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`http_${res.status}`);
  return res.json();
};

const ACTION_LABELS = {
  customer: 'إنشاء عميل', vehicle: 'إنشاء مركبة', visit: 'فتح زيارة', supplier: 'إنشاء مورد',
  close_visits: 'إغلاق زيارات', delete_operation: 'حذف عملية', delete_customer: 'حذف عميل', delete_vehicle: 'حذف مركبة',
  update_customer: 'تعديل عميل', update_vehicle: 'تعديل مركبة', update_visit: 'تعديل زيارة',
  invoice: 'فاتورة', payment: 'تحصيل دفعة', expense: 'مصروف', reverse: 'قيد عكسي', purchase: 'شراء من مورد',
  external_operation: 'عملية من النظام', external_operation_payment: 'تحصيل عملية',
};

const SOURCE_LABELS = {
  USER_DRAFT: 'طلب مستخدم', SYSTEM_DRAFT: 'طلب نظام', AI_SUGGESTION: 'اقتراح كاترينا', TEST_ARTIFACT: 'أثر اختبار',
};

const SOURCE_STYLES = {
  USER_DRAFT: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-200 dark:border-emerald-800',
  SYSTEM_DRAFT: 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-900/20 dark:text-sky-200 dark:border-sky-800',
  AI_SUGGESTION: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/20 dark:text-amber-200 dark:border-amber-800',
  TEST_ARTIFACT: 'bg-zinc-100 text-zinc-500 border-zinc-300 dark:bg-zinc-900 dark:text-zinc-400 dark:border-zinc-700',
};

const PAY_LABELS = {
  cash: 'نقدي', credit: 'آجل / ذمم', deferred: 'آجل / ذمم', transfer: 'تحويل بنكي', bank: 'بنك', pos: 'شبكة / نقاط بيع', card: 'بطاقة',
};

const EXISTING_RECORD_ACTIONS = new Set(['payment', 'reverse', 'close_visits', 'delete_operation', 'delete_customer', 'delete_vehicle', 'update_customer', 'update_vehicle', 'update_visit', 'external_operation_payment']);
const FINANCIAL_ACTIONS = new Set(['invoice', 'payment', 'expense', 'reverse', 'purchase', 'external_operation', 'external_operation_payment']);

const fmtTs = (ts) => {
  if (!ts) return '—';
  try { return new Date(Number(ts) * 1000).toLocaleString('ar-SA', { dateStyle: 'short', timeStyle: 'short' }); }
  catch { return '—'; }
};

const safeText = (v, fallback = '—') => {
  const s = String(v ?? '').trim();
  return s || fallback;
};

const amountFromPayload = (payload = {}) => payload.amount ?? payload.total ?? payload.payment_amount ?? payload.value;
const entityFromPayload = (payload = {}) => payload.customer || payload.customer_name || payload.partner_name || payload.supplier || payload.name || payload.entity || '—';
const vehicleFromPayload = (payload = {}) => payload.plate || payload.plate_number || payload.vehicle || payload.vehicle_id || payload.vehicleId || '—';
const descriptionFromPayload = (payload = {}) => payload.description || payload.reason || payload.notes || payload.service || payload.category || payload.original_input || '—';
const paymentFromPayload = (payload = {}) => PAY_LABELS[payload.payment_method || payload.paymentMethod] || payload.payment_method || payload.paymentMethod || '—';

const sourceRecordFrom = (approval = {}) => {
  const payload = approval.payload || {};
  if (approval.source_record?.id) return approval.source_record;
  const id = payload._operation_id || payload.operation_id || payload.operationId || payload.journal_id || payload.journalId || payload.vehicle_id || payload.vehicleId || payload.customer_id || payload.customerId || payload.reference_id || payload.referenceId;
  if (!id) return null;
  let table = 'operations';
  if (payload.journal_id || payload.journalId) table = 'journal_entries';
  else if (payload.vehicle_id || payload.vehicleId) table = 'vehicles';
  else if (payload.customer_id || payload.customerId) table = 'customers';
  return { table, id, verified: Boolean(approval.source_record?.verified) };
};

const sourceUrl = (record) => {
  if (!record?.id) return null;
  const id = encodeURIComponent(record.id);
  if (record.table === 'vehicles') return `/vehicles/${id}`;
  if (record.table === 'customers') return `/customers?customerId=${id}`;
  if (record.table === 'journal_entries') return `/accounting/journal-entries?entry=${id}`;
  return `/operations?operationId=${id}`;
};

const provenanceOk = (approval = {}) => Boolean(
  (approval.draft_id || approval.id)
  && (approval.action_type || approval.action)
  && (approval.requested_by || approval.proposer || approval.requester)
  && (approval.requested_at || approval.created_at)
  && (approval.entry_channel || approval.source_classification)
);

const expectedImpact = (approval = {}) => {
  const payload = approval.payload || {};
  if (payload?._echo?.accounts) return payload._echo.accounts;
  if (!FINANCIAL_ACTIONS.has(approval.action)) return 'لا أثر مالي مباشر متوقع.';
  return 'يُحسب ويُرحّل عند التنفيذ عبر AccountingEngine فقط.';
};

function InfoRow({ label, value, testid, mono = false }) {
  return (
    <div data-testid={testid} className="min-w-0 rounded-lg bg-zinc-50 dark:bg-zinc-900/70 border border-zinc-100 dark:border-zinc-800 px-2.5 py-2">
      <div className="text-[10px] font-black text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className={`mt-0.5 text-[12px] font-bold text-zinc-900 dark:text-zinc-100 truncate ${mono ? 'font-mono ltr text-left' : ''}`}>{value}</div>
    </div>
  );
}

function SourceBadge({ source, testid }) {
  const normalized = source || 'USER_DRAFT';
  return (
    <span data-testid={testid} className={`inline-flex items-center h-7 px-2 rounded-full border text-[10px] font-black ${SOURCE_STYLES[normalized] || SOURCE_STYLES.USER_DRAFT}`}>
      {SOURCE_LABELS[normalized] || normalized}
    </span>
  );
}

function ApprovalCard({ approval, busy, onAction }) {
  const payload = approval.payload || {};
  const source = approval.source_classification || 'USER_DRAFT';
  const isTest = source === 'TEST_ARTIFACT';
  const isExisting = EXISTING_RECORD_ACTIONS.has(approval.action);
  const record = sourceRecordFrom(approval);
  const recordUrl = sourceUrl(record);
  const hasProvenance = provenanceOk(approval);
  const amount = amountFromPayload(payload);
  const amountLabel = hasProvenance && amount !== undefined && amount !== null ? `${Number(amount).toLocaleString('en-US')} ر.س` : 'محجوب حتى يكتمل مصدر المسودة';
  const actionDisabled = isTest || !hasProvenance || (isExisting && !record?.id);

  return (
    <article data-testid={`katrina-approval-card-${approval.id}`} className="rounded-[18px] border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-sm overflow-hidden">
      <div className="px-3.5 pt-3.5 pb-2 border-b border-zinc-100 dark:border-zinc-800 bg-gradient-to-l from-zinc-50 to-white dark:from-zinc-900 dark:to-zinc-950">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div data-testid={`approval-action-type-${approval.id}`} className="text-base font-black text-zinc-950 dark:text-white truncate">
              {ACTION_LABELS[approval.action] || approval.action || 'عملية'}
            </div>
            <div className="mt-1 flex items-center gap-1.5 flex-wrap">
              <SourceBadge source={source} testid={`approval-source-classification-${approval.id}`} />
              <span data-testid={`approval-risk-level-${approval.id}`} className="inline-flex h-7 items-center px-2 rounded-full bg-zinc-100 dark:bg-zinc-900 text-[10px] font-black text-zinc-600 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-800">
                {approval.risk_level || 'risk:—'}
              </span>
            </div>
          </div>
          <div data-testid={`approval-amount-${approval.id}`} className={`shrink-0 text-left ${hasProvenance ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-600 dark:text-rose-300'}`}>
            <div className="text-[10px] font-black opacity-70">المبلغ</div>
            <div className="text-sm font-black">{amountLabel}</div>
          </div>
        </div>
      </div>

      <div className="p-3.5 space-y-3">
        {!hasProvenance && (
          <div data-testid={`approval-provenance-warning-${approval.id}`} className="rounded-xl border border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-900/20 px-3 py-2 text-[12px] font-bold text-rose-800 dark:text-rose-200">
            لا تظهر هذه العملية كموافقة قابلة للتنفيذ لأن مصدر المسودة غير مكتمل.
          </div>
        )}
        {isTest && (
          <div data-testid={`approval-test-artifact-warning-${approval.id}`} className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-[12px] font-bold text-zinc-600 dark:text-zinc-300">
            أثر اختبار معزول — لا يظهر كاعتماد مالي عادي ولا يمكن تنفيذه من هنا.
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <InfoRow label="العميل / الجهة" value={safeText(entityFromPayload(payload))} testid={`approval-entity-${approval.id}`} />
          <InfoRow label="المركبة" value={safeText(vehicleFromPayload(payload))} testid={`approval-vehicle-${approval.id}`} />
          <InfoRow label="منشئ الطلب" value={safeText(approval.requested_by || approval.proposer || approval.requester)} testid={`approval-requested-by-${approval.id}`} />
          <InfoRow label="وقت الطلب" value={fmtTs(approval.requested_at || approval.created_at)} testid={`approval-requested-at-${approval.id}`} />
          <InfoRow label="قناة الإدخال" value={safeText(approval.entry_channel)} testid={`approval-entry-channel-${approval.id}`} />
          <InfoRow label="طريقة الدفع" value={safeText(paymentFromPayload(payload))} testid={`approval-payment-method-${approval.id}`} />
        </div>

        <div data-testid={`approval-description-${approval.id}`} className="rounded-xl border border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/70 px-3 py-2">
          <div className="text-[10px] font-black text-zinc-500 dark:text-zinc-400">البيان</div>
          <div className="mt-1 text-[12px] font-bold text-zinc-900 dark:text-zinc-100 leading-relaxed break-words">{safeText(descriptionFromPayload(payload))}</div>
        </div>

        <div data-testid={`approval-source-reference-${approval.id}`} className="rounded-xl border border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/70 px-3 py-2 space-y-1">
          <div className="text-[10px] font-black text-zinc-500 dark:text-zinc-400">المصدر / المرجع</div>
          <div className="text-[11px] font-mono text-zinc-800 dark:text-zinc-100 break-all">draft: {approval.draft_id || '—'}</div>
          <div className="text-[11px] font-mono text-zinc-800 dark:text-zinc-100 break-all">approval: {approval.approval_id || approval.id || '—'}</div>
          <div className="text-[11px] font-mono text-zinc-800 dark:text-zinc-100 break-all">trace: {approval.trace_id || '—'}</div>
          {isExisting ? (
            <div className="text-[11px] font-mono text-zinc-800 dark:text-zinc-100 break-all">source_record: {record?.table || '—'} / {record?.id || 'غير موثق'}</div>
          ) : (
            <div className="text-[11px] text-zinc-600 dark:text-zinc-300">عملية جديدة: لا تتطلب سجلاً سابقاً قبل الاعتماد.</div>
          )}
        </div>

        <div data-testid={`approval-expected-impact-${approval.id}`} className="rounded-xl border border-emerald-100 dark:border-emerald-900 bg-emerald-50/70 dark:bg-emerald-900/10 px-3 py-2">
          <div className="text-[10px] font-black text-emerald-700 dark:text-emerald-300">الأثر المالي المتوقع</div>
          <div className="mt-1 text-[12px] font-bold text-emerald-900 dark:text-emerald-100 leading-relaxed">{expectedImpact(approval)}</div>
        </div>
      </div>

      <div data-testid={`approval-action-footer-${approval.id}`} className="sticky bottom-0 z-10 grid grid-cols-2 gap-2 p-3 bg-white/95 dark:bg-zinc-950/95 backdrop-blur border-t border-zinc-100 dark:border-zinc-800">
        {isExisting && recordUrl ? (
          <button data-testid={`approval-open-source-${approval.id}`} type="button" onClick={() => { window.location.href = recordUrl; }} className="h-12 inline-flex items-center justify-center gap-1.5 rounded-xl border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-200 text-xs font-black hover:bg-zinc-50 dark:hover:bg-zinc-900 active:scale-[0.98] transition">
            <ExternalLink size={15} /> فتح العملية الأصلية
          </button>
        ) : (
          <div data-testid={`approval-source-placeholder-${approval.id}`} className="h-12 inline-flex items-center justify-center rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 text-[11px] font-bold text-zinc-400">
            {isExisting ? 'مصدر غير موثق' : 'مسودة جديدة'}
          </div>
        )}
        <div className="grid grid-cols-2 gap-2">
          <button data-testid={`approval-approve-${approval.id}`} type="button" onClick={() => onAction(approval.id, 'approve')} disabled={busy || actionDisabled} className="h-12 inline-flex items-center justify-center gap-1 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-black disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98] transition">
            <Check size={14} /> اعتماد
          </button>
          <button data-testid={`approval-reject-${approval.id}`} type="button" onClick={() => onAction(approval.id, 'reject')} disabled={busy || isTest} className="h-12 inline-flex items-center justify-center gap-1 rounded-xl border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs font-black hover:bg-rose-50 dark:hover:bg-rose-900/20 disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98] transition">
            <X size={14} /> رفض
          </button>
        </div>
      </div>
    </article>
  );
}

function FindingCard({ finding }) {
  return (
    <article data-testid={`katrina-finding-card-${finding.id}`} className="rounded-[18px] border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-3.5 py-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <span data-testid={`finding-severity-${finding.id}`} className="text-[10px] font-black text-amber-700 dark:text-amber-300">{finding.severity || 'info'}</span>
        <span data-testid={`finding-date-${finding.id}`} className="text-[10px] font-bold text-zinc-400">{safeText(finding.detected_at || '').slice(0, 10)}</span>
      </div>
      <div data-testid={`finding-title-${finding.id}`} className="mt-1 text-sm font-black text-zinc-900 dark:text-white leading-snug">{finding.title || 'اكتشاف'}</div>
      {Number(finding.financial_impact || 0) > 0 && (
        <div data-testid={`finding-impact-${finding.id}`} className="mt-1 text-[12px] font-black text-rose-600 dark:text-rose-300">الأثر: {Number(finding.financial_impact).toLocaleString('en-US')} ر.س</div>
      )}
    </article>
  );
}

function ExecutionCard({ execution }) {
  const payload = execution.payload || {};
  return (
    <article data-testid={`katrina-execution-card-${execution.id}`} className="rounded-[18px] border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-3.5 py-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div data-testid={`execution-action-${execution.id}`} className="text-sm font-black text-zinc-900 dark:text-white">{ACTION_LABELS[execution.action] || execution.action || 'تنفيذ'}</div>
          <div data-testid={`execution-time-${execution.id}`} className="mt-1 text-[11px] font-bold text-zinc-400"><Clock size={11} className="inline ml-1" />{fmtTs(execution.committed_at)}</div>
        </div>
        <SourceBadge source={execution.source_classification || 'USER_DRAFT'} testid={`execution-source-${execution.id}`} />
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <InfoRow label="المبلغ" value={amountFromPayload(payload) ? `${Number(amountFromPayload(payload)).toLocaleString('en-US')} ر.س` : '—'} testid={`execution-amount-${execution.id}`} />
        <InfoRow label="منفذ الالتزام" value={safeText(execution.committer)} testid={`execution-committer-${execution.id}`} />
      </div>
    </article>
  );
}

export const ControlCenterTab = ({ mode = 'approvals', onCountChange }) => {
  const [summary, setSummary] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [findings, setFindings] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [msg, setMsg] = useState(null);

  const currentUser = useMemo(() => {
    try { return JSON.parse(localStorage.getItem('user') || '{}'); } catch { return {}; }
  }, []);
  const currentName = currentUser?.name || currentUser?.username || '';
  const currentRole = String(currentUser?.role || '').toLowerCase();

  const actionableApprovals = useMemo(() => approvals.filter((a) => a.source_classification !== 'TEST_ARTIFACT'), [approvals]);
  const quarantinedApprovals = useMemo(() => approvals.filter((a) => a.source_classification === 'TEST_ARTIFACT'), [approvals]);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const [ares, eres] = await Promise.all([
        fetchJson(`${RUNTIME_API}/approvals?status=pending&limit=60`).catch(() => ({ data: [] })),
        fetchJson(`${RUNTIME_API}/executions?limit=20`).catch(() => ({ data: [] })),
      ]);
      let pend = unwrapArray(ares);
      if (pend.length === 0) {
        const retry = await axios.get(`${RUNTIME_API}/approvals`, authConfig({ params: { status: 'pending', limit: 100 }, timeout: 10000 })).catch(() => ({ data: [] }));
        pend = unwrapArray(retry);
      }
      setApprovals(pend);
      setExecutions(unwrapArray(eres));
      if (onCountChange) onCountChange(pend.filter((a) => a.source_classification !== 'TEST_ARTIFACT').length);
      setLoaded(true);

      const [sres, fres] = await Promise.all([
        fetchJson(`${FC_API}/findings/summary`).catch(() => ({ data: null })),
        fetchJson(`${FC_API}/findings?status=open&limit=20`).catch(() => ({ data: [] })),
      ]);
      setSummary(unwrapObject(sres));
      setFindings(unwrapArray(fres));
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
    const row = approvals.find((item) => item.id === id) || {};
    if (row.source_classification === 'TEST_ARTIFACT') return;
    const isAdminSelfApproval = String(row.proposer || row.requester || '').trim() === String(currentName).trim() && currentRole === 'admin';
    const confirmationText = isAdminSelfApproval
      ? 'سيُسجّل اعتمادك كاستثناء مدير نظام ويُنفّذ الإجراء فوراً. هل أنت متأكد؟'
      : 'سيتم اعتماد هذه العملية وتنفيذها فوراً في السجلات. هل أنت متأكد؟\n\nملاحظة: لا يمكنك اعتماد طلبٍ اقترحتَه بنفسك (مبدأ الأربع أعين).';
    if (kind === 'approve' && !window.confirm(confirmationText)) return;
    setBusy(true); setMsg(null);
    try {
      if (kind === 'approve') {
        await axios.post(`${RUNTIME_API}/approvals/${id}/approve`, {}, authConfig());
        setMsg({ type: 'ok', text: '✅ اعتُمدت ونُفِّذت العملية' });
      } else {
        const reason = window.prompt('سبب الرفض (اختياري):') || '';
        await axios.post(`${RUNTIME_API}/approvals/${id}/reject`, { reason }, authConfig());
        setMsg({ type: 'ok', text: '🚫 رُفضت العملية' });
      }
      window.dispatchEvent(new CustomEvent('runtime:changed', { detail: { source: 'control_center' } }));
      window.dispatchEvent(new CustomEvent('finance:updated', { detail: { source: 'control_center' } }));
      await load();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const errKey = typeof detail === 'object' ? detail?.error || detail?.msg : detail;
      setMsg({ type: 'err', text: errKey === 'four_eyes_violation' ? '⛔ أربع أعين: يلزم مستخدم آخر للاعتماد' : `فشل التنفيذ: ${errKey || 'خطأ غير متوقع'}` });
    } finally { setBusy(false); }
  };

  const header = {
    approvals: ['يحتاج قرارك', ShieldAlert, actionableApprovals.length],
    findings: ['اكتشفته كاترينا', FileSearch, findings.length + quarantinedApprovals.length],
    executions: ['تم بواسطة كاترينا', Check, executions.length],
  }[mode] || ['مركز كاترينا', Bot, 0];
  const HeaderIcon = header[1];

  return (
    <section data-testid={`katrina-control-${mode}`} className="h-full flex flex-col bg-zinc-50/50 dark:bg-zinc-950" dir="rtl">
      <div className="sticky top-0 z-20 px-3.5 py-3 bg-white/95 dark:bg-zinc-950/95 backdrop-blur border-b border-zinc-100 dark:border-zinc-800">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="h-9 w-9 rounded-xl bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 flex items-center justify-center shrink-0"><HeaderIcon size={17} /></div>
            <div className="min-w-0">
              <h4 data-testid={`katrina-control-title-${mode}`} className="text-sm font-black text-zinc-950 dark:text-white truncate">{header[0]}</h4>
              <p data-testid={`katrina-control-count-${mode}`} className="text-[11px] font-bold text-zinc-500 dark:text-zinc-400">{header[2]} عنصر</p>
            </div>
          </div>
          <button data-testid={`katrina-control-refresh-${mode}`} type="button" onClick={load} disabled={busy} className="h-11 w-11 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-center justify-center text-zinc-600 dark:text-zinc-200 disabled:opacity-50 active:scale-95 transition" title="تحديث">
            <RefreshCw size={16} className={busy ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {msg && (
        <div data-testid="katrina-control-message" className={`mx-3 mt-3 px-3 py-2 rounded-xl text-[12px] font-black ${msg.type === 'ok' ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-100 dark:border-emerald-800' : 'bg-rose-50 text-rose-800 border border-rose-200 dark:bg-rose-900/20 dark:text-rose-100 dark:border-rose-800'}`}>
          {msg.text}
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-3.5 py-3 space-y-3 scroll-smooth">
        {!loaded ? (
          <div data-testid={`katrina-control-loading-${mode}`} className="space-y-3">
            {[0, 1, 2].map((i) => <div key={i} className="h-36 rounded-[18px] bg-zinc-100 dark:bg-zinc-900 animate-pulse" />)}
          </div>
        ) : mode === 'approvals' ? (
          actionableApprovals.length === 0 ? (
            <div data-testid="katrina-approvals-empty" className="py-10 text-center text-sm font-bold text-zinc-400 border border-dashed border-zinc-300 dark:border-zinc-700 rounded-[18px]">لا توجد قرارات معلّقة ✓</div>
          ) : actionableApprovals.map((a) => <ApprovalCard key={a.id} approval={a} busy={busy} onAction={act} />)
        ) : mode === 'findings' ? (
          <>
            {summary && (
              <div data-testid="katrina-findings-summary" className="grid grid-cols-2 gap-2">
                <InfoRow label="مفتوحة" value={summary.open_count ?? 0} testid="findings-summary-open" />
                <InfoRow label="الأثر" value={`${Number(summary.open_financial_impact || 0).toLocaleString('en-US')} ر.س`} testid="findings-summary-impact" />
              </div>
            )}
            {quarantinedApprovals.map((a) => <ApprovalCard key={a.id} approval={a} busy={busy} onAction={act} />)}
            {findings.length === 0 && quarantinedApprovals.length === 0 ? (
              <div data-testid="katrina-findings-empty" className="py-10 text-center text-sm font-bold text-zinc-400 border border-dashed border-zinc-300 dark:border-zinc-700 rounded-[18px]">لا توجد اكتشافات مفتوحة ✓</div>
            ) : findings.map((f) => <FindingCard key={f.id} finding={f} />)}
          </>
        ) : executions.length === 0 ? (
          <div data-testid="katrina-executions-empty" className="py-10 text-center text-sm font-bold text-zinc-400 border border-dashed border-zinc-300 dark:border-zinc-700 rounded-[18px]">لا توجد تنفيذات حديثة</div>
        ) : executions.map((e) => <ExecutionCard key={e.id} execution={e} />)}
      </div>
    </section>
  );
};

export default ControlCenterTab;