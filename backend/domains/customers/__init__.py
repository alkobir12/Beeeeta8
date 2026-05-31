"""Customers domain — DDD slice.

Public surface:
  • router — FastAPI APIRouter mounted at /api/customers/*
  • CustomerService — business-logic entry-point (used internally + by tests)
  • CustomerRepository — data-access entry-point
"""
from .router import router  # noqa: F401
from .service import CustomerService  # noqa: F401
from .repository import CustomerRepository  # noqa: F401
