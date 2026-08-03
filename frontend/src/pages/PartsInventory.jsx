import React, { useState, useEffect, useMemo, useDeferredValue } from 'react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { partAPI, fileAPI, api, operationsAPI } from '../services/api';
import { resolveBackendBase } from '../utils/backendBase';
import { Plus, Upload, FileSpreadsheet } from 'lucide-react';
import { useToast } from '../hooks/use-toast';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { useTranslation } from 'react-i18next';
import { InventorySmartOverview } from '../components/inventory/InventorySmartOverview';
import { InventoryAlertsRail } from '../components/inventory/InventoryAlertsRail';
import { PartsOcrPanel } from '../components/inventory/PartsOcrPanel';
import { InventoryStatsCards } from '../components/inventory/InventoryStatsCards';
import { InventoryFiltersPanel } from '../components/inventory/InventoryFiltersPanel';
import { PartInventoryGrid } from '../components/inventory/PartInventoryGrid';
import { PartsTransactionModal } from '../components/inventory/PartsTransactionModal';
import {
  OPERATION_TYPE_LABELS,
  PARTNER_TYPE_LABELS,
  SOURCE_LABELS,
  labelFromMap,
  resolveAccountDisplay,
  resolveVehicleDisplay,
} from '../utils/displayLabels';

const RAKAN_ACCOUNT_KEYWORDS = ['راكان', 'rakan'];
const RAKAN_ACCOUNT_CODE_PREFIX = '5000';

const normalizeText = (value) => String(value || '').trim().toLowerCase();

const normalizeAccountCode = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (raw.startsWith('acc-') && /^acc-\d+$/.test(raw)) return raw.replace('acc-', '');
  return raw;
};

const isRakanCode = (value) => normalizeAccountCode(value).startsWith(RAKAN_ACCOUNT_CODE_PREFIX);

const isRakanAccount = (account) => {
  if (isRakanCode(account?.code)) return true;
  const text = [
    account?.name,
    account?.name_ar,
    account?.code,
    account?.category,
  ]
    .map((v) => normalizeText(v))
    .join(' ');
  return RAKAN_ACCOUNT_KEYWORDS.some((k) => text.includes(k));
};

const isRakanBusinessAccount = (account) => {
  const text = [account?.name, account?.code].map((v) => normalizeText(v)).join(' ');
  return isRakanCode(account?.code) || RAKAN_ACCOUNT_KEYWORDS.some((k) => text.includes(k));
};

const formatCurrency = (value) => `${Number(value || 0).toLocaleString('ar-SA')} ر.س`;

const inferOperationTypeByAccount = (accountType, transactionType) => {
  const normalizedType = String(accountType || '').toLowerCase();
  if (normalizedType === 'revenue') return 'sale';
  if (normalizedType === 'expense') {
    if (transactionType === 'purchase') return 'purchase';
    return 'expense';
  }
  if (normalizedType === 'liability' || normalizedType === 'asset') return 'purchase';
  if (normalizedType === 'equity') return 'expense';
  if (transactionType === 'sale') return 'sale';
  return 'purchase';
};

