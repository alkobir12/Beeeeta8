import React, { useState, useEffect } from 'react';
import { useToast } from '../hooks/use-toast';
import { useTranslation } from 'react-i18next';
import { resolveBackendBase } from '../utils/backendBase';
import { loginRequest } from '../utils/authToken';
import { establishSession } from '../utils/sessionSetup';

const TRUSTED_DEVICE_KEY = 'trusted_device';
const MANAGER_USERNAME = 'مدير';

function formatApiDetail(detail) {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => item?.msg || '').filter(Boolean).join('، ');
  return detail?.msg || 'تعذر إكمال تسجيل الدخول';
}

function readTrustedDevice() {
  try { return JSON.parse(localStorage.getItem(TRUSTED_DEVICE_KEY) || 'null'); }
  catch (e) { return null; }
}

const Login = () => {
  const { toast } = useToast();
  useTranslation();
  const name = MANAGER_USERNAME;
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberDevice, setRememberDevice] = useState(true);
  const [pinMode, setPinMode] = useState(true);
  const [trusted, setTrusted] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = readTrustedDevice();
    if (t?.device_id && t?.username) {
      setTrusted(t);
    }
  }, []);

  const warmCaches = async () => {
    const API_URL = `${resolveBackendBase()}/api`;
    const warm = async (path, key, updatedKey) => {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 8000);
        const res = await fetch(`${API_URL}${path}`, { signal: controller.signal });
        clearTimeout(timeout);
        if (!res.ok) return;
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          localStorage.setItem(key, JSON.stringify(data));
          if (updatedKey) localStorage.setItem(updatedKey, new Date().toISOString());
        }
      } catch (e) { /* ignore warmup failures */ }
    };
    await Promise.all([
      warm('/operations?limit=200', 'operationsCache:all', 'operationsCacheUpdatedAt:all'),
      warm('/accounts', 'chartAccountsCache:all'),
    ]);
  };

  const finishLogin = async (data) => {
    if (data?.device_id && rememberDevice) {
      localStorage.setItem(TRUSTED_DEVICE_KEY, JSON.stringify({
        device_id: data.device_id,
        username: data.username,
      }));
    }
    await establishSession({ username: data.username, role: data.role, token: data.access_token });
    toast({ title: 'مرحباً بك', description: `أهلاً بعودتك، ${data.username}` });
    void warmCaches();
    window.location.replace(`${window.location.origin}/`);
  };

  const handleLogin = async () => {
    if (pinMode && pin.trim().length !== 6) {
      toast({ title: 'رمز غير مكتمل', description: 'أدخل رمز PIN المكوّن من 6 أرقام', variant: 'destructive' });
      return;
    }
    if (!pinMode && !password) {
      toast({ title: 'كلمة المرور مطلوبة', description: 'أدخل كلمة المرور الاحتياطية', variant: 'destructive' });
      return;
    }
    try {
      setLoading(true);
      const body = { username: name.trim() };
      if (pinMode) {
        body.pin = pin.trim();
        if (trusted?.device_id) body.device_id = trusted.device_id;
        body.remember_device = !trusted?.device_id;
      } else if (showPassword && password) {
        body.password = password;
        body.remember_device = rememberDevice;
      }
      const res = await loginRequest(body);
      if (!res.ok) {
        if (res.status === 401 && /كلمة المرور مطلوبة/.test(res.detail || '')) {
          setShowPassword(true);
          setPinMode(false);
          toast({ title: 'كلمة المرور مطلوبة', description: 'كلمة المرور مطلوبة لهذا الحساب — أدخلها للمتابعة' });
          return;
        }
        if (res.status === 429) {
          toast({ title: 'محاولات كثيرة', description: 'انتظر قليلاً ثم حاول مجدداً', variant: 'destructive' });
          return;
        }
        if (pinMode && res.status === 401) {
          toast({ title: 'رمز غير صحيح', description: 'تحقق من رمز PIN وحاول مرة أخرى', variant: 'destructive' });
          return;
        }
        toast({
          title: 'خطأ',
          description: formatApiDetail(res.detail) || 'اسم المستخدم غير معروف أو بيانات الدخول غير صحيحة',
          variant: 'destructive',
        });
        return;
      }
      await finishLogin(res.data);
    } catch (e) {
      console.error('Login error:', e);
      toast({ title: 'خطأ', description: 'فشل في تسجيل الدخول (تعذر الاتصال أو مهلة)', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') handleLogin();
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 relative overflow-hidden">
      <div className="fixed top-[-10%] left-[-10%] w-[500px] h-[500px] bg-blue-200/30 rounded-full blur-[100px] pointer-events-none" aria-hidden="true" />
      <div className="fixed bottom-[-10%] right-[-10%] w-[500px] h-[500px] bg-indigo-200/30 rounded-full blur-[100px] pointer-events-none" aria-hidden="true" />

      <div className="w-full max-w-[400px] z-10 animate-fade-in">
        <div className="apple-card p-10 flex flex-col items-center text-center">

          <div className="w-16 h-16 bg-gradient-to-br from-[#0071E3] to-[#00C7BE] rounded-2xl mb-8 shadow-lg flex items-center justify-center text-white text-2xl font-bold">
            W
          </div>

          <h1 className="text-3xl font-bold text-[#1D1D1F] mb-2 tracking-tight">
            تسجيل الدخول
          </h1>
          <p className="text-[#86868B] text-base mb-8">
            نظام إدارة الورش الذكي
          </p>

          <div className="w-full space-y-5">
            <div className="space-y-2 text-right">
              <span className="text-sm font-medium text-[#1D1D1F] mr-1">اسم المستخدم</span>
              <div
                className="apple-input flex items-center justify-between bg-[#F5F5F7]"
                data-testid="login-manager-identity"
              >
                <span className="text-xs text-[#86868B]">الحساب الإداري</span>
                <strong className="text-[#1D1D1F]">{MANAGER_USERNAME}</strong>
              </div>
            </div>

            {pinMode && (
              <div className="space-y-2 text-right">
                <label className="text-sm font-medium text-[#1D1D1F] mr-1">
                  رمز الدخول السريع
                </label>
                <input
                  type="password"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="••••••"
                  value={pin}
                  onChange={e => setPin(e.target.value.replace(/\D/g, ''))}
                  onKeyPress={handleKeyPress}
                  className="apple-input tracking-[0.5em] text-center text-xl"
                  autoFocus
                  data-testid="login-pin-input"
                />
              </div>
            )}

            {!pinMode && showPassword && (
              <>
                <div className="space-y-2 text-right">
                  <label className="text-sm font-medium text-[#1D1D1F] mr-1">
                    كلمة المرور
                  </label>
                  <input
                    type="password"
                    placeholder="أدخل كلمة المرور"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    onKeyPress={handleKeyPress}
                    className="apple-input"
                    data-testid="login-password-input"
                  />
                </div>
                <label className="flex items-center gap-2 text-sm text-[#1D1D1F] justify-end cursor-pointer select-none">
                  <span>تذكّر هذا الجهاز</span>
                  <input
                    type="checkbox"
                    checked={rememberDevice}
                    onChange={e => setRememberDevice(e.target.checked)}
                    className="w-4 h-4 accent-[#0071E3]"
                    data-testid="login-remember-device-checkbox"
                  />
                </label>
              </>
            )}

            <button
              onClick={handleLogin}
              disabled={loading}
              className="apple-button w-full flex items-center justify-center gap-2"
              data-testid="login-submit-button"
            >
              {loading ? (
                <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                'دخول'
              )}
            </button>

            <div className="flex items-center justify-center text-xs pt-1">
              <button
                type="button"
                onClick={() => { setPinMode(!pinMode); setShowPassword(pinMode); }}
                className="text-[#0071E3] hover:underline"
                data-testid="login-pin-mode-toggle"
              >
                {pinMode ? 'استخدام كلمة المرور الاحتياطية' : 'العودة إلى PIN السريع'}
              </button>
              {!pinMode && !showPassword && (
                <button
                  type="button"
                  onClick={() => setShowPassword(true)}
                  className="text-[#0071E3] hover:underline"
                  data-testid="login-show-password-toggle"
                >
                  لديّ كلمة مرور
                </button>
              )}
            </div>
          </div>

          <div className="mt-8 text-sm text-[#86868B]">
            نسخة تجريبية v2.1
          </div>
        </div>

        <div className="mt-8 text-center text-[#86868B] text-sm">
          جميع الحقوق محفوظة © 2025
        </div>
      </div>
    </div>
  );
};

export default Login;
