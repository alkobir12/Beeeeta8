/**
 * 💼 Financial Control Center — Phase 1
 *
 * Three tabs:
 *   • التدقيق والاكتشافات (Findings)  — list + lifecycle
 *   • الموافقات (Approvals)           — list + actions
 *   • مصفوفة الموافقات (Matrix)       — view-only config
 */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { ShieldAlert, ScanLine, FileCheck2, RefreshCw, AlertTriangle, Eye, ClipboardCheck, X, Bot } from 'lucide-react';
import { KatrinaApprovalsTab } from '../components/KatrinaApprovalsTab';

const API = (process.env.REACT_APP_BACKEND_URL || '') + '/api/financial-control';

const SEV_STYLE = {
  critical: 'bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-900/40 dark:text-rose-200 dark:border-rose-700',
  high:     'bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900/40 dark:text-orange-200 dark:border-orange-700',
  medium:   'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/40 dark:text-amber-200 dark:border-amber-700',
  low:      'bg-sky-100 text-sky-800 border-sky-300 dark:bg-sky-900/40 dark:text-sky-200 dark:border-sky-700',
  info:     'bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700',
};

const STATUS_STYLE = {
  open:           'bg-rose-50 text-rose-700 border-rose-200',
  acknowledged:   'bg-amber-50 text-amber-700 border-amber-200',
  in_progress:    'bg-sky-50 text-sky-700 border-sky-200',
  resolved:       'bg-emerald-50 text-emerald-700 border-emerald-200',
  dismissed:      'bg-slate-50 text-slate-600 border-slate-200',
};

const APP_STATUS_STYLE = {
  pending_review:   'bg-amber-100 text-amber-800 border-amber-300',
  pending_approval: 'bg-sky-100 text-sky-800 border-sky-300',
  approved:         'bg-emerald-100 text-emerald-800 border-emerald-300',
  rejected:         'bg-rose-100 text-rose-800 border-rose-300',
  cancelled:        'bg-slate-100 text-slate-700 border-slate-300',
};

const RULE_LABELS = {
  duplicate_payment:  'دفعة مكررة',
  duplicate_invoice:  'فاتورة مكررة',
  missing_reference:  'قيد محاسبي مفقود',
  negative_inventory: 'مخزون سالب',
  unbalanced_journal: 'قيد غير متوازن',
  backdated:          'تاريخ متأخر',
  future_dated:       'تاريخ مستقبلي',
};

const STATUS_LABELS = {
  open: 'مفتوح', acknowledged: 'مُستلَم', in_progress: 'قيد العمل', resolved: 'محلول', dismissed: 'مرفوض',
  pending_review: 'بانتظار المراجعة', pending_approval: 'بانتظار الاعتماد', approved: 'معتمد', rejected: 'مرفوض', cancelled: 'ملغى',
};

