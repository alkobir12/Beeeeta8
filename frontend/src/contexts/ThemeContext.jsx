import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

const FONT_SIZE_PRESETS = {
  small: { label: 'A-', px: '18px' },
  medium: { label: 'A', px: '20px' },
  large: { label: 'A+', px: '22px' },
};

// تعريف الثيمات المتاحة
export const themes = {
  // الثيم الداكن (الحالي)
  dark: {
    name: 'داكن',
    nameEn: 'Dark',
    mode: 'dark',
    // الألوان الأساسية
    primary: '#3b82f6',
    primaryLight: '#60a5fa',
    primaryDark: '#2563eb',
    secondary: '#64748b',
    accent: '#06b6d4',
    // الخلفيات
    background: '#0f172a',
    backgroundSecondary: '#1e293b',
    surface: '#1e293b',
    surfaceHover: '#334155',
    card: 'rgba(30, 41, 59, 0.8)',
    cardHover: 'rgba(51, 65, 85, 0.9)',
    // النصوص
    text: '#f1f5f9',
    textSecondary: '#94a3b8',
    textMuted: '#64748b',
    // الحدود
    border: '#334155',
    borderLight: '#475569',
    divider: 'rgba(71, 85, 105, 0.5)',
    // ألوان الحالة
    success: '#10b981',
    successLight: 'rgba(16, 185, 129, 0.15)',
    warning: '#f59e0b',
    warningLight: 'rgba(245, 158, 11, 0.15)',
    error: '#ef4444',
    errorLight: 'rgba(239, 68, 68, 0.15)',
    info: '#3b82f6',
    infoLight: 'rgba(59, 130, 246, 0.15)',
    // Sidebar
    sidebarBg: '#0f172a',
    sidebarText: '#94a3b8',
    sidebarActive: '#3b82f6',
    sidebarActiveBg: 'rgba(59, 130, 246, 0.15)',
    sidebarHover: 'rgba(59, 130, 246, 0.1)',
    // الإدخالات
    inputBg: 'rgba(30, 41, 59, 0.5)',
    inputBorder: '#334155',
    inputFocus: '#3b82f6',
    // التدرجات
    gradientPrimary: 'linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)',
    gradientSuccess: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
    gradientCard: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.9) 100%)',
    // الظلال
    shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
    shadowLg: '0 10px 15px -3px rgba(0, 0, 0, 0.3)',
    shadowGlow: '0 0 20px rgba(59, 130, 246, 0.2)',
  },

  // الثيم الفاتح الجديد (مستوحى من الصور)
  light: {
    name: 'فاتح',
    nameEn: 'Light',
    mode: 'light',
    // الألوان الأساسية
    primary: '#2563eb',
    primaryLight: '#3b82f6',
    primaryDark: '#1d4ed8',
    secondary: '#64748b',
    accent: '#0891b2',
    // الخلفيات
    background: '#f8fafc',
    backgroundSecondary: '#f1f5f9',
    surface: '#ffffff',
    surfaceHover: '#f8fafc',
    card: '#ffffff',
    cardHover: '#f8fafc',
    // النصوص
    text: '#0f172a',
    textSecondary: '#475569',
    textMuted: '#94a3b8',
    // الحدود
    border: '#e2e8f0',
    borderLight: '#f1f5f9',
    divider: 'rgba(226, 232, 240, 0.8)',
    // ألوان الحالة
    success: '#10b981',
    successLight: 'rgba(16, 185, 129, 0.1)',
    warning: '#f59e0b',
    warningLight: 'rgba(245, 158, 11, 0.1)',
    error: '#ef4444',
    errorLight: 'rgba(239, 68, 68, 0.1)',
    info: '#3b82f6',
    infoLight: 'rgba(59, 130, 246, 0.1)',
    // Sidebar
    sidebarBg: '#ffffff',
    sidebarText: '#475569',
    sidebarActive: '#2563eb',
    sidebarActiveBg: 'rgba(37, 99, 235, 0.1)',
    sidebarHover: 'rgba(37, 99, 235, 0.05)',
    // الإدخالات
    inputBg: '#ffffff',
    inputBorder: '#e2e8f0',
    inputFocus: '#2563eb',
    // التدرجات
    gradientPrimary: 'linear-gradient(135deg, #2563eb 0%, #0891b2 100%)',
    gradientSuccess: 'linear-gradient(135deg, #10b981 0%, #0891b2 100%)',
    gradientCard: 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)',
    // الظلال
    shadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
    shadowLg: '0 10px 15px -3px rgba(0, 0, 0, 0.08)',
    shadowGlow: '0 0 20px rgba(37, 99, 235, 0.1)',
  },

  // الثيم الأزرق الداكن (داش برو)
  dashPro: {
    name: 'داش برو',
    nameEn: 'Dash Pro',
    mode: 'light',
    // الألوان الأساسية
    primary: '#1e40af',
    primaryLight: '#3b82f6',
    primaryDark: '#1e3a8a',
    secondary: '#64748b',
    accent: '#0ea5e9',
    // الخلفيات
    background: '#f8fafc',
    backgroundSecondary: '#eff6ff',
    surface: '#ffffff',
    surfaceHover: '#f8fafc',
    card: '#ffffff',
    cardHover: '#f8fafc',
    // النصوص
    text: '#1e293b',
    textSecondary: '#475569',
    textMuted: '#94a3b8',
    // الحدود
    border: '#e2e8f0',
    borderLight: '#f1f5f9',
    divider: 'rgba(226, 232, 240, 0.8)',
    // ألوان الحالة
    success: '#10b981',
    successLight: 'rgba(16, 185, 129, 0.08)',
    warning: '#f59e0b',
    warningLight: 'rgba(245, 158, 11, 0.08)',
    error: '#ef4444',
    errorLight: 'rgba(239, 68, 68, 0.08)',
    info: '#3b82f6',
    infoLight: 'rgba(59, 130, 246, 0.08)',
    // Sidebar (داكن على اليمين)
    sidebarBg: '#1e293b',
    sidebarText: '#cbd5e1',
    sidebarActive: '#3b82f6',
    sidebarActiveBg: 'rgba(59, 130, 246, 0.2)',
    sidebarHover: 'rgba(59, 130, 246, 0.1)',
    // الإدخالات
    inputBg: '#ffffff',
    inputBorder: '#e2e8f0',
    inputFocus: '#1e40af',
    // التدرجات
    gradientPrimary: 'linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)',
    gradientSuccess: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
    gradientCard: 'linear-gradient(135deg, #ffffff 0%, #eff6ff 100%)',
    // الظلال
    shadow: '0 1px 3px 0 rgba(0, 0, 0, 0.08)',
    shadowLg: '0 10px 15px -3px rgba(0, 0, 0, 0.06)',
    shadowGlow: '0 0 20px rgba(30, 64, 175, 0.1)',
  },
};

