# LEGACY FILES PRESERVATION MIGRATION — EXECUTED ✅  +  PRE-DEPLOY READINESS

Authorised by the owner. Executed. Verified. **Not deployed.**

---

## 1. نتيجة الترحيل

```text
MODE = APPLY
files                  = 28
uploaded_verified      = 28   (التشغيل الأول)
skip_already_present   = 28   (تشغيل ثانٍ للتحقق من الـidempotency)
conflict               = 0
failed                 = 0
bytes_uploaded         = 21,945,944
sources_unchanged      = 28
sources_modified       = 0
files_deleted          = 0
files_moved            = 0
db_references_changed  = 0
db_writes              = 0
```

**كل ملف تم التحقق منه بـSHA-256**: يُرفع، ثم **يُنزَّل مرة أخرى من التخزين**، ثم تُقارن البصمة.
`sha256_source == sha256_readback` لكل الـ28 ملفاً.

### التوزيع
| surface | action | count | bytes |
|---|---|---|---|
| finance_audit_evidence | MIGRATE_LEGACY_QUARANTINE | 9 | 150 |
| payment_receipt | MIGRATE_LEGACY_QUARANTINE | 5 | 217 |
| payment_receipt | MIGRATE_NORMAL | 1 | 67 |
| template | MIGRATE_NORMAL | 3 | 8,193,213 |
| vehicle | MIGRATE_LEGACY_QUARANTINE | 3 | 4,053,058 |
| vehicle | MIGRATE_NORMAL | 7 | 9,699,239 |
| **الإجمالي** | | **28** | **21,945,944** |

### تخطيط المفاتيح
```text
MIGRATE_NORMAL            -> workshop-erp/{surface}/{entity}/{sha16}-{name}
MIGRATE_LEGACY_QUARANTINE -> workshop-erp/legacy-quarantine/{surface}/{entity}/{sha16}-{name}
payment receipt (NORMAL)  -> workshop-erp/operation-payment-receipts/{op_id}/{name}
                             (المفتاح الحتمي الذي يحلّه مسار الخدمة أصلاً ⇒ قابل للخدمة فوراً)
```
المفاتيح **content-addressed** (بادئة SHA) ⇒ حتمية وقابلة لإعادة التشغيل بلا تكرار.
28 مفتاحاً فريداً من 28، صفر مفتاح مشوّه، صفر `..`.

---

## 2. إثباتات عدم الهدم

| الإثبات | النتيجة |
|---|---|
| بصمات المصادر قبل/بعد (`sha256sum` لكل الـ28) | **متطابقة تماماً** — `diff` فارغ |
| عدد ملفات المصدر | 28 قبل · 28 بعد |
| ملفات محذوفة / منقولة | **0 / 0** |
| مراجع قاعدة البيانات المُغيَّرة | **0** |
| كتابات قاعدة بيانات من السكربت | **0** — السكربت لا يحتوي `insert_one` / `update_one` / `delete_one` / `delete_many` إطلاقاً |
| `operations` count | **39** قبل · **39** بعد |
| `chart_of_accounts` count | **12** قبل · **12** بعد |
| الاستبدال الصامت | مستحيل — الكائن الموجود بمحتوى مختلف يُبلَّغ `CONFLICT` ولا يُكتب فوقه |
| إعادة التشغيل | **28 SKIP_ALREADY_PRESENT** — idempotent |

## 3. عزل الملفات المحجوزة
```text
grep -rn "legacy-quarantine" backend/ frontend/src/  =>  0 نتيجة
```
لا يوجد أي مسار في الخلفية أو الواجهة يقرأ من بادئة `legacy-quarantine/` ⇒ الـ17 ملفاً المحجوزة
**محفوظة لكن غير قابلة للوصول عبر أي نقطة نهاية عادية**، تماماً كما اشترطت.

## 4. حدود صريحة (ما لم يحدث)
الـ11 ملفاً `MIGRATE_NORMAL` **محفوظة في التخزين لكن غير مربوطة بسجلاتها** في قاعدة البيانات، لأن
`db_references_changed = 0` بأمرك. الاستثناء الوحيد: **إيصال السداد الواحد** استُخدم له المفتاح الحتمي
الذي يحلّه مسار الخدمة ⇒ **قابل للخدمة فوراً بلا أي تغيير في قاعدة البيانات**.
ربط بقية السجلات (`storage_path`) يحتاج إذناً منفصلاً لأنه كتابة في قاعدة البيانات.

## 5. الاختبارات
- `backend/tests/test_legacy_files_preservation.py` — **15/15 PASS** (تتحقق من: المانيفست يغطي 28 · صفر هدم ·
  كل مدخل مُتحقَّق بـSHA · صفر conflict/failed · كل مصدر ما زال موجوداً ببصمة مطابقة · المفاتيح فريدة وسليمة ·
  الـ17 محجوزة تحت البادئة الخاصة · الـ11 العادية ليست تحتها · بادئة الحجر غير مُشار إليها في أي كود ·
  الـ15 دليلاً مالياً كلها محفوظة ومنها 14 غير صالح · مفتاح الإيصال = ما يحلّه المسار · **سحب فعلي من
  التخزين ومقارنة بصمة** · السكربت غير هدّام بنيوياً · المانيفست يطابق التصنيف)
