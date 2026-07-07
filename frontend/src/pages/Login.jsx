import React, { useState, useEffect } from 'react';
import { useToast } from '../hooks/use-toast';
import { useTranslation } from 'react-i18next';
import { resolveBackendBase } from '../utils/backendBase';
import { loginRequest } from '../utils/authToken';
import { establishSession } from '../utils/sessionSetup';

const TRUSTED_DEVICE_KEY = 'trusted_device';

function readTrustedDevice() {
  try { return JSON.parse(localStorage.getItem(TRUSTED_DEVICE_KEY) || 'null'); }
  catch (e) { return null; }
}

const Login = () => {
  const { toast } = useToast();
  useTranslation();
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberDevice, setRememberDevice] = useState(false);
  const [pinMode, setPinMode] = useState(false);
  const [trusted, setTrusted] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = readTrustedDevice();
    if (t?.device_id && t?.username) {
      setTrusted(t);
      setPinMode(true);
      setName(t.username);
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
    await warmCaches();
    window.location.assign(`${window.location.origin}/`);
  };

  const handleLogin = async () => {
    if (!name.trim()) {
      toast({ title: 'خطأ', description: 'الرجاء إدخال الاسم', variant: 'destructive' });
      return;
    }
    if (pinMode && !pin.trim()) {
      toast({ title: 'خطأ', description: 'أدخل رمز PIN', variant: 'destructive' });
      return;
    }
    try {
      setLoading(true);
      const body = { username: name.trim() };
      if (pinMode && trusted?.device_id) {
        body.pin = pin.trim();
        body.device_id = trusted.device_id;
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
          toast({ title: 'خطأ', description: 'PIN غير صحيح أو انتهت صلاحية الجهاز الموثوق', variant: 'destructive' });
          return;
        }
        toast({
          title: 'خطأ',
          description: res.detail || 'اسم المستخدم غير معروف أو بيانات الدخول غير صحيحة',
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

  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
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
              <label className="text-sm font-medium text-[#1D1D1F] mr-1">
                اسم المستخدم
              </label>
              <input
                type="text"
                placeholder="أدخل اسمك هنا"
                value={name}
                onChange={e => setName(e.target.value)}
                onKeyPress={handleKeyPress}
                className="apple-input"
                autoFocus
                data-testid="login-username-input"
              />
            </div>

            {pinMode && (
              <div className="space-y-2 text-right">
                <label className="text-sm font-medium text-[#1D1D1F] mr-1">
                  رمز PIN (جهاز موثوق)
                </label>
                <input
                  type="password"
                  inputMode="numeric"
                  maxLength={8}
                  placeholder="أدخل رمز PIN"
                  value={pin}
                  onChange={e => setPin(e.target.value.replace(/\D/g, ''))}
                  onKeyPress={handleKeyPress}
                  className="apple-input tracking-[0.5em] text-center"
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
                  <span>تذكّر هذا الجهاز (دخول بـ PIN لاحقاً)</span>
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
              className="apple-button flex items-center justify-center gap-2"
              data-testid="login-submit-button"
            >
              {loading ? (
                <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                'دخول'
              )}
            </button>

            <div className="flex items-center gap-3 py-1">
              <div className="flex-1 h-px bg-gray-200" />
              <span className="text-xs text-[#86868B]">أو</span>
              <div className="flex-1 h-px bg-gray-200" />
            </div>

            <button
              onClick={handleGoogleLogin}
              type="button"
              className="w-full flex items-center justify-center gap-3 border border-gray-300 rounded-xl py-3 px-4 bg-white hover:bg-gray-50 transition-colors text-[#1D1D1F] font-medium"
              data-testid="login-google-button"
            >
              <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.5 6.1 29.5 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z"/>
                <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.5 6.1 29.5 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
                <path fill="#4CAF50" d="M24 44c5.2 0 10-2 13.6-5.2l-6.3-5.3C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/>
                <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4 5.5l6.3 5.3C41.4 35.1 44 30 44 24c0-1.3-.1-2.6-.4-3.9z"/>
              </svg>
              المتابعة عبر Google
            </button>

            <div className="flex items-center justify-between text-xs pt-1">
              {trusted?.device_id ? (
                <button
                  type="button"
                  onClick={() => { setPinMode(!pinMode); setShowPassword(false); }}
                  className="text-[#0071E3] hover:underline"
                  data-testid="login-pin-mode-toggle"
                >
                  {pinMode ? 'الدخول بالاسم/كلمة المرور' : `دخول سريع بـ PIN (${trusted.username})`}
                </button>
              ) : <span />}
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
