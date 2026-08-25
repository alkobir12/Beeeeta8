# 03_ROUTE_INVENTORY (static)

Declared <Route path> entries: **41** + index:1 + redirects:8

| path | component |
|---|---|
| `/login` | Login |
| `/approval/:token` | ApprovalPublic |
| `/report/:token` | ReportPublic |
| `/track/:trackingId` | CustomerTracking |
| `customers` | Customers |
| `new-vehicle` | NewVehicle |
| `vehicle/:id` | VehicleDetails |
| `customer/:id` | CustomerDetails |
| `technicians` | Technicians |
| `suppliers` | Suppliers |
| `debts-followup` | DebtFollowUp |
| `parts` | PartsInventory |
| `parts-dashboard` | PartsDashboard |
| `catalog` | Navigate |
| `services` | ServicesManagement |
| `invoice-templates` | InvoiceDesignerStudio |
| `settings` | Settings |
| `account/security` | AccountSecurity |
| `profile` | Navigate |
| `archive` | VehicleArchive |
| `database-setup` | DatabaseSetup |
| `setup` | DatabaseSetup |
| `operations` | Operations |
| `import` | Navigate |
| `users` | Navigate |
| `quotations` | QuotationGenerator |
| `print` | DocumentPrint |
| `templates` | TemplatesManager |
| `denso-diagnostics` | Navigate |
| `fault-knowledge` | Navigate |
| `accounting/test` | div |
| `finance/invoices` | Invoices |
| `finance/taxes` | Taxes |
| `accounting/chart-of-accounts` | ChartOfAccounts |
| `accounting/comprehensive` | ComprehensiveFinancial |
| `accounting/journal-entries` | JournalEntries |
| `accounting/firewall` | FirewallPanel |
| `ai-financial` | Navigate |
| `system-audit` | SystemAudit |
| `moltbot` | Navigate |
| `*` | Dashboard |

## Redirects

- `catalog` → `/parts`
- `profile` → `/settings?tab=profile`
- `import` → `/settings?tab=import`
- `users` → `/settings?tab=users`
- `denso-diagnostics` → `/`
- `fault-knowledge` → `/`
- `ai-financial` → `/accounting/firewall`
- `moltbot` → `/`

## Index/fallback

- index → Dashboard