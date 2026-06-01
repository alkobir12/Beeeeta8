"""Vehicles repository — DB-agnostic data-access (supabase / memory / mongo)."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def _provider() -> str:
    return os.environ.get("DB_PROVIDER", "mongo").lower()


class VehicleRepository:
    """Stateless wrapper around the active DB provider for vehicles."""

    # ---- READ ----

    async def list_all(self, limit: int = 200) -> List[Dict[str, Any]]:
        if _provider() == "supabase":
            from server import supabase_service
            return supabase_service.vehicles_list() or []
        if _provider() == "memory":
            from server import _mem_read
            return _mem_read("vehicles") or []
        from server import db
        rows = await db.vehicles.find({}, {"_id": 0}).sort("entryDate", -1).limit(limit).to_list(limit)
        return rows

    async def get(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        if _provider() == "supabase":
            from server import supabase_service
            return supabase_service.vehicles_get(vehicle_id)
        if _provider() == "memory":
            from server import _mem_read
            return next((r for r in (_mem_read("vehicles") or []) if r.get("id") == vehicle_id), None)
        from server import db
        row = await db.vehicles.find_one({"id": vehicle_id})
        if row:
            row.pop("_id", None)
        return row

    # ---- WRITE ----

    async def create(self, vehicle_dict: Dict[str, Any]) -> Dict[str, Any]:
        if _provider() == "supabase":
            from server import supabase_service
            return supabase_service.vehicles_create(vehicle_dict) or vehicle_dict
        if _provider() == "memory":
            from server import _mem_read, _mem_write
            rows = _mem_read("vehicles") or []
            rows.append(vehicle_dict)
            _mem_write("vehicles", rows)
            return vehicle_dict
        from server import db
        await db.vehicles.insert_one(vehicle_dict)
        vehicle_dict.pop("_id", None)
        return vehicle_dict

    async def update(self, vehicle_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not patch:
            return await self.get(vehicle_id)
        if _provider() == "supabase":
            from server import supabase_service
            return supabase_service.vehicles_update(vehicle_id, patch)
        if _provider() == "memory":
            from server import _mem_read, _mem_write
            from datetime import datetime
            rows = _mem_read("vehicles") or []
            updated = None
            for i, r in enumerate(rows):
                if r.get("id") == vehicle_id:
                    # Coerce datetime fields to ISO
                    clean = {**patch}
                    for k in ("estimatedCompletion", "completionDate"):
                        if k in clean and isinstance(clean[k], datetime):
                            clean[k] = clean[k].isoformat()
                    rows[i] = {**r, **clean}
                    updated = rows[i]
                    break
            _mem_write("vehicles", rows)
            return updated
        from server import db
        await db.vehicles.update_one({"id": vehicle_id}, {"$set": patch})
        return await self.get(vehicle_id)

    async def delete(self, vehicle_id: str) -> bool:
        if _provider() == "supabase":
            from server import supabase_service
            if hasattr(supabase_service, "client") and supabase_service.client and not supabase_service.mock_mode:
                try:
                    supabase_service.client.table("invoices").delete().eq("vehicle_id", vehicle_id).execute()
                except Exception:
                    pass
                try:
                    supabase_service.client.table("operations").delete().eq("vehicleId", vehicle_id).execute()
                except Exception:
                    pass
            supabase_service.vehicles_delete(vehicle_id)
            return True
        if _provider() == "memory":
            from server import _mem_read, _mem_write
            rows = _mem_read("vehicles") or []
            new_rows = [r for r in rows if r.get("id") != vehicle_id]
            removed = len(new_rows) != len(rows)
            _mem_write("vehicles", new_rows)
            # cascade operations
            ops = _mem_read("operations") or []
            ops_new = [op for op in ops if op.get("vehicleId") != vehicle_id]
            _mem_write("operations", ops_new)
            return removed
        from server import db
        try:
            await db.invoices.delete_many({"vehicleId": vehicle_id})
        except Exception:
            pass
        try:
            await db.operations.delete_many({"vehicleId": vehicle_id})
        except Exception:
            pass
        res = await db.vehicles.delete_one({"id": vehicle_id})
        return bool(res.deleted_count)
