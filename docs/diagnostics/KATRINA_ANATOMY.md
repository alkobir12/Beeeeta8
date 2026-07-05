# 🔬 KATRINA_ANATOMY.md — خريطة تشريح كاترينا (الموثّق من الكود الفعلي)

**التاريخ:** 2026-07-05 · **المنهج:** كل ادعاء هنا له مرجع (ملف:سطر) أو trace_id — حسب القاعدة الحاكمة لبروتوكول التشريح.
**أدلة trace حية:** `tr-133e4d8e9fd8` (قراءة: ذمم العملاء) · `tr-cfbe1304c8ce` (كتابة: أمر شراء — التقط نفاد رصيد LLM بأمانة).

---

## 0) الخلاصة التنفيذية — مستوى البوت وقدراته وصلاحياته

| السؤال | الإجابة الموثّقة |
|---|---|
| **الاسم/الإصدار المعلن في الكود** | «كاترينا» — `ASSISTANT_VERSION = "L16"` (`core/assistant_kernel.py:590-591`) |
| **المستوى الفعلي المعتمد** | **غير مُصدَّق بعد** — حسب قاعدة Verification Suite («الشهادة = أعلى مستوى مكتمل 100% + امتحان المالك»)، لم تُنفَّذ المستويات L1→L15 بعد (موقوفة على رصيد LLM). آخر تقدير موثّق قبل الحزمة: L6 راسب بدليل جلسة الذمم (وثيقة الحزمة نفسها). التقدير الهندسي من التشريح: بنية L14-L16 موجودة كوداً، والشهادة الحقيقية تنتظر التنفيذ |
| **نموذج LLM** | Claude Sonnet 4.6 عبر Emergent (`assistant_kernel.py:532`, `llm_intent_parser.py:229`) — timeout 60ث (150ث بوضع المطور) |
| **أدوات القراءة** | **21 أداة** مسجلة، 20/20 تعمل فعلياً (فحص A5 — صفر أدوات شبح) |
| **أفعال الكتابة** | **18 فعلاً** عبر محرك التنفيذ الموحد (ليست أدوات LLM) — `llm_intent_parser.py:35-53` |
| **بوابة الكتابة للأدوات** | `BOT_ALLOW_WRITES` غير مضبوط → **0** (أدوات الكتابة محجوبة بنيوياً) — `tool_router.py:35,115` |
| **الأربع أعين** | مفروضة سيرفرياً `ACTION_RUNTIME_ENFORCE_4EYES=true` (افتراضي) — `action_runtime.py:80`. المعتمدون: admin/manager/supervisor (`core/rbac.py:31`) — لا يعتمد أحد مسودته |
| **الهوية** | من JWT الموقّع حصراً (`routes_assistant.py:58-60` → `rbac.extract_identity:144`) — ترويسات الانتحال مُهملة |
| **التتبع** | كل رسالة = trace كامل في MongoDB `llm_traces` + `trace_id` في الرد (`assistant_kernel.py:1086-1140`, `core/llm_traces.py`) |

---

## 1.1) رحلة الرسالة الواحدة (Message Lifecycle)

