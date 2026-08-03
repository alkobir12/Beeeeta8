import React, { useEffect, useMemo, useState } from 'react';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';

export const PartsTransactionModal = ({
  open,
  onOpenChange,
  transactionType,
  saleMode,
  directAmount,
  directDescription,
  transactionVehicleId,
  selectedPartnerId,
  selectedAccountId,
  loadingVehicles,
  loadingPartners,
  loadingAccounts,
  loadingModalParts,
  vehicleOptions,
  customers,
  suppliers,
  accountOptions,
  partOptions,
  transactionItems,
  transactionTotal,
  setTransactionType,
  setSaleMode,
  setDirectAmount,
  setDirectDescription,
  setTransactionVehicleId,
  setSelectedPartnerId,
  setSelectedAccountId,
  updateTransactionItem,
  removeTransactionItem,
  addTransactionItem,
  submitTransaction,
  loadVehicles,
  loadAccounts,
  loadCustomers,
  loadSuppliers,
  loadModalParts,
}) => {
  const [activeTab, setActiveTab] = useState('operation');

  useEffect(() => {
    if (open) {
      setActiveTab('operation');
    }
  }, [open]);

  const isDirect = transactionType === 'direct';
  const partnerOptions = transactionType === 'sale' ? customers : suppliers;

  const canMoveToPartner = useMemo(() => {
    if (!isDirect) return true;
    return Number(directAmount || 0) > 0;
  }, [isDirect, directAmount]);

  const canMoveToItems = useMemo(() => {
    return Boolean(selectedAccountId);
  }, [selectedAccountId]);

  const nextTab = () => {
    if (activeTab === 'operation') {
      if (!canMoveToPartner) return;
      setActiveTab('partner');
      return;
    }
    if (activeTab === 'partner') {
      if (!canMoveToItems) return;
      setActiveTab('items');
    }
  };

  const prevTab = () => {
    if (activeTab === 'items') {
      setActiveTab('partner');
      return;
    }
    if (activeTab === 'partner') {
      setActiveTab('operation');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="liquid-pos w-[100vw] h-[100dvh] sm:w-auto sm:h-auto sm:max-h-[92vh] max-w-5xl overflow-y-auto border border-cyan-300/20 bg-slate-950/95 px-3 sm:px-6" style={{ WebkitOverflowScrolling: 'touch' }}>
        <style>{`
          .liquid-pos {
            position: fixed !important;
            overflow-x: hidden;
            background: radial-gradient(1200px 420px at 10% -10%, rgba(94,184,196,.22), transparent 60%), radial-gradient(900px 360px at 95% 5%, rgba(147,51,234,.18), transparent 60%), rgba(2,6,23,.95);
          }
          .liquid-pos::before, .liquid-pos::after {
            content: '';
            position: absolute;
            border-radius: 9999px;
            filter: blur(40px);
            pointer-events: none;
            animation: liquidDrift 12s ease-in-out infinite alternate;
            opacity: .35;
            z-index: 0;
          }
          .liquid-pos::before {
            width: 180px;
            height: 180px;
            top: -40px;
            right: -40px;
            background: rgba(56,189,248,.4);
          }
          .liquid-pos::after {
            width: 220px;
            height: 220px;
            bottom: -90px;
            left: -70px;
            background: rgba(168,85,247,.4);
            animation-delay: -4s;
          }
          @keyframes liquidDrift {
            from { transform: translate3d(0,0,0) scale(1); }
            to { transform: translate3d(20px,24px,0) scale(1.08); }
          }
          .liquid-pos [data-slot="dialog-header"],
          .liquid-pos [data-testid="transaction-modal-content"] {
            position: relative;
            z-index: 1;
          }
          .liquid-pos .apple-input {
            min-height: 46px;
            font-size: 15px;
            border-radius: 14px;
            border-color: rgba(255,255,255,.16);
            background: rgba(255,255,255,.07);
          }
          .liquid-pos .apple-input:focus {
            box-shadow: 0 0 0 3px rgba(94,184,196,.18);
            border-color: rgba(94,184,196,.72);
          }
        `}</style>
        <DialogHeader>
          <DialogTitle className="text-xl text-slate-100" data-testid="transaction-modal-title">نقطة البيع والعمليات المباشرة</DialogTitle>
          <DialogDescription data-testid="transaction-modal-description">
            اختر الحساب من دليل الحسابات، وسيتم التوجيه المالي تلقائياً حسب تصنيف الحساب.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4" data-testid="transaction-modal-content">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs text-slate-300">تصميم متجاوب: تبويبات + بطاقات لجميع الأجهزة</div>
            <button
              type="button"
              className="px-3 py-1 rounded-lg bg-white/10 text-sm text-white hover:bg-white/20 transition"
              onClick={() => {
                loadVehicles();
                loadAccounts();
                if (transactionType === 'sale') {
                  loadCustomers();
                } else {
                  loadSuppliers();
                }
              }}
              data-testid="transaction-refresh-data"
            >
              تحديث القوائم
            </button>
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full" data-testid="transaction-pos-tabs">
            <TabsList className="grid grid-cols-3 bg-white/5 border border-white/15 rounded-2xl p-1 h-auto">
              <TabsTrigger value="operation" data-testid="transaction-tab-operation">1) العملية</TabsTrigger>
              <TabsTrigger value="partner" data-testid="transaction-tab-partner">2) الربط</TabsTrigger>
              <TabsTrigger value="items" data-testid="transaction-tab-items">3) السلة</TabsTrigger>
            </TabsList>

            <TabsContent value="operation" className="mt-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-2xl border border-white/15 bg-white/5 p-4 space-y-3 shadow-[inset_0_1px_0_rgba(255,255,255,.14)]" data-testid="transaction-type-card">
                  <div>
                    <label className="block text-sm mb-2" data-testid="transaction-type-label">نوع العملية</label>
                    <select
                      className="apple-input"
                      value={transactionType}
                      onChange={(e) => setTransactionType(e.target.value)}
                      data-testid="transaction-type-select"
                    >
                      <option value="sale">بيع</option>
                      <option value="purchase">شراء</option>
                      <option value="direct">عملية مباشرة</option>
                    </select>
                  </div>

                  {transactionType === 'direct' && (
                    <>
                      <div>
                        <label className="block text-sm mb-2" data-testid="transaction-direct-amount-label">المبلغ</label>
                        <input
                          type="number"
                          className="apple-input"
                          value={directAmount}
                          onChange={(e) => setDirectAmount(e.target.value)}
                          data-testid="transaction-direct-amount-input"
                        />
                      </div>
                      <div>
                        <label className="block text-sm mb-2" data-testid="transaction-direct-description-label">الوصف</label>
                        <input
                          type="text"
                          className="apple-input"
                          value={directDescription}
                          onChange={(e) => setDirectDescription(e.target.value)}
                          placeholder="مثال: مصروف بنزين / رسوم تشغيل"
                          data-testid="transaction-direct-description-input"
                        />
                      </div>
                    </>
                  )}
                </div>

                <div className="rounded-2xl border border-cyan-400/25 bg-cyan-500/10 p-4 space-y-3 shadow-[0_0_25px_rgba(94,184,196,.15)]">
                  <p className="text-sm font-semibold text-cyan-100">خيارات البيع</p>
                  {transactionType === 'sale' ? (
                    <>
                      <div>
                        <label className="block text-sm mb-2" data-testid="transaction-sale-mode-label">نوع البيع</label>
                        <select
                          className="apple-input"
                          value={saleMode}
                          onChange={(e) => setSaleMode(e.target.value)}
                          data-testid="transaction-sale-mode"
                        >
                          <option value="instant">بيع فوري</option>
                          <option value="vehicle">مركبة</option>
                        </select>
                      </div>

                      {saleMode === 'vehicle' && (
                        <div>
                          <label className="block text-sm mb-2" data-testid="transaction-vehicle-label">المركبة المرتبطة</label>
                          <select
                            className="apple-input"
                            value={transactionVehicleId}
                            onChange={(e) => setTransactionVehicleId(e.target.value)}
                            onFocus={loadVehicles}
                            data-testid="transaction-vehicle-select"
                          >
                            <option value="">اختر مركبة</option>
                            {loadingVehicles && <option value="">جارٍ التحميل...</option>}
                            {vehicleOptions.map((vehicle) => (
                              <option key={vehicle.id} value={vehicle.id}>
                                {vehicle.plateNumber || vehicle.license_plate || vehicle.id}
                              </option>
                            ))}
                            {!loadingVehicles && vehicleOptions.length === 0 && (
                              <option value="">لا توجد مركبات</option>
                            )}
                          </select>
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="text-sm text-slate-300">هذا القسم يظهر فقط عند اختيار &quot;بيع&quot;.</p>
                  )}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="partner" className="mt-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-2xl border border-white/15 bg-white/5 p-4 space-y-3 shadow-[inset_0_1px_0_rgba(255,255,255,.12)]" data-testid="transaction-partner-card">
                  {!isDirect && (
                    <div>
                      <label className="block text-sm mb-2" data-testid="transaction-partner-label">{transactionType === 'sale' ? 'العميل' : 'المورد'}</label>
                      <select
                        className="apple-input"
                        value={selectedPartnerId}
                        onChange={(e) => setSelectedPartnerId(e.target.value)}
                        onFocus={() => (transactionType === 'sale' ? loadCustomers() : loadSuppliers())}
                        data-testid="transaction-partner-select"
                      >
                        <option value="">اختر</option>
                        {loadingPartners && <option value="">جارٍ التحميل...</option>}
                        {partnerOptions.map((partner) => (
                          <option key={partner.id} value={partner.id}>{partner.name}</option>
                        ))}
                        {!loadingPartners && partnerOptions.length === 0 && (
                          <option value="">لا توجد بيانات</option>
                        )}
                      </select>
                    </div>
                  )}

                  <div>
                    <label className="block text-sm mb-2" data-testid="transaction-account-label">الحساب المحاسبي</label>
                    <select
                      className="apple-input"
                      value={selectedAccountId}
                      onChange={(e) => setSelectedAccountId(e.target.value)}
                      onFocus={loadAccounts}
                      data-testid="transaction-account-select"
                    >
                      <option value="">اختر الحساب</option>
                      {loadingAccounts && <option value="">جارٍ التحميل...</option>}
                      {accountOptions.map((acc) => (
                        <option key={acc.id || acc.code} value={acc.id || acc.code}>{acc.code} - {acc.name}</option>
                      ))}
                      {!loadingAccounts && accountOptions.length === 0 && (
                        <option value="">لا توجد حسابات</option>
                      )}
                    </select>
                  </div>
                </div>

                <div className="rounded-2xl border border-emerald-400/25 bg-emerald-500/10 p-4 space-y-2 shadow-[0_0_24px_rgba(16,185,129,.12)]" data-testid="transaction-total-wrapper">
                  <p className="text-sm text-emerald-100 font-semibold">ملخص العملية</p>
                  <p className="text-sm text-slate-200">النوع: <span className="font-bold">{transactionType === 'sale' ? 'بيع' : transactionType === 'purchase' ? 'شراء' : 'مباشرة'}</span></p>
                  <p className="text-sm text-slate-200">إجمالي العملية:</p>
                  <p className="text-2xl font-extrabold text-emerald-100" data-testid="transaction-total">{transactionTotal.toLocaleString()} ر.س</p>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="items" className="mt-4">
              {!isDirect && (
                <div className="space-y-3" data-testid="transaction-items-section">
                  {transactionItems.map((item, index) => (
                    <div key={`transaction-item-${index}`} className="rounded-xl border border-white/15 bg-white/5 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,.08)]" data-testid={`transaction-item-row-${index}`}>
                      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
                        <div className="md:col-span-2">
                          <label className="block text-sm mb-2" data-testid={`transaction-item-part-label-${index}`}>القطعة</label>
                          <select
                            className="apple-input"
                            value={item.partId}
                            onChange={(e) => updateTransactionItem(index, 'partId', e.target.value)}
                            onFocus={loadModalParts}
                            data-testid={`transaction-item-part-${index}`}
                          >
                            <option value="">اختر قطعة</option>
                            {loadingModalParts && <option value="">جارٍ التحميل...</option>}
                            {partOptions.map((part) => (
                              <option key={part.id} value={part.id}>{part.name}</option>
                            ))}
                            {!loadingModalParts && partOptions.length === 0 && (
                              <option value="">لا توجد قطع</option>
                            )}
                          </select>
                        </div>
                        <div>
                          <label className="block text-sm mb-2" data-testid={`transaction-item-qty-label-${index}`}>الكمية</label>
                          <input
                            type="number"
                            className="apple-input"
                            value={item.quantity}
                            onChange={(e) => updateTransactionItem(index, 'quantity', Number(e.target.value))}
                            data-testid={`transaction-item-qty-${index}`}
                          />
                        </div>
                        <div>
                          <label className="block text-sm mb-2" data-testid={`transaction-item-price-label-${index}`}>السعر</label>
                          <input
                            type="number"
                            className="apple-input"
                            value={item.price}
                            onChange={(e) => updateTransactionItem(index, 'price', Number(e.target.value))}
                            data-testid={`transaction-item-price-${index}`}
                          />
                        </div>
                        <div>
                          {transactionItems.length > 1 ? (
                            <button
                              className="w-full text-sm text-rose-300 border border-rose-400/30 rounded-lg py-2 hover:bg-rose-500/20"
                              type="button"
                              onClick={() => removeTransactionItem(index)}
                              data-testid={`transaction-item-remove-${index}`}
                            >
                              حذف البند
                            </button>
                          ) : (
                            <div className="text-xs text-slate-500">البند الأساسي</div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {isDirect && (
                <div className="rounded-xl border border-slate-700 bg-slate-900/50 p-4 text-sm text-slate-300" data-testid="transaction-direct-summary">
                  العملية المباشرة لا تتطلب إضافة بنود للسلة.
                </div>
              )}
            </TabsContent>
          </Tabs>

          <div className="sticky bottom-0 z-10 rounded-xl border border-white/15 bg-slate-950/92 backdrop-blur px-3 py-3 flex flex-wrap gap-2 justify-between items-center" data-testid="transaction-footer-actions">
            <div className="flex items-center gap-2">
              {!isDirect && (
                <button
                  type="button"
                  className="px-4 py-2.5 rounded-xl bg-white/10 text-white hover:bg-white/20"
                  onClick={addTransactionItem}
                  data-testid="transaction-add-item"
                >
                  + إضافة قطعة أخرى
                </button>
              )}
              <button
                type="button"
                className="px-4 py-2.5 rounded-xl border border-white/20 text-slate-200"
                onClick={prevTab}
                data-testid="transaction-step-prev"
              >
                السابق
              </button>
              <button
                type="button"
                className="px-4 py-2.5 rounded-xl border border-cyan-300/40 text-cyan-100 disabled:opacity-50"
                onClick={nextTab}
                disabled={(activeTab === 'operation' && !canMoveToPartner) || (activeTab === 'partner' && !canMoveToItems) || activeTab === 'items'}
                data-testid="transaction-step-next"
              >
                التالي
              </button>
            </div>

            <Button onClick={submitTransaction} data-testid="transaction-submit" className="apple-button min-h-11 px-5 rounded-xl text-base">
              {isDirect ? 'حفظ العملية المباشرة' : 'حفظ العملية'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
