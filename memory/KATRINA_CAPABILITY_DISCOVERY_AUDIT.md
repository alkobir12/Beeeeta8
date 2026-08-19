# 🔍 KATRINA COMPLETE CAPABILITY DISCOVERY AUDIT — READ ONLY
**التاريخ:** 2026-06 (جلسة الاكتشاف) · **القاعدة:** صفر إصلاحات، صفر تعديل بيانات، صفر تنفيذ مالي
**الأدلة الخام:** `/app/test_reports/katrina_discovery_raw.json` · Traces حية: `tr-eb5881b5768f`

---

## 1 — ARCHITECTURE MAP

```
رسالة المستخدم
  → UI: UnifiedAssistantDrawer.jsx (الشات) / ControlCenterTab.jsx (مركز التحكم)
  → AssistantProvider.jsx (session_id ثابت في localStorage + بث أحداث finance:updated/runtime:changed)
  → POST /api/assistant/chat (routes_assistant.py — الهوية من JWT الموقّع: proposer + proposer_role)
  → assistant_kernel.chat() (core/assistant_kernel.py)
      ├─ llm_traces.start_trace (كل رد يحمل trace_id)
      ├─ developer_mode.handle_trigger
      ├─ بوابة نية الكتابة: _ACTION_VERB_RE / _DIALECT_INTENT_RE
      │     → كتابة؟ → unified_executor.execute_text() → action_runtime (مسودة/اعتماد)
      │           → عند الاعتماد → financial_actions → AccountingEngine (SSOT)
      ├─ قراءة؟ → detect_tools() (أنماط regex حتمية) → tool_router.call_tool()
      │           → handlers → مصادر (unified_financial_engine / Supabase / APIs داخلية)
      ├─ بوابة الإيرادات: _REVENUE_TOOLS + _can_view_revenue(role)
      ├─ تركيب الرد: _llm_chat (prompt v3 مجمّد) + llm_intent_parser
      └─ provenance_guard (يحجب بلوكات نتائج أدوات غير منفَّذة — إصلاح D5)
  → الرد: {success, data:{response, tool_results, trace_id, cards, ...}}
```

| المكوّن | الملف | الدور | الحالة |
|---|---|---|---|
| Assistant Kernel | `core/assistant_kernel.py` (1408 سطر) | التوجيه + بوابات + تركيب الرد | مستخدم ✅ |
| Tool Router | `core/tool_router.py` (1492) | سجل 26 أداة قراءة + تنفيذ | مستخدم ✅ |
| Unified Executor | `core/unified_executor.py` (879) | تحويل نص → Action → مسودة | مستخدم ✅ |
| Action Runtime | `core/action_runtime.py` (1856) | مسودات/اعتمادات/تنفيذ/تدقيق | مستخدم ✅ |
| Financial Actions | `core/financial_actions.py` | كل قيد مالي عبر AccountingEngine | مستخدم ✅ |
| LLM Intent Parser | `core/llm_intent_parser.py` | تحليل نية الكتابة بالنموذج | مستخدم ✅ |
| Prompt Registry | `core/prompt_registry.py` | v3 مجمّد + rollback | مستخدم ✅ |
| LLM Traces | `core/llm_traces.py` | trace لكل رسالة وأداة | مستخدم ✅ |
| Provenance Guard | `core/provenance_guard.py` | منع اختلاق نتائج أدوات | مستخدم ✅ |
| Memory Engine | `core/memory_engine.py` + shared_memory | سياق cross-turn (last_list...) | مستخدم ✅ |
| Legacy splitter | `_legacy_extract_commands` | مقسم نصي قديم | معطَّل (dead، غير محذوف) ⚠️ |
| Assistant Panel | `GET /api/assistant/dashboard` | 8 مؤشرات بلا LLM | مستخدم ✅ |

---

## 2 — TOOL INVENTORY

**TOTAL_REGISTERED_TOOLS = 26 — كلها READ (write=False). `BOT_ALLOW_WRITES` غير مضبوط → تسجيل/استدعاء أي أداة كتابة عبر tool_router محظور بعقد Phase 3A.**

