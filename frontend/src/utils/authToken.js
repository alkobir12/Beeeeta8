/**
 * JWT Authentication helper — preserves name-only login UX.
 *
 * Backend issues a 30-day token after a simple username submission.
 * Frontend stores it in localStorage + attaches it to every axios request
 * via global interceptor (set up in App.js).
 */

const BACKEND = process.env.REACT_APP_BACKEND_URL || '';
const TOKEN_KEY = 'auth_token';
const REFRESH_KEY = 'refresh_token';

/** Call POST /api/auth/login with username, store returned JWT. */
export async function loginAndIssueToken(username) {
  const res = await loginRequest({ username });
  return res.ok ? res.data?.access_token || null : null;
}

/** Persist issued tokens (access + refresh) and reset the logout latch. */
export function storeTokens(data) {
  const token = data?.access_token;
  if (!token) return null;
  localStorage.setItem(TOKEN_KEY, token);
  if (data?.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
  _loggingOut = false;
  return token;
}

/** P1 multi-method login: body may carry {username|email, password, pin, device_id, remember_device}.
 *  Returns {ok, status, data, detail}. Stores tokens on success. */
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

export function getStoredToken() {
  try { return localStorage.getItem(TOKEN_KEY) || ''; }
  catch (e) {
    console.warn('getStoredToken failed:', e);
    return '';
  }
}

function getStoredRefresh() {
  try { return localStorage.getItem(REFRESH_KEY) || ''; }
  catch (e) {
    console.warn('getStoredRefresh failed:', e?.message || e);
    return '';
  }
}

export function clearStoredToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  } catch (e) { console.warn('clearStoredToken failed:', e); }
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

/** Orderly logout when refresh is impossible — clear tokens, notify app, redirect once.
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

/** Mint a fresh access token (single-flight). Uses the httpOnly refresh cookie AND,
 *  as a fallback for cookie-blocked contexts (cross-site iframe / Safari ITP), the
 *  stored refresh token via Authorization: Bearer. Concurrent callers await the same
 *  in-flight promise (request queue), then each replays its own request. */
export async function refreshAccessToken() {
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = (async () => {
    try {
      const headers = { 'Content-Type': 'application/json' };
      const storedRefresh = getStoredRefresh();
      if (storedRefresh) headers.Authorization = `Bearer ${storedRefresh}`;
      const resp = await fetch(`${BACKEND}/api/auth/refresh`, {
        method: 'POST',
        headers,
        credentials: 'include',
      });
      if (!resp.ok) return null;
      const data = await resp.json();
      const token = data?.access_token;
      if (token) {
        localStorage.setItem(TOKEN_KEY, token);
        if (data?.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
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

/** Install global axios + fetch interceptors that attach Bearer header + auto-refresh. */
export function installAuthInterceptors(axios) {
  if (!axios || axios.__authInstalled) return;
  axios.__authInstalled = true;
  // axios request: attach Bearer
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
      const hadAuthContext = Boolean(cfg.__hadAuthToken || getStoredRefresh());
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

  // Patch global fetch to attach the header + auto-refresh on 401
  if (typeof window !== 'undefined' && window.fetch && !window.fetch.__authPatched) {
    const origFetch = window.fetch.bind(window);
    const patched = async function (input, init = {}) {
      const t = getStoredToken();
      const hadAuthContext = Boolean(t || getStoredRefresh());
      const headers = new Headers(init.headers || (typeof input !== 'string' && input?.headers) || {});
      if (t && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${t}`);
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      let resp = await origFetch(input, { ...init, headers });
      if (resp.status === 401 && !init.__isRetry && !_isAuthPath(url) && hadAuthContext) {
        const newToken = await refreshAccessToken();
        if (newToken) {
          headers.set('Authorization', `Bearer ${newToken}`);
          resp = await origFetch(input, { ...init, headers, __isRetry: true });
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
