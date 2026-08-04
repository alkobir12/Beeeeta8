import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Car, Users, Wrench, CheckCircle, Plus, Search, MoreVertical, Clock, RefreshCw, User, Calendar, ArrowRight, Package } from 'lucide-react';
import { vehicleAPI, technicianAPI } from '../services/api';
import { useToast } from '../hooks/use-toast';
import VehicleQuickActions from '../components/VehicleQuickActions';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../contexts/ThemeContext';
import { resolveBackendBase } from '../utils/backendBase';
import { hasPermission } from '../utils/permissions';

const HIDDEN_DASHBOARD_STATUSES = new Set(['delivered', 'archived', 'cancelled', 'canceled']);

const normalizeVehicleStatusForDashboard = (status) => {
  const rawStatus = String(status || '').trim();
  if (!rawStatus || rawStatus === 'تشخيص') return 'diagnosis';
  return rawStatus;
};

const Dashboard = () => {
  const { t, i18n } = useTranslation();
  const { themeName } = useTheme();
  const isLight = themeName === 'light' || themeName === 'dashPro';
  const isRTL = i18n.language === 'ar';
  const navigate = useNavigate();
  const { toast } = useToast();
  const session = useMemo(() => {
    try { return JSON.parse(localStorage.getItem('session') || '{}'); } catch (e) { return {}; }
  }, []);
  const canCreateVehicle = hasPermission(session, 'vehicles', 'create') || hasPermission(session, 'archive', 'create');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [vehicles, setVehicles] = useState([]);
  const [technicians, setTechnicians] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const API_URL = (
    process.env.NODE_ENV === 'production'
      ? '/api'
      : `${resolveBackendBase()}/api`.replace('//api', '/api')
  );
  const WORKSHOP_ID = process.env.REACT_APP_WORKSHOP_ID;
  const [totalAR, setTotalAR] = useState(0);
  const [arCustomers, setArCustomers] = useState([]);

  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [showQuickActions, setShowQuickActions] = useState(false);
  const isMountedRef = useRef(true);
  
  const STATUS_CONFIG = {
    diagnosis: { label: t('status.diagnosis'), color: 'text-orange-400 bg-orange-500/10 border border-orange-500/20', iconColor: 'text-orange-400' },
    quotation: { label: t('status.quotation'), color: 'text-yellow-400 bg-yellow-500/10 border border-yellow-500/20', iconColor: 'text-yellow-400' },
    approved: { label: t('status.approved'), color: 'text-yellow-400 bg-yellow-500/10 border border-yellow-500/20', iconColor: 'text-yellow-400' },
    waiting_approval: { label: t('status.waiting_approval'), color: 'text-yellow-400 bg-yellow-500/10 border border-yellow-500/20', iconColor: 'text-yellow-400' },
    repair: { label: t('status.repair'), color: 'text-blue-400 bg-blue-500/10 border border-blue-500/20', iconColor: 'text-blue-400' },
    in_progress: { label: t('status.in_progress'), color: 'text-blue-400 bg-blue-500/10 border border-blue-500/20', iconColor: 'text-blue-400' },
    quality_check: { label: t('status.quality_check'), color: 'text-purple-400 bg-purple-500/10 border border-purple-500/20', iconColor: 'text-purple-400' },
    ready: { label: t('status.ready'), color: 'text-green-400 bg-green-500/10 border border-green-500/20', iconColor: 'text-green-400' },
    delivered: { label: t('status.delivered'), color: 'text-gray-400 bg-gray-500/10 border border-gray-500/20', iconColor: 'text-gray-400' },
    waiting_for_parts: { label: t('status.waiting_for_parts'), color: 'text-amber-300 bg-amber-500/10 border border-amber-500/20', iconColor: 'text-amber-300' },
    delivering: { label: t('status.delivering'), color: 'text-teal-300 bg-teal-500/10 border border-teal-500/20', iconColor: 'text-teal-300' }
  };

  useEffect(() => {
    isMountedRef.current = true;
    fetchData(true); // Initial load with loading indicator
    
    // Background refresh when returning to dashboard
    const handleVisibilityChange = () => {
      if (!document.hidden && isMountedRef.current) {
        fetchData(false); // Background refresh without loading indicator
      }
    };
    
    // Listen for vehicle updates from other pages
    const handleVehicleUpdated = () => {
      console.log('🔄 Vehicle updated - background refresh');
      if (isMountedRef.current) {
        fetchData(false);
      }
    };

    // Listen for ANY financial update (payment confirmed, POS sale, supplier settlement)
    const handleFinanceUpdated = (e) => {
      console.log('💰 Finance updated:', e?.detail?.source || 'unknown');
      if (isMountedRef.current) {
        fetchData(false);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('vehicleUpdated', handleVehicleUpdated);
    window.addEventListener('finance:updated', handleFinanceUpdated);

    return () => {
      isMountedRef.current = false;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('vehicleUpdated', handleVehicleUpdated);
      window.removeEventListener('finance:updated', handleFinanceUpdated);
    };
  }, []);

  const fetchData = useCallback(async (showLoading = false) => {
    if (!isMountedRef.current) return;
    
    try {
      if (showLoading) {
        setLoading(true);
      } else {
        setIsRefreshing(true);
      }
      
      const today = new Date().toISOString().slice(0, 10);

      const withTimeout = (promise, ms = 9000) => Promise.race([
        promise,
        new Promise((_, reject) => setTimeout(() => reject(new Error('dashboard-timeout')), ms)),
      ]);

      // Load core data first without letting one slow request keep the dashboard spinner forever.
      const [vehiclesRes, techniciansRes] = await Promise.allSettled([
        withTimeout(vehicleAPI.getAll()),
        withTimeout(technicianAPI.getAll()),
      ]);

      let nextVehicles = vehiclesRes.status === 'fulfilled' && Array.isArray(vehiclesRes.value?.data) ? vehiclesRes.value.data : [];
      let nextTechnicians = techniciansRes.status === 'fulfilled' && Array.isArray(techniciansRes.value?.data) ? techniciansRes.value.data : [];

      if (!nextVehicles.length) {
        try {
          const fallbackRes = await fetch('/api/vehicles', { cache: 'no-store' });
          const fallbackData = await fallbackRes.json();
          if (Array.isArray(fallbackData)) nextVehicles = fallbackData;
        } catch (fallbackError) {
          // keep empty list
        }
      }

      if (!nextTechnicians.length) {
        try {
          const fallbackRes = await fetch('/api/technicians', { cache: 'no-store' });
          const fallbackData = await fallbackRes.json();
          if (Array.isArray(fallbackData)) nextTechnicians = fallbackData;
        } catch (fallbackError) {
          // keep empty list
        }
      }

      if (isMountedRef.current) {
        setVehicles(nextVehicles.map((vehicle) => ({
          ...vehicle,
          rawStatus: vehicle.rawStatus || vehicle.status,
          status: normalizeVehicleStatusForDashboard(vehicle.status),
        })));
        setTechnicians(nextTechnicians);
      }

      // Lazy load AR in background (doesn't block UI)
      if (WORKSHOP_ID) {
        axios
          .get(`${API_URL}/finance/ar/customers`, {
            params: { workshop_id: WORKSHOP_ID, as_of: today, include_today: true },
          })
          .then((arRes) => {
            if (!isMountedRef.current) return;
            const arTotal = Number(arRes?.data?.data?.total_ar || 0);
            const customersList = arRes?.data?.data?.customers || [];
            setTotalAR(arTotal);
            setArCustomers(customersList);
          })
          .catch(() => {
            // ignore
          });
      } else {
        if (isMountedRef.current) setTotalAR(0);
        if (isMountedRef.current) setArCustomers([]);
      }
      

    } catch (error) {
      console.error('Error fetching data:', error);
      if (showLoading) {
        toast({ title: t('common.error'), description: t('common.loading'), variant: 'destructive' });
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
        setIsRefreshing(false);
      }
    }
  }, [t, toast]);

  const parseVisitItems = (notes) => {
    if (!notes) return [];
    try {
      if (typeof notes === 'string') {
        const parsed = JSON.parse(notes);
        if (Array.isArray(parsed.items)) return parsed.items;
        if (Array.isArray(parsed.services) || Array.isArray(parsed.parts)) {
          return [...(parsed.services || []), ...(parsed.parts || [])];
        }
        return [];
      }
      if (typeof notes === 'object') {
        if (Array.isArray(notes.items)) return notes.items;
        if (Array.isArray(notes.services) || Array.isArray(notes.parts)) {
          return [...(notes.services || []), ...(notes.parts || [])];
        }
        return [];
      }
    } catch (e) {
      return [];
    }
    return [];
  };

  const getVisitItems = (visit) => {
    if (!visit) return [];
    if (Array.isArray(visit.items) && visit.items.length) return visit.items;
    if (Array.isArray(visit.lineItems) && visit.lineItems.length) return visit.lineItems;
    return parseVisitItems(visit.notes);
  };

  const getServiceTypeLabel = (items = []) => {
    const names = items
      .map((item) => item.name || item.description)
      .filter(Boolean)
      .slice(0, 3);
    if (!names.length) return 'غير محدد';
    return names.join('، ');
  };

  const normalizeCustomerName = (value) => (value || '').toString().trim().toLowerCase();
  const normalizeSearchText = (value) => String(value || '')
    .replace(/[٠-٩]/g, (d) => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))
    .replace(/[۰-۹]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
    .replace(/[أإآ]/g, 'ا')
    .replace(/ة/g, 'ه')
    .replace(/ى/g, 'ي')
    .replace(/[\u064B-\u065F\u0670]/g, '')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
    .toLowerCase();

  const compactSearchText = (value) => normalizeSearchText(value).replace(/\s+/g, '');

  const buildVehicleSearchText = (vehicle) => {
    const summary = vehicleSummaries[vehicle.id] || getVehicleFallbackSummary(vehicle);
    const itemNames = [
      ...(Array.isArray(vehicle?.services) ? vehicle.services : []),
      ...(Array.isArray(vehicle?.parts) ? vehicle.parts : []),
    ].map((item) => item.name || item.description || item.partName || '').join(' ');
    return [
      vehicle.customerName,
      vehicle.ownerName,
      vehicle.customerPhone,
      vehicle.fileNumber,
      vehicle.file_number,
      vehicle.customerFileNumber,
      vehicle.customer_file_number,
      vehicle.vehicleNumber,
      vehicle.id,
      vehicle.plateNumber,
      vehicle.plate_number,
      vehicle.brand,
      vehicle.model,
      vehicle.year,
      vehicle.status,
      STATUS_CONFIG[vehicle.status]?.label,
      summary?.serviceType,
      itemNames,
    ].filter(Boolean).join(' ');
  };

  const [expandedVehicleId, setExpandedVehicleId] = useState(null);
  const [expandedStatWidget, setExpandedStatWidget] = useState(null);
  const [isHovering, setIsHovering] = useState(false);
  const [vehicleSummaries, setVehicleSummaries] = useState({});
  const [vehicleSummaryLoading, setVehicleSummaryLoading] = useState(false);

  const getVehicleFallbackSummary = (vehicle) => {
    const mergedItems = [
      ...(Array.isArray(vehicle?.services) ? vehicle.services : []),
      ...(Array.isArray(vehicle?.parts) ? vehicle.parts : []),
    ];

    const estimatedTotal = mergedItems.reduce((sum, item) => {
      const qty = Number(item.quantity || 1);
      const price = Number(item.price || item.unit_price || 0);
      return sum + (Number(item.total || 0) || (qty * price));
    }, 0);

    return {
      visitsCount: Number(vehicle?.visitsCount || 0),
      estimatedTotal,
      serviceType: getServiceTypeLabel(mergedItems),
    };
  };

  const loadVehicleSummaries = useCallback(async () => {
    if (!vehicles.length) {
      setVehicleSummaries({});
      return;
    }

    setVehicleSummaryLoading(true);
    try {
      const vehicleIds = vehicles.map((vehicle) => vehicle.id).filter(Boolean);
      if (!vehicleIds.length) {
        setVehicleSummaries({});
        return;
      }

      const res = await axios.post(`${API_URL}/vehicles/dashboard/summaries`, {
        vehicle_ids: vehicleIds,
      }, { timeout: 8000 });
      const summariesArray = res?.data?.summaries || [];
      const summariesMap = summariesArray.reduce((acc, summary) => {
        const key = String(summary?.vehicleId || '').trim();
        if (!key) return acc;
        acc[key] = {
          visitsCount: Number(summary?.visitsCount || 0),
          estimatedTotal: Number(summary?.estimatedTotal || 0),
          serviceType: summary?.serviceType || 'غير محدد',
        };
        return acc;
      }, {});

      if (isMountedRef.current) {
        setVehicleSummaries(summariesMap);
      }
    } catch (e) {
      if (isMountedRef.current) {
        setVehicleSummaries({});
      }
    } finally {
      if (isMountedRef.current) {
        setVehicleSummaryLoading(false);
      }
    }
  }, [API_URL, vehicles]);

  useEffect(() => {
    loadVehicleSummaries();
  }, [loadVehicleSummaries]);

  const dashboardVehicles = useMemo(
    () => vehicles.filter((vehicle) => !HIDDEN_DASHBOARD_STATUSES.has(normalizeVehicleStatusForDashboard(vehicle.status))),
    [vehicles]
  );

  const stats = useMemo(() => {
    const inProgressStatuses = new Set([
      'diagnosis',
      'in_progress',
      'waiting_approval',
      'quality_check',
      'repair',
      'quotation',
      'approved',
      'waiting_for_parts',
    ]);

    const busyTechnicianKeys = new Set(
      dashboardVehicles
        .filter((vehicle) => inProgressStatuses.has(vehicle.status))
        .map((vehicle) => String(vehicle.technicianId || vehicle.technicianName || '').trim())
        .filter(Boolean)
    );

    const dashboardCustomerKeys = new Set(
      dashboardVehicles
        .map((vehicle) => normalizeCustomerName(vehicle.customerName))
        .filter(Boolean)
    );

    const arLookup = new Map(
      (arCustomers || []).map((entry) => [
        normalizeCustomerName(entry.customer),
        Number(entry.balance || 0),
      ])
    );

    const dashboardReceivables = [...dashboardCustomerKeys].reduce(
      (sum, key) => sum + (arLookup.get(key) || 0),
      0
    );

    return {
      totalVehicles: dashboardVehicles.length,
      inProgress: dashboardVehicles.filter((vehicle) => inProgressStatuses.has(vehicle.status)).length,
      ready: dashboardVehicles.filter((vehicle) => vehicle.status === 'ready').length,
      technicians: technicians.length,
      waitingParts: dashboardVehicles.filter((vehicle) => vehicle.status === 'waiting_for_parts').length,
      diagnosis: dashboardVehicles.filter((vehicle) => vehicle.status === 'diagnosis').length,
      delivering: dashboardVehicles.filter((vehicle) => vehicle.status === 'delivering').length,
      readyForHandover: dashboardVehicles.filter((vehicle) => ['ready', 'delivering'].includes(vehicle.status)).length,
      busyTechnicians: busyTechnicianKeys.size,
      freeTechnicians: Math.max(technicians.length - busyTechnicianKeys.size, 0),
      waitingPayment: totalAR,
      dashboardReceivables,
    };
  }, [dashboardVehicles, technicians, totalAR, arCustomers]);

  const searchSourceVehicles = searchQuery.trim() ? vehicles : dashboardVehicles;

  const filteredVehicles = searchSourceVehicles.filter(vehicle => {
    const normalizedQuery = normalizeSearchText(searchQuery);
    const compactQuery = compactSearchText(searchQuery);
    const haystack = buildVehicleSearchText(vehicle);
    const normalizedHaystack = normalizeSearchText(haystack);
    const compactHaystack = compactSearchText(haystack);
    const matchesSearch = !normalizedQuery
      || normalizedHaystack.includes(normalizedQuery)
      || (compactQuery && compactHaystack.includes(compactQuery));
    
    const matchesStatus = filterStatus === 'all' || 
                         vehicle.status === filterStatus ||
                         (filterStatus === 'ready' && (vehicle.status === 'ready' || vehicle.status === 'delivered'));

    // عند اختيار "approved" نعرض أيضاً "quotation" (بعض البيانات القديمة محفوظة بهذا الاسم)
    const matchesStatusFixed = filterStatus === 'approved'
      ? (vehicle.status === 'approved' || vehicle.status === 'quotation' || vehicle.status === 'waiting_approval')
      : matchesStatus;
    return matchesSearch && matchesStatusFixed;
  });

  const getStatusConfigForVehicle = (status) => STATUS_CONFIG[status] || STATUS_CONFIG.diagnosis;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[50vh]">
        <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-500 rounded-full animate-spin" />
      </div>
    );
  }

  // Theme-aware dashboard palette
  const styles = {
    bg: isLight
      ? 'linear-gradient(180deg, #f6f7fb 0%, #eef3f8 48%, #f8fafc 100%)'
      : 'linear-gradient(180deg, #0b1223 0%, #0f172a 45%, #111827 100%)',
    cardBg: isLight ? 'rgba(255,255,255,0.92)' : 'rgba(15,23,42,0.72)',
    cardBorder: isLight ? 'rgba(15,23,42,0.08)' : 'rgba(148,163,184,0.22)',
    textPrimary: isLight ? '#05070d' : '#f8fafc',
    textSecondary: isLight ? '#243044' : 'rgba(226,232,240,0.92)',
    textMuted: isLight ? '#4b5565' : 'rgba(148,163,184,0.92)',
    inputBg: isLight ? 'rgba(255,255,255,0.96)' : 'rgba(15,23,42,0.72)',
    inputBorder: isLight ? 'rgba(15,23,42,0.10)' : 'rgba(148,163,184,0.28)',
    hoverBg: isLight ? 'rgba(37,99,235,0.08)' : 'rgba(56,189,248,0.18)',
    statCardBg: isLight ? 'rgba(255,255,255,0.94)' : 'rgba(15,23,42,0.78)',
  };

  // Vehicle cards follow selected theme
  const isGlassPurpleTheme = !isLight;
  const vehicleCardBackground = isGlassPurpleTheme
    ? 'radial-gradient(circle at 12% 18%, rgba(168,85,247,0.24), transparent 52%), radial-gradient(circle at 88% 78%, rgba(99,102,241,0.20), transparent 55%), rgba(255,255,255,0.06)'
    : 'linear-gradient(145deg, rgba(255,255,255,0.98) 0%, rgba(247,250,252,0.96) 100%)';
  const vehicleCardBorder = isGlassPurpleTheme
    ? 'rgba(168,85,247,0.22)'
    : styles.cardBorder;
  const vehicleText = {
    primary: isGlassPurpleTheme ? '#f8fafc' : '#05070d',
    secondary: isGlassPurpleTheme ? 'rgba(226,232,240,0.82)' : '#1f2937',
    muted: isGlassPurpleTheme ? 'rgba(148,163,184,0.82)' : '#374151',
  };

  return (
    <div 
      className={`max-w-7xl mx-auto min-h-screen px-1 sm:px-4 py-4 ${isRTL ? 'rtl' : 'ltr'}`} 
      dir={isRTL ? 'rtl' : 'ltr'}
      style={{ background: styles.bg }}
    >
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 sm:gap-4 mb-4 sm:mb-8">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold" style={{ color: styles.textPrimary }}>{t('dashboard.title')}</h1>
            <p className="text-sm sm:text-base mt-1 flex items-center gap-2" style={{ color: styles.textSecondary }}>
              {t('dashboard.overview')}
              {isRefreshing && (
                <RefreshCw size={14} className="animate-spin text-primary" />
              )}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => fetchData(false)}
              className="p-2 rounded-lg transition-colors"
              style={{ 
                backgroundColor: styles.cardBg,
                border: `1px solid ${styles.cardBorder}`
              }}
              title={t('buttons.refresh')}
            >
              <RefreshCw size={18} className={isRefreshing ? 'animate-spin text-blue-500' : ''} style={{ color: isRefreshing ? undefined : styles.textSecondary }} />
            </button>
            <button
              onClick={() => {
                const newLang = i18n.language === 'ar' ? 'en' : 'ar';
                console.log('🔄 Changing language to:', newLang);
                localStorage.setItem('language', newLang);
                i18n.changeLanguage(newLang);
              }}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              style={{ 
                backgroundColor: isLight ? '#1e293b' : '#3b82f6',
                color: '#ffffff'
              }}
            >
              {i18n.language === 'ar' ? 'EN' : 'AR'}
            </button>
            {canCreateVehicle ? (
            <button 
              onClick={() => navigate('/new-vehicle')}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium text-white transition-all"
              style={{ 
                background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                boxShadow: '0 4px 14px rgba(37, 99, 235, 0.25)'
              }}
            >
              <Plus size={18} />
              <span>{t('dashboard.newVehicle') || t('dashboard.new_vehicle')}</span>
            </button>
            ) : null}
          </div>
        </div>

        {/* Stats Grid - Responsive expandable widgets */}
        <div className="dashboard-stats-grid grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-4 sm:mb-8">
          {/* إجمالي المركبات */}
          <div
            className="dash-widget-shell dashboard-stat-card"
            style={{ 
              backgroundColor: styles.cardBg, 
              border: `1px solid ${styles.cardBorder}`,
              maxHeight: expandedStatWidget === 'total' ? '320px' : '150px',
              transition: 'max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s ease',
              boxShadow: expandedStatWidget === 'total' 
                ? '0 20px 50px rgba(0,0,0,0.15)' 
                : '0 4px 12px rgba(0,0,0,0.05)'
            }}
            data-expanded={expandedStatWidget === 'total'}
            onClick={() => {
              setExpandedStatWidget(prev => prev === 'total' ? null : 'total');
              setFilterStatus('all');
            }}
            onMouseEnter={() => setExpandedStatWidget('total')}
            onMouseLeave={() => setExpandedStatWidget(null)}
          >
            <div className="dash-widget-top">
              <div className="flex flex-col">
                <span className="text-[10px] font-medium" style={{ color: styles.textSecondary }}>{t('dashboard.totalVehicles') || t('dashboard.total_vehicles')}</span>
                <span className="text-2xl font-bold" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-total-vehicles-value">{stats.totalVehicles}</span>
              </div>
            </div>
            <div className="dash-widget-main">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center shadow-md">
                  <Car size={20} className="text-white" />
                </div>
              </div>
            </div>
            <div className="dash-widget-bottom border-t" style={{ borderColor: styles.cardBorder }}>
              <div className="flex flex-col text-[9px]" style={{ color: styles.textSecondary }}>
                <span>{t('dashboard.activeToday') || 'قيد العمل الآن'}</span>
                <span className="font-semibold text-xs" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-total-vehicles-active-value">{stats.inProgress}</span>
              </div>
              <div className="flex flex-col text-[9px]" style={{ color: styles.textSecondary }}>
                <span>{t('dashboard.ready') || 'جاهزة الآن'}</span>
                <span className="font-semibold text-xs" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-total-vehicles-ready-value">{stats.ready}</span>
              </div>
            </div>
            {expandedStatWidget === 'total' && (
              <div className="mt-3 border-t pt-3" style={{ borderColor: styles.cardBorder }}>
                <div className="flex flex-col gap-1">
                  <span
                    className="text-[10px] font-medium"
                    style={{ color: styles.textSecondary }}
                    data-testid="dashboard-stat-total-vehicles-ar-label"
                  >
                    إجمالي الذمم الحالية للمركبات
                  </span>
                  <div
                    className="rounded-xl border border-white/10 bg-slate-950/40 px-3 py-2"
                    data-testid="dashboard-stat-total-vehicles-ar-box"
                  >
                    <span
                      className="text-sm font-bold"
                      style={{ color: styles.textPrimary }}
                      data-testid="dashboard-stat-total-vehicles-ar-value"
                    >
                      {(stats.dashboardReceivables || 0).toLocaleString(isRTL ? 'ar-SA' : 'en-US')} {t('common.currency')}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* مركبات قيد العمل */}
          <div
            className="dash-widget-shell dashboard-stat-card"
            style={{ 
              backgroundColor: styles.cardBg, 
              border: `1px solid ${styles.cardBorder}`,
              maxHeight: expandedStatWidget === 'inProgress' ? '280px' : '150px',
              transition: 'max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s ease',
              boxShadow: expandedStatWidget === 'inProgress' 
                ? '0 20px 50px rgba(0,0,0,0.15)' 
                : '0 4px 12px rgba(0,0,0,0.05)'
            }}
            data-expanded={expandedStatWidget === 'inProgress'}
            onClick={() => {
              setExpandedStatWidget(prev => prev === 'inProgress' ? null : 'inProgress');
              setFilterStatus('in_progress');
            }}
            onMouseEnter={() => setExpandedStatWidget('inProgress')}
            onMouseLeave={() => setExpandedStatWidget(null)}
          >
            <div className="dash-widget-top">
              <div className="flex flex-col">
                <span className="text-[10px] font-medium" style={{ color: styles.textSecondary }}>{t('dashboard.inProgress') || t('dashboard.in_progress')}</span>
                <span className="text-2xl font-bold" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-in-progress-value">{stats.inProgress}</span>
              </div>
            </div>
            <div className="dash-widget-main">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-sky-500 to-blue-600 flex items-center justify-center shadow-md">
                  <Clock size={18} className="text-white" />
                </div>
              </div>
            </div>
            <div className="dash-widget-bottom border-t" style={{ borderColor: styles.cardBorder }}>
              <div className="flex flex-col text-[9px]" style={{ color: styles.textSecondary }}>
                <span>{t('dashboard.waitingParts') || 'بانتظار قطع الغيار'}</span>
                <span className="font-semibold text-xs" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-waiting-parts-value">{stats.waitingParts || 0}</span>
              </div>
              <div className="flex flex-col text-[9px]" style={{ color: styles.textSecondary }}>
                <span>{t('dashboard.inDiagnosis') || 'قيد التشخيص'}</span>
                <span className="font-semibold text-xs" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-diagnosis-value">{stats.diagnosis || 0}</span>
              </div>
            </div>
          </div>

          {/* جاهزة للتسليم */}
          <div
            className="dash-widget-shell dashboard-stat-card"
            style={{ 
              backgroundColor: styles.cardBg, 
              border: `1px solid ${styles.cardBorder}`,
              maxHeight: expandedStatWidget === 'ready' ? '280px' : '150px',
              transition: 'max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s ease',
              boxShadow: expandedStatWidget === 'ready' 
                ? '0 20px 50px rgba(0,0,0,0.15)' 
                : '0 4px 12px rgba(0,0,0,0.05)'
            }}
            data-expanded={expandedStatWidget === 'ready'}
            onClick={() => {
              setExpandedStatWidget(prev => prev === 'ready' ? null : 'ready');
              setFilterStatus('ready');
            }}
            onMouseEnter={() => setExpandedStatWidget('ready')}
            onMouseLeave={() => setExpandedStatWidget(null)}
          >
            <div className="dash-widget-top">
              <div className="flex flex-col">
                <span className="text-[10px] font-medium" style={{ color: styles.textSecondary }}>{t('dashboard.ready')}</span>
                <span className="text-2xl font-bold" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-ready-value">{stats.readyForHandover}</span>
              </div>
            </div>
            <div className="dash-widget-main">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-emerald-400 to-green-600 flex items-center justify-center shadow-md">
                  <CheckCircle size={18} className="text-white" />
                </div>
              </div>
            </div>
            <div className="dash-widget-bottom border-t" style={{ borderColor: styles.cardBorder }}>
              <div className="flex flex-col text-[9px]" style={{ color: styles.textSecondary }}>
                <span>{t('dashboard.ready') || 'بانتظار الاستلام'}</span>
                <span className="font-semibold text-xs" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-ready-waiting-value">{stats.ready || 0}</span>
              </div>
              <div className="flex flex-col text-[9px]" style={{ color: styles.textSecondary }}>
                <span>{t('dashboard.inDelivery') || 'قيد التسليم'}</span>
                <span className="font-semibold text-xs" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-delivering-value">{stats.delivering || 0}</span>
              </div>
            </div>
          </div>

          {/* الفنيين */}
          <div
            className="dash-widget-shell dashboard-stat-card"
            style={{ 
              backgroundColor: styles.cardBg, 
              border: `1px solid ${styles.cardBorder}`,
              maxHeight: expandedStatWidget === 'technicians' ? '280px' : '150px',
              transition: 'max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s ease',
              boxShadow: expandedStatWidget === 'technicians' 
                ? '0 20px 50px rgba(0,0,0,0.15)' 
                : '0 4px 12px rgba(0,0,0,0.05)'
            }}
            data-expanded={expandedStatWidget === 'technicians'}
            onClick={() => {
              setExpandedStatWidget(prev => prev === 'technicians' ? null : 'technicians');
              navigate('/technicians');
            }}
            onMouseEnter={() => setExpandedStatWidget('technicians')}
            onMouseLeave={() => setExpandedStatWidget(null)}
          >
            <div className="dash-widget-top">
              <div className="flex flex-col">
                <span className="text-[10px] font-medium" style={{ color: styles.textSecondary }}>{t('dashboard.technicians')}</span>
                <span className="text-2xl font-bold" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-technicians-value">{stats.technicians}</span>
              </div>
            </div>
            <div className="dash-widget-main">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-md">
                  <Users size={18} className="text-white" />
                </div>
              </div>
            </div>
            <div className="dash-widget-bottom border-t" style={{ borderColor: styles.cardBorder }}>
              <div className="flex flex-col text-[9px]" style={{ color: styles.textSecondary }}>
                <span>{t('dashboard.busyTechs') || 'مشغولون'}</span>
                <span className="font-semibold text-xs" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-busy-technicians-value">{stats.busyTechnicians || 0}</span>
              </div>
              <div className="flex flex-col text-[9px]" style={{ color: styles.textSecondary }}>
                <span>{t('dashboard.freeTechs') || 'متاحون'}</span>
                <span className="font-semibold text-xs" style={{ color: styles.textPrimary }} data-testid="dashboard-stat-free-technicians-value">{stats.freeTechnicians || 0}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Search & Filter - Stack on mobile */}
        <div 
          className="rounded-2xl p-3 sm:p-4 mb-4 sm:mb-6 space-y-3 sm:space-y-0 sm:flex sm:flex-row sm:gap-4 sm:items-center"
          style={{ 
            backgroundColor: styles.cardBg,
            border: `1px solid ${styles.cardBorder}`
          }}
        >
          <div className="relative flex-1 w-full">
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2" size={18} style={{ color: styles.textMuted }} />
            <input
              type="text"
              placeholder="ابحث بالاسم، رقم الملف، العملية، اللوحة، الماركة أو الموديل"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pr-10 pl-4 py-2.5 rounded-xl text-sm sm:text-base transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              style={{ 
                backgroundColor: styles.inputBg,
                border: `1px solid ${styles.inputBorder}`,
                color: styles.textPrimary
              }}
              data-testid="dashboard-search-input"
            />
          </div>
          <div className="flex gap-2 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0 -mx-1 px-1">
            {['all', 'diagnosis', 'quotation', 'approved', 'repair', 'ready'].map((status) => (
              <button
                key={`filter-${status}`}
                onClick={() => setFilterStatus(status)}
                className={`px-3 sm:px-4 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm font-medium whitespace-nowrap transition-all flex-shrink-0 ${
                  filterStatus === status 
                    ? 'bg-blue-600 text-white shadow-md' 
                    : ''
                }`}
                style={filterStatus !== status ? { 
                  backgroundColor: isLight ? '#f1f5f9' : '#334155',
                  color: styles.textSecondary
                } : {}}
              >
                {status === 'all' ? t('common.all') : getStatusConfigForVehicle(status).label}
              </button>
            ))}
          </div>
        </div>

        {/* Vehicles Grid - 1 column mobile, 2 tablet, 3 desktop */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 md:gap-6">
          {filteredVehicles.length === 0 ? (
            <div className="col-span-full py-12 text-center">
              <div 
                className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4"
                style={{ backgroundColor: isLight ? '#f1f5f9' : '#334155' }}
              >
                <Car size={40} style={{ color: styles.textMuted }} />
              </div>
              <h3 className="text-lg font-medium" style={{ color: styles.textPrimary }}>{t('common.no_data')}</h3>
              <p className="mt-1" style={{ color: styles.textSecondary }}>{t('dashboard.searchPlaceholder') || t('dashboard.search')}</p>
            </div>
          ) : (
            filteredVehicles.map((vehicle) => {
              const statusConfig = getStatusConfigForVehicle(vehicle.status);
              const progress = typeof vehicle.progress === 'number' ? vehicle.progress : 65;
              const isUrgent = vehicle.priority === 'urgent' || vehicle.isUrgent;
              const fallbackSummary = getVehicleFallbackSummary(vehicle);
              const summary = vehicleSummaries[vehicle.id] || fallbackSummary;
              const visitsCount = summary.visitsCount ?? fallbackSummary.visitsCount ?? vehicle.visitsCount ?? 0;
              const estimatedTotal = summary.estimatedTotal ?? fallbackSummary.estimatedTotal ?? vehicle.estimatedTotal ?? 0;
              const serviceType = summary.serviceType || fallbackSummary.serviceType || (vehicleSummaryLoading ? 'جارٍ التحميل...' : 'غير محدد');
              return (
                <div
                  key={`vehicle-${vehicle.id}`}
                  className="dash-widget-shell vehicle-card"
                  style={{
                    background: vehicleCardBackground,
                    border: `1px solid ${vehicleCardBorder}`,
                    boxShadow: expandedVehicleId === vehicle.id
                      ? '0 28px 80px rgba(15,23,42,0.16), 0 0 0 1px rgba(37,99,235,0.12)'
                      : '0 18px 50px rgba(15,23,42,0.10)',
                    backdropFilter: isGlassPurpleTheme ? 'blur(14px)' : undefined,
                    WebkitBackdropFilter: isGlassPurpleTheme ? 'blur(14px)' : undefined,
                    height: expandedVehicleId === vehicle.id ? 'auto' : '260px',
                    minHeight: '260px',
                    maxHeight: expandedVehicleId === vehicle.id ? 'none' : '260px',
                    transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
                    transform: expandedVehicleId === vehicle.id ? 'scale(1.02)' : 'scale(1)',
                    overflow: 'hidden',
                  }}
                  data-expanded={expandedVehicleId === vehicle.id}
                  onClick={(e) => {
                    // لا تفعل شيء إذا النقر على زر أو رابط
                    if (e.target.closest('button') || e.target.closest('.navigate-btn')) {
                      return;
                    }
                    // التوسيع/الطي يكون بالضغط فقط لتجنب التعليق
                    setExpandedVehicleId(prev => prev === vehicle.id ? null : vehicle.id);
                  }}
                  data-testid={`dashboard-vehicle-card-${vehicle.id}`}
                >
                  {/* النقاط الرأسية أعلى اليسار */}
                  <div className="absolute top-5 left-5 flex flex-col gap-1 opacity-60">
                    <span className="w-1 h-1 rounded-full bg-gray-400" />
                    <span className="w-1 h-1 rounded-full bg-gray-400" />
                    <span className="w-1 h-1 rounded-full bg-gray-400" />
                  </div>

                  {/* شارة الحالة + ترويسة الكرت */}
                  <div className="flex items-center justify-between mb-4 px-1 pt-1">
                    <div className="flex items-center gap-2 text-xs sm:text-sm">
                      <span className={`px-3 py-1 rounded-full border text-[11px] font-bold ${statusConfig?.color || 'bg-slate-100 text-slate-900 border-slate-300'}`}>
                        {statusConfig?.label || (vehicle.status || '-')}
                      </span>
                      <span className={`w-2 h-2 rounded-full ${vehicle.status === 'delivered' ? 'bg-gray-400' : vehicle.status === 'ready' ? 'bg-green-500' : vehicle.status === 'repair' ? 'bg-blue-500' : 'bg-orange-500'}`} />
                    </div>
                    <button
                      data-testid={`open-quick-actions-${vehicle.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedVehicle(vehicle);
                        setShowQuickActions(true);
                      }}
                      className="p-2 rounded-full hover:bg-gray-100/60 text-gray-400 flex-shrink-0"
                      aria-label="Quick Actions"
                    >
                      <MoreVertical size={16} />
                    </button>
                  </div>

                  {/* هوية المركبة: لوحة واضحة + اسم مركبة منظم */}
                  <div className="mb-4 space-y-3">
                    {/* رقم اللوحة بشكل واضح في المنتصف */}
                    <div className="flex justify-center">
                      <span className="vehicle-plate-pill inline-flex items-center gap-3 px-4 py-2 rounded-2xl bg-white text-black text-base sm:text-lg font-extrabold border border-slate-300 shadow-[0_10px_24px_-18px_rgba(15,23,42,0.35)]">
                        <Car size={16} className="opacity-90 text-black" />
                        <span className="font-mono tracking-[0.35em] uppercase">
                          {vehicle.plateNumber || t('common.unknown')}
                        </span>
                      </span>
                    </div>

                    {/* اسم المركبة + الموديل + حالة الاستعجال */}
                    <div className="flex flex-col items-center justify-center gap-2 text-center">
                      <div className="flex items-baseline gap-2 flex-wrap justify-center">
                        <span
                          className="vehicle-title-main text-base sm:text-xl font-semibold tracking-tight"
                          style={{ color: vehicleText.primary }}
                        >
                          {vehicle.brand || ''} {vehicle.model || ''}
                        </span>
                        {vehicle.year && (
                          <span className="px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs font-semibold border border-slate-200">
                            {vehicle.year}
                          </span>
                        )}
                      </div>
                      {(vehicle.fileNumber || vehicle.file_number) && (
                        <span
                          className="vehicle-file-number text-base sm:text-xl font-semibold tracking-tight"
                          style={{ color: '#000000' }}
                          data-testid={`dashboard-vehicle-file-number-${vehicle.id}`}
                        >
                          رقم ملف: {vehicle.fileNumber || vehicle.file_number}
                        </span>
                      )}
                      <span
                        className="px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-900 text-[11px] font-bold border border-slate-300"
                        data-testid={`vehicle-service-type-${vehicle.id}`}
                      >
                        نوع الخدمة: {serviceType}
                      </span>
                      {isUrgent && (
                        <span className="px-2.5 py-0.5 rounded-full bg-red-500/15 text-red-400 text-[11px] font-bold border border-red-500/30">
                          ⚡ {t('common.urgent')}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* صف الدخول / العميل - المنطقة الأساسية */}
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center">
                        <Calendar size={15} className="text-blue-400" />
                      </div>
                      <div>
                        <p className="text-xs font-bold mb-0.5" style={{ color: vehicleText.muted }}>{t('dashboard.entryDateLabel')}</p>
                        <p className="font-bold text-sm" style={{ color: vehicleText.primary }}>
                          {vehicle.entryDate || vehicle.createdAt
                            ? new Date(vehicle.entryDate || vehicle.createdAt).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US')
                            : '-'}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center">
                        <User size={15} className="text-emerald-400" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-bold mb-0.5" style={{ color: vehicleText.muted }}>{t('dashboard.customerLabel')}</p>
                        <p className="font-bold text-sm truncate" style={{ color: vehicleText.primary }}>
                          {vehicle.customerName || '-'}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* شريط نسبة الإنجاز */}
                  <div className="mb-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Clock size={14} className="text-sky-400" />
                        <span className="text-xs font-bold" style={{ color: vehicleText.secondary }}>{t('dashboard.progressLabel')}</span>
                      </div>
                      <span className="font-extrabold text-base text-slate-950">{progress}%</span>
                    </div>
                    <div className="w-full h-2.5 rounded-full bg-slate-900/40 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-l from-blue-500 to-indigo-500 transition-all duration-500"
                        style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
                      />
                    </div>
                  </div>

                  {/* الشريط السفلي: المسؤول */}
                  <div className="mt-2 flex flex-col gap-2">
                    <div
                      className="flex items-center justify-between rounded-[20px] px-4 py-2.5"
                      style={{
                        backgroundColor: '#020617',
                        border: '1px solid rgba(100,116,139,0.2)'
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                          <Wrench size={15} className="text-white" />
                        </div>
                        <div>
                          <p className="text-xs text-slate-400 mb-0.5">{t('dashboard.responsibleTechnicianLabel')}</p>
                          <p className="font-bold text-sm text-slate-100">
                            {vehicle.technicianName || vehicle.technician || t('common.not_specified')}
                          </p>
                        </div>
                      </div>
                      <div className="navigate-btn flex items-center justify-center w-9 h-9 rounded-full bg-blue-500/20 text-blue-400 hover:bg-blue-500 hover:text-white transition-all cursor-pointer border border-blue-500/30"
                        data-testid={`dashboard-open-vehicle-${vehicle.id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          const vehicleId = String(vehicle.id || vehicle.vehicleId || vehicle._id || '').trim();
                          if (!vehicleId) {
                            toast({ title: 'تعذر فتح الملف', description: 'لا يوجد معرف صالح لهذه المركبة.', variant: 'destructive' });
                            return;
                          }
                          navigate(`/vehicle/${encodeURIComponent(vehicleId)}`);
                        }}
                        title={t('dashboard.openVehicleDetails')}
                      >
                        <ArrowRight size={16} />
                      </div>
                    </div>

                    {/* جزء إضافي يظهر عند التوسّع */}
                    {expandedVehicleId === vehicle.id && (
                      <div className="grid grid-cols-2 gap-3 bg-slate-950/60 rounded-2xl px-4 py-3 border border-slate-800/80 mt-2">
                        <div className="flex flex-col gap-1">
                          <span className="text-xs text-slate-400 font-medium">{t('dashboard.vinLabel')}</span>
                          <span className="font-mono text-slate-100 text-sm font-semibold truncate">{vehicle.vin || t('common.not_specified')}</span>
                        </div>
                        <div className="flex flex-col gap-1">
                        <span className="text-xs text-slate-400 font-medium">{t('dashboard.visitsLabel')}</span>
                        <span className="font-bold text-sm text-slate-100" data-testid={`vehicle-visits-count-${vehicle.id}`}>{visitsCount} {t('dashboard.visitUnit')}</span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="text-xs text-slate-400 font-medium">{t('dashboard.lastUpdateLabel')}</span>
                          <span className="text-slate-100 text-sm font-semibold">
                            {vehicle.updatedAt ? new Date(vehicle.updatedAt).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US') : '-'}
                          </span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="text-xs text-slate-400 font-medium">{t('dashboard.estimatedCostLabel')}</span>
                        <span className="text-emerald-400 text-sm font-bold" data-testid={`vehicle-estimated-total-${vehicle.id}`}>
                          {estimatedTotal
                            ? estimatedTotal.toLocaleString(isRTL ? 'ar-SA' : 'en-US') + ` ${t('common.currency')}`
                            : `0 ${t('common.currency')}`}
                        </span>
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-xs text-slate-400 font-medium">نوع الخدمة</span>
                        <span className="text-slate-100 text-sm font-semibold" data-testid={`vehicle-service-type-expanded-${vehicle.id}`}>{serviceType}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Quick Actions Modal */}
        {showQuickActions && selectedVehicle && (
          <VehicleQuickActions
            isOpen={showQuickActions}
            vehicle={selectedVehicle}
            onClose={() => {
              setShowQuickActions(false);
              setSelectedVehicle(null);
            }}
            onStatusUpdate={async (newStatus) => {
              try {
                await vehicleAPI.update(selectedVehicle.id, { status: newStatus });

                // إذا تم التسليم، أغلق أي فاتورة مفتوحة مرتبطة بهذه المركبة
                if (newStatus === 'delivered') {
                  try {
                    const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);
                    const invRes = await axios.get(`${API_URL}/invoices`, { params: { vehicleId: selectedVehicle.id } });
                    const invoices = invRes.data || [];
                    const openInvoice = invoices.find(inv => inv.status !== 'paid' && inv.status !== 'cancelled');
                    if (openInvoice) {
                      await axios.put(`${API_URL}/invoices/${openInvoice.id}`, { status: 'issued' });
                    }
                  } catch (invErr) {
                    console.error('Failed to close invoice on delivery:', invErr);
                  }
                }

                await fetchData();
              } catch (error) {
                console.error('Failed to update vehicle status', error);
              }
            }}
            onDelete={async () => {
              try {
                await vehicleAPI.delete(selectedVehicle.id);
                await fetchData();
              } catch (error) {
                console.error('Failed to delete vehicle', error);
              }
            }}
          />
        )}
      </div>
  );
};

export default Dashboard;