| الأداة | Agent | الغرض | المصدر | من الشات | من اللوحة | أثر مالي | الحالة |
|---|---|---|---|---|---|---|---|
| finance.ar_summary | Finance | إجمالي الذمم + كبار المدينين | **build_current_ar_snapshot (قانوني)** + طبقات ledger صريحة | ✅ | ✅ | قراءة | **WORKING** |
| finance.payables_summary | Finance | ذمم الموردين | suppliers.ajelBalance (مخزّن) | ✅ | ✅ | قراءة | **WRONG_SOURCE** ⚠️ |
| finance.sales_report | Finance | مبيعات فترة | جدول operations | ✅ | ❌ | قراءة | **PARTIAL/BROKEN** (paid دائماً 0) 🔴 |
| customers.search | Finance | بحث عميل + رصيده | /api/customers + ajelBalance مخزّن | ✅ | ❌ | قراءة | **PARTIAL** (مصدر الرصيد غير قانوني) ⚠️ |
| suppliers.search | Finance | بحث مورد + رصيد | suppliers مخزّن | ✅ | ❌ | قراءة | WORKING (بنفس تحفظ المصدر) |
| accounting.journal_entries | Finance | دفتر اليومية | /api/finance/journal-entries | ✅ | ❌ | قراءة | **PARTIAL** (الإجماليات على آخر N فقط) |
| firewall.health_score | Firewall | صحة مالية | FirewallEngine | ✅ | ✅ | قراءة | WORKING |
| firewall.top_alerts | Firewall | أهم التنبيهات | FirewallEngine | ✅ | ✅ | قراءة | WORKING |
| firewall.cash_flow | Firewall | تدفق 30 يوم | FirewallEngine (قيود خام) | ✅ 🔐 | ✅ | قراءة | **DUPLICATE_CALCULATOR** ⚠️ |
| firewall.operation_integrity | Firewall | عمليات بلا قيود | FirewallEngine | ✅ | ✅ | قراءة | WORKING (45 تحذير حالياً) |
| vehicles.search / recent / status_summary | Workshop | مركبات | /api/vehicles | ✅ | ❌ | — | WORKING |
| workshop.active_visits | Workshop | زيارات مفتوحة | vehicle_visits.status | ✅ | ✅ | — | **MISLEADING** (200 زيارة "نشطة"!) ⚠️ |
| operations.recent / search / empty_items / top_services | Workshop | عمليات | /api/operations | ✅ | ❌ | قراءة | WORKING (top_services غير مبوّب 🔴) |
| parts.search / list / inventory.low_stock | Workshop | مخزون | /api/parts | ✅ | ✅(low) | — | WORKING |
| services.search / categories | Workshop | كتالوج خدمات | /api/services | ✅ | ❌ | — | WORKING |
| nl.search | Workshop | بحث لغة طبيعية | مجمّع | ✅ | ❌ | قراءة | WORKING |
| runtime.pending_approvals / audit_recent | Workshop | اعتمادات/تدقيق | action_runtime | ✅ | ✅(count) | — | WORKING |

كل الأدوات الـ26 قابلة للوصول من الشات عبر أنماط `_TOOL_PATTERNS` — **UNREACHABLE_TOOLS = 0**.

---

## 3 — READ CAPABILITY MAP

