"""Suppliers repository — DB-agnostic data-access (supabase / memory / mongo).

Supports the existing fallback heuristic: when no suppliers table exists,
derive supplier rows from `parts.supplier` and from `accounts` named like
"مورد - X".
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional


def _provider() -> str:
    return os.environ.get("DB_PROVIDER", "mongo").lower()


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


class SupplierRepository:
    """Stateless wrapper around the active DB provider for suppliers."""

    # ---- READ ----

    async def list_all(self) -> List[Dict[str, Any]]:
        """Return raw supplier rows (no financial enrichment)."""
        if _provider() == "supabase":
            # Reuse legacy logic in server.py to keep the fallback heuristic intact
            # (suppliers may be missing → derive from parts + accounts).
            from server import (
                SUPPLIERS_TABLE_AVAILABLE,
                _derive_suppliers_from_parts,
                _enrich_suppliers_from_accounts,
                _mem_read,
                supabase_service,
            )
            if not SUPPLIERS_TABLE_AVAILABLE:
                rows = _mem_read("suppliers")
                if not rows:
                    rows = await _derive_suppliers_from_parts("supabase")
                return await _enrich_suppliers_from_accounts(rows)
            try:
                if supabase_service.client and not supabase_service.mock_mode:
                    res = supabase_service.client.table("suppliers").select("*").execute()
                    rows = res.data or []
                    if not rows:
                        rows = await _derive_suppliers_from_parts("supabase")
                    return await _enrich_suppliers_from_accounts(rows)
            except Exception:
                rows = _mem_read("suppliers")
                if not rows:
                    rows = await _derive_suppliers_from_parts("supabase")
                return await _enrich_suppliers_from_accounts(rows)
            return []

        if _provider() == "memory":
            from server import _derive_suppliers_from_parts, _mem_read
            rows = _mem_read("suppliers")
            if not rows:
                rows = await _derive_suppliers_from_parts("memory")
            return rows

        # Mongo
        from server import _derive_suppliers_from_parts, db
        rows = await db.suppliers.find().to_list(1000)
        normalized = [{k: v for k, v in r.items() if k != "_id"} for r in rows]
        if not normalized:
            normalized = await _derive_suppliers_from_parts("mongo")
        return normalized

    async def get(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        if _provider() == "supabase":
            try:
                from server import supabase_service
                res = supabase_service.client.table("suppliers").select("*").eq("id", supplier_id).maybe_single().execute()
                return getattr(res, "data", None)
            except Exception:
                pass
            # fallback: search the list
            rows = await self.list_all()
            return next((r for r in rows if str(r.get("id")) == str(supplier_id)), None)
        if _provider() == "memory":
            from server import _mem_read
            return next((r for r in (_mem_read("suppliers") or []) if r.get("id") == supplier_id), None)
        from server import db
        row = await db.suppliers.find_one({"id": supplier_id})
        if row:
            row.pop("_id", None)
        return row

    # ---- WRITE ----

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(data)
        payload["createdAt"] = payload.get("createdAt") or _now_iso()

        if _provider() == "supabase":
            from server import SUPPLIERS_TABLE_AVAILABLE, _mem_read, _mem_write, supabase_service
            if SUPPLIERS_TABLE_AVAILABLE:
                try:
                    res = supabase_service.client.table("suppliers").insert(payload).execute()
                    inserted = (res.data or [None])[0] or payload
                    return inserted
                except Exception:
                    pass
            # Fallback to in-memory
            rows = _mem_read("suppliers") or []
            rows.append(payload)
            _mem_write("suppliers", rows)
            return payload
        if _provider() == "memory":
            from server import _mem_read, _mem_write
            rows = _mem_read("suppliers") or []
            rows.append(payload)
            _mem_write("suppliers", rows)
            return payload
        from server import db
        await db.suppliers.insert_one(payload)
        payload.pop("_id", None)
        return payload

    async def update(self, supplier_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not patch:
            return await self.get(supplier_id)
        patch_clean = {k: v for k, v in patch.items() if v is not None}
        patch_clean["updatedAt"] = _now_iso()

        if _provider() == "supabase":
            from server import SUPPLIERS_TABLE_AVAILABLE, _mem_read, _mem_write, supabase_service
            if SUPPLIERS_TABLE_AVAILABLE:
                try:
                    res = supabase_service.client.table("suppliers").update(patch_clean).eq("id", supplier_id).execute()
                    if res.data:
                        return res.data[0]
                except Exception:
                    pass
            rows = _mem_read("suppliers") or []
            updated = None
            for r in rows:
                if r.get("id") == supplier_id:
                    r.update(patch_clean)
                    updated = r
                    break
            _mem_write("suppliers", rows)
            return updated
        if _provider() == "memory":
            from server import _mem_read, _mem_write
            rows = _mem_read("suppliers") or []
            updated = None
            for r in rows:
                if r.get("id") == supplier_id:
                    r.update(patch_clean)
                    updated = r
                    break
            _mem_write("suppliers", rows)
            return updated
        from server import db
        await db.suppliers.update_one({"id": supplier_id}, {"$set": patch_clean})
        return await self.get(supplier_id)

    async def delete(self, supplier_id: str) -> bool:
        if _provider() == "supabase":
            from server import SUPPLIERS_TABLE_AVAILABLE, _mem_read, _mem_write, supabase_service
            if SUPPLIERS_TABLE_AVAILABLE:
                try:
                    supabase_service.client.table("suppliers").delete().eq("id", supplier_id).execute()
                    return True
                except Exception:
                    pass
            rows = _mem_read("suppliers") or []
            new_rows = [r for r in rows if r.get("id") != supplier_id]
            removed = len(new_rows) != len(rows)
            _mem_write("suppliers", new_rows)
            return removed
        if _provider() == "memory":
            from server import _mem_read, _mem_write
            rows = _mem_read("suppliers") or []
            new_rows = [r for r in rows if r.get("id") != supplier_id]
            removed = len(new_rows) != len(rows)
            _mem_write("suppliers", new_rows)
            return removed
        from server import db
        res = await db.suppliers.delete_one({"id": supplier_id})
        return bool(res.deleted_count)
