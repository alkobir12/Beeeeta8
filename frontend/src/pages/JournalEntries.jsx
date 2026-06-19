import React, { useState, useEffect, useMemo } from 'react';
import { resolveBackendBase } from '../utils/backendBase';
import SmartAccountSelect from '../components/SmartAccountSelect';
import SmartPOSJournal from './SmartPOSJournal';
import axios from 'axios';
import { hasPermission } from '../utils/permissions';
import {
  BookOpen,
  Plus,
  Search,
  RefreshCw,
  CheckCircle,
  Clock,
  XCircle,
  Eye,
  FileText,
  ArrowLeftRight,
  Printer,
  Calendar,
  User,
  Receipt,
  ShoppingCart,
  Briefcase,
  CreditCard,
  DollarSign,
  Wrench,
  Pencil,
  Trash2,
  Save,
  X,
} from 'lucide-react';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);
const WORKSHOP_ID = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';

const formatCurrency = (amount) => {
  return new Intl.NumberFormat('ar-SA', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount || 0) + ' ر.س';
};

const formatDate = (date) => {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('ar-SA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};

const getEntryTypeConfig = (type) => {
  const configs = {
    invoice: { icon: Receipt, bgColor: 'bg-blue-500/15', textColor: 'text-blue-200', label: 'فاتورة' },
    payment: { icon: CreditCard, bgColor: 'bg-emerald-500/15', textColor: 'text-emerald-200', label: 'محصلة' },
    purchase: { icon: ShoppingCart, bgColor: 'bg-purple-500/15', textColor: 'text-purple-200', label: 'مشتريات' },
    salary: { icon: Briefcase, bgColor: 'bg-orange-500/15', textColor: 'text-orange-200', label: 'رواتب' },
    manual: { icon: FileText, bgColor: 'bg-slate-500/15', textColor: 'text-slate-200', label: 'يدوي' },
  };
  return configs[type] || configs.manual;
};

const getPaymentMethodTone = (method) => {
  const normalized = String(method || '').toLowerCase();
  if (normalized === 'cash') return 'bg-emerald-500/15 text-emerald-200';
  if (normalized === 'bank') return 'bg-sky-500/15 text-sky-200';
  if (normalized === 'pos') return 'bg-violet-500/15 text-violet-200';
  if (normalized === 'credit') return 'bg-amber-500/15 text-amber-200';
  return 'bg-white/10 text-slate-200';
};

const getPaymentStatusTone = (status) => {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'paid_full' || normalized === 'paid') return 'bg-emerald-500/15 text-emerald-200';
  if (normalized === 'partial') return 'bg-amber-500/15 text-amber-200';
  if (normalized === 'unpaid' || normalized === 'credit' || normalized === 'pending') return 'bg-rose-500/15 text-rose-200';
  return 'bg-white/10 text-slate-200';
};

const getSourceLabel = (source = '') => {
  const normalized = String(source || '').toLowerCase();
  if (normalized === 'operation') return 'عملية';
  if (normalized === 'visit_receipt_voucher') return 'سند قبض';
  if (normalized === 'pos_template' || normalized === 'pos_instant_sale') return 'POS';
  if (normalized === 'period_close') return 'إقفال';
  if (normalized === 'manual') return 'يدوي';
  return normalized ? normalized : 'غير محدد';
};

const getAuditHeaders = () => {
  try {
    const session = JSON.parse(localStorage.getItem('session') || '{}');
    return {
      'Content-Type': 'application/json',
      'x-user-role': String(session?.role || '').toLowerCase(),
      'x-user-id': String(session?.id || session?.userId || session?.name || 'manager').trim() || 'manager',
    };
  } catch {
    return {
      'Content-Type': 'application/json',
      'x-user-role': '',
      'x-user-id': 'manager',
    };
  }
};

const sanitizeEntryText = (value = '') => {
  if (!value) return '';
  return String(value)
    .replace(/\[[A-Z_]+\s*:[^\]]*\]/g, '')   // إزالة الوسوم الخام [PARTY:..] [VEHICLE_REF:..] [VISIT:..] [PARTY_TYPE:..]
    .replace(/ACCOUNT_CODE:\s*\S+/gi, '')
    .replace(/ACCOUNTING_TARGET:\s*\S+/gi, '')
    .replace(/ACCOUNTING_SOURCE:\s*\S+/gi, '')
    .replace(/ACCOUNT_NAME:\s*[^|\n]+/gi, '')
    .replace(/ACCOUNT_CLASS:\s*\S+/gi, '')
    .replace(/\s*[—–-]\s*$/g, '')            // فاصلة شرطة زائدة في النهاية
    .replace(/\s{2,}/g, ' ')
    .trim();
};

// تنظيف الوصف من التكرار: إزالة اسم الطرف/لوحة المركبة من نص الوصف لأنها تُعرض في حقول مستقلة
const cleanDescription = (rawDesc = '', partyLabel = '', vehicleLabel = '') => {
  const base = sanitizeEntryText(rawDesc);
  if (!base) return '';
  const norm = (s) => String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const skip = new Set([norm(partyLabel), norm(vehicleLabel)].filter((s) => s && s !== 'مفتوح'));
  const segments = base.split(/\s*[—–]\s*|\s+-\s+/).map((s) => s.trim()).filter(Boolean);
  const kept = segments.filter((s) => !skip.has(norm(s)));
  const result = (kept.length ? kept : segments).join(' — ');
  return result || base;
};

const extractTagValue = (text = '', tag = '') => {
  if (!tag) return '';
  const rx = new RegExp(`\\[${tag}:([^\\]]+)\\]`, 'i');
  const hit = String(text || '').match(rx);
  return String(hit?.[1] || '').trim();
};

const resolveCurrentAccountCode = (rawCode = '', accountName = '', coaAccounts = []) => {
  const code = String(rawCode || '').trim();
  if (!code) return '';
  const hasAccounts = Array.isArray(coaAccounts) && coaAccounts.length > 0;

  const byName = (needle) => {
    const hit = (coaAccounts || []).find((a) => String(a?.name_ar || a?.name || '').includes(needle));
    return hit?.code || '';
  };

  const cashCode = byName('النقد');
  const bankCode = byName('البنك');
  const arCode = byName('العملاء');
  const apCode = byName('المورد');
  const posCode = byName('نقاط بيع');
  const revenueCode = byName('الإيراد') || byName('ايراد');
  const expenseCode = byName('المصروف');

  // خريطة الأكواد القديمة → الجديدة
  const LEGACY_MAP = {
    '1101': '003', '1102': '004', '1103': '005', '1104': '006',
    '4000': '025', '4100': '026', '5000': '030', '5100': '031',
    '6000': '035', '6100': '036', '6101': '037', '3102': '022',
  };
  // تحويل الكود القديم إلى الجديد إذا كان موجوداً
  const newCode = LEGACY_MAP[code] || code;
  if (newCode !== code) return newCode;

  return code;
};

const ensureArray = (value) => (Array.isArray(value) ? value : []);
const ensureObject = (value) => (value && typeof value === 'object' ? value : null);

// Chart of Accounts (loaded from API)

