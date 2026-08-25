# AUTHORIZATION_REPAIR_REPORT — PHASE 1 (AUTHZ-SYSTEMIC + P0-SEC-USERS)
2026-06 · **CODE REPAIR ONLY — صفر تعديل بيانات / صفر migration / صفر deploy.** تم التحقق بوكيل الاختبار (iteration_363: 27/27).

## BEFORE (المصفوفة قبل الإصلاح — 512 endpoint)
PUBLIC_INTENTIONAL 17 · AUTHZ_COMPLETE 0 · ROLE_CHECK_ONLY 34 · AUTH_ONLY_NO_OBJECT_CHECK 379 · **MISSING_AUTHZ 82** · object-level = 0. (المصدر: `authz_matrix.json`).

## ROOT CAUSE
- المصادقة (`auth_guard`) كانت تفرض JWT فقط، **دون أي طبقة تفويض**.
- بدائل RBAC موجودة في `core/rbac.py` (Actor + خريطة role→permission من `config/role_permissions.json`) لكنها مُستخدمة يدوياً في ~34 endpoint فقط ⇒ **التفويض مجزّأ وغير منهجي**.
- الـbackend يستخدم Supabase `service_role` ⇒ **RLS متجاوَز** ⇒ الحماية الوحيدة الممكنة هي طبقة التطبيق، والتي كانت غائبة على 82 مسار تعديل حسّاس (أخطرها كل `/api/users*`: أي مستخدم مُصادَق يرفع نفسه admin).

## AUTHORIZATION ARCHITECTURE (النموذج الموحّد الجديد)
```
REQUEST → auth_guard (JWT) → core/authz (نقطة إنفاذ واحدة) →
          [permission(role→module.action) | role | object-level] → route/service → DB
```
- **`core/authz.py`** = SSOT واحد: يعيد استخدام `rbac.get_role_permissions` (لا إطار موازٍ).
  - سجل سياسات مركزي `_RULES` (regex على المسار + method) مبني **حصراً** على الأدوار/الصلاحيات الفعلية.
  - `enforce_or_none(path, method, payload)` يُستدعى من **نقطة واحدة** في الـmiddleware.
  - Fail-closed للسياسات الحرجة (users/destructive) حتى بلا دور؛ fail-open عند الأخطاء الداخلية (لا يُسقط التطبيق)؛ المسارات غير المُدرجة تبقى «مُصادَق فقط» (منع كسر الوظائف).
  - مساعدات object-level للطرق: `resolve_request_actor` (يشمل تجاوزات المستخدم).

## FILES CHANGED
| ملف | التغيير |
|---|---|
| **`core/authz.py`** (جديد) | Authorization SSOT: Actor/سياسة/إنفاذ + object-level helpers |
| **`server.py`** (+9 أسطر) | استيراد + استدعاء `_authz_enforce` بعد المصادقة (نقطة إنفاذ وحيدة) → 403 عند الرفض |
| **`routes_users.py`** (~50) | حراس object-level: لا تغيير دور/صلاحية/حالة ذاتية، لا حذف ذاتي، لا تصعيد صلاحيات (`_actor_is_admin`,`_grants_privileged_perms`) + `request:Request` |
| `tests/test_authz_ssot.py` (جديد) | 32 اختبار أمني وحدوي |
| `tests/closure_authz_after.py` (جديد) | إعادة تدقيق المصفوفة بعد الإصلاح |
> لم تُمَس: AccountingEngine / ترحيل القيود / حسابات AR / التقارير المالية (P0-DUP-AR منفصل). لم تُعدّل `.env`/`yarn.lock` (فروق baseline من الـfork).

## ENDPOINTS CHANGED (الحماية)
السياسة المركزية غطّت الآن (AUTHZ_COMPLETE) الفئات التالية:
- `/api/users*` → users.{view/create/edit/delete} (P0 مغلق).
- مسارات هدّامة (`financial-reset|reset|cleanup|purge|wipe|danger`) → دور admin فقط.
- `/api/settings|workshop-config` تعديلات → settings.edit.
- `/api/invoices*` تعديلات → invoices.{create/edit/delete}.
- `/api/operations|finance-engine` تعديلات → operations.{edit/delete}.
- `/api/finance/|accounting/|accounts/|smart-accounting|chart-of-accounts` تعديلات → journal_entries.{edit}, والحذف → journal_entries.delete (admin).
- `/api/financial-control*` تعديلات → أدوار الاعتماد (APPROVER_ROLES).
- `/api/suppliers-ext/*/settlements|transactions` → journal_entries.edit.
+ 34 endpoint سبق أن كانت ROLE_CHECK داخل الـhandler (بقيت).

