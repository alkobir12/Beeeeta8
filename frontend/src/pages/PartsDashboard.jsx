import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BarChart3, Boxes, ClipboardList, Loader2, RefreshCw, ShoppingCart, TrendingUp, Wrench, Cog, Receipt } from 'lucide-react';
import { api, financeAPI, operationsAPI, partAPI } from '../services/api';
import { Button } from '../components/ui/button';
import { InventoryPlannerTab } from '../components/parts-dashboard/InventoryPlannerTab';

const formatCurrency = (value) => `${Number(value || 0).toLocaleString('ar-SA')} ر.س`;

const pctClass = (value) => {
  if (value > 0) return 'text-rose-300';
  if (value < 0) return 'text-emerald-300';
  return 'text-slate-300';
};

const deltaTone = (value) => {
  if (value > 0) return 'text-emerald-300';
  if (value < 0) return 'text-rose-300';
  return 'text-slate-300';
};

const HIGH_VOLATILITY_THRESHOLD = 15;

const formatLearningStatus = (value, ready, samples) => {
  if (ready) {
    return formatCurrency(value);
  }
  return `قيد التعلم (${samples}/5)`;
};

const backorderStatusOptions = [
  { value: 'all', label: 'الكل' },
  { value: 'pending', label: 'قيد الانتظار' },
  { value: 'ordered', label: 'تم الطلب' },
  { value: 'arrived', label: 'وصلت' },
  { value: 'cancelled', label: 'ملغية' },
];

const normalizeText = (value) => String(value || '').trim().toLowerCase();

const normalizeAccountCode = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (raw.startsWith('acc-') && /^acc-\d+$/.test(raw)) return raw.replace('acc-', '');
  return raw;
};

const WORKSHOP_ACCOUNT_TARGETS = [
  {
    key: 'workshop-parts-revenue',
    title: 'إيراد قطع الورشة',
    icon: Wrench,
    color: '#22c55e',
    accountType: 'revenue',
    codes: ['041', '042'],
    keywords: ['ايراد قطع الورشه', 'إيراد قطع الورشة', 'ايراد قطع الورشة', 'إيراد قطع الورشه'],
  },
  {
    key: 'workshop-parts-cost',
    title: 'تكلفة قطع الورشة',
    icon: Receipt,
    color: '#f97316',
    accountType: 'expense',
    codes: ['167', '0421'],
    keywords: ['تكلفة قطع الورشة', 'تكلفة قطع الورشه'],
  },
  {
    key: 'engine-repair',
    title: 'حساب إصلاح المحركات',
    icon: Cog,
    color: '#f59e0b',
    codes: [],
    keywords: ['إصلاح المحركات', 'اصلاح المحركات', 'إصلاح محركات', 'اصلاح محركات'],
  },
];

