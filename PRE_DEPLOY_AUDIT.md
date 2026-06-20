# 🔍 تقرير التدقيق الهندسي قبل النشر — Parts Pro / FIXSA
**المدقّق:** Senior Pre-Deployment Auditor (قراءة فقط — لا تعديلات في هذه الجولة)
**التاريخ:** 2026-06-20
**النطاق:** كامل الشجرة (backend + frontend)

> كل ادعاء أدناه مدعوم بـ `file:line` تمّت قراءته فعليًا. ما لم يُتحقق منه مُدرَج صراحةً في قسم «الفجوات غير المؤكَّدة».

---

## ⚠️ تصحيح وصف النظام (مهم قبل أي شيء)
وصف المهمة ذكر: «Backend: FastAPI + **MongoDB**، Frontend: **React 19 + TypeScript + Vite**».
**الواقع المُتحقَّق منه:**
- **النسخة الحيّة المنشورة فعليًا:**
  - Backend: `/app/backend` — FastAPI، يعمل عبر `uvicorn server:app` (`/etc/supervisor/conf.d` → `directory=/app/backend`). قاعدة البيانات **الأساسية = Supabase (Postgres)** عبر `supabase_service.py`، و**MongoDB ثانوية** فقط لطبقة منع التكرار + الحالة + التدقيق.
  - Frontend: `/app/frontend` — **React 18.3.1 + CRA (react-scripts 5.0.1) + craco**، **200 ملف `.jsx`، صفر `.tsx`** (`frontend/package.json`؛ `directory=/app/frontend` `command=yarn start`).
- وصف «React 19 + TS + Vite + MongoDB» يطابق شجرة **`/app/autoprofit-pro`** وهي **نسخة مكرّرة خاملة** (لا تعمل كخدمة).

---

## 1) الملخّص التنفيذي

**هل النظام جاهز للنشر الإنتاجي؟ → لا (بشكل مشروط).**
السلامة المحاسبية (المحرك المركزي، توازن القيد، منع التكرار) **ممتازة وجاهزة**. الموانع تتعلق بـ**أمن الوصول** و**نظافة الشجرة**.

**أهم 3 موانع (P0):**
1. **🔴 صلاحيات RBAC قابلة للانتحال (spoofable):** الهوية تُقرأ من ترويسات غير مُوثَّقة (`x-user-role`) ولا توجد بوابة مصادقة (`Depends(get_current_user)`) على مسارات المال/العمليات. أي طلب يحمل `x-user-role: admin` يتجاوز RBAC والأربع أعين. — `core/rbac.py:155-167`, `routes_financial_actions.py:30-32`.
2. **🔴 CORS مفتوح بالكامل (`*`)** على واجهة برمجية مالية — `backend/.env:CORS_ORIGINS=*` + `server.py:415-417`. مع البند (1) أي موقع خارجي يستطيع استدعاء واجهات المال.
3. **🟠→🔴 شجرة مصدر مكرّرة مُتتبَّعة في git** (`autoprofit-pro/`, 73 ملفًا) ومعها workflow نشر مستقل `autoprofit-pro/.github/workflows/deploy.yml` (push→main يبني/ينشر صورة Docker للنسخة الخاطئة). خطر نشر التطبيق الخطأ والتباس.

> ملاحظة: لو كان النشر داخل شبكة موثوقة/مستأجر واحد فقط، يَنزل البند (1) إلى P1 (مخاطرة مقبولة بقرار المالك «تسجيل بالاسم فقط»).

---

## 2) الجدول المرتّب حسب الخطورة

