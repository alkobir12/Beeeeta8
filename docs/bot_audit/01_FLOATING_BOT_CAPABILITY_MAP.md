# 01 — Floating Bot Capability Map

**Audit date**: 2026-02-12
**Auditor**: E1 (read-only mode)
**Bot version**: Beeeeta8 Assistant L5.1
**Mode**: `single_assistant_read_only` (per `assistant_kernel.kernel_stats()`)

This map enumerates every capability the floating bot currently has, sourced
**directly from the live `tool_router` registry** at audit time (12 tools).

| Capability | Type | Tool / Component | R/W | Audience | Data Source | Status | Notes |
|---|---|---|---|---|---|---|---|
| البحث عن العملاء | search | `customers.search` (FinanceAgent) | **Read** | admin | `GET /api/customers` → Supabase | active | يرجع 5 مطابقات + رصيد الذمم لكل عميل |
| البحث عن المركبات | search | `vehicles.search` (WorkshopAgent) | **Read** | admin | `GET /api/vehicles` → Supabase | active | بحث بالـ plate/brand/model/owner |
| البحث عن القطع | search | `parts.search` (WorkshopAgent) | **Read** | admin | `GET /api/parts` → Supabase | active | يرجع السعر + الكمية + ترتيب بالـ"المتوفر أولاً" |
| القطع الناقصة | report | `inventory.low_stock` (WorkshopAgent) | **Read** | admin | `GET /api/parts` (فلتر `qty ≤ minQty`) | active | فلترة محلية بعد القراءة |
| ذمم العملاء | report | `finance.ar_summary` (FinanceAgent) | **Read** | admin | `GET /api/customers` (فلتر `ajelBalance > 0`) | active | Top-5 + إجمالي AR |
| ذمم الموردين | report | `finance.payables_summary` (FinanceAgent) | **Read** | admin | `GET /api/suppliers` (فلتر `ajelBalance > 0`) | active | Top-5 + إجمالي AP |
| آخر العمليات | report | `operations.recent` (WorkshopAgent) | **Read** | admin | `GET /api/operations?limit=N` | active | يرجع type/total/partner/status |
| Firewall — Health Score | analytics | `firewall.health_score` (FirewallAgent) | **Read** | admin | `FirewallEngine.run_full_analysis()` | active | درجة /100 + status |
| Firewall — Top Alerts | analytics | `firewall.top_alerts` (FirewallAgent) | **Read** | admin | `FirewallEngine.run_full_analysis()` | active | أعلى 5 حسب severity |
| Firewall — Cash Flow | analytics | `firewall.cash_flow` (FirewallAgent) | **Read** | admin | `FirewallEngine.run_full_analysis()` | active | 30-day inflow/outflow/net |
| Firewall — Operation Integrity | analytics | `firewall.operation_integrity` (FirewallAgent) | **Read** | admin | `POST /api/operations/integrity/check` | active | يكشف عمليات بقيد مفقود/duplicates |
| Workshop — Active Visits | report | `workshop.active_visits` (WorkshopAgent) | **Read** | admin | Supabase `vehicle_visits` table | active | فلتر `status ∉ {delivered, closed, cancelled}` |
| **Write to DB** | — | **— غير موجود** | — | — | — | **absent** | لا توجد أداة كتابة مسجّلة في الـ registry |
| **Approval / مصادقة** | — | **— غير موجود** | — | — | — | **absent** | لا أداة تستطيع الموافقة على شيء |
| **Create / Update / Delete** | — | **— غير موجود** | — | — | — | **absent** | RBAC = قراءة فقط بنيوياً |

## Capability counts

| | الإجمالي |
|---|---|
| Tools registered (live) | **12** |
| Read-only tools | **12** |
| Write tools | **0** |
| Agent classifications used | 3 (`FinanceAgent`, `WorkshopAgent`, `FirewallAgent`) — تصنيف label فقط (راجع `02_AI_AGENTS_AND_MODELS.md`) |
| Tools requiring `query` param | 3 (`customers.search`, `vehicles.search`, `parts.search`) |
| Tools using internal HTTP (httpx) | 7 |
| Tools using Supabase client directly | 2 (`workshop.active_visits`, `firewall.*` indirectly) |
| Tools using FirewallEngine | 4 |

