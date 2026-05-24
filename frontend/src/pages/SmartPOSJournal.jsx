import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Banknote,
  CarFront,
  Copy,
  CreditCard,
  HandCoins,
  Landmark,
  Loader2,
  Pencil,
  Plus,
  Save,
  ShoppingCart,
  Sparkles,
  Trash2,
  UserRound,
  Wallet,
} from 'lucide-react';
import { PAYMENT_METHOD_LABELS, SOURCE_LABELS, labelFromMap } from '../utils/displayLabels';
import { generateIdempotencyKey } from '../utils/idempotency';
import SmartAccountSelect from '../components/SmartAccountSelect';

const formatSAR = (value) => (
  `${new Intl.NumberFormat('ar-SA', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value) || 0)} ر.س`
);

const normalizeArray = (value) => (Array.isArray(value) ? value.filter(Boolean) : []);

const normalizeText = (value) => String(value || '').trim().toLowerCase();

const roundAmount = (value) => Number((Number(value) || 0).toFixed(2));

const extractToken = (text = '', token = '') => {
  if (!token) return '';
  const match = String(text || '').match(new RegExp(`\\[${token}:([^\\]]+)\\]`, 'i'));
  return String(match?.[1] || '').trim();
};

const stripTokens = (text = '') => String(text || '')
  .replace(/\[PARTY:[^\]]+\]/gi, '')
  .replace(/\[PARTY_TYPE:[^\]]+\]/gi, '')
  .replace(/\[VEHICLE_REF:[^\]]+\]/gi, '')
  .replace(/\[VISIT:[^\]]+\]/gi, '')
  .replace(/\[IDEMP:[^\]]+\]/gi, '')
  .replace(/\s{2,}/g, ' ')
  .trim();

const resolveRecentParty = (entry = {}) => (
  entry.party_label || entry.partyLabel || extractToken(entry.description, 'PARTY') || 'مفتوح'
);

const resolveRecentVehicle = (entry = {}) => (
  entry.vehicle_label || entry.vehicleLabel || entry.vehicle_plate || entry.vehiclePlate || extractToken(entry.description, 'VEHICLE_REF') || 'غير محددة'
);

const recentEntryLinesSummary = (entry = {}) => {
  const lines = normalizeArray(entry.lines).slice(0, 3);
  if (!lines.length) return '';
  return lines.map((line) => {
    const account = line.account_name || line.name || line.account || line.code || 'حساب';
    const debit = Number(line.debit || 0);
    const credit = Number(line.credit || 0);
    if (debit > 0) return `${account}: مدين ${formatSAR(debit)}`;
    if (credit > 0) return `${account}: دائن ${formatSAR(credit)}`;
    return account;
  }).join(' • ');
};

const PAYMENT_METHODS = [
  { key: 'cash', label: 'نقدي', icon: Banknote },
  { key: 'bank', label: 'بنك / تحويل', icon: Landmark },
  { key: 'pos', label: 'نقاط بيع', icon: CreditCard },
];

const TEMPLATE_META = [
  {
    key: 'instant_sale',
    title: '⚡ بيع فوري',
    desc: 'فاتورة سريعة ببنود متعددة وعميل ومركبة وامكانية بيع بدون عميل او مركبه',
    color: 'emerald',
    transactionType: 'sale',
    partyRole: 'customer',
    paymentSide: 'debit',
    counterAccountKey: 'mechanicalRevenue',
    supportsItems: true,
    supportsVehicle: true,
    requiresParty: false,
    defaultPaymentMethod: 'cash',
  },
  {
    key: 'purchase',
    title: 'شراء',
    desc: 'فاتورة مشتريات (يمكن تعديل حساب المدين)',
    color: 'rose',
    transactionType: 'expense',
    partyRole: 'supplier',
    paymentSide: 'credit',
    counterAccountKey: 'operatingExpense',
    supportsItems: true,
    supportsVehicle: false,
    requiresParty: false,
    defaultPaymentMethod: 'cash',
  },
  {
    key: 'receipt_voucher',
    title: 'سند قبض',
    desc: 'سند قبض مرتبط بعميل ومركبه',
    color: 'sky',
    transactionType: 'settlement',
    partyRole: 'customer',
    paymentSide: 'debit',
    counterAccountKey: 'customers',
    supportsItems: false,
    supportsVehicle: true,
    requiresParty: true,
    requiresVehicle: true,
    defaultPaymentMethod: 'cash',
  },
  {
    key: 'salary',
    title: '👷 رواتب',
    desc: 'صرف رواتب الموظفين أو الفنيين من نفس الشاشة',
    color: 'amber',
    transactionType: 'expense',
    partyRole: null,
    paymentSide: 'credit',
    counterAccountKey: 'salaryExpense',
    supportsItems: true,
    supportsVehicle: false,
    requiresParty: false,
    defaultPaymentMethod: 'bank',
  },
  {
    key: 'collect_customer',
    title: '🤝 تحصيل من عميل',
    desc: 'تسوية ذمم عميل مقابل نقد أو بنك',
    color: 'violet',
    transactionType: 'settlement',
    partyRole: 'customer',
    paymentSide: 'debit',
    counterAccountKey: 'customers',
    supportsItems: false,
    supportsVehicle: false,
    requiresParty: true,
    defaultPaymentMethod: 'cash',
  },
  {
    key: 'pay_supplier',
    title: '📦 سداد لمورد',
    desc: 'سداد رصيد مورد من النقد أو البنك',
    color: 'indigo',
    transactionType: 'settlement',
    partyRole: 'supplier',
    paymentSide: 'credit',
    counterAccountKey: 'suppliers',
    supportsItems: false,
    supportsVehicle: false,
    requiresParty: true,
    defaultPaymentMethod: 'cash',
  },
  {
    key: 'bank_deposit',
    title: '🏧 إيداع بنكي',
    desc: 'إيداع بنكي',
    color: 'slate',
    transactionType: 'manual',
    partyRole: null,
    paymentSide: 'static',
    supportsItems: false,
    supportsVehicle: false,
    requiresParty: false,
    defaultPaymentMethod: 'bank',
  },
];

