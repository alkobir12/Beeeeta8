
import React, { useEffect, useState } from 'react';
import { Scale, Download, RefreshCw, Calendar, Wallet, Building2, PiggyBank, AlertCircle, Loader2, TrendingUp, TrendingDown } from 'lucide-react';
import { financeAPI } from '../services/api';
import { formatCurrency, formatDate } from '../utils/formatters';
import FinancialCard from '../components/FinancialCard';
import { useTheme } from '../contexts/ThemeContext';

const BalanceSheet = () => {
  const { themeName } = useTheme();
  const isLight = themeName === 'light' || themeName === 'dashPro';
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().split('T')[0]);

  const workshopId = process.env.REACT_APP_WORKSHOP_ID;

  useEffect(() => {
    if (!workshopId) {
      setError('لم يتم ضبط معرف الورشة REACT_APP_WORKSHOP_ID');
      setLoading(false);
      return;
    }
    fetchData();
  }, [asOfDate, workshopId]);

  // 🔗 ترابط حي — أي قيد مالي جديد (من البوت أو الصفحات) يحدّث الميزانية فوراً
  useEffect(() => {
    const handler = () => { if (workshopId) fetchData(); };
    window.addEventListener('finance:updated', handler);
    return () => window.removeEventListener('finance:updated', handler);
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await financeAPI.getBalanceSheet({
        workshop_id: workshopId,
        as_of_date: asOfDate,
      });

      const data = response.data?.data;
      setReport(data || null);
    } catch (err) {
      console.error('Error fetching balance sheet:', err);
      setError('تعذر جلب الميزانية العمومية. يرجى المحاولة مرة أخرى.');
    } finally {
      setLoading(false);
    }
  };

  const totals = report?.totals || { assets: 0, liabilities: 0, equity: 0, liabilities_plus_equity: 0 };
  const sections = report?.sections || { assets: [], liabilities: [], equity: [] };

  const isBalanced =
    totals.assets !== undefined &&
    totals.liabilities_plus_equity !== undefined &&
    Math.abs(totals.assets - totals.liabilities_plus_equity) < 0.01;

  if (loading && !report) {
    return (
      <div className="flex flex-col items-center justify-center h-96" dir="rtl">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
        <p className="text-lg" style={{ color: 'var(--text-secondary)' }}>جاري تحميل الميزانية العمومية...</p>
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
            <Scale className="text-blue-600" />
            الميزانية العمومية
          </h1>
          <p className="mt-1" style={{ color: 'var(--text-secondary)' }}>
            قائمة المركز المالي حتى تاريخ {report?.as_of ? formatDate(report.as_of) : formatDate(asOfDate)}
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
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="bg-transparent border-0 outline-none text-sm"
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

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <FinancialCard
          title={formatCurrency(totals.assets)}
          subtitle="إجمالي الأصول"
          icon={Wallet}
          variant="default"
          details={
            sections.assets?.slice(0, 5).map(acc => ({
              label: acc.is_contra ? `${acc.name} (${acc.balance_nature || 'رصيد عكسي'})` : acc.name,
              value: formatCurrency(acc.balance),
              valueColor: Number(acc.balance) < 0 ? 'text-amber-400' : undefined
            })) || []
          }
        />

        <FinancialCard
          title={formatCurrency(totals.liabilities)}
          subtitle="إجمالي الالتزامات"
          icon={TrendingDown}
          variant="warning"
          details={
            sections.liabilities?.slice(0, 5).map(acc => ({
              label: acc.name,
              value: formatCurrency(acc.balance),
              valueColor: 'text-red-400'
            })) || []
          }
        />

        <FinancialCard
          title={formatCurrency(totals.equity)}
          subtitle="حقوق الملكية"
          icon={PiggyBank}
          variant="success"
          details={
            sections.equity?.slice(0, 5).map(acc => ({
              label: acc.name,
              value: formatCurrency(acc.balance),
              valueColor: 'text-emerald-400'
            })) || []
          }
        />
      </div>

      {/* Balance Check Card */}
      <div className="mb-6">
        <FinancialCard
          title={isBalanced ? 'الميزانية متوازنة ✓' : 'الميزانية غير متوازنة'}
          subtitle="معادلة الميزانية"
          icon={Scale}
          variant={isBalanced ? 'success' : 'danger'}
          expandable={false}
          details={[
            { label: 'الأصول', value: formatCurrency(totals.assets) },
            { label: 'الالتزامات + حقوق الملكية', value: formatCurrency(totals.liabilities_plus_equity) },
            { label: 'الفرق', value: formatCurrency(Math.abs(totals.assets - totals.liabilities_plus_equity)), valueColor: isBalanced ? 'text-emerald-400' : 'text-red-400' }
          ]}
        />
      </div>

      {/* Detailed Sections - Show only if there's data */}
      {sections.assets && sections.assets.length > 0 && (
        <div className="mb-6">
          <h2 className="text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
            تفاصيل الأصول
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sections.assets.map((acc, idx) => (
              <div
                key={idx}
                className="rounded-xl p-4"
                style={{
                  backgroundColor: 'var(--bg-card)',
                  border: '1px solid var(--border-color)'
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{acc.code}</span>
                  <Wallet size={16} className="text-blue-400" />
                </div>
                <h3 className="font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>{acc.name}</h3>
                <div className="flex items-center gap-2 flex-wrap">
                  <p className={`text-lg font-bold ${Number(acc.balance) < 0 ? 'text-amber-400' : 'text-blue-400'}`}>{formatCurrency(acc.balance)}</p>
                  {acc.is_contra ? (
                    <span className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                      style={{ backgroundColor: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.4)', color: '#f59e0b' }}
                      data-testid={`balance-sheet-contra-tag-${idx}`}
                    >
                      {acc.balance_nature || 'رصيد عكسي'}
                    </span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default BalanceSheet;
