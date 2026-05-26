import React, { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import Sidebar from './Sidebar';
import { Eye, EyeOff, Menu } from 'lucide-react';
import { Outlet, useLocation } from 'react-router-dom';
import AnimatedBackground from './AnimatedBackground';
import { useTranslation } from 'react-i18next';
import { AssistantProvider } from './assistant/AssistantProvider';
import UnifiedAssistantDrawer from './assistant/UnifiedAssistantDrawer';
import FinanceAlertsWidget from './FinanceAlertsWidget';
import { Toaster } from './ui/toaster';
import { hasRoutePermission, resolveRoutePermission } from '../utils/permissions';
import { siteBuilderAPI } from '../services/siteBuilderAPI';
import { PageCustomCardsDock } from './PageCustomCardsDock';
import { applyPageCustomizations, clearPageCustomizations } from '../utils/pageCustomization';
import { useRecentPagesTracker } from '../hooks/useRecentPages';
import { useTheme } from '../contexts/ThemeContext';



const Layout = ({ pageTitle }) => {
  useRecentPagesTracker();
  const { themeName } = useTheme();
  const isLightTheme = themeName === 'light' || themeName === 'dashPro';
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [pageCustomization, setPageCustomization] = useState({ custom_cards: [] });
  const appliedCustomizationsRef = useRef([]);
  const applyingCustomizationRef = useRef(false);
  const [isMobileViewport, setIsMobileViewport] = useState(() => window.innerWidth < 1024);
  const [desktopSidebarCollapsed, setDesktopSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem('ui.sidebarCollapsed') === 'true';
    } catch (error) {
      return false;
    }
  });
  const [desktopSidebarHidden, setDesktopSidebarHidden] = useState(() => {
    try {
      return localStorage.getItem('ui.sidebarHidden') === 'true';
    } catch (error) {
      return false;
    }
  });
  const { t } = useTranslation();
  const location = useLocation();
  const isEditorPreview = useMemo(() => new URLSearchParams(location.search).get('editor-preview') === '1', [location.search]);
  const isEditorWorkspace = isEditorPreview || location.pathname === '/moltbot';
  const customizationScopeId = useMemo(() => {
    const workshopId = String(process.env.REACT_APP_WORKSHOP_ID || '').trim();
    return workshopId ? `workshop:${workshopId}` : '';
  }, []);
  const readSession = () => {
    try {
      return JSON.parse(localStorage.getItem('session') || '{}');
    } catch (error) {
      return {};
    }
  };
  const [session, setSession] = useState(() => readSession());

  useEffect(() => {
    localStorage.setItem('ui.sidebarCollapsed', String(desktopSidebarCollapsed));
  }, [desktopSidebarCollapsed]);

  useEffect(() => {
    localStorage.setItem('ui.sidebarHidden', String(desktopSidebarHidden));
  }, [desktopSidebarHidden]);

  useEffect(() => {
    const handleResize = () => setIsMobileViewport(window.innerWidth < 1024);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    const sync = () => setSession(readSession());
    window.addEventListener('storage', sync);
    window.addEventListener('sessionUpdated', sync);
    return () => {
      window.removeEventListener('storage', sync);
      window.removeEventListener('sessionUpdated', sync);
    };
  }, []);

  useEffect(() => {
    const userId = customizationScopeId;
    if (!userId) return undefined;
    let cancelled = false;

    try {
      const localKey = `moltbot-published:${userId}:${location.pathname || '/'}`;
      const localRaw = window.localStorage.getItem(localKey);
      if (localRaw) {
        const localCustomization = JSON.parse(localRaw);
        if (localCustomization && typeof localCustomization === 'object') {
          setPageCustomization(localCustomization);
          window.__layoutCustomizationDebug = {
            ...localCustomization,
            __meta: { userId, path: location.pathname || '/', source: 'local-storage' },
          };
        }
      }
    } catch (_error) {
      // ignore local fallback parse errors
    }

    siteBuilderAPI.getCustomization({ user_id: userId, path: location.pathname || '/' })
      .then((response) => {
        if (cancelled) return;
        const nextCustomization = response.data?.data || { custom_cards: [] };
        setPageCustomization(nextCustomization);
        window.__layoutCustomizationDebug = { ...nextCustomization, __meta: { userId, path: location.pathname || '/', source: 'axios' } };
      })
      .catch(async () => {
        try {
          const params = new URLSearchParams({ user_id: userId, path: location.pathname || '/' });
          const fallbackRes = await fetch(`/api/alkabeer-bot/customization?${params.toString()}`);
          if (!fallbackRes.ok || cancelled) return;
          const fallbackJson = await fallbackRes.json();
          const fallbackCustomization = fallbackJson?.data || { custom_cards: [] };
          setPageCustomization(fallbackCustomization);
          window.__layoutCustomizationDebug = { ...fallbackCustomization, __meta: { userId, path: location.pathname || '/', source: 'fallback-catch' } };
        } catch (_error) {
          return;
        }
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname, session, isEditorWorkspace, customizationScopeId]);

  useEffect(() => {
    if (isEditorWorkspace) return undefined;
    const applyNow = () => {
      if (applyingCustomizationRef.current) return;
      applyingCustomizationRef.current = true;
      applyPageCustomizations(pageCustomization || {}, appliedCustomizationsRef);
      window.setTimeout(() => {
        applyingCustomizationRef.current = false;
      }, 0);
    };
    applyNow();
    const t1 = window.setTimeout(applyNow, 320);
    const t2 = window.setTimeout(applyNow, 1200);

    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, [pageCustomization, location.pathname, isEditorWorkspace]);

  useEffect(() => () => clearPageCustomizations(appliedCustomizationsRef), []);

  useEffect(() => {
    const handleCustomizationUpdate = (event) => {
      const detail = event?.detail;
      if (!detail) return;
      const pathFromEvent = typeof detail.path === 'string' ? detail.path : '';
      const customization = detail.customization || detail;
      if (pathFromEvent && pathFromEvent !== location.pathname) return;
      setPageCustomization(customization);
      if (!isEditorWorkspace) {
        applyPageCustomizations(customization, appliedCustomizationsRef);
      }
    };
    window.addEventListener('page-customization-updated', handleCustomizationUpdate);
    return () => window.removeEventListener('page-customization-updated', handleCustomizationUpdate);
  }, [location.pathname, isEditorWorkspace]);

  useEffect(() => {
    const handleSidebarPrefs = (event) => {
      const detail = event?.detail;
      if (detail && typeof detail === 'object') {
        if (typeof detail.collapsed === 'boolean') {
          setDesktopSidebarCollapsed(detail.collapsed);
        }
        if (typeof detail.hidden === 'boolean') {
          setDesktopSidebarHidden(detail.hidden);
        }
        return;
      }

      try {
        setDesktopSidebarCollapsed(localStorage.getItem('ui.sidebarCollapsed') === 'true');
        setDesktopSidebarHidden(localStorage.getItem('ui.sidebarHidden') === 'true');
      } catch (error) {
        return;
      }
    };

    window.addEventListener('ui-sidebar-preferences-changed', handleSidebarPrefs);
    return () => window.removeEventListener('ui-sidebar-preferences-changed', handleSidebarPrefs);
  }, []);

  const contentOffset = useMemo(() => {
    if (desktopSidebarHidden) return '0px';
    return desktopSidebarCollapsed ? '132px' : '322px';
  }, [desktopSidebarCollapsed, desktopSidebarHidden]);

  const toggleSidebarVisibility = () => {
    if (window.innerWidth < 1024) {
      setSidebarOpen((prev) => !prev);
      return;
    }
    setDesktopSidebarHidden((prev) => !prev);
  };

  const permissionRule = resolveRoutePermission(location.pathname);
  const canAccessRoute = hasRoutePermission(session, permissionRule);

  const UnauthorizedPanel = () => (
    <div className="mx-auto max-w-xl rounded-3xl border border-white/10 bg-slate-950/70 p-6 text-center shadow-xl shadow-black/20">
      <h2 className="text-lg font-bold text-white" data-testid="permission-denied-title">غير مصرح بالوصول</h2>
      <p className="mt-2 text-sm text-slate-300" data-testid="permission-denied-description">
        لا تملك الصلاحية لعرض هذه الصفحة. إذا كنت تعتقد أن هذا خطأ، تواصل مع مدير النظام.
      </p>
    </div>
  );

  return (
    <AssistantProvider>
    <div
      className="layout-main"
      style={{ backgroundColor: 'var(--bg-primary)', minHeight: '100vh', position: 'relative' }}
    >
      {/* Animated Background */}
      {process.env.NODE_ENV === 'production' ? null : <AnimatedBackground />}
      <div
        className="pointer-events-none"
        style={{
          position: 'absolute',
          inset: 0,
          background: isLightTheme
            ? 'radial-gradient(1200px circle at 20% 10%, rgba(37,99,235,0.08), transparent 45%), radial-gradient(900px circle at 80% 20%, rgba(14,165,233,0.06), transparent 50%)'
            : 'radial-gradient(1200px circle at 20% 10%, rgba(168,85,247,0.18), transparent 45%), radial-gradient(900px circle at 80% 20%, rgba(99,102,241,0.16), transparent 50%)',
          opacity: isLightTheme ? 0.75 : 0.9,
          zIndex: 1,
        }}
      />
      <div
        className={`pointer-events-none absolute -top-20 left-[18%] h-56 w-56 rounded-full blur-[90px] animate-pulse ${
          isLightTheme ? 'bg-cyan-500/10' : 'bg-cyan-400/12'
        }`}
      />
      <div
        className={`pointer-events-none absolute bottom-10 right-[12%] h-64 w-64 rounded-full blur-[110px] animate-pulse ${
          isLightTheme ? 'bg-sky-500/8' : 'bg-sky-500/10'
        }`}
      />
      
      {/* Sidebar */}
      {isEditorWorkspace ? null : (
        <Sidebar 
          isOpen={sidebarOpen} 
          onClose={() => setSidebarOpen(false)} 
          isCollapsed={desktopSidebarCollapsed}
          isHidden={desktopSidebarHidden}
        />
      )}

      {isEditorWorkspace ? null : <div className="fixed bottom-4 left-4 z-[70] lg:bottom-6 lg:left-6" data-testid="floating-sidebar-visibility-wrapper">
        <button
          type="button"
          onClick={toggleSidebarVisibility}
          className={`pointer-events-auto inline-flex h-11 w-11 items-center justify-center rounded-2xl border backdrop-blur-2xl transition-all ${
            isLightTheme
              ? 'border-slate-200 bg-white/95 text-slate-700 shadow-lg shadow-slate-300/25 hover:bg-slate-50'
              : 'border-white/10 bg-slate-950/85 text-slate-100 shadow-2xl shadow-black/35 hover:bg-white/12'
          }`}
          data-testid={desktopSidebarHidden ? 'floating-sidebar-show-button' : 'floating-sidebar-hide-button'}
          title={isMobileViewport ? 'القائمة' : desktopSidebarHidden ? 'إظهار القائمة' : 'إخفاء القائمة'}
          aria-label={isMobileViewport ? 'Toggle Menu' : desktopSidebarHidden ? 'Show Sidebar' : 'Hide Sidebar'}
        >
          {isMobileViewport ? <Menu size={18} /> : desktopSidebarHidden ? <Eye size={18} /> : <EyeOff size={18} />}
        </button>
      </div>}
      
      {/* Main Content */}
      <main className="content-area" style={{ backgroundColor: 'transparent', position: 'relative', zIndex: 10, '--content-offset': isEditorWorkspace ? '0px' : contentOffset }}>
        {/* Mobile Header - Fixed at top */}
        {isEditorWorkspace ? null : <div className={`lg:hidden sticky top-0 z-40 mt-8 mb-4 rounded-[20px] border px-4 py-3 backdrop-blur-xl ${
          isLightTheme
            ? 'border-slate-200 bg-white/95 shadow-lg shadow-slate-300/25'
            : 'border-white/10 bg-slate-950/88 shadow-xl shadow-black/25'
        }`}>
          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className={`inline-flex h-9 w-9 items-center justify-center rounded-2xl border transition-colors ${
                isLightTheme
                  ? 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
                  : 'border-white/10 bg-white/6 text-slate-100 hover:bg-white/12'
              }`}
              aria-label="Open Menu"
              data-testid="mobile-sidebar-open-button"
            >
              <Menu size={18} className="text-foreground" />
            </button>
            <div className="min-w-0 flex-1 text-center">
              <h1 className={`truncate text-sm font-bold ${isLightTheme ? 'text-slate-900' : 'text-white'}`}>{pageTitle || t('app.dashboard')}</h1>
            </div>
            <span className="h-9 w-9" aria-hidden="true" />
          </div>
        </div>}

        {/* Finance Alerts (Permanent Monitor) */}
        {isEditorWorkspace ? null : <FinanceAlertsWidget
          enabledPaths={[
            '/operations',
            '/accounting/chart-of-accounts',
            '/accounting/comprehensive',
            '/ai-financial',
          ]}
        />}
        
        {/* Page Content */}
        <div className="animate-fade-in" style={{ position: 'relative', zIndex: 10 }}>
          <Suspense
            fallback={
              <div className="flex items-center justify-center h-[50vh]">
                <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin" />
              </div>
            }
          >
            {canAccessRoute ? (
              <>
                <PageCustomCardsDock cards={pageCustomization.custom_cards || []} />
                <Outlet />
              </>
            ) : <UnauthorizedPanel />}
          </Suspense>
        </div>

        {/* AbuFahad Floating Chat - replaced by UnifiedAssistantDrawer */}
      </main>
        {/* Unified Assistant Drawer (kernel-backed, replaces UnifiedBotWidget + FloatingAIAssistant + WorkshopAIBot UI) */}
        {isEditorWorkspace ? null : <UnifiedAssistantDrawer />}

      
      {/* Toast Notifications */}
      <Toaster />
    </div>
    </AssistantProvider>
  );
};

export default Layout;