const toneClasses = (color) => ({
  emerald: { bg: 'from-emerald-500/20 to-teal-500/10', border: 'border-emerald-400/30', text: 'text-emerald-100', ring: 'ring-emerald-400/40' },
  sky: { bg: 'from-sky-500/20 to-cyan-500/10', border: 'border-sky-400/30', text: 'text-sky-100', ring: 'ring-sky-400/40' },
  cyan: { bg: 'from-cyan-500/20 to-blue-500/10', border: 'border-cyan-400/30', text: 'text-cyan-100', ring: 'ring-cyan-400/40' },
  amber: { bg: 'from-amber-500/20 to-orange-500/10', border: 'border-amber-400/30', text: 'text-amber-100', ring: 'ring-amber-400/40' },
  rose: { bg: 'from-rose-500/20 to-pink-500/10', border: 'border-rose-400/30', text: 'text-rose-100', ring: 'ring-rose-400/40' },
  violet: { bg: 'from-violet-500/20 to-fuchsia-500/10', border: 'border-violet-400/30', text: 'text-violet-100', ring: 'ring-violet-400/40' },
  indigo: { bg: 'from-indigo-500/20 to-blue-500/10', border: 'border-indigo-400/30', text: 'text-indigo-100', ring: 'ring-indigo-400/40' },
  slate: { bg: 'from-slate-500/20 to-slate-400/10', border: 'border-slate-400/30', text: 'text-slate-100', ring: 'ring-slate-300/30' },
}[color] || {
  bg: 'from-slate-500/20 to-slate-400/10',
  border: 'border-slate-400/30',
  text: 'text-slate-100',
  ring: 'ring-slate-300/30',
});

const pickAccount = (accounts = [], candidates = [], fallback = { code: '', name: 'حساب' }) => {
  const safeAccounts = normalizeArray(accounts);
  for (const candidate of candidates) {
    const hit = safeAccounts.find((account) => {
      const code = String(account?.code || '').trim();
      const name = normalizeText(account?.name_ar || account?.name);
      const type = normalizeText(account?.type || '');
      if (candidate.type && type !== normalizeText(candidate.type)) return false;
      if (candidate.codes?.length && candidate.codes.includes(code)) return true;
      if (candidate.includesAll?.length && candidate.includesAll.every((part) => name.includes(normalizeText(part)))) return true;
      if (candidate.includesAny?.length && candidate.includesAny.some((part) => name.includes(normalizeText(part)))) return true;
      return false;
    });
    if (hit) {
      return {
        code: String(hit.code || fallback.code || '').trim(),
        name: hit.name_ar || hit.name || fallback.name,
      };
    }
  }
  return fallback;
};

const buildVehicleLabel = (vehicle) => {
  const plate = String(vehicle?.plateNumber || vehicle?.fileNumber || '').trim();
  const customer = String(vehicle?.customerName || '').trim();
  return [plate, customer].filter(Boolean).join(' — ');
};