| القدرة | متاح | المصدر | الجودة | نمط الفشل |
|---|---|---|---|---|
| عميل: بحث بالاسم/الجوال | YES | /api/customers | جيدة (تطبيع عربي + همزات) | not_found صريح |
| عميل: ذمته الحالية | **PARTIAL** | ajelBalance مخزّن (متطابق حالياً مع القانوني بالعينة: سعد العقيلي 4,500=4,500 لكن المصدر مختلف) | خطر انحراف | — |
| عميل: دفعاته/كشف حساب | **NO** | لا توجد أداة (الشات أجاب من سياق cross-turn) | — | NOT_IMPLEMENTED |
| مركبة: لوحة | YES | vehicles.search + نمط لوحة عارٍ | جيدة | not_found |
| مركبة: VIN | **NO** | لا نمط ولا resolver | — | NOT_IMPLEMENTED |
| مركبة: ملف مالي (إجمالي نهائي/مدفوع/متبقي) | **NO** | unified-v1 financial-summary ليس أداة | — | NOT_IMPLEMENTED 🔴 |
| مركبة: حالة/عدّادات | YES | vehicles.status_summary (مطابق للوحة: 19 حالية) | ممتازة | — |
| مالية: إجمالي الذمم | **YES قانوني** | build_current_ar_snapshot = 19,405 / 14 | ممتازة، fail-closed | خطأ صريح |
| مالية: قائمة دخل / صافي دخل / ميزانية / نقد بالحساب | **NO** | لا أدوات | — | NOT_IMPLEMENTED 🔴 |
| مالية: إيراد | PARTIAL | sales_report (عمليات: 16,170 هذا الشهر) ≠ قائمة الدخل القانونية (66,314) | مضلِّلة | — 🔴 |
| مالية: مصروفات | PARTIAL | cash_flow (outflow 822) ≠ القانوني (2,642) | مضلِّلة | حجب صريح لغير المخوّل ✅ |
| مالية: القيود | YES | journal-entries (آخر N) | جيدة | خطأ صريح عند non-200 ✅ |
| مالية: ميزان مراجعة | PARTIAL | نفس أداة القيود — يجمع المدين/الدائن على المعروض فقط | ناقصة | — |
| موردين: بحث/حركات | YES | suppliers + journal query | مقبولة | — |
| موردين: التزامات | **WRONG** | مخزّن = 0 بينما الدفتر = 420 (مورد مخرطة العوفي) | خاطئة فعلياً 🔴 | صفر صامت |
| عمليات: بحث/حالة/سداد | YES | /api/operations | جيدة | — |
| نظام: تنبيهات/اعتمادات/اكتشافات/منفَّذ | YES | firewall + runtime + financial-control | جيدة | — |

---

## 4 — ACTION / WRITE CAPABILITY MAP (فحص كود + سجل — بدون أي تنفيذ)

**كل الكتابة تمر حصراً عبر: unified_executor → action_runtime (مسودة → اعتماد → تنفيذ → تدقيق). كاترينا لا تملك أي مسار كتابة مباشر عبر tool_router.**

| Action | مسار | Canonical؟ | اعتماد | أربع أعين | كاترينا تنفذ مباشرة؟ | الحالة |
|---|---|---|---|---|---|---|
| create_customer / create_vehicle / create_visit / create_supplier | runtime upsert | Supabase مباشر (غير مالي) | مطلوب للالتزام | ✅ | ❌ تقترح فقط | WORKING |
| update_customer / update_vehicle / update_visit | runtime update | — | مطلوب | ✅ | ❌ | WORKING |
| collect_payment / create_invoice / create_expense / create_purchase | financial_actions | **AccountingEngine.post_entry ✅** | **إلزامي (RISKY)** | ✅ | ❌ | WORKING |
| reverse_entry | financial_actions → engine.reverse | **AccountingEngine ✅** | إلزامي | ✅ | ❌ | WORKING |
| delete_customer / delete_vehicle / delete_operation / bulk_delete | runtime | — | إلزامي (RISKY) | ✅ | ❌ | WORKING |
| finalize vehicle / deliver vehicle | — | — | — | — | — | **NOT_IMPLEMENTED من الشات** |
| approve final_customer_total | — (مسار الواجهة فقط) | — | — | — | — | NOT_CONNECTED |
| send WhatsApp | — (outbound share من الواجهة فقط) | — | — | — | — | NOT_CONNECTED (backlog معتمد) |
| create document / print | — | — | — | — | — | NOT_CONNECTED (مهمة P1 قادمة) |
| approve/reject draft | action_runtime.approve/reject | — | ذاته | proposer≠approver + admin override مسجَّل | ✅ للمعتمِد البشري | WORKING |