```
[واجهة] AssistantProvider.jsx:405 → POST /api/assistant/chat/stream (SSE)
   │  (أو POST /api/assistant/chat — routes_assistant.py:44)
   ▼
[Middleware] حارس مصادقة عام (auth_guard داخل SecurityHeadersAndRateLimitMiddleware)
   │  JWT إلزامي لكل /api/* — 401 بدونه. Rate limit: 30 رسالة/دقيقة/IP (routes_assistant.py:38,45)
   ▼
[هوية] rbac.extract_identity(request) → proposer + role من التوكن الموقّع (routes_assistant.py:58-60,197-199)
   ▼
[نواة] assistant_kernel.chat() :1086 — يبدأ trace (llm_traces.start_trace) ثم _chat_impl() :656
   │
   ├─ 1. حفظ رسالة المستخدم بذاكرة الجلسة (shared_memory.append_message :677)
   ├─ 2. اعتراض وضع المطور rrr — admin فقط (developer_mode.handle_trigger :681)
   ├─ 3. حسم تأكيد معلّق «نعم/لا» لإجراء آمن قبل أي parsing (:689-710)
   ├─ 4. إلغاء سياقي «الغي آخر عملية» → سحب آخر مسودة معلقة (:714-717)
   ├─ 5. أوامر الذاكرة المباشرة («الذاكرة» / «احفظ في المعرفة: …») (:720-771)
   ├─ 6. قصّ بادئة /power إن وجدت (power_mode.strip_power_prefix :777-780)
   │
   ├─ 7. 🔀 القرار المركزي: هل الرسالة أمر كتابة؟ looks_like_action() :198-215
   │      (regex أفعال: اضف/سجل/احذف/اشتري/اشتريت… _ACTION_VERB_RE :155)
   │      نعم → unified_executor.execute_text() :786-799
   │              └─ LLM intent parse (llm_intent_parser.py:203) → عقد JSON منظم
   │                 → مستوى ١ آمن: awaiting_confirmation (echo-back + «نعم»)
   │                 → مستوى ٢ مالي/حذف: pending_approval (مسودة + أربع أعين)
   │                 → فشل/غير مفهوم → يسقط بصمت لمسار القراءة ⚠️ (:799 — نقطة تحويل صامتة)
   │
   ├─ 8. مسار القراءة: detect_tools() :127 — regex ثابتة _TOOL_PATTERNS :36-78
   │      (كلمات مفتاحية عربية/قصيمية → أسماء أدوات؛ **ليس** function-calling من LLM)
   │      → tool_router.call_tool() لكل أداة (:811) — النتائج تُجمع + بطاقات UI
   ├─ 9. بناء السياق: snapshot مالي حي (ai_context.build_context_snapshot :825 — يُعاد بناؤه كل رسالة، لا يتجمد)
   │      + موجز الورشة (context_brief :833) + ذاكرة top-k=5 (memory_engine.retrieve :849)
   ├─ 10. تركيب system message: البرومبت (:594-653, ~5,845 حرفاً بعد التنقيح — دليل tr-133e4d8e9fd8)
   │      + السياق + الموجز + الذاكرة + نتائج أدوات **هذه الرسالة فقط** (:865-869)
   ├─ 11. التاريخ: آخر 10 رسائل نصية (ai_context.get_conversation_history :872 → shared_memory)
   ├─ 12. نداء LLM: _llm_chat() :525 — تنقيح PDPL على system + النص (:549,556-557)
   │      → التاريخ يُضمَّن **داخل نص رسالة المستخدم** («السياق السابق للمحادثة:…» :552-554)
   │      → timeout 60ث (:563) → trace يسجل الطلب والرد الخام (:558-570)
   ├─ 13. fallback بلا LLM: تجميع نتائج الأدوات نصياً (:907-917)
   └─ 14. التخزين: رد المساعد في ذاكرة الجلسة (:922) + bot_audit (:933-946)
          + مؤشرات last_customer/vehicle/… من البطاقات (:949-972) + vector_memory (:973-990)
   ▼
[الرد] envelope: {response, cards[], tool_results[], executed?, trace_id, session_id, …} :992-1012
   + غلاف chat(): الملخص اليومي حسب الدور + تذكير المعلقات في أول رسالة (:1106-1123)
   + إنهاء الـ trace وإرفاق trace_id (:1133-1139)
   ▼
[واجهة] SSE: job → progress → tool → done (routes_assistant.py:201-263)
   + إن انقطع البث: GET /chat/result/{job_id} (:266-272, TTL 15 دقيقة :166)
   + بعد الرد: بثّ أحداث finance:updated / runtime:changed لتحديث الصفحات حياً (AssistantProvider._dispatchRefreshEvents)
```

---

## 1.2) جرد الأدوات الحقيقي (21 أداة — كلها قراءة)

**حقيقة معمارية حاسمة:** الأدوات تُستدعى **قبل** نداء الـ LLM بقرار regex من الـ router — **النموذج لا يرى تعريفات الأدوات ولا يستدعيها** (لا function-calling)؛ يرى فقط أسماءها في البرومبت (:619-624) و**نتائجها** محقونة في system message (:865-869).

