import React, { useEffect, useMemo, useState } from 'react';

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

const cardStyles = {
  wrap: { maxWidth: 430, margin: 'auto', direction: 'rtl' },
  title: { color: '#344054', fontWeight: 800, fontSize: 19, margin: '0 5px 12px' },
  card: { background: 'linear-gradient(180deg,#18263d,#142136)', borderRadius: 28, padding: 22, boxShadow: '0 18px 45px #1c294333', color: '#fff' },
  cap: { fontSize: 12, color: '#9aa8ba' },
  amount: { fontSize: 42, fontWeight: 850, margin: '5px 0 18px', lineHeight: 1.1 },
  amountUnit: { fontSize: 14, color: '#aab5c4' },
  rows: { borderTop: '1px solid #ffffff14', borderBottom: '1px solid #ffffff14' },
  row: { display: 'flex', justifyContent: 'space-between', gap: 15, padding: '15px 2px', borderBottom: '1px solid #ffffff0e' },
  rowLabel: { color: '#aeb9c8', fontSize: 13 },
  rowValue: { fontSize: 15 },
  paid: { display: 'flex', justifyContent: 'space-between', margin: '15px 0 0', padding: 14, borderRadius: 16, background: '#ffffff0a' },
  paidLabel: { color: '#aeb9c8' },
  actions: { display: 'grid', gap: 10, marginTop: 18 },
  button: { minHeight: 55, borderRadius: 17, fontSize: 15, fontWeight: 800, cursor: 'pointer', transition: 'transform 160ms ease, opacity 160ms ease' },
  pay: { background: '#1c3c4a', color: '#bdfaff', border: '1px solid #26cdd45c' },
  finish: { background: '#1e493f', color: '#d9fff2', border: '1px solid #36d49a5c' },
  details: { background: '#ffffff0a', color: '#eef2f7', border: '1px solid #ffffff1c' },
  final: { background: '#fff', color: '#172033', borderRadius: 24, padding: 20, marginTop: 16, boxShadow: '0 14px 35px #1c294322' },
  finalTitle: { fontSize: 18, margin: '0 0 5px', fontWeight: 800 },
  finalText: { fontSize: 12, color: '#7b8493', margin: '0 0 16px' },
  finalRow: { display: 'flex', justifyContent: 'space-between', padding: '11px 0', borderBottom: '1px solid #edf0f3', gap: 12 },
  finalRowLabel: { color: '#7a8493' },
  finalRowValue: { fontSize: 16 },
  hint: { color: '#667085', fontSize: 11, lineHeight: 1.7, marginTop: 10 },
  input: { width: '100%', height: 58, border: '1px solid #dce2e9', borderRadius: 15, padding: '0 14px', fontSize: 25, fontWeight: 800, margin: '10px 0', textAlign: 'right', outline: 'none' },
  result: { background: '#f4f7fa', borderRadius: 15, padding: 14, margin: '8px 0 14px', display: 'flex', justifyContent: 'space-between', gap: 12 },
  approve: { width: '100%', background: '#7c3aed', color: '#fff', border: 0 },
};

