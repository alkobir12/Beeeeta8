import React, { useMemo, useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import { financeAPI } from '../services/api';
import { formatCurrency } from '../utils/formatters';
import { OPERATION_TYPE_LABELS, labelFromMap } from '../utils/displayLabels';

const ARReceivablesTab = () => {
  const queryClient = useQueryClient();
  const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';
  const [asOf, setAsOf] = useState(() => new Date().toISOString().split('T')[0]);
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return d.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [selectedCustomer, setSelectedCustomer] = useState('');
  const [exporting, setExporting] = useState(false);

  // 🔄 إعادة التحميل عند أي عملية مالية
  useEffect(() => {
    const onFinUpdated = () => {
      try {
        queryClient.invalidateQueries({ queryKey: ['ar-customers'] });
        queryClient.invalidateQueries({ queryKey: ['ar-aging'] });
      } catch (e) { console.warn('ar refresh err', e); }
    };
    window.addEventListener('finance:updated', onFinUpdated);
    return () => window.removeEventListener('finance:updated', onFinUpdated);
  }, [queryClient]);

  const customersQuery = useQuery({
    queryKey: ['ar-customers', workshopId, asOf],
    queryFn: async () => {
      const res = await financeAPI.getARCustomers({ workshop_id: workshopId, as_of: asOf });
      return res.data?.data || null;
    },
    retry: 1,
  });

  const agingQuery = useQuery({
    queryKey: ['ar-aging', workshopId, asOf],
    queryFn: async () => {
      const res = await financeAPI.getARAging({ workshop_id: workshopId, as_of: asOf });
      return res.data?.data || null;
    },
  });

  const ledgerQuery = useQuery({
    queryKey: ['ar-ledger', workshopId, startDate, endDate],
    queryFn: async () => {
      const res = await financeAPI.getARLedger({ workshop_id: workshopId, start_date: startDate, end_date: endDate });
      return res.data?.data || null;
    },
  });

  const statementQuery = useQuery({
    queryKey: ['ar-statement', workshopId, selectedCustomer, startDate, endDate],
    enabled: !!selectedCustomer,
    queryFn: async () => {
      const res = await financeAPI.getARCustomerStatement({
        workshop_id: workshopId,
        customer: selectedCustomer,
        start_date: startDate,
        end_date: endDate,
      });
      return res.data?.data || null;
    },
  });

  const customers = customersQuery.data?.customers || [];
  const customerNames = useMemo(() => customers.map((c) => c.customer).filter(Boolean), [customers]);

  const totalAR = customersQuery.data?.total_ar ?? 0;
  const buckets = agingQuery.data?.buckets || {};

  const handleExport = async () => {
    try {
      setExporting(true);
      const response = await financeAPI.exportARLedgerExcel({
        workshop_id: workshopId,
        start_date: startDate,
        end_date: endDate,
        as_of: asOf,
        customer: selectedCustomer || undefined,
      });
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      const safeCustomer = String(selectedCustomer || 'all-customers').replace(/[^\u0600-\u06FF\w-]+/g, '-');
      link.href = url;
      link.download = `receivables-ledger-${safeCustomer}-${endDate}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('AR export failed', error);
      window.alert('تعذر تصدير ملف Excel الآن. حاول مرة أخرى بعد قليل.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-col md:flex-row md:items-end gap-3">
        <div className="flex items-center gap-2 rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>حتى تاريخ</span>
          <input
            type="date"
            value={asOf}
            onChange={(e) => setAsOf(e.target.value)}
            className="bg-transparent border-0 outline-none text-sm"
            style={{ color: 'var(--text-primary)' }}
            data-testid="ar-as-of-date-input"
          />
        </div>

        <div className="flex items-center gap-2 rounded-lg px-3 py-2" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>الفترة</span>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="bg-transparent border-0 outline-none text-sm"
            style={{ color: 'var(--text-primary)' }}
            data-testid="ar-start-date-input"
          />
          <span style={{ color: 'var(--text-secondary)' }}>-</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="bg-transparent border-0 outline-none text-sm"
            style={{ color: 'var(--text-primary)' }}
            data-testid="ar-end-date-input"
          />
        </div>

        <div className="flex-1" />

        <button
          type="button"
          onClick={handleExport}
          disabled={exporting || ledgerQuery.isLoading}
          className="inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-2 text-sm font-medium transition disabled:opacity-60"
          style={{
            backgroundColor: 'rgba(34, 197, 94, 0.14)',
            border: '1px solid rgba(74, 222, 128, 0.22)',
            color: '#d1fae5',
          }}
          data-testid="ar-export-excel-button"
        >
          <Download size={16} />
          {exporting ? 'جاري التصدير...' : 'تصدير Excel للمطابقة'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-2xl p-4" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }} data-testid="ar-total-card">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }} data-testid="ar-total-card-title">إجمالي ذمم العملاء</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }} data-testid="ar-total-card-value">{formatCurrency(totalAR)}</p>
          <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }} data-testid="ar-total-card-note">∑ أرصدة العملاء = رصيد الذمم</p>
        </div>

        <div className="rounded-2xl p-4" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }} data-testid="ar-aging-card">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }} data-testid="ar-aging-card-title">تقادم الذمم</p>
          <div className="mt-2 space-y-1 text-sm" style={{ color: 'var(--text-primary)' }} data-testid="ar-aging-card-values">
            <div className="flex justify-between"><span>0-30 يوم</span><span className="font-mono" data-testid="ar-aging-0-30">{formatCurrency(buckets['0_30'] || 0)}</span></div>
            <div className="flex justify-between"><span>31-60 يوم</span><span className="font-mono" data-testid="ar-aging-31-60">{formatCurrency(buckets['31_60'] || 0)}</span></div>
            <div className="flex justify-between"><span>61-90 يوم</span><span className="font-mono" data-testid="ar-aging-61-90">{formatCurrency(buckets['61_90'] || 0)}</span></div>
            <div className="flex justify-between"><span>90+ يوم</span><span className="font-mono" data-testid="ar-aging-90-plus">{formatCurrency(buckets['90_plus'] || 0)}</span></div>
          </div>
        </div>

        <div className="rounded-2xl p-4" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }} data-testid="ar-customers-count-card">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }} data-testid="ar-customers-count-card-title">عدد العملاء المدينين</p>
          <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }} data-testid="ar-customers-count-card-value">{customers.length}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
          <div className="px-4 py-3 font-semibold" style={{ color: 'var(--text-primary)', borderBottom: '1px solid var(--border-color)' }}>
            أرصدة العملاء (حتى {asOf})
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/20">
                <tr>
                  <th className="px-4 py-3 text-right" style={{ color: 'var(--text-secondary)' }}>العميل</th>
                  <th className="px-4 py-3 text-right" style={{ color: 'var(--text-secondary)' }}>الرصيد</th>
                </tr>
              </thead>
              <tbody>
                {customersQuery.isLoading ? (
                  <tr><td className="px-4 py-4" colSpan={2} style={{ color: 'var(--text-secondary)' }}>جار التحميل...</td></tr>
                ) : (customers.length === 0 ? (
                  <tr><td className="px-4 py-4" colSpan={2} style={{ color: 'var(--text-secondary)' }}>لا توجد ذمم</td></tr>
                ) : customers.map((c) => (
                  <tr key={c.customer} className="border-t" style={{ borderColor: 'var(--border-color)' }}>
                    <td className="px-4 py-3" style={{ color: 'var(--text-primary)' }}>{c.customer}</td>
                    <td className="px-4 py-3 font-mono" style={{ color: 'var(--text-primary)' }}>{formatCurrency(c.balance || 0)}</td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
          <div className="px-4 py-3 font-semibold" style={{ color: 'var(--text-primary)', borderBottom: '1px solid var(--border-color)' }}>
            كشف حساب عميل
          </div>
          <div className="p-4 space-y-3">
            <select
              value={selectedCustomer}
              onChange={(e) => setSelectedCustomer(e.target.value)}
              className="w-full rounded-lg px-3 py-2"
              style={{ backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
              data-testid="ar-customer-select"
            >
              <option value="">اختر عميل...</option>
              {customerNames.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>

            <div className="text-sm" style={{ color: 'var(--text-secondary)' }} data-testid="ar-statement-period-label">
              {selectedCustomer ? `الفترة: ${startDate} إلى ${endDate}` : 'اختر عميل لعرض كشف الحساب'}
            </div>

            {selectedCustomer && (
              <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border-color)' }}>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-900/20">
                      <tr>
                        <th className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>التاريخ</th>
                        <th className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>النوع</th>
                        <th className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>مدين</th>
                        <th className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>دائن</th>
                        <th className="px-3 py-2 text-right" style={{ color: 'var(--text-secondary)' }}>الرصيد</th>
                      </tr>
                    </thead>
                    <tbody>
                      {statementQuery.isLoading ? (
                        <tr><td className="px-3 py-3" colSpan={5} style={{ color: 'var(--text-secondary)' }}>جار التحميل...</td></tr>
                      ) : (
                        (statementQuery.data?.rows || []).map((r, idx) => (
                          <tr key={idx} className="border-t" style={{ borderColor: 'var(--border-color)' }}>
                            <td className="px-3 py-2" style={{ color: 'var(--text-primary)' }}>{String(r.date || '').slice(0, 10)}</td>
                            <td className="px-3 py-2" style={{ color: 'var(--text-primary)' }}>{labelFromMap(r.type, OPERATION_TYPE_LABELS, r.type || '-')}</td>
                            <td className="px-3 py-2 font-mono" style={{ color: 'var(--text-primary)' }}>{formatCurrency(r.debit || 0)}</td>
                            <td className="px-3 py-2 font-mono" style={{ color: 'var(--text-primary)' }}>{formatCurrency(r.credit || 0)}</td>
                            <td className="px-3 py-2 font-mono" style={{ color: 'var(--text-primary)' }}>{formatCurrency(r.running_balance || 0)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="px-3 py-2 text-sm" style={{ borderTop: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
                  الرصيد الختامي: <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{formatCurrency(statementQuery.data?.ending_balance || 0)}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
        <div className="px-4 py-3 font-semibold" style={{ color: 'var(--text-primary)', borderBottom: '1px solid var(--border-color)' }}>
          دفتر الأستاذ - حساب الذمم (113) للفترة
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/20">
              <tr>
                <th className="px-4 py-3 text-right" style={{ color: 'var(--text-secondary)' }}>التاريخ</th>
                <th className="px-4 py-3 text-right" style={{ color: 'var(--text-secondary)' }}>العميل</th>
                <th className="px-4 py-3 text-right" style={{ color: 'var(--text-secondary)' }}>مدين</th>
                <th className="px-4 py-3 text-right" style={{ color: 'var(--text-secondary)' }}>دائن</th>
                <th className="px-4 py-3 text-right" style={{ color: 'var(--text-secondary)' }}>الرصيد</th>
              </tr>
            </thead>
            <tbody>
              {ledgerQuery.isLoading ? (
                <tr><td className="px-4 py-4" colSpan={5} style={{ color: 'var(--text-secondary)' }}>جار التحميل...</td></tr>
              ) : (
                (ledgerQuery.data?.rows || []).map((r, idx) => (
                  <tr key={idx} className="border-t" style={{ borderColor: 'var(--border-color)' }}>
                    <td className="px-4 py-2" style={{ color: 'var(--text-primary)' }}>{String(r.date || '').slice(0, 10)}</td>
                    <td className="px-4 py-2" style={{ color: 'var(--text-primary)' }}>{r.customer}</td>
                    <td className="px-4 py-2 font-mono" style={{ color: 'var(--text-primary)' }}>{formatCurrency(r.debit || 0)}</td>
                    <td className="px-4 py-2 font-mono" style={{ color: 'var(--text-primary)' }}>{formatCurrency(r.credit || 0)}</td>
                    <td className="px-4 py-2 font-mono" style={{ color: 'var(--text-primary)' }}>{formatCurrency(r.running_balance || 0)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-3 text-sm" style={{ borderTop: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
          الرصيد الختامي: <span className="font-mono" style={{ color: 'var(--text-primary)' }}>{formatCurrency(ledgerQuery.data?.ending_balance || 0)}</span>
        </div>
      </div>
    </div>
  );
};

export default ARReceivablesTab;