| الأداة | من يستدعيها | شرط الاستدعاء الفعلي (regex `assistant_kernel.py:36-78`) | الـ LLM يرى | فحص A5 |
|---|---|---|---|---|
| firewall.health_score | router | «صحة النظام/المال، درجة الصحة، health» | النتيجة فقط | ✅ يعمل |
| firewall.top_alerts | router | «تنبيه/تحذير/خطأ/مشكلة/audit» | النتيجة فقط | ✅ |
| firewall.operation_integrity | router | «قيد مفقود/بدون قيد/سلامة/integrity» | النتيجة فقط | ✅ |
| firewall.cash_flow | router | «تدفق/إيراد/مصاريف/سيولة» | النتيجة فقط | ✅ |
| finance.ar_summary | router | «ذمم العملاء/مدين/متأخر/آجل» | النتيجة فقط | ✅ (دليل tr-133e4d8e9fd8) |
| finance.payables_summary | router | «ذمم المورد/دائنين/نستحق» | النتيجة فقط | ✅ |
| inventory.low_stock | router | «قطع ناقصة/مخزون منخفض/نفاد» | النتيجة فقط | ✅ |
| parts.search | router + query | «بيع/سعر قطعة/كم عندي/هل عندنا» | النتيجة فقط | ✅ |
| parts.list | router + query | «قطع الغيار/parts list» | النتيجة فقط | ✅ |
| operations.recent | router | «آخر العمليات/عمليات اليوم» | النتيجة فقط | ✅ |
| operations.search | router + query | «تفاصيل عملية فلان/عمليات [اسم]» + فلترة زمنية عربية (`tool_router._extract_date_range`) | النتيجة فقط | ✅ |
| customers.search | router + query | «ابحث عن عميل/رصيد/بيانات [اسم]/وش عند…» (نمطان :57-60) | النتيجة فقط | ✅ |
| vehicles.search | router + query | «ابحث مركبة/لوحة/بيانات سيارة» | النتيجة فقط | ✅ |
| workshop.active_visits | router | «زيارة نشطة/مركبات داخل» | النتيجة فقط | ✅ |
| nl.search | router + query | «أكبر مدينين/فواتير متأخرة/أعلى مبيعات» | النتيجة فقط | ✅ |
| runtime.pending_approvals | router | «اعتمادات كاترينا/موافقات معلقة» | النتيجة فقط | ✅ |
| runtime.audit_recent | router | «سجل التدقيق/من غيّر» | النتيجة فقط | ✅ |
| services.search | router + query | «الخدمات المتوفرة/سعر خدمة» | النتيجة فقط | ✅ |
| services.categories | router | «تصنيفات/أقسام الخدمات» | النتيجة فقط | ✅ |
| accounting.journal_entries | router + query | «قيد محاسبي/دفتر اليومية/ميزان مراجعة» | النتيجة فقط | ✅ |
| whatsapp.send | ⚠️ **لا نمط له** — لا يُستدعى من الشات إطلاقاً | فقط مباشرة عبر `POST /api/assistant/tool/whatsapp.send` | — | مُستثنى (إرسال خارجي حقيقي عبر Infobip — `tool_router.py:1127-1132`) |

### ⚠️ اكتشافان أمنيان من الجرد (تسجيل فقط — لا إصلاح بالجولة الأولى)
1. **`whatsapp.send` مسجل بلا `write=True`** (`tool_router.py:1127-1132` — لا معامل write) → **يتجاوز بوابة BOT_ALLOW_WRITES** رغم أنه كتابة/إرسال خارجي حقيقي.
2. **`POST /api/assistant/tool/{name}`** (`routes_assistant.py:123-127`) يسمح لأي JWT صالح (أي دور، حتى technician) باستدعاء **أي** أداة مباشرة — بما فيها whatsapp.send — **بلا فحص دور**.

### أفعال الكتابة الـ 18 (مسار منفصل — ليست أدوات)
`llm_intent_parser.ALLOWED_ACTIONS:35-53`: create_customer · create_vehicle · create_visit · create_supplier · close_visits · get_active_visits · delete_operation · delete_customer · delete_vehicle · update_customer · update_vehicle · **create_invoice · collect_payment · create_expense · reverse_entry · create_purchase** (مالية = أربع أعين دائماً) · get_customers · get_vehicles

| مستوى الحوكمة | الأفعال | الآلية | المرجع |
|---|---|---|---|
| مستوى ١ (آمن) | عميل/مورد/مركبة/زيارة/تعديل | `awaiting_confirmation` — echo-back + رد «نعم» يثبّت، «لا» يلغي | `unified_executor.py:565`, `_chat_impl:689-710` |
| مستوى ٢ (خطِر) | فاتورة/دفعة/مصروف/عكس/شراء/حذف | `pending_approval` — مسودة + بطاقة + معتمد **مختلف** (أربع أعين سيرفرية) | `unified_executor.py:507,534`, `action_runtime.py:80` |
| تعديل مسودة قبل الاعتماد | شراء | `PATCH /api/runtime/drafts/{id}/patch` (دفع/ضريبة/بنود/مورد) + إعادة resolver | routes_action_runtime |
| منع التكرار | نفس الفعل+الجهة+المبلغ معلّق | يرجع بطاقة «♻️ طلب مطابق معلق» بلا مسودة جديدة | `unified_executor._find_duplicate_pending` |
| مدقق قبل الاعتماد | مبلغ صفري/سالب/مرتفع ≥50K/تكرار 24س/ملاحظات مفتوحة | `core/draft_audit.py` → audit_notes في البطاقة | |

