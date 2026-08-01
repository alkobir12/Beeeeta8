import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Banknote,
  BarChart3,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Save,
  Scale,
  ShieldCheck,
  Trash2,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { financeAPI } from '../services/api';
import { formatCurrency } from '../utils/formatters';
import ARReceivablesTab from '../components/ARReceivablesTab';
import { FinanceBulkDeleteAuditPanel } from '../components/FinanceBulkDeleteAuditPanel';

const tabs = [
  { key: 'overview', label: 'نظرة عامة' },
  { key: 'balance', label: 'الميزانية' },
  { key: 'income', label: 'قائمة الدخل' },
  { key: 'cashflow', label: 'التدفقات النقدية' },
  { key: 'receivables', label: 'الذمم' },
  { key: 'trial', label: 'ميزان المراجعة' },
  { key: 'budget', label: 'الموازنة' },
  { key: 'reconcile', label: 'مطابقة العمليات' },
];

const GlassCard = ({ title, value, subtitle, testId, accent = 'from-sky-500/25 to-cyan-400/10' }) => (
  <div
    className="rounded-3xl border border-white/15 bg-slate-950/45 backdrop-blur-2xl p-5 shadow-[0_10px_45px_-20px_rgba(14,165,233,0.55)]"
    data-testid={`${testId}-card`}
  >
    <div className={`h-1.5 w-28 rounded-full bg-gradient-to-r ${accent}`} />
    <p className="mt-3 text-xs text-slate-300" data-testid={`${testId}-title`}>{title}</p>
    <p className="mt-2 text-2xl font-bold text-slate-50" data-testid={testId}>{value}</p>
    {subtitle ? <p className="mt-2 text-xs text-slate-400" data-testid={`${testId}-subtitle`}>{subtitle}</p> : null}
  </div>
);

