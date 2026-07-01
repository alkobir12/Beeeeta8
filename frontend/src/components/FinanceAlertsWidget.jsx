import React, { useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AlertTriangle, CheckCircle, RefreshCw, ShieldAlert, ChevronDown, ChevronUp, ArrowLeft } from 'lucide-react';
import { useFinanceAlerts } from '../hooks/useFinanceAlerts';

const SEV = {
  high: {
    icon: AlertTriangle,
    bar: 'border-red-500/60 bg-red-500/8',
    badge: 'bg-red-500/20 text-red-300 border-red-500/30',
    dot: 'bg-red-400',
    btn: 'border-red-500/40 text-red-300 hover:bg-red-500/15',
  },
  medium: {
    icon: ShieldAlert,
    bar: 'border-amber-500/60 bg-amber-500/8',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    dot: 'bg-amber-400',
    btn: 'border-amber-500/40 text-amber-300 hover:bg-amber-500/15',
  },
  low: {
    icon: CheckCircle,
    bar: 'border-emerald-500/40 bg-emerald-500/6',
    badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
    dot: 'bg-emerald-400',
    btn: 'border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/15',
  },
};

const SEV_LABEL = { high: 'عالي', medium: 'متوسط', low: 'منخفض' };

export default function FinanceAlertsWidget({
  enabledPaths = ['/', '/operations', '/accounting/chart-of-accounts', '/accounting/comprehensive', '/ai-financial', '/debts-followup'],
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const path = location.pathname || '';
  const enabled = useMemo(() => enabledPaths.includes(path), [enabledPaths, path]);

  const [isOpen, setIsOpen] = useState(false);
  const { data, isFetching, refetch, dataUpdatedAt } = useFinanceAlerts();
  const alerts = data?.alerts || [];
  const health = data?.health || null;
  const loading = isFetching;
  const lastUpdated = dataUpdatedAt ? new Date(dataUpdatedAt) : null;

  if (!enabled) return null;

  const highCount   = alerts.filter(a => a.severity === 'high').length;
  const mediumCount = alerts.filter(a => a.severity === 'medium').length;

  return (
    <div className="w-full" dir="rtl">
      {/* ─── شريط ملخص علوي ─────────────────────────────────────────────── */}
      <div className="sticky top-0 z-40">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="mt-2 rounded-xl border border-slate-800/70 bg-slate-950/90 backdrop-blur-xl px-3 py-2 flex items-center justify-between gap-2">

            {/* أيقونة + ملخص */}
            <div className="flex items-center gap-2">
              {loading ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin text-sky-400 flex-shrink-0" />
              ) : highCount > 0 ? (
                <AlertTriangle className="h-3.5 w-3.5 text-red-400 flex-shrink-0" />
              ) : mediumCount > 0 ? (
                <ShieldAlert className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
              ) : (
                <CheckCircle className="h-3.5 w-3.5 text-emerald-400 flex-shrink-0" />
              )}

              <span className="text-[11px] font-semibold text-slate-200 whitespace-nowrap">مراقب المحاسبة</span>

              {health && !loading && (
                <span
                  data-testid="alerts-health-chip"
                  title="درجة الصحة المالية — نفس مصدر جدار الحماية"
                  className={`rounded-full border text-[10px] px-1.5 py-0.5 font-semibold ${
                    health.score >= 90
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      : health.score >= 60
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                        : 'bg-red-500/20 text-red-300 border-red-500/30'
                  }`}
                >
                  🛡️ {health.score}/100
                </span>
              )}

              {!loading && alerts.length > 0 && (
                <div className="flex items-center gap-1.5">
                  {highCount > 0 && (
                    <span className="rounded-full bg-red-500/25 border border-red-500/30 text-red-300 text-[10px] px-1.5 py-0.5 font-semibold">
                      {highCount} عالي
                    </span>
                  )}
                  {mediumCount > 0 && (
                    <span className="rounded-full bg-amber-500/25 border border-amber-500/30 text-amber-300 text-[10px] px-1.5 py-0.5 font-semibold">
                      {mediumCount} متوسط
                    </span>
                  )}
                </div>
              )}

              {!loading && alerts.length === 0 && (
                <span className="text-[11px] text-slate-400">لا توجد تنبيهات</span>
              )}

              {lastUpdated && (
                <span className="text-[10px] text-slate-600 hidden sm:inline">
                  {lastUpdated.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>

            {/* أزرار */}
            <div className="flex items-center gap-1.5">
              {alerts.length > 0 && (
                <button
                  type="button"
                  onClick={() => setIsOpen(v => !v)}
                  className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 transition-colors"
                  data-testid="alerts-toggle-btn"
                >
                  {isOpen ? 'إخفاء' : 'التفاصيل'}
                  {isOpen ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                </button>
              )}
              <button
                type="button"
                onClick={() => refetch()}
                className="text-[11px] px-2 py-1 rounded-lg border border-slate-700 text-slate-400 hover:bg-slate-800 transition-colors"
                title="تحديث"
                data-testid="alerts-refresh-btn"
              >
                <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ─── قائمة التفاصيل ──────────────────────────────────────────────── */}
      {isOpen && alerts.length > 0 && (
        <div className="mx-auto max-w-7xl px-4 sm:px-6 mt-2 pb-1">
          <div className="space-y-1.5">
            {alerts.slice(0, 8).map((a) => {
              const cfg = SEV[a.severity] || SEV.low;
              const Icon = cfg.icon;
              return (
                <div
                  key={a.id}
                  className={`flex items-start gap-3 rounded-xl border px-3 py-2.5 ${cfg.bar}`}
                  data-testid={`alert-card-${a.id}`}
                >
                  {/* أيقونة */}
                  <div className="flex-shrink-0 mt-0.5">
                    <Icon size={14} className={`${cfg.badge.split(' ').find(c => c.startsWith('text-'))}`} />
                  </div>

                  {/* محتوى */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[11px] font-bold text-slate-100">{a.title}</span>
                      <span className={`text-[9px] rounded-full border px-1.5 py-0.5 font-semibold ${cfg.badge}`}>
                        {SEV_LABEL[a.severity] || a.severity}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-300 mt-0.5 leading-relaxed">
                      {a.message}
                    </p>
                    {a.action && (
                      <p className="text-[10px] text-slate-500 mt-0.5">{a.action}</p>
                    )}
                  </div>

                  {/* زر حل المشكلة / الاطلاع */}
                  {a.route && (
                    <button
                      type="button"
                      onClick={() => { navigate(a.route); setIsOpen(false); }}
                      className={`flex-shrink-0 flex items-center gap-1 text-[10px] rounded-lg border px-2.5 py-1.5 transition-colors font-medium whitespace-nowrap ${cfg.btn}`}
                      data-testid={`alert-action-btn-${a.id}`}
                    >
                      {a.route_label || 'حل المشكلة'}
                      <ArrowLeft size={10} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
