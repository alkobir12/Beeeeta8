/**
 * JWT Authentication helper — httpOnly-cookie-first (XSS hardening).
 *
 * Tokens are NEVER persisted in localStorage. The access token lives in
 * module memory only; the authoritative copies are httpOnly cookies set by
 * the backend (access_token + refresh_token). A non-sensitive marker
 * ('auth_session'='1') tells the app a session likely exists after reload.
 */

const BACKEND = process.env.REACT_APP_BACKEND_URL || '';
const SESSION_MARKER = 'auth_session';
const LEGACY_TOKEN_KEY = 'auth_token';
const LEGACY_REFRESH_KEY = 'refresh_token';

let _accessToken = '';

function _isBackendUrl(url) {
  const u = String(url || '');
  return u.startsWith('/') || (BACKEND && u.startsWith(BACKEND));
}

function _setMarker(on) {
  try {
    if (on) localStorage.setItem(SESSION_MARKER, '1');
    else localStorage.removeItem(SESSION_MARKER);
  } catch (e) { /* noop */ }
}

/** Purge any legacy localStorage tokens (pre-hardening sessions). */
function _purgeLegacyTokens() {
  try {
    const hadLegacy = Boolean(localStorage.getItem(LEGACY_TOKEN_KEY) || localStorage.getItem(LEGACY_REFRESH_KEY));
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    localStorage.removeItem(LEGACY_REFRESH_KEY);
    localStorage.removeItem('token');
    if (hadLegacy) _setMarker(true);
  } catch (e) { /* noop */ }
}

/** True if a session likely exists (in-memory token or marker from a prior login). */
export function hasAuthSession() {
  if (_accessToken) return true;
  try { return localStorage.getItem(SESSION_MARKER) === '1'; } catch { return false; }
}

/** Call POST /api/auth/login with username, keep returned JWT in memory. */
export async function loginAndIssueToken(username) {
  const res = await loginRequest({ username });
  return res.ok ? res.data?.access_token || null : null;
}

/** Keep the issued access token in memory only + set the session marker. */
export function storeTokens(data) {
  const token = data?.access_token;
  if (!token) return null;
  _accessToken = token;
  _setMarker(true);
  _purgeLegacyTokens();
  _loggingOut = false;
  return token;
}

/** P1 multi-method login: body may carry {username|email, password, pin, device_id, remember_device}.
 *  Returns {ok, status, data, detail}. Keeps the access token in memory on success. */
export async function loginRequest(body) {
  const performLogin = async (withCredentials = true) => fetch(`${BACKEND}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: withCredentials ? 'include' : 'omit',
    body: JSON.stringify(body || {}),
  });
  try {
    let resp = await performLogin(true);
    if (resp.status === 0 || resp.type === 'opaque') {
      resp = await performLogin(false);
    }
    let data = null;
    try { data = await resp.json(); }
    catch (e) {
      console.warn('Login response was not valid JSON:', e?.message || e);
      data = null;
    }
    if (!resp.ok) {
      return {
        ok: false,
        status: resp.status,
        data,
        detail: data?.detail || data?.error || '',
      };
    }
    storeTokens(data);
    return { ok: true, status: resp.status, data, detail: '' };
  } catch (e) {
    try {
      const resp = await performLogin(false);
      let data = null;
      try { data = await resp.json(); } catch (_) { data = null; }
      if (resp.ok) {
        storeTokens(data);
        return { ok: true, status: resp.status, data, detail: '' };
      }
      return { ok: false, status: resp.status, data, detail: data?.detail || data?.error || 'network_error' };
    } catch (fallbackError) {
      console.warn('login request error:', e, fallbackError);
      return { ok: false, status: 0, data: null, detail: 'network_error' };
    }
  }
}

/** In-memory access token (may be '' right after reload — cookies still authenticate). */
export function getStoredToken() {
  return _accessToken || '';
}

export function clearStoredToken() {
  _accessToken = '';
  try {
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    localStorage.removeItem(LEGACY_REFRESH_KEY);
    localStorage.removeItem('token');
  } catch (e) { /* noop */ }
  _setMarker(false);
}

let _refreshPromise = null;
let _loggingOut = false;
const AUTH_PATHS = ['/api/auth/login', '/api/auth/refresh', '/api/auth/logout'];

function _isAuthPath(url) {
  try { return AUTH_PATHS.some((p) => String(url || '').includes(p)); }
  catch (e) {
    console.warn('Auth path detection failed:', e?.message || e);
    return false;
  }
}

/** Orderly logout when refresh is impossible — clear session, notify app, redirect once.
 *  Prevents the "401 → refresh-fail → repeat" cascade/loop the owner reported. */
function _orderlyLogout() {
  if (_loggingOut) return;
  _loggingOut = true;
  clearStoredToken();
  try { window.dispatchEvent(new CustomEvent('auth:session-expired')); }
  catch (e) { console.warn('Session expiry event dispatch failed:', e?.message || e); }
  try {
    const path = window.location?.pathname || '';
    if (!path.startsWith('/login')) {
      // give listeners a tick, then hard-redirect to a clean login
      setTimeout(() => { window.location.assign('/login'); }, 50);
    }
  } catch (e) { console.warn('Orderly logout redirect failed:', e?.message || e); }
}

/** Mint a fresh access token via the httpOnly refresh cookie (single-flight).
 *  Concurrent callers await the same in-flight promise, then replay their requests. */
export async function refreshAccessToken() {
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = (async () => {
    try {
      const resp = await fetch(`${BACKEND}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      });
      if (!resp.ok) return null;
      const data = await resp.json();
      const token = data?.access_token;
      if (token) {
        _accessToken = token;
        _setMarker(true);
        _loggingOut = false; // a successful refresh clears the logout latch
        return token;
      }
      return null;
    } catch (e) {
      console.warn('Access token refresh failed:', e?.message || e);
      return null;
    } finally {
      setTimeout(() => { _refreshPromise = null; }, 0);
    }
  })();
  return _refreshPromise;
}

