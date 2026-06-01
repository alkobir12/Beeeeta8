"""Suppliers domain — Pydantic DTOs.

Mirrors `SupplierBase` in /app/backend/models.py to keep wire-compatibility
with the existing frontend. All financial fields are populated by the service
layer after persistence (see SupplierService.list_suppliers).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    """Fields accepted when creating a supplier (mirror of SupplierBase)."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: Optional[str] = None
    contactPerson: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = 5.0


class SupplierUpdate(BaseModel):
    """All-optional update payload."""
    name: Optional[str] = None
    phone: Optional[str] = None
    contactPerson: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = None


class SupplierOut(BaseModel):
    """Supplier row + financial enrichment returned by GET /api/suppliers."""
    id: str
    name: str
    phone: Optional[str] = None
    contactPerson: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = 5.0
    createdAt: Optional[datetime] = None

    # Financial enrichment
    balance: Optional[float] = 0
    debitBalance: Optional[float] = 0
    creditBalance: Optional[float] = 0
    overdueBalance: Optional[float] = 0
    ajelBalance: Optional[float] = 0
    settledAmount: Optional[float] = 0
    paymentPlanCount: Optional[int] = 0
    netBalance: Optional[float] = 0
    movements: Optional[List[Any]] = []

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
