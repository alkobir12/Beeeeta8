"""Suppliers service — business logic layer with financial enrichment."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from shared import partner_financials as _pf
from .repository import SupplierRepository


class SupplierService:
    def __init__(self, repo: Optional[SupplierRepository] = None):
        self.repo = repo or SupplierRepository()

    # ---- READ ----

    async def list_suppliers(
        self,
        workshop_id: Optional[str] = None,
        sync_accounts: bool = False,
    ) -> List[Dict[str, Any]]:
        rows = await self.repo.list_all()
        if not rows:
            return []
        financial_map = await _pf.build_partner_financial_map("supplier", rows, workshop_id)
        if sync_accounts:
            try:
                await _pf.safe_sync_partner_subaccounts("supplier", rows, financial_map)
            except Exception:
                pass
        empty_summary = _pf.partner_summary_template()
        enriched = []
        for row in rows:
            sid = str(row.get("id") or "")
            summary = financial_map.get(sid, empty_summary)
            enriched.append({**row, **summary})
        return enriched

    async def get_supplier(self, supplier_id: str) -> Optional[Dict[str, Any]]:
        return await self.repo.get(supplier_id)

    # ---- WRITE ----

    async def create_supplier(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = await self.repo.create(data)
        self._invalidate_caches()
        return result

    async def update_supplier(self, supplier_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        result = await self.repo.update(supplier_id, patch)
        self._invalidate_caches()
        return result

    async def delete_supplier(self, supplier_id: str) -> bool:
        ok = await self.repo.delete(supplier_id)
        if ok:
            self._invalidate_caches()
        return ok

    @staticmethod
    def _invalidate_caches() -> None:
        try:
            import perf_cache
            perf_cache.invalidate("partner_fin_map")
            perf_cache.invalidate("ops_for_partner_fin")
        except Exception:
            pass