---

## 1.3) خريطة نافذة السياق (Context Window Map) — لكل رسالة جديدة

| المكوّن | يدخل؟ | من أي رسالة يبقى؟ | الحجم التقريبي | المرجع |
|---|---|---|---|---|
| System prompt | ✅ يُعاد بناؤه كل رسالة | — | ~4K حرف قبل الإضافات | `_system_prompt:594-653` |
| Snapshot مالي (تنبيهات+تدفق) | ✅ **حي — يُعاد بناؤه كل رسالة، لا يتجمد** | الرسالة الحالية فقط | متغير | `:825-830` |
| موجز الورشة (كتالوج حي) | ✅ | الحالية فقط | ~1K | `context_brief :833-838` |
| ذاكرة RRR (top-k) | ✅ انتقائية k=5 (لا حقن كامل) | عابرة للجلسات (Mongo) | ≤2K token سقف المعرفة | `memory_engine.retrieve :849`, ROADMAP قواعد الترقية |
| تاريخ المحادثة | ✅ آخر **10 رسائل نصية** — تُضمَّن **داخل نص رسالة المستخدم** لا كـ messages منفصلة | 10 للخلف، TTL الجلسة ساعة واحدة in-process | نصي فقط | `:872`, `_llm_chat:552-554`, `shared_memory.py:17` |
| نتائج أدوات **الرسالة الحالية** | ✅ خام في system message | الحالية فقط | كامل النتيجة | `:865-869` |
| **نتائج أدوات الرسائل السابقة** | ⚠️ **لا تدخل خام أبداً** — يبقى فقط ما صاغه المساعد نصاً في رده السابق (يدخل عبر التاريخ) | عبر نص الرد فقط | مضغوط/منسّق | `get_conversation_history` (ai_context.py:79-83 — role+content فقط، بلا tool meta) |
| تعريفات الأدوات (function specs) | ❌ لا ترسل — أسماء وصفية فقط في البرومبت | — | — | `:619-624` |

### 🔴 جوهر حادثة False Confession — الإجابة الدقيقة من الكود
نتائج الأدوات الخام **تعيش رسالة واحدة فقط**. في الرسالة التالية، الـ LLM يرى فقط *النص* الذي كتبه سابقاً (عبر التاريخ). إذا سأل المستخدم «راجع القيود» بعد عرض الذمم: النموذج لا يجد `output_raw` السابق في سياقه، فإن لم يُفعِّل الـ router أداة جديدة (regex lookup)، قد «يشكك» في أرقامه السابقة — لأنها فعلاً غير موجودة أمامه إلا كنص محادثة. **هذا سيناريو الفئة ب (6-9) في بروتوكول الاختبار، وL14 في الحزمة — الحكم النهائي يتطلب traces حية بعد شحن الرصيد.**
**عامل مفاقم:** ذاكرة الجلسة in-process بTTL ساعة (`shared_memory.py:17`) — إعادة تشغيل الخادم = فقدان تاريخ كل الجلسات الحية (الـ traces الجديدة في Mongo دائمة).

---

## 1.4) نقاط التحويل الصامتة (بين النموذج والمستخدم)

