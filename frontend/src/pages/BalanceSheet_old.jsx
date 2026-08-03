
import React, { useEffect, useState } from 'react';
import { Scale, Download, RefreshCw, Calendar, Wallet, Building2, PiggyBank, AlertCircle, Loader2 } from 'lucide-react';
import { financeAPI } from '../services/api';
import { formatCurrency, formatDate } from '../utils/formatters';

const BalanceSheet = () => {
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
    // eslint disabled
  }, [asOfDate, workshopId]);

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

  const renderAccountsSection = (title, accounts, total, Icon, headerBg, accentText) => {
    return (
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div className={`${headerBg} px-4 py-3 flex items-center gap-2`}>
          <Icon className={accentText} size={20} />
          <h3 className={`font-bold ${accentText}`}>{title}</h3>
        </div>
        <div className="p-4 space-y-2">
          {accounts && accounts.length > 0 ? (
            <>
              <div className="grid grid-cols-12 text-xs font-medium text-gray-500 border-b border-gray-100 pb-2">
                <div className="col-span-3">كود الحساب</div>
                <div className="col-span-5">اسم الحساب</div>
                <div className="col-span-4 text-left">الرصيد</div>
              </div>
              {accounts.map((acc, idx) => (
                <div
                  key={acc.id || idx}
                  className="grid grid-cols-12 items-center text-sm py-1.5 px-1 rounded hover:bg-gray-50"
                >
                  <div className="col-span-3 font-mono text-gray-500 text-xs">{acc.code}</div>
                  <div className="col-span-5 text-gray-800">{acc.name}</div>
                  <div className="col-span-4 text-left font-mono text-gray-900">
                    {formatCurrency(acc.balance)}
                  </div>
                </div>
              ))}
            </>
          ) : (
            <p className="text-sm text-gray-500 text-center py-4">لا توجد حسابات متاحة لهذا القسم.</p>
          )}

          <div className="flex justify-between items-center mt-3 pt-3 border-t border-gray-100">
            <span className="text-gray-500 text-sm">إجمالي {title}</span>
            <span className={`font-bold ${accentText}`}>{formatCurrency(total || 0)}</span>
          </div>
        </div>
      </div>
    );
  };

  if (loading && !report) {
    return (
      <div className="flex flex-col items-center justify-center h-96" dir="rtl">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
        <p className="text-lg text-gray-600">جاري تحميل الميزانية العمومية...</p>
        <p className="text-sm text-gray-500">قد يستغرق هذا بضع لحظات</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6" dir="rtl" data-testid="balance-sheet-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <Scale className="text-blue-600" />
            الميزانية العمومية
          </h1>
          <p className="text-gray-600 mt-1">
            قائمة المركز المالي حتى تاريخ {report?.as_of ? formatDate(report.as_of) : formatDate(asOfDate)}
          </p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex items-center gap-2 bg-white rounded-lg px-3 py-2 border border-gray-200">
            <Calendar size={18} className="text-gray-500" />
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
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

      {/* Balance Check */}
      <div
        className={`rounded-xl p-4 mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4 border ${
          isBalanced ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
        }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`p-2 rounded-full ${
              isBalanced ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'
            }`}
          >
            <Scale size={24} />
          </div>
          <div>
            <p className={`font-bold ${isBalanced ? 'text-green-700' : 'text-red-700'}`}>
              {isBalanced ? 'الميزانية متوازنة ✓' : 'الميزانية غير متوازنة'}
            </p>
            <p className={`${isBalanced ? 'text-green-600/80' : 'text-red-600/80'} text-sm`}>
              الأصول = الالتزامات + حقوق الملكية
            </p>
          </div>
        </div>
        <div className="text-left">
          <p className="text-sm text-gray-500">الفرق</p>
          <p className={`font-bold text-lg ${isBalanced ? 'text-green-700' : 'text-red-700'}`}>
            {formatCurrency(Math.abs((totals.assets || 0) - (totals.liabilities_plus_equity || 0)))}
          </p>
        </div>
      </div>

      {/* Summary Cards - بطاقات ملخص محسّنة */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-2xl p-6 border-2 border-blue-200 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-3 bg-blue-200 rounded-xl">
              <Wallet className="text-blue-700" size={24} />
            </div>
            <span className="text-base font-bold text-blue-900">إجمالي الأصول</span>
          </div>
          <div className="text-3xl font-black text-blue-950">{formatCurrency(totals.assets)}</div>
        </div>

        <div className="bg-gradient-to-br from-red-50 to-red-100 rounded-2xl p-6 border-2 border-red-200 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-3 bg-red-200 rounded-xl">
              <Building2 className="text-red-700" size={24} />
            </div>
            <span className="text-base font-bold text-red-900">إجمالي الالتزامات</span>
          </div>
          <div className="text-3xl font-black text-red-950">{formatCurrency(totals.liabilities)}</div>
        </div>

        <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-2xl p-6 border-2 border-purple-200 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-3 bg-purple-200 rounded-xl">
              <PiggyBank className="text-purple-700" size={24} />
            </div>
            <span className="text-base font-bold text-purple-900">حقوق الملكية</span>
          </div>
          <div className="text-3xl font-black text-purple-950">{formatCurrency(totals.equity)}</div>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-5 text-white shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <Wallet size={24} />
            <span className="font-medium">إجمالي الأصول</span>
          </div>
          <p className="text-3xl font-bold">{formatCurrency(totals.assets || 0)}</p>
        </div>

        <div className="bg-gradient-to-br from-red-500 to-red-600 rounded-xl p-5 text-white shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <Building2 size={24} />
            <span className="font-medium">إجمالي الالتزامات</span>
          </div>
          <p className="text-3xl font-bold">{formatCurrency(totals.liabilities || 0)}</p>
        </div>

        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-5 text-white shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <PiggyBank size={24} />
            <span className="font-medium">حقوق الملكية</span>
          </div>
          <p className="text-3xl font-bold">{formatCurrency(totals.equity || 0)}</p>
        </div>
      </div>

      {/* Balance Sheet Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {renderAccountsSection('الأصول', sections.assets, totals.assets, Wallet, 'bg-blue-50', 'text-blue-600')}

        <div className="space-y-6">
          {renderAccountsSection(
            'الالتزامات',
            sections.liabilities,
            totals.liabilities,
            Building2,
            'bg-red-50',
            'text-red-600',
          )}

          {renderAccountsSection('حقوق الملكية', sections.equity, totals.equity, PiggyBank, 'bg-purple-50', 'text-purple-600')}
        </div>
      </div>
    </div>
  );
};

export default BalanceSheet;
