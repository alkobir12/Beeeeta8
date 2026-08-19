import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, X, Send, Sparkles, AlertTriangle, Settings, Trash2, Mic, Volume2, VolumeX, Copy, Check, ShieldAlert, FileSearch, History } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useLocation } from 'react-router-dom';
import axios from 'axios';
import { getStoredToken } from '../../utils/authToken';
import { useAssistant } from './AssistantProvider';
import { AssistantCard } from './AssistantCard';
import { AssistantDashboard } from './AssistantDashboard';
import { RecentOperationsWidget } from './RecentOperationsWidget';
import { ControlCenterTab } from './ControlCenterTab';

// 📱 Detect mobile breakpoint reactively
function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(() => {
    try { return window.innerWidth < breakpoint; } catch (e) { return false; }
  });
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < breakpoint);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [breakpoint]);
  return isMobile;
}

/**
 * 🤖 UnifiedAssistantDrawer — واجهة كاترينا بأسلوب Kodee (Hostinger):
 * بطاقة عائمة نظيفة بزوايا مدوّرة كبيرة، Bottom Sheet شبه كامل على الجوال،
 * تفاعلية (حركات دخول ناعمة، مؤشر كتابة، رقائق اقتراحات).
 */

const AGENT_LABELS = {
  FirewallAgent: { name: 'وكيل الحماية', icon: '🛡️' },
  FinanceAgent: { name: 'وكيل المالية', icon: '💰' },
  WorkshopAgent: { name: 'وكيل الورشة', icon: '🔧' },
};

// 💡 Page-aware suggestions: different starter prompts depending on the route the user is currently on.
const SUGGESTIONS_DEFAULT = [
  'كم درجة الصحة المالية؟',
  'أعطني أهم التنبيهات',
  'كم ذمم العملاء؟',
  'كم زيارة نشطة الآن؟',
  'كيف التدفق النقدي؟',
  '/power سجل عميل احمد، أضف مركبة 9935',
];
const SUGGESTIONS_BY_PATH = {
  '/customers': ['كم ذمم العملاء؟', 'من هم أعلى المدينين؟', 'آخر العمليات', '/power سجل عميل جديد ، افتح زيارة'],
  '/suppliers': ['كم ذمم الموردين؟', 'من أعلى الموردين دائنية؟', 'أهم التنبيهات', '/power أضف مورد جديد'],
  '/parts': ['ما هي القطع الناقصة؟', 'قطع وصلت للحد الأدنى', 'أهم تنبيهات المخزون', '/power كم سعر زيت ، كم عندي فلتر'],
  '/operations': ['آخر العمليات', 'عمليات بها قيد مفقود', 'كم درجة الصحة المالية؟', '/power أضف عملية ، تحصيل 500'],
  '/accounting/firewall': ['أعطني أهم التنبيهات', 'كم درجة الصحة المالية؟', 'عمليات بها قيد مفقود', 'كيف التدفق النقدي؟'],
};

function getSuggestionsForPath(pathname) {
  for (const [prefix, list] of Object.entries(SUGGESTIONS_BY_PATH)) {
    if (pathname?.startsWith(prefix)) return list;
  }
  return SUGGESTIONS_DEFAULT;
}

