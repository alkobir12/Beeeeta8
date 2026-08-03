import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Search,
  Filter,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  AlertTriangle,
  Download,
  X,
  GripHorizontal,
} from 'lucide-react';
import * as XLSX from 'xlsx';
import { resolveBackendBase } from '../utils/backendBase';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);

const typeOptions = [
  { value: 'all', label: 'الكل' },
  { value: 'asset', label: 'أصول' },
  { value: 'liability', label: 'خصوم' },
  { value: 'equity', label: 'حقوق' },
  { value: 'revenue', label: 'إيرادات' },
  { value: 'expense', label: 'مصروفات' },
];

const typeBadgeClass = {
  asset: 'bg-cyan-500/20 text-cyan-100 border-cyan-300/30',
  liability: 'bg-amber-500/20 text-amber-100 border-amber-300/30',
  equity: 'bg-indigo-500/20 text-indigo-100 border-indigo-300/30',
  revenue: 'bg-emerald-500/20 text-emerald-100 border-emerald-300/30',
  expense: 'bg-rose-500/20 text-rose-100 border-rose-300/30',
};

const formatCurrency = (value) =>
  new Intl.NumberFormat('ar-SA', {
    style: 'currency',
    currency: 'SAR',
    minimumFractionDigits: 2,
  }).format(Number(value || 0));

