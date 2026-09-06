# P0-DEAD-DESTRUCTIVE-CODE-REMOVAL + LEGACY-FILES-MIGRATION-CLASSIFICATION

Scope: exactly the two requested parts. No deploy · no migration · no reset · no DB mutation · no Phase 2A.

---

## PART A — إزالة الكود الهدّام الميت (P0)

### A1. ما حُذف
كان المسارَان يرفعان `410` كأول تعليمة، لكن أسفل الـ`raise` كان يقبع **كود هدّام كامل غير قابل للوصول**.
أي تعديل مستقبلي يحذف الـ`raise` كان سيُسلّحه فوراً.

| الدالة | نطاق الأسطر المحذوفة | عدد الأسطر | ما كان يحتويه |
|---|---|---|---|
| `reset_all_financial_data` (`routes_finance.py`) | 5600 → 5713 | **114** | حذف `operations` / `journal_entries` / `chart_of_accounts` / `invoices` على Supabase وMongo |
| `reset_ops_journals_keep_debts_only` | 5768 → 5959 | **192** | حذف كل القيود اليومية والعمليات غير المرتبطة بالذمم |
| **الإجمالي** | | **306 سطر** | |

الآن كل دالة = docstring + `raise HTTPException(410)` فقط. **لم يُستبدل بمسار آخر ولم يُفعَّل**، ولم تُحذف
نقطتا النهاية نفساهما (العقد العام محفوظ).

تحقق حي مُصادَق:
```text
DELETE /api/finance/reset-all-data                 -> 410 legacy_reset_all_data_disabled
DELETE /api/finance/reset-ops-journals-keep-debts  -> 410 legacy_keep_debts_only_disabled
```

### A2. مسح repository-wide لكل عملية هدّامة غير مُفلترة

| الموقع | الحالة | التصنيف |
|---|---|---|
| `routes_finance.py` | **صفر** `delete_many({})` أو `delete().neq()` بعد الحذف | REMOVED |
| `routes_extended.py:delete_all_operations` (`DELETE /api/operations`) | `require_destructive_authorization` قبل كل شيء | **GUARDED** |
| `server.py:reset_inventory_data` (`POST /api/admin/reset-inventory`) | مُحمَّى (كان **بلا أي مصادقة**) | **GUARDED** |
| `routes_accounts_chart.py:reset_accounts_chart` (`DELETE /api/accounts-chart/reset`) | **كان يمسح دليل الحسابات كاملاً على Supabase بلا `Request` ولا `confirm` ولا حراسة** — أُضيفت الحراسة الآن | **GUARDED (اكتشاف جديد)** |
| `clear_data.py` · `clean_and_add_services.py` · `adopt_unified_workflow_template.py` · `reset_primary_invoice_template.py` | سكربتات مستقلة تمسح مجموعات كاملة (منها `invoices`, `transactions`, `customer_receipts`) — أُضيف `require_destructive_cli` fail-closed | **GUARDED (CLI)** |
| `core/runtime_store.py:clear_all()` | بلا أي مُستدعٍ؛ أصبحت fail-closed بنفس الراية | **GUARDED** |
| `routes_templates_extended.py:436` · `core/prompt_registry.py:80` | `update_many({}, {...False})` — ثابتة «افتراضي واحد / نشط واحد»، ليست فقد بيانات | BENIGN |
| `core/memory_engine.py:87` · `routes_workshop_bot.py:644` | مُفلترة (TTL / نطاق جلسة) | BENIGN |

تحقق حي مُصادَق:
```text
DELETE /api/accounts-chart/reset?confirm=DELETE_ALL -> 403 destructive_operations_disabled (correlation_id)
DELETE /api/operations?confirm=DELETE_ALL           -> 403 destructive_operations_disabled (correlation_id)
python3 clear_data.py            -> REFUSED [clear_all_data]: ... Nothing was touched.
python3 clean_and_add_services.py -> REFUSED [clean_and_seed_services]: ... Nothing was touched.
python3 adopt_unified_workflow_template.py -> REFUSED ... Nothing was touched.
python3 reset_primary_invoice_template.py  -> REFUSED ... Nothing was touched.
```