| # | الخطورة | المحور | file:line | الدليل (سطر فعلي) | الإصلاح المقترح |
|---|---|---|---|---|---|
| 1 | 🔴 P0 | D/B | `core/rbac.py:155-167` ، `routes_financial_actions.py:30-32` ، `routes_action_runtime.py` (approve/commit) | `extract_identity` يقرأ `headers.get("x-user-role")`؛ لا يوجد أي `Depends(get_current_user)` على routers المال/العمليات (grep أرجع `auth_jwt.py` فقط). انتحلتُ `x-user-role:admin` فعليًا ونجح إصدار فاتورة. | اربط هوية RBAC بـ`auth_jwt.get_current_user` (الـ`sub` من JWT المُوقَّع) بدل الترويسة الخام؛ أضِف الاعتمادية على routers المال/العمليات/الـruntime. |
| 2 | 🔴 P0 | D | `backend/.env` (`CORS_ORIGINS=*`) ، `server.py:415-417` | `allow_origins=["*"]`، `allow_credentials=False`. | حدِّد النطاقات الفعلية للواجهة في الإنتاج (`CORS_ORIGINS=https://app-domain`). |
| 3 | 🔴 P0 | A | `autoprofit-pro/` (73 ملف في `git ls-files`) ، `autoprofit-pro/.github/workflows/deploy.yml:1-13` | شجرة Vite/TS/React19 خاملة مُتتبَّعة + workflow `on: push [main,production]` يبني صورة لـghcr.io. | احذف الشجرة من المستودع (أو انقلها لمستودع مستقل) واحذف/عطّل الـworkflow. |
| 4 | 🟠 P1 | B | `core/accounting_engine.py:63,312` ، `core/financial_actions.py:35` | المبالغ المالية `round(float(...),2)` — **float لا Decimal**. التوازن يُقاس بهامش `abs(debit-credit)>0.01` (`accounting_engine.py:308`). | استخدم `Decimal` (quantize) في حسابات المال لتفادي تراكم خطأ الفاصلة العائمة. |
| 5 | 🟠 P1 | D | `auth_jwt.py:19` | `ACCESS_TOKEN_EXPIRE_DAYS = 30` — توكن طويل العمر جدًا لتطبيق مالي. | قلّل المدة (مثلًا 1–7 أيام) + refresh token، أو ربط بانتهاء جلسة. |
| 6 | 🟠 P1 | C | `core/assistant_kernel.py:331,340` | استدعاء `LlmChat.send_message` بدون `timeout=` صريح (بينما `llm_helpers.py:28,38,80` تضبط timeout). | اضبط مهلة صريحة على المسار الأساسي للـLLM لتفادي تعليق الطلب/502. |
| 7 | 🟠 P1 | C | `core/ai_context.py:50` ، `core/assistant_kernel.py:489-495` | يُبنى snapshot يتضمن بيانات مالية (`financial_impact`) ويُرسل للـLLM الخارجي (Emergent/Anthropic). | تقليل/إخفاء (redact) البيانات الحسّاسة قبل الإرسال، وتوثيق سياسة الخصوصية للمالك. |
| 8 | 🟠 P1 | C | `core/assistant_kernel.py:615` | `fallback_used=False` ثابت + تعليق «Groq fallback wired in Phase 3B» — لم أتأكد أن fallback الثانوي مُفعّل فعلًا. | تحقّق/فعّل سلسلة fallback (Ollama→Emergent→Groq) واختبرها عند تعطّل المزوّد. |
| 9 | 🟡 P2 | B | `routes_extended.py:1611-1646` | مسار fallback داخل `_safe_insert_journal_entry` يُدرج مباشرةً (بدون توازن/idempotency المحرك) إذا رمى المحرك استثناءً. | اجعل الـfallback يمرّ بـ`_insert_adaptive` مع تحقق التوازن، أو سجّل تنبيهًا حادًّا. |
| 10 | 🟡 P2 | A | 447 × `print(` في backend (`routes_finance.py`=47، `server.py`=28، `routes_extended.py`=24، +سكربتات) | لوقينق تشخيصي عبر `print` رغم وجود `get_logger`. | استبدل `print` بالـlogger في كود التشغيل؛ انقل السكربتات لمجلد `scripts/`. |
| 11 | 🟡 P2 | B | يُكتب `[PARTY:..]/[VEHICLE_REF:..]` في `routes_finance.py`، `server.py`، والواجهة `JournalEntries.jsx:538` | الوصف المخزّن ما زال يضمّن وسومًا خامًا (تُنظَّف **عند العرض فقط** عبر `sanitizeEntryText`/`cleanDescription` في `JournalEntries.jsx:957,1116`). | انقل الطرف/المركبة إلى أعمدة حقيقية بدل حقنها في الوصف. |
| 12 | 🟡 P2 | A | `JournalEntries.jsx:290,576` | يستخدمان `sanitizeEntryText` فقط (يُزيل الوسوم) دون `cleanDescription` (إزالة تكرار الطرف/اللوحة). | وحّد الاستخدام على `cleanDescription` في كل مواضع العرض. |
| 13 | 🟡 P2 | A | 11 × `console.log` بالواجهة، 6 × TODO/FIXME | لوقينق/ملاحظات متروكة. | تنظيف قبل النشر. |

---

## ✅ ما تم التحقق منه أنه **سليم** (نقاط قوة)

