import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Phone, FileText, Send, Car, Wrench, Package, AlertTriangle, ExternalLink, Building2, User, Receipt, Sparkles, ClipboardList, CalendarCheck, BadgeCheck, ShieldCheck, History, MessageCircle, BarChart3, Bug } from 'lucide-react';

/**
 * 🎴 AssistantCard — renderer for interactive ERP cards embedded inside chat.
 *
 * Backend tool handlers attach a `cards: [{type,title,data,actions}]` list to
 * their result. The drawer collects them and renders one <AssistantCard/> per
 * card. Each action chip dispatches based on its `intent`:
 *   • navigate  → react-router push
 *   • tool      → re-trigger an assistant tool (read-only)
 *   • runtime   → POST to /api/runtime/* (Phase 3C)
 *   • deferred  → display as disabled with a "Phase 3X" hint
 *
 * 🆕 Phase 3B Round 2: DraftCard styling (dashed border + amber gradient).
 * 🆕 Phase 3C.5:       7 new card types (Visit/Payment/Approval/Audit/WhatsApp/ReportDetail/Finding).
 */

const TYPE_META = {
  CustomerCard: { Icon: User, color: 'from-indigo-600 to-blue-600', tone: 'border-indigo-300 dark:border-indigo-700' },
  VehicleCard: { Icon: Car, color: 'from-emerald-600 to-teal-600', tone: 'border-emerald-300 dark:border-emerald-700' },
  InvoiceCard: { Icon: Receipt, color: 'from-amber-600 to-orange-600', tone: 'border-amber-300 dark:border-amber-700' },
  OperationCard: { Icon: Wrench, color: 'from-slate-600 to-zinc-600', tone: 'border-slate-300 dark:border-slate-700' },
  SupplierCard: { Icon: Building2, color: 'from-fuchsia-600 to-purple-600', tone: 'border-fuchsia-300 dark:border-fuchsia-700' },
  InventoryCard: { Icon: Package, color: 'from-cyan-600 to-sky-600', tone: 'border-cyan-300 dark:border-cyan-700' },
  AuditCard: { Icon: History, color: 'from-slate-500 to-stone-600', tone: 'border-slate-300 dark:border-slate-700' },
  // 🆕 Phase 3C.6 — friendly guidance card (no draft)
  GuidanceCard: { Icon: Sparkles, color: 'from-indigo-500 to-violet-600', tone: 'border-indigo-200 dark:border-indigo-800' },
  // 🆕 Phase 3C.5
  VisitCard: { Icon: CalendarCheck, color: 'from-teal-600 to-cyan-600', tone: 'border-teal-300 dark:border-teal-700' },
  PaymentCard: { Icon: Receipt, color: 'from-emerald-600 to-green-600', tone: 'border-emerald-300 dark:border-emerald-700' },
  ApprovalCard: { Icon: BadgeCheck, color: 'from-violet-600 to-purple-600', tone: 'border-violet-300 dark:border-violet-700' },
  WhatsAppCard: { Icon: MessageCircle, color: 'from-green-600 to-emerald-600', tone: 'border-green-300 dark:border-green-700' },
  ReportDetailCard: { Icon: BarChart3, color: 'from-blue-600 to-indigo-600', tone: 'border-blue-300 dark:border-blue-700' },
  FindingCard: { Icon: Bug, color: 'from-rose-600 to-red-600', tone: 'border-rose-300 dark:border-rose-700' },
  ReportCard: { Icon: BarChart3, color: 'from-blue-500 to-indigo-500', tone: 'border-blue-200 dark:border-blue-700' },
  // 🆕 Phase 3C.9 — Service catalog card
  ServiceCard: { Icon: Wrench, color: 'from-amber-500 via-orange-500 to-rose-500', tone: 'border-amber-200 dark:border-amber-800' },
  SearchIntentCard: { Icon: Sparkles, color: 'from-cyan-500 to-blue-500', tone: 'border-cyan-200 dark:border-cyan-800' },
};

