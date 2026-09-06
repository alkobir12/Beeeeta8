#!/usr/bin/env python3
"""LEGACY FILES PRESERVATION MIGRATION — upload only, verified, never destructive.

Consumes the approved classification (scripts/classify_legacy_upload_files.py) and
copies every legacy on-disk upload into Emergent Object Storage.

Hard guarantees:
  * NEVER deletes or modifies a source file (source SHA-256 is re-checked afterwards)
  * NEVER changes a database reference — zero DB writes of any kind
  * NEVER overwrites an existing object with different content (reports CONFLICT)
  * idempotent — keys are content-addressed, so re-running yields SKIP_ALREADY_PRESENT
  * every upload is verified by downloading it back and comparing SHA-256
  * dry-run is the default; --apply additionally requires --i-understand-this-writes

Key layout:
  MIGRATE_NORMAL              -> workshop-erp/{surface}/{entity}/{sha16}-{name}
  MIGRATE_LEGACY_QUARANTINE   -> workshop-erp/legacy-quarantine/{surface}/{entity}/{sha16}-{name}
  payment receipts (NORMAL)   -> workshop-erp/operation-payment-receipts/{op_id}/{name}
                                 (the deterministic key the serving route already resolves)

Nothing here links an object back to its database record. Preserved objects are
unreachable from the API until a separately authorised linking step runs.
"""

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SCRIPTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPTS_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env", override=False)

from core import object_storage  # noqa: E402
from classify_legacy_upload_files import QUARANTINE_PREFIX, SURFACES, classify  # noqa: E402

MANIFEST_PATH = SCRIPTS_DIR.parent / "memory" / "discovery" / "LEGACY_FILES_PRESERVATION_MANIFEST.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def target_key(row: Dict[str, Any], sha: str) -> str:
    surface_key = SURFACES[row["surface"]]["storage_surface"]
    entity = row["related_entity"] or "unassigned"
    name = object_storage.safe_basename(Path(row["source_path"]).name)

    if row["surface"] == "payment_receipt" and row["proposed_action"] == "MIGRATE_NORMAL":
        # the receipt serving route resolves exactly this key
        return object_storage.build_named_object_key(surface_key, entity, name)

    if row["proposed_action"] == "MIGRATE_LEGACY_QUARANTINE":
        # nested private prefix — built directly because build_named_object_key
        # collapses "/" out of the surface segment
        entity_part = object_storage.re.sub(r"[^A-Za-z0-9_\-]", "-", str(entity)).strip("-") or "unassigned"
        return (
            f"{object_storage.APP_NAME}/{QUARANTINE_PREFIX}/{surface_key}/"
            f"{entity_part}/{sha[:16]}-{name}"
        )

    return object_storage.build_named_object_key(surface_key, entity, f"{sha[:16]}-{name}")


async def run(apply_changes: bool) -> Dict[str, Any]:
    classification = await classify()
    rows: List[Dict[str, Any]] = classification["files"]

    entries: List[Dict[str, Any]] = []
    totals = {
        "files": len(rows),
        "uploaded_verified": 0,
        "skip_already_present": 0,
        "conflict": 0,
        "failed": 0,
        "would_upload": 0,
        "bytes_uploaded": 0,
        "sources_unchanged": 0,
        "sources_modified": 0,
    }

    for row in rows:
        source = Path(row["source_path"])
        data = source.read_bytes()
        sha_source = sha256_bytes(data)
        assert sha_source == row["sha256"], f"classification SHA mismatch for {source}"

        key = target_key(row, sha_source)
        entry = {
            "source_path": str(source),
            "surface": row["surface"],
            "size": len(data),
            "sha256_source": sha_source,
            "object_key": key,
            "classified_action": row["proposed_action"],
            "financial_evidence": row["FINANCIAL_EVIDENCE"],
            "db_referenced": row["DB_REFERENCED"],
            "valid_under_new_policy": row["VALID_UNDER_NEW_POLICY"],
            "content_type": row["detected_actual_type"],
        }

        if not apply_changes:
            entry.update({"result": "WOULD_UPLOAD", "verified": False, "sha256_readback": None})
            totals["would_upload"] += 1
            entries.append(entry)
            continue

        existing = None
        try:
            existing, _ = await object_storage.get_object(key)
        except Exception:
            existing = None

        if existing is not None:
            if sha256_bytes(existing) == sha_source:
                entry.update({"result": "SKIP_ALREADY_PRESENT", "verified": True, "sha256_readback": sha_source})
                totals["skip_already_present"] += 1
            else:
                entry.update({
                    "result": "CONFLICT",
                    "verified": False,
                    "sha256_readback": sha256_bytes(existing),
                    "note": "object exists with different content — NOT overwritten",
                })
                totals["conflict"] += 1
            entries.append(entry)
            continue

        # content type is stored for fidelity; legacy files are preserved as-is
        media_type = row["detected_actual_type"]
        if media_type.startswith("video/unknown"):
            media_type = "application/octet-stream"

        try:
            await object_storage.put_object(key, data, media_type)
            readback, _ = await object_storage.get_object(key)
            sha_readback = sha256_bytes(readback)
        except Exception as exc:
            entry.update({"result": "FAILED", "verified": False, "sha256_readback": None, "error": str(exc)})
            totals["failed"] += 1
            entries.append(entry)
            continue

        verified = sha_readback == sha_source
        entry.update({
            "result": "UPLOADED_VERIFIED" if verified else "UPLOADED_UNVERIFIED",
            "verified": verified,
            "sha256_readback": sha_readback,
        })
        if verified:
            totals["uploaded_verified"] += 1
            totals["bytes_uploaded"] += len(data)
        else:
            totals["failed"] += 1
        entries.append(entry)

    # non-destructive proof: every source file must still exist with an identical hash
    for entry in entries:
        source = Path(entry["source_path"])
        if source.is_file() and sha256_bytes(source.read_bytes()) == entry["sha256_source"]:
            totals["sources_unchanged"] += 1
        else:
            totals["sources_modified"] += 1

    return {
        "mode": "APPLY" if apply_changes else "DRY_RUN",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files_deleted": 0,
        "files_moved": 0,
        "db_references_changed": 0,
        "db_writes": 0,
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

    if args.apply and not args.i_understand_this_writes:
        print("REFUSED: --apply also requires --i-understand-this-writes", file=sys.stderr)
        sys.exit(2)

    result = asyncio.run(run(bool(args.apply)))

    if args.apply:
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    t = result["totals"]
    print(f"MODE = {result['mode']}")
    print(f"files={t['files']} uploaded_verified={t['uploaded_verified']} "
          f"skip_already_present={t['skip_already_present']} conflict={t['conflict']} "
          f"failed={t['failed']} would_upload={t['would_upload']}")
    print(f"bytes_uploaded={t['bytes_uploaded']} sources_unchanged={t['sources_unchanged']} "
          f"sources_modified={t['sources_modified']}")
    print(f"files_deleted={result['files_deleted']} files_moved={result['files_moved']} "
          f"db_references_changed={result['db_references_changed']} db_writes={result['db_writes']}")
    for entry in result["entries"]:
        flag = "OK " if entry.get("verified") else "!! "
        print(f"  {flag}[{entry['result']}] {entry['surface']} :: {entry['source_path']}")
        print(f"      -> {entry['object_key']}")
        print(f"      sha_source={entry['sha256_source'][:16]}… sha_readback="
              f"{(entry.get('sha256_readback') or '-')[:16]}…")
    if args.apply:
        print(f"\nmanifest written: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
