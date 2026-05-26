import React, { useEffect, useRef, useState } from 'react';
import { Bot, X, Send, Sparkles, AlertTriangle, RefreshCw, Settings, Trash2 } from 'lucide-react';
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

const SUGGESTIONS = [
  'كم درجة الصحة المالية؟',
  'أعطني أهم التنبيهات',
  'كم ذمم العملاء؟',
  'كم زيارة نشطة الآن؟',
  'كيف التدفق النقدي؟',
];

export const UnifiedAssistantDrawer = () => {
  const {
    open, setOpen,
    messages, busy, activeAgent,
    alerts, stats,
    sendMessage, resetSession,
  } = useAssistant();

  const [input, setInput] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const messagesEndRef = useRef(null);

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
    setInput(s);
    setTimeout(() => sendMessage(s), 60);
  };

  const criticalCount = (alerts || []).filter((a) => a.severity === 'critical').length;
  const agentMeta = activeAgent ? AGENT_LABELS[activeAgent] : null;

  // FAB (Floating Action Button)
  if (!open) {
    return (
      <button
        data-testid="unified-assistant-fab"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 left-6 z-40 group"
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
      className="fixed bottom-0 left-0 sm:bottom-6 sm:left-6 z-40 w-full sm:w-[420px] h-[85vh] sm:h-[640px] bg-white dark:bg-slate-900 rounded-t-2xl sm:rounded-2xl shadow-2xl border-2 border-slate-300 dark:border-slate-700 flex flex-col overflow-hidden"
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
        <div className="bg-slate-100 dark:bg-slate-800 border-b border-slate-300 dark:border-slate-700 p-2 flex justify-between items-center" data-testid="assistant-settings-panel">
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
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-50 dark:bg-slate-950" data-testid="assistant-messages">
        {messages.length === 0 ? (
          <div className="text-center py-6">
            <Bot className="mx-auto mb-2 text-indigo-500" size={36} />
            <p className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-2">مرحباً! كيف أساعدك اليوم؟</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">جرّب أحد الاقتراحات:</p>
            <div className="flex flex-wrap gap-1.5 justify-center">
              {SUGGESTIONS.map((s, i) => (
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
              <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap break-words ${
                m.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-sm'
                  : m.meta?.error
                  ? 'bg-rose-100 dark:bg-rose-950 text-rose-900 dark:text-rose-100 border border-rose-300 dark:border-rose-700 rounded-bl-sm'
                  : 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 border border-slate-300 dark:border-slate-700 rounded-bl-sm'
              }`}>
                {m.content}
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
