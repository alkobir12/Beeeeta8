/** Google SSO callback — exchanges the Emergent session_id for an app JWT.
 * REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
 */
import React, { useEffect, useRef, useState } from 'react';
import { resolveBackendBase } from '../utils/backendBase';
import { storeTokens } from '../utils/authToken';
import { establishSession } from '../utils/sessionSetup';

export default function AuthCallback() {
  const hasProcessed = useRef(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;
    (async () => {
      const hash = window.location.hash || '';
      const m = hash.match(/session_id=([^&]+)/);
      const sessionId = m ? decodeURIComponent(m[1]) : '';
      try {
        window.history.replaceState(null, '', window.location.pathname + window.location.search);
      } catch (e) { /* ignore */ }
      if (!sessionId) {
        window.location.replace('/login');
        return;
      }
      try {
        const resp = await fetch(`${resolveBackendBase()}/api/auth/google/session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ session_id: sessionId }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          setError(data?.detail || 'فشل تسجيل الدخول عبر Google');
          return;
        }
        storeTokens(data);
        await establishSession({ username: data.username, role: data.role, token: data.access_token });
        window.location.replace('/');
      } catch (e) {
        setError('تعذر الاتصال بالخادم');
      }
    })();
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4" data-testid="google-auth-callback">
      {error ? (
        <div className="apple-card p-10 max-w-[420px] w-full text-center space-y-4">
          <div className="text-4xl">⚠️</div>
          <h1 className="text-xl font-bold text-[#1D1D1F]" data-testid="google-auth-error">{error}</h1>
          <p className="text-sm text-[#86868B]">
            تأكد من ربط بريدك الإلكتروني بحسابك في النظام (صفحة المستخدمين) ثم حاول مجدداً.
          </p>
          <a href="/login" className="apple-button inline-block" data-testid="google-auth-back-to-login">
            العودة لتسجيل الدخول
          </a>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <span className="w-10 h-10 border-4 border-blue-200 border-t-[#0071E3] rounded-full animate-spin" />
          <p className="text-[#86868B]">جارٍ إتمام تسجيل الدخول عبر Google…</p>
        </div>
      )}
    </div>
  );
}
