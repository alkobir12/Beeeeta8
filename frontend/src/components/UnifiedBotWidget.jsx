/**
 * UnifiedBotWidget — بوت موحد يجمع:
 * 1. المساعد الذكي (Workshop AI)
 * 2. المدقق المالي (Finance Auditor)
 * 3. نقطة بيع ذكية + إنشاء قيد/عملية بربط تلقائي للحسابات
 */
import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  Bot, X, MessageSquare, Plus, Send, Loader,
  FileText, Wrench, Zap, CreditCard, ShoppingBag, DollarSign,
  Users, Package, TrendingUp, AlertCircle, CheckCircle, ChevronDown
} from 'lucide-react';
import axios from 'axios';
import { PAYMENT_METHOD_LABELS, labelFromMap } from '../utils/displayLabels';

const API = process.env.REACT_APP_BACKEND_URL;
const WID = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';

// ─── خريطة الحسابات (الأكواد الحالية من الدليل الحي) ───────────────────────
const ACCOUNTS = {
  '003': 'النقد',   '004': 'البنك',     '005': 'العملاء',
  '006': 'نقاط بيع','026': 'خدمات ميكانيكية','027': 'إصلاح محركات',
  '028': 'فرامل وتعليق','029': 'تكلفة الخدمات','034': 'المصروفات التشغيلية',
  '035': 'مصروفات عامة','036': 'رواتب','041': 'ايراد قطع الورشه',
  '167': 'تكلفة قطع الورشة',
  '2101': 'الموردون (آجل)', '166': 'فروقات ترحيل',
};

// حسابات خاصة تظهر في قائمة الاختيار
const SPECIAL_ACCOUNTS = [
  { code: '041', name: 'ايراد قطع الورشه', group: 'الورشة' },
  { code: '167', name: 'تكلفة قطع الورشة', group: 'الورشة' },
  { code: '026', name: 'إيرادات خدمات ميكانيكية', group: 'الورشة' },
  { code: '027', name: 'إيرادات إصلاح محركات', group: 'الورشة' },
  { code: '028', name: 'إيرادات فرامل وتعليق', group: 'الورشة' },
  { code: '034', name: 'المصروفات التشغيلية', group: 'مصروفات' },
  { code: '035', name: 'مصروفات عامة وإدارية', group: 'مصروفات' },
  { code: '036', name: 'رواتب إدارية', group: 'مصروفات' },
  { code: '005', name: 'العملاء (ذمم مدينة)', group: 'حسابات' },
  { code: '2101', name: 'الموردون (آجل)', group: 'حسابات' },
];

const PAYMENT_ACCOUNT = { bank: '004', cash: '003', pos: '006', credit: '005' };

// ─── نماذج العمليات الذكية ──────────────────────────────────────────────────
const SMART_TEMPLATES = [
  {
    id: 'service_sale',
    label: 'بيع خدمة',
    icon: Wrench,
    color: '#38bdf8',
    desc: 'صيانة / خدمة ميكانيكية',
    getLines: (pm, amt) => [
      { account: PAYMENT_ACCOUNT[pm] || '004', name: ACCOUNTS[PAYMENT_ACCOUNT[pm]] || 'البنك', debit: amt, credit: 0 },
      { account: '026', name: 'خدمات ميكانيكية', debit: 0, credit: amt },
    ],
    opType: 'sale',
  },
  {
    id: 'parts_sale',
    label: 'بيع قطع',
    icon: Package,
    color: '#a78bfa',
    desc: 'قطع غيار ورشة',
    getLines: (pm, amt) => [
      { account: PAYMENT_ACCOUNT[pm] || '004', name: ACCOUNTS[PAYMENT_ACCOUNT[pm]] || 'البنك', debit: amt, credit: 0 },
      { account: '041', name: 'ايراد قطع الورشه', debit: 0, credit: amt },
    ],
    opType: 'sale',
  },
  {
    id: 'expense',
    label: 'مصروف',
    icon: TrendingUp,
    color: '#fb923c',
    desc: 'مصروف تشغيلي / إداري',
    getLines: (pm, amt) => [
      { account: '035', name: 'مصروفات عامة', debit: amt, credit: 0 },
      { account: PAYMENT_ACCOUNT[pm] || '004', name: ACCOUNTS[PAYMENT_ACCOUNT[pm]] || 'البنك', debit: 0, credit: amt },
    ],
    opType: 'expense',
  },
  {
    id: 'salary',
    label: 'رواتب',
    icon: Users,
    color: '#34d399',
    desc: 'رواتب الموظفين / العمال',
    getLines: (pm, amt) => [
      { account: '036', name: 'رواتب', debit: amt, credit: 0 },
      { account: PAYMENT_ACCOUNT[pm] || '004', name: ACCOUNTS[PAYMENT_ACCOUNT[pm]] || 'البنك', debit: 0, credit: amt },
    ],
    opType: 'expense',
  },
  {
    id: 'credit_sale',
    label: 'بيع آجل',
    icon: CreditCard,
    color: '#f59e0b',
    desc: 'خدمة بالآجل (ذمة مدينة)',
    getLines: (_pm, amt) => [
      { account: '005', name: 'العملاء (ذمم مدينة)', debit: amt, credit: 0 },
      { account: '026', name: 'خدمات ميكانيكية', debit: 0, credit: amt },
    ],
    opType: 'sale',
    forcePayment: 'credit',
  },
  {
    id: 'purchase',
    label: 'مشتريات',
    icon: ShoppingBag,
    color: '#64748b',
    desc: 'شراء قطع / مواد من مورد',
    getLines: (pm, amt) => [
      { account: '029', name: 'تكلفة الخدمات', debit: amt, credit: 0 },
      { account: pm === 'credit' ? '2101' : PAYMENT_ACCOUNT[pm] || '004',
        name: pm === 'credit' ? 'الموردون (آجل)' : ACCOUNTS[PAYMENT_ACCOUNT[pm]] || 'البنك', debit: 0, credit: amt },
    ],
    opType: 'purchase',
  },
];

// اقتراح النموذج من الوصف النصي
const guessTemplate = (text) => {
  const t = text.toLowerCase();
  if (/راتب|رواتب|أجر|عمال/.test(t)) return 'salary';
  if (/قطع|فلتر|زيت|مرشح/.test(t)) return 'parts_sale';
  if (/آجل|اجل|ذمة|دين/.test(t)) return 'credit_sale';
  if (/شراء|مشتري|مورد|فاتورة شراء/.test(t)) return 'purchase';
  if (/مصروف|مصاريف|بنزين|فطور|إيجار|كهرباء|ماء/.test(t)) return 'expense';
  if (/صيانة|خدمة|فرامل|كلتش|تعليق|مكيف/.test(t)) return 'service_sale';
  return null;
};