### A3. الاختبارات (static / mocked فقط)
`backend/tests/test_p0_dead_destructive_code_removal.py` — **20/20 PASS**، تتضمن:
- كل دالة legacy تحتوي **تعليمة واحدة** بعد الـdocstring وهي `raise`
- نقطتا النهاية لم تُحذفا، ولم تُعَد تسليحهما خلف الحراسة
- الحراسة تُستدعى **قبل** أي `delete_many/update_many/delete` في كل مسار قابل للوصول (فحص AST بترتيب الأسطر)
- السكربتات الأربعة ترفض فعلياً عبر `subprocess` بلا الراية
- بوابة الـCLI ترفض بالترتيب: راية ← تصريح قاعدة البيانات ← وسيط تأكيد صريح
- `runtime_store.clear_all()` لا تلمس قاعدة البيانات بلا الراية
- مسح شامل: أي `delete_many({})` / `update_many({})` / `delete().neq("id","")` غير مُدرَج في قائمة السماح ⇒ فشل الاختبار

`RESET_EXECUTED = NO` · `DB_MUTATION = NO` · `DEPLOY = NO`

---

## PART B — تصنيف الملفات القديمة (READ-ONLY)

```text
MODE = READ_ONLY_CLASSIFICATION
files_moved = 0 · files_deleted = 0 · db_references_changed = 0 · objects_uploaded = 0
files = 28 · bytes = 21,945,944
valid_under_new_policy = 12 · invalid = 16
db_referenced = 20 · orphan = 8 · financial_evidence = 15
proposed: MIGRATE_NORMAL = 11 · MIGRATE_LEGACY_QUARANTINE = 17 · HOLD_FOR_REVIEW = 0
```

### قواعد القرار المُطبَّقة
1. «غير صالح تحت السياسة الجديدة» **ليس** سبباً لحذف أو فقد أي ملف قديم.
2. كل `finance_audit_evidence` و`payment_receipt` قديم = **دليل يجب حفظه** حتى لو فشل التحقق الحديث.
3. غير الصالح الذي يجب حفظه ⇒ يُقترح إلى `workshop-erp/legacy-quarantine/…` وهو **غير قابل للاسترجاع عبر نقاط النهاية العادية** (لا مسار يقرأ من هذه البادئة).
4. `orphan` **لا يعني** delete.
5. لم يُنقل أو يُحذف أي ملف، ولم يُغيَّر أي مرجع في قاعدة البيانات.

### حقلان منفصلان لا يُخلطان
- **`DB_REFERENCED`** = يوجد سجل يشير إلى **هذا الملف بعينه**.
- **`ENTITY_EXISTS`** = الكيان المالك (مركبة/عملية) ما زال موجوداً حياً. `N/A` حيث لا يوجد كيان مستقل (أدلة التدقيق مرتبطة بالجلسة/الملاحظة، والقوالب بنوع المستند).

### الجدول التفصيلي (28 ملفاً)

