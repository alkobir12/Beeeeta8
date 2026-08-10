import React, { useState } from 'react';
import { Calculator, CheckCircle2, CreditCard, FileSearch, Plus, Wallet } from 'lucide-react';

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

const MiniMetric = ({ title, value, tone = 'slate', testId }) => {
  const tones = {
    teal: { bg: 'rgba(20,184,166,0.11)', border: 'rgba(20,184,166,0.24)', text: 'rgba(153,246,228,0.96)' },
    emerald: { bg: 'rgba(16,185,129,0.10)', border: 'rgba(16,185,129,0.22)', text: 'rgba(167,243,208,0.96)' },
    rose: { bg: 'rgba(244,63,94,0.10)', border: 'rgba(244,63,94,0.22)', text: 'rgba(254,202,202,0.96)' },
    amber: { bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.25)', text: 'rgba(253,230,138,0.96)' },
    sky: { bg: 'rgba(56,189,248,0.10)', border: 'rgba(56,189,248,0.22)', text: 'rgba(186,230,253,0.96)' },
    slate: { bg: 'rgba(255,255,255,0.06)', border: 'rgba(148,163,184,0.20)', text: 'rgba(226,232,240,0.92)' },
  };
  const c = tones[tone] || tones.slate;
  return (
    <div
      className="dash-widget-shell"
      style={{
        background: `radial-gradient(circle at 12% 18%, ${c.bg}, transparent 55%), rgba(255,255,255,0.06)`,
        border: `1px solid ${c.border}`,
        boxShadow: '0 18px 60px rgba(2,6,23,0.45)',
        padding: 14,
      }}
      data-testid={testId}
    >
      <div className="text-[11px] sm:text-xs font-semibold" style={{ color: 'rgba(226,232,240,0.72)' }} data-testid={`${testId}-title`}>
        {title}
      </div>
      <div className="mt-2 text-xl sm:text-3xl font-black tabular-nums" style={{ color: c.text }} data-testid={`${testId}-value`}>
        {formatMoney(value)} <span className="text-xs font-medium" style={{ color: 'rgba(226,232,240,0.65)' }}>ر.س</span>
      </div>
    </div>
  );
};

