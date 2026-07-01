# Workshop ERP — Product Requirements (PRD)

## Original Problem Statement
نظام إدارة ورشة سيارات متكامل (ERP) يدعم اللغة العربية، يضم وحدات محاسبية صارمة، نظام جرد ذكي، تتبع ذمم، ومدقق مالي بالذكاء الاصطناعي.
هدف المرحلة الحالية: "Enterprise Operator" — ترحيل الحالات المؤقتة إلى قواعد بيانات دائمة، RBAC خلفي صارم، مبدأ أربع أعين حقيقي، محرك محاسبة مركزي (كاتب وحيد)، وإجراءات مالية عبر البوت بحوكمة كاملة.

## CHANGELOG — 2026-07-01 · توحيد مصدر الحقيقة المالية + حوكمة كاترينا المرحلة C (منع الأوامر الوهمية)
المستخدم أبلغ عن: (1) تضارب التنبيهات — صفحة العمليات تعرض 3 تنبيهات بينما الجدار/البوت 0، (2) كاترينا تنفّذ أوامر وهمية
(ادّعت "تم إضافة المورّد بنجاح" بدون أي أداة، حفظت عميل "بدون اسم"، وPower Mode فسّر رقم الجوال كمبلغ 55,555,555).
**تم — مختبَر 10/10 (iteration_243, 100%):**
- **توحيد المصدر (SSOT = FirewallEngine)**: `/api/finance/alerts` أصبح يُشتق كاملاً من `firewall_engine.run_full_analysis()`
  — نفس التنبيهات/الصحة/التدفق النقدي في: شريط «مراقب المحاسبة» (العمليات + لوحة التحكم + الذمم)، جدار الحماية، والبوت.
- **محرك الجدار اكتسب كواشف جديدة**: `analyze_profitability` (هامش/خسارة من القيود آخر 30 يوم بنافذة timedelta صحيحة —
  النافذة القديمة `replace(day=...)` كانت معطوبة)، `detect_missing_journal_entries` (عمليات مالية بدون قيود — كشف فعلياً
  8 عمليات بـ13,550 ر.س بدون أي قيد لأن جدول journal_entries فارغ حالياً)، `detect_open_receivables` (ذمم مدينة/دائنة).
  معيار الصحة `audit_coverage` (placeholder) → `profitability` (الواجهة حُدّثت: HealthScoreGauge label «الربحية»).
- **حوكمة كاترينا المرحلة C**: الإجراءات الآمنة (عميل/مركبة/زيارة/مورد/تعديل) لم تعد auto-commit —
  ترجع `awaiting_confirmation` مع echo-back، والتثبيت فقط عند رد المستخدم «نعم» (و«لا» يلغي). المسودة المعلّقة في
  shared_memory per-session. المالية (فاتورة/دفعة/مصروف/عكس) تبقى أربع أعين pending_approval بلا تغيير.
- **create_supplier حقيقي end-to-end**: intent LLM + regex fallback + commit متزامن إلى `uploads/suppliers.json`
  (جدول suppliers غير موجود في Supabase) + فحص تكرار + إبطال كاش — يظهر فوراً في GET /api/suppliers وصفحة /suppliers.
- **حارس الاسم الإلزامي**: create_customer/create_supplier بدون اسم → needs_clarification («ما اسم العميل/المورّد؟»)
  بدل حفظ «بدون اسم». حُذف السجل الوهمي القديم (ddbae1b7).
- **إصلاح استخراج الكيانات في Power Mode**: الجوال يُلتقط أولاً (05\d{7,9} يشمل الأرقام الناقصة)، المبلغ بكلمة مفتاحية
  (بقيمة/بمبلغ/بسعر) قبل اللوحة، واللوحة بـ negative-lookahead لكلمات (جوال/ريال/باسم...). «بقيمة 4500 ... جوال 0555555555»
  → amount=4500 وphone منفصل.
- **تحصين برومبت الصدق**: ممنوع على الـLLM ادعاء تنفيذ أي كتابة — رسالة «✅ تم بنجاح» تصدر من المحرك فقط.
- Frontend: FinanceAlertsWidget يعرض شريحة الصحة `alerts-health-chip` (92/100) + skeleton أثناء التحميل، ويظهر الآن
  أيضاً على `/` و`/debts-followup`. AssistantProvider يدعم `awaiting_confirmation` و`d.ask`.
