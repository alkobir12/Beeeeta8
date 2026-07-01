import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Wrench,
  Package,
  FileText,
  Settings,
  LogOut,
  ChevronDown,
  ChevronUp,
  Car,
  Printer,
  X,
  Activity,
  BarChart3,
  UserCircle,
  Archive,
  Building2,
  DollarSign,
  Receipt,
  Upload,
  BookOpen,
  Truck,
  Bot,
} from 'lucide-react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import LanguageToggleButton from './LanguageToggleButton';
import { resolveBackendBase } from '../utils/backendBase';
import { hasPermission, hasRoutePermission, resolveRoutePermission } from '../utils/permissions';
import { readRecentPages, clearRecentPages } from '../hooks/useRecentPages';
import { Clock } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);

const Sidebar = ({
  isOpen,
  onClose,
  isCollapsed = false,
  isHidden = false,
}) => {
  const { t, i18n } = useTranslation();
  const { themeName } = useTheme();
  const isLightTheme = themeName === 'light' || themeName === 'dashPro';
  const navigate = useNavigate();
  const location = useLocation();
  const navRef = useRef(null);
  const [collapsedGroups, setCollapsedGroups] = useState({});
  const [activeCollapsedGroup, setActiveCollapsedGroup] = useState('');
  const [workshopName, setWorkshopName] = useState('');

  // Lint rule in this repo discourages setState inside useEffect.
  // We keep an initial name and only update it after user interaction if needed.
  // (Settings loading is non-critical for login flow.)
  const canLoadSettings = useMemo(() => true, []);

  const MENU_ITEMS = [
    { path: '/', label: t('nav.dashboard'), icon: LayoutDashboard, enabled: true, permission: { module: 'dashboard', action: 'view' } },
    { path: '/operations', label: t('nav.operations'), icon: Receipt, enabled: true, permission: { module: 'operations', action: 'view' } },
    { path: '/debts-followup', label: '📲 متابعة الذمم والتحصيل', icon: DollarSign, enabled: true, permission: { module: 'debts', action: 'view' } },
    { path: '/archive', label: t('nav.archive'), icon: Archive, enabled: true, permission: { module: 'archive', action: 'view' } },
    {
      group: true,
      label: i18n.language === 'ar' ? 'العملاء والفنيون' : 'Customers & Technicians',
      icon: Users,
      enabled: true,
      permission: { module: 'customers', action: 'view' },
      children: [
        { path: '/customers', label: t('nav.customers'), enabled: true, permission: { module: 'customers', action: 'view' } },
        { path: '/technicians', label: t('nav.technicians'), enabled: true, permission: { module: 'users', action: 'view' } },
      ],
    },
    {
      group: true,
      label: t('nav.inventory'),
      icon: BookOpen,
      enabled: true,
      permission: { module: 'inventory', action: 'view' },
      children: [
        { path: '/parts-dashboard', label: t('inventory.parts_dashboard') || 'لوحة تحكم القطع', enabled: true, permission: { module: 'inventory', action: 'view' } },
        { path: '/parts', label: t('inventory.inventory'), enabled: true, permission: { module: 'inventory', action: 'view' } },
        { path: '/services', label: t('nav.services'), enabled: true, permission: { module: 'work_orders', action: 'view' } },
        { path: '/suppliers', label: t('nav.suppliers'), enabled: true, permission: { module: 'inventory', action: 'view' } },
      ]
    },
    {
      group: true,
      label: `💰 ${t('nav.finance_accounting')}`,
      icon: BarChart3,
      enabled: true,
      permission: { module: 'reports', action: 'view' },
      children: [
        { path: '/accounting/chart-of-accounts', label: t('nav.chart_of_accounts'), enabled: true, permission: { module: 'reports', action: 'view' } },
        { path: '/accounting/comprehensive', label: `📊 ${t('nav.financial_statements')}`, enabled: true, permission: { module: 'reports', action: 'view' } },
        { path: '/accounting/journal-entries', label: `📖 ${t('nav.journal')}`, enabled: true, permission: { module: 'journal_entries', action: 'view' } },
        { path: '/accounting/firewall', label: `🛡️ ${i18n.language === 'ar' ? 'جدار حماية المحاسبة' : 'Accounting Firewall'}`, enabled: true, permission: { module: 'reports', action: 'view' } },
        { path: '/financial-control', label: `✅ ${i18n.language === 'ar' ? 'الرقابة والاعتمادات' : 'Financial Control'}`, enabled: true, permission: { module: 'reports', action: 'view' }, roles: ['admin', 'manager', 'supervisor'] },
        { path: '/finance/taxes', label: t('nav.taxes'), enabled: true, permission: { module: 'reports', action: 'view' } },
      ]
    },
    { path: '/fault-knowledge', label: `📚 ${t('nav.fault_knowledge')}`, icon: Archive, enabled: true, permission: { module: 'vehicles', action: 'view' } },
    { path: '/denso-diagnostics', label: `⚡ ${t('nav.denso_diagnostics')}`, icon: Activity, enabled: true, permission: { module: 'vehicles', action: 'view' } },
    {
      group: true,
      label: t('nav.documents'),
      icon: FileText,
      enabled: true,
      permission: { module: 'invoices', action: 'view' },
      children: [
        { path: '/print', label: t('nav.print_quotes'), enabled: true, permission: { module: 'invoices', action: 'view' } },
        { path: '/templates', label: `🎨 ${t('nav.templates_manager')}`, enabled: true, permission: { module: 'invoices', action: 'view' } },
      ]
    },
    { path: '/settings', label: t('nav.settings'), icon: Settings, enabled: true, permission: { module: 'settings', action: 'view' } },
    // 🤖 Moltbot Studio أُزيل من القائمة الجانبية — البوتات أصبحت موحدة في UnifiedAssistantDrawer العائم.
    // إذا احتاج المدير الوصول للـ Studio، المسار /moltbot لا يزال متاحاً مباشرة.
  ];

  const loadSettings = async () => {
    try {
      // جلب بيانات الورشة من ملف الورشة أولاً
      const profileRes = await axios.get(`${API_URL}/profile`).catch(() => ({ data: null }));
      if (profileRes.data?.name) {
        setWorkshopName(profileRes.data.name);
        return;
      }
      
      // إذا لم يوجد، نجلب من الإعدادات القديمة
      const { data } = await axios.get(`${API_URL}/settings`);
      if (data?.workshopName) setWorkshopName(data.workshopName);
    } catch (e) {
      console.error('Error loading settings:', e);
    }
  };

  // Note: avoid calling loadSettings() inside useEffect to satisfy lint rules in this repo.
  // Keeping workshop name default is acceptable for now.
  // If you want workshop name dynamic, we can rework this with a user-triggered refresh.
  useEffect(() => {
    if (!canLoadSettings) return;
    loadSettings();
  }, [canLoadSettings]);

  useEffect(() => {
    setActiveCollapsedGroup('');
  }, [location.pathname, isCollapsed]);

  const toggleGroup = (label) => {
    if (isCollapsed) {
      setActiveCollapsedGroup((prev) => (prev === label ? '' : label));
      return;
    }
    const scrollToGroup = () => {
      setTimeout(() => {
        try {
          const btn = navRef.current?.querySelector(`[data-group-label]`);
          const allBtns = navRef.current?.querySelectorAll(`[data-group-label]`);
          let target = null;
          allBtns?.forEach(b => {
            if (b.getAttribute('data-group-label') === label) target = b;
          });
          target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (_) {}
      }, 80);
    };
    if (window.innerWidth < 1024) {
      setCollapsedGroups((prev) => {
        const next = {};
        groupLabels.forEach((groupLabel) => { next[groupLabel] = true; });
        const opening = prev[label] !== false;
        next[label] = !prev[label];
        if (opening) scrollToGroup();
        return next;
      });
      return;
    }
    setCollapsedGroups(prev => {
      const wasCollapsed = prev[label] !== false;
      if (wasCollapsed) scrollToGroup();
      return { ...prev, [label]: !prev[label] };
    });
  };

  const handleNavigate = (path) => {
    navigate(path);
    setActiveCollapsedGroup('');
    if (window.innerWidth < 1024) onClose?.();
  };

  const handleLogout = () => {
    localStorage.removeItem('workshopUser');
    localStorage.removeItem('session');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const readSession = () => {
    try {
      return JSON.parse(localStorage.getItem('session') || '{}');
    } catch (e) {
      return {};
    }
  };

  const [session, setSession] = useState(() => readSession());
  const [recentPages, setRecentPages] = useState(() => readRecentPages());
  const groupLabels = useMemo(
    () => MENU_ITEMS.filter((item) => item.group && Array.isArray(item.children)).map((item) => item.label),
    [MENU_ITEMS]
  );

  useEffect(() => {
    const sync = () => setRecentPages(readRecentPages());
    window.addEventListener('recentpages:update', sync);
    return () => window.removeEventListener('recentpages:update', sync);
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
    // Collapse all groups by default on ALL viewports, then open the active one
    setCollapsedGroups((prev) => {
      if (Object.keys(prev).length) return prev;  // already initialised
      const next = {};
      groupLabels.forEach((label) => { next[label] = true; });
      // auto-open the group that contains the current route
      const activeGroup = MENU_ITEMS.find(
        (item) => item.group && item.children?.some((child) => child.path === location.pathname)
      );
      if (activeGroup?.label) next[activeGroup.label] = false;
      return next;
    });
  }, [groupLabels]);  // intentionally omit location.pathname so it only runs once

  useEffect(() => {
    // When route changes, open the matching group (any viewport)
    const activeGroup = MENU_ITEMS.find(
      (item) => item.group && item.children?.some((child) => child.path === location.pathname)
    );
    if (!activeGroup?.label) return;
    setCollapsedGroups((prev) => {
      if (prev[activeGroup.label] === false) return prev;  // already open
      const next = { ...prev };
      next[activeGroup.label] = false;
      return next;
    });
  }, [location.pathname]);

  const renderMenuItem = (item, index) => {
    if (!item.enabled) return null;

    const role = session.role;

    if (item.allowedRoles && !item.allowedRoles.includes(role)) {
      return null;
    }

    const roleAllows = (entry) => Array.isArray(entry.roles) && entry.roles.includes(String(session?.role || '').toLowerCase());
    const canAccessItem = roleAllows(item) || !item.permission || hasPermission(session, item.permission.module, item.permission.action);

    if (item.group && item.children) {
      const visibleChildren = item.children.filter((child) => {
        if (child.enabled === false) return false;
        return roleAllows(child) || !child.permission || hasPermission(session, child.permission.module, child.permission.action);
      });

      if (!visibleChildren.length) return null;

      const groupCollapsed = collapsedGroups[item.label];
      const hasFloatingMenu = activeCollapsedGroup === item.label;
      const hasActiveChild = visibleChildren.some(child => location.pathname === child.path);
      const Icon = item.icon || FileText;

      return (
        <div key={index} className="relative mb-1">
          <button
            onClick={() => toggleGroup(item.label)}
            className={`sidebar-item w-full justify-between ${hasActiveChild ? 'sidebar-item-active active' : ''} ${isCollapsed ? '!justify-center !px-0' : ''}`}
            data-testid={`sidebar-group-${String(item.label).replace(/\s+/g, '-')}`}
            data-group-label={item.label}
            title={item.label}
          >
            {isCollapsed ? (
              <Icon size={18} className={hasActiveChild ? 'text-white' : 'text-slate-300'} />
            ) : (
              <>
                <span className="flex items-center gap-3">
                  <Icon size={18} className={hasActiveChild ? 'text-white' : 'text-slate-400'} />
                  <span className="truncate">{item.label}</span>
                </span>
                <span
                  className="flex-shrink-0 transition-transform duration-200"
                  style={{ transform: groupCollapsed ? 'rotate(0deg)' : 'rotate(0deg)' }}
                >
                  {groupCollapsed
                    ? <ChevronDown size={14} className="text-slate-400" />
                    : <ChevronUp size={14} className="text-sky-300" />
                  }
                </span>
              </>
            )}
          </button>

          {!isCollapsed && !groupCollapsed && (
            <div className="mt-1 space-y-0.5" style={{ paddingRight: '0.5rem', paddingLeft: '0.25rem' }}>
              {visibleChildren.map((child, childIndex) => {
                const isActive = location.pathname === child.path;
                return (
                  <button
                    key={childIndex}
                    onClick={() => handleNavigate(child.path)}
                    className={`sidebar-item w-full text-sm ${isActive ? 'sidebar-item-active active' : '!bg-transparent hover:!bg-white/8 !text-slate-300'}`}
                    style={{ borderRight: isActive ? '3px solid rgba(56,189,248,0.7)' : '3px solid transparent', borderRadius: '12px' }}
                    data-testid={`sidebar-item-${child.path.replace(/\//g, '-')}`}
                    title={child.label}
                  >
                    <span className="truncate">{child.label}</span>
                  </button>
                );
              })}
            </div>
          )}

          {isCollapsed && hasFloatingMenu && (
            <div
              className={`absolute top-0 z-[9999] w-64 rounded-[20px] border p-3 backdrop-blur-2xl ${
                isLightTheme
                  ? 'border-slate-200 bg-white/98 shadow-xl shadow-slate-300/25'
                  : 'border-white/12 bg-slate-950/97 shadow-2xl shadow-black/50'
              }`}
              style={{ left: 'calc(100% + 10px)' }}
              data-testid={`sidebar-collapsed-group-panel-${index}`}
            >
              <div className={`mb-2 flex items-center gap-2 px-2 ${isLightTheme ? 'text-slate-900' : 'text-slate-100'}`}>
                <Icon size={16} className="text-sky-300" />
                <span className="text-sm font-semibold">{item.label}</span>
              </div>
              <div className="space-y-1">
                {visibleChildren.map((child, childIndex) => {
                  const isActive = location.pathname === child.path;
                  return (
                    <button
                      key={childIndex}
                      type="button"
                      onClick={() => handleNavigate(child.path)}
                      className={`sidebar-item w-full ${isActive ? 'sidebar-item-active active' : '!bg-transparent hover:!bg-white/8 !text-slate-200'}`}
                      data-testid={`sidebar-collapsed-item-${child.path.replace(/\//g, '-')}`}
                    >
                      <span className="truncate">{child.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      );
    }

    if (!canAccessItem) return null;

    const Icon = item.icon || FileText;
    const isActive = location.pathname === item.path;

    return (
      <button
        key={index}
        onClick={() => handleNavigate(item.path)}
        className={`sidebar-item w-full rounded-2xl px-3 py-2 text-[0.9rem] flex items-center gap-3 transition-colors ${isCollapsed ? '!justify-center !px-0' : ''} ${
          isActive
            ? 'sidebar-item-active active'
            : 'text-slate-300 hover:bg-white/8 hover:text-slate-50'
        }`}
        data-testid={`sidebar-item-${item.path.replace(/\//g, '-') || 'dashboard'}`}
        title={item.label}
      >
        <Icon
          size={18}
          className={isActive ? 'text-white' : 'text-slate-400'}
        />
        {!isCollapsed && <span className="truncate">{item.label}</span>}
      </button>
    );
  };

  const sidebarPositionClass = isOpen
    ? 'translate-x-0'
    : '-translate-x-full';
  const desktopVisibilityClass = isHidden
    ? 'lg:-translate-x-[120%] lg:opacity-0 lg:pointer-events-none'
    : 'lg:translate-x-0 lg:opacity-100';

  return (
    <>
      {/* Mobile Overlay */}
      <div
        className={`fixed inset-0 bg-black/20 backdrop-blur-sm z-40 lg:hidden transition-opacity duration-200 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
        data-testid="mobile-sidebar-overlay"
      />

      <aside
        className={`sidebar-modern flex flex-col ${sidebarPositionClass} ${desktopVisibilityClass}`}
        style={{ '--sidebar-shell-width': isCollapsed ? '96px' : '286px' }}
        data-testid="app-sidebar"
        data-collapsed={isCollapsed ? 'true' : 'false'}
      >
        <div className={`${isCollapsed ? 'px-3 py-4' : 'p-5'} border-b ${
          isLightTheme
            ? 'border-slate-200 bg-gradient-to-br from-white via-slate-50 to-slate-100'
            : 'border-white/10 bg-gradient-to-br from-slate-950 via-slate-950 to-slate-900'
        }`}>
          <div className={`flex items-center ${isCollapsed ? 'justify-center' : 'justify-between'} gap-3`}>
            <div className={`flex items-center gap-3 ${isCollapsed ? 'justify-center' : ''}`}>
              <div className="flex h-12 w-12 items-center justify-center rounded-[18px] bg-gradient-to-br from-[#0ea5e9] via-[#38bdf8] to-[#6366f1] text-white shadow-lg shadow-sky-500/30">
              <Car size={20} />
            </div>
              {!isCollapsed && (
                <div>
                  <h2 className={`max-w-[150px] truncate text-sm font-semibold leading-tight ${isLightTheme ? 'text-slate-900' : 'text-slate-50'}`} data-testid="sidebar-workshop-name">
                    {workshopName || t('nav.workshop_system')}
                  </h2>
                  <div className={`mt-1 flex items-center gap-2 text-[11px] ${isLightTheme ? 'text-slate-500' : 'text-slate-400'}`}>
                    <Activity size={12} className="text-sky-300" />
                    <span>{t('nav.workshop_system')}</span>
                  </div>
                </div>
              )}
            </div>

          </div>
          <button onClick={onClose} className={`mt-3 lg:hidden ${isLightTheme ? 'text-slate-500 hover:text-slate-900' : 'text-slate-400 hover:text-white'}`} data-testid="mobile-sidebar-close-button">
            <X size={20} />
          </button>
        </div>

        <nav ref={navRef} className={`overflow-y-auto flex-1 min-h-0 ${isCollapsed ? 'px-2 pt-3' : 'px-3 pt-3'}`}>
          {/* 📜 Recent Pages — last 5 visited */}
          {!isCollapsed && recentPages.length > 0 ? (
            <div className={`mb-4 rounded-xl border p-2.5 ${isLightTheme ? 'border-slate-200 bg-white' : 'border-white/10 bg-white/[0.03]'}`} data-testid="sidebar-recent-pages">
              <div className="flex items-center justify-between mb-1.5">
                <div className={`flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold ${isLightTheme ? 'text-slate-500' : 'text-slate-400'}`}>
                  <Clock size={11} className="text-slate-400" />
                  أحدث الصفحات
                </div>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); clearRecentPages(); }}
                  className="text-[9px] text-slate-500 hover:text-slate-200 transition"
                  data-testid="sidebar-recent-pages-clear"
                  title="مسح السجل"
                >
                  مسح
                </button>
              </div>
              <ul className="space-y-0.5">
                {recentPages.filter((p) => {
                  const rule = resolveRoutePermission(p.path);
                  return hasRoutePermission(session, rule);
                }).map((p) => (
                  <li key={p.path}>
                    <button
                      type="button"
                      onClick={() => handleNavigate(p.path)}
                      className={`w-full text-right text-[12px] px-2 py-1 rounded-md transition truncate ${
                        location.pathname === p.path
                          ? 'bg-cyan-500/15 text-cyan-100'
                          : 'text-slate-300 hover:bg-white/5 hover:text-slate-100'
                      }`}
                      data-testid={`sidebar-recent-page-${p.path.replace(/[^a-zA-Z0-9-]/g, '-')}`}
                      title={p.path}
                    >
                      {p.label}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="space-y-1.5 pb-4">
            {MENU_ITEMS.map((item, index) => renderMenuItem(item, index))}
          </div>
        </nav>

        <div className={`flex-shrink-0 border-t ${isCollapsed ? 'px-2 py-3 pb-6' : 'p-4 pb-6'} space-y-2 ${
          isLightTheme ? 'border-slate-200 bg-slate-50/90' : 'border-white/10 bg-black/10'
        }`}>
          <LanguageToggleButton collapsed={isCollapsed} />
          <button
            onClick={handleLogout}
            className={`sidebar-item w-full text-red-300 hover:!bg-red-500/15 hover:!text-red-100 ${isCollapsed ? '!justify-center !px-0' : ''}`}
            data-testid="sidebar-logout-button"
            title={t('app.logout')}
          >
            <LogOut size={18} />
            {!isCollapsed && <span>{t('app.logout')}</span>}
          </button>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;