import React, { lazy, Suspense } from "react";
import axios from "axios";
import "./App.css"
import "./i18n"; // Initialize i18next
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { QueryClientProvider } from '@tanstack/react-query';
import ErrorBoundary from "./components/ErrorBoundary";
import Layout from "./components/Layout";
import { ThemeProvider } from './contexts/ThemeContext';
import { AssistantProvider } from './components/assistant/AssistantProvider';
import { queryClient } from './queryClient';
import { getFirstAllowedRoute, hasRoutePermission, normalizePermissions, resolveRoutePermission } from './utils/permissions';
import { resolveBackendBase } from './utils/backendBase';
import { installAuthInterceptors } from './utils/authToken';

// 🔒 Install JWT interceptors globally — auto-attaches Authorization header to every
// axios/fetch request once a token is stored in localStorage (set by Login.jsx).
installAuthInterceptors(axios);

// Eager load critical pages
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import PartsInventory from "./pages/PartsInventory";

// Lazy load other pages for better performance
const Customers = lazy(() => import("./pages/Customers"));
const NewVehicle = lazy(() => import("./pages/NewVehicle"));
const VehicleDetails = lazy(() => import("./pages/VehicleDetails"));
const CustomerDetails = lazy(() => import("./pages/CustomerDetails"));
const Technicians = lazy(() => import("./pages/Technicians"));
const Suppliers = lazy(() => import("./pages/Suppliers"));
const PartsDashboard = lazy(() => import("./pages/PartsDashboard"));
const ServicesManagement = lazy(() => import("./pages/ServicesManagement"));
const InvoiceDesignerStudio = lazy(() => import("./pages/InvoiceDesignerStudio"));
const Settings = lazy(() => import("./pages/Settings"));
const WorkshopProfile = lazy(() => import("./pages/WorkshopProfile"));
const VehicleArchive = lazy(() => import("./pages/VehicleArchive"));
const DatabaseSetup = lazy(() => import("./pages/DatabaseSetup"));
const Operations = lazy(() => import("./pages/Operations"));
const ApprovalPublic = lazy(() => import("./pages/ApprovalPublic"));
const ReportPublic = lazy(() => import("./pages/ReportPublic"));
const ImportPage = lazy(() => import("./pages/Import"));
const CustomerTracking = lazy(() => import("./pages/CustomerTracking"));
const Users = lazy(() => import("./pages/UsersManagement"));
const QuotationGenerator = lazy(() => import("./pages/QuotationGenerator"));
const DocumentPrint = lazy(() => import("./pages/DocumentPrint"));
const DensoDiagnostics = lazy(() => import("./pages/DensoDiagnostics"));
const FaultKnowledge = lazy(() => import("./pages/FaultKnowledge"));
const TemplatesManager = lazy(() => import("./pages/TemplatesManager"));
const Taxes = lazy(() => import("./pages/Taxes"));
const Invoices = lazy(() => import("./pages/Invoices"));
const ChartOfAccounts = lazy(() => import("./pages/ChartOfAccountsLiquid"));
const JournalEntries = lazy(() => import("./pages/JournalEntries"));
const ComprehensiveFinancial = lazy(() => import("./pages/ComprehensiveFinancial"));
const AIFinancial = lazy(() => import("./pages/AIFinancial"));
const FirewallPanel = lazy(() => import("./pages/FirewallPanel"));
const SystemAudit = lazy(() => import("./pages/SystemAudit"));
const MoltBot = lazy(() => import("./pages/MoltBotStudio"));
const DebtFollowUp = lazy(() => import("./pages/DebtFollowUp"));

// Loading component
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
  </div>
);

const getSessionFromCookie = () => {
  try {
    const cookieStr = document.cookie || '';
    const parts = cookieStr.split(';').map(p => p.trim());
    const sessionPart = parts.find(p => p.startsWith('session='));
    if (!sessionPart) return null;
    const value = decodeURIComponent(sessionPart.split('=')[1] || '');
    return JSON.parse(value || 'null');
  } catch (e) {
    return null;
  }
};

