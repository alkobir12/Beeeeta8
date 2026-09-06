# PRODUCTION SUPABASE RUNTIME VERIFICATION — READ ONLY

Generated: 2026-06 (fork session) · Scope: READ-ONLY · NO DEPLOY · NO SECRET CHANGE · NO DB MUTATION
No secret values are printed. Only type / length / sha256-first-8 / JWT public claims.

---

## 0. الخلاصة المطلوبة (Answer Block)

```text
PRODUCTION_REACHABLE = YES
  - https://car-repair-sys.emergent.host/api/health = 200 {"status":"ok"}
  - https://alkobir.com/api/health                  = 200 {"status":"ok"}
  - https://fixsa.online                            = UNREACHABLE (curl 000)
  - نفس الحزمة على الدومينين => نشر واحد بدومينين.

PRODUCTION_SUPABASE_PROJECT_REF = kqjlyozhvwswooztccag
PROJECT_REF_MATCH (beeeta8) = YES   ← تصحيح رسمي لتقرير سابق قال NO (كان يقارن اسم المشروع بالـref)

PRODUCTION_SUPABASE_URL_SOURCE = DEPLOYED_ARTIFACT_BACKEND_DOTENV (git-tracked at deployed commit)
PRODUCTION_SERVER_KEY_SOURCE   = DEPLOYED_ARTIFACT_BACKEND_DOTENV (نفس المصدر)
  - السبب: العُقدة المنشورة مبنية من commit في نافذة 2026-08-19T23:23Z .. 2026-08-20T21:55Z،
    وفي تلك النافذة كان `backend/.env` **متتبَّعاً في git** (أُزيل فقط في 0ceb2ddc بتاريخ 2026-09-02).
  - و`server.py` يستخدم `load_dotenv(ROOT_DIR/".env", override=False)` => متغيرات المنصة تسبق الملف
    **فقط إن وُجدت في process env**؛ وفي هذه الفئة من العُقد لا تُحقن SUPABASE_* إطلاقاً (مثبت في المعاينة).

PRODUCTION_SUPABASE_KEY_TYPE = NOT_VERIFIABLE (runtime probe غير متاح)
  STRONGEST_EVIDENCE => LEGACY (service_role JWT)
  - المفتاح الموجود في `backend/.env` داخل نافذة النشر: LEGACY_JWT · sha256_8 = 28196474
    · claims = {iss: supabase, ref: kqjlyozhvwswooztccag, role: service_role, exp: 2078696006}
  - لا يوجد أي دليل على أن قيمة المنصة الجديدة (sb_secret_*) وصلت إلى الإنتاج،
    لأن **أرتيفاكت الإنتاج لم يتغير منذ 2026-08-20** (إثبات في §2 و§3).

PRODUCTION_KEY_IS_VALID = YES (الإنتاج يعمل ويقرأ بيانات)
LEGACY_JWT_STILL_ACCEPTED_BY_PROJECT = YES
  - قراءة حقيقية READ-ONLY على المشروع: `GET /rest/v1/vehicles?select=id&limit=1`
    => HTTP 206 · content-range = 0-0/237
  - لذلك لا يمكن التمييز بين LEGACY و NEW_SB_SECRET من الخارج: كلاهما صالح لنفس المشروع.

DEPLOY_EXECUTED = NO
SECRET_CHANGED = NO
DB_MUTATION = NO
ACCOUNTINGENGINE_TOUCHED = NO
```

---

## 1. مصدر إعدادات المعاينة (Preview) — مثبت مباشرة

قراءة process env الحقيقي للـbackend العامل (`/proc/264/environ`, backend pid=264):

```text
SUPABASE_URL                = <ABSENT>
SUPABASE_SERVICE_ROLE_KEY   = <ABSENT>
DB_PROVIDER / DB_NAME       = <ABSENT>
CORS_ORIGINS                = <ABSENT>
APP_URL                     = https://b6aca8b4-....preview.emergentagent.com   (من supervisor)
total env vars in process   = 24
any sb_secret_* / sb_publishable_* value present = NO
```

`/etc/supervisor/conf.d/*.conf` → برنامج backend يحقن فقط `APP_URL` و`INTEGRATION_PROXY_URL`.

**النتيجة:** PREVIEW_SUPABASE_CONFIG_SOURCE = `backend/.env` (عبر `load_dotenv`) — **صفر حقن من المنصة**.

قيم `backend/.env` الحالية (نوع فقط):
```text
SUPABASE_URL = https://kqjlyozhvwswooztccag.supabase.co   → ref = kqjlyozhvwswooztccag
SUPABASE_SERVICE_ROLE_KEY = LEGACY_JWT · len=219 · sha256_8=28196474
  claims = {iss: supabase, ref: kqjlyozhvwswooztccag, role: service_role}
PREVIEW_KEY_TYPE = LEGACY
PREVIEW_PROJECT_REF_MATCH = YES
```

---

## 2. تحديد نسخة أرتيفاكت الإنتاج (Frontend bundle fingerprint)

