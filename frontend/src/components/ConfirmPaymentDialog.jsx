import React, { useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;
const todayISO = () => new Date().toISOString().split('T')[0];

const BASE_METHODS = [
  { value: 'bank', label: 'بنك / تحويل', sub: '004', color: 'border-sky-500/60 bg-sky-500/10 text-sky-200' },
  { value: 'cash', label: 'نقد',          sub: '003', color: 'border-emerald-500/60 bg-emerald-500/10 text-emerald-200' },
  { value: 'pos',  label: 'نقاط بيع',     sub: '006', color: 'border-violet-500/60 bg-violet-500/10 text-violet-200' },
];

const SUPPLIER_BALANCE_METHOD = {
  value: 'supplier_balance',
  label: 'رصيد مورد',
  sub: '2101',
  color: 'border-amber-500/60 bg-amber-500/10 text-amber-200',
};

const emptyLine = () => ({ id: Date.now() + Math.random(), method: 'bank', amountStr: '' });

const ConfirmPaymentDialog = ({
  open, onOpenChange, onConfirm, loading = false, remainingBalance = 0,
  // خيارات إضافية
  supplierId = null,   // إذا كان السداد من رصيد مورد
  vehicleId  = null,   // إذا كان مرتبطاً بمركبة
  showArchiveOption = false,  // هل يظهر خيار الأرشفة
  allowSupplierBalance = true,
  allowDiscount = true, // عرض حقل الخصم
}) => {
  const [lines, setLines]             = useState([emptyLine()]);
  const [dateStr, setDateStr]         = useState(todayISO());
  const [archiveVehicle, setArchiveVehicle] = useState(false);
  const [discountStr, setDiscountStr] = useState('');
  const [supplierBal, setSupplierBal] = useState(null); // رصيد المورد المُجلَب
  const [balLoading, setBalLoading]   = useState(false);
  const [selectedSupplierId, setSelectedSupplierId] = useState(supplierId || '');
  const [suppliers, setSuppliers] = useState([]);
  const [suppliersLoading, setSuppliersLoading] = useState(false);
  const methods = useMemo(() => {
    const canUseSupplierBalance = allowSupplierBalance;
    return canUseSupplierBalance
      ? [...BASE_METHODS, SUPPLIER_BALANCE_METHOD]
      : BASE_METHODS;
  }, [allowSupplierBalance]);

  const effectiveSupplierId = supplierId || selectedSupplierId || '';

  useEffect(() => {
    if (!open || !allowSupplierBalance || supplierId) return;
    let mounted = true;
    const loadSuppliers = async () => {
      setSuppliersLoading(true);
      try {
        const r = await axios.get(`${API}/api/suppliers`);
        const rows = r?.data?.data || r?.data || [];
        if (mounted) {
          setSuppliers(Array.isArray(rows) ? rows : []);
        }
      } catch {
        if (mounted) setSuppliers([]);
      } finally {
        if (mounted) setSuppliersLoading(false);
      }
    };
    loadSuppliers();
    return () => {
      mounted = false;
    };
  }, [open, allowSupplierBalance, supplierId]);

  /* reset when dialog opens */
  const handleOpenChange = (v) => {
    if (v) {
      setLines([emptyLine()]);
      setDateStr(todayISO());
      setArchiveVehicle(false);
      setSupplierBal(null);
      setSelectedSupplierId(supplierId || '');
      setDiscountStr('');
    }
    onOpenChange(v);
  };

  // عند اختيار "رصيد مورد" → جلب رصيد المورد
  const handleMethodChange = async (lineId, method) => {
    updateLine(lineId, 'method', method);
    const targetSupplierId = supplierId || selectedSupplierId;
    if (method === 'supplier_balance' && targetSupplierId && !supplierBal) {
      setBalLoading(true);
      try {
        const r = await axios.get(`${API}/api/suppliers/${targetSupplierId}`);
        const sup = r.data?.data || r.data || {};
        setSupplierBal({
          name:   sup.name || 'المورد',
          credit: Number(sup.credit_balance || sup.creditBalance || 0),
        });
      } catch {
        setSupplierBal({ name: 'المورد', credit: 0 });
      } finally {
        setBalLoading(false);
      }
    }
  };

  const updateLine = (id, field, value) => {
    setLines(prev => prev.map(l => l.id === id ? { ...l, [field]: value } : l));
  };

  const addLine = () => setLines(prev => [...prev, emptyLine()]);
  const removeLine = (id) => setLines(prev => prev.length > 1 ? prev.filter(l => l.id !== id) : prev);

  /* إجمالي ما أُدخل */
  const enteredTotal = lines.reduce((s, l) => {
    const n = parseFloat(l.amountStr);
    return s + (Number.isFinite(n) && n > 0 ? n : 0);
  }, 0);

  const discountValue = (() => {
    const n = parseFloat(discountStr);
    return Number.isFinite(n) && n > 0 ? n : 0;
  })();

  const totalCovered = enteredTotal + discountValue;

  const hasError = lines.some(l => {
    if (!l.amountStr.trim()) return false;
    const n = parseFloat(l.amountStr);
    return !Number.isFinite(n) || n <= 0;
  }) || (discountValue > remainingBalance + 0.01);

  const handleSubmit = async () => {
    if (hasError) return;

    const paymentLines = lines.map(l => {
      const n = parseFloat(l.amountStr);
      return { method: l.method, amount: Number.isFinite(n) && n > 0 ? n : null };
    });

    // التحقق من رصيد المورد عند اختيار "رصيد مورد"
    const usesSupplierBalance = paymentLines.some(pl => pl.method === 'supplier_balance');
    if (usesSupplierBalance && !effectiveSupplierId) {
      alert('يرجى اختيار مورد قبل السداد عبر رصيد المورد.');
      return;
    }

    if (usesSupplierBalance && supplierBal !== null) {
      const needed = paymentLines.filter(pl => pl.method === 'supplier_balance')
        .reduce((s, pl) => s + (pl.amount || remainingBalance), 0);
      if (needed > supplierBal.credit) {
        alert(`رصيد المورد (${supplierBal.credit.toLocaleString('ar-SA')} ر.س) غير كافٍ للسداد.`);
        return;
      }
    }

    onConfirm({
      paymentLines,
      date: dateStr || todayISO(),
      archiveVehicle,
      viaSupplierBalance: usesSupplierBalance,
      supplierId: effectiveSupplierId || null,
      discount: discountValue,
    });
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent dir="rtl" className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>تأكيد السداد</DialogTitle>
          {remainingBalance > 0 && (
            <p className="text-sm text-amber-300 mt-1">
              الرصيد المتبقي: <span className="font-bold tabular-nums">{remainingBalance.toLocaleString('ar-SA', { minimumFractionDigits: 2 })}</span> ر.س
            </p>
          )}
        </DialogHeader>

        <div className="space-y-3 mt-2">
          {/* سطور الوسائل */}
          {lines.map((line, idx) => {
            const n = parseFloat(line.amountStr);
            const isValid = !line.amountStr.trim() || (Number.isFinite(n) && n > 0);
            const isSupBal = line.method === 'supplier_balance';
            return (
              <div key={line.id} className="rounded-xl border border-white/10 bg-white/4 p-3 space-y-2" data-testid={`pay-line-${idx}`}>
                {/* وسيلة الدفع — 2×2 */}
                <div className="grid grid-cols-4 gap-1.5">
                  {methods.map(opt => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => handleMethodChange(line.id, opt.value)}
                      className={`rounded-lg border px-1 py-2 text-center text-[10px] transition-all ${
                        line.method === opt.value
                          ? opt.color + ' border-opacity-80 font-semibold'
                          : 'border-slate-600 bg-slate-800/40 text-slate-400 hover:border-slate-500'
                      }`}
                      data-testid={`pay-line-${idx}-method-${opt.value}`}
                    >
                      <div className="font-medium truncate">{opt.label}</div>
                      <div className="text-[9px] opacity-60">{opt.sub}</div>
                    </button>
                  ))}
                </div>

                {/* معلومات رصيد المورد */}
                {isSupBal && (
                  <div className="space-y-2 rounded-lg bg-amber-500/8 border border-amber-500/25 px-3 py-2 text-xs">
                    {!supplierId && (
                      <select
                        value={selectedSupplierId}
                        onChange={async (e) => {
                          const next = e.target.value;
                          setSelectedSupplierId(next);
                          setSupplierBal(null);
                          if (!next) return;
                          setBalLoading(true);
                          try {
                            const r = await axios.get(`${API}/api/suppliers/${next}`);
                            const sup = r.data?.data || r.data || {};
                            setSupplierBal({
                              name: sup.name || 'المورد',
                              credit: Number(sup.credit_balance || sup.creditBalance || 0),
                            });
                          } catch {
                            setSupplierBal({ name: 'المورد', credit: 0 });
                          } finally {
                            setBalLoading(false);
                          }
                        }}
                        className="w-full rounded-lg border border-amber-500/30 bg-slate-900/60 px-2 py-1.5 text-xs text-slate-100"
                        data-testid={`pay-line-${idx}-supplier-select`}
                        disabled={suppliersLoading}
                      >
                        <option value="">{suppliersLoading ? 'جارٍ تحميل الموردين...' : 'اختر المورد'}</option>
                        {suppliers.map((sup) => (
                          <option key={sup.id} value={sup.id}>{sup.name}</option>
                        ))}
                      </select>
                    )}
                    {balLoading ? (
                      <span className="text-amber-400 animate-pulse">جارٍ جلب رصيد المورد...</span>
                    ) : supplierBal ? (
                      <span className="text-amber-300">
                        رصيد <strong>{supplierBal.name}</strong>: {supplierBal.credit.toLocaleString('ar-SA')} ر.س
                      </span>
                    ) : (
                      <span className="text-slate-400">اختر مورداً لعرض رصيده</span>
                    )}
                  </div>
                )}

                {/* المبلغ */}
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={line.amountStr}
                    onChange={e => updateLine(line.id, 'amountStr', e.target.value)}
                    placeholder={
                      idx === 0 && lines.length === 1
                        ? `${remainingBalance > 0 ? remainingBalance.toLocaleString('ar-SA') : 'المبلغ'} ر.س — فارغ = كامل الرصيد`
                        : 'المبلغ'
                    }
                    className={`flex-1 rounded-lg border px-3 py-2 text-sm bg-slate-900/60 text-slate-100 outline-none focus:ring-1 ${
                      isValid ? 'border-slate-600 focus:ring-sky-500' : 'border-red-500 focus:ring-red-500'
                    }`}
                    data-testid={`pay-line-${idx}-amount`}
                  />
                  {lines.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeLine(line.id)}
                      className="p-2 rounded-lg text-red-400 hover:bg-red-500/10 border border-red-500/30 text-xs"
                      data-testid={`pay-line-${idx}-remove`}
                    >✕</button>
                  )}
                </div>
                {!isValid && <p className="text-xs text-red-400">مبلغ غير صحيح</p>}
              </div>
            );
          })}

          <button
            type="button"
            onClick={addLine}
            className="w-full rounded-xl border border-dashed border-slate-500 py-2 text-xs text-slate-400 hover:border-sky-500 hover:text-sky-300 transition-all"
            data-testid="pay-add-method-btn"
          >
            + إضافة وسيلة دفع أخرى
          </button>

          {enteredTotal > 0 && (
            <div className="flex justify-between text-sm rounded-lg bg-white/5 px-3 py-2">
              <span className="text-slate-400">إجمالي المُدخل</span>
              <span className="font-bold tabular-nums text-sky-300">
                {enteredTotal.toLocaleString('ar-SA', { minimumFractionDigits: 2 })} ر.س
              </span>
            </div>
          )}

          {/* حقل الخصم — يقلل من رصيد العميل بدون أن يكون دفعة نقدية */}
          {allowDiscount && (
            <div className="space-y-1.5">
              <label className="text-xs text-slate-400 flex items-center justify-between">
                <span>الخصم (اختياري)</span>
                {discountValue > 0 && (
                  <span className="text-[10px] text-emerald-300">
                    سيُخصم من رصيد العميل
                  </span>
                )}
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={discountStr}
                onChange={e => setDiscountStr(e.target.value)}
                placeholder="0.00"
                className={`w-full rounded-lg border px-3 py-2 text-sm bg-slate-900/60 text-slate-100 outline-none focus:ring-1 ${
                  discountValue > remainingBalance + 0.01
                    ? 'border-red-500 focus:ring-red-500'
                    : 'border-emerald-500/40 focus:ring-emerald-500'
                }`}
                data-testid="confirm-payment-dialog-discount"
              />
              {discountValue > remainingBalance + 0.01 && (
                <p className="text-xs text-red-400">
                  الخصم أكبر من الرصيد المتبقي ({remainingBalance.toLocaleString('ar-SA')} ر.س)
                </p>
              )}
              {totalCovered > 0 && discountValue > 0 && (
                <div className="flex justify-between text-xs rounded-lg bg-emerald-500/8 border border-emerald-500/20 px-2 py-1.5 mt-1">
                  <span className="text-emerald-300">المسدَّد + الخصم</span>
                  <span className="font-bold tabular-nums text-emerald-200">
                    {totalCovered.toLocaleString('ar-SA', { minimumFractionDigits: 2 })} ر.س
                  </span>
                </div>
              )}
            </div>
          )}

          {/* خيار أرشفة المركبة (يظهر فقط عند وجود vehicleId) */}
          {showArchiveOption && vehicleId && (
            <label className="flex items-center gap-3 rounded-xl border border-slate-700 bg-white/3 px-3 py-2.5 cursor-pointer hover:bg-white/5 transition-colors"
              data-testid="archive-vehicle-option">
              <input
                type="checkbox"
                checked={archiveVehicle}
                onChange={e => setArchiveVehicle(e.target.checked)}
                className="w-4 h-4 rounded border-slate-600"
              />
              <div>
                <div className="text-xs font-semibold text-slate-200">إغلاق ملف المركبة وأرشفته</div>
                <div className="text-[10px] text-slate-500 mt-0.5">ينقل الملف لقسم الأرشيف بعد تأكيد السداد</div>
              </div>
            </label>
          )}

          <div className="space-y-1">
            <label className="text-xs text-slate-400">تاريخ السداد</label>
            <input
              type="date"
              value={dateStr}
              onChange={e => setDateStr(e.target.value)}
              className="w-full rounded-lg border border-slate-600 bg-slate-900/60 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-1 focus:ring-sky-500"
              data-testid="confirm-payment-dialog-date"
            />
          </div>
        </div>

        <DialogFooter className="gap-2 mt-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={loading} data-testid="confirm-payment-dialog-cancel">
            إلغاء
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={loading || hasError}
            data-testid="confirm-payment-dialog-submit"
          >
            {loading ? 'جارٍ التنفيذ...' : 'تأكيد السداد'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ConfirmPaymentDialog;