- الحزمة الكاملة لهذه الجلسة: **92/92 PASS**
  (`test_p1_sec_upload_and_reset_guard` + `test_p1_sec_upload_functional` +
  `test_p0_dead_destructive_code_removal` + `test_legacy_files_preservation`)

---

## 6. بناء الإنتاج

```text
cd /app/frontend && yarn build
BUILD_EXIT = 0   ·   المدة 29.75s   ·   صفر errors   ·   صفر warnings
output = /app/frontend/build (16 MB)
entry  = main.8a3bf6a3.js      (الإنتاج الحالي عليه main.35a8f1ca.js — أرتيفاكت 2026-08-20 قديم)
css    = main.a57d9888.css
code-splitting = مُفعَّل الآن (chunks متعددة) بعد أن كان الإنتاج حزمة واحدة
```

## 7. فحص جاهزية النشر النهائي
```text
status = PASS  ·  findings = []  ·  destructive_db_startup_confirmed = false
compilation_passed · env_files_ok · frontend_urls_in_env_only · backend_urls_in_env_only
cors_allows_production_origin · supervisor_config_valid · auth_redirect_url_valid
gitignore/dockerignore لا يحجبان ملفات مطلوبة · لا أسرار مثبتة في الكود
requests==2.32.5 مثبَّت في requirements.txt (يعتمد عليه core/object_storage.py)
```

---

## 8. 🔴 شرط واحد إلزامي قبل النشر (إجراء إعداد من جهتك، لا كود)

الأسطح الستة للرفع صارت كلها تعتمد على Object Storage، وهو يحتاج **`EMERGENT_LLM_KEY`**.

```text
backend/.env متتبَّع في git؟            = NO  (أُزيل في 0ceb2ddc بتاريخ 2026-09-02)
EMERGENT_LLM_KEY موجود في backend/.env؟ = YES (لكنه غير مُتتبَّع ⇒ لن يصل عبر git)
المنصة تحقنه في process env؟            = NO  (مثبت من /proc/<backend_pid>/environ: 0 تطابق)
INTEGRATION_PROXY_URL يُحقَن؟            = YES (supervisor: https://integrations.emergentagent.com)
                                          ولدى الكود قيمة افتراضية لنفس العنوان ⇒ ليس نقطة فشل
```

**النتيجة**: إن لم يكن `EMERGENT_LLM_KEY` مضبوطاً في **إعدادات بيئة المنصة** للنشر، فإن كل رفع أو تنزيل
لملف بعد النشر سيُرجع **`503 object_storage_not_configured`** (فشل صريح ومُعلَن، لا fallback صامت،
ولا كتابة على قرص مؤقت).

**المطلوب منك قبل الإذن بالنشر**: تأكيد وجود `EMERGENT_LLM_KEY` في إعدادات بيئة الإنتاج على المنصة.
**لم ألمس أي `.env` ولم أضع أي قيمة.**

ملاحظة: هذا **لا يؤثر على الترحيل المُنفَّذ** — الـ28 ملفاً محفوظة ومُتحقَّق منها بالفعل.

---

## 9. حراسة نهائية
```text
LEGACY_PRESERVATION_EXECUTED = YES (28/28 verified)
FILES_DELETED = 0 · FILES_MOVED = 0 · DB_REFERENCES_CHANGED = 0 · DB_WRITES = 0
SOURCE_INTEGRITY = IDENTICAL (28/28 SHA-256)
PRODUCTION_BUILD = PASS (exit 0, zero warnings)
PRE_DEPLOY_READINESS = PASS (findings = [])
DEPLOY = NO  ·  RESET_EXECUTED = NO  ·  SEED_EXECUTED = NO
FINANCIAL_MUTATION = NO · ACCOUNTING_ENGINE_CHANGED = NO
ENV_CHANGED = NO · SECRETS_CHANGED = NO · PHASE_2A_STARTED = NO
```

## 10. مخرجات
- `scripts/preserve_legacy_upload_files.py` — المُنفِّذ (dry-run افتراضي، يتطلب `--apply --i-understand-this-writes`)
- `memory/discovery/LEGACY_FILES_PRESERVATION_MANIFEST.json` — المانيفست الكامل بكل بصمة
- `memory/discovery/legacy_sources_before.sha256` — بصمات المصادر قبل الترحيل (للمقارنة المستقبلية)
- `backend/tests/test_legacy_files_preservation.py` — 15 اختباراً
- `/app/frontend/build` — أرتيفاكت الإنتاج الجاهز (غير منشور)
