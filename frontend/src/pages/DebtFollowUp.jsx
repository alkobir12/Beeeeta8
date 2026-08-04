import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, MessageCircle, RefreshCw, Send, WalletCards } from 'lucide-react';
import { api, customerAPI, supplierAPI } from '../services/api';
import { useToast } from '../hooks/use-toast';
import DebtWhatsAppComposerDialog from '../components/DebtWhatsAppComposerDialog';
import ConfirmPaymentDialog from '../components/ConfirmPaymentDialog';
import { buildDebtWhatsAppDraft } from '../utils/debtWhatsapp';
import { getWhatsAppLink } from '../utils/constants';

const CURRENT_AR_CACHE_KEY = 'debt-followup.current-ar.snapshot.v1';

const readCurrentArCache = () => {
  try {
    const raw = localStorage.getItem(CURRENT_AR_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed?.rows) ? parsed.rows : [];
  } catch {
    return [];
  }
};

const writeCurrentArCache = (rows = []) => {
  if (!Array.isArray(rows) || !rows.length) return;
  try {
    localStorage.setItem(CURRENT_AR_CACHE_KEY, JSON.stringify({ rows, savedAt: new Date().toISOString() }));
  } catch {
    // best effort cache فقط لتثبيت العرض عند abort/reload
  }
};