export default function FinancialControl() {
  const [tab, setTab] = useState('findings');
  const [katrinaCount, setKatrinaCount] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const refreshCount = () => {
      axios.get(`${(process.env.REACT_APP_BACKEND_URL || '')}/api/runtime/approvals`, { params: { status: 'pending', limit: 100 } })
        .then(({ data }) => setKatrinaCount((data?.data || []).length))
        .catch(() => {});
    };
    refreshCount();
    // 🔗 ترابط حي مع البوت وباقي الصفحات — أي كتابة/مسودة/اعتماد تحدّث الصفحة فوراً
    const handler = () => { setRefreshKey((k) => k + 1); refreshCount(); };
    window.addEventListener('finance:updated', handler);
    window.addEventListener('runtime:changed', handler);
    return () => {
      window.removeEventListener('finance:updated', handler);
      window.removeEventListener('runtime:changed', handler);
    };
  }, []);

  return (
    <div className="p-6 max-w-7xl mx-auto" dir="rtl" data-testid="financial-control-page">
      <header className="mb-6">
        <h1 className="text-2xl md:text-3xl font-extrabold flex items-center gap-2 text-slate-900 dark:text-white">
          <ShieldAlert className="text-indigo-600" /> مركز التحكم المالي
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
          الموافقات المالية المستندة على مصفوفة المبالغ + قاعدة الأعين الأربعة + 7 قواعد تدقيق محاسبية ذكية.
        </p>
      </header>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-300 dark:border-slate-700 mb-6">
        {[
          { k: 'findings',  label: 'التدقيق والاكتشافات', icon: ScanLine },
          { k: 'approvals', label: 'الموافقات', icon: FileCheck2 },
          { k: 'katrina',   label: 'اعتمادات كاترينا', icon: Bot, badge: katrinaCount },
          { k: 'matrix',    label: 'مصفوفة الموافقات', icon: ClipboardCheck },
        ].map(t => (
          <button
            key={t.k}
            data-testid={`fc-tab-${t.k}`}
            onClick={() => setTab(t.k)}
            className={`px-4 py-2 rounded-t-lg text-sm font-bold border-b-2 transition-colors flex items-center gap-1 ${
              tab === t.k
                ? 'border-indigo-600 text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40'
                : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <t.icon size={16} /> {t.label}
            {t.badge > 0 && (
              <span data-testid="katrina-pending-badge" className="ml-1 min-w-[18px] h-[18px] px-1 rounded-full bg-rose-600 text-white text-[10px] font-black inline-flex items-center justify-center">
                {t.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      <div key={refreshKey}>
        {tab === 'findings' && <FindingsTab />}
        {tab === 'approvals' && <ApprovalsTab />}
        {tab === 'katrina' && <KatrinaApprovalsTab onCountChange={setKatrinaCount} />}
        {tab === 'matrix' && <MatrixTab />}
      </div>
    </div>
  );
}

// ============== Findings Tab ==============
function FindingsTab() {
  const [summary, setSummary] = useState(null);
  const [findings, setFindings] = useState([]);
  const [filterStatus, setFilterStatus] = useState('open');
  const [filterRule, setFilterRule] = useState('');
  const [busy, setBusy] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [selected, setSelected] = useState(null);

  const load = async () => {
    setBusy(true);
    try {
      const [sres, lres] = await Promise.all([
        axios.get(`${API}/findings/summary`),
        axios.get(`${API}/findings`, { params: { status: filterStatus || undefined, rule_code: filterRule || undefined, limit: 200 } }),
      ]);
      setSummary(sres.data?.data || null);
      setFindings(lres.data?.data || []);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filterStatus, filterRule]);

  const runScan = async () => {
    setScanning(true);
    try {
      const r = await axios.post(`${API}/findings/scan`, {});
      alert(`تم الفحص — جديد: ${r.data?.data?.scan?.created} | محدّث: ${r.data?.data?.scan?.updated}`);
      await load();
    } catch (e) {
      alert('فشل الفحص: ' + (e.response?.data?.detail || e.message));
    } finally {
      setScanning(false);
    }
  };

  return (
    <div>
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <KPI title="مفتوحة" value={summary?.open_count ?? '—'} color="rose" testid="kpi-open"/>
        <KPI title="حرجة" value={summary?.by_severity?.critical ?? 0} color="rose" testid="kpi-critical"/>
        <KPI title="مرتفعة" value={summary?.by_severity?.high ?? 0} color="orange" testid="kpi-high"/>
        <KPI title="محلولة" value={summary?.by_status?.resolved ?? 0} color="emerald" testid="kpi-resolved"/>
        <KPI title="الأثر المالي" value={`${(summary?.open_financial_impact ?? 0).toLocaleString('en-US')} ر.س`} color="indigo" testid="kpi-impact"/>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button
          data-testid="findings-scan-btn"
          onClick={runScan}
          disabled={scanning}
          className="inline-flex items-center gap-1 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold disabled:opacity-50"
        >
          {scanning ? <RefreshCw size={16} className="animate-spin"/> : <ScanLine size={16}/>}
          {scanning ? 'جاري الفحص...' : 'تشغيل الفحص الآن'}
        </button>

        <select
          data-testid="findings-filter-status"
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="text-sm px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
        >
          <option value="">كل الحالات</option>
          <option value="open">مفتوح</option>
          <option value="acknowledged">مُستلَم</option>
          <option value="in_progress">قيد العمل</option>
          <option value="resolved">محلول</option>
          <option value="dismissed">مرفوض</option>
        </select>

        <select
          data-testid="findings-filter-rule"
          value={filterRule}
          onChange={e => setFilterRule(e.target.value)}
          className="text-sm px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
        >
          <option value="">كل القواعد</option>
          {Object.entries(RULE_LABELS).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
        </select>

        <button
          data-testid="findings-refresh-btn"
          onClick={load}
          disabled={busy}
          className="inline-flex items-center gap-1 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          <RefreshCw size={14} className={busy ? 'animate-spin' : ''}/> تحديث
        </button>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
        {findings.length === 0 ? (
          <div className="p-10 text-center text-slate-500 dark:text-slate-400" data-testid="findings-empty">
            <ScanLine className="mx-auto mb-2" size={36}/>
            لا توجد اكتشافات حالياً للفلتر المحدد. شغّل فحصاً جديداً إذا رغبت.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800 text-xs uppercase tracking-wider text-slate-600 dark:text-slate-400">
              <tr>
                <th className="px-3 py-2 text-right">الخطورة</th>
                <th className="px-3 py-2 text-right">القاعدة</th>
                <th className="px-3 py-2 text-right">العنوان</th>
                <th className="px-3 py-2 text-right">الأثر</th>
                <th className="px-3 py-2 text-right">الحالة</th>
                <th className="px-3 py-2 text-right">اكتُشف</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {findings.map(f => (
                <tr key={f.id} data-testid={`finding-row-${f.id}`} className="hover:bg-slate-50 dark:hover:bg-slate-800/60">
                  <td className="px-3 py-2"><Pill cls={SEV_STYLE[f.severity]}>{f.severity}</Pill></td>
                  <td className="px-3 py-2 text-slate-700 dark:text-slate-300 text-xs whitespace-nowrap">{RULE_LABELS[f.rule_code] || f.rule_code}</td>
                  <td className="px-3 py-2 text-slate-900 dark:text-slate-100 max-w-md truncate">{f.title}</td>
                  <td className="px-3 py-2 text-slate-700 dark:text-slate-300 whitespace-nowrap">{Number(f.financial_impact || 0).toLocaleString('en-US')} ر.س</td>
                  <td className="px-3 py-2"><Pill cls={STATUS_STYLE[f.status]}>{STATUS_LABELS[f.status] || f.status}</Pill></td>
                  <td className="px-3 py-2 text-xs text-slate-500">{f.detected_at?.slice(0,10)}</td>
                  <td className="px-3 py-2">
                    <button data-testid={`finding-view-${f.id}`} onClick={() => setSelected(f)} className="text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-1 text-xs">
                      <Eye size={12}/> فحص
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && <FindingDrawer finding={selected} onClose={() => setSelected(null)} onChanged={() => { setSelected(null); load(); }}/>}
    </div>
  );
}

function FindingDrawer({ finding, onClose, onChanged }) {
  const [actor, setActor] = useState('مدير');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const act = async (path, body) => {
    setBusy(true);
    try {
      await axios.post(`${API}/findings/${finding.id}/${path}`, body);
      onChanged();
    } catch (e) {
      alert('خطأ: ' + (e.response?.data?.detail || e.message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose} dir="rtl">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="finding-drawer">
        <div className="flex items-start justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <Pill cls={SEV_STYLE[finding.severity]}>{finding.severity}</Pill>
              <Pill cls={STATUS_STYLE[finding.status]}>{STATUS_LABELS[finding.status] || finding.status}</Pill>
            </div>
            <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">{finding.title}</h3>
            <p className="text-xs text-slate-500 mt-0.5">القاعدة: {RULE_LABELS[finding.rule_code] || finding.rule_code} • الأثر: {Number(finding.financial_impact || 0).toLocaleString('en-US')} ر.س</p>
          </div>
          <button data-testid="finding-drawer-close" onClick={onClose} className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded">
            <X size={18}/>
          </button>
        </div>

        <div className="p-4 space-y-3">
          <Section title="الوصف">
            <p className="text-sm text-slate-700 dark:text-slate-300">{finding.description}</p>
          </Section>
          {finding.root_cause && (
            <Section title="السبب الجذري">
              <p className="text-sm text-slate-700 dark:text-slate-300">{finding.root_cause}</p>
            </Section>
          )}
          {finding.evidence && Object.keys(finding.evidence).length > 0 && (
            <Section title="الأدلة">
              <pre className="text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700 overflow-x-auto text-slate-700 dark:text-slate-200">
                {JSON.stringify(finding.evidence, null, 2)}
              </pre>
            </Section>
          )}
          {finding.assignee && (
            <Section title="المسؤول"><p className="text-sm">{finding.assignee} {finding.due_date && <span className="text-xs text-slate-500 mr-2">(استحقاق: {finding.due_date})</span>}</p></Section>
          )}
          {finding.comments?.length > 0 && (
            <Section title="التعليقات">
              <div className="space-y-2">
                {finding.comments.map(c => (
                  <div key={c.id} className="bg-slate-50 dark:bg-slate-800 p-2 rounded text-sm">
                    <div className="text-xs text-slate-500 mb-0.5">{c.author} • {c.at?.slice(0,16)}</div>
                    <div className="text-slate-700 dark:text-slate-200">{c.text}</div>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>

        {/* Actions */}
        <div className="p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <input data-testid="finding-actor-input" value={actor} onChange={e => setActor(e.target.value)} placeholder="اسم المنفّذ" className="text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900"/>
            <input data-testid="finding-note-input" value={note} onChange={e => setNote(e.target.value)} placeholder="ملاحظة / حل" className="text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900"/>
          </div>
          <div className="flex flex-wrap gap-2">
            {finding.status === 'open' && (
              <button data-testid="finding-ack-btn" disabled={busy} onClick={() => act('acknowledge', { actor, note })} className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded disabled:opacity-50">استلام</button>
            )}
            {['open','acknowledged'].includes(finding.status) && (
              <button data-testid="finding-start-btn" disabled={busy} onClick={() => act('start', { actor, note })} className="px-3 py-1.5 bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold rounded disabled:opacity-50">بدء العمل</button>
            )}
            {['open','acknowledged','in_progress'].includes(finding.status) && (
              <>
                <button data-testid="finding-resolve-btn" disabled={busy || !note} onClick={() => act('resolve', { actor, resolution: note })} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded disabled:opacity-50">تم الحل</button>
                <button data-testid="finding-dismiss-btn" disabled={busy || !note} onClick={() => act('dismiss', { actor, reason: note })} className="px-3 py-1.5 bg-slate-600 hover:bg-slate-700 text-white text-xs font-bold rounded disabled:opacity-50">رفض</button>
                <button data-testid="finding-assign-btn" disabled={busy || !actor} onClick={() => act('assign', { assignee: actor })} className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded disabled:opacity-50">تعيين</button>
              </>
            )}
            <button data-testid="finding-comment-btn" disabled={busy || !note} onClick={() => act('comment', { author: actor, text: note })} className="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 text-xs font-bold rounded disabled:opacity-50">تعليق</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============== Approvals Tab ==============
function ApprovalsTab() {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [filterStatus, setFilterStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [selected, setSelected] = useState(null);

  const load = async () => {
    setBusy(true);
    try {
      const [s, l] = await Promise.all([
        axios.get(`${API}/approvals/stats`),
        axios.get(`${API}/approvals`, { params: { status: filterStatus || undefined, limit: 100 } }),
      ]);
      setStats(s.data?.data || null);
      setItems(l.data?.data || []);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filterStatus]);

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <KPI title="إجمالي" value={stats?.total ?? 0} color="indigo" testid="kpi-app-total"/>
        <KPI title="بانتظار" value={stats?.pending ?? 0} color="amber" testid="kpi-app-pending"/>
        <KPI title="معتمدة" value={stats?.by_status?.approved?.count ?? 0} color="emerald" testid="kpi-app-approved"/>
        <KPI title="مرفوضة" value={stats?.by_status?.rejected?.count ?? 0} color="rose" testid="kpi-app-rejected"/>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button data-testid="approval-create-btn" onClick={() => setShowCreate(true)} className="inline-flex items-center gap-1 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold">
          <FileCheck2 size={16}/> طلب موافقة جديد
        </button>
        <select data-testid="approvals-filter-status" value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="text-sm px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100">
          <option value="">كل الحالات</option>
          <option value="pending_review">بانتظار المراجعة</option>
          <option value="pending_approval">بانتظار الاعتماد</option>
          <option value="approved">معتمد</option>
          <option value="rejected">مرفوض</option>
          <option value="cancelled">ملغى</option>
        </select>
        <button data-testid="approvals-refresh-btn" onClick={load} disabled={busy} className="inline-flex items-center gap-1 px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-sm text-slate-700 dark:text-slate-200">
          <RefreshCw size={14} className={busy ? 'animate-spin' : ''}/> تحديث
        </button>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
        {items.length === 0 ? (
          <div className="p-10 text-center text-slate-500" data-testid="approvals-empty">
            <FileCheck2 className="mx-auto mb-2" size={36}/> لا توجد طلبات في هذه الحالة.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800 text-xs uppercase tracking-wider text-slate-600 dark:text-slate-400">
              <tr>
                <th className="px-3 py-2 text-right">العنوان</th>
                <th className="px-3 py-2 text-right">المبلغ</th>
                <th className="px-3 py-2 text-right">المستوى</th>
                <th className="px-3 py-2 text-right">المُنشئ</th>
                <th className="px-3 py-2 text-right">الحالة</th>
                <th className="px-3 py-2 text-right">التاريخ</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
              {items.map(a => (
                <tr key={a.id} data-testid={`approval-row-${a.id}`} className="hover:bg-slate-50 dark:hover:bg-slate-800/60">
                  <td className="px-3 py-2 text-slate-900 dark:text-slate-100 max-w-xs truncate">{a.title}</td>
                  <td className="px-3 py-2 whitespace-nowrap font-bold">{Number(a.amount || 0).toLocaleString('en-US')} ر.س</td>
                  <td className="px-3 py-2"><Pill cls="bg-indigo-100 text-indigo-800 border-indigo-300">{a.required_level}</Pill></td>
                  <td className="px-3 py-2 text-xs text-slate-600 dark:text-slate-300">{a.creator}</td>
                  <td className="px-3 py-2"><Pill cls={APP_STATUS_STYLE[a.status]}>{STATUS_LABELS[a.status] || a.status}</Pill></td>
                  <td className="px-3 py-2 text-xs text-slate-500">{a.created_at?.slice(0,10)}</td>
                  <td className="px-3 py-2">
                    <button data-testid={`approval-view-${a.id}`} onClick={() => setSelected(a)} className="text-indigo-600 hover:text-indigo-800 text-xs inline-flex items-center gap-1">
                      <Eye size={12}/> فحص
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showCreate && <CreateApprovalModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }}/>}
      {selected && <ApprovalDrawer approval={selected} onClose={() => setSelected(null)} onChanged={() => { setSelected(null); load(); }}/>}
    </div>
  );
}

function CreateApprovalModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ entity_type: 'expense', amount: '', creator: 'مدير', creator_role: 'admin', title: '', description: '' });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/approvals`, { ...form, amount: parseFloat(form.amount) || 0 });
      onCreated();
    } catch (e) {
      alert('خطأ: ' + (e.response?.data?.detail || e.message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose} dir="rtl">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-md w-full" onClick={e => e.stopPropagation()} data-testid="approval-create-modal">
        <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <h3 className="font-extrabold text-slate-900 dark:text-white">طلب موافقة جديد</h3>
          <button data-testid="approval-create-close" onClick={onClose}><X size={18}/></button>
        </div>
        <div className="p-4 space-y-3">
          <Field label="العنوان"><input data-testid="approval-form-title" value={form.title} onChange={e => setForm({...form, title: e.target.value})} className="w-full text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800"/></Field>
          <Field label="نوع العملية">
            <select data-testid="approval-form-entity-type" value={form.entity_type} onChange={e => setForm({...form, entity_type: e.target.value})} className="w-full text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800">
              <option value="expense">مصروف</option>
              <option value="purchase">شراء</option>
              <option value="journal_entry">قيد محاسبي</option>
              <option value="payment_order">أمر دفع</option>
              <option value="operation">عملية عامة</option>
            </select>
          </Field>
          <Field label="المبلغ (ر.س)"><input data-testid="approval-form-amount" type="number" step="0.01" value={form.amount} onChange={e => setForm({...form, amount: e.target.value})} className="w-full text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800"/></Field>
          <Field label="المُنشئ"><input data-testid="approval-form-creator" value={form.creator} onChange={e => setForm({...form, creator: e.target.value})} className="w-full text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800"/></Field>
          <Field label="الدور">
            <select data-testid="approval-form-role" value={form.creator_role} onChange={e => setForm({...form, creator_role: e.target.value})} className="w-full text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800">
              <option value="clerk">موظف</option>
              <option value="manager">مدير</option>
              <option value="senior_manager">مدير أول</option>
              <option value="director">مدير عام</option>
              <option value="admin">مسؤول</option>
            </select>
          </Field>
          <Field label="الوصف"><textarea data-testid="approval-form-desc" value={form.description} onChange={e => setForm({...form, description: e.target.value})} rows={2} className="w-full text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800"/></Field>
        </div>
        <div className="p-4 border-t border-slate-200 dark:border-slate-700 flex justify-end gap-2">
          <button data-testid="approval-create-cancel" onClick={onClose} className="px-4 py-1.5 text-sm rounded border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300">إلغاء</button>
          <button data-testid="approval-create-submit" disabled={busy || !form.title || !form.amount} onClick={submit} className="px-4 py-1.5 text-sm rounded bg-indigo-600 hover:bg-indigo-700 text-white font-bold disabled:opacity-50">{busy ? 'جاري...' : 'إرسال'}</button>
        </div>
      </div>
    </div>
  );
}

function ApprovalDrawer({ approval, onClose, onChanged }) {
  const [actor, setActor] = useState('مدير');
  const [role, setRole] = useState('manager');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const act = async (path, body) => {
    setBusy(true);
    try {
      await axios.post(`${API}/approvals/${approval.id}/${path}`, body);
      onChanged();
    } catch (e) {
      alert('خطأ: ' + (e.response?.data?.detail || e.message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose} dir="rtl">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="approval-drawer">
        <div className="flex items-start justify-between p-4 border-b border-slate-200 dark:border-slate-700">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <Pill cls="bg-indigo-100 text-indigo-800 border-indigo-300">{approval.required_level}</Pill>
              <Pill cls={APP_STATUS_STYLE[approval.status]}>{STATUS_LABELS[approval.status] || approval.status}</Pill>
            </div>
            <h3 className="text-lg font-extrabold text-slate-900 dark:text-white">{approval.title}</h3>
            <p className="text-xs text-slate-500 mt-0.5">{Number(approval.amount || 0).toLocaleString('en-US')} ر.س • {approval.entity_type}</p>
          </div>
          <button data-testid="approval-drawer-close" onClick={onClose} className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded"><X size={18}/></button>
        </div>

        <div className="p-4 space-y-3">
          <Section title="معلومات">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-slate-500">المُنشئ:</span> {approval.creator} ({approval.creator_role})</div>
              {approval.reviewer && <div><span className="text-slate-500">المُراجِع:</span> {approval.reviewer}</div>}
              {approval.approver && <div><span className="text-slate-500">المُعتمِد:</span> {approval.approver}</div>}
              <div><span className="text-slate-500">تاريخ الإنشاء:</span> {approval.created_at?.slice(0,16)}</div>
            </div>
          </Section>
          {approval.description && <Section title="الوصف"><p className="text-sm">{approval.description}</p></Section>}
          <Section title="سجل الإجراءات">
            <div className="space-y-1">
              {approval.actions?.map(a => (
                <div key={a.id} className="text-xs flex items-center gap-2 bg-slate-50 dark:bg-slate-800 p-2 rounded">
                  <Pill cls="bg-slate-200 text-slate-700">{a.action}</Pill>
                  <span className="font-bold">{a.actor}</span>
                  <span className="text-slate-500">{a.at?.slice(11,16)}</span>
                  {a.note && <span className="text-slate-600 mr-2">— {a.note}</span>}
                </div>
              ))}
            </div>
          </Section>
        </div>

        {!['approved','rejected','cancelled'].includes(approval.status) && (
          <div className="p-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 space-y-2">
            <div className="grid grid-cols-3 gap-2">
              <input data-testid="approval-actor-input" value={actor} onChange={e => setActor(e.target.value)} placeholder="اسم المنفّذ" className="text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900"/>
              <select data-testid="approval-role-select" value={role} onChange={e => setRole(e.target.value)} className="text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900">
                <option value="clerk">موظف</option>
                <option value="manager">مدير</option>
                <option value="senior_manager">مدير أول</option>
                <option value="director">مدير عام</option>
                <option value="admin">مسؤول</option>
              </select>
              <input data-testid="approval-note-input" value={note} onChange={e => setNote(e.target.value)} placeholder="ملاحظة" className="text-sm px-2 py-1.5 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900"/>
            </div>
            <div className="flex flex-wrap gap-2">
              {approval.status === 'pending_review' && (
                <button data-testid="approval-review-btn" disabled={busy} onClick={() => act('review', { reviewer: actor, reviewer_role: role, note })} className="px-3 py-1.5 bg-sky-600 hover:bg-sky-700 text-white text-xs font-bold rounded disabled:opacity-50">مراجعة</button>
              )}
              {approval.status === 'pending_approval' && (
                <button data-testid="approval-approve-btn" disabled={busy} onClick={() => act('approve', { approver: actor, approver_role: role, note })} className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded disabled:opacity-50">اعتماد</button>
              )}
              <button data-testid="approval-reject-btn" disabled={busy} onClick={() => act('reject', { actor, actor_role: role, note })} className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded disabled:opacity-50">رفض</button>
              <button data-testid="approval-cancel-btn" disabled={busy} onClick={() => act('cancel', { actor, note })} className="px-3 py-1.5 bg-slate-600 hover:bg-slate-700 text-white text-xs font-bold rounded disabled:opacity-50">إلغاء</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============== Matrix Tab ==============
function MatrixTab() {
  const [matrix, setMatrix] = useState([]);
  useEffect(() => {
    axios.get(`${API}/approvals/matrix`).then(r => setMatrix(r.data?.data || [])).catch(() => {});
  }, []);
  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden" data-testid="matrix-table">
      <div className="p-4 border-b border-slate-200 dark:border-slate-700">
        <h3 className="font-extrabold text-slate-900 dark:text-white">مصفوفة الموافقات المعتمدة</h3>
        <p className="text-xs text-slate-500 mt-1">المبالغ بالريال السعودي. التطبيق آلي عند إنشاء طلب جديد.</p>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-slate-50 dark:bg-slate-800 text-xs uppercase">
          <tr>
            <th className="px-3 py-2 text-right">من</th>
            <th className="px-3 py-2 text-right">إلى</th>
            <th className="px-3 py-2 text-right">المستوى</th>
            <th className="px-3 py-2 text-right">الأدوار المخوّلة</th>
            <th className="px-3 py-2 text-right">المسار</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
          {matrix.map((t, i) => (
            <tr key={i} data-testid={`matrix-row-${t.level}`} className="text-slate-900 dark:text-slate-100">
              <td className="px-3 py-2 font-bold">{t.min_amount.toLocaleString('en-US')}</td>
              <td className="px-3 py-2 font-bold">{t.max_amount?.toLocaleString('en-US') || '∞'}</td>
              <td className="px-3 py-2"><Pill cls="bg-indigo-100 text-indigo-800 border-indigo-300">{t.level}</Pill></td>
              <td className="px-3 py-2 text-xs">{t.required_roles.join(', ')}</td>
              <td className="px-3 py-2 text-xs text-slate-600 dark:text-slate-300">
                {t.level === 'auto' && 'موافقة آلية فورية'}
                {t.level === 'manager' && 'اعتماد مدير (Four Eyes)'}
                {t.level === 'senior_manager' && 'مراجعة + اعتماد مدير أول'}
                {t.level === 'director' && 'مراجعة + اعتماد مدير عام'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ============== Building blocks ==============
function KPI({ title, value, color, testid }) {
  const map = {
    rose: 'from-rose-500/10 to-rose-500/5 border-rose-200 text-rose-700 dark:text-rose-200 dark:border-rose-800',
    orange: 'from-orange-500/10 to-orange-500/5 border-orange-200 text-orange-700 dark:text-orange-200 dark:border-orange-800',
    amber: 'from-amber-500/10 to-amber-500/5 border-amber-200 text-amber-700 dark:text-amber-200 dark:border-amber-800',
    emerald: 'from-emerald-500/10 to-emerald-500/5 border-emerald-200 text-emerald-700 dark:text-emerald-200 dark:border-emerald-800',
    indigo: 'from-indigo-500/10 to-indigo-500/5 border-indigo-200 text-indigo-700 dark:text-indigo-200 dark:border-indigo-800',
  };
  return (
    <div data-testid={testid} className={`p-3 rounded-xl border bg-gradient-to-br ${map[color] || map.indigo} dark:bg-slate-900`}>
      <div className="text-xs font-bold opacity-80">{title}</div>
      <div className="text-xl font-extrabold mt-1">{value}</div>
    </div>
  );
}

function Pill({ cls, children }) {
  return <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold border ${cls || ''}`}>{children}</span>;
}

function Section({ title, children }) {
  return (
    <div>
      <div className="text-xs font-bold text-slate-500 dark:text-slate-400 mb-1">{title}</div>
      {children}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-bold text-slate-600 dark:text-slate-300 mb-1">{label}</label>
      {children}
    </div>
  );
}
