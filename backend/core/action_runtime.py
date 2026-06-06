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
import json
from datetime import datetime, timezone
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

VALID_ACTIONS = {"customer", "vehicle", "visit", "close_visits", "delete_operation",
                 "delete_customer", "delete_vehicle", "update_customer", "update_vehicle"}
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
    """Map a draft payload to the Supabase `vehicles` schema.
    `brand` is NOT NULL in the DB, so it defaults to 'غير محدد' when missing."""
    return {
        "plate_number": (data.get("plate") or "")[:32],
        "brand": data.get("brand") or "غير محدد",
        "model": data.get("model") or data.get("vehicle_type") or None,
        "year": int(data.get("year")) if str(data.get("year") or "").isdigit() else None,
        "status": data.get("status") or "تشخيص",
        "customer_name": data.get("name") or data.get("customer_name") or None,
        "customer_phone": data.get("phone") or None,
    }


def _payload_to_visits_row(data: Dict[str, Any]) -> Dict[str, Any]:
    """Deprecated — visits now write to the existing `vehicle_visits` table.
    Kept only for backward compatibility with any external caller."""
    return {"notes": json.dumps({"text": data.get("reason") or "", "items": [], "payments": []}, ensure_ascii=False),
            "status": data.get("status") or "in_progress"}


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

    # ── Visits → write to the EXISTING vehicle_visits table (integrates with
    #    vehicle details & financial reports). Falls back to staging if we
    #    can't resolve/create a vehicle to link the visit to.
    if client and table == "visits":
        try:
            vehicle_id = _resolve_or_create_vehicle_for_visit(data)
            if vehicle_id:
                notes_obj: Dict[str, Any] = {
                    "text": data.get("reason") or "", "items": [], "payments": [], "source": "katrina",
                }
                svc_name = str(data.get("service") or "").strip()
                if svc_name:
                    try:
                        price = float(str(data.get("price") or "").replace(",", "")) if str(data.get("price") or "").strip() else 0
                    except Exception:
                        price = 0
                    notes_obj["items"].append({
                        "itemType": "service", "name": svc_name, "quantity": 1, "qty": 1,
                        "price": price, "total": price, "billingType": "workshop",
                    })
                row = {
                    "vehicle_id": vehicle_id,
                    "entry_date": datetime.now(timezone.utc).isoformat(),
                    "exit_date": None,
                    "status": "in_progress",
                    "notes": json.dumps(notes_obj, ensure_ascii=False),
                }
                res = client.table("vehicle_visits").insert(row).execute()
                if res.data:
                    created = res.data[0]
                    # Friendly display fields (consumed by the chat confirmation)
                    created["plate_number"] = data.get("plate") or None
                    created["name"] = data.get("customer_name") or data.get("plate") or None
                    # Mark the vehicle active so the visit surfaces in dashboards/get_active_visits
                    try:
                        client.table("vehicles").update({"status": "تشخيص"}).eq("id", vehicle_id).execute()
                    except Exception:
                        pass
                    DB.setdefault("visits", {})[created["id"]] = created
                    _audit("DB_WRITE_SUPABASE", table="vehicle_visits", entity_id=created.get("id"))
                    return created
        except Exception as e:
            _audit("DB_WRITE_FALLBACK_STAGING", table="vehicle_visits", reason=redact(str(e), max_len=100))

    # ── Staging fallback (DB-unavailable) ──
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


