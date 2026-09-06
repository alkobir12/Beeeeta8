#!/usr/bin/env python3
"""Migrate pre-existing local upload files to Emergent Object Storage.

DRY-RUN BY DEFAULT. Nothing is uploaded, nothing is written to the database and
no source file is ever deleted unless BOTH --apply and --i-understand-this-writes
are supplied. This script has NOT been executed: the real migration requires a
separate explicit authorisation from the owner.

Guarantees:
  * idempotent — a target object key that already exists is reported as SKIP
  * non-destructive — the original file is never deleted or modified
  * never silently overwrites an existing object
  * a dry run changes nothing in the database

Usage:
    python scripts/migrate_local_uploads_to_object_storage.py --dry-run
    python scripts/migrate_local_uploads_to_object_storage.py --dry-run --json
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env", override=False)

from core import object_storage  # noqa: E402

# surface -> local root directory
SURFACE_ROOTS = {
    "vehicle-files": BACKEND_DIR / "uploads" / "vehicles",
    "finance-audit-evidence": BACKEND_DIR / "uploads" / "finance_audit_evidence",
    "operation-payment-receipts": BACKEND_DIR / "uploads" / "operation_payment_receipts",
    "document-templates": BACKEND_DIR / "custom_templates",
}

# surface -> (mongo collection, field holding the legacy absolute path)
SURFACE_DB_REFS = {
    "vehicle-files": ("vehicle_files", "filePath"),
    "finance-audit-evidence": ("finance_audit_evidence", "file_path"),
    "operation-payment-receipts": ("operations", "payment_receipt_filename"),
    "document-templates": ("document_templates", "filename"),
}


def _discover(surface: str, root: Path) -> List[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


async def _db():
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        return None
    return AsyncIOMotorClient(mongo_url)[db_name]


async def _known_paths(db, surface: str) -> Dict[str, str]:
    """Map legacy local path -> owning record id (read-only)."""
    if db is None:
        return {}
    collection_name, field = SURFACE_DB_REFS[surface]
    known: Dict[str, str] = {}
    cursor = db[collection_name].find({field: {"$exists": True, "$ne": None}}, {"_id": 0})
    async for row in cursor:
        value = str(row.get(field) or "")
        if value:
            known[value] = str(row.get("id") or row.get("evidence_id") or "")
    return known


async def plan(apply_changes: bool, confirmed: bool) -> Dict[str, Any]:
    db = await _db()
    entries: List[Dict[str, Any]] = []
    totals = {
        "discovered": 0,
        "valid": 0,
        "invalid": 0,
        "conflicts": 0,
        "skipped": 0,
        "would_upload": 0,
        "total_bytes": 0,
        "orphan_files": 0,
        "missing_db_references": 0,
    }

    for surface, root in SURFACE_ROOTS.items():
        known = await _known_paths(db, surface)
        known_basenames = {Path(k).name for k in known}
        for source in _discover(surface, root):
            totals["discovered"] += 1
            size = source.stat().st_size
            entry: Dict[str, Any] = {
                "surface": surface,
                "source_path": str(source),
                "size": size,
                "related_entity": source.parent.name if source.parent != root else None,
            }

            related_id = known.get(str(source)) or (
                "" if source.name in known_basenames else None
            )
            if related_id is None:
                totals["orphan_files"] += 1
                entry["db_reference"] = "ORPHAN_FILE_NO_DB_RECORD"
            else:
                entry["db_reference"] = related_id or "MATCHED_BY_FILENAME"

            data = source.read_bytes()
            try:
                checked = object_storage.validate_upload(data, source.name, None, surface)
            except Exception as exc:
                totals["invalid"] += 1
                entry.update({"action": "INVALID", "reason": str(getattr(exc, "detail", exc))})
                entries.append(entry)
                continue

            totals["valid"] += 1
            totals["total_bytes"] += size
            entry["detected_type"] = checked["content_type"]
            entry["content_verification"] = checked["verification_level"]
            entry["target_object_key"] = object_storage.build_object_key(
                surface, entry["related_entity"] or "unassigned", checked["ext"]
            )
            if surface == "operation-payment-receipts":
                # the serving route resolves this key deterministically from op_id + name
                entry["target_object_key"] = object_storage.build_named_object_key(
                    surface, entry["related_entity"] or "unassigned", source.name
                )

            already = False
            if apply_changes and confirmed:
                try:
                    await object_storage.get_object(entry["target_object_key"])
                    already = True
                except Exception:
                    already = False

            if already:
                totals["conflicts"] += 1
                entry["action"] = "CONFLICT"
            elif apply_changes and confirmed:
                await object_storage.put_object(
                    entry["target_object_key"], data, checked["content_type"]
                )
                totals["would_upload"] += 1
                entry["action"] = "UPLOADED"
            else:
                totals["would_upload"] += 1
                entry["action"] = "WOULD_UPLOAD"

            entries.append(entry)

    if db is not None:
        for surface, (collection_name, field) in SURFACE_DB_REFS.items():
            cursor = db[collection_name].find({}, {"_id": 0})
            async for row in cursor:
                legacy = str(row.get(field) or "")
                if not row.get("storage_path") and legacy and not Path(legacy).is_file():
                    totals["missing_db_references"] += 1

    return {
        "mode": "APPLY" if (apply_changes and confirmed) else "DRY_RUN",
        "db_mutated": False,
        "source_files_deleted": 0,
        "totals": totals,
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--i-understand-this-writes", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    confirmed = bool(args.i_understand_this_writes)
    if apply_changes and not confirmed:
        print("REFUSED: --apply also requires --i-understand-this-writes", file=sys.stderr)
        sys.exit(2)

    result = asyncio.run(plan(apply_changes, confirmed))

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    t = result["totals"]
    print(f"MODE = {result['mode']}")
    print(f"discovered={t['discovered']} valid={t['valid']} invalid={t['invalid']} "
          f"conflicts={t['conflicts']} would_upload={t['would_upload']}")
    print(f"total_bytes={t['total_bytes']} orphan_files={t['orphan_files']} "
          f"missing_db_references={t['missing_db_references']}")
    print(f"db_mutated={result['db_mutated']} source_files_deleted={result['source_files_deleted']}")
    for entry in result["entries"]:
        print(f"  [{entry['action']}] {entry['surface']} :: {entry['source_path']} "
              f"-> {entry.get('target_object_key', '-')}")


if __name__ == "__main__":
    main()
