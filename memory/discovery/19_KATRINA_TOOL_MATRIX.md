# 19_KATRINA_TOOL_MATRIX (static, from registry)

Total registered tools: **26**
Write-capable tools: **0** (require BOT_ALLOW_WRITES=1; env currently=unset)

| tool | agent | sensitivity | write | params |
|---|---|---|---|---|
| `accounting.journal_entries` | FinanceAgent | financial | no | workshop_id, limit, query |
| `customers.search` | FinanceAgent | financial | no | workshop_id, query, limit |
| `finance.ar_summary` | FinanceAgent | financial | no | workshop_id |
| `finance.payables_summary` | FinanceAgent | financial | no | workshop_id, limit, query |
| `finance.sales_report` | FinanceAgent | revenue | no | workshop_id, query, limit |
| `suppliers.search` | FinanceAgent | financial | no | workshop_id, query, limit |
| `firewall.cash_flow` | FirewallAgent | revenue | no | workshop_id |
| `firewall.health_score` | FirewallAgent | operational | no | workshop_id |
| `firewall.operation_integrity` | FirewallAgent | operational | no | workshop_id, limit |
| `firewall.top_alerts` | FirewallAgent | operational | no | workshop_id, limit |
| `inventory.low_stock` | WorkshopAgent | operational | no | workshop_id, limit |
| `nl.search` | WorkshopAgent | operational | no | workshop_id, query, limit |
| `operations.empty_items` | WorkshopAgent | operational | no | workshop_id, limit |
| `operations.recent` | WorkshopAgent | operational | no | workshop_id, limit |
| `operations.search` | WorkshopAgent | operational | no | workshop_id, query, limit |
| `operations.top_services` | WorkshopAgent | revenue | no | workshop_id, limit |
| `parts.list` | WorkshopAgent | operational | no | workshop_id, query, limit |
| `parts.search` | WorkshopAgent | operational | no | workshop_id, query, limit, in_stock_only |
| `runtime.audit_recent` | WorkshopAgent | operational | no | workshop_id, limit |
| `runtime.pending_approvals` | WorkshopAgent | operational | no | workshop_id, limit |
| `services.categories` | WorkshopAgent | operational | no | workshop_id |
| `services.search` | WorkshopAgent | operational | no | workshop_id, query, category, limit |
| `vehicles.recent` | WorkshopAgent | operational | no | workshop_id, limit |
| `vehicles.search` | WorkshopAgent | operational | no | workshop_id, query, limit |
| `vehicles.status_summary` | WorkshopAgent | operational | no | workshop_id |
| `workshop.active_visits` | WorkshopAgent | operational | no | workshop_id |

## Sensitivity distribution

- operational: 18
- revenue: 3
- financial: 5