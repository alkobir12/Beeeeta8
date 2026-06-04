import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Phone, FileText, Send, Car, Wrench, Package, AlertTriangle, ExternalLink, Building2, User, Receipt, Sparkles, ClipboardList } from 'lucide-react';

/**
 * 🎴 AssistantCard — renderer for interactive ERP cards embedded inside chat.
 *
 * Backend tool handlers attach a `cards: [{type,title,data,actions}]` list to
 * their result. The drawer collects them and renders one <AssistantCard/> per
 * card. Each action chip dispatches based on its `intent`:
 *   • navigate  → react-router push
 *   • tool      → re-trigger an assistant tool (read-only)
 *   • deferred  → display as disabled with a "Phase 3X" hint
 *
 * 🆕 Phase 3B Round 2: cards whose type ends with "DraftCard" are rendered
 * in a distinct "draft" style (dashed border + amber gradient + "مسوّدة" badge).
 */

const TYPE_META = {
  CustomerCard: { Icon: User, color: 'from-indigo-600 to-blue-600', tone: 'border-indigo-300 dark:border-indigo-700' },
  VehicleCard: { Icon: Car, color: 'from-emerald-600 to-teal-600', tone: 'border-emerald-300 dark:border-emerald-700' },
  InvoiceCard: { Icon: Receipt, color: 'from-amber-600 to-orange-600', tone: 'border-amber-300 dark:border-amber-700' },
  OperationCard: { Icon: Wrench, color: 'from-slate-600 to-zinc-600', tone: 'border-slate-300 dark:border-slate-700' },
  SupplierCard: { Icon: Building2, color: 'from-fuchsia-600 to-purple-600', tone: 'border-fuchsia-300 dark:border-fuchsia-700' },
  InventoryCard: { Icon: Package, color: 'from-cyan-600 to-sky-600', tone: 'border-cyan-300 dark:border-cyan-700' },
  AuditCard: { Icon: AlertTriangle, color: 'from-rose-600 to-red-600', tone: 'border-rose-300 dark:border-rose-700' },
};

// 🆕 Round 2 — Draft card styling per intent kind
const DRAFT_META = {
  customer: { Icon: User, color: 'from-amber-500 via-amber-600 to-orange-600' },
  vehicle: { Icon: Car, color: 'from-amber-500 via-orange-500 to-rose-500' },
  visit: { Icon: ClipboardList, color: 'from-amber-500 via-amber-600 to-amber-700' },
  operation: { Icon: Wrench, color: 'from-amber-500 via-orange-600 to-red-600' },
  invoice: { Icon: Receipt, color: 'from-amber-500 to-orange-600' },
  collection: { Icon: Receipt, color: 'from-emerald-500 via-amber-500 to-orange-600' },
  payment: { Icon: Receipt, color: 'from-rose-500 via-amber-500 to-orange-600' },
  supplier: { Icon: Building2, color: 'from-amber-500 via-fuchsia-500 to-purple-600' },
  inventory: { Icon: Package, color: 'from-amber-500 via-cyan-500 to-sky-600' },
  part_search: { Icon: Package, color: 'from-amber-400 via-amber-500 to-orange-500' },
  unknown: { Icon: Sparkles, color: 'from-amber-400 via-amber-500 to-amber-600' },
};

const STATUS_LABEL = {
  paid: 'مسددة',
  unpaid: 'غير مسددة',
  partial: 'جزئي',
  pending: 'معلّقة',
  delivered: 'مُسلَّمة',
  open: 'مفتوحة',
  closed: 'مغلقة',
  in_progress: 'قيد العمل',
};

function chipClass(intent, disabled) {
  if (disabled) return 'bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed';
  if (intent === 'navigate') return 'bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-200 hover:bg-indigo-200 dark:hover:bg-indigo-800 border-indigo-300 dark:border-indigo-700';
  if (intent === 'tool') return 'bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-200 hover:bg-emerald-200 dark:hover:bg-emerald-800 border-emerald-300 dark:border-emerald-700';
  return 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-300 dark:border-slate-700';
}

