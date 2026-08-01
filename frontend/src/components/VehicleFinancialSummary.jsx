import React from 'react';
import { ArrowDownRight, ArrowUpRight, Wallet, Building2, HandCoins } from 'lucide-react';

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
      <div className="text-[11px] sm:text-xs font-medium" style={{ color: 'rgba(226,232,240,0.72)' }}>{title}</div>
      <div className="mt-1 text-lg sm:text-2xl font-extrabold tabular-nums" style={{ color: c.text }}>
        {formatMoney(value)}
        <span className="text-xs font-medium" style={{ color: 'rgba(226,232,240,0.65)', marginInlineStart: 6 }}>
          {subtitle ? '' : 'ر.س'}
        </span>
      </div>
      {subtitle ? (
        <div className="mt-1 text-xs" style={{ color: 'rgba(226,232,240,0.65)' }}>{subtitle}</div>
      ) : (
        <div className="mt-1 text-[11px]" style={{ color: 'rgba(226,232,240,0.55)' }}>
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
  const balance = Number(s.balance || 0);

  const safeT = (key, fallback) => {
    const v = t?.(key);
    if (!v || v === key) return fallback;
    return v;
  };

  const balanceAccent = balance === 0 ? 'emerald' : balance > 0 ? 'rose' : 'sky';

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3">
      <StatCard
        title={safeT('vehicle_finance.workshop_due', 'ذمم الورشة')}
        value={s.total_workshop}
        subtitle={safeT('vehicle_finance.workshop_due_hint', 'إيراد الورشة (ذمم العميل)')}
        accent="violet"
        testId="vehicle-financial-summary-workshop-due"
        onShowSource={onShowSource}
        sourceKey="workshop_due"
      />
      <StatCard
        title={safeT('vehicle_finance.suppliers_due', 'حركة الموردين')}
        value={s.total_suppliers}
        subtitle={safeT('vehicle_finance.suppliers_due_hint', 'أرشيف موردين (منفصل عن ربح الورشة)')}
        accent="rose"
        testId="vehicle-financial-summary-suppliers-due"
        onShowSource={onShowSource}
        sourceKey="suppliers_due"
      />
      <StatCard
        title={safeT('vehicle_finance.total_paid', 'المدفوع')}
        value={s.total_paid}
        accent="emerald"
        testId="vehicle-financial-summary-total-paid"
        onShowSource={onShowSource}
        sourceKey="paid"
      />
      <StatCard
        title={safeT('vehicle_finance.advance_paid', 'دفعة مقدمة')}
        value={s.advance_paid}
        accent="sky"
        testId="vehicle-financial-summary-advance-paid"
        onShowSource={onShowSource}
        sourceKey="advance"
      />
      <StatCard
        title={safeT('vehicle_finance.balance', 'المتبقي')}
        value={s.balance}
        subtitle={balance < 0 ? safeT('vehicle_finance.credit', 'رصيد للعميل') : safeT('vehicle_finance.balance_hint', 'المتبقي للورشة فقط')}
        accent={balanceAccent}
        testId="vehicle-financial-summary-balance"
        onShowSource={onShowSource}
        sourceKey="balance"
      />
    </div>
  );
}