export default function VehicleFinancialSummary({
  summary,
  vehicle,
  onShowSource,
  onAddPayment,
  onFinalizeTotal,
}) {
  const s = summary || {};
  const serviceTotal = Number(s.total_workshop ?? s.workshop_service_total ?? 0);
  const supplierPreview = Number(s.supplier_archive_total ?? s.parts_charge_total ?? s.total_suppliers ?? 0);
  const itemsTotal = useMemo(() => serviceTotal + supplierPreview, [serviceTotal, supplierPreview]);
  const confirmedPaid = Number(s.confirmed_paid ?? s.total_paid ?? 0);
  const hasFinalTotal = s.final_customer_total !== null && s.final_customer_total !== undefined && s.final_customer_total !== '';
  const currentFinalTotal = Number(hasFinalTotal ? s.final_customer_total : itemsTotal);
  const [showFinal, setShowFinal] = useState(false);
  const [finalTotalInput, setFinalTotalInput] = useState(String(currentFinalTotal || ''));
  const [savingFinal, setSavingFinal] = useState(false);

  useEffect(() => {
    setFinalTotalInput(String(currentFinalTotal || ''));
    setShowFinal(Boolean(hasFinalTotal || String(vehicle?.status || '').toLowerCase() === 'delivered'));
  }, [currentFinalTotal, hasFinalTotal, vehicle?.status]);

  const finalTotalValue = Number(finalTotalInput || 0);
  const remaining = Math.max((Number.isFinite(finalTotalValue) ? finalTotalValue : 0) - confirmedPaid, 0);
  const canApprove = Number.isFinite(finalTotalValue) && finalTotalValue >= 0 && !savingFinal;

  const approveFinalTotal = async () => {
    if (!canApprove) return;
    try {
      setSavingFinal(true);
      await onFinalizeTotal?.({
        finalCustomerTotal: finalTotalValue,
        previousServiceTotal: serviceTotal,
      });
    } finally {
      setSavingFinal(false);
    }
  };

  return (
    <div style={cardStyles.wrap} data-testid="vehicle-financial-summary-layout">
      <div style={cardStyles.title} data-testid="vehicle-financial-summary-title">الملخص المالي</div>
      <div style={cardStyles.card} data-testid="vehicle-financial-summary-card">
        <div style={cardStyles.cap} data-testid="vehicle-financial-summary-items-total-label">إجمالي البنود</div>
        <div style={cardStyles.amount} data-testid="vehicle-financial-summary-items-total-value">
          {formatMoney(itemsTotal)} <small style={cardStyles.amountUnit}>ر.س</small>
        </div>

        <div style={cardStyles.rows} data-testid="vehicle-financial-summary-breakdown-rows">
          <div style={cardStyles.row} data-testid="vehicle-financial-summary-workshop-service-row">
            <span style={cardStyles.rowLabel}>خدمات الورشة</span>
            <b style={cardStyles.rowValue} data-testid="vehicle-financial-summary-workshop-service-value">{formatMoney(serviceTotal)} ر.س</b>
          </div>
          <div style={{ ...cardStyles.row, borderBottom: 0 }} data-testid="vehicle-financial-summary-supplier-preview-row">
            <span style={cardStyles.rowLabel}>مشتريات الموردين</span>
            <b style={cardStyles.rowValue} data-testid="vehicle-financial-summary-supplier-preview-value">{formatMoney(supplierPreview)} ر.س</b>
          </div>
        </div>

        <div style={cardStyles.paid} data-testid="vehicle-financial-summary-confirmed-paid-row">
          <span style={cardStyles.paidLabel}>المدفوع المؤكد</span>
          <b data-testid="vehicle-financial-summary-confirmed-paid-value">{formatMoney(confirmedPaid)} ر.س</b>
        </div>

        <div style={cardStyles.actions} data-testid="vehicle-financial-summary-actions">
          <button
            type="button"
            style={{ ...cardStyles.button, ...cardStyles.pay }}
            onClick={() => onAddPayment?.({ amount: '', method: 'cash' })}
            data-testid="vehicle-financial-summary-add-payment-button"
          >
            ＋ إضافة دفعة
          </button>
          <button
            type="button"
            style={{ ...cardStyles.button, ...cardStyles.finish }}
            onClick={() => setShowFinal(true)}
            data-testid="vehicle-financial-summary-finish-pricing-button"
          >
            ✓ إنهاء وتسعير المركبة
          </button>
          <button
            type="button"
            style={{ ...cardStyles.button, ...cardStyles.details }}
            onClick={() => onShowSource?.('display_total')}
            data-testid="vehicle-financial-summary-details-sources-button"
          >
            ▧ عرض التفاصيل والمصادر
          </button>
        </div>
      </div>

      {showFinal && (
        <div style={cardStyles.final} data-testid="vehicle-financial-summary-final-settlement-panel">
          <h2 style={cardStyles.finalTitle} data-testid="vehicle-financial-summary-final-title">التسوية النهائية</h2>
          <p style={cardStyles.finalText} data-testid="vehicle-financial-summary-final-description">تظهر هذه المرحلة فقط عند إنهاء المركبة.</p>

          <div style={cardStyles.finalRow} data-testid="vehicle-financial-summary-final-items-total-row">
            <span style={cardStyles.finalRowLabel}>إجمالي البنود</span>
            <strong style={cardStyles.finalRowValue} data-testid="vehicle-financial-summary-final-items-total-value">{formatMoney(itemsTotal)} ر.س</strong>
          </div>

          <label style={cardStyles.hint} htmlFor="vehicle-final-customer-total" data-testid="vehicle-financial-summary-final-input-label">الإجمالي النهائي للعميل</label>
          <input
            id="vehicle-final-customer-total"
            type="number"
            min="0"
            step="0.01"
            value={finalTotalInput}
            onChange={(event) => setFinalTotalInput(event.target.value)}
            style={cardStyles.input}
            data-testid="vehicle-financial-summary-final-customer-total-input"
          />

          <div style={cardStyles.finalRow} data-testid="vehicle-financial-summary-final-paid-row">
            <span style={cardStyles.finalRowLabel}>المدفوع المؤكد</span>
            <strong style={cardStyles.finalRowValue} data-testid="vehicle-financial-summary-final-paid-value">{formatMoney(confirmedPaid)} ر.س</strong>
          </div>

          <div style={cardStyles.result} data-testid="vehicle-financial-summary-final-remaining-row">
            <span>المتبقي على العميل</span>
            <strong data-testid="vehicle-financial-summary-final-remaining-value">{formatMoney(remaining)} ر.س</strong>
          </div>

          <button
            type="button"
            style={{ ...cardStyles.button, ...cardStyles.approve, opacity: canApprove ? 1 : 0.6 }}
            onClick={approveFinalTotal}
            disabled={!canApprove}
            data-testid="vehicle-financial-summary-approve-final-total-button"
          >
            {savingFinal ? 'جارٍ الاعتماد…' : 'اعتماد الإجمالي النهائي'}
          </button>
          <div style={cardStyles.hint} data-testid="vehicle-financial-summary-final-hint">
            بعد الاعتماد يصبح الإجمالي النهائي هو أساس المتبقي والتحصيل عند التسليم.
          </div>
        </div>
      )}
    </div>
  );
}