export default function JournalEntries() {
  const themeName = 'dark';
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [editingEntry, setEditingEntry] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [partyEditorEntry, setPartyEditorEntry] = useState(null);
  const [partyEditorLabel, setPartyEditorLabel] = useState('');
  const [partyEditorType, setPartyEditorType] = useState('open');
  const [partyEditorSaving, setPartyEditorSaving] = useState(false);
  const [resetKeepDebtsLoading, setResetKeepDebtsLoading] = useState(false);
  const [coaAccounts, setCoaAccounts] = useState([]);
  const [viewMode, setViewMode] = useState(() => {
    try { return localStorage.getItem('journal.viewMode') || 'pos'; } catch (e) { return 'pos'; }
  });
  const [workshopProfile, setWorkshopProfile] = useState(null);
  const [workshopSettings, setWorkshopSettings] = useState(null);
  const session = useMemo(() => {
    try { return JSON.parse(localStorage.getItem('session') || '{}'); } catch (e) { return {}; }
  }, []);
  const canCreateJournal = hasPermission(session, 'journal_entries', 'create');
  const canEditJournal = hasPermission(session, 'journal_entries', 'edit');
  const canDeleteJournal = hasPermission(session, 'journal_entries', 'delete');
  const canUsePosJournal = hasPermission(session, 'journal_entries', 'pos');
  
  const isLight = false;

  useEffect(() => {
    if (!canUsePosJournal && viewMode === 'pos') {
      setViewMode('full');
      try { localStorage.setItem('journal.viewMode', 'full'); } catch (e) {}
    }
  }, [canUsePosJournal, viewMode]);

  useEffect(() => {
    const journalController = new AbortController();
    const profileController = new AbortController();
    const settingsController = new AbortController();

    fetchJournalEntries(journalController.signal);
    fetchWorkshopProfile(profileController.signal);
    fetchWorkshopSettings(settingsController.signal);

    return () => {
      journalController.abort();
      profileController.abort();
      settingsController.abort();
    };
  }, []);

  useEffect(() => {
    const accountsController = new AbortController();
    fetchChartOfAccounts(accountsController.signal);

    return () => {
      accountsController.abort();
    };
  }, []);

  // 🔄 إعادة التحميل عند أي عملية مالية (سداد / POS / تسوية مورد / خصم)
  useEffect(() => {
    const onFinUpdated = () => {
      try { fetchJournalEntries(); } catch (e) { console.warn('finance refresh err', e); }
    };
    window.addEventListener('finance:updated', onFinUpdated);
    return () => window.removeEventListener('finance:updated', onFinUpdated);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (coaAccounts.length > 0) {
      fetchJournalEntries();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coaAccounts.length]);

  const isAbortLikeError = (error, signal) => {
    if (signal?.aborted) return true;
    const message = String(error?.message || '').toLowerCase();
    return error?.name === 'AbortError' || message.includes('aborted');
  };

  const fetchJournalEntries = async (signal = undefined) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/finance/journal-entries?workshop_id=${WORKSHOP_ID}&limit=50`, { signal });
      const data = await response.json();

      if (data?.success) {
        const rawEntries = ensureArray(data?.data)
          .map((entry) => ensureObject(entry))
          .filter(Boolean);

        const transformedEntries = rawEntries.map((entry, index) => {
          const rawLines = ensureArray(entry?.lines)
            .map((line) => ensureObject(line))
            .filter(Boolean);

          return {
          id: entry?.id || String(index),
          entry_number: `JE-${String(index + 1).padStart(4, '0')}`,
          date: entry?.date,
          total: Number(entry?.total || 0),
          entry_date: entry?.date,
          description: sanitizeEntryText(entry?.description || ''),
          reference_type: entry?.source === 'operation'
            ? (entry?.transaction_type === 'sale' || entry?.transaction_type === 'service' ? 'invoice' : 'purchase')
            : 'manual',
          status: 'posted',
          total_debit: Number(entry?.total || 0),
          total_credit: Number(entry?.total || 0),
          lines: rawLines.map((line) => ({
            account: resolveCurrentAccountCode(line?.account, line?.account_name, coaAccounts),
            code: resolveCurrentAccountCode(line?.account || line?.code, line?.account_name || line?.name, coaAccounts),
            account_code: resolveCurrentAccountCode(line?.account, line?.account_name, coaAccounts),
            account_name: line?.account_name || line?.name || '',
            name: line?.account_name || line?.name || '',
            debit: Number(line?.debit || 0),
            credit: Number(line?.credit || 0)
          })),
          vehicle_plate: entry?.vehicle_label || entry?.vehicle_plate,
          vehicle_label: entry?.vehicle_label || entry?.vehicle_plate,
          customer_name: entry?.party_label || entry?.customer_name,
          party_label: entry?.party_label || 'مفتوح',
          party_type: entry?.party_type || 'open',
          operation_type_label: entry?.operation_type_label || 'غير محدد',
          payment_method: entry?.payment_method || '',
          payment_method_label_ar: entry?.payment_method_label_ar || '',
          payment_status: entry?.payment_status || '',
          payment_status_label_ar: entry?.payment_status_label_ar || '',
          transaction_type: entry?.transaction_type || '',
          source: entry?.source || 'manual'
        };
      });
        setEntries(transformedEntries);
      } else {
        setEntries([]);
      }
    } catch (error) {
      if (isAbortLikeError(error, signal)) return;
      console.error('Error fetching journal entries:', error);
      setEntries([]);
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  };

  const fetchWorkshopProfile = async (signal = undefined) => {
    try {
      const response = await fetch(`${API_URL}/profile`, { signal });
      const data = await response.json();
      const normalizedProfile = (data?.success && data?.data)
        ? data.data
        : (data?.data || data || null);

      if (normalizedProfile && typeof normalizedProfile === 'object') {
        setWorkshopProfile(normalizedProfile);
      }
    } catch (error) {
      if (isAbortLikeError(error, signal)) return;
      console.error('Error fetching workshop profile:', error);
    }
  };

  const fetchWorkshopSettings = async (signal = undefined) => {
    try {
      const response = await fetch(`${API_URL}/settings`, { signal });
      const data = await response.json();
      if (data) {
        setWorkshopSettings(data);
      }
    } catch (error) {
      if (isAbortLikeError(error, signal)) return;
      console.error('Error fetching workshop settings:', error);
    }
  };

  const fetchChartOfAccounts = async (signal = undefined) => {
    try {
      const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';
      const response = await fetch(`${API_URL}/finance/chart-of-accounts?workshop_id=${workshopId}`, { signal });
      const data = await response.json();
      if (data?.success && Array.isArray(data?.data)) {
        setCoaAccounts(data.data);
      } else {
        const fallback = await fetch(`${API_URL}/accounts?workshop_id=${workshopId}`, { signal });
        const fallbackData = await fallback.json();
        const normalized = Array.isArray(fallbackData)
          ? fallbackData
          : (Array.isArray(fallbackData?.data) ? fallbackData.data : []);
        setCoaAccounts(normalized);
      }
    } catch (e) {
      if (isAbortLikeError(e, signal)) return;
      console.error('Failed to fetch chart of accounts:', e);
      try {
        const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';
        const fallback = await fetch(`${API_URL}/accounts?workshop_id=${workshopId}`, { signal });
        const fallbackData = await fallback.json();
        const normalized = Array.isArray(fallbackData)
          ? fallbackData
          : (Array.isArray(fallbackData?.data) ? fallbackData.data : []);
        setCoaAccounts(normalized);
      } catch (fallbackError) {
        if (isAbortLikeError(fallbackError, signal)) return;
        setCoaAccounts([]);
      }
    }
  };

  const handleCreateEntry = async (formData) => {
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/finance/journal-entries?workshop_id=${WORKSHOP_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: formData.date,
          description: formData.description,
          transaction_type: formData.transaction_type,
          lines: formData.lines,
          total: formData.lines.reduce((sum, l) => sum + (l.debit || 0), 0)
        })
      });

      const data = await response.json();
      if (data.success) {
        await fetchJournalEntries();
        setShowEntryForm(false);
        setEditingEntry(null);
      } else {
        alert(data.message || 'حدث خطأ في إنشاء القيد');
      }
    } catch (error) {
      console.error('Error creating entry:', error);
      alert('حدث خطأ في إنشاء القيد');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateEntry = async (formData) => {
    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/finance/journal-entries/${editingEntry.id}?workshop_id=${WORKSHOP_ID}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: formData.date,
          description: formData.description,
          transaction_type: formData.transaction_type,
          lines: formData.lines,
          total: formData.lines.reduce((sum, l) => sum + (l.debit || 0), 0)
        })
      });
      const data = await response.json();
      if (data.success) {
        await fetchJournalEntries();
        setShowEntryForm(false);
        setEditingEntry(null);
      } else {
        alert(data.message || 'حدث خطأ في تحديث القيد');
      }
    } catch (error) {
      console.error('Error updating entry:', error);
      alert('حدث خطأ في تحديث القيد');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteEntry = async (entryId) => {
    try {
      const response = await fetch(`${API_URL}/finance/journal-entries/${entryId}?workshop_id=${WORKSHOP_ID}`, {
        method: 'DELETE'
      });
      const data = await response.json();
      if (data.success) {
        await fetchJournalEntries();
        setDeleteConfirm(null);
      } else {
        alert(data.message || 'حدث خطأ في حذف القيد');
      }
    } catch (error) {
      console.error('Error deleting entry:', error);
      alert('حدث خطأ في حذف القيد');
    }
  };

  const handleResetToDebtsOnly = async () => {
    const firstConfirm = window.confirm(
      '⚠️ تحذير: سيتم حذف كل القيود اليومية وكل العمليات غير المرتبطة بالذمم.\n\nسيتم الإبقاء فقط على عمليات الذمم (الآجل/أوامر السداد).\n\nهل تريد المتابعة؟'
    );
    if (!firstConfirm) return;

    const finalConfirm = window.prompt('اكتب "ذمم فقط" للتأكيد النهائي:', '');
    if (finalConfirm !== 'ذمم فقط') {
      alert('تم إلغاء العملية');
      return;
    }

    try {
      setResetKeepDebtsLoading(true);
      const response = await fetch(
        `${API_URL}/cleanup/keep-debts-only?confirm=KEEP_DEBTS_ONLY`,
        { method: 'DELETE', headers: getAuditHeaders() }
      );
      const data = await response.json();

      if (!data?.success) {
        alert(data?.message || 'تعذر تنفيذ التنظيف');
        return;
      }

      const payload = data?.data || {};
      alert(
        '✅ تم تنفيذ الحذف بنجاح\n\n' +
        `• العمليات المحذوفة: ${payload.operations_deleted || 0}\n` +
        `• عمليات الذمم المتبقية: ${payload.operations_kept || 0}\n` +
        `• القيود المحذوفة: ${payload.journal_entries_deleted || 0}`
      );

      await fetchJournalEntries();
    } catch (error) {
      console.error('Error resetting financial data to debts-only:', error);
      alert('حدث خطأ أثناء تنفيذ العملية');
    } finally {
      setResetKeepDebtsLoading(false);
    }
  };

  const handleQuickEditParty = (entry) => {
    setPartyEditorEntry(entry);
    setPartyEditorLabel(entry?.party_label || 'مفتوح');
    setPartyEditorType(entry?.party_type || 'open');
  };

  const submitPartyEditor = async () => {
    if (!partyEditorEntry) return;
    const trimmed = partyEditorLabel.trim();
    if (!trimmed) {
      alert('يرجى إدخال طرف العملية');
      return;
    }

    setPartyEditorSaving(true);
    const cleanDescription = String(partyEditorEntry.description || '')
      .replace(/\[PARTY:[^\]]+\]/g, '')
      .replace(/\[PARTY_TYPE:[^\]]+\]/g, '')
      .trim();
    const nextDescription = `${cleanDescription} [PARTY:${trimmed}] [PARTY_TYPE:${partyEditorType}]`.trim();

    try {
      const response = await fetch(`${API_URL}/finance/journal-entries/${partyEditorEntry.id}?workshop_id=${WORKSHOP_ID}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: partyEditorEntry.entry_date,
          description: nextDescription,
          transaction_type: partyEditorEntry.transaction_type || 'manual',
          lines: partyEditorEntry.lines?.map((l) => ({
            account: l.account_code || l.account,
            account_name: l.account_name,
            debit: l.debit || 0,
            credit: l.credit || 0,
          })) || [],
          total: partyEditorEntry.total_debit || 0,
        }),
      });

      const data = await response.json();
      if (!data?.success) throw new Error(data?.message || 'تعذر التحديث');
      setPartyEditorEntry(null);
      await fetchJournalEntries();
    } catch (error) {
      console.error('Error updating party label:', error);
      alert('تعذر تحديث طرف العملية');
    } finally {
      setPartyEditorSaving(false);
    }
  };

  const filteredEntries = ensureArray(entries).filter((entry) => {
    const safeEntry = ensureObject(entry);
    if (!safeEntry) return false;
    if (statusFilter !== 'all' && entry.status !== statusFilter) return false;
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    const safeDescription = sanitizeEntryText(entry.description || '');
    return (
      entry.entry_number?.toLowerCase().includes(query) ||
      safeDescription.toLowerCase().includes(query) ||
      entry.operation_type_label?.toLowerCase().includes(query) ||
      entry.party_label?.toLowerCase().includes(query) ||
      entry.customer_name?.toLowerCase().includes(query) ||
      entry.vehicle_plate?.toLowerCase().includes(query)
    );
  });

  const getEntryLinkage = (entry) => {
    const hasReference = Boolean(entry?.reference_id || entry?.referenceId);
    const hasVehicle = Boolean(entry?.vehicle_plate || extractTagValue(entry?.description || '', 'VEHICLE_REF'));
    const party = String(entry?.party_label || '').trim();
    const hasParty = Boolean(party && party !== 'مفتوح');
    const linked = hasReference || hasVehicle || hasParty;
    return {
      linked,
      label: linked ? 'مترابط' : 'مفتوح',
      hint: linked ? 'مرتبط بعملية/طرف/مركبة' : 'غير مرتبط بمرجع واضح',
    };
  };

  const safeEntries = ensureArray(entries).filter((entry) => ensureObject(entry));

  const stats = {
    total: safeEntries.length,
    posted: safeEntries.filter(e => e.status === 'posted').length,
    draft: safeEntries.filter(e => e.status === 'draft').length,
    totalAmount: safeEntries.reduce((sum, e) => sum + (Number(e.total_debit) || 0), 0),
    manual: safeEntries.filter(e => e.source === 'manual').length,
  };

  const handlePrintInvoice = (entry) => {
    const printWindow = window.open('', '_blank', 'width=800,height=1000');
    if (!printWindow) return;
    const safeEntry = ensureObject(entry) || {};
    const safeLines = ensureArray(safeEntry.lines)
      .map((line) => ensureObject(line))
      .filter(Boolean);
    const total = Number(safeEntry.total_debit || 0);
    // 🎯 الأولوية: Profile (المستخدم يضبطه يدوياً) > Settings (افتراضي قديم)
    const workshopName = workshopProfile?.business_name || workshopProfile?.name || workshopSettings?.workshopName || 'ورشة الصيانة';
    const workshopPhone = workshopProfile?.phone || workshopProfile?.phone_number || workshopSettings?.workshopPhone || '';
    const workshopAddress = workshopProfile?.address || workshopSettings?.workshopAddress || '';
    const workshopTax = workshopProfile?.taxNumber || workshopProfile?.tax_number || workshopSettings?.taxNumber || '';
    const workshopCR = workshopProfile?.commercialRegister || workshopProfile?.commercial_register || workshopSettings?.commercialRegister || '';
    // الشعار (base64 أو URL)
    const workshopLogo = workshopProfile?.logo || workshopProfile?.logo_url || workshopProfile?.logoUrl || workshopSettings?.logoUrl || '';
    const logoHtml = workshopLogo
      ? `<img src="${workshopLogo}" alt="logo" style="max-height:56px;max-width:120px;object-fit:contain;margin-left:12px;border-radius:6px;background:#fff;padding:4px;" />`
      : '';
    printWindow.document.write(`<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <title>فاتورة - ${safeEntry.entry_number || '-'}</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; padding: 24px; background: #f5f5f5; color: #111827; }
    .container { max-width: 800px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 24px 28px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #3b82f6; padding-bottom: 16px; margin-bottom: 24px; }
    .title { font-size: 22px; font-weight: 700; color: #1e40af; }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; }
    th { background: #1e40af; color: white; padding: 12px; text-align: right; }
    td { padding: 12px; border-bottom: 1px solid #e5e7eb; }
    .totals { margin-top: 24px; padding: 16px; background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); border-radius: 8px; color: white; }
    .totals-row { display: flex; justify-content: space-between; padding: 8px 0; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div style="display:flex;align-items:center;gap:12px;">
        ${logoHtml}
        <div class="title">${workshopName}</div>
      </div>
      <div>فاتورة: ${safeEntry.entry_number || '-'}<br/>التاريخ: ${safeEntry.entry_date || '-'}</div>
    </div>
    <p><strong>العنوان:</strong> ${workshopAddress || '-'} | <strong>الهاتف:</strong> ${workshopPhone || '-'}</p>
    <p><strong>السجل التجاري:</strong> ${workshopCR || '-'} | <strong>الرقم الضريبي:</strong> ${workshopTax || '-'}</p>
    <p><strong>العميل:</strong> ${sanitizeEntryText(safeEntry.customer_name || '-') || '-'} | <strong>اللوحة:</strong> ${safeEntry.vehicle_plate || '-'}</p>
    <table>
      <thead><tr><th>الحساب</th><th>مدين</th><th>دائن</th></tr></thead>
      <tbody>
        ${safeLines.map((l) => `<tr><td>${l.account_code || '-'} - ${l.account_name || '—'}</td><td>${Number(l.debit || 0) > 0 ? Number(l.debit || 0).toFixed(2) : '-'}</td><td>${Number(l.credit || 0) > 0 ? Number(l.credit || 0).toFixed(2) : '-'}</td></tr>`).join('')}
      </tbody>
    </table>
    <div class="totals">
      <div class="totals-row"><span>الإجمالي</span><span>${total.toFixed(2)} ر.س</span></div>
    </div>
  </div>
  <script>window.onload = function() { window.print(); };</script>
</body>
</html>`);
    printWindow.document.close();
  };

  const styles = {
    bg: 'radial-gradient(140% 140% at 10% 0%, rgba(56, 189, 248, 0.12) 0%, rgba(15, 23, 42, 0.92) 55%, #0b1120 100%)',
    cardBg: 'rgba(15, 23, 42, 0.68)',
    cardBorder: 'rgba(148, 163, 184, 0.2)',
    cardShadow: '0 18px 40px rgba(15, 23, 42, 0.45)',
    cardBlur: 'blur(16px)',
    textPrimary: '#f8fafc',
    textSecondary: '#cbd5f5',
    textMuted: '#94a3b8',
    inputBg: 'rgba(15, 23, 42, 0.6)',
    inputBorder: 'rgba(148, 163, 184, 0.25)',
    hoverBg: 'rgba(59, 130, 246, 0.12)',
  };

  return (
    <div 
      className="relative p-4 md:p-6 min-h-screen overflow-hidden transition-colors duration-500"
      style={{
        background: `
          radial-gradient(circle at 12% 18%, rgba(56,189,248,0.20) 0%, rgba(56,189,248,0) 38%),
          radial-gradient(circle at 88% 8%, rgba(14,116,144,0.22) 0%, rgba(14,116,144,0) 40%),
          radial-gradient(circle at 72% 78%, rgba(34,197,94,0.10) 0%, rgba(34,197,94,0) 42%),
          ${styles.bg}
        `,
      }}
      data-testid="journal-entries-page"
    >
      <div className="pointer-events-none absolute -top-20 -right-16 h-72 w-72 rounded-full blur-3xl opacity-50" style={{ background: 'radial-gradient(circle, rgba(14,165,233,0.42) 0%, rgba(14,165,233,0.02) 70%)' }} />
      <div className="pointer-events-none absolute top-1/3 -left-20 h-72 w-72 rounded-full blur-3xl opacity-35" style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.35) 0%, rgba(59,130,246,0.01) 72%)' }} />
      <div className="pointer-events-none absolute bottom-0 right-1/3 h-64 w-64 rounded-full blur-3xl opacity-35" style={{ background: 'radial-gradient(circle, rgba(16,185,129,0.28) 0%, rgba(16,185,129,0.01) 72%)' }} />

      {/* Header */}
      <div
        className="relative mb-6 rounded-[28px] border px-6 py-5 backdrop-blur-2xl"
        style={{
          background: 'linear-gradient(145deg, rgba(15,23,42,0.84) 0%, rgba(8,47,73,0.66) 50%, rgba(15,23,42,0.86) 100%)',
          borderColor: 'rgba(125,211,252,0.28)',
          boxShadow: '0 24px 40px -24px rgba(14,165,233,0.55), inset 0 1px 0 rgba(255,255,255,0.12)',
          backdropFilter: styles.cardBlur
        }}
        data-testid="journal-header-card"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: styles.textPrimary }} data-testid="journal-header-title">
              دفتر اليومية المحاسبية
            </h1>
            <p className="text-sm mt-1" style={{ color: styles.textSecondary }} data-testid="journal-header-subtitle">
              إدارة السيولة، الضرائب، وتحليلات النظام المالي
            </p>
          </div>

          <div className="flex gap-2">
            {canDeleteJournal ? (
            <button
              onClick={handleResetToDebtsOnly}
              disabled={resetKeepDebtsLoading}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium text-white transition-all disabled:opacity-60"
              style={{
                background: 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)',
                boxShadow: '0 4px 14px rgba(220, 38, 38, 0.28)'
              }}
              data-testid="journal-reset-keep-debts-button"
              title="حذف القيود والعمليات غير المرتبطة بالذمم"
            >
              <Trash2 size={17} />
              <span>{resetKeepDebtsLoading ? 'جارِ الحذف...' : 'حذف الكل مع إبقاء الذمم'}</span>
            </button>
            ) : null}

            <button
              onClick={fetchJournalEntries}
              className="p-2.5 rounded-xl transition-all"
              style={{ 
                backgroundColor: styles.cardBg,
                border: `1px solid ${styles.cardBorder}`,
                boxShadow: styles.cardShadow,
                color: styles.textSecondary
              }}
              data-testid="refresh-btn"
            >
              <RefreshCw size={18} />
            </button>
            {canCreateJournal ? (
            <button
              onClick={() => {
                setEditingEntry(null);
                setShowEntryForm(true);
              }}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium text-white transition-all"
              style={{ 
                background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                boxShadow: '0 4px 14px rgba(37, 99, 235, 0.25)'
              }}
              data-testid="new-entry-btn"
            >
              <Plus size={18} />
              <span>قيد جديد</span>
            </button>
            ) : null}
          </div>
        </div>
      </div>

      {/* 💳 POS / Full View Toggle */}
      <div className="mb-4 flex items-center gap-2" data-testid="journal-view-mode-toggle">
        <span className="text-xs text-slate-400">العرض:</span>
        {canUsePosJournal ? (
        <button
          type="button"
          onClick={() => { setViewMode('pos'); try { localStorage.setItem('journal.viewMode','pos'); } catch (e) {} }}
          data-testid="journal-mode-pos-button"
          className={`px-4 py-2 rounded-xl text-sm border transition ${
            viewMode === 'pos'
              ? 'bg-emerald-500/20 border-emerald-400/40 text-emerald-50'
              : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'
          }`}
        >
          💳 POS الذكي
        </button>
        ) : null}
        <button
          type="button"
          onClick={() => { setViewMode('full'); try { localStorage.setItem('journal.viewMode','full'); } catch (e) {} }}
          data-testid="journal-mode-full-button"
          className={`px-4 py-2 rounded-xl text-sm border transition ${
            viewMode === 'full'
              ? 'bg-cyan-500/20 border-cyan-400/40 text-cyan-50'
              : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'
          }`}
        >
          📖 العرض الكامل
        </button>
      </div>

      {viewMode === 'pos' ? (
        <div className="rounded-[24px] border p-4 backdrop-blur-2xl mb-6"
          style={{
            background: 'linear-gradient(145deg, rgba(15,23,42,0.84) 0%, rgba(8,47,73,0.66) 50%, rgba(15,23,42,0.86) 100%)',
            borderColor: 'rgba(125,211,252,0.28)',
            boxShadow: '0 24px 40px -24px rgba(14,165,233,0.55), inset 0 1px 0 rgba(255,255,255,0.12)',
          }}
          data-testid="journal-pos-container"
        >
          <SmartPOSJournal
            apiBase={API_URL}
            workshopId={WORKSHOP_ID}
            accounts={coaAccounts}
            recentEntries={(entries || []).slice(0, 5)}
            onSaved={() => fetchJournalEntries()}
          />
        </div>
      ) : null}

      {viewMode === 'full' ? (
        <>
      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">

        {/* Stat Cards */}
        {[
          { key: 'total', label: 'إجمالي القيود', value: stats.total, icon: FileText, iconBg: 'bg-blue-500/15', iconColor: 'text-blue-200' },
          { key: 'manual', label: 'القيود اليدوية', value: stats.manual, icon: Pencil, iconBg: 'bg-emerald-500/15', iconColor: 'text-emerald-200' },
          { key: 'amount', label: 'إجمالي الحركات', value: formatCurrency(stats.totalAmount), icon: DollarSign, iconBg: 'bg-purple-500/15', iconColor: 'text-purple-200', small: true },
        ].map((stat) => (
          <div 
            key={stat.key}
            className="rounded-2xl p-5 border backdrop-blur-xl"
            style={{ 
              background: 'linear-gradient(150deg, rgba(15,23,42,0.82) 0%, rgba(15,23,42,0.6) 48%, rgba(8,47,73,0.55) 100%)',
              borderColor: 'rgba(125,211,252,0.24)',
              boxShadow: '0 18px 26px -22px rgba(56,189,248,0.5), inset 0 1px 0 rgba(255,255,255,0.10)',
              backdropFilter: styles.cardBlur
            }}
            data-testid={`journal-stat-${stat.key}`}
          >
            <div className="flex items-center gap-3">
              <div className={`w-12 h-12 rounded-xl ${stat.iconBg} flex items-center justify-center`}>
                <stat.icon size={22} className={stat.iconColor} />
              </div>
              <div>
                <p className="text-xs" style={{ color: styles.textMuted }} data-testid={`journal-stat-${stat.key}-label`}>{stat.label}</p>
                <p className={`font-bold ${stat.small ? 'text-lg' : 'text-2xl'}`} style={{ color: styles.textPrimary }} data-testid={`journal-stat-${stat.key}-value`}>
                  {stat.value}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Search and Filters */}
      <div 
        className="rounded-2xl p-4 mb-6 border backdrop-blur-xl"
        style={{ 
          background: 'linear-gradient(145deg, rgba(15,23,42,0.8) 0%, rgba(15,23,42,0.62) 58%, rgba(6,95,70,0.22) 100%)',
          borderColor: 'rgba(94,234,212,0.24)',
          boxShadow: '0 20px 28px -24px rgba(45,212,191,0.48), inset 0 1px 0 rgba(255,255,255,0.08)',
          backdropFilter: styles.cardBlur
        }}
        data-testid="journal-filters-card"
      >
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: styles.textMuted }} size={18} />
            <input
              type="text"
              placeholder="بحث برقم القيد أو الوصف أو العميل..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pr-10 pl-4 py-2.5 rounded-xl text-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              style={{ 
                backgroundColor: styles.inputBg,
                border: `1px solid ${styles.inputBorder}`,
                color: styles.textPrimary
              }}
              data-testid="search-input"
            />
          </div>

          <div 
            className="flex gap-1.5 p-1 rounded-xl"
            style={{ backgroundColor: styles.inputBg }}
            data-testid="journal-status-filter"
          >
            {['all', 'posted', 'draft'].map((filter) => (
              <button
                key={filter}
                onClick={() => setStatusFilter(filter)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  statusFilter === filter ? 'bg-blue-600 text-white shadow-md' : ''
                }`}
                style={statusFilter !== filter ? { color: styles.textSecondary } : {}}
                data-testid={`filter-${filter}`}
              >
                {filter === 'all' ? 'الكل' : filter === 'posted' ? 'مرحّل' : 'مسودة'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Journal Entries Table */}
      <div 
        className="rounded-2xl overflow-hidden border backdrop-blur-xl"
        style={{ 
          background: 'linear-gradient(170deg, rgba(15,23,42,0.86) 0%, rgba(15,23,42,0.68) 45%, rgba(2,132,199,0.15) 100%)',
          borderColor: 'rgba(125,211,252,0.25)',
          boxShadow: '0 24px 34px -24px rgba(14,165,233,0.55), inset 0 1px 0 rgba(255,255,255,0.09)',
          backdropFilter: styles.cardBlur
        }}
        data-testid="journal-entries-card"
      >
        <div className="px-6 py-4" style={{ borderBottom: `1px solid ${styles.cardBorder}` }}>
          <div className="flex items-center gap-2">
            <FileText size={18} className="text-blue-300" />
            <h2 className="font-semibold" style={{ color: styles.textPrimary }} data-testid="journal-entries-title">سجل الفواتير والعمليات</h2>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="flex flex-col items-center gap-3">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500"></div>
              <span style={{ color: styles.textSecondary }}>جاري التحميل...</span>
            </div>
          </div>
        ) : filteredEntries.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center" style={{ backgroundColor: styles.inputBg }}>
              <BookOpen size={32} style={{ color: styles.textMuted }} />
            </div>
            <h3 className="text-lg font-semibold mb-2" style={{ color: styles.textPrimary }}>لا توجد قيود</h3>
            <p style={{ color: styles.textSecondary }}>أضف قيداً جديداً أو قم بإضافة بنود لملف مركبة</p>
          </div>
        ) : (
          <>
            <div className="block md:hidden px-4 pb-4 space-y-3">
              {filteredEntries.map((entry) => {
                const typeConfig = getEntryTypeConfig(entry.reference_type);
                const TypeIcon = typeConfig.icon;
                const total = entry.total_debit || 0;
                const isManual = entry.source === 'manual';
                const safeDescription = cleanDescription(entry.description || 'قيد محاسبي', entry.party_label, entry.vehicle_plate);
                const linkage = getEntryLinkage(entry);

                return (
                  <div
                    key={entry.id}
                    className="rounded-2xl border p-4 backdrop-blur-xl"
                    style={{
                      backgroundColor: styles.cardBg,
                      borderColor: styles.cardBorder,
                      boxShadow: styles.cardShadow,
                      backdropFilter: styles.cardBlur
                    }}
                    data-testid={`entry-card-${entry.id}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${typeConfig.bgColor}`}>
                          <TypeIcon size={18} className={typeConfig.textColor} />
                        </div>
                        <div>
                          <p className="text-[11px] text-blue-200 mb-0.5" data-testid={`entry-card-op-type-${entry.id}`}>
                            نوع العملية: {entry.operation_type_label || 'غير محدد'}
                          </p>
                          <p className="text-sm font-semibold text-slate-100" data-testid={`entry-card-desc-${entry.id}`}>
                            {safeDescription || 'قيد محاسبي'}
                          </p>
                          <p className="text-xs text-slate-400" data-testid={`entry-card-number-${entry.id}`}>
                            {entry.entry_number}
                          </p>
                        </div>
                      </div>
                      <span className={`text-xs px-2.5 py-1 rounded-full ${
                        isManual ? 'bg-white/10 text-slate-200' : 'bg-blue-500/15 text-blue-200'
                      }`} data-testid={`entry-card-source-${entry.id}`}>
                        {isManual ? 'يدوي' : 'آلي'}
                      </span>
                    </div>

                    <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                      <span data-testid={`entry-card-date-${entry.id}`}>{formatDate(entry.entry_date)}</span>
                      <span data-testid={`entry-card-customer-${entry.id}`}>طرف العملية: {entry.party_label || 'مفتوح'}</span>
                    </div>

                    <div className="mt-2 flex flex-wrap gap-2" data-testid={`entry-card-payment-row-${entry.id}`}>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] ${getPaymentMethodTone(entry.payment_method)}`} data-testid={`entry-card-payment-method-${entry.id}`}>
                        {entry.payment_method_label_ar ? `الطريقة: ${entry.payment_method_label_ar}` : `المصدر: ${getSourceLabel(entry.source)}`}
                      </span>
                      {entry.payment_status_label_ar && entry.payment_status_label_ar !== '-' ? (
                        <span className={`px-2 py-0.5 rounded-full text-[10px] ${getPaymentStatusTone(entry.payment_status)}`} data-testid={`entry-card-payment-status-${entry.id}`}>
                          {entry.payment_status_label_ar}
                        </span>
                      ) : null}
                      <span className="px-2 py-0.5 rounded-full text-[10px] bg-white/10 text-slate-200" data-testid={`entry-card-source-detail-${entry.id}`}>
                        {getSourceLabel(entry.source)}
                      </span>
                    </div>

                    <div className="mt-1">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] ${linkage.linked ? 'bg-emerald-500/15 text-emerald-200' : 'bg-amber-500/15 text-amber-200'}`}
                        data-testid={`entry-card-linkage-${entry.id}`}
                      >
                        {linkage.label}
                      </span>
                    </div>

                    <div className="mt-1 text-xs text-slate-400" data-testid={`entry-card-vehicle-${entry.id}`}>
                      المركبة: {entry.vehicle_plate || 'غير محدد'}
                    </div>

                    <div className="mt-3 flex items-center justify-between">
                      <span className="text-lg font-bold text-slate-100" data-testid={`entry-card-total-${entry.id}`}>
                        {formatCurrency(total)}
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handlePrintInvoice(entry)}
                          className="p-2 rounded-lg transition-colors hover:bg-white/10"
                          title="طباعة"
                          data-testid={`entry-card-print-${entry.id}`}
                        >
                          <Printer size={16} className="text-blue-300" />
                        </button>
                        <button
                          onClick={() => {
                            setSelectedEntry(entry);
                            setShowDetailModal(true);
                          }}
                          className="p-2 rounded-lg transition-colors hover:bg-white/10"
                          title="عرض التفاصيل"
                          data-testid={`entry-card-view-${entry.id}`}
                        >
                          <Eye size={16} className="text-blue-300" />
                        </button>
                        {canEditJournal ? (
                          <button
                            onClick={() => handleQuickEditParty(entry)}
                            className="p-2 rounded-lg transition-colors hover:bg-white/10"
                            title="تعديل طرف العملية"
                            data-testid={`entry-card-edit-party-${entry.id}`}
                          >
                            <User size={16} className="text-cyan-300" />
                          </button>
                        ) : null}
                        {canEditJournal ? (
                          <button
                            onClick={() => {
                              setEditingEntry(entry);
                              setShowEntryForm(true);
                            }}
                            className="p-2 rounded-lg transition-colors hover:bg-white/10"
                            title="تعديل"
                            data-testid={`entry-card-edit-${entry.id}`}
                          >
                            <Pencil size={16} className="text-amber-300" />
                          </button>
                        ) : null}
                        {canDeleteJournal ? (
                          <button
                            onClick={() => setDeleteConfirm(entry)}
                            className="p-2 rounded-lg transition-colors hover:bg-white/10"
                            title="حذف"
                            data-testid={`entry-card-delete-${entry.id}`}
                          >
                            <Trash2 size={16} className="text-rose-300" />
                          </button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="hidden md:block">
              <div>
                {/* Table Header */}
                <div 
                  className="grid grid-cols-12 gap-4 px-6 py-3 text-xs font-semibold uppercase tracking-wider"
                  style={{ 
                    color: styles.textSecondary,
                    backgroundColor: 'rgba(15, 23, 42, 0.85)'
                  }}
                >
                  <div className="col-span-3">الوصف</div>
                  <div className="col-span-2">التاريخ</div>
                  <div className="col-span-3">طرف العملية</div>
                  <div className="col-span-2">المبلغ</div>
                  <div className="col-span-1">النوع</div>
                  <div className="col-span-1"></div>
                </div>

                {/* Table Rows */}
                {filteredEntries.map((entry) => {
                  const typeConfig = getEntryTypeConfig(entry.reference_type);
                  const TypeIcon = typeConfig.icon;
                  const total = entry.total_debit || 0;
                  const isManual = entry.source === 'manual';
                  const safeDescription = cleanDescription(entry.description || 'قيد محاسبي', entry.party_label, entry.vehicle_plate);
                  const linkage = getEntryLinkage(entry);

                  return (
                    <div 
                      key={entry.id}
                      className="grid grid-cols-12 gap-4 px-6 py-4 items-center transition-colors"
                      style={{ borderBottom: `1px solid ${styles.cardBorder}` }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = styles.hoverBg}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                      data-testid={`entry-row-${entry.id}`}
                    >
                      <div className="col-span-3 flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${typeConfig.bgColor}`}>
                          <TypeIcon size={18} className={typeConfig.textColor} />
                        </div>
                        <div>
                          <p className="text-[11px] text-blue-200">
                            نوع العملية: {entry.operation_type_label || 'غير محدد'}
                          </p>
                          <p className="font-medium text-sm" style={{ color: styles.textPrimary }}>
                            {safeDescription || 'قيد محاسبي'}
                          </p>
                          <p className="text-xs" style={{ color: styles.textMuted }}>
                            {entry.entry_number}
                          </p>
                        </div>
                      </div>

                      <div className="col-span-2">
                        <p className="text-sm" style={{ color: styles.textSecondary }}>
                          {formatDate(entry.entry_date)}
                        </p>
                      </div>

                      <div className="col-span-3">
                        <div className="flex items-center gap-2">
                          <p className="text-sm truncate" style={{ color: styles.textPrimary }} data-testid={`entry-row-party-${entry.id}`}>
                            طرف العملية: {entry.party_label || 'مفتوح'}
                          </p>
                          {canEditJournal ? (
                            <button
                              onClick={() => handleQuickEditParty(entry)}
                              className="p-1.5 rounded-md hover:bg-white/10"
                              title="تعديل طرف العملية"
                              data-testid={`entry-row-party-edit-${entry.id}`}
                            >
                              <Pencil size={13} className="text-cyan-300" />
                            </button>
                          ) : null}
                        </div>
                        <p className="text-xs" style={{ color: styles.textMuted }} data-testid={`entry-row-vehicle-${entry.id}`}>
                          المركبة: {entry.vehicle_plate || 'غير محدد'}
                        </p>
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] ${getPaymentMethodTone(entry.payment_method)}`} data-testid={`entry-row-payment-method-${entry.id}`}>
                            {entry.payment_method_label_ar ? `الطريقة: ${entry.payment_method_label_ar}` : `المصدر: ${getSourceLabel(entry.source)}`}
                          </span>
                          {entry.payment_status_label_ar && entry.payment_status_label_ar !== '-' ? (
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] ${getPaymentStatusTone(entry.payment_status)}`} data-testid={`entry-row-payment-status-${entry.id}`}>
                              {entry.payment_status_label_ar}
                            </span>
                          ) : null}
                        </div>
                        <p className={`text-[10px] mt-1 ${linkage.linked ? 'text-emerald-300' : 'text-amber-300'}`} data-testid={`entry-row-linkage-${entry.id}`}>
                          حالة الربط: {linkage.label}
                        </p>
                      </div>

                      <div className="col-span-2">
                        <p className="font-semibold" style={{ color: styles.textPrimary }}>
                          {formatCurrency(total)}
                        </p>
                      </div>

                      <div className="col-span-1">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                          isManual 
                            ? 'bg-white/10 text-slate-200' 
                            : 'bg-blue-500/15 text-blue-200'
                        }`}>
                          {isManual ? 'يدوي' : getSourceLabel(entry.source)}
                        </span>
                      </div>

                      <div className="col-span-1 flex justify-end gap-1">
                        <button
                          onClick={() => {
                            setSelectedEntry(entry);
                            setShowDetailModal(true);
                          }}
                          className="p-2 rounded-lg transition-colors hover:bg-white/10"
                          title="عرض التفاصيل"
                          data-testid={`view-btn-${entry.id}`}
                        >
                          <Eye size={16} style={{ color: styles.textSecondary }} />
                        </button>
                        {canEditJournal ? (
                          <button
                            onClick={() => {
                              setEditingEntry(entry);
                              setShowEntryForm(true);
                            }}
                            className="p-2 rounded-lg transition-colors hover:bg-white/10"
                            title="تعديل"
                            data-testid={`edit-btn-${entry.id}`}
                          >
                            <Pencil size={16} className="text-amber-300" />
                          </button>
                        ) : null}
                        {canDeleteJournal ? (
                          <button
                            onClick={() => setDeleteConfirm(entry)}
                            className="p-2 rounded-lg transition-colors hover:bg-white/10"
                            title="حذف"
                            data-testid={`delete-btn-${entry.id}`}
                          >
                            <Trash2 size={16} className="text-rose-300" />
                          </button>
                        ) : null}
                        <button
                          onClick={() => handlePrintInvoice(entry)}
                              className="p-2 rounded-lg transition-colors hover:bg-white/10"
                          title="طباعة"
                          data-testid={`print-btn-${entry.id}`}
                        >
                          <Printer size={16} style={{ color: styles.textSecondary }} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>
        </>
      ) : null}

      {/* Detail Modal */}
      {showDetailModal && selectedEntry && (
        <EntryDetailModal
          entry={selectedEntry}
          onClose={() => {
            setShowDetailModal(false);
            setSelectedEntry(null);
          }}
          onPrint={handlePrintInvoice}
          isLight={isLight}
          styles={styles}
        />
      )}

      {/* Entry Form Modal */}
      {showEntryForm && (
        <EntryFormModal
          entry={editingEntry}
          onClose={() => {
            setShowEntryForm(false);
            setEditingEntry(null);
          }}
          onSave={editingEntry ? handleUpdateEntry : handleCreateEntry}
          saving={saving}
          isLight={isLight}
          styles={styles}
          coaAccounts={coaAccounts}
        />
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <DeleteConfirmModal
          entry={deleteConfirm}
          onClose={() => setDeleteConfirm(null)}
          onConfirm={() => handleDeleteEntry(deleteConfirm.id)}
          isLight={isLight}
          styles={styles}
        />
      )}

      {partyEditorEntry && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" data-testid="party-editor-modal">
          <div className="w-full max-w-md rounded-2xl p-5" style={{ backgroundColor: styles.cardBg, border: `1px solid ${styles.cardBorder}` }}>
            <h3 className="text-lg font-bold mb-3" style={{ color: styles.textPrimary }}>تعديل طرف العملية</h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs mb-1 block" style={{ color: styles.textSecondary }}>نوع الطرف</label>
                <select
                  value={partyEditorType}
                  onChange={(e) => setPartyEditorType(e.target.value)}
                  className="w-full rounded-xl px-3 py-2"
                  style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', color: styles.textPrimary, border: `1px solid ${styles.cardBorder}` }}
                  data-testid="party-editor-type-select"
                >
                  <option value="customer">عميل</option>
                  <option value="supplier">مورد</option>
                  <option value="open">مفتوح</option>
                  <option value="manual">مخصص</option>
                </select>
              </div>

              <div>
                <label className="text-xs mb-1 block" style={{ color: styles.textSecondary }}>اسم طرف العملية</label>
                <input
                  value={partyEditorLabel}
                  onChange={(e) => setPartyEditorLabel(e.target.value)}
                  className="w-full rounded-xl px-3 py-2"
                  style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', color: styles.textPrimary, border: `1px solid ${styles.cardBorder}` }}
                  data-testid="party-editor-label-input"
                  placeholder="مثال: عميل فلان / مورد فلان / مفتوح"
                />
              </div>
            </div>

            <div className="mt-4 flex gap-2">
              <button
                onClick={submitPartyEditor}
                disabled={partyEditorSaving}
                className="flex-1 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium disabled:opacity-50"
                data-testid="party-editor-save-button"
              >
                {partyEditorSaving ? 'جارٍ الحفظ...' : 'حفظ'}
              </button>
              <button
                onClick={() => setPartyEditorEntry(null)}
                className="flex-1 py-2 rounded-xl"
                style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', color: styles.textSecondary }}
                data-testid="party-editor-cancel-button"
              >
                إلغاء
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function EntryFormModal({ entry, onClose, onSave, saving, isLight, styles, coaAccounts }) {
  const safeCoaAccounts = ensureArray(coaAccounts)
    .map((acc) => ensureObject(acc))
    .filter(Boolean);

  const normalizedEntryLines = ensureArray(entry?.lines)
    .map((line) => ensureObject(line))
    .filter(Boolean);

  const defaultPartyType =
    entry?.party_type
    || (entry?.transaction_type === 'sale'
      ? 'customer'
      : ['purchase', 'expense'].includes(entry?.transaction_type)
        ? 'supplier'
        : 'open');

  const [formData, setFormData] = useState({
    date: entry?.entry_date || new Date().toISOString().split('T')[0],
    description: entry?.description || '',
    transaction_type: entry?.transaction_type || 'manual',
    party_type: defaultPartyType,
    party_name: entry?.party_label && entry?.party_label !== 'مفتوح' ? entry.party_label : '',
    vehicle_reference: extractTagValue(entry?.description || '', 'VEHICLE_REF') || entry?.vehicle_reference || '',
    lines: normalizedEntryLines.length > 0 ? normalizedEntryLines.map(l => ({
      account_code: l?.account_code || l?.account || '',
      account_name: l?.account_name || '',
      debit: Number(l?.debit || 0),
      credit: Number(l?.credit || 0)
    })) : [
      { account_code: '', account_name: '', debit: 0, credit: 0 },
      { account_code: '', account_name: '', debit: 0, credit: 0 }
    ]
  });

  const [ocrImage, setOcrImage] = useState('');
  const [ocrPreview, setOcrPreview] = useState('');
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [ocrError, setOcrError] = useState('');
  const [customers, setCustomers] = useState([]);
  const [suppliers, setSuppliers] = useState([]);

  useEffect(() => {
    let mounted = true;

    const fetchParties = async () => {
      try {
        const [customersRes, suppliersRes] = await Promise.all([
          fetch(`${API_URL}/customers`),
          fetch(`${API_URL}/suppliers`),
        ]);
        const customersData = await customersRes.json();
        const suppliersData = await suppliersRes.json();

        if (!mounted) return;
        setCustomers(Array.isArray(customersData) ? customersData : []);
        setSuppliers(Array.isArray(suppliersData) ? suppliersData : []);
      } catch {
        if (!mounted) return;
        setCustomers([]);
        setSuppliers([]);
      }
    };

    fetchParties();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    setFormData((prev) => {
      if (['sale', 'sale_return', 'receipt_voucher'].includes(prev.transaction_type)) {
        if (prev.party_type === 'customer') return prev;
        return { ...prev, party_type: 'customer' };
      }
      if (['purchase', 'purchase_return', 'expense'].includes(prev.transaction_type)) {
        if (prev.party_type === 'supplier') return prev;
        return { ...prev, party_type: 'supplier' };
      }
      if (prev.transaction_type === 'settlement') {
        if (['customer', 'supplier'].includes(prev.party_type)) return prev;
        return { ...prev, party_type: 'customer' };
      }
      if (prev.party_type === 'open') return prev;
      return { ...prev, party_type: 'open' };
    });
  }, [formData.transaction_type]);

  const smartOperationType = useMemo(() => {
    if (formData.transaction_type === 'sale') return 'sale';
    if (formData.transaction_type === 'sale_return') return 'sale';
    if (formData.transaction_type === 'purchase') return 'purchase';
    if (formData.transaction_type === 'purchase_return') return 'purchase';
    if (formData.transaction_type === 'expense') return 'expense';
    if (formData.transaction_type === 'receipt_voucher') return 'receipt';
    if (formData.transaction_type === 'settlement') {
      return formData.party_type === 'supplier' ? 'payment' : 'receipt';
    }
    return 'sale';
  }, [formData.transaction_type, formData.party_type]);

  const includeAllAccounts = ['manual', 'other'].includes(formData.transaction_type);
  const partyOptions = formData.party_type === 'customer' ? customers : formData.party_type === 'supplier' ? suppliers : [];

  const totalDebit = formData.lines.reduce((sum, l) => sum + (parseFloat(l.debit) || 0), 0);
  const totalCredit = formData.lines.reduce((sum, l) => sum + (parseFloat(l.credit) || 0), 0);
  const isBalanced = Math.abs(totalDebit - totalCredit) < 0.01;

  const getLineFieldKey = (line, idx) => {
    const debit = Number(line?.debit || 0);
    const credit = Number(line?.credit || 0);
    if (debit > 0 && credit <= 0) return 'debit';
    if (credit > 0 && debit <= 0) return 'credit';
    return idx % 2 === 0 ? 'debit' : 'credit';
  };

  const debitLine = useMemo(
    () => formData.lines.find((l) => Number(l?.debit || 0) > 0 && String(l?.account_code || '').trim()) || null,
    [formData.lines]
  );

  const creditLine = useMemo(
    () => formData.lines.find((l) => Number(l?.credit || 0) > 0 && String(l?.account_code || '').trim()) || null,
    [formData.lines]
  );

  const resolveLineAccountLabel = (line) => {
    if (!line) return 'غير محدد';
    const code = String(line.account_code || '').trim();
    const acc = safeCoaAccounts.find((a) => String(a?.code) === code);
    const name = line.account_name || acc?.name_ar || acc?.name || '';
    return code ? `[${code}] ${name || 'حساب'}` : 'غير محدد';
  };

  const entryRuleSummary = useMemo(() => {
    const rows = [
      { side: 'مدين', flow: 'الذي دخل لك', account: resolveLineAccountLabel(debitLine) },
      { side: 'دائن', flow: 'الذي خرج منك', account: resolveLineAccountLabel(creditLine) },
    ];

    let example = 'قاعدة تفسيرية عامة.';
    if (['purchase', 'purchase_return', 'expense'].includes(formData.transaction_type)) {
      example = 'مثال الشراء: المشتريات = مدين، الصندوق/البنك = دائن.';
    } else if (['sale', 'sale_return'].includes(formData.transaction_type)) {
      example = 'مثال البيع: الصندوق/البنك أو العميل = مدين، الإيراد = دائن.';
    } else if (formData.transaction_type === 'receipt_voucher') {
      example = 'مثال سند القبض: التحصيل = مدين، ذمم العملاء = دائن.';
    } else if (formData.transaction_type === 'settlement') {
      example = 'مثال التسوية: طبّق قاعدة دخل/خرج حسب الطرف المختار.';
    }

    return { rows, example };
  }, [debitLine, creditLine, formData.transaction_type, coaAccounts]);

  const addLine = () => {
    setFormData(prev => ({
      ...prev,
      lines: [...prev.lines, { account_code: '', account_name: '', debit: 0, credit: 0 }]
    }));
  };

  const removeLine = (index) => {
    if (formData.lines.length <= 2) return;
    setFormData(prev => ({
      ...prev,
      lines: prev.lines.filter((_, i) => i !== index)
    }));
  };

  const updateLine = (index, field, value) => {
    setFormData(prev => {
      const newLines = [...prev.lines];
      if (field === 'account_code') {
        const account = safeCoaAccounts.find((a) => String(a?.code) === String(value));
        newLines[index] = {
          ...newLines[index],
          account_code: value,
          account_name: account ? (account.name_ar || account.name || '') : ''
        };
      } else {
        newLines[index] = { ...newLines[index], [field]: value };
      }
      return { ...prev, lines: newLines };
    });
  };

  const handleOcrFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result?.toString() || '';
      setOcrImage(base64);
      setOcrPreview(base64);
      setOcrResult(null);
      setOcrError('');
    };
    reader.readAsDataURL(file);
  };

  const runOcr = async () => {
    if (!ocrImage) return;
    setOcrLoading(true);
    setOcrError('');
    try {
      const { data } = await axios.post(`${API_URL}/parts/ocr`, { image_base64: ocrImage });
      setOcrResult(data);
    } catch (error) {
      setOcrError(error?.response?.data?.detail || 'تعذر قراءة الفاتورة');
    } finally {
      setOcrLoading(false);
    }
  };

  const applyOcrToEntry = () => {
    if (!ocrResult) return;
    const total = Number(ocrResult?.totals?.grand_total || 0);
    const description = [
      'فاتورة مشتريات',
      ocrResult.vendor,
      ocrResult.invoice_number ? `#${ocrResult.invoice_number}` : ''
    ].filter(Boolean).join(' ');

    setFormData(prev => ({
      ...prev,
      description: description || prev.description,
      lines: [
        { account_code: '', account_name: '', debit: total || 0, credit: 0 },
        { account_code: '', account_name: '', debit: 0, credit: total || 0 }
      ]
    }));
  };

  const handleSubmit = () => {
    if (!formData.description.trim()) {
      alert('يرجى إدخال وصف القيد');
      return;
    }
    if (!isBalanced) {
      alert('القيد غير متوازن. يجب أن يتساوى المدين والدائن');
      return;
    }
    if (totalDebit === 0) {
      alert('يرجى إدخال مبالغ للقيد');
      return;
    }

    const txType = String(formData.transaction_type || '').trim();
    const partyName = String(formData.party_name || '').trim();
    const vehicleRef = String(formData.vehicle_reference || '').trim();

    if (['sale', 'sale_return'].includes(txType) && !partyName && !vehicleRef) {
      alert('قيد البيع/مرتجع البيع يتطلب ربطه بعميل أو مرجع مركبة.');
      return;
    }

    if (['purchase', 'purchase_return', 'expense'].includes(txType) && !partyName) {
      alert('قيد الشراء/المصروف يتطلب تحديد المورد.');
      return;
    }

    if (txType === 'receipt_voucher' && !vehicleRef) {
      alert('سند القبض يتطلب مرجع مركبة (مثل رقم اللوحة أو رقم الزيارة).');
      return;
    }

    if (txType === 'settlement') {
      if (!partyName) {
        alert('التسوية تتطلب تحديد عميل أو مورد.');
        return;
      }
      if (!['customer', 'supplier'].includes(formData.party_type)) {
        alert('التسوية يجب أن تكون مرتبطة بعميل أو مورد.');
        return;
      }
    }

    const inferredPartyType =
      ['sale', 'sale_return', 'receipt_voucher'].includes(formData.transaction_type)
        ? 'customer'
        : ['purchase', 'purchase_return', 'expense'].includes(formData.transaction_type)
          ? 'supplier'
          : (formData.party_type || 'open');

    const cleanDescription = String(formData.description || '')
      .replace(/\[PARTY:[^\]]+\]/g, '')
      .replace(/\[PARTY_TYPE:[^\]]+\]/g, '')
      .replace(/\[VEHICLE_REF:[^\]]+\]/g, '')
      .trim();

    const finalDescription = [
      cleanDescription,
      partyName ? `[PARTY:${partyName}] [PARTY_TYPE:${inferredPartyType}]` : '',
      vehicleRef ? `[VEHICLE_REF:${vehicleRef}]` : '',
    ].filter(Boolean).join(' ').trim();

    onSave({
      ...formData,
      description: finalDescription,
      party_type: inferredPartyType,
      party_label: partyName || 'مفتوح',
      lines: formData.lines.map(l => ({
        account: l.account_code,
        account_name: l.account_name,
        debit: parseFloat(l.debit) || 0,
        credit: parseFloat(l.credit) || 0
      }))
    });
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div 
        className="rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto"
        style={{ 
          backgroundColor: styles.cardBg,
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)' 
        }}
      >
        {/* Header */}
        <div 
          className="p-6"
          style={{ 
            borderBottom: `1px solid ${styles.cardBorder}`,
            background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)'
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-xl bg-white/20 flex items-center justify-center">
                <FileText size={28} className="text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">
                  {entry ? 'تعديل قيد محاسبي' : 'قيد محاسبي جديد'}
                </h2>
                <p className="text-white/80 text-sm">أدخل تفاصيل القيد المحاسبي</p>
              </div>
            </div>
            <button 
              onClick={onClose} 
              className="p-2 rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors"
            >
              <X size={24} />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Basic Info */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: styles.textPrimary }}>
                التاريخ
              </label>
              <input
                type="date"
                value={formData.date}
                onChange={(e) => setFormData(prev => ({ ...prev, date: e.target.value }))}
                className="w-full px-4 py-2.5 rounded-xl text-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                style={{ 
                  backgroundColor: styles.inputBg,
                  border: `1px solid ${styles.inputBorder}`,
                  color: styles.textPrimary
                }}
                data-testid="entry-date-input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: styles.textPrimary }}>
                الوصف
              </label>
              <input
                type="text"
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                placeholder="مثال: دفعة إيجار الشهر"
                className="w-full px-4 py-2.5 rounded-xl text-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                style={{ 
                  backgroundColor: styles.inputBg,
                  border: `1px solid ${styles.inputBorder}`,
                  color: styles.textPrimary
                }}
                data-testid="entry-description-input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: styles.textPrimary }}>
                نوع الحركة
              </label>
              <select
                value={formData.transaction_type}
                onChange={(e) => setFormData(prev => ({ ...prev, transaction_type: e.target.value, party_name: '' }))}
                className="w-full px-4 py-2.5 rounded-xl text-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                style={{ 
                  backgroundColor: styles.inputBg,
                  border: `1px solid ${styles.inputBorder}`,
                  color: styles.textPrimary
                }}
                data-testid="entry-transaction-type-select"
              >
                <option value="manual">قيد يدوي عام</option>
                <option value="purchase">شراء</option>
                <option value="purchase_return">مرتجع شراء</option>
                <option value="sale">بيع</option>
                <option value="sale_return">مرتجع بيع</option>
                <option value="receipt_voucher">سند قبض (مرتبط بمركبة)</option>
                <option value="settlement">تسوية (عميل/مورد)</option>
                <option value="expense">مصاريف تشغيلية</option>
                <option value="other">أخرى</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: styles.textPrimary }}>
                {formData.party_type === 'customer' ? 'العميل' : formData.party_type === 'supplier' ? 'المورد' : 'الطرف'}
              </label>
              {formData.transaction_type === 'settlement' && (
                <div className="flex gap-2 mb-2">
                  <button
                    type="button"
                    className={`px-3 py-1 rounded-lg text-xs border ${formData.party_type === 'customer' ? 'bg-blue-500/20 border-blue-400/40 text-blue-100' : 'border-slate-500/40 text-slate-300'}`}
                    onClick={() => setFormData((prev) => ({ ...prev, party_type: 'customer', party_name: '' }))}
                    data-testid="entry-settlement-party-customer"
                  >
                    عميل
                  </button>
                  <button
                    type="button"
                    className={`px-3 py-1 rounded-lg text-xs border ${formData.party_type === 'supplier' ? 'bg-blue-500/20 border-blue-400/40 text-blue-100' : 'border-slate-500/40 text-slate-300'}`}
                    onClick={() => setFormData((prev) => ({ ...prev, party_type: 'supplier', party_name: '' }))}
                    data-testid="entry-settlement-party-supplier"
                  >
                    مورد
                  </button>
                </div>
              )}
              <input
                type="text"
                list={`journal-party-options-${formData.party_type}`}
                value={formData.party_name || ''}
                onChange={(e) => {
                  const value = e.target.value;
                  const match = partyOptions.find((row) => String(row?.name || '').trim().toLowerCase() === value.trim().toLowerCase());
                  setFormData(prev => ({ ...prev, party_name: match?.name || value }));
                }}
                placeholder={
                  formData.party_type === 'customer'
                    ? 'اختر عميل أو اكتب الاسم'
                    : formData.party_type === 'supplier'
                      ? 'اختر مورد أو اكتب الاسم'
                      : 'اختياري'
                }
                className="w-full px-4 py-2.5 rounded-xl text-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                style={{
                  backgroundColor: styles.inputBg,
                  border: `1px solid ${styles.inputBorder}`,
                  color: styles.textPrimary,
                }}
                data-testid="entry-party-name-input"
              />
              <datalist id={`journal-party-options-${formData.party_type}`}>
                {ensureArray(partyOptions)
                  .map((row) => ensureObject(row))
                  .filter(Boolean)
                  .map((row, idx) => (
                  <option key={row.id || row.name || `party-${idx}`} value={row.name || ''} />
                ))}
              </datalist>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: styles.textPrimary }}>
                مرجع المركبة
              </label>
              <input
                type="text"
                value={formData.vehicle_reference || ''}
                onChange={(e) => setFormData((prev) => ({ ...prev, vehicle_reference: e.target.value }))}
                placeholder="مثال: اللوحة 10560 أو رقم زيارة"
                className="w-full px-4 py-2.5 rounded-xl text-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                style={{
                  backgroundColor: styles.inputBg,
                  border: `1px solid ${styles.inputBorder}`,
                  color: styles.textPrimary,
                }}
                data-testid="entry-vehicle-reference-input"
              />
            </div>
          </div>

          <div
            className="rounded-xl p-4"
            style={{ border: `1px solid ${styles.cardBorder}`, backgroundColor: 'rgba(37,99,235,0.10)' }}
            data-testid="entry-explanation-rule-card"
          >
            <div className="text-sm font-semibold mb-2" style={{ color: styles.textPrimary }} data-testid="entry-explanation-rule-title">
              تفسير القيد حسب المدخلات
            </div>
            <div className="space-y-1 text-xs" style={{ color: styles.textSecondary }}>
              <div data-testid="entry-explanation-rule-core-0">• الذي دخل لك = مدين</div>
              <div data-testid="entry-explanation-rule-core-1">• الذي خرج منك = دائن</div>
            </div>
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
              {entryRuleSummary.rows.map((row, idx) => (
                <div
                  key={`entry-rule-row-${idx}`}
                  className="rounded-lg px-3 py-2"
                  style={{
                    backgroundColor: row.side === 'مدين' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.10)',
                    border: `1px solid ${row.side === 'مدين' ? 'rgba(34,197,94,0.35)' : 'rgba(239,68,68,0.35)'}`,
                    color: styles.textPrimary,
                  }}
                  data-testid={`entry-explanation-rule-line-${idx}`}
                >
                  <div className="font-semibold">{row.side}</div>
                  <div>{row.flow}</div>
                  <div className="font-mono text-[11px]" style={{ color: styles.textSecondary }}>{row.account}</div>
                </div>
              ))}
            </div>
          </div>

        {/* OCR Invoice */}
        <div className="rounded-xl p-4 mb-4" style={{ border: `1px solid ${styles.cardBorder}`, backgroundColor: styles.cardBg }}>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold" style={{ color: styles.textPrimary }}>مسح فاتورة مشتريات</div>
              <div className="text-xs" style={{ color: styles.textSecondary }}>التقط صورة أو ارفع ملف لملء القيد تلقائياً</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <label className="text-xs px-3 py-2 rounded-lg cursor-pointer" style={{ backgroundColor: styles.inputBg, border: `1px solid ${styles.inputBorder}`, color: styles.textPrimary }}>
                التقاط بالكاميرا
                <input type="file" accept="image/*" capture="environment" className="hidden" onChange={handleOcrFileChange} data-testid="journal-ocr-camera-input" />
              </label>
              <label className="text-xs px-3 py-2 rounded-lg cursor-pointer" style={{ backgroundColor: styles.inputBg, border: `1px solid ${styles.inputBorder}`, color: styles.textPrimary }}>
                رفع ملف
                <input type="file" accept="image/*" className="hidden" onChange={handleOcrFileChange} data-testid="journal-ocr-file-input" />
              </label>
              <button
                type="button"
                onClick={runOcr}
                disabled={ocrLoading}
                className="text-xs px-3 py-2 rounded-lg"
                style={{ backgroundColor: '#2563eb', color: '#fff' }}
                data-testid="journal-ocr-run"
              >
                {ocrLoading ? 'جاري القراءة...' : 'تشغيل OCR'}
              </button>
              {ocrResult && (
                <button
                  type="button"
                  onClick={applyOcrToEntry}
                  className="text-xs px-3 py-2 rounded-lg"
                  style={{ backgroundColor: '#10b981', color: '#fff' }}
                  data-testid="journal-ocr-apply"
                >
                  تطبيق على القيد
                </button>
              )}
            </div>
          </div>
          {ocrPreview && (
            <img src={ocrPreview} alt="OCR" className="mt-3 max-h-48 rounded-xl" data-testid="journal-ocr-preview" />
          )}
          {ocrError && (
            <div className="mt-2 text-xs text-red-500" data-testid="journal-ocr-error">{ocrError}</div>
          )}
          {ocrResult && (
            <div className="mt-2 text-xs" style={{ color: styles.textSecondary }} data-testid="journal-ocr-summary">
              المورد: {ocrResult.vendor || 'غير محدد'} | الإجمالي: {ocrResult.totals?.grand_total || '—'}
            </div>
          )}
        </div>

          {/* Entry Lines */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold flex items-center gap-2" style={{ color: styles.textPrimary }}>
                <ArrowLeftRight size={16} className="text-blue-300" />
                بنود القيد
              </h3>
              <button
                onClick={addLine}
                className="text-sm text-blue-300 hover:text-blue-200 font-medium flex items-center gap-1"
                data-testid="add-line-btn"
              >
                <Plus size={16} />
                إضافة سطر
              </button>
            </div>

            <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px]" data-testid="entry-debit-credit-color-legend">
              <span className="px-2 py-1 rounded-md" style={{ background: 'rgba(34,197,94,0.16)', color: 'rgba(134,239,172,0.95)', border: '1px solid rgba(34,197,94,0.35)' }}>
                مدين = أخضر
              </span>
              <span className="px-2 py-1 rounded-md" style={{ background: 'rgba(239,68,68,0.14)', color: 'rgba(252,165,165,0.95)', border: '1px solid rgba(239,68,68,0.35)' }}>
                دائن = أحمر
              </span>
            </div>

            <div 
              className="rounded-xl overflow-hidden"
              style={{ border: `1px solid ${styles.cardBorder}` }}
            >
              <div className="md:hidden p-2 space-y-2" data-testid="entry-lines-mobile-list">
                {formData.lines.map((line, idx) => (
                  <div
                    key={`mobile-line-${idx}`}
                    className="rounded-lg border p-2.5 space-y-2"
                    style={{ borderColor: styles.cardBorder, backgroundColor: styles.cardBg }}
                    data-testid={`entry-line-mobile-card-${idx}`}
                  >
                    <div className="space-y-1" data-testid={`line-account-wrapper-mobile-${idx}`}>
                      <SmartAccountSelect
                        entryType={smartOperationType}
                        lineType={getLineFieldKey(line, idx)}
                        operationType={smartOperationType}
                        fieldKey={getLineFieldKey(line, idx)}
                        description={formData.description}
                        includeAll={includeAllAccounts}
                        allAccounts={safeCoaAccounts}
                        compact={true}
                        value={line.account_code}
                        onChange={(nextCode, account) => {
                          setFormData((prev) => {
                            const newLines = [...prev.lines];
                            newLines[idx] = {
                              ...newLines[idx],
                              account_code: nextCode,
                              account_name: account?.name || account?.name_ar || '',
                            };
                            return { ...prev, lines: newLines };
                          });
                        }}
                        placeholder="اختر الحساب"
                        data-testid={`line-account-mobile-${idx}`}
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="number"
                        value={line.debit || ''}
                        onChange={(e) => updateLine(idx, 'debit', e.target.value)}
                        placeholder="مدين"
                        className="w-full px-2.5 py-2 rounded-lg text-xs text-center"
                        style={{
                          backgroundColor: line.account_code ? 'rgba(34,197,94,0.12)' : styles.inputBg,
                          border: `1px solid ${line.account_code ? 'rgba(34,197,94,0.45)' : styles.inputBorder}`,
                          color: styles.textPrimary,
                        }}
                        data-testid={`line-debit-mobile-${idx}`}
                      />
                      <input
                        type="number"
                        value={line.credit || ''}
                        onChange={(e) => updateLine(idx, 'credit', e.target.value)}
                        placeholder="دائن"
                        className="w-full px-2.5 py-2 rounded-lg text-xs text-center"
                        style={{
                          backgroundColor: line.account_code ? 'rgba(239,68,68,0.10)' : styles.inputBg,
                          border: `1px solid ${line.account_code ? 'rgba(239,68,68,0.45)' : styles.inputBorder}`,
                          color: styles.textPrimary,
                        }}
                        data-testid={`line-credit-mobile-${idx}`}
                      />
                    </div>

                    {formData.lines.length > 2 && (
                      <div className="flex justify-end">
                        <button
                          onClick={() => removeLine(idx)}
                          className="p-1.5 rounded-lg hover:bg-white/10 text-rose-300"
                          data-testid={`remove-line-mobile-${idx}`}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <table className="hidden md:table w-full">
                <thead style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)' }}>
                  <tr>
                    <th className="px-4 py-3 text-right text-xs font-semibold" style={{ color: styles.textSecondary }}>الحساب</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold w-32" style={{ color: 'rgba(134,239,172,0.95)' }}>مدين</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold w-32" style={{ color: 'rgba(252,165,165,0.95)' }}>دائن</th>
                    <th className="px-4 py-3 w-12"></th>
                  </tr>
                </thead>
                <tbody>
                  {formData.lines.map((line, idx) => (
                    <tr key={line?.id ?? line?.uid ?? `line-${idx}`} style={{ borderBottom: `1px solid ${styles.cardBorder}` }}>
                      <td className="px-4 py-3">
                        <div className="space-y-1.5" data-testid={`line-account-wrapper-${idx}`}>
                          <SmartAccountSelect
                            entryType={smartOperationType}
                            lineType={getLineFieldKey(line, idx)}
                            operationType={smartOperationType}
                            fieldKey={getLineFieldKey(line, idx)}
                            description={formData.description}
                            includeAll={includeAllAccounts}
                            allAccounts={safeCoaAccounts}
                            compact={true}
                            value={line.account_code}
                            onChange={(nextCode, account) => {
                              setFormData((prev) => {
                                const newLines = [...prev.lines];
                                newLines[idx] = {
                                  ...newLines[idx],
                                  account_code: nextCode,
                                  account_name: account?.name || account?.name_ar || '',
                                };
                                return { ...prev, lines: newLines };
                              });
                            }}
                            placeholder="اختر الحساب"
                            data-testid={`line-account-${idx}`}
                          />
                          <div className="text-[10px]" style={{ color: styles.textMuted }} data-testid={`line-account-filter-label-${idx}`}>
                            الفلتر: {getLineFieldKey(line, idx) === 'credit' ? 'حسابات دائن مرتبطة بالنوع' : 'حسابات مدين مرتبطة بالنوع'}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="number"
                          value={line.debit || ''}
                          onChange={(e) => updateLine(idx, 'debit', e.target.value)}
                          placeholder="0.00"
                          className="w-full px-3 py-2 rounded-lg text-sm text-center"
                          style={{ 
                            backgroundColor: line.account_code ? 'rgba(34,197,94,0.10)' : styles.inputBg,
                            border: `1px solid ${line.account_code ? 'rgba(34,197,94,0.45)' : styles.inputBorder}`,
                            color: styles.textPrimary
                          }}
                          data-testid={`line-debit-${idx}`}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="number"
                          value={line.credit || ''}
                          onChange={(e) => updateLine(idx, 'credit', e.target.value)}
                          placeholder="0.00"
                          className="w-full px-3 py-2 rounded-lg text-sm text-center"
                          style={{ 
                            backgroundColor: line.account_code ? 'rgba(239,68,68,0.10)' : styles.inputBg,
                            border: `1px solid ${line.account_code ? 'rgba(239,68,68,0.45)' : styles.inputBorder}`,
                            color: styles.textPrimary
                          }}
                          data-testid={`line-credit-${idx}`}
                        />
                      </td>
                      <td className="px-4 py-3">
                        {formData.lines.length > 2 && (
                          <button
                            onClick={() => removeLine(idx)}
                            className="p-1.5 rounded-lg hover:bg-white/10 text-rose-300"
                            data-testid={`remove-line-${idx}`}
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)' }}>
                  <tr className="font-bold">
                    <td className="px-4 py-3" style={{ color: styles.textPrimary }}>الإجمالي</td>
                    <td className="px-4 py-3 text-center text-emerald-300">{formatCurrency(totalDebit)}</td>
                    <td className="px-4 py-3 text-center text-rose-300">{formatCurrency(totalCredit)}</td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Balance Check */}
          <div className={`rounded-xl p-4 flex items-center gap-3 border ${
            isBalanced && totalDebit > 0
              ? 'bg-emerald-500/10 border-emerald-400/30' 
              : 'bg-amber-500/10 border-amber-400/30'
          }`}>
            {isBalanced && totalDebit > 0 ? (
              <>
                <div className="p-2 bg-emerald-500/15 rounded-lg">
                  <CheckCircle size={20} className="text-emerald-300" />
                </div>
                <span className="text-emerald-300 font-medium">القيد متوازن ✓</span>
              </>
            ) : (
              <>
                <div className="p-2 bg-amber-500/15 rounded-lg">
                  <Clock size={20} className="text-amber-300" />
                </div>
                <span className="text-amber-300 font-medium">
                  {totalDebit === 0 ? 'أدخل المبالغ' : `فرق: ${formatCurrency(Math.abs(totalDebit - totalCredit))}`}
                </span>
              </>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 flex gap-3" style={{ borderTop: `1px solid ${styles.cardBorder}` }}>
          <button
            onClick={handleSubmit}
            disabled={saving || !isBalanced || totalDebit === 0}
            className="flex-1 py-3 rounded-xl font-medium text-white transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ 
              background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
              boxShadow: '0 4px 14px rgba(37, 99, 235, 0.25)'
            }}
            data-testid="save-entry-btn"
          >
            {saving ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
            ) : (
              <>
                <Save size={18} />
                {entry ? 'حفظ التعديلات' : 'إنشاء القيد'}
              </>
            )}
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-3 rounded-xl font-medium transition-all"
            style={{ 
              backgroundColor: styles.inputBg,
              border: `1px solid ${styles.cardBorder}`,
              color: styles.textSecondary
            }}
          >
            إلغاء
          </button>
        </div>
      </div>
    </div>
  );
}

function DeleteConfirmModal({ entry, onClose, onConfirm, isLight, styles }) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div 
        className="rounded-2xl w-full max-w-md overflow-hidden"
        style={{ 
          backgroundColor: styles.cardBg,
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)' 
        }}
      >
        <div className="p-6 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-rose-100 flex items-center justify-center">
            <Trash2 size={32} className="text-rose-300" />
          </div>
          <h3 className="text-xl font-bold mb-2" style={{ color: styles.textPrimary }}>
            حذف القيد المحاسبي
          </h3>
          <p className="mb-6" style={{ color: styles.textSecondary }}>
            هل أنت متأكد من حذف القيد
            <span className="font-semibold"> {sanitizeEntryText(entry.description || entry.entry_number)} </span>؟
            <br />
            <span className="text-rose-300 text-sm">هذا الإجراء لا يمكن التراجع عنه</span>
          </p>
          
          <div className="flex gap-3">
            <button
              onClick={onConfirm}
              className="flex-1 py-3 rounded-xl font-medium text-white bg-rose-600 hover:bg-rose-700 transition-all flex items-center justify-center gap-2"
              data-testid="confirm-delete-btn"
            >
              <Trash2 size={18} />
              نعم، احذف
            </button>
            <button
              onClick={onClose}
              className="flex-1 py-3 rounded-xl font-medium transition-all"
              style={{ 
                backgroundColor: 'rgba(15, 23, 42, 0.85)',
                color: styles.textSecondary
              }}
              data-testid="cancel-delete-btn"
            >
              إلغاء
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function EntryDetailModal({ entry, onClose, onPrint, isLight, styles }) {
  const safeLines = ensureArray(entry?.lines)
    .map((line) => ensureObject(line))
    .filter(Boolean);

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div 
        className="rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        style={{ 
          backgroundColor: styles.cardBg,
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)' 
        }}
      >
        {/* Header */}
        <div 
          className="p-6"
          style={{ 
            borderBottom: `1px solid ${styles.cardBorder}`,
            background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)'
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-xl bg-white/20 flex items-center justify-center">
                <Receipt size={28} className="text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">{entry.entry_number}</h2>
                <p className="text-white/80 text-sm">{sanitizeEntryText(entry.description || '')}</p>
              </div>
            </div>
            <button 
              onClick={onClose} 
              className="p-2 rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors"
            >
              <XCircle size={24} />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Entry Info */}
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: 'التاريخ', value: formatDate(entry.entry_date), icon: Calendar, iconBg: 'bg-blue-500/15', iconColor: 'text-blue-200' },
              { label: 'النوع', value: entry.source === 'manual' ? 'يدوي' : 'آلي', icon: FileText, iconBg: 'bg-slate-50', iconColor: 'text-slate-600' },
              entry.customer_name && { label: 'العميل', value: entry.customer_name, icon: User, iconBg: 'bg-purple-50', iconColor: 'text-purple-600' },
              entry.vehicle_plate && { label: 'رقم اللوحة', value: entry.vehicle_plate, icon: Wrench, iconBg: 'bg-orange-50', iconColor: 'text-orange-600' },
            ].filter(Boolean).map((item, i) => (
              <div 
                key={item?.label ?? `info-${i}`}
                className="rounded-xl p-4"
                style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)' }}
              >
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg ${item.iconBg} flex items-center justify-center`}>
                    <item.icon size={18} className={item.iconColor} />
                  </div>
                  <div>
                    <p className="text-xs" style={{ color: styles.textSecondary }}>{item.label}</p>
                    <p className="font-semibold" style={{ color: styles.textPrimary }}>
                      {item.value}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Entry Lines */}
          <div>
            <h3 className="font-semibold mb-3 flex items-center gap-2" style={{ color: styles.textPrimary }}>
              <ArrowLeftRight size={16} className="text-blue-300" />
              تفاصيل القيد
            </h3>
            <div 
              className="rounded-xl overflow-hidden"
              style={{ border: `1px solid ${styles.cardBorder}` }}
            >
              <table className="w-full">
                <thead style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)' }}>
                  <tr>
                    <th className="px-4 py-3 text-right text-xs font-semibold" style={{ color: styles.textSecondary }}>الحساب</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold" style={{ color: styles.textSecondary }}>مدين</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold" style={{ color: styles.textSecondary }}>دائن</th>
                  </tr>
                </thead>
                <tbody>
                  {safeLines.map((line, idx) => (
                    <tr key={line?.id ?? `${line?.account_code || 'acc'}-${idx}`} style={{ borderBottom: `1px solid ${styles.cardBorder}` }}>
                      <td className="px-4 py-3" style={{ color: styles.textPrimary }}>
                        <span className="font-mono text-xs bg-blue-500/15 text-blue-200 px-2 py-0.5 rounded ml-2">
                          {line.account_code || '-'}
                        </span>
                        {line.account_name || '—'}
                      </td>
                      <td className="px-4 py-3 text-left font-mono">
                        {Number(line.debit || 0) > 0 ? (
                          <span className="text-emerald-300 font-semibold">{formatCurrency(Number(line.debit || 0))}</span>
                        ) : <span style={{ color: styles.textMuted }}>-</span>}
                      </td>
                      <td className="px-4 py-3 text-left font-mono">
                        {Number(line.credit || 0) > 0 ? (
                          <span className="text-rose-300 font-semibold">{formatCurrency(Number(line.credit || 0))}</span>
                        ) : <span style={{ color: styles.textMuted }}>-</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)' }}>
                  <tr className="font-bold">
                    <td className="px-4 py-3" style={{ color: styles.textPrimary }}>الإجمالي</td>
                    <td className="px-4 py-3 text-left text-emerald-300">{formatCurrency(entry.total_debit)}</td>
                    <td className="px-4 py-3 text-left text-rose-300">{formatCurrency(entry.total_credit)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Balance Check */}
          <div className={`rounded-xl p-4 flex items-center gap-3 ${
            entry.total_debit === entry.total_credit 
              ? 'bg-emerald-500/10 border border-emerald-400/30' 
              : 'bg-rose-500/10 border border-rose-400/30'
          }`}>
            {entry.total_debit === entry.total_credit ? (
              <>
                <div className="p-2 bg-emerald-100 rounded-lg">
                  <CheckCircle size={20} className="text-emerald-300" />
                </div>
                <span className="text-emerald-700 font-medium">القيد متوازن ✓</span>
              </>
            ) : (
              <>
                <div className="p-2 bg-rose-100 rounded-lg">
                  <XCircle size={20} className="text-rose-300" />
                </div>
                <span className="text-rose-700 font-medium">القيد غير متوازن!</span>
              </>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 flex gap-3" style={{ borderTop: `1px solid ${styles.cardBorder}` }}>
          <button
            onClick={() => onPrint(entry)}
            className="flex-1 py-3 rounded-xl font-medium text-white transition-all flex items-center justify-center gap-2"
            style={{ 
              background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
              boxShadow: '0 4px 14px rgba(37, 99, 235, 0.25)'
            }}
          >
            <Printer size={18} />
            طباعة كفاتورة
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-3 rounded-xl font-medium transition-all"
            style={{ 
              backgroundColor: 'rgba(15, 23, 42, 0.85)',
              color: styles.textSecondary
            }}
          >
            إغلاق
          </button>
        </div>
      </div>
    </div>
  );
}