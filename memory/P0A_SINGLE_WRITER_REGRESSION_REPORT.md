# P0-A — Single Writer Hardening Regression Report

## النطاق
- البيئة: **Preview فقط**.
- Production: **لم يُفحص ولم يُعدّل**.
- P0-B: **لم يبدأ**؛ لم تُصحح 2,300 أو 167.84 أو فجوة 908 أو Katrina/Reconciliation.
- البنود المجمدة لم تتغير: `AccountingEngine` implementation، Income Statement rules، Journal KPI UI، `final_customer_total` policy، Supplier Exclusion policy.

## التغييرات
- أُزيلت الكتابات المباشرة على `journal_entries` خارج AccountingEngine، وعُطلت مسارات maintenance القديمة عند طلب الكتابة.
- `repost_bank_and_fix_imbalance` وsuspense balancing plug محظوران 410.
- backfill للـ43 عملية و`operations/integrity/fix-all` محظوران؛ dry-run فقط يبقى متاحًا ويعرض 43.
- `financial_reset_engine.execute_reset` محظور بالكامل؛ dry-run فقط.
- manual journal update محظور؛ manual create/close period/supplier import/payment posting تفشل إذا أعاد المحرك `[]` أو `None` أو خطأ.
- supplier import يتحقق من كامل الملف قبل أول posting، ولا يرجع نجاحًا جزئيًا صامتًا.
- حالة سداد القيد المؤقت لم تعد تعدّل وصف `journal_entries`؛ الحالة التشغيلية تبقى في `operation`.
- memory/Mongo financial operation fallback محظور، وإن فشل posting بعد إنشاء operation تُعكس القيود الجزئية عبر AccountingEngine وتُحذف العملية غير المكتملة.
- endpoint القديم `save-parts-and-create-journal` محظور 410 قبل أي كتابة لأنه يتعارض مع canonical finalization.

## القبول
| البند | النتيجة |
|---|---|
| `ACTIVE_DIRECT_FINANCIAL_WRITES` | `0` |
| `ACTIVE_SILENT_FINANCIAL_FALLBACKS` | `0` |
| `BALANCING_PLUG_PATH` | `BLOCKED` |
| `BACKFILL_43_OPERATIONS` | `BLOCKED` |
| `EMPTY_ENGINE_RESULT_FAILS_CLOSED` | `PASS` |
| `MANUAL_JOURNAL_FALSE_SUCCESS` | `0` |
| `SUPPLIER_IMPORT_PARTIAL_SILENT_SUCCESS` | `0` |
| `ACCOUNTINGENGINE_SINGLE_WRITER` | `PASS` |
| `FINANCIAL_DATA_CHANGES` | `0` |

## سلامة البيانات الحية
- قبل/بعد: `journal_entries=36`, `operations=56`, `accounts=192`, `vehicle_visits=181` مع SHA-256 متطابق لكل جدول.
- `AR_CORE=9,181.00`.
- Income Statement المجمد: Revenue `7,494.00`، Expenses `2,274.00`، Net Income `5,220.00`.

## الاختبارات
- self-test: **92 passed, 0 skipped, 0 failed** للحزم المستهدفة والمجمدة.
- Testing Agent: Iter347 ثم Iter348؛ لا P0-A runtime regressions، بصمات البيانات ثابتة، والواجهة تعمل.
- التقارير: `/app/test_reports/iteration_347.json` و`/app/test_reports/iteration_348.json`.

## حالة التوقف
**STOPPED AFTER P0-A.** يلزم اعتماد مستقل قبل بدء أي خطوة من P0-B.