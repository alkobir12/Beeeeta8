/**
 * JWT Authentication helper — preserves name-only login UX.
 *
 * Backend issues a 30-day token after a simple username submission.
 * Frontend stores it in localStorage + attaches it to every axios request
 * via global interceptor (set up in App.js).
 */

const BACKEND = process.env.REACT_APP_BACKEND_URL || '';
const TOKEN_KEY = 'auth_token';

/** Call POST /api/auth/login with username, store returned JWT. */
export async function loginAndIssueToken(username) {
  try {
    const resp = await fetch(`${BACKEND}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include', // keep httpOnly cookie too
      body: JSON.stringify({ username }),
    });
    if (!resp.ok) {
      console.warn('JWT login failed:', resp.status);
      return null;
    }
    const data = await resp.json();
    const token = data?.access_token;
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
      return token;
    }
    return null;
  } catch (e) {
    console.warn('JWT login error:', e);
    return null;
  }
}

export function getStoredToken() {
  try { return localStorage.getItem(TOKEN_KEY) || ''; }
  catch (e) {
    console.warn('getStoredToken failed:', e);
    return '';
  }
}

export function clearStoredToken() {
  try { localStorage.removeItem(TOKEN_KEY); } catch (e) { console.warn('clearStoredToken failed:', e); }
}

/** Install global axios + fetch interceptors that attach Bearer header. */
export function installAuthInterceptors(axios) {
  if (!axios || axios.__authInstalled) return;
  axios.__authInstalled = true;
  // axios interceptor
  axios.interceptors.request.use(
    (cfg) => {
      const t = getStoredToken();
      if (t) {
        cfg.headers = cfg.headers || {};
        if (!cfg.headers.Authorization) cfg.headers.Authorization = `Bearer ${t}`;
      }
      return cfg;
    },
    (err) => Promise.reject(err)
  );
  // optional: react to 401 globally — clear token (forces re-login)
  axios.interceptors.response.use(
    (res) => res,
    (err) => {
      if (err?.response?.status === 401) {
        clearStoredToken();
      }
      return Promise.reject(err);
    }
  );

  // Patch global fetch to attach the same header automatically
  if (typeof window !== 'undefined' && window.fetch && !window.fetch.__authPatched) {
    const origFetch = window.fetch.bind(window);
    const patched = function (input, init = {}) {
      const t = getStoredToken();
      const headers = new Headers(init.headers || (typeof input !== 'string' && input?.headers) || {});
      if (t && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${t}`);
      }
      return origFetch(input, { ...init, headers });
    };
    patched.__authPatched = true;
    window.fetch = patched;
  }
}
