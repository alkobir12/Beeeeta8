# PHASE_1B_FINAL_CONSISTENCY_REPORT
Generated=2026-08-25 20:38 UTC
Scope=READ-ONLY / CODE+TESTS ONLY / no deploy / no production mutation / no AccountingEngine / no P0-DUP-AR.

## Canonical endpoint totals
- PUBLIC_INTENTIONAL: 8
- GENERAL_AUTHENTICATED_READ: 109
- SELF_ONLY: 6
- ROLE_RESTRICTED: 16
- PERMISSION_RESTRICTED: 106
- AUTHZ_COMPLETE_MUTATION: 267
- SUM: 512
- MISSING_AUTHZ: 0
- POLICY_DECISION_REQUIRED: 0
- AUTH_ONLY_NO_OBJECT_CHECK: 0
- UNKNOWN: 0

## Public endpoints القائمة النهائية
01. GET /api/approvals/public/{token} [routes_approvals.py::public_approval] — رابط تحقق/اعتماد عام بالتوكن؛ التفويض قائم على token capability لا على JWT.
02. POST /api/approvals/public/{token}/respond [routes_approvals.py::respond_public_approval] — رد اعتماد عام بالتوكن؛ التفويض قائم على token capability لا على JWT.
03. POST /api/auth/google/session [auth_jwt.py::google_session] — تبادل جلسة Google قبل وجود JWT داخلي؛ يجب أن يبدأ عاماً ثم ينتج جلسة محمية.
04. POST /api/auth/login [auth_jwt.py::login] — نقطة دخول المصادقة؛ لا يمكن طلب JWT قبل تسجيل الدخول.
05. POST /api/auth/logout [auth_jwt.py::logout] — إنهاء الجلسة/تنظيف الكوكي يجب أن يبقى قابلاً للاستدعاء حتى لو انتهت الجلسة.
06. POST /api/auth/refresh [auth_jwt.py::refresh] — تجديد الجلسة يعتمد على refresh/cookie قبل إصدار access JWT جديد.
07. GET /api/health [server.py::api_health_check] — فحص صحة خدمة عام للـprobe/monitoring ولا يعرض بيانات أعمال.
08. GET /api/health [server.py::health_check] — فحص صحة خدمة عام للـprobe/monitoring ولا يعرض بيانات أعمال.

## تفسير اختلاف 8/17
- العدد النهائي الصحيح Canonical هو 8 public endpoints، وهو مطابق لـ auth_guard public allowlist الحالي.
- رقم 17 كان من closure script legacy بعد Phase 1؛ احتسب health/chat bot health وبعض approvals العامة/شبه العامة ضمن PUBLIC_INTENTIONAL لأغراض توافق قديمة.
- في Phase 1B Final لا يبقى public إلا auth bootstrap + public approval token + health. أمثلة أزيلت من public legacy: /api/approvals, /api/finance-bot/health, /api/diesel-chat/health, /api/workshop-bot/health؛ أصبحت explicit authenticated/restricted أو general-auth reads.

## تفسير 267/495
- 267 هو عدد AUTHZ_COMPLETE_MUTATION الحقيقي في التصنيف التفصيلي: مسارات write/execute/mutate أو reads شديدة الحساسية التي عوملت كسياسة كاملة في المصفوفة.
- 495 في closure_authz_after.py ليس تصنيفاً Canonical؛ هو تجميع legacy = 512 - 17 public في التقرير القديم. كان يطوي GR/PR/RR/SR/AZ داخل AUTHZ_COMPLETE، لذلك يخفي أنواع السياسات المختلفة.
- بناءً عليه لا يُستخدم 495 كـ AUTHZ_COMPLETE نهائي. التصنيف النهائي الوحيد هو الجدول Canonical أعلاه.

## نتيجة إعادة تدقيق الـ286 writers
- تم استبدال S=self/V=alw/M=guard المولدة آلياً بتدقيق محافظ في write_path_audit_phase1b_consistency.json بعدد rows=286.
- المعاني الصحيحة الآن: actor_scope يصف actor الحقيقي أو inherited/system؛ route_service_caller يميز route/helper/service؛ permission_source يذكر مصدر policy؛ object_resource_scope يميز SELF/ROLE/SENSITIVE_FINANCIAL/TENANT؛ payload_validation_mechanism وmass_assignment_protection_mechanism لا يدعيان allowlist إلا للأسطح التي ثبتت فيها allowlists أو typed model.
- لا توجد قيمة S=self موحدة. internal/background writers مصنفة SYSTEM_INTERNAL_OR_INHERITED_CALLER أو INHERITED_FROM_AUTHORIZED_CALLER حسب الملف.
- Writer UNKNOWN count: 0
- caller breakdown: API_ROUTE_HANDLER=219, CORE_BUSINESS_SERVICE=14, DOMAIN_REPOSITORY_HELPER=19, INTERNAL_SERVICE_OR_BACKGROUND_JOB=34
- actor_scope breakdown: AUTHENTICATED_ACTOR_FROM_MIDDLEWARE=213, INHERITED_FROM_AUTHORIZED_CALLER=33, SELF_OWNED_RESOURCE=6, SYSTEM_INTERNAL_OR_INHERITED_CALLER=34
- resource_scope breakdown: ROLE_RESTRICTED=47, SELF_OWNED=6, SENSITIVE_FINANCIAL=71, TENANT_WORKSHOP_WIDE=162
- payload_validation breakdown: CALLER_CONTRACT_PLUS_DOMAIN_MAPPING=33, EXPLICIT_ALLOWLIST_OR_TYPED_MODEL=34, INTERNAL_SERVICE_CONTRACT=31, ROUTE_SCHEMA_OR_BUSINESS_MAPPING_NO_GLOBAL_ALLOWLIST=188
- mass_assignment breakdown: EXPLICIT_ALLOWLIST_GUARD=34, NOT_DIRECT_USER_PAYLOAD_INTERNAL_WRITE=64, NO_PRIVILEGE_FIELDS_ON_SURFACE_OR_BUSINESS_MAPPING=188
- canonical path breakdown: ACCOUNTING_ENGINE_SSOT=12, BUSINESS_ROUTE_OR_DOMAIN_PATH_NO_DIRECT_JOURNAL_WRITE=96, OPERATIONAL_DOMAIN_PATH=178
- financial_effect breakdown: NO=178, YES=108

## أي UNKNOWN
- Endpoint UNKNOWN: 0
- Writer UNKNOWN: 0

## Tests Results
- Local pytest: `pytest -q /app/backend/tests/test_authz_ssot.py /app/backend/tests/test_authorization_phase1b.py` => 18 passed / 0 failed.
- Local script mode: `test_authz_ssot.py` => ALL PASS; `test_authorization_phase1b.py` => 10/10 PASS.
- Local consistency/static checks: canonical endpoints SUM=512, endpoint UNKNOWN=0, writers=286, writer UNKNOWN=0.
- Legacy closure script still prints AUTHZ_COMPLETE=495/PUBLIC_INTENTIONAL=17 by old aggregation; this is intentionally superseded by Canonical totals above and is no longer used as final classification.
- Independent testing agent iteration 365: 21/21 passed; verified canonical totals, public=8, 17/495 legacy explanations, writer audit rows=286, writer UNKNOWN=0, no fake S=self/V=alw/M=guard defaults, no DB/financial mutation, no MOCKED APIs.

## Final verdict
PHASE 1B AUTHORIZATION CLOSURE VERIFIED
