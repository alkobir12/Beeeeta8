import React from 'react';
import { useNavigate } from 'react-router-dom';
import { X, Wrench, Check, AlertCircle, Database, Calendar, Hash, ExternalLink } from 'lucide-react';

const formatSar = (v) => new Intl.NumberFormat('ar-SA', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v || 0)) + ' ر.س';

export const AlertDetailsDrawer = ({ alert, onClose, onAutoFix, onResolve, busy }) => {
  const navigate = useNavigate();
  if (!alert) return null;
  const canAutoFix = alert.auto_fix === 'auto';

  // 🎯 Determine the best landing page for the source-link button.
  // Priority: explicit alert.action_url > category-based mapping > related_entries fallback.
  const buildSourceUrl = () => {
    if (alert.action_url) return alert.action_url;
    const cat = String(alert.category || alert.type || '').toLowerCase();
    const refId = Array.isArray(alert.related_entries) && alert.related_entries.length
      ? String(alert.related_entries[0])
      : (alert.reference_id || alert.entity_id || '');

    // Journal-entry-related alerts
    if (cat.includes('ledger') || cat.includes('journal') || cat.includes('orphan')) {
      return refId ? `/accounting/journal-entries?ref=${encodeURIComponent(refId)}` : '/accounting/journal-entries';
    }
    // Operation-related alerts
    if (cat.includes('operation') || cat.includes('duplicate') || cat.includes('mismatch') || cat.includes('visit')) {
      return refId ? `/operations?ref=${encodeURIComponent(refId)}` : '/operations';
    }
    // Account / chart issues
    if (cat.includes('account') || cat.includes('chart') || cat.includes('balance')) {
      return '/accounting/chart-of-accounts';
    }
    // AR / AP issues
    if (cat.includes('debt') || cat.includes('ar_') || cat.includes('ap_') || cat.includes('overdue')) {
      return '/debts-followup';
    }
    // Generic fallback — comprehensive financial statements
    return refId ? `/operations?ref=${encodeURIComponent(refId)}` : '/accounting/comprehensive';
  };

  const goToSource = () => {
    const url = buildSourceUrl();
    onClose?.();
    navigate(url);
  };

  return (
    <div
      data-testid="alert-details-drawer"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
      dir="rtl"
    >
      <div
        className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border-2 border-slate-300 dark:border-slate-600 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="sticky top-0 bg-gradient-to-r from-slate-800 to-slate-900 px-5 py-4 border-b-2 border-slate-300 dark:border-slate-600 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <AlertCircle className="text-amber-400 flex-shrink-0" size={20} />
            <h3 className="text-base font-extrabold text-white truncate">{alert.title}</h3>
          </div>
          <button
            data-testid="alert-details-close"
            onClick={onClose}
            className="text-white/80 hover:text-white p-1.5 rounded hover:bg-white/10 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* body */}
        <div className="p-5 space-y-4">
          {/* meta */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-slate-100 dark:bg-slate-800 rounded-lg p-3 border border-slate-300 dark:border-slate-600">
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-bold mb-1">الخطورة</p>
              <p className="text-sm font-extrabold text-slate-900 dark:text-slate-50">{alert.severity}</p>
            </div>
            <div className="bg-slate-100 dark:bg-slate-800 rounded-lg p-3 border border-slate-300 dark:border-slate-600">
              <p className="text-[10px] text-slate-500 dark:text-slate-400 font-bold mb-1">التأثير المالي</p>
              <p className="text-sm font-extrabold text-rose-700 dark:text-rose-300">{formatSar(alert.financial_impact)}</p>
            </div>
          </div>

          {/* description */}
          <div>
            <h4 className="text-xs font-bold text-slate-500 dark:text-slate-400 mb-1">الشرح</h4>
            <p className="text-sm text-slate-900 dark:text-slate-100 leading-relaxed">{alert.description}</p>
          </div>

          {/* root cause */}
          {alert.root_cause && (
            <div>
              <h4 className="text-xs font-bold text-slate-500 dark:text-slate-400 mb-1">السبب الجذري</h4>
              <p className="text-sm text-slate-900 dark:text-slate-100 leading-relaxed">{alert.root_cause}</p>
            </div>
          )}

          {/* affected accounts */}
          {Array.isArray(alert.affected_accounts) && alert.affected_accounts.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-slate-500 dark:text-slate-400 mb-1">الحسابات المتأثرة</h4>
              <div className="flex flex-wrap gap-1.5">
                {alert.affected_accounts.map((acc, i) => (
                  <span key={i} className="text-xs px-2.5 py-1 rounded bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-100 border border-slate-300 dark:border-slate-600 font-semibold">
                    {acc}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* evidence */}
          {alert.evidence && (
            <div>
              <h4 className="text-xs font-bold text-slate-500 dark:text-slate-400 mb-1 flex items-center gap-1">
                <Database size={12} /> الأدلة
              </h4>
              <div className="bg-slate-900 dark:bg-slate-950 text-emerald-300 p-3 rounded-lg text-[11px] font-mono overflow-x-auto leading-relaxed border border-slate-700">
                <pre>{JSON.stringify(alert.evidence, null, 2)}</pre>
              </div>
            </div>
          )}

          {/* related entries */}
          {Array.isArray(alert.related_entries) && alert.related_entries.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-slate-500 dark:text-slate-400 mb-1 flex items-center gap-1">
                <Hash size={12} /> العمليات/القيود المرتبطة
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {alert.related_entries.map((id, i) => (
                  <code key={i} className="text-[10px] px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-600">
                    {String(id).slice(0, 8)}
                  </code>
                ))}
              </div>
            </div>
          )}

          {/* auto-fix preview */}
          {alert.auto_fix_preview && (
            <div className="bg-emerald-50 dark:bg-emerald-950/30 border-2 border-emerald-300 dark:border-emerald-700 rounded-lg p-3">
              <h4 className="text-xs font-bold text-emerald-700 dark:text-emerald-300 mb-1 flex items-center gap-1">
                <Wrench size={12} /> {canAutoFix ? 'إصلاح آلي متاح' : 'خطوات الإصلاح المقترحة'}
              </h4>
              <p className="text-xs text-emerald-900 dark:text-emerald-100 leading-relaxed">
                {alert.auto_fix_preview.message || JSON.stringify(alert.auto_fix_preview, null, 2)}
              </p>
            </div>
          )}

          {/* timeline */}
          <div>
            <h4 className="text-xs font-bold text-slate-500 dark:text-slate-400 mb-1 flex items-center gap-1">
              <Calendar size={12} /> أُنشئ التنبيه
            </h4>
            <p className="text-xs text-slate-700 dark:text-slate-200">{alert.created_at}</p>
          </div>
        </div>

        {/* footer actions */}
        <div className="sticky bottom-0 bg-slate-100 dark:bg-slate-800 px-5 py-3 border-t-2 border-slate-300 dark:border-slate-600 flex flex-wrap gap-2 justify-end">
          <button
            data-testid="alert-details-source"
            onClick={goToSource}
            disabled={busy}
            className="text-sm px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold inline-flex items-center gap-1 disabled:opacity-50 transition-colors"
            title="انتقل إلى مكان المشكلة بالضبط"
          >
            <ExternalLink size={14} /> اذهب إلى المصدر
          </button>
          {canAutoFix && (
            <button
              data-testid="alert-details-autofix"
              onClick={() => onAutoFix?.(alert)}
              disabled={busy}
              className="text-sm px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold inline-flex items-center gap-1 disabled:opacity-50 transition-colors"
            >
              <Wrench size={14} /> {busy ? 'جاري...' : 'تنفيذ الإصلاح الآلي'}
            </button>
          )}
          <button
            data-testid="alert-details-resolve"
            onClick={() => onResolve?.(alert)}
            disabled={busy}
            className="text-sm px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white font-bold inline-flex items-center gap-1 disabled:opacity-50 transition-colors"
          >
            <Check size={14} /> تعليم كمحلول
          </button>
          <button
            data-testid="alert-details-close-btn"
            onClick={onClose}
            className="text-sm px-4 py-2 rounded-lg bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-100 border border-slate-300 dark:border-slate-500 font-bold hover:bg-slate-100 dark:hover:bg-slate-600 transition-colors"
          >
            إغلاق
          </button>
        </div>
      </div>
    </div>
  );
};

export default AlertDetailsDrawer;
