# P1-SEC-UPLOAD + P0-DESTRUCTIVE-RESET-HARDENING — Approved Contract

Status: **APPROVED**. This document is the binding contract for the batch.

Code-only. No deployment, no data migration, no movement or deletion of existing files, no change
to accounting logic, balances, journal entries, operations or the chart of accounts, no change to
`.env` or secrets.

---

## 1. Scope correction agreed at approval

The readiness scanner flagged five paths, but they are **not the same kind of thing**. They split:

**Persistent user files → object storage (four surfaces)**

| Surface | What is stored |
|---|---|
| Vehicle files | photos, diagnostic attachments on a vehicle record |
| Document templates | uploaded template assets |
| Finance audit evidence | evidence attached to audit findings |
| References | reference documents |

**Processing temp file → stays on the filesystem, made safely ephemeral (one path)**

The reference-import path writes an uploaded PDF to a temporary file only so a parser can read it,
then never needs it again. Pushing that into durable storage would be storing rubbish forever just
to silence a scanner. Instead it gets: an OS-managed temporary directory, a random server-generated
name, and cleanup that is guaranteed on both success and failure. Nothing about it is recorded as a
durable reference.

The governing rule for the batch:

- `PERSISTENT_USER_FILES` → object storage
- `PROCESSING_TEMP_FILES` → safe ephemeral temp + guaranteed cleanup

---

## 2. Approved decisions

**2.1 Files already on disk — read-only legacy fallback: YES**

Reads try object storage first, then fall back to the old local path only when needed. No existing
file is moved, no existing file is deleted, no existing database reference is rewritten. New uploads
never use local disk as their durable home. The fallback is labelled in code as
`LEGACY TEMPORARY COMPATIBILITY`, explicitly not the final storage architecture. The report states
how many files and which locations still depend on it.

**2.2 Deletion — soft-delete, with the two categories kept separate**

Object storage exposes no delete operation, so "delete" can only mean "marked deleted".

- *Finance audit evidence*: retention-first. No physical deletion in this batch. Logical hiding only
  where the existing workflow already requires it.
- *Ordinary non-financial files*: soft-delete now to preserve compatibility, plus a recorded residual
  requirement — **`P1-OBJECT-STORAGE-PHYSICAL-DELETION / RETENTION-POLICY`** — because vehicle photos
  and potentially personal files must not be assumed kept forever without a stated retention and
  deletion policy.

No fake delete API will be invented.

**2.3 Destructive reset — fully fail-closed**

A future legitimate reset must satisfy all of: authenticated actor · privileged server-side
authorization · explicit destructive confirmation · a double-confirmation mechanism · a dedicated
enable flag · audit log · correlation/request id · environment and database protection.

With the enable flag absent, reset is **DENIED**. The flag value is not added to `.env` in this
batch; only the variable name is documented in `.env.example` if that fits the project, and it
carries no secret. A version without an environment guard is explicitly rejected — preview is not a
safe environment for reset, because preview and production share one database.

**2.4 Browser file delivery — authenticated fetch to a blob/object URL, only**

`TOKEN_IN_FILE_URL = NO`. No session or access token may appear in an image URL, query string,
download URL or redirect URL. This applies to finance evidence, vehicle photos, references and
templates alike. Authorization stays server-side on every file fetch. Blob URLs are released with
`URL.revokeObjectURL`, loading and error states are handled, and authorization is never written to
logs.

**2.5 Limits and accepted types**

Maximum **25 MB** per file. No video in this batch.

- Vehicle files: JPEG, PNG, WebP, HEIC/HEIF, PDF
- Finance audit evidence: JPEG, PNG, WebP, HEIC/HEIF, PDF
- Document templates / references: JPEG, PNG, WebP, PDF, TXT, CSV, DOC/DOCX, XLS/XLSX

HEIC/HEIF is accepted only if the detection actually available can verify it. Where reliable content
verification is not possible for a format, no pretence of full verification is made — the best
available reliable check is applied and the verification level plus its residual limitation is
stated in the report. The browser-declared content type is never sufficient on its own.

---

## 3. Quality gate — functional proof required

The batch is **not** considered passing merely because path names disappeared from the scanner.
Required proof:

- the four persistent upload surfaces no longer depend on container-local storage
- every remaining filesystem write is processing-only, bounded, and cleaned up
- finance audit evidence is durable
- authentication and authorization on retrieval are correct
- `TOKEN_IN_FILE_URL = 0`
- path-traversal attempts fail safely
- size and type validation reject correctly
- reset is fail-closed for: anonymous, ordinary user, privileged user without confirmation, and
  privileged user without the enable flag
- no real reset is ever executed, and no migration is ever executed

---

## 4. Hard prohibitions (unchanged)

No deploy · no migration run · no `seed_database.py` run · no reset endpoint run · no writing or
deleting business data · no change to operations, chart of accounts, journal entries, balances or
the accounting engine · no `.env` change · no secret change · no moving or deleting old files.

New code may be written. Mocked and isolated tests are allowed. If a test database cannot be proven
separate from production/preview, it is not used.

---

## 5. Required final report

Exactly these fields:

```
P1_SEC_UPLOAD_STATUS =
RESET_P0_HARDENING_STATUS =
QUALITY_GATE_EPHEMERAL_UPLOAD =
PERSISTENT_LOCAL_UPLOADS_REMAINING =
SAFE_TEMP_PROCESSING_PATHS =
LEGACY_LOCAL_READ_FALLBACK =
TOKEN_IN_FILE_URL = NO
FILES_MIGRATED_NOW = 0
OLD_FILES_MIGRATION_SCRIPT =
OLD_FILES_MIGRATION_EXECUTED = NO
RESET_EXECUTED = NO
SEED_EXECUTED = NO
DB_MUTATION = NO
FINANCIAL_MUTATION = NO
ACCOUNTING_ENGINE_CHANGED = NO
ENV_CHANGED = NO
SECRETS_CHANGED = NO
DEPLOY = NO
```

Plus: before/after per finding · modified files · tests and their results · every remaining
filesystem write with its classification (safe / expected-temporary / persistent-storage-fixed /
destructive-protected / needs-review) · residual risks · any external configuration required · any
API compatibility change · count of legacy files still at risk where that can be established
read-only · the final quality-gate result.

---

## 6. Migration script for existing files

Written, `--dry-run` supported, **not executed**. Idempotent, non-destructive by default, never
deletes the original, never silently overwrites an existing object, and changes nothing in the
database during a dry run. Per file it reports source path, target object key, size, detected type,
related entity where determinable, and an action of `WOULD_UPLOAD` / `SKIP` / `CONFLICT` / `INVALID`.
Summary covers total discovered, valid, invalid, conflicts, total bytes, orphan files, and missing
database references. The real migration waits for a separate explicit authorisation.

---

## 7. Stop condition

If object storage turns out to require configuration that is genuinely absent, no value is invented
and `.env` is not touched — the achievable hardening is completed and the blocker is reported
precisely.

On completion: **stop**. No deploy. No migration of old files. Phase 2A does not start until this
report is reviewed.
