# P1-SEC-UPLOAD + P0-DESTRUCTIVE-RESET-HARDENING — Final Report

Contract: the approved batch document. Code-only. Verified by `testing_agent` iterations 380 → 381.
Reports: `/app/test_reports/iteration_380.json` (found 2 misses) · `/app/test_reports/iteration_381.json` (closure, 0 critical).

---

## 1. Required fields

```text
P1_SEC_UPLOAD_STATUS               = COMPLETE (6 surfaces: 5 persistent -> object storage, 1 temp -> safe ephemeral)
RESET_P0_HARDENING_STATUS          = COMPLETE (fail-closed; DENIED with the enable flag absent)
QUALITY_GATE_EPHEMERAL_UPLOAD      = PASS (functional proof, not path-string removal)
PERSISTENT_LOCAL_UPLOADS_REMAINING = 0
SAFE_TEMP_PROCESSING_PATHS         = 1  (routes_references.py:151, tempfile.TemporaryDirectory, cleanup guaranteed)
LEGACY_LOCAL_READ_FALLBACK         = YES (read-only, labelled LEGACY TEMPORARY COMPATIBILITY, 5 read paths)
TOKEN_IN_FILE_URL                  = NO
FILES_MIGRATED_NOW                 = 0
OLD_FILES_MIGRATION_SCRIPT         = /app/scripts/migrate_local_uploads_to_object_storage.py (dry-run default)
OLD_FILES_MIGRATION_EXECUTED       = NO
RESET_EXECUTED                     = NO
SEED_EXECUTED                      = NO
DB_MUTATION                        = NO
FINANCIAL_MUTATION                 = NO
ACCOUNTING_ENGINE_CHANGED          = NO
ENV_CHANGED                        = NO
SECRETS_CHANGED                    = NO
DEPLOY                             = NO
```

`ENV_CHANGED = NO` note: no `.env` file was read-modified. A **new** `backend/.env.example` was added
containing only two non-secret variable *names* with empty values.

---

## 2. Before / after per finding

| # | Surface | Before | After |
|---|---|---|---|
| 1 | Vehicle files (`server.py:2887` upload_vehicle_file) | wrote to `UPLOAD_DIR/vehicles/{id}/{user_filename}`; 10 MB cap; MIME trusted from the browser header; traversal patched by regex | object storage; server-generated key; content-verified type; 25 MB cap; `storage_path` in metadata; download storage-first + legacy read-only + 410 when legacy bytes are gone |
| 2 | Vehicle files (`routes_vehicle_files.py`, router **not mounted**) | same local-disk pattern | object storage + new authenticated `GET /vehicles/{id}/files/{fid}/download` |
| 3 | Finance audit evidence (`routes_finance_bot.py:573`) | wrote to `uploads/finance_audit_evidence/{session}/…` — **audit evidence on ephemeral disk** | object storage, `is_deleted=False` retention-first, new authenticated `GET /evidence/{id}/download` |
| 4 | Document templates (`routes_document_templates.py:330`) | `target.write_text` / `shutil.copyfileobj` to `custom_templates/` | sanitised HTML / PDF bytes to object storage; `_content()` + `/download` storage-first with legacy read-only fallback |
| 5 | **Legacy templates router** (`routes_templates.py:136`) — *missed in the original scope, caught by iteration_380* | `shutil.copyfileobj` to `custom_templates/`; **no size cap, no content verification**; `download` wrote a temp file for builtins | object storage + `validate_upload` gating; builtins returned as `Response` with no filesystem write; `import shutil` removed |
| 6 | **Operation payment receipts** (`routes_extended.py:167`) — *missed in the original scope, caught by iteration_380* | base64 decoded and written to `uploads/operation_payment_receipts/{op_id}/` — **financial evidence on ephemeral disk** | `async`, content-verified, `build_named_object_key` so the public URL contract is **unchanged**; serving route storage-first + legacy read-only + 404 |
| 7 | Reference PDF import (`routes_references.py:142`) | `Path("/tmp")/file.filename` — attacker-influenced name, never cleaned up | `tempfile.TemporaryDirectory` + `uuid4` name, all pages read inside the context (cleanup guaranteed on success **and** exception), `validate_upload` before any parsing |
| 8 | `DELETE /api/operations` (`routes_extended.py:2517`) | reachable `delete_many({})` on `operations` + `journal_entries` behind permissions only | `require_destructive_authorization` **first**, then the original permission checks |
| 9 | `POST /api/admin/reset-inventory` (`server.py`) | **no `Request`, no auth argument at all** | takes `request`, guard runs first, returns the correlation id |

---

## 3. Modified / created files

