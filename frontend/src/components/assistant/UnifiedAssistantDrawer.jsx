import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, X, Send, Sparkles, AlertTriangle, RefreshCw, Settings, Trash2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useLocation } from 'react-router-dom';
import { useAssistant } from './AssistantProvider';
import { AssistantCard } from './AssistantCard';
import { AssistantDashboard } from './AssistantDashboard';

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
    sendMessage, resetSession, appendMessage,
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

  // 🆕 Phase 3C.5 — Smart Execute (POST /api/runtime/execute)
  // Routes the text through LLM intent → policy → auto-commit (or pending_approval).
  const handleExecute = async () => {
    if (!input.trim() || busy) return;
    const text = input.trim();
    setInput('');
    let proposer = null;
    try {
      const u = JSON.parse(localStorage.getItem('user') || 'null');
      proposer = u?.name || u?.username || null;
    } catch (e) { /* noop */ }

    // 1) Push the user's request as a chat bubble
    appendMessage?.({ role: 'user', text: `🚀 ${text}` });

    try {
      const url = `${process.env.REACT_APP_BACKEND_URL || ''}/api/runtime/execute`;
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, proposer }),
      });
      const data = await resp.json();
      const d = data?.data || {};
      const action = d.action?.action || 'unknown';
      let summary;
      let cards = [];

      if (d.status === 'committed') {
        summary = `✅ تم تنفيذ **${action}** مباشرة (auto-safe).\n• نتيجة: ${(d.result || {}).name || (d.result || {}).id || JSON.stringify(d.result || {}).slice(0, 120)}\n• Execution: ${d.execution_id}`;
      } else if (d.status === 'pending_approval') {
        summary = `⏳ **${action}** بانتظار اعتماد بشري.\n• Draft: ${d.draft?.id}\n• Approval: ${d.approval?.approval_id}`;
        // Synthesize an ApprovalCard so the user can act on it inline
        cards = [{
          type: 'ApprovalCard',
          id: d.approval?.approval_id,
          title: `موافقة — ${action}`,
          status: 'pending',
          data: { approval_id: d.approval?.approval_id, draft_id: d.draft?.id, status: 'pending', requester: proposer },
          actions: [
            { id: 'approve', label: 'اعتماد', intent: 'runtime',
              endpoint: `/api/runtime/approvals/${d.approval?.approval_id}/approve`, method: 'POST' },
            { id: 'reject', label: 'رفض', intent: 'runtime',
              endpoint: `/api/runtime/approvals/${d.approval?.approval_id}/reject`, method: 'POST' },
          ],
        }];
      } else if (d.status === 'read_only') {
        const n = Array.isArray(d.result) ? d.result.length : 0;
        summary = `🔎 **${action}** — ${n} نتيجة.`;
      } else if (d.status === 'rejected') {
        summary = `🚫 لم أفهم: ${d.reason || 'unknown_action'}. جرّب صياغة أوضح.`;
      } else {
        summary = `⚠️ ${d.reason || JSON.stringify(d).slice(0, 200)}`;
      }
      appendMessage?.({ role: 'assistant', text: summary, cards });
    } catch (e) {
      appendMessage?.({ role: 'assistant', text: `⚠️ فشل التنفيذ الذكي: ${e.message}` });
    }
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
    // 🆕 Phase 3C — runtime intent: call the runtime REST endpoint directly.
    if (action?.intent === 'runtime' && action?.endpoint) {
      try {
        // Read the logged-in user once — used as requester/approver/committer
        let me = 'anonymous';
        try {
          const u = JSON.parse(localStorage.getItem('user') || 'null');
          me = u?.name || u?.username || 'anonymous';
        } catch (e) { /* noop */ }

        const url = `${(process.env.NODE_ENV === 'production' ? '' : (process.env.REACT_APP_BACKEND_URL || ''))}${action.endpoint}`;
        const opts = {
          method: action.method || 'POST',
          headers: { 'Content-Type': 'application/json' },
        };
        if ((action.method || 'POST') !== 'GET') {
          opts.body = JSON.stringify({
            requester: me, approver: me, committer: me, rollbacker: me, by: me,
          });
        }
        const resp = await fetch(url, opts);
        const data = await resp.json();
        const ok = resp.ok && data?.success;
        const summary = ok
          ? `✅ تم: ${action.label} (draft: ${card.id})`
          : `⚠️ فشل: ${action.label} — ${JSON.stringify(data?.detail || data?.error || data).slice(0, 120)}`;
        sendMessage(summary);
      } catch (e) {
        sendMessage(`⚠️ خطأ في ${action.label}: ${e.message}`);
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
      className={
        isMobile
          ? 'fixed bottom-0 inset-x-0 z-[80] w-full bg-white dark:bg-slate-900 rounded-t-2xl shadow-2xl border-t-2 border-x border-slate-300 dark:border-slate-700 flex flex-col overflow-hidden'
          : 'fixed bottom-6 right-6 z-[80] w-[420px] h-[640px] bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border-2 border-slate-300 dark:border-slate-700 flex flex-col overflow-hidden'
      }
      style={isMobile ? { height: '95vh', paddingBottom: 'env(safe-area-inset-bottom)' } : undefined}
      dir="rtl"
    >
      {/* Mobile drag handle */}
      {isMobile && (
        <div className="flex justify-center py-2" data-testid="assistant-mobile-handle">
          <div className="w-10 h-1 bg-slate-300 dark:bg-slate-600 rounded-full" />
        </div>
      )}
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
          <div className="text-center py-3">
            <Bot className="mx-auto mb-2 text-indigo-500" size={32} />
            <p className="text-sm font-bold text-slate-700 dark:text-slate-200 mb-1">مرحباً! كيف أساعدك اليوم؟</p>
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
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} flex-col`} data-testid={`assistant-msg-${i}`}>
              <div className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} w-full`}>
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
              {/* 🎴 Cards rendered just below the assistant bubble (Phase 3B) */}
              {m.role === 'assistant' && Array.isArray(m.meta?.cards) && m.meta.cards.length > 0 && (
                <div className="w-full mt-1.5 space-y-1.5" data-testid={`assistant-msg-cards-${i}`}>
                  {m.meta.cards.map((c, j) => (
                    <AssistantCard key={`${c.type}-${c.id}-${j}`} card={c} onAction={handleCardAction} />
                  ))}
                </div>
              )}
            </div>
          ))
        )}
        {busy && (
          <div className="flex justify-start" data-testid="assistant-typing">
            <div className="bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-2xl rounded-bl-sm px-3 py-2 text-sm">
              <RefreshCw className="inline animate-spin ml-1" size={12} />
              <span data-testid="assistant-typing-phase">{streamingPhase || 'يفكّر...'}</span>
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
          placeholder="اسأل أو نفّذ — مثل: 'سجل عميل احمد 0501234567'"
          disabled={busy}
          className="flex-1 text-sm bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100 rounded-full px-3 py-2 border-2 border-slate-300 dark:border-slate-600 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
        />
        <button
          data-testid="assistant-power-shortcut"
          onClick={() => setInput((v) => v.startsWith('/power') ? v : `/power ${v}`.trim())}
          disabled={busy}
          title="Power Mode (أوامر متعددة)"
          className="px-2.5 py-2 rounded-full bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-[11px] font-bold"
        >
          ⚡
        </button>
        <button
          data-testid="assistant-execute-btn"
          onClick={handleExecute}
          disabled={busy || !input.trim()}
          title="تنفيذ ذكي عبر LLM (تنشئ تلقائياً بعد موافقة)"
          className="px-2.5 py-2 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-[12px] font-bold"
        >
          🚀
        </button>
        <button
          data-testid="assistant-send-btn"
          onClick={handleSend}
          disabled={busy || !input.trim()}
          className="px-3 py-2 rounded-full bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title="إرسال (سؤال)"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
};

export default UnifiedAssistantDrawer;