| # | النقطة | الاتجاه | الأثر | المرجع |
|---|---|---|---|---|
| 1 | **تنقيح PDPL** — أسماء/جوالات تُقنَّع قبل الإرسال | مستخدم→نموذج | النموذج يرى `[REDACTED]` بدل القيم؛ قد يعيد القناع في رده | `assistant_kernel:549,556-557`, `core/pdpl_redactor.py` |
| 2 | حقن التاريخ داخل نص رسالة المستخدم («السياق السابق للمحادثة:») | مستخدم→نموذج | النموذج يرى محادثة مسطّحة لا بنية أدوار حقيقية | `:552-554` |
| 3 | **سقوط صامت من مسار الكتابة للقراءة** — فشل intent parse (timeout/رصيد/JSON تالف) → الرسالة تُعامل كسؤال عادي | داخلي | أمر تنفيذ قد يرجع «إجابة كلامية» بلا مسودة — **دليل حي: tr-cfbe1304c8ce** (أمر شراء + نفاد رصيد → رد كلامي) | `_chat_impl:795-799` |
| 4 | إلحاق الملخص اليومي + تذكير المعلقات **قبل** نص رد النموذج (أول رسالة) | نموذج→مستخدم | ما يراه المستخدم ≠ response_raw (إضافة لا قص) | `chat():1106-1123` |
| 5 | fallback بلا LLM: تجميع نتائج الأدوات + رسالة قالبية | نموذج→مستخدم | رد بلا أي LLM يظهر كأنه رد البوت | `:907-917` |
| 6 | قوالب النظام: «✅ تم بنجاح» تصدر من المحرك لا من النموذج (قاعدة صدق مفروضة برومبتياً + بنيوياً) | نموذج→مستخدم | الرسائل التنفيذية مُولَّدة قالبياً | `_build_action_chat_response:413`, البرومبت `:634-638` |
| 7 | قصّ بادئة /power قبل المعالجة | مستخدم→نموذج | — | `power_mode.py:54` |
| 8 | رندر Markdown + بطاقات في الواجهة | نموذج→مستخدم | تحويل عرض فقط | `UnifiedAssistantDrawer.jsx` |
| 9 | انقطاع SSE > 60ث → الرد عبر Job/Poll | نموذج→مستخدم | نفس المحتوى بمسار بديل | `routes_assistant.py:162-272` |

---

## 2) المدخلات والمخرجات (سطح الـ API الكامل للبوت)

### مدخلات المحادثة
`POST /api/assistant/chat` و`/chat/stream` — Body: `{message, session_id?, workshop_id?, use_ai?=true, model?=(sonnet|ollama), daily_summary?=true}` + JWT (الهوية والدور يُشتقان منه حصراً).

### مخرجات المحادثة (envelope موحّد)
```json
{"success": true, "data": {
  "session_id", "response": "نص Markdown",
  "cards": [{type: Approval|Customer|Vehicle|Invoice|…, data, actions[]}],
  "tool_results": [{tool, success, result|error}],
  "executed": {"status": "committed|pending_approval|awaiting_confirmation|cancelled|…", "action", "entity_id", "approval_id"},
  "intent", "ai_used", "model_used", "developer_mode",
  "trace_id": "tr-…"   // 🆕 المرحلة 2 من بروتوكول التشريح
}}
```
أحداث SSE: `job` → `progress` → `tool` → `done|error` (`routes_assistant.py:201-263`).

### بقية السطح
| Endpoint | الوظيفة | حماية |
|---|---|---|
| GET /api/assistant/dashboard | 8 مؤشرات افتتاحية بلا LLM | JWT |
| GET /api/assistant/session/{id} · /memory/{id} · /report/{id} | سجل/ذاكرة/تقرير جلسة | JWT |
| GET /api/assistant/tools · /models · /stats · /alerts · /audit/recent | جرد وإحصاء | JWT |
| POST /api/assistant/tool/{name} | استدعاء أداة مباشر | ⚠️ JWT فقط — بلا فحص دور (اكتشاف 1.2) |
| POST /api/runtime/execute | تنفيذ نصي مباشر (نفس محرك الشات) | JWT + هوية من التوكن |
| POST /api/runtime/approve|reject|commit|rollback/{id} | دورة الاعتماد | JWT + دور اعتماد + أربع أعين |
| PATCH /api/runtime/drafts/{id}/patch · POST …/spawn_supplier | تعديل مسودة/إنشاء مورد فوري | JWT |
| GET /api/traces/{id} · /api/traces?session_id= · /stats | 🆕 سجل التشريح | JWT + دور اعتماد (403 لغيره — مُختبَر) |

### الربط الحي بالواجهة
بعد كل رد: `AssistantProvider._dispatchRefreshEvents` يبثّ `finance:updated` (عند committed) و`runtime:changed` — تستمع لها 15+ صفحة (Dashboard، العمليات، الذمم، القيود، الاعتمادات، الموردون…) فتتحدث بلا إعادة تحميل.

---

## 3) مصفوفة الصلاحيات (من الكود)

