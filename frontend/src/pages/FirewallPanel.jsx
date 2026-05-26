import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { useToast } from '../hooks/use-toast';
import { resolveBackendBase } from '../utils/backendBase';
import {
  Shield, RefreshCw, AlertTriangle, Filter, TrendingUp, TrendingDown,
  Activity, Brain, ArrowUpRight, ArrowDownRight,
} from 'lucide-react';

import HealthScoreGauge from '../components/firewall/HealthScoreGauge';
import AlertCard from '../components/firewall/AlertCard';
import AIInsightsPanel from '../components/firewall/AIInsightsPanel';
import LiveActivityFeed from '../components/firewall/LiveActivityFeed';
import AlertDetailsDrawer from '../components/firewall/AlertDetailsDrawer';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);
const WORKSHOP_ID = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';

const formatSar = (v) => new Intl.NumberFormat('ar-SA', { minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(Number(v || 0)) + ' ر.س';

const CATEGORY_FILTERS = [
  { key: 'all', label: 'الكل' },
  { key: 'balance_integrity', label: 'توازن القيود' },
  { key: 'duplicate_detection', label: 'كشف التكرار' },
  { key: 'consistency', label: 'اتساق البيانات' },
  { key: 'anomaly', label: 'شذوذ' },
  { key: 'integrity', label: 'نزاهة' },
];

const SEVERITY_FILTERS = [
  { key: 'all', label: 'الكل', color: 'bg-slate-700' },
  { key: 'critical', label: 'حرج', color: 'bg-rose-600' },
  { key: 'high', label: 'عالي', color: 'bg-orange-600' },
  { key: 'medium', label: 'متوسط', color: 'bg-amber-600' },
  { key: 'low', label: 'منخفض', color: 'bg-sky-600' },
];

const FirewallPanel = () => {
  const [data, setData] = useState(null);
  const [insights, setInsights] = useState({ insights: [], ai_enabled: false });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterSeverity, setFilterSeverity] = useState('all');
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [busyAlertId, setBusyAlertId] = useState(null);
  const { toast } = useToast();

  // ---------- load data ----------
  const loadDashboard = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setRefreshing(true);
    try {
      const res = await axios.get(`${API_URL}/firewall/dashboard`, { params: { workshop_id: WORKSHOP_ID } });
      if (res.data?.success) setData(res.data.data);
    } catch (e) {
      console.error('Firewall dashboard load failed:', e);
      toast({ title: 'خطأ', description: 'تعذر تحميل لوحة الجدار', variant: 'destructive' });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [toast]);

  const loadInsights = useCallback(async () => {
    setInsightsLoading(true);
    try {
      const res = await axios.get(`${API_URL}/firewall/ai-insights`, {
        params: { workshop_id: WORKSHOP_ID, use_ai: true },
        timeout: 60000,
      });
      if (res.data?.success) setInsights(res.data.data);
    } catch (e) {
      console.warn('AI insights load failed:', e);
    } finally {
      setInsightsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
    loadInsights();
  }, [loadDashboard, loadInsights]);

  // Listen for live finance updates to refresh the dashboard
  useEffect(() => {
    const onFinUpdated = () => loadDashboard(true);
    window.addEventListener('finance:updated', onFinUpdated);
    return () => window.removeEventListener('finance:updated', onFinUpdated);
  }, [loadDashboard]);

  // ---------- alert actions ----------
  const handleDetails = (alert) => setSelectedAlert(alert);

  const handleAutoFix = async (alert) => {
    setBusyAlertId(alert.id);
    try {
      const res = await axios.post(`${API_URL}/firewall/auto-fix`, { alert_id: alert.id }, {
        params: { workshop_id: WORKSHOP_ID },
      });
      if (res.data?.success) {
        toast({ title: 'تم الإصلاح', description: `تم تنفيذ: ${res.data.action_taken}` });
        await loadDashboard(true);
        setSelectedAlert(null);
      } else {
        toast({ title: 'تعذر الإصلاح الآلي', description: res.data?.error || 'الإجراء يحتاج معالجة يدوية', variant: 'destructive' });
      }
    } catch (e) {
      toast({ title: 'فشل الإصلاح', description: e?.response?.data?.detail || e.message, variant: 'destructive' });
    } finally {
      setBusyAlertId(null);
    }
  };

  const handleDismiss = async (alert) => {
    setBusyAlertId(alert.id);
    try {
      await axios.post(`${API_URL}/firewall/alerts/${alert.id}/dismiss`, { expires_in_hours: 24 }, {
        params: { workshop_id: WORKSHOP_ID },
      });
      toast({ title: 'تم التجاهل', description: 'لن يظهر التنبيه لمدة 24 ساعة' });
      await loadDashboard(true);
    } catch (e) {
      toast({ title: 'خطأ', description: e.message, variant: 'destructive' });
    } finally {
      setBusyAlertId(null);
    }
  };

  const handleResolve = async (alert) => {
    setBusyAlertId(alert.id);
    try {
      await axios.post(`${API_URL}/firewall/alerts/${alert.id}/resolve`, { user: 'manager' }, {
        params: { workshop_id: WORKSHOP_ID },
      });
      toast({ title: 'تم التعليم', description: 'تم تعليم التنبيه كمحلول' });
      await loadDashboard(true);
      setSelectedAlert(null);
    } catch (e) {
      toast({ title: 'خطأ', description: e.message, variant: 'destructive' });
    } finally {
      setBusyAlertId(null);
    }
  };

  // ---------- filters ----------
  const filteredAlerts = useMemo(() => {
    let list = data?.alerts || [];
    if (filterCategory !== 'all') list = list.filter((a) => a.category === filterCategory);
    if (filterSeverity !== 'all') list = list.filter((a) => a.severity === filterSeverity);
    return list;
  }, [data, filterCategory, filterSeverity]);

  // ---------- render ----------
  if (loading && !data) {
    return (
      <div data-testid="firewall-loading" className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-300">
        <div className="text-center">
          <RefreshCw className="animate-spin mx-auto mb-3" size={32} />
          <p>جاري تحميل مركز الحماية المالية…</p>
        </div>
      </div>
    );
  }

  const health = data?.health || { score: 0, status: '—', color: 'amber', breakdown: {} };
  const cashFlow = data?.cash_flow || { inflow: 0, outflow: 0, net: 0, period_days: 30 };
  const stats = data?.stats || {};
  const counts = data?.counts_by_severity || {};

  return (
    <div data-testid="firewall-panel-page" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-4 sm:p-6" dir="rtl">
      {/* HEADER */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-700 shadow-xl">
            <Shield className="text-white" size={28} />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-black text-white">مركز الحماية المالية الذكي</h1>
            <p className="text-sm text-slate-400">Accounting Firewall Center — مراقبة وتحليل وتدقيق حي</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            data-testid="firewall-refresh-btn"
            onClick={() => { loadDashboard(); loadInsights(); }}
            disabled={refreshing}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold inline-flex items-center gap-2 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={refreshing ? 'animate-spin' : ''} size={16} />
            {refreshing ? 'جاري التحديث' : 'تحديث الآن'}
          </button>
        </div>
      </div>

      {/* TOP ROW: HEALTH + KEY STATS */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-6">
        {/* Health Score */}
        <div className="lg:col-span-4">
          <HealthScoreGauge score={health.score} status={health.status} color={health.color} breakdown={health.breakdown} />
        </div>

        {/* KPI cards */}
        <div className="lg:col-span-8 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KpiCard
            icon={AlertTriangle}
            label="تنبيهات حرجة"
            value={counts.critical || 0}
            tone="rose"
            sub={`من ${data?.alerts_count || 0} تنبيه`}
            testid="kpi-critical"
          />
          <KpiCard
            icon={AlertTriangle}
            label="عالي الخطورة"
            value={counts.high || 0}
            tone="orange"
            sub={`متوسط: ${counts.medium || 0}`}
            testid="kpi-high"
          />
          <KpiCard
            icon={ArrowDownRight}
            label="إيرادات (30 يوم)"
            value={formatSar(cashFlow.inflow)}
            tone="emerald"
            sub="تدفق داخل"
            testid="kpi-inflow"
          />
          <KpiCard
            icon={ArrowUpRight}
            label="مصروفات (30 يوم)"
            value={formatSar(cashFlow.outflow)}
            tone="rose"
            sub={`صافي: ${formatSar(cashFlow.net)}`}
            testid="kpi-outflow"
          />
          <KpiCard
            icon={TrendingUp}
            label="قيود مسجلة"
            value={stats.total_journals || 0}
            tone="sky"
            sub={`عمليات: ${stats.total_operations || 0}`}
            testid="kpi-journals"
          />
          <KpiCard
            icon={Activity}
            label="زيارات مرتبطة"
            value={stats.total_visits || 0}
            tone="violet"
            sub="ملفات مركبات"
            testid="kpi-visits"
          />
          <KpiCard
            icon={cashFlow.is_negative ? TrendingDown : TrendingUp}
            label="حالة التدفق"
            value={cashFlow.is_negative ? 'سلبي' : 'إيجابي'}
            tone={cashFlow.is_negative ? 'rose' : 'emerald'}
            sub={`${cashFlow.period_days} يوماً`}
            testid="kpi-cashflow"
          />
          <KpiCard
            icon={Brain}
            label="AI Insights"
            value={insights.count || 0}
            tone="indigo"
            sub={insights.ai_enabled ? 'AI نشط' : 'محرك قواعد'}
            testid="kpi-insights"
          />
        </div>
      </div>

      {/* AI INSIGHTS + LIVE ACTIVITY */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-6">
        <div className="lg:col-span-7">
          <AIInsightsPanel insights={insights.insights || []} aiEnabled={insights.ai_enabled} loading={insightsLoading} />
        </div>
        <div className="lg:col-span-5">
          <LiveActivityFeed activity={data?.live_activity || []} loading={loading} />
        </div>
      </div>

      {/* ALERTS SECTION */}
      <div className="bg-slate-900/80 rounded-2xl border-2 border-slate-700 shadow-xl p-5">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h3 className="text-base font-extrabold text-white flex items-center gap-2">
            <AlertTriangle className="text-amber-400" size={18} />
            التنبيهات الذكية ({filteredAlerts.length})
          </h3>

          {/* filters */}
          <div className="flex flex-wrap items-center gap-1.5">
            <Filter className="text-slate-400" size={14} />
            {SEVERITY_FILTERS.map((s) => (
              <button
                key={s.key}
                data-testid={`firewall-filter-severity-${s.key}`}
                onClick={() => setFilterSeverity(s.key)}
                className={`text-[10px] px-2.5 py-1 rounded-full font-bold transition-colors ${
                  filterSeverity === s.key ? `${s.color} text-white` : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5 mb-4">
          {CATEGORY_FILTERS.map((c) => (
            <button
              key={c.key}
              data-testid={`firewall-filter-category-${c.key}`}
              onClick={() => setFilterCategory(c.key)}
              className={`text-[11px] px-3 py-1 rounded-full font-bold border transition-colors ${
                filterCategory === c.key
                  ? 'bg-indigo-600 text-white border-indigo-500'
                  : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        {filteredAlerts.length === 0 ? (
          <div className="text-center py-10 text-slate-400">
            <Shield className="mx-auto mb-2 text-emerald-500" size={40} />
            <p className="text-sm">لا توجد تنبيهات في هذا التصنيف. النظام في حالة سليمة.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="firewall-alerts-grid">
            {filteredAlerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onDetails={handleDetails}
                onAutoFix={handleAutoFix}
                onDismiss={handleDismiss}
                onResolve={handleResolve}
                busy={busyAlertId === alert.id}
              />
            ))}
          </div>
        )}
      </div>

      {/* drawer */}
      <AlertDetailsDrawer
        alert={selectedAlert}
        onClose={() => setSelectedAlert(null)}
        onAutoFix={handleAutoFix}
        onResolve={handleResolve}
        busy={busyAlertId === selectedAlert?.id}
      />
    </div>
  );
};

// ---------- KPI Card ----------
const TONE = {
  rose: 'from-rose-600/20 to-rose-700/10 border-rose-500/40 text-rose-300',
  orange: 'from-orange-600/20 to-orange-700/10 border-orange-500/40 text-orange-300',
  amber: 'from-amber-600/20 to-amber-700/10 border-amber-500/40 text-amber-300',
  emerald: 'from-emerald-600/20 to-emerald-700/10 border-emerald-500/40 text-emerald-300',
  sky: 'from-sky-600/20 to-sky-700/10 border-sky-500/40 text-sky-300',
  violet: 'from-violet-600/20 to-violet-700/10 border-violet-500/40 text-violet-300',
  indigo: 'from-indigo-600/20 to-indigo-700/10 border-indigo-500/40 text-indigo-300',
};

const KpiCard = ({ icon: Icon, label, value, sub, tone = 'sky', testid }) => {
  const t = TONE[tone] || TONE.sky;
  return (
    <div data-testid={testid} className={`bg-gradient-to-br ${t} border-2 rounded-xl p-3 shadow-md flex flex-col justify-between min-h-[88px]`}>
      <div className="flex items-center justify-between">
        <Icon size={16} />
        <span className="text-[10px] font-bold opacity-80">{sub}</span>
      </div>
      <div>
        <p className="text-[10px] text-slate-300 mb-0.5">{label}</p>
        <p className="text-lg font-black text-white truncate">{value}</p>
      </div>
    </div>
  );
};

export default FirewallPanel;
