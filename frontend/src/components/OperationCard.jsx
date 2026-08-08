import React, { useEffect, useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Pencil,
  Save,
  X,
  Printer,
  Trash2,
  Car,
  CreditCard,
  FileText,
  Landmark,
  Link2,
  Calendar,
  Wallet,
  Receipt,
  CheckCircle2,
  Eye,
  AlertTriangle,
} from 'lucide-react';
import {
  ACCOUNT_NAME_MAP,
  OPERATION_TYPE_LABELS,
  PAYMENT_METHOD_LABELS,
  PAYMENT_STATUS_LABELS,
  cleanAccountingText,
  extractAccountMetaFromNotes,
  formatVisitNumber,
  labelFromMap,
  normalizeAccountCode,
  resolveAccountDisplay,
  resolveVehicleDisplay,
  resolveVisitDisplay,
} from '../utils/displayLabels';
import { cleanNotes as cleanNotesUtil } from '../utils/operationCardHelpers';
import OperationCardHeader from './operation/OperationCardHeader';
import OperationCardMeta from './operation/OperationCardMeta';
import AccountingBadge from './operation/AccountingBadge';
import StatusBadgeNew from './operation/StatusBadge';

const formatDateTime = (dateLike, isRTL) => {
  try {
    const d = new Date(dateLike);
    const locale = isRTL ? 'ar-SA-u-ca-gregory' : 'en-US';
    const raw = String(dateLike || '');
    const dateStr = d.toLocaleDateString(locale, { year: 'numeric', month: '2-digit', day: '2-digit' });
    if (/T00:00:00|^\d{4}-\d{2}-\d{2}$/.test(raw)) return dateStr;
    const timeStr = d.toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
    return `${dateStr} ${timeStr}`;
  } catch {
    return '-';
  }
};

const sanitizeAccountingText = cleanAccountingText;

const normalizePaymentSourceAccount = (operation = {}, t) => {
  const method = String(operation.paymentMethod || '').toLowerCase();
  if (method === 'cash') return 'الصندوق';
  if (method === 'transfer' || method === 'bank') return 'البنك';
  if (method === 'card' || method === 'pos') return 'نقاط البيع';
  if (method === 'credit') {
    return ['sale', 'service', 'instant_sale'].includes(String(operation.type || '').toLowerCase()) ? 'الذمم المدينة' : 'الذمم الدائنة';
  }
  return t('operations.paymentMethod') || 'الدفع';
};

const accountPhrase = (value, fallback) => {
  const text = sanitizeAccountingText(value || fallback || 'الحساب');
  return String(text).trim().startsWith('حساب') ? text : `حساب ${text}`;
};

const resolveTargetAccountName = (operation, chartAccount, businessAccount, t) => {
  const notes = String(operation?.notes || '');
  const marker = 'ACCOUNTING_TARGET:';
  const markerIndex = notes.indexOf(marker);
  if (markerIndex >= 0) {
    const parsed = notes.slice(markerIndex + marker.length).split('|')[0].trim();
    if (parsed) return sanitizeAccountingText(parsed) || parsed;
  }
  const resolved = resolveAccountDisplay(operation, chartAccount ? [chartAccount] : [], businessAccount ? [businessAccount] : []);
  if (resolved?.name && resolved.name !== 'الحساب غير محدد') return resolved.name;

  const opType = String(operation?.type || '').toLowerCase();
  const partnerType = String(operation?.partnerType || '').toLowerCase();
  if (['sale', 'service', 'sale_return'].includes(opType)) return 'إيرادات الخدمات';
  if (['purchase', 'expense', 'purchase_return'].includes(opType)) return 'مصروفات / مشتريات';
  if (opType === 'payment_order' && partnerType === 'supplier') return 'الموردون';
  if (opType === 'payment_order' && partnerType === 'customer') return 'العملاء';
  return t('operations.account') || 'الحساب';
};

const resolveAccountCode = (operation, chartAccount, businessAccount) => {
  const notes = String(operation?.notes || '');
  const codeMatch = notes.match(/ACCOUNT_CODE\s*:\s*([0-9]+)/i);
  if (codeMatch?.[1]) return normalizeAccountCode(codeMatch[1]);
  if (chartAccount?.code) return normalizeAccountCode(String(chartAccount.code));
  if (businessAccount?.code) return normalizeAccountCode(String(businessAccount.code));
  const fallback = operation?.accountCode || operation?.account_number || operation?.accountNumber;
  const normalized = normalizeAccountCode(fallback || operation?.accountingAccountId || '');
  return ACCOUNT_NAME_MAP[normalized] ? normalized : (fallback ? normalizeAccountCode(String(fallback)) : '');
};