| المحور | النتيجة | الدليل |
|---|---|---|
| B — الكاتب الواحد | ✅ لا توجد كتابة مباشرة غير محكومة في `journal_entries`. الكتابات الوحيدة المتبقية (`routes_extended.py:1614,1627,1646`) كلها **داخل** `_safe_insert_journal_entry` كـ**fallback** بعد محاولة المحرك أولًا (`:1608-1609`). المسارات التي ذُكرت سابقًا (routes_finance 2940/3079/3098, smart_accounting 238, suppliers 505, firewall 412, server 892/1070/1077, routes_extended 2135) **لم تعد تحوي insert مباشرًا** (grep). | `routes_extended.py:1603-1649` |
| B — توازن القيد | ✅ المحرك يرفض غير المتوازن. | `core/accounting_engine.py:308-310` |
| B — منع التكرار | ✅ فهرس فريد على `tx_hash` (race-safe) + `reference_id`. (اختُبر سابقًا: 12 خيط متزامن → قيد واحد فقط.) | `core/accounting_engine.py:134-135` |
| B — الأربع أعين | ✅ يُفرض على الـbackend، يمنع اعتماد المُنشئ لإجرائه، والعلَم يُقرأ صحيحًا (افتراضي true). | `core/action_runtime.py:79,543` |
| B — صحة الحالة بعد الإقلاع | ✅ المسودات/الموافقات/التدقيق على MongoDB مع hydrate. | `core/runtime_store.py:47-49,99-117` |
| D — الأسرار | ✅ لا أسرار مُصلّبة في الكود؛ كلها عبر `os.environ`؛ `.env` **غير مُتتبَّع في git** (`.gitignore:92-94,...`). الواجهة لا تكشف أي مفتاح (نصوص الواجهة فيها اسم الموديل فقط للعرض). | `git ls-files` (فارغ) ، `frontend/.env` |
| D — security headers | ✅ X-Frame-Options/X-Content-Type-Options/CSP frame-ancestors. | `server.py:531-535` |
| D — فهارس Mongo | ✅ فهارس فريدة مُنشأة برمجيًا. | `core/accounting_engine.py:134-135`, `core/runtime_store.py:47-49` |
| C — مفتاح الـAI | ✅ `EMERGENT_LLM_KEY` يُقرأ في الـbackend فقط؛ موديل `claude-sonnet-4-6`؛ يوجد fallback Ollama→Emergent. | `core/assistant_kernel.py:309,320,538-547` |

---

## 3) الفجوات غير المؤكَّدة (لم أتمكن من التحقق — أعلنها صراحةً)

1. **build إنتاج الواجهة لم يُنفَّذ** (CRA build بطيء > دقيقتين). دليل غير مباشر: خادم التطوير يعمل (الواجهة تُقلِع) ⇒ الكود يُترجم، لكن لم أُجرِ `yarn build` فعليًا.
2. **تحليل الاعتماديات غير المستخدمة لم يُجرَ بشكل شامل** (يتطلب `depcheck`/`pip-check`) — لم أؤكّد كل سطر في `package.json`/`requirements.txt`.
3. **لم أفحص كل ملفات الـAI الـ20+ فرديًا** — عيّنت `assistant_kernel.py`, `llm_helpers.py`, `ai_context.py`. البقية (routes_diesel_*, routes_moltbot, routes_dtc, parts_ocr, ...) لم تُفحص سطرًا بسطر.
4. **مهلة `LlmChat.send_message` الفعلية** — لم أتأكد إن كانت `emergentintegrations` تضع مهلة افتراضية داخلية (البند 6).
5. **استعلامات N+1** — لم أُجرِ تنميطًا (profiling) فعليًا؛ حساب الذمم يستخدم استعلامين فقط (`routes_finance.py:3527-3528`) وهو ليس N+1، لكن لم أفحص كل المسارات.
6. **سلوك الانتحال على كل المسارات** — أكّدته على `finance-actions` فقط؛ لم أختبر كل endpoint.
7. **منطق مكرّر بين الملفات** — وُحِّدت كتابة القيود في المحرك، لكن لم أقارن كامل منطق القراءة المالية بحثًا عن تكرار متبقٍّ.

---

## ملاحظة منهجية
هذه جولة **قراءة فقط**؛ لم يُعدَّل أي ملف من ملفات الكود. التعديلات تنتظر موافقتك، ويُقترح البدء بالموانع P0 بالترتيب (1 → 2 → 3).
