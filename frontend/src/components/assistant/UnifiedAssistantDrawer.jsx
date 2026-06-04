import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, X, Send, Sparkles, AlertTriangle, RefreshCw, Settings, Trash2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useLocation } from 'react-router-dom';
import { useAssistant } from './AssistantProvider';

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
];
const SUGGESTIONS_BY_PATH = {
  '/customers': ['كم ذمم العملاء؟', 'من هم أعلى المدينين؟', 'آخر العمليات', 'كم ذمم الموردين؟'],
  '/suppliers': ['كم ذمم الموردين؟', 'من أعلى الموردين دائنية؟', 'أهم التنبيهات', 'كيف التدفق النقدي؟'],
  '/parts': ['ما هي القطع الناقصة؟', 'قطع وصلت للحد الأدنى', 'أهم تنبيهات المخزون', 'آخر العمليات'],
  '/operations': ['آخر العمليات', 'عمليات بها قيد مفقود', 'كم درجة الصحة المالية؟', 'أهم التنبيهات'],
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
    messages, busy, activeAgent,
    alerts, stats,
    model, setModel, availableModels,
    sendMessage, resetSession,
  } = useAssistant();

  const [input, setInput] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const messagesEndRef = useRef(null);
  const location = useLocation();
  const pageSuggestions = useMemo(() => getSuggestionsForPath(location?.pathname || '/'), [location?.pathname]);

  // Auto-scroll on new messages
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [messages.length, busy]);

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

  const handleSend = async () => {
    if (!input.trim() || busy) return;
    const text = input.trim();
    setInput('');
    await sendMessage(text);
  };

  const handleSuggestion = (s) => {
    if (busy) return;
    setInput('');
    sendMessage(s);
  };

  const criticalCount = (alerts || []).filter((a) => a.severity === 'critical').length;
  const agentMeta = activeAgent ? AGENT_LABELS[activeAgent] : null;

  // FAB (Floating Action Button)
  if (!open) {
    return (
      <button
        data-testid="unified-assistant-fab"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-[80] group"
        title="افتح المساعد الذكي (Ctrl+Shift+B)"
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
      className="fixed bottom-0 right-0 sm:bottom-6 sm:right-6 z-[80] w-full sm:w-[420px] h-[85vh] sm:h-[640px] bg-white dark:bg-slate-900 rounded-t-2xl sm:rounded-2xl shadow-2xl border-2 border-slate-300 dark:border-slate-700 flex flex-col overflow-hidden"
      dir="rtl"
    >
      {/* Header */}
      <div className={`bg-gradient-to-r ${agentMeta?.color || 'from-indigo-600 to-purple-700'} text-white px-4 py-3 flex items-center justify-between`}>
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-lg">
            {agentMeta?.icon || '🤖'}
          </div>
          <div className="min-w-0">
            <h3 className="font-extrabold text-sm truncate">{agentMeta?.name || 'المساعد الذكي'}</h3>
            <p className="text-[10px] opacity-90">
              {stats?.ai_enabled ? <><Sparkles size={9} className="inline ml-0.5" /> AI نشط</> : 'محرك قواعد'}
              <span className="mx-1 opacity-60">·</span>
              <span data-testid="assistant-model-badge" className="font-bold">
                {model === 'ollama' ? '🦙 Ollama' : '⚡ GPT'}
              </span>
              {alerts.length > 0 && (
                <span className="mr-2"><AlertTriangle size={9} className="inline ml-0.5" />{alerts.length} تنبيه</span>
              )}
            </p>
          </div>
        </div>
        <div className="flex gap-1">
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
            className="p-1.5 rounded hover:bg-white/20 transition-colors"
            title="إغلاق"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="bg-slate-100 dark:bg-slate-800 border-b border-slate-300 dark:border-slate-700 p-2 space-y-2" data-testid="assistant-settings-panel">
          <div className="flex justify-between items-center">
            <span className="text-[11px] text-slate-600 dark:text-slate-300">
              {messages.length} رسالة في الجلسة
            </span>
            <button
              data-testid="assistant-reset-btn"
              onClick={() => { resetSession(); setShowSettings(false); }}
              className="text-[11px] px-2 py-1 rounded bg-rose-600 hover:bg-rose-700 text-white font-bold inline-flex items-center gap-1"
            >
              <Trash2 size={10} /> مسح المحادثة
            </button>
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

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-50 dark:bg-slate-950" data-testid="assistant-messages">
        {messages.length === 0 ? (
          <div className="text-center py-6">
            <Bot className="mx-auto mb-2 text-indigo-500" size={36} />
            <p className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-2">مرحباً! كيف أساعدك اليوم؟</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">جرّب أحد الاقتراحات:</p>
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
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`} data-testid={`assistant-msg-${i}`}>
              <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm break-words ${
                m.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-sm whitespace-pre-wrap'
                  : m.meta?.error
                  ? 'bg-rose-100 dark:bg-rose-950 text-rose-900 dark:text-rose-100 border border-rose-300 dark:border-rose-700 rounded-bl-sm whitespace-pre-wrap'
                  : 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 border border-slate-300 dark:border-slate-700 rounded-bl-sm'
              }`}>
                {m.role === 'assistant' && !m.meta?.error ? (
                  <div data-testid={`assistant-msg-body-${i}`} className="assistant-md text-[13px]">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                      {m.content || ''}
                    </ReactMarkdown>
                  </div>
                ) : (
                  m.content
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
          ))
        )}
        {busy && (
          <div className="flex justify-start" data-testid="assistant-typing">
            <div className="bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-2xl rounded-bl-sm px-3 py-2 text-sm">
              <RefreshCw className="inline animate-spin ml-1" size={12} /> يفكّر...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t-2 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 p-2 flex gap-1">
        <input
          data-testid="assistant-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="اسأل عن أي شيء..."
          disabled={busy}
          className="flex-1 text-sm bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 rounded-full px-3 py-2 border-2 border-slate-300 dark:border-slate-600 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
        />
        <button
          data-testid="assistant-send-btn"
          onClick={handleSend}
          disabled={busy || !input.trim()}
          className="px-3 py-2 rounded-full bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title="إرسال"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
};

export default UnifiedAssistantDrawer;