const classifyAccountCode = (accountCode = '') => {
  const code = String(accountCode || '').trim();
  if (!code) return 'غير مصنف';
  if (/^0?0[3-9]$/.test(code) || ['010', '1101', '1102', '1103', '1104', '1105'].includes(code)) return 'أصل';
  if (code === '2101' || code.startsWith('2')) return 'التزام';
  if (['024', '025', '026', '027', '028', '041', '042'].includes(code) || code.startsWith('4')) return 'إيراد';
  if (['029', '030', '031', '032', '033', '034', '035', '036', '037', '038', '039', '040', '167', '0421'].includes(code) || code.startsWith('5') || code.startsWith('6')) return 'مصروف';
  if (code.startsWith('4')) return 'إيراد';
  if (code.startsWith('5') || code.startsWith('6')) return 'مصروف';
  if (code.startsWith('1')) return 'أصل';
  if (code.startsWith('2')) return 'التزام';
  if (code.startsWith('3')) return 'حقوق ملكية';
  return 'غير مصنف';
};

const classifyAccountDisplay = (accountCode = '', accountName = '') => {
  const byCode = classifyAccountCode(accountCode);
  if (byCode !== 'غير مصنف') return byCode;
  const name = String(accountName || '').toLowerCase();
  if (name.includes('إيراد') || name.includes('ايراد') || name.includes('خدمات')) return 'إيراد';
  if (name.includes('تكلفة') || name.includes('مصروف') || name.includes('رواتب')) return 'مصروف';
  if (name.includes('مورد') || name.includes('ذمم دائنة')) return 'التزام';
  if (name.includes('عميل') || name.includes('صندوق') || name.includes('بنك') || name.includes('ذمم مدينة')) return 'أصل';
  return byCode;
};

const classifyOperationAccount = (operation = {}, accountCode = '', accountName = '') => {
  const direct = classifyAccountDisplay(accountCode, accountName);
  if (direct !== 'غير مصنف') return direct;
  const opType = String(operation.type || '').toLowerCase();
  const partnerType = String(operation.partnerType || '').toLowerCase();
  if (['sale', 'service', 'instant_sale', 'collect_customer'].includes(opType)) return 'إيراد';
  if (['purchase', 'expense', 'cash_expense', 'salary', 'purchase_return'].includes(opType)) return 'مصروف';
  if (opType === 'payment_order' && partnerType === 'supplier') return 'التزام';
  if (opType === 'payment_order' && partnerType === 'customer') return 'أصل';
  return 'تلقائي حسب العملية';
};

// ============================================================
// 🎨 Visual helpers moved to /utils/operationCardHelpers.js and /components/operation/*
// (cleanNotes, StatusBadge, InfoCard are now imported from dedicated files)
// ============================================================
const cleanNotes = cleanNotesUtil;