// 📐 Lightweight markdown renderer config — keeps things readable inside chat bubbles.
const MD_COMPONENTS = {
  p: ({ node, ...props }) => <p className="mb-1.5 last:mb-0 leading-relaxed" {...props} />,
  strong: ({ node, ...props }) => <strong className="font-extrabold" {...props} />,
  em: ({ node, ...props }) => <em className="italic" {...props} />,
  ul: ({ node, ...props }) => <ul className="list-disc pr-5 mb-1.5 space-y-0.5" {...props} />,
  ol: ({ node, ...props }) => <ol className="list-decimal pr-5 mb-1.5 space-y-0.5" {...props} />,
  li: ({ node, ...props }) => <li className="leading-relaxed" {...props} />,
  code: ({ node, inline, className, children, ...props }) => (
    inline
      ? <code className="px-1 py-0.5 rounded bg-zinc-200/70 dark:bg-zinc-700 text-[12px] font-mono" {...props}>{children}</code>
      : <pre className="rounded-xl bg-zinc-900 text-zinc-100 text-[11px] p-2 my-1 overflow-auto" {...props}><code>{children}</code></pre>
  ),
  table: ({ node, ...props }) => (
    <div className="overflow-auto my-1 rounded-lg border border-zinc-200 dark:border-zinc-700">
      <table className="text-[11px] border-collapse w-full" {...props} />
    </div>
  ),
  th: ({ node, ...props }) => <th className="border-b border-zinc-200 dark:border-zinc-700 px-2 py-1 bg-zinc-50 dark:bg-zinc-800 font-bold text-right" {...props} />,
  td: ({ node, ...props }) => <td className="border-b border-zinc-100 dark:border-zinc-800 px-2 py-1" {...props} />,
  a: ({ node, ...props }) => <a className="text-violet-600 dark:text-violet-300 underline" target="_blank" rel="noopener noreferrer" {...props} />,
};

