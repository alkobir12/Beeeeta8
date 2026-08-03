/* eslint-disable */

import React, { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useLocation } from 'react-router-dom';
import {
  Brain,
  RefreshCw,
  Send,
  Loader2,
  AlertTriangle,
  CheckCircle,
  Shield,
  Car,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Receipt,
  Scale,
  Trash2,
  FileText,
  ListChecks,
} from 'lucide-react';

import FinancialCard from '../components/FinancialCard';
import QuickCard from '../components/QuickCard';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';

import { aiAPI, financeAPI, vehicleAPI } from '../services/api';
import { formatCurrency } from '../utils/formatters';
import { resolveBackendBase } from '../utils/backendBase';
import WorkshopAIBot from '../components/WorkshopAIBot';

const STORAGE_KEYS = {
  sessions: 'finance_bot_sessions_v1',
  messages: 'finance_bot_session_messages_v1',
  activeSession: 'finance_bot_active_session_v1',
};

function useQuery() {
  const { search } = useLocation();
  return useMemo(() => new URLSearchParams(search), [search]);
}

export default function AIFinancial() {
  const assistantOnlyMode = true;

  const query = useQuery();
  const vehicleId = query.get('vehicleId') || query.get('vehicle_id') || '';

  const workshopId = process.env.REACT_APP_WORKSHOP_ID;

  const [timeRange, setTimeRange] = useState('month');
  const [assistantTab, setAssistantTab] = useState('finance');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [summary, setSummary] = useState({
    revenue: 0,
    expenses: 0,
    netProfit: 0,
    profitMargin: 0,
    assets: 0,
    liabilities: 0,
    equity: 0,
  });

  const [trialBalance, setTrialBalance] = useState({ accounts: [], totals: null });
  const [accounts, setAccounts] = useState([]);

  // Chat (AbuFahad)
  const [chatSessions, setChatSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState('');
  const [sessionMessages, setSessionMessages] = useState({});
  const [selectedAccountCode, setSelectedAccountCode] = useState('');
  const [chatQuery, setChatQuery] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  const chatHistory = sessionMessages[activeSessionId] || [];
  const activeSession = chatSessions.find((s) => s.id === activeSessionId);

  // Audit
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditReport, setAuditReport] = useState(null);
  const [auditBotLoading, setAuditBotLoading] = useState(false);
  const [auditBotResponse, setAuditBotResponse] = useState('');

  // Vehicle
  const [vehicle, setVehicle] = useState(null);
  const [vehicleLoading, setVehicleLoading] = useState(false);

  const getStartDate = (range) => {
    const now = new Date();
    const d = new Date(now);
    switch (range) {
      case 'week':
        d.setDate(d.getDate() - 7);
        break;
      case 'month':
        d.setMonth(d.getMonth() - 1);
        break;
      case 'quarter':
        d.setMonth(d.getMonth() - 3);
        break;
      case 'year':
        d.setFullYear(d.getFullYear() - 1);
        break;
      default:
        d.setMonth(d.getMonth() - 1);
    }
    return d.toISOString().split('T')[0];
  };

  const generateSessionId = () => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return `session_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  };

  const defaultGreeting = {
    role: 'assistant',
    content:
      'مرحباً، أنا أبوفهد المحاسب المالي للورشة. ماذا تحب أن نحلّل اليوم؟ هل تريد نظرة عامة على الربحية والسيولة، أم تدقيق حساب محدد (مثل 411 أو 514)؟',
  };

  const persistChatToStorage = (nextSessions, nextMessages, nextActiveId) => {
    try {
      localStorage.setItem(STORAGE_KEYS.sessions, JSON.stringify(nextSessions));
      localStorage.setItem(STORAGE_KEYS.messages, JSON.stringify(nextMessages));
      if (nextActiveId) localStorage.setItem(STORAGE_KEYS.activeSession, nextActiveId);
    } catch (e) {}
  };

  const loadChatFromStorage = () => {
    let storedSessions = [];
    let storedMessages = {};
    let storedActive = '';

    try {
      storedSessions = JSON.parse(localStorage.getItem(STORAGE_KEYS.sessions) || '[]');
    } catch (e) {}

    try {
      storedMessages = JSON.parse(localStorage.getItem(STORAGE_KEYS.messages) || '{}');
    } catch (e) {}

    try {
      storedActive = localStorage.getItem(STORAGE_KEYS.activeSession) || '';
    } catch (e) {}

    if (!Array.isArray(storedSessions) || storedSessions.length === 0) {
      const newId = generateSessionId();
      storedSessions = [
        {
          id: newId,
          title: 'جلسة جديدة',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
      ];
      storedActive = newId;
      storedMessages = { [newId]: [defaultGreeting] };
    }

    if (!storedActive) {
      storedActive = storedSessions[0].id;
    }

    if (!storedMessages[storedActive]) {
      storedMessages[storedActive] = [defaultGreeting];
    }

    setChatSessions(storedSessions);
    setActiveSessionId(storedActive);
    setSessionMessages(storedMessages);
    persistChatToStorage(storedSessions, storedMessages, storedActive);
  };

  const updateSessionMeta = (sessions, sessionId, userText) => {
    const now = new Date().toISOString();
    return sessions.map((s) => {
      if (s.id !== sessionId) return s;
      const nextTitle = s.title && s.title !== 'جلسة جديدة' ? s.title : userText.slice(0, 24);
      return { ...s, title: nextTitle || 'جلسة جديدة', updatedAt: now };
    });
  };

  const createNewSession = () => {
    const newId = generateSessionId();
    const now = new Date().toISOString();
    const newSession = { id: newId, title: 'جلسة جديدة', createdAt: now, updatedAt: now };
    const nextSessions = [newSession, ...chatSessions];
    const nextMessages = { ...sessionMessages, [newId]: [defaultGreeting] };
    setChatSessions(nextSessions);
    setActiveSessionId(newId);
    setSessionMessages(nextMessages);
    setSelectedAccountCode('');
    persistChatToStorage(nextSessions, nextMessages, newId);
  };

  const selectSession = (sessionId) => {
    if (!sessionId) return;
    setActiveSessionId(sessionId);
    if (!sessionMessages[sessionId]) {
      const nextMessages = { ...sessionMessages, [sessionId]: [defaultGreeting] };
      setSessionMessages(nextMessages);
      persistChatToStorage(chatSessions, nextMessages, sessionId);
      return;
    }
    persistChatToStorage(chatSessions, sessionMessages, sessionId);
  };

  const deleteSession = (sessionId) => {
    const remaining = chatSessions.filter((s) => s.id !== sessionId);
    const nextMessages = { ...sessionMessages };
    delete nextMessages[sessionId];
    let nextActive = activeSessionId;
    if (activeSessionId === sessionId) {
      nextActive = remaining[0]?.id || '';
    }

    if (!remaining.length) {
      const newId = generateSessionId();
      remaining.push({
        id: newId,
        title: 'جلسة جديدة',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });
      nextMessages[newId] = [defaultGreeting];
      nextActive = newId;
    }

    setChatSessions(remaining);
    setSessionMessages(nextMessages);
    setActiveSessionId(nextActive);
    persistChatToStorage(remaining, nextMessages, nextActive);
  };

  const fetchCoreFinancials = async () => {
    if (!workshopId) {
      setError('لم يتم ضبط REACT_APP_WORKSHOP_ID. يرجى ضبط معرف الورشة.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError('');

    try {
      const endDate = new Date().toISOString().split('T')[0];
      const startDate = getStartDate(timeRange);

      const [incomeRes, balanceRes, trialRes] = await Promise.all([
        financeAPI.getIncomeStatement({ workshop_id: workshopId, start_date: startDate, end_date: endDate }),
        financeAPI.getBalanceSheet({ workshop_id: workshopId }),
        financeAPI.getTrialBalance({ workshop_id: workshopId }),
      ]);

      const incomeData = incomeRes.data?.data;
      const balanceData = balanceRes.data?.data;
      const trialData = trialRes.data?.data;

      const revenue = incomeData?.totals?.revenue || 0;
      const expenses = incomeData?.totals?.expenses || 0;
      const netProfit = incomeData?.totals?.net_income ?? revenue - expenses;
      const profitMargin = revenue > 0 ? (netProfit / revenue) * 100 : 0;

      const assets = balanceData?.totals?.assets || 0;
      const liabilities = balanceData?.totals?.liabilities || 0;
      const equity = balanceData?.totals?.equity || 0;

      setSummary({ revenue, expenses, netProfit, profitMargin, assets, liabilities, equity });
      setTrialBalance({ accounts: trialData?.accounts || [], totals: trialData?.totals || null });
    } catch (e) {
      console.error(e);
      setError('تعذر جلب البيانات المالية.');
    } finally {
      setLoading(false);
    }
  };

  const fetchAccounts = async () => {
    try {
      const res = await financeAPI.getChartOfAccounts();
      const data = res.data?.data ?? res.data?.accounts ?? res.data;
      const list = Array.isArray(data) ? data : [];
      setAccounts(list);
    } catch (e) {
      // non-blocking
      setAccounts([]);
    }
  };

  const fetchVehicleIfNeeded = async () => {
    if (!vehicleId) return;
    setVehicleLoading(true);
    try {
      const res = await vehicleAPI.getById(vehicleId);
      setVehicle(res.data);
    } catch (e) {
      setVehicle(null);
    } finally {
      setVehicleLoading(false);
    }
  };

  const runAudit = async () => {
    if (!workshopId) return;
    setAuditLoading(true);
    setAuditBotResponse('');

    try {
      const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);
      const resp = await fetch(`${API_URL}/finance/audit-system?workshop_id=${workshopId}`, { method: 'POST' });
      const data = await resp.json();
      if (data?.success) {
        setAuditReport(data.data);
      } else {
        setAuditReport(null);
      }
    } catch (e) {
      setAuditReport(null);
    } finally {
      setAuditLoading(false);
    }
  };

  const analyzeAuditWithAbuFahad = async () => {
    if (!auditReport) return;

    setAuditBotLoading(true);
    try {
      const summaryParts = [];
      if (auditReport.summary) {
        summaryParts.push(`ملخص التدقيق:\n${JSON.stringify(auditReport.summary, null, 2)}`);
      }
      if (auditReport.corrections_needed?.length) {
        summaryParts.push(
          'تصحيحات مطلوبة:\n' +
            auditReport.corrections_needed
              .map((c, idx) => `${idx + 1}- ${c.issue} | تصحيح مقترح: ${c.correction || '-'} | اقتراح: ${c.suggestion || '-'}`)
              .join('\n')
        );
      }

      const payload = {
        message:
          `${summaryParts.join('\n\n')}\n\n` +
          'حلّل تقرير التدقيق أعلاه بإيجاز شديد: سطر ملخص، ثم 3 نقاط مخاطر، ثم توصيتين كحد أقصى.',
        workshop_id: workshopId,
      };

      const res = await aiAPI.financeBotChat(payload);
      setAuditBotResponse(res.data?.response || 'تعذر الحصول على تحليل من أبوفهد.');
    } catch (e) {
      const detail = e?.response?.data?.detail || e?.message;
      setAuditBotResponse(
        detail
          ? `تعذر الاتصال بأبوفهد لتحليل تقرير التدقيق.\nتفاصيل: ${detail}`
          : 'تعذر الاتصال بأبوفهد لتحليل تقرير التدقيق.'
      );
    } finally {
      setAuditBotLoading(false);
    }
  };

  const getProfitVariant = () => {
    if (summary.profitMargin >= 20) return 'success';
    if (summary.profitMargin >= 10) return 'warning';
    return 'danger';
  };

  const riskQuickCards = useMemo(() => {
    const cards = [];

    if (summary.profitMargin < 10) {
      cards.push({
        title: 'تنبيه الربحية',
        value: 'هامش الربح منخفض جداً',
        subtitle: `الهامش الحالي ${summary.profitMargin.toFixed(1)}%`,
        icon: AlertTriangle,
        variant: 'danger',
      });
    } else if (summary.profitMargin < 20) {
      cards.push({
        title: 'تحسين الربحية',
        value: 'هامش الربح يحتاج رفع',
        subtitle: `الهامش الحالي ${summary.profitMargin.toFixed(1)}%`,
        icon: AlertTriangle,
        variant: 'warning',
      });
    } else {
      cards.push({
        title: 'الربحية',
        value: 'الأداء ممتاز',
        subtitle: `الهامش الحالي ${summary.profitMargin.toFixed(1)}%`,
        icon: CheckCircle,
        variant: 'success',
      });
    }

    if (summary.liabilities > summary.assets * 0.5 && summary.assets > 0) {
      cards.push({
        title: 'الديون',
        value: 'نسبة التزامات مرتفعة',
        subtitle: 'راجع جدول السداد والسيولة',
        icon: AlertTriangle,
        variant: 'warning',
      });
    }

    if (trialBalance.accounts?.length === 0) {
      cards.push({
        title: 'الميزان',
        value: 'لا توجد بيانات ميزان مراجعة',
        subtitle: 'تحقق من القيود اليومية والعمليات',
        icon: Scale,
        variant: 'warning',
      });
    }

    return cards.slice(0, 4);
  }, [summary, trialBalance.accounts]);

  const auditPreview = useMemo(() => {
    if (!auditBotResponse) return '';
    return auditBotResponse.split('\n').slice(0, 4).join('\n');
  }, [auditBotResponse]);

  const auditSummaryDetails = useMemo(() => {
    if (!auditReport) return [];
    return [
      { label: 'الأخطاء', value: auditReport.summary?.total_issues ?? 0 },
      { label: 'التصحيحات', value: auditReport.summary?.corrections_needed ?? 0 },
      { label: 'النواقص', value: auditReport.summary?.missing_items ?? 0 },
      { label: 'السجل', value: auditReport.summary?.audit_log_entries ?? 0 },
    ];
  }, [auditReport]);

  const auditAnalysisDetails = useMemo(() => {
    if (!auditBotResponse) return [];
    return [{ label: 'ملخص سريع', value: auditPreview }];
  }, [auditBotResponse, auditPreview]);

  const summaryCards = useMemo(() => ([
    {
      title: 'إجمالي الإيرادات',
      value: formatCurrency(summary.revenue),
      subtitle: 'ملخص الإيرادات للفترة المختارة',
      icon: DollarSign,
      variant: 'default',
      details: [
        { label: 'صافي الربح', value: formatCurrency(summary.netProfit) },
        { label: 'المصروفات', value: formatCurrency(summary.expenses) },
        { label: 'هامش الربح', value: `${summary.profitMargin.toFixed(1)}%` },
      ],
    },
    {
      title: 'صافي الربح',
      value: formatCurrency(summary.netProfit),
      subtitle: `هامش ${summary.profitMargin.toFixed(1)}%`,
      icon: summary.netProfit >= 0 ? TrendingUp : TrendingDown,
      variant: getProfitVariant(),
      details: [
        { label: 'الإيرادات', value: formatCurrency(summary.revenue) },
        { label: 'المصروفات', value: formatCurrency(summary.expenses) },
      ],
    },
    {
      title: 'إجمالي المصروفات',
      value: formatCurrency(summary.expenses),
      subtitle: 'المدفوعات والتكاليف التشغيلية',
      icon: Receipt,
      variant: 'warning',
      details: [
        { label: 'صافي الربح', value: formatCurrency(summary.netProfit) },
        { label: 'هامش الربح', value: `${summary.profitMargin.toFixed(1)}%` },
      ],
    },
    {
      title: 'ميزان المراجعة',
      value: trialBalance.accounts?.length ? `${trialBalance.accounts.length} حساب` : 'بدون بيانات',
      subtitle: trialBalance.totals
        ? `مدين ${formatCurrency(trialBalance.totals.total_debit)} | دائن ${formatCurrency(trialBalance.totals.total_credit)}`
        : 'لا توجد حركة',
      icon: Scale,
      variant: trialBalance.accounts?.length ? 'success' : 'warning',
      details: [
        { label: 'إجمالي المدين', value: formatCurrency(trialBalance.totals?.total_debit || 0) },
        { label: 'إجمالي الدائن', value: formatCurrency(trialBalance.totals?.total_credit || 0) },
        { label: 'عدد الحسابات', value: trialBalance.accounts?.length || 0 },
      ],
    },
  ]), [summary, trialBalance]);

  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatQuery.trim()) return;

    const userText = chatQuery;
    const userMsg = { role: 'user', content: userText };

    const currentSessionId = activeSessionId || generateSessionId();
    const currentMessages = sessionMessages[currentSessionId] || [defaultGreeting];
    const optimistic = [...currentMessages, userMsg];
    const nextMessagesMap = { ...sessionMessages, [currentSessionId]: optimistic };

    let nextSessions = chatSessions;
    if (!chatSessions.find((s) => s.id === currentSessionId)) {
      const now = new Date().toISOString();
      nextSessions = [
        { id: currentSessionId, title: userText.slice(0, 24) || 'جلسة جديدة', createdAt: now, updatedAt: now },
        ...chatSessions,
      ];
    } else {
      nextSessions = updateSessionMeta(chatSessions, currentSessionId, userText);
    }

    setChatSessions(nextSessions);
    setActiveSessionId(currentSessionId);
    setSessionMessages(nextMessagesMap);
    setChatQuery('');
    setChatLoading(true);
    persistChatToStorage(nextSessions, nextMessagesMap, currentSessionId);

    try {
      const payload = {
        message: userText,
        workshop_id: workshopId,
        account_code: selectedAccountCode || undefined,
        conversation_id: currentSessionId || undefined,
        // تزويد أبوفهد بملخص مالي صغير لتمكين التحليل القواعدي (P1)
        financial_data: {
          revenue: summary.revenue,
          expenses: summary.expenses,
          net_profit: summary.netProfit,
          assets: summary.assets,
          liabilities: summary.liabilities,
        },
      };

      const res = await aiAPI.financeBotChat(payload);

      const botMsg = {
        role: 'assistant',
        content: res.data?.response || 'تعذر الحصول على رد من أبوفهد حالياً.',
      };

      const resolvedId = res.data?.conversation_id || currentSessionId;
      let updatedSessions = nextSessions;
      let updatedMessagesMap = { ...nextMessagesMap };

      if (resolvedId !== currentSessionId) {
        updatedMessagesMap[resolvedId] = updatedMessagesMap[currentSessionId] || optimistic;
        delete updatedMessagesMap[currentSessionId];
        updatedSessions = nextSessions.map((s) =>
          s.id === currentSessionId ? { ...s, id: resolvedId } : s
        );
        setActiveSessionId(resolvedId);
      }

      const next = [...(updatedMessagesMap[resolvedId] || []), botMsg];
      updatedMessagesMap[resolvedId] = next;
      updatedSessions = updateSessionMeta(updatedSessions, resolvedId, userText);
      setChatSessions(updatedSessions);
      setSessionMessages(updatedMessagesMap);
      persistChatToStorage(updatedSessions, updatedMessagesMap, resolvedId);
    } catch (e) {
      const detail = e?.response?.data?.detail || e?.message;
      const errText = detail
        ? `تعذر الاتصال بأبوفهد. حاول مرة أخرى.\nتفاصيل: ${detail}`
        : 'تعذر الاتصال بأبوفهد. حاول مرة أخرى.';

      const next = [
        ...optimistic,
        { role: 'assistant', content: errText },
      ];
      const updatedMessagesMap = { ...nextMessagesMap, [currentSessionId]: next };
      setSessionMessages(updatedMessagesMap);
      persistChatToStorage(nextSessions, updatedMessagesMap, currentSessionId);
    } finally {
      setChatLoading(false);
    }
  };

  const clearChat = () => {
    createNewSession();
  };

  useEffect(() => {
    if (assistantOnlyMode) return;
    loadChatFromStorage();
    fetchAccounts();
  }, [assistantOnlyMode]);

  useEffect(() => {
    if (assistantOnlyMode) return;
    fetchVehicleIfNeeded();
  }, [vehicleId, assistantOnlyMode]);

  useEffect(() => {
    if (assistantOnlyMode) return;
    fetchCoreFinancials();
  }, [workshopId, timeRange, assistantOnlyMode]);

  // تحسين بسيط: فتح محادثة أبوفهد تلقائياً إذا لم يكن هناك تاريخ محادثة
  useEffect(() => {
    if (assistantOnlyMode) return;
    if (!chatHistory?.length) return;
    // لا شيء هنا حالياً، فقط مكان مخصص لتحسينات UX لاحقاً بدون كسر السلوك.
  }, [chatHistory, assistantOnlyMode]);

  if (assistantOnlyMode) {
    return (
      <div
        className="container mx-auto p-6 max-w-7xl"
        dir="rtl"
        style={{ backgroundColor: 'var(--bg-primary)', minHeight: '100vh' }}
        data-testid="ai-financial-assistant-only-page"
      >
        <div className="mb-6" data-testid="assistant-only-header">
          <h1 className="text-3xl font-bold flex items-center gap-3" style={{ color: 'var(--text-primary)' }}>
            <Brain size={34} className="text-blue-500" />
            صفحة المساعد فقط
          </h1>
          <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }} data-testid="assistant-only-description">
            تم تعطيل القوائم والبيانات المالية الجذرية في هذه الصفحة لتفادي أي ربط مالي أو أخطاء.
            للاعتماد الرسمي على القوائم المالية استخدم صفحة القسم المالي: <strong>/accounting/comprehensive</strong>.
          </p>
        </div>

        <div
          className="rounded-2xl overflow-hidden"
          style={{
            border: '1px solid var(--border-color)',
            backgroundColor: 'var(--bg-card)',
            minHeight: '760px',
          }}
          data-testid="assistant-only-workshop-panel"
        >
          <WorkshopAIBot />
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96" dir="rtl">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
        <p className="text-lg text-gray-600">جاري تحميل التحليل المالي...</p>
        <p className="text-sm text-gray-500">قد يستغرق ذلك لحظات</p>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-red-200 max-w-2xl mx-auto mt-8" dir="rtl">
        <CardHeader>
          <CardTitle className="text-red-700">حدث خطأ</CardTitle>
          <CardDescription>تعذر تحميل بيانات التحليل المالي</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-red-600 mb-4">{error}</p>
          <Button onClick={fetchCoreFinancials} className="bg-blue-600 hover:bg-blue-700">
            <RefreshCw className="h-4 w-4 ml-2" />
            إعادة المحاولة
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div
      className="container mx-auto p-6 max-w-7xl"
      dir="rtl"
      style={{ backgroundColor: 'var(--bg-primary)', minHeight: '100vh' }}
    >
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3" style={{ color: 'var(--text-primary)' }}>
            <Brain size={34} className="text-blue-500" />
            المساعد الذكي الموحد
          </h1>
          <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
            واجهة موحّدة تجمع ذكاء الورشة والتحليل المالي في مكان واحد.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            data-testid="unified-assistant-time-range-select"
            className="px-4 py-2 rounded-lg"
            style={{
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
            }}
          >
            <option value="week">آخر أسبوع</option>
            <option value="month">آخر شهر</option>
            <option value="quarter">آخر ربع سنة</option>
            <option value="year">آخر سنة</option>
          </select>

          <Button onClick={fetchCoreFinancials} className="bg-blue-600 hover:bg-blue-700" data-testid="unified-assistant-refresh-button">
            <RefreshCw className="h-4 w-4 ml-2" />
            تحديث
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-6" data-testid="unified-assistant-tab-switcher">
        <button
          type="button"
          onClick={() => setAssistantTab('finance')}
          data-testid="unified-assistant-tab-finance"
          className="px-4 py-2 rounded-lg text-sm transition-all"
          style={{
            backgroundColor: assistantTab === 'finance' ? 'var(--accent-primary)' : 'var(--bg-card)',
            color: assistantTab === 'finance' ? '#fff' : 'var(--text-secondary)',
            border: '1px solid var(--border-color)',
          }}
        >
          التحليل المالي
        </button>
        <button
          type="button"
          onClick={() => setAssistantTab('workshop')}
          data-testid="unified-assistant-tab-workshop"
          className="px-4 py-2 rounded-lg text-sm transition-all"
          style={{
            backgroundColor: assistantTab === 'workshop' ? 'var(--accent-primary)' : 'var(--bg-card)',
            color: assistantTab === 'workshop' ? '#fff' : 'var(--text-secondary)',
            border: '1px solid var(--border-color)',
          }}
        >
          ذكاء الورشة
        </button>
      </div>

      {assistantTab === 'workshop' ? (
        <div
          className="rounded-2xl overflow-hidden"
          style={{
            border: '1px solid var(--border-color)',
            backgroundColor: 'var(--bg-card)',
            minHeight: '720px',
          }}
          data-testid="unified-assistant-workshop-panel"
        >
          <WorkshopAIBot />
        </div>
      ) : (
        <>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {summaryCards.map((card, idx) => (
          <FinancialCard
            key={idx}
            title={card.title}
            subtitle={card.subtitle}
            icon={card.icon}
            variant={card.variant}
            expandable
            details={card.details}
          >
            <div
              className="text-2xl font-bold"
              style={{ color: 'var(--text-primary)' }}
              data-testid={`financial-summary-value-${idx}`}
            >
              {card.value}
            </div>
            <div className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
              اضغط لعرض التفاصيل
            </div>
          </FinancialCard>
        ))}
      </div>

      {/* Alerts */}
      {riskQuickCards.length ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {riskQuickCards.map((c, idx) => (
            <FinancialCard
              key={idx}
              title={c.title}
              subtitle={c.subtitle}
              icon={c.icon}
              variant={c.variant}
              expandable
              details={c.subtitle ? [{ label: 'تفاصيل', value: c.subtitle }] : []}
            >
              <div
                className="text-2xl font-bold"
                style={{ color: 'var(--text-primary)' }}
                data-testid={`financial-risk-value-${idx}`}
              >
                {c.value}
              </div>
              <div className="text-xs mt-2" style={{ color: 'var(--text-secondary)' }}>
                اضغط لعرض التفاصيل
              </div>
            </FinancialCard>
          ))}
        </div>
      ) : null}

      {/* Vehicle status (optional) */}
      {vehicleId ? (
        <div className="mb-8">
          <FinancialCard
            title="حالة المركبة"
            subtitle={vehicleLoading ? 'جاري التحميل...' : vehicle ? `${vehicle.plateNumber || '-'} | ${vehicle.brand || ''} ${vehicle.model || ''}` : 'تعذر جلب بيانات المركبة'}
            icon={Car}
            variant={vehicle ? 'default' : 'warning'}
            expandable
            details={vehicle ? [
              { label: 'معرّف المركبة', value: vehicleId },
              { label: 'الحالة', value: getStatusLabel(vehicle.status) },
              { label: 'الدخول', value: vehicle.entryDate ? new Date(vehicle.entryDate).toLocaleDateString('ar-SA') : '—' },
              { label: 'الخروج', value: vehicle.exitDate ? new Date(vehicle.exitDate).toLocaleDateString('ar-SA') : '—' },
            ] : []}
          />
        </div>
      ) : null}

      {/* Centralize Financial Statements in dedicated Financial section only */}
      <div className="mb-8">
        <FinancialCard
          title="القوائم المالية"
          subtitle="تم اعتمادها حصرياً داخل صفحة القوائم المالية في القسم المالي"
          icon={FileText}
          variant="default"
          expandable={false}
        >
          <div
            className="rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-200"
            data-testid="assistant-financial-statements-centralized-note"
          >
            تم إخفاء القوائم المالية من تبويب <strong>التحليل المالي</strong> في صفحة المساعد.
            <br />
            للوصول إلى القوائم الرئيسية (الميزانية، قائمة الدخل، التدفقات، وغيرها) استخدم صفحة
            <strong> القوائم المالية</strong> ضمن القسم المالي.
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button
              onClick={() => (window.location.href = '/accounting/comprehensive')}
              className="bg-blue-600 hover:bg-blue-700"
              data-testid="assistant-go-financial-statements-button"
            >
              فتح صفحة القوائم المالية
            </Button>
          </div>
        </FinancialCard>
      </div>

      {/* AbuFahad Chat */}
      <div className="mb-8">
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-lg" dir="rtl">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                <Brain className="h-4 w-4 text-blue-400" />
                محادثة أبوفهد
              </h3>
              <Button variant="outline" className="h-8" onClick={clearChat} data-testid="abu-new-session-button">
                جلسة جديدة
              </Button>
            </div>

            <p className="text-xs text-slate-400 mb-3">
              يمكنك ترك الحقل بدون تحديد حساب لتحليل عام، أو اختيار حساب لتدقيقه.
            </p>

            <div className="mb-3 space-y-2">
              <label className="block text-xs font-medium text-slate-300">الجلسة النشطة</label>
              <div className="flex items-center gap-2">
                <select
                  value={activeSessionId}
                  onChange={(e) => selectSession(e.target.value)}
                  className="flex-1 px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  data-testid="abu-session-select"
                >
                  {chatSessions.map((session) => (
                    <option key={session.id} value={session.id}>
                      {session.title || 'جلسة جديدة'}
                    </option>
                  ))}
                </select>
                {chatSessions.length > 1 ? (
                  <button
                    onClick={() => deleteSession(activeSessionId)}
                    className="h-9 w-9 rounded-lg border border-slate-700 bg-slate-900 text-slate-200 hover:text-red-300"
                    data-testid="abu-delete-session-button"
                  >
                    <Trash2 className="h-4 w-4 mx-auto" />
                  </button>
                ) : null}
              </div>
            </div>

            <div className="mb-3">
              <label className="block text-xs font-medium text-slate-300 mb-1">الحساب (اختياري)</label>
              <select
                value={selectedAccountCode}
                onChange={(e) => setSelectedAccountCode(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                data-testid="abu-account-select"
              >
                <option value="">بدون تحديد حساب</option>
                {(Array.isArray(accounts) ? accounts : []).map((acc) => (
                  <option key={acc.id || acc.code} value={acc.code}>
                    {acc.code} - {acc.name_ar || acc.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="h-52 overflow-y-auto rounded-lg bg-slate-900/60 border border-slate-800 mb-3 p-2 space-y-2 text-xs">
              {chatHistory.map((msg, idx) => (
                <div
                  key={idx}
                  className={`rounded-lg px-2 py-1.5 whitespace-pre-wrap ${
                    msg.role === 'user'
                      ? 'bg-blue-500/10 text-blue-100 ml-6 text-right'
                      : 'bg-slate-800/80 text-slate-100 mr-6 text-right'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <div className="prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    msg.content
                  )}
                </div>
              ))}
            </div>

            <form onSubmit={handleChatSubmit} className="flex items-center gap-2">
              <input
                type="text"
                value={chatQuery}
                onChange={(e) => setChatQuery(e.target.value)}
                placeholder="اكتب سؤالك المالي هنا..."
                className="flex-1 px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                data-testid="abu-chat-input"
              />
              <button
                type="submit"
                disabled={chatLoading}
                className="h-9 w-9 rounded-full bg-blue-600 hover:bg-blue-700 flex items-center justify-center text-white disabled:opacity-50"
                data-testid="abu-chat-send-button"
              >
                {chatLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </form>
          </div>
      </div>

      {/* System Audit */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <FinancialCard
            title="تدقيق النظام المحاسبي"
            subtitle="فحص الاتساق والتوازن واكتشاف الأخطاء المحتملة"
            icon={Shield}
            variant="default"
            expandable
            details={auditSummaryDetails}
          >
            <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-4">
              <Button onClick={runAudit} disabled={auditLoading} className="bg-blue-600 hover:bg-blue-700">
                {auditLoading ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <RefreshCw className="h-4 w-4 ml-2" />}
                تشغيل التدقيق
              </Button>

              {auditReport ? (
                <Button variant="outline" onClick={analyzeAuditWithAbuFahad} disabled={auditBotLoading}>
                  {auditBotLoading ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Brain className="h-4 w-4 ml-2" />}
                  اطلب من أبوفهد تحليل التقرير
                </Button>
              ) : null}
            </div>

            {!auditReport ? (
              <div className="text-sm text-slate-400">شغّل التدقيق لعرض النتائج هنا.</div>
            ) : (
              <div className="space-y-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3 text-sm text-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300">درجة صحة النظام</span>
                    <span className="font-bold tabular-nums">{auditReport.health_score}/100</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {[
                    { label: 'الأخطاء', value: auditReport.summary?.total_issues || 0, icon: AlertTriangle },
                    { label: 'التصحيحات', value: auditReport.summary?.corrections_needed || 0, icon: CheckCircle },
                    { label: 'النواقص', value: auditReport.summary?.missing_items || 0, icon: FileText },
                    { label: 'السجل', value: auditReport.summary?.audit_log_entries || 0, icon: ListChecks },
                  ].map((item, idx) => (
                    <div key={idx} className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <item.icon size={14} />
                        {item.label}
                      </div>
                      <div className="text-lg font-bold text-slate-100 mt-1" data-testid={`audit-summary-${idx}`}>
                        {item.value}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <details className="rounded-xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-200" data-testid="audit-corrections-block">
                    <summary className="cursor-pointer text-slate-300">التصحيحات المطلوبة</summary>
                    <div className="mt-2 space-y-2 max-h-[200px] overflow-auto">
                      {(auditReport.corrections_needed || []).length ? (
                        (auditReport.corrections_needed || []).map((item, idx) => (
                          <div key={idx} className="rounded-lg border border-slate-800 bg-slate-950/60 p-2">
                            <div className="font-semibold text-slate-100">{item.issue || 'تصحيح'}</div>
                            <div className="text-slate-300">{item.details || item.correction || item.suggestion || '—'}</div>
                          </div>
                        ))
                      ) : (
                        <div className="text-slate-400">لا توجد تصحيحات مسجلة.</div>
                      )}
                    </div>
                  </details>
                  <details className="rounded-xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-200" data-testid="audit-log-block">
                    <summary className="cursor-pointer text-slate-300">سجل التدقيق</summary>
                    <div className="mt-2 space-y-2 max-h-[200px] overflow-auto">
                      {(auditReport.audit_log || []).length ? (
                        (auditReport.audit_log || []).map((item, idx) => (
                          <div key={idx} className="text-slate-300">{item}</div>
                        ))
                      ) : (
                        <div className="text-slate-400">لا يوجد سجل بعد.</div>
                      )}
                    </div>
                  </details>
                </div>

                <details className="rounded-xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-200">
                  <summary className="cursor-pointer text-slate-300">عرض ملخص تقرير التدقيق</summary>
                  <div className="mt-3 whitespace-pre-wrap max-h-[220px] overflow-auto" data-testid="audit-report-details">
                    {JSON.stringify(auditReport.summary || auditReport, null, 2)}
                  </div>
                </details>
              </div>
            )}
          </FinancialCard>
        </div>

        <div>
          <FinancialCard
            title="تحليل أبوفهد للتدقيق"
            subtitle="شرح المخاطر وخطوات التصحيح"
            icon={Brain}
            variant="default"
            expandable
            details={auditAnalysisDetails}
          >
            <details className="rounded-xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-200">
              <summary className="cursor-pointer text-slate-300">
                {auditBotLoading
                  ? 'جاري التحليل...'
                  : auditBotResponse
                  ? 'عرض التحليل الكامل'
                  : 'بعد تشغيل التدقيق اضغط (اطلب من أبوفهد تحليل التقرير).'}
              </summary>
              {!auditBotLoading && auditBotResponse ? (
                <div className="mt-3 whitespace-pre-wrap max-h-[320px] overflow-auto" data-testid="audit-analysis-full">
                  {auditBotResponse}
                </div>
              ) : null}
            </details>
            {!auditBotLoading && auditBotResponse ? (
              <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-200 whitespace-pre-wrap" data-testid="audit-analysis-preview">
                {auditPreview}
              </div>
            ) : null}
          </FinancialCard>
        </div>
      </div>
        </>
      )}
    </div>
  );
}