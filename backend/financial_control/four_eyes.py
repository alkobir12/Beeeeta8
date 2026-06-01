"""
👁️ Four-Eyes Validator — enforces separation of duties.

Rules:
  • Creator ≠ Reviewer
  • Creator ≠ Approver
  • Reviewer ≠ Approver (when both exist)
  • Same role can hold all 3 only with explicit override + admin role

Use as a standalone guard before applying any privileged change, OR
through ApprovalEngine which already invokes the checks at each transition.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FourEyesViolation(Exception):
    code: str
    detail: str

    def __str__(self) -> str:  # type: ignore[override]
        return f"[{self.code}] {self.detail}"


class FourEyesValidator:
    """Pure-function validator — no I/O."""

    @staticmethod
    def check(
        *,
        creator: str,
        reviewer: Optional[str] = None,
        approver: Optional[str] = None,
        allow_admin_override: bool = False,
        actor_role: Optional[str] = None,
    ) -> None:
        """Raise FourEyesViolation on conflict; return None when clean."""
        if not creator:
            raise FourEyesViolation(code="creator_missing", detail="creator is required")

        # admin override (rare; only for emergency)
        admin = allow_admin_override and (actor_role or "").lower() == "admin"

        if reviewer and reviewer == creator and not admin:
            raise FourEyesViolation(
                code="four_eyes.creator_equals_reviewer",
                detail="المُراجِع لا يمكن أن يكون نفس مُنشئ العملية",
            )
        if approver and approver == creator and not admin:
            raise FourEyesViolation(
                code="four_eyes.creator_equals_approver",
                detail="المُعتمِد لا يمكن أن يكون نفس مُنشئ العملية",
            )
        if reviewer and approver and reviewer == approver and not admin:
            raise FourEyesViolation(
                code="four_eyes.reviewer_equals_approver",
                detail="المُعتمِد لا يمكن أن يكون نفس المُراجِع",
            )

    @staticmethod
    def is_clean(*, creator: str, reviewer: Optional[str] = None, approver: Optional[str] = None) -> bool:
        try:
            FourEyesValidator.check(creator=creator, reviewer=reviewer, approver=approver)
            return True
        except FourEyesViolation:
            return False
