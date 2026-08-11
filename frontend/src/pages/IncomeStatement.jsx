
import React, { useEffect, useState } from 'react';
import { TrendingUp, Download, RefreshCw, Calendar, DollarSign, TrendingDown, AlertCircle, Loader2 } from 'lucide-react';
import { financeAPI } from '../services/api';
import { formatCurrency, formatDate } from '../utils/formatters';
import FinancialCard from '../components/FinancialCard';
import { useTheme } from '../contexts/ThemeContext';

const IncomeStatement = () => {
  const { themeName } = useTheme();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 3); // 3 أشهر بدلاً من شهر واحد
    return d.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);

  const workshopId = process.env.REACT_APP_WORKSHOP_ID;

  useEffect(() => {
    if (!workshopId) {
      setError('لم يتم ضبط معرف الورشة REACT_APP_WORKSHOP_ID');
      setLoading(false);
      return;
    }
    fetchData();
  }, [startDate, endDate, workshopId]);

  // 🔗 ترابط حي — أي قيد مالي جديد (من البوت أو الصفحات) يحدّث القائمة فوراً
  useEffect(() => {
    const handler = () => { if (workshopId) fetchData(); };
    window.addEventListener('finance:updated', handler);
    return () => window.removeEventListener('finance:updated', handler);
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await financeAPI.getIncomeStatement({
        workshop_id: workshopId,
        start_date: startDate,
        end_date: endDate,
      });

      const data = response.data?.data;
      setReport(data || null);
    } catch (err) {
      console.error('Error fetching income statement:', err);
      setError('تعذر جلب قائمة الدخل. يرجى المحاولة مرة أخرى.');
    } finally {
      setLoading(false);
    }
  };

  const totals = report?.totals || { revenue: 0, expenses: 0, net_income: 0 };
  const details = report?.details || { revenue_by_account: {}, expenses_by_account: {} };
  const statementSafety = report?.statement_safety || {};
  const revenueSourceAudit = report?.revenue_source_audit || {};

  const profitMargin = totals.revenue > 0 ? ((totals.net_income / totals.revenue) * 100).toFixed(1) : '0.0';

  const formatAccountList = (records) =>
    Object.entries(records || {}).map(([code, data]) => ({ 
      code, 
      name: data.name || `حساب ${code}`, 
      amount: data.amount || 0 
    }));

  const revenueAccounts = formatAccountList(details.revenue_by_account);
  const expenseAccounts = formatAccountList(details.expenses_by_account);

  if (loading && !report) {
    return (
      <div className="flex flex-col items-center justify-center h-96" dir="rtl">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
        <p className="text-lg" style={{ color: 'var(--text-secondary)' }}>جاري تحميل قائمة الدخل...</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-7xl" dir="rtl" style={{
      backgroundColor: 'var(--bg-primary)',
      minHeight: '100vh'
    }}>
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <TrendingUp className="text-emerald-600" />
            قائمة الدخل
          </h1>
          <p className="mt-1" style={{ color: 'var(--text-secondary)' }}>
            من {formatDate(startDate)} إلى {formatDate(endDate)}
          </p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg px-3 py-2" style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-color)'
          }}>
            <Calendar size={18} style={{ color: 'var(--text-secondary)' }} />
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-transparent border-0 outline-none text-sm w-32"
              style={{ color: 'var(--text-primary)' }}
            />
            <span style={{ color: 'var(--text-secondary)' }}>-</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-transparent border-0 outline-none text-sm w-32"
              style={{ color: 'var(--text-primary)' }}
            />
          </div>
          <button
            onClick={fetchData}
            className="p-2 rounded-lg transition-colors flex items-center gap-1 text-sm"
            style={{
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)'
            }}
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin text-blue-600" /> : <RefreshCw size={18} />}
            <span>تحديث</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg px-3 py-2 text-sm"
          style={{
            backgroundColor: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.3)',
            color: '#ef4444'
          }}
        >
          <AlertCircle className="h-4 w-4 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {statementSafety?.warning && (
        <div
          className="mb-4 flex items-start gap-2 rounded-lg px-3 py-2 text-sm"
          style={{
            backgroundColor: 'rgba(245,158,11,0.12)',
            border: '1px solid rgba(245,158,11,0.35)',
            color: '#b45309'
          }}
          data-testid="income-statement-safety-banner"
        >
          <AlertCircle className="h-4 w-4 mt-0.5" />
          <div>
            <p className="font-bold" data-testid="income-statement-safety-title">{statementSafety.warning}</p>
            <p className="mt-1" data-testid="income-statement-safety-detail">
              الإيراد قبل الفلترة {formatCurrency(revenueSourceAudit.revenue_before || 0)}، المستبعد {formatCurrency(revenueSourceAudit.excluded_legacy_revenue || 0)}، والإيراد المعروض {formatCurrency(revenueSourceAudit.canonical_revenue || totals.revenue || 0)}.
            </p>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <FinancialCard
          title={formatCurrency(totals.revenue)}
          subtitle="إجمالي الإيرادات"
          icon={DollarSign}
          trend="up"
          trendValue="+15%"
          variant="success"
          details={
            revenueAccounts.slice(0, 4).map(acc => ({
              label: acc.name,
              value: formatCurrency(acc.amount)
            }))
          }
        />

        <FinancialCard
          title={formatCurrency(totals.expenses)}
          subtitle="إجمالي المصروفات"
          icon={TrendingDown}
          trend="down"
          trendValue="-8%"
          variant="warning"
          details={
            expenseAccounts.slice(0, 4).map(acc => ({
              label: acc.name,
              value: formatCurrency(acc.amount),
              valueColor: 'text-red-400'
            }))
          }
        />

        <FinancialCard
          title={formatCurrency(totals.net_income)}
          subtitle="صافي الدخل"
          icon={TrendingUp}
          trend={totals.net_income >= 0 ? 'up' : 'down'}
          trendValue={`${profitMargin}%`}
          variant={totals.net_income >= 0 ? 'success' : 'danger'}
          details={[
            { label: 'هامش الربح', value: `${profitMargin}%` },
            { label: 'الإيرادات', value: formatCurrency(totals.revenue) },
            { label: 'المصروفات', value: formatCurrency(totals.expenses), valueColor: 'text-red-400' }
          ]}
        />

        <FinancialCard
          title={`${profitMargin}%`}
          subtitle="هامش الربح الصافي"
          icon={DollarSign}
          variant={parseFloat(profitMargin) > 20 ? 'success' : parseFloat(profitMargin) > 10 ? 'warning' : 'danger'}
          expandable={false}
        />
      </div>

      {/* Detailed breakdown - only if data exists */}
      {(revenueAccounts.length > 0 || expenseAccounts.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Revenue breakdown */}
          {revenueAccounts.length > 0 && (
            <div>
              <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
                تفصيل الإيرادات
              </h2>
              <div className="space-y-3">
                {revenueAccounts.map((acc, idx) => (
                  <div
                    key={idx}
                    className="rounded-xl p-4"
                    style={{
                      backgroundColor: 'var(--bg-card)',
                      border: '1px solid var(--border-color)'
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{acc.code}</span>
                        <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>{acc.name}</h3>
                      </div>
                      <p className="text-lg font-bold text-emerald-400">{formatCurrency(acc.amount)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Expense breakdown */}
          {expenseAccounts.length > 0 && (
            <div>
              <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
                تفصيل المصروفات
              </h2>
              <div className="space-y-3">
                {expenseAccounts.map((acc, idx) => (
                  <div
                    key={idx}
                    className="rounded-xl p-4"
                    style={{
                      backgroundColor: 'var(--bg-card)',
                      border: '1px solid var(--border-color)'
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{acc.code}</span>
                        <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>{acc.name}</h3>
                      </div>
                      <p className="text-lg font-bold text-red-400">{formatCurrency(acc.amount)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default IncomeStatement;