const ExpandableMetricCard = ({ title, value, subtitle, details = [], expanded, onToggle, testId, accent }) => (
  <div
    className="relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900/70 to-slate-950/70 backdrop-blur-xl p-5 shadow-[0_8px_30px_rgba(0,0,0,0.4)] hover:border-white/20 transition"
    data-testid={`${testId}-card`}
  >
    {/* Decorative accent stripe (top-right) */}
    <div className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${accent}`} />
    <div className={`pointer-events-none absolute -bottom-12 -right-12 w-32 h-32 rounded-full bg-gradient-to-br ${accent} opacity-[0.08] blur-2xl`} />

    <button type="button" onClick={onToggle} className="w-full text-right" data-testid={`${testId}-toggle`}>
      <div className="flex items-start justify-between gap-3 mb-2">
        <p className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold" data-testid={`${testId}-title`}>{title}</p>
        <span className="text-slate-400 shrink-0 transition-transform" style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>
          <ChevronRight size={14} />
        </span>
      </div>
      <p className="text-3xl lg:text-4xl font-black text-white tabular-nums leading-tight" data-testid={testId}>{value}</p>

      {subtitle && typeof subtitle === 'string' ? (
        <p className="mt-2 text-xs text-slate-400" data-testid={`${testId}-subtitle`}>{subtitle}</p>
      ) : null}
      {subtitle && Array.isArray(subtitle) && subtitle.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5" data-testid={`${testId}-subtitle`}>
          {subtitle.slice(0, 3).map((chip, idx) => (
            <span
              key={`${testId}-chip-${idx}`}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-[10px] text-slate-200"
            >
              <span className="text-slate-400">{chip.label}</span>
              <span className="tabular-nums font-semibold text-slate-50">{chip.value}</span>
            </span>
          ))}
          {subtitle.length > 3 ? (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-[10px] text-slate-400">
              +{subtitle.length - 3}
            </span>
          ) : null}
        </div>
      ) : null}
    </button>

    {expanded && details.length > 0 ? (
      <div className="mt-3 border-t border-white/15 pt-3 space-y-0.5" data-testid={`${testId}-details`}>
        {details.map((line, idx) => {
          // Section header form: { section }
          if (line && typeof line === 'object' && 'section' in line) {
            return (
              <div
                key={`${testId}-section-${idx}`}
                className="mt-2 first:mt-0 mb-1 text-[11px] font-semibold text-slate-300 uppercase tracking-wider"
              >
                {line.section}
              </div>
            );
          }
          // Object form: { label, value, highlight?, tooltip? }
          if (line && typeof line === 'object' && 'label' in line) {
            const base = 'flex items-center justify-between gap-3 text-xs py-1.5 border-b border-white/5 last:border-b-0';
            const valueClass = line.highlight
              ? 'text-emerald-200 tabular-nums font-bold text-left'
              : 'text-slate-100 tabular-nums font-medium text-left';
            return (
              <div key={`${testId}-line-${idx}`} className={base}>
                <span className="text-slate-400 whitespace-nowrap flex items-center gap-1">
                  {line.label}
                  {line.tooltip && (
                    <span
                      title={line.tooltip}
                      className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full text-[9px] cursor-help"
                      style={{ background: 'rgba(148,163,184,0.25)', color: 'rgba(148,163,184,0.9)' }}
                    >?</span>
                  )}
                </span>
                <span className={valueClass}>{line.value}</span>
              </div>
            );
          }
          // Legacy string form
          return (
            <p key={`${testId}-line-${idx}`} className="text-xs text-slate-300 leading-relaxed">• {line}</p>
          );
        })}
      </div>
    ) : null}
  </div>
);

const safeDate = (date) => date.toISOString().split('T')[0];

const resolveWorkshopId = () => {
  const fromEnv = process.env.REACT_APP_WORKSHOP_ID;
  if (fromEnv && String(fromEnv).trim()) return String(fromEnv).trim();

  try {
    const rawSession = localStorage.getItem('session') || localStorage.getItem('workshopUser') || '{}';
    const parsed = JSON.parse(rawSession);
    const fromSession = parsed?.workshopId || parsed?.workshop_id || parsed?.workshop || '';
    if (fromSession && String(fromSession).trim()) return String(fromSession).trim();
  } catch (_e) {
    // ignore
  }
  return '';
};

const unwrapApiData = (response, fallback = null) => {
  if (!response) return fallback;
  if (response?.data?.data !== undefined) return response.data.data;
  if (response?.data !== undefined) return response.data;
  return fallback;
};

const ensureSuccessResponse = (response) => {
  if (response?.data?.success === false) {
    throw new Error(response?.data?.message || 'finance api returned success=false');
  }
  return response;
};

export default function ComprehensiveFinancial() {
  const queryClient = useQueryClient();
  const workshopId = useMemo(() => resolveWorkshopId(), []);
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [accountTreePage, setAccountTreePage] = useState(1);
  const [showChildrenTree, setShowChildrenTree] = useState(true);
  const [salesOpsPage, setSalesOpsPage] = useState(1);
  const [expandedHeadlineCards, setExpandedHeadlineCards] = useState({
    net_income: true,
    debts: false,
    expenses: false,
    parts_profit: false,
  });
  const [startDate, setStartDate] = useState('2000-01-01');
  const [endDate, setEndDate] = useState(() => safeDate(new Date()));
  const [activePreset, setActivePreset] = useState('all');
  const [showCloseDialog, setShowCloseDialog] = useState(false);
  const [closing, setClosing] = useState(false);
  const [closeResult, setCloseResult] = useState(null);
  const [lastCloseInfo, setLastCloseInfo] = useState(null);
  const [budgetMonth, setBudgetMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  const [budgetDraft, setBudgetDraft] = useState({ name: '', category: 'operating', planned: '', actual: '', notes: '' });
  const [trialSearch, setTrialSearch] = useState('');
  const [isReclassifyingPayments, setIsReclassifyingPayments] = useState(false);
  const [lastReclassifyResult, setLastReclassifyResult] = useState(null);
  const [directCoreFallback, setDirectCoreFallback] = useState({ income: null, balance: null });
  const [coreLoadingGraceExpired, setCoreLoadingGraceExpired] = useState(false);

  const commonParams = useMemo(() => ({ workshop_id: workshopId, start_date: startDate, end_date: endDate }), [workshopId, startDate, endDate]);
  const shouldLoadCashFlow = activeTab === 'cashflow';
  const shouldLoadTrialBalance = activeTab === 'trial';

  const balanceSheetQuery = useQuery({
    queryKey: ['financial-balance-sheet', workshopId, endDate],
    queryFn: async () => {
      const res = ensureSuccessResponse(await financeAPI.getBalanceSheet({ workshop_id: workshopId, as_of_date: endDate }));
      return unwrapApiData(res, null);
    },
    enabled: Boolean(workshopId),
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnReconnect: 'always',
    retry: 2,
  });

  const incomeStatementQuery = useQuery({
    queryKey: ['financial-income-statement', workshopId, startDate, endDate],
    queryFn: async () => {
      const res = ensureSuccessResponse(await financeAPI.getIncomeStatement(commonParams));
      return unwrapApiData(res, null);
    },
    enabled: Boolean(workshopId),
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnReconnect: 'always',
    retry: 2,
  });

  const cashFlowQuery = useQuery({
    queryKey: ['financial-cash-flow', workshopId, startDate, endDate],
    queryFn: async () => {
      const res = await financeAPI.getCashFlow(commonParams);
      return unwrapApiData(res, null);
    },
    enabled: Boolean(workshopId) && shouldLoadCashFlow,
  });

  const trialBalanceQuery = useQuery({
    queryKey: ['financial-trial-balance', workshopId, startDate, endDate],
    queryFn: async () => {
      const res = await financeAPI.getTrialBalance(commonParams);
      return unwrapApiData(res, { accounts: [], totals: { total_debit: 0, total_credit: 0 } });
    },
    enabled: Boolean(workshopId) && shouldLoadTrialBalance,
  });

  const receivablesSummaryQuery = useQuery({
    queryKey: ['financial-ar-summary', workshopId, endDate],
    queryFn: async () => {
      const res = await financeAPI.getARCustomers({ workshop_id: workshopId, as_of: endDate });
      return unwrapApiData(res, { total_ar: 0, customers: [] });
    },
    enabled: Boolean(workshopId),
  });

  const budgetsQuery = useQuery({
    queryKey: ['financial-budgets', workshopId, budgetMonth],
    queryFn: async () => {
      const res = await financeAPI.getBudgets({ workshop_id: workshopId, month: budgetMonth });
      return unwrapApiData(res, { rows: [], totals: { planned: 0, actual: 0, variance: 0 } });
    },
    enabled: Boolean(workshopId),
  });

  const operationTraceQuery = useQuery({
    queryKey: ['financial-operation-trace', workshopId, startDate, endDate],
    queryFn: async () => {
      const res = await financeAPI.getOperationTrace({
        workshop_id: workshopId,
        start_date: startDate,
        end_date: endDate,
      });
      return unwrapApiData(res, { rows: [], summary: { operations_total: 0, journal_total: 0, types_count: 0 } });
    },
    enabled: Boolean(workshopId),
  });

  const reconciliationQuery = useQuery({
    queryKey: ['financial-reconciliation', workshopId, startDate, endDate],
    queryFn: async () => {
      const res = await financeAPI.getReconciliation(commonParams);
      return unwrapApiData(res, { summary: { matched: true, total_absolute_difference: 0 }, rows: [] });
    },
    enabled: Boolean(workshopId),
  });

  const bulkDeleteAuditQuery = useQuery({
    queryKey: ['financial-bulk-delete-audit', workshopId],
    queryFn: async () => {
      const res = await financeAPI.getBulkDeleteAuditLogs({ workshop_id: workshopId, limit: 20 });
      return unwrapApiData(res, { rows: [], count: 0 });
    },
    enabled: Boolean(workshopId),
    placeholderData: { rows: [], count: 0 },
    refetchOnWindowFocus: false,
  });

  const chartAccountsQuery = useQuery({
    queryKey: ['financial-chart-of-accounts', workshopId],
    queryFn: async () => {
      const res = await financeAPI.getChartOfAccounts({ workshop_id: workshopId });
      return unwrapApiData(res, []);
    },
    enabled: Boolean(workshopId),
  });

  const chartAccountsForRouting = Array.isArray(chartAccountsQuery.data) ? chartAccountsQuery.data : [];
  const findAccountCodeBy = (predicate) => {
    const hit = chartAccountsForRouting.find((acc) => {
      const name = String(acc?.name || acc?.name_ar || '').toLowerCase();
      return predicate(name, String(acc?.code || '').trim(), String(acc?.type || '').toLowerCase(), acc);
    });
    return String(hit?.code || '').trim();
  };
  const revenueRootCode =
    findAccountCodeBy((name, _code, type, acc) => type === 'revenue' && !acc?.parent_id && !acc?.parentId)
    || findAccountCodeBy((name) => name.includes('الإيراد') || name.includes('ايراد'));

  const accountTreeDetailsQuery = useQuery({
    queryKey: ['financial-account-tree-details', workshopId, selectedAccount?.code, startDate, endDate, accountTreePage],
    queryFn: async () => {
      if (!selectedAccount?.code) return null;
      const res = await financeAPI.getAccountTreeDetails({
        workshop_id: workshopId,
        account_code: selectedAccount.code,
        start_date: startDate,
        end_date: endDate,
        include_descendants: true,
        page: accountTreePage,
        page_size: 20,
      });
      return unwrapApiData(res, null);
    },
    enabled: Boolean(workshopId && selectedAccount?.code),
  });

  const salesOperationsQuery = useQuery({
    queryKey: ['financial-sales-operations', workshopId, revenueRootCode, startDate, endDate, salesOpsPage],
    queryFn: async () => {
      const res = await financeAPI.getAccountTreeDetails({
        workshop_id: workshopId,
        account_code: revenueRootCode,
        start_date: startDate,
        end_date: endDate,
        include_descendants: true,
        page: salesOpsPage,
        page_size: 10,
      });
      return unwrapApiData(res, null);
    },
    enabled: Boolean(workshopId && revenueRootCode),
  });

  useEffect(() => {
    let cancelled = false;

    const runDirectCoreFallback = async () => {
      if (!workshopId) {
        if (!cancelled) setDirectCoreFallback({ income: null, balance: null });
        return;
      }

      try {
        const [incomeRes, balanceRes] = await Promise.all([
          financeAPI.getIncomeStatement(commonParams),
          financeAPI.getBalanceSheet({ workshop_id: workshopId, as_of_date: endDate }),
        ]);

        const income = incomeRes?.data?.success === false ? null : unwrapApiData(incomeRes, null);
        const balance = balanceRes?.data?.success === false ? null : unwrapApiData(balanceRes, null);

        if (!cancelled) {
          setDirectCoreFallback({ income, balance });
        }
      } catch (_error) {
        // keep last successful fallback snapshot
      }
    };

    runDirectCoreFallback();
    return () => {
      cancelled = true;
    };
  }, [workshopId, startDate, endDate]);

  useEffect(() => {
    setCoreLoadingGraceExpired(false);
    const timeoutId = setTimeout(() => setCoreLoadingGraceExpired(true), 8000);
    return () => clearTimeout(timeoutId);
  }, [workshopId, startDate, endDate]);

  const hasDirectCoreFallback = Boolean(directCoreFallback?.income || directCoreFallback?.balance);
  const hasAnyCoreSnapshot = Boolean(
    balanceSheetQuery.data
    || incomeStatementQuery.data
    || directCoreFallback?.income
    || directCoreFallback?.balance
  );

  const coreLoading = Boolean(workshopId) && !hasAnyCoreSnapshot && !coreLoadingGraceExpired && [balanceSheetQuery, incomeStatementQuery].some(
    (query) => query.isLoading && !query.data
  );

  const hasCoreError = Boolean(workshopId) && !hasAnyCoreSnapshot && [balanceSheetQuery, incomeStatementQuery].some(
    (query) => query.isError && !query.data
  );

  const hasNonBlockingError = [
    cashFlowQuery,
    trialBalanceQuery,
    budgetsQuery,
    operationTraceQuery,
    receivablesSummaryQuery,
    reconciliationQuery,
    bulkDeleteAuditQuery,
  ].some((query) => query.isError);

  const balanceData = (() => {
    const queryData = balanceSheetQuery.data;
    const totals = queryData?.totals || {};
    const hasQueryValues = Number(totals.assets || 0) !== 0 || Number(totals.liabilities || 0) !== 0 || Number(totals.equity || 0) !== 0;
    if (hasQueryValues) return queryData;
    return directCoreFallback.balance || queryData || null;
  })();

  const incomeData = (() => {
    const queryData = incomeStatementQuery.data;
    const totals = queryData?.totals || {};
    const hasQueryValues = Number(totals.revenue || 0) !== 0 || Number(totals.expenses || 0) !== 0 || Number(totals.net_income || 0) !== 0;
    if (hasQueryValues) return queryData;
    return directCoreFallback.income || queryData || null;
  })();

  const bsTotals = balanceData?.totals || { assets: 0, liabilities: 0, equity: 0 };
  const bsDetails = balanceData?.details || {};
  const incomeTotals = incomeData?.totals || { revenue: 0, expenses: 0, net_income: 0 };
  const cashFlow = cashFlowQuery.data || {};
  const trialBalance = trialBalanceQuery.data || { accounts: [], totals: { total_debit: 0, total_credit: 0 } };
  const budgetsData = budgetsQuery.data || { rows: [], totals: { planned: 0, actual: 0, variance: 0 } };
  const operationTraceData = operationTraceQuery.data || { rows: [], summary: { operations_total: 0, journal_total: 0, types_count: 0 } };
  const arSummary = receivablesSummaryQuery.data || { total_ar: 0, customers: [] };
  const reconciliation = reconciliationQuery.data || { summary: { matched: true, total_absolute_difference: 0 }, rows: [] };
  const bulkDeleteAudit = bulkDeleteAuditQuery.data || { rows: [], count: 0 };
  const isBulkDeleteAuditLoading = !bulkDeleteAuditQuery.data && (bulkDeleteAuditQuery.isLoading || bulkDeleteAuditQuery.isPending);
  const chartAccounts = chartAccountsQuery.data || [];
  const accountTree = accountTreeDetailsQuery.data || null;
  const salesOperationsData = salesOperationsQuery.data || null;
  const filteredTrialAccounts = useMemo(() => {
    const q = String(trialSearch || '').trim().toLowerCase();
    if (!q) return trialBalance.accounts || [];
    return (trialBalance.accounts || []).filter((acc) => {
      const code = String(acc?.code || '').toLowerCase();
      const name = String(acc?.name || acc?.name_ar || '').toLowerCase();
      return code.includes(q) || name.includes(q);
    });
  }, [trialBalance.accounts, trialSearch]);

  const accountNameMap = useMemo(() => {
    const map = {};
    chartAccounts.forEach((acc) => {
      const code = String(acc?.code || '').trim();
      if (!code) return;
      map[code] = acc?.name || acc?.name_ar || code;
    });
    return map;
  }, [chartAccounts]);

  const revenueEntries = Object.entries(incomeData?.details?.revenue_by_account || {});
  const expenseEntries = Object.entries(incomeData?.details?.expenses_by_account || {});

  const parseEntryAmount = (entryValue) => {
    if (typeof entryValue === 'number') return Number(entryValue || 0);
    if (entryValue && typeof entryValue === 'object') {
      return Number(entryValue.amount ?? entryValue.total ?? 0);
    }
    return Number(entryValue || 0);
  };

  const resolveReadableAccountName = (code, rawName) => {
    const fallback = rawName || '';
    if (accountNameMap[code]) return accountNameMap[code];
    if (!fallback) return code;
    const trimmed = String(fallback).trim();
    if (!trimmed || trimmed === code || /^[0-9]+$/.test(trimmed)) {
      return accountNameMap[code] || code;
    }
    return trimmed;
  };

  const normalizePaymentMethod = (value) => {
    const raw = String(value || '').trim().toLowerCase();
    if (!raw) return '';
    if (['credit', 'اجل', 'آجل', 'unpaid', 'pending', 'partial'].includes(raw)) return 'credit';
    if (['card', 'pos', 'mada', 'visa', 'mastercard', 'بطاقة', 'بطاقه', 'شبكة', 'نقاط بيع', 'نقاط_بيع'].includes(raw)) return 'pos';
    if (['bank', 'transfer', 'bank_transfer', 'تحويل', 'تحويل بنكي', 'تحويل_بنكي', 'بنك'].includes(raw)) return 'bank_transfer';
    if (['cash', 'نقد', 'نقدي', 'كاش'].includes(raw)) return 'cash';
    return raw;
  };

  const reconcileTypeLabelMap = {
    sale: 'بيع',
    purchase: 'شراء',
    expense: 'مصروف',
    sale_return: 'مرتجع بيع',
    purchase_return: 'مرتجع شراء',
    payment_order: 'أمر سداد',
  };

  const currentCashBalance = Number((incomeTotals.revenue || 0) - (incomeTotals.expenses || 0));
  const salesSummary = incomeData?.sales_summary || salesOperationsData?.operations?.summary || {
    operations_total: 0,
    operations_count: 0,
    total_credit: 0,
    total_cash_component: 0,
    total_bank_component: 0,
    total_receivable_component: 0,
    operations_cash_total: 0,
    operations_bank_total: 0,
    operations_bank_transfer_total: 0,
    operations_pos_total: 0,
    operations_credit_total: 0,
  };

  const profitMargin = incomeTotals.revenue > 0 ? (incomeTotals.net_income / incomeTotals.revenue) * 100 : 0;
  const isBalanceEquationHealthy = Math.abs((bsTotals.assets || 0) - ((bsTotals.liabilities || 0) + (bsTotals.equity || 0))) < 0.01;

  const classifyBucket = (code, rawName) => {
    const name = String(rawName || '').toLowerCase();

    if (
      name.includes('قطع') ||
      name.includes('غيار') ||
      name.includes('part')
    ) {
      return 'parts';
    }

    if (
      name.includes('خدم') ||
      name.includes('صيان') ||
      name.includes('service')
    ) {
      return 'service';
    }

    return 'other';
  };

  const revenueBreakdown = useMemo(() => {
    return revenueEntries.reduce(
      (acc, [code, value]) => {
        const amount = parseEntryAmount(value);
        const name = resolveReadableAccountName(code, value?.name);
        const bucket = classifyBucket(code, name);
        acc[bucket] += amount;
        return acc;
      },
      { parts: 0, service: 0, other: 0 }
    );
  }, [revenueEntries, accountNameMap]);

  const expenseBreakdown = useMemo(() => {
    return expenseEntries.reduce(
      (acc, [code, value]) => {
        const amount = parseEntryAmount(value);
        const name = resolveReadableAccountName(code, value?.name);
        const bucket = classifyBucket(code, name);
        acc[bucket] += amount;
        return acc;
      },
      { parts: 0, service: 0, other: 0 }
    );
  }, [expenseEntries, accountNameMap]);

  const partsNet = revenueBreakdown.parts - expenseBreakdown.parts;
  const serviceNet = revenueBreakdown.service - expenseBreakdown.service;

  const assetAccountEntries = useMemo(
    () => Object.entries(bsDetails.assets_by_account || {}),
    [bsDetails]
  );

  // Read actual current balances from the Balance Sheet `sections.assets` array
  // (this is the real post-migration balance, e.g. Bank = 16,150).
  const balanceSheetAssets = useMemo(() => balanceData?.sections?.assets || [], [balanceData]);

  const cashAccountBalance = useMemo(() => {
    // Prefer the real current balance from Balance Sheet sections
    const fromSections = balanceSheetAssets.reduce((sum, a) => {
      const name = String(a?.name || '').toLowerCase();
      if (name === 'النقد' || name === 'nقد' || name === 'cash' || name === 'الصندوق') {
        return sum + Number(a?.balance || 0);
      }
      return sum;
    }, 0);
    if (Math.abs(fromSections) > 0.0001) return fromSections;
    // Legacy fallback via assets_by_account map
    return assetAccountEntries.reduce((sum, [code, value]) => {
      const amount = parseEntryAmount(value);
      const name = resolveReadableAccountName(code, value?.name);
      const normalizedName = String(name || '').toLowerCase();
      if (
        normalizedName === 'النقد'
        || normalizedName === 'الصندوق'
        || normalizedName === 'cash'
      ) {
        return sum + amount;
      }
      return sum;
    }, 0);
  }, [balanceSheetAssets, assetAccountEntries, accountNameMap]);

  const bankAccountBalance = useMemo(() => {
    // Prefer the real current balance from Balance Sheet sections (exact match on البنك)
    const fromSections = balanceSheetAssets.reduce((sum, a) => {
      const name = String(a?.name || '').toLowerCase();
      if (name === 'البنك' || name === 'bank') {
        return sum + Number(a?.balance || 0);
      }
      return sum;
    }, 0);
    if (Math.abs(fromSections) > 0.0001) return fromSections;
    return assetAccountEntries.reduce((sum, [code, value]) => {
      const amount = parseEntryAmount(value);
      const name = resolveReadableAccountName(code, value?.name);
      const normalizedName = String(name || '').toLowerCase();
      if (normalizedName === 'البنك' || normalizedName === 'bank') {
        return sum + amount;
      }
      return sum;
    }, 0);
  }, [balanceSheetAssets, assetAccountEntries, accountNameMap]);

  const posAccountBalance = useMemo(() => {
    const fromSections = balanceSheetAssets.reduce((sum, a) => {
      const name = String(a?.name || '').toLowerCase();
      if (name === 'نقاط بيع' || name === 'pos') {
        return sum + Number(a?.balance || 0);
      }
      return sum;
    }, 0);
    return fromSections;
  }, [balanceSheetAssets]);

  const salesPaymentBreakdown = useMemo(() => ({
    cash: Number(salesSummary.operations_cash_total ?? salesSummary.total_cash_component ?? 0),
    bank_transfer: Number(salesSummary.operations_bank_transfer_total ?? salesSummary.operations_bank_total ?? salesSummary.total_bank_component ?? 0),
    pos: Number(salesSummary.operations_pos_total ?? 0),
    credit: Number(salesSummary.operations_credit_total ?? 0),
    unknown: 0,
  }), [salesSummary]);

  const normalizedCashAccountBalance = useMemo(() => {
    if (Math.abs(cashAccountBalance) > 0.0001) return cashAccountBalance;
    return 0;
  }, [cashAccountBalance]);

  const normalizedBankAccountBalance = useMemo(() => {
    if (Math.abs(bankAccountBalance) > 0.0001) return bankAccountBalance;
    return 0;
  }, [bankAccountBalance]);

  const topCards = [
    {
      key: 'net_income',
      title: 'صافي الدخل',
      value: formatCurrency(incomeTotals.net_income || 0),
      subtitle: [
        { label: 'الهامش', value: `${profitMargin.toFixed(1)}%` },
        { label: 'الإيرادات', value: formatCurrency(incomeTotals.revenue || 0) },
        { label: 'المصروفات', value: formatCurrency(incomeTotals.expenses || 0) },
      ],
      accent: incomeTotals.net_income >= 0 ? 'from-emerald-500/25 to-teal-400/10' : 'from-rose-500/25 to-pink-400/10',
      details: [
        { section: '💰 الإيراد والمصروف' },
        { label: 'إجمالي الإيرادات', value: formatCurrency(incomeTotals.revenue || 0) },
        { label: 'إجمالي المصروفات', value: formatCurrency(incomeTotals.expenses || 0) },
        { label: 'صافي الدخل', value: formatCurrency(incomeTotals.net_income || 0), highlight: true },
        { section: '💳 تفصيل المبيعات حسب طريقة الدفع' },
        { label: 'نقدي', value: formatCurrency(salesPaymentBreakdown.cash) },
        { label: 'نقاط بيع', value: formatCurrency(salesPaymentBreakdown.pos) },
        { label: 'تحويل بنكي', value: formatCurrency(salesPaymentBreakdown.bank_transfer) },
        { label: 'آجل (ذمة)', value: formatCurrency(salesPaymentBreakdown.credit) },
        { section: '🏦 الأرصدة الحالية' },
        { label: 'رصيد النقد', value: formatCurrency(normalizedCashAccountBalance) },
        { label: 'رصيد البنك', value: formatCurrency(normalizedBankAccountBalance) },
        { label: 'رصيد نقاط البيع', value: formatCurrency(posAccountBalance) },
      ],
      testId: 'financial-headline-net-income',
    },
    {
      key: 'debts',
      title: 'الذمم',
      value: formatCurrency(arSummary.total_ar || 0),
      subtitle: [
        { label: 'عدد العملاء', value: `${(arSummary.customers || []).length}` },
      ],
      accent: 'from-violet-500/25 to-blue-400/10',
      details: [
        { label: 'ذمم العملاء المدينة', value: formatCurrency(arSummary.total_ar || 0) },
        { label: 'مطلوبات الموردين (من الميزانية)', value: formatCurrency(bsTotals.liabilities || 0) },
      ],
      testId: 'financial-headline-debts',
    },
    {
      key: 'expenses',
      title: 'المصروفات',
      value: formatCurrency(incomeTotals.expenses || 0),
      subtitle: 'تفصيل المصروفات حسب النشاط',
      accent: 'from-rose-500/25 to-orange-400/10',
      details: [
        { label: 'مصروفات الخدمات', value: formatCurrency(expenseBreakdown.service || 0) },
        { label: 'مصروفات القطع', value: formatCurrency(expenseBreakdown.parts || 0) },
        { label: 'مصروفات أخرى', value: formatCurrency(expenseBreakdown.other || 0) },
      ],
      testId: 'financial-headline-expenses',
    },
    {
      key: 'parts_profit',
      title: 'أرباح القطع',
      value: formatCurrency(partsNet),
      subtitle: partsNet >= 0 ? 'القطع تحقق ربحًا' : 'القطع في منطقة خسارة',
      accent: partsNet >= 0 ? 'from-cyan-500/25 to-blue-400/10' : 'from-rose-500/25 to-pink-400/10',
      details: [
        {
          label: 'إيرادات القطع',
          value: formatCurrency(revenueBreakdown.parts || 0),
          tooltip: 'المبالغ المحصّلة من بيع القطع للعملاء (حساب 042 ايراد قطع الورشه)',
        },
        {
          label: 'تكلفة/مصروفات القطع',
          value: formatCurrency(expenseBreakdown.parts || 0),
          tooltip: 'تكلفة شراء القطع من الموردين (تُخصم من الإيراد لحساب الربح الصافي)',
        },
        {
          label: 'صافي ربح/خسارة القطع',
          value: formatCurrency(partsNet),
          tooltip: 'إيرادات القطع ناقص تكاليفها — رقم موجب = ربح، سالب = خسارة',
          highlight: true,
        },
        {
          label: 'ربح/خسارة الخدمات',
          value: formatCurrency(serviceNet),
          tooltip: 'صافي نشاط الخدمات الميكانيكية (إيرادات 027/028 ناقص مصروفاتها)',
        },
        {
          label: 'هامش الربح (القطع)',
          value: revenueBreakdown.parts > 0
            ? `${((partsNet / revenueBreakdown.parts) * 100).toFixed(1)}%`
            : '—',
          tooltip: 'نسبة الربح الصافي إلى إيراد القطع',
        },
      ],
      testId: 'financial-headline-parts-profit',
    },
  ];

  useEffect(() => {
    setSalesOpsPage(1);
  }, [startDate, endDate]);

  // 📅 Date range quick-presets
  // Fetch last-close info on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await financeAPI.getLastClose(workshopId);
        if (!cancelled) {
          setLastCloseInfo(r?.data?.data || null);
        }
      } catch {
        if (!cancelled) setLastCloseInfo(null);
      }
    })();
    return () => { cancelled = true; };
  }, [workshopId, closeResult]);

  const applyDatePreset = (presetKey) => {
    const today = new Date();
    const end = safeDate(today);
    let start;
    switch (presetKey) {
      case 'today':
        start = end;
        break;
      case 'after_close': {
        // اقفز إلى أول يوم بعد آخر قيد إقفال
        const closeDateStr = lastCloseInfo?.last_close_date;
        if (closeDateStr) {
          const cd = new Date(closeDateStr);
          cd.setDate(cd.getDate() + 1);
          start = safeDate(cd);
        } else {
          start = end;
        }
        break;
      }
      case '7d': {
        const s = new Date(today);
        s.setDate(s.getDate() - 6);
        start = safeDate(s);
        break;
      }
      case '30d': {
        const s = new Date(today);
        s.setDate(s.getDate() - 29);
        start = safeDate(s);
        break;
      }
      case '90d': {
        const s = new Date(today);
        s.setDate(s.getDate() - 89);
        start = safeDate(s);
        break;
      }
      case 'ytd': {
        start = `${today.getFullYear()}-01-01`;
        break;
      }
      case 'all':
      default:
        start = '2000-01-01';
    }
    setStartDate(start);
    setEndDate(end);
    setActivePreset(presetKey);
  };

  // 🧾 Close Period — creates a balanced closing entry
  const handleClosePeriod = async () => {
    if (closing) return;
    setClosing(true);
    setCloseResult(null);
    try {
      const res = await financeAPI.closePeriod(workshopId, {
        as_of_date: endDate,
        description: `إقفال الفترة حتى ${endDate}`,
      });
      const data = res?.data?.data || res?.data || {};
      setCloseResult({ ok: true, data });
      // 📌 NOTE: لا نُعيد ضبط التاريخ/preset هنا حتى يرى المستخدم بطاقة النجاح.
      // ينفّذ الـ reset عند ضغط زر "إغلاق" في الحوار.
    } catch (err) {
      setCloseResult({
        ok: false,
        error: err?.response?.data?.detail || err?.message || 'فشل الإقفال',
      });
    } finally {
      setClosing(false);
    }
  };

  // يُستدعى عند ضغط "إغلاق" بعد نجاح الإقفال — هنا نضبط التاريخ ونحدّث الكروت
  const dismissCloseDialog = () => {
    const wasSuccessful = closeResult?.ok === true && closeResult?.data?.closed === true;
    setShowCloseDialog(false);
    setCloseResult(null);
    if (wasSuccessful) {
      const today = safeDate(new Date());
      setStartDate(today);
      setEndDate(today);
      setActivePreset('today');
      setTimeout(() => {
        queryClient.invalidateQueries();
      }, 250);
    }
  };

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ['financial-balance-sheet', workshopId] });
    queryClient.invalidateQueries({ queryKey: ['financial-income-statement', workshopId] });
    queryClient.invalidateQueries({ queryKey: ['financial-cash-flow', workshopId] });
    queryClient.invalidateQueries({ queryKey: ['financial-trial-balance', workshopId] });
    queryClient.invalidateQueries({ queryKey: ['financial-ar-summary', workshopId] });
    queryClient.invalidateQueries({ queryKey: ['financial-reconciliation', workshopId] });
    queryClient.invalidateQueries({ queryKey: ['financial-chart-of-accounts', workshopId] });
    if (selectedAccount?.code) {
      queryClient.invalidateQueries({ queryKey: ['financial-account-tree-details', workshopId, selectedAccount.code] });
    }
    queryClient.invalidateQueries({ queryKey: ['financial-sales-operations', workshopId] });
    queryClient.invalidateQueries({ queryKey: ['financial-budgets', workshopId] });
    queryClient.invalidateQueries({ queryKey: ['financial-operation-trace', workshopId] });
  };

  const handleSaveBudget = async () => {
    if (!budgetDraft.name.trim()) return;
    await financeAPI.createBudget({
      workshop_id: workshopId,
      month: budgetMonth,
      name: budgetDraft.name.trim(),
      category: budgetDraft.category,
      planned: Number(budgetDraft.planned || 0),
      actual: Number(budgetDraft.actual || 0),
      notes: budgetDraft.notes,
    });
    setBudgetDraft({ name: '', category: 'operating', planned: '', actual: '', notes: '' });
    queryClient.invalidateQueries({ queryKey: ['financial-budgets', workshopId, budgetMonth] });
  };

  const handleDeleteBudget = async (budgetId) => {
    await financeAPI.deleteBudget(budgetId, { workshop_id: workshopId });
    queryClient.invalidateQueries({ queryKey: ['financial-budgets', workshopId, budgetMonth] });
  };

  const handleReclassifyPayments = async () => {
    try {
      setIsReclassifyingPayments(true);
      const res = await financeAPI.reclassifyPaymentAccounts({
        workshop_id: workshopId,
        start_date: '2000-01-01',
        end_date: endDate,
        apply_changes: true,
      });
      const payload = unwrapApiData(res, { candidates: 0, updated: 0 });
      setLastReclassifyResult(payload);
      refreshAll();
    } finally {
      setIsReclassifyingPayments(false);
    }
  };

  if (!workshopId) {
    return (
      <div className="max-w-4xl mx-auto p-6" dir="rtl">
        <div className="rounded-2xl border border-rose-300/40 bg-rose-500/10 p-5" data-testid="financial-missing-workshop-id-alert">
          <h2 className="text-lg font-semibold text-rose-200">تعذر تحميل اللوحة المالية</h2>
          <p className="text-sm text-rose-100 mt-1">المتغير REACT_APP_WORKSHOP_ID غير موجود في البيئة.</p>
        </div>
      </div>
    );
  }

  if (hasCoreError) {
    return (
      <div className="max-w-5xl mx-auto p-6" dir="rtl">
        <div className="rounded-3xl border border-amber-300/35 bg-amber-500/10 p-5" data-testid="financial-error-state">
          <h2 className="text-lg font-semibold text-amber-100">تعذر تحميل بعض البيانات المالية</h2>
          <p className="text-sm text-amber-50 mt-1">يمكنك إعادة التحديث الآن.</p>
          <button
            onClick={refreshAll}
            className="mt-4 rounded-xl px-4 py-2 bg-amber-500/20 border border-amber-200/35 text-amber-50"
            data-testid="financial-error-refresh-button"
          >
            إعادة التحديث
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-7xl p-4 md:p-6" dir="rtl">
      <div className="rounded-[34px] border border-white/10 bg-gradient-to-br from-[#0f172a] via-[#111827] to-[#0b1220] p-5 md:p-7 shadow-[0_35px_120px_-45px_rgba(14,165,233,0.45)]">
        <div className="absolute pointer-events-none" />

        {coreLoading && (
          <div className="mb-4 rounded-2xl border border-cyan-300/25 bg-cyan-500/10 px-4 py-2 text-xs text-cyan-100" data-testid="financial-loading-state">
            جاري تحميل البيانات الأساسية... سيتم عرض الأرقام تدريجيًا.
          </div>
        )}

        {hasNonBlockingError && (
          <div className="mb-4 rounded-2xl border border-amber-300/25 bg-amber-500/10 px-4 py-2 text-xs text-amber-100" data-testid="financial-partial-error-banner">
            بعض التقارير الفرعية لم تكتمل الآن، لكن البيانات الأساسية متاحة.
          </div>
        )}

        {lastReclassifyResult ? (
          <div className="mb-4 rounded-2xl border border-emerald-300/25 bg-emerald-500/10 px-4 py-2 text-xs text-emerald-100" data-testid="financial-reclassify-result-banner">
            تم تصحيح ربط طرق الدفع بالحسابات: مرشحات {Number(lastReclassifyResult.candidates || 0)} • تم تحديث {Number(lastReclassifyResult.updated || 0)}
          </div>
        ) : null}

        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-6">
          <div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black text-white tracking-tight" data-testid="financial-dashboard-main-title">
              لوحة المؤشرات المالية
            </h1>
            <p className="text-sm md:text-base text-slate-300 mt-3" data-testid="financial-dashboard-main-subtitle">
              تصميم زجاجي شامل مع مطابقة تلقائية بين العمليات والقيود خلال الفترة المحددة.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 rounded-2xl border border-white/15 bg-white/10 px-3 py-2" data-testid="financial-date-range-panel">
              <CalendarDays size={16} className="text-cyan-300" />
              <input
                type="date"
                value={startDate}
                onChange={(e) => { setStartDate(e.target.value); setActivePreset('custom'); }}
                className="bg-transparent text-sm text-slate-100 outline-none"
                data-testid="financial-start-date-input"
              />
              <span className="text-slate-300">إلى</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => { setEndDate(e.target.value); setActivePreset('custom'); }}
                className="bg-transparent text-sm text-slate-100 outline-none"
                data-testid="financial-end-date-input"
              />
            </div>
            <button
              onClick={refreshAll}
              className="inline-flex items-center gap-2 rounded-2xl border border-cyan-200/40 bg-cyan-500/20 px-3 py-2 text-cyan-50"
              data-testid="financial-refresh-button"
            >
              <RefreshCw size={16} />
              تحديث
            </button>
            <button
              onClick={() => setShowCloseDialog(true)}
              className="inline-flex items-center gap-2 rounded-2xl border border-amber-300/40 bg-amber-500/20 px-3 py-2 text-amber-50 font-medium hover:bg-amber-500/30 transition"
              data-testid="financial-close-period-button"
            >
              <Scale size={16} />
              إقفال الفترة
            </button>
            <button
              onClick={handleReclassifyPayments}
              disabled={isReclassifyingPayments}
              className="inline-flex items-center gap-2 rounded-2xl border border-emerald-200/40 bg-emerald-500/20 px-3 py-2 text-emerald-50 disabled:opacity-60 disabled:cursor-not-allowed"
              data-testid="financial-reclassify-payments-button"
            >
              <ShieldCheck size={16} />
              {isReclassifyingPayments ? 'جاري التصحيح...' : 'تصحيح ربط الدفع للحسابات الحالية'}
            </button>
          </div>
        </div>

        {/* 📅 Date Range Quick Presets */}
        <div className="flex flex-wrap items-center gap-1.5 mb-5" data-testid="financial-date-presets-bar">
          <span className="text-[11px] text-slate-400 ml-2">عرض:</span>
          {[
            { k: 'today', label: 'اليوم' },
            { k: 'after_close', label: 'بعد آخر إقفال' },
            { k: '7d', label: '٧ أيام' },
            { k: '30d', label: '٣٠ يوم' },
            { k: '90d', label: '٩٠ يوم' },
            { k: 'ytd', label: 'منذ بداية السنة' },
            { k: 'all', label: 'كل الفترة' },
          ].map((p) => {
            const isAfterClose = p.k === 'after_close';
            const disabled = isAfterClose && !lastCloseInfo?.last_close_date;
            return (
              <button
                key={p.k}
                type="button"
                onClick={() => !disabled && applyDatePreset(p.k)}
                disabled={disabled}
                data-testid={`financial-date-preset-${p.k}`}
                title={disabled ? 'لا يوجد قيد إقفال بعد' : undefined}
                className={`px-3 py-1.5 rounded-full text-[12px] border transition ${
                  activePreset === p.k
                    ? (isAfterClose
                        ? 'bg-amber-500/25 border-amber-300/45 text-amber-50'
                        : 'bg-cyan-500/25 border-cyan-300/45 text-cyan-50')
                    : 'bg-white/5 border-white/10 text-slate-300 hover:bg-white/10'
                } ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
              >
                {p.label}
              </button>
            );
          })}
          {lastCloseInfo?.last_close_date ? (
            <span
              data-testid="financial-last-close-badge"
              className="ml-1 px-2.5 py-1.5 rounded-full text-[11px] bg-amber-500/10 border border-amber-400/30 text-amber-100"
              title={`آخر قيد إقفال: ${lastCloseInfo.last_close_date}`}
            >
              🧾 آخر إقفال: {lastCloseInfo.last_close_date}
            </span>
          ) : null}
          {activePreset === 'custom' ? (
            <span data-testid="financial-date-preset-custom-indicator" className="px-3 py-1.5 rounded-full text-[12px] border bg-violet-500/15 border-violet-400/30 text-violet-100">
              مخصص: {startDate} → {endDate}
            </span>
          ) : null}
        </div>

        {/* 🧾 Close Period — confirmation dialog */}
        {showCloseDialog ? (
          <div
            data-testid="financial-close-period-dialog"
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
            onClick={() => !closing && dismissCloseDialog()}
          >
            <div
              className="max-w-lg w-full rounded-2xl border border-amber-400/40 bg-slate-900/95 p-5 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-2 text-amber-200 mb-3">
                <Scale size={18} />
                <h3 className="text-base font-bold">تأكيد إقفال الفترة</h3>
              </div>
              <div className="space-y-2 text-sm text-slate-200">
                <p>هذا الإجراء سيُنشئ <strong className="text-amber-200">قيداً محاسبياً متوازناً</strong> ينقل كل أرصدة الإيرادات/المصروفات إلى <strong className="text-cyan-200">الأرباح المحتجزة</strong> ويُصفّرها للبدء من جديد.</p>
                <ul className="text-xs text-slate-400 list-disc pr-5 space-y-0.5">
                  <li>تاريخ الإقفال: <span className="text-slate-200 font-mono">{endDate}</span></li>
                  <li>سيُنشأ قيد واحد متوازن (مدين = دائن)</li>
                  <li>الجدار سيرفض القيد إذا لم يكن متوازناً</li>
                  <li>الأرصدة التاريخية تُحفظ في «أرباح محتجزة» (023)</li>
                  <li>كرت صافي الدخل سيظهر صفر بعد الإقفال</li>
                </ul>
                {closeResult?.ok && closeResult?.data?.closed === true ? (
                  <div data-testid="financial-close-period-success" className="rounded-lg bg-emerald-500/10 border border-emerald-400/30 p-3 text-xs text-emerald-100 space-y-1">
                    <div>✅ تم الإقفال بنجاح</div>
                    <div>الإيرادات: {(closeResult.data.total_revenue_closed || 0).toLocaleString('ar-SA')} ر.س</div>
                    <div>المصروفات: {(closeResult.data.total_expense_closed || 0).toLocaleString('ar-SA')} ر.س</div>
                    <div>المنقول للأرباح المحتجزة: {(closeResult.data.net_income_transferred || 0).toLocaleString('ar-SA')} ر.س</div>
                    <div className="font-mono opacity-70">JE: {(closeResult.data.journal_entry_id || '').slice(0, 12)}</div>
                  </div>
                ) : null}
                {closeResult?.ok && closeResult?.data?.closed === false ? (
                  <div
                    data-testid="financial-close-period-already-closed"
                    className="rounded-lg bg-amber-500/10 border border-amber-400/30 p-3 text-xs text-amber-100 space-y-1"
                  >
                    <div className="font-semibold">ℹ️ لا حاجة للإقفال</div>
                    <div>{closeResult.data.message || 'لا توجد أرصدة لإقفالها.'}</div>
                    {closeResult.data.existing_journal_entry_id ? (
                      <div className="font-mono opacity-70">
                        قيد سابق: {String(closeResult.data.existing_journal_entry_id).slice(0, 12)}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {closeResult?.ok === false ? (
                  <div data-testid="financial-close-period-error" className="rounded-lg bg-rose-500/10 border border-rose-400/30 p-3 text-xs text-rose-100">
                    ❌ {String(closeResult.error)}
                  </div>
                ) : null}
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  data-testid="financial-close-period-cancel"
                  onClick={dismissCloseDialog}
                  disabled={closing}
                  className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-slate-200 hover:bg-white/10 disabled:opacity-50"
                >
                  إغلاق
                </button>
                {!(closeResult?.ok && closeResult?.data?.closed === true) && !(closeResult?.ok && closeResult?.data?.closed === false) ? (
                  <button
                    data-testid="financial-close-period-confirm"
                    onClick={handleClosePeriod}
                    disabled={closing}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/25 border border-amber-300/40 text-xs text-amber-50 font-medium hover:bg-amber-500/40 disabled:opacity-50"
                  >
                    <Scale size={13} className={closing ? 'animate-pulse' : ''} />
                    {closing ? 'جاري الإقفال...' : 'تأكيد الإقفال'}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-6" data-testid="financial-headline-cards-grid">
          {topCards.map((card) => (
            <ExpandableMetricCard
              key={card.key}
              title={card.title}
              value={card.value}
              subtitle={card.subtitle}
              details={card.details}
              expanded={Boolean(expandedHeadlineCards[card.key])}
              onToggle={() => setExpandedHeadlineCards((prev) => ({ ...prev, [card.key]: !prev[card.key] }))}
              testId={card.testId}
              accent={card.accent}
            />
          ))}
        </div>

        <div className="mb-6 flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`rounded-full px-4 py-2 text-sm border transition-all ${
                activeTab === tab.key
                  ? 'bg-cyan-500/30 border-cyan-300/45 text-cyan-50'
                  : 'bg-white/5 border-white/15 text-slate-300 hover:bg-white/10'
              }`}
              data-testid={`financial-tab-${tab.key}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'overview' && (
          <div className="space-y-4" data-testid="financial-overview-panel">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="rounded-3xl border border-white/15 bg-white/5 p-5">
                <h3 className="text-base font-semibold text-white flex items-center gap-2" data-testid="financial-balance-status-title">
                  <Scale size={16} className="text-cyan-300" />
                  حالة معادلة الميزانية
                </h3>
                <p className={`mt-3 text-sm ${isBalanceEquationHealthy ? 'text-emerald-300' : 'text-rose-300'}`} data-testid="financial-balance-equation-status">
                  {isBalanceEquationHealthy ? '✅ الميزانية متوازنة' : '⚠️ الميزانية غير متوازنة'}
                </p>
                <div className="mt-3 space-y-1 text-sm text-slate-200">
                  <p data-testid="financial-overview-assets">الأصول: {formatCurrency(bsTotals.assets || 0)}</p>
                  <p data-testid="financial-overview-liabilities-equity">الخصوم + حقوق الملكية: {formatCurrency((bsTotals.liabilities || 0) + (bsTotals.equity || 0))}</p>
                </div>
              </div>

              <div className="rounded-3xl border border-white/15 bg-white/5 p-5">
                <h3 className="text-base font-semibold text-white flex items-center gap-2" data-testid="financial-reconcile-summary-title">
                  <ShieldCheck size={16} className="text-violet-300" />
                  ملخص المطابقة المحاسبية
                </h3>
                <p
                  className={`mt-3 text-sm ${reconciliation.summary?.matched ? 'text-emerald-300' : 'text-amber-300'}`}
                  data-testid="financial-reconcile-summary-status"
                >
                  {reconciliation.summary?.matched ? '✅ لا توجد فروقات' : '⚠️ توجد فروقات تحتاج مراجعة'}
                </p>
                <p className="mt-2 text-sm text-slate-100" data-testid="financial-reconcile-summary-diff">
                  إجمالي الفروقات المطلقة: {formatCurrency(reconciliation.summary?.total_absolute_difference || 0)}
                </p>
                <p className="mt-1 text-xs text-slate-300" data-testid="financial-reconcile-summary-missing-journals">
                  قيود العمليات المفقودة: {reconciliation.summary?.missing_operation_journals?.count || 0}
                </p>
                <p className="mt-1 text-xs text-slate-400" data-testid="financial-reconcile-summary-unclassified-journals">
                  قيود غير مصنفة: {reconciliation.summary?.unclassified_journal_entries?.count || 0}
                </p>
              </div>
            </div>

            <div className="rounded-3xl border border-white/15 bg-white/5 p-5" data-testid="financial-operation-trace-panel">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-base font-semibold text-white" data-testid="financial-operation-trace-title">تتبّع مسار الأرقام حسب نوع العملية</h3>
                <p className="text-xs text-slate-300" data-testid="financial-operation-trace-period">
                  {startDate} → {endDate}
                </p>
              </div>

              <div className="mt-2 text-xs text-slate-300" data-testid="financial-operation-trace-explainers">
                النقد: {operationTraceData?.explainers?.cash || 'حساب النقد'} • البنك: {operationTraceData?.explainers?.bank || 'حساب البنك'} • الذمم: {operationTraceData?.explainers?.ar || 'حساب الذمم'}
              </div>

              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-white/10 text-slate-300">
                      <th className="p-2 text-right">نوع العملية</th>
                      <th className="p-2 text-right">عدد العمليات</th>
                      <th className="p-2 text-right">إجمالي العمليات</th>
                      <th className="p-2 text-right">أثر النقد (صافي)</th>
                      <th className="p-2 text-right">أثر البنك (صافي)</th>
                      <th className="p-2 text-right">أثر الذمم (صافي)</th>
                      <th className="p-2 text-right">أثر الأصول (صافي)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(operationTraceData?.rows || []).map((row, idx) => (
                      <tr key={`${row.type}-${idx}`} className="border-b border-white/5 text-slate-100" data-testid={`financial-operation-trace-row-${idx}`}>
                        <td className="p-2">{row.type_label_ar || row.type}</td>
                        <td className="p-2">{row.operations_count || 0}</td>
                        <td className="p-2">{formatCurrency(row.operations_total || 0)}</td>
                        <td className="p-2">{formatCurrency(row.impact?.cash?.net || 0)}</td>
                        <td className="p-2">{formatCurrency(row.impact?.bank?.net || 0)}</td>
                        <td className="p-2">{formatCurrency(row.impact?.ar?.net || 0)}</td>
                        <td className="p-2">{formatCurrency(row.impact?.assets?.net || 0)}</td>
                      </tr>
                    ))}
                    {!(operationTraceData?.rows || []).length && (
                      <tr>
                        <td className="p-3 text-center text-slate-400" colSpan={7} data-testid="financial-operation-trace-empty">لا توجد بيانات تتبّع ضمن الفترة.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'balance' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4" data-testid="financial-balance-panel">
            {[
              { key: 'assets', label: 'الأصول', list: balanceSheetQuery.data?.sections?.assets || [] },
              { key: 'liabilities', label: 'الخصوم', list: balanceSheetQuery.data?.sections?.liabilities || [] },
              { key: 'equity', label: 'حقوق الملكية', list: balanceSheetQuery.data?.sections?.equity || [] },
            ].map((section) => (
              <div key={section.key} className="rounded-3xl border border-white/15 bg-white/5 p-4">
                <h3 className="text-sm font-semibold text-white" data-testid={`financial-balance-${section.key}-title`}>{section.label}</h3>
                <div className="mt-3 space-y-2 max-h-[360px] overflow-y-auto">
                  {section.list.length ? section.list.map((acc, idx) => (
                    <button
                      key={`${section.key}-${idx}`}
                      type="button"
                      onClick={() => {
                        const code = String(acc.code || acc.account_code || '').trim();
                        if (!code) return;
                        setSelectedAccount({ code, name: acc.name || code });
                        setAccountTreePage(1);
                        setActiveTab('income');
                      }}
                      className="w-full text-right rounded-xl border border-white/10 bg-slate-900/45 px-3 py-2 hover:bg-slate-900/60"
                      data-testid={`financial-balance-${section.key}-source-button-${idx}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs text-slate-300" data-testid={`financial-balance-${section.key}-name-${idx}`}>{acc.name}</p>
                        <span className="text-[10px] text-cyan-200">عرض المصدر</span>
                      </div>
                      <p className="text-sm text-slate-100 font-semibold" data-testid={`financial-balance-${section.key}-value-${idx}`}>{formatCurrency(acc.balance || 0)}</p>
                    </button>
                  )) : <p className="text-xs text-slate-400" data-testid={`financial-balance-${section.key}-empty`}>لا توجد بيانات</p>}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'income' && (
          <div className="space-y-4" data-testid="financial-income-panel">
            <div className="rounded-3xl border border-cyan-300/20 bg-cyan-500/5 p-4" data-testid="financial-sales-operations-block">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                <div>
                  <h3 className="text-sm text-cyan-100 font-semibold" data-testid="financial-sales-operations-title">عمليات البيع (مع الإجمالي)</h3>
                  <p className="text-[11px] text-cyan-200/80">يعرض البيع الكلي، المحصل نقدًا، والذمم غير المسددة.</p>
                </div>
                <div className="text-xs text-cyan-100 space-y-1 text-left" data-testid="financial-sales-operations-summary">
                  <p>إجمالي البيع: <span className="font-semibold">{formatCurrency(salesSummary.operations_total || salesSummary.total_credit || 0)}</span></p>
                  <p>المحصل نقدًا: <span className="font-semibold">{formatCurrency(salesSummary.operations_cash_total || 0)}</span></p>
                  <p>المحصل بنك/بطاقة: <span className="font-semibold">{formatCurrency(salesSummary.operations_bank_total || 0)}</span></p>
                  <p>آجل غير مسدد: <span className="font-semibold">{formatCurrency(salesSummary.operations_credit_total || 0)}</span></p>
                </div>
              </div>

              {salesOperationsQuery.isLoading ? (
                <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-xs text-slate-300" data-testid="financial-sales-operations-loading-state">
                  جاري تحميل عمليات البيع...
                </div>
              ) : (
                <>
                  <div className="overflow-x-auto" data-testid="financial-sales-operations-table-wrap">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-white/10 text-slate-300">
                          <th className="p-2 text-right">التاريخ</th>
                          <th className="p-2 text-right">الوصف</th>
                          <th className="p-2 text-right">النوع</th>
                          <th className="p-2 text-right">المبلغ</th>
                          <th className="p-2 text-right">نقدي</th>
                          <th className="p-2 text-right">آجل</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(salesOperationsData?.operations?.items || []).map((item, idx) => (
                          <tr key={`${item.entry_id}-${idx}`} className="border-b border-white/5 text-slate-100">
                            <td className="p-2" data-testid={`financial-sales-op-date-${idx}`}>{String(item.date || '').slice(0, 10)}</td>
                            <td className="p-2" data-testid={`financial-sales-op-description-${idx}`}>{item.description || '-'}</td>
                            <td className="p-2" data-testid={`financial-sales-op-type-${idx}`}>{item.transaction_type_label_ar || item.transaction_type || '-'}</td>
                            <td className="p-2" data-testid={`financial-sales-op-total-${idx}`}>{formatCurrency(item.credit || 0)}</td>
                            <td className="p-2" data-testid={`financial-sales-op-cash-${idx}`}>{formatCurrency(item.cash_component || 0)}</td>
                            <td className="p-2" data-testid={`financial-sales-op-ar-${idx}`}>{formatCurrency(item.receivable_component || 0)}</td>
                          </tr>
                        ))}
                        {!(salesOperationsData?.operations?.items || []).length && (
                          <tr>
                            <td colSpan={6} className="p-4 text-center text-slate-400" data-testid="financial-sales-op-empty">لا توجد عمليات بيع ضمن الفترة.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  <div className="mt-3 flex items-center justify-between" data-testid="financial-sales-operations-pagination">
                    <button
                      type="button"
                      onClick={() => setSalesOpsPage((p) => Math.max(1, p - 1))}
                      disabled={!salesOperationsData?.operations?.pagination?.has_prev}
                      className="rounded-lg border border-white/20 px-3 py-1.5 text-xs text-slate-100 disabled:opacity-40"
                      data-testid="financial-sales-operations-prev-page-button"
                    >
                      السابق
                    </button>
                    <span className="text-xs text-slate-300" data-testid="financial-sales-operations-pagination-info">
                      صفحة {salesOperationsData?.operations?.pagination?.page || 1} / {salesOperationsData?.operations?.pagination?.total_pages || 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => setSalesOpsPage((p) => p + 1)}
                      disabled={!salesOperationsData?.operations?.pagination?.has_next}
                      className="rounded-lg border border-white/20 px-3 py-1.5 text-xs text-slate-100 disabled:opacity-40"
                      data-testid="financial-sales-operations-next-page-button"
                    >
                      التالي
                    </button>
                  </div>
                </>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="rounded-3xl border border-white/15 bg-white/5 p-4">
                <h3 className="text-sm text-emerald-300 font-semibold flex items-center gap-2" data-testid="financial-income-revenue-title">
                  <TrendingUp size={14} />
                  الإيرادات حسب الحساب
                  <span className="text-[10px] text-slate-400">(اضغط لعرض الشجرة والعمليات)</span>
                </h3>
                <div className="mt-3 space-y-2 max-h-[360px] overflow-y-auto">
                  {revenueEntries.map(([code, row], idx) => {
                    const accountName = resolveReadableAccountName(code, row?.name);
                    const isSelected = selectedAccount?.code === code;
                    return (
                      <button
                        key={code}
                        type="button"
                        onClick={() => {
                          setSelectedAccount({ code, name: accountName });
                          setAccountTreePage(1);
                        }}
                        className={`w-full text-right rounded-xl border px-3 py-2 transition-all ${isSelected ? 'border-cyan-300/50 bg-cyan-500/15' : 'border-emerald-300/15 bg-emerald-500/10 hover:bg-emerald-500/20'}`}
                        data-testid={`financial-income-revenue-account-button-${idx}`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <p className="text-xs text-emerald-100" data-testid={`financial-income-revenue-name-${idx}`}>{accountName}</p>
                            <p className="text-[10px] text-emerald-200/80">{code}</p>
                          </div>
                          {isSelected ? <ChevronDown size={14} className="text-cyan-200" /> : <ChevronRight size={14} className="text-emerald-200" />}
                        </div>
                        <p className="text-sm text-white mt-1" data-testid={`financial-income-revenue-value-${idx}`}>{formatCurrency(row.amount || 0)}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="rounded-3xl border border-white/15 bg-white/5 p-4">
                <h3 className="text-sm text-rose-300 font-semibold flex items-center gap-2" data-testid="financial-income-expenses-title">
                  <TrendingDown size={14} />
                  المصروفات حسب الحساب
                  <span className="text-[10px] text-slate-400">(اضغط لعرض الشجرة والعمليات)</span>
                </h3>
                <div className="mt-3 space-y-2 max-h-[360px] overflow-y-auto">
                  {expenseEntries.map(([code, row], idx) => {
                    const accountName = resolveReadableAccountName(code, row?.name);
                    const isSelected = selectedAccount?.code === code;
                    return (
                      <button
                        key={code}
                        type="button"
                        onClick={() => {
                          setSelectedAccount({ code, name: accountName });
                          setAccountTreePage(1);
                        }}
                        className={`w-full text-right rounded-xl border px-3 py-2 transition-all ${isSelected ? 'border-cyan-300/50 bg-cyan-500/15' : 'border-rose-300/15 bg-rose-500/10 hover:bg-rose-500/20'}`}
                        data-testid={`financial-income-expenses-account-button-${idx}`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <p className="text-xs text-rose-100" data-testid={`financial-income-expenses-name-${idx}`}>{accountName}</p>
                            <p className="text-[10px] text-rose-200/80">{code}</p>
                          </div>
                          {isSelected ? <ChevronDown size={14} className="text-cyan-200" /> : <ChevronRight size={14} className="text-rose-200" />}
                        </div>
                        <p className="text-sm text-white mt-1" data-testid={`financial-income-expenses-value-${idx}`}>{formatCurrency(row.amount || 0)}</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {selectedAccount && (
              <div className="rounded-3xl border border-cyan-300/30 bg-cyan-500/5 p-4" data-testid="financial-income-account-tree-panel">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                  <div>
                    <p className="text-xs text-cyan-200">تفاصيل الحساب المحدد</p>
                    <h4 className="text-sm font-semibold text-white" data-testid="financial-income-selected-account-name">
                      {selectedAccount.name} ({selectedAccount.code})
                    </h4>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowChildrenTree((v) => !v)}
                    className="rounded-xl border border-cyan-200/35 bg-cyan-500/15 px-3 py-1.5 text-xs text-cyan-50"
                    data-testid="financial-income-toggle-children-tree-button"
                  >
                    {showChildrenTree ? 'إخفاء الفروع' : 'إظهار الفروع'}
                  </button>
                </div>

                {showChildrenTree && (
                  <div className="mb-3" data-testid="financial-income-children-tree-list">
                    <p className="text-[11px] text-slate-300 mb-2">الحسابات الفرعية</p>
                    <div className="flex flex-wrap gap-2">
                      {(accountTree?.children || []).length ? (accountTree.children || []).map((child, idx) => (
                        <button
                          key={`${child.code}-${idx}`}
                          type="button"
                          onClick={() => {
                            setSelectedAccount({ code: child.code, name: child.name || child.code });
                            setAccountTreePage(1);
                          }}
                          className="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs text-slate-100"
                          data-testid={`financial-income-child-account-button-${idx}`}
                        >
                          {child.name} ({child.code})
                        </button>
                      )) : <span className="text-xs text-slate-400">لا توجد حسابات فرعية</span>}
                    </div>
                  </div>
                )}

                {accountTreeDetailsQuery.isLoading ? (
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-xs text-slate-300" data-testid="financial-income-account-tree-loading-state">
                    جاري تحميل تفاصيل الحساب والعمليات...
                  </div>
                ) : (
                <div className="overflow-x-auto" data-testid="financial-income-account-operations-table-wrap">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-white/10 text-slate-300">
                        <th className="p-2 text-right">التاريخ</th>
                        <th className="p-2 text-right">الوصف</th>
                        <th className="p-2 text-right">النوع</th>
                        <th className="p-2 text-right">مدين</th>
                        <th className="p-2 text-right">دائن</th>
                        <th className="p-2 text-right">حساب مقابل</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(accountTree?.operations?.items || []).map((entry, idx) => (
                        <tr key={`${entry.entry_id}-${idx}`} className="border-b border-white/5 text-slate-100">
                          <td className="p-2" data-testid={`financial-income-account-op-date-${idx}`}>{String(entry.date || '').slice(0, 10)}</td>
                          <td className="p-2" data-testid={`financial-income-account-op-desc-${idx}`}>{entry.description || '-'}</td>
                          <td className="p-2" data-testid={`financial-income-account-op-type-${idx}`}>{entry.transaction_type_label_ar || entry.transaction_type || '-'}</td>
                          <td className="p-2" data-testid={`financial-income-account-op-debit-${idx}`}>{formatCurrency(entry.debit || 0)}</td>
                          <td className="p-2" data-testid={`financial-income-account-op-credit-${idx}`}>{formatCurrency(entry.credit || 0)}</td>
                          <td className="p-2" data-testid={`financial-income-account-op-counterparts-${idx}`}>
                            {(entry.counterpart_accounts || []).map((cp) => cp.name || cp.code).join(' • ') || '-'}
                          </td>
                        </tr>
                      ))}
                      {!(accountTree?.operations?.items || []).length && (
                        <tr>
                          <td colSpan={6} className="p-4 text-center text-slate-400" data-testid="financial-income-account-op-empty">لا توجد عمليات لهذا الحساب ضمن الفترة.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                )}

                <div className="mt-3 flex items-center justify-between" data-testid="financial-income-account-pagination">
                  <button
                    type="button"
                    onClick={() => setAccountTreePage((p) => Math.max(1, p - 1))}
                    disabled={!accountTree?.operations?.pagination?.has_prev}
                    className="rounded-lg border border-white/20 px-3 py-1.5 text-xs text-slate-100 disabled:opacity-40"
                    data-testid="financial-income-account-prev-page-button"
                  >
                    السابق
                  </button>
                  <span className="text-xs text-slate-300" data-testid="financial-income-account-pagination-info">
                    صفحة {accountTree?.operations?.pagination?.page || 1} / {accountTree?.operations?.pagination?.total_pages || 1}
                  </span>
                  <button
                    type="button"
                    onClick={() => setAccountTreePage((p) => p + 1)}
                    disabled={!accountTree?.operations?.pagination?.has_next}
                    className="rounded-lg border border-white/20 px-3 py-1.5 text-xs text-slate-100 disabled:opacity-40"
                    data-testid="financial-income-account-next-page-button"
                  >
                    التالي
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'cashflow' && (
          cashFlowQuery.isLoading ? (
            <div className="rounded-2xl border border-white/15 bg-white/5 p-6 text-sm text-slate-300" data-testid="financial-cashflow-loading-state">
              جاري تحميل بيانات التدفقات النقدية...
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3" data-testid="financial-cashflow-panel">
              <GlassCard
                title="التدفق التشغيلي"
                value={formatCurrency(cashFlow.operating_activities?.net_operating_cash || 0)}
                subtitle="صافي الأنشطة التشغيلية"
                testId="financial-cash-operating"
                accent="from-emerald-500/25 to-cyan-400/10"
              />
              <GlassCard
                title="التدفق الاستثماري"
                value={formatCurrency(cashFlow.investing_activities?.net_investing_cash || 0)}
                subtitle="صافي الأنشطة الاستثمارية"
                testId="financial-cash-investing"
                accent="from-indigo-500/25 to-sky-400/10"
              />
              <GlassCard
                title="التدفق التمويلي"
                value={formatCurrency(cashFlow.financing_activities?.net_financing_cash || 0)}
                subtitle="صافي الأنشطة التمويلية"
                testId="financial-cash-financing"
                accent="from-violet-500/25 to-fuchsia-400/10"
              />
              <GlassCard
                title="صافي التغير النقدي"
                value={formatCurrency(cashFlow.net_change_in_cash || 0)}
                subtitle="خلال الفترة المحددة"
                testId="financial-cash-net-change"
                accent="from-amber-500/25 to-orange-400/10"
              />
            </div>
          )
        )}

        {activeTab === 'receivables' && (
          <div data-testid="financial-receivables-panel">
            <ARReceivablesTab />
          </div>
        )}

        {activeTab === 'trial' && (
          trialBalanceQuery.isLoading ? (
            <div className="rounded-2xl border border-white/15 bg-white/5 p-6 text-sm text-slate-300" data-testid="financial-trial-loading-state">
              جاري تحميل ميزان المراجعة...
            </div>
          ) : (
            <div className="space-y-4" data-testid="financial-trial-enhanced-panel">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <GlassCard
                  title="إجمالي المدين"
                  value={formatCurrency(trialBalance.totals?.total_debit || 0)}
                  subtitle="من ميزان المراجعة"
                  testId="financial-trial-summary-debit"
                  accent="from-cyan-500/25 to-blue-400/10"
                />
                <GlassCard
                  title="إجمالي الدائن"
                  value={formatCurrency(trialBalance.totals?.total_credit || 0)}
                  subtitle="من ميزان المراجعة"
                  testId="financial-trial-summary-credit"
                  accent="from-indigo-500/25 to-violet-400/10"
                />
                <GlassCard
                  title="فرق الميزان"
                  value={formatCurrency((trialBalance.totals?.total_debit || 0) - (trialBalance.totals?.total_credit || 0))}
                  subtitle="يفترض أن يكون قريبًا من الصفر"
                  testId="financial-trial-summary-diff"
                  accent="from-amber-500/25 to-orange-400/10"
                />
              </div>

              <div className="rounded-3xl border border-white/15 bg-white/5 p-4" data-testid="financial-trial-balance-panel">
                <div className="mb-3 flex flex-col md:flex-row gap-2 md:items-center md:justify-between">
                  <h3 className="text-sm font-semibold text-white" data-testid="financial-trial-title">ميزان المراجعة المطور</h3>
                  <input
                    type="text"
                    value={trialSearch}
                    onChange={(e) => setTrialSearch(e.target.value)}
                    placeholder="بحث بالكود أو اسم الحساب"
                    className="rounded-xl border border-white/15 bg-slate-900/40 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/40"
                    data-testid="financial-trial-search-input"
                  />
                </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-slate-200 border-b border-white/10">
                      <th className="p-3 text-right">الكود</th>
                      <th className="p-3 text-right">الحساب</th>
                      <th className="p-3 text-right">مدين</th>
                      <th className="p-3 text-right">دائن</th>
                      <th className="p-3 text-right">مصدر الرقم</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(filteredTrialAccounts || []).map((acc, idx) => (
                      <tr key={`${acc.code}-${idx}`} className="border-b border-white/5 text-slate-100">
                        <td className="p-3" data-testid={`financial-trial-code-${idx}`}>{acc.code}</td>
                        <td className="p-3" data-testid={`financial-trial-name-${idx}`}>{acc.name || acc.name_ar}</td>
                        <td className="p-3" data-testid={`financial-trial-debit-${idx}`}>{formatCurrency(acc.debit || 0)}</td>
                        <td className="p-3" data-testid={`financial-trial-credit-${idx}`}>{formatCurrency(acc.credit || 0)}</td>
                        <td className="p-3">
                          <button
                            type="button"
                            onClick={() => {
                              const code = String(acc.code || '').trim();
                              if (!code) return;
                              setSelectedAccount({ code, name: acc.name || acc.name_ar || code });
                              setAccountTreePage(1);
                              setActiveTab('income');
                            }}
                            className="rounded-lg border border-cyan-300/35 bg-cyan-500/15 px-2 py-1 text-[11px] text-cyan-100"
                            data-testid={`financial-trial-source-button-${idx}`}
                          >
                            عرض المصدر
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="text-cyan-200 font-semibold">
                      <td className="p-3" colSpan={2}>الإجمالي</td>
                      <td className="p-3" data-testid="financial-trial-total-debit">{formatCurrency(trialBalance.totals?.total_debit || 0)}</td>
                      <td className="p-3" data-testid="financial-trial-total-credit">{formatCurrency(trialBalance.totals?.total_credit || 0)}</td>
                      <td className="p-3">—</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
              </div>
            </div>
          )
        )}

        {activeTab === 'budget' && (
          <div className="space-y-4" data-testid="financial-budget-panel">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <GlassCard
                title="الموازنة المخططة"
                value={formatCurrency(budgetsData.totals?.planned || 0)}
                subtitle={`الشهر: ${budgetMonth}`}
                testId="financial-budget-planned"
                accent="from-cyan-500/25 to-blue-400/10"
              />
              <GlassCard
                title="المصروف الفعلي"
                value={formatCurrency(budgetsData.totals?.actual || 0)}
                subtitle="إجمالي البنود"
                testId="financial-budget-actual"
                accent="from-rose-500/25 to-orange-400/10"
              />
              <GlassCard
                title="الانحراف"
                value={formatCurrency(budgetsData.totals?.variance || 0)}
                subtitle="المخطط - الفعلي"
                testId="financial-budget-variance"
                accent="from-violet-500/25 to-fuchsia-400/10"
              />
            </div>

            <div className="rounded-3xl border border-white/15 bg-white/5 p-4 space-y-3" data-testid="financial-budget-editor">
              <div className="flex flex-wrap gap-2 items-center">
                <label className="text-xs text-slate-300">شهر الموازنة:</label>
                <input
                  type="month"
                  value={budgetMonth}
                  onChange={(e) => setBudgetMonth(e.target.value)}
                  className="rounded-lg border border-white/15 bg-slate-900/40 px-2 py-1.5 text-xs text-slate-100"
                  data-testid="financial-budget-month-input"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                <input
                  type="text"
                  placeholder="اسم البند"
                  value={budgetDraft.name}
                  onChange={(e) => setBudgetDraft((p) => ({ ...p, name: e.target.value }))}
                  className="rounded-lg border border-white/15 bg-slate-900/40 px-2 py-2 text-xs text-slate-100"
                  data-testid="financial-budget-name-input"
                />
                <select
                  value={budgetDraft.category}
                  onChange={(e) => setBudgetDraft((p) => ({ ...p, category: e.target.value }))}
                  className="rounded-lg border border-white/15 bg-slate-900/40 px-2 py-2 text-xs text-slate-100"
                  data-testid="financial-budget-category-select"
                >
                  <option value="operating">تشغيلي</option>
                  <option value="parts">قطع</option>
                  <option value="services">خدمات</option>
                  <option value="other">أخرى</option>
                </select>
                <input
                  type="number"
                  placeholder="المخطط"
                  value={budgetDraft.planned}
                  onChange={(e) => setBudgetDraft((p) => ({ ...p, planned: e.target.value }))}
                  className="rounded-lg border border-white/15 bg-slate-900/40 px-2 py-2 text-xs text-slate-100"
                  data-testid="financial-budget-planned-input"
                />
                <input
                  type="number"
                  placeholder="الفعلي"
                  value={budgetDraft.actual}
                  onChange={(e) => setBudgetDraft((p) => ({ ...p, actual: e.target.value }))}
                  className="rounded-lg border border-white/15 bg-slate-900/40 px-2 py-2 text-xs text-slate-100"
                  data-testid="financial-budget-actual-input"
                />
                <button
                  type="button"
                  onClick={handleSaveBudget}
                  className="inline-flex items-center justify-center gap-1 rounded-lg border border-emerald-300/35 bg-emerald-500/15 px-2 py-2 text-xs text-emerald-100"
                  data-testid="financial-budget-save-button"
                >
                  <Save size={13} />
                  إضافة بند
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-white/10 text-slate-200">
                      <th className="p-2 text-right">البند</th>
                      <th className="p-2 text-right">الفئة</th>
                      <th className="p-2 text-right">المخطط</th>
                      <th className="p-2 text-right">الفعلي</th>
                      <th className="p-2 text-right">الانحراف</th>
                      <th className="p-2 text-right">إجراء</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(budgetsData.rows || []).map((row, idx) => (
                      <tr key={row.id || idx} className="border-b border-white/5 text-slate-100" data-testid={`financial-budget-row-${idx}`}>
                        <td className="p-2">{row.name}</td>
                        <td className="p-2">{row.category}</td>
                        <td className="p-2">{formatCurrency(row.planned || 0)}</td>
                        <td className="p-2">{formatCurrency(row.actual || 0)}</td>
                        <td className="p-2">{formatCurrency((row.planned || 0) - (row.actual || 0))}</td>
                        <td className="p-2">
                          <button
                            type="button"
                            onClick={() => handleDeleteBudget(row.id)}
                            className="inline-flex items-center gap-1 rounded-md border border-rose-300/30 bg-rose-500/15 px-2 py-1 text-rose-100"
                            data-testid={`financial-budget-delete-${idx}`}
                          >
                            <Trash2 size={12} />
                            حذف
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'reconcile' && (
          <div className="space-y-4" data-testid="financial-reconciliation-tab">
            <div className="rounded-3xl border border-white/15 bg-white/5 p-4" data-testid="financial-reconciliation-panel">
              <div className="mb-3 flex items-center gap-2 text-sm text-slate-100" data-testid="financial-reconcile-panel-summary">
                {reconciliation.summary?.matched ? (
                  <ShieldCheck size={16} className="text-emerald-300" />
                ) : (
                  <AlertTriangle size={16} className="text-amber-300" />
                )}
                <span>
                  {reconciliation.summary?.matched ? 'مطابقة كاملة بين العمليات والقيود' : 'يوجد اختلاف بين العمليات والقيود'}
                </span>
              </div>
              <div className="mb-3 text-xs text-slate-300" data-testid="financial-reconcile-panel-metrics">
                <span>قيود مفقودة: {reconciliation.summary?.missing_operation_journals?.count || 0}</span>
                <span className="mx-2">|</span>
                <span>قيود غير مصنفة: {reconciliation.summary?.unclassified_journal_entries?.count || 0}</span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/10 text-slate-200">
                      <th className="p-3 text-right">النوع</th>
                      <th className="p-3 text-right">عدد العمليات</th>
                      <th className="p-3 text-right">عدد القيود</th>
                      <th className="p-3 text-right">إجمالي العمليات</th>
                      <th className="p-3 text-right">إجمالي القيود</th>
                      <th className="p-3 text-right">الفرق</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(reconciliation.rows || []).map((row, idx) => (
                      <tr key={`${row.type}-${idx}`} className="border-b border-white/5 text-slate-100">
                        <td className="p-3" data-testid={`financial-reconcile-type-${idx}`}>
                          <div className="font-medium">{row.type_label_ar || reconcileTypeLabelMap[row.type] || row.type}</div>
                          {(row.account_labels || []).length ? (
                            <div className="text-[10px] text-slate-400 mt-1" data-testid={`financial-reconcile-type-accounts-${idx}`}>
                              {(row.account_labels || []).join(' • ')}
                            </div>
                          ) : null}
                        </td>
                        <td className="p-3" data-testid={`financial-reconcile-op-count-${idx}`}>{row.operations_count}</td>
                        <td className="p-3" data-testid={`financial-reconcile-je-count-${idx}`}>{row.journal_entries_count}</td>
                        <td className="p-3" data-testid={`financial-reconcile-op-total-${idx}`}>{formatCurrency(row.operations_total || 0)}</td>
                        <td className="p-3" data-testid={`financial-reconcile-je-total-${idx}`}>{formatCurrency(row.journal_entries_total || 0)}</td>
                        <td className={`p-3 ${Math.abs(Number(row.difference || 0)) < 0.01 ? 'text-emerald-300' : 'text-amber-300'}`} data-testid={`financial-reconcile-diff-${idx}`}>
                          {formatCurrency(row.difference || 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <FinanceBulkDeleteAuditPanel rows={bulkDeleteAudit.rows || []} loading={isBulkDeleteAuditLoading} />
          </div>
        )}
      </div>
    </div>
  );
}