- ملفات: firewall_engine.py، routes_finance.py (/alerts)، core/{unified_executor,assistant_kernel,action_runtime,power_mode,llm_intent_parser}.py،
  frontend FinanceAlertsWidget.jsx، useFinanceAlerts.js، AssistantProvider.jsx، HealthScoreGauge.jsx.
- Regression file: /app/backend/tests/test_bot_governance_phase_c_iter243.py (10/10).
- ملاحظة بيانات (ليست خطأ كود): جدول journal_entries في Supabase فارغ حالياً بينما توجد 8 عمليات — التنبيه الأول
  الموحّد يرشد المستخدم لتشغيل «تصحيح القيود المفقودة» (POST /api/operations/integrity/fix-all) من مركز الجدار.

## CHANGELOG — 2026-06-20 (سابق) · JWT RBAC + محرك المحاسبة + بوت مالي بأربع أعين
- ترحيل JWT RBAC كامل (P0)، حصر CORS، إزالة autoprofit-pro، إصلاح race تسجيل الدخول.
- `AccountingEngine.reverse()` قيود عكسية (لا حذف نهائي)؛ حوكمة البوت A+B: إجراءات مالية عبر البوت echo-back + أربع أعين
  (21/21 اختبار — iterations 240-242).

## Core Requirements
- Strict double-entry accounting + Single-Writer AccountingEngine (journal_entries محمي من الكتابة المباشرة)
- Four-Eyes حقيقي للإجراءات المالية والحذف؛ Level-1 confirm-first للإجراءات الآمنة (المرحلة C ✅)
- مصدر حقيقة مالي واحد: FirewallEngine (تنبيهات/صحة/تدفق/ربحية) ✅
- Smart POS Journal Entries / Smart Inventory with COGS / Idempotency
- RBAC (name-only login by design + JWT)

## User Personas
- **مدير** — admin (يعتمد) | **احمد1** — supervisor (يعتمد) | **فرج1** — accountant (لا يعتمد) | **مستخدم اختبار** — technician

## Tech Stack
React 18.3.1 (CRA) + FastAPI + Supabase (relational) + MongoDB (state/audit) + Emergent LLM Key (claude-sonnet-4-6)

## Key API endpoints
- POST /api/auth/login {username} → JWT (httpOnly cookies + Bearer)
- GET /api/finance/alerts?workshop_id= → موحّد من FirewallEngine {alerts, health, cash_flow, profitability, source}
- GET /api/firewall/dashboard?workshop_id= → نفس المصدر
- POST /api/assistant/chat {message, session_id, proposer} → envelope {success, data:{response, executed, cards...}}
- POST /api/runtime/execute {text, proposer, session_id} → status: committed|awaiting_confirmation|pending_approval|needs_clarification|read_only|rejected
- POST /api/finance-actions/{invoice|payment|expense|reverse} (RBAC JWT)
- POST /api/operations/integrity/fix-all (إعادة إنشاء القيود المفقودة)

## Backlog (مرتّب)
- **P1**: Decimal بدل float في محرك المحاسبة؛ timeouts صريحة لنداءات LLM؛ تنقيح البيانات الحساسة قبل إرسالها للـLLM
- **P1**: refactor server.py / routes_finance.py (224KB) / routes_extended.py (212KB)
- **P2**: ربط أداة whatsapp.send بموجّه نوايا البوت؛ deep-links سياقية (?pos= ?part=)
- **P2**: «الطلبات الافتراضية» — بانتظار تعريف المستخدم (أوامر عمل؟ طلبات شراء؟)
- **P2**: Ollama fallback معطوب في بيئة المعاينة (binary مفقود)
- **P3**: تقسيم مكونات React الضخمة (VehicleDetails 4510 سطر، Operations 3835)؛ CRA→Vite

## Known Status
- journal_entries (Supabase) فارغ حالياً — 8 عمليات بدون قيود؛ المستخدم يقرر تشغيل fix-all أو إدخال قيود.
- suppliers لا جدول له في Supabase — المخزن الفعلي uploads/suppliers.json (fallback معتمد).
- 89 npm vulnerabilities كلها في build tooling (تحتاج CRA→Vite).

## Security Status (20 Jun 2026) — كما هو
JWT RBAC ✅ | deny-by-default ✅ | CORS مقيّد ✅ | refresh tokens ✅
