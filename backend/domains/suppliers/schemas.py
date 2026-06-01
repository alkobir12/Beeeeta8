"""Suppliers domain — Pydantic DTOs."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    creditLimit: Optional[float] = 0


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    creditLimit: Optional[float] = None


class SupplierOut(BaseModel):
    id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    createdAt: Optional[datetime] = None

    # Financial enrichment
    creditLimit: Optional[float] = 0
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
