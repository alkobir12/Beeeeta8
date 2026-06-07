/* eslint-disable */

import React, { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { Plus, Trash2, FileText, CreditCard, User, Car, Clock, Camera, Upload, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useToast } from '../hooks/use-toast';
import GuidanceStepper from '../components/GuidanceStepper';
// Floating assistant disabled: AbuFahad floating chat is injected via Layout
import { financeAPI } from '../services/api';
import { generateIdempotencyKey } from '../utils/idempotency';
import { useTheme } from '../contexts/ThemeContext';
import ConfirmPaymentDialog from '../components/ConfirmPaymentDialog';
import SmartAccountSelect from '../components/SmartAccountSelect';
import OperationDetailsModal from '../components/OperationDetailsModal';
import OperationCard from '../components/OperationCard';
import OperationDeleteConfirmDialog from '../components/OperationDeleteConfirmDialog';
import QuickPrintDialog from '../components/QuickPrintDialog';
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { resolveBackendBase } from '../utils/backendBase';
import { resolveVisitDisplay, normalizeAccountCode, LEGACY_TO_NEW_CODE } from '../utils/displayLabels';
import { hasPermission } from '../utils/permissions';
import { RecentOperationsWidget } from '../components/assistant/RecentOperationsWidget';

const API_URL = `${resolveBackendBase()}/api`;
const OPERATIONS_PAGE_SIZE = 15;
const OPERATION_KIND_WORKSHOP = 'WORKSHOP_OPERATION';
const OPERATION_KIND_VEHICLE = 'VEHICLE_OPERATION';
// 🔥 OPERATION_KIND_RAKAN constant kept for backwards-compat only; not exposed in UI.
const OPERATION_KIND_RAKAN = 'RAKAN_PARTS_OPERATION';
const RAKAN_ACCOUNT_CODE_PREFIX = '5000';

const OPERATION_KIND_LABELS = {
  [OPERATION_KIND_WORKSHOP]: 'عملية ورشة',
  [OPERATION_KIND_VEHICLE]: 'عملية مركبة',
};

const OPERATION_KIND_META = {
  [OPERATION_KIND_WORKSHOP]: { icon: '🏭', label: 'عملية ورشة' },
  [OPERATION_KIND_VEHICLE]: { icon: '⚙️', label: 'عملية مركبة' },
};

const OPERATION_TYPE_OPTIONS = [
  { value: 'purchase', label: 'شراء' },
  { value: 'sale', label: 'بيع' },
  { value: 'receipt_voucher', label: 'سند قبض (مركبة)' },
  { value: 'settlement', label: 'تسوية (عميل/مورد)' },
  { value: 'sale_return', label: 'مرتجع بيع' },
  { value: 'purchase_return', label: 'مرتجع شراء' },
  { value: 'payment_order', label: 'سداد مستحقات' },
  { value: 'expense', label: 'مصروف نقدي' },
];

const SALE_LIKE_TYPES = new Set(['sale', 'sale_return']);
const PURCHASE_LIKE_TYPES = new Set(['purchase', 'purchase_return']);
const PAYMENT_ORDER_LIKE_TYPES = new Set(['payment_order', 'receipt_voucher', 'settlement']);
const RECEIPT_VOUCHER_TYPE = 'receipt_voucher';
const SETTLEMENT_TYPE = 'settlement';

const normalizeOperationTypeForBackend = (opType) => (
  PAYMENT_ORDER_LIKE_TYPES.has(opType) ? 'payment_order' : opType
);

const defaultPartnerTypeForOperation = (opType, current = 'customer') => {
  if (SALE_LIKE_TYPES.has(opType)) return 'customer';
  if (PURCHASE_LIKE_TYPES.has(opType)) return 'supplier';
  if (opType === 'expense') return 'supplier';
  if (opType === RECEIPT_VOUCHER_TYPE) return 'customer';
  if (opType === SETTLEMENT_TYPE) return (current === 'supplier' ? 'supplier' : 'customer');
  if (opType === 'payment_order') return current || 'customer';
  return current || 'customer';
};

const PAYMENT_METHOD_OPTIONS = [
  { value: 'cash', label: 'نقدي', icon: '💵' },
  { value: 'transfer', label: 'تحويل', icon: '🏦' },
  { value: 'card', label: 'بطاقة', icon: '💳' },
  { value: 'credit', label: 'آجل', icon: '📄' },
];

const RAKAN_ACCOUNT_KEYWORDS = ['راكان', 'rakan'];
const ACCOUNT_USAGE_CACHE_KEY = 'operations:account-usage:v1';
const ACCOUNT_GROUP_LABELS = new Set([
  'الأصول',
  'الأصول المتداولة',
  'الخصوم',
  'حقوق الملكية',
  'الإيرادات',
  'المصروفات',
  'assets',
  'current assets',
  'liabilities',
  'equity',
  'revenue',
  'expenses',
]);
const UUID_LIKE_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const normalizeText = (value) => String(value || '').trim().toLowerCase();
const normalizeSearchText = (value) => String(value || '')
  .replace(/[٠-٩]/g, (d) => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))
  .replace(/[۰-۹]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
  .replace(/[أإآ]/g, 'ا')
  .replace(/ة/g, 'ه')
  .replace(/ى/g, 'ي')
  .replace(/[\u064B-\u065F\u0670]/g, '')
  .replace(/[^\p{L}\p{N}]+/gu, ' ')
  .trim()
  .toLowerCase();
const compactSearchText = (value) => normalizeSearchText(value).replace(/\s+/g, '');

const getAccountPriorityRank = (account) => {
  const accountName = normalizeText(account?.name_ar || account?.name || account?.code || '');

  if (accountName.includes('البنك')) return 0;
  if (accountName.includes('النقد') || accountName.includes('الصندوق')) return 1;
  if (accountName.includes('فطور العمال')) return 2;
  if (
    accountName.includes('المصروفات التشغيلية')
    || accountName.includes('مصروفات تشغيلية')
    || accountName.includes('مصاريف تشغيلية')
    || accountName.includes('مصروف تشغيل')
  ) {
    return 3;
  }
  if (
    accountName === 'قطع راكان'
    || accountName === 'قطع غيار راكان'
    || accountName.startsWith('قطع غيار راكان')
  ) {
    return 4;
  }
  if (accountName.includes('بنزين غسيل')) return 5;

  return Number.MAX_SAFE_INTEGER;
};

// normalizeAccountCode imported from displayLabels.js

const accountMatchesPreference = (account, preference = {}) => {
  const code = normalizeAccountCode(account?.code || account?.id || '');
  const name = normalizeText(account?.name_ar || account?.name || '');
  const accountType = normalizeText(account?.type || '');

  if (preference.codes?.length && preference.codes.includes(code)) return true;
  if (preference.type && accountType !== normalizeText(preference.type)) return false;
  if (preference.includesAll?.length && preference.includesAll.every((part) => name.includes(normalizeText(part)))) return true;
  if (preference.includesAny?.length && preference.includesAny.some((part) => name.includes(normalizeText(part)))) return true;
  return false;
};

const pickPreferredOperationAccount = (accounts = [], opType = '', partnerType = 'customer') => {
  const preferences = SALE_LIKE_TYPES.has(opType)
    ? [
        { codes: ['025', '026', '027'], type: 'revenue' },
        { includesAll: ['إيرادات', 'الخدمات'], type: 'revenue' },
        { includesAll: ['إيرادات', 'خدمات'], type: 'revenue' },
      ]
    : PAYMENT_ORDER_LIKE_TYPES.has(opType)
      ? (partnerType === 'supplier'
          ? [
              { codes: ['2101'], type: 'liability' },
              { includesAny: ['الموردون', 'مورد'], type: 'liability' },
            ]
          : [
              { codes: ['005'], type: 'asset' },
              { includesAny: ['العملاء'], type: 'asset' },
            ])
      : (PURCHASE_LIKE_TYPES.has(opType) || opType === 'expense')
        ? [
            { codes: ['035'], type: 'expense' },
            { includesAll: ['مصروفات', 'إدارية'], type: 'expense' },
            { includesAll: ['مصروفات', 'عامة'], type: 'expense' },
            { codes: ['036'], type: 'expense' },
          ]
        : [];

  for (const preference of preferences) {
    const match = accounts.find((account) => accountMatchesPreference(account, preference));
    if (match) return match;
  }

  return accounts[0] || null;
};

const isRakanCode = (value) => normalizeAccountCode(value).startsWith(RAKAN_ACCOUNT_CODE_PREFIX);

const isRakanBusinessAccount = (account) => {
  const haystack = [account?.name, account?.code].map((v) => normalizeText(v)).join(' ');
  return isRakanCode(account?.code) || RAKAN_ACCOUNT_KEYWORDS.some((k) => haystack.includes(k));
};

const isRakanChartAccount = (account) => {
  if (isRakanCode(account?.code)) return true;
  const haystack = [account?.name_ar, account?.name, account?.code, account?.category]
    .map((v) => normalizeText(v))
    .join(' ');
  return RAKAN_ACCOUNT_KEYWORDS.some((k) => haystack.includes(k));
};

const isRakanOperationTagged = (operation = {}) => {
  const scope = normalizeText(operation.scope);
  const source = normalizeText(operation.source);
  const businessUnit = normalizeText(operation.businessUnit || operation.business_unit);
  const notes = normalizeText(operation.notes);
  return (
    scope === 'rakan_parts' ||
    source === 'rakan_parts_pos' ||
    businessUnit === 'rakan_parts' ||
    notes.includes('[rakan_parts]') ||
    notes.includes('account_code:5000')
  );
};

const Operations = () => {
  const { t, i18n } = useTranslation();
  const { themeName } = useTheme();
  const isLight = false; // keep dark/glass look for operations page
  const isRTL = i18n.language === 'ar';
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const session = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem('session'));
    } catch (e) {
      return null;
    }
  }, []);
  const canSettleOperations = hasPermission(session, 'operations', 'settle');
  const canEditOperations = hasPermission(session, 'operations', 'edit');
  const canDeleteOperations = hasPermission(session, 'operations', 'delete');
  const guidanceEnabled = session?.guidanceEnabled !== false;
  const [selectedOperation, setSelectedOperation] = useState(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [editingOperationId, setEditingOperationId] = useState(null);

  const [saveOpId, setSaveOpId] = useState(null);
  const [deleteOpId, setDeleteOpId] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const lastSubmitRef = useRef({ hash: '', timestamp: 0 });
  const formRef = useRef(null);

  const [createError, setCreateError] = useState('');
  const [accountUsageVersion, setAccountUsageVersion] = useState(0);
  const [integrityMap, setIntegrityMap] = useState({});
  const [integritySummary, setIntegritySummary] = useState({ total: 0, ok: 0, warnings: 0, duplicates: 0 });
  const [integrityLoading, setIntegrityLoading] = useState(false);

  const [form, setForm] = useState({ 
    accountId: '', 
    accountingAccountId: '',
    operationKind: OPERATION_KIND_WORKSHOP,
    vehicleId: '',
    visitId: '',
    // scope: يحدد هل العملية مرتبطة بمركبة أم عملية عامة للورشة
    scope: 'workshop', // 'vehicle' | 'workshop'
    type: 'purchase', 
    partnerType: 'supplier', 
    partnerId: '',
    partnerName: '', 
    partnerPhone: '',
    items: [], 
    paymentMethod: 'cash', 
    paymentStatus: 'paid',
    paymentAmount: '',
    status: 'issued',
    invoiceNumber: '',
    notes: '',
    // تاريخ العملية (افتراضي اليوم)
    date: new Date().toISOString().split('T')[0],

    paymentReceipt: null,
  });

  const operationsSteps = useMemo(() => (
    [
      {
        id: 'account',
        title: 'اختيار الحساب والطرف',
        hint: 'اختر الحساب واسم المورد/العميل قبل المتابعة.',
        done: Boolean(form.accountingAccountId),
      },
      {
        id: 'items',
        title: 'إضافة البنود',
        hint: 'أضف البنود والكميات والأسعار بدقة.',
        done: form.items.length > 0,
      },
      {
        id: 'payment',
        title: 'تأكيد السداد',
        hint: 'حدد طريقة السداد أو أرفق إيصالًا إن وجد.',
        done: Boolean(form.paymentMethod),
      },
    ].filter((step) => step.id !== 'payment' || canSettleOperations)
  ), [form.accountingAccountId, form.items.length, form.paymentMethod, canSettleOperations]);

  const operationsSubtitle = form.operationKind === OPERATION_KIND_WORKSHOP
    ? 'أنت تنشئ عملية ورشة تشغيلية مستقلة عن المركبات. راجع القيد قبل الحفظ.'
    : form.operationKind === OPERATION_KIND_VEHICLE
      ? 'عملية مرتبطة بمركبة: سيتم ربط العميل تلقائياً من بيانات المركبة.'
      : 'عملية قطع راكان: يجب ربطها بعميل أو مركبة وتُفصل ماليًا عن الورشة.';
  const [item, setItem] = useState({ 
    itemType: 'part', 
    itemId: '', 
    name: '', 
    customName: '',
    quantity: 1, 
    price: 0 
  });

  const [ocrImage, setOcrImage] = useState('');
  const [ocrPreview, setOcrPreview] = useState('');
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [ocrError, setOcrError] = useState('');
  const [ocrInvoiceType, setOcrInvoiceType] = useState(form.type || 'purchase');

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState(null);

  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [activeOperationsTab, setActiveOperationsTab] = useState('workshop');
  const [operationsSearchQuery, setOperationsSearchQuery] = useState('');
  const [fallbackOperations, setFallbackOperations] = useState([]);
  const operationsBootstrapStartedRef = useRef(false);
  const [rakanPage, setRakanPage] = useState(1);
  const [workshopPage, setWorkshopPage] = useState(1);
  const [creditReminderDays, setCreditReminderDays] = useState(() => {
    if (typeof window === 'undefined') return 7;
    const stored = window.localStorage.getItem('creditReminderDays');
    const parsed = stored ? Number(stored) : 7;
    return Number.isNaN(parsed) || parsed <= 0 ? 7 : parsed;
  });
  const [expandedOperationId, setExpandedOperationId] = useState(null);
  const [printDialogOpen, setPrintDialogOpen] = useState(false);
  const [printDialogConfig, setPrintDialogConfig] = useState(null);
  const [createFormTab, setCreateFormTab] = useState('operation');

  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const vehicleIdFromUrl = searchParams.get('vehicleId');
  const vehiclePlateFromUrl = searchParams.get('plate');
  // 🆕 Bot deep-link: /operations?focus=<op_id> → expand + scroll to that op.
  const focusOpFromUrl = searchParams.get('focus');
  const workshopId = process.env.REACT_APP_WORKSHOP_ID;
  const [isDeferredDataEnabled, setIsDeferredDataEnabled] = useState(false);
  const freshQueryOptions = {
    staleTime: 3 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    retry: 1,
  };

  const operationsCacheKey = React.useMemo(
    () => `operationsCache:${vehicleIdFromUrl || 'all'}`,
    [vehicleIdFromUrl]
  );
  const operationsCacheUpdatedAtKey = React.useMemo(
    () => `operationsCacheUpdatedAt:${vehicleIdFromUrl || 'all'}`,
    [vehicleIdFromUrl]
  );
  const cachedOperations = React.useMemo(() => {
    if (typeof window === 'undefined') return [];
    try {
      const updatedAt = localStorage.getItem(operationsCacheUpdatedAtKey);
      if (updatedAt) {
        const ageMs = Date.now() - new Date(updatedAt).getTime();
        if (Number.isFinite(ageMs) && ageMs > 1000 * 60 * 60 * 12) {
          return [];
        }
      }
      const cached = localStorage.getItem(operationsCacheKey);
      return cached ? JSON.parse(cached) : [];
    } catch (error) {
      return [];
    }
  }, [operationsCacheKey, operationsCacheUpdatedAtKey]);

  const cachedChartAccounts = React.useMemo(() => {
    if (typeof window === 'undefined') return [];
    try {
      const cached = localStorage.getItem('chartAccountsCache:all');
      const parsed = cached ? JSON.parse(cached) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }, []);

  const accountsQuery = useQuery({
    queryKey: ['chart-of-accounts', workshopId],
    queryFn: async () => {
      let accountsData = [];

      try {
        const ledgerAccountsRes = await axios.get(`${API_URL}/accounts`, { timeout: 5000 });
        accountsData = Array.isArray(ledgerAccountsRes?.data) ? ledgerAccountsRes.data : [];
      } catch (error) {
        accountsData = [];
      }

      if (!accountsData.length) {
        try {
          const chartAccRes = await financeAPI.getChartOfAccounts();
          const chartPayload = chartAccRes?.data;
          if (chartPayload?.success && Array.isArray(chartPayload?.data)) {
            accountsData = chartPayload.data;
          } else if (Array.isArray(chartPayload?.data)) {
            accountsData = chartPayload.data;
          } else if (Array.isArray(chartPayload)) {
            accountsData = chartPayload;
          } else if (Array.isArray(chartPayload?.accounts)) {
            accountsData = chartPayload.accounts;
          }
        } catch (error) {
          accountsData = [];
        }
      }

      const unique = [];
      const seen = new Set();
      (Array.isArray(accountsData) ? accountsData : []).forEach((account) => {
        const displayName = String(account?.name_ar || account?.name || '').trim();
        if (!displayName || UUID_LIKE_REGEX.test(displayName)) return;
        const key = normalizeText(account?.id || account?.code || displayName);
        if (!key || seen.has(key)) return;
        seen.add(key);
        unique.push({
          ...account,
          name: account?.name || account?.name_ar || displayName,
          name_ar: account?.name_ar || account?.name || displayName,
        });
      });

      if (typeof window !== 'undefined' && unique.length > 0) {
        localStorage.setItem('chartAccountsCache:all', JSON.stringify(unique));
      }

      return unique;
    },
    initialData: cachedChartAccounts.length ? cachedChartAccounts : undefined,
    enabled: true,
    ...freshQueryOptions,
  });

  const partsQuery = useQuery({
    queryKey: ['parts'],
    queryFn: async () => {
      const res = await axios.get(`${API_URL}/parts`);
      return res.data || [];
    },
    enabled: true,
    ...freshQueryOptions,
  });

  const servicesQuery = useQuery({
    queryKey: ['services'],
    queryFn: async () => {
      const res = await axios.get(`${API_URL}/services`);
      return res.data || [];
    },
    enabled: isDeferredDataEnabled,
    ...freshQueryOptions,
  });

  const customersQuery = useQuery({
    queryKey: ['customers'],
    queryFn: async () => {
      const res = await axios.get(`${API_URL}/customers`);
      return res.data || [];
    },
    enabled: isDeferredDataEnabled,
    ...freshQueryOptions,
  });

  const suppliersQuery = useQuery({
    queryKey: ['suppliers'],
    queryFn: async () => {
      const res = await axios.get(`${API_URL}/suppliers`);
      return res.data || [];
    },
    enabled: isDeferredDataEnabled,
    ...freshQueryOptions,
  });

  const vehiclesQuery = useQuery({
    queryKey: ['vehicles'],
    queryFn: async () => {
      const res = await axios.get(`${API_URL}/vehicles`);
      return res.data || [];
    },
    enabled: isDeferredDataEnabled,
    ...freshQueryOptions,
  });

  const operationsQuery = useQuery({
    queryKey: ['operations', workshopId || 'default', vehicleIdFromUrl || 'all'],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: '200' });
      if (vehicleIdFromUrl) params.set('vehicle_id', vehicleIdFromUrl);
      const res = await fetch(`${API_URL}/operations?${params.toString()}`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`operations-fetch-${res.status}`);
      const data = await res.json();
      if (Array.isArray(data)) {
        try {
          localStorage.setItem(operationsCacheKey, JSON.stringify(data));
          localStorage.setItem(operationsCacheUpdatedAtKey, new Date().toISOString());
        } catch (e) {
          // ignore cache write errors
        }
      }
      return data || [];
    },
    staleTime: 30 * 1000,
    refetchOnWindowFocus: false,
    refetchOnMount: true,
    keepPreviousData: true,
    initialData: cachedOperations.length ? cachedOperations : undefined,
    placeholderData: cachedOperations.length ? cachedOperations : undefined,
  });

  if (typeof window !== 'undefined' && !fallbackOperations.length && !cachedOperations.length && !operationsBootstrapStartedRef.current) {
    operationsBootstrapStartedRef.current = true;
    const params = new URLSearchParams({ limit: '200' });
    if (vehicleIdFromUrl) params.set('vehicle_id', vehicleIdFromUrl);
    fetch(`${API_URL}/operations?${params.toString()}`, { cache: 'no-store' })
      .then((res) => res.json())
      .then((data) => {
        if (!Array.isArray(data)) return;
        setFallbackOperations(data);
        try {
          localStorage.setItem(operationsCacheKey, JSON.stringify(data));
          localStorage.setItem(operationsCacheUpdatedAtKey, new Date().toISOString());
        } catch (e) {
          // ignore cache write errors
        }
      })
      .catch(() => {
        operationsBootstrapStartedRef.current = false;
      });
  }

  useEffect(() => {
    let mounted = true;
    const loadFallbackOperations = async () => {
      try {
        const params = new URLSearchParams({ limit: '200' });
        if (vehicleIdFromUrl) params.set('vehicle_id', vehicleIdFromUrl);
        const res = await fetch(`${API_URL}/operations?${params.toString()}`, { cache: 'no-store' });
        const data = await res.json();
        if (!mounted || !Array.isArray(data)) return;
        setFallbackOperations(data);
        try {
          localStorage.setItem(operationsCacheKey, JSON.stringify(data));
          localStorage.setItem(operationsCacheUpdatedAtKey, new Date().toISOString());
        } catch (e) {
          // ignore cache write errors
        }
      } catch (e) {
        if (mounted) setFallbackOperations([]);
      }
    };
    loadFallbackOperations();
    return () => {
      mounted = false;
    };
  }, [vehicleIdFromUrl, operationsCacheKey, operationsCacheUpdatedAtKey]);

  useEffect(() => {
    if (isDeferredDataEnabled) return;
    if (operationsQuery.isSuccess || cachedOperations.length > 0) {
      setIsDeferredDataEnabled(true);
      return;
    }
    const timer = window.setTimeout(() => {
      setIsDeferredDataEnabled(true);
    }, 200);
    return () => window.clearTimeout(timer);
  }, [isDeferredDataEnabled, operationsQuery.isSuccess, cachedOperations.length]);

  // 🔄 إعادة التحديث عند أي عملية مالية في صفحة أخرى (POS / تأكيد سداد / تسوية مورد)
  useEffect(() => {
    const onFinUpdated = () => {
      try {
        // invalidate + force refetch لضمان ظهور التحديث فوراً في الواجهة
        queryClient.invalidateQueries({ queryKey: ['operations'] });
        queryClient.invalidateQueries({ queryKey: ['biz-accounts'] });
        queryClient.refetchQueries({ queryKey: ['operations'], type: 'active' });
      } catch (e) {
        console.warn('finance:updated invalidate failed', e);
      }
    };
    window.addEventListener('finance:updated', onFinUpdated);
    return () => window.removeEventListener('finance:updated', onFinUpdated);
  }, [queryClient]);

  const bizAccountsQuery = useQuery({
    queryKey: ['biz-accounts'],
    queryFn: async () => {
      const res = await axios.get(`${API_URL}/biz-accounts`);
      return res.data || [];
    },
    enabled: true,
    ...freshQueryOptions,
  });

  const updateOperationMutation = useMutation({
    mutationFn: async ({ opId, payload }) => {
      const res = await axios.put(`${API_URL}/operations/${opId}`, payload);
      return res.data;
    },
    onSuccess: (updatedOp, variables) => {
      queryClient.setQueriesData({ queryKey: ['operations'] }, (old) => {
        if (Array.isArray(old)) {
          return old.map((op) => (String(op?.id) === String(variables?.opId) ? { ...op, ...(updatedOp || {}) } : op));
        }
        return old;
      });
      queryClient.invalidateQueries({ queryKey: ['operations'], refetchType: 'inactive' });
      toast({
        title: t('common.success'),
        description: t('operations.saved_successfully') || 'تم حفظ العملية',
      });
    },
    onError: (e) => {
      const detail = e?.response?.data?.detail || e?.message;
      toast({
        title: t('common.error'),
        description: detail || t('operations.save_failed') || 'فشل حفظ العملية',
        variant: 'destructive',
      });
    },
  });

  const activeVehicleId = form.operationKind !== OPERATION_KIND_WORKSHOP
    ? (form.vehicleId || vehicleIdFromUrl)
    : '';

  const visitsQuery = useQuery({
    queryKey: ['vehicle-visits', activeVehicleId || 'none'],
    queryFn: async () => {
      if (!activeVehicleId) return [];
      const res = await axios.get(`${API_URL}/vehicles/${activeVehicleId}/visits`);
      return res.data || [];
    },
    enabled: Boolean(activeVehicleId) && isDeferredDataEnabled
  });

  const accounts = accountsQuery.data || [];
  const accountsLoading = (!accounts.length) && (accountsQuery.isLoading || accountsQuery.isFetching);
  const bizAccounts = bizAccountsQuery.data || [];
  const rakanBizAccount = useMemo(
    () => bizAccounts.find((account) => isRakanBusinessAccount(account)) || null,
    [bizAccounts]
  );
  const workshopBizAccount = useMemo(() => {
    const nonRakan = bizAccounts.filter((account) => !isRakanBusinessAccount(account));
    if (!nonRakan.length) return null;
    const preferred = nonRakan.find((account) => {
      const text = `${normalizeText(account.name)} ${normalizeText(account.code)}`;
      return ['main', 'الرئيس', 'الرئيسي', 'workshop', 'default'].some((k) => text.includes(k));
    });
    return preferred || nonRakan[0] || null;
  }, [bizAccounts]);

  const selectedBusinessAccount = useMemo(() => {
    if (form.operationKind === OPERATION_KIND_RAKAN) {
      return rakanBizAccount;
    }
    return workshopBizAccount || rakanBizAccount || null;
  }, [form.operationKind, rakanBizAccount, workshopBizAccount]);

  const rakanBizAccountIds = useMemo(
    () => new Set((bizAccounts || [])
      .filter((account) => isRakanBusinessAccount(account))
      .map((account) => String(account.id || account.code || '').trim())
      .filter(Boolean)),
    [bizAccounts]
  );
  const rakanChartAccountIds = useMemo(
    () => new Set((accounts || [])
      .filter((account) => isRakanChartAccount(account))
      .map((account) => String(account.id || account.code || '').trim())
      .filter(Boolean)),
    [accounts]
  );
  const operationsForRanking = (Array.isArray(operationsQuery.data) && operationsQuery.data.length)
    ? operationsQuery.data
    : (cachedOperations.length ? cachedOperations : fallbackOperations);
  const accountUsageStats = useMemo(() => {
    const usage = new Map();
    const lastUsed = new Map();

    (operationsForRanking || []).forEach((op) => {
      const rawId = String(op?.accountingAccountId || op?.accountId || '').trim();
      if (!rawId) return;

      const keyVariants = [
        normalizeText(rawId),
        normalizeText(normalizeAccountCode(rawId)),
      ].filter(Boolean);

      keyVariants.forEach((key) => {
        usage.set(key, (usage.get(key) || 0) + 1);
      });

      const ts = new Date(op?.date || op?.createdAt || op?.created_at || 0).getTime();
      if (!Number.isFinite(ts)) return;
      keyVariants.forEach((key) => {
        const prev = lastUsed.get(key) || 0;
        if (ts > prev) lastUsed.set(key, ts);
      });
    });

    if (typeof window !== 'undefined') {
      try {
        const cachedRaw = localStorage.getItem(ACCOUNT_USAGE_CACHE_KEY);
        const cached = cachedRaw ? JSON.parse(cachedRaw) : {};
        Object.entries(cached || {}).forEach(([key, info]) => {
          const normalizedKey = normalizeText(key);
          if (!normalizedKey) return;
          const count = Number(info?.count || 0);
          const usedAt = Number(info?.lastUsed || 0);
          if (count > 0) usage.set(normalizedKey, (usage.get(normalizedKey) || 0) + count);
          if (usedAt > (lastUsed.get(normalizedKey) || 0)) lastUsed.set(normalizedKey, usedAt);
        });
      } catch (_error) {
        // ignore local usage cache parse errors
      }
    }

    return { usage, lastUsed };
  }, [operationsForRanking, accountUsageVersion]);

  const filteredAccounts = useMemo(() => {
    const typeScoped = accounts.filter((account) => {
      const accountType = String(account?.type || '').toLowerCase();
      if (SALE_LIKE_TYPES.has(form.type)) return accountType === 'revenue';
      if (PURCHASE_LIKE_TYPES.has(form.type)) return ['expense', 'asset', 'liability'].includes(accountType);
      if (form.type === 'expense') return ['expense', 'asset'].includes(accountType);
      if (PAYMENT_ORDER_LIKE_TYPES.has(form.type)) return ['asset', 'liability', 'expense'].includes(accountType);
      return true;
    });

    const cleaned = typeScoped.filter((account) => {
      const accountId = String(account?.id || account?.code || '').trim();
      const accountName = normalizeText(account?.name_ar || account?.name);
      const accountCode = normalizeAccountCode(account?.code || accountId);

      const isGroupLabel = ACCOUNT_GROUP_LABELS.has(accountName);
      const isPartnerSubAccount =
        accountId.startsWith('acc-customer-')
        || accountId.startsWith('acc-supplier-')
        || accountCode.startsWith('1103')   // legacy AR
        || accountCode.startsWith('005')    // جديد: العملاء
        || accountCode.startsWith('2101')
        || accountName.startsWith('عميل -')
        || accountName.startsWith('مورد -')
        || accountName.includes('حساب العملاء')
        || accountName.includes('حساب الموردين');

      return !(isGroupLabel || isPartnerSubAccount);
    });

    const base = cleaned.length > 0 ? cleaned : typeScoped;

    const sorted = [...base].sort((a, b) => {
      const aPriorityRank = getAccountPriorityRank(a);
      const bPriorityRank = getAccountPriorityRank(b);
      if (aPriorityRank !== bPriorityRank) return aPriorityRank - bPriorityRank;

      const buildKeys = (account) => {
        const rawId = String(account?.id || '').trim();
        const rawCode = String(account?.code || '').trim();
        return [
          normalizeText(rawId),
          normalizeText(rawCode),
          normalizeText(normalizeAccountCode(rawId)),
          normalizeText(normalizeAccountCode(rawCode)),
        ].filter(Boolean);
      };

      const pickMax = (mapRef, keys) => keys.reduce((max, key) => Math.max(max, mapRef.get(key) || 0), 0);
      const aKeys = buildKeys(a);
      const bKeys = buildKeys(b);

      const aLast = pickMax(accountUsageStats.lastUsed, aKeys);
      const bLast = pickMax(accountUsageStats.lastUsed, bKeys);
      if (bLast !== aLast) return bLast - aLast;

      const aUsage = pickMax(accountUsageStats.usage, aKeys);
      const bUsage = pickMax(accountUsageStats.usage, bKeys);
      if (bUsage !== aUsage) return bUsage - aUsage;

      const aCode = normalizeAccountCode(a?.code || a?.id || '');
      const bCode = normalizeAccountCode(b?.code || b?.id || '');
      return String(aCode).localeCompare(String(bCode), 'ar');
    });

    // علامة "_recentlyUsed" لأول 3 حسابات ذات استخدام حديث
    const topUsedSet = new Set(
      sorted
        .filter(a => {
          const keys = [String(a.id||''), String(a.code||'')];
          return keys.some(k => accountUsageStats.lastUsed.get(k) > 0);
        })
        .slice(0, 3)
        .map(a => a.id || a.code)
    );
    return sorted.map(a => ({ ...a, _recentlyUsed: topUsedSet.has(a.id || a.code) }));
  }, [accounts, form.type, accountUsageStats]);
  const selectedAccountingAccount = useMemo(
    () => accounts.find((account) => String(account.id || account.code) === String(form.accountingAccountId || '')) || null,
    [accounts, form.accountingAccountId]
  );
  const selectedAccountingCode = normalizeAccountCode(selectedAccountingAccount?.code || form.accountingAccountId || '');
  const isSelectedAccountingRakan = isRakanCode(selectedAccountingCode);
  const recordAccountUsage = (accountIdOrCode) => {
    const raw = String(accountIdOrCode || '').trim();
    if (!raw || typeof window === 'undefined') return;

    const matched = accounts.find((acc) => String(acc?.id || acc?.code || '') === raw) || null;
    const keyVariants = [
      normalizeText(raw),
      normalizeText(normalizeAccountCode(raw)),
      normalizeText(matched?.code),
      normalizeText(normalizeAccountCode(matched?.code)),
      normalizeText(matched?.id),
    ].filter(Boolean);

    try {
      const cacheRaw = localStorage.getItem(ACCOUNT_USAGE_CACHE_KEY);
      const cache = cacheRaw ? JSON.parse(cacheRaw) : {};
      const now = Date.now();
      keyVariants.forEach((key) => {
        const prev = cache[key] || { count: 0, lastUsed: 0 };
        cache[key] = {
          count: Number(prev.count || 0) + 1,
          lastUsed: Math.max(Number(prev.lastUsed || 0), now),
        };
      });
      localStorage.setItem(ACCOUNT_USAGE_CACHE_KEY, JSON.stringify(cache));
      setAccountUsageVersion((v) => v + 1);
    } catch (_error) {
      // ignore cache write errors
    }
  };
  const parts = partsQuery.data || [];
  const services = servicesQuery.data || [];
  const normalizeItemId = (it) => it?.id || it?._id || '';
  const resolveItemPrice = (selectedItem, itemType, operationType) => {
    if (!selectedItem) return 0;
    const sellingPrice =
      selectedItem.sellingPrice ??
      selectedItem.sell_price ??
      selectedItem.sale_price ??
      selectedItem.sellPrice ??
      selectedItem.price ??
      0;
    const purchasePrice =
      selectedItem.purchasePrice ??
      selectedItem.purchase_price ??
      selectedItem.cost_price ??
      selectedItem.buy_price ??
      selectedItem.price ??
      0;

    if (itemType === 'part') {
      return SALE_LIKE_TYPES.has(operationType) ? sellingPrice : purchasePrice;
    }
    return selectedItem.price ?? sellingPrice ?? purchasePrice ?? 0;
  };
  const itemOptions = useMemo(() => {
    const source = item.itemType === 'service' ? services : parts;
    return source.map((it) => ({
      id: normalizeItemId(it),
      name: it.name,
      raw: it,
    }));
  }, [item.itemType, parts, services]);

  const customers = customersQuery.data || [];
  const suppliers = suppliersQuery.data || [];
  const vehicles = vehiclesQuery.data || [];
  const partnerOptions = useMemo(() => {
    const source = form.partnerType === 'supplier' ? suppliers : customers;
    return (source || []).map((it) => ({
      id: it.id || it._id || '',
      name: it.name || '',
      phone: it.phone || '',
    }));
  }, [form.partnerType, suppliers, customers]);
  const activeVehicles = useMemo(
    () => vehicles.filter((vehicle) => !['delivered', 'completed', 'finished', 'تم التسليم', 'مكتمل'].includes(vehicle.status)),
    [vehicles]
  );
  const vehicleOptions = useMemo(
    () => (activeVehicles.length ? activeVehicles : vehicles),
    [activeVehicles, vehicles]
  );
  const customerVehicles = useMemo(() => {
    if (!form.partnerId) return vehicleOptions;
    const list = vehicleOptions.filter((vehicle) => String(vehicle.customerId || '') === String(form.partnerId || ''));
    return list.length ? list : vehicleOptions;
  }, [vehicleOptions, form.partnerId]);
  const ops = operationsForRanking;
  const operationsLoading = (!ops.length) && (operationsQuery.isLoading || operationsQuery.isFetching);

  const ensureOperationsLoaded = useCallback(async (force = false) => {
    if (!force && (ops.length || fallbackOperations.length || cachedOperations.length)) return;
    try {
      const params = new URLSearchParams({ limit: '200' });
      if (vehicleIdFromUrl) params.set('vehicle_id', vehicleIdFromUrl);
      const res = await fetch(`${API_URL}/operations?${params.toString()}`, { cache: 'no-store' });
      const data = await res.json();
      if (!Array.isArray(data)) return;
      setFallbackOperations(data);
      try {
        localStorage.setItem(operationsCacheKey, JSON.stringify(data));
        localStorage.setItem(operationsCacheUpdatedAtKey, new Date().toISOString());
      } catch (e) {
        // ignore cache write errors
      }
    } catch (e) {
      // keep existing loading state
    }
  }, [ops.length, fallbackOperations.length, cachedOperations.length, vehicleIdFromUrl, operationsCacheKey, operationsCacheUpdatedAtKey]);

  const handleOperationsSearchChange = useCallback((event) => {
    setOperationsSearchQuery(event.target.value);
    if (event.target.value.trim()) ensureOperationsLoaded(true);
    else ensureOperationsLoaded(false);
  }, [ensureOperationsLoaded]);
  const visits = visitsQuery.data || [];

  const vehicleSearchById = useMemo(() => {
    const map = new Map();
    (vehicles || []).forEach((vehicle) => {
      const vehicleId = String(vehicle.id || vehicle._id || '').trim();
      if (!vehicleId) return;
      map.set(vehicleId, [
        vehicle.fileNumber,
        vehicle.file_number,
        vehicle.customerFileNumber,
        vehicle.customer_file_number,
        vehicle.customerName,
        vehicle.ownerName,
        vehicle.plateNumber,
        vehicle.plate_number,
        vehicle.brand,
        vehicle.model,
        vehicle.year,
        vehicle.status,
        vehicleId,
      ].filter(Boolean).join(' '));
    });
    return map;
  }, [vehicles]);

  const operationMatchesSearch = useCallback((op) => {
    const normalizedQuery = normalizeSearchText(operationsSearchQuery);
    const compactQuery = compactSearchText(operationsSearchQuery);
    if (!normalizedQuery) return true;
    const itemsText = Array.isArray(op.items)
      ? op.items.map((it) => [it.name, it.customName, it.description, it.itemType].filter(Boolean).join(' ')).join(' ')
      : '';
    const vehicleId = String(op.vehicleId || op.vehicle_id || '').trim();
    const haystack = [
      op.id,
      op._id,
      op.invoiceNumber,
      op.invoice_number,
      op.operationNumber,
      op.operation_number,
      op.type,
      op.source,
      op.partnerName,
      op.customerName,
      op.supplierName,
      op.partnerId,
      op.vehiclePlate,
      op.vehicle_plate,
      op.vehicleBrand,
      op.vehicle_brand,
      op.vehicleModel,
      op.vehicle_model,
      op.visitNumber,
      op.visitNumberDisplay,
      op.accountName,
      op.account_name,
      op.notes,
      op.total,
      op.balance,
      itemsText,
      vehicleSearchById.get(vehicleId),
    ].filter(Boolean).join(' ');
    const normalizedHaystack = normalizeSearchText(haystack);
    const compactHaystack = compactSearchText(haystack);
    return normalizedHaystack.includes(normalizedQuery) || (compactQuery && compactHaystack.includes(compactQuery));
  }, [operationsSearchQuery, vehicleSearchById]);

  const sortedOps = useMemo(() => {
    const arr = Array.isArray(ops) ? [...ops] : [];
    const getTs = (o) => {
      try {
        return new Date(
          o.date
          || o.op_date
          || o.createdAt
          || o.created_at
          || o.updatedAt
          || o.updated_at
          || 0
        ).getTime() || 0;
      } catch {
        return 0;
      }
    };
    // Smart order (CEO view): newest first, then higher absolute total
    arr.sort((a, b) => {
      const dt = getTs(b) - getTs(a);
      if (dt !== 0) return dt;
      const at = Math.abs(Number(b.total || 0)) - Math.abs(Number(a.total || 0));
      if (at !== 0) return at;
      return String(b.id || b._id || '').localeCompare(String(a.id || a._id || ''));
    });
    return arr;
  }, [ops]);

  const searchableOps = useMemo(
    () => sortedOps.filter(operationMatchesSearch),
    [sortedOps, operationMatchesSearch]
  );

  const rakanOps = useMemo(
    () => searchableOps.filter((op) => (
      rakanBizAccountIds.has(String(op.accountId || ''))
      || rakanChartAccountIds.has(String(op.accountingAccountId || op.accountId || ''))
      || isRakanOperationTagged(op)
    )),
    [searchableOps, rakanBizAccountIds, rakanChartAccountIds]
  );

  const workshopOps = useMemo(
    () => searchableOps.filter((op) => !(
      rakanBizAccountIds.has(String(op.accountId || ''))
      || rakanChartAccountIds.has(String(op.accountingAccountId || op.accountId || ''))
      || isRakanOperationTagged(op)
    )),
    [searchableOps, rakanBizAccountIds, rakanChartAccountIds]
  );

  const getCreditSummary = (opsList) => {
    const now = new Date();
    const msDay = 1000 * 60 * 60 * 24;
    return opsList.reduce(
      (acc, op) => {
        const paymentStatus = (op.paymentStatus || op.payment_status || '').toString().toLowerCase();
        const paymentMethod = (op.paymentMethod || op.payment_method || '').toString().toLowerCase();
        const isCredit = paymentStatus === 'unpaid' || paymentMethod === 'credit';
        if (!isCredit) return acc;
        acc.total += 1;
        const opDate = new Date(op.date || op.op_date || op.createdAt || op.created_at || 0);
        if (!Number.isNaN(opDate.getTime())) {
          const diffDays = Math.floor((now - opDate) / msDay);
          if (diffDays >= creditReminderDays) {
            acc.overdue += 1;
          }
        }
        return acc;
      },
      { total: 0, overdue: 0 }
    );
  };

  const workshopCreditSummary = useMemo(
    () => getCreditSummary(workshopOps),
    [workshopOps, creditReminderDays]
  );

  const rakanCreditSummary = useMemo(
    () => getCreditSummary(rakanOps),
    [rakanOps, creditReminderDays]
  );

  const rakanTotalPages = useMemo(
    () => Math.max(1, Math.ceil(rakanOps.length / OPERATIONS_PAGE_SIZE)),
    [rakanOps.length]
  );

  const workshopTotalPages = useMemo(
    () => Math.max(1, Math.ceil(workshopOps.length / OPERATIONS_PAGE_SIZE)),
    [workshopOps.length]
  );

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('creditReminderDays', String(creditReminderDays));
    }
  }, [creditReminderDays]);

  useEffect(() => {
    setRakanPage((prev) => Math.min(Math.max(prev, 1), rakanTotalPages));
  }, [rakanTotalPages]);

  useEffect(() => {
    setWorkshopPage((prev) => Math.min(Math.max(prev, 1), workshopTotalPages));
  }, [workshopTotalPages]);

  // Collapse the expanded card when the user switches tab/page/search — but
  // never collapse the bot deep-link focus op (?focus=), so it survives the
  // automatic pagination/tab settling that happens right after data loads.
  useEffect(() => {
    setExpandedOperationId((prev) => (prev && prev === focusOpFromUrl ? prev : null));
  }, [activeOperationsTab, rakanPage, workshopPage, operationsSearchQuery, focusOpFromUrl]);

  useEffect(() => {
    setRakanPage(1);
    setWorkshopPage(1);
  }, [operationsSearchQuery]);

  const paginatedRakanOps = useMemo(() => {
    const start = (rakanPage - 1) * OPERATIONS_PAGE_SIZE;
    return rakanOps.slice(start, start + OPERATIONS_PAGE_SIZE);
  }, [rakanOps, rakanPage]);

  const paginatedWorkshopOps = useMemo(() => {
    const start = (workshopPage - 1) * OPERATIONS_PAGE_SIZE;
    return workshopOps.slice(start, start + OPERATIONS_PAGE_SIZE);
  }, [workshopOps, workshopPage]);

  const isRakanTabActive = activeOperationsTab === 'rakan';
  const hasOperationsSearch = Boolean(normalizeSearchText(operationsSearchQuery));
  const searchPageOps = hasOperationsSearch ? searchableOps.slice(0, OPERATIONS_PAGE_SIZE) : [];
  const activeOps = hasOperationsSearch ? searchPageOps : (isRakanTabActive ? paginatedRakanOps : paginatedWorkshopOps);
  const activeOpsTotalCount = hasOperationsSearch ? searchableOps.length : (isRakanTabActive ? rakanOps.length : workshopOps.length);
  const activePage = hasOperationsSearch ? 1 : (isRakanTabActive ? rakanPage : workshopPage);
  const activeTotalPages = hasOperationsSearch ? 1 : (isRakanTabActive ? rakanTotalPages : workshopTotalPages);

  const setActivePage = (nextPage) => {
    if (isRakanTabActive) {
      setRakanPage(nextPage);
    } else {
      setWorkshopPage(nextPage);
    }
  };

  const activePageNumbers = useMemo(
    () => Array.from({ length: activeTotalPages }, (_, i) => i + 1),
    [activeTotalPages]
  );

  const activeOpsIdsKey = useMemo(
    () => (activeOps || []).map((op) => String(op?.id || '')).filter(Boolean).join(','),
    [activeOps]
  );

  useEffect(() => {
    const opIds = activeOpsIdsKey ? activeOpsIdsKey.split(',') : [];
    if (!opIds.length) {
      setIntegrityMap({});
      setIntegritySummary({ total: 0, ok: 0, warnings: 0, duplicates: 0 });
      return;
    }

    let mounted = true;
    const run = async () => {
      setIntegrityLoading(true);
      try {
        const r = await axios.post(`${API_URL}/operations/integrity/check`, {
          op_ids: opIds,
          workshop_id: workshopId || process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync',
        });
        const rows = r?.data?.data?.items || [];
        const summary = r?.data?.data?.summary || { total: 0, ok: 0, warnings: 0, duplicates: 0 };
        if (!mounted) return;
        const nextMap = {};
        rows.forEach((row) => {
          const id = String(row?.op_id || '');
          if (id) nextMap[id] = row;
        });
        setIntegrityMap(nextMap);
        setIntegritySummary(summary);
      } catch {
        if (!mounted) return;
        setIntegrityMap({});
      } finally {
        if (mounted) setIntegrityLoading(false);
      }
    };

    run();
    return () => {
      mounted = false;
    };
  }, [activeOpsIdsKey, workshopId]);

  useEffect(() => {
    if (!expandedOperationId) return;
    const exists = sortedOps.some((op) => op.id === expandedOperationId);
    if (!exists) setExpandedOperationId(null);
  }, [expandedOperationId, sortedOps]);

  // 🆕 Bot deep-link focus: once the op is in the loaded list, expand it and
  // scroll it into view. Runs once per distinct focus id so the user can still
  // collapse it afterwards.
  const focusHandledRef = useRef(null);
  useEffect(() => {
    if (!focusOpFromUrl || focusHandledRef.current === focusOpFromUrl) return;
    const exists = (sortedOps || []).some((op) => String(op.id) === String(focusOpFromUrl));
    if (!exists) return;
    focusHandledRef.current = focusOpFromUrl;
    setExpandedOperationId(focusOpFromUrl);
    setTimeout(() => {
      try {
        const el = document.querySelector(`[data-testid="operation-card-${focusOpFromUrl}"]`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } catch (e) { /* noop */ }
    }, 350);
  }, [focusOpFromUrl, sortedOps]);

  useEffect(() => {
    if (!selectedBusinessAccount?.id) return;
    setForm((prev) => {
      if (prev.accountId === selectedBusinessAccount.id) return prev;
      return { ...prev, accountId: selectedBusinessAccount.id };
    });
  }, [selectedBusinessAccount]);

  useEffect(() => {
    if (accountsLoading) return;
    if (!filteredAccounts.length) {
      setForm((prev) => {
        if (!prev.accountingAccountId) return prev;
        return { ...prev, accountingAccountId: '' };
      });
      return;
    }
    const preferred = pickPreferredOperationAccount(filteredAccounts, form.type, form.partnerType);
    const preferredId = String(preferred?.id || preferred?.code || '');
    const exists = filteredAccounts.some((acc) => String(acc.id || acc.code) === String(form.accountingAccountId || ''));
    const nextId = preferredId || String(filteredAccounts[0].id || filteredAccounts[0].code || '');
    if (!exists || (nextId && String(form.accountingAccountId || '') !== nextId)) {
      setForm((prev) => {
        if (String(prev.accountingAccountId || '') === nextId) return prev;
        return { ...prev, accountingAccountId: nextId };
      });
    }
  }, [filteredAccounts, form.accountingAccountId, form.type, form.partnerType, accountsLoading]);

  useEffect(() => {
    if (!form.accountingAccountId) return;
    if (isSelectedAccountingRakan && form.operationKind !== OPERATION_KIND_RAKAN) {
      setForm((prev) => ({ ...prev, operationKind: OPERATION_KIND_RAKAN }));
      return;
    }
    if (!isSelectedAccountingRakan && form.operationKind === OPERATION_KIND_RAKAN) {
      setForm((prev) => ({
        ...prev,
        operationKind: prev.vehicleId ? OPERATION_KIND_VEHICLE : OPERATION_KIND_WORKSHOP,
      }));
    }
  }, [form.accountingAccountId, form.operationKind, form.vehicleId, isSelectedAccountingRakan]);

  useEffect(() => {
    if (!vehicleIdFromUrl) return;
    setForm((prev) => {
      if (
        prev.operationKind === OPERATION_KIND_VEHICLE
        && prev.scope === 'vehicle'
        && prev.vehicleId === vehicleIdFromUrl
      ) {
        return prev;
      }
      return {
        ...prev,
        operationKind: OPERATION_KIND_VEHICLE,
        scope: 'vehicle',
        vehicleId: vehicleIdFromUrl,
      };
    });
  }, [vehicleIdFromUrl]);

  useEffect(() => {
    if (!form.vehicleId) return;
    const selectedVehicle = vehicleOptions.find((v) => String(v.id) === String(form.vehicleId));
    if (!selectedVehicle) return;

    if (form.operationKind === OPERATION_KIND_VEHICLE || form.operationKind === OPERATION_KIND_RAKAN) {
      setForm((prev) => {
        const nextPartnerId = selectedVehicle.customerId || prev.partnerId || '';
        const nextPartnerName = selectedVehicle.customerName || prev.partnerName || '';
        if (
          prev.partnerType === 'customer'
          && String(prev.partnerId || '') === String(nextPartnerId)
          && String(prev.partnerName || '') === String(nextPartnerName)
        ) {
          return prev;
        }
        return {
          ...prev,
          partnerType: 'customer',
          partnerId: nextPartnerId,
          partnerName: nextPartnerName,
        };
      });
    }
  }, [form.vehicleId, form.operationKind, vehicleOptions]);

  useEffect(() => {
    if (!form.partnerId) return;
    if (form.operationKind !== OPERATION_KIND_RAKAN) return;
    const customer = customers.find((c) => String(c.id) === String(form.partnerId));
    if (!customer) return;
    setForm((prev) => {
      const nextPartnerName = customer.name || prev.partnerName;
      if (
        prev.partnerType === 'customer'
        && String(prev.partnerName || '') === String(nextPartnerName || '')
      ) {
        return prev;
      }
      return {
        ...prev,
        partnerType: 'customer',
        partnerName: nextPartnerName,
      };
    });
  }, [form.partnerId, form.operationKind, customers]);

  useEffect(() => {
    if (vehicleIdFromUrl) {
      return;
    }
    if (form.operationKind === OPERATION_KIND_WORKSHOP) {
      setForm((prev) => {
        const requiresSupplier = PURCHASE_LIKE_TYPES.has(prev.type);
        const nextPartnerId = requiresSupplier ? prev.partnerId : '';
        const nextPartnerType = requiresSupplier ? 'supplier' : prev.partnerType;
        if (
          prev.scope === 'workshop'
          && !prev.vehicleId
          && !prev.visitId
          && String(prev.partnerId || '') === String(nextPartnerId || '')
          && String(prev.partnerType || '') === String(nextPartnerType || '')
        ) {
          return prev;
        }
        return {
          ...prev,
          scope: 'workshop',
          vehicleId: '',
          visitId: '',
          partnerId: nextPartnerId,
          partnerType: nextPartnerType,
        };
      });
    } else if (form.operationKind === OPERATION_KIND_VEHICLE) {
      setForm((prev) => {
        if (prev.scope === 'vehicle' && prev.partnerType === 'customer') {
          return prev;
        }
        return {
          ...prev,
          scope: 'vehicle',
          partnerType: 'customer',
        };
      });
    } else if (form.operationKind === OPERATION_KIND_RAKAN) {
      setForm((prev) => {
        if (prev.scope === 'rakan_parts' && prev.partnerType === 'customer') {
          return prev;
        }
        return {
          ...prev,
          scope: 'rakan_parts',
          partnerType: 'customer',
        };
      });
    }
  }, [form.operationKind, vehicleIdFromUrl]);

  useEffect(() => {
    if (!visits.length || form.visitId) return;
    const activeVisit = visits.find(v => v.status === 'in_progress');
    if (activeVisit) {
      setForm(prev => ({ ...prev, visitId: activeVisit.id }));
    }
  }, [visits, form.visitId]);

  useEffect(() => {
    if (SALE_LIKE_TYPES.has(form.type)) {
      setOcrInvoiceType('sale');
    } else if (PURCHASE_LIKE_TYPES.has(form.type)) {
      setOcrInvoiceType('purchase');
    }
  }, [form.type]);

  const createInlineItem = async (name) => {
    const trimmed = name.trim();
    if (!trimmed) return null;
    try {
      if (item.itemType === 'service') {
        const payload = {
          name: trimmed,
          category: 'خدمات عامة',
          price: Number(item.price) || 0,
          duration: 30,
        };
        const { data } = await axios.post(`${API_URL}/services`, payload);
        servicesQuery.refetch();
        return data;
      }

      const payload = {
        name: trimmed,
        partNumber: `AUTO-${Date.now().toString().slice(-6)}`,
        category: 'عام',
        purchasePrice: PURCHASE_LIKE_TYPES.has(form.type) ? Number(item.price) || 0 : 0,
        sellingPrice: SALE_LIKE_TYPES.has(form.type) ? Number(item.price) || 0 : Number(item.price) || 0,
        quantity: 0,
      };
      const { data } = await axios.post(`${API_URL}/parts`, payload);
      partsQuery.refetch();
      return data;
    } catch (error) {
      toast({ title: 'تعذر حفظ الصنف الجديد', variant: 'destructive' });
      return null;
    }
  };

  const addItem = async () => {
    if (!item.name && !item.itemId && !item.customName) return;
    let itemId = item.itemId;
    let itemName = item.name;

    if (!itemId && item.customName) {
      const created = await createInlineItem(item.customName);
      if (!created) return;
      itemId = created.id;
      itemName = created.name;
    }

    const total = Number(item.quantity) * Number(item.price);
    setForm(prev => ({
      ...prev,
      items: [...prev.items, { ...item, itemId, name: itemName, total }]
    }));
    setItem({ itemType: 'part', itemId: '', name: '', customName: '', quantity: 1, price: 0 });
  };

  const handleCreateCustomer = async () => {
    if (!form.partnerName || !form.partnerPhone) {
      toast({ title: 'يرجى إدخال اسم العميل ورقم الجوال', variant: 'destructive' });
      return;
    }
    try {
      const payload = {
        name: form.partnerName,
        phone: form.partnerPhone,
        email: '',
        address: '',
      };
      const { data } = await axios.post(`${API_URL}/customers`, payload);
      setForm(prev => ({
        ...prev,
        partnerId: data.id,
        partnerName: data.name,
        partnerPhone: data.phone || prev.partnerPhone,
      }));
      customersQuery.refetch();
      toast({ title: 'تمت إضافة العميل بنجاح' });
    } catch (error) {
      toast({ title: 'تعذر إضافة العميل', variant: 'destructive' });
    }
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

  const applyOcrToItems = () => {
    if (!ocrResult?.items?.length) return;
    const itemType = ocrInvoiceType === 'sale' ? 'service' : 'part';
    const mappedItems = ocrResult.items.map((ocrItem) => {
      const qty = Number(ocrItem.quantity || 1);
      const price = Number(ocrItem.unit_price || 0);
      return {
        itemType,
        itemId: ocrItem.part_number || '',
        name: ocrItem.description || ocrItem.part_number || 'بند',
        quantity: qty || 1,
        price: price || 0,
        total: (qty || 1) * (price || 0),
      };
    });
    setForm(prev => ({
      ...prev,
      type: ocrInvoiceType,
      items: mappedItems,
      partnerName: prev.partnerName || ocrResult.vendor || '',
      invoiceNumber: prev.invoiceNumber || ocrResult.invoice_number || ''
    }));
  };

  const getErrorMessage = (e) => {
    const detail = e?.response?.data?.detail;
    if (Array.isArray(detail)) {
      return detail.map((x) => x?.msg || x?.message || JSON.stringify(x)).join(' | ');
    }
    if (detail && typeof detail === 'object') return JSON.stringify(detail);
    return detail || e?.response?.data?.message || e?.message || t('common.error') || 'حدث خطأ';
  };

  const normalizeDuplicateToken = (value) => normalizeText(value).replace(/\s+/g, '');
  const toDateKey = (value) => String(value || '').slice(0, 10);

  const extractPlateFromText = (value) => {
    const txt = String(value || '');
    const m = txt.match(/(?:اللوحة|plate)\s*[:：]?\s*([^|\n\]]+)/i);
    return normalizeDuplicateToken(m?.[1] || '');
  };

  const resolvePlateTokenFromOperation = (op) => {
    return normalizeDuplicateToken(
      op?.plateNumber
      || op?.plate_number
      || op?.vehiclePlate
      || op?.vehicle_plate
      || ''
    ) || extractPlateFromText(op?.notes || '');
  };

  const buildItemsSignature = (items) => {
    if (!Array.isArray(items) || items.length === 0) return '';
    return items
      .map((item) => {
        const qty = Number(item?.quantity || item?.qty || 1);
        const price = Number(item?.price || 0);
        const total = Number(item?.total || (qty * price) || 0);
        return [
          normalizeDuplicateToken(item?.itemType || ''),
          normalizeDuplicateToken(item?.itemId || item?.name || item?.linkedPart || ''),
          qty.toFixed(3),
          price.toFixed(2),
          total.toFixed(2),
        ].join(':');
      })
      .sort()
      .join('|');
  };

  const createOperationMutation = useMutation({
    mutationFn: async (payload) => {
      const res = await axios.post(`${API_URL}/operations`, payload);
      return res.data;
    },
    onSuccess: (createdOp) => {
      queryClient.setQueriesData({ queryKey: ['operations'] }, (old) => {
        if (Array.isArray(old) && createdOp && typeof createdOp === 'object') {
          return [createdOp, ...old];
        }
        return old;
      });
      queryClient.invalidateQueries({ queryKey: ['operations'], refetchType: 'inactive' });
      toast({
        title: t('common.success'),
        description: t('operations.saved_successfully') || 'تم حفظ العملية',
      });
    },
    onError: (e) => {
      const msg = getErrorMessage(e);
      toast({
        title: t('common.error'),
        description: msg || t('operations.save_failed') || 'فشل حفظ العملية',
        variant: 'destructive',
      });
    },
  });


  const handleUpdateOperationItems = async (opId, items, meta = {}) => {
    try {
      setSaveOpId(opId);

      const safeItems = Array.isArray(items) ? items : [];
      const newTotal = safeItems.reduce(
        (sum, it) => sum + (Number(it.quantity || 1) * Number(it.price || 0)),
        0
      );

      const targetOp = operations.find((o) => String(o.id) === String(opId)) || {};
      const opType = String(targetOp?.type || '').toLowerCase();
      const isPurchase = ['purchase', 'expense', 'out', 'purchase_return'].includes(opType);

      const payload = {
        items: safeItems,
        subtotal: newTotal,
        total: newTotal,
        workshopId: workshopId || null,
      };

      if (meta?.accountCode) {
        payload.account = meta.accountCode;
        payload.accountCode = meta.accountCode;
      }
      if (meta?.accountName) {
        payload.accountName = meta.accountName;
      }

      if (meta?.partnerName !== undefined) {
        payload.partnerName = meta.partnerName || '';
      }

      if (isPurchase) {
        payload.supplierName = meta?.partnerName || targetOp?.supplierName || '';
        payload.supplierId = meta?.partnerId || targetOp?.supplierId || null;
        payload.partnerType = 'supplier';
      } else {
        payload.customerName = meta?.partnerName || targetOp?.customerName || '';
        payload.customerId = meta?.partnerId || targetOp?.customerId || null;
        payload.partnerType = 'customer';
      }

      await updateOperationMutation.mutateAsync({ opId, payload });
      return true;
    } catch (e) {
      return false;
    } finally {
      setSaveOpId(null);
    }
  };

  const resolvePartnerPhone = (operation) => {
    const partnerId = operation?.partnerId || operation?.customerId || operation?.supplierId;
    const partnerName = operation?.partnerName || operation?.customerName || operation?.supplierName || '';
    const customerMatch = customers.find((c) =>
      (partnerId && String(c.id) === String(partnerId)) || (partnerName && c.name === partnerName)
    );
    const supplierMatch = suppliers.find((s) =>
      (partnerId && String(s.id) === String(partnerId)) || (partnerName && s.name === partnerName)
    );
    return (
      operation?.partnerPhone ||
      operation?.customerPhone ||
      operation?.supplierPhone ||
      customerMatch?.phone ||
      supplierMatch?.phone ||
      ''
    );
  };

  const buildOperationPayload = (operation) => {
    const opType = (operation?.type || '').toLowerCase();
    const isPurchase = ['purchase', 'expense', 'out', 'purchase_return'].includes(opType);
    const partnerPhone = resolvePartnerPhone(operation);
    const partner = {
      name: operation?.partnerName || operation?.customerName || operation?.supplierName || '',
      phone: partnerPhone,
    };
    const items = (operation?.items || []).map((item) => {
      const quantity = Number(item?.quantity || 1);
      const price = Number(item?.price || 0);
      const total = Number(item?.total || quantity * price);
      const itemName = item?.name || item?.itemName || 'عنصر';
      return {
        name: itemName,
        description: itemName,
        quantity,
        price,
        total,
        unit: item?.unit || 'حبة',
      };
    });

    const accountLabel = operation?.accountName || operation?.account_name || operation?.accountLabel || '';
    const documentTitle = isPurchase ? (accountLabel || 'فاتورة شراء') : 'فاتورة مبيعات';

    return {
      doc_type: 'invoice',
      items,
      customer: isPurchase ? {} : partner,
      supplier: isPurchase ? partner : {},
      vehicle: {
        plate: operation?.vehiclePlate || operation?.vehicle_plate || '',
        model: operation?.vehicleModel || operation?.vehicle_model || '',
        brand: operation?.vehicleBrand || operation?.vehicle_brand || '',
      },
      notes: operation?.description || operation?.notes || '',
      date: operation?.date || operation?.created_at || '',
      settings: {
        document_number: operation?.reference || operation?.id?.slice(0, 8) || '',
        document_title: documentTitle,
      },
    };
  };

  const openPrintDialogForOperation = (operation) => {
    const opType = (operation?.type || '').toLowerCase();
    const label = ['purchase', 'expense', 'out', 'purchase_return'].includes(opType) ? 'فاتورة شراء' : 'فاتورة مبيعات';
    const phone = resolvePartnerPhone(operation);
    setPrintDialogConfig({
      title: label,
      phone,
      payloadBuilder: () => buildOperationPayload(operation),
    });
    setPrintDialogOpen(true);
  };

  const startEditOperationInMainForm = (operation) => {
    if (!operation?.id) return;

    const opType = String(operation.type || 'purchase').toLowerCase();
    const inferredKind = (() => {
      const scope = String(operation.scope || '').toLowerCase();
      if (scope === 'vehicle' || operation.vehicleId) return OPERATION_KIND_VEHICLE;
      if (scope === 'rakan_parts' || isRakanOperationTagged(operation)) return OPERATION_KIND_RAKAN;
      return OPERATION_KIND_WORKSHOP;
    })();

    const normalizedDateRaw = operation.date || operation.op_date || operation.createdAt || operation.created_at || '';
    const normalizedDate = String(normalizedDateRaw).slice(0, 10) || new Date().toISOString().split('T')[0];

    const normalizedItems = Array.isArray(operation.items)
      ? operation.items.map((it) => ({
          name: it?.name || it?.itemName || it?.description || '',
          itemType: it?.itemType || 'part',
          itemId: it?.itemId || it?.id || '',
          quantity: Number(it?.quantity || 1),
          price: Number(it?.price || 0),
          total: Number(it?.total || Number(it?.quantity || 1) * Number(it?.price || 0)),
        }))
      : [];

    setEditingOperationId(operation.id);
    setCreateError('');
    setCreateFormTab('operation');

    setForm((prev) => ({
      ...prev,
      accountId: prev.accountId || selectedBusinessAccount?.id || '',
      accountingAccountId: operation.accountingAccountId || operation.accountId || operation.accountCode || operation.account || '',
      operationKind: inferredKind,
      vehicleId: operation.vehicleId || '',
      visitId: operation.visitId || '',
      scope: inferredKind === OPERATION_KIND_WORKSHOP ? 'workshop' : (inferredKind === OPERATION_KIND_VEHICLE ? 'vehicle' : 'rakan_parts'),
      type: opType || 'purchase',
      partnerType: operation.partnerType || defaultPartnerTypeForOperation(opType, prev.partnerType),
      partnerId: operation.partnerId || operation.customerId || operation.supplierId || '',
      partnerName: operation.partnerName || operation.customerName || operation.supplierName || '',
      partnerPhone: operation.partnerPhone || operation.customerPhone || operation.supplierPhone || '',
      items: normalizedItems,
      paymentMethod: operation.paymentMethod || operation.payment_method || 'cash',
      paymentStatus: operation.paymentStatus || operation.payment_status || 'paid',
      paymentAmount: Number(operation.paymentAmount || operation.total || 0) || '',
      status: operation.status || 'issued',
      invoiceNumber: operation.invoiceNumber || operation.reference || '',
      notes: operation.notes || '',
      date: normalizedDate,
      paymentReceipt: null,
    }));

    window.setTimeout(() => {
      try {
        formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } catch (_e) {
        // ignore scroll errors
      }
    }, 80);
  };

  const requestDeleteOperation = (op) => {
    if (!op?.id) return;
    setDeleteTarget(op);
    setDeleteConfirmOpen(true);
  };

  const confirmDeleteOperation = async () => {
    if (!deleteTarget?.id) return;
    try {
      setDeleteOpId(deleteTarget.id);
      await axios.delete(`${API_URL}/operations/${deleteTarget.id}`);
      queryClient.invalidateQueries({ queryKey: ['operations'] });
      setDeleteConfirmOpen(false);
      setDeleteTarget(null);
    } catch (e) {
      console.error('Failed to delete operation:', e);
    } finally {
      setDeleteOpId(null);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    if (isSaving) return;
    setIsSaving(true);

    // Validate required fields
    setCreateError('');

    if (!form.accountingAccountId) {
      const msg = t('operations.account_required') || 'اختر الحساب';
      setCreateError(msg);
      toast({
        title: t('common.error'),
        description: msg,
        variant: 'destructive',
      });
      setIsSaving(false);
      return;
    }

    if (!selectedBusinessAccount?.id) {
      const msg = 'لا يوجد حساب أعمال مناسب لنوع العملية الحالي';
      setCreateError(msg);
      toast({ title: t('common.error'), description: msg, variant: 'destructive' });
      setIsSaving(false);
      return;
    }

    const hasCustomerOrVehicle = Boolean(activeVehicleId || form.partnerId || form.partnerName);
    const hasSupplierLink = Boolean(form.partnerId || form.partnerName);
    const effectiveOperationKind = isSelectedAccountingRakan
      ? OPERATION_KIND_RAKAN
      : (form.operationKind === OPERATION_KIND_RAKAN
        ? (activeVehicleId ? OPERATION_KIND_VEHICLE : OPERATION_KIND_WORKSHOP)
        : form.operationKind);

    const selectedType = form.type;
    const effectiveType = normalizeOperationTypeForBackend(selectedType);
    const requiresSupplier = PURCHASE_LIKE_TYPES.has(effectiveType);
    const requiresCustomerOrVehicle = SALE_LIKE_TYPES.has(selectedType);
    const requiresVehicleForReceiptVoucher = selectedType === RECEIPT_VOUCHER_TYPE;
    const requiresPartnerForSettlement = selectedType === SETTLEMENT_TYPE;

    if (effectiveOperationKind === OPERATION_KIND_VEHICLE && !activeVehicleId) {
      const msg = 'عملية المركبة تتطلب اختيار مركبة';
      setCreateError(msg);
      toast({
        title: t('common.error'),
        description: msg,
        variant: 'destructive',
      });
      setIsSaving(false);
      return;
    }

    if (requiresCustomerOrVehicle && !hasCustomerOrVehicle) {
      const msg = 'أنواع البيع ومرتجع البيع تتطلب اختيار عميل أو مركبة';
      setCreateError(msg);
      toast({ title: t('common.error'), description: msg, variant: 'destructive' });
      setIsSaving(false);
      return;
    }

    if (requiresVehicleForReceiptVoucher && !activeVehicleId) {
      const msg = 'سند القبض يتطلب ربط العملية بمركبة.';
      setCreateError(msg);
      toast({ title: t('common.error'), description: msg, variant: 'destructive' });
      setIsSaving(false);
      return;
    }

    if (requiresPartnerForSettlement && !hasCustomerOrVehicle && !hasSupplierLink) {
      const msg = 'التسوية تتطلب ربط العملية بعميل أو مورد.';
      setCreateError(msg);
      toast({ title: t('common.error'), description: msg, variant: 'destructive' });
      setIsSaving(false);
      return;
    }

    if (requiresSupplier && !hasSupplierLink) {
      const msg = 'أنواع الشراء ومرتجع الشراء تتطلب اختيار مورد';
      setCreateError(msg);
      toast({ title: t('common.error'), description: msg, variant: 'destructive' });
      setIsSaving(false);
      return;
    }

    if (effectiveOperationKind === OPERATION_KIND_RAKAN && SALE_LIKE_TYPES.has(effectiveType) && !hasCustomerOrVehicle) {
      const msg = 'عملية قطع راكان تتطلب تحديد عميل أو مركبة';
      setCreateError(msg);
      toast({ title: t('common.error'), description: msg, variant: 'destructive' });
      setIsSaving(false);
      return;
    }

    try {
      let resolvedPartnerId = form.partnerId || '';
      let resolvedPartnerName = (form.partnerName || '').trim();
      let resolvedPartnerPhone = (form.partnerPhone || '').trim();
      let resolvedPartnerType = defaultPartnerTypeForOperation(effectiveType, form.partnerType);

      const shouldAutoCreateSupplier = (
        (requiresSupplier || (effectiveType === 'payment_order' && resolvedPartnerType === 'supplier'))
        && !resolvedPartnerId
        && resolvedPartnerName
      );

      if (shouldAutoCreateSupplier) {
        const existingSupplier = suppliers.find(
          (sup) => normalizeText(sup?.name) === normalizeText(resolvedPartnerName)
        );

        if (existingSupplier?.id) {
          resolvedPartnerId = existingSupplier.id;
          resolvedPartnerName = existingSupplier.name || resolvedPartnerName;
          resolvedPartnerPhone = existingSupplier.phone || resolvedPartnerPhone;
        } else {
          const createdSupplierRes = await axios.post(`${API_URL}/suppliers`, {
            name: resolvedPartnerName,
            phone: resolvedPartnerPhone || null,
          });
          const createdSupplier = createdSupplierRes?.data || {};
          resolvedPartnerId = createdSupplier.id || '';
          resolvedPartnerName = createdSupplier.name || resolvedPartnerName;
          resolvedPartnerPhone = createdSupplier.phone || resolvedPartnerPhone;
          queryClient.invalidateQueries({ queryKey: ['suppliers'] });
        }
        resolvedPartnerType = 'supplier';
      }

      const selectedVehicle = (vehicleOptions || []).find((v) => v.id === activeVehicleId);
      const selectedVisit = (visits || []).find((v) => String(v.id) === String(form.visitId));
      const vehicleDetailsNote = ((effectiveOperationKind === OPERATION_KIND_VEHICLE || effectiveOperationKind === OPERATION_KIND_RAKAN) && selectedVehicle)
        ? `\n[VEHICLE] اللوحة: ${selectedVehicle.plateNumber || selectedVehicle.plate_number || '-'} | النوع: ${selectedVehicle.brand || '-'} ${selectedVehicle.model || ''} | العميل: ${selectedVehicle.customerName || selectedVehicle.ownerName || '-'} | رقم الزيارة: ${selectedVisit ? resolveVisitDisplay(selectedVisit, '-') : '-'}`
        : '';

      const normalizedScope = effectiveOperationKind === OPERATION_KIND_WORKSHOP
        ? 'workshop'
        : effectiveOperationKind === OPERATION_KIND_VEHICLE
          ? 'vehicle'
          : 'rakan_parts';

      const normalizedSource = effectiveOperationKind === OPERATION_KIND_WORKSHOP
        ? 'workshop_operation'
        : effectiveOperationKind === OPERATION_KIND_VEHICLE
          ? 'vehicle_operation'
          : 'rakan_parts_operation';

      const paymentAmountValue = effectiveType === 'payment_order'
        ? Number(form.paymentAmount || 0)
        : 0;
      const itemsForSubmit = effectiveType === 'payment_order'
        ? [{
            name: 'سداد مديونية',
            itemType: 'service',
            quantity: 1,
            price: paymentAmountValue,
            total: paymentAmountValue,
          }]
        : form.items;

      const cleanPayload = {
        ...form,
        type: effectiveType,
        items: itemsForSubmit,
        paymentAmount: paymentAmountValue,
        workshopId: workshopId || null,
        operationKind: effectiveOperationKind,
        accountId: selectedBusinessAccount.id,
        accountingAccountId: form.accountingAccountId || null,
        partnerId: resolvedPartnerId || null,
        partnerName: resolvedPartnerName || null,
        partnerPhone: resolvedPartnerPhone || null,
        opDate: form.date,
        scope: normalizedScope,
        source: normalizedSource,
        businessUnit: effectiveOperationKind === OPERATION_KIND_RAKAN ? 'rakan_parts' : 'workshop',
        vehicleId: effectiveOperationKind === OPERATION_KIND_WORKSHOP ? null : (activeVehicleId || null),
        visitId: effectiveOperationKind === OPERATION_KIND_WORKSHOP ? null : (form.visitId || null),
        partnerType: resolvedPartnerType,

        // NOTE: avoid sending File objects in JSON payload
        paymentReceipt: null,
        notes: `${selectedType === RECEIPT_VOUCHER_TYPE ? '[FLOW:RECEIPT_VOUCHER] ' : ''}${selectedType === SETTLEMENT_TYPE ? '[FLOW:SETTLEMENT] ' : ''}${form.notes || ''}${vehicleDetailsNote}`.trim(),
        originalType: selectedType,
      };

      if (!editingOperationId) {
        const payloadHash = JSON.stringify(cleanPayload);
        const now = Date.now();
        if (lastSubmitRef.current.hash === payloadHash && now - lastSubmitRef.current.timestamp < 4000) {
          setCreateError('تم منع تكرار العملية');
          toast({
            title: 'تم منع التكرار',
            description: 'تم تجاهل حفظ مكرر لنفس العملية. الرجاء الانتظار لحظات.',
            variant: 'destructive',
          });
          setIsSaving(false);
          return;
        }
        lastSubmitRef.current = { hash: payloadHash, timestamp: now };

        const candidateAmount = Number(cleanPayload?.total || cleanPayload?.paymentAmount || 0);
        const candidateType = normalizeDuplicateToken(cleanPayload?.type);
        const candidateOriginalType = normalizeDuplicateToken(cleanPayload?.originalType || '');
        const candidatePartnerId = normalizeDuplicateToken(cleanPayload?.partnerId);
        const candidatePartnerName = normalizeDuplicateToken(cleanPayload?.partnerName);
        const candidateDate = toDateKey(cleanPayload?.opDate || cleanPayload?.date);
        const candidateInvoice = normalizeDuplicateToken(cleanPayload?.invoiceNumber);
        const candidateItemsSig = buildItemsSignature(cleanPayload?.items);
        const candidatePlate = normalizeDuplicateToken(
          selectedVehicle?.plateNumber
          || selectedVehicle?.plate_number
          || ''
        ) || extractPlateFromText(cleanPayload?.notes || '');

        const duplicateMatches = (ops || []).filter((op) => {
          const opAmount = Number(op?.total || op?.amount || op?.paymentAmount || 0);
          if (!Number.isFinite(opAmount) || !Number.isFinite(candidateAmount)) return false;
          if (Math.abs(opAmount - candidateAmount) > 0.01) return false;

          const sameType = normalizeDuplicateToken(op?.type) === candidateType;
          if (!sameType) return false;

          const opOriginalType = normalizeDuplicateToken(op?.originalType || op?.original_type || '');
          if (candidateOriginalType && opOriginalType && candidateOriginalType !== opOriginalType) {
            return false;
          }

          const opPlate = resolvePlateTokenFromOperation(op);
          if (candidatePlate && opPlate && candidatePlate !== opPlate) {
            // نفس العميل قد يملك أكثر من مركبة، اختلاف اللوحة يعني غالباً أنها عملية مختلفة
            return false;
          }

          const samePartner =
            (candidatePartnerId && normalizeDuplicateToken(op?.partnerId || op?.partner_id) === candidatePartnerId)
            || (candidatePartnerName && normalizeDuplicateToken(op?.partnerName || op?.partner_name) === candidatePartnerName);

          const samePlate = Boolean(candidatePlate && opPlate && candidatePlate === opPlate);
          const sameDate = toDateKey(op?.date || op?.opDate || op?.createdAt || op?.created_at) === candidateDate;
          const sameInvoice = candidateInvoice
            ? normalizeDuplicateToken(op?.invoiceNumber || op?.invoice_number) === candidateInvoice
            : false;
          const sameItems = candidateItemsSig
            ? candidateItemsSig === buildItemsSignature(op?.items)
            : false;

          const signals = [samePartner, samePlate, sameDate, sameInvoice, sameItems].filter(Boolean).length;
          return signals >= 2;
        });

        if (duplicateMatches.length > 0) {
          const latest = duplicateMatches[0];
          const latestTime = latest?.date || latest?.createdAt || latest?.created_at || '-';
          const latestPlate = resolvePlateTokenFromOperation(latest) || '-';
          const latestPartner = latest?.partnerName || latest?.partner_name || '-';
          const proceed = window.confirm(
            `⚠️ تم العثور على عملية مشابهة جدًا قبل الحفظ.\n` +
            `النوع: ${latest?.type || '-'} | المبلغ: ${Number(latest?.total || 0).toLocaleString('ar-SA')}\n` +
            `العميل/المورد: ${latestPartner} | اللوحة: ${latestPlate}\n` +
            `التاريخ: ${latestTime}\n\n` +
            `إذا كانت هذه عملية مختلفة (مثلاً نفس العميل لكن مركبة أخرى) اضغط موافق للمتابعة.`
          );
          if (!proceed) {
            setIsSaving(false);
            return;
          }
        }

        await createOperationMutation.mutateAsync(cleanPayload);
      } else {
        await updateOperationMutation.mutateAsync({
          opId: editingOperationId,
          payload: cleanPayload,
        });
      }
      if (cleanPayload.accountingAccountId) {
        recordAccountUsage(cleanPayload.accountingAccountId);
      }
      setCreateError('');
      setEditingOperationId(null);

      setForm({
        accountId: selectedBusinessAccount?.id || '',
        accountingAccountId: '',
        operationKind: vehicleIdFromUrl ? OPERATION_KIND_VEHICLE : OPERATION_KIND_WORKSHOP,
        vehicleId: vehicleIdFromUrl || '',
        visitId: '',
        scope: vehicleIdFromUrl ? 'vehicle' : 'workshop',
        type: 'purchase',
        partnerType: 'supplier',
        partnerId: '',
        partnerName: '',
        partnerPhone: '',
        items: [],
        paymentMethod: 'cash',
        paymentStatus: 'paid',
        paymentAmount: '',
        status: 'issued',
        invoiceNumber: '',
        notes: '',
        date: new Date().toISOString().split('T')[0],
        paymentReceipt: null,
      });
      setItem({ itemType: 'part', itemId: '', name: '', customName: '', quantity: 1, price: 0 });
    } catch (e) {
      const msg = getErrorMessage(e);
      setCreateError(msg || t('operations.save_failed') || 'فشل حفظ العملية');
      toast({
        title: t('common.error'),
        description: msg || t('operations.save_failed') || 'فشل حفظ العملية',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const subtotal = form.items.reduce((s, it) => s + Number(it.total || (Number(it.quantity || 1) * Number(it.price || 0)) || 0), 0);
  const previewEffectiveType = normalizeOperationTypeForBackend(form.type);
  const isReceiptVoucherType = form.type === RECEIPT_VOUCHER_TYPE;
  const isSettlementType = form.type === SETTLEMENT_TYPE;
  const isPaymentOrderLikeType = PAYMENT_ORDER_LIKE_TYPES.has(form.type);
  const smartAccountFieldKey = isSettlementType
    ? (form.partnerType === 'supplier' ? 'credit' : 'debit')
    : SALE_LIKE_TYPES.has(form.type)
      ? 'credit'
      : 'debit';
  const previewKind = isSelectedAccountingRakan
    ? OPERATION_KIND_RAKAN
    : (form.operationKind === OPERATION_KIND_RAKAN
      ? (activeVehicleId ? OPERATION_KIND_VEHICLE : OPERATION_KIND_WORKSHOP)
      : form.operationKind);
  const missingVehicleForVehicleKind = previewKind === OPERATION_KIND_VEHICLE && !activeVehicleId;
  const missingCustomerOrVehicleForRakan = previewKind === OPERATION_KIND_RAKAN
    && SALE_LIKE_TYPES.has(previewEffectiveType)
    && !(activeVehicleId || form.partnerId || form.partnerName);
  const missingSupplierForPurchaseLike = PURCHASE_LIKE_TYPES.has(form.type)
    && !(form.partnerId || form.partnerName);
  const missingVehicleForReceiptVoucher = isReceiptVoucherType && !activeVehicleId;
  const missingPartnerForSettlement = isSettlementType && !form.partnerId && !form.partnerName;
  const hasRequiredItems = isPaymentOrderLikeType
    ? Number(form.paymentAmount) > 0
    : form.items.length > 0;
  const missingPartnerForPayment = (form.type === 'payment_order') && !form.partnerId && !form.partnerName;
  const submitDisabled = (
    !hasRequiredItems
    || !selectedBusinessAccount?.id
    || !form.accountingAccountId
    || missingVehicleForVehicleKind
    || missingVehicleForReceiptVoucher
    || missingCustomerOrVehicleForRakan
    || missingSupplierForPurchaseLike
    || missingPartnerForSettlement
    || missingPartnerForPayment
    || isSaving
  );
  const isSaleLikeType = SALE_LIKE_TYPES.has(form.type);
  const isPurchaseLikeType = PURCHASE_LIKE_TYPES.has(form.type);
  const showVehicleLinking = isSaleLikeType || isReceiptVoucherType || form.operationKind === OPERATION_KIND_VEHICLE || form.operationKind === OPERATION_KIND_RAKAN;
  const showCustomerLinking = isSaleLikeType || isReceiptVoucherType || form.operationKind === OPERATION_KIND_VEHICLE || form.operationKind === OPERATION_KIND_RAKAN;
  const operationTypeLabel = OPERATION_TYPE_OPTIONS.find((opt) => opt.value === form.type)?.label || form.type;
  const settlementAccountCode =
    form.paymentMethod === 'transfer' ? '004'
      : form.paymentMethod === 'card' ? '006'
        : '003';

  const journalPreview = useMemo(() => {
    const operationAccountCode = selectedAccountingCode || form.accountingAccountId || '';
    const lines = [];
    const reasons = [];
    const coreRules = ['الذي دخل لك = مدين', 'الذي خرج منك = دائن'];

    if (SALE_LIKE_TYPES.has(form.type)) {
      const debitAccount = form.paymentMethod === 'credit' ? '005' : settlementAccountCode;
      const creditAccount = operationAccountCode || '027';
      lines.push({ side: 'مدين', account: debitAccount, flow: 'دخل لك', reason: form.paymentMethod === 'credit' ? 'دخل لك كذمم عملاء' : 'دخل لك كطريقة تحصيل' });
      lines.push({ side: 'دائن', account: creditAccount, flow: 'خرج منك', reason: 'خرج منك كإيراد/خدمة' });
      reasons.push('بيع/مرتجع بيع: ما دخل لك يُسجل مدينًا، وما خرج منك (الإيراد) يُسجل دائنًا.');
    } else if (PURCHASE_LIKE_TYPES.has(form.type) || form.type === 'expense') {
      const debitAccount = operationAccountCode || '030';
      const creditAccount = form.paymentMethod === 'credit' ? '2101' : settlementAccountCode;
      lines.push({ side: 'مدين', account: debitAccount, flow: 'دخل لك', reason: 'دخل لك كمشتريات/مصروف مستلم' });
      lines.push({ side: 'دائن', account: creditAccount, flow: 'خرج منك', reason: form.paymentMethod === 'credit' ? 'خرج منك كالتزام مورد' : 'خرج منك من الصندوق/البنك' });
      reasons.push('شراء/مصروف: المشتريات مدين (دخل لك)، والصندوق/البنك أو ذمم المورد دائن (خرج منك).');
    } else if (isPaymentOrderLikeType) {
      if (form.partnerType === 'supplier') {
        lines.push({ side: 'مدين', account: '2101', flow: 'دخل لك', reason: 'دخل لك كتخفيض التزام المورد' });
        lines.push({ side: 'دائن', account: settlementAccountCode, flow: 'خرج منك', reason: 'خرج منك من وسيلة الدفع' });
        reasons.push('تسوية مورد: الذي دخل لك (إغلاق ذمم المورد) مدين، والذي خرج منك (دفع) دائن.');
      } else {
        lines.push({ side: 'مدين', account: settlementAccountCode, flow: 'دخل لك', reason: 'دخل لك كتحصيل نقدي/بنكي' });
        lines.push({ side: 'دائن', account: '005', flow: 'خرج منك', reason: 'خرج منك كإقفال ذمم عميل' });
        reasons.push('سند قبض/تسوية عميل: التحصيل داخل = مدين، إقفال ذمم العميل خارج = دائن.');
      }
    }

    return { lines, reasons, coreRules };
  }, [form.type, form.paymentMethod, form.partnerType, form.accountingAccountId, selectedAccountingCode, settlementAccountCode, isPaymentOrderLikeType]);
  const canMoveToLinkingTab = Boolean(form.type && form.date);
  const canMoveToItemsTab = Boolean(form.accountingAccountId);

  const goToNextCreateTab = () => {
    if (createFormTab === 'operation') {
      if (!canMoveToLinkingTab) return;
      setCreateFormTab('linking');
      return;
    }
    if (createFormTab === 'linking') {
      if (!canMoveToItemsTab) return;
      setCreateFormTab('items');
    }
  };

  const goToPrevCreateTab = () => {
    if (createFormTab === 'items') {
      setCreateFormTab('linking');
      return;
    }
    if (createFormTab === 'linking') {
      setCreateFormTab('operation');
    }
  };

  // Theme-based styles (align with dashboard glass look)
  const styles = {
    bg: 'transparent',
    cardBg: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
    cardBorder: isLight ? '#e2e8f0' : 'rgba(168,85,247,0.18)',
    textPrimary: isLight ? '#1e293b' : '#f8fafc',
    textSecondary: isLight ? '#64748b' : 'rgba(226,232,240,0.78)',
    textMuted: isLight ? '#94a3b8' : 'rgba(148,163,184,0.82)',
    inputBg: isLight ? '#ffffff' : 'rgba(255,255,255,0.06)',
    inputBorder: isLight ? '#e2e8f0' : 'rgba(255,255,255,0.10)',
    hoverBg: isLight ? '#f1f5f9' : 'rgba(255,255,255,0.08)',
    tableBg: isLight ? '#f8fafc' : 'rgba(2,6,23,0.35)',
  };

  return (
    <div 
      className={`max-w-7xl mx-auto space-y-8 p-2 sm:p-4 min-h-screen ${isRTL ? 'rtl' : 'ltr'}`} 
      dir={isRTL ? 'rtl' : 'ltr'}
      style={{ backgroundColor: styles.bg }}
    >
        <style>{`
          .ops-glass-create {
            position: relative;
            overflow: hidden;
            background: linear-gradient(135deg, rgba(12, 24, 48, 0.88) 0%, rgba(8, 18, 36, 0.92) 100%);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 30px;
            box-shadow: 0 18px 60px rgba(2, 6, 23, 0.55);
            backdrop-filter: blur(20px) saturate(160%);
            -webkit-backdrop-filter: blur(20px) saturate(160%);
          }
          .ops-glass-content { position: relative; z-index: 2; }
          .ops-glass-orb {
            position: absolute;
            border-radius: 9999px;
            filter: blur(70px);
            opacity: .35;
            pointer-events: none;
            animation: opsFloat 12s ease-in-out infinite alternate;
            z-index: 1;
          }
          .ops-glass-orb-a { width: 260px; height: 260px; top: -90px; right: -60px; background: radial-gradient(circle, rgba(94,184,196,.85), transparent 70%); }
          .ops-glass-orb-b { width: 220px; height: 220px; bottom: -90px; left: -60px; background: radial-gradient(circle, rgba(167,139,250,.85), transparent 70%); animation-delay: -3s; }
          .ops-glass-orb-c { width: 140px; height: 140px; top: 48%; left: 36%; background: radial-gradient(circle, rgba(246,168,98,.85), transparent 70%); opacity:.2; animation-delay: -6s; }
          @keyframes opsFloat { from { transform: translate3d(0,0,0); } to { transform: translate3d(26px,22px,0); } }

          .ops-glass-create .apple-input {
            background: rgba(255,255,255,0.07) !important;
            border: 1px solid rgba(255,255,255,0.16) !important;
            border-radius: 12px !important;
            color: rgba(255,255,255,0.92) !important;
          }
          .ops-glass-create .apple-input:focus {
            border-color: rgba(94,184,196,0.75) !important;
            box-shadow: 0 0 0 3px rgba(94,184,196,0.2) !important;
            background: rgba(94,184,196,0.08) !important;
          }
          .ops-glass-section {
            background: rgba(255,255,255,0.045) !important;
            border: 1px solid rgba(255,255,255,0.16) !important;
            border-radius: 18px !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.12);
          }
          .ops-section-title {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 14px;
            color: rgba(248,250,252,0.95);
            font-size: 14px;
            font-weight: 700;
          }
          .ops-section-icon {
            width: 32px;
            height: 32px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 10px;
            font-size: 14px;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(255,255,255,0.08);
          }
          .ops-kind-option {
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 12px;
            padding: 11px 10px;
            font-size: 13px;
            color: rgba(226,232,240,0.82);
            background: rgba(255,255,255,0.05);
            transition: .2s ease;
          }
          .ops-kind-option:hover { border-color: rgba(255,255,255,0.35); background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.95); }
          .ops-kind-option-active {
            border-color: rgba(94,184,196,0.85);
            background: rgba(94,184,196,0.18);
            color: #9BE4EE;
            box-shadow: 0 0 0 1px rgba(94,184,196,0.35), 0 10px 24px rgba(94,184,196,0.18);
          }
          .ops-glass-create .apple-button {
            background: linear-gradient(135deg, #5EB8C4, #3A9BAA) !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            box-shadow: 0 6px 24px rgba(94,184,196,0.4);
          }
          .ops-total-bar {
            margin-top: 14px;
            background: rgba(94,184,196,.12) !important;
            border: 1px solid rgba(94,184,196,.28) !important;
            border-radius: 14px;
          }
          .ops-page-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 16px;
            padding-bottom: 14px;
            border-bottom: 1px solid rgba(255,255,255,0.14);
          }
          .ops-save-top-btn {
            background: linear-gradient(135deg, #5EB8C4, #3A9BAA);
            color: #fff;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 12px;
            padding: 10px 16px;
            font-size: 13px;
            font-weight: 700;
            box-shadow: 0 6px 22px rgba(94,184,196,.35);
          }
          .ops-chip-grid {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
          }
          .ops-pay-chip {
            border: 1px solid rgba(255,255,255,.2);
            border-radius: 999px;
            padding: 8px 14px;
            font-size: 12px;
            color: rgba(226,232,240,.85);
            background: rgba(255,255,255,.06);
            transition: .2s ease;
          }
          .ops-pay-chip:hover { border-color: rgba(255,255,255,.35); color: rgba(255,255,255,.95); }
          .ops-pay-chip-active {
            border-color: rgba(167,139,250,.7);
            background: rgba(167,139,250,.2);
            color: #ddd6fe;
            box-shadow: 0 0 0 1px rgba(167,139,250,.25);
          }
          .ops-scanner-bar {
            background: rgba(15, 40, 80, 0.48);
            border: 1px solid rgba(94,184,196,.28);
            border-radius: 14px;
            padding: 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            box-shadow: inset 0 1px 0 rgba(94,184,196,.15);
          }
          .ops-input-row-grid {
            display: grid;
            grid-template-columns: 1.2fr 2fr .8fr .9fr auto;
            gap: 10px;
            align-items: end;
          }
          .ops-item-add-btn {
            background: linear-gradient(135deg, #5EB8C4, #3A9BAA);
            color: white;
            border: none;
            border-radius: 12px;
            height: 36px;
            padding: 0 16px;
            font-weight: 700;
            box-shadow: 0 4px 18px rgba(94,184,196,.35);
          }
          .ops-pos-tabs [data-slot="tabs-list"] {
            border-radius: 16px;
            padding: 4px;
            border: 1px solid rgba(255,255,255,.16);
            background: rgba(255,255,255,.05);
          }
          .ops-pos-tabs [data-slot="tabs-trigger"] {
            min-height: 38px;
            border-radius: 12px;
            font-size: 12px;
            color: rgba(226,232,240,.85);
          }
          .ops-pos-tabs [data-slot="tabs-trigger"][data-state="active"] {
            background: rgba(94,184,196,.2);
            color: #cffafe;
            box-shadow: 0 0 0 1px rgba(94,184,196,.35);
          }
          @media (max-width: 920px) {
            .ops-input-row-grid { grid-template-columns: 1fr 1fr; }
          }
        `}</style>
        {/* Header */}
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold" style={{ color: styles.textPrimary }}>{t('operations.title')}</h1>
          <p className="mt-1 text-sm sm:text-base" style={{ color: styles.textSecondary }}>{t('operations.subtitle')}</p>
        </div>

        <div className="mt-6" data-testid="operations-guidance-stepper">
          <GuidanceStepper
            title="إرشادات صفحة العمليات"
            subtitle={operationsSubtitle}
            steps={operationsSteps}
            enabled={guidanceEnabled}
            storageKey={`guidance-operations-${session?.id || session?.name || 'default'}`}
          />
        </div>

        {/* Create Operation Card */}
        {false ? (
        <div 
          className="ops-glass-create p-5 sm:p-6"
        >
          <div className="ops-glass-orb ops-glass-orb-a" aria-hidden="true" />
          <div className="ops-glass-orb ops-glass-orb-b" aria-hidden="true" />
          <div className="ops-glass-orb ops-glass-orb-c" aria-hidden="true" />
          <div className="ops-glass-content">
          {createError ? (
            <div
              className="mb-5 rounded-2xl border px-4 py-3"
              style={{
                backgroundColor: 'rgba(244,63,94,0.10)',
                borderColor: 'rgba(244,63,94,0.25)',
              }}
              role="alert"
              data-testid="operation-create-error-banner"
            >
              <div className="text-sm font-semibold" style={{ color: 'rgba(254,226,226,0.95)' }}>
                {t('common.error') || 'خطأ'}
              </div>
              <div className="text-sm mt-1" style={{ color: 'rgba(254,226,226,0.82)' }}>
                {createError}
              </div>
              <button
                type="button"
                className="mt-2 text-xs underline"
                style={{ color: 'rgba(254,226,226,0.85)' }}
                onClick={() => setCreateError('')}
              >
                {t('common.close') || 'إغلاق'}
              </button>
            </div>
          ) : null}
          <div className="ops-page-header" data-testid="operation-glass-header">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-sky-500 to-blue-600 flex items-center justify-center shadow-md">
                <Plus size={20} className="text-white" />
              </div>
              <div>
                <h2 className="text-base sm:text-lg font-semibold" style={{ color: styles.textPrimary }}>{t('operations.new_operation')}</h2>
                <p className="text-xs mt-0.5" style={{ color: styles.textMuted }}>مسودة · نموذج زجاجي</p>
              </div>
            </div>
            <button
              type="button"
              className="ops-save-top-btn"
              onClick={() => formRef.current?.requestSubmit()}
              data-testid="operation-save-top-button"
            >
              💾 حفظ العملية
            </button>
          </div>

          <form ref={formRef} onSubmit={submit} className="space-y-4">
            <Tabs value={createFormTab} onValueChange={setCreateFormTab} className="ops-pos-tabs w-full" data-testid="operation-create-tabs">
              <TabsList className="grid grid-cols-3">
                <TabsTrigger value="operation" data-testid="operation-create-tab-operation">1) العملية</TabsTrigger>
                <TabsTrigger value="linking" data-testid="operation-create-tab-linking">2) الربط</TabsTrigger>
                <TabsTrigger value="items" data-testid="operation-create-tab-items">3) العناصر</TabsTrigger>
              </TabsList>

              <div className="mt-3 mb-1 flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2" data-testid="operation-create-stepper-top">
                <button
                  type="button"
                  className="px-3 py-1.5 rounded-lg border border-white/20 text-slate-200 disabled:opacity-50"
                  onClick={goToPrevCreateTab}
                  disabled={createFormTab === 'operation'}
                  data-testid="operation-create-prev-step-top"
                >
                  السابق
                </button>
                <span className="text-xs text-slate-300">
                  {createFormTab === 'operation' ? 'الخطوة 1: العملية' : createFormTab === 'linking' ? 'الخطوة 2: الربط' : 'الخطوة 3: العناصر'}
                </span>
                <button
                  type="button"
                  className="px-3 py-1.5 rounded-lg border border-cyan-300/40 text-cyan-100 disabled:opacity-50"
                  onClick={goToNextCreateTab}
                  disabled={(createFormTab === 'operation' && !canMoveToLinkingTab) || (createFormTab === 'linking' && !canMoveToItemsTab) || createFormTab === 'items'}
                  data-testid="operation-create-next-step-top"
                >
                  التالي
                </button>
              </div>

            <div className={createFormTab === 'operation' ? 'space-y-5 mt-4' : 'hidden'}>
              {/* Section 1: Basic Info */}
              <div className="ops-glass-section rounded-2xl border px-4 py-4" style={{ backgroundColor: styles.tableBg, borderColor: styles.cardBorder }}>
                <div className="ops-section-title"><span className="ops-section-icon">📋</span><span>{t('common.basic_info') || 'المعلومات الأساسية'}</span></div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="space-y-2 md:col-span-2 lg:col-span-4">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>نوع العملية في النظام</label>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2" data-testid="operation-kind-selector">
                      {[OPERATION_KIND_WORKSHOP, OPERATION_KIND_VEHICLE, OPERATION_KIND_RAKAN].map((kind) => (
                        <button
                          key={kind}
                          type="button"
                          className={`ops-kind-option ${form.operationKind === kind ? 'ops-kind-option-active' : ''}`}
                          onClick={() => {
                            setForm((prev) => ({
                              ...prev,
                              operationKind: kind,
                              partnerId: kind === OPERATION_KIND_WORKSHOP ? '' : prev.partnerId,
                              partnerName: kind === OPERATION_KIND_WORKSHOP ? '' : prev.partnerName,
                              vehicleId: kind === OPERATION_KIND_WORKSHOP ? '' : prev.vehicleId,
                              visitId: kind === OPERATION_KIND_WORKSHOP ? '' : prev.visitId,
                            }));
                          }}
                          data-testid={`operation-kind-${kind}`}
                        >
                          <span className="block text-lg leading-none mb-1">{OPERATION_KIND_META[kind]?.icon}</span>
                          <span className="block text-xs sm:text-sm">{OPERATION_KIND_META[kind]?.label || OPERATION_KIND_LABELS[kind]}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>{t('operations.operation_type')}</label>
                    <div className="relative">
                      <FileText className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                      <select
                        className="apple-input pr-10"
                        value={form.type}
                        onChange={(e) => {
                          const selectedType = e.target.value;
                          const isReceiptType = selectedType === RECEIPT_VOUCHER_TYPE;
                          const isPaymentOrderLike = PAYMENT_ORDER_LIKE_TYPES.has(selectedType);
                          const nextPartnerType = defaultPartnerTypeForOperation(selectedType, form.partnerType);
                          const shouldKeepVehicle = SALE_LIKE_TYPES.has(selectedType) || isReceiptType;
                          setForm({
                            ...form,
                            type: selectedType,
                            operationKind: isReceiptType ? OPERATION_KIND_VEHICLE : form.operationKind,
                            scope: isReceiptType ? 'vehicle' : form.scope,
                            partnerType: nextPartnerType,
                            partnerId: '',
                            partnerName: '',
                            vehicleId: shouldKeepVehicle ? form.vehicleId : '',
                            visitId: shouldKeepVehicle ? form.visitId : '',
                            items: isPaymentOrderLike ? [] : form.items,
                            paymentStatus: isPaymentOrderLike ? 'paid' : form.paymentStatus,
                            paymentAmount: isPaymentOrderLike ? '' : form.paymentAmount,
                          });
                          if (selectedType && form.date) {
                            window.setTimeout(() => setCreateFormTab('linking'), 120);
                          }
                        }}
                        data-testid="operation-type-select"
                      >
                        {OPERATION_TYPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>{t('operations.operationDateLabel')}</label>
                    <input
                      type="date"
                      value={form.date}
                      onChange={(e) => {
                        setForm({ ...form, date: e.target.value });
                        if (form.type && e.target.value) {
                          window.setTimeout(() => setCreateFormTab('linking'), 120);
                        }
                      }}
                      className="apple-input"
                    />
                  </div>

                  <div className="space-y-2 lg:col-span-2">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>{t('common.description') || 'الوصف'}</label>
                    <textarea
                      className="apple-input h-[44px] py-2"
                      style={{ minHeight: 44, resize: 'vertical' }}
                      value={form.notes}
                      onChange={(e) => setForm({ ...form, notes: e.target.value })}
                      placeholder={t('common.optional') || 'اختياري'}
                      data-testid="operation-notes-input"
                    />
                  </div>
                </div>
              </div>

              </div>

              <div className={createFormTab === 'linking' ? 'space-y-5 mt-4' : 'hidden'}>
              {/* Section 2: Linking */}
              <div className="ops-glass-section rounded-2xl border px-4 py-4" style={{ backgroundColor: styles.tableBg, borderColor: styles.cardBorder }}>
                <div className="ops-section-title"><span className="ops-section-icon">🔗</span><span>{t('common.linking') || 'الربط'}</span></div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>حساب الأعمال</label>
                    <div className="apple-input text-sm" data-testid="operation-business-account-readonly">
                      {selectedBusinessAccount?.name || '---'}
                    </div>
                    <p className="text-[11px]" style={{ color: styles.textMuted }}>
                      {form.operationKind === OPERATION_KIND_RAKAN ? 'سيتم التسجيل ضمن حساب أعمال قطع راكان المستقل' : 'سيتم التسجيل ضمن حساب أعمال الورشة'}
                    </p>
                  </div>

                  {showVehicleLinking && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>{t('operations.vehicle')} {isSaleLikeType ? '(اختياري)' : ''}</label>
                      <div className="relative">
                        <Car className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                        <select
                          className="apple-input pr-10"
                          value={form.vehicleId}
                          onChange={(e) => {
                            const vehicleId = e.target.value;
                            setForm((prev) => ({ ...prev, vehicleId, visitId: '' }));
                          }}
                          data-testid="operation-vehicle-select"
                        >
                          <option value="">{t('operations.select_vehicle')}...</option>
                          {(form.operationKind === OPERATION_KIND_RAKAN || isSaleLikeType ? customerVehicles : vehicleOptions).map((v) => (
                            <option key={v.id} value={v.id}>
                              {v.plateNumber} - {v.brand} {v.model}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  )}

                  {showCustomerLinking && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>
                        {form.operationKind === OPERATION_KIND_VEHICLE && !isSaleLikeType ? 'العميل المرتبط بالمركبة' : 'العميل'}
                      </label>
                      {form.operationKind === OPERATION_KIND_VEHICLE && !isSaleLikeType ? (
                        <div className="apple-input text-sm" data-testid="operation-linked-customer-readonly">
                          {form.partnerName || '---'}
                        </div>
                      ) : (
                        <select
                          className="apple-input"
                          value={form.partnerId || ''}
                          onChange={(e) => {
                            const value = e.target.value;
                            const selected = customers.find((item) => item.id === value);
                            setForm((prev) => ({
                              ...prev,
                              partnerId: value,
                              partnerName: selected?.name || '',
                              partnerPhone: selected?.phone || '',
                              partnerType: 'customer',
                              vehicleId: value ? prev.vehicleId : '',
                              visitId: '',
                            }));
                          }}
                          data-testid="operation-partner-select"
                        >
                          <option value="">اختر عميل</option>
                          {customers.map((item) => (
                            <option key={item.id} value={item.id}>{item.name}</option>
                          ))}
                        </select>
                      )}
                      {form.operationKind === OPERATION_KIND_RAKAN && (
                        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                          <div>
                            <label className="text-xs mb-1 block" style={{ color: styles.textMuted }}>اسم العميل (يدوي)</label>
                            <input
                              className="apple-input"
                              value={form.partnerName}
                              onChange={(e) =>
                                setForm((prev) => ({
                                  ...prev,
                                  partnerName: e.target.value,
                                  partnerId: '',
                                }))
                              }
                              data-testid="operation-partner-manual-name"
                            />
                          </div>
                          <div>
                            <label className="text-xs mb-1 block" style={{ color: styles.textMuted }}>جوال العميل (للحفظ)</label>
                            <input
                              className="apple-input"
                              value={form.partnerPhone}
                              onChange={(e) =>
                                setForm((prev) => ({
                                  ...prev,
                                  partnerPhone: e.target.value,
                                  partnerId: '',
                                }))
                              }
                              data-testid="operation-partner-manual-phone"
                            />
                          </div>
                          <button
                            type="button"
                            onClick={handleCreateCustomer}
                            className="md:col-span-2 rounded-lg bg-emerald-500/20 px-3 py-2 text-xs text-emerald-200 hover:bg-emerald-500/30"
                            data-testid="operation-partner-save"
                          >
                            حفظ العميل
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {form.operationKind === OPERATION_KIND_VEHICLE && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>{t('operations.visit') || t('operations.date')}</label>
                      <div className="relative">
                        <Clock className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                        <select
                          className="apple-input pr-10"
                          value={form.visitId || ''}
                          onChange={e => setForm({ ...form, visitId: e.target.value })}
                          disabled={!form.vehicleId}
                          data-testid="operation-visit-select"
                        >
                          <option value="">---</option>
                          {visits.map(v => (
                            <option key={v.id} value={v.id}>
                              زيارة {resolveVisitDisplay(v, '---')} • {new Date(v.entryDate || v.entry_date).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US')}
                              {v.status === 'in_progress' ? ` (${t('status.in_progress')})` : ''}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  )}

                  {form.operationKind === OPERATION_KIND_WORKSHOP && !isSaleLikeType && (
                    <div className="space-y-2 md:col-span-2 lg:col-span-3">
                      <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>
                        {isPaymentOrderLikeType
                          ? 'الجهة/المستفيد (إلزامي)'
                          : isPurchaseLikeType
                            ? 'المورد (إلزامي)'
                            : form.type === 'expense'
                              ? 'المستفيد/المورد (اختياري)'
                              : 'الجهة/المستفيد (اختياري)'}
                      </label>
                      {isPaymentOrderLikeType ? (
                        <div className="space-y-2">
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              className={`dash-btn ${form.partnerType === 'customer' ? 'dash-btn-primary' : 'dash-btn-secondary'}`}
                              onClick={() => setForm({ ...form, partnerType: 'customer', partnerId: '', partnerName: '' })}
                              data-testid="operation-partner-type-customer"
                              disabled={isReceiptVoucherType}
                            >
                              عميل
                            </button>
                            <button
                              type="button"
                              className={`dash-btn ${form.partnerType === 'supplier' ? 'dash-btn-primary' : 'dash-btn-secondary'}`}
                              onClick={() => setForm({ ...form, partnerType: 'supplier', partnerId: '', partnerName: '' })}
                              data-testid="operation-partner-type-supplier"
                              disabled={isReceiptVoucherType}
                            >
                              مورد
                            </button>
                          </div>
                          <div className="relative">
                            <User className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                            <input
                              className="apple-input pr-10"
                              list="payment-partner-options"
                              placeholder="اختر عميل/مورد أو اكتب اسمًا جديدًا"
                              value={form.partnerName}
                              onChange={(e) => {
                                const value = e.target.value;
                                const normalized = value.trim().toLowerCase();
                                const match = partnerOptions.find((it) => (it.name || '').trim().toLowerCase() === normalized);
                                setForm({
                                  ...form,
                                  partnerName: value,
                                  partnerId: match?.id || '',
                                  partnerPhone: match?.phone || '',
                                });
                              }}
                              data-testid="operation-partner-name-input"
                            />
                            <datalist id="payment-partner-options">
                              {partnerOptions.map((option) => (
                                <option key={option.id || option.name} value={option.name} />
                              ))}
                            </datalist>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="relative">
                            <User className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                            <input
                              className="apple-input pr-10"
                              list={isPurchaseLikeType || form.type === 'expense' ? 'supplier-options-list' : undefined}
                              placeholder={isPurchaseLikeType ? 'اختر مورد أو اكتب اسم مورد' : 'مثال: شركة الكهرباء / مورد أدوات'}
                              value={form.partnerName}
                              onChange={e => {
                                const value = e.target.value;
                                const match = suppliers.find((sup) => (sup.name || '').trim().toLowerCase() === value.trim().toLowerCase());
                                setForm({
                                  ...form,
                                  partnerName: value,
                                  partnerId: match?.id || '',
                                  partnerPhone: match?.phone || '',
                                  partnerType: defaultPartnerTypeForOperation(form.type, form.partnerType),
                                });
                              }}
                              data-testid="operation-partner-name-input"
                            />
                            {(isPurchaseLikeType || form.type === 'expense') && (
                              <datalist id="supplier-options-list">
                                {suppliers.map((option) => (
                                  <option key={option.id || option.name} value={option.name} />
                                ))}
                              </datalist>
                            )}
                          </div>
                          {isPurchaseLikeType && (
                            <p className="text-[11px] text-emerald-300" data-testid="operation-supplier-auto-create-note">
                              عند كتابة اسم مورد جديد سيتم إنشاؤه تلقائيًا عند حفظ العملية.
                            </p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>

                {form.operationKind === OPERATION_KIND_RAKAN && (
                  <div className="mt-3 text-xs text-cyan-200" data-testid="operation-rakan-rule-note">
                    ملاحظة: عند استخدام حساب مصنّف لوحدة قطع راكان تُرحّل العملية تلقائيًا إلى وحدة قطع راكان، ويلزم ربط عميل/مركبة فقط في حالات البيع.
                  </div>
                )}
              </div>

              {/* Section 3: Payment */}
              <div className="ops-glass-section rounded-2xl border px-4 py-4" style={{ backgroundColor: styles.tableBg, borderColor: styles.cardBorder }}>
                <div className="ops-section-title"><span className="ops-section-icon">💳</span><span>{t('common.payment') || 'الدفع'}</span></div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="space-y-2 lg:col-span-4">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>{t('operations.paymentMethod')}</label>
                    <div className="ops-chip-grid" data-testid="operation-payment-method-chips">
                      {PAYMENT_METHOD_OPTIONS.map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          className={`ops-pay-chip ${form.paymentMethod === option.value ? 'ops-pay-chip-active' : ''}`}
                          onClick={() => setForm({ ...form, paymentMethod: option.value })}
                          data-testid={`operation-payment-chip-${option.value}`}
                        >
                          <span className="ml-1">{option.icon}</span>
                          {option.label}
                        </button>
                      ))}
                    </div>
                    <select
                      className="sr-only"
                      value={form.paymentMethod}
                      onChange={e => setForm({ ...form, paymentMethod: e.target.value })}
                      data-testid="operation-payment-method-select"
                    >
                      <option value="cash">{t('operations.cash')}</option>
                      <option value="card">{t('operations.card')}</option>
                      <option value="transfer">{t('operations.transfer')}</option>
                      <option value="credit">{t('operations.credit')}</option>
                    </select>
                    {isReceiptVoucherType && (
                      <p className="mt-1 text-[11px] text-amber-300" data-testid="operation-type-receipt-hint">
                        سند القبض يجب ربطه بمركبة، ويتم توجيه الطرف تلقائياً كعميل.
                      </p>
                    )}
                    {isSettlementType && (
                      <p className="mt-1 text-[11px] text-amber-300" data-testid="operation-type-settlement-hint">
                        التسوية تتطلب اختيار عميل أو مورد قبل الحفظ.
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>الحساب المحاسبي (القيد)</label>
                    <div className="space-y-2" data-testid="operations-smart-account-select-wrapper">
                      <SmartAccountSelect
                        entryType={previewEffectiveType}
                        lineType={smartAccountFieldKey}
                        operationType={previewEffectiveType}
                        fieldKey={smartAccountFieldKey}
                        description={form.notes || form.description || ''}
                        includeAll={false}
                        value={selectedAccountingCode || form.accountingAccountId || ''}
                        onChange={(nextCode, acc) => {
                          const normalizedCode = String(acc?.code || nextCode || '').trim();
                          setForm((prev) => ({ ...prev, accountingAccountId: normalizedCode }));
                          if (normalizedCode) {
                            recordAccountUsage(normalizedCode);
                            window.setTimeout(() => setCreateFormTab('items'), 120);
                          }
                        }}
                        placeholder={accountsLoading ? 'جاري تحميل الحسابات...' : 'اختر الحساب المحاسبي'}
                        data-testid="operation-account-select"
                      />
                      <p className="text-[11px] text-slate-400" data-testid="operations-smart-account-hint">
                        يتم تقديم آخر 3 حسابات مستخدمة تلقائياً في أعلى القائمة.
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>{t('operations.invoiceNumber') || t('invoices.invoice_number') || 'رقم الفاتورة'}</label>
                    <input
                      className="apple-input"
                      value={form.invoiceNumber}
                      onChange={(e) => setForm({ ...form, invoiceNumber: e.target.value })}
                      placeholder="INV-..."
                      data-testid="operation-invoice-number-input"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>{t('status.status') || 'الحالة'}</label>
                    <select
                      className="apple-input"
                      value={form.status}
                      onChange={(e) => setForm({ ...form, status: e.target.value })}
                      data-testid="operation-status-select"
                    >
                      <option value="issued">{t('common.issued') || 'صادرة'}</option>
                      <option value="draft">{t('common.draft') || 'مسودة'}</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>{t('operations.paymentStatus') || (t('common.payment_status') || 'حالة الدفع')}</label>
                    <select
                      className="apple-input"
                      value={form.paymentStatus}
                      onChange={(e) => setForm({ ...form, paymentStatus: e.target.value })}
                      data-testid="operation-payment-status-select"
                    >
                      <option value="paid">{t('common.paid') || 'مدفوع'}</option>
                      <option value="unpaid">{t('common.unpaid') || 'غير مدفوع'}</option>
                    </select>
                  </div>

                  <div className="space-y-2 lg:col-span-3">
                    <label className="text-sm font-medium" style={{ color: styles.textSecondary }}>
                      📎 {t('operations.payment_receipt_optional')}
                    </label>
                    <input
                      type="file"
                      accept="image/*,.pdf"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) setForm({ ...form, paymentReceipt: file });
                      }}
                      className="w-full px-3 py-2 border rounded-lg text-sm"
                      style={{
                        backgroundColor: styles.inputBg,
                        borderColor: styles.inputBorder,
                        color: styles.textPrimary,
                      }}
                      data-testid="operation-payment-receipt-input"
                    />
                    {form.paymentReceipt && (
                      <p className="text-xs" style={{ color: 'rgba(34,197,94,0.95)' }}>✓ {form.paymentReceipt.name}</p>
                    )}
                  </div>
                </div>
              </div>

              </div>

            <div className={createFormTab === 'items' ? 'space-y-5 mt-4' : 'hidden'}>
            {/* OCR Invoice */}
            <div className="ops-glass-section rounded-2xl p-4 border" style={{ backgroundColor: styles.tableBg, borderColor: styles.cardBorder }}>
              <div className="ops-scanner-bar">
                <div>
                  <div className="text-sm font-semibold" style={{ color: styles.textPrimary }}>📷 مسح فاتورة (Scanner)</div>
                  <div className="text-xs" style={{ color: styles.textSecondary }}>التقط صورة أو ارفع ملف لملء البنود تلقائياً</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <select
                    value={ocrInvoiceType}
                    onChange={(e) => setOcrInvoiceType(e.target.value)}
                    className="text-xs px-3 py-2 rounded-lg border"
                    style={{ borderColor: styles.inputBorder, backgroundColor: styles.inputBg, color: styles.textPrimary }}
                    data-testid="operation-ocr-invoice-type"
                  >
                    <option value="purchase">فاتورة شراء</option>
                    <option value="sale">فاتورة بيع</option>
                  </select>
                  <label className="ops-pay-chip flex items-center gap-2 text-xs cursor-pointer" style={{ borderColor: styles.inputBorder, backgroundColor: styles.inputBg, color: styles.textPrimary }}>
                    <Camera size={14} /> التقاط
                    <input type="file" accept="image/*" capture="environment" className="hidden" onChange={handleOcrFileChange} data-testid="operation-ocr-camera-input" />
                  </label>
                  <label className="ops-pay-chip flex items-center gap-2 text-xs cursor-pointer" style={{ borderColor: styles.inputBorder, backgroundColor: styles.inputBg, color: styles.textPrimary }}>
                    <Upload size={14} /> رفع ملف
                    <input type="file" accept="image/*" className="hidden" onChange={handleOcrFileChange} data-testid="operation-ocr-file-input" />
                  </label>
                  <button
                    type="button"
                    onClick={runOcr}
                    disabled={ocrLoading}
                    className="ops-item-add-btn text-xs"
                    style={{ height: 34 }}
                    data-testid="operation-ocr-run"
                  >
                    {ocrLoading ? 'جاري القراءة...' : 'تشغيل OCR'}
                  </button>
                  {ocrResult && (
                    <button
                      type="button"
                      onClick={applyOcrToItems}
                      className="ops-item-add-btn text-xs"
                      style={{ height: 34, background: 'linear-gradient(135deg, #34d399, #059669)' }}
                      data-testid="operation-ocr-apply"
                    >
                      تطبيق البنود
                    </button>
                  )}
                </div>
              </div>
              {ocrPreview && (
                <img src={ocrPreview} alt="OCR" className="mt-2 max-h-40 rounded-lg" data-testid="operation-ocr-preview" />
              )}
              {ocrError && (
                <div className="mt-2 text-xs text-red-500" data-testid="operation-ocr-error">{ocrError}</div>
              )}
              {ocrResult && (
                <div className="mt-2 text-xs" style={{ color: styles.textSecondary }} data-testid="operation-ocr-summary">
                  المورد: {ocrResult.vendor || 'غير محدد'} | الإجمالي: {ocrResult.totals?.grand_total || '—'}
                </div>
              )}
            </div>

              {/* Section 4: Items */}

            {/* Items Section */}
            <div className="ops-glass-section rounded-2xl p-4 border" style={{ backgroundColor: styles.tableBg, borderColor: styles.cardBorder }}>
              <div className="ops-section-title"><span className="ops-section-icon">📦</span><span>{t('operations.addItems')}</span></div>

              {/* Live total summary */}
              <div className="ops-total-bar mt-4 flex items-center justify-between rounded-2xl border px-4 py-3" style={{ backgroundColor: 'rgba(15,23,42,0.35)', borderColor: styles.cardBorder }}>
                <div className="text-sm" style={{ color: styles.textSecondary }}>{t('operations.total') || 'الإجمالي'}</div>
                <div className="text-lg font-extrabold tabular-nums" style={{ color: styles.textPrimary }}>
                  {subtotal.toFixed(2)} {t('operations.SAR')}
                </div>
              </div>

              
              {isPaymentOrderLikeType ? (
                <div className="grid grid-cols-1 md:grid-cols-8 gap-3 items-end mb-4">
                  <div className="md:col-span-2">
                    <label className="text-xs mb-1 block" style={{ color: styles.textMuted }}>مبلغ السداد</label>
                    <input
                      type="number"
                      className="apple-input h-9 text-sm"
                      min="0"
                      step="0.01"
                      value={form.paymentAmount}
                      onChange={e=> setForm({ ...form, paymentAmount: e.target.value })}
                      data-testid="operation-payment-amount-input"
                    />
                  </div>
                </div>
              ) : (
                <div className="ops-input-row-grid mb-4">
                  <div>
                  <label className="text-xs mb-1 block" style={{ color: styles.textMuted }}>نوع العنصر</label>
                  <select 
                    className="apple-input h-9 text-sm"
                    value={item.itemType} 
                    onChange={e=>setItem({ ...item, itemType: e.target.value, itemId: '', name: '', customName: '' })}
                    data-testid="operation-item-type-select"
                  >
                    <option value="part">{t('operations.part')}</option>
                    <option value="service">{t('operations.service')}</option>
                  </select>
                </div>
                
                <div>
                  <label className="text-xs mb-1 block" style={{ color: styles.textMuted }}>{t('operations.items')}</label>
                  <input
                    type="text"
                    list="operation-item-options"
                    className="apple-input h-9 text-sm"
                    value={item.name || item.customName}
                    onChange={(event) => {
                      const value = event.target.value;
                      const normalized = value.trim().toLowerCase();
                      const selected = itemOptions.find((it) => (it.name || '').trim().toLowerCase() === normalized);
                      if (selected) {
                        setItem({
                          ...item,
                          itemId: selected.id,
                          name: selected.name,
                          customName: '',
                          price: resolveItemPrice(selected.raw, item.itemType, form.type),
                        });
                      } else {
                        setItem({
                          ...item,
                          itemId: '',
                          name: value,
                          customName: value,
                        });
                      }
                    }}
                    placeholder="اختر صنفاً أو اكتب جديداً"
                    data-testid="operation-item-select-or-input"
                  />
                  <datalist id="operation-item-options">
                    {itemOptions.map((it) => (
                      <option key={it.id} value={it.name} />
                    ))}
                  </datalist>
                </div>

                <div>
                  <label className="text-xs mb-1 block" style={{ color: styles.textMuted }}>{t('operations.quantity')}</label>
                  <input 
                    type="number" 
                    className="apple-input h-9 text-sm"
                    value={item.quantity} 
                    onChange={e=> setItem({...item, quantity: Number(e.target.value) || 0})} 
                    data-testid="operation-item-quantity-input"
                  />
                </div>

                <div>
                  <label className="text-xs mb-1 block" style={{ color: styles.textMuted }}>سعر الحبة</label>
                  <input 
                    type="number" 
                    className="apple-input h-9 text-sm"
                    value={item.price} 
                    onChange={e=> setItem({...item, price: Number(e.target.value) || 0})} 
                    data-testid="operation-item-price-input"
                  />
                </div>

                <div>
                  <label className="text-xs mb-1 block" style={{ color: 'transparent' }}>.</label>
                  <button 
                    type="button" 
                    onClick={addItem}
                    className="ops-item-add-btn w-full flex items-center justify-center gap-1"
                    data-testid="operation-add-item-button"
                  >
                    <Plus size={16} />
                    <span>{t('operations.addItem')}</span>
                  </button>
                </div>
              </div>
              )}

              {/* Items Table */}
              {!isPaymentOrderLikeType && form.items.length > 0 && (
                <>
                  <div className="md:hidden space-y-3">
                    {form.items.map((it, idx) => (
                      <div
                        key={`mobile-${idx}`}
                        className="rounded-2xl border p-3"
                        style={{ backgroundColor: styles.cardBg, borderColor: styles.cardBorder }}
                        data-testid={`operation-item-card-mobile-${idx}`}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-xs" style={{ color: styles.textSecondary }} data-testid={`operation-item-type-mobile-${idx}`}>
                              {it.itemType === 'part' ? t('operations.part') : t('operations.service')}
                            </div>
                            <div className="text-sm font-semibold" style={{ color: styles.textPrimary }} data-testid={`operation-item-name-mobile-${idx}`}>
                              {it.name}
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              const newItems = [...form.items];
                              newItems.splice(idx, 1);
                              setForm({ ...form, items: newItems });
                            }}
                            className="text-rose-200 hover:text-rose-100 p-1"
                            data-testid={`operation-remove-item-button-mobile-${idx}`}
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <div style={{ color: styles.textSecondary }}>{t('operations.qty')}</div>
                            <div className="text-sm" style={{ color: styles.textPrimary }} data-testid={`operation-item-qty-mobile-${idx}`}>{it.quantity}</div>
                          </div>
                          <div>
                            <div style={{ color: styles.textSecondary }}>{t('operations.price')}</div>
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              value={it.price}
                              onChange={(event) => {
                                const newItems = [...form.items];
                                const price = Number(event.target.value || 0);
                                const quantity = Number(newItems[idx]?.quantity || 1);
                                newItems[idx] = {
                                  ...newItems[idx],
                                  price: event.target.value,
                                  total: quantity * price
                                };
                                setForm({ ...form, items: newItems });
                              }}
                              className="apple-input h-9 text-sm"
                              data-testid={`operation-item-price-input-mobile-${idx}`}
                            />
                          </div>
                          <div className="col-span-2">
                            <div style={{ color: styles.textSecondary }}>{t('operations.total')}</div>
                            <div className="text-sm font-semibold" style={{ color: styles.textPrimary }} data-testid={`operation-item-total-mobile-${idx}`}>
                              {(Number(it.quantity) * Number(it.price)).toFixed(2)} {t('operations.SAR')}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="hidden md:block rounded-2xl border overflow-hidden" style={{ backgroundColor: styles.cardBg, borderColor: styles.cardBorder }}>
                    <table className="w-full text-sm">
                      <thead style={{ backgroundColor: styles.tableBg, color: styles.textSecondary }}>
                        <tr>
                          <th className="p-3 text-right font-medium">نوع العنصر</th>
                          <th className="p-3 text-right font-medium">{t('operations.itemName')}</th>
                          <th className="p-3 text-right font-medium">{t('operations.qty')}</th>
                          <th className="p-3 text-right font-medium">{t('operations.price')}</th>
                          <th className="p-3 text-right font-medium">{t('operations.total')}</th>
                          <th className="p-3"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y" style={{ borderColor: 'rgba(148,163,184,0.14)' }}>
                        {form.items.map((it, idx)=> (
                          <tr key={it?.id ?? it?.uid ?? `op-item-${idx}`}>
                            <td className="p-3" style={{ color: styles.textSecondary }}>{it.itemType==='part'? t('operations.part') : t('operations.service')}</td>
                            <td className="p-3 font-medium" style={{ color: styles.textPrimary }}>{it.name}</td>
                            <td className="p-3" style={{ color: styles.textSecondary }}>{it.quantity}</td>
                            <td className="p-3">
                              <input
                                type="number"
                                min="0"
                                step="0.01"
                                value={it.price}
                                onChange={(event) => {
                                  const newItems = [...form.items];
                                  const price = Number(event.target.value || 0);
                                  const quantity = Number(newItems[idx]?.quantity || 1);
                                  newItems[idx] = {
                                    ...newItems[idx],
                                    price: event.target.value,
                                    total: quantity * price
                                  };
                                  setForm({ ...form, items: newItems });
                                }}
                                className="apple-input h-9 text-sm w-24"
                                data-testid={`operation-item-price-input-${idx}`}
                              />
                            </td>
                            <td className="p-3 font-medium" style={{ color: styles.textPrimary }}>{(Number(it.quantity)*Number(it.price)).toFixed(2)}</td>
                            <td className="p-3 text-left">
                              <button 
                                type="button"
                                onClick={() => {
                                  const newItems = [...form.items];
                                  newItems.splice(idx, 1);
                                  setForm({...form, items: newItems});
                                }}
                                className="text-rose-200 hover:text-rose-100 p-1"
                                data-testid={`operation-remove-item-button-${idx}`}
                              >
                                <Trash2 size={16} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="font-bold" style={{ backgroundColor: styles.tableBg, color: styles.textPrimary }}>
                        <tr>
                          <td colSpan="4" className="p-3 text-left">{t('operations.total')}:</td>
                          <td className="p-3" style={{ color: '#93c5fd' }}>{subtotal.toFixed(2)} {t('operations.SAR')}</td>
                          <td></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </>
              )}
            </div>

            <div className="sticky bottom-0 z-10 rounded-xl border border-white/15 bg-slate-950/92 backdrop-blur px-3 py-3 mt-4" data-testid="operation-create-footer-actions">
              <div className="flex flex-wrap gap-2 items-center justify-between">
                <div className="flex items-center gap-2">
                  {editingOperationId ? (
                    <span className="px-2.5 py-1 rounded-lg bg-amber-500/15 border border-amber-300/35 text-amber-100 text-xs" data-testid="operation-editing-badge">
                      وضع تعديل العملية
                    </span>
                  ) : null}
                  <button
                    type="button"
                    className="px-4 py-2.5 rounded-xl border border-white/20 text-slate-200"
                    onClick={goToPrevCreateTab}
                    disabled={createFormTab === 'operation'}
                    data-testid="operation-create-prev-step"
                  >
                    السابق
                  </button>
                  <button
                    type="button"
                    className="px-4 py-2.5 rounded-xl border border-cyan-300/40 text-cyan-100 disabled:opacity-50"
                    onClick={goToNextCreateTab}
                    disabled={(createFormTab === 'operation' && !canMoveToLinkingTab) || (createFormTab === 'linking' && !canMoveToItemsTab) || createFormTab === 'items'}
                    data-testid="operation-create-next-step"
                  >
                    التالي
                  </button>
                  <div className="text-xs" style={{ color: styles.textMuted }} data-testid="operation-create-items-count">
                    {t('operations.items_count') || 'العناصر'}: {form.items.length}
                  </div>
                  {editingOperationId ? (
                    <button
                      type="button"
                      className="px-3 py-2 rounded-lg border border-rose-400/30 text-rose-100 text-xs"
                      onClick={() => {
                        setEditingOperationId(null);
                        setCreateError('');
                      }}
                      data-testid="operation-edit-cancel-button"
                    >
                      إلغاء التعديل
                    </button>
                  ) : null}
                </div>

                <button
                  type="submit"
                  disabled={submitDisabled}
                  className="apple-button min-h-11 px-6 rounded-xl text-base w-full sm:w-auto"
                  data-testid="operation-save-button"
                  aria-busy={isSaving}
                >
                  {isSaving ? 'جارٍ الحفظ...' : (editingOperationId ? 'تحديث العملية' : t('operations.submit'))}
                </button>
              </div>

              <div className="mt-2 space-y-1 text-xs text-slate-500">
                <div
                  className="mt-2 rounded-xl border border-cyan-400/25 bg-cyan-500/10 p-3 text-[11px]"
                  data-testid="operation-journal-explanation-card"
                >
                  <div className="font-semibold text-cyan-100 mb-2" data-testid="operation-journal-explanation-title">
                    تفسير القيد المتوقع • {operationTypeLabel}
                  </div>
                  <div className="mb-2 space-y-1" data-testid="operation-journal-core-rule">
                    {(journalPreview.coreRules || []).map((rule, idx) => (
                      <div key={`core-rule-${idx}`} className="text-cyan-100/95" data-testid={`operation-journal-core-rule-${idx}`}>
                        • {rule}
                      </div>
                    ))}
                  </div>
                  {journalPreview.lines.length > 0 ? (
                    <div className="space-y-1.5">
                      {journalPreview.lines.map((line, idx) => (
                        <div key={`journal-preview-${idx}`} className="flex flex-wrap items-center justify-between gap-2 text-cyan-50" data-testid={`operation-journal-preview-line-${idx}`}>
                          <span>{line.side}</span>
                          <span className="font-mono">{line.account}</span>
                          <span className="text-cyan-300/90">{line.flow}</span>
                          <span className="text-cyan-200/80">{line.reason}</span>
                        </div>
                      ))}
                      {journalPreview.reasons.map((reason, idx) => (
                        <div key={`journal-reason-${idx}`} className="text-cyan-200/90" data-testid={`operation-journal-preview-reason-${idx}`}>
                          • {reason}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-cyan-200/80" data-testid="operation-journal-explanation-empty">
                      اختر نوع الحركة والحساب لإظهار تفسير القيد.
                    </div>
                  )}
                </div>

                {!isPaymentOrderLikeType && form.items.length === 0 && (
                  <div>{t('operations.items_required') || 'أضف عنصر واحد على الأقل قبل الحفظ'}</div>
                )}

                {isPaymentOrderLikeType && !(Number(form.paymentAmount) > 0) && (
                  <div>أدخل مبلغ السداد قبل الحفظ.</div>
                )}

                {missingVehicleForVehicleKind && (
                  <div>{t('operations.select_vehicle_required') || 'اختر مركبة أولاً'}</div>
                )}

                {missingVehicleForReceiptVoucher && (
                  <div>سند القبض يتطلب ربط العملية بمركبة.</div>
                )}

                {missingPartnerForSettlement && (
                  <div>التسوية تتطلب اختيار عميل أو مورد.</div>
                )}
              </div>
            </div>
            </div>
            </Tabs>
          </form>
          </div>
        </div>
        ) : null}

        {/* 🆕 Phase 3C.7 — Recent bot-executed operations */}
        <RecentOperationsWidget
          variant="page"
          limit={5}
          className="mb-4"
        />

        {/* Recent Operations */}
        <div className="space-y-6" data-testid="operations-sections-wrapper">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-950">{t('operations.recentOperations')}</h2>
              <p className="text-sm text-slate-700 mt-1">{t('operations.subtitle') || ''}</p>
            </div>
            <div className="relative w-full lg:max-w-md">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600" size={18} />
              <input
                type="text"
                value={operationsSearchQuery}
                onFocus={ensureOperationsLoaded}
                onChange={handleOperationsSearchChange}
                onInput={handleOperationsSearchChange}
                placeholder="ابحث بالاسم، رقم الملف، رقم العملية، اللوحة أو البند"
                className="w-full rounded-2xl border border-slate-300 bg-white py-3 pl-4 pr-10 text-sm text-slate-950 placeholder:text-slate-500 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                data-testid="operations-search-input"
              />
              {operationsSearchQuery ? (
                <button
                  type="button"
                  onClick={() => setOperationsSearchQuery('')}
                  className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-800 hover:bg-slate-200"
                  data-testid="operations-search-clear-button"
                >
                  مسح
                </button>
              ) : null}
            </div>
          </div>

          {workshopCreditSummary.overdue > 0 && (
            <div
              className="glass-card border border-rose-500/30 bg-rose-500/10 p-4 flex flex-col gap-2"
              data-testid="operations-credit-reminder-card"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm text-rose-200">تذكير سداد العمليات الآجل</div>
                <label className="flex items-center gap-2 text-xs text-rose-200/80">
                  مدة التذكير (يوم)
                  <input
                    type="number"
                    min="1"
                    value={creditReminderDays}
                    onChange={(event) => setCreditReminderDays(Math.max(1, Number(event.target.value) || 1))}
                    className="w-16 rounded-lg border border-rose-400/40 bg-transparent px-2 py-1 text-center text-rose-100"
                    data-testid="operations-credit-reminder-days-input"
                  />
                </label>
              </div>
              <div className="text-base text-white space-y-1">
                <div>
                  ورشة: <span className="text-rose-300 font-semibold" data-testid="operations-credit-reminder-workshop-count">{workshopCreditSummary.total}</span> عملية آجل (متأخرة: {workshopCreditSummary.overdue}).
                </div>
              </div>
              <div className="text-xs text-rose-200/80">التنبيه يظهر عند تجاوز مدة التذكير المحددة.</div>
            </div>
          )}

          <div className="flex items-center justify-between" data-testid="operations-active-tab-summary">
            <h3 className="text-lg font-bold text-slate-950" data-testid="operations-active-tab-title">
              عمليات الورشة
            </h3>
            <span className="text-xs px-2 py-1 rounded bg-slate-100 text-slate-900 font-bold" data-testid="operations-active-tab-count">
              {activeOpsTotalCount} عملية
            </span>
          </div>

          <div className="glass-card p-3" data-testid="operations-integrity-summary-card">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-100 border border-emerald-400/35" data-testid="operations-integrity-ok">
                سليم: {integritySummary.ok || 0}
              </span>
              <span className="px-2.5 py-1 rounded-full bg-rose-500/15 text-rose-100 border border-rose-400/35" data-testid="operations-integrity-warnings">
                ملاحظات: {integritySummary.warnings || 0}
              </span>
              <span className="px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-100 border border-amber-400/35" data-testid="operations-integrity-duplicates">
                تكرار محتمل: {integritySummary.duplicates || 0}
              </span>
              <span className="text-slate-700 font-semibold" data-testid="operations-integrity-location-hint">
                كشف الربط يظهر هنا، وداخل كل عملية، وفي ملف المركبة.
              </span>
              {integrityLoading ? <span className="text-cyan-300">جاري التحقق...</span> : null}
            </div>
          </div>

          {operationsLoading && activeOpsTotalCount === 0 ? (
            <div className="apple-card p-4 text-center" data-testid="operations-loading">
              <div className="text-sm text-slate-300">جاري تحميل العمليات...</div>
            </div>
          ) : activeOpsTotalCount === 0 ? (
            <div className="apple-card p-4 text-center" data-testid="operations-active-tab-empty">
              <div className="text-sm text-slate-400">
                لا توجد عمليات ورشة حالياً
              </div>
            </div>
          ) : (
            <>
              <div
                className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4"
                data-testid="operations-active-tab-grid"
              >
                {activeOps.map((op, index) => {
                  const opRenderKey = op.id || `${isRakanTabActive ? 'rakan' : 'workshop'}-${op.invoiceNumber || 'op'}-${activePage}-${index}`;
                  return (
                  <OperationCard
                    key={opRenderKey}
                    operation={op}
                    integrityStatus={integrityMap[String(op.id)] || null}
                    isRTL={isRTL}
                    t={t}
                    accounts={accounts}
                    businessAccounts={bizAccounts}
                    customers={customers}
                    suppliers={suppliers}
                    vehicles={vehicleOptions}
                    isSaving={saveOpId === op.id}
                    isDeleting={deleteOpId === op.id}
                    expanded={expandedOperationId === (op.id || opRenderKey)}
                    onExpandedChange={(next) => {
                      if (next) {
                        setExpandedOperationId(op.id || opRenderKey);
                      } else {
                        setExpandedOperationId((prev) => (prev === op.id || prev === opRenderKey ? null : prev));
                      }
                    }}
                    onPrint={(o) => {
                      if (!o?.id) return;
                      openPrintDialogForOperation(o);
                    }}
                    onViewVehicle={(o) => {
                      if (!o?.vehicleId) return;
                      navigate(`/vehicle/${o.vehicleId}`);
                    }}
                    onConfirmCreditPayment={canSettleOperations ? ((o) => {
                      setConfirmTarget(o);
                      setConfirmOpen(true);
                    }) : undefined}
                    onDelete={canDeleteOperations ? ((o) => requestDeleteOperation(o)) : undefined}
                    onEditInForm={canEditOperations ? ((o) => startEditOperationInMainForm(o)) : undefined}
                    onUpdateItems={canEditOperations ? ((opId, items, meta) => handleUpdateOperationItems(opId, items, meta)) : undefined}
                  />
                  );
                })}
              </div>

              <div className="glass-card p-3" data-testid="operations-pagination-wrapper">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                  <span className="text-sm text-slate-300" data-testid="operations-pagination-label">
                    صفحة {activePage} من {activeTotalPages} صفحات
                  </span>

                  <div className="flex flex-wrap items-center gap-2" data-testid="operations-pagination-controls">
                    <button
                      type="button"
                      className="px-3 py-1.5 rounded-lg bg-white/10 text-slate-200 disabled:opacity-50"
                      disabled={activePage <= 1}
                      onClick={() => setActivePage(activePage - 1)}
                      data-testid="operations-pagination-prev-button"
                    >
                      السابق
                    </button>

                    <div className="flex flex-wrap items-center gap-1" data-testid="operations-pagination-numbers">
                      {activePageNumbers.map((pageNumber) => (
                        <button
                          key={`operations-page-${isRakanTabActive ? 'rakan' : 'workshop'}-${pageNumber}`}
                          type="button"
                          className={`w-9 h-9 rounded-lg text-sm border transition-colors ${pageNumber === activePage ? 'bg-cyan-500/30 border-cyan-300/40 text-cyan-100' : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'}`}
                          onClick={() => setActivePage(pageNumber)}
                          data-testid={`operations-pagination-page-button-${pageNumber}`}
                        >
                          {pageNumber}
                        </button>
                      ))}
                    </div>

                    <button
                      type="button"
                      className="px-3 py-1.5 rounded-lg bg-white/10 text-slate-200 disabled:opacity-50"
                      disabled={activePage >= activeTotalPages}
                      onClick={() => setActivePage(activePage + 1)}
                      data-testid="operations-pagination-next-button"
                    >
                      التالي
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        <OperationDetailsModal
          open={detailsOpen}
          onOpenChange={setDetailsOpen}
          operation={selectedOperation}
          accounts={accounts}
          t={(k) => {
            // small adapter to reuse existing translations
            if (k === 'operations.from_to') return t('operations_ui.from_to');
            if (k === 'operations.notes') return t('operations_ui.notes');
            return t(k);
          }}
          isRTL={isRTL}
          onPrint={() => {
            if (!selectedOperation?.id) return;
            openPrintDialogForOperation(selectedOperation);
          }}
          onViewVehicle={() => {
            if (!selectedOperation?.vehicleId) return;
            navigate(`/vehicle/${selectedOperation.vehicleId}`);
          }}
          onDelete={canDeleteOperations ? (async () => {
            if (!selectedOperation?.id) return;
            requestDeleteOperation(selectedOperation);
          }) : undefined}
        />
      
      {/* أبوفهد (المساعد المالي) أصبح عبر الزر العائم الموحد */}

      <ConfirmPaymentDialog
        open={confirmOpen}
        onOpenChange={(v) => {
          setConfirmOpen(v);
          if (!v) setConfirmTarget(null);
        }}
        remainingBalance={(() => {
          const op = confirmTarget;
          if (!op) return 0;
          const total = parseFloat(op.total || op.workshopTotal || 0);
          return Math.max(0, total);
        })()}
        onConfirm={async ({ paymentLines, date, amount, paymentMethod, receipt, supplierId, discount = 0 }) => {
          if (!confirmTarget?.id) return;
          // جلب workshopId من env أو من العملية مباشرة
          const wid = workshopId
            || confirmTarget.workshopId
            || confirmTarget.workshop_id
            || process.env.REACT_APP_WORKSHOP_ID
            || 'finmodule-sync';
          try {
            const lines = paymentLines && paymentLines.length > 0
              ? paymentLines
              : [{ method: paymentMethod || 'bank', amount }];

            for (const line of lines) {
              const payAmt = (line.amount && line.amount > 0) ? line.amount : undefined;
              if (line.method === 'supplier_balance') {
                const resolvedSupplierId =
                  supplierId
                  || confirmTarget?.supplierId
                  || (normalizeText(confirmTarget?.partnerType) === 'supplier' ? confirmTarget?.partnerId : null)
                  || null;

                if (!resolvedSupplierId) {
                  throw new Error('يرجى اختيار المورد قبل السداد عبر رصيد المورد.');
                }

                const idemKey = generateIdempotencyKey('op-supbal', confirmTarget.id);
                await axios.post(
                  `${API_URL}/smart-accounting/operations/${confirmTarget.id}/confirm-via-supplier-balance`,
                  {
                    workshopId: wid,
                    workshop_id: wid,
                    supplier_id: resolvedSupplierId,
                    ...(payAmt !== undefined && { amount: payAmt }),
                    date,
                    notes: `تسوية عملية عبر رصيد المورد — ${confirmTarget?.partnerName || confirmTarget?.supplierName || ''}`.trim(),
                  },
                  { headers: { 'Idempotency-Key': idemKey } },
                );
              } else {
                const idemKey = generateIdempotencyKey('op-pay', confirmTarget.id);
                await axios.post(
                  `${API_URL}/operations/${confirmTarget.id}/confirm-payment`,
                  {
                    workshopId: wid,
                    ...(payAmt !== undefined && { amount: payAmt }),
                    date,
                    payment_method: line.method || 'bank',
                    receipt: receipt || null,
                    ...(Number(discount) > 0 && { discount: Number(discount) }),
                  },
                  { headers: { 'Idempotency-Key': idemKey } },
                );
              }
            }

            setConfirmOpen(false);
            setConfirmTarget(null);
            queryClient.invalidateQueries({ queryKey: ['operations'] });
            // 🔄 إشعار باقي الصفحات (Dashboard) بالتحديث
            try {
              window.dispatchEvent(new CustomEvent('finance:updated', {
                detail: { source: 'operation_confirm_payment', opId: confirmTarget.id }
              }));
            } catch (e) { console.warn('finance:updated dispatch failed', e); }
            toast({ title: 'تم السداد بنجاح', description: 'تم تسجيل الدفعة وتحديث حالة العملية' });
          } catch (e) {
            console.error('Failed to confirm payment:', e);
            const errMsg = e?.response?.data?.detail || e?.message || '';
            toast({ title: 'فشل تأكيد السداد', description: errMsg || 'تأكد من الاتصال وحاول مرة أخرى', variant: 'destructive' });
          }
        }}
        supplierId={
          confirmTarget?.supplierId
          || (normalizeText(confirmTarget?.partnerType) === 'supplier' ? confirmTarget?.partnerId : null)
          || null
        }
        allowSupplierBalance={true}
      />
      
      <OperationDeleteConfirmDialog
        open={deleteConfirmOpen}
        onOpenChange={(v) => {
          // prevent closing while delete is in-flight
          if (deleteOpId) return;
          setDeleteConfirmOpen(v);
          if (!v) setDeleteTarget(null);
        }}
        operation={deleteTarget}
        isRTL={isRTL}
        t={t}
        isLoading={Boolean(deleteOpId)}
        onConfirm={confirmDeleteOperation}
      />

      <QuickPrintDialog
        open={printDialogOpen}
        title={printDialogConfig?.title || 'خيارات الطباعة'}
        description="معاينة تفاصيل العملية قبل الطباعة أو الإرسال"
        payloadBuilder={printDialogConfig?.payloadBuilder}
        initialPhone={printDialogConfig?.phone}
        onClose={() => setPrintDialogOpen(false)}
      />
      
      <span data-testid="confirm-open-state" className="hidden">{confirmOpen ? 'open' : 'closed'}</span>

    </div>
  );
};

export default Operations;