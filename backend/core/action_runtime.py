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

VALID_ACTIONS = {"customer", "vehicle", "visit", "supplier", "close_visits", "delete_operation",
                 "delete_customer", "delete_vehicle", "update_customer", "update_vehicle",
                 "invoice", "payment", "expense", "reverse", "purchase"}
DRAFT_STATUSES = {"draft", "pending_approval", "approved", "committed", "rolled_back", "rejected"}


def _enforce_4eyes() -> bool:
    return os.environ.get("ACTION_RUNTIME_ENFORCE_4EYES", "true").lower() in ("1", "true", "yes", "on")


# ─────────────────────────────────────────────────────────────────────────────
# 3) Audit helper
# ─────────────────────────────────────────────────────────────────────────────


def _audit(event: str, **kwargs) -> Dict[str, Any]:
    """Append a row to the audit trail AND persist state to MongoDB.

    Every state transition in this module funnels through `_audit` right before
    returning, so this is the single hook for durable persistence: the audit row
    is appended to MongoDB, and any draft/approval/execution referenced by id in
    the kwargs is upserted (write-through). Falls back to in-memory if MongoDB is
    unavailable.
    """
    row = {"event": event, "ts": time.time(), **kwargs}
    STATE["audit"].append(row)
    try:
        from core import runtime_store
        runtime_store.append_audit(row)
        if kwargs.get("draft_id"):
            runtime_store.save_draft(STATE, kwargs["draft_id"])
        if kwargs.get("approval_id"):
            runtime_store.save_approval(STATE, kwargs["approval_id"])
        if kwargs.get("execution_id"):
            runtime_store.save_execution(STATE, kwargs["execution_id"])
    except Exception as e:  # pragma: no cover
        _log.debug("runtime persist skipped: %s", redact(str(e), max_len=80))
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
            # 🧾 أنشئ/اربط سجل العميل الحقيقي أيضاً (وليس فقط اسمه على المركبة)
            cust_name = str(data.get("customer_name") or data.get("name") or "").strip()
            cust_phone = str(data.get("customer_phone") or data.get("phone") or "").strip()
            if cust_name:
                found = resolve_customer_target({"name": cust_name, "phone": cust_phone or None})
                if not found.get("row"):
                    try:
                        upsert_entity("customers", {"name": cust_name, "phone": cust_phone or None})
                    except Exception:
                        pass
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


