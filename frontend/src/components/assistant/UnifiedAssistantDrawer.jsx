import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, X, Send, Sparkles, AlertTriangle, RefreshCw, Settings, Trash2, Mic, Volume2, VolumeX, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useLocation } from 'react-router-dom';
import axios from 'axios';
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
 * 🤖 UnifiedAssistantDrawer — مساعد عائم موحّد (drawer من اليسار/يمين).
 * يستهلك AssistantProvider — لا state محلي مكرّر.
 *
 * يستبدل: UnifiedBotWidget + FloatingAIAssistant + WorkshopAIBot UI.
 */

const AGENT_LABELS = {
  FirewallAgent: { name: 'وكيل الحماية', icon: '🛡️', color: 'from-rose-600 to-orange-600' },
  FinanceAgent: { name: 'وكيل المالية', icon: '💰', color: 'from-emerald-600 to-teal-600' },
  WorkshopAgent: { name: 'وكيل الورشة', icon: '🔧', color: 'from-blue-600 to-indigo-600' },
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
      ? <code className="px-1 py-0.5 rounded bg-slate-200/70 dark:bg-slate-700 text-[12px] font-mono" {...props}>{children}</code>
      : <pre className="rounded bg-slate-900 text-slate-100 text-[11px] p-2 my-1 overflow-auto" {...props}><code>{children}</code></pre>
  ),
  table: ({ node, ...props }) => (
    <div className="overflow-auto my-1">
      <table className="text-[11px] border-collapse border border-slate-300 dark:border-slate-700" {...props} />
    </div>
  ),
  th: ({ node, ...props }) => <th className="border border-slate-300 dark:border-slate-700 px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 font-bold" {...props} />,
  td: ({ node, ...props }) => <td className="border border-slate-300 dark:border-slate-700 px-1.5 py-0.5" {...props} />,
  a: ({ node, ...props }) => <a className="text-indigo-600 dark:text-indigo-300 underline" target="_blank" rel="noopener noreferrer" {...props} />,
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
  // Derived value (no setState-in-effect): show the live transcript while
  // listening, otherwise fall back to the typed input.
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
      axios.get(`${process.env.REACT_APP_BACKEND_URL || ''}/api/runtime/approvals`, { params: { status: 'pending', limit: 100 } })
        .then(({ data }) => setControlCount((data?.data || []).length))
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

  // 🆕 Single SMART send (merged Send + 🚀 Execute into one button). Multi-intent
  // → /power; otherwise sendMessage auto-routes (action → /runtime/execute,
  // question → /chat) with a graceful rejected→answer fallback.
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

  // Helper: dispatch a "tool" action chip → re-trigger the assistant with the tool's intent.
  const handleCardAction = async (action, card) => {
    if (action?.intent === 'navigate') {
      // close drawer on navigation so user sees the target page (mobile especially)
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
      // Confirm dialog if the action requires it
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
        const bodyData = {
          ...(action.body || {}),
          requester: me, approver: me, committer: me, proposer: me, by: me,
        };

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
            // Approval auto-commit of a delete — report the REAL outcome.
            summary = committedRes.deleted
              ? `✅ **تم الاعتماد والحذف بنجاح.**`
              : `⚠️ تم الاعتماد، لكن لم أعثر على العنصر المطلوب حذفه (ربما حُذف مسبقاً).`;
          } else if (action.id === 'reject') {
            summary = `🚫 تم رفض العملية.`;
          } else {
            summary = `✅ تم: ${action.label}`;
          }
          // Reactive binding — refresh related pages
          try {
            window.dispatchEvent(new CustomEvent('finance:updated', { detail: { source: 'card_action', action: action.id } }));
            window.dispatchEvent(new CustomEvent('runtime:changed', { detail: { source: 'card_action', action: action.id } }));
          } catch (e) { /* noop */ }
        } else {
          summary = `⚠️ ${resultData?.detail || resultData?.error || 'فشل تنفيذ العملية'}`;
        }
        // Show as assistant message
        appendMessage({ role: 'assistant', content: summary, meta: { status: ok ? 'success' : 'error', action: action.id } });
      } catch (e) {
        // The backend may raise HTTPException with a dict `detail`
        // (e.g. {error:'four_eyes_violation', msg:'...'}). Render a readable
        // string instead of "[object Object]".
        const detail = e?.response?.data?.detail;
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

  // FAB (Floating Action Button)
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
          <div className="w-14 h-14 rounded-full bg-gradient-to-br from-indigo-600 to-purple-700 shadow-2xl flex items-center justify-center hover:scale-110 transition-transform">
            <Bot className="text-white" size={28} />
          </div>
          {criticalCount > 0 && (
            <span data-testid="assistant-fab-badge" className="absolute -top-1 -right-1 bg-rose-500 text-white text-[10px] font-bold rounded-full w-6 h-6 flex items-center justify-center border-2 border-white animate-pulse">
              {criticalCount}
            </span>
          )}
          <div className="absolute top-0 right-0 w-3 h-3 bg-emerald-400 rounded-full border-2 border-white" />
        </div>
      </button>
    );
  }

  return (
    <div
      data-testid="unified-assistant-drawer"
      className={
        isMobile
          ? 'fixed bottom-0 inset-x-0 z-[80] w-full bg-white dark:bg-slate-900 rounded-t-2xl shadow-2xl border-t-2 border-x border-slate-300 dark:border-slate-700 flex flex-col overflow-hidden'
          : 'fixed bottom-6 right-6 z-[80] w-[420px] h-[640px] bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border-2 border-slate-300 dark:border-slate-700 flex flex-col overflow-hidden'
      }
      style={isMobile ? { height: '80vh', maxHeight: '80vh', paddingBottom: 'env(safe-area-inset-bottom)' } : undefined}
      dir="rtl"
    >
      {/* Mobile drag handle — tap to close */}
      {isMobile && (
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="flex flex-col items-center justify-center py-2 w-full active:bg-slate-100 dark:active:bg-slate-800"
          data-testid="assistant-mobile-handle"
          title="اضغط للإغلاق"
        >
          <div className="w-12 h-1.5 bg-slate-300 dark:bg-slate-600 rounded-full" />
        </button>
      )}
      {/* Header */}
      <div className={`bg-gradient-to-r ${agentMeta?.color || 'from-indigo-600 to-purple-700'} text-white px-4 py-3 flex items-center justify-between`}>
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-lg">
            {agentMeta?.icon || '🤖'}
          </div>
          <div className="min-w-0">
            <h3 className="font-extrabold text-sm truncate">{agentMeta?.name || 'كاترينا'}</h3>
            <p className="text-[10px] opacity-90">
              {voice?.listening ? <span className="text-emerald-200 font-bold">🎙️ أستمع…</span>
                : voice?.speaking ? <span className="text-emerald-200 font-bold">🔊 أتحدّث…</span>
                : (stats?.ai_enabled ? <><Sparkles size={9} className="inline ml-0.5" /> AI نشط</> : 'محرك قواعد')}
              <span className="mx-1 opacity-60">·</span>
              <span data-testid="assistant-model-badge" className="font-bold">
                {model === 'ollama' ? '🦙 Ollama' : '⚡ Sonnet'}
              </span>
              {alerts.length > 0 && (
                <span className="mr-2"><AlertTriangle size={9} className="inline ml-0.5" />{alerts.length} تنبيه</span>
              )}
            </p>
          </div>
        </div>
        <div className="flex gap-1 items-center">
          {voice?.supported?.tts && (
            <button
              data-testid="assistant-voice-toggle"
              onClick={() => setVoiceEnabled(!voiceEnabled)}
              className={`p-1.5 rounded transition-colors ${voiceEnabled ? 'bg-white/30' : 'hover:bg-white/20'}`}
              title={voiceEnabled ? 'إيقاف نطق الردود' : 'تفعيل نطق الردود'}
            >
              {voiceEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
            </button>
          )}
          <button
            data-testid="assistant-settings-btn"
            onClick={() => setShowSettings(!showSettings)}
            className="p-1.5 rounded hover:bg-white/20 transition-colors"
            title="إعدادات"
          >
            <Settings size={14} />
          </button>
          <button
            data-testid="assistant-close-btn"
            onClick={() => setOpen(false)}
            className={`rounded hover:bg-white/20 transition-colors ${isMobile ? 'p-2 bg-white/15' : 'p-1.5'}`}
            title="إغلاق"
          >
            <X size={isMobile ? 22 : 16} />
          </button>
        </div>
      </div>

      {/* 🗂️ Tabs — المحادثة / مركز التحكم المالي */}
      <div className="flex border-b-2 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900" data-testid="assistant-tabs">
        <button
          data-testid="assistant-tab-chat"
          onClick={() => setTab('chat')}
          className={`flex-1 py-2 text-xs font-black transition-colors border-b-2 -mb-0.5 ${
            tab === 'chat'
              ? 'border-indigo-600 text-indigo-700 dark:text-indigo-300 bg-indigo-50/60 dark:bg-indigo-950/40'
              : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
          }`}
        >
          💬 المحادثة
        </button>
        <button
          data-testid="assistant-tab-control"
          onClick={() => setTab('control')}
          className={`flex-1 py-2 text-xs font-black transition-colors border-b-2 -mb-0.5 inline-flex items-center justify-center gap-1 ${
            tab === 'control'
              ? 'border-indigo-600 text-indigo-700 dark:text-indigo-300 bg-indigo-50/60 dark:bg-indigo-950/40'
              : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
          }`}
        >
          🛡️ مركز التحكم
          {controlCount > 0 && (
            <span data-testid="assistant-control-badge" className="min-w-[16px] h-[16px] px-1 rounded-full bg-rose-600 text-white text-[9px] font-black inline-flex items-center justify-center">
              {controlCount}
            </span>
          )}
        </button>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="bg-slate-100 dark:bg-slate-800 border-b border-slate-300 dark:border-slate-700 p-2 space-y-2" data-testid="assistant-settings-panel">
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-slate-600 dark:text-slate-300">
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
                className={`text-[11px] px-2 py-1 rounded font-bold inline-flex items-center gap-1 ${
                  dailySummaryOn ? 'bg-emerald-600 hover:bg-emerald-700 text-white' : 'bg-slate-400 hover:bg-slate-500 text-white'
                }`}
              >
                📅 الملخص اليومي: {dailySummaryOn ? 'مفعّل' : 'موقوف'}
              </button>
              <button
                data-testid="assistant-reset-btn"
                onClick={() => { resetSession(); setShowSettings(false); }}
                className="text-[11px] px-2 py-1 rounded bg-rose-600 hover:bg-rose-700 text-white font-bold inline-flex items-center gap-1"
              >
                <Trash2 size={10} /> مسح المحادثة
              </button>
            </div>
          </div>
          {/* 🆕 Model selector */}
          {availableModels && availableModels.length > 0 && (
            <div data-testid="assistant-model-selector" className="space-y-1">
              <div className="text-[10px] font-bold text-slate-700 dark:text-slate-300">النموذج الذكي:</div>
              <div className="grid grid-cols-2 gap-1.5">
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
                      className={`text-right text-[11px] p-2 rounded border transition-colors ${
                        selected
                          ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-200'
                          : disabled
                            ? 'border-slate-300 dark:border-slate-700 bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed opacity-60'
                            : 'border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:border-indigo-400'
                      }`}
                    >
                      <div className="font-bold flex items-center gap-1 justify-end">
                        {selected && <span>✓</span>}
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

      {tab === 'control' ? (
        <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950" data-testid="assistant-control-panel">
          <ControlCenterTab onCountChange={setControlCount} />
        </div>
      ) : (
      <>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-50 dark:bg-slate-950" data-testid="assistant-messages">
        {/* 🆕 Phase 3C.7 — recent executed operations widget (always visible at top) */}
        <RecentOperationsWidget variant="drawer" limit={6} className="mb-2" />
        {messages.length === 0 ? (
          <div className="text-center py-3">
            <Bot className="mx-auto mb-2 text-indigo-500" size={32} />
            <p className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-1">هلا والله! أنا كاترينا 👋 كيف أقدر أساعدك؟</p>
            <AssistantDashboard onAskMore={(p) => sendMessage(`تفاصيل ${p.label}`)} />
            <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-3 mb-1.5">أو جرّب:</p>
            <div className="flex flex-wrap gap-1.5 justify-center">
              {pageSuggestions.map((s, i) => (
                <button
                  key={i}
                  data-testid={`assistant-suggestion-${i}`}
                  onClick={() => handleSuggestion(s)}
                  className="text-[11px] px-2.5 py-1 rounded-full bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-200 hover:bg-indigo-200 dark:hover:bg-indigo-800 transition-colors border border-indigo-300 dark:border-indigo-700"
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
                <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm break-words shadow-sm transition-all hover:shadow-md ${
                  m.role === 'user'
                    ? 'bg-gradient-to-br from-indigo-600 to-indigo-700 text-white rounded-br-md whitespace-pre-wrap shadow-indigo-500/20'
                    : m.meta?.error
                    ? 'bg-rose-50 dark:bg-rose-950/70 text-rose-900 dark:text-rose-100 border border-rose-200 dark:border-rose-800 rounded-bl-md whitespace-pre-wrap'
                    : 'bg-white dark:bg-slate-800/80 text-slate-900 dark:text-slate-100 border border-slate-200 dark:border-slate-700 rounded-bl-md backdrop-blur-sm'
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
                          className="mt-2 flex items-center gap-1 text-[10px] px-2 py-1 rounded-md bg-indigo-50 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-700 hover:bg-indigo-100 dark:hover:bg-indigo-800 transition-colors"
                        >
                          {copiedIdx === i ? <><Check size={11} /> نُسخ ✓</> : <><Copy size={11} /> نسخ Proposal</>}
                        </button>
                      )}
                    </div>
                  ) : (
                    m.content || m.text
                )}
                {m.role === 'assistant' && m.meta?.agent && (
                  <div className="text-[9px] mt-1 opacity-70 flex gap-1 items-center">
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
            <div className="bg-white dark:bg-slate-800 border border-indigo-200 dark:border-indigo-700 rounded-2xl rounded-bl-md px-3 py-2.5 text-sm shadow-sm">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-typingDot" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-typingDot" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-typingDot" style={{ animationDelay: '300ms' }} />
                </div>
                <span data-testid="assistant-typing-phase" className="text-[12px] text-slate-600 dark:text-slate-300 font-medium">
                  {streamingPhase === 'executing' ? '⚙️ يُنفّذ...' :
                    streamingPhase === 'thinking' ? '🧠 يفكّر...' :
                      streamingPhase || '...'}
                </span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input — single SMART send button (merged Send + 🚀 Execute) */}
      <div className="border-t-2 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-2 flex gap-1.5">
        <input
          data-testid="assistant-input"
          type="text"
          value={displayInput}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder={voice?.listening ? '🎙️ أستمع إليك… تكلّم' : 'اسأل أو نفّذ — مثال: سجل عميل احمد 0501234567'}
          disabled={busy}
          className="flex-1 text-sm bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 rounded-full px-4 py-2.5 border-2 border-slate-300 dark:border-slate-600 focus:outline-none focus:border-indigo-500 disabled:opacity-50 transition-colors"
        />
        {voice?.supported?.stt && (
          <button
            data-testid="assistant-mic-btn"
            onClick={handleMic}
            disabled={busy}
            title={voice.listening ? 'إيقاف الاستماع' : '🎙️ تحدّث'}
            className={`px-3 py-2.5 rounded-full text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md ${
              voice.listening
                ? 'bg-rose-600 animate-pulse shadow-rose-500/40'
                : 'bg-slate-600 hover:bg-slate-700'
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
          className="px-4 py-2.5 rounded-full bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:scale-105 active:scale-95 shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/50"
        >
          <Send size={16} />
        </button>
      </div>
      </>
      )}
    </div>
  );
};

export default UnifiedAssistantDrawer;