// 🆕 Round 2 — Draft card styling per intent kind (more polished, matches site theme)
const DRAFT_META = {
  customer: { Icon: User, color: 'from-indigo-500 via-blue-500 to-cyan-500' },
  vehicle: { Icon: Car, color: 'from-emerald-500 via-teal-500 to-cyan-500' },
  visit: { Icon: ClipboardList, color: 'from-teal-500 via-cyan-500 to-sky-500' },
  operation: { Icon: Wrench, color: 'from-slate-600 via-zinc-600 to-gray-600' },
  invoice: { Icon: Receipt, color: 'from-amber-500 via-orange-500 to-rose-500' },
  collection: { Icon: Receipt, color: 'from-emerald-500 to-green-600' },
  payment: { Icon: Receipt, color: 'from-rose-500 to-red-600' },
  supplier: { Icon: Building2, color: 'from-fuchsia-500 via-purple-500 to-violet-600' },
  inventory: { Icon: Package, color: 'from-cyan-500 to-sky-600' },
  part_search: { Icon: Package, color: 'from-cyan-400 via-cyan-500 to-sky-600' },
  unknown: { Icon: Sparkles, color: 'from-slate-500 to-zinc-600' },
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
  // 🆕 Phase 3C.5
  approved: 'مُعتمدة',
  rejected: 'مرفوضة',
  rolled_back: 'مُلغاة',
  committed: 'مُنفّذة',
  sent: 'مُرسلة',
  failed: 'فشلت',
  queued: 'في الطابور',
  MOCKED: 'محاكاة',
  critical: '🔴 حرجة',
  warning: '🟡 تنبيه',
  info: '🔵 معلومة',
  diagnosis: 'تشخيص',
  repair: 'تحت الإصلاح',
  ready: 'جاهزة للتسليم',
  archived: 'مؤرشفة',
};

// 💳 تسميات طرق الدفع العربية — لعرض واضح بدل القيم الخام
const PAY_LABEL = {
  cash: '💵 نقدي', credit: '⏳ آجل (ذمم)', deferred: '⏳ آجل (ذمم)',
  bank: '🏦 تحويل بنكي', transfer: '🏦 تحويل بنكي', pos: '💳 شبكة / نقاط بيع',
  card: '💳 بطاقة', 'آجل': '⏳ آجل (ذمم)', 'اجل': '⏳ آجل (ذمم)', 'نقدي': '💵 نقدي',
};

