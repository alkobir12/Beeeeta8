import React, { createContext, useContext, useState, useEffect } from 'react';
import i18n from '../i18n';
import translations from '../translations';
import { englishTexts } from '../constants/englishTexts';

const LanguageContext = createContext();

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};

export const LanguageProvider = ({ children }) => {
  // اللغة الافتراضية: عربية (RTL)
  const initialLang = (() => {
    try {
      return localStorage.getItem('language') || i18n.language || 'ar';
    } catch (e) {
      return i18n.language || 'ar';
    }
  })();

  const [language, setLanguage] = useState(initialLang);
  const [renderKey, setRenderKey] = useState(0); // Force re-render trigger

  // Sync context language when i18next changes (e.g., LanguageToggleButton)
  useEffect(() => {
    const handler = (lng) => {
      if (lng && lng !== language) {
        setLanguage(lng);
        setRenderKey((prev) => prev + 1);
      }
    };

    i18n.on('languageChanged', handler);
    return () => {
      i18n.off('languageChanged', handler);
    };
  }, []);

  // Handle language change
  const changeLanguage = (newLang) => {
    console.log('🔄 Changing language from', language, 'to', newLang);

    try {
      localStorage.setItem('language', newLang);
    } catch (e) {
      // ignore
    }

    // Sync with i18next so components using react-i18next update too
    try {
      if (i18n.language !== newLang) {
        i18n.changeLanguage(newLang);
      }
    } catch (e) {
      // ignore
    }

    setLanguage(newLang);
    setRenderKey((prev) => prev + 1); // Force all consumers to re-render
  };

  // تحديث اتجاه الصفحة عند تغيير اللغة
  useEffect(() => {
    console.log('✅ Language effect triggered:', language);

    // Persist (so i18next detector finds it)
    try {
      localStorage.setItem('language', language);
    } catch (e) {
      // ignore
    }

    // Keep i18next in sync (in case language was initialized differently)
    try {
      if (i18n.language !== language) {
        i18n.changeLanguage(language);
      }
    } catch (e) {
      // ignore
    }

    document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
    document.documentElement.lang = language;
  }, [language]);

  // دالة الترجمة
  const t = (key) => {
    if (language === 'en') {
      return englishTexts[key] || key;
    }
    
    // للعربية، نبحث في ملف الترجمات
    const keys = key.split('.');
    let value = translations;
    
    for (const k of keys) {
      value = value?.[k];
      if (value === undefined) {
        console.warn('⚠️ Translation missing for key:', key, 'in language:', language);
        return key;
      }
    }
    
    return value;
  };

  const value = {
    language,
    setLanguage: changeLanguage, // Use custom change function
    t,
    isRTL: language === 'ar',
    renderKey // Expose renderKey for debugging
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};
