import React, { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, Printer, UserRound, Trash2 } from 'lucide-react';

export const TRANSACTION_TYPE_LABELS = {
  sale: 'بيع',
  sale_return: 'مرتجع بيع',
  payment: 'تحصيل / سداد',
  receipt_voucher: 'سند قبض',
  purchase: 'شراء',
  purchase_return: 'مرتجع شراء',
  expense: 'مصروف',
  salary: 'رواتب',
  settlement: 'تسوية',
  repair_reversal: 'قيد تصحيحي',
  closing: 'قيد إقفال',
  manual: 'قيد يدوي',
};

export const SOURCE_LABELS = {
  operation: 'عملية',
  operation_payment: 'تحصيل عملية',
  vehicle_visit: 'ملف مركبة',
  visit_receipt_voucher: 'سند قبض زيارة',
  unified_visit_payment: 'تحصيل زيارة',
  pos_template: 'نقاط البيع',
  pos_instant_sale: 'نقاط البيع',
  smart_pos: 'نقاط البيع',
  period_close: 'إقفال فترة',
  manual: 'قيد يدوي',
  historical_financial_repair: 'تصحيح محاسبي',
  hist_vehicle_ar_repair: 'استرجاع ذمم سابقة',
  active_vehicle_ar_repair: 'إثبات ذمم مركبات',
  fin_engine_align_v1: 'محاذاة المحرك المالي',
  ajel_supplier_purchase: 'شراء آجل من مورد',
  financial_reset_opening_receivable: 'رصيد افتتاحي',
  archived_financial_period: 'فترة مؤرشفة',
};

const hasLatin = (value) => /[A-Za-z]/.test(String(value || ''));

export const sourceLabel = (source) => SOURCE_LABELS[String(source || '').toLowerCase()] || 'مصدر آخر';

export const entryTypeLabel = (entry) => {
  const apiLabel = entry?.transaction_type_label_ar;
  if (apiLabel && apiLabel !== '-' && !hasLatin(apiLabel)) return apiLabel;
  const opLabel = entry?.operation_type_label;
  if (opLabel && opLabel !== 'غير محدد' && !hasLatin(opLabel)) return opLabel;
  return TRANSACTION_TYPE_LABELS[String(entry?.transaction_type || '').toLowerCase()] || 'قيد محاسبي';
};

export const classifyEntry = (entry) => {
  const type = String(entry?.transaction_type || '').toLowerCase();
  if (['sale', 'sale_return', 'receipt_voucher'].includes(type)) return 'income';
  if (type === 'payment') return 'collection';
  if (['purchase', 'purchase_return', 'expense', 'salary'].includes(type)) return 'outflow';
  if (type === 'repair_reversal') return 'correction';
  if (type === 'closing') return 'closing';
  return 'neutral';
};

const KIND_STYLES = {
  income: {
    background: 'radial-gradient(circle at 12% 18%, rgba(16,185,129,0.22), transparent 52%), radial-gradient(circle at 88% 78%, rgba(45,212,191,0.10), transparent 55%), #fbfbf8',
    border: 'rgba(16,185,129,0.40)',
    typePill: 'border-emerald-300 bg-emerald-50 text-emerald-900',
    amount: 'text-emerald-800',
    stripe: '#10b981',
  },
  collection: {
    background: 'radial-gradient(circle at 12% 18%, rgba(20,184,166,0.20), transparent 52%), radial-gradient(circle at 88% 78%, rgba(16,185,129,0.10), transparent 55%), #fbfbf8',
    border: 'rgba(20,184,166,0.40)',
    typePill: 'border-teal-300 bg-teal-50 text-teal-900',
    amount: 'text-teal-800',
    stripe: '#14b8a6',
  },
  outflow: {
    background: 'radial-gradient(circle at 12% 18%, rgba(244,63,94,0.20), transparent 52%), radial-gradient(circle at 88% 78%, rgba(248,113,113,0.10), transparent 55%), #fbfbf8',
    border: 'rgba(244,63,94,0.40)',
    typePill: 'border-rose-300 bg-rose-50 text-rose-900',
    amount: 'text-rose-800',
    stripe: '#f43f5e',
  },
  correction: {
    background: 'radial-gradient(circle at 12% 18%, rgba(245,158,11,0.18), transparent 52%), #fbfbf8',
    border: 'rgba(245,158,11,0.40)',
    typePill: 'border-amber-300 bg-amber-50 text-amber-900',
    amount: 'text-amber-800',
    stripe: '#f59e0b',
  },
  closing: {
    background: 'radial-gradient(circle at 12% 18%, rgba(100,116,139,0.16), transparent 52%), #fbfbf8',
    border: 'rgba(100,116,139,0.38)',
    typePill: 'border-slate-300 bg-slate-100 text-slate-800',
    amount: 'text-slate-800',
    stripe: '#64748b',
  },
  neutral: {
    background: 'radial-gradient(circle at 12% 18%, rgba(100,116,139,0.14), transparent 52%), #fbfbf8',
    border: 'rgba(100,116,139,0.32)',
    typePill: 'border-slate-300 bg-slate-100 text-slate-800',
    amount: 'text-zinc-900',
    stripe: '#94a3b8',
  },
};

