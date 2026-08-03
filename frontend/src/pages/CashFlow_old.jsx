
import React, { useEffect, useState } from 'react';
import {
  Banknote,
  Download,
  RefreshCw,
  Calendar,
  ArrowUpRight,
  ArrowDownRight,
  Wallet,
  TrendingUp,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { financeAPI } from '../services/api';
import { formatCurrency, formatDate } from '../utils/formatters';

const CashFlow = () => {
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

  const period = report?.period || `${startDate} إلى ${endDate}`;
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
        <p className="text-lg text-gray-600">جاري تحميل قائمة التدفقات النقدية...</p>
        <p className="text-sm text-gray-500">قد يستغرق هذا بضع لحظات</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6" dir="rtl" data-testid="cash-flow-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <Banknote className="text-green-600" />
            قائمة التدفقات النقدية
          </h1>
          <p className="text-gray-600 mt-1">
            تتبع حركة النقد الداخل والخارج عن الفترة من {new Date(startDate).toLocaleDateString('ar-SA')} إلى{' '}
            {new Date(endDate).toLocaleDateString('ar-SA')}
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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-2xl p-6 border-2 border-green-200 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-3 bg-green-200 rounded-xl">
              <TrendingUp className="text-green-700" size={24} />
            </div>
            <span className="text-base font-bold text-green-900">صافي التدفق من التشغيل</span>
          </div>
          <div className="text-3xl font-black text-green-950">{formatCurrency(netOperatingCash)}</div>
        </div>

        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-2xl p-6 border-2 border-blue-200 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-3 bg-blue-200 rounded-xl">
              <ArrowDownRight className="text-blue-700" size={24} />
            </div>
            <span className="text-base font-bold text-blue-900">صافي التدفق من الاستثمار</span>
          </div>
          <div className="text-3xl font-black text-blue-950">{formatCurrency(netInvestingCash)}</div>
        </div>

        <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-2xl p-6 border-2 border-purple-200 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-3 bg-purple-200 rounded-xl">
              <Wallet className="text-purple-700" size={24} />
            </div>
            <span className="text-base font-bold text-purple-900">صافي التدفق من التمويل</span>
          </div>
          <div className="text-3xl font-black text-purple-950">{formatCurrency(netFinancingCash)}</div>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <Wallet className="text-gray-500" size={20} />
            <span className="text-sm text-gray-500">صافي التدفق من التشغيل</span>
          </div>
          <p
            className={`text-2xl font-bold ${
              netOperatingCash >= 0 ? 'text-green-700' : 'text-red-700'
            }`}
          >
            {formatCurrency(netOperatingCash)}
          </p>
        </div>

        <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="text-purple-500" size={20} />
            <span className="text-sm text-gray-500">صافي التدفق من الاستثمار</span>
          </div>
          <p
            className={`text-2xl font-bold ${
              netInvestingCash >= 0 ? 'text-green-700' : 'text-red-700'
            }`}
          >
            {formatCurrency(netInvestingCash)}
          </p>
        </div>

        <div className="bg-white rounded-xl p-5 border border-gray-200 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="text-blue-500" size={20} />
            <span className="text-sm text-gray-500">صافي التدفق من التمويل</span>
          </div>
          <p
            className={`text-2xl font-bold ${
              netFinancingCash >= 0 ? 'text-green-700' : 'text-red-700'
            }`}
          >
            {formatCurrency(netFinancingCash)}
          </p>
        </div>
      </div>

      {/* Activities */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {renderActivitySection('الأنشطة التشغيلية', operating, 'bg-blue-50', 'text-blue-600')}
        {renderActivitySection('الأنشطة الاستثمارية', investing, 'bg-purple-50', 'text-purple-600')}
        {renderActivitySection('الأنشطة التمويلية', financing, 'bg-orange-50', 'text-orange-600')}
      </div>

      {/* Summary */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4 shadow-sm">
        <h3 className="font-bold text-gray-800 text-lg mb-2">ملخص التدفقات النقدية</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">صافي التدفق من الأنشطة التشغيلية</span>
            <span
              className={`font-bold ${
                netOperatingCash >= 0 ? 'text-green-700' : 'text-red-700'
              }`}
            >
              {formatCurrency(netOperatingCash)}
            </span>
          </div>

          <div className="flex justify-between">
            <span className="text-gray-600">صافي التدفق من الأنشطة الاستثمارية</span>
            <span
              className={`font-bold ${
                netInvestingCash >= 0 ? 'text-green-700' : 'text-red-700'
              }`}
            >
              {formatCurrency(netInvestingCash)}
            </span>
          </div>

          <div className="flex justify-between">
            <span className="text-gray-600">صافي التدفق من الأنشطة التمويلية</span>
            <span
              className={`font-bold ${
                netFinancingCash >= 0 ? 'text-green-700' : 'text-red-700'
              }`}
            >
              {formatCurrency(netFinancingCash)}
            </span>
          </div>

          <div className="flex justify-between items-center p-3 mt-2 bg-blue-50 border border-blue-100 rounded-lg">
            <span className="font-bold text-blue-700">صافي التغير في النقد</span>
            <span
              className={`text-xl font-bold ${
                netChangeInCash >= 0 ? 'text-green-700' : 'text-red-700'
              }`}
            >
              {formatCurrency(netChangeInCash)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

const renderActivitySection = (title, activity, headerBg, accentText) => {
  const inflows = activity?.inflows || [];
  const outflows = activity?.outflows || [];
  const net = activity?.net_cash_flow || 0;

  const totalInflows = inflows.reduce((sum, item) => sum + item.amount, 0);
  const totalOutflows = outflows.reduce((sum, item) => sum + item.amount, 0);

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      <div className={`${headerBg} px-4 py-3 flex items-center justify-between`}>
        <div className="flex items-center gap-2">
          <Banknote className={accentText} size={20} />
          <h3 className={`font-bold ${accentText}`}>{title}</h3>
        </div>
        <span
          className={`font-bold ${net >= 0 ? 'text-green-700' : 'text-red-700'}`}
        >
          {formatCurrency(net)}
        </span>
      </div>

      <div className="p-4 space-y-4 text-sm">
        {/* Inflows */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <ArrowUpRight className="text-green-600" size={16} />
            <h4 className="text-green-700 font-medium">التدفقات الداخلة</h4>
          </div>
          {inflows.length > 0 ? (
            <>
              <div className="space-y-1">
                {inflows.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex justify-between items-center py-1.5 px-2 rounded hover:bg-gray-50"
                  >
                    <span className="text-gray-800">{item.name}</span>
                    <span className="font-mono text-green-700">
                      {formatCurrency(item.amount)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex justify-between items-center mt-2 pt-2 border-t border-gray-100">
                <span className="text-gray-500">إجمالي التدفقات الداخلة</span>
                <span className="font-bold text-green-700">{formatCurrency(totalInflows)}</span>
              </div>
            </>
          ) : (
            <p className="text-gray-500 text-center">لا توجد تدفقات داخلة.</p>
          )}
        </div>

        {/* Outflows */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <ArrowDownRight className="text-red-600" size={16} />
            <h4 className="text-red-700 font-medium">التدفقات الخارجة</h4>
          </div>
          {outflows.length > 0 ? (
            <>
              <div className="space-y-1">
                {outflows.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex justify-between items-center py-1.5 px-2 rounded hover:bg-gray-50"
                  >
                    <span className="text-gray-800">{item.name}</span>
                    <span className="font-mono text-red-700">
                      {formatCurrency(item.amount)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex justify-between items-center mt-2 pt-2 border-t border-gray-100">
                <span className="text-gray-500">إجمالي التدفقات الخارجة</span>
                <span className="font-bold text-red-700">{formatCurrency(totalOutflows)}</span>
              </div>
            </>
          ) : (
            <p className="text-gray-500 text-center">لا توجد تدفقات خارجة.</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default CashFlow;
