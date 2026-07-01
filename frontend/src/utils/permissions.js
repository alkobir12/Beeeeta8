import rolePermissions from '../config/rolePermissions.json';

export const ROLE_DEFINITIONS = rolePermissions?.roles || {};

export const MODULE_DEFINITIONS = [
  { key: 'dashboard', label: 'لوحة التحكم', actions: ['view'] },
  { key: 'operations', label: 'صفحة العمليات', actions: ['view', 'settle', 'edit', 'delete'] },
  { key: 'journal_entries', label: 'دفتر اليومية', actions: ['view', 'create', 'edit', 'delete', 'pos'] },
  { key: 'archive', label: 'الأرشيف', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'vehicles', label: 'ملفات المركبات', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'customers', label: 'العملاء', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'invoices', label: 'الفواتير', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'debts', label: 'الذمم', actions: ['view', 'settle'] },
  { key: 'inventory', label: 'المخزون', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'work_orders', label: 'أوامر الشغل', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'reports', label: 'التقارير', actions: ['view'] },
  { key: 'users', label: 'المستخدمين', actions: ['view', 'create', 'edit', 'delete'] },
  { key: 'settings', label: 'الإعدادات', actions: ['view', 'edit'] },
];

export const ACTION_LABELS = {
  view: 'عرض',
  create: 'إضافة',
  edit: 'تعديل',
  delete: 'حذف',
  settle: 'تسوية',
  pos: 'POS',
};

const LEGACY_PERMISSION_MAP = {
  canViewDashboard: { module: 'dashboard', actions: ['view'] },
  canManageVehicles: { module: 'vehicles', actions: ['view', 'create', 'edit', 'delete'] },
  canManageCustomers: { module: 'customers', actions: ['view', 'create', 'edit', 'delete'] },
  canManageParts: { module: 'inventory', actions: ['view', 'create', 'edit', 'delete'] },
  canManageServices: { module: 'work_orders', actions: ['view', 'create', 'edit', 'delete'] },
  canViewReports: { module: 'reports', actions: ['view'] },
  canManageFinance: { module: 'debts', actions: ['view', 'settle'] },
  canManageUsers: { module: 'users', actions: ['view', 'create', 'edit', 'delete'] },
  canManageSettings: { module: 'settings', actions: ['view', 'edit'] },
};

export const getRolePermissions = (role) => {
  return ROLE_DEFINITIONS?.[role]?.permissions || {};
};

export const getRoleLabel = (role) => {
  return ROLE_DEFINITIONS?.[role]?.name || role || '';
};

export const isLegacyPermissions = (permissions) => {
  if (!permissions || typeof permissions !== 'object') return false;
  return Object.keys(permissions).some((key) => key.startsWith('can'));
};

export const normalizePermissions = (permissions, role) => {
  if (!permissions || typeof permissions !== 'object' || Object.keys(permissions).length === 0) {
    return getRolePermissions(role);
  }

  if (!isLegacyPermissions(permissions)) {
    const next = clonePermissions(permissions);
    if (!next.operations && next.work_orders) {
      next.operations = {
        view: next.work_orders.view === true,
        settle: next.work_orders.edit === true || next.debts?.settle === true,
        edit: next.work_orders.edit === true,
        delete: next.work_orders.delete === true,
      };
    }
    if (!next.journal_entries && next.reports) {
      next.journal_entries = {
        view: next.reports.view === true,
        create: next.reports.create === true,
        edit: next.reports.edit === true,
        delete: next.reports.delete === true,
        pos: next.reports.view === true,
      };
    }
    if (!next.archive && next.vehicles) {
      next.archive = {
        view: next.vehicles.view === true,
        create: next.vehicles.create === true,
        edit: next.vehicles.edit === true,
        delete: next.vehicles.delete === true,
      };
    }
    return next;
  }

  const next = {};
  Object.entries(LEGACY_PERMISSION_MAP).forEach(([legacyKey, config]) => {
    if (!permissions[legacyKey]) return;
    config.actions.forEach((action) => {
      if (!next[config.module]) next[config.module] = {};
      next[config.module][action] = true;
    });
  });

  const resolved = Object.keys(next).length ? next : getRolePermissions(role);
  return normalizePermissions(resolved, role);
};

