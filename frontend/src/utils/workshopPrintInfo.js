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

    return {
      name:
        settings?.workshopName ||
        profile?.business_name ||
        profile?.name ||
        FALLBACK.name,
      business_name:
        settings?.workshopName ||
        profile?.business_name ||
        profile?.name ||
        FALLBACK.business_name,
      phone:
        settings?.workshopPhone ||
        profile?.phone ||
        profile?.phone_number ||
        FALLBACK.phone,
      address:
        settings?.workshopAddress ||
        profile?.address ||
        FALLBACK.address,
      tax_number:
        settings?.taxNumber ||
        profile?.taxNumber ||
        profile?.tax_number ||
        FALLBACK.tax_number,
      commercial_register:
        settings?.commercialRegister ||
        profile?.commercialRegister ||
        profile?.commercial_register ||
        FALLBACK.commercial_register,
      email:
        settings?.workshopEmail ||
        profile?.email ||
        FALLBACK.email,
      website:
        settings?.workshopWebsite ||
        profile?.website ||
        FALLBACK.website,
      // الشعار يأتي base64 أو URL مباشر — نقبل أيّاً منهما
      logo:
        profile?.logo ||
        profile?.logo_url ||
        profile?.logoUrl ||
        settings?.logoUrl ||
        FALLBACK.logo,
      logo_url:
        profile?.logo ||
        profile?.logo_url ||
        profile?.logoUrl ||
        settings?.logoUrl ||
        FALLBACK.logo,
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
