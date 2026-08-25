# FULL-STACK PRODUCTION REALITY AUDIT — التقرير الموحّد النهائي
نظام إدارة الورشة (finmodule-sync) + مساعد كاترينا · تاريخ: 2026-06
**الوضع: READ-ONLY بالكامل — صفر تعديل بيانات / صفر migration / صفر reverse_entry.**
Checkpoint: `PRODUCTION_REALITY_AUDIT.md` (Phases 1–7). هذا الملف يكمل كل ما كان NOT VERIFIED/PARTIAL/UNKNOWN.

---
## 1) COVERAGE MATRIX الكامل
| # | المجال | الحالة | الدليل / السبب |
|---|---|---|---|
| 1 | System Inventory | ✅ VERIFIED | package.json / requirements.txt / tree |
| 2 | Architecture Map | ✅ VERIFIED | flat routes + domains/ + financial_control/ |
| 3 | Pages / Routes | ✅ VERIFIED (جرد) · 🟡 سلوك per-page NOT VERIFIED | 62 صفحة، مسارات App.js، عامة: login/approval/report/track |
| 4 | Buttons / Actions | 🟡 PARTIAL | 472 onClick + 1581 data-testid (جرد كمي)؛ تنفيذ كل زر E2E = NOT VERIFIED (يلزم testing_agent) |
| 5 | Fields / Forms | 🟡 PARTIAL | 33 form؛ التحقق الخلفي per-field = NOT VERIFIED |
| 6 | CRUD paths | 🟡 PARTIAL | مسارات موجودة + RBAC متفاوت؛ DELETE للقيود = عكسي (مؤكد) |
| 7 | API endpoints | ✅ VERIFIED (جرد ~500) · 🟡 سلوك per-endpoint NOT VERIFIED | 518 decorator، ~50 راوتر |
| 8 | Authorization / RBAC | 🔴 PARTIAL/FAIL | إنفاذ متفرّق؛ **`/api/users` بلا حارس دور** (P0-SEC-USERS) |
| 9 | IDOR / BOLA | 🟡 NOT VERIFIED | يلزم اختبار per-object (لم يُنفَّذ — قد يتطلب طلبات معدّلة على الإنتاج) |
| 10 | service_role / RLS bypass | ✅ VERIFIED | الخلفية service_role تتجاوز RLS؛ الواجهة لا تلمس DB. الأمان = الخلفية فقط |
| 11 | Katrina tools/permissions/CRUD | ✅ VERIFIED | 28 أداة read-only افتراضياً؛ writes خلف BOT_ALLOW_WRITES + اعتماد |
| 12 | Prompt Injection (direct/indirect) | 🟡 PARTIAL | محتوى غير موثوق يدخل الـprompt بلا guards؛ الأثر محدود (bot للقراءة). Exploit = NOT VERIFIED |
| 13 | Business Logic SSOT | 🟡 PARTIAL | مالياً موحّد (AccountingEngine)؛ لكن ازدواج عبر المصادر (P0-DUP-AR) |
| 14 | State Machines | ✅ VERIFIED | four-eyes + approval tiers + action_runtime DRAFT→…→COMMITTED |
| 15 | Transaction integrity | 🟡 PARTIAL | لا ACID عبر PostgREST؛ تعويض تطبيقي (compensation) قد يفشل |
| 16 | Concurrency | 🟡 NOT VERIFIED | يلزم اختبار تزامن (محظور: قد يُنشئ بيانات/سباقات على الإنتاج) |
| 17 | Idempotency | 🟡 PARTIAL | قانوني per reference_id ✅؛ idempotency middleware **in-memory** (غير معمّم) |
| 18 | Audit Trail | ✅ VERIFIED | accounting_audit + journal_attribution + auth_audit + llm_traces + _audit×50 |
| 19 | File / Upload security | 🔴 FAILED | path traversal + بلا فحص نوع/حجم + قرص محلي زائل (P1-SEC-UPLOAD) |
| 20 | Error handling | 🟡 PARTIAL | fail-closed مالياً ✅؛ لكن silent memory fallback في routes_users |
| 21 | Observability | ✅ VERIFIED (traces) · 🟡 metrics NOT VERIFIED | tr-* + audit؛ لا metrics/APM |
| 22 | Performance | 🟡 PARTIAL | journal يجلب كامل الدفتر ثم يفلتر بايثون (مقبول الآن)؛ latency NOT VERIFIED |
| 23 | Caching | 🟡 PARTIAL | perf_cache TTL 15s in-memory single-process؛ إبطال namespace |
| 24 | Environment / Secrets | 🟠 P1 | `.env` في git (خاص)؛ **تدوير الأسرار مؤجّل**؛ لا تسريب للواجهة/AI ✅ |
| 25 | CI/CD | 🟡 PARTIAL | Emergent (.emergent/emergent.yml + cron)؛ لا بوابات test/lint تقليدية مرئية |
| 26 | Dependencies | 🟡 NOT VERIFIED | لم يُشغَّل npm/pip audit؛ ملاحظة: `lucide-react ^1.7.0` قيمة غير معتادة — للمراجعة |
| 27 | Backup / Restore | 🟡 PARTIAL | `/admin/backup/drive` + export sheets موجودة؛ **restore غير مُختبر** = NOT VERIFIED |
| 28 | Responsive / Mobile | 🟡 PARTIAL | 809 responsive class + viewport meta؛ runtime NOT VERIFIED |
| 29 | Accessibility | 🟡 PARTIAL (ضعيف) | 39 aria فقط عبر ~140 مكوّن — تغطية منخفضة |
| 30 | Search / Filters | ✅ VERIFIED (finance) · 🟡 غيرها PARTIAL | journal server-side كامل؛ ilike في مسارات أخرى |
| 31 | Notifications | 🟡 PARTIAL | WhatsApp Infobip (تحت write-flag) + sonner؛ حالات التسليم غير متتبَّعة (مؤجّل موثّق) |
| 32 | Full E2E journeys | 🟡 NOT VERIFIED | يلزم testing_agent (غير تدميري) — لم يُنفَّذ بعد |
| 33 | Production Readiness | 🔴 NOT READY | بسبب P0-DUP-AR + P0-SEC-USERS |

