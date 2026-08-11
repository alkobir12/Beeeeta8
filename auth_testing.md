# Auth Testing Playbook

Security P0 hardening verification:
- Name-only login must return 401.
- Shared/default/admin PIN must return 401.
- Empty credential must return 401.
- Wrong credential must return 401.
- Valid per-user credential returns token with that user role only.
- Non-admin access to admin endpoint returns 403.
- Repeated failed attempts trigger lockout/rate limit.
- Responses/logs must not include secrets or PINs.