| # | surface | file | size | sha256 (12) | actual type | declared | VALID | invalid reason | DB_REF | entity exists | entity | FIN.EV | action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | vehicle | `uploads/vehicles/1a8d6eba-27e8-4603-a8ef-876a2f664167/f59f1fb6-cadf-4b0b-932a-e183aabd55a0.jpeg` | 139965 | `bed69d37a295` | image/jpeg | jpeg | YES | — | YES | YES | `1a8d6eba-27e8-4603-a8ef-876a2f664167` | NO | **NORMAL** |
| 2 | vehicle | `uploads/vehicles/3bd7dfd4-e831-4583-8399-e9d86aa9275b/7f0cb065-fe89-47e0-9e89-c81df8d85cd6.jpeg` | 78948 | `7490cbbf1839` | image/jpeg | jpeg | YES | — | YES | NO | `3bd7dfd4-e831-4583-8399-e9d86aa9275b` | NO | **NORMAL** |
| 3 | vehicle | `uploads/vehicles/641b1f96-6a55-46db-80e7-a76e3d1f394d/78938947585__A3FB0998-02AF-4347-9074-75A0C7564C81.MOV` | 340078 | `4074f2e4082f` | video/quicktime | mov | NO | unsupported_file_type (mov) | YES | NO | `641b1f96-6a55-46db-80e7-a76e3d1f394d` | NO | **QUARANTINE** |
| 4 | vehicle | `uploads/vehicles/641b1f96-6a55-46db-80e7-a76e3d1f394d/IMG_1088.png` | 3712922 | `3e5e7b5b66f0` | image/png | png | YES | — | NO | NO | `641b1f96-6a55-46db-80e7-a76e3d1f394d` | NO | **QUARANTINE** |
| 5 | vehicle | `uploads/vehicles/641b1f96-6a55-46db-80e7-a76e3d1f394d/IMG_1089.png` | 1523760 | `0f7310c3cd01` | image/png | png | YES | — | YES | NO | `641b1f96-6a55-46db-80e7-a76e3d1f394d` | NO | **NORMAL** |
| 6 | vehicle | `uploads/vehicles/641b1f96-6a55-46db-80e7-a76e3d1f394d/image.jpg` | 1932857 | `50c6608729f3` | image/jpeg | jpg | YES | — | YES | NO | `641b1f96-6a55-46db-80e7-a76e3d1f394d` | NO | **NORMAL** |
| 7 | vehicle | `uploads/vehicles/641b1f96-6a55-46db-80e7-a76e3d1f394d/test_invoice.txt` | 58 | `50dcecbdfcfb` | text/plain | txt | NO | unsupported_file_type (txt) | YES | NO | `641b1f96-6a55-46db-80e7-a76e3d1f394d` | NO | **QUARANTINE** |
| 8 | vehicle | `uploads/vehicles/e062c31c-4ab7-4944-93ea-452957b5c6b3/image.jpg` | 5826601 | `61df2f64f818` | image/jpeg | jpg | YES | — | YES | NO | `e062c31c-4ab7-4944-93ea-452957b5c6b3` | NO | **NORMAL** |
| 9 | vehicle | `uploads/vehicles/eceae870-0427-4bc9-9a08-ae3e37ac4f5e/c86690ee-1c84-4342-8e3e-3778c2960807.jpeg` | 118679 | `37efe765afe8` | image/jpeg | jpeg | YES | — | YES | YES | `eceae870-0427-4bc9-9a08-ae3e37ac4f5e` | NO | **NORMAL** |
| 10 | vehicle | `uploads/vehicles/fc0e7716-e24d-4aeb-a45f-3a1a25fbeb46/bb5fa9b5-4d7e-45f5-80f2-392358d769e0.jpeg` | 78429 | `2a021cd1a344` | image/jpeg | jpeg | YES | — | YES | NO | `fc0e7716-e24d-4aeb-a45f-3a1a25fbeb46` | NO | **NORMAL** |
| 11 | finance_audit_evidence | `uploads/finance_audit_evidence/audit-interactive-patch-1/b1a1f404-2f37-435e-922b-dffbfa3cab46.txt` | 8 | `ee8250fb76e0` | text/plain | txt | NO | unsupported_file_type (txt) | YES | N/A | `audit-interactive-patch-1` | YES | **QUARANTINE** |
| 12 | finance_audit_evidence | `uploads/finance_audit_evidence/audit-test-session-1/3d78c487-046a-479f-adfa-a21046f70031.txt` | 14 | `02098a28485e` | text/plain | txt | NO | unsupported_file_type (txt) | NO | N/A | `audit-test-session-1` | YES | **QUARANTINE** |
| 13 | finance_audit_evidence | `uploads/finance_audit_evidence/audit-test-session-2/330a6c8e-86c8-4147-a5f7-bc9480b47ae4.txt` | 8 | `ee8250fb76e0` | text/plain | txt | NO | unsupported_file_type (txt) | YES | N/A | `audit-test-session-2` | YES | **QUARANTINE** |
| 14 | finance_audit_evidence | `uploads/finance_audit_evidence/audit-test-session-2/b7345cb0-59aa-4f75-9024-8a8d88e408ef.txt` | 8 | `ee8250fb76e0` | text/plain | txt | NO | unsupported_file_type (txt) | YES | N/A | `audit-test-session-2` | YES | **QUARANTINE** |
| 15 | finance_audit_evidence | `uploads/finance_audit_evidence/audit-test-session-3/6e758820-afda-49c4-99eb-8e83c836cfc2.txt` | 8 | `ee8250fb76e0` | text/plain | txt | NO | unsupported_file_type (txt) | YES | N/A | `audit-test-session-3` | YES | **QUARANTINE** |
| 16 | finance_audit_evidence | `uploads/finance_audit_evidence/test-session-67f9cedf-b56b-443c-983e-5865e6dfac1c/f16e6245-8916-4791-86ed-05485325e39a.txt` | 21 | `d96060951196` | text/plain | txt | NO | unsupported_file_type (txt) | YES | N/A | `test-session-67f9cedf-b56b-443c-983e-5865e6dfac1c` | YES | **QUARANTINE** |
| 17 | finance_audit_evidence | `uploads/finance_audit_evidence/test-session-b3c63553-c53b-41af-8e5b-5608bb28ca6e/21e22e03-0af4-41f2-aa1e-db8e90a07e2f.pdf` | 22 | `245384488b7d` | text/plain | pdf | NO | file_content_not_verifiable (pdf) | YES | N/A | `test-session-b3c63553-c53b-41af-8e5b-5608bb28ca6e` | YES | **QUARANTINE** |
| 18 | finance_audit_evidence | `uploads/finance_audit_evidence/test_close_ecef8028/72984866-5d8d-4ca4-a02b-061ed5a97912.pdf` | 31 | `738270e0ea43` | text/plain | pdf | NO | file_content_not_verifiable (pdf) | YES | N/A | `test_close_ecef8028` | YES | **QUARANTINE** |
| 19 | finance_audit_evidence | `uploads/finance_audit_evidence/test_upload_3d9e1b08/693b3860-0694-4c31-8b25-3d11e9dce8d4.txt` | 30 | `01c7760421ad` | text/plain | txt | NO | unsupported_file_type (txt) | YES | N/A | `test_upload_3d9e1b08` | YES | **QUARANTINE** |
| 20 | payment_receipt | `uploads/operation_payment_receipts/209878af-ab7a-4565-b095-5d4f1704eec2/20260419200003_22dce3fa.txt` | 23 | `7e50a55cff5e` | text/plain | txt | NO | unsupported_file_type (txt) | NO | NO | `209878af-ab7a-4565-b095-5d4f1704eec2` | YES | **QUARANTINE** |
| 21 | payment_receipt | `uploads/operation_payment_receipts/4fe046ae-f7e7-4672-a36a-d958d6a5cbe1/20260419195949_e9e42c07.txt` | 76 | `fd1c61c69907` | text/plain | txt | NO | unsupported_file_type (txt) | NO | NO | `4fe046ae-f7e7-4672-a36a-d958d6a5cbe1` | YES | **QUARANTINE** |
| 22 | payment_receipt | `uploads/operation_payment_receipts/b666d607-dfde-46e4-b221-0dab4111d0bc/20260419195621_dad7ccd4.txt` | 31 | `ac4755f36e94` | text/plain | txt | NO | unsupported_file_type (txt) | NO | YES | `b666d607-dfde-46e4-b221-0dab4111d0bc` | YES | **QUARANTINE** |
| 23 | payment_receipt | `uploads/operation_payment_receipts/b666d607-dfde-46e4-b221-0dab4111d0bc/20260419195718_88dbe7fb.txt` | 29 | `3214febd348d` | text/plain | txt | NO | unsupported_file_type (txt) | NO | YES | `b666d607-dfde-46e4-b221-0dab4111d0bc` | YES | **QUARANTINE** |
| 24 | payment_receipt | `uploads/operation_payment_receipts/eede8f17-3e1c-4132-aa94-c8c574a18314/20260419195935_36bf6189.png` | 67 | `ebf4f635a17d` | image/png | png | YES | — | NO | NO | `eede8f17-3e1c-4132-aa94-c8c574a18314` | YES | **NORMAL** |
| 25 | payment_receipt | `uploads/operation_payment_receipts/fff80180-defb-48f3-b418-fc785d09d867/20260419195928_0e93252f.txt` | 58 | `16b9760a00df` | text/plain | txt | NO | unsupported_file_type (txt) | NO | NO | `fff80180-defb-48f3-b418-fc785d09d867` | YES | **QUARANTINE** |
| 26 | template | `custom_templates/2071f1fa-e806-4a3f-9bbb-708f6b2228e2.html` | 16053 | `b8d6bc4de541` | text/plain | html | YES | — | YES | N/A | `—` | NO | **NORMAL** |
| 27 | template | `custom_templates/fa68fe6e-bcd8-4002-bc8e-5c739dea314e.pdf` | 1331070 | `908c3e99fe72` | application/pdf | pdf | YES | — | YES | N/A | `—` | NO | **NORMAL** |
| 28 | template | `custom_templates/fd3178e1-2624-4523-b4f1-7b1965cc2010.pdf` | 6846090 | `4a51cbd4c587` | application/pdf | pdf | YES | — | YES | N/A | `—` | NO | **NORMAL** |