// تحديد الثيم الأولي بشكل متناسق مع الـ inline script في index.html (يمنع FOWT)
function getInitialTheme() {
  try {
    const fromHtml = document.documentElement.getAttribute('data-theme');
    if (fromHtml && themes[fromHtml]) return fromHtml;
    const fromStorage = localStorage.getItem('theme');
    if (fromStorage && themes[fromStorage]) return fromStorage;
  } catch (e) {
    // localStorage may be unavailable
  }
  return 'dashPro';
}

export const ThemeProvider = ({ children }) => {
  const [currentTheme, setCurrentTheme] = useState(getInitialTheme);
  const [fontSize, setFontSize] = useState(() => localStorage.getItem('fontSize') || 'large');
  const [layoutMode, setLayoutMode] = useState(() => localStorage.getItem('layoutMode') || 'comfortable');

  const applyTheme = (themeName) => {
    const theme = themes[themeName] || themes.dark;
    const root = document.documentElement;
    
    // تطبيق متغيرات CSS
    Object.entries(theme).forEach(([key, value]) => {
      if (key !== 'name' && key !== 'nameEn' && key !== 'mode') {
        // تحويل camelCase إلى kebab-case
        const cssVar = key.replace(/([A-Z])/g, '-$1').toLowerCase();
        root.style.setProperty(`--theme-${cssVar}`, value);
      }
    });

    // تطبيق الوضع الداكن/الفاتح
    if (theme.mode === 'dark') {
      document.body.classList.add('dark-mode');
      document.body.classList.remove('light-mode');
    } else {
      document.body.classList.add('light-mode');
      document.body.classList.remove('dark-mode');
    }

    // إضافة اسم الثيم كـ class
    document.body.setAttribute('data-theme', themeName);
    // مزامنة مع <html> (الذي ضبطه inline script)
    document.documentElement.setAttribute('data-theme', themeName);
    document.documentElement.setAttribute('data-theme-mode', theme.mode);
    document.documentElement.style.colorScheme = theme.mode;
    // مزامنة لون الخلفية على <html> لمنع أي وميض عند التنقل
    document.documentElement.style.backgroundColor = theme.background || '';
    // تحديث لون شريط العنوان على الموبايل
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) {
      metaTheme.setAttribute('content', theme.background || '#0f172a');
    }
  };

  const applyFontSize = (size) => {
    const root = document.documentElement;
    const selectedSize = FONT_SIZE_PRESETS[size] || FONT_SIZE_PRESETS.large;
    root.style.setProperty('--app-font-size', selectedSize.px);
    root.setAttribute('data-font-size', size);
  };

  useEffect(() => {
    applyTheme(currentTheme);
  }, [currentTheme]);

  useEffect(() => {
    applyFontSize(fontSize);
  }, [fontSize]);

  // applyTheme handles setting CSS vars + mode + data-theme; keep changeTheme below for state updates

  // applyFontSize defined above

  const changeTheme = (themeName) => {
    if (themes[themeName]) {
      setCurrentTheme(themeName);
      localStorage.setItem('theme', themeName);
      applyTheme(themeName);
    }
  };

  const changeFontSize = (size) => {
    setFontSize(size);
    localStorage.setItem('fontSize', size);
    applyFontSize(size);
  };

  const changeLayoutMode = (mode) => {
    setLayoutMode(mode);
    localStorage.setItem('layoutMode', mode);
  };

  // للتوافق مع الكود القديم
  const setTheme = changeTheme;

  return (
    <ThemeContext.Provider value={{
      theme: themes[currentTheme] || themes.dark,
      themeName: currentTheme,
      isDark: (themes[currentTheme] || themes.dark).mode === 'dark',
      isLight: (themes[currentTheme] || themes.dark).mode === 'light',
      fontSize,
      fontSizePresets: FONT_SIZE_PRESETS,
      layoutMode,
      changeTheme,
      setTheme,
      changeFontSize,
      changeLayoutMode,
      availableThemes: Object.keys(themes),
      themes
    }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};
