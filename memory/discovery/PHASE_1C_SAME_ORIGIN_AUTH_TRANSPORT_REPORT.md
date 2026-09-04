# PHASE_1C_SAME_ORIGIN_AUTH_TRANSPORT_REPORT

## Scope
- Authentication transport/routing only.
- No JWT secret changes.
- No Supabase credential changes.
- No PIN/password/user changes.
- No AccountingEngine changes.
- No financial/business mutations.
- No migrations.
- No Phase 2.

## Routing Finding
- SAME_ORIGIN_PROXY_SUPPORTED = YES for the configured/current Emergent host from `REACT_APP_BACKEND_URL`: `https://katrina-fix-core.preview.emergentagent.com`.
- Same-origin `/api/health` is reachable on that host.
- Older separate host `https://accounting-ssot-fix.preview.emergentagent.com` is not the supported same-origin transport target for this build and previously depended on failing cross-origin edge CORS.

## Implementation
- Browser API base is now relative same-origin `/api` through `resolveBackendBase()` returning `''` in browser runtime.
- Login uses `credentials: 'include'` only; fallback `credentials: 'omit'` was removed.
- Shared Axios client has `withCredentials: true` and global `axios.defaults.withCredentials = true`.
- Logout uses the same resolver instead of a separate cross-origin backend URL.

## Verification
- Browser same-origin flow on `https://katrina-fix-core.preview.emergentagent.com`:
  - `/api/health` = 200
  - `POST /api/auth/login` = 200
  - `GET /api/auth/me` after login = 200
  - reload
  - `GET /api/auth/me` after reload = 200
  - `GET /api/vehicles` = 200
  - `GET /api/customers` = 200
- Cookie attributes observed without token values:
  - HttpOnly = true
  - Secure = true
  - SameSite = None
  - Path = /
  - Domain = not required for same-origin
- Internal untrusted CORS probe did not grant credentialed authorization.
- External cross-origin edge still returns wildcard ACAO without ACAC, but this is no longer the primary browser auth path.

## Tests
- Local pytest suite: 25 passed / 0 failed.
- Frontend build: passed.
- Independent testing agent iteration 377: same-origin auth/data flow passed; no MOCKED APIs.

## Final
- AUTH_TRANSPORT_CLOSURE = PASS