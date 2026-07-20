/**
 * أداة مساعدة موحَّدة لجلب بيانات الورشة للطباعة.
 * تُستخدم في جميع المكونات التي تولّد HTML للطباعة محلياً
 * (Customers, JournalEntries, …).
 *
 * عند الإمكان يُفضَّل تمرير `workshop` كاملاً إلى `/api/documents/generate`
 * لأن الباك يُكمِّل الحقول الناقصة تلقائياً.
 */

const FALLBACK = Object.freeze({
  name: 'الورشة',
  business_name: 'الورشة',
  phone: '',
  address: '',
  tax_number: '',
  commercial_register: '',
  email: '',
  website: '',
  logo: '',  // base64 data URL
});

/**
 * جلب بيانات الورشة (اسم/عنوان/هاتف/شعار/ضريبي/ت.تجاري/إيميل/موقع).
 * يجلب من `/api/settings` و `/api/profile` ويدمجهما.
 *
 * @param {object} apiOrFetcher - axios-like (له get) أو دالة fetch
 * @returns {Promise<object>} كائن الورشة الموحَّد
 */
export async function loadWorkshopPrintInfo(apiOrFetcher) {
  try {
    let settings = {};
    let profileRaw = {};

    if (apiOrFetcher && typeof apiOrFetcher.get === 'function') {
      const [s, p] = await Promise.all([
        apiOrFetcher.get('/settings').catch(() => ({ data: {} })),
        apiOrFetcher.get('/profile').catch(() => ({ data: {} })),
      ]);
      settings = s?.data || {};
      profileRaw = p?.data || {};
    } else if (typeof apiOrFetcher === 'function') {
      const [s, p] = await Promise.all([
        apiOrFetcher('/settings').then(r => r.json()).catch(() => ({})),
        apiOrFetcher('/profile').then(r => r.json()).catch(() => ({})),
      ]);
      settings = s || {};
      profileRaw = p || {};
    } else {
      const base =
        (typeof process !== 'undefined' && process?.env?.REACT_APP_BACKEND_URL)
          ? `${process.env.REACT_APP_BACKEND_URL}/api`
          : '/api';
      const [s, p] = await Promise.all([
        fetch(`${base}/settings`).then(r => r.json()).catch(() => ({})),
        fetch(`${base}/profile`).then(r => r.json()).catch(() => ({})),
      ]);
      settings = s || {};
      profileRaw = p || {};
    }

    const profile = profileRaw?.profile || profileRaw?.data || profileRaw || {};

    // 🎯 الأولوية: ملف الورشة (Profile) > الإعدادات (Settings) > الافتراضي
    // (المستخدم يحدّث اسم/شعار/عنوان الورشة من صفحة "ملف الورشة"، لذا تكون لها الأولوية)
    const normalizedName =
      profile?.business_name ||
      profile?.name ||
      settings?.workshopName ||
      FALLBACK.name;
    const normalizedPhone =
      profile?.phone ||
      profile?.phone_number ||
      profile?.whatsapp ||
      settings?.workshopPhone ||
      FALLBACK.phone;
    const normalizedAddress =
      profile?.address ||
      settings?.workshopAddress ||
      FALLBACK.address;
    const normalizedCommercial =
      profile?.commercialRegister ||
      profile?.commercial_register ||
      settings?.commercialRegister ||
      FALLBACK.commercial_register;
    const normalizedTax =
      profile?.taxNumber ||
      profile?.tax_number ||
      settings?.taxNumber ||
      FALLBACK.tax_number;
    const normalizedLogo =
      profile?.logo ||
      profile?.logo_url ||
      profile?.logoUrl ||
      settings?.logoUrl ||
      FALLBACK.logo;

    return {
      name:
        normalizedName,
      name_en: profile?.nameEnglish || profile?.name_en || '',
      nameEnglish: profile?.nameEnglish || profile?.name_en || '',
      business_name: normalizedName,
      phone: normalizedPhone,
      whatsapp: profile?.whatsapp || normalizedPhone,
      address: normalizedAddress,
      tax_number: normalizedTax,
      taxNumber: normalizedTax,
      commercial_register: normalizedCommercial,
      commercialRegister: normalizedCommercial,
      email:
        profile?.email ||
        settings?.workshopEmail ||
        FALLBACK.email,
      website:
        profile?.website ||
        settings?.workshopWebsite ||
        FALLBACK.website,
      // الشعار يأتي base64 أو URL مباشر — نقبل أيّاً منهما (Profile له الأولوية)
      logo: normalizedLogo,
      logo_url: normalizedLogo,
    };
  } catch (e) {
    console.warn('loadWorkshopPrintInfo failed:', e);
    return { ...FALLBACK };
  }
}

/**
 * توليد رأس HTML موحَّد للطباعة يتضمن الشعار + اسم الورشة + الهاتف/العنوان/الضريبي/ت.تجاري.
 * صالح للاستخدام داخل أي قالب طباعة محلي.
 *
 * @param {object} workshop - مُرجَع `loadWorkshopPrintInfo`
 * @returns {string} HTML للرأس
 */
export function buildWorkshopHeaderHtml(workshop = {}) {
  const w = { ...FALLBACK, ...(workshop || {}) };
  const logoBlock = w.logo
    ? `<img src="${w.logo}" alt="logo" style="max-height:64px;max-width:120px;object-fit:contain;margin-bottom:8px;" />`
    : '';
  const safe = (v) => (v ? String(v).replace(/[<>]/g, '') : '');
  return `
    <div style="display:flex;align-items:flex-start;gap:12px;border-bottom:2px solid #1e40af;padding-bottom:10px;margin-bottom:12px;">
      ${logoBlock}
      <div style="flex:1;">
        <div style="font-size:18px;font-weight:800;color:#1e40af;">${safe(w.name) || 'الورشة'}</div>
        ${safe(w.address) ? `<div style="font-size:12px;color:#475569;">${safe(w.address)}</div>` : ''}
        <div style="font-size:11px;color:#64748b;margin-top:4px;">
          ${safe(w.phone) ? `هاتف: ${safe(w.phone)}` : ''}
          ${safe(w.email) ? ` • ${safe(w.email)}` : ''}
        </div>
        <div style="font-size:11px;color:#64748b;">
          ${safe(w.commercial_register) ? `س.تجاري: ${safe(w.commercial_register)}` : ''}
          ${safe(w.tax_number) ? ` • ر.ضريبي: ${safe(w.tax_number)}` : ''}
        </div>
      </div>
    </div>
  `;
}
