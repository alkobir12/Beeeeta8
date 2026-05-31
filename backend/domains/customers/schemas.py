"""Customers domain — Pydantic schemas (L5 DDD).

Note: this project uses **string UUIDs** (not UUID objects) for compatibility
with Supabase/Mongo serialisation across all existing endpoints.
"""
from __future__ import annotations
from typing import Any, List, Optional
from datetime import datetime
import uuid

from pydantic import BaseModel, Field


# ---------- Create / Update DTOs ----------

class CustomerCreate(BaseModel):
    """Fields accepted when creating a new customer."""
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str  # required by master-data policy
    fileNumber: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    vehicleBrand: Optional[str] = None
    vehiclePlate: Optional[str] = None
    vehicleKm: Optional[int] = None
    creditLimit: Optional[float] = 10000


class CustomerUpdate(BaseModel):
    """All-optional update payload."""
    name: Optional[str] = None
    phone: Optional[str] = None
    fileNumber: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    vehicleBrand: Optional[str] = None
    vehiclePlate: Optional[str] = None
    vehicleKm: Optional[int] = None
    creditLimit: Optional[float] = None


# ---------- Read DTO (enriched with financial summary) ----------

class CustomerOut(BaseModel):
    """Customer row + financial enrichment returned by GET /api/customers."""
    id: str
    name: str
    phone: Optional[str] = None
    fileNumber: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    vehicleBrand: Optional[str] = None
    vehiclePlate: Optional[str] = None
    vehicleKm: Optional[int] = None

    # Linked entities
    vehicles: List[str] = []
    totalVisits: int = 0
    lastVisit: Optional[datetime] = None
    createdAt: Optional[datetime] = None

    # Financials (enriched from partner_financial_map)
    creditLimit: Optional[float] = 10000
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
