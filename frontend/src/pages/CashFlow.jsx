/* eslint-disable */

import React, { useEffect, useState } from 'react';
import { Banknote, Download, RefreshCw, Calendar, ArrowUpRight, ArrowDownRight, Wallet, TrendingUp, AlertCircle, Loader2 } from 'lucide-react';
import { financeAPI } from '../services/api';
import { formatCurrency, formatDate } from '../utils/formatters';
import FinancialCard from '../components/FinancialCard';
import { useTheme } from '../contexts/ThemeContext';

const CashFlow = () => {
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

  // 🔗 ترابط حي — أي قيد مالي جديد (من البوت أو الصفحات) يحدّث التدفقات فوراً
  useEffect(() => {
    const handler = () => { if (workshopId) fetchData(); };
    window.addEventListener('finance:updated', handler);
    return () => window.removeEventListener('finance:updated', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await financeAPI.getCashFlow({
        workshop_id: workshopId,
        start_date: startDate,
        end_date: endDate,
      });

      const data = response.data?.data;
      setReport(data || null);
    } catch (err) {
      console.error('Error fetching cash flow:', err);
      setError('تعذر جلب قائمة التدفقات النقدية. يرجى المحاولة مرة أخرى.');
    } finally {
      setLoading(false);
    }
  };

  const operating = report?.operating_activities || {};
  const investing = report?.investing_activities || {};
  const financing = report?.financing_activities || {};
  
  const netOperatingCash = operating.net_operating_cash || 0;
  const netInvestingCash = investing.net_investing_cash || 0;
  const netFinancingCash = financing.net_financing_cash || 0;
  const netChangeInCash = report?.net_change_in_cash || 0;
  const beginningCash = report?.beginning_cash || 0;
  const endingCash = report?.ending_cash || 0;

  if (loading && !report) {
    return (
      <div className="flex flex-col items-center justify-center h-96" dir="rtl">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
        <p className="text-lg" style={{ color: 'var(--text-secondary)' }}>جاري تحميل قائمة التدفقات النقدية...</p>
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
            <Banknote className="text-green-600" />
            قائمة التدفقات النقدية
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

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <FinancialCard
          title={formatCurrency(netOperatingCash)}
          subtitle="الأنشطة التشغيلية"
          icon={Wallet}
          trend={netOperatingCash >= 0 ? 'up' : 'down'}
          trendValue={netOperatingCash >= 0 ? 'تدفق نقدي داخل' : 'تدفق نقدي خارج'}
          variant={netOperatingCash >= 0 ? 'success' : 'danger'}
          details={[
            { label: 'النقد من العملاء', value: formatCurrency(operating.cash_from_customers || 0) },
            { label: 'النقد للموردين', value: formatCurrency(operating.cash_to_suppliers || 0), valueColor: 'text-red-400' },
            { label: 'النقد للرواتب', value: formatCurrency(operating.cash_for_salaries || 0), valueColor: 'text-red-400' }
          ]}
        />

        <FinancialCard
          title={formatCurrency(netInvestingCash)}
          subtitle="الأنشطة الاستثمارية"
          icon={TrendingUp}
          trend={netInvestingCash >= 0 ? 'up' : 'down'}
          variant="default"
          details={[
            { label: 'شراء معدات', value: formatCurrency(investing.equipment_purchases || 0), valueColor: 'text-red-400' },
            { label: 'بيع أصول', value: formatCurrency(investing.asset_sales || 0), valueColor: 'text-emerald-400' }
          ]}
        />

        <FinancialCard
          title={formatCurrency(netFinancingCash)}
          subtitle="الأنشطة التمويلية"
          icon={Banknote}
          trend={netFinancingCash >= 0 ? 'up' : 'down'}
          variant="warning"
          details={[
            { label: 'قروض جديدة', value: formatCurrency(financing.new_loans || 0), valueColor: 'text-emerald-400' },
            { label: 'سداد قروض', value: formatCurrency(financing.loan_payments || 0), valueColor: 'text-red-400' }
          ]}
        />

        <FinancialCard
          title={formatCurrency(endingCash)}
          subtitle="رصيد النقد النهائي"
          icon={Wallet}
          variant="success"
          details={[
            { label: 'رصيد البداية', value: formatCurrency(beginningCash) },
            { label: 'صافي التغير', value: formatCurrency(netChangeInCash), valueColor: netChangeInCash >= 0 ? 'text-emerald-400' : 'text-red-400' },
            { label: 'رصيد النهاية', value: formatCurrency(endingCash), valueColor: 'text-emerald-400' }
          ]}
        />
      </div>

      {/* Net Change Card */}
      <div className="mb-6">
        <FinancialCard
          title={formatCurrency(netChangeInCash)}
          subtitle="صافي التغير في النقد"
          icon={ArrowUpRight}
          trend={netChangeInCash >= 0 ? 'up' : 'down'}
          variant={netChangeInCash >= 0 ? 'success' : 'danger'}
          expandable={false}
          details={[
            { label: 'الأنشطة التشغيلية', value: formatCurrency(netOperatingCash), valueColor: netOperatingCash >= 0 ? 'text-emerald-400' : 'text-red-400' },
            { label: 'الأنشطة الاستثمارية', value: formatCurrency(netInvestingCash), valueColor: netInvestingCash >= 0 ? 'text-emerald-400' : 'text-red-400' },
            { label: 'الأنشطة التمويلية', value: formatCurrency(netFinancingCash), valueColor: netFinancingCash >= 0 ? 'text-emerald-400' : 'text-red-400' }
          ]}
        />
      </div>
    </div>
  );
};

export default CashFlow;
