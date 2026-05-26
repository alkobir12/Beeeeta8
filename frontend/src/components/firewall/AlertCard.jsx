import React from 'react';
import {
  AlertTriangle, AlertOctagon, Info, Shield, Wrench, Eye, X, Check, Sparkles,
} from 'lucide-react';

/**
 * 🚨 Smart Alert Card
 * بطاقة تنبيه تفاعلية تحوي:
 *  • عنوان + الخطورة
 *  • السبب الجذري + التأثير المالي
 *  • أزرار: عرض التفاصيل / Auto-Fix / تجاهل / تعليم كمحلول
 */

const SEVERITY_STYLES = {
  critical: {
    bg: 'bg-rose-50 dark:bg-rose-950/40',
    border: 'border-rose-400 dark:border-rose-600',
    badge: 'bg-rose-600 text-white',
    icon: AlertOctagon,
    iconColor: 'text-rose-500',
    label: 'حرج',
  },
  high: {
    bg: 'bg-orange-50 dark:bg-orange-950/40',
    border: 'border-orange-400 dark:border-orange-600',
    badge: 'bg-orange-600 text-white',
    icon: AlertTriangle,
    iconColor: 'text-orange-500',
    label: 'عالي',
  },
  medium: {
    bg: 'bg-amber-50 dark:bg-amber-950/40',
    border: 'border-amber-400 dark:border-amber-600',
    badge: 'bg-amber-600 text-white',
    icon: AlertTriangle,
    iconColor: 'text-amber-500',
    label: 'متوسط',
  },
  low: {
    bg: 'bg-sky-50 dark:bg-sky-950/40',
    border: 'border-sky-400 dark:border-sky-600',
    badge: 'bg-sky-600 text-white',
    icon: Info,
    iconColor: 'text-sky-500',
    label: 'منخفض',
  },
  info: {
    bg: 'bg-slate-50 dark:bg-slate-800',
    border: 'border-slate-300 dark:border-slate-600',
    badge: 'bg-slate-600 text-white',
    icon: Info,
    iconColor: 'text-slate-500',
    label: 'معلومة',
  },
};

const CATEGORY_LABELS = {
  balance_integrity: 'توازن القيود',
  duplicate_detection: 'كشف التكرار',
  consistency: 'اتساق البيانات',
  anomaly: 'شذوذ',
  integrity: 'نزاهة',
  overdue: 'متأخرات',
};

const formatSar = (v) => {
  const n = Number(v || 0);
  return new Intl.NumberFormat('ar-SA', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + ' ر.س';
};

export const AlertCard = ({ alert, onDetails, onAutoFix, onDismiss, onResolve, busy }) => {
  const sev = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.info;
  const Icon = sev.icon;
  const canAutoFix = alert.auto_fix === 'auto';
  const canGuidedFix = alert.auto_fix === 'guided';

  return (
    <div
      data-testid={`alert-card-${alert.id}`}
      className={`relative ${sev.bg} ${sev.border} border-2 rounded-2xl p-4 shadow-md hover:shadow-lg transition-shadow`}
    >
      {/* header */}
      <div className="flex items-start gap-3">
        <div className={`flex-shrink-0 p-2 rounded-full bg-white dark:bg-slate-900 ${sev.iconColor}`}>
          <Icon size={22} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center flex-wrap gap-2 mb-1">
            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${sev.badge}`}>{sev.label}</span>
            <span className="text-[10px] font-bold text-slate-600 dark:text-slate-300 bg-white/70 dark:bg-slate-900/70 px-2 py-0.5 rounded-full border border-slate-300 dark:border-slate-600">
              {CATEGORY_LABELS[alert.category] || alert.category}
            </span>
            {alert.financial_impact > 0 && (
              <span className="text-[10px] font-bold text-rose-700 dark:text-rose-200 bg-rose-100 dark:bg-rose-900/60 px-2 py-0.5 rounded-full border border-rose-300 dark:border-rose-700">
                {formatSar(alert.financial_impact)}
              </span>
            )}
          </div>
          <h4 className="font-extrabold text-base text-slate-900 dark:text-slate-50 leading-snug" data-testid={`alert-title-${alert.id}`}>
            {alert.title}
          </h4>
          <p className="text-xs text-slate-700 dark:text-slate-200 mt-1 leading-relaxed">{alert.description}</p>
          {alert.root_cause && (
            <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-2 italic">السبب: {alert.root_cause}</p>
          )}
        </div>
      </div>

      {/* affected accounts mini-chips */}
      {Array.isArray(alert.affected_accounts) && alert.affected_accounts.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {alert.affected_accounts.slice(0, 4).map((acc, i) => (
            <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-slate-200/60 dark:bg-slate-700/60 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-600">
              {acc}
            </span>
          ))}
          {alert.affected_accounts.length > 4 && (
            <span className="text-[10px] px-2 py-0.5 text-slate-500">+{alert.affected_accounts.length - 4}</span>
          )}
        </div>
      )}

      {/* actions */}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          data-testid={`alert-action-details-${alert.id}`}
          onClick={() => onDetails?.(alert)}
          className="text-xs px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-800 text-white font-semibold inline-flex items-center gap-1 transition-colors"
        >
          <Eye size={12} /> التفاصيل
        </button>
        {canAutoFix && (
          <button
            data-testid={`alert-action-autofix-${alert.id}`}
            onClick={() => onAutoFix?.(alert)}
            disabled={busy}
            className="text-xs px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold inline-flex items-center gap-1 disabled:opacity-50 transition-colors"
          >
            <Wrench size={12} /> {busy ? '...' : 'إصلاح تلقائي'}
          </button>
        )}
        {canGuidedFix && (
          <button
            data-testid={`alert-action-guided-${alert.id}`}
            onClick={() => onDetails?.(alert)}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold inline-flex items-center gap-1 transition-colors"
          >
            <Sparkles size={12} /> خطوات الإصلاح
          </button>
        )}
        <button
          data-testid={`alert-action-resolve-${alert.id}`}
          onClick={() => onResolve?.(alert)}
          disabled={busy}
          className="text-xs px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 text-white font-semibold inline-flex items-center gap-1 disabled:opacity-50 transition-colors"
        >
          <Check size={12} /> محلول
        </button>
        <button
          data-testid={`alert-action-dismiss-${alert.id}`}
          onClick={() => onDismiss?.(alert)}
          disabled={busy}
          className="text-xs px-3 py-1.5 rounded-lg bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-600 font-semibold inline-flex items-center gap-1 border border-slate-300 dark:border-slate-500 disabled:opacity-50 transition-colors"
        >
          <X size={12} /> تجاهل 24س
        </button>
      </div>
    </div>
  );
};

export default AlertCard;
