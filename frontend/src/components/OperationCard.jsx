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
  if (['025', '026', '027', '028', '029', '042'].includes(code) || code.startsWith('4')) return 'إيراد';
  if (['030', '031', '035', '036', '037', '0421'].includes(code) || code.startsWith('5') || code.startsWith('6')) return 'مصروف';
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
// 🎨 New visual helpers (mobile-first ERP redesign)
// ============================================================

const cleanNotes = (notes) => {
  if (!notes) return '';
  return String(notes)
    .replace(/\[.*?\]/g, '')
    .replace(/PARTY_TYPE:\s*\S+/g, '')
    .replace(/SOURCE:\s*\S+/g, '')
    .replace(/VEHICLE_REF:\s*\S+/g, '')
    .replace(/ACCOUNT_CODE:\s*\S+/g, '')
    .replace(/ACCOUNTING_TARGET:\s*[^\n]+/g, '')
    .replace(/\s+/g, ' ')
    .trim();
};

const StatusBadge = ({ text, tone = 'slate', testid }) => {
  const tones = {
    emerald: 'bg-emerald-500/10 text-emerald-700 border-emerald-300 dark:text-emerald-300 dark:border-emerald-700',
    amber:   'bg-amber-500/10 text-amber-700 border-amber-300 dark:text-amber-300 dark:border-amber-700',
    rose:    'bg-rose-500/10 text-rose-700 border-rose-300 dark:text-rose-300 dark:border-rose-700',
    sky:     'bg-sky-500/10 text-sky-700 border-sky-300 dark:text-sky-300 dark:border-sky-700',
    indigo:  'bg-indigo-500/10 text-indigo-700 border-indigo-300 dark:text-indigo-300 dark:border-indigo-700',
    cyan:    'bg-cyan-500/10 text-cyan-700 border-cyan-300 dark:text-cyan-300 dark:border-cyan-700',
    slate:   'bg-slate-500/10 text-slate-700 border-slate-300 dark:text-slate-200 dark:border-slate-600',
  };
  return (
    <span
      data-testid={testid}
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-bold ${tones[tone] || tones.slate}`}
    >
      {text}
    </span>
  );
};

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

  return (
    <div
      className="group relative overflow-hidden rounded-3xl border bg-white dark:bg-[#111111] transition-all duration-300 hover:shadow-xl"
      style={{
        borderColor: paymentBorder,
        boxShadow: isExpanded
          ? `0 22px 60px rgba(15,23,42,0.16), 0 0 0 1px ${paymentBorder}`
          : '0 6px 20px rgba(15,23,42,0.08)',
        transition: 'all 0.28s cubic-bezier(0.4, 0, 0.2, 1)',
      }}
      data-expanded={isExpanded ? 'true' : 'false'}
      onClick={() => setExpandedState(!isExpanded)}
      dir={isRTL ? 'rtl' : 'ltr'}
      data-testid={`operation-card-${operation.id || operation.invoiceNumber || 'unknown'}`}
    >
      {/* hover glow */}
      <div className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100 bg-gradient-to-br from-cyan-500/5 to-emerald-500/5 dark:from-cyan-500/10 dark:to-emerald-500/10" />

      <div className="relative z-10 p-4 sm:p-5">
        {/* ===== HEADER: Amount + Status pills ===== */}
        <div className="flex items-start justify-between gap-3">
          {/* Amount */}
          <div className="min-w-0">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white tabular-nums" data-testid={`operation-card-total-${operation.id}`}>
              {Number(displayedWorkshopAmount).toFixed(2)}
              <span className="ms-2 text-base font-semibold text-slate-500 dark:text-zinc-500">ر.س</span>
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-600 dark:text-zinc-400">
              {isIncome ? 'إيراد الورشة' : (isPurchaseOperation ? 'مصروف الورشة' : 'حركة مالية')} • {typeLabel}
            </p>
          </div>

          {/* Status pills */}
          <div className="flex flex-wrap justify-end gap-1.5 max-w-[60%]" data-testid={`operation-card-pills-${operation.id}`}>
            {hasPaymentStatus ? (
              <StatusBadge
                text={paymentStatusLabel}
                tone={isCredit ? 'amber' : 'emerald'}
                testid={`operation-card-payment-status-pill-${operation.id}`}
              />
            ) : null}
            <StatusBadge
              text={movementLabel}
              tone={movementSide === 'debit' ? 'emerald' : movementSide === 'credit' ? 'rose' : 'slate'}
              testid={`operation-card-movement-pill-${operation.id}`}
            />
            <StatusBadge
              text={originLabel}
              tone={originLabel === 'POS' ? 'indigo' : originLabel === 'ملف المركبة' ? 'cyan' : 'slate'}
              testid={`operation-card-origin-pill-${operation.id}`}
            />
            {operation.invoiceNumber ? (
              <StatusBadge
                text={operation.invoiceNumber}
                tone="slate"
                testid={`operation-card-invoice-${operation.id}`}
              />
            ) : null}
            {integrityStatus && hasIntegrityWarning ? (
              <StatusBadge
                text={`⚠️ ${integrityWarnings.length}`}
                tone="rose"
                testid={`operation-card-integrity-pill-${operation.id}`}
              />
            ) : null}
          </div>
        </div>

        {/* ===== QUICK INFO GRID (4 cards) ===== */}
        <div className="mt-5 grid grid-cols-2 gap-2.5" data-testid={`operation-card-meta-${operation.id}`}>
          <InfoCard
            icon={<Calendar size={16} />}
            label="التاريخ"
            value={formatDateTime(operation.date || operation.op_date || operation.createdAt, isRTL)}
            accent="emerald"
            testid={`operation-card-meta-date-${operation.id}`}
          />
          <InfoCard
            icon={<Wallet size={16} />}
            label="طريقة الدفع"
            value={paymentMethodLabel}
            accent="amber"
            testid={`operation-card-meta-method-${operation.id}`}
          />
          <InfoCard
            icon={<Car size={16} />}
            label="المركبة"
            value={vehicleDisplay}
            accent="cyan"
            testid={`operation-card-meta-vehicle-${operation.id}`}
          />
          <InfoCard
            icon={<Receipt size={16} />}
            label="نوع العملية"
            value={typeLabel}
            accent="indigo"
            testid={`operation-card-meta-type-${operation.id}`}
          />
        </div>

        {/* ===== Customer / Partner ===== */}
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-white/5 dark:bg-white/[0.03]" data-testid={`operation-card-partner-block-${operation.id}`}>
          <p className="text-[10px] font-bold text-slate-500 dark:text-zinc-500 mb-1">العميل / الطرف</p>
          <h2 className="text-lg sm:text-xl font-extrabold text-slate-900 dark:text-white" data-testid={`operation-card-partner-${operation.id}`}>
            {customerDisplay}
          </h2>
        </div>

        {/* ===== Accounting Entry Badge ===== */}
        <div className="mt-3 rounded-2xl border border-cyan-200 bg-cyan-50/70 p-4 dark:border-cyan-500/20 dark:bg-cyan-500/[0.05]">
          <div className="flex items-center gap-2 mb-1">
            <Receipt size={14} className="text-cyan-600 dark:text-cyan-400" />
            <p className="text-xs font-bold text-cyan-700 dark:text-cyan-300">القيد المحاسبي</p>
          </div>
          <p className="text-xs text-slate-700 dark:text-zinc-300 leading-6 whitespace-normal break-words" data-testid={`operation-card-journal-entry-${operation.id}`}>
            {journalEntryText}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="rounded-full bg-white/70 dark:bg-white/[0.06] border border-cyan-200 dark:border-cyan-500/20 px-2.5 py-0.5 text-[10px] font-semibold text-slate-700 dark:text-zinc-200" data-testid={`operation-card-account-name-${operation.id}`}>
              {targetAccountName || 'حساب غير محدد'}{accountCode ? ` (${accountCode})` : ''}
            </span>
            <span className="rounded-full bg-white/70 dark:bg-white/[0.06] border border-cyan-200 dark:border-cyan-500/20 px-2.5 py-0.5 text-[10px] font-semibold text-slate-700 dark:text-zinc-200" data-testid={`operation-card-account-class-${operation.id}`}>
              تصنيف: {accountClassLabel}
            </span>
          </div>
        </div>

        {/* ===== Notes (clean) ===== */}
        {displayNotesClean ? (
          <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/5 dark:bg-white/[0.02]">
            <div className="flex items-center justify-between mb-1.5">
              <p className="text-[10px] font-bold text-slate-500 dark:text-zinc-500">وصف العملية</p>
              <span className="text-[10px] text-slate-500 dark:text-zinc-500">{itemsSummary !== '-' ? `${(operation.items || []).length} بند` : ''}</span>
            </div>
            <p className="text-xs leading-6 text-slate-800 dark:text-zinc-200 break-words" data-testid={`operation-card-notes-${operation.id}`}>
              {displayNotesClean}
            </p>
          </div>
        ) : null}

        {/* ===== Payment Summary (when has payment) ===== */}
        {hasPaymentStatus ? (
          <div className="mt-3 grid grid-cols-2 gap-2.5" data-testid={`operation-card-payment-summary-${operation.id}`}>
            <div className={`rounded-2xl border p-3 ${totalPaid > 0 ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-700/40 dark:bg-emerald-950/30' : 'border-slate-200 bg-slate-50 dark:border-white/5 dark:bg-white/[0.03]'}`}>
              <p className="text-[10px] text-slate-500 dark:text-zinc-500">المدفوع</p>
              <h3 className="text-lg font-extrabold text-emerald-700 dark:text-emerald-300 tabular-nums">{totalPaid.toFixed(2)}</h3>
            </div>
            <div className={`rounded-2xl border p-3 ${remainingBalance > 0 ? 'border-rose-200 bg-rose-50 dark:border-rose-700/40 dark:bg-rose-950/30' : 'border-slate-200 bg-slate-50 dark:border-white/5 dark:bg-white/[0.03]'}`}>
              <p className="text-[10px] text-slate-500 dark:text-zinc-500">المتبقي</p>
              <h3 className={`text-lg font-extrabold tabular-nums ${remainingBalance > 0 ? 'text-rose-700 dark:text-rose-300' : 'text-slate-700 dark:text-zinc-300'}`}>{remainingBalance.toFixed(2)}</h3>
            </div>
          </div>
        ) : null}

        {/* ===== Toggle details ===== */}
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-bold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:bg-white/[0.03] dark:text-zinc-200 dark:hover:bg-white/[0.06] transition-colors"
            onClick={(e) => { stop(e); setExpandedState(!isExpanded); }}
            data-testid={`operation-card-toggle-${operation.id}`}
          >
            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            <span>{t('common.details') || 'التفاصيل'}</span>
          </button>
        </div>
      </div>

      <div className="relative z-10 px-4 sm:px-5 pb-4 border-t border-slate-200 dark:border-white/5" onClick={stop}>
        {/* Primary CTA: Confirm credit payment (when applicable) */}
        {canConfirmCreditPayment && typeof onConfirmCreditPayment === 'function' ? (
          <button
            type="button"
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-500 px-4 py-3 text-sm font-bold text-white shadow-md hover:bg-emerald-600 active:scale-[0.99] transition-all"
            onClick={() => onConfirmCreditPayment(operation)}
            disabled={isSaving || isDeleting}
            data-testid={`operation-card-confirm-credit-payment-${operation.id}`}
          >
            <CheckCircle2 size={16} />
            {t('operations.confirm_credit_payment') || 'تأكيد سداد المبلغ المتبقي'}
          </button>
        ) : null}

        <div className="mt-4 flex flex-wrap items-center gap-2" data-testid={`operation-card-actions-${operation.id}`}>
          {!editing && canEditOperation ? (
            <button
              type="button"
              className="flex flex-1 min-w-[90px] items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:bg-white/[0.03] dark:text-zinc-200 dark:hover:bg-white/[0.06] transition-colors"
              onClick={() => {
                if (typeof onEditInForm === 'function') {
                  onEditInForm(operation);
                  return;
                }
                setExpandedState(true);
                setEditing(true);
              }}
              disabled={isSaving || isDeleting}
              data-testid={`operation-card-edit-${operation.id}`}
            >
              <Pencil size={12} />
              {t('common.edit') || 'تعديل'}
            </button>
          ) : editing ? (
            <>
              <button
                type="button"
                className="flex flex-1 min-w-[90px] items-center justify-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-bold text-white hover:bg-indigo-700 transition-colors disabled:opacity-50"
                onClick={async () => {
                  const ok = await onUpdateItems(operation.id, itemsDraft, editMeta);
                  if (ok) setEditing(false);
                }}
                disabled={isSaving}
                data-testid={`operation-card-save-edit-${operation.id}`}
              >
                <Save size={12} />
                {isSaving ? (t('common.loading') || '...') : (t('common.save') || 'حفظ')}
              </button>
              <button
                type="button"
                className="flex flex-1 min-w-[90px] items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:bg-white/[0.03] dark:text-zinc-200 dark:hover:bg-white/[0.06] transition-colors"
                onClick={() => {
                  setEditing(false);
                  setItemsDraft(Array.isArray(operation.items) ? operation.items.map((it) => ({ ...it })) : []);
                  setEditMeta({
                    partnerName: operation.partnerName || operation.customerName || operation.supplierName || '',
                    partnerId: operation.partnerId || operation.customerId || operation.supplierId || '',
                    accountCode: operation.accountCode || operation.account || '',
                    accountName: operation.accountName || operation.account_name || '',
                  });
                }}
                disabled={isSaving}
                data-testid={`operation-card-cancel-edit-${operation.id}`}
              >
                <X size={12} />
                {t('common.cancel') || 'إلغاء'}
              </button>
            </>
          ) : null}

          <button
            type="button"
            className="flex flex-1 min-w-[90px] items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:bg-white/[0.03] dark:text-zinc-200 dark:hover:bg-white/[0.06] transition-colors"
            onClick={() => onPrint(operation)}
            disabled={isSaving || isDeleting}
            data-testid={`operation-card-print-${operation.id}`}
          >
            <Printer size={12} />
            {t('common.print') || 'طباعة'}
          </button>

          {operation.vehicleId ? (
            <button
              type="button"
              className="flex flex-1 min-w-[90px] items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 dark:border-white/10 dark:bg-white/[0.03] dark:text-zinc-200 dark:hover:bg-white/[0.06] transition-colors"
              onClick={() => onViewVehicle(operation)}
              disabled={isSaving || isDeleting}
              data-testid={`operation-card-view-vehicle-${operation.id}`}
            >
              <Eye size={12} />
              {t('common.view') || 'عرض'}
            </button>
          ) : null}

          {canDeleteOperation ? (
            <button
              type="button"
              className="flex items-center justify-center gap-1.5 rounded-xl border border-rose-300 bg-rose-50 px-3 py-2 text-xs font-bold text-rose-700 hover:bg-rose-100 dark:border-rose-700 dark:bg-rose-950/40 dark:text-rose-300 dark:hover:bg-rose-900/60 transition-colors disabled:opacity-50 me-auto"
              onClick={() => onDelete(operation)}
              disabled={isDeleting}
              title={t('common.delete') || 'حذف'}
              data-testid={`operation-card-delete-${operation.id}`}
            >
              <Trash2 size={12} />
              {isDeleting ? (t('common.loading') || '...') : (t('common.delete') || 'حذف')}
            </button>
          ) : null}
        </div>
      </div>

      {isExpanded ? (
        <div className="px-4 pb-4" data-testid={`operation-card-expanded-${operation.id}`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 mb-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5">
              <div className="text-[10px] text-slate-600 font-bold mb-1">{t('operations.customerName') || t('operations.partner_name') || 'العميل'}</div>
              <div className="text-xs font-bold text-slate-950 break-words">{customerDisplay}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5">
              <div className="text-[10px] text-slate-600 font-bold mb-1">{t('operations.operationType') || 'نوع العملية'}</div>
              <div className="text-xs font-bold text-slate-950 break-words">{typeLabel}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5">
              <div className="text-[10px] text-slate-600 font-bold mb-1">{t('operations.operationDateLabel') || t('operations.date') || 'التاريخ'}</div>
              <div className="text-xs font-bold text-slate-950 break-words">{formatDateTime(operation.date || operation.op_date || operation.createdAt, isRTL)}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5" data-testid={`operation-card-vehicle-expanded-${operation.id}`}>
              <div className="text-[10px] text-slate-600 font-bold mb-1">المركبة</div>
              <div className="text-xs font-bold text-slate-950 break-words">{vehicleDisplay}</div>
            </div>
            {integrityStatus ? (
              <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5" data-testid={`operation-card-integrity-expanded-${operation.id}`}>
                <div className="text-[10px] text-slate-600 font-bold mb-1">كشف الربط</div>
                {!hasIntegrityWarning ? (
                  <div className="text-xs font-bold text-emerald-800">سليم • مرتبط باليومية والزيارة</div>
                ) : (
                  <div className="space-y-1">
                    {integrityWarnings.map((w, idx) => (
                      <div key={`${operation.id}-integrity-warning-${idx}`} className="text-[11px] text-rose-800 font-semibold break-words" data-testid={`operation-card-integrity-warning-${operation.id}-${idx}`}>
                        • {integrityLabelMap[w] || w}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
            <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5">
              <div className="text-[10px] text-slate-600 font-bold mb-1">{t('operations.paymentMethod') || 'طريقة الدفع'}</div>
              <div className="text-xs font-bold text-slate-950 break-words">{paymentMethodLabel}</div>
            </div>
            {hasPaymentStatus ? (
              <>
                <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5" data-testid={`operation-card-payment-status-expanded-${operation.id}`}>
                  <div className="text-[10px] text-slate-600 font-bold mb-1">حالة السداد</div>
                  <div className="text-xs font-bold text-slate-950 break-words">{paymentStatusLabel}</div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5" data-testid={`operation-card-total-paid-expanded-${operation.id}`}>
                  <div className="text-[10px] text-slate-600 font-bold mb-1">المدفوع</div>
                  <div className="text-xs font-bold text-slate-950 break-words tabular-nums">{totalPaid.toFixed(2)}</div>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5" data-testid={`operation-card-balance-expanded-${operation.id}`}>
                  <div className="text-[10px] text-slate-600 font-bold mb-1">المتبقي</div>
                  <div className="text-xs font-bold text-slate-950 break-words tabular-nums">{remainingBalance.toFixed(2)}</div>
                </div>
              </>
            ) : null}
            <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5">
              <div className="text-[10px] text-slate-600 font-bold mb-1">{t('operations.account') || 'الحساب'}</div>
              <div className="text-xs font-bold text-slate-950 break-words">
                {targetAccountName}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5" data-testid={`operation-card-account-class-expanded-${operation.id}`}>
              <div className="text-[10px] text-slate-600 font-bold mb-1">التصنيف المحاسبي</div>
              <div className="text-xs font-bold text-slate-950 break-words">{accountClassLabel} {accountCode ? `(${accountCode})` : ''}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5">
              <div className="text-[10px] text-slate-600 font-bold mb-1">إيراد الورشة</div>
              <div className="text-xs font-extrabold text-slate-950 tabular-nums">{Number(displayedWorkshopAmount).toFixed(2)} {t('common.currency') || ''}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50/90 px-3 py-2.5" data-testid={`operation-card-supplier-total-${operation.id}`}>
              <div className="text-[10px] text-slate-600 font-bold mb-1">إجمالي بنود الموردين</div>
              <div className="text-xs font-extrabold text-slate-950 tabular-nums">{Number(supplierItemsTotal).toFixed(2)} {t('common.currency') || ''}</div>
            </div>
          </div>

          {editing ? (
            <div className="mb-3 bg-sky-50 rounded-xl border border-sky-200 p-3 space-y-3" data-testid={`operation-card-edit-meta-${operation.id}`}>
              <div className="text-xs font-bold text-sky-950">تعديل العميل/المورد والحساب</div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                <div>
                  <label className="text-[10px] text-slate-700 font-bold block mb-1">{isPurchaseOperation ? 'المورد' : 'العميل'}</label>
                  <input
                    list={`operation-card-party-list-${operation.id}`}
                    className="apple-input h-9 text-xs"
                    value={editMeta.partnerName || ''}
                    onChange={(e) => {
                      const nextName = e.target.value;
                      const matched = (partyOptions || []).find((p) => (p?.name || '') === nextName);
                      setEditMeta((prev) => ({
                        ...prev,
                        partnerName: nextName,
                        partnerId: matched?.id || '',
                      }));
                    }}
                    placeholder={isPurchaseOperation ? 'اختر أو اكتب اسم المورد' : 'اختر أو اكتب اسم العميل'}
                    data-testid={`operation-card-edit-partner-${operation.id}`}
                  />
                  <datalist id={`operation-card-party-list-${operation.id}`}>
                    {(partyOptions || []).map((p) => (
                      <option key={p.id || p.name} value={p.name} />
                    ))}
                  </datalist>
                </div>

                <div>
                  <label className="text-[10px] text-slate-700 font-bold block mb-1">الحساب</label>
                  <select
                    className="apple-input h-9 text-xs"
                    value={editMeta.accountCode || ''}
                    onChange={(e) => {
                      const code = e.target.value;
                      const selected = (accounts || []).find((acc) => String(acc.code || acc.id || '') === code);
                      setEditMeta((prev) => ({
                        ...prev,
                        accountCode: code,
                        accountName: selected?.name || prev.accountName || '',
                      }));
                    }}
                    data-testid={`operation-card-edit-account-${operation.id}`}
                  >
                    <option value="">اختر الحساب</option>
                    {(accounts || []).map((acc) => {
                      const code = String(acc.code || acc.id || '');
                      return (
                        <option key={`acc-${code}`} value={code}>
                          {code} - {acc.name || acc.account_name || code}
                        </option>
                      );
                    })}
                  </select>
                </div>
              </div>
            </div>
          ) : null}

          <div className="mb-3 bg-blue-50 rounded-xl px-3 py-2.5 border border-blue-200" data-testid={`operation-card-journal-entry-box-${operation.id}`}>
            <div className="text-[10px] text-blue-900 font-bold mb-1 flex items-center gap-1">
              <Landmark size={12} />
              <span>القيد المحاسبي</span>
            </div>
            <div className="text-xs text-slate-950 font-semibold whitespace-pre-wrap leading-relaxed">{journalEntryText}</div>
          </div>

          {operation.scope === 'vehicle' && operation.vehicleId ? (
            <div className="mb-3 bg-sky-50 rounded-xl px-3 py-2.5 border border-sky-200" data-testid={`operation-card-vehicle-details-${operation.id}`}>
              <div className="text-[10px] text-sky-900 font-bold mb-1">تفاصيل المركبة المرتبطة</div>
              <div className="text-xs text-slate-950 font-semibold leading-relaxed whitespace-pre-wrap">
                {vehicle
                  ? `اللوحة: ${vehicle.plateNumber || vehicle.plate_number || operation.vehiclePlate || '-'} • ${vehicle.brand || operation.vehicleBrand || '-'} ${vehicle.model || operation.vehicleModel || ''} • العميل: ${vehicle.customerName || vehicle.ownerName || operation.customerName || '-'} • رقم الزيارة: ${formatVisitNumber(visitDisplay, visitDisplay)}`
                  : `${vehicleDisplay} • رقم الزيارة: ${formatVisitNumber(visitDisplay, visitDisplay)}`}
              </div>
            </div>
          ) : null}

          {operation.notes ? (
            <div className="mb-3 bg-slate-50 rounded-xl px-3 py-2.5 border border-slate-200">
              <div className="text-[10px] text-slate-600 font-bold mb-1">{t('common.notes') || 'ملاحظات'}</div>
              <div className="text-xs text-slate-950 font-semibold whitespace-pre-wrap leading-relaxed">{operationNotesDisplay}</div>
              {paymentReceiptUrl ? (
                <a
                  href={paymentReceiptUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-flex items-center gap-1 rounded-lg border border-emerald-400/40 bg-emerald-500/15 px-2 py-1 text-[11px] text-emerald-200"
                  data-testid={`operation-card-payment-receipt-link-${operation.id}`}
                >
                  <Link2 size={12} /> عرض إيصال السداد
                </a>
              ) : null}
            </div>
          ) : null}

          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="px-3 py-2.5 flex items-center justify-between border-b border-slate-200 bg-slate-50">
              <div className="text-xs font-bold text-slate-950">{t('operations.items') || 'البنود'}</div>
              <div className="text-[10px] text-slate-700 font-bold tabular-nums">
                إيراد الورشة: {Number(displayedWorkshopAmount).toFixed(2)} {t('common.currency') || ''}
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-[10px] text-slate-700 bg-slate-50">
                  <tr>
                    <th className="p-2 text-right font-bold">{t('vehicle.itemName') || t('operations.itemName') || 'البند'}</th>
                    <th className="p-2 text-right font-bold w-[95px]">{t('operations.qty') || t('vehicle.quantity') || 'الكمية'}</th>
                    <th className="p-2 text-right font-bold w-[105px]">{t('common.price') || t('operations.price') || 'السعر'}</th>
                    <th className="p-2 text-right font-bold w-[110px]">{t('common.total') || 'الإجمالي'}</th>
                    {editing ? <th className="p-2 w-[60px]" /> : null}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {(itemsView || []).map((it, idx) => {
                    const lineTotal = Number(it.quantity || 1) * Number(it.price || 0);
                    return (
                      <tr key={`${operation.id}-item-${idx}`}>
                        <td className="p-2">
                          {editing ? (
                            <input
                              className="apple-input h-8 text-xs"
                              value={it.name || ''}
                              onChange={(e) => {
                                const v = e.target.value;
                                setItemsDraft((prev) => prev.map((x, i) => (i === idx ? { ...x, name: v } : x)));
                              }}
                            />
                          ) : (
                            <div className="text-slate-950 font-semibold break-words">{it.name || it.description || '-'}</div>
                          )}
                        </td>
                        <td className="p-2">
                          {editing ? (
                            <input
                              type="number"
                              className="apple-input h-8 text-xs"
                              value={Number(it.quantity || 1)}
                              onChange={(e) => {
                                const v = Number(e.target.value) || 0;
                                setItemsDraft((prev) => prev.map((x, i) => (i === idx ? { ...x, quantity: v } : x)));
                              }}
                            />
                          ) : (
                            <div className="text-slate-900 font-semibold tabular-nums">{Number(it.quantity || 1)}</div>
                          )}
                        </td>
                        <td className="p-2">
                          {editing ? (
                            <input
                              type="number"
                              className="apple-input h-8 text-xs"
                              value={Number(it.price || 0)}
                              onChange={(e) => {
                                const v = Number(e.target.value) || 0;
                                setItemsDraft((prev) => prev.map((x, i) => (i === idx ? { ...x, price: v } : x)));
                              }}
                            />
                          ) : (
                            <div className="text-slate-900 font-semibold tabular-nums">{Number(it.price || 0).toFixed(2)}</div>
                          )}
                        </td>
                        <td className="p-2">
                          <div className="text-slate-950 tabular-nums font-bold">{Number(lineTotal).toFixed(2)}</div>
                        </td>
                        {editing ? (
                          <td className="p-2">
                            <button
                              type="button"
                              className="text-rose-200 hover:text-rose-100"
                              onClick={() => setItemsDraft((prev) => prev.filter((_, i) => i !== idx))}
                              title={t('common.delete') || 'حذف'}
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}

                  {(itemsView || []).length === 0 ? (
                    <tr>
                      <td colSpan={editing ? 5 : 4} className="p-3 text-center text-slate-600 font-semibold text-xs">
                        {t('operations.noItems') || t('operations.no_items') || '-'}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>

            {editing ? (
              <div className="px-3 py-2 border-t border-slate-200 flex justify-end">
                <button
                  type="button"
                  className="apple-button-secondary h-8 px-2.5 text-[11px]"
                  onClick={() => setItemsDraft((prev) => ([...prev, { name: '', quantity: 1, price: 0 }]))}
                  disabled={isSaving}
                >
                  {t('common.add') || 'إضافة'}
                </button>
              </div>
            ) : null}
          </div>

          <div className="mt-3 bg-amber-50 rounded-xl border border-amber-200 overflow-hidden" data-testid={`operation-card-supplier-items-${operation.id}`}>
            <div className="px-3 py-2.5 flex items-center justify-between border-b border-amber-200">
              <div className="text-xs font-bold text-amber-950">بنود الموردين (الاسم + السعر)</div>
              <div className="text-[10px] text-amber-900 font-bold tabular-nums">
                الإجمالي: {Number(supplierItemsTotal).toFixed(2)} {t('common.currency') || ''}
              </div>
            </div>

            <div className="px-3 py-2.5 space-y-2">
              {supplierItems.length === 0 ? (
                <div className="text-xs text-slate-700 font-semibold" data-testid={`operation-card-supplier-items-empty-${operation.id}`}>
                  لا توجد بنود موردين في هذه العملية.
                </div>
              ) : (
                supplierItems.map((item, idx) => (
                  <div key={`${operation.id}-supplier-item-${idx}`} className="flex items-center justify-between gap-2 text-xs" data-testid={`operation-card-supplier-item-${operation.id}-${idx}`}>
                    <div className="text-slate-950 font-semibold break-words">
                      {item.name || item.description || '-'}
                    </div>
                    <div className="text-amber-950 font-bold tabular-nums whitespace-nowrap">
                      {Number(item.price || 0).toFixed(2)} × {Number(item.quantity || 1)} = {Number(item.lineTotal || 0).toFixed(2)} {t('common.currency') || ''}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