export default function VehicleFinancialSummary({ summary, onShowSource, onAddPayment, onConfirmPayment }) {
  const s = summary || {};
  const serviceTotal = Number(s.total_workshop || 0);
  const supplierPreview = Number(s.supplier_archive_total ?? s.parts_charge_total ?? s.total_suppliers ?? 0);
  const hasFinalTotal = s.final_customer_total !== null && s.final_customer_total !== undefined && s.final_customer_total !== '';
  const customerTotal = Number(hasFinalTotal ? s.final_customer_total : (s.current_customer_due ?? s.customer_total ?? s.total_items ?? s.total_amount ?? serviceTotal));
  const confirmedPaid = Number(s.confirmed_paid ?? s.total_paid ?? 0);
  const appliedPaid = Number(s.applied_paid ?? Math.min(confirmedPaid, customerTotal));
  const remaining = Number(s.display_remaining ?? s.balance ?? Math.max(customerTotal - appliedPaid, 0));
  const customerCredit = Number(s.customer_credit ?? s.customer_advance_liability ?? Math.max(confirmedPaid - customerTotal, 0));
  const pendingPayment = Number(s.pending_payment_total || 0);
  const [quickPaymentOpen, setQuickPaymentOpen] = useState(false);
  const [quickPayment, setQuickPayment] = useState({ amount: '', method: 'cash' });

  const submitQuickPayment = () => {
    const amount = Number(quickPayment.amount);
    if (!Number.isFinite(amount) || amount <= 0) return;
    onAddPayment?.({ amount, method: quickPayment.method || 'cash' });
    setQuickPayment({ amount: '', method: quickPayment.method || 'cash' });
    setQuickPaymentOpen(false);
  };

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
        data-testid="vehicle-financial-summary-customer-total-card"
      >
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs font-semibold" style={{ color: 'rgba(153,246,228,0.9)' }}>
              <Calculator size={16} />
              <span data-testid="vehicle-financial-summary-customer-total-title">{hasFinalTotal ? 'الإجمالي النهائي' : 'المستحق الحالي'}</span>
            </div>
            <div
              className="mt-2 text-3xl sm:text-5xl font-black tabular-nums leading-tight break-words"
              style={{ color: 'rgba(240,253,250,0.98)' }}
              data-testid="vehicle-financial-summary-customer-total-value"
            >
              {formatMoney(customerTotal)} <span className="text-sm font-medium" style={{ color: 'rgba(226,232,240,0.68)' }}>ر.س</span>
            </div>
            <div className="mt-2 text-xs" style={{ color: 'rgba(226,232,240,0.68)' }} data-testid="vehicle-financial-summary-customer-total-formula">
              {hasFinalTotal ? 'الإجمالي النهائي المعتمد عند التسليم' : 'المستحق الحالي = خدمات الورشة فقط'}
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs leading-relaxed" data-testid="vehicle-financial-summary-customer-total-breakdown">
              <span className="rounded-xl px-3 py-1.5" style={{ background: 'rgba(255,255,255,0.07)', color: 'rgba(226,232,240,0.86)' }} data-testid="vehicle-financial-summary-service-chip">
                خدمات الورشة: {formatMoney(serviceTotal)} ر.س
              </span>
              <span className="rounded-xl px-3 py-1.5" style={{ background: 'rgba(255,255,255,0.07)', color: 'rgba(226,232,240,0.86)' }} data-testid="vehicle-financial-summary-parts-chip">
                مشتريات الموردين للمعاينة: {formatMoney(supplierPreview)} ر.س
              </span>
              {hasFinalTotal && <span className="rounded-xl px-3 py-1.5" style={{ background: 'rgba(20,184,166,0.12)', color: 'rgba(153,246,228,0.95)' }} data-testid="vehicle-financial-summary-finalized-chip">معتمد</span>}
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 lg:flex lg:flex-col gap-2 lg:min-w-[210px]">
            <button
              type="button"
              onClick={() => setQuickPaymentOpen(true)}
              className="min-h-11 rounded-xl px-4 py-2.5 text-xs font-bold inline-flex items-center justify-center gap-2 transition-transform active:scale-95"
              style={{ background: 'rgba(20,184,166,0.14)', border: '1px solid rgba(20,184,166,0.28)', color: 'rgba(153,246,228,0.95)' }}
              data-testid="vehicle-financial-summary-add-payment-button"
            >
              <Plus size={14} /> إضافة دفعة
            </button>
            <button
              type="button"
              onClick={() => onConfirmPayment?.()}
              className="min-h-11 rounded-xl px-4 py-2.5 text-xs font-bold inline-flex items-center justify-center gap-2 transition-transform active:scale-95"
              style={{ background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.30)', color: 'rgba(187,247,208,0.95)' }}
              data-testid="vehicle-financial-summary-confirm-payment-button"
            >
              <CheckCircle2 size={14} /> تأكيد السداد
            </button>
            <button
              type="button"
              onClick={() => onShowSource?.('display_total')}
              className="min-h-11 rounded-xl px-4 py-2.5 text-xs font-bold inline-flex items-center justify-center gap-2 transition-transform active:scale-95"
              style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(148,163,184,0.22)', color: 'rgba(226,232,240,0.9)' }}
              data-testid="vehicle-financial-summary-details-sources-button"
            >
              <FileSearch size={14} /> عرض التفاصيل والمصادر
            </button>
          </div>
        </div>

        {quickPaymentOpen && (
          <div
            className="mt-4 grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto_auto] gap-2"
            data-testid="vehicle-financial-summary-quick-payment-form"
          >
            <input
              type="number"
              min="0"
              step="0.01"
              value={quickPayment.amount}
              onChange={(event) => setQuickPayment((prev) => ({ ...prev, amount: event.target.value }))}
              className="min-h-11 rounded-xl px-3 py-2 text-sm sm:text-xs outline-none"
              style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(148,163,184,0.24)', color: 'rgba(240,253,250,0.96)' }}
              placeholder="قيمة الدفعة"
              data-testid="vehicle-financial-summary-quick-payment-amount-input"
            />
            <select
              value={quickPayment.method}
              onChange={(event) => setQuickPayment((prev) => ({ ...prev, method: event.target.value }))}
              className="min-h-11 rounded-xl px-3 py-2 text-sm sm:text-xs outline-none"
              style={{ background: 'rgba(15,23,42,0.82)', border: '1px solid rgba(148,163,184,0.24)', color: 'rgba(240,253,250,0.96)' }}
              data-testid="vehicle-financial-summary-quick-payment-method-select"
            >
              <option value="cash">نقد</option>
              <option value="bank_transfer">تحويل/بنك</option>
              <option value="pos">نقاط بيع</option>
            </select>
            <button
              type="button"
              onClick={submitQuickPayment}
              className="min-h-11 rounded-xl px-4 py-2 text-xs font-bold transition-transform active:scale-95 disabled:opacity-50"
              style={{ background: 'rgba(20,184,166,0.18)', border: '1px solid rgba(20,184,166,0.32)', color: 'rgba(153,246,228,0.96)' }}
              disabled={!Number.isFinite(Number(quickPayment.amount)) || Number(quickPayment.amount) <= 0}
              data-testid="vehicle-financial-summary-quick-payment-save-button"
            >
              حفظ وتأكيد الدفعة
            </button>
            <button
              type="button"
              onClick={() => setQuickPaymentOpen(false)}
              className="min-h-11 rounded-xl px-4 py-2 text-xs font-bold transition-transform active:scale-95"
              style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(148,163,184,0.20)', color: 'rgba(226,232,240,0.86)' }}
              data-testid="vehicle-financial-summary-quick-payment-cancel-button"
            >
              إلغاء
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3" data-testid="vehicle-financial-summary-core-grid">
        <MiniMetric title="المدفوع المؤكد" value={confirmedPaid} tone="emerald" testId="vehicle-financial-summary-confirmed-paid" />
        <MiniMetric title="المتبقي على العميل" value={remaining} tone={remaining > 0 ? 'rose' : 'teal'} testId="vehicle-financial-summary-customer-remaining" />
      </div>

      {(customerCredit > 0 || pendingPayment > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3" data-testid="vehicle-financial-summary-conditional-grid">
          {customerCredit > 0 && (
            <MiniMetric title="رصيد العميل" value={customerCredit} tone="sky" testId="vehicle-financial-summary-customer-credit" />
          )}
          {pendingPayment > 0 && (
            <MiniMetric title="دفعة بانتظار التأكيد" value={pendingPayment} tone="amber" testId="vehicle-financial-summary-pending-payment" />
          )}
        </div>
      )}

      <div className="sr-only" data-testid="vehicle-financial-summary-applied-paid-value">
        {formatMoney(appliedPaid)}
      </div>
      <div className="sr-only" data-testid="vehicle-financial-summary-audit-icon-label">
        <CreditCard size={1} /> <Wallet size={1} />
      </div>
    </div>
  );
}