---
## 2) الحقائق المؤكّدة (VERIFIED) — أساس سليم
- **كاتب محاسبي وحيد:** كل الكتابة عبر `AccountingEngine.post_entry`؛ صفر كتابة مباشرة على `journal_entries` من مسارات حيّة (الوحيدة في سكربت offline). الدفتر متوازن حياً 205,570.06 = 205,570.06، صفر قيود غير متوازنة.
- **حد الأمان في الخلفية:** الواجهة تكلّم FastAPI فقط (صفر supabase-js في المتصفح)؛ auth_guard (JWT httpOnly) على `/api/*` عدا (login/refresh/logout/google-session + مسارات token عامة)؛ RBAC عبر `config/role_permissions.json` + APPROVER_ROLES.
- **كاترينا آمنة الوضع:** 28 أداة كلها قراءة افتراضياً (BOT_ALLOW_WRITES غير مضبوط)، بوابة إيرادات fail-closed، لا كتابة مالية عبر الأدوات (تمر عبر اعتماد + أربع أعين).
- **آلة حالة الاعتماد:** four-eyes (منشئ≠مراجع≠معتمِد، تجاوز المدير موثّق)، شرائح مبالغ (AUTO ≤1000 → اعتماد تلقائي، ثم PENDING_REVIEW→PENDING_APPROVAL→APPROVED/REJECTED)، provenance guard يرفض تنفيذ AI_SUGGESTION/TEST_ARTIFACT.
- **سجل تدقيق شامل:** accounting_audit + journal_attribution («من فعل ماذا») + auth_audit + llm_traces (tr-*).

---
## 3) النتائج المصنّفة P0/P1/P2/P3

### 🔴 P0 (حاجز إنتاج)
**P0-DUP-AR — ازدواج الذمم في الدفتر الخام (مالي).**
- Observed: رصيد 005 خام = 26,901 مقابل قانوني = 14,832 (فجوة ~12,069).
- Root cause: لا معرّف عمل موحّد للمركبة يمنع الازدواج عبر المصادر؛ طبقة تاريخية (active_vehicle_ar_repair/fin_engine_align_v1/hist_vehicle_ar_repair/operation مؤقتة) تتعايش مع `[CANONICAL_BUSINESS]` لنفس المركبة بلا إلغاء متبادل. الدفعات تُسوّي القانونية فقط.
- Impact: تضخّم AR/إيراد في الدفتر والميزان (عروض الذمم القانونية سليمة لأنها تقرأ من حالة المركبة).

**P0-SEC-USERS — Broken Access Control على إدارة المستخدمين (أمني).**
- Evidence (code): `routes_users.py` — `GET/POST/PUT/DELETE /api/users` و`PUT /api/users/{id}` (يضبط `role` و`permissions`) **بلا أي فحص دور server-side**. `auth_guard` يطلب JWT صالحاً فقط (أي دور).
- Impact: أي مستخدم مُصادَق (حتى فني) يستطيع رفع نفسه إلى admin أو حذف مستخدمين → سيطرة كاملة تشمل المالية.
- ملاحظة: لم يُنفَّذ اختبار استغلال حي (يتطلب تعديل مستخدم = mutation ممنوعة). الدليل الكودي كافٍ.

