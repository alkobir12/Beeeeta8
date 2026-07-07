/** 🔐 Account security settings (P1/SEC-003): set password + PIN (trusted device). */
import React, { useState } from 'react';
import { toast } from 'sonner';
import { KeyRound, Smartphone, ShieldCheck } from 'lucide-react';
import { resolveBackendBase } from '../utils/backendBase';
import { getStoredToken } from '../utils/authToken';

const TRUSTED_DEVICE_KEY = 'trusted_device';

async function authedPost(path, body) {
  const resp = await fetch(`${resolveBackendBase()}/api${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getStoredToken()}`,
    },
    credentials: 'include',
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  return { ok: resp.ok, status: resp.status, data };
}

export const SecuritySettings = () => {
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [pin, setPin] = useState('');
  const [savingPw, setSavingPw] = useState(false);
  const [savingPin, setSavingPin] = useState(false);
  const currentUsername = (() => {
    try { return JSON.parse(localStorage.getItem('session') || 'null')?.name || ''; }
    catch (e) { return ''; }
  })();
  const trustedHere = (() => {
    try {
      const t = JSON.parse(localStorage.getItem(TRUSTED_DEVICE_KEY) || 'null');
      return t?.username === currentUsername;
    } catch (e) { return false; }
  })();

  const savePassword = async () => {
    if (!password || password.length < 6) {
      toast.error('كلمة المرور 6 أحرف على الأقل');
      return;
    }
    if (password !== password2) {
      toast.error('كلمتا المرور غير متطابقتين');
      return;
    }
    setSavingPw(true);
    const res = await authedPost('/auth/set-password', { new_password: password });
    setSavingPw(false);
    if (res.ok) {
      toast.success('تم تعيين كلمة المرور — ستُطلب عند تسجيل الدخول القادم');
      setPassword('');
      setPassword2('');
    } else {
      toast.error(res.data?.detail || 'فشل تعيين كلمة المرور');
    }
  };

  const savePin = async () => {
    if (!/^\d{4,8}$/.test(pin)) {
      toast.error('PIN من 4 إلى 8 أرقام');
      return;
    }
    setSavingPin(true);
    const res = await authedPost('/auth/set-pin', { pin });
    setSavingPin(false);
    if (res.ok && res.data?.device_id) {
      localStorage.setItem(TRUSTED_DEVICE_KEY, JSON.stringify({
        device_id: res.data.device_id,
        username: currentUsername,
      }));
      toast.success('تم تفعيل PIN وتوثيق هذا الجهاز (30 يوماً)');
      setPin('');
    } else {
      toast.error(res.data?.detail || 'فشل تعيين PIN');
    }
  };

  return (
    <div className="rounded-2xl border p-4 space-y-6" data-testid="security-settings"
         style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border-color)' }}>
      <h2 className="text-lg font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
        <ShieldCheck size={18} />
        أمان الحساب
      </h2>

      <div className="space-y-3">
        <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <KeyRound size={15} />
          كلمة المرور
        </h3>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          بعد تعيينها لن يُقبل الدخول بالاسم فقط — ستُطلب كلمة المرور دائماً.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <input
            type="password"
            placeholder="كلمة المرور الجديدة"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="apple-input"
            data-testid="security-new-password-input"
          />
          <input
            type="password"
            placeholder="تأكيد كلمة المرور"
            value={password2}
            onChange={e => setPassword2(e.target.value)}
            className="apple-input"
            data-testid="security-confirm-password-input"
          />
        </div>
        <button
          onClick={savePassword}
          disabled={savingPw}
          className="apple-button !w-auto px-6"
          data-testid="security-save-password-button"
        >
          {savingPw ? 'جارٍ الحفظ…' : 'حفظ كلمة المرور'}
        </button>
      </div>

      <div className="space-y-3 border-t pt-4" style={{ borderColor: 'var(--border-color)' }}>
        <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <Smartphone size={15} />
          الدخول السريع بـ PIN
          {trustedHere && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-100 text-green-700" data-testid="security-trusted-device-badge">
              هذا الجهاز موثوق ✓
            </span>
          )}
        </h3>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          يوثّق هذا الجهاز لمدة 30 يوماً ويتيح الدخول برمز رقمي قصير بدل كلمة المرور.
        </p>
        <div className="flex items-center gap-3">
          <input
            type="password"
            inputMode="numeric"
            maxLength={8}
            placeholder="PIN (4-8 أرقام)"
            value={pin}
            onChange={e => setPin(e.target.value.replace(/\D/g, ''))}
            className="apple-input !w-44 text-center tracking-[0.4em]"
            data-testid="security-pin-input"
          />
          <button
            onClick={savePin}
            disabled={savingPin}
            className="apple-button !w-auto px-6"
            data-testid="security-save-pin-button"
          >
            {savingPin ? 'جارٍ الحفظ…' : 'تفعيل PIN'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SecuritySettings;