function chipClass(intent, disabled) {
  if (disabled) return 'bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed';
  if (intent === 'navigate') return 'bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-200 hover:bg-indigo-200 dark:hover:bg-indigo-800 border-indigo-300 dark:border-indigo-700';
  if (intent === 'tool') return 'bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-200 hover:bg-emerald-200 dark:hover:bg-emerald-800 border-emerald-300 dark:border-emerald-700';
  if (intent === 'runtime') return 'bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-200 hover:bg-amber-200 dark:hover:bg-amber-800 border-amber-400 dark:border-amber-700 font-bold';
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
    // 🆕 Phase 3C.5 — 7 new card renderers
    case 'VisitCard':
      return (
        <>
          {d.customer_name && <Row label="العميل" value={d.customer_name} />}
          {d.plate && <Row label="اللوحة" value={d.plate} />}
          {d.status && <Row label="الحالة" value={STATUS_LABEL[d.status] || d.status} highlight="teal" />}
          {d.brand && <Row label="الماركة" value={`${d.brand}${d.model ? ' ' + d.model : ''}`} />}
          {d.entry_date && <Row label="تاريخ الدخول" value={String(d.entry_date).slice(0, 10)} />}
        </>
      );
    case 'PaymentCard':
      return (
        <>
          {d.party && <Row label="الطرف" value={d.party} />}
          {d.amount_formatted && <Row label="المبلغ" value={d.amount_formatted} highlight={d.direction === 'in' ? 'emerald' : 'rose'} />}
          {d.method && <Row label="الطريقة" value={d.method} />}
          {d.reference && <Row label="مرجع" value={d.reference} />}
          {d.date && <Row label="التاريخ" value={String(d.date).slice(0, 10)} />}
        </>
      );
    case 'ApprovalCard':
      return (
        <>
          {d.status && <Row label="الحالة" value={STATUS_LABEL[d.status] || d.status} highlight={d.status === 'approved' ? 'emerald' : d.status === 'rejected' ? 'rose' : 'indigo'} />}
          {d.requester && <Row label="مقدّم الطلب" value={d.requester} />}
          {d.approver && <Row label="المعتمد" value={d.approver} />}
          {d.draft_id && <Row label="مسوّدة" value={String(d.draft_id).slice(0, 12)} />}
        </>
      );
    case 'AuditCard':
      return (
        <>
          {d.event && <Row label="حدث" value={d.event} highlight="indigo" />}
          {d.proposer && <Row label="المُنشئ" value={d.proposer} />}
          {d.approver && <Row label="المعتمد" value={d.approver} />}
          {d.table && <Row label="الجدول" value={d.table} />}
          {d.draft_id && <Row label="مسوّدة" value={String(d.draft_id).slice(0, 10)} />}
        </>
      );
    case 'WhatsAppCard':
      return (
        <>
          {d.to && <Row label="إلى" value={d.to} />}
          {d.message && <Row label="نص" value={String(d.message).slice(0, 80)} />}
          {d.status && <Row label="الحالة" value={STATUS_LABEL[d.status] || d.status} highlight={d.status === 'sent' ? 'emerald' : d.status === 'failed' ? 'rose' : 'amber'} />}
          {d.provider && <Row label="المزوّد" value={d.provider} />}
        </>
      );
    case 'ReportDetailCard':
      return (
        <>
          {d.summary && <Row label="خلاصة" value={d.summary} />}
          {d.period && <Row label="الفترة" value={d.period} />}
          {typeof d.total_rows === 'number' && <Row label="عدد" value={`${d.total_rows} سطر`} highlight="indigo" />}
          {Array.isArray(d.kpis) && d.kpis.slice(0, 3).map((k, i) => (
            <Row key={i} label={k.label || k.name} value={k.value_formatted || k.value} highlight="emerald" />
          ))}
        </>
      );
    case 'FindingCard':
      return (
        <>
          {d.severity && <Row label="الخطورة" value={STATUS_LABEL[d.severity] || d.severity} highlight={d.severity === 'critical' ? 'rose' : d.severity === 'warning' ? 'amber' : 'indigo'} />}
          {d.detail && <Row label="التفاصيل" value={String(d.detail).slice(0, 100)} />}
          {d.entity_type && <Row label="النوع" value={d.entity_type} />}
          {d.suggested_action && <Row label="مقترح" value={String(d.suggested_action).slice(0, 80)} highlight="emerald" />}
        </>
      );
    case 'ReportCard':
      return (
        <>
          {Object.entries(d).filter(([k]) => !['id', 'title'].includes(k)).slice(0, 4).map(([k, v]) => (
            <Row key={k} label={k} value={typeof v === 'object' ? JSON.stringify(v).slice(0, 30) : String(v).slice(0, 50)} />
          ))}
        </>
      );
    case 'ServiceCard':
      return (
        <>
          {d.category && <Row label="التصنيف" value={d.category} highlight="indigo" />}
          {d.price_formatted && <Row label="السعر" value={d.price_formatted} highlight="emerald" />}
          {d.duration_minutes && <Row label="المدة" value={`${d.duration_minutes} دقيقة`} />}
        </>
      );
    case 'SearchIntentCard':
      return (
        <div className="text-[12px] text-slate-600 dark:text-slate-300 py-1">
          {d.raw && <div className="opacity-80">{String(d.raw).slice(0, 100)}</div>}
        </div>
      );
    case 'GuidanceCard':
      return (
        <div className="text-[12px] space-y-1.5 py-1">
          {d.hint && (
            <div className="text-slate-600 dark:text-slate-300">{d.hint}</div>
          )}
          {Array.isArray(d.examples) && d.examples.length > 0 && (
            <div className="space-y-1">
              <div className="text-[11px] text-slate-500 dark:text-slate-400 font-bold">جرّب أمثلة:</div>
              {d.examples.slice(0, 4).map((ex, i) => (
                <div key={i} className="text-[11px] text-indigo-600 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 px-2 py-1 rounded border border-indigo-200 dark:border-indigo-800">
                  • {ex}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    default:
      // 🆕 Round 2 — Draft cards (e.g. CustomerDraftCard, VehicleDraftCard, ...)
      if (typeof t === 'string' && t.endsWith('DraftCard')) {
        const payMethod = d.payment_method || d.paymentMethod;
        const echoAccounts = d._echo && d._echo.accounts;
        return (
          <>
            {d.name && <Row label="الاسم" value={d.name} />}
            {(d.customer || d.customer_name) && <Row label="العميل" value={d.customer || d.customer_name} />}
            {d.supplier && <Row label="المورد" value={d.supplier} />}
            {d.plate && <Row label="اللوحة" value={d.plate} />}
            {d.phone && <Row label="هاتف" value={d.phone} />}
            {typeof d.amount === 'number' && (
              <Row label="المبلغ" value={`${d.amount.toLocaleString('ar-SA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ر.س`} highlight="indigo" />
            )}
            {payMethod && (
              <Row
                label="طريقة الدفع"
                value={PAY_LABEL[payMethod] || payMethod}
                highlight={['credit', 'آجل', 'اجل', 'deferred'].includes(payMethod) ? 'amber' : 'slate'}
              />
            )}
            {(d.category || d.description) && <Row label="البيان" value={String(d.category || d.description).slice(0, 60)} />}
            {d.date && <Row label="التاريخ" value={String(d.date).slice(0, 10)} />}
            {d._resolved_from && (
              <Row label="مستند إلى" value={d._resolved_from.title || d._resolved_from.key} highlight="emerald" />
            )}
            {echoAccounts && (
              <div className="mt-1 text-[11px] font-bold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 rounded-md px-2 py-1 border border-indigo-200 dark:border-indigo-800" data-testid="draft-accounting-effect">
                🧾 الأثر المحاسبي: {echoAccounts}
              </div>
            )}
            {!d.name && !d.customer && !d.customer_name && !d.supplier && typeof d.amount !== 'number' && d.raw && (
              <Row label="النص" value={String(d.raw).slice(0, 80)} />
            )}
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
    teal: 'text-teal-600 dark:text-teal-300 font-bold',
    amber: 'text-amber-600 dark:text-amber-300 font-bold',
  };
  return (
    <div className="flex justify-between items-center gap-2 text-xs">
      <span className="text-slate-500 dark:text-slate-400 font-semibold shrink-0">{label}</span>
      <span className={`${tones[highlight] || tones.slate} text-left`}>{value}</span>
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

  // 🆕 Phase 3C — runtime-enabled drafts get an extra status pill
  const runtimeEnabled = isDraft && card.runtime && card.runtime.enabled;
  const cardStatus = card.status || (runtimeEnabled ? 'draft' : null);

  const handleAction = (action) => {
    if (!action) return;
    if (action.intent === 'deferred') return;
    if (action.intent === 'navigate' && action.target) {
      navigate(action.target);
      onAction?.(action, card);
      return;
    }
    if (action.intent === 'tool' && action.tool) {
      onAction?.(action, card);
      return;
    }
    // 🆕 Phase 3C — runtime actions delegate to the parent (drawer) that knows
    // how to POST to /api/runtime/*. The drawer then refreshes the card.
    if (action.intent === 'runtime') {
      onAction?.(action, card);
      return;
    }
    onAction?.(action, card);
  };

  const containerClass = isDraft
    ? 'rounded-xl border border-slate-200 dark:border-slate-700 bg-gradient-to-br from-slate-50 to-white dark:from-slate-800/60 dark:to-slate-900/80 shadow-md hover:shadow-lg transition-all overflow-hidden my-2'
    : `rounded-xl border ${meta.tone} bg-white dark:bg-slate-900 shadow-sm hover:shadow-md transition-shadow overflow-hidden my-1.5`;

  return (
    <div
      data-testid={`assistant-card-${card.type}-${card.id || 'x'}`}
      className={containerClass}
    >
      <div className={`bg-gradient-to-l ${meta.color} text-white px-3 py-2 flex items-center gap-2`}>
        <Icon size={16} className="shrink-0 drop-shadow" />
        <div
          className="flex-1 truncate text-sm font-black tracking-tight"
          style={{ textShadow: '0 1px 2px rgba(0,0,0,0.45)' }}
          data-testid="assistant-card-title"
        >
          {card.title || card.type}
        </div>
        {isDraft && (
          <span
            data-testid={`draft-badge-${card.id || 'x'}`}
            className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-black/25 border border-white/50 shrink-0"
            style={{ textShadow: '0 1px 1px rgba(0,0,0,0.4)' }}
          >
            {cardStatus === 'committed' ? 'مُنفّذة' :
              cardStatus === 'approved' ? 'مُعتمدة' :
                cardStatus === 'pending_approval' ? 'بانتظار اعتماد' :
                  cardStatus === 'rejected' ? 'مرفوضة' :
                    cardStatus === 'rolled_back' ? 'مُلغاة' : 'مسوّدة'}
          </span>
        )}
      </div>
      <div className="px-3 py-2 space-y-0.5">
        {renderFields(card)}
        {runtimeEnabled && (
          <div className="mt-1 text-[10px] text-amber-700 dark:text-amber-300 flex items-center gap-1">
            <Sparkles size={9} />
            <span>Phase 3C runtime: تعتمد → ثم تُنفّذ بقاعدة 4-Eyes</span>
          </div>
        )}
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
