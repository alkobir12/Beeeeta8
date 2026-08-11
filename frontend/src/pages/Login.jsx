import React, { useState, useEffect } from 'react';
import { useToast } from '../hooks/use-toast';
import { useTranslation } from 'react-i18next';
import { resolveBackendBase } from '../utils/backendBase';
import { loginRequest } from '../utils/authToken';
import { establishSession } from '../utils/sessionSetup';

const TRUSTED_DEVICE_KEY = 'trusted_device';
const LAST_USERNAME_KEY = 'last_login_username';

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
  const [initialTrusted] = useState(() => readTrustedDevice());
  const [name, setName] = useState(() => localStorage.getItem(LAST_USERNAME_KEY) || '');
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [showPassword, setShowPassword] = useState(() => !initialTrusted?.device_id);
  const [rememberDevice, setRememberDevice] = useState(true);
  const [pinMode, setPinMode] = useState(() => Boolean(initialTrusted?.device_id));
  const [trusted, setTrusted] = useState(initialTrusted);
  const [loading, setLoading] = useState(false);
  const [authError, setAuthError] = useState('');

  useEffect(() => {
    const t = readTrustedDevice();
    if (t?.device_id && t?.username) {
      setTrusted(t);
      setName(current => current || t.username);
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
    localStorage.setItem(LAST_USERNAME_KEY, data.username);
    if (data?.device_id && data?.pin_configured === true && rememberDevice) {
      localStorage.setItem(TRUSTED_DEVICE_KEY, JSON.stringify({
        device_id: data.device_id,
        username: data.username,
      }));
    } else {
      localStorage.removeItem(TRUSTED_DEVICE_KEY);
    }
    await establishSession({ username: data.username, role: data.role, token: data.access_token });
    toast({ title: 'مرحباً بك', description: `أهلاً بعودتك، ${data.username}` });
    void warmCaches();
    window.location.replace(`${window.location.origin}/`);
  };

  const handleLogin = async () => {
    setAuthError('');
    if (!name.trim()) {
      setAuthError('أدخل اسم المستخدم للمتابعة');
      toast({ title: 'اسم المستخدم مطلوب', description: 'أدخل اسم المستخدم للمتابعة', variant: 'destructive' });
      return;
    }
    if (pinMode && pin.trim().length !== 6) {
      setAuthError('أدخل رمز PIN المكوّن من 6 أرقام');
      toast({ title: 'رمز غير مكتمل', description: 'أدخل رمز PIN المكوّن من 6 أرقام', variant: 'destructive' });
      return;
    }
    if (!pinMode && !password) {
      setAuthError('أدخل كلمة المرور للمتابعة');
      toast({ title: 'كلمة المرور مطلوبة', description: 'أدخل كلمة المرور الاحتياطية', variant: 'destructive' });
      return;
    }
    try {
      setLoading(true);
      const body = { username: name.trim() };
      if (pinMode) {
        body.pin = pin.trim();
        const matchingTrustedDevice = trusted?.username === name.trim() ? trusted.device_id : null;
        if (matchingTrustedDevice) body.device_id = matchingTrustedDevice;
        body.remember_device = !matchingTrustedDevice;
      } else if (showPassword && password) {
        body.password = password;
        body.remember_device = rememberDevice;
      }
      const res = await loginRequest(body);
      if (!res.ok) {
        if (res.status === 401 && /كلمة المرور مطلوبة/.test(res.detail || '')) {
          setShowPassword(true);
          setPinMode(false);
          setAuthError('كلمة المرور مطلوبة لهذا الحساب');
          toast({ title: 'كلمة المرور مطلوبة', description: 'كلمة المرور مطلوبة لهذا الحساب — أدخلها للمتابعة' });
          return;
        }
        if (res.status === 429) {
          setAuthError('محاولات كثيرة — انتظر قليلاً ثم حاول مجددًا');
          toast({ title: 'محاولات كثيرة', description: 'انتظر قليلاً ثم حاول مجدداً', variant: 'destructive' });
          return;
        }
        if (pinMode && res.status === 401) {
          localStorage.removeItem(TRUSTED_DEVICE_KEY);
          setTrusted(null);
          setPinMode(false);
          setShowPassword(true);
          setPin('');
          setAuthError('تعذر استخدام PIN على هذا الجهاز. أدخل كلمة المرور للمتابعة');
          toast({
            title: 'استخدم كلمة المرور',
            description: 'تعذر استخدام PIN على هذا الجهاز، فتم نقلك إلى الدخول الآمن بكلمة المرور',
            variant: 'destructive',
          });
          return;
        }
        const message = formatApiDetail(res.detail) || 'اسم المستخدم غير معروف أو بيانات الدخول غير صحيحة';
        setAuthError(message);
        toast({
          title: 'خطأ',
          description: message,
          variant: 'destructive',
        });
        return;
      }
      await finishLogin(res.data);
    } catch (e) {
      console.error('Login error:', e);
      setAuthError('فشل في تسجيل الدخول بسبب تعذر الاتصال أو انتهاء المهلة');
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
              <label className="text-sm font-medium text-[#1D1D1F] mr-1" htmlFor="login-username">
                اسم المستخدم
              </label>
              <input
                id="login-username"
                type="text"
                placeholder="مثال: احمد"
                value={name}
                onChange={event => { setName(event.target.value); setAuthError(''); }}
                onKeyPress={handleKeyPress}
                className="apple-input"
                autoFocus
                autoComplete="username"
                data-testid="login-username-input"
              />
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
                  onChange={e => { setPin(e.target.value.replace(/\D/g, '')); setAuthError(''); }}
                  onKeyPress={handleKeyPress}
                  className="apple-input tracking-[0.5em] text-center text-xl"
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
                    onChange={e => { setPassword(e.target.value); setAuthError(''); }}
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

            {authError && (
              <div
                role="alert"
                aria-live="assertive"
                className="w-full border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700 text-right"
                data-testid="login-error-alert"
              >
                {authError}
              </div>
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
              {(pinMode || trusted?.device_id) ? (
              <button
                type="button"
                onClick={() => {
                  setPinMode(!pinMode);
                  setShowPassword(pinMode);
                  setAuthError('');
                }}
                className="text-[#0071E3] hover:underline"
                data-testid="login-pin-mode-toggle"
              >
                {pinMode ? 'استخدام كلمة المرور الاحتياطية' : 'العودة إلى PIN السريع'}
              </button>
              ) : (
                <span className="text-[#6E6E73]" data-testid="login-pin-availability-note">
                  يتاح PIN السريع بعد تسجيل الدخول وتوثيق هذا الجهاز
                </span>
              )}
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