## POLICY_DECISION_REQUIRED (22) — يحتاج قرارك (لم يُفرض تلقائياً تجنباً للتخمين)
مسارات تعديل حسّاسة لا يمكن تحديد سياستها بثقة من الأدوار الحالية — **مصنّفة صراحةً، غير صامتة**:
- **Payroll (5):** POST `/api/salaries`, POST `/api/salary-records`, PUT `/api/salary-records/{id}`, POST `/api/employee-performance` — (من يُدير الرواتب؟ لا يوجد module رواتب في role_permissions).
- **Action Runtime (5):** POST `/api/runtime/execute`, `/api/runtime/intent/execute`, `/api/runtime/intent/parse`, `/api/runtime/power`, `/api/runtime/drafts/{id}/request_approval` — (لديها أربع-أعين downstream؛ هل نضيف حارس دور مقدّماً؟).
- **Finance-bot (4):** POST `/api/finance-bot/chat|auto-link|detect-contradictions|evidence/upload`.
- **Files/uploads (3):** POST `/api/vehicles/{id}/upload-file` (×2 server.py+router), POST `/api/vehicles/compare-diagnostics` — (مرتبط بـP1-SEC-UPLOAD).
- **أخرى (5):** POST `/api/accounts` (accounts_extended), POST `/api/notifications/prepare`, POST `/api/profile/upload-logo`, PUT `/api/profile`, POST `/api/references/import-file`, PUT `/api/user-layouts/{user_id}/{page}` (self-scope؟).

## TESTS ADDED + RESULTS
- **Unit (`test_authz_ssot.py`): 32/32 PASS** — تصعيد users، هدّامة admin-only، ledger/operations/invoices/settings/fincontrol grounded، لا-كسر للقراءات، مساعدات mass-assignment/self-guard.
- **testing_agent HTTP (iteration_362 → 363): 27/27 PASS (100%)، retest_needed=False** — على الـbackend الحيّ، غير تدميري:
  - محاسب (احمد) → 403 على كل `/api/users` CRUD + financial-reset + cleanup + settings PUT + ledger DELETE.
  - admin (مدير) → 200 على GET `/api/users`؛ ledger create/invoices مسموحة للمحاسب.
  - تصعيد صلاحيات محاسب (POST users role=admin) → 403.
  - object-level: admin حذف/تعديل دور حسابه → 403.
  - قراءات (vehicles/customers/operations/journal-entries) → 200 للطرفين (لا انحدار)؛ بلا مصادقة → 401؛ صفر 500.

## AFTER MATRIX (512)
PUBLIC_INTENTIONAL 17 · **AUTHZ_COMPLETE 110** · AUTH_ONLY_NO_OBJECT_CHECK 363 (قراءات غير-حسّاسة) · **POLICY_DECISION_REQUIRED 22** · **MISSING_AUTHZ صامت = 0** · SUM 512 ✓.
(المصدر: `11_AUTHORIZATION_MATRIX_AFTER.md`, `authz_matrix_after.json`).

## WRITE-PATH SECURITY (286 production-reachable writers)
- كل مسارات الكتابة الحسّاسة (users/financial-reset/ledger/operations/invoices/settings/suppliers/fincontrol) أصبحت خلف السياسة المركزية.
- Katrina: 0 أداة كتابة نشطة (BOT_ALLOW_WRITES مطفأ)؛ الأدوات ترث صلاحيات المستخدم عبر بوابة server-side (لا تعتمد على prompt) ⇒ لا حاجة لتغيير كود؛ عند تفعيل الكتابة مستقبلاً تُطبَّق نفس السياسة.
- المتبقي (22 POLICY_DECISION_REQUIRED) هي مسارات كتابة إنتاجية بحاجة قرار سياسة (payroll/runtime/uploads/…).

## REMAINING AUTHZ RISKS
- 22 POLICY_DECISION_REQUIRED (payroll/runtime/finance-bot/uploads) — بلا حارس بعد.
- object-level حقيقي «per-object ownership» غير مطبّق لأن النموذج single-tenant (كل الطاقم يخدم كل العملاء) ⇒ object-level = tenant-scope + role + (self للمستخدمين). موثّق كقرار معماري لا نقص.
- تجاوزات صلاحية per-user (GRANT فوق الدور) لا تُقرأ في الـmiddleware (role-based)؛ الطرق الحسّاسة الحرجة تستخدم `resolve_request_actor` (يشملها).
- P1-SEC-UPLOAD (path traversal) لم يُعالَج في هذه المرحلة (منفصل).

## DEPLOYMENT PLAN (لا تنفيذ حتى موافقة منفصلة)
1. مراجعتك للتقرير + قرار الـ22 POLICY_DECISION_REQUIRED.
2. (اختياري) تدوير الأسرار قبل النشر.
3. Deploy عبر خط أنابيب Emergent (كود فقط؛ لا migration).
4. تحقق دخان بعد النشر: admin login + accountant 403 على users.

## ROLLBACK PLAN
- التغييرات كود فقط عبر git checkpoints ⇒ rollback المنصة (مجاني) يعيد الحالة فوراً.
- إزالة سطرَي الاستيراد+الاستدعاء في `server.py` تُعطّل الإنفاذ فوراً دون أثر بيانات (النظام يعود لسلوك «مُصادَق فقط»).
- لا تغييرات بيانات/DB ⇒ لا rollback بيانات مطلوب.

# النتيجة: ✅ PHASE 1 AUTHZ REPAIR COMPLETE & VERIFIED — بانتظار موافقتك (لا deploy، لا انتقال إلى Financial Repair).
