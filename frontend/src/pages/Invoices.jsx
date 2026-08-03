
import React, { useEffect, useState } from 'react';
import {
  FileText,
  Plus,
  Download,
  RefreshCw,
  Filter,
  AlertCircle,
  Search,
  Loader2,
} from 'lucide-react';
import { financeAPI } from '../services/api';
import { formatCurrency, formatDate } from '../utils/formatters';

const Invoices = () => {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const workshopId = process.env.REACT_APP_WORKSHOP_ID;

  useEffect(() => {
    if (!workshopId) {
      setError('لم يتم ضبط معرف الورشة REACT_APP_WORKSHOP_ID');
      setLoading(false);
      return;
    }
    fetchData();
    // eslint disabled
  }, [statusFilter, typeFilter, workshopId]);
  // الاستماع لأي تحديث على المركبات (من صفحة VehicleDetails أو QuickActions)
  useEffect(() => {
    const handler = (e) => {
      // عند تحديث مركبة، نقوم بإعادة تحميل الفواتير فوراً
      fetchData();
    };
    window.addEventListener('vehicleUpdated', handler);
    window.addEventListener('finance:updated', handler);
    return () => {
      window.removeEventListener('vehicleUpdated', handler);
      window.removeEventListener('finance:updated', handler);
    };
  }, []);


  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // إضافة باراميتر زمني بسيط لتفادي أي كاش محتمل من المتصفح أو البروكسي
      const response = await financeAPI.getInvoices({
        status: statusFilter || undefined,
        _ts: Date.now(),
      });

      // تحويل البيانات للتأكد من توافق الحقول
      const invoicesData = (response.data || response || []).map(inv => ({
        id: inv.id,
        invoice_number: inv.invoice_number || inv.id?.substring(0, 8) || 'N/A',
        customer_name: inv.customerName || inv.customer_name || 'غير محدد',
        plate_number: inv.plateNumber || inv.plate_number || '',
        vehicle_id: inv.vehicleId || inv.vehicle_id,
        items: inv.items || [],
        subtotal: inv.subtotal || 0,
        tax: inv.tax || 0,
        total: inv.total || 0,
        status: inv.status || 'pending',
        date: inv.date || inv.created_at,
        created_at: inv.created_at
      }));
      
      setInvoices(invoicesData);
      console.log('✅ تم جلب', invoicesData.length, 'فاتورة');
    } catch (err) {
      console.error('Error fetching invoices:', err);
      setError('تعذر جلب الفواتير. يرجى المحاولة مرة أخرى.');
      setInvoices([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredInvoices = invoices.filter((inv) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      inv.invoice_number?.toLowerCase().includes(q) ||
      inv.customer_name?.toLowerCase().includes(q) ||
      inv.status?.toLowerCase().includes(q)
    );
  });

  if (loading && invoices.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-96" dir="rtl">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
        <p className="text-lg text-gray-600">جاري تحميل الفواتير...</p>
        <p className="text-sm text-gray-500">قد يستغرق هذا بضع لحظات</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6" dir="rtl" data-testid="invoices-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <FileText className="text-blue-600" />
            الفواتير
          </h1>
          <p className="text-gray-600 mt-1">إدارة ومتابعة فواتير الورشة</p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <button className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 text-sm">
            <Plus className="h-4 w-4" />
            إنشاء فاتورة جديدة
          </button>
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

      {/* Filters */}
      <div className="bg-white rounded-xl p-4 border border-gray-200 mb-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
            <input
              type="text"
              placeholder="بحث برقم الفاتورة أو اسم العميل أو الحالة..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pr-10 pl-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              data-testid="search-invoices"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Filter className="text-gray-400" size={18} />
              <span className="text-sm text-gray-600">نوع الفاتورة</span>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="px-3 py-2 border border-gray-200 rounded-lg bg-white text-sm"
              >
                <option value="">الكل</option>
                <option value="sale">مبيعات</option>
                <option value="purchase">مشتريات</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">حالة الفاتورة</span>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 border border-gray-200 rounded-lg bg-white text-sm"
              >
                <option value="">الكل</option>
                <option value="draft">مسودة</option>
                <option value="issued">صادرة</option>
                <option value="cancelled">ملغاة</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Invoices Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-right font-semibold text-gray-500">رقم الفاتورة</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-500">التاريخ</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-500">العميل</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-500">لوحة المركبة</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-500">إجمالي الفاتورة</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-500">المدفوع</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-500">المتبقي</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-500">حالة الفاتورة</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-500">حالة الدفع</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredInvoices.length > 0 ? (
                filteredInvoices.map((invoice) => (
                  <tr key={invoice.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-900">{invoice.invoice_number || '-'}</td>
                    <td className="px-4 py-3 text-gray-600">{formatDate(invoice.date)}</td>
                    <td className="px-4 py-3 text-gray-900 font-medium">{invoice.customer_name}</td>
                    <td className="px-4 py-3 text-gray-700">{invoice.plate_number || '-'}</td>
                    <td className="px-4 py-3 text-left text-gray-900 font-bold">{formatCurrency(invoice.total)}</td>
                    <td className="px-4 py-3 text-left text-green-600">{formatCurrency(0)}</td>
                    <td className="px-4 py-3 text-left text-red-600">{formatCurrency(invoice.total)}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex px-2 py-1 rounded text-xs font-medium bg-blue-50 text-blue-700">
                        صادرة
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-1 rounded text-xs font-medium ${
                        invoice.status === 'paid' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {invoice.status === 'paid' ? 'مدفوعة' : 'معلقة'}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-gray-500">
                    لا توجد فواتير مطابقة لخيارات التصفية الحالية.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Invoices;