الحزمة الوحيدة (لا code-splitting): `/static/js/main.35a8f1ca.js` (1,827,969 bytes) — متطابقة على
`car-repair-sys.emergent.host` و`alkobir.com`.

| علامة داخل الحزمة | موجودة؟ | أُضيفت/أُزيلت في |
|---|---|---|
| `auth_session` | ✅ موجودة | **أُضيفت** 46cff96d — 2026-08-19T23:23Z |
| `credentials:t?"include":"omit"` (fallback القديم) | ✅ موجودة | **أُزيلت** b7c3a996 — 2026-09-04T14:19Z |
| `journal-card-creator-tag` | ❌ غائبة | **أُضيفت** 6524e763 — 2026-08-20T21:55Z |
| `REACT_APP_BACKEND_URL:"https://alkobir.com"` (base مطلق) | ✅ موجودة | نمط ما قبل same-origin (3952ecf4 — 2026-09-04T14:38Z) |

```text
PRODUCTION_BUILD_COMMIT_WINDOW = (2026-08-19T23:23Z , 2026-08-20T21:55Z)
```

**تبعات مباشرة:** الإنتاج **لا يحتوي**:
- Phase 1B Authorization Closure (2026-09-02)
- Phase 1C CORS/Cookie fix (2026-09-04)
- Same-Origin `/api` Auth Transport (2026-09-04)
- ولا ميزات دفتر اليومية/إظهار المنشئ (2026-08-20 وما بعدها)

**ملاحظة نقل مهمة:** حزمة الإنتاج تستخدم base مطلق `https://alkobir.com` وليس `/api` نسبي.
=> على `alkobir.com` الطلبات same-origin (سليم)، لكن من `car-repair-sys.emergent.host` تصبح
**cross-origin credentialed** — وهو بالضبط سبب فشل الدخول الذي أُصلح في المعاينة ولم يصل للإنتاج بعد.

---

## 3. تأكيد مستقل من جهة الـbackend (CORS runtime fingerprint)

`OPTIONS /api/auth/login` مع `Origin` و`Access-Control-Request-*` (قراءة رؤوس فقط):

| البيئة | allow-methods | allow-headers | التفسير |
|---|---|---|---|
| **localhost:8001 (HEAD الحالي)** | `GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD` (ترتيب الإعداد الصريح) | `Accept, Accept-Language, Authorization, Content-Language, Content-Type, X-Correlation-ID, X-Request-ID, X-Requested-With` (قائمة صريحة) | إعداد **غير wildcard** = ما بعد b7c3a996 |
| **PRODUCTION** | `DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT` (= Starlette ALL_METHODS، أبجدي) | `content-type,authorization` (= صدى الطلب) | إعداد **wildcard `*`** = **ما قبل** b7c3a996 |
| PREVIEW عبر الحافة | `*` + `allow-origin: *` (HTTP 204) | `*` | الحافة الخارجية تجيب قبل FastAPI (قيد منصة موثق سابقاً) |

```text
PRODUCTION_BACKEND_VERSION = PRE_b7c3a996  (يطابق نافذة الحزمة في §2)
FRONTEND_AND_BACKEND_ARTIFACT_CONSISTENT = YES
```

كذلك: الإنتاج يرفض origin غير مسموح (HTTP 400 بلا `allow-origin`) => حارس CORS المُعتمِد فعّال.

---

## 4. سطح الفحص المتاح على الإنتاج (لماذا الـruntime probe غير ممكن)

| المسار | الإنتاج |
|---|---|
| `/api/health` | 200 `{"status":"ok"}` |
| `/api/supabase/status` | **401** Not authenticated |
| `/api/supabase/vehicles` | 401 |
| `/api/auth/me` | 401 |
| `/api/finance/reports/trial-balance` | 401 |
| `/docs`, `/openapi.json` | تُخدَم كـSPA HTML (لا Swagger مكشوف) |

- المسار العام الوحيد `(/api/approvals/public/{token})` يتطلب توكن اعتماد صالح — لا يكشف إعدادات Supabase.
- وحتى مع اعتمادات إنتاج، **لا يوجد endpoint في الكود يكشف project ref أو نوع المفتاح**
  (`/api/supabase/status` يعيد booleans فقط: connected/mode/url_configured/key_configured).
- ولذلك: `PRODUCTION_SUPABASE_KEY_TYPE = NOT_VERIFIABLE` بدون أحد الخيارات في §5.

---

## 5. ما يلزم لإثبات نوع المفتاح 100% (لم يُنفَّذ — يحتاج قرارك)

1. **نشر endpoint تشخيصي للقراءة فقط** (admin-only) يعيد: `project_ref` + `key_type` + `key_sha8` + `config_source`.
   بلا أي قيمة سر. يتطلب **نشر build جديد** (ممنوع حالياً بأمرك).
