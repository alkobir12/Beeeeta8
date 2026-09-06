# Addendum — findings from read-only inspection (Part C scope correction)

Added after approval. Read-only inspection changed what Part C actually has to fix. Nothing here
alters the approved decisions in `plan.md`; it corrects the target list.

---

## 1. The reset endpoint named at approval is dead code, not a live risk

`routes_finance.py` — `DELETE /api/finance/reset-all-data` returns HTTP 410 as its **first
statement**. Every destructive line below it (the bulk deletes of `operations`,
`chart_of_accounts`, `invoices` in both Postgres and Mongo) is unreachable.

It is still dangerous: a single edit removing that 410 silently re-arms a full financial wipe, and
the block is written so the deletes run *before* the 410 that follows them. Treatment: **delete the
unreachable destructive block** so it cannot be revived by accident. The 410 response stays, so no
caller behaviour changes.

## 2. The genuinely live destructive endpoint is a different one

`DELETE /api/operations` (delete-all-operations) deletes **every operation record**. It is reachable
today. It checks role permissions and writes an audit event, but it has:

- no confirmation value of any kind
- no double confirmation
- no environment guard
- and it does **not** reverse the journal entries it leaves orphaned — so a single call desynchronises
  operations from the accounting ledger

This is the highest-severity item in the batch and receives the full fail-closed treatment agreed in
`plan.md` §2.3.

## 3. A second live mass-mutation endpoint, not on the original list

`POST /api/admin/reset-inventory` sets **every part quantity to zero and every service price to
zero**. Admin-gated, but no confirmation and no environment guard. It is not a delete, so the
scanner did not flag it, but the business effect is comparable to one — the entire price list and
stock count are wiped in a single unconfirmed request.

Proposed: same fail-closed treatment as the operations reset. Say so if it should instead be left
alone and only logged as a backlog item.

## 4. Two file-write paths are worse than the scan indicated

- `routes_references.py` builds its temporary path by joining the temp directory with the
  **client-supplied filename**, so a crafted name escapes the directory. Admin-only, but a real
  traversal escape. It is the path being converted to safe ephemeral temp under `plan.md` §1, which
  closes this.
- `routes_vehicle_files.py` writes using the client-supplied filename with **no** sanitising, size
  cap or type check — the worst pattern in the repository. It is, however, an **unregistered
  router**: nothing imports it, so the endpoint does not exist at runtime and the duplicate live
  version in `server.py` (which does sanitise, cap at 10 MB and check type) is what actually serves
  vehicle uploads. It is still brought onto the shared storage layer so the pattern stops existing,
  and it is reported as unregistered rather than claimed as a live fix.

## 5. Consequence for the report

`RESET_P0_HARDENING_STATUS` will therefore cover: one dead-code removal, two live endpoints hardened
fail-closed (operations reset, inventory reset), and an explicit statement that the endpoint named at
approval was already unreachable. Every remaining destructive call found in the sweep is listed with
its classification, whether or not it is in scope.