| الدور | مثال | يدخل الشات | يرى البيانات المالية | ينشئ مسودات | يعتمد (أربع أعين) | rrr وضع المطور | /api/traces |
|---|---|---|---|---|---|---|---|
| admin | مدير | ✅ | ✅ | ✅ | ✅ (ليس مسودته) | ✅ | ✅ |
| supervisor | احمد1 | ✅ | ✅ | ✅ | ✅ (ليس مسودته) | ❌ | ✅ |
| accountant | فرج1 | ✅ | جزئي (اختبار L13/L19 معلّق) | ✅ | ❌ | ❌ (مرفوض بالدور) | ❌ 403 (مُختبَر) |
| technician | مستخدم اختبار | ✅ | جزئي | ✅ | ❌ | ❌ | ❌ |

- الملخص اليومي حسب الدور: admin يرى الإيرادات، الموظف يرى مهامه المعلقة (`core/daily_summary.py`) — أرقامه من استعلامات مباشرة **بلا LLM**.
- الهوية لا تُنتحل: `x-user-role` مُهمل؛ JWT فقط (`test_credentials.md` + `rbac.py:144`).

---

## 4) طبقات الذاكرة (كما هي مبنية فعلاً)

| الطبقة | المخزن | العمر | تدخل سياق LLM؟ |
|---|---|---|---|
| ذاكرة الجلسة (رسائل + سياق pending_confirm + last_*) | in-process dict | ساعة (TTL) — تُفقد بإعادة التشغيل | آخر 10 رسائل نصاً |
| Vector memory (بطاقات دلالية) | in-process | جلسة | لا مباشرة (مسار /brain) |
| RRR Short→Long→Knowledge | MongoDB | قواعد الترقية الخمس المعتمدة (ROADMAP) — Knowledge باعتماد بشري فقط | top-k=5 انتقائي، سقف 2K token |
| bot_audit (metadata بلا محتوى) | MongoDB | دائم | ❌ |
| 🆕 llm_traces (payload خام كامل) | MongoDB | دائم | ❌ (للتشخيص — أدوار الاعتماد فقط) |

---

## 5) حكم المستوى — الإجابة المباشرة

- **ما يدّعيه الكود:** L16 (`assistant_kernel.py:591`).
- **ما هو مثبت فعلياً حتى اليوم:** بنية L16 (CRUD بأربع أعين + ذاكرة + PDPL + حوكمة + تتبع) **موجودة ومختبرة وحدةً** (123+7 pytest)، لكن **الشهادة الرسمية حسب حزمة التحقق = معلّقة**: المستويات L1→L15 لم تُنفَّذ بعد من الشات الحقيقي بأدلة trace، وL6 كان راسباً بآخر دليل موثّق، وامتحان المالك لم يجرِ.
- **الحكم الأمين:** «**L16 معمارياً — غير مُصدَّق تشغيلياً**». التصديق ينتظر: (1) شحن رصيد LLM، (2) تنفيذ L1→L15 + الملحقين ب/ج، (3) امتحان المالك على L8/L11/L13/L14.

---

## 6) فجوات مسجلة من هذا التشريح (تُضاف لقائمة الإصلاح — بلا تنفيذ الآن)

| # | الفجوة | الخطورة | المرجع |
|---|---|---|---|
| G1 | `whatsapp.send` بلا `write=True` → خارج بوابة BOT_ALLOW_WRITES | 🔴 | tool_router.py:1127 |
| G2 | `/api/assistant/tool/{name}` بلا فحص دور — أي JWT يستدعي أي أداة | 🔴 | routes_assistant.py:123 |
| G3 | السقوط الصامت كتابة→قراءة عند فشل intent parse (بلا إخبار المستخدم أن الأمر لم يُنفَّذ) | 🟠 | _chat_impl:795-799 + tr-cfbe1304c8ce |
| G4 | نتائج الأدوات السابقة لا تبقى خاماً في السياق (جذر False Confession المرجّح — يؤكَّد بـ L14) | 🟠 | ai_context.py:79 |
| G5 | ذاكرة الجلسة in-process — restart يمسح الجلسات الحية | 🟡 | shared_memory.py:17 |
| G6 | التاريخ يُحقن كنص داخل رسالة المستخدم لا كـ messages منظمة | 🟡 | _llm_chat:552 |

*(تُدمج مع 23 بند LEGACY_AUDIT.md في قائمة الإصلاح المرتبة بالتقرير النهائي.)*