/** Install global axios + fetch interceptors: cookies-first auth + auto-refresh on 401. */
export function installAuthInterceptors(axios) {
  if (!axios || axios.__authInstalled) return;
  axios.__authInstalled = true;
  _purgeLegacyTokens();
  // send httpOnly cookies with every axios request (same-origin backend)
  axios.defaults.withCredentials = true;
  // axios request: attach in-memory Bearer when available (cookies cover the rest)
  axios.interceptors.request.use(
    (cfg) => {
      const t = getStoredToken();
      cfg.__hadAuthToken = Boolean(t);
      if (t) {
        cfg.headers = cfg.headers || {};
        if (!cfg.headers.Authorization) cfg.headers.Authorization = `Bearer ${t}`;
      }
      return cfg;
    },
    (err) => Promise.reject(err)
  );
  // axios response: on 401, try one silent refresh then retry the request
  axios.interceptors.response.use(
    (res) => res,
    async (err) => {
      const cfg = err?.config || {};
      const status = err?.response?.status;
      const hadAuthContext = Boolean(cfg.__hadAuthToken || hasAuthSession());
      if (status === 401 && !cfg.__isRetry && !_isAuthPath(cfg.url) && hadAuthContext) {
        const newToken = await refreshAccessToken();
        if (newToken) {
          cfg.__isRetry = true;
          cfg.headers = cfg.headers || {};
          cfg.headers.Authorization = `Bearer ${newToken}`;
          return axios(cfg);
        }
        _orderlyLogout();
      }
      return Promise.reject(err);
    }
  );

  // Patch global fetch: include cookies for backend calls + auto-refresh on 401
  if (typeof window !== 'undefined' && window.fetch && !window.fetch.__authPatched) {
    const origFetch = window.fetch.bind(window);
    const patched = async function (input, init = {}) {
      const t = getStoredToken();
      const hadAuthContext = Boolean(t || hasAuthSession());
      const headers = new Headers(init.headers || (typeof input !== 'string' && input?.headers) || {});
      if (t && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${t}`);
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      const sendCookies = _isBackendUrl(url) && !init.credentials;
      const baseInit = sendCookies ? { ...init, credentials: 'include' } : init;
      let resp = await origFetch(input, { ...baseInit, headers });
      if (resp.status === 401 && !init.__isRetry && !_isAuthPath(url) && hadAuthContext) {
        const newToken = await refreshAccessToken();
        if (newToken) {
          headers.set('Authorization', `Bearer ${newToken}`);
          resp = await origFetch(input, { ...baseInit, headers, __isRetry: true });
        } else {
          _orderlyLogout();
        }
      }
      return resp;
    };
    patched.__authPatched = true;
    window.fetch = patched;
  }
}