### مصفوفة surface × referenced/orphan × valid/invalid × financial/non-financial

| surface | reference | validity | class | count |
|---|---|---|---|---|
| finance_audit_evidence | referenced | invalid | financial | 8 |
| finance_audit_evidence | orphan | invalid | financial | 1 |
| payment_receipt | orphan | invalid | financial | 5 |
| payment_receipt | orphan | valid | financial | 1 |
| template | referenced | valid | non-financial | 3 |
| vehicle | referenced | valid | non-financial | 7 |
| vehicle | referenced | invalid | non-financial | 2 |
| vehicle | orphan | valid | non-financial | 1 |
| **الإجمالي** | | | | **28** |

مصفوفة إضافية — `ENTITY_EXISTS` (الكيان المالك ما زال حياً؟):

| surface | DB_REFERENCED | ENTITY_EXISTS | count |
|---|---|---|---|
| finance_audit_evidence | YES | N/A | 8 |
| finance_audit_evidence | NO | N/A | 1 |
| payment_receipt | NO | **YES** | 2 |
| payment_receipt | NO | NO | 4 |
| template | YES | N/A | 3 |
| vehicle | YES | **NO** | 7 |
| vehicle | YES | YES | 2 |
| vehicle | NO | NO | 1 |

---

## ملاحظات جوهرية على البيانات (تحتاج قرارك، ولم أتصرف بها)

