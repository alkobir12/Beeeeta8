"""
📋 Financial Control Models — Pydantic schemas for the FC Layer.

Models:
  • ApprovalRequest  — workflow entity (PENDING_REVIEW → PENDING_APPROVAL → APPROVED/REJECTED)
  • ApprovalAction   — per-step action (review, approve, reject) for audit trail
  • Finding          — durable audit finding produced by AuditRulesEngine
  • FindingComment   — collaboration thread on a finding
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============== Approval ==============

class ApprovalLevel(str, Enum):
    AUTO = "auto"
    MANAGER = "manager"
    SENIOR_MANAGER = "senior_manager"
    DIRECTOR = "director"


class ApprovalStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalAction(BaseModel):
    """A single step in the approval audit trail."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    action: str  # 'create' | 'review' | 'approve' | 'reject' | 'cancel'
    actor: str   # username
    actor_role: Optional[str] = None
    note: Optional[str] = None
    at: str = Field(default_factory=_now_iso)


class ApprovalRequest(BaseModel):
    """A financial action awaiting workflow approval."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    workshop_id: str = "finmodule-sync"
    # subject of approval
    entity_type: str          # 'operation' | 'journal_entry' | 'expense' | 'purchase' | ...
    entity_id: Optional[str] = None
    entity_payload: Dict[str, Any] = Field(default_factory=dict)
    amount: float = 0.0
    currency: str = "SAR"
    title: str
    description: Optional[str] = None
    # workflow
    required_level: ApprovalLevel
    status: ApprovalStatus = ApprovalStatus.PENDING_REVIEW
    creator: str
    creator_role: Optional[str] = None
    reviewer: Optional[str] = None
    approver: Optional[str] = None
    # audit trail
    actions: List[ApprovalAction] = Field(default_factory=list)
    # timing
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    completed_at: Optional[str] = None
    # idempotency
    idempotency_key: Optional[str] = None


# ============== Findings ==============

class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class FindingComment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    author: str
    text: str
    at: str = Field(default_factory=_now_iso)


class Finding(BaseModel):
    """A durable audit finding with lifecycle (open → resolved/dismissed)."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    workshop_id: str = "finmodule-sync"
    rule_code: str            # e.g. 'duplicate_payment', 'negative_inventory'
    severity: FindingSeverity
    title: str
    description: str
    root_cause: Optional[str] = None
    financial_impact: float = 0.0
    # context
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    affected_accounts: List[str] = Field(default_factory=list)
    related_entries: List[str] = Field(default_factory=list)
    # lifecycle
    status: FindingStatus = FindingStatus.OPEN
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    comments: List[FindingComment] = Field(default_factory=list)
    # timing
    detected_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    # signature for idempotent re-detection (prevents duplicates each scan)
    signature: str = ""


# ============== Approval Matrix Tier ==============

class ApprovalMatrixTier(BaseModel):
    """Configurable threshold tier."""
    min_amount: float
    max_amount: Optional[float] = None  # None = unlimited
    level: ApprovalLevel
    required_roles: List[str]  # roles eligible to approve at this tier


DEFAULT_MATRIX: List[ApprovalMatrixTier] = [
    ApprovalMatrixTier(min_amount=0, max_amount=1000, level=ApprovalLevel.AUTO, required_roles=["any"]),
    ApprovalMatrixTier(min_amount=1000.01, max_amount=10000, level=ApprovalLevel.MANAGER, required_roles=["manager", "admin"]),
    ApprovalMatrixTier(min_amount=10000.01, max_amount=50000, level=ApprovalLevel.SENIOR_MANAGER, required_roles=["senior_manager", "admin"]),
    ApprovalMatrixTier(min_amount=50000.01, max_amount=None, level=ApprovalLevel.DIRECTOR, required_roles=["director", "admin"]),
]
