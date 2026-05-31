/**
 * 📜 useRecentPages — Track the user's last visited routes
 *
 * Stores the last N visited paths (with a friendly label) in localStorage so
 * the sidebar can render a "Recent Pages" section at the top.
 *
 * • Skips ignored paths (login, root, errors).
 * • Deduplicates consecutive visits to the same path.
 * • Adds a friendly Arabic label heuristically from the path segments
 *   (callers can override via setRecentPageLabel).
 */

import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

const LS_KEY = 'recentPages.v1';
const MAX_PAGES = 5;
const IGNORED_PATHS = new Set(['/', '/login', '/logout', '/auth', '/error']);

const PATH_LABELS = {
  '/dashboard': '🏠 الرئيسية',
  '/operations': '🔄 العمليات',
  '/customers': '👥 العملاء',
  '/vehicles': '🚗 المركبات',
  '/parts': '📦 قطع الغيار',
  '/parts-inventory': '📦 قطع الغيار',
  '/parts-dashboard': '📊 لوحة القطع',
  '/services': '🔧 الخدمات',
  '/technicians': '🧑‍🔧 الفنيون',
  '/business-accounts': '🏢 الفروع',
  '/accounting/journal-entries': '📖 دفتر اليومية',
  '/accounting/firewall': '🛡️ جدار الحماية',
  '/accounting/comprehensive': '💎 المؤشرات المالية',
  '/ai-financial': '🛡️ مركز جدار حماية المحاسبة',
  '/invoice-templates': '🧾 قوالب الفواتير',
  '/analytics': '📈 التحليلات',
  '/settings': '⚙️ الإعدادات',
  '/audit': '🔍 التدقيق',
};

const friendlyLabel = (pathname) => {
  if (!pathname) return '';
  // Exact match
  if (PATH_LABELS[pathname]) return PATH_LABELS[pathname];
  // Try first segment matching
  const seg = pathname.split('/').filter(Boolean)[0];
  const exact = Object.keys(PATH_LABELS).find((k) => k === `/${seg}`);
  if (exact) return PATH_LABELS[exact];
  // Fallback: capitalize last segment
  const parts = pathname.split('/').filter(Boolean);
  return parts.length ? `📄 ${parts[parts.length - 1]}` : '';
};

const isSafeRecentPage = (page) => {
  const text = `${page?.path || ''} ${page?.label || ''}`;
  return !/DOM-CHECK|page-description|\[VISIT:|\[IDEMP:/i.test(text);
};

export const readRecentPages = () => {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter(isSafeRecentPage).slice(0, MAX_PAGES) : [];
  } catch (e) {
    return [];
  }
};

const writeRecentPages = (list) => {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(list.slice(0, MAX_PAGES)));
    // Notify listeners (Sidebar) of changes
    window.dispatchEvent(new CustomEvent('recentpages:update'));
  } catch (e) {
    /* noop */
  }
};

export const useRecentPagesTracker = () => {
  const location = useLocation();
  useEffect(() => {
    const path = location.pathname;
    if (!path || IGNORED_PATHS.has(path)) return;
    const label = friendlyLabel(path);
    if (!label) return;
    const existing = readRecentPages();
    // Dedupe: move existing to top, otherwise prepend
    const filtered = existing.filter((p) => p.path !== path);
    const next = [{ path, label, ts: Date.now() }, ...filtered].filter(isSafeRecentPage).slice(0, MAX_PAGES);
    writeRecentPages(next);
  }, [location.pathname]);
};

export const clearRecentPages = () => {
  try {
    localStorage.removeItem(LS_KEY);
    window.dispatchEvent(new CustomEvent('recentpages:update'));
  } catch (e) {
    /* noop */
  }
};