### 🟠 P1 (خطر إنتاج عالٍ)
- **P1-SEC-UPLOAD:** `routes_vehicle_files.py` upload يستخدم `file.filename` الخام لبناء المسار → path traversal؛ بلا فحص content-type/امتداد/حجم؛ يكتب لقرص محلي (زائل على المنصة).
- **P1-SECRETS:** تدوير JWT_SECRET / SUPABASE_SERVICE_ROLE_KEY / EMERGENT_LLM_KEY مؤجّل (`.env` متتبَّع في git خاص لأغراض النشر).
- **P1-AUTHZ-COVERAGE:** إنفاذ RBAC متفرّق وغير موحّد؛ عدة مسارات مُعدِّلة بلا حارس دور صريح مرئي (يلزم تحقق per-endpoint شامل).

### 🟡 P2 (عيوب مهمة)
- **P2-IDEMPOTENCY:** idempotency middleware in-memory dict (يضيع عند إعادة التشغيل/متعدد النسخ).
- **P2-RATELIMIT:** rate limit in-memory single-process (يمكن تجاوزه في نشر متعدد النسخ).
- **P2-TX:** لا ACID عبر PostgREST؛ تعويض تطبيقي (create op ثم journal) قد يترك حالة جزئية إن فشل التعويض.
- **P2-UPLOAD-DURABILITY:** ملفات المركبات على قرص محلي زائل بدل object storage.
- **P2-PROMPT-INJECTION:** محتوى غير موثوق (أسماء عملاء/ملاحظات/قطع) يدخل prompt كاترينا بلا sanitization/delimiters (الأثر محدود بالقراءة).
- **P2-USER-FALLBACK:** routes_users يسقط بصمت إلى ملف JSON محلي عند خطأ DB (يخفي الفشل).
- **P2-AUTO-APPROVE:** اعتماد تلقائي للمبالغ ≤1000 بلا بشر — سياسة تحتاج تأكيد المالك.

### 🔵 P3 (تحسينات)
- **P3-DEADCODE:** صفحات `*_old.jsx` (BalanceSheet/CashFlow/Customers/Suppliers/Technicians/IncomeStatement) + orphans (Knowledge/DieselExpertChat/InjectorDiagnostics).
- **P3-A11Y:** تغطية aria منخفضة (39 عبر ~140 مكوّن).
- **P3-DEPS:** مراجعة `lucide-react ^1.7.0` + تشغيل audit للتبعيات.

---
## 4) CANDIDATE REVERSAL LEDGER (قراءة فقط — لم يُنفَّذ عكس)
مصدر: `/app/memory/candidate_reversal_ledger.json` (سكربت `tests/candidate_reversal_ledger_readonly.py`).
**مرشّحات آمنة (يوجد قيد قانوني + طبقة تاريخية لنفس المركبة): 10 مركبات، إجمالي طبقة تاريخية = 14,136 ر.س.**
| المركبة | القانوني | تاريخي للعكس | القيود |
|---|---|---|---|
| b9fe95f6 | 13,887 | 5,981 | 5abdbff4 align 3181 · e90e9a39 active 500 · 74045e29 operation 2300 |
| a422209f | 6,118 | 2,500 | 0e83fc0c operation 2500 |
| d5376421 | 4,278 | 2,428 | e3ef28ca active 2428 |
| a57b698d | 1,800 | 1,975 | 6e010906 active 1975 |
| c92405eb | 500 | 500 | a31b2a3a active 500 |
| f6590225 | 302 | 302 | 2933cb91 active 302 |
| c02cc9c7 | 300 | 300 | b31a49f4 active 300 |
| 0ee51492 | 300 | 150 | 6ddcabf8 operation 150 |
| bea27237 | 250 | 0 (مقاصّة سابقة) | — لا إجراء |
| b885d618 | 2,300 | 0 (معكوس سابقاً) | — لا إجراء |

**طبقة تاريخية بلا قيد قانوني (لا تُعكَس تلقائياً — قرار حالة بحالة): 5 مركبات، إجمالي 2,400** (496cff37 800 · f0946eb4 800 · c5bfe993 800 · اثنتان net-zero).

⚠️ **تحذير دقّة الإصلاح:** المبلغ الصحيح للعكس لكل مركبة = (ledger_ar − canonical_ar) لتلك المركبة، **وليس** مجموع الطبقة التاريخية كاملاً — لأن الدفعات قد تكون استهلكت جزءاً. يجب dry-run لكل مركبة يثبت أن العكس يُصفّر الفجوة دون تجاوز، قبل أي تنفيذ.

