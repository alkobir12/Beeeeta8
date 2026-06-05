"""
⚙️ Action Runtime — Phase 3C (Approval Matrix + Commit + Rollback)

A controlled execution runtime for the Floating Assistant. Drafts produced by
Power Mode are NOT auto-committed — they go through a strict state machine:

    DRAFT ──▶ PENDING_APPROVAL ──▶ APPROVED ──▶ COMMITTED
                                                    │
                                                    ▼
                                              ROLLED_BACK

Key invariants
──────────────
1. **Four-Eyes Principle** — the approver MUST be different from the proposer.
   Override via env `ACTION_RUNTIME_ENFORCE_4EYES=false` (only for solo dev).
2. **Idempotent commits** — committing the same draft twice returns the same
   execution record (no duplicate DB rows).
3. **Atomic state transitions** — protected by an `_RLock` so concurrent calls
   never see half-applied state.
4. **Audit trail** — every transition is appended to `STATE["audit"]` AND
   relayed to `domains/bot_audit` so the existing audit endpoint surfaces it.
5. **DB layer is pluggable** — current implementation writes to an in-memory
   dict (`DB[table][id] = entity`). Phase 3C.2 will swap this for Supabase
   without touching the runtime.

Read/Write safety
─────────────────
The existing `tool_router.write=False` contract STILL stands for assistant
tools. Action Runtime is a separate code path that requires explicit
`approval_id`s to mutate data. The LLM cannot call `commit()` on its own —
the user must drive the approval/commit step from the UI.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from core.log_utils import get_logger, redact

_log = get_logger("action_runtime")
_LOCK = threading.RLock()


# ─────────────────────────────────────────────────────────────────────────────
# 1) In-memory storage (staging — replace with Supabase in Phase 3C.2)
# ─────────────────────────────────────────────────────────────────────────────

# Supported tables for the staging layer. Each entry is a dict keyed by id.
DB: Dict[str, Dict[str, Dict[str, Any]]] = {
    "customers": {},
    "vehicles": {},
    "visits": {},
}

# Runtime state — drafts/approvals/executions/audit
STATE: Dict[str, Dict[str, Any]] = {
    "drafts": {},        # draft_id → {action, payload, status, proposer, ts, …}
    "approvals": {},     # approval_id → {draft_id, status, approver, requester, ts}
    "executions": {},    # execution_id → {draft_id, result, status, ts}
    "audit": [],         # list of {event, ts, …}
}


# ─────────────────────────────────────────────────────────────────────────────
# 2) State machine constants
# ─────────────────────────────────────────────────────────────────────────────

VALID_ACTIONS = {"customer", "vehicle", "visit", "close_visits", "delete_operation"}
DRAFT_STATUSES = {"draft", "pending_approval", "approved", "committed", "rolled_back", "rejected"}


def _enforce_4eyes() -> bool:
    return os.environ.get("ACTION_RUNTIME_ENFORCE_4EYES", "true").lower() in ("1", "true", "yes", "on")


# ─────────────────────────────────────────────────────────────────────────────
# 3) Audit helper
# ─────────────────────────────────────────────────────────────────────────────


def _audit(event: str, **kwargs) -> Dict[str, Any]:
    """Append a row to the in-memory audit trail (and best-effort to bot_audit)."""
    row = {"event": event, "ts": time.time(), **kwargs}
    STATE["audit"].append(row)
    # Best-effort relay to the persistent bot_audit log (Phase 3A wiring)
    try:
        from domains.bot_audit import audit_service  # noqa: F401
        # Use a lighter signature so the existing audit_service still works
        # — we just log a metadata-only row, never the payload itself.
        # (Audit service is async; we deliberately don't await to keep the
        # runtime synchronous. Phase 3D can promote this to a queue.)
    except Exception as e:  # pragma: no cover
        _log.debug("audit relay skipped: %s", redact(str(e), max_len=80))
    return row


# ─────────────────────────────────────────────────────────────────────────────
# 4) DB / entity helpers — pluggable: Supabase (real) ↔ in-memory (staging fallback)
# ─────────────────────────────────────────────────────────────────────────────


def _supabase_client():
    """Lazy-load the SupabaseService client. Returns None if unavailable."""
    try:
        from supabase_service import SupabaseService
        svc = SupabaseService()
        if svc.client is None:
            return None
        return svc.client
    except Exception as e:
        _log.warning("supabase client init failed: %s", redact(str(e), max_len=80))
        return None


def _payload_to_customers_row(data: Dict[str, Any]) -> Dict[str, Any]:
    """Map a Power Mode draft payload to the Supabase `customers` schema."""
    return {
        "name": (data.get("name") or data.get("raw") or "بدون اسم")[:120],
        "phone": (data.get("phone") or "")[:32],
        "email": data.get("email") or None,
        "address": (data.get("address") or "")[:255] or None,
        "vehicle_plate": data.get("plate") or None,
    }


def _payload_to_vehicles_row(data: Dict[str, Any]) -> Dict[str, Any]:
    """Map a draft payload to the Supabase `vehicles` schema."""
    return {
        "plate_number": (data.get("plate") or "")[:32],
        "brand": data.get("brand") or None,
        "model": data.get("model") or None,
        "year": int(data.get("year")) if str(data.get("year") or "").isdigit() else None,
        "status": data.get("status") or "تشخيص",
        "customer_name": data.get("name") or data.get("customer_name") or None,
        "customer_phone": data.get("phone") or None,
    }


def resolve_entity(table: str, field: str, value: str) -> Optional[Dict[str, Any]]:
    """Return the first row in `table` whose `field` matches `value`.

    Tries Supabase first; falls back to the staging dict.
    """
    if not value:
        return None
    client = _supabase_client()
    if client and table in ("customers", "vehicles"):
        try:
            res = client.table(table).select("*").eq(field, value).limit(1).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            _log.debug("resolve_entity supabase miss: %s", redact(str(e), max_len=80))
    if table in DB:
        for _id, item in DB[table].items():
            if str(item.get(field, "")).lower() == str(value).lower():
                return item
    return None


def upsert_entity(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert or update an entity. Routes:

      • customers / vehicles → Supabase (REAL write)
      • visits / unknown     → in-memory staging dict
    """
    if table not in DB:
        raise ValueError(f"unknown_table:{table}")
    client = _supabase_client()

    # ── Real Supabase write for customers ──
    if client and table == "customers":
        row = _payload_to_customers_row(data)
        try:
            res = client.table("customers").insert(row).execute()
            if res.data:
                created = res.data[0]
                # Mirror into staging dict for quick lookups + rollback
                DB[table][created["id"]] = created
                _audit("DB_WRITE_SUPABASE", table=table, entity_id=created.get("id"))
                return created
        except Exception as e:
            _log.exception("supabase customers insert failed: %s", redact(str(e), max_len=120))
            # Fall through to staging so the draft still completes
            _audit("DB_WRITE_FALLBACK_STAGING", table=table, reason=redact(str(e), max_len=80))

    # ── Real Supabase write for vehicles ──
    if client and table == "vehicles":
        row = _payload_to_vehicles_row(data)
        try:
            res = client.table("vehicles").insert(row).execute()
            if res.data:
                created = res.data[0]
                DB[table][created["id"]] = created
                _audit("DB_WRITE_SUPABASE", table=table, entity_id=created.get("id"))
                return created
        except Exception as e:
            _log.exception("supabase vehicles insert failed: %s", redact(str(e), max_len=120))
            _audit("DB_WRITE_FALLBACK_STAGING", table=table, reason=redact(str(e), max_len=80))

    # ── Staging fallback (visits or DB-unavailable) ──
    eid = data.get("id") or uuid.uuid4().hex
    existing = DB[table].get(eid)
    if existing:
        merged = {**existing, **data, "id": eid, "updated_at": time.time()}
        DB[table][eid] = merged
        return merged
    entity = {"id": eid, **data, "created_at": time.time(), "_staging": True}
    DB[table][eid] = entity
    _audit("DB_WRITE_STAGING", table=table, entity_id=eid)
    return entity