const Protected = ({ children }) => {
  const location = useLocation();
  const readSession = () => {
    // أولوية القراءة من الكوكي
    const fromCookie = getSessionFromCookie();
    if (fromCookie) return fromCookie;
    // توافق مع التخزين القديم في localStorage
    try {
      return JSON.parse(localStorage.getItem('session') || 'null');
    } catch (e) {
      return null;
    }
  };

  const [session, setSession] = React.useState(() => readSession());

  React.useEffect(() => {
    const sync = () => setSession(readSession());

    // تحديث عند تغيّر localStorage من نافذة أخرى
    window.addEventListener('storage', sync);

    // تحديث داخل نفس الصفحة (login/logout)
    window.addEventListener('sessionUpdated', sync);

    return () => {
      window.removeEventListener('storage', sync);
      window.removeEventListener('sessionUpdated', sync);
    };
  }, []);

  React.useEffect(() => {
    if (!session?.id && !session?.name) return undefined;
    let cancelled = false;
    const refreshSessionPermissions = async () => {
      try {
        const res = await fetch(`${resolveBackendBase()}/api/users`, { cache: 'no-store' });
        if (!res.ok || cancelled) return;
        const users = await res.json();
        const latest = (Array.isArray(users) ? users : []).find((user) => (
          String(user.id || '') === String(session.id || '')
          || String(user.username || '').trim() === String(session.name || '').trim()
          || String(user.name || '').trim() === String(session.name || '').trim()
        ));
        if (!latest || latest.isActive === false || cancelled) return;
        const nextSession = {
          ...session,
          id: latest.id || session.id,
          name: latest.name || session.name,
          phone: latest.phone || session.phone || '',
          email: latest.email || session.email || '',
          role: latest.role || session.role,
          permissions: normalizePermissions(latest.permissions, latest.role || session.role),
          guidanceEnabled: latest.guidanceEnabled !== false,
        };
        const currentSerialized = JSON.stringify(session.permissions || {});
        const nextSerialized = JSON.stringify(nextSession.permissions || {});
        if (currentSerialized !== nextSerialized || nextSession.role !== session.role || nextSession.name !== session.name) {
          localStorage.setItem('session', JSON.stringify(nextSession));
          localStorage.setItem('user', JSON.stringify(latest));
          try {
            document.cookie = 'session=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
            document.cookie = `session=${encodeURIComponent(JSON.stringify(nextSession))}; path=/`;
          } catch (e) {
            // ignore cookie refresh errors
          }
          window.dispatchEvent(new Event('sessionUpdated'));
          setSession(nextSession);
        }
      } catch (e) {
        // keep current session if refresh fails
      }
    };
    refreshSessionPermissions();
    return () => {
      cancelled = true;
    };
  }, [session?.id, session?.name]);

  if (!session) {
    return <Login />;
  }

  const routePermission = resolveRoutePermission(location.pathname);
  if (!routePermission && location.pathname !== '/') {
    const fallbackPath = getFirstAllowedRoute(session);
    return <Navigate to={fallbackPath} replace />;
  }
  if (routePermission && !hasRoutePermission(session, routePermission)) {
    const fallbackPath = getFirstAllowedRoute(session);
    return <Navigate to={fallbackPath === location.pathname ? '/login' : fallbackPath} replace />;
  }

  return children;
};

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AssistantProvider>
          <div className="App" style={{ backgroundColor: 'var(--bg-primary)', minHeight: '100vh' }}>
            <Router>
              <Suspense fallback={<PageLoader />}>
                <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/approval/:token" element={<ApprovalPublic />} />
                <Route path="/report/:token" element={<ReportPublic />} />
                <Route path="/track/:trackingId" element={<CustomerTracking />} />


                <Route
                  path="/"
                  element={
                    <Protected>
                      <Layout />
                    </Protected>
                  }
                >
                  <Route index element={<Dashboard />} />
                  <Route path="customers" element={<Customers />} />
                  <Route path="new-vehicle" element={<NewVehicle />} />
                  <Route path="vehicle/:id" element={<VehicleDetails />} />
                  <Route path="customer/:id" element={<CustomerDetails />} />
                  <Route path="technicians" element={<Technicians />} />
                  <Route path="suppliers" element={<Suppliers />} />
                  <Route path="debts-followup" element={<DebtFollowUp />} />
                  <Route path="parts" element={<PartsInventory />} />
                  <Route path="parts-dashboard" element={<PartsDashboard />} />
                  <Route path="catalog" element={<Navigate to="/parts" replace />} />
                  <Route path="services" element={<ServicesManagement />} />
                  <Route path="invoice-templates" element={<InvoiceDesignerStudio />} />
                  <Route path="settings" element={<Settings />} />
                  <Route path="profile" element={<Navigate to="/settings?tab=profile" replace />} />
                  <Route path="archive" element={<VehicleArchive />} />
                  <Route path="database-setup" element={<DatabaseSetup />} />
                  <Route path="setup" element={<DatabaseSetup />} />
                  <Route path="operations" element={<Operations />} />
                  <Route path="import" element={<Navigate to="/settings?tab=import" replace />} />
                  <Route path="users" element={<Navigate to="/settings?tab=users" replace />} />
                  <Route path="quotations" element={<QuotationGenerator />} />
                  <Route path="print" element={<DocumentPrint />} />
                  <Route path="templates" element={<TemplatesManager />} />
                  <Route path="denso-diagnostics" element={<DensoDiagnostics />} />
                  <Route path="fault-knowledge" element={<FaultKnowledge />} />

                  {/* Finance & Accounting Routes */}
                  <Route path="accounting/test" element={<div data-testid="accounting-test">TEST ACCOUNTING</div>} />
                  <Route path="finance/invoices" element={<Invoices />} />
                  <Route path="finance/taxes" element={<Taxes />} />
                  <Route path="accounting/chart-of-accounts" element={<ChartOfAccounts />} />
                  <Route path="accounting/comprehensive" element={<ComprehensiveFinancial />} />
                  <Route path="accounting/journal-entries" element={<JournalEntries />} />
                  <Route path="accounting/firewall" element={<FirewallPanel />} />

                  <Route path="ai-financial" element={<Navigate to="/accounting/firewall" replace />} />
                  <Route path="system-audit" element={<SystemAudit />} />
                  <Route path="moltbot" element={<MoltBot />} />

                  <Route path="*" element={<Dashboard />} />

                  
                </Route>
                </Routes>
              </Suspense>
            </Router>
          </div>
          </AssistantProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
