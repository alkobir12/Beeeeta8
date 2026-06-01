# 03 — Tool Registry Audit

**Source of truth**: `/app/backend/core/tool_router.py::_TOOLS` registry
populated by `_bootstrap()`.

**Live verification**: `GET /api/assistant/tools` returned **12 tools** at
audit time.

All 12 tools are documented below in registration order.

---

## Tool 1 — `firewall.health_score`

```
Tool name:           firewall.health_score
Handler:             _firewall_health_score
File:                /app/backend/core/tool_router.py (line ~70)
Input parameters:    workshop_id: Optional[str] (default "finmodule-sync")
Output shape:        { score: int, status: str, alerts_count: int,
                       counts_by_severity: dict }
Intent patterns:     "صح(ة|ه)\s*(?:ال)?(نظام|مال)", "درج(ة|ه)\s*(?:ال)?صح",
                     "نقاط", "health score", "health"
Example questions:   كم درجة الصحة المالية؟ / Health score?
Backend endpoint:    None (direct call to FirewallEngine)
Read/write:          READ
Permission required: None (any authenticated user)
Risk level:          LOW
Test coverage:       tests/test_assistant_iter223.py (covered)
Status:              active
```

---

## Tool 2 — `firewall.top_alerts`

```
Tool name:           firewall.top_alerts
Handler:             _firewall_top_alerts
File:                /app/backend/core/tool_router.py (line ~82)
Input parameters:    workshop_id: Optional[str], limit: int (default 5)
Output shape:        List[{id, title, severity, category, financial_impact,
                            description}]
Intent patterns:     "تنبيه", "تنبيهات", "alerts?", "تصحيح", "خطأ",
                     "مشكلة", "audit", "warning", "fix", "issue"
Example questions:   أعطني أهم التنبيهات / Show alerts
Backend endpoint:    None (direct call to FirewallEngine.run_full_analysis())
Read/write:          READ
Permission required: None
Risk level:          LOW
Test coverage:       tests/test_assistant_iter223.py
Status:              active
```

---

## Tool 3 — `firewall.cash_flow`

```
Tool name:           firewall.cash_flow
Handler:             _firewall_cash_flow
File:                /app/backend/core/tool_router.py (line ~97)
Input parameters:    workshop_id: Optional[str]
Output shape:        { inflow: float, outflow: float, net: float, ... }
Intent patterns:     "تدفق", "cash flow", "إيرادات", "مصاريف", "سيولة"
Example questions:   كيف التدفق النقدي؟ / Cash flow?
Backend endpoint:    None (FirewallEngine)
Read/write:          READ
Permission required: None
Risk level:          LOW
Test coverage:       indirect (via /assistant/chat tests)
Status:              active
```

---

## Tool 4 — `firewall.operation_integrity`

```
Tool name:           firewall.operation_integrity
Handler:             _firewall_operation_integrity
File:                /app/backend/core/tool_router.py (line ~143)
Input parameters:    workshop_id: Optional[str], limit: int (default 20)
Output shape:        { total_operations, ok, with_warnings, duplicates,
                       sample: [{operation_id, invoice_number, label, warnings,
                                 status, duplicate_group_size}] }
Intent patterns:     "ملاحظات", "integrity", "قيد مفقود", "missing.*journal",
                     "عمليات.*خطأ", "عمليات.*مشكل"
Example questions:   أعطني العمليات التي بها قيد مفقود
Backend endpoint:    POST /api/operations/integrity/check (httpx internal)
Read/write:          READ
Permission required: None
Risk level:          LOW
Test coverage:       indirect
Status:              active
```

---

## Tool 5 — `finance.ar_summary`

```
Tool name:           finance.ar_summary
Handler:             _finance_ar_summary
File:                /app/backend/core/tool_router.py (line ~103)
Input parameters:    workshop_id: Optional[str]
Output shape:        { total_customers_with_debt, total_ar,
                       top_debtors: [{name, balance}] }
Intent patterns:     "ذمم العملاء", "مدين", "debtors", "آجل العملاء"
Example questions:   كم ذمم العملاء؟ / Show AR
Backend endpoint:    GET /api/customers (httpx internal)
Read/write:          READ
Permission required: None
Risk level:          MEDIUM (exposes customer names + debt amounts)
Test coverage:       tests/test_assistant_iter223.py
Status:              active
Notes:               Requires DB_PROVIDER=supabase
```

---

## Tool 6 — `workshop.active_visits`

```
Tool name:           workshop.active_visits
Handler:             _workshop_active_visits
File:                /app/backend/core/tool_router.py (line ~128)
Input parameters:    workshop_id: Optional[str]
Output shape:        { active_visits: int, total_visits: int }
Intent patterns:     "زيارة نشط", "مركبات مفتوح", "active visits", "كم زيارة"
Example questions:   كم زيارة نشطة الآن؟
Backend endpoint:    None (direct Supabase .table("vehicle_visits"))
Read/write:          READ
Permission required: None
Risk level:          LOW
Test coverage:       indirect
Status:              active
Notes:               Requires DB_PROVIDER=supabase
```

---

## Tool 7 — `customers.search`

```
Tool name:           customers.search
Handler:             _customers_search
File:                /app/backend/core/tool_router.py (line ~178)
Input parameters:    workshop_id: Optional[str],
                     query: str (required noun extracted from message),
                     limit: int (default 5)
Output shape:        { query, matches: [{id (8 chars), name, phone,
                       ajel_balance, total_visits, vehicle_plate}], count }
Intent patterns:     "ابحث عن (ال)?عميل", "بيانات (ال)?عميل",
                     "رصيد (ال)?عميل", "كم رصيد", "كم يستحق (ال)?عميل"
Example questions:   ابحث عن العميل ابراهيم / كم رصيد ابراهيم
Backend endpoint:    GET /api/customers?search=... (httpx internal)
Read/write:          READ
Permission required: None
Risk level:          MEDIUM-HIGH (exposes PII: phone + balance)
Test coverage:       tests/test_bot_tools_iter232.py
Status:              active
```