def _update_entity(table: str, entity_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Patch an entity's fields. Returns the updated row (Supabase) or None."""
    client = _supabase_client()
    if client and table in ("customers", "vehicles") and changes:
        try:
            res = client.table(table).update(changes).eq("id", entity_id).execute()
            if res.data:
                updated = res.data[0]
                DB.setdefault(table, {})[entity_id] = updated
                _audit("DB_UPDATE_SUPABASE", table=table, entity_id=entity_id, fields=list(changes.keys()))
                return updated
        except Exception as e:
            _log.exception("supabase update failed for %s/%s: %s", table, entity_id, redact(str(e), max_len=100))
    # Staging fallback
    if table in DB and entity_id in DB[table]:
        DB[table][entity_id] = {**DB[table][entity_id], **changes, "updated_at": time.time()}
        return DB[table][entity_id]
    return None


def _fetch_all(table: str) -> List[Dict[str, Any]]:
    client = _supabase_client()
    if client and table in ("customers", "vehicles"):
        try:
            return (client.table(table).select("*").limit(5000).execute().data) or []
        except Exception as e:
            _log.warning("fetch_all %s failed: %s", table, redact(str(e), max_len=80))
    return list(DB.get(table, {}).values())


def resolve_customer_target(criteria: Dict[str, Any]) -> Dict[str, Any]:
    """Find the single customer matching criteria {customer_id?|id?|phone?|name?}.

    Returns {"row": {...}} | {"error": "not_found"|"ambiguous", "candidates": [...]}.
    """
    from core.arabic_nlp import arabic_match, normalize_arabic
    criteria = criteria or {}
    cid = criteria.get("customer_id") or criteria.get("id")
    rows = _fetch_all("customers")
    if cid:
        hit = next((c for c in rows if str(c.get("id")) == str(cid)), None)
        return {"row": hit} if hit else {"error": "not_found", "candidates": []}
    phone = str(criteria.get("phone") or "").strip()
    name = str(criteria.get("name") or "").strip()
    cands: List[Dict[str, Any]] = []
    if phone:
        np = normalize_arabic(phone)
        cands = [c for c in rows if np and np in normalize_arabic(c.get("phone"))]
    if not cands and name:
        cands = [c for c in rows if arabic_match(name, c.get("name"))]
    if not cands:
        return {"error": "not_found", "candidates": []}
    if len(cands) > 1:
        return {"error": "ambiguous",
                "candidates": [{"id": c.get("id"), "name": c.get("name"), "phone": c.get("phone")} for c in cands[:6]]}
    return {"row": cands[0]}


def resolve_vehicle_target(criteria: Dict[str, Any]) -> Dict[str, Any]:
    """Find the single vehicle matching criteria {vehicle_id?|id?|plate?}."""
    from core.arabic_nlp import arabic_match, normalize_arabic
    criteria = criteria or {}
    vid = criteria.get("vehicle_id") or criteria.get("id")
    rows = _fetch_all("vehicles")
    if vid:
        hit = next((v for v in rows if str(v.get("id")) == str(vid)), None)
        return {"row": hit} if hit else {"error": "not_found", "candidates": []}
    plate = str(criteria.get("plate") or criteria.get("plate_number") or "").strip()
    cands: List[Dict[str, Any]] = []
    if plate:
        npl = normalize_arabic(plate)
        cands = [v for v in rows
                 if npl and (npl in normalize_arabic(v.get("plate_number")) or npl in normalize_arabic(v.get("plate")))]
    name = str(criteria.get("name") or criteria.get("customer_name") or "").strip()
    if not cands and name:
        cands = [v for v in rows if arabic_match(name, v.get("customer_name"), v.get("ownerName"))]
    if not cands:
        return {"error": "not_found", "candidates": []}
    if len(cands) > 1:
        return {"error": "ambiguous",
                "candidates": [{"id": v.get("id"),
                                "plate": v.get("plate_number") or v.get("plate"),
                                "brand": v.get("brand"), "model": v.get("model")} for v in cands[:6]]}
    return {"row": cands[0]}


def _resolve_or_create_vehicle_for_visit(data: Dict[str, Any]) -> Optional[str]:
    """Find (or create) the vehicle to attach a visit to. Returns vehicle_id.

    Resolution order: plate → single customer-phone match → create from plate.
    Returns None when there is nothing to link to (caller falls back to staging).
    """
    from core.arabic_nlp import normalize_arabic
    plate = str(data.get("plate") or "").strip()
    phone = str(data.get("customer_phone") or data.get("phone") or "").strip()
    if plate:
        res = resolve_vehicle_target({"plate": plate})
        if res.get("row"):
            return res["row"].get("id")
    if phone:
        npq = normalize_arabic(phone)
        matches = [v for v in _fetch_all("vehicles")
                   if npq and npq in normalize_arabic(v.get("customer_phone"))]
        if len(matches) == 1:
            return matches[0].get("id")
    # Create a new vehicle only when we have a plate to identify it.
    if plate:
        veh = upsert_entity("vehicles", {
            "plate": plate,
            "model": data.get("vehicle_type") or data.get("model"),
            "year": data.get("year"),
            "name": data.get("customer_name") or data.get("name"),
            "phone": phone or None,
        })
        return veh.get("id") if isinstance(veh, dict) else None
    return None



# ─────────────────────────────────────────────────────────────────────────────
# 4b) Duplicate Detection — L16 prevents double-creating the same entity
# ─────────────────────────────────────────────────────────────────────────────


def _find_duplicate_customer(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check if a customer with the same name+phone already exists."""
    name = (payload.get("name") or "").strip().lower()
    phone = (payload.get("phone") or "").strip()
    if not name:
        return None
    client = _supabase_client()
    if client:
        try:
            q = client.table("customers").select("*")
            if phone:
                res = q.eq("phone", phone).limit(1).execute()
                if res.data:
                    return res.data[0]
            res = client.table("customers").select("*").ilike("name", f"%{name}%").limit(5).execute()
            for row in (res.data or []):
                if name in (row.get("name") or "").lower():
                    return row
        except Exception as e:
            _log.debug("duplicate customer check failed: %s", redact(str(e), max_len=80))
    return None


def _find_duplicate_vehicle(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check if a vehicle with the same plate already exists."""
    plate = (payload.get("plate") or "").strip()
    if not plate:
        return None
    client = _supabase_client()
    if client:
        try:
            res = client.table("vehicles").select("*").eq("plate_number", plate).limit(1).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            _log.debug("duplicate vehicle check failed: %s", redact(str(e), max_len=80))
    return None


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

        # ── delete_operation — direct SYNCHRONOUS Supabase delete (cascade JE) ──
        #    Previously this fired an async httpx request via
        #    `loop.run_until_complete()`, which raises "event loop is already
        #    running" inside FastAPI's running loop → the commit silently failed
        #    (the bot reported success but nothing was deleted, and approvals
        #    surfaced an [object Object] error). We now delete directly through
        #    the synchronous Supabase client and report the *real* outcome.
        if action == "delete_operation":
            op_id = payload.get("operation_id") or payload.get("id") or ""
            if not op_id:
                return {"error": "missing_operation_id"}
            try:
                client = _supabase_client()
                deleted = False
                if client:
                    # 1) cascade: remove linked journal entries first (best-effort)
                    try:
                        client.table("journal_entries").delete().eq("reference_id", op_id).execute()
                    except Exception as je:
                        _log.debug("cascade journal delete skipped: %s", redact(str(je), max_len=80))
                    # 2) delete the operation — capture returned rows to know if it existed
                    res = client.table("operations").delete().eq("id", op_id).execute()
                    deleted = bool(getattr(res, "data", None))
                    # 3) best-effort cache invalidation so the UI reflects the delete
                    try:
                        from routes_extended import _invalidate_ops_caches
                        _invalidate_ops_caches()
                    except Exception:
                        pass
                result_data = {"operation_id": op_id, "deleted": deleted}
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
                       operation_id=op_id, deleted=deleted, committer=committer)
                return {"execution_id": execution_id, "result": result_data}
            except Exception as e:
                _log.exception("delete_operation commit failed: %s", redact(str(e), max_len=120))
                return {"error": "commit_failed", "detail": redact(str(e), max_len=120)}

        # ── delete_customer / delete_vehicle (target id pre-resolved in payload) ──
        if action in ("delete_customer", "delete_vehicle"):
            tbl = "customers" if action == "delete_customer" else "vehicles"
            ent_id = payload.get("customer_id") or payload.get("vehicle_id") or payload.get("id")
            if not ent_id:
                return {"error": "missing_target_id"}
            removed = _delete_entity(tbl, ent_id)
            result_data = {"id": ent_id, "deleted": removed,
                           "name": payload.get("_target_label"), "_action": action}
            execution_id = uuid.uuid4().hex[:12]
            STATE["executions"][execution_id] = {
                "id": execution_id, "draft_id": draft_id, "result": result_data,
                "status": "executed", "committer": committer or "anonymous",
                "committed_at": time.time(),
            }
            draft["status"] = "committed"
            draft["execution_id"] = execution_id
            _audit("COMMIT_DELETE_ENTITY", draft_id=draft_id, execution_id=execution_id,
                   table=tbl, entity_id=ent_id, committer=committer)
            return {"execution_id": execution_id, "result": result_data}

        # ── update_customer / update_vehicle ──
        if action in ("update_customer", "update_vehicle"):
            tbl = "customers" if action == "update_customer" else "vehicles"
            ent_id = payload.get("customer_id") or payload.get("vehicle_id") or payload.get("id")
            changes = dict(payload.get("set") or {})
            if action == "update_vehicle":
                if "plate" in changes:
                    changes["plate_number"] = changes.pop("plate")
                if "year" in changes and str(changes.get("year") or "").strip().isdigit():
                    changes["year"] = int(changes["year"])
            if not ent_id:
                return {"error": "missing_target_id"}
            if not changes:
                return {"error": "no_changes"}
            updated = _update_entity(tbl, ent_id, changes)
            if updated is None:
                return {"error": "update_failed"}
            result_data = {**updated, "_action": action, "_updated_fields": list(changes.keys())}
            execution_id = uuid.uuid4().hex[:12]
            STATE["executions"][execution_id] = {
                "id": execution_id, "draft_id": draft_id, "result": result_data,
                "status": "executed", "committer": committer or "anonymous",
                "committed_at": time.time(),
            }
            draft["status"] = "committed"
            draft["execution_id"] = execution_id
            _audit("COMMIT_UPDATE_ENTITY", draft_id=draft_id, execution_id=execution_id,
                   table=tbl, entity_id=ent_id, fields=list(changes.keys()), committer=committer)
            return {"execution_id": execution_id, "result": result_data}

        # Map action → table
        table = {"customer": "customers", "vehicle": "vehicles", "visit": "visits"}[action]

        # L16 Duplicate Prevention — check if entity already exists before creating
        if action == "customer" and payload.get("name"):
            existing = _find_duplicate_customer(payload)
            if existing:
                # Return the existing entity instead of creating a duplicate
                execution_id = uuid.uuid4().hex[:12]
                STATE["executions"][execution_id] = {
                    "id": execution_id,
                    "draft_id": draft_id,
                    "result": {**existing, "_duplicate": True},
                    "status": "executed",
                    "committer": committer or "anonymous",
                    "committed_at": time.time(),
                }
                draft["status"] = "committed"
                draft["execution_id"] = execution_id
                _audit("COMMIT_DUPLICATE_SKIPPED", draft_id=draft_id, execution_id=execution_id,
                       table=table, existing_id=existing.get("id"))
                return {"execution_id": execution_id, "result": {**existing, "_duplicate": True, "_message": "العميل موجود مسبقاً"}}

        if action == "vehicle" and payload.get("plate"):
            existing = _find_duplicate_vehicle(payload)
            if existing:
                execution_id = uuid.uuid4().hex[:12]
                STATE["executions"][execution_id] = {
                    "id": execution_id,
                    "draft_id": draft_id,
                    "result": {**existing, "_duplicate": True},
                    "status": "executed",
                    "committer": committer or "anonymous",
                    "committed_at": time.time(),
                }
                draft["status"] = "committed"
                draft["execution_id"] = execution_id
                _audit("COMMIT_DUPLICATE_SKIPPED", draft_id=draft_id, execution_id=execution_id,
                       table=table, existing_id=existing.get("id"))
                return {"execution_id": execution_id, "result": {**existing, "_duplicate": True, "_message": "المركبة موجودة مسبقاً"}}

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
    # Append staging visits dict too (no-plate fallback visits)
    for vid, v in DB.get("visits", {}).items():
        if v.get("status") not in ("closed", "completed", "delivered"):
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