export const hasPermission = (session, moduleKey, action = 'view') => {
  if (!moduleKey) return true;
  const permissions = normalizePermissions(session?.permissions, session?.role);
  return permissions?.[moduleKey]?.[action] === true;
};

export const hasAnyPermission = (session, rules = []) => (
  (rules || []).some((rule) => hasPermission(session, rule.module, rule.action || 'view'))
);

export const ROUTE_PERMISSIONS = [
  { pattern: /^\/$/, module: 'dashboard', action: 'view' },
  { pattern: /^\/operations/, module: 'operations', action: 'view' },
  { pattern: /^\/new-vehicle/, anyOf: [{ module: 'vehicles', action: 'create' }, { module: 'archive', action: 'create' }] },
  { pattern: /^\/vehicle\//, anyOf: [{ module: 'vehicles', action: 'view' }, { module: 'archive', action: 'view' }] },
  { pattern: /^\/customers/, module: 'customers', action: 'view' },
  { pattern: /^\/customer\//, module: 'customers', action: 'view' },
  { pattern: /^\/technicians/, module: 'users', action: 'view' },
  { pattern: /^\/suppliers/, module: 'inventory', action: 'view' },
  { pattern: /^\/parts/, module: 'inventory', action: 'view' },
  { pattern: /^\/parts-dashboard/, module: 'inventory', action: 'view' },
  { pattern: /^\/services/, module: 'work_orders', action: 'view' },
  { pattern: /^\/finance\//, module: 'reports', action: 'view' },
  { pattern: /^\/accounting\/journal-entries/, module: 'journal_entries', action: 'view' },
  { pattern: /^\/accounting\//, module: 'reports', action: 'view' },
  { pattern: /^\/financial-control/, module: 'reports', action: 'view', roles: ['admin', 'manager', 'supervisor'] },
  { pattern: /^\/ai-financial/, module: 'reports', action: 'view' },
  { pattern: /^\/system-audit/, module: 'reports', action: 'view' },
  { pattern: /^\/archive/, module: 'archive', action: 'view' },
  { pattern: /^\/import/, module: 'inventory', action: 'create' },
  { pattern: /^\/users/, module: 'users', action: 'view' },
  { pattern: /^\/settings/, module: 'settings', action: 'view' },
  { pattern: /^\/profile/, module: 'settings', action: 'view' },
  { pattern: /^\/quotations/, module: 'invoices', action: 'view' },
  { pattern: /^\/print/, module: 'invoices', action: 'view' },
  { pattern: /^\/templates/, module: 'invoices', action: 'view' },
  { pattern: /^\/denso-diagnostics/, module: 'vehicles', action: 'view' },
  { pattern: /^\/fault-knowledge/, module: 'vehicles', action: 'view' },
  { pattern: /^\/moltbot/, module: 'reports', action: 'view' },
  { pattern: /^\/debts-followup/, module: 'reports', action: 'view' },
];

export const resolveRoutePermission = (path) => {
  if (!path) return null;
  return ROUTE_PERMISSIONS.find((rule) => rule.pattern.test(path)) || null;
};

export const hasRoutePermission = (session, routeRule) => {
  if (!routeRule) return true;
  if (Array.isArray(routeRule.roles) && routeRule.roles.includes(String(session?.role || '').toLowerCase())) return true;
  if (Array.isArray(routeRule.anyOf)) return hasAnyPermission(session, routeRule.anyOf);
  return hasPermission(session, routeRule.module, routeRule.action || 'view');
};

export const FIRST_ALLOWED_ROUTES = [
  { path: '/', module: 'dashboard', action: 'view' },
  { path: '/operations', module: 'operations', action: 'view' },
  { path: '/accounting/journal-entries', module: 'journal_entries', action: 'view' },
  { path: '/archive', module: 'archive', action: 'view' },
  { path: '/customers', module: 'customers', action: 'view' },
  { path: '/parts-dashboard', module: 'inventory', action: 'view' },
  { path: '/settings', module: 'settings', action: 'view' },
];

export const getFirstAllowedRoute = (session) => (
  FIRST_ALLOWED_ROUTES.find((route) => hasPermission(session, route.module, route.action))?.path || '/login'
);

export const clonePermissions = (permissions) => {
  return JSON.parse(JSON.stringify(permissions || {}));
};