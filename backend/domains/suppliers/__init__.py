"""Suppliers domain — DDD extraction (iter 233).

Public exports:
  • suppliers_domain_router : FastAPI router (mount at /api via api_router)
  • SupplierService         : business logic + enrichment
  • SupplierRepository      : DB-agnostic data access
"""
from .repository import SupplierRepository  # noqa: F401
from .router import router as suppliers_domain_router  # noqa: F401
from .service import SupplierService  # noqa: F401