// ─── محرك الأوامر الإدارية ─────────────────────────────────────────────────
const ADMIN_PATTERNS = [
  {
    match: (t) => /الوضع العام|ملخص مالي|وضع الورشه|وضع الورشة|الوضع الراهن|كيف الوضع/.test(t),
    label: 'الوضع العام',
    handler: async (finCtx) => {
      if (!finCtx) return null;
      const margin = finCtx.revenue > 0 ? ((finCtx.net / finCtx.revenue) * 100).toFixed(1) : 0;
      const status = finCtx.net > 0 ? '✅ الورشة تحقق ربحاً' : '⚠️ الورشة في منطقة خسارة';
      return `${status}\n\n` +
        `💰 الإيرادات: ${finCtx.revenue.toLocaleString('ar-SA')} ر.س\n` +
        `📉 المصروفات: ${finCtx.expenses.toLocaleString('ar-SA')} ر.س\n` +
        `📊 صافي الدخل: ${finCtx.net.toLocaleString('ar-SA')} ر.س\n` +
        `📈 هامش الربح: ${margin}%\n\n` +
        (finCtx.alerts.length ? `⚠️ تنبيهات: ${finCtx.alerts.map(a => a.title).join(' | ')}` : '✅ لا تنبيهات مالية');
    },
  },
  {
    match: (t) => /الذمم|ذمم|آجل|اجل|عملاء آجل|ديون عملاء|ماذا يدين|من يدين/.test(t),
    label: 'الذمم المدينة',
    handler: async () => {
      const r = await axios.get(`${API}/api/finance/reports/trial-balance?workshop_id=${WID}`);
      const accounts = r.data?.data?.accounts || [];
      const AR_CODES = ['005', '1103', '113'];
      const arAccounts = accounts.filter(a => AR_CODES.some(c => String(a.code||'').startsWith(c)));
      const arTotal = arAccounts.reduce((s, a) => s + (Number(a.debit || 0) - Number(a.credit || 0)), 0);
      const AP_CODES = ['2101', '211'];
      const apAccounts = accounts.filter(a => AP_CODES.some(c => String(a.code||'').startsWith(c)));
      const apTotal = apAccounts.reduce((s, a) => s + (Number(a.credit || 0) - Number(a.debit || 0)), 0);
      return `📋 **الذمم الحالية:**\n\n` +
        `👥 ذمم مدينة (عملاء آجل): **${Math.max(0, arTotal).toLocaleString('ar-SA')} ر.س**\n` +
        `🏢 ذمم دائنة (مستحق للموردين): **${Math.max(0, apTotal).toLocaleString('ar-SA')} ر.س**\n\n` +
        (arTotal > 0 ? `💡 يوجد ${Math.max(0, arTotal).toLocaleString('ar-SA')} ر.س لم يُحصَّل من العملاء بعد.` : '✅ لا ذمم مدينة مفتوحة.');
    },
  },
  {
    match: (t) => /العمليات الأخيرة|آخر عمليات|اخر عمليات|سجل العمليات/.test(t),
    label: 'العمليات الأخيرة',
    handler: async () => {
      const r = await axios.get(`${API}/api/operations?limit=5`);
      const ops = Array.isArray(r.data) ? r.data : r.data?.data || r.data?.operations || [];
      if (!ops.length) return 'لا توجد عمليات مسجلة.';
      return `📑 **آخر 5 عمليات:**\n\n` +
        ops.map(o => `• ${o.partnerName || '—'} | ${Number(o.total||0).toLocaleString('ar-SA')} ر.س | ${labelFromMap(o.paymentMethod, PAYMENT_METHOD_LABELS, '—')} | ${String(o.date||'').slice(0,10)}`).join('\n');
    },
  },
  {
    match: (t) => /إحصاء المركبات|المركبات الحالية|كم مركبة|عدد المركبات/.test(t),
    label: 'إحصاء المركبات',
    handler: async () => {
      const r = await axios.get(`${API}/api/vehicles?limit=200`);
      const all = Array.isArray(r.data) ? r.data : r.data?.data || r.data?.vehicles || [];
      const inProgress = all.filter(v => ['in_progress','open','new'].includes(v.status)).length;
      const completed = all.filter(v => ['completed','delivered'].includes(v.status)).length;
      return `🚗 **المركبات في النظام:**\n\n` +
        `📊 الإجمالي: **${all.length}** مركبة\n` +
        `🔧 قيد الصيانة: **${inProgress}**\n` +
        `✅ مكتملة: **${completed}**`;
    },
  },
  {
    match: (t) => /قائمة الموردين|الموردون|أرني الموردين|ارني الموردين/.test(t),
    label: 'قائمة الموردين',
    handler: async () => {
      const r = await axios.get(`${API}/api/suppliers`);
      const sup = Array.isArray(r.data) ? r.data : r.data?.data || r.data?.suppliers || [];
      const real = sup.filter(s => !String(s.id).startsWith('acc-')).slice(0, 8);
      return `🏢 **الموردون الرئيسيون (${real.length}):**\n\n` +
        real.map(s => `• ${s.name}${s.phone ? ` — ${s.phone}` : ''}`).join('\n');
    },
  },
  {
    match: (t) => /عدد العملاء|قائمة العملاء|كم عميل/.test(t),
    label: 'إحصاء العملاء',
    handler: async () => {
      const r = await axios.get(`${API}/api/customers?limit=200`);
      const cust = Array.isArray(r.data) ? r.data : r.data?.data || r.data?.customers || [];
      return `👥 **العملاء:** ${cust.length} عميل مسجل في النظام.`;
    },
  },
  {
    match: (t) => /قائمة القيود|آخر قيود|اخر قيود|القيود الأخيرة/.test(t),
    label: 'آخر القيود',
    handler: async () => {
      const r = await axios.get(`${API}/api/finance/journal-entries?workshop_id=${WID}&limit=5`);
      const entries = Array.isArray(r.data) ? r.data : r.data?.entries || r.data?.data || [];
      if (!entries.length) return 'لا توجد قيود.';
      return `📒 **آخر 5 قيود:**\n\n` +
        entries.map(e => `• ${String(e.date||'').slice(0,10)} | ${e.description?.slice(0,40)||'—'}`).join('\n');
    },
  },
  {
    match: (t) => /انظر.*قسم المالي|القسم المالي|اعرض البيانات المالية|بيانات مالية|نظرة عامة|النظرة العامة/.test(t),
    label: 'نظرة مالية',
    handler: async (finCtx) => {
      if (!finCtx) return 'لا تزال البيانات تُحمَّل، انتظر لحظة ثم أعِد المحاولة.';
      const margin = finCtx.revenue > 0 ? ((finCtx.net / finCtx.revenue) * 100).toFixed(1) : '0';
      const balanced = Math.abs((finCtx.totalDebit||0) - (finCtx.totalCredit||0)) < 1;
      return `📋 **البيانات المالية الحالية:**\n\n` +
        `💰 الإيرادات: **${finCtx.revenue.toLocaleString('ar-SA')} ر.س**\n` +
        `📉 المصروفات: **${finCtx.expenses.toLocaleString('ar-SA')} ر.س**\n` +
        `📊 صافي الدخل: **${finCtx.net.toLocaleString('ar-SA')} ر.س** (${margin}%)\n` +
        `⚖️ الميزان: **${balanced ? '✅ متوازن' : `❌ يوجد فرق ${Math.abs((finCtx.totalDebit||0)-(finCtx.totalCredit||0)).toLocaleString('ar-SA')} ر.س`}**\n\n` +
        (finCtx.alerts?.length ? `⚠️ تنبيهات: ${finCtx.alerts.map(a=>a.title).join(' | ')}` : '✅ لا تنبيهات');
    },
  },
  {
    match: (t) => /إحصائيات شاملة|لوحة التحكم|ملخص عام شامل/.test(t),
    label: 'إحصائيات شاملة',
    handler: async (finCtx) => {
      const [opsR, custR, vehR] = await Promise.all([
        axios.get(`${API}/api/operations?limit=200`),
        axios.get(`${API}/api/customers?limit=200`),
        axios.get(`${API}/api/vehicles?limit=200`),
      ]);
      const ops = Array.isArray(opsR.data) ? opsR.data : opsR.data?.data || opsR.data?.operations || [];
      const cust = Array.isArray(custR.data) ? custR.data : custR.data?.data || custR.data?.customers || [];
      const veh = Array.isArray(vehR.data) ? vehR.data : vehR.data?.data || vehR.data?.vehicles || [];
      return `📊 **لوحة التحكم الشاملة:**\n\n` +
        `💰 الإيرادات: ${finCtx?.revenue.toLocaleString('ar-SA')||'—'} ر.س\n` +
        `📉 المصروفات: ${finCtx?.expenses.toLocaleString('ar-SA')||'—'} ر.س\n` +
        `📈 صافي: ${finCtx?.net.toLocaleString('ar-SA')||'—'} ر.س\n\n` +
        `🚗 المركبات: ${veh.length}\n` +
        `👥 العملاء: ${cust.length}\n` +
        `📑 العمليات: ${ops.length}\n` +
        `⚠️ تنبيهات: ${finCtx?.alerts?.length||0}`;
    },
  },
];

async function runAdminCommand(text, finCtx) {
  const t = text.trim();
  const pattern = ADMIN_PATTERNS.find(p => p.match(t));
  if (!pattern) return null;
  try {
    return await pattern.handler(finCtx);
  } catch (e) {
    return `تعذر جلب بيانات ${pattern.label}: ${e?.message || 'خطأ'}`;
  }
}
const TABS = [
  { id: 'assistant', label: 'المساعد', icon: MessageSquare },
  { id: 'create',    label: 'إنشاء',   icon: Zap          },
  { id: 'quick',     label: 'فوري',    icon: DollarSign   },
];

const INIT_ASSISTANT = [{ role: 'assistant', content: 'مرحباً! أنا مساعد الورشة. اسألني عن أي شيء.' }];
const INIT_AUDITOR   = [{ role: 'assistant', content: 'مرحباً! أنا المدقق المالي. يمكنني مراجعة الحسابات وإنشاء قيود بأوامر نصية مثل "أنشئ قيد".' }];

const QUICK_AMOUNTS = [50, 100, 200, 500, 1000];
const PAYMENT_METHODS = [
  { v: 'bank', l: 'بنك', acc: '004' },
  { v: 'cash', l: 'نقد', acc: '003' },
  { v: 'pos',  l: 'POS', acc: '006' },
  { v: 'credit', l: 'آجل', acc: '005' },
];

