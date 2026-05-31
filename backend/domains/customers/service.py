"""Customers service — business logic layer.

Responsibilities:
  • Listing customers with financial enrichment (debit/credit/overdue balances).
  • Adding file numbers from auxiliary lookup table.
  • Optional sync of partner subaccounts in the chart of accounts.
  • Cache invalidation on writes.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from .repository import CustomerRepository

# Lazy imports through shared helpers to avoid circular dependency with server.py
from shared import partner_financials as _pf


class CustomerService:
    def __init__(self, repo: Optional[CustomerRepository] = None):
        self.repo = repo or CustomerRepository()

    # ---- READ ----

    async def list_customers(
        self,
        workshop_id: Optional[str] = None,
        sync_accounts: bool = False,
    ) -> List[Dict[str, Any]]:
        rows = await self.repo.list_all()
        if not rows:
            return []

        ids = [str(r.get("id") or "") for r in rows]
        file_map = await _pf.get_customer_file_number_map(ids)
        financial_map = await _pf.build_partner_financial_map("customer", rows, workshop_id)

        if sync_accounts:
            try:
                await _pf.safe_sync_partner_subaccounts("customer", rows, financial_map)
            except Exception:
                pass  # never block listing because of optional sync

        empty_summary = _pf.partner_summary_template()
        enriched = []
        for row in rows:
            cid = str(row.get("id") or "")
            summary = financial_map.get(cid, empty_summary)
            enriched.append({
                **row,
                **summary,
                "fileNumber": row.get("fileNumber") or file_map.get(cid) or None,
            })
        return enriched

    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return await self.repo.get(customer_id)

    # ---- WRITE ----

    async def create_customer(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = await self.repo.create(data)
        self._invalidate_caches()
        return result

    async def update_customer(self, customer_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        result = await self.repo.update(customer_id, patch)
        self._invalidate_caches()
        return result

    async def delete_customer(self, customer_id: str) -> bool:
        ok = await self.repo.delete(customer_id)
        if ok:
            self._invalidate_caches()
        return ok

    # ---- Cache helpers ----

    @staticmethod
    def _invalidate_caches() -> None:
        try:
            import perf_cache
            perf_cache.invalidate("partner_fin_map")
            perf_cache.invalidate("ops_for_partner_fin")
        except Exception:
            pass