2. **اختبار سلبي على Supabase**: تعطيل مفاتيح JWT القديمة (legacy) في لوحة Supabase.
   إن استمر الإنتاج بالعمل ⇒ NEW_SB_SECRET. إن توقف ⇒ LEGACY.
   ⚠️ هذا **تجربة على الإنتاج الحي** وقد تُسقط الخدمة فوراً — لا أنصح بها الآن.
3. **اعتمادات إنتاج للقراءة فقط** + مقارنة بصمة بيانات (عدد المركبات = 237). تُثبت الـproject ref فقط،
   **لا** تُثبت نوع المفتاح.

---

## 6. Preview Configuration — لا يوجد drift (تصحيح ذاتي)

```text
CURRENT_PREVIEW_HOST = https://financial-ssot.preview.emergentagent.com
CORS_ORIGINS (backend/.env:24) =
  https://financial-ssot.preview.emergentagent.com,
  https://car-repair-sys.emergent.host,
  https://alkobir.com, https://www.alkobir.com,
  https://fixsa.online, https://www.fixsa.online,
  http://localhost:3000
PREVIEW_CONFIGURATION_DRIFT = NONE  ← تصحيح: ادّعاء سابق في هذه الجلسة قال إن CORS_ORIGINS
                                      يحمل host المعاينة القديم — الادّعاء **خاطئ**؛ الـhost الحالي موجود فعلاً.
PRIMARY_AUTH_PATH = same-origin `/api` (`resolveBackendBase()` يعيد '' في المتصفح)
  - `GET https://financial-ssot.preview.emergentagent.com/api/health = 200`
`.env` FILES TOUCHED = NONE
```

---

## 8. Deployment Readiness Health Check (نفس الجلسة)

```text
FIRST_SCAN  = FAIL — 1 BLOCKER
  backend/seed_database.py: عمليات هدم `delete_many({})` على
  services (582) · technicians (636) · workshop_profile (657)
  الخطر: تنفيذ عرضي للسكربت أثناء نشر/صيانة يمسح البيانات، وقاعدة الإنتاج والمعاينة **واحدة**.

FIX_APPLIED (كود فقط — لم يُنفَّذ السكربت إطلاقاً) =
  - `from pymongo import UpdateOne` (سطر 9)
  - services: إزالة التكرار بالاسم إلى `unique_services` ثم
    `bulk_write([UpdateOne({"name": ...}, {"$setOnInsert": ...}, upsert=True)], ordered=False)`
  - technicians: upsert على `phone` بـ`$setOnInsert`
  - workshop_profile: `update_one({"id": "workshop_profile"}, {"$setOnInsert": ...}, upsert=True)`
  - `grep -nE "delete_many|insert_many|\.drop\(|drop_database"` على الملف ⇒ **0 نتائج**

SECOND_SCAN = PASS · findings = [] · destructive_db_startup_confirmed = false
VERIFICATION (iteration_379, READ-ONLY) = backend 100%
  - `$setOnInsert` في كل المواضع ⇒ لا يُعدَّل أي مستند قائم أبداً؛ إعادة التشغيل لا تُنتج تكراراً
  - `/api/health` 200 · بدء تشغيل نظيف بعد إضافة الاستيراد · login 200 · `/api/auth/me` 200
  - قراءات تمثيلية (vehicles/services/technicians/parts) 200 · HTTP 500 = 0 · لا تسريب `_id`
  - السكربت **لم يُنفَّذ** · صفر تعديل بيانات
  - نقطة الاستدعاء الوحيدة: `/app/backend_test_new_apis.py:345` (لا startup ولا route)

REMAINING (P1، مؤجَّل بأمر المالك) =
  - P1-SEC-UPLOAD: 5 مسارات ترفع على قرص العُقدة بدل Object Storage
    server.py:2918 · routes_vehicle_files.py:38 · routes_document_templates.py:330
    routes_finance_bot.py:573 · routes_references.py:142
  - RBAC/تدقيق على مسارات الـreset الهدّامة داخل FastAPI (سلوك قائم سابقاً، غير مُستحدث):
    routes_finance.py:5668,5672,5684-5685 · routes_extended.py:2585
```

---

## 7. حراسة عدم التعديل (Mutation Guard)

```text
FILES_CHANGED (app/runtime config) = NONE
.env FILES TOUCHED = NONE
DEPLOY / RESTART OF PRODUCTION = NONE
DB WRITES = NONE (كل الوصول GET/HEAD فقط؛ قراءة Supabase الوحيدة كانت select=id limit=1)
PRODUCTION LOGIN ATTEMPTS = NONE (تجنباً لقفل brute-force)
```

تعديلات كود جانبية في هذه الجلسة (غير مالية، غير متعلقة بالإنتاج، لرفع أخطاء lint حاجبة قديمة):
- 11 `except:` مكشوف → `except Exception:` في ملفات `backend/tests/*`
- `routes_finance.py` و`routes_workshop_config.py`: تمرير نسخة `dict(doc)` إلى `insert_one` لمنع تسريب `ObjectId` في الاستجابة.