- `RISKY_ACTIONS` (11): bulk_delete, bulk_update, close_visits, collect_payment, create_expense, create_invoice, create_purchase, delete_customer, delete_operation, delete_vehicle, reverse_entry
- `FOUR_EYES = True` (مفعّل بيئياً)
- **كل قيد مالي يصل في النهاية إلى AccountingEngine** (financial_actions تستورد get_engine حصراً) ✅

---

## 5 — PERMISSION MODEL

- **هوية الشات:** من JWT الموقّع (`identity_from_request`) — proposer/proposer_role لا يُؤخذان من العميل عند وجود توكن. (fallback `payload.proposer` موجود لكنه غير قابل للوصول لأن auth_guard يفرض JWT على /api/*).
- **⚠️ FINDING (مقصود تصميمياً لكن يجب توثيقه):** الأدوات تستدعي APIs الداخلية بتوكن خدمة **`katrina-internal` بدور admin** (`_int_headers` في tool_router). أي أداة قراءة تصل لبيانات بمستوى admin، والتحكم بالدور يتم فقط عبر بوابة kernel (`_REVENUE_TOOLS`).
- **🔴 SECURITY/CONTROL FINDING (مؤكد حياً):** بوابة الإيرادات ناقصة:
  - `_REVENUE_TOOLS = {"firewall.cash_flow", "services.top"}` — الاسم `services.top` **قديم غير موجود**؛ الأداة الفعلية `operations.top_services` **غير مبوّبة** → فني حقيقي حصل على إيرادات الخدمات (2,600 ر.س...) في اختبار حي.
  - `finance.sales_report` (إيراد صريح) و`accounting.journal_entries` غير مشمولتين بالبوابة.
  - المقابل الإيجابي: `firewall.cash_flow` حُجبت عن الفني برسالة صريحة 🚫 (لا صفر صامت) ✅.
- **READ ≠ WRITE مثبت:** القراءة بمستوى admin (مع الثغرات أعلاه)، الكتابة محكومة بالكامل: مسودة + اعتماد + أربع أعين + rbac.can_approve. كاترينا **لا** تصبح admin في الكتابة.

| الدور | يقرأ | يقترح | ينفذ |
|---|---|---|---|
| technician | كل شيء عدا cash_flow (وثغرة top_services/sales_report) | مسودات | ❌ |
| accountant (احمد) | كل شيء (APPROVER_ROLES) | مسودات | يعتمد لغيره فقط (أربع أعين) |
| admin (مدير) | كل شيء | مسودات | يعتمد + admin override مسجَّل بالتدقيق |

---

## 6 — APPROVAL MODEL

المسار الفعلي: `USER_REQUEST → create_draft (تصنيف المصدر) → request_approval → approve (بوابات) → execute → audit`
- التصنيفات: USER_DRAFT / SYSTEM_DRAFT / AI_SUGGESTION / TEST_ARTIFACT (`_classify_draft_source`)
- **TEST_ARTIFACT_ACTIONABLE = NO** ✅ — سطر 898-910 في action_runtime: أي مسودة مالية من AI_SUGGESTION أو TEST_ARTIFACT **تُحجب من التنفيذ** حتى تحويلها صراحة إلى USER_DRAFT. الواجهة تعزلها (quarantinedApprovals) وتستبعدها من عدّاد "يحتاج قرارك".
- أربع أعين: `four_eyes_violation` عند approver==proposer ✅ (admin override مسموح ومسجَّل `APPROVAL_GRANTED_ADMIN_OVERRIDE`).
- **لا يوجد أي مسار عملية مالية حساسة بدون approval من الشات.** (فحص الكود: كل FINANCIAL/RISKY → requires_approval=True).
- المعلّق حالياً: 4 اعتمادات كلها USER_DRAFT (3 external_operation + 1 customer) — لا TEST_ARTIFACT معلّق.

---

## 7 — ENTITY RESOLUTION — **PASS** (بملاحظة واحدة)

| الاختبار | النتيجة |
|---|---|
| اسم تام «سعد العقيلي» | ✅ RESOLVED (فريد) |
| اسم جزئي «العقيلي» | ✅ ambiguous + 3 مرشحين (لا اختيار عشوائي) |
| اسم مكرر «محمد» | ✅ ambiguous + 6 مرشحين |
| كيان مجهول | ✅ not_found صريح |
| لوحة «د س ا 3313» | ✅ RESOLVED (مركبة العطان) |
| لوحة مجهولة | ✅ not_found |
| جوال | ✅ مدعوم (normalize_arabic على الأرقام) |
| VIN | ❌ غير مدعوم في أي resolver |
| تفضيل التطابق التام | ✅ («محمد الحربي» يفوز على «محمد علي الحربي») |
| ⚠️ resolve_visit_target | عند تعدد الزيارات المفتوحة المطابقة **يختار الأحدث صامتاً** (لا ambiguous) — الملف action_runtime.py:531 |

---

## 8 — INTENT ROUTING TEST (الطبقة الحتمية detect_tools — بدون LLM)

| السؤال | الأداة المكتشفة | التقييم |
|---|---|---|
| كم إجمالي الذمم؟ | finance.ar_summary | ✅ PASS |
| كم ذمة سعد العقيلي؟ | customers.search+operations.search | ✅ (حي: أجاب 4,500 صحيحاً عبر السياق) |
| من أكثر عميل عليه؟ | fallback اسمي (وليس nl.search) | ⚠️ PARTIAL (صيغة «عليه» غير مغطاة) |
| كم دخلنا هذا الشهر؟ | fallback اسمي (وليس sales_report) | 🔴 GAP («دخلنا» غير مغطاة) |
| كم المصروف؟ | firewall.cash_flow | ✅ PASS |
| كم صافي الدخل؟ | fallback — **لا توجد أداة أصلاً** | 🔴 NOT_IMPLEMENTED |
| هل الميزانية متوازنة؟ | fallback — لا أداة | 🔴 NOT_IMPLEMENTED |
| كم عندنا نقد؟ | fallback — لا أداة (رصيد حساب) | 🔴 NOT_IMPLEMENTED |
| اعرض آخر قيد | fallback (وليس journal_entries) | ⚠️ GAP («آخر قيد» مفرد غير مغطى) |
| كم زيارة لهذه المركبة؟ | workshop.active_visits | ⚠️ خاطئ دلالياً (يجيب عن كل الورشة) |
| وش يحتاج قراري اليوم؟ | fallback (وليس pending_approvals) | ⚠️ GAP |
| من الموردين؟ | fallback (وليس suppliers) | ⚠️ GAP |
| قيود مؤقتة | finance.ar_summary | ✅ PASS |
| اعرض سيارة فارس / كامري صالح / ح ق م 5520 | fallback اسمي ثم نمط اللوحة العارية للأرقام | ⚠️ PARTIAL |

**ملاحظة إنصاف:** طبقة LLM تعوّض جزءاً من الفجوات عبر تركيب الرد من نتائج الأدوات والسياق (مثبت حياً بسؤال العقيلي)، لكن الأسئلة التي لا أداة لها (صافي دخل/ميزانية/نقد) لا يمكن للـLLM الإجابة عنها بأرقام قانونية — والحارس يمنع الاختلاق.

---

## 9 — ZERO / NULL / FAILURE AUDIT (P0)

**SILENT_ZERO_FALLBACK_COUNT (دلالي مؤكد) = 2** 🔴

| # | الموقع | الوصف | التصنيف |
|---|---|---|---|
| 1 | `tool_router.py:659` `_finance_sales_report` | يقرأ `paidAmount`/`paid_amount` وهي **مفاتيح غير موجودة** في العمليات (الفعلية: `totalPaid`/`paymentAmount`/`advancePaid`) → **المدفوع دائماً 0 وغير المدفوع = الإجمالي دائماً** (مثبت: 16 عملية × 16,170 كلها "غير مدفوعة") | SILENT_ZERO 🔴 |
| 2 | `tool_router.py:521-523` `_finance_payables_summary` | يجمع `suppliers.ajelBalance` المخزّن = **0** بينما الدفتر القانوني يظهر التزام مورد فعلي = **420** (مخرطة العوفي 2101) | SILENT_ZERO / WRONG_SOURCE 🔴 |
| 3 | `tool_router.py:303` `_workshop_active_visits` | "زيارات نشطة" = **200** (كل زيارة status ليست delivered/closed/cancelled — تشمل زيارات قديمة لمركبات مسلَّمة) مقابل 19 مركبة حالية فعلياً | MISLEADING_METRIC ⚠️ |
| 4 | `tool_router.py:358` `_customers_search` | `ajel_balance` من الرصيد المخزّن (طبقة قديمة) وليس المحرك القانوني — متطابق حالياً بالعينة لكنه غير مضمون | WRONG_SOURCE_RISK ⚠️ |
| 5 | `routes_assistant.py` dashboard | `.get(key, 0)` بعد نجاح الأداة (لو غاب المفتاح → 0) — لكن عند فشل الأداة **يُحذف المؤشر ولا يُعرض صفر** ✅ | LOW |

قِيَم `or 0` الإجمالية (معظمها تحويل عرض مشروع): tool_router = 32، assistant_kernel = 12.
**الإيجابيات المثبتة:** ar_summary fail-closed صريح ✅ · journal non-200 → خطأ صريح ✅ (تعليق CR-4 يمنع "دفتر فارغ متوازن" الزائف) · أداة مفقودة → `tool not found` صريح ✅ · حجب الصلاحية → رسالة 🚫 صريحة ✅.

---

## 10 — CHAT VS ASSISTANT PANEL

| المؤشر | CHAT | PANEL | CANONICAL | DELTA |
|---|---|---|---|---|
| Total AR | 19,405.0 | 19,405.0 | 19,405.0 (build_current_ar_snapshot) | **0.00** ✅ |
| Debtor Count | 14 | 14 | 14 | 0 ✅ |
| Total AP | 0 | 0 | **420 (دفتر)** | **-420** 🔴 (متطابقان على مصدر خاطئ) |
| Revenue (شهر) | 16,170 (sales_report) | لا يُعرض | 66,314 (قائمة الدخل) | 🔴 مصدر مختلف |
| Expenses | 822 (cash_flow outflow) | — | 2,642 | 🔴 مصدر مختلف |
| Net Income | لا أداة | — | 63,672 | NOT_IMPLEMENTED |
| Vehicle Remaining | لا أداة | — | unified-v1 | NOT_IMPLEMENTED |
| زيارات نشطة | 200 | 200 | 19 مركبة حالية (لوحة التحكم) | 🔴 مقياس مضلِّل |

**CHAT_PANEL_PARITY = PASS** (الشات واللوحة يقرآن نفس الأدوات — لا انحراف بينهما)
**CHAT_CANONICAL_PARITY = PARTIAL** (الذمم قانونية ✅ — الإيراد/المصروف/الموردون من مصادر غير قانونية 🔴)

---

## 11 — SOURCE OF TRUTH AUDIT

| المعلومة | المصدر الفعلي | التصنيف |
|---|---|---|
| Total AR / كبار المدينين | `unified_financial_engine.build_current_ar_snapshot` | **CANONICAL** ✅ |
| طبقات الذمم (ledger/pending/temp-deferred) | `ar_ledger.summary` بأسماء صريحة | CANONICAL (طبقي) ✅ |
| رصيد عميل في البحث | `customers.ajelBalance` | **LEGACY/STORED** ⚠️ |
| ذمم الموردين | `suppliers.ajelBalance` | **LEGACY — خاطئ فعلياً (0 مقابل 420)** 🔴 |
| الإيراد (sales_report) | جدول operations | **DUPLICATE_CALCULATOR** 🔴 |
| تدفق نقدي/مصروف | FirewallEngine على القيود الخام | **DUPLICATE_CALCULATOR** 🔴 |
| القيود | /api/finance/journal-entries | CANONICAL (محدود بآخر N) |
| قائمة الدخل / الميزانية / صافي الدخل | — | **غير متاح لكاترينا إطلاقاً** |
| متبقي المركبة | — (unified-v1 ليس أداة) | غير متاح |
| المخزون/الخدمات/العمليات | APIs التطبيق | CANONICAL |

**WRONG_SOURCE_COUNT = 2 · DUPLICATE_CALCULATOR_COUNT = 2 · UNKNOWN_SOURCE_COUNT = 0**

---

## 12 — FAILURE BEHAVIOR

| السيناريو | السلوك الفعلي | التقييم |
|---|---|---|
| DB غير متاح | ar_summary يرجع خطأ صريحاً (fail-closed) — لا صفر | ✅ |
| API يرجع non-200 | journal tool → `error: HTTP xxx` صريح | ✅ |
| عميل غير موجود | not_found → الشات يقول لا يوجد / يقترح إضافة | ✅ |
| عميل مكرر | قائمة مرشحين — لا اختيار عشوائي | ✅ |
| صلاحية مرفوضة | رسالة 🚫 صريحة (مثبت حياً للفني) | ✅ |
| أداة مفقودة | `tool not found` صريح | ✅ |
| مصدر يرجع null | ar_summary يمرر null كما هو (لا يحوله 0) | ✅ |
| قيمة مالية حقيقية = 0 | ⚠️ الخطر الوحيد: payables يعرض 0 من مصدر خاطئ فلا يمكن تمييز الصفر الحقيقي | 🔴 |
| LLM budget منتهٍ | خطأ صادق في الـtrace (سابقة tr-cfbe1304c8ce) | ✅ |
| اختلاق نتائج أدوات | provenance_guard يحجب البلوكات المزيفة (D5) | ✅ |

---

## 13 — DISCOVERY / PROACTIVE TABS

| التبويب | المصدر | التصنيف |
|---|---|---|
| يحتاج قرارك | `GET /api/runtime/approvals?status=pending` مع استبعاد TEST_ARTIFACT من العدّاد والأزرار | REAL SYSTEM EVENTS ✅ |
| اكتشفته كاترينا | `GET /api/financial-control/findings` (محرك قواعد فحص مالي) + عرض TEST_ARTIFACT المعزولة كأثر غير قابل للتنفيذ | RULE ENGINE ✅ |
| تم بواسطة كاترينا | `GET /api/runtime/executions` (سجل تنفيذ حقيقي) | REAL AUDIT ✅ |
| المحادثة | كيرنل + أدوات + LLM | REAL |

**Test Artifacts لا تظهر كقرار حقيقي** ✅ (عدّاد الشارة يستبعدها، `isTest` يعطل الأزرار، والخلفية تمنع تنفيذها).

---

## 14 — FINAL CAPABILITY MATRIX (مختصر بالحالة)

| النطاق | WORKING | PARTIAL | BROKEN | NOT_CONNECTED / NOT_IMPLEMENTED |
|---|---|---|---|---|
| قراءة عملاء | بحث/زيارات | رصيد (مصدر مخزّن) | — | كشف دفعات العميل |
| قراءة مركبات | لوحة/حالة/عدّادات | — | — | VIN · الملف المالي (متبقي/مدفوع/إجمالي نهائي) |
| قراءة مالية | إجمالي الذمم (قانوني) · قيود | ميزان مراجعة (جزئي) · إيراد/مصروف (مصادر مكررة) | **paid في sales_report** | قائمة دخل · ميزانية · صافي دخل · نقد بالحساب · AR aging |
| موردين | بحث | حركات | التزامات (0 مقابل 420) | — |
| عمليات | recent/search/integrity/top | — | — | — |
| كتابة | كل الإجراءات الـ16 عبر اعتماد + أربع أعين + AccountingEngine | — | — | إنهاء/تسليم مركبة · مستندات/طباعة · واتساب (بقرار مؤجل) |
| نظام | تنبيهات/اعتمادات/اكتشافات/تدقيق | زيارات نشطة (مقياس مضلِّل) | — | — |

---

## 15 — FINAL NUMBERS

```
TOTAL_REGISTERED_TOOLS      = 26 (كلها READ)
TOTAL_REACHABLE_TOOLS       = 26 (شات) / 8 (لوحة المساعد)
WRITE_ACTION_TYPES          = 16 (عبر unified_executor/action_runtime حصراً)
APPROVAL_REQUIRED_ACTIONS   = 11 RISKY + كل الإجراءات المالية (أربع أعين مفعّلة)

WORKING                     = 20 أداة
PARTIAL                     = 4  (sales_report، customers.search-balance، journal-totals، active_visits)
BROKEN                      = 1  (كشف المدفوع في sales_report — مفاتيح غير موجودة)
NOT_CONNECTED               = 3  (مستندات/طباعة، واتساب، اعتماد الإجمالي النهائي)
NOT_IMPLEMENTED (قدرات)     = 7  (قائمة دخل، ميزانية، صافي دخل، نقد بالحساب، ملف مركبة مالي، VIN، كشف دفعات عميل)

SILENT_ZERO_FALLBACKS       = 2  (sales_report.paid · payables.total_ap)
WRONG_SOURCE_CAPABILITIES   = 2  (payables · customer-balance-in-search)
DUPLICATE_CALCULATORS       = 2  (sales_report · firewall.cash_flow)
UNREACHABLE_TOOLS           = 0
PERMISSION_GATE_HOLES       = 2  (operations.top_services «اسم قديم services.top» · finance.sales_report غير مبوّبة)
PENDING_APPROVALS           = 4  (كلها USER_DRAFT — لا TEST_ARTIFACT معلّق)
```

---

## 16 — FINAL VERDICT

| المحور | الحكم |
|---|---|
| KATRINA_ARCHITECTURE | **PASS** (فصل نظيف: قراءة أدوات / كتابة اعتمادات / SSOT محاسبي) |
| KATRINA_VISIBILITY | **PARTIAL** (لا ترى قائمة الدخل ولا الميزانية ولا الملف المالي للمركبة) |
| KATRINA_ENTITY_RESOLUTION | **PASS** (ملاحظة: زيارة متعددة المطابقات تُحسم بالأحدث صامتاً) |
| KATRINA_INTENT_ROUTING | **PARTIAL** (فجوات صيغ: دخلنا/آخر قيد/يحتاج قراري/الموردين — يعوضها LLM جزئياً) |
| KATRINA_CANONICAL_READS | **PARTIAL** (الذمم قانونية 100% ✅ — الإيراد/المصروف/الموردون مصادر مكررة/قديمة 🔴) |
| KATRINA_CHAT_PANEL_PARITY | **PASS** (دلتا 0.00 على كل المؤشرات المشتركة) |
| KATRINA_FAILURE_HANDLING | **PASS** (fail-closed، لا اختلاق، أخطاء صريحة، حجب صريح) |
| KATRINA_PERMISSION_MODEL | **PARTIAL** (كتابة محكومة ✅ — قراءة بتوكن admin داخلي + ثغرتا بوابة إيرادات مؤكدتان حياً 🔴) |
| KATRINA_APPROVAL_MODEL | **PASS** (أربع أعين + عزل TEST_ARTIFACT + كل قيد عبر AccountingEngine) |

# ⚖️ KATRINA_OVERALL_READINESS = **PARTIAL**

**أخطر 5 نتائج (بدون إصلاح — بانتظار قرارك):**
1. 🔴 P0: `finance.sales_report` يعرض "المدفوع = 0" دائماً (مفاتيح paidAmount غير موجودة — الصحيح totalPaid/paymentAmount)
2. 🔴 P0: ذمم الموردين لدى كاترينا = 0 بينما الدفتر = 420 (مصدر مخزّن قديم بدل الدفتر)
3. 🔴 P0: تسريب إيرادات لدور الفني عبر `operations.top_services` (بوابة تشير لاسم أداة قديم) + `sales_report` غير مبوّبة
4. 🟠 P1: إيراد/مصروف كاترينا من حاسبات مكررة تخالف قائمة الدخل القانونية (16,170/822 مقابل 66,314/2,642) — ولا توجد أداة قائمة دخل أصلاً
5. 🟠 P1: "زيارات نشطة = 200" مقياس مضلِّل (مقابل 19 مركبة حالية) + الملف المالي للمركبة (متبقي/مدفوع) غير متاح للشات إطلاقاً
