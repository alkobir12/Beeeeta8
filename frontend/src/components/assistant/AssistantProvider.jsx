import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { resolveBackendBase } from '../../utils/backendBase';
import { useVoice } from './useVoice';

/**
 * 🤖 AssistantProvider — Shared state for the Unified Assistant.
 *  • Single conversation store (session-based)
 *  • Single event listener for finance:updated → re-fetch alerts
 *  • Tool execution + chat through one endpoint
 *  • Persists session_id in localStorage to keep history across reloads
 *
 *  Replaces 3 separate stores (UnifiedBotWidget local state + WorkshopAIBot + FirewallPanel insights).
 */

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);
const WORKSHOP_ID = process.env.REACT_APP_WORKSHOP_ID || 'finmodule-sync';
const STORAGE_KEY = 'assistant.session_id';

const hasAuthToken = () => {
  try { return Boolean(localStorage.getItem('auth_token')); } catch { return false; }
};

const AssistantContext = createContext(null);

// 🔗 ترابط حي — يبثّ أحداث التحديث لكل الصفحات بعد أي كتابة/مسودة/إلغاء من البوت.
function _dispatchRefreshEvents(executed) {
  if (!executed || !executed.status) return;
  const detail = {
    source: 'assistant_chat',
    action: executed.action,
    entity_id: executed.entity_id,
    approval_id: executed.approval_id,
    status: executed.status,
  };
  try {
    if (executed.status === 'committed') {
      window.dispatchEvent(new CustomEvent('finance:updated', { detail }));
    }
    if (['committed', 'pending_approval', 'cancelled', 'rejected'].includes(executed.status)) {
      window.dispatchEvent(new CustomEvent('runtime:changed', { detail }));
    }
  } catch (e) { /* noop */ }
}

