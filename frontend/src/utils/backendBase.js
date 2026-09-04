export const resolveBackendBase = () => {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return '';
  }
  const raw =
    (typeof process !== 'undefined' && process.env && process.env.REACT_APP_BACKEND_URL) || '';
  if (raw && /^https?:\/\//i.test(raw)) {
    return raw.replace(/\/$/, '');
  }
  return '';
};

export const API_BASE = `${resolveBackendBase()}/api`;