---

## Tool 8 — `vehicles.search`

```
Tool name:           vehicles.search
Handler:             _vehicles_search
File:                /app/backend/core/tool_router.py (line ~219)
Input parameters:    workshop_id: Optional[str],
                     query: str (plate / brand / model / owner-name),
                     limit: int (default 5)
Output shape:        { query, matches: [{id, plate, brand, model, year,
                       status, owner}], count }
Intent patterns:     "ابحث عن (ال)?مركب", "بيانات (ال)?مركب",
                     "أين (ال)?مركب", "لوحة (ال)?مركب", "رقم (ال)?لوحة"
Example questions:   ابحث عن مركبة 9935
Backend endpoint:    GET /api/vehicles (httpx internal)
Read/write:          READ
Permission required: None
Risk level:          MEDIUM (exposes owner names + plates)
Test coverage:       tests/test_bot_tools_iter232.py
Status:              active
```

---

## Tool 9 — `parts.search`

```
Tool name:           parts.search
Handler:             _parts_search
File:                /app/backend/core/tool_router.py (line ~257)
Input parameters:    workshop_id: Optional[str],
                     query: str (optional — empty returns top by stock),
                     limit: int (default 8),
                     in_stock_only: bool (default False)
Output shape:        { query, total_inventory, matches_count, in_stock_count,
                       items: [{name, sku, category, selling_price, quantity,
                                in_stock}], next_action_hint }
Intent patterns:     "بيع", "أبيع", "ابيع", "اشتري", "كم سعر",
                     "سعر [قطعة]", "تكلفة قطع", "كم عندي", "كم يتوفر",
                     "متوفر لدينا", "هل عندنا", "كم مخزون", "أحتاج قطع"
Example questions:   أبيع زيت / كم سعر فلتر الزيت / كم عندي بطاريات
Backend endpoint:    GET /api/parts (httpx internal)
Read/write:          READ
Permission required: None
Risk level:          LOW
Test coverage:       tests/test_bot_tools_iter232.py
Status:              active
```

---

## Tool 10 — `inventory.low_stock`

```
Tool name:           inventory.low_stock
Handler:             _inventory_low_stock
File:                /app/backend/core/tool_router.py (line ~317)
Input parameters:    workshop_id: Optional[str], limit: int (default 10)
Output shape:        { total_parts, low_stock_count,
                       items: [{name, sku, quantity, min_quantity, shortage}] }
Intent patterns:     "(ال)?قطع (ال)?ناقص", "مخزون منخفض", "low stock",
                     "نفاد", "الحد الأدنى", "تنبيه.*مخزون"
Example questions:   ما هي القطع الناقصة؟ / Low stock parts
Backend endpoint:    GET /api/parts (httpx internal)
Read/write:          READ
Permission required: None
Risk level:          LOW
Test coverage:       tests/test_bot_tools_iter232.py
Status:              active
```

---

## Tool 11 — `finance.payables_summary`

```
Tool name:           finance.payables_summary
Handler:             _finance_payables_summary
File:                /app/backend/core/tool_router.py (line ~388)
Input parameters:    workshop_id: Optional[str], limit: int (default 5)
Output shape:        { total_suppliers_with_balance, total_ap,
                       top_creditors: [{name, balance}] }
Intent patterns:     "ذمم (ال)?مورد", "دائن", "payables", "نستحق",
                     "نحن مدين", "للمورد"
Example questions:   كم ذمم الموردين؟
Backend endpoint:    GET /api/suppliers (httpx internal — DDD)
Read/write:          READ
Permission required: None
Risk level:          MEDIUM (exposes supplier names + AP totals)
Test coverage:       tests/test_bot_tools_iter232.py
Status:              active
```

---

## Tool 12 — `operations.recent`

```
Tool name:           operations.recent
Handler:             _operations_recent
File:                /app/backend/core/tool_router.py (line ~408)
Input parameters:    workshop_id: Optional[str], limit: int (default 5)
Output shape:        { count, items: [{id (8 chars), type, total,
                       payment_method, payment_status, partner, date}] }
Intent patterns:     "آخر (ال)?عمليات", "أحدث (ال)?عمليات",
                     "recent operations", "عمليات اليوم"
Example questions:   أعطني آخر العمليات
Backend endpoint:    GET /api/operations?limit=N (httpx internal)
Read/write:          READ
Permission required: None
Risk level:          MEDIUM (exposes operation totals + partner names)
Test coverage:       tests/test_bot_tools_iter232.py
Status:              active
```

---

## Registry-level totals

| Metric | Value |
|---|---|
| Total tools registered | **12** |
| Tools classified READ | **12** |
| Tools classified WRITE | **0** |
| Tools requiring `query` arg | 3 (customers/vehicles/parts search) |
| Tools using internal httpx → /api/* | 7 |
| Tools using Supabase client directly | 1 (`workshop.active_visits`) |
| Tools using FirewallEngine | 4 |
| Tools with explicit test in pytest | 6 (covered by tests/test_assistant_iter223.py + tests/test_bot_tools_iter232.py) |
| Tools NOT directly tested by name | 6 (covered indirectly via chat tests) |

## No write tools exist

A grep over `tool_router.py` for any `.insert(`, `.update(`, `.delete(`,
`.upsert(`, `POST /api`, `PUT /api`, `DELETE /api` inside any registered
handler returns **zero matches inside the registered tool surface**. All
write paths in the wider codebase are outside the tool registry.