const formatCurrency = (amount) =>
  new Intl.NumberFormat('ar-SA', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(amount) || 0) + ' ر.س';

const formatDate = (date) => {
  if (!date) return '-';
  try {
    return new Date(date).toLocaleDateString('ar-SA-u-ca-gregory', { year: 'numeric', month: '2-digit', day: '2-digit' });
  } catch {
    return '-';
  }
};

export default function JournalEntryCard({
  entry,
  description = '',
  canEdit = false,
  canDelete = false,
  onView,
  onPrint,
  onEditParty,
  onDelete,
}) {
  const [expanded, setExpanded] = useState(false);
  const [showMenu, setShowMenu] = useState(false);

  const cardId = entry?.id || 'unknown';
  const kind = classifyEntry(entry);
  const ks = KIND_STYLES[kind] || KIND_STYLES.neutral;
  const typeLabel = entryTypeLabel(entry);

  const partyName = entry?.party_label && entry.party_label !== 'مفتوح' ? entry.party_label : '';
  const partyRole = entry?.party_type === 'customer' ? 'عميل' : entry?.party_type === 'supplier' ? 'مورد' : '';
  const vehicleLabel = entry?.vehicle_label || entry?.vehicle_plate || '';
  const amount = Number(entry?.total_debit ?? entry?.total ?? 0);

  const methodLabel = useMemo(() => {
    const label = entry?.payment_method_label_ar;
    if (label && label !== '-' && label !== 'غير محدد' && !hasLatin(label)) return label;
    return '';
  }, [entry?.payment_method_label_ar]);

  const statusLabel = useMemo(() => {
    const label = entry?.payment_status_label_ar;
    if (label && label !== '-' && !hasLatin(label)) return label;
    return '';
  }, [entry?.payment_status_label_ar]);

  const statusPaid = ['paid', 'paid_full', 'full', 'settled'].includes(String(entry?.payment_status || '').toLowerCase());

  const linkage = useMemo(() => {
    const hasOperation = Boolean(entry?.reference_id);
    const hasVehicle = Boolean(vehicleLabel);
    if (hasOperation && hasVehicle) return { linked: true, label: 'مرتبط بعملية ومركبة' };
    if (hasOperation) return { linked: true, label: 'مرتبط بعملية' };
    if (hasVehicle) return { linked: true, label: 'مرتبط بمركبة' };
    if (partyName) return { linked: true, label: 'مرتبط بطرف' };
    return { linked: false, label: 'غير مرتبط' };
  }, [entry?.reference_id, vehicleLabel, partyName]);

  const lines = Array.isArray(entry?.lines) ? entry.lines : [];
  const totalDebit = lines.reduce((sum, l) => sum + (Number(l?.debit) || 0), 0);
  const totalCredit = lines.reduce((sum, l) => sum + (Number(l?.credit) || 0), 0);

  const subtitle = vehicleLabel
    ? `مركبة: ${vehicleLabel}`
    : (description || sourceLabel(entry?.source));

  return (
    <article
      className="relative overflow-visible rounded-[24px] border text-zinc-950 shadow-[0_12px_30px_rgba(15,23,42,0.10)] transition-transform duration-200 hover:-translate-y-0.5"
      style={{ background: ks.background, borderColor: ks.border }}
      dir="rtl"
      data-testid={`journal-card-${cardId}`}
    >
      <span
        className="absolute inset-y-4 right-0 w-1 rounded-full"
        style={{ backgroundColor: ks.stripe }}
        aria-hidden="true"
      />
      <section className="p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-[18px] font-black leading-tight text-zinc-950" data-testid={`journal-card-title-${cardId}`}>
              {partyName || typeLabel}
              {partyName && partyRole ? (
                <span className="mr-2 align-middle rounded-full border border-zinc-300 bg-white px-2 py-0.5 text-[10px] font-black text-zinc-600" data-testid={`journal-card-party-role-${cardId}`}>
                  {partyRole}
                </span>
              ) : null}
            </h2>
            <div className="mt-1 line-clamp-2 text-[12px] font-bold leading-relaxed text-zinc-700" data-testid={`journal-card-subtitle-${cardId}`}>
              {subtitle || 'قيد محاسبي'}
            </div>
          </div>
          <div className="shrink-0 text-left" data-testid={`journal-card-amount-${cardId}`}>
            <strong className={`block text-[22px] font-black tabular-nums ${ks.amount}`}>
              {Number(amount).toLocaleString('en-US')}
            </strong>
            <span className="text-[11px] font-black text-zinc-700">ر.س</span>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5" data-testid={`journal-card-tags-${cardId}`}>
          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-black ${ks.typePill}`} data-testid={`journal-card-type-tag-${cardId}`}>
            {typeLabel}
          </span>
          {methodLabel ? (
            <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-black text-amber-800" data-testid={`journal-card-payment-method-tag-${cardId}`}>
              {methodLabel}
            </span>
          ) : null}
          {statusLabel ? (
            <span
              className={`rounded-full border px-2.5 py-1 text-[11px] font-black ${statusPaid ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-rose-200 bg-rose-50 text-rose-800'}`}
              data-testid={`journal-card-payment-status-tag-${cardId}`}
            >
              {statusLabel}
            </span>
          ) : null}
          <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-black text-sky-800" data-testid={`journal-card-source-tag-${cardId}`}>
            {sourceLabel(entry?.source)}
          </span>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] font-bold text-zinc-700" data-testid={`journal-card-meta-line-${cardId}`}>
          <span data-testid={`journal-card-date-${cardId}`}>
            {entry?.entry_number ? `${entry.entry_number} · ` : ''}{formatDate(entry?.entry_date || entry?.date)}
          </span>
          <span
            className={`rounded-full px-2.5 py-1 text-[11px] font-black ${linkage.linked ? 'text-emerald-800' : 'text-amber-800'}`}
            data-testid={`journal-card-linkage-${cardId}`}
          >
            {linkage.linked ? '●' : '○'} {linkage.label}
          </span>
        </div>
      </section>

      <section className="border-t border-zinc-200 bg-white/65" data-testid={`journal-card-details-section-${cardId}`}>
        <button
          type="button"
          className="flex min-h-[48px] w-full items-center justify-between px-4 text-[13px] font-black text-zinc-800"
          onClick={() => setExpanded((prev) => !prev)}
          data-testid={`journal-card-toggle-${cardId}`}
        >
          <span>تفاصيل القيد</span>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>

        {expanded ? (
          <div className="space-y-3 px-4 pb-4" data-testid={`journal-card-details-${cardId}`}>
            {description ? (
              <div className="rounded-2xl border border-zinc-200 bg-white px-3 py-2 text-[12px] font-bold leading-relaxed text-zinc-700" data-testid={`journal-card-description-${cardId}`}>
                {description}
              </div>
            ) : null}

            <div className="overflow-hidden rounded-2xl border border-zinc-200">
              <table className="w-full text-[11px]" data-testid={`journal-card-lines-table-${cardId}`}>
                <thead className="bg-zinc-50 text-zinc-700">
                  <tr>
                    <th className="p-2 text-right">الحساب</th>
                    <th className="p-2 text-center text-emerald-700">مدين</th>
                    <th className="p-2 text-center text-rose-700">دائن</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {lines.length ? lines.map((line, idx) => (
                    <tr key={`${cardId}-line-${idx}`} data-testid={`journal-card-line-${cardId}-${idx}`}>
                      <td className="p-2 font-bold text-zinc-800">
                        {line?.account_name || 'حساب'}
                      </td>
                      <td className="p-2 text-center tabular-nums text-emerald-800">{Number(line?.debit || 0) > 0 ? Number(line.debit).toLocaleString('en-US') : '-'}</td>
                      <td className="p-2 text-center tabular-nums text-rose-800">{Number(line?.credit || 0) > 0 ? Number(line.credit).toLocaleString('en-US') : '-'}</td>
                    </tr>
                  )) : (
                    <tr><td colSpan={3} className="p-3 text-center text-zinc-500">لا توجد بنود مسجلة</td></tr>
                  )}
                </tbody>
                <tfoot className="bg-zinc-50 font-black">
                  <tr>
                    <td className="p-2">الإجمالي</td>
                    <td className="p-2 text-center tabular-nums text-emerald-800" data-testid={`journal-card-total-debit-${cardId}`}>{formatCurrency(totalDebit)}</td>
                    <td className="p-2 text-center tabular-nums text-rose-800" data-testid={`journal-card-total-credit-${cardId}`}>{formatCurrency(totalCredit)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        ) : null}
      </section>

      <div className="relative flex items-center gap-2 border-t border-zinc-200 bg-white p-3 rounded-b-[24px]" data-testid={`journal-card-actions-${cardId}`}>
        <button
          type="button"
          className="min-h-[48px] flex-1 rounded-2xl bg-zinc-950 px-4 text-sm font-black text-white shadow-sm transition active:scale-[0.99]"
          onClick={() => onView && onView(entry)}
          data-testid={`journal-card-view-${cardId}`}
        >
          عرض التفاصيل
        </button>
        <button
          type="button"
          className="min-h-[48px] w-14 rounded-2xl border border-zinc-200 bg-zinc-50 text-lg font-black text-zinc-800 transition active:scale-[0.98]"
          onClick={() => setShowMenu((prev) => !prev)}
          aria-expanded={showMenu}
          data-testid={`journal-card-more-${cardId}`}
        >
          •••
        </button>
        {showMenu ? (
          <div className="absolute bottom-[70px] left-3 z-20 w-[210px] overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-xl" data-testid={`journal-card-more-menu-${cardId}`}>
            <button
              type="button"
              className="flex min-h-[48px] w-full items-center gap-2 px-3 text-right text-[12px] font-black hover:bg-zinc-50"
              onClick={() => { setShowMenu(false); onPrint && onPrint(entry); }}
              data-testid={`journal-card-print-${cardId}`}
            >
              <Printer size={14} /> طباعة
            </button>
            {canEdit ? (
              <button
                type="button"
                className="flex min-h-[48px] w-full items-center gap-2 px-3 text-right text-[12px] font-black hover:bg-zinc-50"
                onClick={() => { setShowMenu(false); onEditParty && onEditParty(entry); }}
                data-testid={`journal-card-edit-party-${cardId}`}
              >
                <UserRound size={14} /> تعديل طرف العملية
              </button>
            ) : null}
            {canDelete ? (
              <button
                type="button"
                className="flex min-h-[48px] w-full items-center gap-2 px-3 text-right text-[12px] font-black text-rose-700 hover:bg-rose-50"
                onClick={() => { setShowMenu(false); onDelete && onDelete(entry); }}
                data-testid={`journal-card-delete-${cardId}`}
              >
                <Trash2 size={14} /> حذف
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}
