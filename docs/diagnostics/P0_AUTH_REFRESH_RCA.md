# P0 — Root Cause Analysis: `/api/auth/refresh` 401 Cascade

**التاريخ:** 2026-02-24 | **الأولوية:** P0 | **الحالة:** ✅ مُصلَح ومُختبَر (5/5 + تحقق حي)

---

## 1) العَرَض (Symptom)
شلال أخطاء **401** على `/api/auth/refresh` يؤدي إلى تسجيل خروج غير منظّم وتعطّل تحميل اللوحة —
ظهر بوضوح في سجلّ الكونسول: `POST /api/auth/refresh → 401` متبوعاً بـ`ERR_ABORTED` لبقية الطلبات.

## 2) السبب الجذري (Root Cause) — بالدليل القاطع

### السبب الأساسي: كوكيز الجلسة لا تعيش داخل iframe المعاينة (cross-site)
- التطبيق يُعرَض داخل **iframe** في محرّر/معاينة Emergent → سياق **third-party (cross-site)**.
- كوكيز المصادقة كانت تُضبط بـ:
  ```
  refresh_token=...; HttpOnly; SameSite=lax; Path=/     ← بلا Secure
  ```
- المتصفحات الحديثة **لا ترسل** كوكي `SameSite=Lax` في سياق cross-site/iframe. ونقطة
  `/api/auth/refresh` كانت تعتمد على **كوكي `refresh_token` فقط** → لا يصل توكن → **401**.
- **الدليل:** `curl` مع الكوكي = **200**، وبلا كوكي = **401** — أثبت أن المنطق سليم والمشكلة في **تسليم الكوكي**.

### سبب ثانوي (متانة): لا يوجد بديل عندما تُحجب الكوكيز
- الواجهة كانت تعتمد على الكوكي حصراً في التجديد؛ لا fallback عبر Bearer، ولا logout منظّم،
  فيتحول 401 واحد إلى سلسلة فشل صامتة.

## 3) ما الذي تم تغييره (Changes)

### الباك — `backend/auth_jwt.py` (إصلاح الجذر)
| التغيير | قبل | بعد |
|---|---|---|
| سمات الكوكي | `SameSite=lax; secure=False` | `SameSite=None; Secure` (قابلة للضبط عبر `AUTH_COOKIE_SAMESITE`/`AUTH_COOKIE_SECURE`) |
| جسم `/login` | يُرجع refresh | يُرجع refresh (كما هو) |
| جسم `/refresh` | access فقط | + `refresh_token` (لتغذية fallback عبر Bearer) |
| `/logout` | `delete_cookie` بلا سمات | بنفس `SameSite/Secure` كي يُحذف فعلاً |

### الواجهة — `frontend/src/utils/authToken.js` (المتانة المطلوبة)
- **تخزين refresh** من ردّي login/refresh في `localStorage` (fallback لسياقات حجب الكوكيز: iframe / Safari ITP).
- **`refreshAccessToken()`**: single-flight (طلب واحد متزامن) + يرسل `credentials:'include'` **و** `Authorization: Bearer <refresh>` معاً → يعمل سواء وصلت الكوكي أم لا.
- **طابور الطلبات:** الطلبات المتزامنة التي تلقّت 401 تنتظر نفس وعد التجديد ثم تُعاد كلٌّ منها.
- **منع الحلقات (Refresh Loop):** لا تجديد على مسارات `/api/auth/*`، وحارس `__isRetry` لمنع التكرار.
- **Logout منظّم:** عند فشل التجديد → `_orderlyLogout()` يمسح التوكنات، يبثّ `auth:session-expired`، ويعيد التوجيه لـ`/login` **مرة واحدة** (حارس `_loggingOut`). يُصفَّر العلم عند نجاح دخول/تجديد لاحق.

## 4) الإثبات (Verification)
| اختبار | النتيجة |
|---|---|
| curl: `/refresh` مع كوكي | **200** |
| curl: `/refresh` عبر Bearer فقط (سياق محجوب الكوكي) | **200** + تدوير |
| curl: `/refresh` بلا توكن | **401** (صحيح) |
| curl: access token بدل refresh | **401** (فحص النوع) |
| Set-Cookie | `SameSite=None; Secure` ✅ |
| متصفح حي (بعد الدخول): `/refresh` | **200** |
| متصفح حي: `/assistant/stats` | **200** |
| متصفح حي: اللوحة تحمّل كاملة | ✅ (12 مركبة، إحصاءات) |
| pytest `test_auth_refresh_iter255.py` | **5/5** |

ملاحظة: الـ401 التي تظهر **قبل** تسجيل الدخول (AssistantProvider يستطلع بلا جلسة) سلوك متوقّع
(لا جلسة بعد) وليست عطلاً.

## 5) مخاطر/ملاحظات متبقية
- **تخزين refresh في localStorage** يوسّع سطح XSS نظرياً؛ خُفِّف بأن الكوكي httpOnly تبقى الآلية
  الأساسية وأن P1 سيضيف **تدوير refresh بـ jti فريد + كشف إعادة الاستخدام + تخزين خادمي**.
- **التدوير الحالي** (HS256 عديم الحالة) يُنتج توكناً مطابقاً بايتياً داخل نفس الثانية — لا يمثّل
  تدويراً حقيقياً؛ هذا **من نطاق P1** كما حدّده المالك.
- **الحالة داخل الذاكرة** (drafts/sessions) لا تزال تُفقد عند إعادة التشغيل — **P4**.
