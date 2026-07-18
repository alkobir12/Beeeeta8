/** Shared post-login session bootstrap (used by Login + Google AuthCallback). */
import { normalizePermissions } from './permissions';
import { resolveBackendBase } from './backendBase';

export async function establishSession({ username, role, token }) {
  let user = null;
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const resp = await fetch(`${resolveBackendBase()}/api/users`, {
      signal: controller.signal,
      headers: { Authorization: `Bearer ${token}` },
    });
    clearTimeout(timeout);
    if (resp.ok) {
      const users = await resp.json();
      const ln = String(username || '').trim().toLowerCase();
      user = (Array.isArray(users) ? users : []).find((u) => [u.username, u.name, u.phone]
        .filter(Boolean)
        .some((v) => String(v).trim().toLowerCase() === ln)) || null;
    }
  } catch (e) {
    console.warn('Session user lookup failed; using token-derived session:', e?.message || e);
  }
  const resolvedRole = user?.role || role || 'technician';
  const appUser = user
    ? { ...user, permissions: normalizePermissions(user.permissions, user.role) }
    : {
        id: `jwt-${username}`,
        name: username,
        phone: '',
        email: '',
        role: resolvedRole,
        permissions: normalizePermissions(null, resolvedRole),
        isActive: true,
        guidanceEnabled: true,
      };
  const session = {
    id: appUser.id,
    name: appUser.name,
    phone: appUser.phone || '',
    email: appUser.email || '',
    role: appUser.role,
    permissions: appUser.permissions,
    guidanceEnabled: appUser.guidanceEnabled !== false,
    loginTime: new Date().toISOString(),
  };
  localStorage.setItem('session', JSON.stringify(session));
  localStorage.setItem('user', JSON.stringify(appUser));
  try {
    document.cookie = 'session=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
    document.cookie = `session=${encodeURIComponent(JSON.stringify(session))}; path=/`;
  } catch (e) {
    console.warn('Session compatibility cookie could not be written:', e?.message || e);
  }
  window.dispatchEvent(new Event('sessionUpdated'));
  return session;
}