function iconForAction(action) {
  const id = action.id || '';
  if (id.includes('open') || id === 'view') return <ExternalLink size={11} />;
  if (id.includes('phone') || id === 'call') return <Phone size={11} />;
  if (id === 'whatsapp') return <Send size={11} />;
  if (id === 'pdf' || id === 'statement' || id === 'preview') return <FileText size={11} />;
  return null;
}

function renderFields(card) {
  const t = card.type;
  const d = card.data || {};
  switch (t) {
    case 'CustomerCard':
      return (
        <>
          {d.phone && <Row label="هاتف" value={d.phone} />}
          {d.balance_formatted && <Row label="الرصيد" value={d.balance_formatted} highlight={d.balance > 0 ? 'rose' : 'slate'} />}
          {d.vehicle_plate && <Row label="مركبة" value={d.vehicle_plate} />}
          {(d.vehicles_count > 0) && <Row label="زيارات" value={d.vehicles_count} />}
        </>
      );
    case 'VehicleCard':
      return (
        <>
          {d.owner && <Row label="المالك" value={d.owner} />}
          {d.year && <Row label="السنة" value={d.year} />}
          {d.status && <Row label="الحالة" value={STATUS_LABEL[d.status] || d.status} />}
          {d.mileage && <Row label="العداد" value={`${d.mileage} كم`} />}
        </>
      );
    case 'InvoiceCard':
      return (
        <>
          {d.customer && <Row label="العميل" value={d.customer} />}
          {d.amount_formatted && <Row label="القيمة" value={d.amount_formatted} highlight="indigo" />}
          {d.balance > 0 && <Row label="متبقّي" value={d.balance_formatted} highlight="rose" />}
          {d.status && <Row label="الحالة" value={STATUS_LABEL[d.status] || d.status} highlight={d.status === 'paid' ? 'emerald' : 'rose'} />}
          {d.date && <Row label="التاريخ" value={String(d.date).slice(0, 10)} />}
        </>
      );
    case 'OperationCard':
      return (
        <>
          {d.partner && <Row label="الطرف" value={d.partner} />}
          {d.amount_formatted && <Row label="المبلغ" value={d.amount_formatted} highlight="indigo" />}
          {d.payment_status && <Row label="السداد" value={STATUS_LABEL[d.payment_status] || d.payment_status} />}
          {d.date && <Row label="التاريخ" value={String(d.date).slice(0, 10)} />}
        </>
      );
    case 'SupplierCard':
      return (
        <>
          {d.phone && <Row label="هاتف" value={d.phone} />}
          {d.balance_formatted && <Row label="نستحق له" value={d.balance_formatted} highlight={d.balance > 0 ? 'rose' : 'slate'} />}
          {d.category && <Row label="التصنيف" value={d.category} />}
          {d.city && <Row label="المدينة" value={d.city} />}
        </>
      );
    case 'InventoryCard':
      return (
        <>
          {d.selling_price_formatted && <Row label="السعر" value={d.selling_price_formatted} highlight="emerald" />}
          <Row label="الكمية" value={`${d.quantity}${d.min_quantity ? ' / حد أدنى ' + d.min_quantity : ''}`} highlight={d.in_stock ? 'emerald' : 'rose'} />
          {!d.in_stock && d.shortage > 0 && <Row label="ناقص" value={d.shortage} highlight="rose" />}
          {d.category && <Row label="التصنيف" value={d.category} />}
        </>
      );
    default:
      // 🆕 Round 2 — Draft cards (e.g. CustomerDraftCard, VehicleDraftCard, ...)
      if (typeof t === 'string' && t.endsWith('DraftCard')) {
        return (
          <>
            {d.name && <Row label="الاسم" value={d.name} />}
            {d.plate && <Row label="اللوحة" value={d.plate} />}
            {d.phone && <Row label="هاتف" value={d.phone} />}
            {typeof d.amount === 'number' && (
              <Row label="المبلغ" value={`${d.amount.toLocaleString('ar-SA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ر.س`} highlight="indigo" />
            )}
            {d._resolved_from && (
              <Row label="مستند إلى" value={d._resolved_from.title || d._resolved_from.key} highlight="emerald" />
            )}
            {d.raw && <Row label="النص" value={String(d.raw).slice(0, 80)} />}
          </>
        );
      }
      return null;
  }
}

