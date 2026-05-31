import React from 'react';
import StatusBadge from './StatusBadge';

/**
 * 🎨 OperationCardHeader — top section of an operation card.
 *   Left: large amount + sub-label
 *   Right: stacked status badges (payment status / movement / origin / invoice / integrity)
 */
export const OperationCardHeader = ({
  operationId,
  amount,
  subLabel,
  paymentStatusLabel,
  paymentStatusTone, // 'emerald' for paid, 'amber' for credit/unpaid
  hasPaymentStatus,
  movementLabel,
  movementSide,
  originLabel,
  invoiceNumber,
  integrityWarningsCount,
  integrityWarnings,
  integrityLabelMap,
  onIntegrityClick,
}) => {
  const warningTitle = Array.isArray(integrityWarnings) && integrityWarnings.length
    ? integrityWarnings.map((w) => (integrityLabelMap && integrityLabelMap[w]) || w).join(' • ')
    : 'انقر لعرض تفاصيل التنبيه';
  return (
    <div className="flex items-start justify-between gap-3">
      {/* Amount */}
      <div className="min-w-0">
        <h1
          className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white tabular-nums"
          data-testid={`operation-card-total-${operationId}`}
        >
          {Number(amount || 0).toFixed(2)}
          <span className="ms-2 text-base font-semibold text-slate-500 dark:text-zinc-500">ر.س</span>
        </h1>
        <p className="mt-1 text-xs sm:text-sm text-slate-600 dark:text-zinc-400">{subLabel}</p>
      </div>

      {/* Status pills */}
      <div className="flex flex-wrap justify-end gap-1.5 max-w-[60%]" data-testid={`operation-card-pills-${operationId}`}>
        {hasPaymentStatus ? (
          <StatusBadge
            text={paymentStatusLabel}
            tone={paymentStatusTone || 'slate'}
            testid={`operation-card-payment-status-pill-${operationId}`}
          />
        ) : null}
        <StatusBadge
          text={movementLabel}
          tone={movementSide === 'debit' ? 'emerald' : movementSide === 'credit' ? 'rose' : 'slate'}
          testid={`operation-card-movement-pill-${operationId}`}
        />
        <StatusBadge
          text={originLabel}
          tone={originLabel === 'POS' ? 'indigo' : originLabel === 'ملف المركبة' ? 'cyan' : 'slate'}
          testid={`operation-card-origin-pill-${operationId}`}
        />
        {invoiceNumber ? (
          <StatusBadge
            text={invoiceNumber}
            tone="slate"
            testid={`operation-card-invoice-${operationId}`}
          />
        ) : null}
        {integrityWarningsCount > 0 ? (
          <StatusBadge
            text={`⚠️ ${integrityWarningsCount}`}
            tone="rose"
            testid={`operation-card-integrity-pill-${operationId}`}
            title={warningTitle}
            onClick={typeof onIntegrityClick === 'function' ? onIntegrityClick : undefined}
          />
        ) : null}
      </div>
    </div>
  );
};

export default OperationCardHeader;