---
## 5) خطة الإصلاح الدقيقة (مقترحة — تنتظر موافقتك الصريحة)
**لن أنفّذ أي إصلاح/mutation قبل موافقة منفصلة صريحة منك.**

### P0-DUP-AR (الترتيب)
1. `snapshot` كامل للدفتر + hash قبل أي تعديل.
2. dry-run per-vehicle: يحسب excess = ledger_ar − canonical_ar، ويختار مجموعة قيود تاريخية عكسها يساوي excess تماماً (بلا تجاوز).
3. عكس عبر `AccountingEngine.reverse_entry` حصراً (بلا حذف) للمرشّحات المؤكّدة.
4. القرار اليدوي: legacy-without-canonical (2,400) + دفعات/ذمم ناقصة الترحيل.
5. **إصلاح الجذر:** حارس في الترحيل القانوني يفحص/يعكس طبقة تاريخية سابقة لنفس المركبة قبل الترحيل + تقاعد سكربتات الإصلاح.
6. إعادة التسوية: إثبات فجوة 0.00 + `testing_agent` انحدار.

### P0-SEC-USERS
- إضافة حارس دور server-side على كل `/api/users*` (admin/canManageUsers فقط) عبر `Depends(_require_admin_actor)` (نمط موجود في `routes_financial_reset.py`).
- منع رفع الدور الذاتي (لا يعدّل المستخدم دوره).

### P1
- SEC-UPLOAD: تعقيم اسم الملف (uuid + امتداد whitelist)، حد حجم، content-type، ونقل التخزين إلى Emergent Object Storage.
- SECRETS: تدوير الأسرار الثلاثة بعد تأكيد النشر.
- AUTHZ-COVERAGE: تدقيق per-endpoint وإضافة حراس موحّدة للمسارات المُعدِّلة.

---
## 6) EXACT PROPOSED MUTATIONS (للموافقة — غير منفّذة)
1. `reverse_entry` لـ~8 قيود تاريخية (b9fe95f6, a422209f, d5376421, a57b698d, c92405eb, f6590225, c02cc9c7, 0ee51492) بمبالغ تُحدَّد dry-run per-vehicle (سقف نظري 14,136، الفعلي = مجموع excess لكل مركبة).
2. تعديل كود (غير بيانات): حارس دور على routes_users + حارس تجاوز طبقة تاريخية في vehicle_finalization_posting + تعقيم رفع الملفات.
3. لا DELETE/UPDATE مباشر على أي جدول إنتاج.

## 7) ROLLBACK PLAN
- كل عكس هو قيد عكسي جديد عبر المحرك → **قابل للعكس بعكسٍ مضاد** (لا حذف، لا فقدان تاريخ). snapshot + hash قبل/بعد.
- تغييرات الكود عبر git checkpoints (rollback المنصة مجاني).

## 8) REGRESSION TESTS (بعد الموافقة)
- `test_p0_dup_ar_reconciliation.py`: بعد العكس، ledger_ar_per_vehicle == canonical_ar (فجوة 0.00)، الدفتر متوازن، idempotent (إعادة التشغيل delta=0).
- `test_users_authz.py`: غير المدير → 403 على POST/PUT/DELETE /api/users؛ منع رفع الدور الذاتي.
- `test_upload_security.py`: رفض `../` في الاسم، رفض امتداد/حجم غير مسموح.
- `testing_agent`: E2E frontend + سلامة تدفقات الاعتماد/الدفع (غير تدميري).

## 9) RECONCILIATION PROOF (معيار القبول)
- قبل: raw_ledger_ar_005 = 26,901 · canonical = 14,832.
- بعد الإصلاح المتوقّع: |raw_ledger_ar_005 − canonical_ar| ≤ 0.01 لكل مركبة وإجمالاً؛ الدفتر متوازن؛ صفر قيود معلّقة غير معكوسة.

## 10) PRODUCTION READINESS BLOCKERS
1. 🔴 P0-DUP-AR (ازدواج الذمم).
2. 🔴 P0-SEC-USERS (تصعيد صلاحيات عبر /api/users).
3. 🟠 P1-SEC-UPLOAD (path traversal).
(إضافة إلى مجالات NOT VERIFIED التي تحتاج تمريرة testing_agent غير تدميرية: E2E، IDOR/BOLA، concurrency، dependencies، restore.)

---
# الحالة النهائية: 🔴 NOT PRODUCTION READY
السبب: P0-DUP-AR + P0-SEC-USERS مؤكّدان بالدليل، وP1-SEC-UPLOAD. الأساس المعماري سليم لكن هذه الحواجز تمنع الجاهزية.
**لا إصلاح فعلي أو mutation إنتاج حتى موافقتك الصريحة المنفصلة.**
