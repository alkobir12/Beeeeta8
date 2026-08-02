import React from 'react';
import { Calculator, ReceiptText } from 'lucide-react';

const formatMoney = (value) => {
  const n = Number(value || 0);
  try {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: n % 1 === 0 ? 0 : 2,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return n.toFixed(2);
  }
};

const StatCard = ({ title, value, subtitle, accent = 'slate', testId, onShowSource, sourceKey }) => {
  const accentMap = {
    emerald: {
      bg: 'rgba(16,185,129,0.10)',
      border: 'rgba(16,185,129,0.22)',
      text: 'rgba(167,243,208,0.95)',
    },
    rose: {
      bg: 'rgba(244,63,94,0.10)',
      border: 'rgba(244,63,94,0.22)',
      text: 'rgba(254,202,202,0.95)',
    },
    sky: {
      bg: 'rgba(56,189,248,0.10)',
      border: 'rgba(56,189,248,0.22)',
      text: 'rgba(186,230,253,0.95)',
    },
    violet: {
      bg: 'rgba(168,85,247,0.10)',
      border: 'rgba(168,85,247,0.22)',
      text: 'rgba(233,213,255,0.95)',
    },
    slate: {
      bg: 'rgba(255,255,255,0.06)',
      border: 'rgba(148,163,184,0.20)',
      text: 'rgba(226,232,240,0.92)',
    },
  };

  const c = accentMap[accent] || accentMap.slate;

  return (
    <div
      className="dash-widget-shell"
      data-testid={testId}
      style={{
        background:
          `radial-gradient(circle at 12% 18%, ${c.bg}, transparent 55%), rgba(255,255,255,0.06)`,
        border: `1px solid ${c.border}`,
        boxShadow: '0 18px 60px rgba(2,6,23,0.55)',
        backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)',
        padding: 12,
      }}
    >
      <div className="text-[11px] sm:text-xs font-medium" style={{ color: 'rgba(226,232,240,0.72)' }} data-testid={`${testId}-title`}>{title}</div>
      <div className="mt-1 text-lg sm:text-2xl font-extrabold tabular-nums" style={{ color: c.text }} data-testid={`${testId}-value`}>
        {formatMoney(value)}
        <span className="text-xs font-medium" style={{ color: 'rgba(226,232,240,0.65)', marginInlineStart: 6 }}>
          {subtitle ? '' : 'ر.س'}
        </span>
      </div>
      {subtitle ? (
        <div className="mt-1 text-xs" style={{ color: 'rgba(226,232,240,0.65)' }} data-testid={`${testId}-subtitle`}>{subtitle}</div>
      ) : (
        <div className="mt-1 text-[11px]" style={{ color: 'rgba(226,232,240,0.55)' }} data-testid={`${testId}-subtitle`}>
          {title}
        </div>
      )}
      {typeof onShowSource === 'function' ? (
        <button
          type="button"
          onClick={() => onShowSource(sourceKey)}
          className="mt-2 text-[11px] px-2 py-1 rounded-lg"
          style={{
            background: 'rgba(255,255,255,0.08)',
            border: '1px solid rgba(148,163,184,0.18)',
            color: 'rgba(186,230,253,0.95)',
          }}
          data-testid={`${testId}-source-button`}
        >
          عرض المصدر
        </button>
      ) : null}
    </div>
  );
};

