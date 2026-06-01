"""Vehicles service — business logic layer.

Handles:
  • Customer linkage (get-or-create) on POST
  • Customer file-number propagation
  • Tracking-link generation
  • Vehicle status side-effects (settle credit ops on delivery)
  • Cascade delete (invoices + operations + file-based invoices)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .repository import VehicleRepository


class VehicleService:
    def __init__(self, repo: Optional[VehicleRepository] = None):
        self.repo = repo or VehicleRepository()

    # ---- READ ----

    async def list_vehicles(self) -> List[Dict[str, Any]]:
        from server import _attach_customer_file_numbers_to_vehicles  # noqa: WPS433
        rows = await self.repo.list_all()
        rows = await _attach_customer_file_numbers_to_vehicles(rows)
        # Set default status & estimatedTotal
        for r in rows:
            if r.get("status") is None:
                r["status"] = "diagnosis"
            est = 0
            parts = r.get("parts")
            if isinstance(parts, list):
                for p in parts:
                    if isinstance(p, dict):
                        price = p.get("price") or 0
                        qty = p.get("quantity") or 1
                        try:
                            est += float(price) * float(qty)
                        except Exception:
                            pass
            if est:
                r["estimatedTotal"] = est
        return rows

    async def get_vehicle(self, vehicle_id: str) -> Dict[str, Any]:
        from server import _attach_customer_file_numbers_to_vehicles  # noqa: WPS433
        row = await self.repo.get(vehicle_id)
        if not row:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        patched = await _attach_customer_file_numbers_to_vehicles([row])
        return patched[0] if patched else row

    # ---- WRITE ----

    async def create_vehicle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        from server import (  # noqa: WPS433
            _get_customer_file_number_map,
            generate_tracking_link,
            get_or_create_customer,
        )
        customer_id = await get_or_create_customer(
            data.get("customerName"),
            data.get("customerPhone"),
            data.get("customerEmail"),
        )
        vehicle_dict = {
            **data,
            "id": str(uuid.uuid4()),
            "customerId": customer_id,
            "trackingLink": generate_tracking_link(),
            "estimatedCompletion": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "entryDate": datetime.utcnow().isoformat(),
        }
        file_map = await _get_customer_file_number_map([customer_id])
        vehicle_dict["customerFileNumber"] = file_map.get(customer_id) or None
        return await self.repo.create(vehicle_dict)

    async def update_vehicle(
        self,
        vehicle_id: str,
        raw_update: Dict[str, Any],
    ) -> Dict[str, Any]:
        from server import (  # noqa: WPS433
            _attach_customer_file_numbers_to_vehicles,
            _set_customer_file_number,
            settle_vehicle_credit_operations,
        )
        customer_file_present = "customerFileNumber" in raw_update
        customer_file_value = raw_update.pop("customerFileNumber", None) if customer_file_present else None
        patch = {k: v for k, v in raw_update.items() if v is not None}

        # Get existing for fallback customerId
        existing = await self.repo.get(vehicle_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        updated = await self.repo.update(vehicle_id, patch) if patch else existing
        if not updated:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        customer_id = str(updated.get("customerId") or existing.get("customerId") or "").strip()
        if customer_file_present and customer_id:
            await _set_customer_file_number(customer_id, customer_file_value)

        if patch.get("status") == "delivered":
            await settle_vehicle_credit_operations(vehicle_id)

        patched_rows = await _attach_customer_file_numbers_to_vehicles([updated])
        return patched_rows[0] if patched_rows else updated

    async def delete_vehicle(self, vehicle_id: str) -> bool:
        from server import delete_invoices_by_vehicle_id  # noqa: WPS433
        ok = await self.repo.delete(vehicle_id)
        try:
            delete_invoices_by_vehicle_id(vehicle_id)
        except Exception:
            pass
        return ok