**Created**
- `backend/core/object_storage.py` — transport, server-generated keys, 25 MB cap, per-surface allow-lists, magic-byte / container / text content verification
- `backend/core/destructive_guard.py` — 8-condition fail-closed guard
- `backend/.env.example` — two non-secret variable names only
- `backend/tests/test_p1_sec_upload_and_reset_guard.py`
- `backend/tests/test_p1_sec_upload_functional.py`
- `scripts/migrate_local_uploads_to_object_storage.py` — dry-run only, never executed
- `frontend/src/components/AuthenticatedFileImage.jsx`

**Modified**
- `backend/server.py`, `backend/routes_vehicle_files.py`, `backend/routes_finance_bot.py`,
  `backend/routes_document_templates.py`, `backend/routes_templates.py`,
  `backend/routes_extended.py`, `backend/routes_references.py`
- `frontend/src/pages/VehicleDetails.jsx`, `frontend/src/components/vehicle-details/VehicleDetailsChrome.jsx`

**Untouched**: `core/accounting_engine.py` · `backend/.env` · `frontend/.env` · `JWT_SECRET` · every financial route and model.

---

## 4. Tests and results

| Suite | Result |
|---|---|
| `tests/test_p1_sec_upload_and_reset_guard.py` + `tests/test_p1_sec_upload_functional.py` | **57 passed** (independently reproduced by iteration_381) |
| `tests/test_journal_pagination_iter361.py` + `tests/test_ar_ssot.py` | 20 passed — no financial-read regression |
| `tests/test_p0_red_findings_repair.py` | 28 passed / **6 pre-existing failures** — absolute-number drift, see §6 |
| Live denial matrix (preview) | `DELETE /api/operations` 403 `destructive_operations_disabled` · `POST /api/admin/reset-inventory` 403 same · unauth vehicle-file download 401 · operations count unchanged before/after |
| Hostile receipt filenames | `../../../etc/passwd` and `..%2F..%2Fsecret.png` → 404, zero bytes served |
| Migration dry-run | discovered=28 valid=12 invalid=16 conflicts=0 would_upload=12 total_bytes=21,605,441 orphan_files=17 missing_db_references=3 · `--apply` alone **REFUSED** |
| Durability | real object-storage round-trip passes (isolated `_selftest` prefix); every persistence call in the functional suite is monkeypatched, so **zero business writes** |
| Health | `/api/health` 200 · clean startup, no circular import from the two new `from core import object_storage` lines · login + `/api/auth/me` 200 · representative reads 200 · **0 HTTP 500** · no raw `_id` leaked |
| Frontend smoke | login + dashboard render, no console errors from the `AuthenticatedFileImage` chain |

---

## 5. Every remaining filesystem write, classified

| Location | Classification |
|---|---|
| `routes_references.py:151` `temp_path.write_bytes` | **expected-temporary** — inside `TemporaryDirectory`, random name, cleanup guaranteed both paths |
| `server.py` `_mem_write` / `MEM_DIR` / `SETTINGS_FILE`, `app_state.py`, `routes_import.py`, `routes_users.py`, `routes_user_layouts.py`, `routes_smart_accounting.py`, `routes_suppliers_extended.py`, `routes_alkabeer_bot.py`, `routes_finance.py` budgets, `smart_inventory_service.py`, `routes_templates.py:42` index | **safe** — text-mode JSON application state, not user uploads (pre-existing pattern, out of scope) |
| `bulk_delete_audit.py`, `core/financial_reset_engine.py` snapshots/audit | **destructive-protected** — audit/snapshot artefacts on the reset path |
| `manuals_converter.py`, `extract_toyota_content.py`, `parse_toyota_enhanced.py` | **needs-review** — offline tools, no importer and no route; unreachable over HTTP |
| All six migrated upload surfaces | **persistent-storage-fixed** |
| `routes_diesel_expert.py`, `routes_workshop_config.py`, `routes_fault_knowledge.py`, `routes_import.py` (UploadFile endpoints) | **safe** — parse in memory, zero binary writes |

Sweep command for future audits:
`grep -rnE "open\([^)]*['\"](wb|ab)['\"]\)|\.write_bytes\(|copyfileobj" --include="*.py" backend/`
→ only `routes_references.py:151` may appear.

---

## 6. Residual risks

1. **`P1-OBJECT-STORAGE-PHYSICAL-DELETION / RETENTION-POLICY`** (recorded as agreed). Object storage
   exposes no delete operation, so deletion is logical only (`is_deleted`). Vehicle photos and
   potentially personal files must not be assumed kept forever without a stated retention and
   deletion policy. Finance audit evidence is deliberately retention-first with no physical deletion.