export default function UnifiedBotWidget() {
  const [open, setOpen]       = useState(false);
  const [tab, setTab]         = useState('assistant');
  const [input, setInput]     = useState('');
  const [loading, setLoading] = useState(false);

  // assistant / auditor messages
  const [aMessages, setAMessages] = useState(INIT_ASSISTANT);
  const [fMessages, setFMessages] = useState(INIT_AUDITOR);
  const [fSession]                = useState(`sess-${Date.now()}`);

  // smart create state
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [paymentMethod, setPaymentMethod]        = useState('bank');
  const [amount, setAmount]                      = useState('');
  const [description, setDescription]            = useState('');
  const [partnerName, setPartnerName]            = useState('');
  const [date, setDate]                          = useState(new Date().toISOString().split('T')[0]);
  const [customDebit, setCustomDebit]            = useState('');
  const [customCredit, setCustomCredit]          = useState('');
  const [createResult, setCreateResult]          = useState(null);
  const [createMode, setCreateMode]              = useState('smart'); // 'smart' | 'manual'

  // vehicle + account linking
  const [vehicles, setVehicles]               = useState([]);
  const [createDataLoaded, setCreateDataLoaded] = useState(false);
  const [vehicleSearch, setVehicleSearch]     = useState('');
  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [vehicleDropOpen, setVehicleDropOpen] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState(null);

  // services + parts catalog
  const [servicesCatalog, setServicesCatalog] = useState([]);
  const [partsCatalog, setPartsCatalog]       = useState([]);
  const [recentOps, setRecentOps]             = useState([]);
  const [itemSearch, setItemSearch]           = useState('');
  const [itemDropOpen, setItemDropOpen]       = useState(false);
  const [pageSuggestion, setPageSuggestion]   = useState(null);
  const [suggestionBusy, setSuggestionBusy]   = useState(false);
  const [interactiveDraft, setInteractiveDraft] = useState(null);
  const contextTimerRef                        = useRef(null);
  const lastContextKeyRef                      = useRef('');

  const messagesEndRef = useRef(null);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [aMessages, fMessages, tab]);

  // auditor: load real financial context on tab open
  const [finContext, setFinContext] = useState(null);

  useEffect(() => {
    if (tab !== 'quick' || finContext) return;
    const load = async () => {
      try {
        const [isR, alertsR, tbR] = await Promise.all([
          axios.get(`${API}/api/finance/reports/income-statement`).catch(() => ({ data: {} })),
          axios.get(`${API}/api/finance/alerts?workshop_id=${WID}`).catch(() => ({ data: {} })),
          axios.get(`${API}/api/finance/reports/trial-balance?workshop_id=${WID}`).catch(() => ({ data: {} })),
        ]);
        const totals   = isR.data?.data?.totals || {};
        const alerts   = alertsR.data?.data?.alerts || [];
        const tbTotals = tbR.data?.data?.totals || {};
        const ctx = {
          revenue:  Number(totals.revenue   || 0),
          expenses: Number(totals.expenses  || 0),
          net:      Number(totals.net_income|| 0),
          totalDebit:  Number(tbTotals.total_debit  || 0),
          totalCredit: Number(tbTotals.total_credit || 0),
          alerts,
        };
        setFinContext(ctx);
        const margin   = ctx.revenue > 0 ? ((ctx.net / ctx.revenue) * 100).toFixed(1) : '0';
        const balanced = Math.abs(ctx.totalDebit - ctx.totalCredit) < 1;
        setFMessages([{
          role: 'assistant',
          content:
            `✅ اطّلعت على البيانات المالية الفعلية:\n\n` +
            `💰 الإيرادات: **${ctx.revenue.toLocaleString('ar-SA')} ر.س**\n` +
            `📉 المصروفات: **${ctx.expenses.toLocaleString('ar-SA')} ر.س**\n` +
            `📊 صافي الدخل: **${ctx.net.toLocaleString('ar-SA')} ر.س** (هامش ${margin}%)\n` +
            `⚖️ الميزان: **${balanced ? '✅ متوازن' : `❌ فرق ${Math.abs(ctx.totalDebit-ctx.totalCredit).toLocaleString('ar-SA')} ر.س`}**\n\n` +
            (alerts.length ? `⚠️ **${alerts.length} تنبيه:** ${alerts.map(a=>a.title).join(' | ')}` : '✅ لا تنبيهات') +
            `\n\n**أوامر سريعة:** اكتب الوضع العام | الذمم | العمليات الأخيرة | المركبات | الموردين | "أنشئ قيد"`,
        }]);
      } catch {
        // keep default
      }
    };
    load();
  }, [tab, finContext]);

  // جلب المركبات عند فتح تبويب الإنشاء
  useEffect(() => {
    if (tab !== 'create' || createDataLoaded) return;
    axios.get(`${API}/api/vehicles?limit=200`)
      .then(r => {
        const list = Array.isArray(r.data) ? r.data : r.data?.data || r.data?.vehicles || [];
        setVehicles(list);
      })
      .catch(() => {});
    // جلب الخدمات والقطع
    axios.get(`${API}/api/services?limit=500`)
      .then(r => {
        const list = Array.isArray(r.data) ? r.data : r.data?.data || r.data?.services || [];
        setServicesCatalog(list.filter(s => s.active !== false));
      }).catch(() => {});
    axios.get(`${API}/api/parts?limit=500`)
      .then(r => {
        const list = Array.isArray(r.data) ? r.data : r.data?.data || r.data?.parts || [];
        setPartsCatalog(list.filter(p => Number(p.quantity || 0) > 0));
      }).catch(() => {});
    axios.get(`${API}/api/operations?limit=120`)
      .then(r => {
        const list = Array.isArray(r.data) ? r.data : r.data?.data || r.data?.operations || [];
        setRecentOps(list);
      }).catch(() => {});
    setCreateDataLoaded(true);
  }, [tab, createDataLoaded]);

  // auto-detect template from description
  useEffect(() => {
    if (!description) return;
    const guess = guessTemplate(description);
    if (guess && !selectedTemplate) setSelectedTemplate(guess);
  }, [description]);

  useEffect(() => {
    if (tab !== 'create' || !selectedTemplate || !description || interactiveDraft) return;

    const partner = (partnerName || '').trim();
    const partnerNorm = normalizeArabicText(partner);
    const candidateVehicles = partnerNorm
      ? (vehicles || []).filter((v) => normalizeArabicText(v?.customerName || '').includes(partnerNorm)).slice(0, 8)
      : [];

    const missing = [];
    if (!amount) missing.push('المبلغ');
    if (['purchase', 'parts_sale', 'service_sale', 'credit_sale'].includes(selectedTemplate) && !partner && !selectedVehicle) {
      missing.push('الطرف (عميل/مورد أو مركبة)');
    }
    if (['parts_sale', 'service_sale', 'credit_sale'].includes(selectedTemplate) && !selectedVehicle) {
      missing.push('المركبة');
    }

    const templateLabel = SMART_TEMPLATES.find((t) => t.id === selectedTemplate)?.label || selectedTemplate;
    setInteractiveDraft({
      templateId: selectedTemplate,
      templateLabel,
      amount,
      partnerName: partner,
      description,
      vehicleCandidates: candidateVehicles,
      selectedVehicleId: selectedVehicle?.id || null,
      missing,
    });

    const summary = [
      '🧾 ملخص قبل التنفيذ:',
      `• النوع: ${templateLabel}`,
      `• الوصف: ${description || '-'}`,
      `• الطرف: ${partner || 'غير محدد'}`,
      `• المبلغ: ${amount || 'غير محدد'}`,
      missing.length ? `\n⚠️ النواقص: ${missing.join(' + ')}` : '\n✅ جاهز للتنفيذ. اضغط تأكيد الآن.',
    ].join('\n');
    setCreateResult({ ok: missing.length === 0, msg: summary });
  }, [tab, selectedTemplate, description, amount, partnerName, selectedVehicle, interactiveDraft, vehicles]);

  useEffect(() => {
    if (tab !== 'create' || recentOps.length > 0) return;
    axios.get(`${API}/api/operations?limit=120`)
      .then(r => {
        const list = Array.isArray(r.data) ? r.data : r.data?.data || r.data?.operations || [];
        setRecentOps(list);
      })
      .catch(() => {});
  }, [tab, recentOps.length]);

  const currentTemplate = useMemo(() => SMART_TEMPLATES.find(t => t.id === selectedTemplate), [selectedTemplate]);

  const templateRecentMap = useMemo(() => {
    const isPartsLike = (op) => /قطع|part/i.test(String(op?.notes || op?.description || '')) || ['041', '042'].includes(String(op?.accountingAccountCode || '').trim());
    const isSalaryLike = (op) => /راتب|رواتب|salary/i.test(String(op?.notes || op?.description || '')) || String(op?.accountingAccountCode || '').trim() === '037';
    const rows = Array.isArray(recentOps) ? recentOps : [];

    const pick = (fn) => rows.filter(fn).slice(0, 3);

    return {
      service_sale: pick(op => ['sale', 'service'].includes(String(op?.type || '').toLowerCase()) && !isPartsLike(op)),
      parts_sale: pick(op => ['sale', 'service'].includes(String(op?.type || '').toLowerCase()) && isPartsLike(op)),
      credit_sale: pick(op => ['sale', 'service'].includes(String(op?.type || '').toLowerCase()) && String(op?.paymentMethod || '').toLowerCase() === 'credit'),
      purchase: pick(op => String(op?.type || '').toLowerCase() === 'purchase'),
      expense: pick(op => ['expense', 'payment_order'].includes(String(op?.type || '').toLowerCase()) && !isSalaryLike(op)),
      salary: pick(op => ['expense', 'payment_order'].includes(String(op?.type || '').toLowerCase()) && isSalaryLike(op)),
    };
  }, [recentOps]);

  const previewLines = useMemo(() => {
    if (createMode === 'manual') {
      const amt = parseFloat(amount) || 0;
      if (!amt || !customDebit || !customCredit) return [];
      return [
        { account: customDebit,  name: ACCOUNTS[customDebit]  || customDebit,  debit: amt, credit: 0 },
        { account: customCredit, name: ACCOUNTS[customCredit] || customCredit, debit: 0, credit: amt },
      ];
    }
    if (!currentTemplate || !amount) return [];
    const pm = currentTemplate.forcePayment || paymentMethod;
    const lines = currentTemplate.getLines(pm, parseFloat(amount) || 0);
    // إذا تم اختيار حساب خاص → نُبدّل سطر الدائن (الإيراد/المصروف)
    if (selectedAccount) {
      return lines.map((l, i) => {
        // آخر سطر عادةً هو الدائن للإيراد أو المدين للمصروف
        if (i === 1 && l.credit > 0) {
          return { ...l, account: selectedAccount.code, name: selectedAccount.name };
        }
        if (i === 0 && l.debit > 0 && currentTemplate.opType !== 'sale') {
          return { ...l, account: selectedAccount.code, name: selectedAccount.name };
        }
        return l;
      });
    }
    return lines;
  }, [currentTemplate, paymentMethod, amount, createMode, customDebit, customCredit, selectedAccount]);

  const isBalanced = useMemo(() => {
    const d = previewLines.reduce((s, l) => s + l.debit, 0);
    const c = previewLines.reduce((s, l) => s + l.credit, 0);
    return Math.abs(d - c) < 0.01 && d > 0;
  }, [previewLines]);

  // ─── المساعد ─────────────────────────────────────────────────────────────
  const sendAssistant = useCallback(async (text) => {
    if (!text.trim()) return;
    setAMessages(prev => [...prev, { role: 'user', content: text }]);
    setInput(''); setLoading(true);
    try {
      const r = await axios.post(`${API}/api/ai/chat`, {
        message: text, workshop_id: WID,
        history: aMessages.slice(-6).map(m => ({ role: m.role, content: m.content })),
      });
      setAMessages(prev => [...prev, { role: 'assistant', content: r.data?.response || r.data?.message || 'لا استجابة' }]);
    } catch { setAMessages(prev => [...prev, { role: 'assistant', content: 'حدث خطأ، حاول مرة أخرى.' }]); }
    finally { setLoading(false); }
  }, [aMessages]);

  const normalizeArabicText = (raw = '') => String(raw || '')
    .toLowerCase()
    .replace(/[أإآ]/g, 'ا')
    .replace(/ى/g, 'ي')
    .replace(/ة/g, 'ه')
    .replace(/\s+/g, ' ')
    .trim();

  const parseCreateIntent = (raw = '') => {
    const text = normalizeArabicText(raw);
    const isCreate = /(انش|انشي|انشى|سجل|سوي).*(عمليه|عملية|بيع|شراء|مصروف|راتب)/.test(text);
    if (!isCreate) return null;

    let templateId = 'service_sale';
    if (text.includes('شراء')) templateId = 'purchase';
    else if (text.includes('راتب')) templateId = 'salary';
    else if (text.includes('مصروف')) templateId = 'expense';
    else if (text.includes('بيع') && /(قطع|قطعه|قطعة|غيار|part)/.test(text)) templateId = 'parts_sale';
    else if (text.includes('بيع')) templateId = 'service_sale';

    const amountMatch = raw.match(/(\d+(?:[\.,]\d+)?)/);
    const amountVal = amountMatch ? String(amountMatch[1]).replace(',', '.') : '';

    const onMatch = raw.match(/(?:على|لـ|ل)\s+([^\n،,]+)/i);
    const partner = onMatch ? String(onMatch[1]).trim() : '';

    return {
      templateId,
      amount: amountVal,
      partnerName: partner,
      description: raw.trim(),
    };
  };

  const findVehiclesForPartner = async (partnerNameRaw = '') => {
    const partner = normalizeArabicText(partnerNameRaw);
    if (!partner) return [];

    let pool = Array.isArray(vehicles) ? vehicles : [];
    if (!pool.length) {
      try {
        const vr = await axios.get(`${API}/api/vehicles?limit=300`);
        pool = Array.isArray(vr.data) ? vr.data : vr.data?.data || vr.data?.vehicles || [];
        setVehicles(pool);
      } catch {
        pool = [];
      }
    }

    return pool.filter((v) => {
      const owner = normalizeArabicText(v?.customerName || v?.customer_name || '');
      return owner && owner.includes(partner);
    }).slice(0, 8);
  };

  // ─── المدقق ──────────────────────────────────────────────────────────────
  const sendAuditor = useCallback(async (text) => {
    if (!text.trim()) return;
    setFMessages(prev => [...prev, { role: 'user', content: text }]);
    setInput(''); setLoading(true);
    try {
      const lc = normalizeArabicText(text);
      if (lc.includes('انشئ قيد') || lc.includes('انشي قيد') || lc.includes('انشى قيد')) {
        setTab('create'); setCreateMode('smart');
        setFMessages(prev => [...prev, { role: 'assistant', content: '✅ انتقلت لتبويب الإنشاء الذكي — اختر نموذج العملية وأدخل المبلغ.' }]);
        setLoading(false); return;
      }

      const parsedCreate = parseCreateIntent(text);
      if (parsedCreate) {
        setTab('create'); setCreateMode('smart');
        setSelectedTemplate(parsedCreate.templateId);
        if (parsedCreate.amount) setAmount(parsedCreate.amount);
        if (parsedCreate.partnerName) setPartnerName(parsedCreate.partnerName);
        if (parsedCreate.description) setDescription(parsedCreate.description);

        const candidateVehicles = await findVehiclesForPartner(parsedCreate.partnerName);
        let selectedVehicleId = selectedVehicle?.id || null;
        if (!selectedVehicleId && candidateVehicles.length === 1) {
          setSelectedVehicle(candidateVehicles[0]);
          selectedVehicleId = candidateVehicles[0].id;
        }

        const missing = [];
        if (!parsedCreate.amount) missing.push('المبلغ');
        if (['purchase', 'parts_sale', 'service_sale', 'credit_sale'].includes(parsedCreate.templateId) && !parsedCreate.partnerName && !selectedVehicle) {
          missing.push('الطرف (عميل/مورد أو مركبة)');
        }
        if (['parts_sale', 'service_sale', 'credit_sale'].includes(parsedCreate.templateId) && !selectedVehicleId) {
          missing.push('المركبة');
        }

        const templateLabel = SMART_TEMPLATES.find(t => t.id === parsedCreate.templateId)?.label || parsedCreate.templateId;
        const summary = [
          `🧾 ملخص قبل التنفيذ:`,
          `• النوع: ${templateLabel}`,
          `• الوصف: ${parsedCreate.description || '-'}`,
          `• الطرف: ${parsedCreate.partnerName || 'غير محدد'}`,
          `• المبلغ: ${parsedCreate.amount || 'غير محدد'}`,
          missing.length ? `\n⚠️ النواقص: ${missing.join(' + ')}` : '\n✅ جاهز للتنفيذ. اضغط تنفيذ من تبويب إنشاء.',
        ].join('\n');

        setInteractiveDraft({
          ...parsedCreate,
          templateLabel,
          missing,
          vehicleCandidates: candidateVehicles,
          selectedVehicleId,
        });
        setCreateResult({ ok: missing.length === 0, msg: summary });
        setLoading(false); return;
      }
      // ── أوامر إدارية مباشرة (بدون LLM) ──────────────────────────────────
      const adminReply = await runAdminCommand(text, finContext);
      if (adminReply) {
        setFMessages(prev => [...prev, { role: 'assistant', content: adminReply }]);
        setLoading(false); return;
      }

      // إضافة السياق المالي الفعلي مع الرسالة للـ LLM
      const contextNote = finContext
        ? `[بيانات مباشرة من النظام: إيرادات=${finContext.revenue.toLocaleString('ar-SA')} ر.س | مصروفات=${finContext.expenses.toLocaleString('ar-SA')} ر.س | صافي=${finContext.net.toLocaleString('ar-SA')} ر.س | تنبيهات=${finContext.alerts.map(a=>a.title).join(',')||'لا تنبيهات'}]\nالسؤال: `
        : '';
      const r = await axios.post(`${API}/api/finance-bot/chat`, {
        message: contextNote + text,
        session_id: fSession, workshop_id: WID,
        financial_data: finContext ? { totals: { revenue: finContext.revenue, expenses: finContext.expenses, net_income: finContext.net } } : {},
        findings: [], action: null,
      });
      const data = r.data || {};
      setFMessages(prev => [...prev, {
        role: 'assistant', content: data.response || 'لا استجابة',
        state: data.state, linkedData: data.linked_data,
        contradictions: data.contradictions, sessionId: fSession,
      }]);
    } catch { setFMessages(prev => [...prev, { role: 'assistant', content: 'حدث خطأ، حاول مرة أخرى.' }]); }
    finally { setLoading(false); }
  }, [fMessages, fSession, finContext]);

  // state عملية فورية
  const [quickAmount, setQuickAmount]   = useState('');
  const [quickPM, setQuickPM]           = useState('bank');
  const [quickDesc, setQuickDesc]       = useState('');
  const [quickResult, setQuickResult]   = useState(null);
  const [quickLoading, setQuickLoading] = useState(false);

  const handleQuickOp = async () => {
    const amt = parseFloat(quickAmount);
    if (!amt || amt <= 0) { setQuickResult({ ok: false, msg: 'أدخل مبلغاً صحيحاً' }); return; }
    setQuickLoading(true); setQuickResult(null);
    try {
      await axios.post(`${API}/api/operations`, {
        workshopId: WID, workshop_id: WID,
        type: 'sale', paymentMethod: quickPM, paymentStatus: 'paid',
        partnerName: quickDesc || 'عملية فورية', partnerType: 'customer',
        scope: 'workshop', date: new Date().toISOString().split('T')[0],
        total: amt, subtotal: amt,
        items: [{ name: quickDesc || 'خدمة', itemType: 'service', qty: 1, price: amt, total: amt }],
      });
      setQuickResult({ ok: true, msg: `✅ ${amt.toLocaleString('ar-SA')} ر.س — سُجّلت كعملية عبر المسار الموحّد` });
      setQuickAmount(''); setQuickDesc('');
    } catch (err) {
      setQuickResult({ ok: false, msg: err?.response?.data?.detail || 'فشل الإنشاء' });
    } finally { setQuickLoading(false); }
  };

  // ─── الإنشاء الذكي ───────────────────────────────────────────────────────
  const handleCreate = async (e = null) => {
    if (e?.preventDefault) e.preventDefault();
    if (!isBalanced) { setCreateResult({ ok: false, msg: 'القيد غير متوازن أو البيانات ناقصة' }); return; }
    setLoading(true); setCreateResult(null);
    try {
      const amt = parseFloat(amount);
      const pm  = currentTemplate?.forcePayment || paymentMethod;
      const linkedPartnerName = (partnerName || selectedVehicle?.customerName || '').trim();

      if (currentTemplate?.opType === 'sale' && !linkedPartnerName && !selectedVehicle) {
        setCreateResult({ ok: false, msg: 'عملية البيع تتطلب عميلًا أو مركبة للربط.' });
        setLoading(false);
        return;
      }

      if (currentTemplate?.opType === 'purchase' && !linkedPartnerName) {
        setCreateResult({ ok: false, msg: 'عملية الشراء تتطلب اسم المورد للربط.' });
        setLoading(false);
        return;
      }

      if (!currentTemplate) {
        setCreateResult({ ok: false, msg: 'تم إيقاف إنشاء القيود المباشرة من الواجهة. اختر قالب عملية مرتبط.' });
        setLoading(false);
        return;
      }

      // إنشاء عملية فقط؛ الـBackend مسؤول عن ترحيل القيد مرة واحدة.
      if (currentTemplate) {
        const botOriginalType = currentTemplate.id === 'salary' ? 'salary' : currentTemplate.id;
        await axios.post(`${API}/api/operations`, {
          workshopId: WID, workshop_id: WID,
          type: currentTemplate.opType,
          originalType: botOriginalType,
          paymentMethod: pm,
          paymentStatus: pm === 'credit' ? 'credit' : 'paid',
          partnerName: linkedPartnerName || (currentTemplate.opType === 'expense' ? 'مصروف عام' : ''),
          partnerType: currentTemplate.opType === 'purchase' ? 'supplier' : 'customer',
          scope: selectedVehicle ? 'vehicle' : 'workshop', date, total: amt, subtotal: amt,
          // ربط المركبة إذا تم اختيارها
          ...(selectedVehicle && { vehicleId: selectedVehicle.id, vehicleInfo: `${selectedVehicle.plateNumber} - ${selectedVehicle.customerName}` }),
          // الحساب المحاسبي المحدد
          ...(selectedAccount && { accountingAccountCode: selectedAccount.code }),
          notes: `[BOT_TEMPLATE:${currentTemplate.id}] ${description || currentTemplate.desc || ''}`.trim(),
          items: [{
            name: description || currentTemplate.label,
            itemType: currentTemplate.opType === 'purchase' ? 'supplier' : (currentTemplate.id === 'parts_sale' ? 'part' : 'service'),
            qty: 1,
            price: amt,
            total: amt,
          }],
        });
      }

      setCreateResult({ ok: true, msg: `✅ تم إنشاء القيد بنجاح (${previewLines.map(l=>l.name).join(' / ')}) — ${amt.toLocaleString('ar-SA')} ر.س` });
      setInteractiveDraft(null);
      setAmount(''); setDescription(''); setPartnerName('');
    } catch (err) {
      setCreateResult({ ok: false, msg: err?.response?.data?.detail || 'فشل الإنشاء' });
    } finally { setLoading(false); }
  };

  const handleSend = (e) => {
    e?.preventDefault();
    if (tab === 'assistant') sendAssistant(input);
    else if (tab === 'quick') sendAuditor(input);
  };

  const messages = tab === 'assistant' ? aMessages : fMessages;

  const focusCreateField = (field) => {
    if (field === 'المبلغ') {
      const el = document.querySelector('[data-testid="create-amount-input"]');
      el?.focus();
      return;
    }
    if (field.includes('الطرف')) {
      const el = document.querySelector('[data-testid="create-partner-input"]');
      el?.focus();
      return;
    }
    if (field.includes('المركبة')) {
      const el = document.querySelector('[data-testid="create-vehicle-search"]');
      el?.focus();
    }
  };

  const handleSelectDraftVehicle = (vehicle) => {
    if (!vehicle) return;
    setSelectedVehicle(vehicle);
    setInteractiveDraft((prev) => {
      if (!prev) return prev;
      const nextMissing = (prev.missing || []).filter((m) => !m.includes('المركبة'));
      return { ...prev, selectedVehicleId: vehicle.id, missing: nextMissing };
    });
  };

  const handleAddNewVehicleFromDraft = () => {
    setCreateResult({ ok: false, msg: 'افتح ملف المركبات لإضافة مركبة جديدة ثم ارجع لإكمال التنفيذ.' });
    try {
      window.open('/vehicles', '_blank');
    } catch {
      // ignore
    }
  };

  const collectPageContext = () => {
    const fields = {};
    document.querySelectorAll('input, select, textarea').forEach((el) => {
      const key = el.getAttribute('data-testid') || el.getAttribute('name') || el.getAttribute('id');
      if (!key) return;
      const value = el.type === 'checkbox' ? Boolean(el.checked) : el.value;
      if (value === undefined || value === null) return;
      fields[key] = value;
    });
    return {
      page: window.location.pathname,
      fields,
    };
  };

  const scheduleContextAnalysis = () => {
    const path = window.location.pathname || '';
    const isFinancialPath = /(operations|accounting|journal|finance|vehicle|suppliers|debts|invoices|inventory|accounts)/i.test(path);
    if (!isFinancialPath) return;

    if (contextTimerRef.current) {
      clearTimeout(contextTimerRef.current);
    }

    contextTimerRef.current = setTimeout(async () => {
      try {
        const payload = collectPageContext();
        const contextKey = `${payload.page}::${JSON.stringify(payload.fields).slice(0, 2000)}`;
        if (lastContextKeyRef.current === contextKey) return;
        lastContextKeyRef.current = contextKey;

        const r = await axios.post(`${API}/api/nlp/page/context`, payload);
        const suggestion = r?.data?.suggestion || null;
        setPageSuggestion(suggestion);
      } catch {
        // ignore silently
      }
    }, 650);
  };

  const applyFieldValue = (fieldKey, value) => {
    const selectors = [
      `[data-testid="${fieldKey}"]`,
      `[name="${fieldKey}"]`,
      `#${fieldKey.replace(/([^a-zA-Z0-9_-])/g, '\\$1')}`,
    ];
    let target = null;
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el) {
        target = el;
        break;
      }
    }
    if (!target) return false;

    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') {
      target.value = value;
      target.dispatchEvent(new Event('input', { bubbles: true }));
      target.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    }
    return false;
  };

  const handleSuggestionDecision = async (accepted) => {
    if (!pageSuggestion?.id || suggestionBusy) return;
    setSuggestionBusy(true);
    try {
      const r = await axios.post(`${API}/api/nlp/page/apply_correction`, {
        suggestion_id: pageSuggestion.id,
        accepted,
      });

      if (accepted) {
        const corrected = r?.data?.corrected_fields || {};
        Object.entries(corrected).forEach(([key, val]) => {
          applyFieldValue(key, val);
        });
        setFMessages((prev) => ([...prev, { role: 'assistant', content: '✅ تم تطبيق التصحيح المقترح بعد موافقتك.' }]));
      }

      setPageSuggestion(null);
    } catch {
      setFMessages((prev) => ([...prev, { role: 'assistant', content: '⚠️ تعذّر تطبيق التصحيح حالياً.' }]));
    } finally {
      setSuggestionBusy(false);
    }
  };

  useEffect(() => {
    const onFieldChange = (event) => {
      const target = event?.target;
      if (!target || !['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return;
      scheduleContextAnalysis();
    };

    document.addEventListener('input', onFieldChange, true);
    document.addEventListener('change', onFieldChange, true);

    if (open) {
      scheduleContextAnalysis();
    }

    return () => {
      document.removeEventListener('input', onFieldChange, true);
      document.removeEventListener('change', onFieldChange, true);
      if (contextTimerRef.current) clearTimeout(contextTimerRef.current);
    };
  }, [open, tab]);

  const forceOpenBotPanel = () => {
    setOpen(true);
  };

  return (
    <>
      {/* ─── زر البوت ─────────────────────────────────────────────────── */}
      {!open && (
        <div className="fixed z-[2147483000] left-4 bottom-20 lg:bottom-6 lg:left-auto lg:right-6" data-testid="unified-bot-trigger">
          <button
            type="button"
            onClick={forceOpenBotPanel}
            className="relative w-12 h-12 rounded-full flex items-center justify-center shadow-2xl transition-all hover:scale-110 active:scale-95 border"
            style={{
              background: 'linear-gradient(135deg,#0ea5e9,#6366f1)',
              borderColor: 'rgba(99,102,241,0.5)',
            }}
            data-testid="unified-bot-button"
          >
            <Bot size={20} className="text-white" />
            <span className="absolute top-1 right-1 w-2.5 h-2.5 rounded-full bg-green-400 border border-slate-900 animate-pulse" />
          </button>
        </div>
      )}

      {/* ─── نافذة البوت ──────────────────────────────────────────────── */}
      {open && (
        <div
          className="fixed z-[2147482999] left-3 bottom-24 w-[92vw] max-w-[420px] lg:left-6 lg:bottom-20 lg:w-[420px] rounded-[28px] overflow-hidden flex flex-col pointer-events-auto"
          style={{
            height: 'min(72vh, 580px)',
            maxHeight: 'calc(100dvh - 110px)',
            bottom: 'calc(5.5rem + env(safe-area-inset-bottom, 0px))',
            background: 'linear-gradient(145deg, rgba(6,10,30,0.98) 0%, rgba(2,6,23,0.98) 100%)',
            backdropFilter: 'blur(40px) saturate(180%)',
            WebkitBackdropFilter: 'blur(40px) saturate(180%)',
            border: '1px solid rgba(56,189,248,0.15)',
            boxShadow: '0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04), inset 0 1px 0 rgba(255,255,255,0.06)',
          }}
          data-testid="unified-bot-panel"
        >
          {/* رأس */}
          <div className="flex items-center justify-between px-4 py-3 flex-shrink-0"
            style={{
              background: 'linear-gradient(135deg, rgba(14,165,233,0.12) 0%, rgba(99,102,241,0.12) 100%)',
              borderBottom: '1px solid rgba(56,189,248,0.12)',
            }}>
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-xl flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg,#0ea5e9,#6366f1)' }}>
                <Bot size={14} className="text-white" />
              </div>
              <div>
                <div className="text-xs font-bold text-slate-100">المساعد الموحد</div>
                <div className="text-[10px] text-green-400 flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />متصل</div>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="p-1.5 rounded-lg hover:bg-white/8 text-slate-400" data-testid="unified-bot-close"><X size={14} /></button>
          </div>

          {/* تبويبات */}
          <div className="flex border-b border-slate-800/60 flex-shrink-0">
            {TABS.map(t => {
              const Icon = t.icon;
              return (
                <button key={t.id} onClick={() => { setTab(t.id); setInput(''); setCreateResult(null); }}
                  className={`flex-1 flex items-center justify-center gap-1 py-2 text-[11px] font-medium transition-colors ${
                    tab === t.id ? 'border-b-2 border-sky-500 text-sky-300 bg-sky-500/5' : 'text-slate-500 hover:text-slate-300'}`}
                  data-testid={`bot-tab-${t.id}`}>
                  <Icon size={12} />{t.label}
                  {t.id === 'create' && <span className="w-1.5 h-1.5 rounded-full bg-green-400 ml-0.5" />}
                </button>
              );
            })}
          </div>

          {/* ─── محتوى ──────────────────────────────────────────────────── */}
          {tab !== 'create' ? (
            <>
              <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {tab === 'quick' && (
                  <div className="rounded-xl border border-slate-700/70 bg-slate-900/55 p-2.5 space-y-2" data-testid="quick-merged-panel">
                    <div className="text-[10px] text-slate-300 font-semibold">فوري + تدقيق (مُدمج)</div>
                    <div className="grid grid-cols-4 gap-1.5">
                      {PAYMENT_METHODS.map(pm => (
                        <button key={pm.v} type="button" onClick={() => setQuickPM(pm.v)}
                          className={`py-1.5 rounded-lg border text-[10px] ${quickPM===pm.v?'border-sky-500/60 bg-sky-500/20 text-sky-200':'border-slate-700 text-slate-500 hover:text-slate-200'}`}
                          data-testid={`quick-merged-pm-${pm.v}`}>
                          {pm.l}
                        </button>
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <input value={quickDesc} onChange={e => setQuickDesc(e.target.value)}
                        placeholder="وصف فوري (اختياري)"
                        className="w-full rounded-lg px-2 py-1.5 text-[10px] text-slate-100"
                        style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(71,85,105,0.5)' }}
                        data-testid="quick-merged-desc" />
                      <input type="number" min="0" step="0.01" value={quickAmount}
                        onChange={e => setQuickAmount(e.target.value)}
                        placeholder="المبلغ"
                        className="w-full rounded-lg px-2 py-1.5 text-[10px] text-slate-100"
                        style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(34,197,94,0.45)' }}
                        data-testid="quick-merged-amount" />
                    </div>
                    <button type="button" onClick={handleQuickOp} disabled={quickLoading || !quickAmount}
                      className="w-full rounded-lg py-1.5 text-[11px] font-semibold text-white disabled:opacity-40"
                      style={{ background: quickAmount&&!quickLoading?'linear-gradient(135deg,#22c55e,#16a34a)':'rgba(71,85,105,0.5)' }}
                      data-testid="quick-merged-submit">
                      {quickLoading ? 'جارٍ التسجيل...' : '⚡ تسجيل فوري الآن'}
                    </button>
                    {quickResult && (
                      <div className={`rounded-lg p-1.5 text-[10px] text-center ${quickResult.ok?'bg-green-500/10 border border-green-500/30 text-green-300':'bg-red-500/10 border border-red-500/30 text-red-300'}`}
                        data-testid="quick-merged-result">
                        {quickResult.msg}
                      </div>
                    )}
                  </div>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className="max-w-[88%] px-3.5 py-2.5 text-[11px] leading-relaxed"
                      style={m.role === 'user'
                        ? {
                            background: 'linear-gradient(135deg,rgba(14,165,233,0.22),rgba(99,102,241,0.18))',
                            color: 'rgba(186,230,253,0.95)',
                            borderRadius: '18px 18px 4px 18px',
                            border: '1px solid rgba(56,189,248,0.2)',
                          }
                        : {
                            background: 'rgba(255,255,255,0.05)',
                            color: 'rgba(226,232,240,0.92)',
                            borderRadius: '18px 18px 18px 4px',
                            border: '1px solid rgba(255,255,255,0.07)',
                          }
                      }>
                      {m.content}
                      {m.contradictions?.length > 0 && (
                        <div className="mt-1.5 rounded bg-amber-500/10 border border-amber-500/30 p-1.5 text-[10px] text-amber-300">
                          ⚠️ {m.contradictions[0].description?.slice(0, 70)}
                        </div>
                      )}
                      {m.state && (
                        <span className={`mt-1 inline-block rounded-full text-[9px] px-1.5 py-0.5 ${
                          m.state==='escalated'?'bg-red-500/20 text-red-300':m.state==='resolved'?'bg-green-500/20 text-green-300':'bg-sky-500/20 text-sky-300'}`}>
                          {m.state==='escalated'?'مصعّدة':m.state==='resolved'?'محلولة':'قيد التحقيق'}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="flex justify-start">
                    <div className="rounded-xl px-3 py-2 bg-slate-800/80 flex items-center gap-1.5">
                      <Loader size={12} className="text-sky-400 animate-spin" />
                      <span className="text-[10px] text-slate-400">جارٍ التفكير...</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
              <form onSubmit={handleSend} className="flex gap-2 p-3 border-t border-slate-800/60 flex-shrink-0">
                <input value={input} onChange={e => setInput(e.target.value)}
                  placeholder={tab==='quick' ? '"أنشئ قيد" أو راجع الحسابات...' : 'اسأل عن أي شيء...'}
                  className="flex-1 rounded-xl px-3 py-2 text-[11px] text-slate-100 outline-none"
                  style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(71,85,105,0.5)' }}
                  disabled={loading} data-testid="bot-input" />
                <button type="submit" disabled={loading || !input.trim()}
                  className="w-9 h-9 rounded-xl flex items-center justify-center disabled:opacity-40"
                  style={{ background: 'rgba(14,165,233,0.25)', border: '1px solid rgba(14,165,233,0.4)' }}
                  data-testid="bot-send">
                  <Send size={13} className="text-sky-300" />
                </button>
              </form>
            </>
          ) : tab === 'quick' ? (
            /* ─── عملية فورية ──────────────────────────────────────── */
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <div className="text-center pt-2">
                <div className="w-12 h-12 rounded-2xl mx-auto mb-2 flex items-center justify-center"
                  style={{ background: 'linear-gradient(135deg,#22c55e,#16a34a)' }}>
                  <DollarSign size={22} className="text-white" />
                </div>
                <div className="text-sm font-bold text-white">عملية فورية</div>
                <div className="text-[11px] text-slate-400 mt-0.5">قيد + عملية بضغطة واحدة</div>
              </div>
              <div className="grid grid-cols-4 gap-1.5">
                {PAYMENT_METHODS.map(pm => (
                  <button key={pm.v} type="button" onClick={() => setQuickPM(pm.v)}
                    className={`py-2 rounded-xl border text-[11px] font-medium transition-all ${quickPM===pm.v?'border-sky-500/60 bg-sky-500/20 text-sky-200':'border-slate-700 text-slate-400 hover:text-slate-200'}`}
                    data-testid={`quick-pm-${pm.v}`}>
                    <div>{pm.l}</div><div className="text-[9px] opacity-60">{pm.acc}</div>
                  </button>
                ))}
              </div>
              <input value={quickDesc} onChange={e => setQuickDesc(e.target.value)}
                placeholder="الوصف (اختياري) — مثال: صيانة فرامل"
                className="w-full rounded-xl px-3 py-2 text-sm text-slate-100"
                style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(71,85,105,0.5)' }}
                data-testid="quick-desc-input" />
              <input type="number" min="0" step="0.01" value={quickAmount}
                onChange={e => setQuickAmount(e.target.value)}
                placeholder="0.00"
                className="w-full rounded-xl px-3 py-4 text-2xl font-bold text-center text-white"
                style={{ background: 'rgba(30,41,59,0.8)', border: '2px solid rgba(34,197,94,0.4)' }}
                data-testid="quick-amount-input" />
              <div className="grid grid-cols-5 gap-1.5">
                {QUICK_AMOUNTS.map(a => (
                  <button key={a} type="button" onClick={() => setQuickAmount(String(a))}
                    className={`py-1.5 rounded-lg text-[11px] border transition-colors ${quickAmount===String(a)?'border-green-500/60 bg-green-500/15 text-green-300':'border-slate-700 text-slate-500 hover:text-slate-300'}`}>
                    {a}
                  </button>
                ))}
              </div>
              {quickResult && (
                <div className={`rounded-xl p-3 text-sm text-center font-medium ${quickResult.ok?'bg-green-500/10 border border-green-500/30 text-green-300':'bg-red-500/10 border border-red-500/30 text-red-300'}`}
                  data-testid="quick-result">{quickResult.msg}</div>
              )}
              <button type="button" onClick={handleQuickOp} disabled={quickLoading || !quickAmount}
                className="w-full rounded-2xl py-4 text-sm font-bold text-white transition-all disabled:opacity-40"
                style={{ background: quickAmount&&!quickLoading?'linear-gradient(135deg,#22c55e,#16a34a)':'rgba(71,85,105,0.5)' }}
                data-testid="quick-submit-btn">
                {quickLoading ? <Loader size={18} className="animate-spin mx-auto" /> : (
                  <span>⚡ تسجيل فوري{quickAmount&&` — ${Number(quickAmount).toLocaleString('ar-SA')} ر.س`}</span>
                )}
              </button>
              <div className="text-[10px] text-slate-600 text-center">
                يُنشئ عملية فقط؛ ترحيل القيد يتم من الـBackend مرة واحدة.
              </div>
            </div>
          ) : (
            /* ─── تبويب الإنشاء الذكي ──────────────────────────────── */
            <div className="flex-1 overflow-y-auto">
              {/* وضع: ذكي أو يدوي */}
              <div className="flex gap-1.5 p-3 pb-0">
                {[['smart','ذكي ✨'],['manual','يدوي']].map(([v,l]) => (
                  <button key={v} onClick={() => { setCreateMode(v); setSelectedTemplate(null); setCreateResult(null); }}
                    className={`flex-1 text-[11px] py-1.5 rounded-lg border transition-colors font-medium ${
                      createMode===v ? 'border-sky-500/60 bg-sky-500/15 text-sky-300' : 'border-slate-700 text-slate-500 hover:text-slate-300'}`}
                    data-testid={`create-mode-${v}`}>{l}
                  </button>
                ))}
              </div>

              <form onSubmit={handleCreate} className="p-3 space-y-3">
                {createMode === 'smart' ? (
                  <>
                    {/* نماذج سريعة */}
                    <div>
                      <label className="text-[10px] text-slate-400 mb-1.5 block">نوع العملية</label>
                      <div className="grid grid-cols-3 gap-1.5">
                        {SMART_TEMPLATES.map(t => {
                          const Icon = t.icon;
                          const recentForTemplate = templateRecentMap[t.id] || [];
                          return (
                            <button key={t.id} type="button"
                              onClick={() => { setSelectedTemplate(t.id); setCreateResult(null); setInteractiveDraft(null); setItemSearch(''); setItemDropOpen(false); if (t.forcePayment) setPaymentMethod(t.forcePayment); }}
                              className={`rounded-xl p-2 flex flex-col items-center gap-1 border text-[10px] transition-all ${
                                selectedTemplate === t.id
                                  ? 'border-opacity-60 font-semibold'
                                  : 'border-slate-700/60 bg-slate-800/30 text-slate-400 hover:text-slate-200'
                              }`}
                              style={selectedTemplate === t.id ? { borderColor: t.color, background: `${t.color}15`, color: t.color } : {}}
                              data-testid={`template-${t.id}`}>
                              <Icon size={14} />
                              <span>{t.label}</span>
                              <span className="text-[9px] text-slate-400 mt-0.5" data-testid={`template-recent-count-${t.id}`}>
                                آخر {recentForTemplate.length} عمليات
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {selectedTemplate && (
                      <div className="rounded-xl border border-slate-700/70 bg-slate-900/45 p-2" data-testid="template-recent-operations-list">
                        <div className="text-[10px] text-slate-400 mb-1">آخر العمليات لنفس النوع:</div>
                        {(templateRecentMap[selectedTemplate] || []).length === 0 ? (
                          <div className="text-[10px] text-slate-500" data-testid="template-recent-empty">
                            لا توجد عمليات سابقة لهذا النوع بعد.
                          </div>
                        ) : (
                          <div className="space-y-1">
                            {(templateRecentMap[selectedTemplate] || []).map((op, idx) => (
                              <button
                                key={`recent-op-${op.id || idx}`}
                                type="button"
                                onClick={() => {
                                  setAmount(String(op.total || ''));
                                  setPartnerName(op.partnerName || '');
                                  setDescription(op.notes || op.description || '');
                                }}
                                className="w-full text-right rounded-lg px-2 py-1 text-[10px] text-slate-200 hover:bg-sky-500/10 border border-transparent hover:border-sky-500/20"
                                data-testid={`template-recent-op-${idx}`}
                              >
                                {Number(op.total || 0).toLocaleString('ar-SA')} ر.س • {op.partnerName || 'بدون طرف'} • {String(op.date || op.createdAt || '').slice(0, 10)}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* ── قائمة الخدمات عند "بيع خدمة" ── */}
                    {selectedTemplate === 'service_sale' && (
                      <div>
                        <label className="text-[10px] text-slate-400 mb-1 block">
                          اختر خدمة <span className="text-slate-600">({servicesCatalog.length} خدمة متاحة)</span>
                        </label>
                        <div className="relative">
                          <input
                            value={itemSearch}
                            onChange={e => { setItemSearch(e.target.value); setItemDropOpen(true); }}
                            onFocus={() => setItemDropOpen(true)}
                            placeholder="ابحث في قائمة الخدمات..."
                            className="w-full rounded-lg px-2.5 py-1.5 text-[11px] text-slate-100"
                            style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(56,189,248,0.3)' }}
                            data-testid="service-search-input"
                          />
                          {itemDropOpen && (
                            <div className="absolute top-full left-0 right-0 mt-0.5 rounded-lg border border-slate-700 max-h-44 overflow-y-auto z-50"
                              style={{ background: 'rgba(15,23,42,0.99)' }}>
                              {servicesCatalog
                                .filter(s => !itemSearch || s.name?.toLowerCase().includes(itemSearch.toLowerCase()))
                                .slice(0, 50)
                                .map(s => (
                                  <button key={s.id} type="button"
                                    onClick={() => {
                                      setDescription(s.name);
                                      setAmount(String(s.price || ''));
                                      setItemSearch(s.name);
                                      setItemDropOpen(false);
                                    }}
                                    className="w-full text-right px-2.5 py-2 text-[11px] text-slate-200 hover:bg-sky-500/15 flex justify-between items-center border-b border-slate-800/50 last:border-0"
                                    data-testid={`service-option-${s.id}`}>
                                    <span className="text-sky-300 font-medium tabular-nums">{Number(s.price || 0).toLocaleString('ar-SA')} ر.س</span>
                                    <span className="truncate max-w-[65%]">{s.name}</span>
                                  </button>
                                ))}
                              {servicesCatalog.filter(s => !itemSearch || s.name?.toLowerCase().includes(itemSearch.toLowerCase())).length === 0 && (
                                <div className="px-2.5 py-2 text-[10px] text-slate-500">لا توجد نتائج</div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* ── قائمة القطع عند "بيع قطع" ── */}
                    {selectedTemplate === 'parts_sale' && (
                      <div>
                        <label className="text-[10px] text-slate-400 mb-1 block">
                          اختر قطعة <span className="text-slate-600">({partsCatalog.length} قطعة متاحة)</span>
                        </label>
                        <div className="relative">
                          <input
                            value={itemSearch}
                            onChange={e => { setItemSearch(e.target.value); setItemDropOpen(true); }}
                            onFocus={() => setItemDropOpen(true)}
                            placeholder="ابحث في قائمة القطع..."
                            className="w-full rounded-lg px-2.5 py-1.5 text-[11px] text-slate-100"
                            style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(167,139,250,0.3)' }}
                            data-testid="part-search-input"
                          />
                          {itemDropOpen && (
                            <div className="absolute top-full left-0 right-0 mt-0.5 rounded-lg border border-slate-700 max-h-44 overflow-y-auto z-50"
                              style={{ background: 'rgba(15,23,42,0.99)' }}>
                              {partsCatalog
                                .filter(p => !itemSearch || p.name?.toLowerCase().includes(itemSearch.toLowerCase()))
                                .slice(0, 50)
                                .map(p => (
                                  <button key={p.id} type="button"
                                    onClick={() => {
                                      setDescription(p.name);
                                      setAmount(String(p.sellingPrice || p.price || ''));
                                      setItemSearch(p.name);
                                      setItemDropOpen(false);
                                    }}
                                    className="w-full text-right px-2.5 py-2 text-[11px] text-slate-200 hover:bg-violet-500/15 flex justify-between items-center border-b border-slate-800/50 last:border-0"
                                    data-testid={`part-option-${p.id}`}>
                                    <div className="flex flex-col items-end">
                                      <span className="text-violet-300 font-medium tabular-nums">{Number(p.sellingPrice || p.price || 0).toLocaleString('ar-SA')} ر.س</span>
                                      <span className="text-[9px] text-slate-500">متبقي: {p.quantity}</span>
                                    </div>
                                    <span className="truncate max-w-[60%]">{p.name}</span>
                                  </button>
                                ))}
                              {partsCatalog.filter(p => !itemSearch || p.name?.toLowerCase().includes(itemSearch.toLowerCase())).length === 0 && (
                                <div className="px-2.5 py-2 text-[10px] text-slate-500">لا توجد نتائج</div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* وسيلة السداد */}
                    {selectedTemplate && !currentTemplate?.forcePayment && (
                      <div>
                        <label className="text-[10px] text-slate-400 mb-1 block">وسيلة السداد</label>
                        <div className="flex gap-1.5">
                          {PAYMENT_METHODS.map(pm => (
                            <button key={pm.v} type="button" onClick={() => setPaymentMethod(pm.v)}
                              className={`flex-1 py-1.5 rounded-lg border text-[10px] font-medium transition-colors ${
                                paymentMethod===pm.v ? 'border-sky-500/60 bg-sky-500/15 text-sky-300' : 'border-slate-700 text-slate-500'}`}
                              data-testid={`pm-${pm.v}`}>
                              {pm.l}
                              <div className="text-[9px] opacity-60">{pm.acc}</div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* الوصف */}
                    <div>
                      <label className="text-[10px] text-slate-400 mb-1 block">الوصف (اختياري — يُعرَّف النموذج تلقائياً)</label>
                      <input value={description} onChange={e => { setDescription(e.target.value); setInteractiveDraft(null); }}
                        placeholder="مثال: صيانة فرامل، فطور عمال، شراء زيت..."
                        className="w-full rounded-lg px-2.5 py-1.5 text-[11px] text-slate-100"
                        style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(71,85,105,0.5)' }} />
                    </div>

                    {/* اسم الشريك */}
                    <div>
                      <label className="text-[10px] text-slate-400 mb-1 block">
                        {currentTemplate?.opType === 'purchase' ? 'اسم المورد' : 'اسم العميل'} (اختياري — لإنشاء عملية أيضاً)
                      </label>
                      <input value={partnerName} onChange={e => { setPartnerName(e.target.value); setInteractiveDraft(null); }}
                        placeholder="اترك فارغاً لقيد فقط"
                        className="w-full rounded-lg px-2.5 py-1.5 text-[11px] text-slate-100"
                        style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(71,85,105,0.5)' }}
                        data-testid="create-partner-input" />
                    </div>

                    {/* ربط مركبة حالية */}
                    <div>
                      <label className="text-[10px] text-slate-400 mb-1 block">ربط مركبة (اختياري)</label>
                      <div className="relative">
                        <input
                          value={selectedVehicle
                            ? `${selectedVehicle.plateNumber} — ${selectedVehicle.customerName}`
                            : vehicleSearch}
                          onChange={e => { setVehicleSearch(e.target.value); setSelectedVehicle(null); setVehicleDropOpen(true); }}
                          onFocus={() => setVehicleDropOpen(true)}
                          placeholder="ابحث برقم اللوحة أو اسم العميل..."
                          className="w-full rounded-lg px-2.5 py-1.5 text-[11px] text-slate-100 pr-7"
                          style={{ background: 'rgba(30,41,59,0.8)', border: `1px solid ${selectedVehicle ? 'rgba(56,189,248,0.5)' : 'rgba(71,85,105,0.5)'}` }}
                          data-testid="create-vehicle-search"
                        />
                        {selectedVehicle && (
                          <button type="button" onClick={() => { setSelectedVehicle(null); setVehicleSearch(''); setPartnerName(''); }}
                            className="absolute left-1.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200">
                            <X size={11} />
                          </button>
                        )}
                        {vehicleDropOpen && !selectedVehicle && (
                          <div className="absolute top-full left-0 right-0 mt-0.5 rounded-lg border border-slate-700 max-h-36 overflow-y-auto z-50"
                            style={{ background: 'rgba(15,23,42,0.98)' }}>
                            {vehicles
                              .filter(v => {
                                const q = vehicleSearch.toLowerCase();
                                return !q || v.plateNumber?.toLowerCase().includes(q) || v.customerName?.toLowerCase().includes(q);
                              })
                              .slice(0, 15)
                              .map(v => (
                                <button key={v.id} type="button"
                                  onClick={() => { setSelectedVehicle(v); setVehicleSearch(''); setVehicleDropOpen(false); setPartnerName(v.customerName || ''); }}
                                  className="w-full text-right px-2.5 py-1.5 text-[11px] text-slate-200 hover:bg-sky-500/15 flex justify-between items-center"
                                  data-testid={`vehicle-option-${v.id}`}>
                                  <span className="text-slate-400 text-[10px]">{v.customerName}</span>
                                  <span className="font-medium text-sky-300">{v.plateNumber}</span>
                                </button>
                              ))}
                            {vehicles.filter(v => {
                              const q = vehicleSearch.toLowerCase();
                              return !q || v.plateNumber?.toLowerCase().includes(q) || v.customerName?.toLowerCase().includes(q);
                            }).length === 0 && (
                              <div className="px-2.5 py-2 text-[10px] text-slate-500">لا توجد نتائج</div>
                            )}
                          </div>
                        )}
                      </div>
                      {selectedVehicle && (
                        <div className="mt-1 text-[10px] text-sky-400 flex items-center gap-1">
                          ✓ مرتبط: {selectedVehicle.plateNumber} — {selectedVehicle.brand} {selectedVehicle.model}
                        </div>
                      )}
                    </div>

                    {/* اختيار حساب خاص (override) */}
                    <div>
                      <label className="text-[10px] text-slate-400 mb-1 block">حساب خاص (اختياري — يُبدّل حساب الإيراد/المصروف)</label>
                      <select
                        value={selectedAccount?.code || ''}
                        onChange={e => {
                          const acc = SPECIAL_ACCOUNTS.find(a => a.code === e.target.value);
                          setSelectedAccount(acc || null);
                        }}
                        className="w-full rounded-lg px-2 py-1.5 text-[11px] text-slate-100"
                        style={{ background: 'rgba(30,41,59,0.8)', border: `1px solid ${selectedAccount ? 'rgba(167,139,250,0.5)' : 'rgba(71,85,105,0.5)'}` }}
                        data-testid="special-account-select"
                      >
                        <option value="">الحساب الافتراضي من النموذج</option>
                        {Object.entries(
                          SPECIAL_ACCOUNTS.reduce((g, a) => ({ ...g, [a.group]: [...(g[a.group]||[]), a] }), {})
                        ).map(([group, accs]) => (
                          <optgroup key={group} label={group}>
                            {accs.map(a => (
                              <option key={a.code} value={a.code}>[{a.code}] {a.name}</option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                      {selectedAccount && (
                        <div className="mt-1 text-[10px] text-violet-400 flex items-center gap-1">
                          ✓ مُبدَّل إلى: [{selectedAccount.code}] {selectedAccount.name}
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  /* ─── وضع يدوي ──────────────────────────────────────── */
                  <>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[10px] text-slate-400 mb-1 block">حساب المدين</label>
                        <input value={customDebit} onChange={e => setCustomDebit(e.target.value)}
                          placeholder="مثال: 036"
                          className="w-full rounded-lg px-2.5 py-1.5 text-[11px] text-slate-100"
                          style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(71,85,105,0.5)' }} />
                        {customDebit && <div className="text-[9px] text-sky-400 mt-0.5">{ACCOUNTS[customDebit] || '—'}</div>}
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 mb-1 block">حساب الدائن</label>
                        <input value={customCredit} onChange={e => setCustomCredit(e.target.value)}
                          placeholder="مثال: 004"
                          className="w-full rounded-lg px-2.5 py-1.5 text-[11px] text-slate-100"
                          style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(71,85,105,0.5)' }} />
                        {customCredit && <div className="text-[9px] text-sky-400 mt-0.5">{ACCOUNTS[customCredit] || '—'}</div>}
                      </div>
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 mb-1 block">الوصف</label>
                      <input value={description} onChange={e => setDescription(e.target.value)}
                        placeholder="وصف القيد..."
                        className="w-full rounded-lg px-2.5 py-1.5 text-[11px] text-slate-100"
                        style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(71,85,105,0.5)' }} />
                    </div>
                  </>
                )}

                {/* التاريخ + المبلغ */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-slate-400 mb-1 block">التاريخ</label>
                    <input type="date" value={date} onChange={e => setDate(e.target.value)}
                      className="w-full rounded-lg px-2 py-1.5 text-[11px] text-slate-100"
                      style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(71,85,105,0.5)' }} />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 mb-1 block">المبلغ (ر.س)</label>
                    <input type="number" min="0" step="0.01" value={amount} onChange={e => { setAmount(e.target.value); setInteractiveDraft(null); }}
                      placeholder="0.00"
                      className="w-full rounded-lg px-2.5 py-1.5 text-[11px] text-slate-100"
                      style={{ background: 'rgba(30,41,59,0.8)', border: '1px solid rgba(71,85,105,0.5)' }}
                      data-testid="create-amount-input" />
                  </div>
                </div>

                {/* أزرار مبالغ سريعة */}
                <div className="flex gap-1.5 flex-wrap">
                  {QUICK_AMOUNTS.map(a => (
                    <button key={a} type="button" onClick={() => setAmount(String(a))}
                      className={`px-2 py-1 rounded-lg text-[10px] border transition-colors ${
                        amount===String(a) ? 'border-sky-500/60 bg-sky-500/15 text-sky-300' : 'border-slate-700 text-slate-500 hover:text-slate-300'}`}>
                      {a}
                    </button>
                  ))}
                </div>

                {/* معاينة القيد */}
                {previewLines.length > 0 && (
                  <div className={`rounded-xl border p-2.5 ${isBalanced ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'}`}
                    data-testid="journal-preview">
                    <div className="flex items-center gap-1.5 mb-1.5 text-[10px] font-semibold">
                      {isBalanced ? <CheckCircle size={12} className="text-green-400" /> : <AlertCircle size={12} className="text-red-400" />}
                      <span className={isBalanced ? 'text-green-300' : 'text-red-300'}>
                        {isBalanced ? 'قيد متوازن ✓' : 'قيد غير متوازن'}
                      </span>
                    </div>
                    {previewLines.map((l, i) => (
                      <div key={i} className="flex justify-between items-center text-[10px] py-0.5">
                        <span className="text-slate-300">[{l.account}] {l.name}</span>
                        <div className="flex gap-3">
                          {l.debit  > 0 && <span className="text-red-300">د {l.debit.toLocaleString('ar-SA')}</span>}
                          {l.credit > 0 && <span className="text-green-300">ء {l.credit.toLocaleString('ar-SA')}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {interactiveDraft && (
                  <div className="rounded-xl border border-sky-500/25 bg-sky-500/10 p-2.5 space-y-2" data-testid="interactive-draft-cards">
                    <div className="text-[11px] font-semibold text-sky-200">معاينة تفاعلية قبل التأكيد</div>

                    <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                      <button type="button" onClick={() => setSelectedTemplate(interactiveDraft.templateId)}
                        className="text-right rounded-lg border border-slate-600 bg-slate-900/40 px-2 py-1 text-slate-100"
                        data-testid="draft-card-type">
                        النوع: {interactiveDraft.templateLabel}
                      </button>
                      <button type="button" onClick={() => focusCreateField('الطرف')}
                        className="text-right rounded-lg border border-slate-600 bg-slate-900/40 px-2 py-1 text-slate-100"
                        data-testid="draft-card-partner">
                        الطرف: {interactiveDraft.partnerName || 'غير محدد'}
                      </button>
                      <button type="button" onClick={() => focusCreateField('المبلغ')}
                        className="text-right rounded-lg border border-slate-600 bg-slate-900/40 px-2 py-1 text-slate-100 col-span-2"
                        data-testid="draft-card-amount">
                        المبلغ: {interactiveDraft.amount || 'غير محدد'}
                      </button>
                    </div>

                    {interactiveDraft.missing?.length > 0 && (
                      <div className="flex flex-wrap gap-1" data-testid="draft-missing-chips">
                        {interactiveDraft.missing.map((m, idx) => (
                          <button
                            key={`missing-${idx}`}
                            type="button"
                            onClick={() => focusCreateField(m)}
                            className="px-2 py-0.5 rounded-full text-[10px] border border-amber-500/40 bg-amber-500/10 text-amber-200"
                            data-testid={`draft-missing-${idx}`}
                          >
                            {m}
                          </button>
                        ))}
                      </div>
                    )}

                    {interactiveDraft.partnerName && !interactiveDraft.selectedVehicleId && (
                      <div className="space-y-1" data-testid="draft-vehicle-candidates">
                        <div className="text-[10px] text-slate-300">مركبات العميل المطابقة:</div>
                        {(interactiveDraft.vehicleCandidates || []).length === 0 ? (
                          <div className="text-[10px] text-slate-500">لا توجد مركبات مطابقة بالاسم.</div>
                        ) : (
                          <div className="space-y-1">
                            {(interactiveDraft.vehicleCandidates || []).map((v, idx) => (
                              <button
                                key={`candidate-${v.id || idx}`}
                                type="button"
                                onClick={() => handleSelectDraftVehicle(v)}
                                className="w-full text-right px-2 py-1 rounded-lg text-[10px] border border-slate-600 bg-slate-900/40 text-slate-100 hover:border-sky-500/40"
                                data-testid={`draft-vehicle-candidate-${idx}`}
                              >
                                {v.plateNumber} • {v.model} • {v.customerName}
                              </button>
                            ))}
                          </div>
                        )}
                        <button
                          type="button"
                          onClick={handleAddNewVehicleFromDraft}
                          className="w-full text-center px-2 py-1 rounded-lg text-[10px] border border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                          data-testid="draft-add-new-vehicle"
                        >
                          + إضافة مركبة جديدة
                        </button>
                      </div>
                    )}

                    <div className="grid grid-cols-3 gap-1.5" data-testid="draft-action-buttons">
                      <button
                        type="button"
                        onClick={() => handleCreate()}
                        disabled={loading || !isBalanced}
                        className="rounded-lg py-1.5 text-[10px] font-semibold text-white disabled:opacity-40"
                        style={{ background: 'linear-gradient(135deg,#22c55e,#16a34a)' }}
                        data-testid="draft-action-confirm"
                      >
                        تأكيد الآن
                      </button>
                      <button
                        type="button"
                        onClick={() => setCreateResult({ ok: false, msg: 'يمكنك تعديل الحقول ثم الضغط على التنفيذ.' })}
                        className="rounded-lg py-1.5 text-[10px] font-semibold text-slate-100 border border-slate-600"
                        data-testid="draft-action-edit"
                      >
                        تعديل الحقول
                      </button>
                      <button
                        type="button"
                        onClick={() => { setInteractiveDraft(null); setCreateResult({ ok: false, msg: 'تم إلغاء المعاينة.' }); }}
                        className="rounded-lg py-1.5 text-[10px] font-semibold text-rose-200 border border-rose-500/40"
                        data-testid="draft-action-cancel"
                      >
                        إلغاء
                      </button>
                    </div>
                  </div>
                )}

                {createResult && (
                  <div className={`rounded-lg p-2 text-[11px] ${
                    createResult.ok ? 'bg-green-500/10 border border-green-500/30 text-green-300' : 'bg-red-500/10 border border-red-500/30 text-red-300'
                  }`} data-testid="create-result">{createResult.msg}</div>
                )}

                <button type="submit" disabled={loading || !isBalanced}
                  className="w-full rounded-xl py-2.5 text-xs font-bold text-white transition-all disabled:opacity-40"
                  style={{ background: isBalanced ? 'linear-gradient(135deg,#0ea5e9,#6366f1)' : 'rgba(71,85,105,0.5)' }}
                  data-testid="create-submit-btn">
                  {loading ? <Loader size={14} className="animate-spin mx-auto" /> :
                    partnerName ? 'إنشاء القيد + العملية' : 'إنشاء القيد'}
                </button>

                {/* مقترحات */}
                <div className="rounded-xl border border-dashed border-slate-700 p-2.5 text-[10px] text-slate-500 space-y-1">
                  <div className="font-semibold text-slate-400 mb-1">💡 اقتراحات سريعة:</div>
                  {[
                    ['بيع خدمة بنك', () => { setSelectedTemplate('service_sale'); setPaymentMethod('bank'); }],
                    ['مصروف نقدي', () => { setSelectedTemplate('expense'); setPaymentMethod('cash'); }],
                    ['رواتب عمال', () => { setSelectedTemplate('salary'); setPaymentMethod('bank'); }],
                    ['مشتريات آجل', () => { setSelectedTemplate('purchase'); setPaymentMethod('credit'); }],
                  ].map(([l, fn]) => (
                    <button key={l} type="button" onClick={fn}
                      className="w-full text-right py-1 px-2 rounded-lg hover:bg-white/5 text-slate-400 hover:text-sky-300 transition-colors">
                      → {l}
                    </button>
                  ))}
                </div>
              </form>
            </div>
          )}

          {pageSuggestion && (
            <div
              className="absolute bottom-16 right-3 w-[88%] rounded-xl border border-slate-200 shadow-2xl p-3"
              style={{ background: 'rgba(255,255,255,0.98)' }}
              data-testid="page-suggestion-box"
            >
              <div className="text-[11px] font-semibold text-slate-800 mb-1">اقتراح تلقائي</div>
              <div className="text-[11px] text-slate-700 mb-2" data-testid="page-suggestion-message">
                {pageSuggestion.message}
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => handleSuggestionDecision(true)}
                  disabled={suggestionBusy}
                  className="flex-1 rounded-lg py-1.5 text-[11px] font-semibold text-white"
                  style={{ background: 'linear-gradient(135deg,#22c55e,#16a34a)' }}
                  data-testid="page-suggestion-apply"
                >
                  {suggestionBusy ? '...' : 'تطبيق'}
                </button>
                <button
                  type="button"
                  onClick={() => handleSuggestionDecision(false)}
                  disabled={suggestionBusy}
                  className="flex-1 rounded-lg py-1.5 text-[11px] font-semibold text-slate-700 border border-slate-300"
                  data-testid="page-suggestion-ignore"
                >
                  تجاهل
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