const PartsInventory = () => {
  const apiBase = `${resolveBackendBase()}/api`;
  const { t } = useTranslation();
  const { toast } = useToast();
  const [parts, setParts] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedBrand, setSelectedBrand] = useState('');
  const [stockStatus, setStockStatus] = useState('');
  const [loading, setLoading] = useState(true);
  const [editingPart, setEditingPart] = useState(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [ocrImage, setOcrImage] = useState('');
  const [ocrPreview, setOcrPreview] = useState('');
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrImporting, setOcrImporting] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [ocrError, setOcrError] = useState('');
  const [showTransactionModal, setShowTransactionModal] = useState(false);
  const [transactionType, setTransactionType] = useState('sale');
  const [saleMode, setSaleMode] = useState('instant');
  const [directAmount, setDirectAmount] = useState('');
  const [directDescription, setDirectDescription] = useState('');
  const [transactionVehicleId, setTransactionVehicleId] = useState('');
  const [transactionItems, setTransactionItems] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [selectedPartnerId, setSelectedPartnerId] = useState('');
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [loadingVehicles, setLoadingVehicles] = useState(false);
  const [loadingPartners, setLoadingPartners] = useState(false);
  const [modalParts, setModalParts] = useState([]);
  const [loadingModalParts, setLoadingModalParts] = useState(false);
  const [inventoryDashboard, setInventoryDashboard] = useState(null);
  const [inventoryAlerts, setInventoryAlerts] = useState([]);
  const [loadingInventoryIntelligence, setLoadingInventoryIntelligence] = useState(false);
  const [inventoryViewTab, setInventoryViewTab] = useState('stock');
  const [posOperations, setPosOperations] = useState([]);
  const [loadingPosOperations, setLoadingPosOperations] = useState(false);
  const [missingRakanAccounts, setMissingRakanAccounts] = useState(false);
  const [businessAccounts, setBusinessAccounts] = useState([]);
  const [rakanBusinessAccountId, setRakanBusinessAccountId] = useState('');

  const [formData, setFormData] = useState({
    partNumber: '', name: '', category: '', purchasePrice: '', sellingPrice: '',
    quantity: '', minQuantity: '5', supplier: '', image: '', location: ''
  });
  const partsById = useMemo(() => new Map(parts.map((part) => [part.id, part])), [parts]);

  useEffect(() => { loadParts(); }, []);

  // 🔗 ترابط حي — شراء قطع من شات كاترينا يحدّث المخزون فوراً
  useEffect(() => {
    const handler = () => loadParts();
    window.addEventListener('finance:updated', handler);
    return () => window.removeEventListener('finance:updated', handler);
  }, []);

  useEffect(() => {
    loadAccounts();
    loadBusinessAccounts();
  }, []);

  useEffect(() => {
    loadInventoryIntelligence();
  }, []);

  useEffect(() => {
    if (inventoryViewTab !== 'pos') return;
    loadPosOperations();
  }, [inventoryViewTab]);

  useEffect(() => {
    if (showTransactionModal) {
      if (!modalParts.length) loadModalParts();
      if (!accounts.length) loadAccounts();
      if (!businessAccounts.length) loadBusinessAccounts();
      if (transactionType === 'sale') {
        if (!customers.length) loadCustomers();
      } else if (transactionType === 'purchase') {
        if (!suppliers.length) loadSuppliers();
      } else {
        if (!customers.length) loadCustomers();
        if (!suppliers.length) loadSuppliers();
      }
      if (saleMode === 'vehicle' && !vehicles.length) loadVehicles();
    }
  }, [showTransactionModal, transactionType, saleMode, modalParts.length, accounts.length, businessAccounts.length, customers.length, suppliers.length, vehicles.length]);

  // Define accountOptions early so useEffects can reference it
  const accountOptions = useMemo(() => {
    if (transactionType === 'direct') return accounts;
    const expectedTypes = transactionType === 'sale'
      ? ['revenue']
      : ['expense', 'asset', 'liability'];
    const byType = accounts.filter((acc) => expectedTypes.includes(String(acc.type || '').toLowerCase()));
    return byType.length ? byType : accounts;
  }, [accounts, transactionType]);

  useEffect(() => {
    if (!showTransactionModal) return;
    if (!accountOptions.length) {
      setSelectedAccountId('');
      return;
    }
    if (!selectedAccountId || !accountOptions.some((acc) => (acc.id || acc.code) === selectedAccountId)) {
      setSelectedAccountId(accountOptions[0].id || accountOptions[0].code || '');
    }
  }, [showTransactionModal, accountOptions, selectedAccountId]);

  useEffect(() => {
    if (transactionType !== 'sale') {
      setSaleMode('instant');
      setTransactionVehicleId('');
    }
    setTransactionItems(prev => prev.map(item => {
      if (!item.partId) return item;
      const selected = partsById.get(item.partId);
      if (!selected) return item;
      return {
        ...item,
        price: transactionType === 'sale'
          ? Number(selected.sellingPrice || item.price || 0)
          : Number(selected.purchasePrice || item.price || 0)
      };
    }));
  }, [transactionType, showTransactionModal, partsById]);

  const loadParts = async () => {
    try {
      setLoading(true);
      const response = await partAPI.getAll();
      const list = Array.isArray(response.data) ? response.data : [];
      setParts(list);
    } catch (error) {
      console.error(error);
      setParts([]);
    } finally {
      setLoading(false);
    }
  };

  const loadInventoryIntelligence = async () => {
    try {
      setLoadingInventoryIntelligence(true);
      const [dashboardRes, alertsRes] = await Promise.all([
        api.get('/inventory/dashboard'),
        api.get('/inventory/alerts', { params: { limit: 20 } }),
      ]);
      setInventoryDashboard(dashboardRes.data || null);
      setInventoryAlerts(Array.isArray(alertsRes.data) ? alertsRes.data : []);
    } catch (error) {
      setInventoryDashboard(null);
      setInventoryAlerts([]);
    } finally {
      setLoadingInventoryIntelligence(false);
    }
  };

  const loadPosOperations = async () => {
    try {
      setLoadingPosOperations(true);
      let cachedRows = [];
      try {
        const cached = localStorage.getItem('operationsCache:all');
        const parsed = cached ? JSON.parse(cached) : [];
        cachedRows = Array.isArray(parsed) ? parsed : [];
      } catch (_e) {
        cachedRows = [];
      }

      if (cachedRows.length) {
        const cachedFiltered = cachedRows
          .filter((op) => {
            const source = normalizeText(op?.source);
            return source === 'parts_pos' || source === 'rakan_parts_pos';
          })
          .sort((a, b) => {
            const aTs = new Date(a?.date || a?.createdAt || a?.created_at || 0).getTime();
            const bTs = new Date(b?.date || b?.createdAt || b?.created_at || 0).getTime();
            return bTs - aTs;
          });
        setPosOperations(cachedFiltered);
      }

      const response = await api.get('/operations', { params: { limit: 200 }, timeout: 7000 });
      const rows = Array.isArray(response?.data) ? response.data : [];
      const filtered = rows
        .filter((op) => {
          const source = normalizeText(op?.source);
          return source === 'parts_pos' || source === 'rakan_parts_pos';
        })
        .sort((a, b) => {
          const aTs = new Date(a?.date || a?.createdAt || a?.created_at || 0).getTime();
          const bTs = new Date(b?.date || b?.createdAt || b?.created_at || 0).getTime();
          return bTs - aTs;
        });
      setPosOperations(filtered);
    } catch (_error) {
      setPosOperations([]);
    } finally {
      setLoadingPosOperations(false);
    }
  };

  const handleAlertSelection = (alert) => {
    if (!alert) return;
    if (alert.part_name) {
      setSearchQuery(alert.part_name);
    }
    if (alert.alert_type === 'out_of_stock') {
      setStockStatus('out');
    } else if (alert.alert_type === 'low_stock' || alert.alert_type === 'fast_moving') {
      setStockStatus('low');
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      setUploading(true);
      const response = await fileAPI.upload(file);
      setFormData({ ...formData, image: response.data.url });
      toast({ title: t('common.success'), description: t('messages.success_saved') });
    } catch (error) {
      toast({ title: t('common.error'), description: t('messages.error_occurred'), variant: 'destructive' });
    } finally {
      setUploading(false);
    }
  };

  const handleImportParts = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    try {
      setImporting(true);
      const formData = new FormData();
      formData.append('file', file);
      
      const res = await fetch(`${resolveBackendBase()}/api/import/parts`, {
        method: 'POST',
        body: formData
      });

      const result = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(result?.detail || 'Import failed');
      }

      toast({
        title: t('common.success'),
        description: result.imported_parts !== undefined
          ? `قطع: ${result.imported_parts || 0} | خدمات: ${result.imported_services || 0} | تمت المعالجة: ${result.processed || (result.total || 0)}`
          : `تم الاستيراد: ${result.imported || 0} / تم التحديث: ${result.updated || 0} / تمت المعالجة: ${result.processed || (result.total || 0)}`,
      });
      loadParts();
    } catch (error) {
      toast({ title: t('common.error'), description: t('messages.error_occurred'), variant: 'destructive' });
    } finally {
      setImporting(false);
      e.target.value = ''; // reset input
    }
  };

  const handleOcrFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result?.toString() || '';
      setOcrImage(base64);
      setOcrPreview(base64);
      setOcrResult(null);
      setOcrError('');
    };
    reader.readAsDataURL(file);
  };

  const runOcr = async () => {
    if (!ocrImage) {
      toast({ title: 'تنبيه', description: 'يرجى رفع صورة الفاتورة أولاً', variant: 'destructive' });
      return;
    }
    setOcrLoading(true);
    setOcrError('');
    try {
      const { data } = await api.post('/parts/ocr', { image_base64: ocrImage });
      setOcrResult(data);
    } catch (error) {
      console.error('OCR error:', error);
      const detail = error?.response?.data?.detail;
      setOcrError(detail || 'تعذر قراءة الفاتورة. حاول بصورة أوضح.');
    } finally {
      setOcrLoading(false);
    }
  };

  const importOcrItems = async () => {
    if (!ocrResult?.items?.length) return;
    setOcrImporting(true);
    try {
      let imported = 0;
      for (const [index, item] of ocrResult.items.entries()) {
        const description = item.description || item.name || item.part_number || `بند OCR ${index + 1}`;
        const qty = Number(item.quantity || 1);
        const unitPrice = Number(item.unit_price || (item.total && qty ? item.total / qty : 0));
        const partNumber = item.part_number || `OCR-${Date.now()}-${index + 1}`;
        const existing = parts.find((p) => p.partNumber === partNumber);
        if (existing) {
          await partAPI.update(existing.id, {
            quantity: Number(existing.quantity || 0) + (qty || 1),
            purchasePrice: unitPrice || existing.purchasePrice || 0,
            sellingPrice: unitPrice || existing.sellingPrice || 0,
          });
        } else {
          await partAPI.create({
            partNumber,
            name: description,
            category: 'OCR',
            purchasePrice: unitPrice || 0,
            sellingPrice: unitPrice || 0,
            quantity: qty || 1,
            minQuantity: 1,
            supplier: ocrResult?.vendor || '',
          });
        }
        imported += 1;
      }
      await loadParts();
      await loadInventoryIntelligence();
      toast({
        title: 'تم الاستيراد',
        description: `تم إضافة ${imported} بند للمخزون بنجاح`,
      });
    } catch (error) {
      console.error('Import OCR items error:', error);
      const detail = error?.response?.data?.detail || error?.message;
      toast({ title: 'خطأ', description: detail || 'تعذر استيراد البنود', variant: 'destructive' });
    } finally {
      setOcrImporting(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      ...formData,
      purchasePrice: parseFloat(formData.purchasePrice) || 0,
      sellingPrice: parseFloat(formData.sellingPrice) || 0,
      quantity: parseInt(formData.quantity) || 0,
      minQuantity: parseInt(formData.minQuantity) || 0
    };
    
    try {
      if (editingPart) {
        await partAPI.update(editingPart.id, payload);
        toast({ title: "Success", description: "Success" });
      } else {
        await partAPI.create(payload);
        toast({ title: "Success", description: "Success" });
      }
      setIsDialogOpen(false);
      resetForm();
      loadParts();
      loadInventoryIntelligence();
    } catch (error) {
      toast({ title: "Error", description: "Error", variant: 'destructive' });
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure?")) return;
    try {
      await partAPI.delete(id);
      toast({ title: "Success", description: "Success" });
      loadParts();
      loadInventoryIntelligence();
    } catch (error) {
      toast({ title: "Error", description: "Error", variant: 'destructive' });
    }
  };

  const handleSellPart = async (part) => {
    openTransactionModal('sale', part);
  };

  const handleRestockPart = async (part) => {
    openTransactionModal('purchase', part);
  };

  const handleResetFilters = () => {
    setSearchQuery('');
    setSelectedCategory('');
    setSelectedBrand('');
    setStockStatus('');
  };

  const loadVehicles = async () => {
    setLoadingVehicles(true);
    try {
      const res = await fetch(`${apiBase}/vehicles`);
      const data = await res.json();
      setVehicles(Array.isArray(data) ? data : []);
    } catch (error) {
      setVehicles([]);
    } finally {
      setLoadingVehicles(false);
    }
  };

  const loadCustomers = async () => {
    setLoadingPartners(true);
    try {
      const res = await fetch(`${apiBase}/customers`);
      const data = await res.json();
      setCustomers(Array.isArray(data) ? data : []);
    } catch (error) {
      setCustomers([]);
    } finally {
      setLoadingPartners(false);
    }
  };

  const loadSuppliers = async () => {
    setLoadingPartners(true);
    try {
      const res = await fetch(`${apiBase}/suppliers`);
      const data = await res.json();
      setSuppliers(Array.isArray(data) ? data : []);
    } catch (error) {
      setSuppliers([]);
    } finally {
      setLoadingPartners(false);
    }
  };

  const loadAccounts = async () => {
    setLoadingAccounts(true);
    try {
      const workshopId = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';
      const financeRes = await fetch(`${apiBase}/finance/chart-of-accounts?workshop_id=${workshopId}`);
      const financeData = await financeRes.json().catch(() => ({}));

      let loaded = [];
      if (financeRes.ok && financeData?.success && Array.isArray(financeData.data)) {
        loaded = financeData.data.map((acc) => ({
          id: acc.id || acc.code,
          code: acc.code,
          name: acc.name_ar || acc.name,
          name_ar: acc.name_ar || acc.name,
          type: acc.type,
          category: acc.category,
          parent_id: acc.parent_id || null,
        }));
      } else {
        const res = await fetch(`${apiBase}/accounts-chart`);
        const data = await res.json().catch(() => ({}));
        loaded = Array.isArray(data?.accounts) ? data.accounts : [];
      }

      setAccounts(loaded);

      const hasRakanRevenue = loaded.some((acc) => isRakanAccount(acc) && acc.type === 'revenue');
      const hasRakanExpense = loaded.some((acc) => isRakanAccount(acc) && acc.type === 'expense');
      setMissingRakanAccounts(!(hasRakanRevenue && hasRakanExpense));
    } catch (error) {
      setAccounts([]);
      setMissingRakanAccounts(true);
    } finally {
      setLoadingAccounts(false);
    }
  };

  const loadBusinessAccounts = async () => {
    try {
      const res = await fetch(`${apiBase}/biz-accounts`);
      const data = await res.json().catch(() => ([]));
      const list = Array.isArray(data) ? data : [];
      // 🔥 Rakan auto-creation removed (Feb 2026).
      setBusinessAccounts(list);
      setRakanBusinessAccountId('');
      setMissingRakanAccounts(false);
    } catch (error) {
      setBusinessAccounts([]);
      setRakanBusinessAccountId('');
      setMissingRakanAccounts(false);
    }
  };

  const loadModalParts = async () => {
    setLoadingModalParts(true);
    try {
      const response = await partAPI.getAll();
      const list = Array.isArray(response.data) ? response.data : [];
      setModalParts(list);
      if (!parts.length) {
        setParts(list);
      }
    } catch (error) {
      setModalParts([]);
    } finally {
      setLoadingModalParts(false);
    }
  };

  const openTransactionModal = (type, part = null) => {
    setTransactionType(type || 'sale');
    setSaleMode(type === 'sale' ? 'instant' : 'instant');
    setDirectAmount('');
    setDirectDescription('');
    setTransactionVehicleId('');
    setSelectedPartnerId('');
    setSelectedAccountId('');
    if (part) {
      setTransactionItems([
        {
          partId: part.id,
          name: part.name,
          quantity: 1,
          price: type === 'sale' ? Number(part.sellingPrice || 0) : Number(part.purchasePrice || 0),
        }
      ]);
    } else {
      setTransactionItems([{ partId: '', name: '', quantity: 1, price: 0 }]);
    }
    setShowTransactionModal(true);
  };

  const updateTransactionItem = (index, field, value) => {
    setTransactionItems(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      if (field === 'partId') {
        const selected = partsById.get(value);
        if (selected) {
          updated[index].name = selected.name;
          updated[index].price = transactionType === 'sale'
            ? Number(selected.sellingPrice || 0)
            : Number(selected.purchasePrice || 0);
        }
      }
      return updated;
    });
  };

  const addTransactionItem = () => {
    setTransactionItems(prev => [...prev, { partId: '', name: '', quantity: 1, price: 0 }]);
  };

  const removeTransactionItem = (index) => {
    setTransactionItems(prev => prev.filter((_, i) => i !== index));
  };

  const submitTransaction = async () => {
    if (!selectedAccountId) {
      toast({ title: 'خطأ', description: 'اختر الحساب المحاسبي للعملية', variant: 'destructive' });
      return;
    }

    const selectedAccount = accounts.find((acc) => (acc.id || acc.code) === selectedAccountId);
    if (!selectedAccount) {
      toast({ title: 'خطأ', description: 'تعذر قراءة الحساب المحدد', variant: 'destructive' });
      return;
    }

    const selectedAccountCode = normalizeAccountCode(selectedAccount.code || selectedAccountId || '');
    const isRakanTarget = isRakanCode(selectedAccountCode);
    let currentBusinessAccounts = Array.isArray(businessAccounts) ? [...businessAccounts] : [];
    let rakanAccount = currentBusinessAccounts.find((acc) => isRakanBusinessAccount(acc)) || null;
    let workshopAccount = currentBusinessAccounts.find((acc) => !isRakanBusinessAccount(acc)) || null;

    if (isRakanTarget && !rakanAccount) {
      toast({
        title: 'خطأ',
        description: 'لا يوجد حساب أعمال مستقل لقطع راكان. أعد تحميل الصفحة أو أنشئ الحساب من الإعدادات.',
        variant: 'destructive',
      });
      return;
    }

    if (!isRakanTarget && !workshopAccount) {
      try {
        const createRes = await fetch(`${apiBase}/biz-accounts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: 'الورشة الرئيسية',
            code: 'MAIN_WORKSHOP',
            currency: 'SAR',
          }),
        });
        const created = await createRes.json().catch(() => null);
        if (createRes.ok && created?.id) {
          currentBusinessAccounts = [created, ...currentBusinessAccounts];
          workshopAccount = created;
          setBusinessAccounts(currentBusinessAccounts);
        }
      } catch (_error) {
        // ignore, handled by guard below
      }
    }

    const targetBusinessAccountId = isRakanTarget
      ? (rakanAccount?.id || rakanBusinessAccountId)
      : (workshopAccount?.id || '');

    if (!targetBusinessAccountId) {
      toast({
        title: 'خطأ',
        description: 'تعذر تحديد حساب الأعمال المناسب للعملية.',
        variant: 'destructive',
      });
      return;
    }

    let itemsPayload = [];
    if (transactionType === 'direct') {
      const amount = Number(directAmount || 0);
      if (!(amount > 0)) {
        toast({ title: 'خطأ', description: 'أدخل مبلغًا صحيحًا للعملية المباشرة', variant: 'destructive' });
        return;
      }
      itemsPayload = [{
        itemType: 'manual',
        itemId: '',
        name: directDescription || selectedAccount?.name_ar || selectedAccount?.name || 'عملية مباشرة',
        quantity: 1,
        price: amount,
        total: amount,
      }];
    } else {
      const validItems = transactionItems.filter((item) => item.partId && item.quantity > 0);
      if (!validItems.length) {
        toast({ title: 'خطأ', description: 'أضف قطعة واحدة على الأقل', variant: 'destructive' });
        return;
      }
      if (transactionType === 'sale' && saleMode === 'vehicle' && !transactionVehicleId) {
        toast({ title: 'خطأ', description: 'اختر المركبة المرتبطة بالبيع', variant: 'destructive' });
        return;
      }
      if (transactionType === 'sale' && saleMode !== 'vehicle' && !selectedPartnerId) {
        toast({ title: 'خطأ', description: 'اختر العميل', variant: 'destructive' });
        return;
      }
      if (transactionType === 'purchase' && !selectedPartnerId) {
        toast({ title: 'خطأ', description: 'اختر المورد', variant: 'destructive' });
        return;
      }
      itemsPayload = validItems.map(item => ({
        itemType: 'part',
        itemId: item.partId,
        name: item.name,
        quantity: Number(item.quantity || 1),
        price: Number(item.price || 0),
        total: Number(item.quantity || 1) * Number(item.price || 0)
      }));
    }

    const operationType = inferOperationTypeByAccount(selectedAccount?.type, transactionType);
    const total = itemsPayload.reduce((sum, item) => sum + item.total, 0);
    const isVehicleOperation = transactionType === 'sale' && saleMode === 'vehicle';
    const operationKind = isRakanTarget
      ? 'RAKAN_PARTS_OPERATION'
      : (isVehicleOperation ? 'VEHICLE_OPERATION' : 'WORKSHOP_OPERATION');
    const scope = isRakanTarget
      ? 'rakan_parts'
      : (isVehicleOperation ? 'vehicle' : 'workshop');
    const businessUnit = isRakanTarget ? 'rakan_parts' : 'workshop';
    const source = isRakanTarget ? 'rakan_parts_pos' : 'parts_pos';

    const partnerName = transactionType === 'sale'
      ? (customers.find(c => c.id === selectedPartnerId)?.name
        || vehicles.find(v => v.id === transactionVehicleId)?.customerName
        || vehicles.find(v => v.id === transactionVehicleId)?.ownerName
        || vehicles.find(v => v.id === transactionVehicleId)?.owner_name
      )
      : (suppliers.find(s => s.id === selectedPartnerId)?.name);

    const baseNote = transactionType === 'direct'
      ? (directDescription || 'عملية مباشرة')
      : (transactionType === 'sale' ? 'عملية بيع قطع' : 'عملية شراء قطع');
    const notes = `${isRakanTarget ? '[RAKAN_PARTS] ' : ''}${baseNote} | ACCOUNT_CODE:${selectedAccountCode} | ACCOUNTING_TARGET:${selectedAccount?.name_ar || selectedAccount?.name || selectedAccountId}`;

    try {
      await operationsAPI.create({
        type: operationType,
        operationKind,
        items: itemsPayload,
        subtotal: total,
        total,
        scope,
        source,
        businessUnit,
        paymentMethod: isVehicleOperation ? 'credit' : 'cash',
        vehicleId: isVehicleOperation ? transactionVehicleId : undefined,
        partnerType: operationType === 'sale' ? 'customer' : 'supplier',
        partnerId: selectedPartnerId,
        partnerName: partnerName || '',
        accountId: targetBusinessAccountId,
        accountingAccountId: selectedAccountId,
        notes,
      });

      if (transactionType !== 'direct') {
        for (const item of itemsPayload) {
          if (transactionType === 'sale') {
            await api.post(`/parts/${item.itemId}/sell`, null, { params: { quantity: item.quantity } });
          } else {
            await api.post(`/parts/${item.itemId}/restock`, null, { params: { quantity: item.quantity } });
          }
        }
      }

      toast({
        title: 'تمت العملية',
        description: transactionType === 'sale'
          ? 'تم تسجيل عملية البيع'
          : transactionType === 'purchase'
            ? 'تم تسجيل عملية الشراء'
            : 'تم تسجيل العملية المباشرة'
      });
      setShowTransactionModal(false);
      setDirectAmount('');
      setDirectDescription('');
      await loadParts();
      await loadInventoryIntelligence();
    } catch (error) {
      const detail = error?.response?.data?.detail || 'تعذر حفظ العملية';
      toast({ title: 'خطأ', description: detail, variant: 'destructive' });
    }
  };

  const resetForm = () => {
    setFormData({
      partNumber: '', name: '', category: '', purchasePrice: '', sellingPrice: '',
      quantity: '', minQuantity: '5', supplier: '', image: '', location: ''
    });
    setEditingPart(null);
  };

  const openEditDialog = (part) => {
    setEditingPart(part);
    setFormData({
      partNumber: part.partNumber, name: part.name, category: part.category,
      purchasePrice: part.purchasePrice.toString(), sellingPrice: part.sellingPrice.toString(),
      quantity: part.quantity.toString(), minQuantity: part.minQuantity.toString(),
      supplier: part.supplier || '', image: part.image || '', location: part.location || ''
    });
    setIsDialogOpen(true);
  };

  const deferredSearchQuery = useDeferredValue(searchQuery);

  const filteredParts = useMemo(() => {
    return parts
      .filter((p) => {
        if (!deferredSearchQuery.trim()) return true;
        const q = deferredSearchQuery.trim().toLowerCase();
        return (
          (p.name || '').toLowerCase().includes(q) ||
          (p.partNumber || '').toLowerCase().includes(q) ||
          (p.category || '').toLowerCase().includes(q)
        );
      })
      .filter((p) => !selectedCategory || p.category === selectedCategory)
      .filter((p) => !selectedBrand || p.brand === selectedBrand)
      .filter((p) => {
        if (!stockStatus) return true;
        if (stockStatus === 'low') return p.quantity > 0 && p.quantity <= p.minQuantity;
        if (stockStatus === 'out') return p.quantity === 0;
        if (stockStatus === 'good') return p.quantity > p.minQuantity;
        return true;
      });
  }, [parts, deferredSearchQuery, selectedCategory, selectedBrand, stockStatus]);

  const lowStockCount = useMemo(
    () => parts.filter((p) => p.quantity <= p.minQuantity).length,
    [parts]
  );

  const outOfStockCount = useMemo(
    () => parts.filter((p) => p.quantity <= 0).length,
    [parts]
  );

  const inventoryValue = useMemo(
    () => parts.reduce((sum, p) => sum + (Number(p.quantity || 0) * Number(p.sellingPrice || 0)), 0),
    [parts]
  );

  const categories = useMemo(
    () => Array.from(new Set(parts.map((p) => p.category).filter(Boolean))),
    [parts]
  );

  const brands = useMemo(
    () => Array.from(new Set(parts.map((p) => p.brand).filter(Boolean))),
    [parts]
  );

  const categoryStats = useMemo(
    () => categories.map((cat) => {
      const catParts = parts.filter((p) => p.category === cat);
      const low = catParts.filter((p) => p.quantity > 0 && p.quantity <= p.minQuantity).length;
      return { name: cat, count: catParts.length, low };
    }),
    [categories, parts]
  );
  const currentDate = useMemo(() => new Date().toLocaleDateString('ar-SA', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }), []);
  const activeVehicles = useMemo(() => {
    const inactiveStatuses = ['delivered', 'completed', 'finished', 'تم التسليم', 'مكتمل'];
    return vehicles.filter(vehicle => !inactiveStatuses.includes(vehicle.status));
  }, [vehicles]);
  // accountOptions is defined earlier in the component (before useEffects that need it)
  const partOptions = useMemo(() => (modalParts.length ? modalParts : parts), [modalParts, parts]);
  const transactionTotal = useMemo(() => {
    if (transactionType === 'direct') {
      return Number(directAmount || 0);
    }
    return transactionItems.reduce((sum, item) => sum + (Number(item.quantity || 0) * Number(item.price || 0)), 0);
  }, [transactionItems, transactionType, directAmount]);
  const vehicleOptions = useMemo(() => (activeVehicles.length ? activeVehicles : vehicles), [activeVehicles, vehicles]);
  const rakanBusinessAccount = useMemo(
    () => businessAccounts.find((acc) => acc.id === rakanBusinessAccountId) || null,
    [businessAccounts, rakanBusinessAccountId]
  );
  const selectedTransactionAccount = useMemo(
    () => accounts.find((acc) => (acc.id || acc.code) === selectedAccountId) || null,
    [accounts, selectedAccountId]
  );
  const isSelectedTransactionRakan = isRakanCode(selectedTransactionAccount?.code || selectedAccountId);

  return (
    <div className="max-w-7xl mx-auto space-y-6 overflow-x-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold text-white">🔧 نظام إدارة قطع الغيار</h1>
          <p className="text-slate-400">إدارة المخزون والبيع والشراء للقطع</p>
        </div>
        <div className="px-4 py-2 rounded-lg bg-white/10 text-sm text-white" data-testid="inventory-date-badge">
          {currentDate}
        </div>
        <div className="flex flex-wrap gap-2 w-full sm:w-auto">
          <Button
            onClick={() => openTransactionModal()}
            className="bg-emerald-600 hover:bg-emerald-700 text-white w-full sm:w-auto"
            data-testid="inventory-pos-button"
          >
            نقطة بيع
          </Button>
          <div className="relative">
            <input 
              type="file" 
              accept=".xlsx,.xls,.csv" 
              onChange={handleImportParts} 
              className="hidden" 
              id="import-excel"
              disabled={importing}
              data-testid="parts-import-input"
            />
            <label htmlFor="import-excel">
              <Button
                variant="outline"
                asChild
                className="cursor-pointer bg-green-50 text-green-700 hover:bg-green-100 border-green-200 w-full sm:w-auto"
                data-testid="parts-import-button"
              >
                <span>
                  <FileSpreadsheet className="ml-2" size={18} />
                  {importing ? 'جارٍ الاستيراد...' : 'استيراد Excel'}
                </span>
              </Button>
            </label>
          </div>
          
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button
            onClick={() => { resetForm(); setIsDialogOpen(true); }}
            className="apple-button w-full sm:w-auto"
            data-testid="parts-add-button"
          >
            <Plus className="ml-2" size={18} />
            إضافة قطعة
          </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>{editingPart ? 'تعديل قطعة' : 'إضافة قطعة جديدة'}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>رقم القطعة *</Label>
                    <Input required value={formData.partNumber} onChange={e => setFormData({...formData, partNumber: e.target.value})} data-testid="part-number-input" />
                  </div>
                  <div className="space-y-2">
                    <Label>اسم القطعة *</Label>
                    <Input required value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} data-testid="part-name-input" />
                  </div>
                  <div className="space-y-2">
                    <Label>التصنيف *</Label>
                    <Input required value={formData.category} onChange={e => setFormData({...formData, category: e.target.value})} data-testid="part-category-input" />
                  </div>
                  <div className="space-y-2">
                    <Label>الموقع</Label>
                    <Input value={formData.location} onChange={e => setFormData({...formData, location: e.target.value})} placeholder="A-12" data-testid="part-location-input" />
                  </div>
                  <div className="space-y-2">
                    <Label>الكمية *</Label>
                    <Input required type="number" value={formData.quantity} onChange={e => setFormData({...formData, quantity: e.target.value})} data-testid="part-quantity-input" />
                  </div>
                  <div className="space-y-2">
                    <Label>الحد الأدنى</Label>
                    <Input type="number" value={formData.minQuantity} onChange={e => setFormData({...formData, minQuantity: e.target.value})} data-testid="part-min-quantity-input" />
                  </div>
                  <div className="space-y-2">
                    <Label>سعر الشراء *</Label>
                    <Input required type="number" value={formData.purchasePrice} onChange={e => setFormData({...formData, purchasePrice: e.target.value})} data-testid="part-purchase-price-input" />
                  </div>
                  <div className="space-y-2">
                    <Label>سعر البيع *</Label>
                    <Input required type="number" value={formData.sellingPrice} onChange={e => setFormData({...formData, sellingPrice: e.target.value})} data-testid="part-selling-price-input" />
                  </div>
                  <div className="space-y-2 col-span-2">
                    <Label>المورد</Label>
                    <Input value={formData.supplier} onChange={e => setFormData({...formData, supplier: e.target.value})} data-testid="part-supplier-input" />
                  </div>
                </div>

                  <div className="space-y-2">
                    <Label>الصورة</Label>
                    <div className="flex items-center gap-4">
                      <label className="cursor-pointer apple-button-secondary flex items-center gap-2 px-4 py-2">
                        <Upload size={16} />
                        <span>{uploading ? 'جارٍ الرفع...' : 'رفع صورة'}</span>
                        <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" data-testid="part-image-input" />
                      </label>
                      {formData.image && <img src={formData.image} alt="Preview" className="h-12 w-12 object-cover rounded-lg border border-gray-200" />}
                    </div>
                  </div>

                <div className="flex gap-3 pt-4">
                  <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)} className="flex-1" data-testid="part-dialog-cancel">إلغاء</Button>
                  <Button type="submit" className="flex-1 apple-button" data-testid="part-dialog-save">حفظ</Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>

      <PartsTransactionModal
        open={showTransactionModal}
        onOpenChange={setShowTransactionModal}
        transactionType={transactionType}
        saleMode={saleMode}
        directAmount={directAmount}
        directDescription={directDescription}
        transactionVehicleId={transactionVehicleId}
        selectedPartnerId={selectedPartnerId}
        selectedAccountId={selectedAccountId}
        loadingVehicles={loadingVehicles}
        loadingPartners={loadingPartners}
        loadingAccounts={loadingAccounts}
        loadingModalParts={loadingModalParts}
        vehicleOptions={vehicleOptions}
        customers={customers}
        suppliers={suppliers}
        accountOptions={accountOptions}
        partOptions={partOptions}
        transactionItems={transactionItems}
        transactionTotal={transactionTotal}
        setTransactionType={setTransactionType}
        setSaleMode={setSaleMode}
        setDirectAmount={setDirectAmount}
        setDirectDescription={setDirectDescription}
        setTransactionVehicleId={setTransactionVehicleId}
        setSelectedPartnerId={setSelectedPartnerId}
        setSelectedAccountId={setSelectedAccountId}
        updateTransactionItem={updateTransactionItem}
        removeTransactionItem={removeTransactionItem}
        addTransactionItem={addTransactionItem}
        submitTransaction={submitTransaction}
        loadVehicles={loadVehicles}
        loadAccounts={loadAccounts}
        loadCustomers={loadCustomers}
        loadSuppliers={loadSuppliers}
        loadModalParts={loadModalParts}
      />

      {showTransactionModal && isSelectedTransactionRakan && missingRakanAccounts && (
        <div
          className="glass-card p-3 border border-amber-400/50 bg-amber-500/10 text-amber-200 text-sm"
          data-testid="transaction-rakan-accounts-warning"
        >
          تنبيه: لم يتم العثور على حسابَي إيراد/مصروف لقطع راكان بشكل كامل. يرجى التأكد من وجودهما في دليل الحسابات.
        </div>
      )}

      {showTransactionModal && isSelectedTransactionRakan && rakanBusinessAccount && (
        <div className="text-xs text-cyan-200" data-testid="transaction-rakan-business-account-note">
          سيتم تسجيل العملية ضمن حساب الأعمال المستقل: <strong>{rakanBusinessAccount.name}</strong>
        </div>
      )}
        </div>
      </div>

      <div className="glass-card p-2 flex gap-2 w-full sm:w-fit" data-testid="inventory-main-tabs">

      {/* بطاقات الإحصاء المحسّنة */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-2 w-full" data-testid="inventory-stats-cards">
        {[
          { label: 'إجمالي الأصناف', value: parts.length, color: '#a78bfa', icon: '📦' },
          { label: 'قيمة المخزون', value: inventoryValue.toLocaleString('ar-SA') + ' ر.س', color: '#38bdf8', icon: '💰' },
          { label: 'نفاد الحد الأدنى', value: lowStockCount, color: '#fb923c', icon: '⚠️', alert: lowStockCount > 0 },
          { label: 'نافد تماماً', value: outOfStockCount, color: '#ef4444', icon: '🚫', alert: outOfStockCount > 0 },
        ].map((s) => (
          <div key={s.label}
            className={`rounded-2xl p-3 border transition-all ${s.alert ? 'animate-pulse' : ''}`}
            style={{
              background: `${s.color}14`,
              borderColor: `${s.color}30`,
            }}
            data-testid={`inventory-stat-${s.label}`}
          >
            <div className="text-xl mb-1">{s.icon}</div>
            <div className="text-lg font-bold tabular-nums" style={{ color: s.color }}>{s.value}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

        <Button
          type="button"
          onClick={() => setInventoryViewTab('stock')}
          className={inventoryViewTab === 'stock' ? 'apple-button' : 'apple-button-secondary'}
          data-testid="inventory-main-tab-stock"
        >
          تبويب المخزون
        </Button>
        <Button
          type="button"
          onClick={() => setInventoryViewTab('pos')}
          className={inventoryViewTab === 'pos' ? 'apple-button' : 'apple-button-secondary'}
          data-testid="inventory-main-tab-pos-operations"
        >
          عمليات نقطة البيع
        </Button>
      </div>

      {inventoryViewTab === 'stock' ? (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4" data-testid="inventory-smart-intelligence-section">
            <div className="xl:col-span-2">
              <InventorySmartOverview
                summary={inventoryDashboard?.summary}
                topMovers={inventoryDashboard?.top_movers || []}
                loading={loadingInventoryIntelligence}
              />
            </div>
            <div>
              <InventoryAlertsRail
                alerts={inventoryAlerts}
                onSelectAlert={handleAlertSelection}
              />
            </div>
          </div>
          <PartsOcrPanel
            ocrPreview={ocrPreview}
            ocrError={ocrError}
            ocrResult={ocrResult}
            ocrLoading={ocrLoading}
            ocrImporting={ocrImporting}
            onFileChange={handleOcrFileChange}
            onRun={runOcr}
            onImport={importOcrItems}
          />

          <InventoryStatsCards
            partsCount={parts.length}
            lowStockCount={lowStockCount}
            outOfStockCount={outOfStockCount}
            inventoryValue={inventoryValue}
          />

          <InventoryFiltersPanel
            searchQuery={searchQuery}
            selectedCategory={selectedCategory}
            selectedBrand={selectedBrand}
            stockStatus={stockStatus}
            categories={categories}
            brands={brands}
            categoryStats={categoryStats}
            outOfStockCount={outOfStockCount}
            lowStockCount={lowStockCount}
            onSearchChange={setSearchQuery}
            onCategoryChange={setSelectedCategory}
            onBrandChange={setSelectedBrand}
            onStockStatusChange={setStockStatus}
            onResetFilters={handleResetFilters}
            onCategoryQuickFilter={setSelectedCategory}
            onOutFilter={() => setStockStatus('out')}
            onLowFilter={() => setStockStatus('low')}
          />

          <PartInventoryGrid
            loading={loading}
            parts={filteredParts}
            onSell={handleSellPart}
            onRestock={handleRestockPart}
            onEdit={openEditDialog}
            onDelete={handleDelete}
          />
        </>
      ) : (
        <div className="glass-card p-4 space-y-4" data-testid="inventory-pos-operations-tab-panel">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white" data-testid="inventory-pos-operations-title">العمليات المنشأة من نقطة البيع</h2>
              <p className="text-sm text-slate-300" data-testid="inventory-pos-operations-subtitle">تظهر هنا عمليات نقطة البيع مع معلومات الربط بالمركبات والعملاء والموردين.</p>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={loadPosOperations}
              data-testid="inventory-pos-operations-refresh-button"
            >
              تحديث العمليات
            </Button>
          </div>

          {loadingPosOperations ? (
            <div className="text-sm text-slate-300" data-testid="inventory-pos-operations-loading">جاري تحميل العمليات...</div>
          ) : posOperations.length === 0 ? (
            <div className="text-sm text-slate-400" data-testid="inventory-pos-operations-empty">لا توجد عمليات نقطة بيع حتى الآن.</div>
          ) : (
            <div className="space-y-3" data-testid="inventory-pos-operations-list">
              {posOperations.map((op) => {
                const opDate = op?.date || op?.createdAt || op?.created_at;
                const linkType = op?.vehicleId ? 'مركبة' : labelFromMap(op?.partnerType, PARTNER_TYPE_LABELS, 'عميل');
                const linkValue = op?.vehicleId ? resolveVehicleDisplay(op, vehicles) : (op?.partnerName || 'غير مرتبط');
                const accountDisplay = resolveAccountDisplay(op, accounts, businessAccounts);
                return (
                  <div key={op.id} className="rounded-xl border border-white/10 bg-white/5 p-3" data-testid={`inventory-pos-operation-row-${op.id}`}>
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                      <div className="space-y-1">
                        <p className="text-white text-sm" data-testid={`inventory-pos-operation-type-${op.id}`}>
                          {labelFromMap(op?.type, OPERATION_TYPE_LABELS, 'عملية')} • {formatCurrency(op?.total || op?.amount || 0)}
                        </p>
                        <p className="text-xs text-slate-300" data-testid={`inventory-pos-operation-link-${op.id}`}>
                          الربط: {linkType} — {linkValue}
                        </p>
                        <p className="text-xs text-slate-400" data-testid={`inventory-pos-operation-account-${op.id}`}>
                          الحساب المحاسبي: {accountDisplay.name}{accountDisplay.code ? ` (${accountDisplay.code})` : ''}
                        </p>
                      </div>
                      <div className="text-xs text-slate-400 text-right" data-testid={`inventory-pos-operation-meta-${op.id}`}>
                        <p>المصدر: {labelFromMap(op?.source, SOURCE_LABELS, '-')}</p>
                        <p>{opDate ? new Date(opDate).toLocaleString('ar-SA') : 'بدون تاريخ'}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PartsInventory;