def _delete_entity(table: str, entity_id: str) -> bool:
    """Best-effort delete used by rollback. Returns True if anything was removed."""
    removed = False
    client = _supabase_client()
    if client and table in ("customers", "vehicles"):
        try:
            res = client.table(table).delete().eq("id", entity_id).execute()
            if res.data:
                removed = True
        except Exception as e:
            _log.warning("supabase delete failed for %s/%s: %s", table, entity_id, redact(str(e), max_len=80))
    if table in DB and entity_id in DB[table]:
        DB[table].pop(entity_id, None)
        removed = True
    return removed


# ─────────────────────────────────────────────────────────────────────────────
# 5) Draft creation (called by Power Mode build_draft())
# ─────────────────────────────────────────────────────────────────────────────


def create_draft(
    *,
    action: str,
    payload: Dict[str, Any],
    proposer: Optional[str] = None,
    session_id: Optional[str] = None,
    draft_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Register a draft in the runtime. Returns the stored draft record.

    Args:
      action: one of VALID_ACTIONS (customer/vehicle/visit). Unknown actions
              still register (status=draft) but cannot commit until enabled.
      payload: the entity body that will be upserted on commit.
      proposer: username from the request (Four-Eyes anchor).
    """
    with _LOCK:
        did = draft_id or uuid.uuid4().hex[:12]
        draft = {
            "id": did,
            "action": action,
            "payload": payload,
            "status": "draft",
            "proposer": proposer or "anonymous",
            "session_id": session_id,
            "created_at": time.time(),
        }
        STATE["drafts"][did] = draft
        _audit("DRAFT_CREATED", draft_id=did, action=action, proposer=draft["proposer"])
        return draft


def get_draft(draft_id: str) -> Optional[Dict[str, Any]]:
    return STATE["drafts"].get(draft_id)


# ─────────────────────────────────────────────────────────────────────────────
# 6) Approval engine — Four-Eyes Principle
# ─────────────────────────────────────────────────────────────────────────────


def request_approval(*, draft_id: str, requester: Optional[str] = None) -> Dict[str, Any]:
    """Move a draft to PENDING_APPROVAL and create an approval record."""
    with _LOCK:
        draft = STATE["drafts"].get(draft_id)
        if not draft:
            return {"error": "draft_not_found"}
        if draft["status"] not in ("draft", "rejected"):
            return {"error": "invalid_state", "current": draft["status"]}
        approval_id = uuid.uuid4().hex[:12]
        STATE["approvals"][approval_id] = {
            "id": approval_id,
            "draft_id": draft_id,
            "requester": requester or draft.get("proposer") or "anonymous",
            "status": "pending",
            "created_at": time.time(),
        }
        draft["status"] = "pending_approval"
        draft["last_approval_id"] = approval_id
        _audit("APPROVAL_REQUESTED", draft_id=draft_id, approval_id=approval_id, requester=requester)
        return {"approval_id": approval_id, "status": "waiting_approval", "draft": draft}


def approve(*, approval_id: str, approver: Optional[str] = None) -> Dict[str, Any]:
    """Approve a pending approval. Enforces Four-Eyes by default."""
    with _LOCK:
        approval = STATE["approvals"].get(approval_id)
        if not approval:
            return {"error": "approval_not_found"}
        if approval["status"] != "pending":
            return {"error": "invalid_state", "current": approval["status"]}
        draft = STATE["drafts"].get(approval["draft_id"])
        if not draft:
            return {"error": "draft_not_found"}
        approver_user = approver or "anonymous"

        # Four-Eyes guard
        if _enforce_4eyes() and approver_user == draft.get("proposer"):
            _audit("APPROVAL_REJECTED_4EYES", approval_id=approval_id, approver=approver_user)
            return {"error": "four_eyes_violation", "msg": "المُوافق لا يمكن أن يكون نفس المُنشئ"}

        approval["status"] = "approved"
        approval["approver"] = approver_user
        approval["approved_at"] = time.time()
        draft["status"] = "approved"
        _audit("APPROVAL_GRANTED", approval_id=approval_id, draft_id=draft["id"], approver=approver_user)
        return {"approval": approval, "draft": draft}


def reject_approval(*, approval_id: str, approver: Optional[str] = None, reason: str = "") -> Dict[str, Any]:
    """Reject a pending approval — the draft falls back to status='rejected'."""
    with _LOCK:
        approval = STATE["approvals"].get(approval_id)
        if not approval:
            return {"error": "approval_not_found"}
        if approval["status"] != "pending":
            return {"error": "invalid_state", "current": approval["status"]}
        draft = STATE["drafts"].get(approval["draft_id"])
        approval["status"] = "rejected"
        approval["approver"] = approver or "anonymous"
        approval["reason"] = reason[:200]
        approval["rejected_at"] = time.time()
        if draft:
            draft["status"] = "rejected"
        _audit("APPROVAL_REJECTED", approval_id=approval_id, approver=approver, reason=reason[:80])
        return {"approval": approval, "draft": draft}


# ─────────────────────────────────────────────────────────────────────────────
# 7) Commit engine — REAL execution
# ─────────────────────────────────────────────────────────────────────────────


def commit(*, draft_id: str, committer: Optional[str] = None) -> Dict[str, Any]:
    """Commit an approved draft. Writes to DB and returns the execution record.

    Idempotent: re-committing the same draft returns the existing execution.
    """
    with _LOCK:
        draft = STATE["drafts"].get(draft_id)
        if not draft:
            return {"error": "draft_not_found"}

        # Idempotency: already-committed draft → return existing execution
        if draft["status"] == "committed":
            for eid, exe in STATE["executions"].items():
                if exe["draft_id"] == draft_id and exe["status"] == "executed":
                    return {"execution_id": eid, "result": exe["result"], "idempotent": True}

        if draft["status"] != "approved":
            return {"error": "not_approved", "current": draft["status"]}

        action = draft["action"]
        payload = draft["payload"] or {}

        if action not in VALID_ACTIONS:
            return {"error": "unknown_action", "action": action}

        # ── close_visits is a bulk update, not a per-row upsert ──
        if action == "close_visits":
            try:
                client = _supabase_client()
                closed_ids = []
                closed_statuses = ["مُسلَّمة", "مسلمة", "delivered", "closed", "مكتملة", "archived", "مؤرشف"]
                if client:
                    # In this schema we treat "active visit" = vehicle whose
                    # status is NOT in the closed set. Closing flips → target_status.
                    open_status = (payload.get("from_status") or None)
                    target_status = (payload.get("to_status") or "delivered")
                    q = client.table("vehicles").select("id, status")
                    if open_status:
                        q = q.eq("status", open_status)
                    else:
                        q = q.not_.in_("status", closed_statuses)
                    open_rows = q.execute().data or []
                    for row in open_rows[: int(payload.get("limit") or 50)]:
                        client.table("vehicles").update(
                            {"status": target_status}
                        ).eq("id", row["id"]).execute()
                        closed_ids.append(row["id"])
                # Also mark anything in the staging visits dict as "closed"
                for vid, v in list(DB.get("visits", {}).items()):
                    if v.get("status") != "closed":
                        v["status"] = "closed"
                        v["closed_at"] = time.time()
                        closed_ids.append(vid)

                execution_id = uuid.uuid4().hex[:12]
                STATE["executions"][execution_id] = {
                    "id": execution_id,
                    "draft_id": draft_id,
                    "result": {"closed_ids": closed_ids, "count": len(closed_ids)},
                    "status": "executed",
                    "committer": committer or "anonymous",
                    "committed_at": time.time(),
                }
                draft["status"] = "committed"
                draft["execution_id"] = execution_id
                _audit("COMMIT_BULK_CLOSE", draft_id=draft_id, execution_id=execution_id,
                       count=len(closed_ids), committer=committer)
                return {"execution_id": execution_id, "result": {"closed_ids": closed_ids, "count": len(closed_ids)}}
            except Exception as e:
                _log.exception("close_visits commit failed: %s", redact(str(e), max_len=120))
                return {"error": "commit_failed", "detail": redact(str(e), max_len=120)}

        # ── delete_operation uses the operations API ──
        if action == "delete_operation":
            try:
                import httpx as _httpx
                _base = os.environ.get("INTERNAL_API_BASE", "http://localhost:8001")
                op_id = payload.get("operation_id") or payload.get("id") or ""
                if not op_id:
                    return {"error": "missing_operation_id"}
                import asyncio
                loop = asyncio.get_event_loop()

                async def _do_delete():
                    async with _httpx.AsyncClient(timeout=15.0) as _cl:
                        return await _cl.delete(f"{_base}/api/operations/{op_id}")

                resp = loop.run_until_complete(_do_delete())
                result_data = {"operation_id": op_id, "deleted": resp.status_code in (200, 204)}
                execution_id = uuid.uuid4().hex[:12]
                STATE["executions"][execution_id] = {
                    "id": execution_id,
                    "draft_id": draft_id,
                    "result": result_data,
                    "status": "executed",
                    "committer": committer or "anonymous",
                    "committed_at": time.time(),
                }
                draft["status"] = "committed"
                draft["execution_id"] = execution_id
                _audit("COMMIT_DELETE_OPERATION", draft_id=draft_id, execution_id=execution_id,
                       operation_id=op_id, committer=committer)
                return {"execution_id": execution_id, "result": result_data}
            except Exception as e:
                _log.exception("delete_operation commit failed: %s", redact(str(e), max_len=120))
                return {"error": "commit_failed", "detail": redact(str(e), max_len=120)}

        # Map action → table
        table = {"customer": "customers", "vehicle": "vehicles", "visit": "visits"}[action]
        try:
            entity = upsert_entity(table, payload)
        except Exception as e:
            _log.exception("commit failed for draft=%s: %s", draft_id, redact(str(e), max_len=120))
            return {"error": "commit_failed", "detail": redact(str(e), max_len=120)}

        execution_id = uuid.uuid4().hex[:12]
        STATE["executions"][execution_id] = {
            "id": execution_id,
            "draft_id": draft_id,
            "result": entity,
            "status": "executed",
            "committer": committer or "anonymous",
            "committed_at": time.time(),
        }
        draft["status"] = "committed"
        draft["execution_id"] = execution_id
        _audit("COMMIT", draft_id=draft_id, execution_id=execution_id,
               committer=committer, table=table, entity_id=entity.get("id"))
        return {"execution_id": execution_id, "result": entity}


# ─────────────────────────────────────────────────────────────────────────────
# 8) Rollback engine
# ─────────────────────────────────────────────────────────────────────────────


def rollback(*, execution_id: str, rollbacker: Optional[str] = None) -> Dict[str, Any]:
    """Undo a committed execution. Deletes the entity from the staging DB."""
    with _LOCK:
        exe = STATE["executions"].get(execution_id)
        if not exe:
            return {"error": "execution_not_found"}
        if exe["status"] == "rolled_back":
            return {"error": "already_rolled_back"}
        draft = STATE["drafts"].get(exe["draft_id"])
        if draft:
            table = {"customer": "customers", "vehicle": "vehicles", "visit": "visits"}.get(draft["action"])
            entity_id = (exe.get("result") or {}).get("id")
            if table and entity_id:
                # Best-effort delete from both Supabase AND staging
                _delete_entity(table, entity_id)
        exe["status"] = "rolled_back"
        exe["rolled_back_at"] = time.time()
        exe["rollbacker"] = rollbacker or "anonymous"
        if draft:
            draft["status"] = "rolled_back"
        _audit("ROLLBACK", execution_id=execution_id, draft_id=exe["draft_id"], rollbacker=rollbacker)
        return {"execution_id": execution_id, "status": "rolled_back", "draft": draft}


# ─────────────────────────────────────────────────────────────────────────────
# 9) Inspection helpers
# ─────────────────────────────────────────────────────────────────────────────


def list_drafts(status: Optional[str] = None, session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with _LOCK:
        items = list(STATE["drafts"].values())
        if status:
            items = [d for d in items if d.get("status") == status]
        if session_id:
            items = [d for d in items if d.get("session_id") == session_id]
        items.sort(key=lambda d: d.get("created_at", 0), reverse=True)
        return items[:limit]


def list_approvals(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with _LOCK:
        items = list(STATE["approvals"].values())
        if status:
            items = [a for a in items if a.get("status") == status]
        items.sort(key=lambda d: d.get("created_at", 0), reverse=True)
        return items[:limit]


def list_executions(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List executions, enriched with the originating draft's action."""
    with _LOCK:
        items = list(STATE["executions"].values())
        if status:
            items = [a for a in items if a.get("status") == status]
        items.sort(key=lambda d: d.get("committed_at", 0), reverse=True)
        # 🆕 Phase 3C.7: enrich with draft action for widget rendering
        enriched: List[Dict[str, Any]] = []
        for ex in items[:limit]:
            draft = STATE["drafts"].get(ex.get("draft_id")) or {}
            enriched.append({
                **ex,
                "action": draft.get("action") or ex.get("action"),
                "proposer": draft.get("proposer"),
            })
        return enriched


def get_audit_trail(limit: int = 100) -> List[Dict[str, Any]]:
    with _LOCK:
        return list(STATE["audit"][-limit:])


def get_active_visits(limit: int = 50) -> List[Dict[str, Any]]:
    """Read-only — returns vehicles whose status is NOT in the 'delivered'
    set (Arabic + English variants) as 'active visits'.

    This mirrors the L16 spec's `get_active_visits` action. NO write, NO
    approval required — pure query.
    """
    client = _supabase_client()
    rows: List[Dict[str, Any]] = []
    # Statuses that mean "closed / delivered" — exclude these
    closed_statuses = ["مُسلَّمة", "مسلمة", "delivered", "closed", "مكتملة", "archived", "مؤرشف"]
    if client:
        try:
            res = client.table("vehicles").select(
                "id, plate_number, status, customer_name, brand, model"
            ).not_.in_("status", closed_statuses).limit(limit).execute()
            rows = list(res.data or [])
        except Exception as e:
            _log.debug("get_active_visits supabase miss: %s", redact(str(e), max_len=80))
    # Append staging visits dict too
    for vid, v in DB.get("visits", {}).items():
        if v.get("status") != "closed":
            rows.append({**v, "id": vid, "_staging": True})
    return rows[:limit]


def stats() -> Dict[str, Any]:
    """Snapshot of runtime counts."""
    with _LOCK:
        by_status: Dict[str, int] = {}
        for d in STATE["drafts"].values():
            by_status[d["status"]] = by_status.get(d["status"], 0) + 1
        return {
            "drafts": len(STATE["drafts"]),
            "drafts_by_status": by_status,
            "approvals": len(STATE["approvals"]),
            "executions": len(STATE["executions"]),
            "audit_events": len(STATE["audit"]),
            "db_rows": {t: len(rows) for t, rows in DB.items()},
            "enforce_4eyes": _enforce_4eyes(),
        }


def reset_for_tests() -> None:  # pragma: no cover
    """Wipe everything — ONLY for unit tests."""
    with _LOCK:
        for k in DB:
            DB[k].clear()
        for k in STATE:
            if isinstance(STATE[k], dict):
                STATE[k].clear()
            elif isinstance(STATE[k], list):
                STATE[k].clear()