## Intent → tool routing (regex-based, not LLM-based)

Located in `/app/backend/core/assistant_kernel.py::_TOOL_PATTERNS`.

| Intent pattern (Arabic phrasing) | Triggers tool |
|---|---|
| صحة المالية / درجة الصحة / health score | `firewall.health_score` |
| تنبيه / تنبيهات / alerts / تصحيح / مشكلة / audit | `firewall.top_alerts` |
| ملاحظات / integrity / قيد مفقود / عمليات.*خطأ | `firewall.operation_integrity` |
| تدفق / cash flow / إيرادات / مصاريف / سيولة | `firewall.cash_flow` |
| ذمم العملاء / مدين / debtors / آجل العملاء | `finance.ar_summary` |
| ذمم الموردين / دائن / payables / للمورد | `finance.payables_summary` |
| القطع الناقصة / مخزون منخفض / الحد الأدنى | `inventory.low_stock` |
| بيع X / أبيع X / كم سعر / كم عندي / هل عندنا | `parts.search` |
| آخر العمليات / أحدث العمليات / recent operations | `operations.recent` |
| ابحث عن العميل / بيانات العميل / كم رصيد | `customers.search` |
| ابحث عن مركبة / لوحة / رقم اللوحة | `vehicles.search` |
| زيارة نشطة / مركبات مفتوحة / كم زيارة | `workshop.active_visits` |

⚠️ The intent layer is **regex-only**. If user phrasing doesn't match the
patterns, **zero tools fire** and the bot answers from the LLM context-only
(context_snapshot + system prompt). This explains why "ما هي قدراتك؟" and
"هل تستطيع إنشاء فاتورة؟" both returned `tools=NONE` in the audit test —
they are conversational and don't match any data-fetch pattern.

## Page-aware suggestions (frontend only, no backend impact)

Defined in `UnifiedAssistantDrawer.jsx::SUGGESTIONS_BY_PATH`.

| Route prefix | Starter suggestions (4–5 chips) |
|---|---|
| `/customers` | كم ذمم العملاء؟ / من هم أعلى المدينين؟ / آخر العمليات / كم ذمم الموردين؟ |
| `/suppliers` | كم ذمم الموردين؟ / من أعلى الموردين دائنية؟ / أهم التنبيهات / كيف التدفق النقدي؟ |
| `/parts` | ما هي القطع الناقصة؟ / قطع وصلت للحد الأدنى / أهم تنبيهات المخزون / آخر العمليات |
| `/operations` | آخر العمليات / عمليات بها قيد مفقود / كم درجة الصحة المالية؟ / أهم التنبيهات |
| `/accounting/firewall` | أعطني أهم التنبيهات / كم درجة الصحة المالية؟ / عمليات بها قيد مفقود / كيف التدفق النقدي؟ |
| `(default)` | كم درجة الصحة المالية؟ / أعطني أهم التنبيهات / كم ذمم العملاء؟ / كم زيارة نشطة الآن؟ / كيف التدفق النقدي؟ |

## What this bot can NOT do (verified)

- ❌ Create / update / delete any entity in DB
- ❌ Open or navigate to any page automatically
- ❌ Fill any form
- ❌ Send WhatsApp / SMS / Email / push notifications
- ❌ Stream tokens (single full response per request)
- ❌ Accept voice input or output audio
- ❌ Authenticate, switch user identity, or impersonate
- ❌ Read files outside the registered tool set
- ❌ Execute arbitrary code, eval, or shell commands

The above are confirmed by reading every handler under
`/app/backend/core/tool_router.py` (lines 70–250). **No tool calls `.insert()`,
`.update()`, `.delete()` on any DB client.**