export const UnifiedAssistantDrawer = () => {
  const {
    open, setOpen,
    messages, busy, activeAgent, streamingPhase,
    alerts, stats,
    model, setModel, availableModels,
    voice, voiceEnabled, setVoiceEnabled,
    sendMessage, resetSession, appendMessage,
  } = useAssistant();

  const [input, setInput] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [tab, setTab] = useState('chat');
  const [controlCount, setControlCount] = useState(0);
  const [dailySummaryOn, setDailySummaryOn] = useState(() => localStorage.getItem('assistant_daily_summary') !== 'off');
  const [copiedIdx, setCopiedIdx] = useState(null);
  const messagesEndRef = useRef(null);
  const location = useLocation();
  const pageSuggestions = useMemo(() => getSuggestionsForPath(location?.pathname || '/'), [location?.pathname]);

  // 🎙️ Live interim transcript feedback while the mic is listening.
  const displayInput = (voice?.listening && voice?.interim) ? voice.interim : input;

  // Auto-scroll on new messages
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [messages.length, busy]);

  // 🛡️ عدّاد الاعتمادات المعلقة — لشارة تبويب مركز التحكم
  useEffect(() => {
    if (!open) return;
    const fetchCount = () => {
      const apiBase = process.env.NODE_ENV === 'production' ? '' : (process.env.REACT_APP_BACKEND_URL || '');
      const token = getStoredToken();
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      axios.get(`${apiBase}/api/runtime/approvals`, { params: { status: 'pending', limit: 100 }, headers, withCredentials: true })
        .then(({ data }) => setControlCount((data?.data || []).filter((a) => a?.source_classification !== 'TEST_ARTIFACT').length))
        .catch(() => {});
    };
    fetchCount();
    window.addEventListener('runtime:changed', fetchCount);
    window.addEventListener('finance:updated', fetchCount);
    return () => {
      window.removeEventListener('runtime:changed', fetchCount);
      window.removeEventListener('finance:updated', fetchCount);
    };
  }, [open]);

  // Keyboard shortcut: Ctrl+Shift+B to open/close
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        setOpen(!open);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, setOpen]);

  // 🆕 Multi-intent detector: separators (، . ؛ ثم) or ≥2 action verbs →
  // route to /power so the chat pipeline batches the drafts.
  const _isMultiIntent = (text) => {
    if (/[،,؛]/.test(text)) return true;
    if (/\sثم\s/.test(text)) return true;
    if ((text.match(/[.]/g) || []).length >= 1 && text.length > 30) return true;
    const verbs = (text.match(/(?:سجل|أضف|اضف|افتح|أنشئ|انشئ|اصدر|بيع|تحصيل|ادفع|اصرف)/g) || []).length;
    return verbs >= 2;
  };

  const smartSend = async (text) => {
    if (!text || busy) return;
    if (_isMultiIntent(text)) {
      await sendMessage(`/power ${text}`);
    } else {
      await sendMessage(text);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || busy) return;
    const text = input.trim();
    setInput('');
    await smartSend(text);
  };

  // 🎙️ Mic — start/stop live Arabic dictation; auto-sends on final transcript.
  const handleMic = () => {
    if (!voice?.supported?.stt) return;
    if (voice.listening) { voice.stopListening(); return; }
    voice.startListening((finalText) => {
      if (finalText && !busy) {
        setInput('');
        smartSend(finalText);
      }
    });
  };

  const handleSuggestion = (s) => {
    if (busy) return;
    setInput('');
    sendMessage(s);
  };

  const criticalCount = (alerts || []).filter((a) => a.severity === 'critical').length;
  const agentMeta = activeAgent ? AGENT_LABELS[activeAgent] : null;
  const isMobile = useIsMobile();
  const tabs = useMemo(() => ([
    { id: 'approvals', label: 'يحتاج قرارك', icon: ShieldAlert, badge: controlCount, testid: 'assistant-tab-approvals' },
    { id: 'findings', label: 'اكتشفته كاترينا', icon: FileSearch, testid: 'assistant-tab-findings' },
    { id: 'executions', label: 'تم بواسطة كاترينا', icon: History, testid: 'assistant-tab-executions' },
    { id: 'chat', label: 'المحادثة', icon: Bot, testid: 'assistant-tab-chat' },
  ]), [controlCount]);

  // Helper: dispatch a "tool" action chip → re-trigger the assistant with the tool's intent.
  const handleCardAction = async (action, card) => {
    if (action?.intent === 'navigate') {
      if (isMobile) setOpen(false);
      return;
    }
    if (action?.intent === 'tool' && action?.tool) {
      const queryHint = action.args?.query;
      const phrase = queryHint ? `ابحث عن ${queryHint}` : `شغّل ${action.label || action.tool}`;
      setInput('');
      sendMessage(phrase);
      return;
    }
    // Phase 3C — runtime intent: call the runtime REST endpoint directly.
    if (action?.intent === 'runtime' && action?.endpoint) {
      if (action.confirm && !window.confirm(action.confirm)) return;
      try {
        let me = 'anonymous';
        try {
          const u = JSON.parse(localStorage.getItem('user') || 'null');
          me = u?.name || u?.username || 'anonymous';
        } catch (e) { /* noop */ }

        const baseUrl = process.env.NODE_ENV === 'production' ? '' : (process.env.REACT_APP_BACKEND_URL || '');
        const url = `${baseUrl}${action.endpoint}`;
        const method = (action.method || 'POST').toUpperCase();
        const bodyData = { ...(action.body || {}) };
        if (action.id === 'approve' && action.requiresDeveloperCode) {
          const code = window.prompt('أدخل رمز المطور لاعتماد وتنفيذ طلبك');
          if (!code) return;
          bodyData.developer_code = code;
        }

        let resp;
        if (method === 'GET') {
          resp = await axios.get(url);
        } else if (method === 'PUT') {
          resp = await axios.put(url, bodyData);
        } else if (method === 'DELETE') {
          resp = await axios.delete(url, { data: bodyData });
        } else {
          resp = await axios.post(url, bodyData);
        }
        const data = resp.data || {};
        const ok = data?.success !== false;
        const resultData = data?.data || data;
        let summary;
        if (ok) {
          const fixedCount = resultData?.fixed;
          const committedRes = resultData?.committed?.result;
          if (fixedCount !== undefined) {
            summary = `✅ تم تصحيح **${fixedCount}** قيد محاسبي مفقود من أصل ${resultData?.missing_before || '?'}`;
          } else if (committedRes && committedRes.deleted !== undefined) {
            summary = committedRes.deleted
              ? `✅ **تم الاعتماد والحذف بنجاح.**`
              : `⚠️ تم الاعتماد، لكن لم أعثر على العنصر المطلوب حذفه (ربما حُذف مسبقاً).`;
          } else if (action.id === 'reject') {
            summary = `🚫 تم رفض العملية.`;
          } else {
            summary = `✅ تم: ${action.label}`;
          }
          try {
            window.dispatchEvent(new CustomEvent('finance:updated', { detail: { source: 'card_action', action: action.id } }));
            window.dispatchEvent(new CustomEvent('runtime:changed', { detail: { source: 'card_action', action: action.id } }));
            window.dispatchEvent(new CustomEvent('operations:updated', { detail: { source: 'card_action', action: action.id } }));
            window.dispatchEvent(new CustomEvent('vehicles:updated', { detail: { source: 'card_action', action: action.id } }));
            window.dispatchEvent(new CustomEvent('customers:updated', { detail: { source: 'card_action', action: action.id } }));
          } catch (e) { /* noop */ }
        } else {
          summary = `⚠️ ${resultData?.detail || resultData?.error || 'فشل تنفيذ العملية'}`;
        }
        appendMessage({ role: 'assistant', content: summary, meta: { status: ok ? 'success' : 'error', action: action.id } });
      } catch (e) {
        const detail = e?.response?.data?.detail;
        const errKey = typeof detail === 'object' ? (detail.error || detail.msg) : detail;
        if (errKey === 'approval_not_found' || e?.response?.status === 404) {
          appendMessage({
            role: 'assistant',
            content: 'ℹ️ هذا الطلب لم يعد موجوداً (اعتُمد أو رُفض سابقاً) — افتح 🛡️ مركز التحكم لرؤية القائمة المحدّثة.',
            meta: { status: 'info' },
          });
          try { window.dispatchEvent(new CustomEvent('runtime:changed', { detail: { source: 'stale_approval' } })); } catch (err) { /* noop */ }
          return;
        }
        let msg;
        if (detail && typeof detail === 'object') {
          msg = detail.msg || detail.error || detail.detail || JSON.stringify(detail);
        } else {
          msg = detail || e?.message || 'خطأ غير معروف';
        }
        appendMessage({ role: 'assistant', content: `⚠️ خطأ في ${action.label}: ${msg}`, meta: { error: true } });
      }
    }
  };

  // ── FAB (Floating Action Button) — Kodee style ──────────────────────────
  if (!open) {
    return (
      <button
        data-testid="unified-assistant-fab"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-[80] group"
        title="افتح كاترينا (Ctrl+Shift+B)"
        dir="rtl"
      >
        <div className="relative">
          <div className="h-14 w-14 rounded-full bg-violet-600 hover:bg-violet-700 shadow-lg shadow-violet-600/30 flex items-center justify-center transition-all duration-200 hover:scale-105 active:scale-95">
            <Bot className="text-white" size={26} />
          </div>
          {criticalCount > 0 && (
            <span data-testid="assistant-fab-badge" className="absolute -top-1 -right-1 bg-rose-500 text-white text-[10px] font-bold rounded-full w-6 h-6 flex items-center justify-center border-2 border-white dark:border-zinc-950 animate-pulse">
              {criticalCount}
            </span>
          )}
          <div className="absolute top-0 right-0 w-3 h-3 bg-emerald-400 rounded-full border-2 border-white dark:border-zinc-950" />
        </div>
      </button>
    );
  }

  return (
    <div
      data-testid="unified-assistant-drawer"
      className={
        isMobile
          ? 'fixed bottom-0 inset-x-0 mx-auto z-[80] w-full max-w-[480px] bg-white dark:bg-zinc-950 rounded-t-[28px] shadow-[0_-10px_40px_-10px_rgba(0,0,0,0.18)] border-t border-zinc-200/60 dark:border-zinc-800 flex flex-col overflow-hidden animate-kodee-sheet'
          : 'fixed bottom-6 right-6 z-[80] w-[420px] h-[680px] max-h-[calc(100vh-64px)] bg-white dark:bg-zinc-950 rounded-[24px] shadow-[0_20px_60px_-15px_rgba(124,58,237,0.25)] dark:shadow-[0_20px_60px_-15px_rgba(0,0,0,0.6)] border border-zinc-200/60 dark:border-zinc-800 flex flex-col overflow-hidden animate-kodee-pop'
      }
      style={isMobile ? { height: '90dvh', maxHeight: '90dvh', paddingBottom: 'env(safe-area-inset-bottom)' } : undefined}
      dir="rtl"
    >
      {/* Mobile drag handle — tap to close */}
      {isMobile && (
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="flex flex-col items-center justify-center pt-3 pb-1 w-full active:bg-zinc-100 dark:active:bg-zinc-900"
          data-testid="assistant-mobile-handle"
          title="اضغط للإغلاق"
        >
          <div className="w-12 h-1.5 bg-zinc-300 dark:bg-zinc-700 rounded-full" />
        </button>
      )}

      {/* Header — clean Kodee style */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 dark:border-zinc-800/80 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-xl">
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative shrink-0">
            <div className="h-10 w-10 rounded-xl bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center text-violet-600 dark:text-violet-300 text-lg">
              {agentMeta?.icon || <Bot size={20} />}
            </div>
            <span className={`absolute -bottom-1 -left-1 h-3 w-3 rounded-full border-2 border-white dark:border-zinc-950 ${voice?.listening ? 'bg-rose-500 animate-pulse' : 'bg-emerald-500'}`} />
          </div>
          <div className="min-w-0">
            <h3 className="text-base font-bold tracking-tight text-zinc-900 dark:text-zinc-100 truncate leading-tight">
              {agentMeta?.name || 'كاترينا'}
            </h3>
            <p className="text-[11px] font-medium text-zinc-500 dark:text-zinc-400 truncate">
              {voice?.listening ? <span className="text-rose-500 font-bold">🎙️ أستمع…</span>
                : voice?.speaking ? <span className="text-emerald-500 font-bold">🔊 أتحدّث…</span>
                : (stats?.ai_enabled ? <><Sparkles size={9} className="inline ml-0.5 text-violet-500" /> AI نشط</> : 'محرك قواعد')}
              <span className="mx-1 opacity-50">·</span>
              <span data-testid="assistant-model-badge" className="font-bold text-violet-600 dark:text-violet-300">
                {model === 'ollama' ? '🦙 Ollama' : '⚡ Sonnet'}
              </span>
              {alerts.length > 0 && (
                <span className="mr-1.5 text-amber-600 dark:text-amber-400"><AlertTriangle size={9} className="inline ml-0.5" />{alerts.length}</span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {voice?.supported?.tts && (
            <button
              data-testid="assistant-voice-toggle"
              onClick={() => setVoiceEnabled(!voiceEnabled)}
              className={`${isMobile ? 'h-12 w-12' : 'h-8 w-8'} rounded-lg flex items-center justify-center transition-colors ${voiceEnabled ? 'bg-violet-100 dark:bg-violet-900/40 text-violet-600 dark:text-violet-300' : 'text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-600'}`}
              title={voiceEnabled ? 'إيقاف نطق الردود' : 'تفعيل نطق الردود'}
            >
              {voiceEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
            </button>
          )}
          <button
            data-testid="assistant-settings-btn"
            onClick={() => setShowSettings(!showSettings)}
            className={`${isMobile ? 'h-12 w-12' : 'h-8 w-8'} rounded-lg flex items-center justify-center transition-colors ${showSettings ? 'bg-violet-100 dark:bg-violet-900/40 text-violet-600 dark:text-violet-300' : 'text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-600'}`}
            title="إعدادات"
          >
            <Settings size={15} />
          </button>
          <button
            data-testid="assistant-close-btn"
            onClick={() => setOpen(false)}
            className={`rounded-lg flex items-center justify-center text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors ${isMobile ? 'h-12 w-12' : 'h-8 w-8'}`}
            title="إغلاق"
          >
            <X size={isMobile ? 20 : 16} />
          </button>
        </div>
      </div>

      {/* 🗂️ Katrina Control Center Tabs — mobile-first */}
      <div className="px-3 pt-2" data-testid="assistant-tabs">
        <div className="flex gap-1 overflow-x-auto p-1 bg-zinc-100/90 dark:bg-zinc-900/90 rounded-2xl no-scrollbar">
          {tabs.map((item) => {
            const Icon = item.icon;
            const selected = tab === item.id;
            return (
              <button
                key={item.id}
                data-testid={item.testid}
                onClick={() => setTab(item.id)}
                className={`min-h-[48px] min-w-[78px] flex-1 flex flex-col items-center justify-center gap-1 px-2 rounded-xl text-[10px] font-black transition-all duration-200 ${
                  selected
                    ? 'bg-white dark:bg-zinc-800 text-zinc-950 dark:text-white shadow-sm'
                    : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
                }`}
              >
                <span className="relative inline-flex">
                  <Icon size={15} />
                  {item.badge > 0 && (
                    <span data-testid="assistant-control-badge" className="absolute -top-2 -left-2 h-5 min-w-[20px] rounded-full bg-rose-500 text-white text-[10px] flex items-center justify-center px-1 font-bold">
                      {item.badge}
                    </span>
                  )}
                </span>
                <span className="leading-tight whitespace-nowrap">{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="mx-4 mt-3 p-3 bg-zinc-50 dark:bg-zinc-900 border border-zinc-200/70 dark:border-zinc-800 rounded-2xl space-y-2 animate-kodee-pop" data-testid="assistant-settings-panel">
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-zinc-500 dark:text-zinc-400 font-medium">
              {messages.length} رسالة في الجلسة
            </span>
            <div className="flex items-center gap-2">
              <button
                data-testid="assistant-daily-summary-toggle"
                onClick={() => {
                  const cur = localStorage.getItem('assistant_daily_summary') !== 'off';
                  localStorage.setItem('assistant_daily_summary', cur ? 'off' : 'on');
                  setDailySummaryOn(!cur);
                }}
                className={`text-[11px] px-2.5 py-1 rounded-lg font-bold inline-flex items-center gap-1 transition-colors ${
                  dailySummaryOn ? 'bg-emerald-500 hover:bg-emerald-600 text-white' : 'bg-zinc-300 dark:bg-zinc-700 hover:bg-zinc-400 text-white'
                }`}
              >
                📅 الملخص اليومي: {dailySummaryOn ? 'مفعّل' : 'موقوف'}
              </button>
              <button
                data-testid="assistant-reset-btn"
                onClick={() => { resetSession(); setShowSettings(false); }}
                className="text-[11px] px-2.5 py-1 rounded-lg bg-rose-500 hover:bg-rose-600 text-white font-bold inline-flex items-center gap-1 transition-colors"
              >
                <Trash2 size={10} /> مسح المحادثة
              </button>
            </div>
          </div>
          {/* 🆕 Model selector */}
          {availableModels && availableModels.length > 0 && (
            <div data-testid="assistant-model-selector" className="space-y-1.5">
              <div className="text-[10px] font-bold text-zinc-600 dark:text-zinc-300">النموذج الذكي:</div>
              <div className="grid grid-cols-2 gap-2">
                {availableModels.map((m) => {
                  const selected = model === m.id;
                  const disabled = !m.available;
                  return (
                    <button
                      key={m.id}
                      data-testid={`assistant-model-${m.id}`}
                      onClick={() => !disabled && setModel(m.id)}
                      disabled={disabled}
                      title={disabled ? `${m.label} غير متاح حالياً` : m.description}
                      className={`text-right text-[11px] p-2.5 rounded-xl border transition-all ${
                        selected
                          ? 'border-2 border-violet-500 bg-violet-50 dark:bg-violet-900/20 text-violet-700 dark:text-violet-200'
                          : disabled
                            ? 'border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 text-zinc-400 cursor-not-allowed opacity-60'
                            : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-200 hover:border-violet-300 dark:hover:border-violet-700'
                      }`}
                    >
                      <div className="font-bold flex items-center gap-1 justify-end">
                        {selected && <span className="text-violet-600">✓</span>}
                        {m.label}
                      </div>
                      <div className="text-[9px] opacity-70 mt-0.5">{m.model}</div>
                      {disabled && <div className="text-[9px] text-rose-500 mt-0.5">غير متاح</div>}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {tab !== 'chat' ? (
        <div className="flex-1 min-h-0 overflow-hidden scroll-smooth" data-testid="assistant-control-panel">
          <ControlCenterTab mode={tab} onCountChange={setControlCount} />
        </div>
      ) : (
      <>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 scroll-smooth" data-testid="assistant-messages">
        {/* 🆕 Phase 3C.7 — recent executed operations widget (always visible at top) */}
        <RecentOperationsWidget variant="drawer" limit={6} className="mb-2" />
        {messages.length === 0 ? (
          <div className="text-center py-3">
            <div className="mx-auto mb-3 h-14 w-14 rounded-2xl bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
              <Bot className="text-violet-600 dark:text-violet-300" size={28} />
            </div>
            <p className="text-sm font-bold text-zinc-800 dark:text-zinc-100 mb-1">هلا والله! أنا كاترينا 👋 كيف أقدر أساعدك؟</p>
            <AssistantDashboard onAskMore={(p) => sendMessage(`تفاصيل ${p.label}`)} />
            <p className="text-[10px] text-zinc-400 dark:text-zinc-500 mt-3 mb-2 font-medium">أو جرّب:</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {pageSuggestions.map((s, i) => (
                <button
                  key={i}
                  data-testid={`assistant-suggestion-${i}`}
                  onClick={() => handleSuggestion(s)}
                  className="text-[11px] px-3 py-1.5 rounded-full font-medium border border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:border-violet-300 dark:hover:border-violet-700 hover:text-violet-600 dark:hover:text-violet-300 hover:bg-violet-50 dark:hover:bg-violet-900/20 transition-all shadow-sm"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} flex-col animate-fadeIn`} data-testid={`assistant-msg-${i}`}>
              <div className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} w-full`}>
                <div className={`max-w-[85%] px-3.5 py-2.5 text-sm break-words transition-shadow ${
                  m.role === 'user'
                    ? 'bg-violet-600 text-white rounded-2xl rounded-br-md whitespace-pre-wrap shadow-md shadow-violet-600/10'
                    : m.meta?.error
                    ? 'bg-rose-50 dark:bg-rose-950/60 text-rose-900 dark:text-rose-100 border border-rose-200 dark:border-rose-800 rounded-2xl rounded-bl-md whitespace-pre-wrap'
                    : 'bg-violet-50/60 dark:bg-violet-900/10 text-zinc-800 dark:text-zinc-200 border border-violet-100/60 dark:border-violet-800/30 rounded-2xl rounded-bl-md shadow-sm'
                }`}>
                  {m.role === 'assistant' && !m.meta?.error ? (
                    <div data-testid={`assistant-msg-body-${i}`} className="assistant-md text-[13px] leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                        {m.content || m.text || ''}
                      </ReactMarkdown>
                      {/* 📋 نسخ Proposal — يظهر فقط عندما تحتوي الرسالة اقتراح كود */}
                      {/proposal/i.test(m.content || m.text || '') && (
                        <button
                          data-testid={`copy-proposal-btn-${i}`}
                          onClick={async () => {
                            try {
                              await navigator.clipboard.writeText(m.content || m.text || '');
                              setCopiedIdx(i);
                              setTimeout(() => setCopiedIdx(null), 2000);
                            } catch (e) { /* clipboard unavailable */ }
                          }}
                          className="mt-2 flex items-center gap-1 text-[10px] px-2.5 py-1 rounded-lg bg-violet-50 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 border border-violet-200 dark:border-violet-700 hover:bg-violet-100 dark:hover:bg-violet-800/50 transition-colors"
                        >
                          {copiedIdx === i ? <><Check size={11} /> نُسخ ✓</> : <><Copy size={11} /> نسخ Proposal</>}
                        </button>
                      )}
                    </div>
                  ) : (
                    m.content || m.text
                )}
                {m.role === 'assistant' && m.meta?.agent && (
                  <div className="text-[9px] mt-1.5 opacity-60 flex gap-1 items-center font-medium">
                    {m.meta.ai_used ? <><Sparkles size={8} />AI</> : '⚙️قواعد'}
                    <span>•</span>
                    <span>{AGENT_LABELS[m.meta.agent]?.name || m.meta.agent}</span>
                    {m.meta.tool_results?.length > 0 && (
                      <><span>•</span><span>{m.meta.tool_results.length} أداة</span></>
                    )}
                  </div>
                )}
              </div>
              </div>
              {/* 🎴 Cards rendered just below the assistant bubble (Phase 3B) */}
              {m.role === 'assistant' && (Array.isArray(m.meta?.cards) || Array.isArray(m.cards)) && (m.meta?.cards || m.cards).length > 0 && (
                <div className="w-full mt-2 space-y-2 animate-fadeIn" data-testid={`assistant-msg-cards-${i}`}>
                  {(m.meta?.cards || m.cards).map((c, j) => (
                    <AssistantCard key={`${c.type}-${c.id}-${j}`} card={c} onAction={handleCardAction} />
                  ))}
                </div>
              )}
            </div>
          ))
        )}
        {busy && (
          <div className="flex justify-start animate-fadeIn" data-testid="assistant-typing">
            <div className="flex items-center gap-2 px-3.5 py-2.5 rounded-2xl rounded-bl-md bg-violet-50/60 dark:bg-violet-900/10 border border-violet-100/60 dark:border-violet-800/30 w-fit">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-typingDot" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-typingDot" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-typingDot" style={{ animationDelay: '300ms' }} />
              </div>
              <span data-testid="assistant-typing-phase" className="text-[12px] text-violet-500/80 dark:text-violet-300/80 font-medium">
                {streamingPhase === 'executing' ? '⚙️ يُنفّذ...' :
                  streamingPhase === 'thinking' ? '🧠 يفكّر...' :
                    streamingPhase || '...'}
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input — Kodee style rounded wrapper */}
      <div className="px-3 pb-3 pt-2 bg-white/90 dark:bg-zinc-950/90 backdrop-blur-xl border-t border-zinc-100 dark:border-zinc-800/80">
        <div className="flex items-center gap-1 bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-1 focus-within:border-violet-400 dark:focus-within:border-violet-600 transition-colors">
          <input
            data-testid="assistant-input"
            type="text"
            value={displayInput}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder={voice?.listening ? '🎙️ أستمع إليك… تكلّم' : 'اسأل أو نفّذ — مثال: سجل عميل احمد'}
            disabled={busy}
            className="flex-1 min-w-0 text-sm bg-transparent text-zinc-900 dark:text-zinc-100 px-3 py-2.5 border-none focus:outline-none placeholder:text-zinc-400 disabled:opacity-50"
          />
          {voice?.supported?.stt && (
            <button
              data-testid="assistant-mic-btn"
              onClick={handleMic}
              disabled={busy}
              title={voice.listening ? 'إيقاف الاستماع' : '🎙️ تحدّث'}
              className={`p-2.5 rounded-xl shrink-0 transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                voice.listening
                  ? 'bg-rose-500 text-white animate-pulse shadow-md shadow-rose-500/30'
                  : 'text-zinc-400 hover:text-violet-600 hover:bg-violet-50 dark:hover:bg-violet-900/20'
              }`}
            >
              <Mic size={16} />
            </button>
          )}
          <button
            data-testid="assistant-send-btn"
            onClick={handleSend}
            disabled={busy || !input.trim()}
            title="إرسال / تنفيذ ذكي — يفهم الأسئلة والأوامر (حتى المتعددة) تلقائياً"
            className="p-2.5 rounded-xl shrink-0 bg-violet-600 hover:bg-violet-700 text-white shadow-sm disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-95"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
      </>
      )}
    </div>
  );
};

export default UnifiedAssistantDrawer;
