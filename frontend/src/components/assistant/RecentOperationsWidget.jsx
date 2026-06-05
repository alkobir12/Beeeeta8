import React, { useEffect, useState, useCallback } from 'react';
import { CheckCircle2, Clock, XCircle, RotateCcw, Sparkles, ChevronUp, ChevronDown, RefreshCw } from 'lucide-react';

/**
 * 🆕 Phase 3C.7 — Mini "Recent Executed Operations" widget.
 *
 * Listens for `assistant:executed` events emitted by AssistantProvider when
 * the bot routes through /api/runtime/execute. Also polls /api/runtime/executions
 * so it stays fresh even when the user opens the page later.
 *
 * Two modes:
 *   • `variant="drawer"` — used inside the Floating Assistant (compact)
 *   • `variant="page"`   — used on Vehicles/Customers/Operations pages
 *
 * Each entry shows the result, status, and quick rollback action.
 */
const STATUS_META = {
  committed: { Icon: CheckCircle2, label: 'مُنفّذة', tone: 'text-emerald-600 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800' },
  pending_approval: { Icon: Clock, label: 'بانتظار اعتماد', tone: 'text-amber-600 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800' },
  approved: { Icon: CheckCircle2, label: 'مُعتمدة', tone: 'text-indigo-600 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800' },
  rejected: { Icon: XCircle, label: 'مرفوضة', tone: 'text-rose-600 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800' },
  rolled_back: { Icon: RotateCcw, label: 'مُلغاة', tone: 'text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700' },
  read_only: { Icon: Sparkles, label: 'استعلام', tone: 'text-cyan-600 dark:text-cyan-300 bg-cyan-50 dark:bg-cyan-950/40 border-cyan-200 dark:border-cyan-800' },
  rejected_action: { Icon: XCircle, label: 'لم تُفهم', tone: 'text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700' },
};

const ACTION_LABEL = {
  create_customer: '👤 عميل',
  customer: '👤 عميل',
  create_vehicle: '🚗 مركبة',
  vehicle: '🚗 مركبة',
  create_visit: '📋 زيارة',
  visit: '📋 زيارة',
  close_visits: '🔒 إغلاق زيارات',
  get_active_visits: '🔍 زيارات نشطة',
  unknown: '❓ غير محدد',
};

const API_URL = (typeof window !== 'undefined' && window.process?.env?.REACT_APP_BACKEND_URL)
  || process.env.REACT_APP_BACKEND_URL || '';