1. **صفر ملف دليل مالي صالح تحت السياسة الجديدة تقريباً.** 15 ملفاً مصنَّفاً `FINANCIAL_EVIDENCE`،
   منها **14 غير صالح** و**واحد فقط صالح** (`.png` إيصال سداد). كل أدلة التدقيق التسعة إما `.txt`
   أو ملفات باسم `.pdf` لكن بايتاتها نص عادي — أي أنها **مصنوعات اختبار وليست أدلة حقيقية**
   (أحجامها 8–31 بايت، ومحتوى مثل `test evidence`). هذا يقلل المخاطر كثيراً لكنه **لا يبرر الحذف**:
   القرار لك.
2. **7 من 10 ملفات مركبات مرجعية لكن مركبتها لم تعد موجودة حياً** (`ENTITY_EXISTS=NO`؛ العدد الحي
   238 مركبة). المرجع موجود في `uploads/vehicle_files.json` لكن صف المركبة اختفى من Supabase.
   هذا مؤشر على حذف/ترحيل تاريخي — يستحق النظر في PHASE 2A، ولا يُحذف شيء الآن.
3. **إيصالات السداد الستة كلها بلا مرجع على مستوى الملف**: مصدر الربط الوحيد في الكود هو نص وصف
   القيد (`| إيصال: {filename}`) ولم يُعثر على أي قيد يشير إليها. لكن **عمليتين من الست ما زالت
   عملياتهما موجودة** ⇒ ليست «يتيمة» بالمعنى الكامل. مصدر الحقيقة لـ`operations`/`journal_entries`
   هو Supabase (وليس Mongo) وقد استُعلم فعلياً (client حقيقي، غير mock).
4. **القوالب الثلاثة كلها صالحة ومرجعية** (2 PDF + 1 HTML، 8.19 ميجابايت) — أنظف مجموعة.
5. `custom_templates_index.json` فارغ ⇒ الراوتر القديم `/api/templates` لا يملك سجلات؛ المراجع
   الثلاثة كلها من `mongo:document_templates`.

## فرق الأرقام مع تقرير سابق
`21,945,944` بايت هنا = **مجموع أحجام الملفات بدقة**. الرقم `22,039,852` في التقرير السابق كان من
`du -sb` الذي يضيف حجم المجلدات نفسها. عدد الملفات متطابق: **28**.

## Financial Test Debt (مُسجَّل، وبلا أي تغيير في البيانات)
```text
ITEM  = FIN-TEST-DEBT-2101
FILE  = backend/tests/test_p0_red_findings_repair.py
TESTS = test_payables_total_ap_420 · test_payables_query_alofi_420 ·
        test_trial_balance_contains_2101_credit_420 · test_dashboard_total_ap_matches_tool ·
        test_admin_chat_supplier_payables · test_paid_amount_uses_totalPaid
FACT  = تُثبِّت رقماً مطلقاً (2101 = 420.0)؛ ميزان المراجعة الحي لا يُرجع الحساب 2101 إطلاقاً
ACTION_TAKEN = لا شيء. لم تُلمس البيانات الحية ولا ميزان المراجعة لإرضاء اختبار.
OPEN_QUESTION = هل الاختبار stale فعلاً، أم أن اختفاء 2101 يكشف مشكلة تاريخية؟ ⇒ يُحسم في PHASE 2A
```

