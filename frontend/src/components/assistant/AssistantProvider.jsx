import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { resolveBackendBase } from '../../utils/backendBase';

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

const AssistantContext = createContext(null);

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
    const now = Date.now();
    if (!force && now - lastFetchRef.current < 8000) return; // dedupe within 8s
    lastFetchRef.current = now;
    try {
      const res = await axios.get(`${API_URL}/assistant/alerts`, { params: { limit: 20 } });
      if (res.data?.success) setAlerts(res.data.data || []);
    } catch (e) { /* silent */ }
  }, []);

  const refreshStats = useCallback(async () => {
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

  // ----- core: send a message -----
  const sendMessage = useCallback(async (text, { forceAgent = null, useAi = true } = {}) => {
    const trimmed = (text || '').trim();
    if (!trimmed || busy) return null;

    // optimistic user message
    const userMsg = { role: 'user', content: trimmed, ts: Date.now() / 1000 };
    setMessages((prev) => [...prev, userMsg]);
    setBusy(true);
    try {
      const res = await axios.post(`${API_URL}/assistant/chat`, {
        message: trimmed,
        session_id: sessionId || undefined,
        workshop_id: WORKSHOP_ID,
        force_agent: forceAgent || undefined,
        use_ai: useAi,
      }, { timeout: 60000 });

      if (!res.data?.success) {
        throw new Error(res.data?.error || 'assistant_failed');
      }

      const data = res.data.data;
      if (data.session_id && data.session_id !== sessionId) {
        // skip the session-reload effect to prevent overwriting optimistic state
        skipNextSessionReloadRef.current = true;
        setSessionId(data.session_id);
      }
      setActiveAgent(data.agent);

      const assistantMsg = {
        role: 'assistant',
        content: data.response,
        meta: { agent: data.agent, tool_results: data.tool_results, ai_used: data.ai_used },
        ts: Date.now() / 1000,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      return data;
    } catch (e) {
      const errMsg = {
        role: 'assistant',
        content: `⚠️ تعذّر الاتصال بالمساعد: ${e.message || 'unknown'}`,
        meta: { error: true },
        ts: Date.now() / 1000,
      };
      setMessages((prev) => [...prev, errMsg]);
      return null;
    } finally {
      setBusy(false);
    }
  }, [busy, sessionId]);

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

  // ----- public value -----
  const value = useMemo(() => ({
    open, setOpen,
    sessionId, setSessionId,
    messages, busy,
    activeAgent,
    alerts, stats,
    sendMessage,
    callTool,
    refreshAlerts,
    refreshStats,
    resetSession,
  }), [open, sessionId, messages, busy, activeAgent, alerts, stats, sendMessage, callTool, refreshAlerts, refreshStats, resetSession]);

  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
};

export const useAssistant = () => {
  const ctx = useContext(AssistantContext);
  if (!ctx) {
    // Fallback safe shape — لو استُخدم خارج Provider
    return {
      open: false, setOpen: () => {},
      sessionId: '', setSessionId: () => {},
      messages: [], busy: false, activeAgent: null,
      alerts: [], stats: null,
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