export default function DebtFollowUp() {
  const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';
  const { toast } = useToast();

  const initialArRows = readCurrentArCache();
  const [loading, setLoading] = useState(true);
  const [arHydrating, setArHydrating] = useState(initialArRows.length === 0);
  const [entries, setEntries] = useState(initialArRows);
  const [selectedIds, setSelectedIds] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [settlementAccounts, setSettlementAccounts] = useState([]);
  const [liquidityBalances, setLiquidityBalances] = useState({ cash: 0, bank: 0 });
  const [expandedCards, setExpandedCards] = useState({});
  const [manualAmounts, setManualAmounts] = useState({});
  const [savingRowId, setSavingRowId] = useState('');
  const [confirmPayRow, setConfirmPayRow] = useState(null);   // الصف المُراد تأكيد سداده
  const [confirmPayLoading, setConfirmPayLoading] = useState(false);
  const [arLedger, setArLedger] = useState(null);             // 📒 L14-D6: طبقات SSOT

  const fetchData = async () => {
    try {
      setLoading(true);
      const withTimeout = (promise, fallback, timeoutMs = 12000) => Promise.race([
        promise.catch(() => fallback),
        new Promise((resolve) => setTimeout(() => resolve(fallback), timeoutMs)),
      ]);
      const fetchCurrentArCustomers = async () => {
        const asOf = new Date().toISOString().slice(0, 10);
        return api.get('/finance/ar/customers', {
          params: { workshop_id: workshopId, as_of: asOf, include_today: true },
          timeout: 8000,
        });
      };
      const arCustomersRes = await withTimeout(fetchCurrentArCustomers(), { data: { data: { customers: [] } } }, 12000);

      // 📒 L14-D6: طبقات SSOT للذمم (best-effort — لا يعطّل الصفحة)
      api.get('/finance/ar-ledger', { params: { workshop_id: workshopId } })
        .then((r) => setArLedger(r?.data?.data || null))
        .catch(() => setArLedger(null));

      const normalizeRows = (payload, preferredKey) => {
        if (Array.isArray(payload)) return payload;
        if (Array.isArray(payload?.[preferredKey])) return payload[preferredKey];
        if (Array.isArray(payload?.data)) return payload.data;
        if (Array.isArray(payload?.items)) return payload.items;
        return [];
      };
      const arCustomerRows = normalizeRows(arCustomersRes?.data?.data, 'customers');
      const arPayload = arCustomersRes?.data?.data || {};
      const arTotalFromEngine = Number(arPayload.total_ar || 0);
      if (arTotalFromEngine > 0) {
        setArLedger((current) => current || {
          current_vehicle_ar_total: arTotalFromEngine,
          ledger_ar_total: arTotalFromEngine,
          pending_unjournalized_total: 0,
          pending_unjournalized_ops: [],
          stored_balances_total: 0,
          reconciliation_gap: 0,
        });
      }
      const customersSource = arCustomerRows.length
        ? arCustomerRows.map((row, index) => ({
          id: row.id || row.customer_id || `ar-customer-${index}`,
          name: row.customer || row.name || row.customerName || row.customer_name || 'عميل',
          phone: row.phone || row.customer_phone || row.customerPhone || row.whatsapp || '',
          ajelBalance: Number(row.balance || 0),
          overdueBalance: Number(row.balance || 0),
          debitBalance: Number(row.debitBalance || row.debit_balance || row.balance || 0),
          creditBalance: Number(row.creditBalance || row.credit_balance || 0),
          source: 'vehicle_visit_current_ar',
        }))
        : [];
      const customers = customersSource.map((row) => ({ ...row, entityType: 'customer' }));
      if (customers.length) setArHydrating(false);
      const suppliers = [];
      const merged = [...customers, ...suppliers]
        .map((row) => ({
          ...row,
          ajelBalance: Number(row.ajelBalance || row.overdueBalance || 0),
          overdueBalance: Number(row.overdueBalance || row.ajelBalance || 0),
        }))
        .filter((row) => row.ajelBalance > 0 || row.overdueBalance > 0);

      if (merged.length > 0) writeCurrentArCache(merged);
      setEntries((current) => {
        if (merged.length > 0) return merged;
        return current.length > 0 ? current : [];
      });
      Promise.all([
        withTimeout(customerAPI.getAll({ workshop_id: workshopId }), { data: [] }, 8000),
        withTimeout(supplierAPI.getAll({ workshop_id: workshopId }), { data: [] }, 8000),
      ]).then(([customersRes, suppliersRes]) => {
        const fallbackCustomers = arCustomerRows.length ? [] : normalizeRows(customersRes?.data, 'customers').map((row) => ({ ...row, entityType: 'customer' }));
        const supplierRows = normalizeRows(suppliersRes?.data, 'suppliers').map((row) => ({ ...row, entityType: 'supplier' }));
        if (fallbackCustomers.length || supplierRows.length) {
          setEntries((current) => {
            const hasCurrentAr = current.some((row) => row.source === 'vehicle_visit_current_ar');
            if (hasCurrentAr && !supplierRows.length) return current;
            return [...current, ...fallbackCustomers, ...supplierRows];
          });
        }
      }).catch(() => {});
      api.get('/finance/chart-of-accounts', { params: { workshop_id: workshopId }, timeout: 8000 })
        .then((accountsRes) => {
          const accountRows = Array.isArray(accountsRes?.data?.data)
            ? accountsRes.data.data
            : Array.isArray(accountsRes?.data)
              ? accountsRes.data
              : [];
          const payableAccounts = accountRows.filter((acc) => ['asset', 'liability', 'expense'].includes(String(acc?.type || '').toLowerCase()));
          setSettlementAccounts(payableAccounts);

          const normalizeName = (acc) => String(acc?.name || acc?.account_name || '').toLowerCase();
          const toBalance = (acc) => Number(acc?.balance ?? acc?.current_balance ?? 0);
          const cashAccounts = accountRows.filter((acc) => {
            const name = normalizeName(acc);
            return name.includes('نقد') || name.includes('صندوق') || name.includes('cash');
          });
          const bankAccounts = accountRows.filter((acc) => {
            const name = normalizeName(acc);
            return name.includes('بنك') || name.includes('bank');
          });
          setLiquidityBalances({
            cash: cashAccounts.reduce((sum, acc) => sum + toBalance(acc), 0),
            bank: bankAccounts.reduce((sum, acc) => sum + toBalance(acc), 0),
          });
        })
        .catch(() => {
          setSettlementAccounts([]);
          setLiquidityBalances({ cash: 0, bank: 0 });
        });
    } catch (error) {
      const cached = readCurrentArCache();
      if (cached.length) setEntries(cached);
      toast({ title: 'خطأ', description: 'تعذر تحميل متابعة الذمم', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  const hydrateCurrentAr = async () => {
    try {
      const asOf = new Date().toISOString().slice(0, 10);
      const response = await api.get('/finance/ar/customers', {
        params: { workshop_id: workshopId, as_of: asOf, include_today: true },
        timeout: 12000,
      });
      const payload = response?.data;
      const rows = Array.isArray(payload?.data?.customers) ? payload.data.customers : [];
      if (!rows.length) {
        const cached = readCurrentArCache();
        if (cached.length) {
          setEntries((current) => (current.length ? current : cached));
          setLoading(false);
        }
        setArHydrating(false);
        return;
      }
      const hydratedRows = rows.map((row, index) => ({
        id: row.id || row.customer_id || `ar-customer-${index}`,
        name: row.customer || row.name || 'عميل',
        phone: row.phone || row.customer_phone || row.customerPhone || row.whatsapp || '',
        ajelBalance: Number(row.balance || 0),
        overdueBalance: Number(row.balance || 0),
        debitBalance: Number(row.debitBalance || row.debit_balance || row.balance || 0),
        creditBalance: Number(row.creditBalance || row.credit_balance || 0),
        movements: [{ date: asOf, amount: Number(row.balance || 0), source: 'vehicle_visit_current_ar' }],
        entityType: 'customer',
        source: 'vehicle_visit_current_ar',
      }));
      writeCurrentArCache(hydratedRows);
      setEntries((current) => {
        const currentTotal = current.reduce((sum, row) => sum + Number(row.ajelBalance || row.overdueBalance || 0), 0);
        const hydratedTotal = hydratedRows.reduce((sum, row) => sum + Number(row.ajelBalance || row.overdueBalance || 0), 0);
        return hydratedTotal >= currentTotal ? hydratedRows : current;
      });
      setArHydrating(false);
      setLoading(false);
    } catch {
      const cached = readCurrentArCache();
      if (cached.length) {
        setEntries((current) => (current.length ? current : cached));
        setLoading(false);
      }
      setArHydrating(false);
    }
  };

  useEffect(() => {
    fetchData();
    hydrateCurrentAr();
    const fallbackTimer = setTimeout(() => hydrateCurrentAr(), 1500);
    const settleTimer = setTimeout(() => hydrateCurrentAr(), 5000);
    // 🔄 إعادة التحديث عند أي عملية مالية في صفحة أخرى
    const onFinUpdated = () => fetchData();
    window.addEventListener('finance:updated', onFinUpdated);
    return () => {
      clearTimeout(fallbackTimer);
      clearTimeout(settleTimer);
      window.removeEventListener('finance:updated', onFinUpdated);
    };
  }, []);

  const fmt = (v) => Number(v || 0).toLocaleString('ar-SA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const totals = useMemo(() => {
    return entries.reduce(
      (acc, row) => {
        if (row.entityType === 'customer') {
          acc.customers += Number(row.ajelBalance || 0);
        } else {
          acc.suppliers += Number(row.ajelBalance || 0);
        }
        return acc;
      },
      { customers: 0, suppliers: 0 }
    );
  }, [entries]);

  const agingBuckets = useMemo(() => {
    const out = { b0_30: 0, b31_60: 0, b61_90: 0, b90_plus: 0 };
    const now = Date.now();
    entries.forEach((row) => {
      const dateText = row?.movements?.[0]?.date;
      const dt = dateText ? new Date(dateText).getTime() : now;
      const ageDays = Math.max(0, Math.floor((now - dt) / (1000 * 60 * 60 * 24)));
      const amt = Number(row.ajelBalance || 0);
      if (ageDays <= 30) out.b0_30 += amt;
      else if (ageDays <= 60) out.b31_60 += amt;
      else if (ageDays <= 90) out.b61_90 += amt;
      else out.b90_plus += amt;
    });
    return out;
  }, [entries]);

  const selectedEntries = useMemo(
    () => entries.filter((row) => selectedIds.includes(`${row.entityType}-${row.id}`)),
    [entries, selectedIds]
  );

  const metricsCards = useMemo(() => {
    const customerRows = entries.filter((row) => row.entityType === 'customer');
    const supplierRows = entries.filter((row) => row.entityType === 'supplier');
    return [
      {
        key: 'customers',
        title: 'ذمم العملاء (آجل)',
        value: totals.customers,
        tone: 'border-cyan-400/20 bg-cyan-500/10 text-cyan-100',
        subtitle: `عدد العملاء: ${customerRows.length}`,
        details: [
          `متوسط الذمة/عميل: ${fmt(customerRows.length ? totals.customers / customerRows.length : 0)} ر.س`,
          `إجمالي الجهات المحددة حاليًا: ${selectedEntries.filter((row) => row.entityType === 'customer').length}`,
        ],
      },
      {
        key: 'suppliers',
        title: 'حركة الموردين',
        value: totals.suppliers,
        tone: 'border-amber-400/20 bg-amber-500/10 text-amber-100',
        subtitle: `عدد الموردين: ${supplierRows.length}`,
        details: [
          `متوسط الحركة/مورد: ${fmt(supplierRows.length ? totals.suppliers / supplierRows.length : 0)} ر.س`,
          `إجمالي الجهات المحددة حاليًا: ${selectedEntries.filter((row) => row.entityType === 'supplier').length}`,
        ],
      },
      {
        key: 'aging_0_30',
        title: '0-30 يوم',
        value: agingBuckets.b0_30,
        tone: 'border-white/10 bg-white/5 text-slate-100',
        subtitle: 'الذمم الحديثة',
        details: [
          `31-60 يوم: ${fmt(agingBuckets.b31_60)} ر.س`,
          `61-90 يوم: ${fmt(agingBuckets.b61_90)} ر.س`,
          `+90 يوم: ${fmt(agingBuckets.b90_plus)} ر.س`,
        ],
      },
      {
        key: 'aging_31_plus',
        title: '+31 يوم',
        value: agingBuckets.b31_60 + agingBuckets.b61_90 + agingBuckets.b90_plus,
        tone: 'border-white/10 bg-white/5 text-slate-100',
        subtitle: 'الذمم المتأخرة',
        details: [
          `31-60 يوم: ${fmt(agingBuckets.b31_60)} ر.س`,
          `61-90 يوم: ${fmt(agingBuckets.b61_90)} ر.س`,
          `+90 يوم: ${fmt(agingBuckets.b90_plus)} ر.س`,
        ],
      },
      {
        key: 'cash_account',
        title: 'رصيد حساب النقد',
        value: liquidityBalances.cash,
        tone: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-100',
        subtitle: 'من دليل الحسابات',
        details: [
          'يشمل جميع الحسابات المصنفة نقدًا.',
          'يُستخدم لمراجعة السيولة النقدية الفعلية قبل أوامر السداد.',
        ],
      },
      {
        key: 'bank_account',
        title: 'رصيد حساب البنك',
        value: liquidityBalances.bank,
        tone: 'border-indigo-400/20 bg-indigo-500/10 text-indigo-100',
        subtitle: 'من دليل الحسابات',
        details: [
          'يشمل جميع الحسابات المصنفة بنكية.',
          'يساعد على اختيار وسيلة السداد المناسبة (نقد/تحويل).',
        ],
      },
    ];
  }, [agingBuckets, entries, liquidityBalances, selectedEntries, totals]);

  const openPreviewForRows = (rows) => {
    const nextDrafts = rows.map((row) => buildDebtWhatsAppDraft(row, row.entityType));
    if (!nextDrafts.length) {
      toast({ title: 'تنبيه', description: 'لا توجد جهات محددة للمعاينة' });
      return;
    }
    setDrafts(nextDrafts);
    setDialogOpen(true);
  };

  const updateDraftMessage = (draftId, message) => {
    setDrafts((prev) => prev.map((draft) => (
      draft.id === draftId
        ? { ...draft, message, url: draft.phone ? getWhatsAppLink(draft.phone, message) : '' }
        : draft
    )));
  };

  const sendCurrent = (draft) => {
    if (!draft?.phone || !draft?.url) {
      toast({ title: 'تنبيه', description: 'لا يوجد رقم واتساب صالح لهذه الجهة', variant: 'destructive' });
      return;
    }
    window.open(draft.url, '_blank', 'noopener,noreferrer');
  };

  const sendAll = (allDrafts) => {
    const validDrafts = (allDrafts || []).filter((draft) => draft.phone && draft.url);
    if (!validDrafts.length) {
      toast({ title: 'تنبيه', description: 'لا توجد رسائل صالحة للإرسال', variant: 'destructive' });
      return;
    }
    validDrafts.forEach((draft, index) => {
      setTimeout(() => {
        window.open(draft.url, '_blank', 'noopener,noreferrer');
      }, index * 280);
    });
    toast({ title: 'تم التنفيذ', description: `تم فتح ${validDrafts.length} رسالة واتساب بعد المعاينة` });
  };

  const createSettlementOrder = async (row, paymentLines, date) => {
    const rowId = `${row.entityType}-${row.id}`;
    const manualAmt = Number(manualAmounts[rowId] || 0);
    const defaultAmount = manualAmt > 0 ? manualAmt : Number(row.ajelBalance || 0);

    if (!paymentLines) {
      // فتح الـ dialog لاختيار وسيلة السداد
      setConfirmPayRow({ ...row, defaultAmount });
      return;
    }

    // تنفيذ السداد بعد اختيار الوسيلة
    const lines = paymentLines.length > 0 ? paymentLines : [{ method: 'bank_transfer', amount: null }];
    const totalFromLines = lines.reduce((s, l) => s + (l.amount || 0), 0);
    const finalAmount = totalFromLines > 0 ? totalFromLines : defaultAmount;

    if (finalAmount <= 0) {
      toast({ title: 'تنبيه', description: 'أدخل مبلغ صحيح', variant: 'destructive' });
      return;
    }

    setSavingRowId(rowId);
    try {
      for (const line of lines) {
        const lineAmt = line.amount && line.amount > 0 ? line.amount : finalAmount;
        const methodLabel = {
          bank: 'تحويل بنكي',
          bank_transfer: 'تحويل بنكي',
          cash: 'نقد',
          pos: 'نقاط بيع',
          supplier_balance: 'رصيد مورد',
        }[line.method] || line.method;

        if (line.method === 'supplier_balance') {
          if (row.entityType !== 'supplier') {
            throw new Error('سداد رصيد المورد متاح فقط لصفوف الموردين.');
          }
          await api.post('/smart-accounting/supplier-balance-payment', {
            supplier_id: row.id,
            amount: lineAmt,
            workshop_id: process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync',
            workshopId: process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync',
            notes: `تسوية ذمم عبر رصيد المورد (${row.name})`,
          });
          continue;
        }

        const cashAccountCode = line.method === 'pos' ? '006' : ['bank', 'bank_transfer', 'transfer'].includes(line.method) ? '004' : '003';
        const payload = {
          workshopId: process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync',
          workshop_id: process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync',
          type: row.entityType === 'supplier' ? 'expense' : 'payment_order',
          total: lineAmt,
          amount: lineAmt,
          paymentAmount: lineAmt,
          paymentMethod: line.method || 'bank',
          paymentStatus: 'paid',
          status: 'issued',
          date: date || new Date().toISOString().split('T')[0],
          accountingAccountCode: cashAccountCode,
          partnerId: row.id,
          partnerName: row.name,
          partnerPhone: row.phone || '',
          partnerType: row.entityType === 'supplier' ? 'supplier' : 'customer',
          scope: 'workshop',
          notes: `أمر تحصيل/سداد (${methodLabel}) - ${row.name}`,
          items: [{
            name: `سداد ذمم (${methodLabel}) — ${row.name}`,
            itemType: 'service',
            quantity: 1,
            qty: 1,
            price: lineAmt,
            total: lineAmt,
            isCustom: true,
          }],
        };
        await api.post('/operations', payload);
      }
      toast({ title: '✅ تم إنشاء أمر السداد', description: `${finalAmount.toLocaleString('ar-SA')} ر.س — ${row.name}` });
      setManualAmounts((prev) => ({ ...prev, [rowId]: '' }));
      setConfirmPayRow(null);
      await fetchData();
    } catch (err) {
      console.error('createSettlementOrder error:', err);
      const msg = err?.response?.data?.detail || err?.message || 'تعذر إنشاء أمر السداد';
      toast({ title: '❌ خطأ في السداد', description: msg, variant: 'destructive' });
    } finally {
      setSavingRowId('');
      setConfirmPayLoading(false);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6 pb-24 md:pb-6" dir="rtl" data-testid="debt-followup-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold text-slate-100" data-testid="debt-followup-title">متابعة الذمم والتحصيل</h1>
          <p className="text-xs sm:text-sm text-slate-300/80 mt-1 leading-6">تقادم الذمم + معاينة رسائل واتساب قبل الإرسال الفردي أو الجماعي.</p>
        </div>
        <button
          type="button"
          className="apple-button h-11 w-full sm:w-auto px-4 justify-center active:scale-[0.98] transition-transform"
          onClick={fetchData}
          data-testid="debt-followup-refresh-button"
        >
          <span className="inline-flex items-center gap-2"><RefreshCw size={14} /> تحديث</span>
        </button>
      </div>

      {/* 📒 شريط تثبيت المحرك المالي: الذمم الحالية من المحرك الموحد، والقيود للمطابقة */}
      {arLedger && (
        <div className="rounded-xl border border-indigo-400/25 bg-indigo-500/10 p-3 text-xs sm:text-sm text-indigo-100 flex flex-wrap items-center gap-x-4 gap-y-1"
             data-testid="ar-ssot-banner">
          <span className="font-bold">📒 المحرك المالي الموحد:</span>
          <span>الذمم الحالية: <b data-testid="ar-ssot-current-engine-total">{fmt(arLedger.current_vehicle_ar_total ?? arLedger.effective_ar)}</b> ر.س</span>
          <span>· رصيد القيود الكلي: <b data-testid="ar-ssot-ledger-total">{fmt(arLedger.ledger_ar_total)}</b> ر.س</span>
          <span>· آجل غير مقيّد: <b data-testid="ar-ssot-pending-total">{fmt(arLedger.pending_unjournalized_total)}</b> ({(arLedger.pending_unjournalized_ops || []).length} عمليات)</span>
          <span>· أرصدة قديمة للمراجعة: <b data-testid="ar-ssot-stored-total">{fmt(arLedger.stored_balances_total)}</b></span>
          <span className="text-amber-200">· فجوة القديم مع القيود: <b data-testid="ar-ssot-gap">{fmt(arLedger.reconciliation_gap)}</b></span>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-3" data-testid="debt-metrics-cards-grid">
        {metricsCards.map((card) => {
          const expanded = !!expandedCards[card.key];
          return (
            <div
              key={card.key}
              className={`rounded-xl border p-2.5 sm:p-3 min-h-[118px] ${card.tone}`}
              data-testid={`debt-summary-card-${card.key}`}
            >
              <button
                type="button"
                onClick={() => setExpandedCards((prev) => ({ ...prev, [card.key]: !prev[card.key] }))}
                className="w-full flex items-start justify-between gap-2 text-right min-h-[92px]"
                data-testid={`debt-summary-card-toggle-${card.key}`}
              >
                <div>
                  <p className="text-[11px] sm:text-xs opacity-80 leading-5">{card.title}</p>
                  <p className="text-base sm:text-lg font-bold mt-1 leading-6 break-words">{fmt(card.value)} ر.س</p>
                  <p className="text-[10px] sm:text-[11px] opacity-80 mt-1 leading-5">{card.subtitle}</p>
                </div>
                <span className="mt-1 opacity-80">
                  {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </span>
              </button>
              {expanded && (
                <div
                  className="mt-3 pt-3 border-t border-white/20 space-y-1 text-[12px] opacity-90"
                  data-testid={`debt-summary-card-details-${card.key}`}
                >
                  {card.details.map((line, idx) => (
                    <p key={`${card.key}-detail-${idx}`}>• {line}</p>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/5 p-3 sm:p-4" data-testid="debt-followup-table-wrapper">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-3">
          <div className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200 sm:border-0 sm:bg-transparent sm:p-0">
            <span>عدد الجهات</span>
            <span className="font-semibold text-cyan-100" data-testid="debt-followup-entries-count">{entries.length}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <button
              type="button"
              className="apple-button-secondary h-11 px-3 justify-center active:scale-[0.98] transition-transform"
              onClick={() => setSelectedIds(entries.map((row) => `${row.entityType}-${row.id}`))}
              data-testid="debt-select-all-button"
            >
              تحديد الكل
            </button>
            <button
              type="button"
              className="apple-button h-11 px-3 justify-center active:scale-[0.98] transition-transform"
              onClick={() => openPreviewForRows(selectedEntries)}
              data-testid="debt-open-bulk-preview-button"
            >
              <span className="inline-flex items-center gap-1"><MessageCircle size={15} /> معاينة جماعية</span>
            </button>
          </div>
        </div>

        {(loading || (arHydrating && entries.length === 0)) ? (
          <div className="py-10 text-center text-slate-400" data-testid="debt-followup-loading">جار تحميل الذمم...</div>
        ) : entries.length === 0 ? (
          <div className="py-10 text-center text-slate-400" data-testid="debt-followup-empty">لا توجد ذمم آجلة حالياً.</div>
        ) : (
          <>
          <div className="md:hidden space-y-3" data-testid="debt-followup-mobile-list">
            {entries.map((row) => {
              const rowId = `${row.entityType}-${row.id}`;
              const selected = selectedIds.includes(rowId);
              return (
                <div
                  key={`mobile-${rowId}`}
                  className="rounded-2xl border border-white/10 bg-slate-950/40 p-3 shadow-lg shadow-black/10"
                  data-testid={`debt-mobile-card-${rowId}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <label className="flex items-start gap-3 min-w-0" data-testid={`debt-mobile-select-label-${rowId}`}>
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={(e) => setSelectedIds((prev) => e.target.checked ? [...prev, rowId] : prev.filter((id) => id !== rowId))}
                        className="mt-1 h-5 w-5 accent-cyan-400"
                        data-testid={`debt-mobile-row-checkbox-${rowId}`}
                      />
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-bold text-slate-50" data-testid={`debt-mobile-row-name-${rowId}`}>{row.name}</span>
                        <span className="mt-1 inline-flex rounded-full border border-white/10 bg-white/10 px-2 py-0.5 text-[11px] text-slate-300" data-testid={`debt-mobile-row-type-${rowId}`}>
                          {row.entityType === 'supplier' ? 'مورد' : 'عميل'}
                        </span>
                      </span>
                    </label>
                    <div className="text-left shrink-0">
                      <p className="text-[11px] text-slate-400">آجل</p>
                      <p className="text-lg font-extrabold text-rose-200" data-testid={`debt-mobile-row-ajel-${rowId}`}>{fmt(row.ajelBalance)}</p>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-xl bg-white/5 p-2" data-testid={`debt-mobile-row-debit-${rowId}`}>
                      <span className="block text-slate-400">مدين</span>
                      <b className="text-slate-100">{fmt(row.debitBalance)}</b>
                    </div>
                    <div className="rounded-xl bg-white/5 p-2" data-testid={`debt-mobile-row-credit-${rowId}`}>
                      <span className="block text-slate-400">دائن</span>
                      <b className="text-slate-100">{fmt(row.creditBalance)}</b>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center gap-2 text-xs text-slate-400" data-testid={`debt-mobile-row-phone-${rowId}`}>
                    <span className="ltr text-left">{row.phone || 'لا يوجد رقم'}</span>
                  </div>

                  <div className="mt-3 grid grid-cols-1 gap-2">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={manualAmounts[rowId] ?? ''}
                      onChange={(e) => setManualAmounts((prev) => ({ ...prev, [rowId]: e.target.value }))}
                      placeholder={`المبلغ: ${Number(row.ajelBalance || 0).toFixed(2)}`}
                      className="h-11 w-full rounded-xl border border-white/15 bg-white/10 px-3 text-sm text-white placeholder:text-slate-400 focus:border-cyan-300 focus:outline-none"
                      data-testid={`debt-mobile-row-manual-amount-${rowId}`}
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        className="h-11 rounded-xl border border-cyan-400/40 bg-cyan-500/15 px-3 text-sm font-semibold text-cyan-100 active:scale-[0.98] transition-transform disabled:opacity-60"
                        onClick={() => createSettlementOrder(row)}
                        disabled={savingRowId === rowId}
                        data-testid={`debt-mobile-row-settlement-order-${rowId}`}
                      >
                        <span className="inline-flex items-center justify-center gap-1"><WalletCards size={15} /> {savingRowId === rowId ? 'جارٍ...' : 'سداد'}</span>
                      </button>
                      <button
                        type="button"
                        className="h-11 rounded-xl border border-emerald-400/40 bg-emerald-500/15 px-3 text-sm font-semibold text-emerald-100 active:scale-[0.98] transition-transform"
                        onClick={() => openPreviewForRows([row])}
                        data-testid={`debt-mobile-row-preview-${rowId}`}
                      >
                        <span className="inline-flex items-center justify-center gap-1"><Send size={15} /> واتساب</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="hidden md:block overflow-auto">
            <table className="w-full text-sm" data-testid="debt-followup-table">
              <thead>
                <tr className="text-slate-300 border-b border-white/10">
                  <th className="p-2 text-right">تحديد</th>
                  <th className="p-2 text-right">الجهة</th>
                  <th className="p-2 text-right">النوع</th>
                  <th className="p-2 text-right">الهاتف</th>
                  <th className="p-2 text-right">مدين</th>
                  <th className="p-2 text-right">دائن</th>
                  <th className="p-2 text-right">آجل</th>
                  <th className="p-2 text-right">إجراء</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((row) => {
                  const rowId = `${row.entityType}-${row.id}`;
                  return (
                    <tr key={rowId} className="border-b border-white/5 text-slate-100" data-testid={`debt-row-${rowId}`}>
                      <td className="p-2">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(rowId)}
                          onChange={(e) => setSelectedIds((prev) => e.target.checked ? [...prev, rowId] : prev.filter((id) => id !== rowId))}
                          data-testid={`debt-row-checkbox-${rowId}`}
                        />
                      </td>
                      <td className="p-2 font-semibold" data-testid={`debt-row-name-${rowId}`}>{row.name}</td>
                      <td className="p-2" data-testid={`debt-row-type-${rowId}`}>{row.entityType === 'supplier' ? 'مورد' : 'عميل'}</td>
                      <td className="p-2 ltr text-left" data-testid={`debt-row-phone-${rowId}`}>{row.phone || '-'}</td>
                      <td className="p-2" data-testid={`debt-row-debit-${rowId}`}>{fmt(row.debitBalance)}</td>
                      <td className="p-2" data-testid={`debt-row-credit-${rowId}`}>{fmt(row.creditBalance)}</td>
                      <td className="p-2 text-rose-200 font-bold" data-testid={`debt-row-ajel-${rowId}`}>{fmt(row.ajelBalance)}</td>
                      <td className="p-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={manualAmounts[rowId] ?? ''}
                            onChange={(e) => setManualAmounts((prev) => ({ ...prev, [rowId]: e.target.value }))}
                            placeholder={String(Number(row.ajelBalance || 0).toFixed(2))}
                            className="h-10 w-32 rounded-xl border border-white/20 bg-white/10 px-3 py-1 text-xs text-white focus:border-cyan-300 focus:outline-none"
                            data-testid={`debt-row-manual-amount-${rowId}`}
                          />
                          <button
                            type="button"
                            className="h-10 rounded-xl border border-cyan-400/40 bg-cyan-500/15 px-3 text-xs font-semibold text-cyan-100 active:scale-[0.98] transition-transform disabled:opacity-60"
                            onClick={() => createSettlementOrder(row)}
                            disabled={savingRowId === rowId}
                            data-testid={`debt-row-settlement-order-${rowId}`}
                          >
                            {savingRowId === rowId ? 'جارٍ...' : 'أمر سداد'}
                          </button>
                          <button
                            type="button"
                            className="h-10 rounded-xl border border-emerald-400/40 bg-emerald-500/15 px-3 text-xs font-semibold text-emerald-100 active:scale-[0.98] transition-transform"
                            onClick={() => openPreviewForRows([row])}
                            data-testid={`debt-row-preview-${rowId}`}
                          >
                            معاينة واتساب
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          </>
        )}
      </div>

      <DebtWhatsAppComposerDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        drafts={drafts}
        onUpdateDraft={updateDraftMessage}
        onSendCurrent={sendCurrent}
        onSendAll={sendAll}
      />

      {/* نافذة تأكيد السداد لمتابعة الذمم */}
      <ConfirmPaymentDialog
        open={!!confirmPayRow}
        onOpenChange={(v) => { if (!v) setConfirmPayRow(null); }}
        loading={confirmPayLoading}
        remainingBalance={confirmPayRow?.defaultAmount || 0}
        supplierId={confirmPayRow?.entityType === 'supplier' ? confirmPayRow?.id : null}
        allowSupplierBalance={confirmPayRow?.entityType === 'supplier'}
        onConfirm={async ({ paymentLines, date }) => {
          if (!confirmPayRow) return;
          setConfirmPayLoading(true);
          await createSettlementOrder(confirmPayRow, paymentLines, date);
        }}
      />
    </div>
  );
}