function Row({ label, value, highlight = 'slate' }) {
  const tones = {
    slate: 'text-slate-700 dark:text-slate-300',
    indigo: 'text-indigo-600 dark:text-indigo-300 font-bold',
    emerald: 'text-emerald-600 dark:text-emerald-300 font-bold',
    rose: 'text-rose-600 dark:text-rose-300 font-bold',
  };
  return (
    <div className="flex justify-between items-center gap-2 text-[11px]">
      <span className="text-slate-500 dark:text-slate-400">{label}</span>
      <span className={tones[highlight] || tones.slate}>{value}</span>
    </div>
  );
}

export const AssistantCard = ({ card, onAction }) => {
  const navigate = useNavigate();
  const isDraft = typeof card.type === 'string' && card.type.endsWith('DraftCard');
  const draftKind = (card.intent_kind || (card.data && card.data.section) || 'unknown');
  const meta = isDraft
    ? (DRAFT_META[draftKind] || DRAFT_META.unknown)
    : (TYPE_META[card.type] || TYPE_META.OperationCard);
  const Icon = meta.Icon;

  const handleAction = (action) => {
    if (!action || action.intent === 'deferred') return;
    if (action.intent === 'navigate' && action.target) {
      navigate(action.target);
      // Auto-close drawer parent will get the event via onAction
      onAction?.(action, card);
      return;
    }
    if (action.intent === 'tool' && action.tool) {
      onAction?.(action, card);
      return;
    }
    onAction?.(action, card);
  };

  // Draft cards get a dashed amber border to distinguish them visually from
  // confirmed read results. Tone is overridden by the per-kind meta.
  const containerClass = isDraft
    ? 'rounded-xl border-2 border-dashed border-amber-400 dark:border-amber-500 bg-amber-50/50 dark:bg-amber-950/30 shadow-sm overflow-hidden my-1.5'
    : `rounded-xl border-2 ${meta.tone} bg-white dark:bg-slate-900 shadow-sm overflow-hidden my-1.5`;

  return (
    <div
      data-testid={`assistant-card-${card.type}-${card.id || 'x'}`}
      className={containerClass}
    >
      <div className={`bg-gradient-to-l ${meta.color} text-white px-3 py-1.5 flex items-center gap-2`}>
        <Icon size={14} />
        <div className="flex-1 truncate text-[12px] font-extrabold">{card.title || card.type}</div>
        {isDraft && (
          <span
            data-testid={`draft-badge-${card.id || 'x'}`}
            className="text-[9px] font-extrabold px-1.5 py-0.5 rounded-full bg-white/30 backdrop-blur-sm border border-white/40"
          >
            مسوّدة
          </span>
        )}
      </div>
      <div className="px-3 py-2 space-y-0.5">
        {renderFields(card)}
      </div>
      {card.actions && card.actions.length > 0 && (
        <div className="px-2 pb-2 pt-1 flex flex-wrap gap-1.5 border-t border-slate-200 dark:border-slate-700">
          {card.actions.map((a) => {
            const disabled = a.intent === 'deferred';
            return (
              <button
                key={a.id}
                data-testid={`card-action-${card.type}-${a.id}`}
                onClick={() => handleAction(a)}
                disabled={disabled}
                title={disabled ? `سيتم تفعيله في ${a.phase || 'مرحلة لاحقة'}` : a.label}
                className={`text-[10px] px-2 py-0.5 rounded-full border inline-flex items-center gap-1 transition-colors ${chipClass(a.intent, disabled)}`}
              >
                {iconForAction(a)}
                {a.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AssistantCard;
