/* eslint-disable react/no-unstable-nested-components */
import React, { useState, useEffect, useRef } from 'react';
import { useToast } from '../hooks/use-toast';
import axios from 'axios';
import { useTheme, themes } from '../contexts/ThemeContext';
import { FontSizeControls } from '../components/FontSizeControls';
import { 
  Building2, 
  Globe, 
  Palette, 
  Database, 
  Save, 
  ChevronLeft,
  Sun,
  Moon,
  Monitor,
  Check,
  Sparkles,
  Settings as SettingsIcon,
  Users as UsersIcon,
  Upload,
  User,
  RotateCcw,
  ShieldAlert,
  FileWarning
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import useStitch from '../hooks/useStitch';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { resolveBackendBase } from '../utils/backendBase';
import WorkshopProfile from './WorkshopProfile';
import UsersManagement from './UsersManagement';
import SettingsImportBlock from '../components/settings/SettingsImportBlock';
import SecuritySettings from '../components/SecuritySettings';
import { api } from '../services/api';

const API_URL = (
  process.env.NODE_ENV === 'production'
    ? '/api'
    : `${resolveBackendBase() || ''}/api`.replace('//api', '/api')
);

const Settings = () => {
  const { t, i18n } = useTranslation();
  const isRTL = i18n.language === 'ar';
  const { toast } = useToast();
  const navigate = useNavigate();
  const { themeName, changeTheme, isDark } = useTheme();
  const { loading: stitchLoading, error: stitchError, result: stitchResult, generateUI, getHistory, resetError } = useStitch();

  // 🧭 Tabs: general | profile | users | import — settable via ?tab=... in URL
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') || 'general';
  const [activeTab, setActiveTab] = useState(initialTab);
  const switchTab = (next) => {
    setActiveTab(next);
    setSearchParams(next === 'general' ? {} : { tab: next });
  };
  const TABS = [
    { id: 'general', label: 'عام', icon: SettingsIcon, testid: 'settings-tab-general' },
    { id: 'profile', label: 'الملف الشخصي', icon: User, testid: 'settings-tab-profile' },
    { id: 'users', label: 'المستخدمون', icon: UsersIcon, testid: 'settings-tab-users' },
    { id: 'import', label: 'استيراد البيانات', icon: Upload, testid: 'settings-tab-import' },
    { id: 'financial-reset', label: 'بدء مالي جديد', icon: RotateCcw, testid: 'settings-tab-financial-reset' },
  ];

  const [loading, setLoading] = useState(true);
  const [sidebarPrefs, setSidebarPrefs] = useState({
    collapsed: false,
    hidden: false,
  });
  const [settings, setSettings] = useState({
    workshopName: 'ورشتي',
    workshopPhone: '',
    workshopEmail: '',
    workshopAddress: '',
    currency: 'SAR',
    taxEnabled: false,
    taxRate: 15,
    language: 'ar',
    themeName: 'dark'
  });
  const [stitchForm, setStitchForm] = useState({
    prompt: '',
    designStyle: 'modern',
    colorScheme: '',
    uiScope: 'section'
  });
  const [stitchHistory, setStitchHistory] = useState([]);
  const [showStitchCode, setShowStitchCode] = useState(false);
  const [resetDryRun, setResetDryRun] = useState(null);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetConfirmation, setResetConfirmation] = useState('');
  const resetConfirmationText = 'أؤكد بدء مالي جديد وترحيل الذمم';
  const themeRequestRef = useRef(0);
  const stitchSuggestions = [
    {
      id: 'full-dashboard',
      label: 'لوحة مالية كاملة',
      prompt: 'صمّم لوحة تحكم مالية كاملة للورشة تشمل بطاقات KPIs ورسوم بيانية وقائمة معاملات.',
      scope: 'full',
    },
    {
      id: 'invoice-page',
      label: 'صفحة فواتير كاملة',
      prompt: 'صمّم صفحة فواتير كاملة مع جدول الفواتير وفلاتر وبطاقات إجمالي.',
      scope: 'full',
    },
    {
      id: 'login-card',
      label: 'بطاقة تسجيل دخول',
      prompt: 'صمّم بطاقة تسجيل دخول أنيقة مع حقول البريد وكلمة المرور وزر أساسي.',
      scope: 'section',
    },
  ];

  useEffect(() => { fetchSettings(); }, []);

  useEffect(() => {
    setSettings((prev) => (prev.themeName === themeName ? prev : { ...prev, themeName: themeName || 'dark' }));
  }, [themeName]);

  useEffect(() => {
    try {
      setSidebarPrefs({
        collapsed: localStorage.getItem('ui.sidebarCollapsed') === 'true',
        hidden: localStorage.getItem('ui.sidebarHidden') === 'true',
      });
    } catch (error) {
      setSidebarPrefs({ collapsed: false, hidden: false });
    }
  }, []);

  useEffect(() => {
    const loadHistory = async () => {
      const history = await getHistory();
      setStitchHistory(Array.isArray(history) ? history : []);
    };
    loadHistory();
  }, [getHistory]);

  const fetchSettings = async () => {
    try {
      const response = await axios.get(`${API_URL}/settings`);
      const localTheme = localStorage.getItem('theme');
      const backendTheme = response?.data?.themeName;
      const resolvedTheme = localTheme || backendTheme || themeName || 'dark';

      if (resolvedTheme !== themeName) {
        changeTheme(resolvedTheme);
      }

      setSettings({
        ...response.data,
        language: response.data.language || 'ar',
        themeName: resolvedTheme
      });
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleThemeChange = async (newTheme) => {
    const nextSettings = { ...settings, themeName: newTheme };
    setSettings(nextSettings);
    changeTheme(newTheme);

    // Persist theme immediately to prevent fast reverts between sessions/environments.
    const reqId = Date.now();
    themeRequestRef.current = reqId;
    try {
      await axios.post(`${API_URL}/settings`, nextSettings);
      if (themeRequestRef.current !== reqId) return;
    } catch (error) {
      // Keep applied theme locally even if backend save fails temporarily.
      console.error('theme_save_failed', error);
    }
  };

  const updateSidebarPrefs = (updater) => {
    setSidebarPrefs((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      try {
        localStorage.setItem('ui.sidebarCollapsed', String(next.collapsed));
        localStorage.setItem('ui.sidebarHidden', String(next.hidden));
      } catch (error) {
        return next;
      }
      window.dispatchEvent(
        new CustomEvent('ui-sidebar-preferences-changed', { detail: next })
      );
      return next;
    });
  };

  const saveSettings = async () => {
    try {
      setLoading(true);
      await axios.post(`${API_URL}/settings`, settings);
      localStorage.setItem('language', settings.language);
      localStorage.setItem('theme', settings.themeName);
      
      toast({ title: t('common.success'), description: t('messages.success_saved') });
    } catch (error) {
      toast({ title: t('common.error'), description: t('messages.error_occurred'), variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateStitch = async () => {
    resetError();
    if ((stitchForm.prompt || '').trim().length < 10) {
      toast({ title: 'تنبيه', description: 'وصف الواجهة يجب أن يكون 10 أحرف على الأقل', variant: 'destructive' });
      return;
    }
    try {
      await generateUI(
        stitchForm.prompt,
        stitchForm.designStyle,
        stitchForm.colorScheme,
        stitchForm.uiScope
      );
      const history = await getHistory();
      setStitchHistory(Array.isArray(history) ? history : []);
    } catch (error) {
      console.error(error);
    }
  };

  const handleCopyStitchPrompt = async () => {
    const text = stitchResult?.prompt || stitchForm.prompt;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast({ title: 'تم النسخ', description: 'تم نسخ وصف الواجهة' });
    } catch (error) {
      toast({ title: 'خطأ', description: 'تعذر نسخ النص', variant: 'destructive' });
    }
  };

  const handleOpenStitch = () => {
    const url = stitchResult?.stitch_url || 'https://stitch.withgoogle.com';
    window.open(url, '_blank');
  };

  const Section = ({ title, icon: Icon, children }) => (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-3 px-1">
        <Icon size={18} className="theme-text-secondary" style={{ color: 'var(--text-muted)' }} />
        <h2 className="text-sm font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{title}</h2>
      </div>
      <div className="rounded-xl border overflow-hidden divide-y shadow-sm" 
           style={{ 
             backgroundColor: 'var(--bg-surface)', 
             borderColor: 'var(--border-color)',
             divideColor: 'var(--border-light)'
           }}>
        {children}
      </div>
    </div>
  );

  const Row = ({ label, children }) => (
    <div className="flex items-center justify-between p-4 min-h-[3.5rem]"
         style={{ borderColor: 'var(--border-light)' }}>
      <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{label}</span>
      <div className="flex items-center gap-2">
        {children}
      </div>
    </div>
  );

  // Theme preview cards
  const ThemeCard = ({ themeKey, theme }) => {
    const isSelected = settings.themeName === themeKey;
    const isDarkTheme = theme.mode === 'dark';
    
    return (
      <button
        onClick={() => handleThemeChange(themeKey)}
        data-testid={`theme-card-${themeKey}`}
        className={`relative flex flex-col items-center p-4 rounded-xl border-2 transition-all duration-200 ${
          isSelected 
            ? 'border-blue-500 ring-2 ring-blue-500/20' 
            : 'border-transparent hover:border-gray-300'
        }`}
        style={{ 
          backgroundColor: isDarkTheme ? '#1e293b' : '#ffffff',
          minWidth: '120px'
        }}
      >
        {/* Theme preview */}
        <div 
          className="w-full h-20 rounded-lg mb-3 overflow-hidden flex"
          style={{ 
            backgroundColor: theme.background,
            border: `1px solid ${theme.border}`
          }}
        >
          {/* Sidebar preview */}
          <div 
            className="w-1/4 h-full"
            style={{ backgroundColor: theme.sidebarBg }}
          >
            <div 
              className="w-3/4 h-2 mx-auto mt-3 rounded"
              style={{ backgroundColor: theme.sidebarActive }}
            />
            <div 
              className="w-1/2 h-1.5 mx-auto mt-2 rounded opacity-50"
              style={{ backgroundColor: theme.sidebarText }}
            />
            <div 
              className="w-1/2 h-1.5 mx-auto mt-1 rounded opacity-50"
              style={{ backgroundColor: theme.sidebarText }}
            />
          </div>
          {/* Content preview */}
          <div className="flex-1 p-2">
            <div 
              className="w-full h-4 rounded"
              style={{ backgroundColor: theme.card }}
            />
            <div className="flex gap-1 mt-1">
              <div 
                className="flex-1 h-6 rounded"
                style={{ backgroundColor: theme.card }}
              />
              <div 
                className="flex-1 h-6 rounded"
                style={{ backgroundColor: theme.card }}
              />
            </div>
          </div>
        </div>
        
        {/* Theme icon */}
        <div className={`p-2 rounded-full mb-2 ${isDarkTheme ? 'bg-gray-700' : 'bg-gray-100'}`}>
          {themeKey === 'dark' && <Moon size={18} className="text-blue-400" />}
          {themeKey === 'light' && <Sun size={18} className="text-amber-500" />}
          {themeKey === 'dashPro' && <Monitor size={18} className="text-indigo-500" />}
        </div>
        
        {/* Theme name */}
        <span className={`text-sm font-medium ${isDarkTheme ? 'text-white' : 'text-gray-900'}`}>
          {theme.name}
        </span>
        
        {/* Selected indicator */}
        {isSelected && (
          <div className="absolute top-2 left-2 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center">
            <Check size={12} className="text-white" />
          </div>
        )}
      </button>
    );
  };

  const runFinancialResetDryRun = async () => {
    setResetLoading(true);
    try {
      const response = await api.get('/finance/reset/dry-run', {
        params: { workshop_id: 'finmodule-sync' },
        timeout: 20000,
      });
      const payload = response?.data?.data;
      setResetDryRun(payload);
      setResetConfirmation('');
      toast({ title: 'تم إنشاء Dry-run', description: payload?.can_execute ? 'الفحص ناجح ويمكن المتابعة بعد التأكيد.' : 'الفحص يحتاج مراجعة قبل التنفيذ.' });
    } catch (error) {
      const message = error?.response?.data?.detail?.msg || error?.response?.data?.detail || error.message;
      toast({ title: 'فشل Dry-run', description: String(message), variant: 'destructive' });
    } finally {
      setResetLoading(false);
    }
  };

  const executeFinancialReset = async () => {
    if (!resetDryRun?.generated_at || resetConfirmation !== resetConfirmationText) return;
    setResetLoading(true);
    try {
      const response = await api.post('/finance/reset/execute', {
        workshop_id: 'finmodule-sync',
        dry_run_token: resetDryRun.generated_at,
        confirmation_text: resetConfirmation,
      }, { timeout: 60000 });
      toast({ title: 'تم بدء مالي جديد', description: `Reset ID: ${response?.data?.data?.reset_id || 'تم التنفيذ'}` });
      setResetDryRun(null);
      setResetConfirmation('');
    } catch (error) {
      const message = error?.response?.data?.detail?.msg || error?.response?.data?.detail || error.message;
      toast({ title: 'تم إيقاف التنفيذ', description: String(message), variant: 'destructive' });
    } finally {
      setResetLoading(false);
    }
  };

  return (
    <div 
      className={`max-w-4xl mx-auto pb-20 ${isRTL ? 'rtl' : 'ltr'}`} 
      dir={isRTL ? 'rtl' : 'ltr'}
      style={{ minHeight: '100vh' }}
    >
      <div className="flex items-center justify-between mb-6 pt-4 flex-wrap gap-3">
        <h1 className="text-3xl font-bold" style={{ color: 'var(--text-primary)' }}>
          {t('settings.title')}
        </h1>
        {activeTab === 'general' ? (
          <button 
            onClick={saveSettings}
            data-testid="settings-save-button"
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl font-medium transition-all"
            style={{ 
              backgroundColor: 'var(--accent-primary)', 
              color: '#ffffff'
            }}
          >
            <Save size={18} />
            <span>{loading ? t('settings.saving') : t('settings.save_changes')}</span>
          </button>
        ) : null}
      </div>

      {/* 🧭 Tabs navigation */}
      <div
        className="mb-6 flex flex-wrap gap-1 rounded-2xl p-1.5 border"
        style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}
        data-testid="settings-tabs-bar"
      >
        {TABS.map(({ id, label, icon: Icon, testid }) => (
          <button
            key={id}
            type="button"
            onClick={() => switchTab(id)}
            data-testid={testid}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all flex-1 min-w-[120px] justify-center ${
              activeTab === id
                ? 'shadow-md'
                : 'opacity-70 hover:opacity-100'
            }`}
            style={
              activeTab === id
                ? { backgroundColor: 'var(--accent-primary)', color: '#ffffff' }
                : { color: 'var(--text-primary)' }
            }
          >
            <Icon size={16} />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* 🪟 Tab panels */}
      {activeTab === 'profile' ? (
        <div data-testid="settings-panel-profile" className="space-y-6">
          <SecuritySettings />
          <WorkshopProfile />
        </div>
      ) : null}

      {activeTab === 'users' ? (
        <div data-testid="settings-panel-users">
          <UsersManagement />
        </div>
      ) : null}

      {activeTab === 'import' ? (
        <div data-testid="settings-panel-import" className="rounded-2xl border p-4" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}>
          <h2 className="text-lg font-bold mb-3" style={{ color: 'var(--text-primary)' }}>
            <Upload size={18} className="inline mb-0.5 ml-1" />
            استيراد البيانات
          </h2>
          <p className="text-xs mb-4" style={{ color: 'var(--text-secondary)' }}>
            ارفع ملفات CSV أو XLSX للعملاء أو الخدمات أو قطع الغيار. سيتم التحقق من البيانات قبل الإدراج.
          </p>
          <SettingsImportBlock />
        </div>
      ) : null}

      {activeTab === 'financial-reset' ? (
        <div data-testid="settings-panel-financial-reset" className="space-y-5">
          <div className="rounded-2xl border p-5" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}>
            <div className="flex items-start gap-3">
              <div className="rounded-xl bg-amber-500/15 p-3 text-amber-300">
                <ShieldAlert size={24} />
              </div>
              <div className="space-y-2">
                <h2 className="text-xl font-black" style={{ color: 'var(--text-primary)' }}>بدء مالي جديد</h2>
                <p className="text-sm leading-7" style={{ color: 'var(--text-secondary)' }}>
                  إعادة ضبط الحركة المالية والبدء من نقطة نظيفة مع الاحتفاظ بالذمم المستحقة فقط، مع حفظ Snapshot كامل وأرشفة الحركة المالية القديمة بدون Hard Delete.
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <button
              type="button"
              onClick={runFinancialResetDryRun}
              disabled={resetLoading}
              data-testid="financial-reset-dry-run-button"
              className="rounded-2xl border p-4 text-right transition-all hover:translate-y-[-1px] disabled:opacity-50"
              style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}
            >
              <FileWarning size={22} className="mb-2 text-cyan-300" />
              <div className="font-black">تشغيل Dry-run</div>
              <div className="mt-1 text-xs" style={{ color: 'var(--text-secondary)' }}>يعرض ما سيحدث بدون تعديل بيانات.</div>
            </button>
            <div className="rounded-2xl border p-4 md:col-span-2" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }} data-testid="financial-reset-guard-card">
              <div className="font-bold mb-2" style={{ color: 'var(--text-primary)' }}>حماية التنفيذ</div>
              <ul className="list-disc space-y-1 pr-5 text-sm" style={{ color: 'var(--text-secondary)' }}>
                <li>Admin فقط من السيرفر.</li>
                <li>Snapshot كامل قبل أي تغيير.</li>
                <li>BLOCK إذا اختلف إجمالي الذمم عن Opening Receivables.</li>
                <li>منع تكرار نفس عملية Reset وإنشاء Opening Balance مرتين.</li>
              </ul>
            </div>
          </div>

          {resetDryRun ? (
            <div className="rounded-2xl border p-5 space-y-4" style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }} data-testid="financial-reset-dry-run-result">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-lg font-black" style={{ color: 'var(--text-primary)' }}>نتيجة Dry-run</h3>
                <span className={`rounded-full px-3 py-1 text-xs font-black ${resetDryRun.can_execute ? 'bg-emerald-500/20 text-emerald-200' : 'bg-red-500/20 text-red-200'}`} data-testid="financial-reset-can-execute-badge">
                  {resetDryRun.can_execute ? 'جاهز للتنفيذ' : 'محظور حتى المراجعة'}
                </span>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ['المركبات النشطة', resetDryRun.summary?.active_vehicle_count],
                  ['مركبات عليها ذمم', resetDryRun.summary?.vehicles_with_receivables],
                  ['إجمالي الذمم قبل Reset', `${Number(resetDryRun.summary?.total_receivables_before_reset || 0).toLocaleString()} ر.س`],
                  ['Opening Receivables بعد Reset', `${Number(resetDryRun.summary?.total_opening_receivables_after_reset || 0).toLocaleString()} ر.س`],
                  ['مركبات رصيدها صفر', resetDryRun.summary?.vehicles_zero_balance],
                  ['Needs Review', resetDryRun.needs_review?.length || 0],
                  ['قيود ستؤرشف', resetDryRun.summary?.journal_entries_to_archive],
                  ['عمليات ستؤرشف', resetDryRun.summary?.operations_to_archive],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl border p-3" style={{ borderColor: 'var(--border-color)' }} data-testid={`financial-reset-summary-${label.replace(/\s+/g, '-')}`}>
                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{label}</div>
                    <div className="mt-1 text-lg font-black" style={{ color: 'var(--text-primary)' }}>{value}</div>
                  </div>
                ))}
              </div>

              {!resetDryRun.can_execute ? (
                <div className="rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100" data-testid="financial-reset-blocked-reasons">
                  أسباب الإيقاف: {(resetDryRun.blocked_reasons || []).join('، ') || 'غير محدد'}
                </div>
              ) : null}

              <div className="space-y-2">
                <label className="block text-sm font-bold" style={{ color: 'var(--text-primary)' }}>عبارة التأكيد</label>
                <input
                  value={resetConfirmation}
                  onChange={(event) => setResetConfirmation(event.target.value)}
                  data-testid="financial-reset-confirmation-input"
                  className="w-full rounded-xl border bg-transparent p-3 text-sm outline-none"
                  style={{ borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}
                  placeholder={resetConfirmationText}
                />
                <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>اكتب بالضبط: {resetConfirmationText}</div>
              </div>

              <button
                type="button"
                onClick={executeFinancialReset}
                disabled={resetLoading || !resetDryRun.can_execute || resetConfirmation !== resetConfirmationText}
                data-testid="financial-reset-execute-button"
                className="w-full rounded-2xl bg-red-600 px-4 py-3 font-black text-white transition-all hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                تنفيذ بدء مالي جديد
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {activeTab !== 'general' ? null : (
      <>
      {/* Theme Selection Section */}
      <Section title="المظهر والثيم" icon={Palette}>
        <div className="p-4">
          <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
            اختر الثيم المناسب للواجهة
          </p>
          <div className="flex flex-wrap gap-4 justify-center sm:justify-start">
            {Object.entries(themes).map(([key, theme]) => (
              <ThemeCard key={key} themeKey={key} theme={theme} />
            ))}
          </div>
        </div>
      </Section>

      <Section title="التحكم بالعرض" icon={Monitor}>
        <Row label="حجم الخط">
          <FontSizeControls compact testIdPrefix="settings-font-size" />
        </Row>
        <Row label="عرض القائمة الجانبية">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => updateSidebarPrefs((prev) => ({ ...prev, hidden: false }))}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
                !sidebarPrefs.hidden
                  ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/25'
                  : 'border border-white/10 text-slate-200 hover:bg-white/10'
              }`}
              data-testid="settings-sidebar-show-button"
            >
              إظهار
            </button>
            <button
              type="button"
              onClick={() => updateSidebarPrefs((prev) => ({ ...prev, hidden: true }))}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
                sidebarPrefs.hidden
                  ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/25'
                  : 'border border-white/10 text-slate-200 hover:bg-white/10'
              }`}
              data-testid="settings-sidebar-hide-button"
            >
              إخفاء
            </button>
          </div>
        </Row>
        <Row label="حجم القائمة الجانبية">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => updateSidebarPrefs((prev) => ({ ...prev, hidden: false, collapsed: false }))}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
                !sidebarPrefs.collapsed && !sidebarPrefs.hidden
                  ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/25'
                  : 'border border-white/10 text-slate-200 hover:bg-white/10'
              }`}
              data-testid="settings-sidebar-expanded-button"
            >
              موسّعة
            </button>
            <button
              type="button"
              onClick={() => updateSidebarPrefs((prev) => ({ ...prev, hidden: false, collapsed: true }))}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all ${
                sidebarPrefs.collapsed && !sidebarPrefs.hidden
                  ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/25'
                  : 'border border-white/10 text-slate-200 hover:bg-white/10'
              }`}
              data-testid="settings-sidebar-collapsed-button"
            >
              مصغّرة
            </button>
          </div>
        </Row>
      </Section>

      <Section title="توليد واجهة Stitch" icon={Sparkles}>
        <div className="p-4 space-y-4" data-testid="stitch-section">
          <div className="space-y-2">
            <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>وصف الواجهة</label>
            <textarea
              className="w-full rounded-xl border bg-transparent p-3 text-sm outline-none"
              style={{ borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}
              rows={4}
              value={stitchForm.prompt}
              onChange={(e) => setStitchForm({ ...stitchForm, prompt: e.target.value })}
              placeholder="مثال: صفحة تسجيل دخول حديثة مع حقل بريد وكلمة مرور"
              data-testid="stitch-prompt-input"
            />
          </div>
          <div className="flex flex-wrap gap-2" data-testid="stitch-suggestions">
            {stitchSuggestions.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() =>
                  setStitchForm((prev) => ({
                    ...prev,
                    prompt: item.prompt,
                    uiScope: item.scope || prev.uiScope,
                  }))
                }
                className="px-3 py-1.5 rounded-full border text-xs font-medium"
                style={{ borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}
                data-testid={`stitch-suggestion-${item.id}`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>نمط التصميم</label>
              <select
                className="w-full rounded-xl border bg-transparent p-2 text-sm outline-none"
                style={{ borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}
                value={stitchForm.designStyle}
                onChange={(e) => setStitchForm({ ...stitchForm, designStyle: e.target.value })}
                data-testid="stitch-style-select"
              >
                <option value="modern">حديث</option>
                <option value="minimal">مختصر</option>
                <option value="classic">كلاسيكي</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>نطاق التوليد</label>
              <select
                className="w-full rounded-xl border bg-transparent p-2 text-sm outline-none"
                style={{ borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}
                value={stitchForm.uiScope}
                onChange={(e) => setStitchForm({ ...stitchForm, uiScope: e.target.value })}
                data-testid="stitch-scope-select"
              >
                <option value="section">قسم واحد</option>
                <option value="full">واجهة كاملة</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>لوحة الألوان</label>
              <input
                className="w-full rounded-xl border bg-transparent p-2 text-sm outline-none"
                style={{ borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}
                value={stitchForm.colorScheme}
                onChange={(e) => setStitchForm({ ...stitchForm, colorScheme: e.target.value })}
                placeholder="أزرق فاتح، داكن..."
                data-testid="stitch-color-input"
              />
            </div>
          </div>

          {stitchError && (
            <div className="rounded-xl border p-3 text-sm" style={{ borderColor: '#f87171', color: '#b91c1c' }} data-testid="stitch-error-message">
              {stitchError}
            </div>
          )}

          <button
            onClick={handleGenerateStitch}
            disabled={stitchLoading}
            className="w-full rounded-xl py-2 text-sm font-medium transition-all"
            style={{ backgroundColor: 'var(--accent-primary)', color: '#ffffff' }}
            data-testid="stitch-generate-button"
          >
            {stitchLoading ? 'جاري التوليد...' : 'توليد واجهة'}
          </button>

          {stitchResult && (
            <div className="rounded-xl border p-4 space-y-3" style={{ borderColor: 'var(--border-color)' }} data-testid="stitch-result-card">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>تم توليد الواجهة</p>
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{stitchResult.status || 'completed'}</p>
                </div>
                {stitchResult.figma_url && (
                  <button
                    onClick={() => window.open(stitchResult.figma_url, '_blank')}
                    className="text-xs font-medium underline"
                    style={{ color: 'var(--accent-primary)' }}
                    data-testid="stitch-figma-link"
                  >
                    فتح في Figma
                  </button>
                )}
              </div>
              {stitchResult.status === 'manual_required' && (
                <div className="rounded-lg border p-3 text-xs" style={{ borderColor: 'var(--border-color)', color: 'var(--text-secondary)' }} data-testid="stitch-manual-hint">
                  <p className="mb-2">لا توجد API عامة لـ Stitch حالياً. استخدم الواجهة اليدوية ثم الصق الناتج هنا.</p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={handleCopyStitchPrompt}
                      className="px-3 py-1.5 rounded-full border text-xs font-medium"
                      style={{ borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}
                      data-testid="stitch-copy-prompt-button"
                    >
                      نسخ الوصف
                    </button>
                    <button
                      type="button"
                      onClick={handleOpenStitch}
                      className="px-3 py-1.5 rounded-full border text-xs font-medium"
                      style={{ borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}
                      data-testid="stitch-open-button"
                    >
                      فتح Stitch
                    </button>
                  </div>
                </div>
              )}
              {stitchResult.generated_code && (
                <div className="space-y-2">
                  <button
                    onClick={() => setShowStitchCode(!showStitchCode)}
                    className="text-xs font-medium underline"
                    style={{ color: 'var(--accent-primary)' }}
                    data-testid="stitch-toggle-code-button"
                  >
                    {showStitchCode ? 'إخفاء الكود' : 'عرض الكود'}
                  </button>
                  {showStitchCode && (
                    <pre className="max-h-56 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100" data-testid="stitch-code-block">
                      {stitchResult.generated_code}
                    </pre>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="space-y-2" data-testid="stitch-history-list">
            <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>سجل التوليد</p>
            {stitchHistory.length === 0 ? (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>لا يوجد توليدات سابقة بعد.</p>
            ) : (
              <div className="space-y-2">
                {stitchHistory.slice(0, 5).map((item) => (
                  <div key={item.id} className="rounded-lg border p-3" style={{ borderColor: 'var(--border-light)' }} data-testid={`stitch-history-item-${item.id}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs" style={{ color: 'var(--text-primary)' }}>{item.prompt}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--bg-card)', color: 'var(--text-muted)' }}>{item.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </Section>

      <Section title={t('settings.workshop_info')} icon={Building2}>
        <div className="rounded-xl border p-4" style={{ borderColor: 'var(--border-light)', background: 'var(--bg-card)' }} data-testid="settings-workshop-info-note">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            تم نقل بيانات الورشة إلى صفحة «ملف الورشة» لتجنب التكرار وضمان توحيد البيانات.
          </p>
          <button
            onClick={() => navigate('/profile')}
            className="mt-3 inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium"
            style={{ borderColor: 'var(--border-light)', color: 'var(--text-primary)' }}
            data-testid="settings-open-workshop-profile"
          >
            فتح ملف الورشة
          </button>
        </div>
      </Section>

      <Section title={t('settings.system_appearance')} icon={Globe}>
        <Row label={t('settings.language')}>
          <select 
            className="bg-transparent outline-none"
            style={{ color: 'var(--text-secondary)' }}
            value={settings.language}
            onChange={e => setSettings({...settings, language: e.target.value})}
            data-testid="settings-language-select"
          >
            <option value="ar">{t('settings.arabic')}</option>
            <option value="en">{t('settings.english')}</option>
          </select>
          <ChevronLeft size={16} style={{ color: 'var(--text-muted)' }} />
        </Row>
        <Row label={t('settings.currency')}>
          <select 
            className="bg-transparent outline-none"
            style={{ color: 'var(--text-secondary)' }}
            value={settings.currency}
            onChange={e => setSettings({...settings, currency: e.target.value})}
            data-testid="settings-currency-select"
          >
            <option value="SAR">ريال سعودي (SAR)</option>
            <option value="USD">دولار أمريكي (USD)</option>
          </select>
          <ChevronLeft size={16} style={{ color: 'var(--text-muted)' }} />
        </Row>
      </Section>

      <Section title="الضرائب والرسوم" icon={Palette}>
        <Row label="تفعيل الضريبة">
          <label className="relative inline-flex items-center cursor-pointer">
            <input 
              type="checkbox" 
              className="sr-only peer"
              checked={settings.taxEnabled}
              onChange={e => setSettings({...settings, taxEnabled: e.target.checked})}
              data-testid="settings-tax-toggle"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
          </label>
        </Row>
        {settings.taxEnabled && (
          <Row label="نسبة الضريبة (%)">
            <input 
              type="number"
              className="text-left bg-transparent outline-none w-20"
              style={{ color: 'var(--text-secondary)' }}
              value={settings.taxRate}
              onChange={e => setSettings({...settings, taxRate: parseFloat(e.target.value)})}
              data-testid="settings-tax-rate-input"
            />
          </Row>
        )}
      </Section>

      <Section title="النسخ الاحتياطي" icon={Database}>
        <Row label="Google Drive">
          <button 
            onClick={async () => {
              try {
                await axios.post(`${API_URL}/admin/backup/drive`);
                toast({ title: 'تم', description: 'تم النسخ الاحتياطي بنجاح' });
              } catch (e) {
                toast({ title: 'خطأ', description: 'فشل النسخ الاحتياطي', variant: 'destructive' });
              }
            }}
            className="text-sm font-medium hover:underline"
            style={{ color: 'var(--accent-primary)' }}
            data-testid="settings-backup-button"
          >
            نسخ الآن
          </button>
        </Row>
      </Section>
      </>
      )}
    </div>
  );
};

export default Settings;