## حراسة عدم التعديل
```text
DEAD_CODE_REMOVED = 306 lines (2 functions)
LEGACY_ENDPOINTS_STILL_410 = YES (verified live, authenticated)
NEWLY_GUARDED = 1 route (accounts-chart reset) + 4 CLI scripts + 1 library helper
FILES_MOVED = 0 · FILES_DELETED = 0 · DB_REFERENCES_CHANGED = 0 · OBJECTS_UPLOADED = 0
MIGRATION_EXECUTED = NO · RESET_EXECUTED = NO · SEED_EXECUTED = NO
DB_MUTATION = NO · FINANCIAL_MUTATION = NO · ACCOUNTING_ENGINE_CHANGED = NO
ENV_CHANGED = NO · SECRETS_CHANGED = NO · DEPLOY = NO · PHASE_2A_STARTED = NO
```

## مخرجات
- `backend/tests/test_p0_dead_destructive_code_removal.py` — 20/20 PASS
- `scripts/classify_legacy_upload_files.py` — أداة التصنيف (قراءة فقط، قابلة لإعادة التشغيل)
- `memory/discovery/LEGACY_UPLOAD_FILES_CLASSIFICATION.json` — المخرج الخام الكامل (28 صفاً بكل الحقول)
- `backend/core/destructive_guard.py` — أُضيفت `require_destructive_cli` + `CLI_CONFIRM_ARG`

---

## التحقق المستقل — `iteration_382` (وكيل الاختبار)

```text
CRITICAL = 0 · MINOR = 0 · retest_needed = false · should_main_agent_self_test = false
backend success = 100%  (20/20 دفعة الكود الميت · 57/57 سويتات الانحدار · 4/4 رفض CLI · 4/4 مصفوفة الرفض الحية)
```

- `routes_finance.py`: **6265 → 5959 سطراً**. كل دالة legacy = docstring + `raise 410`. الديكوريتورات سليمة.
  و`require_destructive_authorization` **غير موجودة** في الملف ⇒ المسارات معطّلة نهائياً وليست مُعاد تسليحها.
- `routes_accounts_chart.py`: الحراسة هي **أول تعليمة `await`** قبل أي `.delete().neq()` — تحقق من الترتيب.
- **صفر تعديل مؤكَّد بالأرقام**: `operations = 39` و`chart_of_accounts = 12` **متطابقان قبل وبعد** كل نداءات
  مصفوفة الرفض.
- **مسح مستقل** عبر كل `/app/backend` لمصطلحات المسح الجماعي في Mongo **وSupabase**
  (`delete_many({})`, `update_many({}`, `.drop()`, `drop_database`, `.delete().neq/gte/gt/is_/not_.is_`):
  **11 إصابة، كلها** إما GUARDED أو CLI fail-closed أو BENIGN. **لا يوجد أي مصطلح Supabase فائت** —
  وهذه كانت أكبر نقطة عمياء محتملة.
- المُصنِّف **read-only بنيوياً**: البحث عن بدائيات الكتابة (`put_object`, `os.remove`, `shutil.move`,
  `.unlink`, `update_one`, `insert_one`, `delete_one`, `insert_many`, `replace_one`) لم يُرجع إلا تطابقين
  داخل نص الـdocstring (اسم الملف يحتوي `upload_files`).
- الأرقام أُعيد إنتاجها **بالبايت**: 28 ملفاً · 21,945,944 بايت · 12 صالح · 16 غير صالح · 20 مرجعي ·
  8 يتيم · 15 دليلاً مالياً · NORMAL=11 · QUARANTINE=17 · HOLD=0. وأُعيد حساب SHA-256 لملفين مستقلاً وتطابقا.
- **الالتزام بقواعد القرار**: صفر ملف مُقترح للحذف · كل الـ15 دليلاً مالياً (بما فيها الـ14 غير الصالحة)
  مُقترح للترحيل ولا شيء منها HOLD · كل هدف حجر تحت `workshop-erp/legacy-quarantine/` و`grep` على كل
  `/app/backend/*.py` أرجع **صفر** إشارة لهذه البادئة ⇒ الملفات المحجوزة غير قابلة للوصول عبر أي مسار.
- الصحة: `/api/health` 200 · `/api/auth/me` 200 · لا أخطاء استيراد ولا tracebacks جديدة.
