import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api/suppliers-ext';

export default function SupplierSettlementDialog({ open, onOpenChange, supplier, workshopId = 'finmodule-sync' }) {
  const [transactions, setTransactions] = useState([]);
  const [selected, setSelected]         = useState(new Set());
  const [loading, setLoading]           = useState(false);
  const [saving, setSaving]             = useState(false);
  const [notes, setNotes]               = useState('');
  const [settlements, setSettlements]   = useState([]);
  const [tab, setTab]                   = useState('new'); // 'new' | 'history'

  useEffect(() => {
    if (!open || !supplier) return;
    setSelected(new Set()); setNotes('');
    loadData();
  }, [open, supplier]);

  const loadData = async () => {
    if (!supplier) return;
    setLoading(true);
    try {
      const [txR, sR] = await Promise.all([
        axios.get(`${API}/${supplier.id}/transactions`, {
          params: { workshop_id: workshopId, supplier_name: supplier.name }
        }),
        axios.get(`${API}/${supplier.id}/settlements`),
      ]);
      setTransactions(txR.data?.data?.transactions || []);
      setSettlements(sR.data?.data || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const toggleAll = (checked) => {
    if (checked) setSelected(new Set(transactions.map(t => t.je_id)));
    else setSelected(new Set());
  };

  const toggle = (jeId) => {
    const s = new Set(selected);
    if (s.has(jeId)) s.delete(jeId); else s.add(jeId);
    setSelected(s);
  };

  const selectedTxns = transactions.filter(t => selected.has(t.je_id));
  const totalDebit   = selectedTxns.reduce((s, t) => s + t.debit, 0);
  const totalCredit  = selectedTxns.reduce((s, t) => s + t.credit, 0);
  const net          = totalCredit - totalDebit;

  const execute = async () => {
    if (!selected.size) return;
    setSaving(true);
    try {
      await axios.post(`${API}/${supplier.id}/settlements`, {
        supplier_name: supplier.name,
        workshop_id: workshopId,
        selected_ids: [...selected],
        notes,
      });
      await loadData();
      setSelected(new Set()); setNotes('');
      setTab('history');
      // 🔄 إشعار باقي الصفحات بالتحديث
      try {
        window.dispatchEvent(new CustomEvent('finance:updated', {
          detail: { source: 'supplier_settlement', supplierId: supplier.id }
        }));
      } catch (evtErr) { console.warn('finance:updated dispatch failed', evtErr); }
    } catch (e) {
      alert(e?.response?.data?.detail || 'فشل التسوية');
    } finally { setSaving(false); }
  };

  const deleteSett = async (sid) => {
    if (!window.confirm('حذف هذه التسوية؟')) return;
    try {
      await axios.delete(`${API}/${supplier.id}/settlements/${sid}`);
      await loadData();
    } catch (e) { alert('فشل الحذف'); }
  };

  const fmt = (n) => Number(n || 0).toLocaleString('ar-SA', { minimumFractionDigits: 2 });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent dir="rtl" className="max-w-3xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>تسوية حساب — {supplier?.name}</DialogTitle>
        </DialogHeader>

        {/* تبويبات */}
        <div className="flex gap-2 border-b border-slate-700 pb-2">
          {[['new','تسوية جديدة'],['history','سجل التسويات']].map(([k,l]) => (
            <button key={k} onClick={() => setTab(k)}
              className={`px-4 py-1.5 rounded-t text-sm font-medium transition-colors ${
                tab===k ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white'}`}
              data-testid={`settlement-tab-${k}`}>{l}
              {k==='history' && settlements.length > 0 && (
                <span className="mr-1.5 rounded-full bg-sky-500/30 px-1.5 text-xs">{settlements.length}</span>
              )}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-8 text-center text-slate-400">جارٍ التحميل...</div>
          ) : tab === 'new' ? (
            <>
              {/* جدول الحركات */}
              <table className="w-full text-xs" data-testid="settlement-transactions-table">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400">
                    <th className="py-2 pr-2 text-right w-8">
                      <input type="checkbox" onChange={e => toggleAll(e.target.checked)}
                        checked={selected.size === transactions.length && transactions.length > 0}
                        data-testid="settlement-select-all" />
                    </th>
                    <th className="py-2 text-right">التاريخ</th>
                    <th className="py-2 text-right">الوصف</th>
                    <th className="py-2 text-right">النوع</th>
                    <th className="py-2 text-left">مدين</th>
                    <th className="py-2 text-left">دائن</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.length === 0 ? (
                    <tr><td colSpan="6" className="py-8 text-center text-slate-500">لا توجد حركات مسجلة</td></tr>
                  ) : transactions.map((t, i) => (
                    <tr key={t.id} className={`border-b border-slate-800 hover:bg-white/4 ${t.settled ? 'opacity-40' : ''}`}
                      data-testid={`settlement-row-${i}`}>
                      <td className="py-1.5 pr-2">
                        <input type="checkbox" checked={selected.has(t.je_id)}
                          onChange={() => toggle(t.je_id)} disabled={t.settled}
                          data-testid={`settlement-check-${i}`} />
                      </td>
                      <td className="py-1.5 text-slate-300">{t.date}</td>
                      <td className="py-1.5 text-slate-200">{t.description?.slice(0, 45)}</td>
                      <td className="py-1.5">
                        <span className={`rounded px-1.5 py-0.5 text-[10px] ${
                          t.type==='credit' ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>
                          {t.type==='credit' ? 'دائن (مستحق)' : 'مدين (مدفوع)'}
                        </span>
                        {t.settled && <span className="mr-1 text-[10px] text-slate-500">مسوّى</span>}
                      </td>
                      <td className="py-1.5 text-left text-red-300 tabular-nums">{t.debit > 0 ? fmt(t.debit) : '—'}</td>
                      <td className="py-1.5 text-left text-green-300 tabular-nums">{t.credit > 0 ? fmt(t.credit) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* ملخص التسوية */}
              {selected.size > 0 && (
                <div className="mt-3 rounded-xl border border-sky-500/30 bg-sky-500/8 p-3 space-y-2"
                  data-testid="settlement-summary">
                  <div className="text-xs font-bold text-sky-300">ملخص التسوية ({selected.size} حركة)</div>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="rounded-lg bg-red-500/10 p-2">
                      <div className="text-slate-400">إجمالي المدين</div>
                      <div className="text-red-300 font-bold tabular-nums">{fmt(totalDebit)} ر.س</div>
                    </div>
                    <div className="rounded-lg bg-green-500/10 p-2">
                      <div className="text-slate-400">إجمالي الدائن</div>
                      <div className="text-green-300 font-bold tabular-nums">{fmt(totalCredit)} ر.س</div>
                    </div>
                    <div className={`rounded-lg p-2 ${net >= 0 ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
                      <div className="text-slate-400">صافي التسوية</div>
                      <div className={`font-bold tabular-nums ${net >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                        {fmt(Math.abs(net))} ر.س {net >= 0 ? '(دائن)' : '(مدين)'}
                      </div>
                    </div>
                  </div>
                  <input value={notes} onChange={e => setNotes(e.target.value)}
                    placeholder="ملاحظات (اختياري)"
                    className="w-full rounded-lg border border-slate-600 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-100"
                    data-testid="settlement-notes" />
                </div>
              )}
            </>
          ) : (
            /* سجل التسويات */
            <div className="space-y-2 p-1">
              {settlements.length === 0 ? (
                <div className="py-8 text-center text-slate-500 text-sm">لا توجد تسويات مسجلة</div>
              ) : settlements.map((s, i) => (
                <div key={s.id} className="rounded-xl border border-slate-700 p-3 space-y-1"
                  data-testid={`settlement-history-${i}`}>
                  <div className="flex justify-between items-center">
                    <div className="text-xs font-bold text-slate-200">
                      تسوية {s.date} — {s.lines?.length || 0} حركة
                    </div>
                    <div className="flex gap-2">
                      <a href={`${API}/settlements/${s.id}/pdf`} target="_blank" rel="noreferrer"
                        className="text-[10px] text-sky-400 hover:underline">PDF</a>
                      <button onClick={() => deleteSett(s.id)}
                        className="text-[10px] text-red-400 hover:underline">حذف</button>
                    </div>
                  </div>
                  <div className="flex gap-4 text-xs">
                    <span className="text-red-300">مدين: {fmt(s.total_debit)}</span>
                    <span className="text-green-300">دائن: {fmt(s.total_credit)}</span>
                    <span className={s.net_amount >= 0 ? 'text-green-300' : 'text-red-300'}>
                      صافي: {fmt(Math.abs(s.net_amount))} {s.net_amount >= 0 ? '(دائن)' : '(مدين)'}
                    </span>
                  </div>
                  {s.notes && <div className="text-[10px] text-slate-500">{s.notes}</div>}
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter className="pt-2">
          {tab === 'new' && (
            <Button onClick={execute} disabled={!selected.size || saving}
              data-testid="settlement-execute-btn"
              className="bg-sky-600 hover:bg-sky-700 text-white">
              {saving ? 'جارٍ التنفيذ...' : `تنفيذ التسوية (${selected.size})`}
            </Button>
          )}
          <Button variant="secondary" onClick={() => onOpenChange(false)}>إغلاق</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
