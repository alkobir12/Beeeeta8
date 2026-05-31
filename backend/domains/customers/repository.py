"""Customers repository — DB-agnostic data-access layer.

Supports 3 backends:
  • supabase  (production)
  • memory    (tests / fallback)
  • mongo     (legacy)

Higher layers (service.py / router.py) talk only to this repository.
"""
from __future__ import annotations
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


def _provider() -> str:
    return os.environ.get("DB_PROVIDER", "mongo").lower()


# ---------- Helpers ----------

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


# ---------- Public repository ----------

class CustomerRepository:
    """Stateless wrapper around the active DB provider."""

    # ---- READ ----

    async def list_all(self) -> List[Dict[str, Any]]:
        if _provider() == "supabase":
            from server import supabase_service  # module-level instance
            return supabase_service.customers_list() or []
        if _provider() == "memory":
            from server import _mem_read  # late import to avoid circular
            return _mem_read("customers") or []
        # Mongo
        from server import db
        rows = await db.customers.find().to_list(1000)
        for r in rows:
            r.pop("_id", None)
        return rows

    async def get(self, customer_id: str) -> Optional[Dict[str, Any]]:
        if _provider() == "supabase":
            from server import supabase_service
            res = supabase_service.client.table("customers").select("*").eq("id", customer_id).maybe_single().execute()
            return getattr(res, "data", None)
        if _provider() == "memory":
            from server import _mem_read
            return next((r for r in (_mem_read("customers") or []) if r.get("id") == customer_id), None)
        from server import db
        row = await db.customers.find_one({"id": customer_id})
        if row:
            row.pop("_id", None)
        return row

    # ---- WRITE ----

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(data)

        if _provider() == "supabase":
            from server import supabase_service
            # Delegate to existing helper that knows Supabase schema specifics
            return supabase_service.customers_create(payload) or payload
        # Memory / Mongo fallbacks set defaults locally
        payload["createdAt"] = payload.get("createdAt") or _now_iso()
        payload.setdefault("vehicles", [])
        payload.setdefault("totalVisits", 0)
        if _provider() == "memory":
            from server import _mem_read, _mem_write
            rows = _mem_read("customers") or []
            rows.append(payload)
            _mem_write("customers", rows)
            return payload
        from server import db
        await db.customers.insert_one(payload)
        payload.pop("_id", None)
        return payload

    async def update(self, customer_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not patch:
            return await self.get(customer_id)

        patch_clean = {k: v for k, v in patch.items() if v is not None}

        if _provider() == "supabase":
            from server import supabase_service
            return supabase_service.customers_update(customer_id, patch_clean) or await self.get(customer_id)
        # Memory / Mongo: stamp updatedAt locally
        patch_clean["updatedAt"] = _now_iso()
        if _provider() == "memory":
            from server import _mem_read, _mem_write
            rows = _mem_read("customers") or []
            updated = None
            for r in rows:
                if r.get("id") == customer_id:
                    r.update(patch_clean)
                    updated = r
                    break
            _mem_write("customers", rows)
            return updated
        from server import db
        await db.customers.update_one({"id": customer_id}, {"$set": patch_clean})
        return await self.get(customer_id)

    async def delete(self, customer_id: str) -> bool:
        """Hard-delete the customer row + cascade vehicles/invoices when possible."""
        if _provider() == "supabase":
            from server import supabase_service
            # cascade delete linked vehicles & invoices best-effort
            try:
                supabase_service.client.table("invoices").delete().eq("customer_id", customer_id).execute()
            except Exception:
                pass
            try:
                supabase_service.client.table("vehicles").delete().eq("customer_id", customer_id).execute()
            except Exception:
                pass
            supabase_service.customers_delete(customer_id)
            return True
        if _provider() == "memory":
            from server import _mem_read, _mem_write
            rows = _mem_read("customers") or []
            new_rows = [r for r in rows if r.get("id") != customer_id]
            removed = len(new_rows) != len(rows)
            _mem_write("customers", new_rows)
            return removed
        from server import db
        res = await db.customers.delete_one({"id": customer_id})
        return bool(res.deleted_count)
