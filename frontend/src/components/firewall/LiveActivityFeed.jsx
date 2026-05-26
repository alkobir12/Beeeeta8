import React from 'react';
import { Activity, Receipt, ArrowDownCircle, ArrowUpCircle } from 'lucide-react';

const formatSar = (v) => new Intl.NumberFormat('ar-SA', { minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(Number(v || 0)) + ' ر.س';

const formatRelTime = (iso) => {
  if (!iso) return '';
  try {
    const t = new Date(iso).getTime();
    const diff = (Date.now() - t) / 1000;
    if (diff < 60) return 'الآن';
    if (diff < 3600) return `قبل ${Math.floor(diff / 60)} د`;
    if (diff < 86400) return `قبل ${Math.floor(diff / 3600)} س`;
    return `قبل ${Math.floor(diff / 86400)} يوم`;
  } catch (e) {
    return '';
  }
};

const SOURCE_LABEL = {
  operation: 'عملية',
  operation_payment: 'تحصيل آجل',
  operation_payment_income: 'تحصيل نقدي',
  operation_cogs: 'تكلفة بضاعة',
  manual: 'يدوي',
  period_close: 'إقفال فترة',
  test: 'اختبار',
  visit_receipt_voucher: 'سند قبض',
  firewall_adjustment: 'تسوية جدار',
};

export const LiveActivityFeed = ({ activity = [], loading = false }) => {
  return (
    <div data-testid="firewall-live-activity" className="bg-gradient-to-br from-slate-900/95 to-slate-800/95 dark:from-slate-900 dark:to-slate-800 rounded-2xl border-2 border-slate-700 shadow-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="relative p-2 rounded-lg bg-emerald-600/30">
          <Activity className="text-emerald-300" size={20} />
          <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 rounded-full animate-pulse" />
        </div>
        <div>
          <h3 className="text-base font-extrabold text-white">المراقبة الحية</h3>
          <p className="text-[11px] text-slate-400">آخر القيود في النظام</p>
        </div>
      </div>

      {loading ? (
        <div className="text-slate-400 text-sm py-4 text-center">جاري التحميل…</div>
      ) : activity.length === 0 ? (
        <div className="text-slate-400 text-sm py-4 text-center">لا توجد قيود حديثة.</div>
      ) : (
        <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
          {activity.map((a, i) => {
            const isExpense = String(a.source || '').includes('cogs') || String(a.description || '').includes('مصروف') || String(a.description || '').includes('سداد');
            return (
              <div
                key={a.id || i}
                data-testid={`firewall-live-entry-${i}`}
                className="bg-slate-800/60 hover:bg-slate-700/70 transition-colors rounded-lg p-3 border border-slate-700/80"
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2 min-w-0">
                    {isExpense ? (
                      <ArrowUpCircle className="text-rose-400 flex-shrink-0" size={16} />
                    ) : (
                      <ArrowDownCircle className="text-emerald-400 flex-shrink-0" size={16} />
                    )}
                    <span className="text-[10px] font-bold text-indigo-300 bg-indigo-900/60 px-1.5 py-0.5 rounded">
                      {SOURCE_LABEL[a.source] || a.source || 'قيد'}
                    </span>
                    <span className="text-[10px] text-slate-400">{formatRelTime(a.date)}</span>
                  </div>
                  <span className="text-sm font-extrabold text-white flex-shrink-0">{formatSar(a.total)}</span>
                </div>
                <p className="text-xs text-slate-200 line-clamp-2 leading-snug pr-6">
                  <Receipt className="inline ml-1 text-slate-500" size={11} />
                  {a.description || '—'}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default LiveActivityFeed;