def _upsert_parts_from_purchase(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """يرفع كميات القطع بعد اعتماد الشراء (best-effort).

    - إن كان لبند `matched_id` → يزيد `quantity` للسجل الحالي.
    - وإلا → يُنشئ سجلاً جديداً في جدول `parts` بالكمية والسعر المشترى.
    الإخفاق (اتصال، جدول غير موجود...) لا يوقف الترحيل — يُسجَّل تحذيراً.
    """
    result = {"restocked": 0, "created": 0, "skipped": 0}
    client = _supabase_client()
    if not client:
        result["skipped"] = len(items or [])
        return result
    for it in (items or []):
        try:
            qty = int(float(it.get("qty") or it.get("quantity") or 1))
            name = str(it.get("name") or "").strip()
            price = float(it.get("price") or 0)
            mid = it.get("matched_id")
            if mid:
                row = (client.table("parts").select("id, quantity").eq("id", mid)
                       .limit(1).execute().data or [None])[0]
                if row:
                    new_q = int(row.get("quantity") or 0) + qty
                    client.table("parts").update({
                        "quantity": new_q,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", mid).execute()
                    result["restocked"] += 1
                    continue
            # إنشاء صنف جديد إذا لا يوجد مطابقة
            if name:
                client.table("parts").insert({
                    "id": str(uuid.uuid4()),
                    "name": name[:120],
                    "quantity": qty,
                    "price": price,
                    "min_stock": 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
                result["created"] += 1
            else:
                result["skipped"] += 1
        except Exception as _e:
            _log.debug("part upsert failed for %s: %s",
                       redact(str(it.get('name')), max_len=40),
                       redact(str(_e), max_len=80))
            result["skipped"] += 1
    return result




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
            "brand": data.get("brand"),
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


def patch_draft(
    *,
    draft_id: str,
    ops: List[Dict[str, Any]],
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    """🛠️ يعدّل payload لمسودة معلّقة قبل الاعتماد (المرحلة 2).

    العمليات المدعومة:
      • {"op":"set_payment_method","value":"cash|transfer|credit"}
      • {"op":"set_vat_mode","value":"none|excluded|included","rate":0.15?}
      • {"op":"add_item","item":{"name":..,"price":..,"qty":..}}
      • {"op":"remove_item","index":0}
      • {"op":"set_supplier_name","name":"..."}
      • {"op":"set_supplier_id","id":"..."}  (بعد اعتماد إضافة المورد يُثبّت is_new=False)

    قيود:
      - المسودة لا بد أن تكون في حالة (`draft`|`pending_approval`) — بعد الاعتماد/الالتزام
        يُرفض التعديل كامل الاحتراز (No hard edit after commit).
      - كل تعديل ماليّ يُعيد تشغيل الـ resolver ليُحدّث `_echo` و`_assumptions`.
    """
    if not ops:
        return {"error": "no_ops"}
    with _LOCK:
        draft = STATE["drafts"].get(draft_id)
        if not draft:
            return {"error": "draft_not_found"}
        if draft["status"] not in ("draft", "pending_approval"):
            return {"error": "immutable_state", "current": draft["status"]}
        if draft.get("action") != "purchase":
            return {"error": "unsupported_action", "action": draft.get("action")}

        payload = dict(draft.get("payload") or {})
        supplier = payload.get("supplier")
        if not isinstance(supplier, dict):
            supplier = {"name": str(supplier or "").strip() or None,
                        "is_new": False, "id": None}
        items = list(payload.get("items") or [])
        vat = dict(payload.get("vat") or {"mode": "none", "rate": 0.15, "inclusive": False})

        applied: List[str] = []
        for op in ops:
            name = str((op or {}).get("op") or "").strip()
            if name == "set_payment_method":
                v = str(op.get("value") or "").strip().lower()
                if v not in ("cash", "transfer", "credit", "bank", "آجل", "تحويل", "نقدي"):
                    return {"error": "invalid_payment_method", "value": v}
                # normalize dialects
                v = {"آجل": "credit", "تحويل": "transfer", "نقدي": "cash", "bank": "transfer"}.get(v, v)
                payload["payment_method"] = v
                applied.append(f"payment_method={v}")
            elif name == "set_vat_mode":
                mode = str(op.get("value") or "none").strip().lower()
                if mode not in ("none", "excluded", "included"):
                    return {"error": "invalid_vat_mode", "value": mode}
                vat["mode"] = mode
                if op.get("rate") is not None:
                    try:
                        vat["rate"] = float(op["rate"])
                    except (TypeError, ValueError):
                        pass
                payload["vat"] = vat
                applied.append(f"vat_mode={mode}")
            elif name == "add_item":
                it = op.get("item") or {}
                if not it.get("name"):
                    return {"error": "invalid_item", "detail": "name is required"}
                items.append({
                    "name": str(it["name"]).strip()[:120],
                    "price": float(it.get("price") or 0),
                    "qty": float(it.get("qty") or it.get("quantity") or 1),
                    "matched_id": it.get("matched_id"),
                })
                payload["items"] = items
                applied.append(f"item_added:{items[-1]['name']}")
            elif name == "remove_item":
                if "index" not in op:
                    return {"error": "index_required"}
                try:
                    idx = int(op["index"])
                except (TypeError, ValueError):
                    return {"error": "invalid_index", "value": op.get("index")}
                if idx < 0 or idx >= len(items):
                    return {"error": "index_out_of_range", "index": idx}
                removed = items.pop(idx)
                payload["items"] = items
                applied.append(f"item_removed:{removed.get('name')}")
            elif name == "set_supplier_name":
                supplier["name"] = str(op.get("name") or "").strip() or None
                payload["supplier"] = supplier
                applied.append(f"supplier_name={supplier['name']}")
            elif name == "set_supplier_id":
                supplier["id"] = op.get("id")
                supplier["is_new"] = False
                payload["supplier"] = supplier
                applied.append(f"supplier_id={supplier['id']}")
            else:
                return {"error": "unknown_op", "op": name}

        # إعادة تشغيل الـ resolver لتحديث _echo + _assumptions
        try:
            from core.unified_executor import _resolve_purchase_target
            res = _resolve_purchase_target(payload)
        except Exception as e:
            _log.warning("resolver failed after patch: %s", redact(str(e), max_len=100))
            res = None
        if res and "error" not in res:
            enrich = res.get("enrich") or {}
            payload.update({k: v for k, v in enrich.items() if k.startswith("_") or k in ("supplier", "items", "payment_method", "vat")})

        draft["payload"] = payload
        draft["patched_at"] = time.time()
        _audit("DRAFT_PATCHED", draft_id=draft_id, ops=applied, actor=actor)
        try:
            from core import runtime_store
            runtime_store.save_draft(STATE, draft_id)
        except Exception:
            pass
        return {"draft": draft, "applied": applied}


# ─────────────────────────────────────────────────────────────────────────────
# 5b) Draft creation (called by Power Mode build_draft())
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
            return {"error": "four_eyes_violation",
                    "msg": "مبدأ الأربع أعين: لا يمكن للمُنشئ اعتماد إجراءه بنفسه — يلزم مستخدم آخر مخوّل للاعتماد"}

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
        _audit("APPROVAL_REJECTED", approval_id=approval_id, draft_id=(draft or {}).get("id"),
               approver=approver, reason=reason[:80])
        return {"approval": approval, "draft": draft}


# ─────────────────────────────────────────────────────────────────────────────
# 7) Commit engine — REAL execution
# ─────────────────────────────────────────────────────────────────────────────


def _commit_sale_operation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """🏦 إنشاء عملية بيع/خدمة كاملة عبر نفس مسار الواجهة.

    تُنشئ: عميل (إن لزم) + مركبة (إن وُجدت لوحة) + عملية (operations) + قيد محاسبي.
    فتظهر فوراً في: العمليات، لوحة التحكم، مركز التحكم المالي، والذمم.

    ⚠️ كل الأرقام حتمية من إدخال المستخدم — لا حساب/توليد من الذكاء الاصطناعي.
    """
    from supabase_service import SupabaseService
    supa = SupabaseService()

    customer_name = str(payload.get("customer") or payload.get("customer_name")
                        or payload.get("partner_name") or "").strip()
    phone = str(payload.get("customer_phone") or payload.get("phone") or "").strip()
    plate = str(payload.get("plate") or payload.get("plate_number") or "").strip()
    vehicle_model = str(payload.get("vehicle_type") or payload.get("model")
                        or payload.get("vehicle_model") or "").strip()
    service = str(payload.get("service") or payload.get("item") or "").strip()
    if not service:
        for it in (payload.get("items") or []):
            n = str((it or {}).get("name") or (it or {}).get("description") or "").strip()
            if n:
                service = n
                break
    service = service or "خدمة"
    payment_method = str(payload.get("payment_method") or "credit").strip().lower()
    is_cash = payment_method in ("cash", "نقدي", "فوري", "كاش", "نقدا", "نقداً")

    try:
        total = round(float(str(payload.get("total") or payload.get("amount")
                                or payload.get("price") or 0).replace(",", "")), 2)
    except (ValueError, TypeError):
        total = 0.0
    if total <= 0:
        return {"error": "invalid_amount"}

    # ── resolve/create customer (credit requires a named customer) ──
    partner_id = None
    if customer_name:
        found = resolve_customer_target({"name": customer_name, "phone": phone or None})
        if found.get("row"):
            partner_id = found["row"].get("id")
            customer_name = found["row"].get("name") or customer_name
        else:
            cust = upsert_entity("customers", {"name": customer_name, "phone": phone or None})
            if isinstance(cust, dict):
                partner_id = cust.get("id")
                customer_name = cust.get("name") or customer_name
    elif is_cash:
        customer_name = "عميل نقدي"
    else:
        return {"error": "missing_customer"}

    # ── resolve/create vehicle when a plate is given ──
    vehicle_id = None
    if plate:
        vfound = resolve_vehicle_target({"plate": plate})
        if vfound.get("row"):
            vehicle_id = vfound["row"].get("id")
        else:
            veh = upsert_entity("vehicles", {
                "plate": plate, "model": vehicle_model or None,
                "name": customer_name, "phone": phone or None,
            })
            if isinstance(veh, dict):
                vehicle_id = veh.get("id")

    workshop_id = payload.get("workshop_id") or payload.get("workshopId") or "finmodule-sync"
    op_payload = {
        "type": "service",
        "partnerType": "customer",
        "partnerId": partner_id,
        "partnerName": customer_name,
        "vehicleId": vehicle_id,
        "items": [{
            "itemType": "service", "name": service, "quantity": 1, "qty": 1,
            "price": total, "total": total, "billingType": "workshop",
        }],
        "paymentMethod": "cash" if is_cash else "credit",
        "paymentStatus": "paid" if is_cash else "unpaid",
        "workshopId": workshop_id,
        "notes": f"عملية عبر كاترينا — {service}",
        "source": "katrina",
    }
    if payload.get("odometer") or payload.get("mileage"):
        op_payload["notes"] += f" — العداد: {payload.get('odometer') or payload.get('mileage')}"

    try:
        op = supa.operations_create(op_payload)
    except Exception as e:
        _log.exception("bot operation create failed: %s", redact(str(e), max_len=140))
        return {"error": "operation_create_failed", "detail": redact(str(e), max_len=120)}

    op_id = op.get("id")
    journal_id = None
    try:
        import routes_extended as _re
        op_row = {
            "id": op_id, "type": "service",
            "partner_name": customer_name, "partner_type": "customer",
            "partnerName": customer_name, "paymentMethod": op_payload["paymentMethod"],
            "vehicle_id": vehicle_id, "vehicleId": vehicle_id,
            "items": op_payload["items"], "subtotal": total, "total": total,
            "payment_method": op_payload["paymentMethod"],
            "payment_status": op_payload["paymentStatus"],
            "invoice_number": op.get("invoiceNumber"),
            "op_date": op.get("date"), "workshop_id": workshop_id,
        }
        built = _re._build_operation_journal_entry(op_row, workshop_id)
        entries = built if isinstance(built, list) else ([built] if built else [])
        for entry in entries:
            entry["reference_id"] = op_id
            entry["source"] = "katrina_operation"
            res = _re._safe_insert_journal_entry(supa, entry)
            if res and not journal_id:
                first = res[0] if isinstance(res, list) else res
                journal_id = (first or {}).get("id")
        try:
            _re._invalidate_ops_caches()
            _re._invalidate_finance_caches_safe()
        except Exception:
            pass
    except Exception as e:
        _log.exception("bot operation journal failed: %s", redact(str(e), max_len=140))

    return {
        "posted": True, "operation_id": op_id, "invoice_number": op.get("invoiceNumber"),
        "journal_id": journal_id, "total": total, "partner_name": customer_name,
        "payment_method": op_payload["paymentMethod"], "service": service,
        "vehicle_id": vehicle_id, "customer_id": partner_id,
    }


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
                    # 1) 🏦 Governance (No Hard Delete): REVERSE linked journal
                    #    entries via the central engine instead of deleting them.
                    #    Preserves original + adds a contra entry (immutable audit).
                    try:
                        from core import accounting_engine
                        accounting_engine.get_engine().reverse(
                            reference_id=op_id, reason="حذف عملية",
                            actor={"user_id": committer or "system"},
                        )
                    except Exception as je:
                        _log.debug("cascade journal reversal skipped: %s", redact(str(je), max_len=80))
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

        # ── 🏦 Sale/Service (invoice) → إنشاء عملية كاملة (تظهر في كل الصفحات المالية) ──
        if action == "invoice":
            fres = _commit_sale_operation(payload)
            if isinstance(fres, dict) and fres.get("error"):
                return {"error": fres.get("error"), "detail": fres}
            execution_id = uuid.uuid4().hex[:12]
            STATE["executions"][execution_id] = {
                "id": execution_id, "draft_id": draft_id, "result": fres,
                "status": "executed", "committer": committer or "anonymous",
                "committed_at": time.time(),
            }
            draft["status"] = "committed"
            draft["execution_id"] = execution_id
            _audit("COMMIT_SALE_OPERATION", draft_id=draft_id, execution_id=execution_id,
                   operation_id=fres.get("operation_id"), journal_id=fres.get("journal_id"),
                   total=fres.get("total"), committer=committer)
            return {"execution_id": execution_id, "result": fres}

        # ── 🏦 Financial actions — committed THROUGH the central accounting engine ──
        #    (Governance: single writer, never auto-commit, immutable audit.)
        if action in ("payment", "expense", "reverse", "purchase"):
            try:
                from core import financial_actions as _fa
                fa_actor = {"user_id": committer or "system"}
                if action == "payment":
                    fres = _fa.collect_payment(
                        customer=payload.get("customer") or payload.get("customer_name") or "",
                        amount=payload.get("amount") or payload.get("total"),
                        payment_method=payload.get("payment_method") or "cash",
                        date=payload.get("date"),
                        reference_id=payload.get("reference_id"),
                        actor=fa_actor,
                    )
                elif action == "expense":
                    fres = _fa.create_expense(
                        description=payload.get("description") or payload.get("category") or "مصروف",
                        amount=payload.get("amount") or payload.get("total"),
                        category=payload.get("category"),
                        supplier=payload.get("supplier"),
                        payment_method=payload.get("payment_method") or "cash",
                        date=payload.get("date"),
                        reference_id=payload.get("reference_id"),
                        actor=fa_actor,
                    )
                elif action == "purchase":
                    # 🛒 شراء من مورد — مدين المخزون / دائن بحسب طريقة الدفع.
                    fres = _fa.create_purchase(
                        supplier=(payload.get("supplier") or {}).get("name")
                                 if isinstance(payload.get("supplier"), dict)
                                 else payload.get("supplier"),
                        items=payload.get("items") or [],
                        payment_method=payload.get("payment_method") or "cash",
                        vat=payload.get("vat"),
                        date=payload.get("date"),
                        reference_id=payload.get("reference_id"),
                        actor=fa_actor,
                    )
                    # 🆕 تحديث كميات المخزون (best-effort) — لا يوقف الترحيل عند الفشل.
                    if isinstance(fres, dict) and (fres.get("posted") or fres.get("journal_id")):
                        try:
                            _upsert_parts_from_purchase(payload.get("items") or [])
                        except Exception as _iee:
                            _log.debug("parts stock update skipped: %s",
                                       redact(str(_iee), max_len=80))
                else:  # reverse
                    fres = _fa.reverse_entry(
                        journal_id=payload.get("journal_id"),
                        reference_id=payload.get("reference_id"),
                        reason=payload.get("reason") or "عكس عبر المساعد",
                        actor=fa_actor,
                    )
            except Exception as e:
                _log.exception("financial commit failed: %s", redact(str(e), max_len=140))
                return {"error": "commit_failed", "detail": redact(str(e), max_len=140)}

            if isinstance(fres, dict) and fres.get("error") and not fres.get("posted") and not fres.get("reversed"):
                return {"error": fres.get("error"), "detail": fres}

            execution_id = uuid.uuid4().hex[:12]
            STATE["executions"][execution_id] = {
                "id": execution_id, "draft_id": draft_id, "result": fres,
                "status": "executed", "committer": committer or "anonymous",
                "committed_at": time.time(),
            }
            draft["status"] = "committed"
            draft["execution_id"] = execution_id
            _audit("COMMIT_FINANCIAL", draft_id=draft_id, execution_id=execution_id,
                   action=action, journal_id=(fres or {}).get("journal_id"), committer=committer)
            return {"execution_id": execution_id, "result": fres}

        # ── 🆕 supplier — synchronous write to the same store the suppliers API uses ──
        #    (Supabase `suppliers` table doesn't exist → the domain repo falls back to
        #    the file-backed mem store `uploads/suppliers.json`; we write there too.)
        if action == "supplier":
            name = str(payload.get("name") or "").strip()
            if not name:
                return {"error": "missing_supplier_name"}
            phone = str(payload.get("phone") or "").strip()
            try:
                from server import _mem_read, _mem_write
                rows = _mem_read("suppliers") or []
                dup = None
                for r in rows:
                    same_name = str(r.get("name") or "").strip() == name
                    r_phone = str(r.get("phone") or "").strip()
                    if same_name and (not phone or not r_phone or r_phone == phone):
                        dup = r
                        break
                if dup:
                    result_data = {**dup, "_duplicate": True, "_action": "create_supplier"}
                    execution_id = uuid.uuid4().hex[:12]
                    STATE["executions"][execution_id] = {
                        "id": execution_id, "draft_id": draft_id, "result": result_data,
                        "status": "executed", "committer": committer or "anonymous",
                        "committed_at": time.time(),
                    }
                    draft["status"] = "committed"
                    draft["execution_id"] = execution_id
                    _audit("COMMIT_DUPLICATE_SKIPPED", draft_id=draft_id, execution_id=execution_id,
                           table="suppliers", existing_id=dup.get("id"))
                    return {"execution_id": execution_id, "result": result_data}

                supplier = {
                    "id": str(uuid.uuid4()),
                    "name": name[:120],
                    "phone": phone[:32] or None,
                    "category": payload.get("category") or None,
                    "paymentTerms": payload.get("payment_terms") or payload.get("paymentTerms") or None,
                    "rating": 5.0,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "source": "katrina",
                }
                rows.append(supplier)
                _mem_write("suppliers", rows)
                try:
                    import perf_cache
                    perf_cache.invalidate("partner_fin_map")
                    perf_cache.invalidate("ops_for_partner_fin")
                except Exception:
                    pass
                execution_id = uuid.uuid4().hex[:12]
                STATE["executions"][execution_id] = {
                    "id": execution_id, "draft_id": draft_id, "result": supplier,
                    "status": "executed", "committer": committer or "anonymous",
                    "committed_at": time.time(),
                }
                draft["status"] = "committed"
                draft["execution_id"] = execution_id
                _audit("COMMIT_SUPPLIER", draft_id=draft_id, execution_id=execution_id,
                       entity_id=supplier["id"], committer=committer)
                return {"execution_id": execution_id, "result": supplier}
            except Exception as e:
                _log.exception("supplier commit failed: %s", redact(str(e), max_len=120))
                return {"error": "commit_failed", "detail": redact(str(e), max_len=120)}

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
        # enrich with originating draft (action + payload + proposer) for UI rendering
        enriched: List[Dict[str, Any]] = []
        for a in items[:limit]:
            draft = STATE["drafts"].get(a.get("draft_id")) or {}
            enriched.append({
                **a,
                "action": draft.get("action"),
                "payload": draft.get("payload") or {},
                "proposer": draft.get("proposer"),
                "session_id": draft.get("session_id"),
                "draft_status": draft.get("status"),
            })
        return enriched


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
        try:
            from core import runtime_store
            runtime_store.clear_all()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# 10) Startup hydration — restore drafts/approvals/executions/audit from MongoDB
# ─────────────────────────────────────────────────────────────────────────────

try:
    from core import runtime_store as _runtime_store
    _runtime_store.hydrate(STATE)
except Exception as _e:  # pragma: no cover
    _log.debug("runtime hydrate skipped: %s", redact(str(_e), max_len=80))
