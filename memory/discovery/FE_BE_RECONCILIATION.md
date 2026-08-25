# FE→BE API RECONCILIATION (path-tail, all src)

Distinct FE call tails: **206** (across pages+components+services+hooks)
Distinct BE endpoint tails: **428** (of 512 endpoints)
FE tails matched to a BE path: **165** · UNMATCHED: **41**
(method+path exact matches: 203; path matches but method differs: 3)

## UNMATCHED FE call tails (no backend path found — verify: dead/typo/proxy/other service)

- `${(process.env.REACT_APP_BACKEND_URL ||`
- `ai/enhanced-chat`
- `ai/search-solutions`
- `ai/workshop/appointment`
- `ai/workshop/diagnose`
- `ai/workshop/info`
- `ai/workshop/search-technical`
- `ai/workshop/service-report`
- `approvals/matrix`
- `approvals/stats`
- `approvals/{}/approve`
- `approvals/{}/reject`
- `approvals/{}/{}`
- `auth/verify-otp`
- `catalog/summary`
- `conversations`
- `conversations/{}`
- `customers/{}/approvals`
- `customers/{}/history`
- `engines`
- `files/upload`
- `findings`
- `findings/scan`
- `findings/summary`
- `findings/{}/{}`
- `import/execute`
- `import/preview`
- `invoice-templates/import`
- `invoice-templates/import-url`
- `invoice-templates/{}/hard`
- `models`
- `reports/public/{}`
- `respond`
- `skills`
- `skills/{}`
- `technicians/{}`
- `user-layouts/{}/vehicleDetails`
- `vehicles/track/{}`
- `{}/settlements`
- `{}/settlements/{}`
- `{}/transactions`