2. **Legacy files still on container disk — will be lost on the next redeploy** (read-only counts,
   nothing moved or deleted):

   | Location | Files | Bytes |
   |---|---|---|
   | `uploads/vehicles` | 10 | 13,780,969 |
   | `uploads/finance_audit_evidence` | 9 | 37,014 |
   | `uploads/operation_payment_receipts` | 6 | 24,860 |
   | `custom_templates` | 3 | 8,197,309 |
   | **total** | **28** | **22,039,852** |

   Of these the dry-run classifies 12 as valid and 16 as INVALID (a `.MOV` video, `.txt` files on an
   image/PDF-only surface, and files named `.pdf` whose bytes are plain text). 17 are orphans with no
   database record, and 3 database records point at files that no longer exist.
3. **Verification level is stated, never faked.** `magic_verified` (JPEG/PNG/WebP/PDF/HEIC-HEIF) ·
   `container_verified` (OOXML zip and legacy OLE — `.doc`/`.xls` share one magic, so the sub-type
   still rests on the extension) · `text_heuristic` (TXT/CSV/HTML have no magic bytes; UTF-8
   decodability plus absence of NUL is the strongest reliable check available). The
   browser-declared content type is never sufficient on its own anywhere.
4. **Two legacy 410 reset endpoints** (`routes_finance.py:5583`, `:5750`) raise `410` on their first
   statement but still contain **unreachable** destructive code beneath it. Currently harmless; a
   future edit that removes the `raise` would arm it instantly. Recommend deleting the dead blocks or
   routing them through `require_destructive_authorization`. **Not changed in this batch.**
5. The **6 pre-existing test failures** in `tests/test_p0_red_findings_repair.py` pin absolute
   financial values (supplier account `2101 == 420.0`). The live trial balance no longer contains
   account `2101` at all, so the payable was settled in live data. Independently confirmed by two
   testing iterations as live-data drift with zero code overlap with this batch.
6. `routes_vehicle_files.py` and `routes_references.py` routers are **not mounted** in `server.py`, so
   those handlers are unreachable over HTTP. They were migrated anyway. Dead-module cleanup remains a
   separate P3 item.

---

## 7. External configuration required

**None for object storage.** `INTEGRATION_PROXY_URL` is injected by supervisor and `EMERGENT_LLM_KEY`
already exists in `backend/.env`; `POST {proxy}/objstore/api/v1/storage/init` returns 200 with a
storage key. The stop condition in §7 of the contract was therefore never triggered.

For a **future** authorised reset, two non-secret variables must be set (documented in
`backend/.env.example`, intentionally left unset here):
`DESTRUCTIVE_RESET_ENABLED` and `DESTRUCTIVE_RESET_ALLOWED_DB` (must equal `DB_NAME`).
They are deliberately absent in preview and production because the two share one database.

---

## 8. API compatibility

| Change | Impact |
|---|---|
| `GET /api/operations/{op_id}/payment-receipts/{filename}` | **unchanged** URL shape — the deterministic object key preserves it, no schema migration |
| `GET /api/vehicles/{id}/files/{file_id}` | unchanged; now returns `410` instead of `404` when a legacy local file's bytes are gone (more accurate) |
| Upload responses | now carry `storage_backend`, `storage_path`, `mime_type`, `content_verification`, `is_deleted`; the local `filePath` / `filename` field is no longer emitted for new records |
| New endpoints | `GET /api/finance-bot/evidence/{evidence_id}/download`, `GET /api/vehicles/{id}/files/{fid}/download` (unmounted module) |
| Destructive routes | now require `confirm=DELETE_ALL` + the `X-Destructive-Confirm` header + the enable flag; currently always `403` |
| Accepted file types | **not widened anywhere.** Both template endpoints still reject anything that is not `.html`/`.htm`/`.pdf`; payment receipts keep their stricter 6 MB cap |

---

## 9. Final quality-gate result

```text
four+ persistent upload surfaces off container-local storage ... PASS (5 of 5, 2 beyond original scope)
every remaining filesystem write processing-only/bounded/cleaned ... PASS (1, temp-dir)
finance audit evidence durable ................................... PASS
payment-receipt financial evidence durable ........................ PASS
auth + authorization on retrieval correct ......................... PASS
TOKEN_IN_FILE_URL = 0 ............................................ PASS (backend and frontend)
path-traversal attempts fail safely .............................. PASS (unit + live hostile filenames)
size and type validation reject correctly ........................ PASS
reset fail-closed: anonymous / user / admin-no-confirm /
  admin-no-flag / wrong double-confirm / wrong DB ................. PASS
no real reset executed, no migration executed .................... CONFIRMED

OVERALL = PASS
```

Stopped here. No deploy. No migration of old files. Phase 2A not started.