export const AssistantProvider = ({ children }) => {
  const [sessionId, setSessionId] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) || ''; } catch (e) { return ''; }
  });
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeAgent, setActiveAgent] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState(null);
  // 🆕 Model selector — persisted across reloads ('gpt' legacy → 'sonnet')
  const MODEL_KEY = 'assistant.model';
  const [model, setModelState] = useState(() => {
    try {
      const stored = localStorage.getItem(MODEL_KEY);
      return (!stored || stored === 'gpt') ? 'sonnet' : stored;
    } catch (e) { return 'sonnet'; }
  });
  const setModel = useCallback((m) => {
    setModelState(m);
    try { localStorage.setItem(MODEL_KEY, m); } catch (e) { /* noop */ }
  }, []);
  const [availableModels, setAvailableModels] = useState([
    // Default fallback list so the selector shows even before /models lands
    { id: 'sonnet', label: 'Claude Sonnet 4.6', provider: 'anthropic', model: 'claude-sonnet-4-6', available: true, description: 'ذكاء عالٍ وفهم ممتاز للهجة (سحابي)' },
    { id: 'ollama', label: 'Ollama (محلي)', provider: 'ollama', model: 'llama3.2:3b', available: true, description: 'خصوصية تامة (يعمل بدون إنترنت)' },
  ]);

  // 🎙️ Voice (كاترينا): browser-native STT + TTS. Auto-speak toggle persisted.
  const VOICE_KEY = 'assistant.voice_enabled';
  const voice = useVoice({ lang: 'ar-SA' });
  const [voiceEnabled, setVoiceEnabledState] = useState(() => {
    try { return localStorage.getItem(VOICE_KEY) === '1'; } catch (e) { return false; }
  });
  const setVoiceEnabled = useCallback((v) => {
    setVoiceEnabledState(v);
    try { localStorage.setItem(VOICE_KEY, v ? '1' : '0'); } catch (e) { /* noop */ }
    if (!v) { try { voice.stopSpeaking(); } catch (e) { /* noop */ } }
  }, [voice]);
  // Refs so sendMessage/_executeDirectly can read live voice state without
  // re-creating their callbacks on every voice tick.
  const voiceEnabledRef = useRef(voiceEnabled);
  const voiceRef = useRef(voice);
  useEffect(() => { voiceEnabledRef.current = voiceEnabled; }, [voiceEnabled]);
  useEffect(() => { voiceRef.current = voice; }, [voice]);
  const _maybeSpeak = useCallback((text) => {
    if (voiceEnabledRef.current && text) {
      try { voiceRef.current?.speak?.(text); } catch (e) { /* noop */ }
    }
  }, []);
  const lastFetchRef = useRef(0);
  const skipNextSessionReloadRef = useRef(false);
  const initialSessionLoadedRef = useRef(false);

  // ----- session persistence -----
  useEffect(() => {
    if (sessionId) {
      try { localStorage.setItem(STORAGE_KEY, sessionId); } catch (e) { /* noop */ }
    }
  }, [sessionId]);

  // ----- load existing messages on mount if session exists (ONCE only, skip if produced by sendMessage) -----
  useEffect(() => {
    if (!sessionId) return;
    // Skip if this sessionId was just produced by sendMessage (avoid race condition that wipes optimistic state)
    if (skipNextSessionReloadRef.current) {
      skipNextSessionReloadRef.current = false;
      return;
    }
    // Only run on initial mount (when sessionId came from localStorage)
    if (initialSessionLoadedRef.current) return;
    initialSessionLoadedRef.current = true;
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API_URL}/assistant/session/${sessionId}`);
        if (!cancelled && res.data?.success) {
          const msgs = (res.data.data?.messages || []).map((m) => ({
            role: m.role,
            content: m.content,
            meta: m.meta,
            ts: m.ts,
          }));
          if (msgs.length > 0) setMessages(msgs);
        }
      } catch (e) {
        // session expired or backend not ready — ignore
      }
    })();
    return () => { cancelled = true; };
  }, [sessionId]);

  // ----- fetch alerts (debounced) -----
  const refreshAlerts = useCallback(async (force = false) => {
    if (!hasAuthToken()) return;
    const now = Date.now();
    if (!force && now - lastFetchRef.current < 8000) return; // dedupe within 8s
    lastFetchRef.current = now;
    try {
      const res = await axios.get(`${API_URL}/assistant/alerts`, { params: { limit: 20 } });
      if (res.data?.success) setAlerts(res.data.data || []);
    } catch (e) { /* silent */ }
  }, []);

  const refreshStats = useCallback(async () => {
    if (!hasAuthToken()) return;
    try {
      const res = await axios.get(`${API_URL}/assistant/stats`);
      if (res.data?.success) setStats(res.data.data);
    } catch (e) { /* silent */ }
  }, []);

  useEffect(() => {
    refreshAlerts();
    refreshStats();
  }, [refreshAlerts, refreshStats]);

  // ----- Single listener for finance:updated (replaces multiple duplicate listeners) -----
  useEffect(() => {
    const handler = () => refreshAlerts(true);
    window.addEventListener('finance:updated', handler);
    return () => window.removeEventListener('finance:updated', handler);
  }, [refreshAlerts]);

  // 🆕 streamingPhase: shown as "thinking/tools/rendering" stages during /chat/stream.
  const [streamingPhase, setStreamingPhase] = useState(null);

  // ----- core: send a message (with optional SSE streaming) -----
  //
  // 🆕 Phase 3C.10 — Smart auto-routing with **structured data detection**
  //
  // Routes to /api/runtime/execute when:
  //   (A) Text starts with an action verb (سجل/اضف/...), OR
  //   (B) Text contains structured ERP signals — phone + service/price/year/plate.
  //   This catches "صالون 2009 رقم الجوال 0553747747 خدمه توضيب سعر ٥٥"
  //   even though it doesn't start with a verb.
  // Routes to /chat (LLM) when the text is a question.
  const _looksLikeAction = useCallback((text) => {
    if (!text) return false;
    const t = text.trim();
    if (t.startsWith('/power')) return true;
    // Question words → keep on the LLM path
    const QUESTION_PREFIX = /^(?:ما\s|ماذا|كم\s|كيف|متى|أين|اين|هل\s|من\s|لماذا|أي\s|اي\s|اعرض|أعطني|اعطني|اخبرني|أخبرني|ابحث|اشرح|why|what|how|when|where|وش\s|ايش\s|وين\s)/i;
    if (QUESTION_PREFIX.test(t)) return false;
    // (A) Action verb — NO \b boundaries (they don't work with Arabic in JS!)
    // Instead use (?:\s|$) lookahead for word end, and match start or after space for word start
    const ACTION_VERB = /(?:^|\s)(?:سجل|اضف|أضف|ضيف|حط|انشئ|أنشئ|افتح|أفتح|اصدر|أصدر|اعمل|أعمل|بع|بيع|تحصيل|اقبض|ادفع|اصرف|أصرف|اغلق|أغلق|اقفل|احذف|أحذف|شيل|امسح|عدل|عدّل|غير|update|create|add|delete|register|close|open)(?:ها|ه|هم|هن|ني|نا|وا|وه|ي|ين)?(?:\s|$)/i;
    if (ACTION_VERB.test(t)) return true;
    // (B) Structured ERP data — phone (Saudi: 05 + 8 digits = 10 total, allow 10-11)
    const HAS_PHONE = /05\d{7,9}/.test(t);
    if (HAS_PHONE) return true;
    // (C) Vehicle type + year (e.g. "صالون 2009", "هايلوكس 2016")
    const HAS_VEHICLE_TYPE_YEAR = /(?:صالون|جيب|شاحنة|بكب|فان|نقل|دباب|باص|هايلوكس|كامري|لاندكروزر|باترول|اكسنت|سوناتا|النترا|كورولا|يارس|راف فور|برادو|اف جي|ددسن|hilux|camry|sedan|suv|pickup)\s*\d{4}/i.test(t);
    if (HAS_VEHICLE_TYPE_YEAR) return true;
    // (D) Service keyword + price/amount
    const HAS_SERVICE = /(?:توضيب|تنجيد|صبغ|تلميع|غسيل|صيانة|إصلاح|اصلاح|فحص|تبديل|تركيب|خدم[ةه]|برمجة|سمكرة|رش|دهان|حداده)/i.test(t);
    const HAS_PRICE = /(?:سعر|بسعر|بـ\s*\d|\d+\s*(?:ر\.?س|ريال|sar))/i.test(t);
    if (HAS_SERVICE && (HAS_PRICE || /\d{2,}/.test(t))) return true;
    return false;
  }, []);

// 🔁 POST مع إعادة محاولة واحدة عند أخطاء الخادم العابرة (404/502/503/504
// أثناء إعادة تشغيل الخادم) — يمنع رسائل «تعذّر الاتصال» المربكة.
const TRANSIENT_STATUSES = [404, 502, 503, 504];
async function postChatWithRetry(url, payload, opts = {}) {
  try {
    return await axios.post(url, payload, opts);
  } catch (e) {
    const st = e?.response?.status;
    if (TRANSIENT_STATUSES.includes(st) || !e?.response) {
      await new Promise((r) => setTimeout(r, 2500));
      return axios.post(url, payload, opts);
    }
    throw e;
  }
}

// 🧾 رسالة خطأ ودّية حسب نوع الفشل
function friendlyChatError(e) {
  const st = e?.response?.status;
  if (TRANSIENT_STATUSES.includes(st) || !e?.response) {
    return '⏳ الخادم يُعاد تشغيله أو الاتصال متقطع — انتظر لحظات ثم أعد إرسال رسالتك.';
  }
  if (st === 401) return '🔐 انتهت الجلسة — أعد تسجيل الدخول.';
  return `⚠️ تعذّر الاتصال بالمساعد: ${e?.message || 'unknown'}`;
}

  const _answerViaChat = useCallback(async (text) => {
    let proposer = null;
    try {
      const u = JSON.parse(localStorage.getItem('user') || 'null');
      proposer = u?.name || u?.username || null;
    } catch (e) { /* noop */ }
    try {
      const res = await postChatWithRetry(`${API_URL}/assistant/chat`, {
        message: text,
        session_id: sessionId || undefined,
        workshop_id: WORKSHOP_ID,
        use_ai: true,
        model: model || 'sonnet',
        proposer,
        daily_summary: localStorage.getItem('assistant_daily_summary') !== 'off',
      }, { timeout: 120000 });
      const data = res.data?.success ? res.data.data : null;
      if (!data) throw new Error(res.data?.error || 'assistant_failed');
      if (data.session_id && data.session_id !== sessionId) {
        skipNextSessionReloadRef.current = true;
        setSessionId(data.session_id);
      }
      setActiveAgent(data.agent);
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: data.response,
        meta: { agent: data.agent, tool_results: data.tool_results, ai_used: data.ai_used, model_used: data.model_used, cards: data.cards || [] },
        ts: Date.now() / 1000,
      }]);
      _dispatchRefreshEvents(data.executed);
      _maybeSpeak(data.response);
      return data;
    } catch (e) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: friendlyChatError(e),
        meta: { error: true },
        ts: Date.now() / 1000,
      }]);
      return null;
    }
  }, [sessionId, model, _maybeSpeak]);

  const _executeDirectly = useCallback(async (text) => {
    // POST to /api/runtime/execute and append the result as a chat reply.
    let proposer = null;
    try {
      const u = JSON.parse(localStorage.getItem('user') || 'null');
      proposer = u?.name || u?.username || null;
    } catch (e) { /* noop */ }
    setMessages((prev) => [...prev, { role: 'user', content: text, ts: Date.now() / 1000 }]);
    setBusy(true);
    setStreamingPhase('executing');
    try {
      const url = `${API_URL}/runtime/execute`;
      // Use XMLHttpRequest-style approach via axios to avoid rrweb fetch interceptor conflicts
      const axResp = await axios.post(url, { text, proposer, session_id: sessionId });
      const data = axResp.data || {};
      const d = data?.data || data || {};
      const action = d.action?.action || 'unknown';
      // 🆕 Not an executable action (e.g. a question) → answer via the chat
      // path instead of showing a "couldn't understand" / 422 error.
      if (d.status === 'rejected') {
        return await _answerViaChat(text);
      }
      let summary;
      let cards = [];
      if (d.status === 'committed') {
        const r = d.result || {};
        const labels = {
          create_customer: 'عميل', create_vehicle: 'مركبة', create_visit: 'زيارة',
          create_supplier: 'مورّد',
          delete_operation: 'حذف عملية', delete_customer: 'حذف عميل', delete_vehicle: 'حذف مركبة',
          update_customer: 'تعديل عميل', update_vehicle: 'تعديل مركبة',
        };
        const actionLabel = labels[action] || action;
        if (action === 'delete_customer' || action === 'delete_vehicle') {
          summary = r.deleted
            ? `✅ **تم الحذف** — ${actionLabel}: ${r.name || r.id || ''}`
            : `⚠️ لم أعثر على ما يُحذف.`;
        } else if (action === 'update_customer' || action === 'update_vehicle') {
          const fields = (r._updated_fields || []).join('، ');
          summary = `✅ **تم التعديل** — ${actionLabel}: ${r.name || r.plate_number || r.id || ''}\n📝 حُدّث: ${fields}`;
        } else if (r._duplicate) {
          summary = `⚠️ **${actionLabel} موجود مسبقاً** — ${r.name || r.plate_number || r.id || ''}\nلم يتم إنشاء نسخة مكررة.`;
        } else {
          summary = `✅ **تم بنجاح** — ${actionLabel}: ${r.name || r.plate_number || r.id || ''}\n📌 تم الحفظ في قاعدة البيانات.`;
        }
        // L16 Reactive Binding — notify all listening pages to refresh
        try {
          window.dispatchEvent(new CustomEvent('finance:updated', {
            detail: { source: 'assistant', action, entity_id: r.id }
          }));
        } catch (e) { /* noop */ }
      } else if (d.status === 'needs_clarification') {
        if (d.ask) {
          summary = d.ask;
        } else {
          const entAr = d.entity === 'customer' ? 'عميل' : d.entity === 'supplier' ? 'مورّد' : 'مركبة';
          const cands = d.candidates || [];
          if (d.reason === 'not_found') {
            summary = `🔎 لم أجد ${entAr} مطابقاً. تأكّد من الاسم أو رقم الجوال/اللوحة وحاول مجدداً.`;
          } else {
            const lines = cands.map((c) => (d.entity === 'customer'
              ? `• ${c.name} — ${c.phone || 'بدون جوال'}`
              : `• لوحة ${c.plate} — ${c.brand || ''} ${c.model || ''}`)).join('\n');
            summary = `⚠️ وجدت أكثر من ${entAr} مطابق — أيّهم تقصد؟\n${lines}\n\nحدّد بالاسم الكامل أو رقم الجوال/اللوحة.`;
          }
        }
      } else if (d.status === 'awaiting_confirmation') {
        summary = d.confirm_text || '📋 بانتظار تأكيدك — رد بـ «نعم» للتنفيذ أو «لا» للإلغاء.';
      } else if (d.status === 'pending_approval') {
        summary = `⏳ **بانتظار اعتمادك** — العملية حساسة (${action}).`;
        try {
          window.dispatchEvent(new CustomEvent('runtime:changed', {
            detail: { source: 'assistant', action, status: 'pending_approval', approval_id: d.approval?.approval_id },
          }));
        } catch (e) { /* noop */ }
        cards = [{
          type: 'ApprovalCard',
          id: d.approval?.approval_id,
          title: `موافقة — ${action}`,
          status: 'pending',
          data: { approval_id: d.approval?.approval_id, draft_id: d.draft?.id, status: 'pending', requester: proposer },
          actions: [
            { id: 'approve', label: '✓ اعتماد', intent: 'runtime',
              endpoint: `/api/runtime/approvals/${d.approval?.approval_id}/approve`, method: 'POST',
              requiresDeveloperCode: d.draft?.proposer === proposer && ['admin', 'manager', 'system_manager'].includes(String(JSON.parse(localStorage.getItem('user') || '{}')?.role || '').toLowerCase()) },
            { id: 'reject', label: '✗ رفض', intent: 'runtime',
              endpoint: `/api/runtime/approvals/${d.approval?.approval_id}/reject`, method: 'POST' },
          ],
        }];
      } else if (d.status === 'read_only') {
        const n = Array.isArray(d.result) ? d.result.length : 0;
        summary = `🔎 **${n} نتيجة** للاستعلام.`;
      } else {
        summary = `⚠️ ${d.reason || 'تعذّر تنفيذ هذا الطلب'}`;
      }
      setMessages((prev) => [...prev, {
        role: 'assistant', content: summary, ts: Date.now() / 1000,
        meta: { cards, status: d.status, action, execution_id: d.execution_id },
      }]);
      _maybeSpeak(summary);
      window.dispatchEvent(new CustomEvent('assistant:executed', { detail: { ...d, text } }));
      return data;
    } catch (e) {
      // Defensive: if the runtime still answered 422 (older deploy) or any
      // "rejected" payload slipped through, answer via the chat path so the
      // user never sees a raw HTTP error for normal conversational text.
      const httpStatus = e?.response?.status;
      const rejected = httpStatus === 422 || e?.response?.data?.data?.status === 'rejected';
      if (rejected) {
        return await _answerViaChat(text);
      }
      console.error('execute error:', e);
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: `⚠️ تعذّر التنفيذ مؤقتاً. حاول مرة أخرى أو صِغ الطلب بشكل أوضح.`,
        ts: Date.now() / 1000, meta: { error: true },
      }]);
      return null;
    } finally {
      setBusy(false);
      setStreamingPhase(null);
    }
  }, [sessionId, _maybeSpeak, _answerViaChat]);

  const sendMessage = useCallback(async (text, { forceAgent = null, useAi = true, stream = false, force = null } = {}) => {
    const trimmed = (text || '').trim();
    if (!trimmed || busy) return null;

    // 🆕 Auto-route action verbs to /execute (unless force='chat').
    // /power multi-intent MUST stay on the chat path (the power_mode handler
    // lives there) — never send it to the single-intent /runtime/execute.
    const _isPower = trimmed.startsWith('/power');
    if (force !== 'chat' && !_isPower && _looksLikeAction(trimmed)) {
      return _executeDirectly(trimmed);
    }

    // optimistic user message
    const userMsg = { role: 'user', content: trimmed, ts: Date.now() / 1000 };
    setMessages((prev) => [...prev, userMsg]);
    setBusy(true);
    setStreamingPhase('يفكّر…');
    try {
      let data = null;
      if (stream && typeof fetch !== 'undefined') {
        // ----- SSE path -----
        // 🆕 Phase 3C — include the logged-in user as `proposer` so the
        // Action Runtime can enforce Four-Eyes against the right identity.
        let proposer = null;
        try {
          const u = JSON.parse(localStorage.getItem('user') || 'null');
          proposer = u?.name || u?.username || null;
        } catch (e) { /* noop */ }

        const resp = await fetch(`${API_URL}/assistant/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: trimmed,
            session_id: sessionId || undefined,
            workshop_id: WORKSHOP_ID,
            force_agent: forceAgent || undefined,
            use_ai: useAi,
            model: model || 'sonnet',
            proposer,
            daily_summary: localStorage.getItem('assistant_daily_summary') !== 'off',
          }),
        });
        // 🆕 Phase 3C.10 — robust SSE reader. We must verify `resp.ok` BEFORE
        // attempting to read the body, otherwise an early failure (e.g. an
        // OPTIONS preflight quirk or 4xx) leaves the body in a "disturbed
        // or locked" state when the catch block later tries to read it again.
        if (!resp.ok) {
          let errBody = '';
          try { errBody = await resp.text(); } catch (e) { /* ignore */ }
          throw new Error(`stream HTTP ${resp.status}: ${errBody.slice(0, 120)}`);
        }
        if (!resp.body) {
          throw new Error('stream: missing response body');
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let jobId = null;
        try {
          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            // SSE messages are separated by blank lines
            const parts = buffer.split('\n\n');
            buffer = parts.pop() || '';
            for (const block of parts) {
              const evMatch = block.match(/^event:\s*(\w+)/m);
              const dataMatch = block.match(/^data:\s*(.*)$/m);
              if (!evMatch || !dataMatch) continue;
              const event = evMatch[1];
              let payload = null;
              try { payload = JSON.parse(dataMatch[1]); } catch (e) { /* keep null */ }
              if (event === 'job' && payload?.job_id) {
                jobId = payload.job_id;
              } else if (event === 'progress' && payload?.label) {
                setStreamingPhase(payload.label);
              } else if (event === 'done') {
                data = payload;
              } else if (event === 'error') {
                throw new Error(payload?.error || 'stream_error');
              }
            }
          }
        } finally {
          // Always release the reader so the connection cleans up gracefully
          // and we never trigger "Body disturbed or locked" on retry.
          try { reader.releaseLock(); } catch (e) { /* ignore */ }
        }
        // 💓 حد الـ ingress يقطع البث عند 60s — النتيجة تُستكمل في الخادم
        // ونستردها بالاستطلاع عبر job_id (ردود وضع المطور الطويلة).
        if (!data && jobId) {
          setStreamingPhase('الرد طويل — جارٍ استكماله…');
          const t0 = Date.now();
          while (!data && Date.now() - t0 < 180000) {
            await new Promise((r) => setTimeout(r, 3000));
            try {
              const jr = await axios.get(`${API_URL}/assistant/chat/result/${jobId}`);
              if (jr.data?.status === 'done') {
                data = jr.data.result;
              } else if (jr.data?.status === 'error') {
                throw Object.assign(new Error(jr.data?.error || 'assistant_failed'), { _final: true });
              }
            } catch (e) {
              if (e?._final) throw e;
              // خطأ شبكة عابر → نواصل الاستطلاع
            }
          }
        }
        if (!data) throw new Error('stream ended without done event');
      } else {
        // ----- Non-streaming fallback -----
        let proposer = null;
        try {
          const u = JSON.parse(localStorage.getItem('user') || 'null');
          proposer = u?.name || u?.username || null;
        } catch (e) { /* noop */ }
        const res = await postChatWithRetry(`${API_URL}/assistant/chat`, {
          message: trimmed,
          session_id: sessionId || undefined,
          workshop_id: WORKSHOP_ID,
          force_agent: forceAgent || undefined,
          use_ai: useAi,
          model: model || 'sonnet',
          proposer,
          daily_summary: localStorage.getItem('assistant_daily_summary') !== 'off',
        }, { timeout: 120000 });
        if (!res.data?.success) {
          throw new Error(res.data?.error || 'assistant_failed');
        }
        data = res.data.data;
      }

      if (data.session_id && data.session_id !== sessionId) {
        // skip the session-reload effect to prevent overwriting optimistic state
        skipNextSessionReloadRef.current = true;
        setSessionId(data.session_id);
      }
      setActiveAgent(data.agent);

      const assistantMsg = {
        role: 'assistant',
        content: data.response,
        meta: { agent: data.agent, tool_results: data.tool_results, ai_used: data.ai_used, model_used: data.model_used, cards: data.cards || [] },
        ts: Date.now() / 1000,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      // 🆕 Reactive binding: if the kernel executed a write via /chat, refresh pages.
      _dispatchRefreshEvents(data.executed);
      _maybeSpeak(data.response);
      return data;
    } catch (e) {
      const errMsg = {
        role: 'assistant',
        content: friendlyChatError(e),
        meta: { error: true },
        ts: Date.now() / 1000,
      };
      setMessages((prev) => [...prev, errMsg]);
      return null;
    } finally {
      setBusy(false);
      setStreamingPhase(null);
    }
  }, [busy, sessionId, model, _maybeSpeak]);

  // 🆕 Fetch available models on mount + retry once after 2s in case of race
  const fetchModels = useCallback(async () => {
    if (!hasAuthToken()) return;
    try {
      const res = await axios.get(`${API_URL}/assistant/models`);
      if (res.data?.success) {
        setAvailableModels(res.data.data?.models || []);
      }
    } catch (e) { /* noop */ }
  }, []);

  useEffect(() => {
    fetchModels();
    const t = setTimeout(fetchModels, 2500);  // retry once
    return () => clearTimeout(t);
  }, [fetchModels]);

  const callTool = useCallback(async (toolName, args = {}) => {
    try {
      const res = await axios.post(`${API_URL}/assistant/tool/${toolName}`, { ...args, workshop_id: WORKSHOP_ID });
      return res.data;
    } catch (e) {
      return { success: false, error: e.message };
    }
  }, []);

  const resetSession = useCallback(() => {
    try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* noop */ }
    initialSessionLoadedRef.current = false;
    skipNextSessionReloadRef.current = false;
    setSessionId('');
    setMessages([]);
    setActiveAgent(null);
  }, []);

  // 🆕 Phase 3C.5 — direct message injection (used by 🚀 Execute path)
  const appendMessage = useCallback((msg) => {
    if (!msg || !msg.role) return;
    const content = msg.content || msg.text || '';
    if (!content && !msg.cards) return;
    setMessages((prev) => [...prev, {
      id: `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      ts: Date.now() / 1000,
      role: msg.role,
      content,
      meta: { ...(msg.meta || {}), cards: msg.cards || msg.meta?.cards },
    }]);
  }, []);

  // ----- public value -----
  const value = useMemo(() => ({
    open, setOpen,
    sessionId, setSessionId,
    messages, busy,
    streamingPhase,  // 🆕 'thinking' | 'يفهم سؤالك…' | etc — for granular UI
    activeAgent,
    alerts, stats,
    model, setModel, availableModels,
    voice, voiceEnabled, setVoiceEnabled,  // 🎙️ voice (STT/TTS)
    sendMessage,
    callTool,
    refreshAlerts,
    refreshStats,
    resetSession,
    appendMessage,  // 🆕 direct UI inject (no LLM call)
  }), [open, sessionId, messages, busy, streamingPhase, activeAgent, alerts, stats, model, setModel, availableModels, voice, voiceEnabled, setVoiceEnabled, sendMessage, callTool, refreshAlerts, refreshStats, resetSession, appendMessage]);

  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
};

export const useAssistant = () => {
  const ctx = useContext(AssistantContext);
  if (!ctx) {
    return {
      open: false, setOpen: () => {},
      sessionId: '', setSessionId: () => {},
      messages: [], busy: false, activeAgent: null,
      streamingPhase: null,
      alerts: [], stats: null,
      model: 'sonnet', setModel: () => {}, availableModels: [],
      voice: { listening: false, speaking: false, interim: '', supported: { stt: false, tts: false }, startListening: () => false, stopListening: () => {}, speak: () => {}, stopSpeaking: () => {} },
      voiceEnabled: false, setVoiceEnabled: () => {},
      sendMessage: async () => null,
      callTool: async () => ({ success: false }),
      refreshAlerts: async () => {},
      refreshStats: async () => {},
      resetSession: () => {},
    };
  }
  return ctx;
};

export default AssistantProvider;