export default function VehicleFinancialSummary({ summary, t, onShowSource }) {
  const s = summary || {};
  const totalItems = Number(s.total_items ?? s.total_amount ?? ((Number(s.total_workshop || 0) + Number(s.total_suppliers || 0))));
  const advancePaid = Number(s.advance_paid || 0);
  const paidOnAccount = Number(s.paid_on_account ?? s.confirmed_paid ?? Math.max(Number(s.total_paid || 0) - advancePaid, 0));
  const totalPaid = Number(s.total_paid ?? (advancePaid + paidOnAccount));
  const balance = Number(s.display_remaining ?? s.balance ?? (totalItems - totalPaid));

  const safeT = (key, fallback) => {
    const v = t?.(key);
    if (!v || v === key) return fallback;
    return v;
  };

  const balanceAccent = balance === 0 ? 'emerald' : balance > 0 ? 'rose' : 'sky';

  return (
    <div className="space-y-3" data-testid="vehicle-financial-summary-layout">
      <div
        className="dash-widget-shell overflow-hidden"
        style={{
          background:
            'linear-gradient(135deg, rgba(15,23,42,0.94), rgba(17,24,39,0.88)), radial-gradient(circle at 12% 18%, rgba(45,212,191,0.18), transparent 42%)',
          border: '1px solid rgba(45,212,191,0.22)',
          boxShadow: '0 18px 60px rgba(2,6,23,0.55)',
          padding: 16,
        }}
        data-testid="vehicle-financial-summary-grand-total-card"
      >
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs font-semibold" style={{ color: 'rgba(153,246,228,0.9)' }}>
              <Calculator size={16} />
              <span data-testid="vehicle-financial-summary-grand-total-title">إجمالي البنود بعد الدفعات</span>
            </div>
            <div
              className="mt-2 text-2xl sm:text-4xl font-black tabular-nums"
              style={{ color: balance < 0 ? 'rgba(186,230,253,0.98)' : 'rgba(240,253,250,0.98)' }}
              data-testid="vehicle-financial-summary-grand-total-value"
            >
              {formatMoney(balance)} <span className="text-sm font-medium" style={{ color: 'rgba(226,232,240,0.68)' }}>ر.س</span>
            </div>
            <div className="mt-1 text-xs" style={{ color: 'rgba(226,232,240,0.68)' }} data-testid="vehicle-financial-summary-grand-total-formula">
              الموردين + ذمم الورشة - الدفعات
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 min-w-[220px]">
            <div className="rounded-xl px-3 py-2" style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(148,163,184,0.18)' }} data-testid="vehicle-financial-summary-total-items-mini">
              <div className="text-[11px]" style={{ color: 'rgba(226,232,240,0.62)' }}>إجمالي البنود</div>
              <div className="text-sm font-extrabold tabular-nums" style={{ color: 'rgba(240,253,250,0.95)' }}>{formatMoney(totalItems)}</div>
            </div>
            <div className="rounded-xl px-3 py-2" style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(148,163,184,0.18)' }} data-testid="vehicle-financial-summary-total-paid-mini">
              <div className="text-[11px]" style={{ color: 'rgba(226,232,240,0.62)' }}>مطروح المدفوع</div>
              <div className="text-sm font-extrabold tabular-nums" style={{ color: 'rgba(167,243,208,0.95)' }}>{formatMoney(totalPaid)}</div>
            </div>
            <button
              type="button"
              onClick={() => onShowSource?.('display_total')}
              className="rounded-xl px-3 py-2 text-xs font-bold inline-flex items-center justify-center gap-2 col-span-2 sm:col-span-1"
              style={{ background: 'rgba(45,212,191,0.13)', border: '1px solid rgba(45,212,191,0.24)', color: 'rgba(153,246,228,0.95)' }}
              data-testid="vehicle-financial-summary-grand-total-source-button"
            >
              <ReceiptText size={14} /> المصدر
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 sm:gap-3" data-testid="vehicle-financial-summary-breakdown-grid">
        <StatCard
          title={safeT('vehicle_finance.workshop_due', 'ذمم الورشة')}
          value={s.total_workshop}
          subtitle={safeT('vehicle_finance.workshop_due_hint', 'إيراد الورشة / ذمة العميل')}
          accent="violet"
          testId="vehicle-financial-summary-workshop-due"
          onShowSource={onShowSource}
          sourceKey="workshop_due"
        />
        <StatCard
          title={safeT('vehicle_finance.suppliers_due', 'الموردين')}
          value={s.total_suppliers}
          subtitle={safeT('vehicle_finance.suppliers_due_hint', 'أرشيف تكلفة داخلي')}
          accent="rose"
          testId="vehicle-financial-summary-suppliers-due"
          onShowSource={onShowSource}
          sourceKey="suppliers_due"
        />
        <StatCard
          title="دفعة مقدمة"
          value={advancePaid}
          subtitle="تظهر كرصيد/التزام للعميل"
          accent="sky"
          testId="vehicle-financial-summary-advance-paid"
          onShowSource={onShowSource}
          sourceKey="advance"
        />
        <StatCard
          title="تحت الحساب / تأكيد سداد"
          value={paidOnAccount}
          subtitle="دفعات مؤكدة على الزيارة"
          accent="emerald"
          testId="vehicle-financial-summary-paid-on-account"
          onShowSource={onShowSource}
          sourceKey="on_account"
        />
        <StatCard
          title={safeT('vehicle_finance.total_paid', 'إجمالي المدفوع')}
          value={totalPaid}
          accent="emerald"
          testId="vehicle-financial-summary-total-paid"
          onShowSource={onShowSource}
          sourceKey="paid"
        />
        <StatCard
          title={safeT('vehicle_finance.balance', 'المتبقي')}
          value={balance}
          subtitle={balance < 0 ? safeT('vehicle_finance.credit', 'رصيد للعميل') : 'حسب الإجمالي المعروض'}
          accent={balanceAccent}
          testId="vehicle-financial-summary-balance"
          onShowSource={onShowSource}
          sourceKey="balance"
        />
      </div>
    </div>
  );
}