export default function OperationCard({
  operation,
  isRTL,
  t,
  accounts,
  businessAccounts,
  customers = [],
  suppliers = [],
  vehicles,
  onPrint,
  onDelete,
  onViewVehicle,
  onConfirmCreditPayment,
  onEditInForm,
  onUpdateItems,
  isSaving,
  isDeleting,
  expanded,
  onExpandedChange,
  integrityStatus = null,
}) {
  const isControlled = typeof expanded === 'boolean' && typeof onExpandedChange === 'function';
  const [internalExpanded, setInternalExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [itemsDraft, setItemsDraft] = useState([]);
  const [editMeta, setEditMeta] = useState({
    partnerName: '',
    partnerId: '',
    accountCode: '',
    accountName: '',
  });

  const isExpanded = isControlled ? expanded : internalExpanded;
  const setExpandedState = (next) => {
    if (isControlled) {
      onExpandedChange(next);
    } else {
      setInternalExpanded(next);
    }
  };

  useEffect(() => {
    if (editing) {
      setItemsDraft(Array.isArray(operation.items) ? operation.items.map((it) => ({ ...it })) : []);
      setEditMeta({
        partnerName: operation.partnerName || operation.customerName || operation.supplierName || '',
        partnerId: operation.partnerId || operation.customerId || operation.supplierId || '',
        accountCode: operation.accountCode || operation.account || '',
        accountName: operation.accountName || operation.account_name || '',
      });
    }
  }, [editing, operation.items]);

  useEffect(() => {
    if (!isExpanded) {
      setEditing(false);
    }
  }, [isExpanded]);

  const chartAccount = useMemo(() => {
    const all = accounts || [];
    const noteCode = extractAccountMetaFromNotes(operation.notes).code;
    const refs = [operation.accountingAccountId, operation.accountId, operation.accountCode, noteCode]
      .filter(Boolean)
      .map((v) => String(v));
    return all.find((a) => {
      const accRefs = [a.id, a.code, normalizeAccountCode(a.id), normalizeAccountCode(a.code)].filter(Boolean).map(String);
      return refs.some((ref) => accRefs.includes(ref) || accRefs.includes(normalizeAccountCode(ref)));
    });
  }, [accounts, operation.accountId, operation.accountingAccountId]);

  const businessAccount = useMemo(
    () => (businessAccounts || []).find((a) => (a.id || a.code) === operation.accountId),
    [businessAccounts, operation.accountId]
  );

  const vehicle = useMemo(
    () => (vehicles || []).find((v) => v.id === operation.vehicleId),
    [vehicles, operation.vehicleId]
  );

  const customerDisplay = useMemo(
    () => {
      if (String(operation?.partnerType || '').toLowerCase() === 'customer') {
        return vehicle?.customerName || vehicle?.ownerName || operation?.customerName || operation?.partnerName || 'غير محدد';
      }
      return operation?.partnerName || vehicle?.customerName || vehicle?.ownerName || 'غير محدد';
    },
    [operation?.partnerType, operation?.partnerName, operation?.customerName, vehicle]
  );

  const vehicleDisplay = useMemo(
    () => resolveVehicleDisplay(operation, vehicle ? [vehicle] : []),
    [vehicle, operation]
  );

  const targetAccountMeta = useMemo(
    () => resolveAccountDisplay(operation, accounts, businessAccounts),
    [operation, accounts, businessAccounts]
  );

  const targetAccountName = useMemo(
    () => targetAccountMeta.name || resolveTargetAccountName(operation, chartAccount, businessAccount, t),
    [targetAccountMeta.name, operation, chartAccount, businessAccount, t]
  );

  const journalEntryText = useMemo(() => {
    const fromAccount = sanitizeAccountingText(normalizePaymentSourceAccount(operation, t));
    const toAccount = sanitizeAccountingText(targetAccountName);
    return `قيد محاسبي: من ${accountPhrase(fromAccount, t('operations.account'))} إلى ${accountPhrase(toAccount, t('operations.account'))}`;
  }, [operation, targetAccountName, t]);

  const paymentReceiptUrl = useMemo(() => {
    const notes = String(operation?.notes || '');
    const match = notes.match(/\[PAYMENT_RECEIPT\]\s*(\S+)/i);
    if (!match?.[1]) return '';
    const candidate = String(match[1]).trim();
    if (!candidate) return '';
    if (candidate.startsWith('http://') || candidate.startsWith('https://')) return candidate;
    return candidate.startsWith('/') ? candidate : `/${candidate}`;
  }, [operation?.notes]);

  const accountCode = useMemo(
    () => targetAccountMeta.code || resolveAccountCode(operation, chartAccount, businessAccount),
    [targetAccountMeta.code, operation, chartAccount, businessAccount]
  );

  const accountClassLabel = useMemo(
    () => classifyOperationAccount(operation, accountCode, targetAccountName),
    [operation, accountCode, targetAccountName]
  );

  const isPurchaseOperation = useMemo(() => {
    const opType = String(operation.type || '').toLowerCase();
    return ['purchase', 'expense', 'out', 'purchase_return'].includes(opType);
  }, [operation.type]);

  const partyOptions = useMemo(
    () => (isPurchaseOperation ? suppliers : customers),
    [isPurchaseOperation, suppliers, customers]
  );

  const itemsSummary = useMemo(() => {
    const items = Array.isArray(operation.items) ? operation.items : [];
    if (!items.length) return '-';
    const names = items
      .map((it) => it?.name || it?.itemName || it?.description)
      .filter(Boolean);
    if (!names.length) return '-';
    return names.slice(0, 2).join(' • ');
  }, [operation.items]);

  const itemsView = editing ? itemsDraft : (operation.items || []);
  const normalizedItems = useMemo(() => {
    const items = Array.isArray(itemsView) ? itemsView : [];
    return items.map((it) => {
      const quantity = Number(it?.quantity || 1);
      const price = Number(it?.price || 0);
      const lineTotal = Number(it?.total ?? (quantity * price));
      return {
        ...it,
        quantity,
        price,
        lineTotal,
      };
    });
  }, [itemsView]);

  const isSupplierItem = (item = {}) => {
    const tags = [
      item.itemType,
      item.type,
      item.billingType,
      item.partyType,
      item.partnerType,
      item.source,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();

    if (tags.includes('supplier') || tags.includes('مورد')) return true;

    const label = String(item?.name || item?.description || '').toLowerCase();
    if (label.includes('مورد')) return true;
    return false;
  };

  const supplierItems = useMemo(
    () => normalizedItems.filter((it) => isSupplierItem(it)),
    [normalizedItems]
  );

  const workshopItems = useMemo(
    () => normalizedItems.filter((it) => !isSupplierItem(it)),
    [normalizedItems]
  );

  const supplierItemsTotal = useMemo(
    () => supplierItems.reduce((sum, it) => sum + Number(it.lineTotal || 0), 0),
    [supplierItems]
  );

  const workshopRevenueTotal = useMemo(
    () => workshopItems.reduce((sum, it) => sum + Number(it.lineTotal || 0), 0),
    [workshopItems]
  );

  const totalDraft = useMemo(() => {
    return normalizedItems.reduce((sum, it) => sum + Number(it.lineTotal || 0), 0);
  }, [normalizedItems]);

  const displayedWorkshopAmount =
    workshopRevenueTotal > 0
      ? workshopRevenueTotal
      : Number(editing ? totalDraft : (operation.total || 0));

  const typeLabel = labelFromMap(operation.type, OPERATION_TYPE_LABELS, '-');

  const isIncome = ['sale', 'service', 'instant_sale', 'collect_customer'].includes(String(operation.type || '').toLowerCase());
  const typePill = isIncome
    ? 'bg-emerald-500/12 text-emerald-200 border border-emerald-500/25'
    : 'bg-rose-500/12 text-rose-200 border border-rose-500/25';

  const scopePill = (operation.scope === 'workshop' || (!operation.scope && !operation.vehicleId))
    ? 'bg-slate-500/10 text-slate-200 border border-slate-500/20'
    : 'bg-sky-500/10 text-sky-200 border border-sky-500/20';

  const cardBackground = isIncome
    ? 'radial-gradient(circle at 12% 18%, rgba(16,185,129,0.20), transparent 52%), radial-gradient(circle at 88% 78%, rgba(99,102,241,0.12), transparent 55%), rgba(255,255,255,0.05)'
    : 'radial-gradient(circle at 12% 18%, rgba(244,63,94,0.20), transparent 52%), radial-gradient(circle at 88% 78%, rgba(168,85,247,0.12), transparent 55%), rgba(255,255,255,0.05)';

  const cardBorder = isIncome ? 'rgba(16,185,129,0.24)' : 'rgba(244,63,94,0.24)';
  const paymentStatus = (operation.paymentStatus || operation.payment_status || '').toString().toLowerCase();
  const paymentMethod = (operation.paymentMethod || operation.payment_method || '').toString().toLowerCase();
  const hasPaymentStatus = Boolean(paymentStatus || paymentMethod);
  const isCredit = ['unpaid', 'credit', 'deferred', 'partial'].includes(paymentStatus)
    || ['credit', 'deferred'].includes(paymentMethod);
  const totalPaid = Number(operation.totalPaid ?? operation.paymentAmount ?? 0);
  const remainingBalance = Number(operation.balance ?? Math.max(Number(operation.total || 0) - totalPaid, 0));
  const canConfirmCreditPayment = isCredit
    && remainingBalance > 0.009
    && !['paid', 'paid_full', 'full', 'settled'].includes(paymentStatus);
  const canEditOperation = typeof onEditInForm === 'function' || typeof onUpdateItems === 'function';
  const canDeleteOperation = typeof onDelete === 'function';
  const paymentStatusLabel = labelFromMap(paymentStatus, PAYMENT_STATUS_LABELS, '-');
  const paymentMethodLabel = labelFromMap(paymentMethod, PAYMENT_METHOD_LABELS, '-');

  // 🟢 تصنيف الحركة من منظور الورشة:
  // - مدينة (Debit / IN): الأموال داخلة للورشة → مبيعات، خدمات، تحصيل عميل، سند قبض
  // - دائنة (Credit / OUT): الأموال خارجة من الورشة → مشتريات، مصاريف، سداد لمورد، رواتب
  const opType = String(operation.type || '').toLowerCase();
  const incomeTypes = new Set(['sale', 'service', 'instant_sale', 'collect_customer', 'receipt_voucher', 'sale_return']);
  const outflowTypes = new Set(['purchase', 'expense', 'cash_expense', 'salary', 'payment_order', 'pay_supplier', 'purchase_return']);
  let movementSide = '';
  let movementLabel = '';
  if (incomeTypes.has(opType)) {
    movementSide = 'debit';
    movementLabel = 'مدين (داخل)';
  } else if (outflowTypes.has(opType)) {
    movementSide = 'credit';
    movementLabel = 'دائن (خارج)';
  } else {
    movementSide = 'neutral';
    movementLabel = 'متعادل';
  }

  // 🟡 مصدر العملية: POS أم ملف المركبة
  const opSource = String(operation.source || '').toLowerCase();
  const opNotesStr = String(operation.notes || '').toLowerCase();
  // POS marker قد يأتي بصيغ مختلفة: source=pos*, notes [pos]/[source:smart_pos]/smart_pos
  const posInNotesRegex = /\[source:[^\]]*pos[^\]]*\]/i;
  const isPosOrigin = (
    opSource.includes('pos') ||
    opSource.includes('instant_sale') ||
    opSource === 'pos_template' ||
    opNotesStr.includes('[pos]') ||
    opNotesStr.includes('smart_pos') ||
    posInNotesRegex.test(operation.notes || '')
  );
  let originLabel = '';
  let originColor = '';
  if (isPosOrigin) {
    originLabel = 'POS';
    originColor = 'bg-indigo-50 text-indigo-950 border-indigo-300';
  } else if (
    opSource === 'vehicle_visit_sync' ||
    opSource.startsWith('visit_') ||
    operation.visitId || operation.visit_id ||
    operation.vehicleId || operation.vehicle_id
  ) {
    originLabel = 'ملف المركبة';
    originColor = 'bg-cyan-50 text-cyan-950 border-cyan-300';
  } else {
    originLabel = 'عام';
    originColor = 'bg-slate-50 text-slate-900 border-slate-300';
  }
  const visitDisplay = resolveVisitDisplay(operation, 'زيارة مرتبطة');
  const operationNotesDisplay = useMemo(() => {
    const cleaned = sanitizeAccountingText(operation.notes);
    if (!cleaned) return '-';
    return cleaned.replace(/عملية من الزيارة\s+[0-9a-f]{6,}/ig, `عملية من الزيارة ${formatVisitNumber(visitDisplay, visitDisplay)}`);
  }, [operation.notes, visitDisplay]);
  const paymentBorder = hasPaymentStatus
    ? (isCredit ? 'rgba(217,119,6,0.45)' : 'rgba(5,150,105,0.45)')
    : 'rgba(15,23,42,0.10)';
  const stop = (e) => e.stopPropagation();

  // 🔔 Integrity warning modal — toggled by clicking the ⚠️ pill
  const [showIntegrityModal, setShowIntegrityModal] = useState(false);
  const [showMoreActions, setShowMoreActions] = useState(false);
  const [showFullDetails, setShowFullDetails] = useState(false);

  const integrityWarnings = Array.isArray(integrityStatus?.warnings) ? integrityStatus.warnings : [];
  const hasIntegrityWarning = integrityWarnings.length > 0;
  const integrityLabelMap = {
    missing_journal_entry: 'لا يوجد قيد يومية مرتبط',
    vehicle_not_found: 'المركبة غير موجودة',
    visit_not_found: 'الزيارة غير موجودة',
    visit_vehicle_mismatch: 'الزيارة لا تطابق المركبة المرتبطة',
    vehicle_scope_without_vehicle: 'العملية من نوع مركبة بدون ربط مركبة',
    potential_duplicate: 'تكرار محتمل لنفس العملية',
  };

  // 🎨 cleaned-up notes for the new design (helper extracted above)
  const displayNotesClean = useMemo(() => cleanNotes(operation.notes), [operation.notes]);

  const operationRef = operation.invoiceNumber || operation.reference || operation.id || '-';
  const operationDateText = formatDateTime(operation.date || operation.op_date || operation.createdAt, isRTL);
  const dueTagLabel = isCredit ? 'آجل' : paymentMethodLabel;
  const settlementTagLabel = remainingBalance > 0.009 ? 'غير مسدد' : 'مسدد';
  const linkOk = integrityStatus ? !hasIntegrityWarning : true;
  const cardId = operation.id || operation.invoiceNumber || 'unknown';
  const fullAmount = Number(operation.total || displayedWorkshopAmount || 0);

  return (
    <article
      className="relative overflow-visible rounded-[24px] border border-zinc-200 bg-[#fbfbf8] text-zinc-950 shadow-[0_12px_30px_rgba(15,23,42,0.08)] transition-transform duration-200 hover:-translate-y-0.5 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50"
      dir={isRTL ? 'rtl' : 'ltr'}
      data-testid={`operation-card-${cardId}`}
    >
      <section className="p-4 sm:p-5" data-testid={`operation-card-v5-main-${cardId}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-[19px] font-black leading-tight text-zinc-950 dark:text-white" data-testid={`operation-card-partner-${cardId}`}>
              {customerDisplay}
            </h2>
            <div className="mt-1 line-clamp-2 text-[12px] font-bold leading-relaxed text-zinc-500 dark:text-zinc-400" data-testid={`operation-card-vehicle-summary-${cardId}`}>
              {vehicleDisplay || 'عملية عامة'}
            </div>
          </div>
          <div className="shrink-0 text-left" data-testid={`operation-card-total-${cardId}`}>
            <strong className="block text-[23px] font-black tabular-nums text-zinc-950 dark:text-white">{Number(displayedWorkshopAmount || fullAmount).toLocaleString('en-US')}</strong>
            <span className="text-[11px] font-black text-zinc-500 dark:text-zinc-400">ر.س</span>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5" data-testid={`operation-card-tags-${cardId}`}>
          <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-black text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200" data-testid={`operation-card-payment-method-tag-${cardId}`}>{dueTagLabel}</span>
          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-black ${remainingBalance > 0.009 ? 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200' : 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200'}`} data-testid={`operation-card-payment-status-tag-${cardId}`}>{settlementTagLabel}</span>
          <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-black text-sky-800 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-200" data-testid={`operation-card-type-tag-${cardId}`}>{typeLabel}</span>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2.5" data-testid={`operation-card-payment-summary-${cardId}`}>
          <div className="rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 dark:border-zinc-800 dark:bg-zinc-900/70">
            <small className="block text-[10px] font-black text-zinc-500 dark:text-zinc-400">المدفوع</small>
            <strong className="mt-1 block text-[15px] font-black tabular-nums text-zinc-950 dark:text-white" data-testid={`operation-card-total-paid-${cardId}`}>{Number(totalPaid || 0).toLocaleString('en-US')} ر.س</strong>
          </div>
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2.5 dark:border-rose-900 dark:bg-rose-950/25">
            <small className="block text-[10px] font-black text-rose-700 dark:text-rose-300">المتبقي</small>
            <strong className="mt-1 block text-[15px] font-black tabular-nums text-rose-800 dark:text-rose-200" data-testid={`operation-card-balance-${cardId}`}>{Number(remainingBalance || 0).toLocaleString('en-US')} ر.س</strong>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2.5" data-testid={`operation-card-finance-split-${cardId}`}>
          <div className="rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 dark:border-zinc-800 dark:bg-zinc-900/70">
            <small className="block text-[10px] font-black text-zinc-500 dark:text-zinc-400">إيراد الورشة</small>
            <strong className="mt-1 block text-[13px] font-black tabular-nums text-zinc-950 dark:text-white" data-testid={`operation-card-workshop-revenue-${cardId}`}>{Number(displayedWorkshopAmount || 0).toLocaleString('en-US')} ر.س</strong>
          </div>
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2.5 dark:border-amber-900 dark:bg-amber-950/25">
            <small className="block text-[10px] font-black text-amber-700 dark:text-amber-300">مشتريات مرتبطة</small>
            <strong className="mt-1 block text-[13px] font-black tabular-nums text-amber-900 dark:text-amber-100" data-testid={`operation-card-supplier-total-${cardId}`}>{Number(supplierItemsTotal || 0).toLocaleString('en-US')} ر.س</strong>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[11px] font-bold text-zinc-500 dark:text-zinc-400" data-testid={`operation-card-meta-line-${cardId}`}>
          <span data-testid={`operation-card-visit-date-${cardId}`}>{formatVisitNumber(visitDisplay, visitDisplay)} · {operationDateText}</span>
          <button
            type="button"
            onClick={(e) => { stop(e); if (hasIntegrityWarning) setShowIntegrityModal(true); }}
            className={`min-h-[48px] rounded-full px-2.5 text-[11px] font-black ${linkOk ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-700 dark:text-rose-300'}`}
            data-testid={`operation-card-link-status-${cardId}`}
          >
            {linkOk ? '● الربط سليم' : `⚠ ${integrityWarnings.length} تنبيه`}
          </button>
        </div>
      </section>

      <section className="border-t border-zinc-200 bg-white/65 dark:border-zinc-800 dark:bg-zinc-900/30" data-testid={`operation-card-quick-section-${cardId}`}>
        <button
          type="button"
          className="flex min-h-[48px] w-full items-center justify-between px-4 text-[13px] font-black text-zinc-800 dark:text-zinc-100"
          onClick={(e) => { stop(e); setExpandedState(!isExpanded); }}
          data-testid={`operation-card-toggle-${cardId}`}
        >
          <span>معلومات إضافية</span>
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>

        {isExpanded ? (
          <div className="space-y-3 px-4 pb-4" onClick={stop} data-testid={`operation-card-expanded-${cardId}`}>
            <div className="grid grid-cols-1 gap-2 text-[12px]">
              <div className="flex items-center justify-between gap-3 rounded-xl bg-zinc-50 px-3 py-2 dark:bg-zinc-950" data-testid={`operation-card-reference-${cardId}`}><span className="font-bold text-zinc-500">مرجع العملية</span><strong className="font-mono text-zinc-900 dark:text-zinc-100 truncate">{operationRef}</strong></div>
              <div className="flex items-center justify-between gap-3 rounded-xl bg-zinc-50 px-3 py-2 dark:bg-zinc-950" data-testid={`operation-card-accounting-treatment-${cardId}`}><span className="font-bold text-zinc-500">المعالجة المحاسبية</span><strong className="text-zinc-900 dark:text-zinc-100">متوقعة عند الترحيل</strong></div>
            </div>
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] font-bold leading-relaxed text-amber-900 dark:border-amber-900 dark:bg-amber-950/25 dark:text-amber-100" data-testid={`operation-card-supplier-note-${cardId}`}>
              مشتريات الموردين مستقلة عن ذمة العميل ولا تدخل في إجمالي الخدمة أو الرصيد المتبقي.
            </div>

            <button
              type="button"
              className="flex min-h-[48px] w-full items-center justify-between rounded-2xl border border-zinc-200 bg-white px-3 text-[13px] font-black text-zinc-800 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100"
              onClick={() => setShowFullDetails((prev) => !prev)}
              data-testid={`operation-card-full-details-toggle-${cardId}`}
            >
              <span>عرض كامل التفاصيل</span>
              {showFullDetails ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {showFullDetails ? (
              <div className="space-y-4" data-testid={`operation-card-full-details-${cardId}`}>
                <div>
                  <div className="mb-2 text-[12px] font-black text-zinc-800 dark:text-zinc-100">بنود العميل</div>
                  <div className="overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800">
                    <table className="w-full text-[11px]" data-testid={`operation-card-customer-items-table-${cardId}`}>
                      <thead className="bg-zinc-50 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400"><tr><th className="p-2 text-right">البند</th><th className="p-2 text-right">الكمية</th><th className="p-2 text-right">السعر</th></tr></thead>
                      <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                        {workshopItems.length ? workshopItems.map((it, idx) => (
                          <tr key={`${cardId}-workshop-${it.id || it.name || idx}`} data-testid={`operation-card-customer-item-${cardId}-${idx}`}><td className="p-2 font-bold">{it.name || it.description || '-'}</td><td className="p-2 tabular-nums">{Number(it.quantity || 1)}</td><td className="p-2 tabular-nums">{Number(it.price || 0).toLocaleString('en-US')}</td></tr>
                        )) : <tr><td colSpan={3} className="p-3 text-center text-zinc-400">لا توجد بنود عميل</td></tr>}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-[12px] font-black text-zinc-800 dark:text-zinc-100">مشتريات الموردين المرتبطة</div>
                  <div className="overflow-hidden rounded-2xl border border-amber-200 dark:border-amber-900">
                    <table className="w-full text-[11px]" data-testid={`operation-card-supplier-items-${cardId}`}>
                      <thead className="bg-amber-50 text-amber-800 dark:bg-amber-950/30 dark:text-amber-200"><tr><th className="p-2 text-right">البند</th><th className="p-2 text-right">الكمية</th><th className="p-2 text-right">التكلفة</th></tr></thead>
                      <tbody className="divide-y divide-amber-100 dark:divide-amber-900/60">
                        {supplierItems.length ? supplierItems.map((it, idx) => (
                          <tr key={`${cardId}-supplier-${it.id || it.name || idx}`} data-testid={`operation-card-supplier-item-${cardId}-${idx}`}><td className="p-2 font-bold">{it.name || it.description || '-'}</td><td className="p-2 tabular-nums">{Number(it.quantity || 1)}</td><td className="p-2 tabular-nums">{Number(it.lineTotal || 0).toLocaleString('en-US')}</td></tr>
                        )) : <tr><td colSpan={3} className="p-3 text-center text-zinc-400">لا توجد بنود موردين</td></tr>}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-2 text-[11px] font-bold text-amber-800 dark:text-amber-200" data-testid={`operation-card-supplier-section-note-${cardId}`}>الإجمالي {Number(supplierItemsTotal || 0).toLocaleString('en-US')} ر.س — لا يدخل في ذمة العميل.</div>
                </div>

                <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-950" data-testid={`operation-card-payment-history-${cardId}`}>
                  <div className="text-[12px] font-black text-zinc-800 dark:text-zinc-100">سجل التحصيل</div>
                  <div className="mt-1 flex items-center justify-between text-[12px]"><span className="font-bold text-zinc-500">{totalPaid > 0 ? 'إجمالي الدفعات المسجلة' : 'لا توجد دفعات مسجلة'}</span><strong className="tabular-nums">{totalPaid > 0 ? `${Number(totalPaid).toLocaleString('en-US')} ر.س` : '—'}</strong></div>
                </div>

                <div className="rounded-2xl border border-sky-200 bg-sky-50 px-3 py-2 text-[12px] font-bold leading-relaxed text-sky-900 dark:border-sky-900 dark:bg-sky-950/25 dark:text-sky-100" data-testid={`operation-card-journal-entry-box-${cardId}`}>
                  <strong>المعالجة المحاسبية</strong><br />{journalEntryText || 'لا تظهر كقيد مرحّل إلا بعد تأكيد المحرك المالي لعملية الترحيل.'}
                </div>

                <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-950" data-testid={`operation-card-audit-line-${cardId}`}>
                  <div className="text-[12px] font-black text-zinc-800 dark:text-zinc-100">السجل</div>
                  <div className="mt-1 flex items-center justify-between text-[12px]"><span className="font-bold text-zinc-500">آخر تحديث</span><strong>{formatDateTime(operation.updatedAt || operation.updated_at || operation.createdAt || operation.date, isRTL)}</strong></div>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <div className="relative flex items-center gap-2 border-t border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950" onClick={stop} data-testid={`operation-card-actions-${cardId}`}>
        <button
          type="button"
          className="min-h-[48px] flex-1 rounded-2xl bg-zinc-950 px-4 text-sm font-black text-white shadow-sm transition active:scale-[0.99] disabled:opacity-40 dark:bg-white dark:text-zinc-950"
          onClick={() => onConfirmCreditPayment && onConfirmCreditPayment(operation)}
          disabled={!canConfirmCreditPayment || !onConfirmCreditPayment || isSaving || isDeleting}
          data-testid={`operation-card-confirm-credit-payment-${cardId}`}
        >
          تحصيل
        </button>
        <button
          type="button"
          className="min-h-[48px] w-14 rounded-2xl border border-zinc-200 bg-zinc-50 text-lg font-black text-zinc-800 transition active:scale-[0.98] dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100"
          onClick={() => setShowMoreActions((prev) => !prev)}
          data-testid={`operation-card-more-actions-${cardId}`}
          aria-expanded={showMoreActions}
        >
          •••
        </button>
        {showMoreActions ? (
          <div className="absolute bottom-[70px] left-3 z-20 w-[210px] overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950" data-testid={`operation-card-more-menu-${cardId}`}>
            {canEditOperation ? <button type="button" className="flex min-h-[48px] w-full items-center gap-2 px-3 text-right text-[12px] font-black hover:bg-zinc-50 dark:hover:bg-zinc-900" onClick={() => { setShowMoreActions(false); if (typeof onEditInForm === 'function') onEditInForm(operation); else { setExpandedState(true); setEditing(true); } }} disabled={isSaving || isDeleting} data-testid={`operation-card-edit-${cardId}`}><Pencil size={14} /> تعديل</button> : null}
            <button type="button" className="flex min-h-[48px] w-full items-center gap-2 px-3 text-right text-[12px] font-black hover:bg-zinc-50 dark:hover:bg-zinc-900" onClick={() => { setShowMoreActions(false); onPrint(operation); }} disabled={isSaving || isDeleting} data-testid={`operation-card-print-${cardId}`}><Printer size={14} /> طباعة</button>
            {operation.vehicleId && typeof onViewVehicle === 'function' ? <button type="button" className="flex min-h-[48px] w-full items-center gap-2 px-3 text-right text-[12px] font-black hover:bg-zinc-50 dark:hover:bg-zinc-900" onClick={() => { setShowMoreActions(false); onViewVehicle(operation); }} disabled={isSaving || isDeleting} data-testid={`operation-card-view-vehicle-${cardId}`}><Car size={14} /> ملف المركبة</button> : null}
            {canDeleteOperation ? <button type="button" className="flex min-h-[48px] w-full items-center gap-2 px-3 text-right text-[12px] font-black text-rose-700 hover:bg-rose-50 dark:text-rose-300 dark:hover:bg-rose-950/30" onClick={() => { setShowMoreActions(false); onDelete(operation); }} disabled={isSaving || isDeleting} data-testid={`operation-card-delete-${cardId}`}><Trash2 size={14} /> حذف</button> : null}
          </div>
        ) : null}
      </div>

      {showIntegrityModal ? (
        <div
          className="fixed inset-0 z-[999] flex items-center justify-center bg-black/50 px-3"
          data-testid={`operation-card-integrity-modal-${cardId}`}
          onClick={(e) => { e.stopPropagation(); setShowIntegrityModal(false); }}
        >
          <div className="w-full max-w-md rounded-3xl border border-rose-200 bg-white p-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-rose-700 font-extrabold"><AlertTriangle size={18} /> تنبيهات ربط العملية</div>
                <p className="mt-1 text-xs text-slate-600">هذه التنبيهات لا تغيّر الأرقام، لكنها تساعد على مراجعة مصدر العملية.</p>
              </div>
              <button type="button" className="h-12 w-12 rounded-full bg-slate-100 text-slate-700" onClick={() => setShowIntegrityModal(false)} data-testid={`operation-card-integrity-modal-close-${cardId}`}><X size={16} /></button>
            </div>
            <div className="mt-4 space-y-2">
              {integrityWarnings.map((warning, idx) => <div key={`${cardId}-integrity-modal-${idx}`} className="rounded-2xl bg-rose-50 px-3 py-2 text-sm font-bold text-rose-800" data-testid={`operation-card-integrity-modal-warning-${cardId}-${idx}`}>{integrityLabelMap[warning] || warning}</div>)}
            </div>
            <button type="button" className="mt-4 min-h-[48px] w-full rounded-2xl bg-slate-950 text-sm font-black text-white" onClick={() => setShowIntegrityModal(false)} data-testid={`operation-card-integrity-modal-ok-${cardId}`}>حسناً</button>
          </div>
        </div>
      ) : null}
    </article>
  );
}