export const RecentOperationsWidget = ({ variant = 'drawer', limit = 8, filterAction = null, className = '' }) => {
  const [items, setItems] = useState([]);
  const [collapsed, setCollapsed] = useState(false);
  const [loading, setLoading] = useState(false);

  const fetchExecutions = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API_URL}/api/runtime/executions?limit=${limit}`);
      const data = await r.json();
      let rows = data?.data || [];
      if (filterAction) {
        rows = rows.filter((x) => {
          const a = (x.action || x.draft_action || '').toLowerCase();
          return Array.isArray(filterAction) ? filterAction.includes(a) : a === filterAction;
        });
      }
      setItems(rows);
    } catch (e) {
      // silent — widget should never block the page
    } finally {
      setLoading(false);
    }
  }, [limit, filterAction]);

  useEffect(() => {
    fetchExecutions();
    const id = setInterval(fetchExecutions, 15000);  // 15s refresh
    const onEv = () => fetchExecutions();
    window.addEventListener('assistant:executed', onEv);
    window.addEventListener('runtime:changed', onEv);
    return () => {
      clearInterval(id);
      window.removeEventListener('assistant:executed', onEv);
      window.removeEventListener('runtime:changed', onEv);
    };
  }, [fetchExecutions]);

  const handleRollback = async (executionId) => {
    if (!executionId) return;
    if (!window.confirm('هل تريد التراجع عن هذه العملية؟')) return;
    try {
      let user = 'anonymous';
      try {
        const u = JSON.parse(localStorage.getItem('user') || 'null');
        user = u?.name || u?.username || 'anonymous';
      } catch (e) { /* noop */ }
      await fetch(`${API_URL}/api/runtime/rollback/${executionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rollbacker: user }),
      });
      window.dispatchEvent(new CustomEvent('runtime:changed'));
      fetchExecutions();
    } catch (e) { /* swallow */ }
  };

  if (variant === 'page' && items.length === 0 && !loading) {
    return null;  // hide empty widget on pages
  }

  const isCompact = variant === 'drawer';

  return (
    <div
      data-testid="recent-operations-widget"
      className={`rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900/80 shadow-sm overflow-hidden ${className}`}
    >
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="w-full px-3 py-2 flex items-center gap-2 bg-gradient-to-l from-emerald-500/10 to-indigo-500/10 dark:from-emerald-900/30 dark:to-indigo-900/30 hover:from-emerald-500/20 hover:to-indigo-500/20 transition-all"
        data-testid="recent-ops-toggle"
      >
        <Sparkles size={isCompact ? 12 : 14} className="text-emerald-600 dark:text-emerald-400" />
        <span className={`flex-1 text-right ${isCompact ? 'text-[11px]' : 'text-[13px]'} font-bold text-slate-700 dark:text-slate-200`}>
          العمليات المُنفّذة بالمساعد
        </span>
        <span data-testid="recent-ops-count" className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-300 font-bold">
          {items.length}
        </span>
        <button
          onClick={(e) => { e.stopPropagation(); fetchExecutions(); }}
          className="p-1 rounded hover:bg-white/30 dark:hover:bg-black/30 transition-colors"
          title="تحديث"
          data-testid="recent-ops-refresh"
        >
          <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
        </button>
        {collapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
      </button>

      {!collapsed && (
        <div className={`px-2 py-1.5 ${isCompact ? 'max-h-[160px]' : 'max-h-[260px]'} overflow-y-auto space-y-1.5`}>
          {items.length === 0 ? (
            <div className="text-center text-[11px] text-slate-400 dark:text-slate-500 py-4">
              {loading ? 'جاري التحميل…' : 'لم تُنفّذ عمليات بعد. جرّب: "سجل عميل جديد"'}
            </div>
          ) : items.map((it) => {
            const draft = it.draft || {};
            const action = draft.action || it.action || 'unknown';
            const status = it.status || draft.status || 'committed';
            const meta = STATUS_META[status] || STATUS_META.committed;
            const Icon = meta.Icon;
            const resultName = (it.result || {}).name || (it.result || {}).id || '';
            const ts = it.committed_at || it.ts || 0;
            const timeStr = ts ? new Date(ts * 1000).toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }) : '';
            return (
              <div
                key={it.id || it.execution_id}
                data-testid={`recent-op-${it.id || it.execution_id}`}
                className={`flex items-center gap-2 rounded-lg border ${meta.tone} px-2 py-1.5 text-[11px] transition-all hover:shadow-sm`}
              >
                <Icon size={12} className="flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-bold truncate">
                    {ACTION_LABEL[action] || action}
                    {resultName && <span className="font-normal opacity-80"> — {String(resultName).slice(0, 20)}</span>}
                  </div>
                  <div className="flex items-center gap-1.5 opacity-70 text-[10px]">
                    <span>{meta.label}</span>
                    {timeStr && <><span>•</span><span>{timeStr}</span></>}
                    {it.committer && <><span>•</span><span>{it.committer}</span></>}
                  </div>
                </div>
                {status === 'committed' && (
                  <button
                    onClick={() => handleRollback(it.id || it.execution_id)}
                    className="p-1 rounded hover:bg-rose-100 dark:hover:bg-rose-950/60 text-rose-500 hover:text-rose-700 transition-colors"
                    title="التراجع عن العملية"
                    data-testid={`recent-op-rollback-${it.id}`}
                  >
                    <RotateCcw size={11} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default RecentOperationsWidget;
