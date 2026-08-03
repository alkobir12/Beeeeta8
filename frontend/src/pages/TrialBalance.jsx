
import React, { useEffect, useState } from 'react';
import { Scale, Download, RefreshCw, Calendar, CheckCircle, XCircle, Search, AlertCircle, Loader2 } from 'lucide-react';
import { financeAPI } from '../services/api';
import { formatCurrency, formatDate } from '../utils/formatters';

const TrialBalance = () => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().split('T')[0]);
  const [searchQuery, setSearchQuery] = useState('');

  const workshopId = process.env.REACT_APP_WORKSHOP_ID;

  useEffect(() => {
    if (!workshopId) {
      setError('لم يتم ضبط معرف الورشة REACT_APP_WORKSHOP_ID');
      setLoading(false);
      return;
    }
    fetchData();
    // 🔄 إعادة التحميل عند أي عملية مالية
    const onFinUpdated = () => fetchData();
    window.addEventListener('finance:updated', onFinUpdated);
    return () => window.removeEventListener('finance:updated', onFinUpdated);
    // eslint disabled
  }, [asOfDate, workshopId]);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await financeAPI.getTrialBalance({
        workshop_id: workshopId,
        as_of_date: asOfDate,
      });

      const data = response.data?.data;
      setReport(data || null);
    } catch (err) {
      console.error('Error fetching trial balance:', err);
      setError('تعذر جلب ميزان المراجعة. يرجى المحاولة مرة أخرى.');
    } finally {
      setLoading(false);
    }
  };

  const accounts = report?.accounts || [];
  const totals = report?.totals || { total_debit: 0, total_credit: 0, is_balanced: true };

  const filteredAccounts = accounts.filter((acc) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return acc.name.toLowerCase().includes(q) || acc.code.includes(q);
  });

  if (loading && !report) {
    return (
      <div className="flex flex-col items-center justify-center h-96" dir="rtl">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
        <p className="text-lg text-gray-600">جاري تحميل ميزان المراجعة...</p>
        <p className="text-sm text-gray-500">قد يستغرق هذا بضع لحظات</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6" dir="rtl" data-testid="trial-balance-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <Scale className="text-blue-600" />
            ميزان المراجعة
          </h1>
          <p className="text-gray-600 mt-1">
            التحقق من توازن الحسابات حتى تاريخ {formatDate(asOfDate)}
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
          totals.is_balanced ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
        }`}
      >
        <div className="flex items-center gap-3">
          {totals.is_balanced ? (
            <>
              <div className="p-2 bg-green-100 rounded-full">
                <CheckCircle className="text-green-600" size={24} />
              </div>
              <div>
                <p className="font-bold text-green-700">ميزان المراجعة متوازن ✓</p>
                <p className="text-sm text-green-600/80">إجمالي المدين = إجمالي الدائن</p>
              </div>
            </>
          ) : (
            <>
              <div className="p-2 bg-red-100 rounded-full">
                <XCircle className="text-red-600" size={24} />
              </div>
              <div>
                <p className="font-bold text-red-700">ميزان المراجعة غير متوازن</p>
                <p className="text-sm text-red-600/80">
                  الفرق: {formatCurrency(Math.abs((totals.total_debit || 0) - (totals.total_credit || 0)))}
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl p-4 border border-gray-200 mb-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
            <input
              type="text"
              placeholder="بحث بالاسم أو رقم الحساب..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pr-10 pl-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              data-testid="search-trial-balance"
            />
          </div>
        </div>
      </div>

      {/* Trial Balance Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-right font-semibold text-gray-500">رمز الحساب</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-500">اسم الحساب</th>
                <th className="px-4 py-3 text-left font-semibold text-green-600">مدين</th>
                <th className="px-4 py-3 text-left font-semibold text-red-600">دائن</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredAccounts.map((account, idx) => (
                <tr key={idx} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-2">
                    <span className="font-mono text-gray-500 text-xs">{account.code}</span>
                  </td>
                  <td className="px-4 py-2 text-gray-800">{account.name}</td>
                  <td className="px-4 py-2 text-left">
                    {account.debit > 0 ? (
                      <span className="font-mono text-green-700">{formatCurrency(account.debit)}</span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-left">
                    {account.credit > 0 ? (
                      <span className="font-mono text-red-700">{formatCurrency(account.credit)}</span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-gray-50">
              <tr className="font-bold">
                <td colSpan={2} className="px-4 py-3 text-gray-700">
                  الإجمالي
                </td>
                <td className="px-4 py-3 text-left text-green-700">
                  {formatCurrency(totals.total_debit || 0)}
                </td>
                <td className="px-4 py-3 text-left text-red-700">
                  {formatCurrency(totals.total_credit || 0)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
};

export default TrialBalance;
