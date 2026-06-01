"""
💼 Financial Control Layer — Phase 1

Modules:
  • approval_engine — Matrix-based approval workflow
  • four_eyes       — Separation-of-duties validator (Creator ≠ Reviewer ≠ Approver)
  • findings_engine — Persistent findings store with lifecycle
  • audit_rules     — 7 enterprise audit rules
  • router          — FastAPI router (/api/financial-control)
"""

from .approval_engine import ApprovalEngine, ApprovalLevel
from .four_eyes import FourEyesValidator, FourEyesViolation
from .findings_engine import FindingsEngine, FindingStatus
from .audit_rules import AuditRulesEngine

__all__ = [
    "ApprovalEngine",
    "ApprovalLevel",
    "FourEyesValidator",
    "FourEyesViolation",
    "FindingsEngine",
    "FindingStatus",
    "AuditRulesEngine",
]
