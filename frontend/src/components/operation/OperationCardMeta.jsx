import React from 'react';
import { Calendar, Wallet, Car, Receipt } from 'lucide-react';

/**
 * 🎨 InfoCard — a small icon + label + value tile, used inside the meta grid.
 */
const InfoCard = ({ icon, label, value, accent = 'slate', testid }) => {
  const accents = {
    slate: 'text-slate-500 dark:text-slate-400',
    cyan: 'text-cyan-600 dark:text-cyan-400',
    emerald: 'text-emerald-600 dark:text-emerald-400',
    amber: 'text-amber-600 dark:text-amber-400',
    indigo: 'text-indigo-600 dark:text-indigo-400',
  };
  return (
    <div
      data-testid={testid}
      className="flex items-center gap-2.5 rounded-2xl border border-slate-200 bg-white/80 p-3 dark:border-white/5 dark:bg-white/[0.03] shadow-sm"
    >
      <div className={`shrink-0 ${accents[accent] || accents.slate}`}>{icon}</div>
      <div className="min-w-0">
        <p className="text-[10px] text-slate-500 dark:text-zinc-500 font-medium">{label}</p>
        <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate" title={value}>
          {value || '-'}
        </p>
      </div>
    </div>
  );
};

/**
 * 🎨 OperationCardMeta — 4 InfoCards: date, payment method, vehicle, type.
 */
export const OperationCardMeta = ({
  operationId,
  dateText,
  paymentMethodLabel,
  vehicleDisplay,
  typeLabel,
}) => (
  <div className="mt-5 grid grid-cols-2 gap-2.5" data-testid={`operation-card-meta-${operationId}`}>
    <InfoCard
      icon={<Calendar size={16} />}
      label="التاريخ"
      value={dateText}
      accent="emerald"
      testid={`operation-card-meta-date-${operationId}`}
    />
    <InfoCard
      icon={<Wallet size={16} />}
      label="طريقة الدفع"
      value={paymentMethodLabel}
      accent="amber"
      testid={`operation-card-meta-method-${operationId}`}
    />
    <InfoCard
      icon={<Car size={16} />}
      label="المركبة"
      value={vehicleDisplay}
      accent="cyan"
      testid={`operation-card-meta-vehicle-${operationId}`}
    />
    <InfoCard
      icon={<Receipt size={16} />}
      label="نوع العملية"
      value={typeLabel}
      accent="indigo"
      testid={`operation-card-meta-type-${operationId}`}
    />
  </div>
);

export { InfoCard };
export default OperationCardMeta;