const PartsDashboard = () => {
  const [daysFilter, setDaysFilter] = useState(30);
  const [analytics, setAnalytics] = useState(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);
  const [backorders, setBackorders] = useState([]);
  const [backorderStatusFilter, setBackorderStatusFilter] = useState('all');
  const [loadingBackorders, setLoadingBackorders] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [inventoryArchitecture, setInventoryArchitecture] = useState(null);
  const [loadingInventoryArchitecture, setLoadingInventoryArchitecture] = useState(true);
  const [workshopAccountStats, setWorkshopAccountStats] = useState([]);
  const [loadingWorkshopAccountStats, setLoadingWorkshopAccountStats] = useState(true);
  const [savingBackorder, setSavingBackorder] = useState(false);
  const [resettingTotals, setResettingTotals] = useState(false);
  const [partsList, setPartsList] = useState([]);
  const [formData, setFormData] = useState({
    part_id: '',
    part_name: '',
    requested_quantity: 1,
    customer_name: '',
    customer_phone: '',
    vehicle_reference: '',
    expected_date: '',
    note: '',
  });

  const buildWorkshopAccountCards = (accounts, operations) => {
    const periodStart = Date.now() - (Number(daysFilter || 30) * 24 * 60 * 60 * 1000);
    return WORKSHOP_ACCOUNT_TARGETS.map((target) => {
      const account = accounts.find((acc) => {
        const accCode = String(acc?.code || '').trim();
        if (target.codes && target.codes.length > 0 && target.codes.includes(accCode)) {
          return true;
        }
        const haystack = [acc?.name, acc?.name_ar, acc?.code].map((v) => normalizeText(v)).join(' ');
        return target.keywords.some((keyword) => haystack.includes(normalizeText(keyword)));
      });

      if (!account) {
        return {
          ...target,
          accountFound: false,
          accountName: 'غير موجود',
          balance: 0,
          periodOpsCount: 0,
          periodAmount: 0,
          lastMovementDate: null,
        };
      }

      const accountIds = new Set([
        normalizeText(account?.id),
        normalizeText(account?.code),
        normalizeText(normalizeAccountCode(account?.code)),
      ].filter(Boolean));

      const matchedOps = operations.filter((op) => {
        const possibleIds = [
          op?.accountingAccountId,
          op?.accountId,
          op?.account_code,
          normalizeAccountCode(op?.accountingAccountId),
          normalizeAccountCode(op?.accountId),
          normalizeAccountCode(op?.account_code),
        ].map((v) => normalizeText(v)).filter(Boolean);
        return possibleIds.some((id) => accountIds.has(id));
      });

      const periodOps = matchedOps.filter((op) => {
        const rawDate = op?.date || op?.createdAt || op?.created_at;
        const ts = rawDate ? new Date(rawDate).getTime() : NaN;
        return Number.isFinite(ts) && ts >= periodStart;
      });

      const sortedOps = [...matchedOps].sort((a, b) => {
        const aTs = new Date(a?.date || a?.createdAt || a?.created_at || 0).getTime();
        const bTs = new Date(b?.date || b?.createdAt || b?.created_at || 0).getTime();
        return bTs - aTs;
      });

      return {
        ...target,
        accountFound: true,
        accountName: account?.name_ar || account?.name || account?.code || target.title,
        balance: Number(account?.balance || 0),
        periodOpsCount: periodOps.length,
        periodAmount: periodOps.reduce((sum, op) => sum + Number(op?.total || op?.amount || 0), 0),
        lastMovementDate: sortedOps[0]?.date || sortedOps[0]?.createdAt || sortedOps[0]?.created_at || null,
      };
    });
  };

  const loadControlPanel = async () => {
    setLoadingAnalytics(true);
    try {
      const { data } = await api.get('/inventory/control-panel', { params: { days: daysFilter } });
      setAnalytics(data || null);
    } catch (error) {
      setAnalytics(null);
    } finally {
      setLoadingAnalytics(false);
    }
  };

  const loadBackorders = async () => {
    setLoadingBackorders(true);
    try {
      const params = backorderStatusFilter !== 'all' ? { status: backorderStatusFilter } : undefined;
      const { data } = await api.get('/inventory/backorders', { params });
      setBackorders(Array.isArray(data) ? data : []);
    } catch (error) {
      setBackorders([]);
    } finally {
      setLoadingBackorders(false);
    }
  };

  const loadParts = async () => {
    try {
      const response = await partAPI.getAll();
      setPartsList(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      setPartsList([]);
    }
  };

  const loadInventoryArchitecture = async () => {
    setLoadingInventoryArchitecture(true);
    try {
      const { data } = await api.get('/inventory/architecture', { params: { days: daysFilter } });
      setInventoryArchitecture(data || null);
    } catch (error) {
      setInventoryArchitecture(null);
    } finally {
      setLoadingInventoryArchitecture(false);
    }
  };

  const loadWorkshopAccountStats = async () => {
    setLoadingWorkshopAccountStats(true);

    const readCachedArray = (key) => {
      try {
        const raw = localStorage.getItem(key);
        const parsed = raw ? JSON.parse(raw) : [];
        return Array.isArray(parsed) ? parsed : [];
      } catch (e) {
        return [];
      }
    };

    const cachedOperations = readCachedArray('operationsCache:all');
    const cachedAccounts = readCachedArray('chartAccountsCache:all');

    if (cachedAccounts.length) {
      setWorkshopAccountStats(buildWorkshopAccountCards(cachedAccounts, cachedOperations));
      setLoadingWorkshopAccountStats(false);
    }

    try {
      const [accountsRes, operationsRes] = await Promise.all([
        financeAPI.getChartOfAccounts(),
        cachedOperations.length ? Promise.resolve({ data: cachedOperations }) : operationsAPI.list({ limit: 120 }),
      ]);

      const accountsPayload = accountsRes?.data;
      const accounts = Array.isArray(accountsPayload?.data)
        ? accountsPayload.data
        : Array.isArray(accountsPayload)
          ? accountsPayload
          : [];

      const operationsPayload = operationsRes?.data;
      const operations = Array.isArray(operationsPayload) ? operationsPayload : [];
      if (accounts.length) {
        localStorage.setItem('chartAccountsCache:all', JSON.stringify(accounts));
      }

      setWorkshopAccountStats(buildWorkshopAccountCards(accounts, operations));
    } catch (error) {
      if (!cachedAccounts.length) {
        setWorkshopAccountStats(
          WORKSHOP_ACCOUNT_TARGETS.map((target) => ({
            ...target,
            accountFound: false,
            accountName: 'تعذر تحميل الحساب',
            balance: 0,
            periodOpsCount: 0,
            periodAmount: 0,
            lastMovementDate: null,
          }))
        );
      }
    } finally {
      setLoadingWorkshopAccountStats(false);
    }
  };

  const handleResetInventoryTotals = async () => {
    const confirmed = window.confirm('سيتم إعادة ضبط إجمالي المبيعات والمصروفات في لوحة القطع وأرشفة العمليات السابقة. هل تريد المتابعة؟');
    if (!confirmed) return;

    setResettingTotals(true);
    try {
      await api.post('/inventory/reset-totals');
      await Promise.all([
        loadControlPanel(),
        loadWorkshopAccountStats(),
      ]);
    } finally {
      setResettingTotals(false);
    }
  };

  useEffect(() => {
    loadControlPanel();
    loadInventoryArchitecture();
    loadWorkshopAccountStats();
  }, [daysFilter]);

  useEffect(() => {
    loadBackorders();
  }, [backorderStatusFilter]);

  useEffect(() => {
    loadParts();
  }, []);

  const handleCreateBackorder = async (event) => {
    event.preventDefault();
    if (!formData.customer_name.trim()) return;

    const selectedPart = partsList.find((part) => part.id === formData.part_id);
    const resolvedPartName = formData.part_name || selectedPart?.name || '';
    if (!resolvedPartName) return;

    try {
      setSavingBackorder(true);
      await api.post('/inventory/backorders', {
        part_id: formData.part_id || null,
        part_name: resolvedPartName,
        requested_quantity: Number(formData.requested_quantity || 1),
        customer_name: formData.customer_name,
        customer_phone: formData.customer_phone || null,
        vehicle_reference: formData.vehicle_reference || null,
        expected_date: formData.expected_date || null,
        note: formData.note || null,
      });
      setFormData({
        part_id: '',
        part_name: '',
        requested_quantity: 1,
        customer_name: '',
        customer_phone: '',
        vehicle_reference: '',
        expected_date: '',
        note: '',
      });
      await Promise.all([loadBackorders(), loadControlPanel()]);
    } finally {
      setSavingBackorder(false);
    }
  };

  const updateBackorderStatus = async (backorderId, status) => {
    await api.patch(`/inventory/backorders/${backorderId}/status`, { status });
    await Promise.all([loadBackorders(), loadControlPanel()]);
  };

  const overview = analytics?.overview || {};
  const cards = useMemo(
    () => [
      { key: 'inventory-cost', label: 'قيمة المخزون (تكلفة)', value: formatCurrency(overview.inventory_cost_value), icon: ShoppingCart, color: '#22c55e' },
      { key: 'inventory-retail', label: 'قيمة المخزون (بيع)', value: formatCurrency(overview.inventory_retail_value), icon: BarChart3, color: '#38bdf8' },
      { key: 'period-ops', label: 'عمليات الفترة', value: Number((analytics?.recent_part_operations || []).length).toLocaleString('ar-SA'), icon: TrendingUp, color: '#8b5cf6' },
      { key: 'low', label: 'منخفض المخزون', value: overview.low_stock_count || 0, icon: AlertTriangle, color: '#f97316' },
      { key: 'out', label: 'نافد المخزون', value: overview.out_of_stock_count || 0, icon: Boxes, color: '#ef4444' },
      { key: 'parts', label: 'إجمالي الأصناف', value: overview.total_parts || 0, icon: ClipboardList, color: '#a78bfa' },
    ],
    [overview, analytics]
  );

  return (
    <div className="p-6 space-y-6" data-testid="parts-control-panel-page">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white" data-testid="parts-control-panel-title">لوحة تحكم القطع</h1>
          <p className="text-slate-400" data-testid="parts-control-panel-subtitle">
            تحليلات ذكية للمبيعات والمخزون وإدارة الطلبات من شاشة واحدة
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="filter-select"
            value={daysFilter}
            onChange={(e) => setDaysFilter(Number(e.target.value))}
            data-testid="parts-control-days-filter"
          >
            <option value={30}>آخر 30 يوم</option>
            <option value={60}>آخر 60 يوم</option>
            <option value={90}>آخر 90 يوم</option>
            <option value={180}>آخر 180 يوم</option>
          </select>
          <Button
            type="button"
            variant="outline"
            className="bg-white/10 text-white border-white/20"
            onClick={() => Promise.all([loadControlPanel(), loadBackorders(), loadInventoryArchitecture(), loadWorkshopAccountStats()])}
            data-testid="parts-control-refresh-button"
          >
            <RefreshCw size={16} className="ml-1" /> تحديث
          </Button>
          <Button
            type="button"
            variant="outline"
            className="bg-rose-500/15 text-rose-100 border-rose-300/30"
            onClick={handleResetInventoryTotals}
            disabled={resettingTotals}
            data-testid="parts-control-reset-totals-button"
          >
            {resettingTotals ? <Loader2 size={16} className="ml-1 animate-spin" /> : null}
            إعادة ضبط الإجماليات
          </Button>
        </div>
      </div>

      {(overview?.totals_reset_at) && (
        <div className="glass-card p-3 text-xs text-amber-200" data-testid="parts-control-reset-totals-note">
          أرشيف العمليات السابقة مفعل من تاريخ: {new Date(overview?.totals_reset_at).toLocaleString('ar-SA')}
        </div>
      )}

      {loadingWorkshopAccountStats ? (
        <div className="glass-card p-5 text-slate-300 flex items-center gap-2" data-testid="parts-control-workshop-account-loading">
          <Loader2 className="animate-spin" size={16} /> جاري تحميل إحصائيات حسابات الورشة...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="parts-control-workshop-account-cards">
          {workshopAccountStats.map((card) => (
            <div key={card.key} className="glass-card p-5 border-t-4" style={{ borderColor: card.color }} data-testid={`parts-control-workshop-account-card-${card.key}`}>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-sm text-slate-300" data-testid={`parts-control-workshop-account-title-${card.key}`}>{card.title}</p>
                  <p className="text-xs text-slate-400" data-testid={`parts-control-workshop-account-name-${card.key}`}>{card.accountName}</p>
                </div>
                <card.icon size={18} style={{ color: card.color }} />
              </div>
              <p className="text-2xl font-bold text-white" data-testid={`parts-control-workshop-account-balance-${card.key}`}>
                {formatCurrency(card.balance)}
              </p>
              <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-white/5 p-2" data-testid={`parts-control-workshop-account-period-ops-${card.key}`}>
                  <p className="text-slate-400">عمليات الفترة</p>
                  <p className="text-white font-semibold">{Number(card.periodOpsCount || 0).toLocaleString('ar-SA')}</p>
                </div>
                <div className="rounded-lg bg-white/5 p-2" data-testid={`parts-control-workshop-account-period-amount-${card.key}`}>
                  <p className="text-slate-400">إجمالي الفترة</p>
                  <p className="text-white font-semibold">{formatCurrency(card.periodAmount)}</p>
                </div>
              </div>
              <p className="mt-3 text-[11px] text-slate-400" data-testid={`parts-control-workshop-account-last-movement-${card.key}`}>
                آخر حركة: {card.lastMovementDate ? new Date(card.lastMovementDate).toLocaleDateString('ar-SA') : 'لا توجد'}
              </p>
              {!card.accountFound && (
                <p className="mt-2 text-[11px] text-amber-300" data-testid={`parts-control-workshop-account-missing-${card.key}`}>
                  لم يتم العثور على الحساب في دليل الحسابات.
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2" data-testid="parts-control-tabs">
        <button
          type="button"
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2.5 rounded-xl text-sm border ${activeTab === 'overview' ? 'bg-cyan-500/20 border-cyan-400/40 text-cyan-100' : 'bg-white/5 border-white/10 text-slate-300'}`}
          data-testid="parts-control-tab-overview"
        >
          النظرة العامة
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('planner')}
          className={`px-4 py-2.5 rounded-xl text-sm border ${activeTab === 'planner' ? 'bg-sky-500/20 border-sky-400/40 text-sky-100' : 'bg-white/5 border-white/10 text-slate-300'}`}
          data-testid="parts-control-tab-planner"
        >
          معمارية المخزون
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('backorders')}
          className={`px-4 py-2.5 rounded-xl text-sm border ${activeTab === 'backorders' ? 'bg-amber-500/20 border-amber-400/40 text-amber-100' : 'bg-white/5 border-white/10 text-slate-300'}`}
          data-testid="parts-control-tab-backorders"
        >
          Backorders
        </button>
      </div>

      {activeTab === 'overview' && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="parts-control-overview-cards">
            {cards.map((card) => (
              <div key={card.key} className="glass-card p-5 border-t-4" style={{ borderColor: card.color }} data-testid={`parts-control-card-${card.key}`}>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm text-slate-300">{card.label}</p>
                  <card.icon size={18} style={{ color: card.color }} />
                </div>
                <p className="text-2xl font-bold text-white" data-testid={`parts-control-card-value-${card.key}`}>{card.value}</p>
              </div>
            ))}
          </div>

          {loadingAnalytics && (
            <div className="glass-card p-5 text-slate-300 flex items-center gap-2" data-testid="parts-control-loading">
              <Loader2 className="animate-spin" size={16} /> جاري تحميل التحليلات...
            </div>
          )}

          {!loadingAnalytics && analytics && (
            <>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4" data-testid="parts-control-kpis-section">
                <div className="glass-card p-4" data-testid="parts-control-top-selling-card">
                  <h2 className="text-white font-semibold mb-3">الأكثر مبيعًا</h2>
                  <div className="space-y-2">
                    {(analytics.top_selling_parts || []).slice(0, 8).map((part) => (
                      <div key={part.part_id} className="flex items-center justify-between text-sm" data-testid={`parts-control-top-selling-${part.part_id}`}>
                        <span className="text-slate-200">{part.part_name}</span>
                        <span className="text-cyan-300">{part.sold_quantity} قطعة</span>
                      </div>
                    ))}
                    {!(analytics.top_selling_parts || []).length && (
                      <p className="text-slate-400 text-sm" data-testid="parts-control-top-selling-empty">لا توجد بيانات مبيعات كافية</p>
                    )}
                  </div>
                </div>

                <div className="glass-card p-4" data-testid="parts-control-margin-watchlist-card">
                  <h2 className="text-white font-semibold mb-3">تحذير الهوامش</h2>
                  <div className="space-y-2">
                    {(analytics.margin_watchlist || []).slice(0, 8).map((part) => (
                      <div key={part.part_id} className="flex items-center justify-between text-sm" data-testid={`parts-control-margin-item-${part.part_id}`}>
                        <span className="text-slate-200">{part.part_name}</span>
                        <span className="text-amber-300">{part.margin_ratio}%</span>
                      </div>
                    ))}
                    {!(analytics.margin_watchlist || []).length && (
                      <p className="text-slate-400 text-sm" data-testid="parts-control-margin-empty">لا توجد قطع بهوامش خطرة</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="glass-card p-4 overflow-auto" data-testid="parts-control-category-performance-card">
                <h2 className="text-white font-semibold mb-3">أداء الفئات</h2>
                <table className="w-full text-sm text-right">
                  <thead className="text-slate-400 border-b border-white/10">
                    <tr>
                      <th className="py-2">الفئة</th>
                      <th className="py-2">عدد الأصناف</th>
                      <th className="py-2">المباع</th>
                      <th className="py-2">الإيراد</th>
                      <th className="py-2">منخفض المخزون</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(analytics.category_performance || []).map((row) => (
                      <tr key={row.category} className="border-b border-white/5 text-slate-200" data-testid={`parts-control-category-row-${row.category}`}>
                        <td className="py-2">{row.category}</td>
                        <td className="py-2">{row.stock_items}</td>
                        <td className="py-2">{row.sold_quantity}</td>
                        <td className="py-2">{formatCurrency(row.revenue)}</td>
                        <td className="py-2">{row.low_stock_items}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}


      {activeTab === 'planner' && (
        <InventoryPlannerTab
          architecture={inventoryArchitecture}
          loading={loadingInventoryArchitecture}
        />
      )}

      {activeTab === 'backorders' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4" data-testid="parts-control-backorders-section">
        <form className="glass-card p-4 space-y-3" onSubmit={handleCreateBackorder} data-testid="parts-control-backorder-form">
          <h2 className="text-white font-semibold">إنشاء طلب Backorder</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">القطعة</label>
              <select
                className="apple-input"
                value={formData.part_id}
                onChange={(e) => {
                  const selected = partsList.find((part) => part.id === e.target.value);
                  setFormData((prev) => ({
                    ...prev,
                    part_id: e.target.value,
                    part_name: selected?.name || prev.part_name,
                  }));
                }}
                data-testid="parts-control-backorder-part-select"
              >
                <option value="">اختيار من المخزون (اختياري)</option>
                {partsList.map((part) => (
                  <option key={part.id} value={part.id}>{part.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">اسم القطعة</label>
              <input
                className="apple-input"
                value={formData.part_name}
                onChange={(e) => setFormData((prev) => ({ ...prev, part_name: e.target.value }))}
                data-testid="parts-control-backorder-part-name-input"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">الكمية المطلوبة</label>
              <input
                type="number"
                min={1}
                className="apple-input"
                value={formData.requested_quantity}
                onChange={(e) => setFormData((prev) => ({ ...prev, requested_quantity: Number(e.target.value) }))}
                data-testid="parts-control-backorder-quantity-input"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">اسم العميل</label>
              <input
                className="apple-input"
                value={formData.customer_name}
                onChange={(e) => setFormData((prev) => ({ ...prev, customer_name: e.target.value }))}
                data-testid="parts-control-backorder-customer-name-input"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">رقم العميل</label>
              <input
                className="apple-input"
                value={formData.customer_phone}
                onChange={(e) => setFormData((prev) => ({ ...prev, customer_phone: e.target.value }))}
                data-testid="parts-control-backorder-customer-phone-input"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">تاريخ متوقع للوصول</label>
              <input
                type="date"
                className="apple-input"
                value={formData.expected_date}
                onChange={(e) => setFormData((prev) => ({ ...prev, expected_date: e.target.value }))}
                data-testid="parts-control-backorder-expected-date-input"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">ملاحظات</label>
            <textarea
              className="apple-input min-h-[72px]"
              value={formData.note}
              onChange={(e) => setFormData((prev) => ({ ...prev, note: e.target.value }))}
              data-testid="parts-control-backorder-note-input"
            />
          </div>
          <Button
            type="submit"
            disabled={savingBackorder}
            className="apple-button"
            data-testid="parts-control-backorder-submit-button"
          >
            {savingBackorder ? 'جاري الحفظ...' : 'حفظ الطلب'}
          </Button>
        </form>

        <div className="glass-card p-4" data-testid="parts-control-backorders-list-card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-white font-semibold">قائمة طلبات Backorder</h2>
            <select
              className="filter-select"
              value={backorderStatusFilter}
              onChange={(e) => setBackorderStatusFilter(e.target.value)}
              data-testid="parts-control-backorder-status-filter"
            >
              {backorderStatusOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          {loadingBackorders ? (
            <p className="text-slate-400 text-sm" data-testid="parts-control-backorders-loading">جاري تحميل الطلبات...</p>
          ) : (
            <div className="space-y-2 max-h-[420px] overflow-auto" data-testid="parts-control-backorders-list">
              {backorders.map((order) => (
                <div key={order.id} className="rounded-xl bg-white/5 p-3" data-testid={`parts-control-backorder-item-${order.id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="text-white text-sm font-medium" data-testid={`parts-control-backorder-part-${order.id}`}>{order.part_name}</p>
                      <p className="text-xs text-slate-400" data-testid={`parts-control-backorder-meta-${order.id}`}>
                        {order.customer_name} • كمية {order.requested_quantity}
                      </p>
                    </div>
                    <select
                      className="apple-input h-9 text-sm"
                      value={order.status}
                      onChange={(e) => updateBackorderStatus(order.id, e.target.value)}
                      data-testid={`parts-control-backorder-status-select-${order.id}`}
                    >
                      <option value="pending">قيد الانتظار</option>
                      <option value="ordered">تم الطلب</option>
                      <option value="arrived">وصلت</option>
                      <option value="cancelled">ملغية</option>
                    </select>
                  </div>
                </div>
              ))}
              {!backorders.length && (
                <p className="text-slate-400 text-sm" data-testid="parts-control-backorders-empty">لا توجد طلبات مطابقة</p>
              )}
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  );
};

export default PartsDashboard;