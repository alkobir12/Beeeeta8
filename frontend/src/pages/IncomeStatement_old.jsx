
import React, { useEffect, useState } from 'react';
import {
  TrendingUp,
  Download,
  RefreshCw,
  Calendar,
  DollarSign,
  ArrowDown,
  ArrowUp,
  Percent,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { financeAPI } from '../services/api';
import { formatCurrency, formatDate } from '../utils/formatters';

const IncomeStatement = () => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
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
    // eslint disabled
  }, [startDate, endDate, workshopId]);

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

  const profitMargin = totals.revenue > 0 ? ((totals.net_income / totals.revenue) * 100).toFixed(1) : '0.0';
  const grossMargin = '—'; // يمكن حسابه لاحقًا عندما نضيف تكلفة المبيعات منفصلة

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
        <p className="text-lg text-gray-600">جاري تحميل قائمة الدخل...</p>
        <p className="text-sm text-gray-500">قد يستغرق هذا بضع لحظات</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6" dir="rtl" data-testid="income-statement-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <TrendingUp className="text-green-600" />
            قائمة الدخل
          </h1>
          <p className="text-gray-600 mt-1">
            بيان الأرباح والخسائر عن الفترة من {formatDate(startDate)} إلى {formatDate(endDate)}
          </p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex items-center gap-2 bg-white rounded-lg px-3 py-2 border border-gray-200">
            <Calendar size={18} className="text-gray-500" />
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-transparent text-gray-800 border-0 outline-none text-sm"
            />
            <span className="text-gray-400">-</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-transparent text-gray-800 border-0 outline-none text-sm"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchData}
              className="p-2 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 transition-colors flex items-center gap-1 text-sm text-gray-700"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
              ) : (
                <RefreshCw size={18} className="text-gray-500" />
              )}
              <span>تحديث</span>
            </button>
            <button className="p-2 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 transition-colors">
              <Download size={18} className="text-gray-500" />
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl p-5 text-white shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <ArrowUp size={20} />
            <span className="text-sm opacity-80">إجمالي الإيرادات</span>
          </div>
          <p className="text-2xl font-bold">{formatCurrency(totals.revenue || 0)}</p>
        </div>

        <div className="bg-gradient-to-br from-red-500 to-red-600 rounded-xl p-5 text-white shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <ArrowDown size={20} />
            <span className="text-sm opacity-80">إجمالي المصروفات</span>
          </div>
          <p className="text-2xl font-bold">{formatCurrency(totals.expenses || 0)}</p>
        </div>

        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-5 text-white shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign size={20} />
            <span className="text-sm opacity-80">صافي الربح</span>
          </div>
          <p className="text-2xl font-bold">{formatCurrency(totals.net_income || 0)}</p>
        </div>

        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-5 text-white shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <Percent size={20} />
            <span className="text-sm opacity-80">هامش صافي الربح</span>
          </div>
          <p className="text-2xl font-bold">{profitMargin}%</p>
        </div>
      </div>

      {/* Income Statement Content */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm mb-6">
        {/* Revenue Section */}
        <div className="border-b border-gray-100">
          <div className="bg-green-50 px-4 py-3 flex items-center gap-2">
            <ArrowUp className="text-green-600" size={20} />
            <h3 className="font-bold text-green-700">الإيرادات</h3>
          </div>

          <div className="p-4 space-y-3">
            {revenueAccounts.length > 0 ? (
              <>
                <div className="grid grid-cols-12 text-xs font-medium text-gray-500 border-b border-gray-100 pb-2">
                  <div className="col-span-3">كود الحساب</div>
                  <div className="col-span-6">اسم الحساب</div>
                  <div className="col-span-3 text-left">المبلغ</div>
                </div>
                {revenueAccounts.map((acc) => (
                  <div
                    key={acc.code}
                    className="grid grid-cols-12 items-center text-sm py-1.5 px-1 rounded hover:bg-gray-50"
                  >
                    <div className="col-span-3 font-mono text-gray-500 text-xs">{acc.code}</div>
                    <div className="col-span-6 text-gray-800">{acc.name}</div>
                    <div className="col-span-3 text-left font-mono text-green-700">
                      {formatCurrency(acc.amount)}
                    </div>
                  </div>
                ))}
              </>
            ) : (
              <p className="text-sm text-gray-500 text-center py-4">لا توجد بيانات إيرادات متاحة.</p>
            )}

            <div className="flex justify-between items-center mt-3 pt-3 border-t border-gray-100">
              <span className="text-gray-500 text-sm">إجمالي الإيرادات</span>
              <span className="font-bold text-green-700">{formatCurrency(totals.revenue || 0)}</span>
            </div>
          </div>
        </div>

        {/* Expenses Section */}
        <div>
          <div className="bg-red-50 px-4 py-3 flex items-center gap-2">
            <ArrowDown className="text-red-600" size={20} />
            <h3 className="font-bold text-red-700">المصروفات</h3>
          </div>

          <div className="p-4 space-y-3">
            {expenseAccounts.length > 0 ? (
              <>
                <div className="grid grid-cols-12 text-xs font-medium text-gray-500 border-b border-gray-100 pb-2">
                  <div className="col-span-3">كود الحساب</div>
                  <div className="col-span-6">اسم الحساب</div>
                  <div className="col-span-3 text-left">المبلغ</div>
                </div>
                {expenseAccounts.map((acc) => (
                  <div
                    key={acc.code}
                    className="grid grid-cols-12 items-center text-sm py-1.5 px-1 rounded hover:bg-gray-50"
                  >
                    <div className="col-span-3 font-mono text-gray-500 text-xs">{acc.code}</div>
                    <div className="col-span-6 text-gray-800">{acc.name}</div>
                    <div className="col-span-3 text-left font-mono text-red-700">
                      {formatCurrency(acc.amount)}
                    </div>
                  </div>
                ))}
              </>
            ) : (
              <p className="text-sm text-gray-500 text-center py-4">لا توجد بيانات مصروفات متاحة.</p>
            )}

            <div className="flex justify-between items-center mt-3 pt-3 border-t border-gray-100">
              <span className="text-gray-500 text-sm">إجمالي المصروفات</span>
              <span className="font-bold text-red-700">{formatCurrency(totals.expenses || 0)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Summary & Margins */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h4 className="text-gray-600 text-sm mb-3">صافي الربح</h4>
          <div className="flex items-end gap-3">
            <span
              className={`text-3xl font-bold ${
                (totals.net_income || 0) >= 0 ? 'text-green-700' : 'text-red-700'
              }`}
            >
              {formatCurrency(totals.net_income || 0)}
            </span>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h4 className="text-gray-600 text-sm mb-3">هامش صافي الربح</h4>
          <div className="flex items-end gap-3">
            <span className="text-3xl font-bold text-blue-700">{profitMargin}%</span>
            <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full"
                style={{ width: `${Math.min(Number(profitMargin) || 0, 100)}%` }}
              />
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-2">النسبة من إجمالي الإيرادات.</p>
        </div>
      </div>
    </div>
  );
};

export default IncomeStatement;
