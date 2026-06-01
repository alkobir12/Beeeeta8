"""Vehicles domain — Pydantic DTOs (re-exports legacy models for compat)."""
from __future__ import annotations

from models import Vehicle, VehicleCreate, VehicleUpdate

__all__ = ["Vehicle", "VehicleCreate", "VehicleUpdate"]