export default function SmartPOSJournal({ apiBase, workshopId, accounts = [], recentEntries = [], onSaved }) {
  const [activeTemplateKey, setActiveTemplateKey] = useState('instant_sale');
  const [customPurchaseAccountId, setCustomPurchaseAccountId] = useState(null);
  const [isEditingDebit, setIsEditingDebit] = useState(false);
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [partyName, setPartyName] = useState('');
  const [partyId, setPartyId] = useState('');
  const [vehicleRef, setVehicleRef] = useState('');
  const [vehicleId, setVehicleId] = useState('');
  const [items, setItems] = useState([]);
  const [itemDraft, setItemDraft] = useState({ name: '', price: '', qty: 1, itemType: 'service' });
  const [customers, setCustomers] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [parts, setParts] = useState([]);
  const [services, setServices] = useState([]);
  const [lookupsLoading, setLookupsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedToast, setSavedToast] = useState(null);
  const [localRecentEntries, setLocalRecentEntries] = useState([]);
  const [recentEntriesLoading, setRecentEntriesLoading] = useState(false);

  const accountRefs = useMemo(() => {
    const cash = pickAccount(accounts, [
      { codes: ['003'] },
      { includesAll: ['النقد'] },
      { includesAny: ['cash'] },
    ], { code: '003', name: 'النقد' });

    const bank = pickAccount(accounts, [
      { codes: ['004'] },
      { includesAll: ['البنك'] },
      { includesAny: ['bank'] },
    ], { code: '004', name: 'البنك' });

    const pos = pickAccount(accounts, [
      { codes: ['006'] },
      { includesAll: ['نقاط', 'بيع'] },
      { includesAny: ['pos'] },
    ], bank);

    const customersAccount = pickAccount(accounts, [
      { codes: ['005'], type: 'asset' },
      { includesAll: ['العملاء'], type: 'asset' },
    ], { code: '005', name: 'العملاء (ذمم مدينة)' });

    const suppliersAccount = pickAccount(accounts, [
      { codes: ['2101'], type: 'liability' },
      { includesAny: ['المورد', 'supplier'], type: 'liability' },
    ], { code: '2101', name: 'الموردون (ذمم دائنة)' });

    const salesRevenue = pickAccount(accounts, [
      { includesAll: ['إيرادات', 'الخدمات'], type: 'revenue' },
      { includesAll: ['إيرادات', 'خدمات'], type: 'revenue' },
      { includesAll: ['إيراد', 'خدمات'], type: 'revenue' },
      { includesAll: ['ايراد', 'خدمات'], type: 'revenue' },
      { codes: ['025', '026', '027'], type: 'revenue' },
    ], { code: '025', name: 'إيرادات الخدمات' });

    const mechanicalRevenue = pickAccount(accounts, [
      { codes: ['027'] },
      { includesAll: ['إيرادات', 'ميكانيكية'] },
    ], { code: '027', name: 'إيرادات خدمات ميكانيكية' });

    const operatingExpense = pickAccount(accounts, [
      { codes: ['034'] },
      { includesAll: ['المصروفات', 'التشغيلية'] },
      { codes: ['035'] },
      { includesAll: ['مصروفات', 'إدارية'], type: 'expense' },
      { includesAll: ['مصروفات', 'عامة'], type: 'expense' },
      { includesAny: ['مصروفات تشغيلية'], type: 'expense' },
      { codes: ['036'], type: 'expense' },
    ], { code: '034', name: 'المصروفات التشغيلية' });

    const salaryExpense = pickAccount(accounts, [
      { includesAll: ['رواتب'], type: 'expense' },
      { includesAny: ['أجور'], type: 'expense' },
      { codes: ['036', '035'], type: 'expense' },
    ], { code: '036', name: 'رواتب إدارية' });

    return {
      cash,
      bank,
      pos,
      customers: customersAccount,
      suppliers: suppliersAccount,
      salesRevenue,
      mechanicalRevenue,
      operatingExpense,
      salaryExpense,
    };
  }, [accounts]);

  const getPaymentAccount = (method) => {
    if (method === 'bank') return accountRefs.bank;
    if (method === 'pos') return accountRefs.pos;
    return accountRefs.cash;
  };

  const templates = useMemo(() => TEMPLATE_META.map((template) => {
    if (template.key === 'bank_deposit') {
      return {
        ...template,
        debitAccount: accountRefs.bank,
        creditAccount: accountRefs.cash,
      };
    }

    return {
      ...template,
      counterAccount: accountRefs[template.counterAccountKey],
    };
  }), [accountRefs]);

  const activeTemplate = templates.find((template) => template.key === activeTemplateKey) || templates[0];

  useEffect(() => {
    if (activeTemplate?.defaultPaymentMethod) {
      setPaymentMethod(activeTemplate.defaultPaymentMethod);
    }
  }, [activeTemplate?.defaultPaymentMethod, activeTemplate?.key]);

  useEffect(() => {
    if (activeTemplate?.partyRole !== 'customer') {
      setVehicleRef('');
      setVehicleId('');
    }
    if (!activeTemplate?.partyRole) {
      setPartyName('');
      setPartyId('');
    }
  }, [activeTemplate?.partyRole]);

  useEffect(() => {
    let mounted = true;

    const loadLookups = async () => {
      setLookupsLoading(true);
      try {
        const [customersRes, suppliersRes, vehiclesRes, partsRes, servicesRes] = await Promise.all([
          axios.get(`${apiBase}/customers`),
          axios.get(`${apiBase}/suppliers`),
          axios.get(`${apiBase}/vehicles`, { params: { limit: 150 } }),
          axios.get(`${apiBase}/parts`, { params: { limit: 150 } }),
          axios.get(`${apiBase}/services`, { params: { limit: 150 } }),
        ]);

        if (!mounted) return;
        setCustomers(normalizeArray(customersRes?.data));
        setSuppliers(normalizeArray(suppliersRes?.data));
        setVehicles(normalizeArray(vehiclesRes?.data));
        setParts(normalizeArray(partsRes?.data));
        setServices(normalizeArray(servicesRes?.data));
      } catch {
        if (!mounted) return;
        setCustomers([]);
        setSuppliers([]);
        setVehicles([]);
        setParts([]);
        setServices([]);
      } finally {
        if (mounted) setLookupsLoading(false);
      }
    };

    loadLookups();
    return () => {
      mounted = false;
    };
  }, [apiBase]);

  useEffect(() => {
    let mounted = true;
    const loadRecentEntries = async () => {
      if (normalizeArray(recentEntries).length > 0) {
        setLocalRecentEntries([]);
        setRecentEntriesLoading(false);
        return;
      }
      try {
        setRecentEntriesLoading(true);
        const response = await axios.get(`${apiBase}/finance/journal-entries`, {
          params: { workshop_id: workshopId, limit: 5 },
        });
        if (!mounted) return;
        const rows = normalizeArray(response?.data?.data || response?.data);
        setLocalRecentEntries(rows);
      } catch {
        if (mounted) setLocalRecentEntries([]);
      } finally {
        if (mounted) setRecentEntriesLoading(false);
      }
    };
    loadRecentEntries();
    return () => {
      mounted = false;
    };
  }, [apiBase, workshopId, recentEntries]);

  const effectiveRecentEntries = normalizeArray(recentEntries).length > 0
    ? normalizeArray(recentEntries)
    : normalizeArray(localRecentEntries);

  const partyOptions = activeTemplate?.partyRole === 'supplier' ? suppliers : customers;

  const filteredVehicles = useMemo(() => {
    if (activeTemplate?.partyRole !== 'customer') return [];
    const normalizedPartyId = String(partyId || '').trim();
    const normalizedPartyName = normalizeText(partyName);
    let matches = normalizeArray(vehicles);

    if (normalizedPartyId) {
      const byId = matches.filter((vehicle) => String(vehicle?.customerId || '').trim() === normalizedPartyId);
      if (byId.length > 0) matches = byId;
    } else if (normalizedPartyName) {
      matches = matches.filter((vehicle) => {
        const joined = normalizeText([
          vehicle?.customerName,
          vehicle?.plateNumber,
          vehicle?.fileNumber,
        ].filter(Boolean).join(' '));
        return joined.includes(normalizedPartyName);
      });
    }

    return matches.slice(0, 60);
  }, [activeTemplate?.partyRole, vehicles, partyId, partyName]);

  const catalogItems = useMemo(() => {
    const serviceRows = normalizeArray(services).map((service, index) => ({
      id: service?.id || `service-${index}`,
      name: String(service?.name || '').trim(),
      itemType: 'service',
      price: roundAmount(service?.price),
      secondary: String(service?.category || 'خدمة').trim(),
    }));

    const partRows = normalizeArray(parts).map((part, index) => ({
      id: part?.id || `part-${index}`,
      name: String(part?.name || '').trim(),
      itemType: 'part',
      price: roundAmount(part?.sellingPrice || part?.purchasePrice),
      secondary: String(part?.partNumber || part?.category || 'قطعة').trim(),
    }));

    return [...serviceRows, ...partRows].filter((item) => item.name);
  }, [services, parts]);

  const suggestedCatalogItems = useMemo(() => {
    const query = normalizeText(itemDraft.name);
    const source = query
      ? catalogItems.filter((item) => normalizeText(`${item.name} ${item.secondary}`).includes(query))
      : catalogItems;
    return source.slice(0, 8);
  }, [catalogItems, itemDraft.name]);

  const itemsTotal = useMemo(
    () => items.reduce((sum, item) => sum + (Number(item?.price) || 0) * (Number(item?.qty) || 1), 0),
    [items]
  );

  const effectiveAmount = useMemo(() => {
    if (activeTemplate?.supportsItems && itemsTotal > 0) {
      return roundAmount(itemsTotal);
    }
    return roundAmount(amount);
  }, [activeTemplate?.supportsItems, itemsTotal, amount]);

  const effectiveEntry = useMemo(() => {
    const paymentAccount = getPaymentAccount(paymentMethod);
    if (!activeTemplate) {
      return {
        debitAccount: accountRefs.cash,
        creditAccount: accountRefs.salesRevenue,
      };
    }

    if (activeTemplate.key === 'bank_deposit') {
      return {
        debitAccount: activeTemplate.debitAccount,
        creditAccount: activeTemplate.creditAccount,
      };
    }

    let resolvedCounterAccount = activeTemplate.counterAccount;
    if (activeTemplate.key === 'purchase' && customPurchaseAccountId) {
      const selectedAccount = accounts.find((a) => a.id === customPurchaseAccountId || a.code === customPurchaseAccountId);
      if (selectedAccount) resolvedCounterAccount = selectedAccount;
    }

    if (activeTemplate.paymentSide === 'debit') {
      return {
        debitAccount: paymentAccount,
        creditAccount: resolvedCounterAccount,
      };
    }

    return {
      debitAccount: resolvedCounterAccount,
      creditAccount: paymentAccount,
    };
  }, [activeTemplate, accountRefs, paymentMethod, customPurchaseAccountId, accounts]);

  const isValid = useMemo(() => {
    if (!(effectiveAmount > 0)) return false;
    if (activeTemplate?.requiresParty && !String(partyName || '').trim()) return false;
    if (activeTemplate?.requiresVehicle && !String(vehicleId || vehicleRef || '').trim()) return false;
    return true;
  }, [effectiveAmount, activeTemplate?.requiresParty, activeTemplate?.requiresVehicle, partyName, vehicleId, vehicleRef]);

  const handlePartyChange = (value) => {
    const match = partyOptions.find((row) => normalizeText(row?.name) === normalizeText(value));
    setPartyName(match?.name || value);
    setPartyId(match?.id || '');

    if (activeTemplate?.partyRole === 'supplier') {
      setVehicleRef('');
      setVehicleId('');
    }
  };

  const handleVehicleChange = (value) => {
    const match = filteredVehicles.find((vehicle) => {
      const label = buildVehicleLabel(vehicle);
      return normalizeText(label) === normalizeText(value)
        || normalizeText(vehicle?.plateNumber) === normalizeText(value)
        || normalizeText(vehicle?.fileNumber) === normalizeText(value);
    });

    setVehicleRef(match?.plateNumber || match?.fileNumber || value);
    setVehicleId(match?.id || '');
    if (match?.customerName) {
      setPartyName(match.customerName);
      setPartyId(match?.customerId || '');
    }
  };

  const appendDigit = (digit) => {
    setAmount((previous) => {
      if (digit === '.' && String(previous).includes('.')) return previous;
      if (String(previous) === '0' && digit !== '.') return String(digit);
      return `${previous || ''}${digit}`;
    });
  };

  const backspaceAmount = () => setAmount((previous) => String(previous || '').slice(0, -1));
  const clearAmount = () => setAmount('');

  const applyCatalogItem = (catalogItem) => {
    setItemDraft((previous) => ({
      ...previous,
      name: catalogItem?.name || previous.name,
      itemType: catalogItem?.itemType || previous.itemType,
      price: String(catalogItem?.price ?? previous.price ?? ''),
    }));
  };

  const handleItemNameChange = (value) => {
    const match = catalogItems.find((item) => normalizeText(item.name) === normalizeText(value));
    setItemDraft((previous) => ({
      ...previous,
      name: value,
      price: match ? String(match.price) : previous.price,
      itemType: match?.itemType || previous.itemType,
    }));
  };

  const addItem = () => {
    const name = String(itemDraft.name || '').trim();
    const price = roundAmount(itemDraft.price);
    const qty = Math.max(1, Number(itemDraft.qty) || 1);
    if (!name || !(price > 0)) return;

    setItems((previous) => ([
      ...previous,
      {
        id: `${Date.now()}-${Math.random()}`,
        name,
        price,
        qty,
        itemType: itemDraft.itemType || 'service',
      },
    ]));
    setItemDraft({ name: '', price: '', qty: 1, itemType: 'service' });
  };

  const removeItem = (id) => {
    setItems((previous) => previous.filter((item) => item.id !== id));
  };

  const resetFormAfterSave = () => {
    setAmount('');
    setNote('');
    setPartyName('');
    setPartyId('');
    setVehicleRef('');
    setVehicleId('');
    setItems([]);
    setItemDraft({ name: '', price: '', qty: 1, itemType: 'service' });
  };

  const findOpenVehicleOperationForCollection = async () => {
    if (!vehicleId) return null;
    const response = await axios.get(`${apiBase}/operations`, {
      params: { vehicle_id: vehicleId, limit: 50 },
    });
    const rows = normalizeArray(response?.data);
    const candidates = rows
      .filter((operation) => ['sale', 'service'].includes(String(operation?.type || '').toLowerCase()))
      .map((operation) => {
        const total = Number(operation?.workshopTotal ?? operation?.total ?? 0) || 0;
        const paid = Number(operation?.totalPaid ?? operation?.paymentAmount ?? 0) || 0;
        const balance = Number(operation?.balance ?? Math.max(total - paid, 0)) || 0;
        return { ...operation, _balance: roundAmount(balance) };
      })
      .filter((operation) => operation._balance > 0.009)
      .sort((a, b) => String(b.date || b.createdAt || '').localeCompare(String(a.date || a.createdAt || '')));
    return candidates[0] || null;
  };

  const buildPosOperationPayload = () => {
    const cleanPartyName = String(partyName || '').trim();
    const cleanVehicleRef = String(vehicleRef || '').trim();
    const total = roundAmount(effectiveAmount);
    const itemSummary = items.map((item) => `${item.name}×${item.qty}`).join('، ');
    const descriptionParts = [
      activeTemplate?.title || 'عملية POS',
      itemSummary,
      note,
    ].filter(Boolean);
    const notes = [
      descriptionParts.join(' — '),
      cleanPartyName ? `[PARTY:${cleanPartyName}] [PARTY_TYPE:${activeTemplate?.partyRole || 'open'}]` : '',
      cleanVehicleRef ? `[VEHICLE_REF:${cleanVehicleRef}]` : '',
      '[SOURCE:SMART_POS]',
    ].filter(Boolean).join(' ').trim();

    const defaultItemName = note || activeTemplate?.title || 'بند POS';
    const operationItems = (activeTemplate?.supportsItems && items.length > 0)
      ? items.map((item) => ({
          name: item.name,
          itemType: item.itemType || 'service',
          quantity: Number(item.qty || 1),
          price: roundAmount(item.price),
          total: roundAmount((Number(item.qty || 1) * Number(item.price || 0))),
        }))
      : [{
          name: defaultItemName,
          itemType: activeTemplate?.transactionType === 'expense' ? 'service' : 'service',
          quantity: 1,
          price: total,
          total,
        }];

    if (activeTemplate?.transactionType === 'settlement') {
      let itemName = 'تسوية عبر POS';
      if (activeTemplate?.key === 'pay_supplier') itemName = 'سداد لمورد عبر POS';
      else if (activeTemplate?.key === 'collect_customer') itemName = 'تحصيل من عميل عبر POS';
      else if (activeTemplate?.key === 'receipt_voucher') itemName = 'سند قبض عبر POS';

      return {
        type: 'payment_order',
        originalType: activeTemplate?.transactionType,
        operationKind: vehicleId ? 'VEHICLE_OPERATION' : 'WORKSHOP_OPERATION',
        scope: vehicleId ? 'vehicle' : 'workshop',
        vehicleId: vehicleId || null,
        partnerType: activeTemplate?.partyRole || 'customer',
        partnerId: partyId || null,
        partnerName: cleanPartyName || null,
        paymentMethod,
        paymentStatus: 'paid',
        paymentAmount: total,
        items: [{
          name: itemName,
          itemType: 'service',
          quantity: 1,
          price: total,
          total,
        }],
        notes,
        workshopId,
        date: new Date().toISOString().slice(0, 10),
        accountingAccountId: activeTemplate?.partyRole === 'supplier' ? accountRefs.suppliers.code : accountRefs.customers.code,
      };
    }

    return {
      type: activeTemplate?.transactionType === 'expense' ? 'expense' : 'sale',
      operationKind: vehicleId ? 'VEHICLE_OPERATION' : 'WORKSHOP_OPERATION',
      scope: vehicleId ? 'vehicle' : 'workshop',
      vehicleId: vehicleId || null,
      partnerType: activeTemplate?.partyRole || (activeTemplate?.transactionType === 'expense' ? 'supplier' : 'customer'),
      partnerId: partyId || null,
      partnerName: cleanPartyName || null,
      paymentMethod,
      paymentStatus: 'paid',
      items: operationItems,
      notes,
      workshopId,
      date: new Date().toISOString().slice(0, 10),
      accountingAccountId: activeTemplate?.transactionType === 'expense'
        ? effectiveEntry.debitAccount?.code
        : effectiveEntry.creditAccount?.code,
    };
  };

  const handleSave = async () => {
    if (!isValid || saving) return;
    setSaving(true);
    setSavedToast(null);

    try {
      if (activeTemplate?.key === 'collect_customer' && vehicleId) {
        const targetOperation = await findOpenVehicleOperationForCollection();
        if (!targetOperation?.id) {
          setSavedToast({ ok: false, error: 'لا توجد عملية آجل مفتوحة لهذه المركبة. لن يتم إنشاء عملية تحصيل منفصلة حتى لا يتكرر السعر.' });
          return;
        }

        const total = roundAmount(effectiveAmount);
        const idemKey = generateIdempotencyKey('pos-collect', targetOperation.id);
        const response = await axios.post(
          `${apiBase}/operations/${targetOperation.id}/confirm-payment`,
          {
            amount: total,
            paymentMethod,
            payment_method: paymentMethod,
            workshopId,
            date: new Date().toISOString().slice(0, 10),
            notes: note || 'تحصيل من POS مرتبط بالعملية الأصلية',
          },
          { headers: { 'Idempotency-Key': idemKey } }
        );

        resetFormAfterSave();
        setSavedToast({ ok: true, total, message: 'تم تسجيل التحصيل على العملية الأصلية بدون إنشاء عملية جديدة.' });
        if (typeof onSaved === 'function') onSaved(response.data);
        return;
      }

      if (activeTemplate?.key !== 'bank_deposit') {
        const operationPayload = buildPosOperationPayload();
        const operationResponse = await axios.post(`${apiBase}/operations`, operationPayload);
        if (operationResponse?.data?.id) {
          resetFormAfterSave();
          setSavedToast({ ok: true, total: roundAmount(effectiveAmount) });
          if (typeof onSaved === 'function') onSaved(operationResponse.data);
          return;
        }
      }

      const cleanPartyName = String(partyName || '').trim();
      const cleanVehicleRef = String(vehicleRef || '').trim();
      const itemSummary = items.map((item) => `${item.name}×${item.qty}`).join('، ');
      const descriptionParts = [
        activeTemplate?.title || 'قيد ذكي',
        itemSummary,
        note,
      ].filter(Boolean);

      const description = [
        descriptionParts.join(' — '),
        cleanPartyName ? `[PARTY:${cleanPartyName}] [PARTY_TYPE:${activeTemplate?.partyRole || 'open'}]` : '',
        cleanVehicleRef ? `[VEHICLE_REF:${cleanVehicleRef}]` : '',
      ].filter(Boolean).join(' ').trim();

      const total = roundAmount(effectiveAmount);
      const payload = {
        date: new Date().toISOString().slice(0, 10),
        description,
        transaction_type: activeTemplate?.transactionType || 'manual',
        source: activeTemplate?.key === 'instant_sale' ? 'pos_instant_sale' : 'pos_template',
        total,
        reference_id: vehicleId || partyId || undefined,
        lines: [
          {
            account: effectiveEntry.debitAccount?.code,
            account_name: effectiveEntry.debitAccount?.name,
            debit: total,
            credit: 0,
          },
          {
            account: effectiveEntry.creditAccount?.code,
            account_name: effectiveEntry.creditAccount?.name,
            debit: 0,
            credit: total,
          },
        ],
      };

      const response = await axios.post(`${apiBase}/finance/journal-entries`, payload, {
        params: { workshop_id: workshopId },
      });

      if (response?.data?.success || response?.data?.id) {
        resetFormAfterSave();
        setSavedToast({ ok: true, total });
        if (typeof onSaved === 'function') onSaved(response.data);
        // 🔄 إشعار باقي الصفحات بالتحديث
        try {
          window.dispatchEvent(new CustomEvent('finance:updated', {
            detail: { source: 'pos_journal', total }
          }));
        } catch (evtErr) { console.warn('finance:updated dispatch failed', evtErr); }
      } else {
        setSavedToast({ ok: false, error: 'استجابة غير متوقعة من الخادم' });
      }
    } catch (error) {
      setSavedToast({
        ok: false,
        error: error?.response?.data?.detail || error?.response?.data?.message || error?.message || 'تعذر حفظ القيد',
      });
    } finally {
      setSaving(false);
      window.setTimeout(() => setSavedToast(null), 4500);
    }
  };

  const copyFromRecent = (entry) => {
    const lines = normalizeArray(entry?.lines);
    const debitLine = lines.find((line) => Number(line?.debit) > 0);
    const creditLine = lines.find((line) => Number(line?.credit) > 0);
    if (!debitLine || !creditLine) return;

    const paymentAccountByCode = {
      [accountRefs.cash.code]: 'cash',
      [accountRefs.bank.code]: 'bank',
      [accountRefs.pos.code]: 'pos',
    };

    let templateKey = 'instant_sale';
    if (debitLine.account === accountRefs.suppliers.code) templateKey = 'pay_supplier';
    else if (creditLine.account === accountRefs.customers.code) templateKey = 'collect_customer';
    else if (debitLine.account === accountRefs.salaryExpense.code) templateKey = 'salary';
    else if (debitLine.account === accountRefs.operatingExpense.code) templateKey = 'purchase';
    else if (debitLine.account === accountRefs.bank.code && creditLine.account === accountRefs.cash.code) templateKey = 'bank_deposit';
    else if (creditLine.account === accountRefs.salesRevenue.code || creditLine.account === accountRefs.mechanicalRevenue.code) {
      templateKey = 'instant_sale';
    }

    setActiveTemplateKey(templateKey);
    setPaymentMethod(paymentAccountByCode[debitLine.account] || paymentAccountByCode[creditLine.account] || 'cash');
    setAmount(String(roundAmount(entry?.total || debitLine?.debit || creditLine?.credit || 0)));
    setNote(stripTokens(entry?.description || ''));
    setPartyName(extractToken(entry?.description || '', 'PARTY'));
    setVehicleRef(extractToken(entry?.description || '', 'VEHICLE_REF'));
    setItems([]);
  };

  const tone = toneClasses(activeTemplate?.color || 'slate');
  const showItemsSection = Boolean(activeTemplate?.supportsItems);
  const showPartyField = Boolean(activeTemplate?.partyRole);
  const showVehicleField = Boolean(activeTemplate?.supportsVehicle);
  const showPaymentMethods = activeTemplate?.paymentSide !== 'static';

  return (
    <div className="space-y-5" dir="rtl" data-testid="pos-journal-root">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl sm:text-3xl font-black text-white" data-testid="pos-journal-title">الـ POS الذكي</h2>
          <p className="text-sm text-slate-300 max-w-2xl" data-testid="pos-journal-subtitle">
            شاشة واحدة لإنشاء بيع فوري ورواتب وتسويات سريعة مع حقول العميل والمركبة والبنود.
          </p>
        </div>

        <div
          className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-slate-300"
          data-testid="pos-lookups-status"
        >
          {lookupsLoading ? 'جاري تحميل العملاء والمركبات والبنود...' : `جاهز: ${customers.length} عميل · ${vehicles.length} مركبة · ${catalogItems.length} بند`}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3" data-testid="pos-templates-grid">
        {templates.map((template) => {
          const templateTone = toneClasses(template.color);
          const isActive = template.key === activeTemplate?.key;
          return (
            <button
              key={template.key}
              type="button"
              onClick={() => setActiveTemplateKey(template.key)}
              data-testid={`pos-template-${template.key}`}
              className={`rounded-[22px] border bg-gradient-to-br p-4 text-right transition ${templateTone.bg} ${templateTone.border} ${templateTone.text} ${isActive ? `ring-2 ${templateTone.ring}` : 'opacity-80 hover:opacity-100'}`}
            >
              <div className="text-lg font-bold leading-tight">{template.title}</div>
              <div className="mt-1 text-xs opacity-80 leading-6">{template.desc}</div>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.4fr)_360px] gap-4 items-start">
        <div className="space-y-4">
          <div className={`rounded-[28px] border bg-gradient-to-br ${tone.bg} ${tone.border} p-5`} data-testid="pos-amount-display">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-[11px] uppercase tracking-[0.25em] text-slate-300/80 mb-2">إجمالي الحركة</div>
                <div className={`text-4xl sm:text-5xl lg:text-6xl font-black tabular-nums ${tone.text}`} data-testid="pos-amount-value">
                  {formatSAR(effectiveAmount)}
                </div>
              </div>

              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-slate-100" data-testid="pos-entry-accounts">
                  مدين {effectiveEntry.debitAccount?.code} ↔ دائن {effectiveEntry.creditAccount?.code}
                </span>
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-slate-100" data-testid="pos-items-count">
                  البنود: {items.length}
                </span>
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-slate-100" data-testid="pos-selected-party">
                  الطرف: {partyName || 'مفتوح'}
                </span>
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-slate-100" data-testid="pos-selected-vehicle">
                  المركبة: {vehicleRef || 'غير محددة'}
                </span>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-3 text-sm text-slate-200">
              <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-3 flex flex-col justify-center">
                <div className="text-xs text-slate-400 mb-1 flex justify-between items-center">
                  <span>الحساب المدين</span>
                  {activeTemplateKey === 'purchase' && !isEditingDebit && (
                    <button type="button" onClick={() => setIsEditingDebit(true)} className="text-sky-400 hover:text-sky-300 text-[10px] flex items-center gap-1">
                      <Pencil size={10} /> تعديل
                    </button>
                  )}
                  {isEditingDebit && (
                    <button type="button" onClick={() => setIsEditingDebit(false)} className="text-slate-400 hover:text-slate-300 text-[10px]">
                      إلغاء
                    </button>
                  )}
                </div>
                {activeTemplateKey === 'purchase' && isEditingDebit ? (
                  <div className="mt-1 relative z-50">
                    <SmartAccountSelect
                      allAccounts={accounts.filter((a) => a.type === 'expense' || String(a.code).startsWith('03') || String(a.code).startsWith('01') || String(a.code).startsWith('5') || String(a.code).startsWith('6'))}
                      includeAll={true}
                      value={customPurchaseAccountId || effectiveEntry.debitAccount?.id}
                      onChange={(account) => {
                        if (account) setCustomPurchaseAccountId(account.id);
                        setIsEditingDebit(false);
                      }}
                      compact={true}
                      className="w-full"
                    />
                  </div>
                ) : (
                  <div className="font-semibold">{effectiveEntry.debitAccount?.code} · {effectiveEntry.debitAccount?.name}</div>
                )}
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-3 flex flex-col justify-center">
                <div className="text-xs text-slate-400 mb-1">الحساب الدائن</div>
                <div className="font-semibold">{effectiveEntry.creditAccount?.code} · {effectiveEntry.creditAccount?.name}</div>
              </div>
            </div>
          </div>

          <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {showPartyField ? (
                <div>
                  <label className="mb-2 block text-sm text-slate-200">
                    {activeTemplate?.partyRole === 'supplier' ? 'المورد' : 'العميل'}
                  </label>
                  <div className="relative">
                    <UserRound className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                    <input
                      type="text"
                      value={partyName}
                      list={`pos-party-options-${activeTemplate?.partyRole || 'open'}`}
                      onChange={(event) => handlePartyChange(event.target.value)}
                      placeholder={activeTemplate?.partyRole === 'supplier' ? 'اختر مورد أو اكتب الاسم' : 'اختر عميل أو اكتب الاسم'}
                      data-testid="pos-party-input"
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/40 py-3 pr-10 pl-4 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                    />
                    <datalist id={`pos-party-options-${activeTemplate?.partyRole || 'open'}`}>
                      {partyOptions.map((party, index) => (
                        <option key={party?.id || `party-${index}`} value={party?.name || ''} />
                      ))}
                    </datalist>
                  </div>
                </div>
              ) : null}

              {showVehicleField ? (
                <div>
                  <label className="mb-2 block text-sm text-slate-200">المركبة</label>
                  <div className="relative">
                    <CarFront className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                    <input
                      type="text"
                      value={vehicleRef}
                      list="pos-vehicle-options"
                      onChange={(event) => handleVehicleChange(event.target.value)}
                      placeholder="اختر مركبة أو اكتب رقم اللوحة"
                      data-testid="pos-vehicle-input"
                      className="w-full rounded-2xl border border-white/10 bg-slate-950/40 py-3 pr-10 pl-4 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                    />
                    <datalist id="pos-vehicle-options">
                      {filteredVehicles.map((vehicle, index) => (
                        <option key={vehicle?.id || `vehicle-${index}`} value={buildVehicleLabel(vehicle)} />
                      ))}
                    </datalist>
                  </div>
                </div>
              ) : null}
            </div>

            <div>
              <label className="mb-2 block text-sm text-slate-200">المبلغ اليدوي</label>
              <input
                type="number"
                inputMode="decimal"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder={showItemsSection ? 'اختياري — يُستخدم عند عدم وجود بنود' : 'أدخل المبلغ'}
                data-testid="pos-amount-input"
                className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-lg tabular-nums text-slate-100 outline-none transition focus:border-cyan-400/50"
              />
              {showItemsSection && items.length > 0 ? (
                <p className="mt-2 text-xs text-emerald-200" data-testid="pos-items-total-hint">
                  يتم اعتماد مجموع البنود تلقائياً: {formatSAR(itemsTotal)}
                </p>
              ) : null}
            </div>

            {showPaymentMethods ? (
              <div>
                <label className="mb-2 block text-sm text-slate-200">طريقة الدفع</label>
                <div className="flex flex-wrap gap-2" data-testid="pos-payment-method-row">
                  {PAYMENT_METHODS.map((method) => {
                    const Icon = method.icon;
                    const isActive = paymentMethod === method.key;
                    return (
                      <button
                        key={method.key}
                        type="button"
                        onClick={() => setPaymentMethod(method.key)}
                        data-testid={`pos-payment-method-${method.key}`}
                        className={`rounded-full border px-4 py-2 text-sm transition ${isActive ? 'border-cyan-400/40 bg-cyan-500/20 text-cyan-50' : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10'}`}
                      >
                        <Icon size={14} className="inline-block ml-1" />
                        {method.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}

            <div>
              <label className="mb-2 block text-sm text-slate-200">ملاحظة</label>
              <input
                type="text"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="مثال: دفعة فورية / راتب أبريل / تحصيل فاتورة"
                data-testid="pos-note-input"
                className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
              />
            </div>

            <div className="grid grid-cols-4 gap-2" data-testid="pos-numpad">
              {['7', '8', '9', 'C', '4', '5', '6', '⌫', '1', '2', '3', '.', '0', '00', '000', 'OK'].map((key) => {
                const handleClick = () => {
                  if (key === 'C') return clearAmount();
                  if (key === '⌫') return backspaceAmount();
                  if (key === 'OK') return handleSave();
                  return appendDigit(key);
                };

                return (
                  <button
                    key={key}
                    type="button"
                    onClick={handleClick}
                    disabled={key === 'OK' && (!isValid || saving)}
                    data-testid={`pos-numpad-${key === '⌫' ? 'backspace' : key === '.' ? 'dot' : key.toLowerCase()}`}
                    className={`h-12 rounded-2xl border text-lg font-bold transition ${key === 'OK' ? 'border-emerald-300/40 bg-emerald-500/30 text-emerald-50 disabled:opacity-40' : key === 'C' ? 'border-rose-300/30 bg-rose-500/15 text-rose-100' : key === '⌫' ? 'border-amber-300/30 bg-amber-500/15 text-amber-100' : 'border-white/10 bg-white/5 text-slate-100 hover:bg-white/10'}`}
                  >
                    {key}
                  </button>
                );
              })}
            </div>
          </div>

          {showItemsSection ? (
            <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-4 space-y-4" data-testid="pos-items-section">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-white font-semibold">
                    <ShoppingCart size={16} />
                    البنود
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    تم دمج سلة الكاشير داخل هذا القسم — أضف خدمات أو قطع أو بنود رواتب ثم احفظ مباشرة.
                  </p>
                </div>

                <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs text-slate-200" data-testid="pos-items-total-badge">
                  إجمالي البنود: {formatSAR(itemsTotal)}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-12 gap-2">
                <div className="md:col-span-2">
                  <select
                    value={itemDraft.itemType}
                    onChange={(event) => setItemDraft((previous) => ({ ...previous, itemType: event.target.value }))}
                    data-testid="pos-item-type-select"
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-3 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                  >
                    <option value="service">خدمة</option>
                    <option value="part">قطعة</option>
                    <option value="custom">مخصص</option>
                  </select>
                </div>

                <div className="md:col-span-5">
                  <input
                    type="text"
                    value={itemDraft.name}
                    list="pos-item-catalog"
                    onChange={(event) => handleItemNameChange(event.target.value)}
                    placeholder={activeTemplate?.key === 'salary' ? 'اسم الموظف أو البدل' : 'اسم الخدمة أو القطعة'}
                    data-testid="pos-item-name-input"
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-400/50"
                  />
                  <datalist id="pos-item-catalog">
                    {catalogItems.map((item) => (
                      <option key={item.id} value={item.name} />
                    ))}
                  </datalist>
                </div>

                <div className="md:col-span-2">
                  <input
                    type="number"
                    value={itemDraft.price}
                    onChange={(event) => setItemDraft((previous) => ({ ...previous, price: event.target.value }))}
                    placeholder="السعر"
                    data-testid="pos-item-price-input"
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm tabular-nums text-slate-100 outline-none transition focus:border-cyan-400/50"
                  />
                </div>

                <div className="md:col-span-1">
                  <input
                    type="number"
                    min="1"
                    value={itemDraft.qty}
                    onChange={(event) => setItemDraft((previous) => ({ ...previous, qty: event.target.value }))}
                    placeholder="1"
                    data-testid="pos-item-qty-input"
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm tabular-nums text-slate-100 outline-none transition focus:border-cyan-400/50"
                  />
                </div>

                <div className="md:col-span-2">
                  <button
                    type="button"
                    onClick={addItem}
                    disabled={!itemDraft.name || !(roundAmount(itemDraft.price) > 0)}
                    data-testid="pos-item-add-button"
                    className="flex h-full w-full items-center justify-center gap-2 rounded-2xl border border-emerald-300/40 bg-emerald-500/25 px-4 py-3 text-sm font-semibold text-emerald-50 transition disabled:opacity-40"
                  >
                    <Plus size={16} />
                    إضافة
                  </button>
                </div>
              </div>

              {suggestedCatalogItems.length > 0 ? (
                <div className="flex flex-wrap gap-2" data-testid="pos-item-suggestions-row">
                  {suggestedCatalogItems.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => applyCatalogItem(item)}
                      data-testid={`pos-item-suggestion-${item.id}`}
                      className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 transition hover:bg-white/10"
                    >
                      <Sparkles size={12} className="inline-block ml-1" />
                      {item.name} · {formatSAR(item.price)}
                    </button>
                  ))}
                </div>
              ) : null}

              {items.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 bg-black/10 px-4 py-6 text-center text-sm text-slate-400" data-testid="pos-items-empty-state">
                  لا توجد بنود بعد — أضف البنود ليُحسب الإجمالي تلقائياً.
                </div>
              ) : (
                <div className="space-y-2" data-testid="pos-items-list">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-black/15 px-4 py-3"
                      data-testid={`pos-item-row-${item.id}`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold text-slate-100">{item.name}</div>
                        <div className="text-xs text-slate-400">{item.itemType === 'part' ? 'قطعة' : item.itemType === 'custom' ? 'مخصص' : 'خدمة'} · {item.qty} × {formatSAR(item.price)}</div>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="text-sm font-semibold tabular-nums text-emerald-200">{formatSAR(item.price * item.qty)}</div>
                        <button
                          type="button"
                          onClick={() => removeItem(item.id)}
                          data-testid={`pos-item-remove-${item.id}`}
                          className="rounded-full border border-rose-300/30 bg-rose-500/10 p-2 text-rose-100 transition hover:bg-rose-500/20"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : null}

          <button
            type="button"
            onClick={handleSave}
            disabled={!isValid || saving}
            data-testid="pos-save-button"
            className="flex w-full items-center justify-center gap-2 rounded-[24px] border border-emerald-300/40 bg-emerald-500/30 px-4 py-4 text-base font-bold text-emerald-50 transition hover:bg-emerald-500/40 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
            {saving ? 'جاري حفظ القيد...' : `حفظ القيد الآن (${formatSAR(effectiveAmount)})`}
          </button>

          {savedToast ? (
            <div
              data-testid="pos-save-toast"
              className={`rounded-2xl border px-4 py-3 text-sm ${savedToast.ok ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-100' : 'border-rose-400/30 bg-rose-500/10 text-rose-100'}`}
            >
              {savedToast.ok ? (savedToast.message || `تم حفظ القيد المتوازن بنجاح بقيمة ${formatSAR(savedToast.total)}`) : savedToast.error}
            </div>
          ) : null}
        </div>

        <div className="rounded-[26px] border border-white/10 bg-white/[0.04] p-4" data-testid="pos-recent-entries-panel">
          <div className="mb-3 flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-400">
            <HandCoins size={14} />
            آخر القيود
          </div>

          {effectiveRecentEntries.length === 0 && recentEntriesLoading ? (
            <div className="rounded-2xl border border-cyan-300/15 bg-cyan-500/10 px-4 py-8 text-center text-sm text-cyan-100" data-testid="pos-recent-entries-loading">
              جاري تحميل آخر القيود...
            </div>
          ) : effectiveRecentEntries.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 bg-black/10 px-4 py-8 text-center text-sm text-slate-500" data-testid="pos-recent-entries-empty">
              لا توجد قيود سابقة للنسخ.
            </div>
          ) : (
            <div className="space-y-2 max-h-[720px] overflow-y-auto pr-1">
              {effectiveRecentEntries.slice(0, 5).map((entry, index) => (
                <div
                  key={entry?.id || `recent-${index}`}
                  className="rounded-2xl border border-white/10 bg-black/15 p-3"
                  data-testid={`pos-recent-entry-row-${entry?.id || index}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0 flex-1 text-sm font-semibold leading-6 text-slate-100" title={stripTokens(entry?.description || '')}>
                          {stripTokens(entry?.description || 'قيد')}
                        </div>
                        <div
                          className="shrink-0 rounded-full border border-emerald-300/30 bg-emerald-500/15 px-3 py-1 text-sm font-bold tabular-nums text-emerald-100"
                          data-testid={`pos-recent-entry-amount-${entry?.id || index}`}
                        >
                          {formatSAR(entry?.total)}
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
                        <span>{entry?.date || ''}</span>
                        <span>•</span>
                        <span>{labelFromMap(entry?.source, SOURCE_LABELS, 'قيد يومية')}</span>
                        {(entry?.payment_method || entry?.paymentMethod || entry?.payment_method_label_ar) ? (
                          <>
                            <span>•</span>
                            <span>{entry?.payment_method_label_ar || labelFromMap(entry?.payment_method || entry?.paymentMethod, PAYMENT_METHOD_LABELS, '')}</span>
                          </>
                        ) : null}
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => copyFromRecent(entry)}
                      data-testid={`pos-recent-entry-copy-${entry?.id || index}`}
                      className="rounded-full border border-cyan-300/30 bg-cyan-500/10 p-2 text-cyan-100 transition hover:bg-cyan-500/20"
                    >
                      <Copy size={14} />
                    </button>
                  </div>

                  <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-slate-300">
                    <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                      الطرف: {resolveRecentParty(entry)}
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                      المركبة: {resolveRecentVehicle(entry)}
                    </div>
                    {recentEntryLinesSummary(entry) ? (
                      <div className="rounded-xl border border-cyan-300/15 bg-cyan-500/10 px-3 py-2 text-cyan-50" data-testid={`pos-recent-entry-lines-${entry?.id || index}`}>
                        القيد: {recentEntryLinesSummary(entry)}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900/80 to-cyan-950/40 p-4" data-testid="pos-smart-summary-panel">
            <div className="mb-2 flex items-center gap-2 text-white font-semibold">
              <Wallet size={16} />
              ملخص الذكاء الحالي
            </div>
            <ul className="space-y-2 text-sm text-slate-300 leading-7">
              <li>• البيع الفوري والبيع النقدي أصبحا في نفس الشاشة.</li>
              <li>• تمت إضافة قالب رواتب وربط العميل/المركبة والبنود.</li>
              <li>• الحفظ يرسل قيداً متوازناً مباشرة إلى دفتر اليومية.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}