const Sparkline = ({ points = [] }) => {
  if (!points.length) return <div className="h-10 text-xs text-slate-400">لا توجد حركة</div>;
  const values = points.map((p) => Number(p.balance || 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const coords = values.map((v, i) => {
    const x = (i / Math.max(values.length - 1, 1)) * 100;
    const y = 36 - ((v - min) / range) * 32;
    return `${x},${y}`;
  });

  return (
    <svg viewBox="0 0 100 40" className="w-full h-10" data-testid="account-sparkline-svg">
      <polyline
        fill="none"
        stroke="rgba(251,191,36,0.95)"
        strokeWidth="1.8"
        points={coords.join(' ')}
      />
    </svg>
  );
};

const highlight = (text, query) => {
  const value = String(text || '');
  if (!query) return value;
  const q = query.toLowerCase();
  const index = value.toLowerCase().indexOf(q);
  if (index < 0) return value;
  return (
    <>
      {value.slice(0, index)}
      <mark className="bg-amber-300/70 text-slate-900 rounded px-1">{value.slice(index, index + query.length)}</mark>
      {value.slice(index + query.length)}
    </>
  );
};

export default function ChartOfAccountsLiquid() {
  const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';
  const searchRef = useRef(null);

  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [hideZero, setHideZero] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [treeMode, setTreeMode] = useState('tree');
  const [summary, setSummary] = useState({ assets: 0, liabilities: 0, net_profit: 0 });
  const [incomeSnapshot, setIncomeSnapshot] = useState({ revenue: 0, expenses: 0, net_income: 0 });
  const [accountsData, setAccountsData] = useState([]);
  const [expanded, setExpanded] = useState(new Set());
  const [recentAccounts, setRecentAccounts] = useState([]);
  const [detailsCache, setDetailsCache] = useState({});
  const [loadingDetails, setLoadingDetails] = useState({});
  const [copiedCode, setCopiedCode] = useState('');
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [sheetAccountId, setSheetAccountId] = useState('');
  const [exporting, setExporting] = useState(false);
  const [resettingAccounts, setResettingAccounts] = useState(false);
  const [reindexingCodes, setReindexingCodes] = useState(false);
  const [applyingBankPolicy, setApplyingBankPolicy] = useState(false);
  const [reconciliationLoading, setReconciliationLoading] = useState(false);
  const [reconciliationReport, setReconciliationReport] = useState(null);
  const [reconciliationCollapsed, setReconciliationCollapsed] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSearchQuery(searchInput.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    const fromStorage = JSON.parse(localStorage.getItem('recentAccounts') || '[]');
    if (Array.isArray(fromStorage)) setRecentAccounts(fromStorage.slice(0, 5));
  }, []);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    const onSlash = (e) => {
      if (e.key === '/') {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onSlash);
    return () => window.removeEventListener('keydown', onSlash);
  }, []);

  const persistRecentAccount = async (accountId) => {
    try {
      const next = [accountId, ...recentAccounts.filter((id) => id !== accountId)].slice(0, 5);
      setRecentAccounts(next);
      localStorage.setItem('recentAccounts', JSON.stringify(next));
      await fetch(`${API_URL}/accounts/${accountId}/touch`, { method: 'PATCH' });
    } catch {
      // ignore
    }
  };

  const fetchTree = async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        workshop_id: workshopId,
        type: typeFilter,
        hideZero: String(hideZero),
        search: searchQuery,
      });
      const res = await fetch(`${API_URL}/accounts/tree?${params.toString()}`);
      const json = await res.json();
      if (!res.ok || !json?.success) throw new Error(json?.detail || json?.error || 'تعذر تحميل الحسابات');

      const payload = json.data || {};
      setTreeMode(payload.mode || 'tree');
      setSummary(payload.summary || {});
      setAccountsData(payload.accounts || []);

      // Auto-expand recently used when tree mode
      if ((payload.mode || 'tree') === 'tree' && recentAccounts.length) {
        setExpanded((prev) => new Set([...Array.from(prev), ...recentAccounts]));
      }
    } catch (err) {
      setError(err?.message || 'تعذر تحميل الحسابات');
      setAccountsData([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchIncomeSnapshot = async () => {
    try {
      const params = new URLSearchParams({
        workshop_id: workshopId,
        start_date: '2000-01-01',
        end_date: new Date().toISOString().slice(0, 10),
      });
      const res = await fetch(`${API_URL}/finance/reports/income-statement?${params.toString()}`);
      const json = await res.json().catch(() => ({}));
      const totals = json?.data?.totals || {};
      setIncomeSnapshot({
        revenue: Number(totals.revenue || 0),
        expenses: Number(totals.expenses || 0),
        net_income: Number(totals.net_income || 0),
      });
    } catch {
      setIncomeSnapshot({ revenue: 0, expenses: 0, net_income: 0 });
    }
  };

  useEffect(() => {
    fetchTree();
    fetchIncomeSnapshot();
  }, [searchQuery, typeFilter, hideZero]);

  useEffect(() => {
    fetchReconciliationReport();
  }, [workshopId]);

  const loadAccountDetails = async (accountId) => {
    if (detailsCache[accountId] || loadingDetails[accountId]) return;
    setLoadingDetails((prev) => ({ ...prev, [accountId]: true }));
    try {
      const [txRes, sparkRes] = await Promise.all([
        fetch(`${API_URL}/accounts/${accountId}/transactions?workshop_id=${workshopId}&limit=10`),
        fetch(`${API_URL}/accounts/${accountId}/sparkline?workshop_id=${workshopId}&days=30`),
      ]);
      const txJson = await txRes.json().catch(() => ({}));
      const sparkJson = await sparkRes.json().catch(() => ({}));

      setDetailsCache((prev) => ({
        ...prev,
        [accountId]: {
          transactions: txJson?.data?.transactions || [],
          sparkline: sparkJson?.data?.points || [],
        },
      }));
    } finally {
      setLoadingDetails((prev) => ({ ...prev, [accountId]: false }));
    }
  };

  const toggleExpand = async (account) => {
    await persistRecentAccount(account.id);

    const hasChildren = Array.isArray(account?.children) && account.children.length > 0;

    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(account.id)) next.delete(account.id);
      else next.add(account.id);
      return next;
    });

    if (isMobile && !hasChildren) {
      setSheetAccountId(account.id);
    }

    await loadAccountDetails(account.id);
  };

  const copyCode = async (code) => {
    try {
      await navigator.clipboard.writeText(String(code || ''));
      setCopiedCode(code);
      setTimeout(() => setCopiedCode(''), 1200);
    } catch {
      setCopiedCode('');
    }
  };

  const exportExcel = async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams({
        workshop_id: workshopId,
        type: typeFilter,
        hideZero: String(hideZero),
        search: searchQuery,
      });
      const res = await fetch(`${API_URL}/accounts/export?${params.toString()}`);
      const json = await res.json();
      const rows = json?.data?.rows || [];
      const worksheet = XLSX.utils.json_to_sheet(rows);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Accounts');
      XLSX.writeFile(workbook, 'chart_of_accounts_filtered.xlsx');
    } finally {
      setExporting(false);
    }
  };

  const resetAccounts = async () => {
    const ok = window.confirm('سيتم إعادة ضبط دليل الحسابات للقيم الافتراضية. هل تريد المتابعة؟');
    if (!ok) return;
    setResettingAccounts(true);
    try {
      const res = await fetch(`${API_URL}/accounts/init-defaults`, { method: 'POST' });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || json?.success === false) throw new Error(json?.detail || json?.error || 'فشل إعادة الضبط');
      await fetchTree();
      await fetchIncomeSnapshot();
      alert('تمت إعادة ضبط الحسابات بنجاح');
    } catch (error) {
      alert(error?.message || 'تعذر إعادة ضبط الحسابات');
    } finally {
      setResettingAccounts(false);
    }
  };

  const reindexDisplayCodes = async () => {
    setReindexingCodes(true);
    try {
      const res = await fetch(`${API_URL}/accounts/reindex-display-codes`, { method: 'POST' });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || json?.success === false) {
        throw new Error(json?.detail || json?.error || 'تعذر إعادة الترقيم');
      }
      await fetchTree();
      await fetchIncomeSnapshot();
      await fetchReconciliationReport();
      alert(`تمت إعادة الترقيم بنجاح من 001 (${json?.data?.count || 0} حساب)`);
    } catch (error) {
      alert(error?.message || 'تعذر إعادة الترقيم');
    } finally {
      setReindexingCodes(false);
    }
  };

  const applyBankRevenuePolicy = async () => {
    const ok = window.confirm('سيتم تحويل ربط الإيرادات التاريخية للبنك وتصفير الكاش تاريخيًا + التأكد من حساب نقاط البيع. هل تريد المتابعة؟');
    if (!ok) return;

    setApplyingBankPolicy(true);
    try {
      const params = new URLSearchParams({
        workshop_id: workshopId,
        apply_changes: 'true',
      });
      const res = await fetch(`${API_URL}/finance/reports/repost-bank-and-fix-imbalance?${params.toString()}`, {
        method: 'POST',
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || json?.success === false) {
        throw new Error(json?.detail || json?.error || json?.message || 'تعذر تطبيق السياسة');
      }

      await fetchTree();
      await fetchIncomeSnapshot();
      await fetchReconciliationReport();

      const journalUpdated = json?.data?.migration?.journal?.updated || 0;
      const operationsUpdated = json?.data?.migration?.operations?.updated || 0;
      const fixedBlanks = json?.data?.repair?.fixed_blank_lines || 0;
      const balancingLines = json?.data?.repair?.added_balance_lines || 0;
      const tbDiff = json?.data?.trial_balance_after?.difference ?? 0;
      alert(`تم تطبيق السياسة والترحيل المحاسبي\nقيود سياسة البنك: ${journalUpdated}\nعمليات محدثة: ${operationsUpdated}\nأسطر فارغة مصححة: ${fixedBlanks}\nأسطر موازنة مضافة: ${balancingLines}\nفرق الميزان بعد المعالجة: ${tbDiff}`);
    } catch (error) {
      alert(error?.message || 'تعذر تطبيق السياسة');
    } finally {
      setApplyingBankPolicy(false);
    }
  };

  const fetchReconciliationReport = async () => {
    setReconciliationLoading(true);
    try {
      const params = new URLSearchParams({ workshop_id: workshopId });
      const res = await fetch(`${API_URL}/accounts/reconciliation-report?${params.toString()}`);
      const json = await res.json().catch(() => ({}));
      if (!res.ok || json?.success === false) {
        throw new Error(json?.detail || json?.error || 'تعذر تحميل تقرير التطابق');
      }
      setReconciliationReport(json?.data || null);
    } catch (error) {
      setReconciliationReport({
        summary: { accounts_count: 0, matched_count: 0, mismatched_count: 0, max_abs_difference: 0 },
        rows: [],
        error: error?.message || 'تعذر تحميل تقرير التطابق',
      });
    } finally {
      setReconciliationLoading(false);
    }
  };

  const accountById = useMemo(() => {
    const map = {};
    const stack = [...accountsData];
    while (stack.length) {
      const item = stack.pop();
      if (!item) continue;
      map[item.id] = item;
      if (Array.isArray(item.children)) stack.push(...item.children);
    }
    return map;
  }, [accountsData]);

  const findAccountByName = (keywords = []) => {
    const candidates = Object.values(accountById).filter((acc) => {
      if (acc?.type && acc.type !== 'asset') return false;
      const name = String(acc?.name || '').trim();
      if (!name) return false;
      const lower = name.toLowerCase();
      return keywords.some((k) => {
        const key = k.toLowerCase();
        return lower === key || lower === `ال${key}`;
      });
    });
    if (candidates.length === 0) return null;
    // Prefer the account with non-zero activity (or balance), then smallest code.
    candidates.sort((a, b) => {
      const aActive = (Number(a.transaction_count || 0) > 0 || Math.abs(Number(a.balance || 0)) > 0) ? 1 : 0;
      const bActive = (Number(b.transaction_count || 0) > 0 || Math.abs(Number(b.balance || 0)) > 0) ? 1 : 0;
      if (aActive !== bActive) return bActive - aActive;
      const aCode = String(a.code || '');
      const bCode = String(b.code || '');
      const aNum = parseInt(aCode, 10);
      const bNum = parseInt(bCode, 10);
      if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
      return aCode.localeCompare(bCode);
    });
    return candidates[0];
  };

  const bankAccountNode = findAccountByName(['بنك', 'bank']);
  const cashAccountNode = findAccountByName(['نقد', 'cash', 'صندوق']);
  const posAccountNode = findAccountByName(['نقاط بيع', 'pos']);

  const bankCodeLabel = bankAccountNode?.code || '---';
  const cashCodeLabel = cashAccountNode?.code || '---';
  const posCodeLabel = posAccountNode?.code || '---';

  const bankBalance = Number(bankAccountNode?.balance || 0);
  const cashBalance = Number(cashAccountNode?.balance || 0);
  const posBalance = Number(posAccountNode?.balance || 0);

  const selectedSheetAccount = sheetAccountId ? accountById[sheetAccountId] : null;

  const renderExpandedContent = (account) => {
    const details = detailsCache[account.id] || { transactions: [], sparkline: [] };
    const isLoadingDetails = loadingDetails[account.id];

    return (
      <div className="mt-3 rounded-2xl border border-white/10 bg-slate-900/45 p-3" data-testid={`coa-account-expanded-${account.id}`}>
        {isLoadingDetails ? (
          <div className="space-y-2" data-testid={`coa-account-expanded-loading-${account.id}`}>
            <div className="h-3 bg-white/10 rounded animate-pulse" />
            <div className="h-3 bg-white/10 rounded animate-pulse" />
            <div className="h-16 bg-white/10 rounded animate-pulse" />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 text-xs mb-3">
              <div className="rounded-lg bg-white/5 p-2" data-testid={`coa-account-balance-${account.id}`}>الرصيد: {formatCurrency(account.balance)}</div>
              <div className="rounded-lg bg-white/5 p-2" data-testid={`coa-account-debit-${account.id}`}>مدين: {formatCurrency(account.total_debit)}</div>
              <div className="rounded-lg bg-white/5 p-2" data-testid={`coa-account-credit-${account.id}`}>دائن: {formatCurrency(account.total_credit)}</div>
              <div className="rounded-lg bg-white/5 p-2" data-testid={`coa-account-tx-count-${account.id}`}>العمليات: {account.transaction_count || 0}</div>
            </div>

            <Sparkline points={details.sparkline} />

            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-xs" data-testid={`coa-account-transactions-table-${account.id}`}>
                <thead>
                  <tr className="text-slate-300 border-b border-white/10">
                    <th className="p-2 text-right">التاريخ</th>
                    <th className="p-2 text-right">الوصف</th>
                    <th className="p-2 text-right">مدين</th>
                    <th className="p-2 text-right">دائن</th>
                    <th className="p-2 text-right">الرصيد</th>
                  </tr>
                </thead>
                <tbody>
                  {(details.transactions || []).map((tx, idx) => (
                    <tr key={`${tx.id}-${idx}`} className="border-b border-white/5">
                      <td className="p-2">{String(tx.date || '').slice(0, 10)}</td>
                      <td className="p-2">{tx.description || '-'}</td>
                      <td className="p-2">{formatCurrency(tx.debit || 0)}</td>
                      <td className="p-2">{formatCurrency(tx.credit || 0)}</td>
                      <td className="p-2">{formatCurrency(tx.balance || 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => (window.location.href = `/accounting/journal-entries?account=${encodeURIComponent(account.code)}`)}
                className="rounded-lg bg-amber-500/25 text-amber-100 border border-amber-300/30 px-3 py-1.5 text-xs"
                data-testid={`coa-account-view-ledger-${account.id}`}
              >
                عرض كل العمليات
              </button>
              <button
                type="button"
                onClick={() => copyCode(account.code)}
                className="rounded-lg bg-white/10 border border-white/20 px-3 py-1.5 text-xs inline-flex items-center gap-2"
                data-testid={`coa-account-copy-code-${account.id}`}
              >
                {copiedCode === account.code ? <Check size={14} /> : <Copy size={14} />} نسخ الكود
              </button>
            </div>
          </>
        )}
      </div>
    );
  };

  const renderNode = (account, depth = 0) => {
    const isExpanded = expanded.has(account.id);
    const children = Array.isArray(account.children) ? account.children : [];
    const showExpandIcon = treeMode === 'tree' && children.length > 0;

    return (
      <div key={account.id} className="space-y-2" data-testid={`coa-account-card-${account.id}`}>
        <div
          className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-3 transition-all duration-300 hover:bg-white/10"
          style={{ marginRight: `${depth * 14}px` }}
        >
          <button
            type="button"
            onClick={() => toggleExpand(account)}
            className="w-full text-right"
            data-testid={`coa-account-toggle-${account.id}`}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                {showExpandIcon ? (
                  isExpanded ? <ChevronDown size={16} className="text-slate-300" /> : <ChevronRight size={16} className="text-slate-300" />
                ) : (
                  <span className="w-4" />
                )}

                <span className="text-xs text-amber-200 font-mono" data-testid={`coa-account-code-${account.id}`}>{account.code}</span>
                <span className="text-sm text-slate-100 truncate" data-testid={`coa-account-name-${account.id}`}>{highlight(account.name, searchQuery)}</span>
                <span className={`text-[10px] border rounded-full px-2 py-0.5 ${typeBadgeClass[account.type] || 'bg-white/10 border-white/20'}`}>
                  {(typeOptions.find((t) => t.value === account.type)?.label) || account.type}
                </span>
                {account.warning_negative ? (
                  <span className="inline-flex items-center gap-1 text-[10px] text-amber-100 bg-amber-500/20 border border-amber-300/30 px-2 py-0.5 rounded-full" data-testid={`coa-account-warning-${account.id}`}>
                    <AlertTriangle size={12} /> ⚠️ يحتاج مراجعة
                  </span>
                ) : null}
              </div>

              <div className="text-xs text-slate-200" data-testid={`coa-account-balance-chip-${account.id}`}>{formatCurrency(account.balance)}</div>
            </div>
          </button>

          {!isMobile && isExpanded && renderExpandedContent(account)}
        </div>

        {treeMode === 'tree' && children.length > 0 && isExpanded && (
          <div className="border-r border-white/10 mr-2 pr-2">
            {children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen p-3 md:p-6" dir="rtl" data-testid="chart-of-accounts-liquid-page">
      <div className="max-w-7xl mx-auto space-y-4">
        <div className="sticky top-0 z-20 rounded-2xl border border-white/10 bg-slate-900/80 backdrop-blur-xl p-3 md:p-4" data-testid="coa-sticky-filter-bar">
          <div className="flex flex-col md:flex-row md:flex-wrap gap-2 items-stretch md:items-center">
            <div className="relative md:flex-1 md:min-w-[320px]">
              <Search size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                ref={searchRef}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="بحث بالاسم أو الكود..."
                className="w-full rounded-xl border border-white/15 bg-white/5 pr-9 pl-3 py-2 text-sm text-slate-100 placeholder:text-slate-400 outline-none"
                data-testid="coa-search-input"
              />
            </div>

            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-slate-100 md:min-w-[130px]"
              data-testid="coa-type-filter-select"
            >
              {typeOptions.map((opt) => (
                <option key={opt.value} value={opt.value} className="text-slate-900">{opt.label}</option>
              ))}
            </select>

            <label className="inline-flex items-center gap-2 text-sm text-slate-200 whitespace-nowrap" data-testid="coa-hide-zero-toggle-wrap">
              <input
                type="checkbox"
                checked={hideZero}
                onChange={(e) => setHideZero(e.target.checked)}
                data-testid="coa-hide-zero-toggle"
              />
              إخفاء الأرصدة الصفرية
            </label>

            <div className="flex flex-wrap items-center gap-2 md:mr-auto">
              <button
                type="button"
                onClick={reindexDisplayCodes}
                disabled={reindexingCodes}
                className="rounded-xl border border-cyan-300/40 bg-cyan-500/20 text-cyan-50 px-3 py-2 text-sm inline-flex items-center gap-2 disabled:opacity-50"
                data-testid="coa-reindex-display-codes-button"
              >
                <Filter size={14} /> {reindexingCodes ? 'جارٍ إعادة الترقيم...' : 'إعادة ترقيم 001'}
              </button>

              <button
                type="button"
                onClick={applyBankRevenuePolicy}
                disabled={applyingBankPolicy}
                className="rounded-xl border border-emerald-300/40 bg-emerald-500/20 text-emerald-50 px-3 py-2 text-sm inline-flex items-center gap-2 disabled:opacity-50"
                data-testid="coa-apply-bank-policy-button"
              >
                <Filter size={14} /> {applyingBankPolicy ? 'جارٍ التطبيق...' : 'تطبيق سياسة البنك/الكاش'}
              </button>

              <button
                type="button"
                onClick={fetchReconciliationReport}
                disabled={reconciliationLoading}
                className="rounded-xl border border-indigo-300/40 bg-indigo-500/20 text-indigo-50 px-3 py-2 text-sm inline-flex items-center gap-2 disabled:opacity-50"
                data-testid="coa-refresh-reconciliation-button"
              >
                <Download size={14} /> {reconciliationLoading ? 'جارٍ التدقيق...' : 'تحديث تدقيق التطابق'}
              </button>

              {!isMobile && (
                <button
                  type="button"
                  onClick={resetAccounts}
                  disabled={resettingAccounts}
                  className="rounded-xl border border-rose-300/40 bg-rose-500/20 text-rose-50 px-3 py-2 text-sm inline-flex items-center gap-2 disabled:opacity-50"
                  data-testid="coa-reset-accounts-button"
                >
                  <Filter size={14} /> {resettingAccounts ? 'جارٍ إعادة الضبط...' : 'إعادة ضبط الحسابات'}
                </button>
              )}

              {!isMobile && (
                <button
                  type="button"
                  onClick={exportExcel}
                  disabled={exporting}
                  className="rounded-xl border border-amber-300/40 bg-amber-500/20 text-amber-50 px-3 py-2 text-sm inline-flex items-center gap-2"
                  data-testid="coa-export-excel-button"
                >
                  <Download size={14} /> {exporting ? 'جاري التصدير...' : 'تصدير Excel'}
                </button>
              )}
            </div>
          </div>

          {/* Top summary bar — 5 financial totals as cards */}
          <div
            className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2"
            data-testid="coa-summary-bar"
          >
            {[
              { label: 'إجمالي الأصول', value: summary.assets, tone: 'emerald' },
              { label: 'إجمالي الخصوم', value: summary.liabilities, tone: 'rose' },
              { label: 'الإيرادات', value: incomeSnapshot.revenue, tone: 'sky' },
              { label: 'المصروفات + المشتريات', value: incomeSnapshot.expenses, tone: 'amber' },
              { label: 'الصافي', value: incomeSnapshot.net_income, tone: (incomeSnapshot.net_income || 0) >= 0 ? 'cyan' : 'rose' },
            ].map((s) => (
              <div
                key={s.label}
                className={`rounded-xl border px-3 py-2 bg-slate-950/40 ${
                  {
                    emerald: 'border-emerald-300/25',
                    rose: 'border-rose-300/25',
                    sky: 'border-sky-300/25',
                    amber: 'border-amber-300/25',
                    cyan: 'border-cyan-300/25',
                  }[s.tone] || 'border-white/10'
                }`}
                data-testid={`coa-summary-stat-${s.label}`}
              >
                <p className="text-[11px] text-slate-400 leading-tight truncate">{s.label}</p>
                <p className={`mt-0.5 text-sm font-semibold tabular-nums ${
                  {
                    emerald: 'text-emerald-100',
                    rose: 'text-rose-100',
                    sky: 'text-sky-100',
                    amber: 'text-amber-100',
                    cyan: 'text-cyan-100',
                  }[s.tone] || 'text-slate-100'
                }`}>{formatCurrency(s.value)}</p>
              </div>
            ))}
          </div>

          {/* Bank / Cash / POS / Total Revenue cards */}
          <div
            className="mt-2 grid grid-cols-2 lg:grid-cols-4 gap-2"
            data-testid="coa-cash-bank-pos-summary-bar"
          >
            <div className="rounded-xl border border-cyan-300/25 bg-slate-950/40 px-3 py-2" data-testid="coa-bank-balance-summary">
              <p className="text-[11px] text-slate-400 leading-tight">البنك <span className="text-cyan-300">({bankCodeLabel})</span></p>
              <p className="mt-0.5 text-sm font-semibold text-cyan-100 tabular-nums">{formatCurrency(bankBalance)}</p>
            </div>
            <div className="rounded-xl border border-emerald-300/25 bg-slate-950/40 px-3 py-2" data-testid="coa-cash-balance-summary">
              <p className="text-[11px] text-slate-400 leading-tight">النقد <span className="text-emerald-300">({cashCodeLabel})</span></p>
              <p className="mt-0.5 text-sm font-semibold text-emerald-100 tabular-nums">{formatCurrency(cashBalance)}</p>
            </div>
            <div className="rounded-xl border border-violet-300/25 bg-slate-950/40 px-3 py-2" data-testid="coa-pos-balance-summary">
              <p className="text-[11px] text-slate-400 leading-tight">نقاط بيع <span className="text-violet-300">({posCodeLabel})</span></p>
              <p className="mt-0.5 text-sm font-semibold text-violet-100 tabular-nums">{formatCurrency(posBalance)}</p>
            </div>
            <div className="rounded-xl border border-sky-300/25 bg-slate-950/40 px-3 py-2" data-testid="coa-revenue-summary">
              <p className="text-[11px] text-slate-400 leading-tight">إجمالي الإيراد</p>
              <p className="mt-0.5 text-sm font-semibold text-sky-100 tabular-nums">{formatCurrency(incomeSnapshot.revenue)}</p>
            </div>
          </div>
        </div>

        {recentAccounts.length > 0 && (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3" data-testid="coa-recent-accounts-row">
            <p className="text-xs text-slate-300 mb-2">الحسابات الأخيرة</p>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {recentAccounts.map((id) => {
                const acc = accountById[id];
                if (!acc) return null;
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => toggleExpand(acc)}
                    className="shrink-0 rounded-full border border-cyan-300/30 bg-cyan-500/15 text-cyan-50 px-3 py-1 text-xs"
                    data-testid={`coa-recent-account-chip-${id}`}
                  >
                    {acc.name}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="rounded-2xl border border-white/10 bg-white/5 p-3" data-testid="coa-reconciliation-panel">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <h2 className="text-sm font-semibold text-slate-100" data-testid="coa-reconciliation-title">تدقيق تطابق مبالغ الحسابات</h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setReconciliationCollapsed((prev) => !prev)}
                className="rounded-lg border border-white/20 bg-white/10 px-3 py-1.5 text-xs text-slate-100"
                data-testid="coa-reconciliation-collapse-toggle-button"
              >
                {reconciliationCollapsed ? 'فتح التدقيق' : 'طي التدقيق'}
              </button>
              <button
                type="button"
                onClick={fetchReconciliationReport}
                disabled={reconciliationLoading}
                className="rounded-lg border border-white/20 bg-white/10 px-3 py-1.5 text-xs text-slate-100 disabled:opacity-50"
                data-testid="coa-reconciliation-refresh-inline-button"
              >
                {reconciliationLoading ? 'جارٍ الفحص...' : 'إعادة الفحص'}
              </button>
            </div>
          </div>

          {!reconciliationCollapsed ? (
            <>
              <div className="text-xs text-slate-200 flex flex-wrap gap-3" data-testid="coa-reconciliation-summary">
                <span>إجمالي الحسابات: {reconciliationReport?.summary?.accounts_count || 0}</span>
                <span>مطابق: {reconciliationReport?.summary?.matched_count || 0}</span>
                <span>غير مطابق: {reconciliationReport?.summary?.mismatched_count || 0}</span>
                <span>أكبر فرق: {formatCurrency(reconciliationReport?.summary?.max_abs_difference || 0)}</span>
              </div>

              {!!reconciliationReport?.error && (
                <div className="mt-2 text-xs text-rose-200" data-testid="coa-reconciliation-error-message">
                  {reconciliationReport.error}
                </div>
              )}

              <div className="mt-3 overflow-x-auto" data-testid="coa-reconciliation-table-wrap">
                <table className="w-full min-w-[760px] text-xs" data-testid="coa-reconciliation-table">
                  <thead>
                    <tr className="text-slate-300 border-b border-white/10">
                      <th className="p-2 text-right">الكود</th>
                      <th className="p-2 text-right">الحساب</th>
                      <th className="p-2 text-right">الرصيد</th>
                      <th className="p-2 text-right">الرصيد المتوقع</th>
                      <th className="p-2 text-right">الفرق</th>
                      <th className="p-2 text-right">الحالة</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(reconciliationReport?.rows || []).slice(0, 30).map((row, idx) => (
                      <tr key={`${row.account_id}-${idx}`} className="border-b border-white/5" data-testid={`coa-reconciliation-row-${idx}`}>
                        <td className="p-2 font-mono">{row.code}</td>
                        <td className="p-2">{row.name}</td>
                        <td className="p-2">{formatCurrency(row.balance || 0)}</td>
                        <td className="p-2">{formatCurrency(row.expected_balance || 0)}</td>
                        <td className="p-2">{formatCurrency(row.difference || 0)}</td>
                        <td className="p-2">
                          <span
                            className={`rounded-full px-2 py-0.5 ${row.matched ? 'bg-emerald-500/20 text-emerald-100' : 'bg-rose-500/20 text-rose-100'}`}
                            data-testid={`coa-reconciliation-status-${idx}`}
                          >
                            {row.matched ? 'مطابق' : 'يحتاج مراجعة'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="text-xs text-slate-300" data-testid="coa-reconciliation-collapsed-note">
              تم طي التدقيق. اضغط &quot;فتح التدقيق&quot; لعرض التفاصيل.
            </div>
          )}
        </div>

        {loading ? (
          <div className="space-y-3" data-testid="coa-loading-skeleton">
            {Array.from({ length: 5 }).map((_, idx) => (
              <div key={idx} className="h-16 rounded-2xl bg-white/10 animate-pulse" />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-rose-300/30 bg-rose-500/10 text-rose-100 p-4" data-testid="coa-error-state">
            {error}
          </div>
        ) : (
          <div className="space-y-3" data-testid="coa-accounts-list-wrap">
            {accountsData.map((account) => renderNode(account, 0))}
            {!accountsData.length && (
              <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-center text-slate-300" data-testid="coa-empty-state">
                لا توجد حسابات مطابقة للفلاتر.
              </div>
            )}
          </div>
        )}
      </div>

      {isMobile && (
        <button
          type="button"
          onClick={exportExcel}
          className="fixed bottom-6 right-6 z-30 h-12 w-12 rounded-full bg-amber-500/90 text-slate-900 flex items-center justify-center shadow-lg"
          data-testid="coa-mobile-export-fab"
        >
          <Download size={18} />
        </button>
      )}

      {isMobile && sheetAccountId && selectedSheetAccount && (
        <>
          <button
            type="button"
            onClick={() => setSheetAccountId('')}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            data-testid="coa-mobile-sheet-backdrop"
          />

          <div className="fixed bottom-0 left-0 right-0 z-50 rounded-t-3xl border border-white/10 bg-slate-900 p-4 max-h-[78vh] overflow-y-auto" data-testid="coa-mobile-bottom-sheet">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <GripHorizontal size={16} className="text-slate-400" />
                <div>
                  <p className="text-sm text-slate-100">{selectedSheetAccount.name}</p>
                  <p className="text-xs text-slate-400">{selectedSheetAccount.code}</p>
                </div>
              </div>
              <button type="button" onClick={() => setSheetAccountId('')} data-testid="coa-mobile-sheet-close">
                <X size={18} className="text-slate-300" />
              </button>
            </div>

            {renderExpandedContent(selectedSheetAccount)}
          </div>
        </>
      )}
    </div>
  );
}
