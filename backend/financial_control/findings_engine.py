"""
📂 Findings Engine — Persistent audit findings with lifecycle.

Differs from firewall_engine in two key ways:
  1. Findings are PERSISTED (not regenerated every scan)
  2. Findings have a lifecycle: open → acknowledged → in_progress → resolved/dismissed

Idempotent: each finding has a deterministic 'signature' so re-running the
audit rules does not create duplicates — instead updates `last_seen_at`.

Storage: MongoDB collection 'fc_findings'.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from .models import Finding, FindingComment, FindingSeverity, FindingStatus, _now_iso

COLLECTION = "fc_findings"


def make_signature(*, rule_code: str, entity_type: Optional[str], entity_id: Optional[str], extra: Optional[str] = None) -> str:
    """Deterministic hash → idempotency key for a finding."""
    parts = [rule_code, entity_type or "", entity_id or "", extra or ""]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


class FindingsEngine:
    def __init__(self, db):
        self.db = db

    # ---------- ingest ----------
    async def upsert(self, finding: Finding) -> Finding:
        """Insert if new; otherwise refresh updated_at + evidence (preserves lifecycle)."""
        if not finding.signature:
            finding.signature = make_signature(
                rule_code=finding.rule_code,
                entity_type=finding.entity_type,
                entity_id=finding.entity_id,
            )
        existing = await self.db[COLLECTION].find_one(
            {"workshop_id": finding.workshop_id, "signature": finding.signature},
            {"_id": 0},
        )
        if existing:
            # Refresh evidence + impact but keep lifecycle (status, assignee, comments)
            now = _now_iso()
            await self.db[COLLECTION].update_one(
                {"id": existing["id"]},
                {"$set": {
                    "evidence": finding.evidence,
                    "financial_impact": finding.financial_impact,
                    "severity": finding.severity.value,
                    "description": finding.description,
                    "affected_accounts": finding.affected_accounts,
                    "related_entries": finding.related_entries,
                    "updated_at": now,
                }},
            )
            existing.update({
                "evidence": finding.evidence,
                "financial_impact": finding.financial_impact,
                "severity": finding.severity.value,
                "description": finding.description,
                "affected_accounts": finding.affected_accounts,
                "related_entries": finding.related_entries,
                "updated_at": now,
            })
            return Finding(**existing)
        await self.db[COLLECTION].insert_one(finding.dict())
        return finding

    async def bulk_upsert(self, findings: List[Finding]) -> Dict[str, int]:
        created = updated = 0
        for f in findings:
            if not f.signature:
                f.signature = make_signature(
                    rule_code=f.rule_code,
                    entity_type=f.entity_type,
                    entity_id=f.entity_id,
                )
            existing = await self.db[COLLECTION].find_one(
                {"workshop_id": f.workshop_id, "signature": f.signature}, {"_id": 0, "id": 1},
            )
            if existing:
                await self.upsert(f)
                updated += 1
            else:
                await self.db[COLLECTION].insert_one(f.dict())
                created += 1
        return {"created": created, "updated": updated, "total": len(findings)}

    # ---------- lifecycle ----------
    async def acknowledge(self, finding_id: str, actor: str, note: Optional[str] = None) -> Finding:
        return await self._transition(finding_id, FindingStatus.ACKNOWLEDGED, actor=actor, note=note)

    async def start(self, finding_id: str, actor: str, note: Optional[str] = None) -> Finding:
        return await self._transition(finding_id, FindingStatus.IN_PROGRESS, actor=actor, note=note)

    async def resolve(self, finding_id: str, *, actor: str, resolution: str) -> Finding:
        f = await self._load(finding_id)
        f.status = FindingStatus.RESOLVED
        f.resolution = resolution
        f.resolved_by = actor
        f.resolved_at = _now_iso()
        f.updated_at = _now_iso()
        await self._save(f)
        return f

    async def dismiss(self, finding_id: str, *, actor: str, reason: str) -> Finding:
        f = await self._load(finding_id)
        f.status = FindingStatus.DISMISSED
        f.resolution = reason
        f.resolved_by = actor
        f.resolved_at = _now_iso()
        f.updated_at = _now_iso()
        await self._save(f)
        return f

    async def assign(self, finding_id: str, *, assignee: str, due_date: Optional[str] = None) -> Finding:
        f = await self._load(finding_id)
        f.assignee = assignee
        if due_date:
            f.due_date = due_date
        f.updated_at = _now_iso()
        await self._save(f)
        return f

    async def comment(self, finding_id: str, *, author: str, text: str) -> Finding:
        f = await self._load(finding_id)
        f.comments.append(FindingComment(author=author, text=text))
        f.updated_at = _now_iso()
        await self._save(f)
        return f

    async def _transition(self, finding_id: str, new_status: FindingStatus, *, actor: str, note: Optional[str] = None) -> Finding:
        f = await self._load(finding_id)
        f.status = new_status
        if note:
            f.comments.append(FindingComment(author=actor, text=note))
        f.updated_at = _now_iso()
        await self._save(f)
        return f

    # ---------- queries ----------
    async def get(self, finding_id: str) -> Optional[Finding]:
        doc = await self.db[COLLECTION].find_one({"id": finding_id}, {"_id": 0})
        return Finding(**doc) if doc else None

    async def list(
        self,
        *,
        workshop_id: str = "finmodule-sync",
        status: Optional[FindingStatus] = None,
        severity: Optional[FindingSeverity] = None,
        rule_code: Optional[str] = None,
        assignee: Optional[str] = None,
        limit: int = 200,
    ) -> List[Finding]:
        query: Dict[str, Any] = {"workshop_id": workshop_id}
        if status:
            query["status"] = status.value
        if severity:
            query["severity"] = severity.value
        if rule_code:
            query["rule_code"] = rule_code
        if assignee:
            query["assignee"] = assignee
        rows = await self.db[COLLECTION].find(query, {"_id": 0}).sort("detected_at", -1).to_list(limit)
        return [Finding(**r) for r in rows]

    async def summary(self, *, workshop_id: str = "finmodule-sync") -> Dict[str, Any]:
        pipeline = [
            {"$match": {"workshop_id": workshop_id}},
            {"$group": {
                "_id": {"status": "$status", "severity": "$severity"},
                "count": {"$sum": 1},
                "impact": {"$sum": "$financial_impact"},
            }},
        ]
        agg = await self.db[COLLECTION].aggregate(pipeline).to_list(200)
        by_status: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        open_impact = 0.0
        for row in agg:
            st = row["_id"]["status"]
            sv = row["_id"]["severity"]
            by_status[st] = by_status.get(st, 0) + row["count"]
            by_severity[sv] = by_severity.get(sv, 0) + row["count"]
            if st in {"open", "acknowledged", "in_progress"}:
                open_impact += row.get("impact", 0)
        return {
            "by_status": by_status,
            "by_severity": by_severity,
            "open_count": by_status.get("open", 0) + by_status.get("acknowledged", 0) + by_status.get("in_progress", 0),
            "open_financial_impact": round(open_impact, 2),
            "total": sum(by_status.values()),
        }

    # ---------- internals ----------
    async def _load(self, finding_id: str) -> Finding:
        doc = await self.db[COLLECTION].find_one({"id": finding_id}, {"_id": 0})
        if not doc:
            raise LookupError(f"finding {finding_id} not found")
        return Finding(**doc)

    async def _save(self, f: Finding) -> None:
        await self.db[COLLECTION].update_one({"id": f.id}, {"$set": f.dict()})
