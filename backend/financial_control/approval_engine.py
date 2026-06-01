"""
✅ Approval Engine — Matrix-based workflow for financial actions.

Workflow:
  1. caller submits ApprovalRequest with (entity_type, amount, creator)
  2. engine determines required_level from the matrix:
       0      ≤ amt ≤ 1000   → AUTO         (auto-approved immediately)
       1000   < amt ≤ 10000  → MANAGER      (1-step manager approval)
       10000  < amt ≤ 50000  → SENIOR_MANAGER (review + senior_manager approval)
       50000  < amt          → DIRECTOR     (review + director approval)
  3. status moves PENDING_REVIEW → PENDING_APPROVAL → APPROVED / REJECTED
  4. each transition is recorded with actor, role, note (audit-grade trail)

Storage: MongoDB collection 'fc_approval_requests' (in-process db reference).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import (
    ApprovalAction,
    ApprovalLevel,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalMatrixTier,
    DEFAULT_MATRIX,
    _now_iso,
)

COLLECTION = "fc_approval_requests"


class ApprovalEngine:
    """Manages approval lifecycle with auditable transitions."""

    def __init__(self, db, matrix: Optional[List[ApprovalMatrixTier]] = None):
        self.db = db
        self.matrix = matrix or DEFAULT_MATRIX

    # ---------- matrix ----------
    def classify(self, amount: float) -> ApprovalLevel:
        """Return required approval level for the given amount."""
        amt = abs(float(amount or 0))
        for tier in self.matrix:
            lo = tier.min_amount
            hi = tier.max_amount if tier.max_amount is not None else float("inf")
            if lo <= amt <= hi:
                return tier.level
        return ApprovalLevel.DIRECTOR  # safe-default for over-max

    def get_tier(self, level: ApprovalLevel) -> Optional[ApprovalMatrixTier]:
        for t in self.matrix:
            if t.level == level:
                return t
        return None

    def role_can_approve(self, role: Optional[str], level: ApprovalLevel) -> bool:
        if role == "admin":
            return True
        tier = self.get_tier(level)
        if not tier:
            return False
        if "any" in tier.required_roles:
            return True
        return (role or "").lower() in [r.lower() for r in tier.required_roles]

    # ---------- workflow ----------
    async def submit(
        self,
        *,
        entity_type: str,
        amount: float,
        creator: str,
        title: str,
        creator_role: Optional[str] = None,
        entity_id: Optional[str] = None,
        entity_payload: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        workshop_id: str = "finmodule-sync",
        idempotency_key: Optional[str] = None,
    ) -> ApprovalRequest:
        # Idempotency: return existing if same key
        if idempotency_key:
            existing = await self.db[COLLECTION].find_one(
                {"workshop_id": workshop_id, "idempotency_key": idempotency_key},
                {"_id": 0},
            )
            if existing:
                return ApprovalRequest(**existing)

        level = self.classify(amount)
        # Auto-approve flow → APPROVED instantly
        initial_status = ApprovalStatus.APPROVED if level == ApprovalLevel.AUTO else (
            ApprovalStatus.PENDING_APPROVAL if level == ApprovalLevel.MANAGER else ApprovalStatus.PENDING_REVIEW
        )

        req = ApprovalRequest(
            workshop_id=workshop_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_payload=entity_payload or {},
            amount=float(amount or 0),
            title=title,
            description=description,
            required_level=level,
            status=initial_status,
            creator=creator,
            creator_role=creator_role,
            idempotency_key=idempotency_key,
        )
        req.actions.append(ApprovalAction(
            action="create", actor=creator, actor_role=creator_role,
            note=f"Submitted at level {level.value} for {amount}",
        ))
        if initial_status == ApprovalStatus.APPROVED:
            req.completed_at = _now_iso()
            req.actions.append(ApprovalAction(
                action="auto_approve", actor="system", actor_role="system",
                note=f"Auto-approved (amount within AUTO tier ≤ {self._tier_max(ApprovalLevel.AUTO)})",
            ))
            req.approver = "system"

        await self.db[COLLECTION].insert_one(req.dict())
        return req

    def _tier_max(self, level: ApprovalLevel) -> float:
        t = self.get_tier(level)
        if not t or t.max_amount is None:
            return float("inf")
        return t.max_amount

    async def review(self, request_id: str, *, reviewer: str, reviewer_role: Optional[str] = None, note: Optional[str] = None) -> ApprovalRequest:
        req = await self._load(request_id)
        if req.status != ApprovalStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot review in status {req.status.value}")
        if reviewer == req.creator:
            raise ValueError("four_eyes: reviewer cannot equal creator")
        req.reviewer = reviewer
        req.status = ApprovalStatus.PENDING_APPROVAL
        req.updated_at = _now_iso()
        req.actions.append(ApprovalAction(
            action="review", actor=reviewer, actor_role=reviewer_role, note=note,
        ))
        await self._save(req)
        return req

    async def approve(self, request_id: str, *, approver: str, approver_role: Optional[str] = None, note: Optional[str] = None) -> ApprovalRequest:
        req = await self._load(request_id)
        if req.status not in {ApprovalStatus.PENDING_APPROVAL}:
            raise ValueError(f"Cannot approve in status {req.status.value}")
        if approver == req.creator:
            raise ValueError("four_eyes: approver cannot equal creator")
        if req.reviewer and approver == req.reviewer:
            raise ValueError("four_eyes: approver cannot equal reviewer")
        if not self.role_can_approve(approver_role, req.required_level):
            raise PermissionError(f"role '{approver_role}' is not authorized for level {req.required_level.value}")

        req.approver = approver
        req.status = ApprovalStatus.APPROVED
        req.updated_at = _now_iso()
        req.completed_at = _now_iso()
        req.actions.append(ApprovalAction(
            action="approve", actor=approver, actor_role=approver_role, note=note,
        ))
        await self._save(req)
        return req

    async def reject(self, request_id: str, *, actor: str, actor_role: Optional[str] = None, note: Optional[str] = None) -> ApprovalRequest:
        req = await self._load(request_id)
        if req.status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED}:
            raise ValueError(f"Cannot reject in terminal status {req.status.value}")
        req.status = ApprovalStatus.REJECTED
        req.updated_at = _now_iso()
        req.completed_at = _now_iso()
        req.actions.append(ApprovalAction(
            action="reject", actor=actor, actor_role=actor_role, note=note,
        ))
        await self._save(req)
        return req

    async def cancel(self, request_id: str, *, actor: str, note: Optional[str] = None) -> ApprovalRequest:
        req = await self._load(request_id)
        if req.status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED}:
            raise ValueError(f"Cannot cancel in terminal status {req.status.value}")
        req.status = ApprovalStatus.CANCELLED
        req.updated_at = _now_iso()
        req.completed_at = _now_iso()
        req.actions.append(ApprovalAction(
            action="cancel", actor=actor, note=note,
        ))
        await self._save(req)
        return req

    # ---------- queries ----------
    async def get(self, request_id: str) -> Optional[ApprovalRequest]:
        doc = await self.db[COLLECTION].find_one({"id": request_id}, {"_id": 0})
        return ApprovalRequest(**doc) if doc else None

    async def list(
        self,
        *,
        workshop_id: str = "finmodule-sync",
        status: Optional[ApprovalStatus] = None,
        creator: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[ApprovalRequest]:
        query: Dict[str, Any] = {"workshop_id": workshop_id}
        if status:
            query["status"] = status.value
        if creator:
            query["creator"] = creator
        if entity_type:
            query["entity_type"] = entity_type
        rows = await self.db[COLLECTION].find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
        return [ApprovalRequest(**r) for r in rows]

    async def stats(self, *, workshop_id: str = "finmodule-sync") -> Dict[str, Any]:
        pipeline = [
            {"$match": {"workshop_id": workshop_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}, "total_amount": {"$sum": "$amount"}}},
        ]
        agg = await self.db[COLLECTION].aggregate(pipeline).to_list(50)
        by_status = {row["_id"]: {"count": row["count"], "total_amount": row["total_amount"]} for row in agg}
        return {
            "by_status": by_status,
            "total": sum(v["count"] for v in by_status.values()),
            "pending": by_status.get("pending_review", {}).get("count", 0)
                      + by_status.get("pending_approval", {}).get("count", 0),
        }

    # ---------- internals ----------
    async def _load(self, request_id: str) -> ApprovalRequest:
        doc = await self.db[COLLECTION].find_one({"id": request_id}, {"_id": 0})
        if not doc:
            raise LookupError(f"approval_request {request_id} not found")
        return ApprovalRequest(**doc)

    async def _save(self, req: ApprovalRequest) -> None:
        await self.db[COLLECTION].update_one({"id": req.id}, {"$set": req.dict()})
