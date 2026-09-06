#!/usr/bin/env python3
"""READ-ONLY classification of legacy on-disk upload files.

Moves nothing. Uploads nothing. Changes no database reference. Deletes nothing.

Decision rules (as approved):
  * "invalid under the NEW upload policy" is NEVER a reason to delete or lose an old file
  * any legacy finance_audit_evidence or payment_receipt is EVIDENCE and must be preserved
    even when modern content validation fails
  * invalid-but-must-keep files are proposed into a private `legacy-quarantine/` prefix that
    is not retrievable through the normal endpoints
  * orphan does NOT mean delete

Usage:
    python3 scripts/classify_legacy_upload_files.py
    python3 scripts/classify_legacy_upload_files.py --json
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env", override=False)

from core import object_storage  # noqa: E402

QUARANTINE_PREFIX = "legacy-quarantine"

SURFACES = {
    "vehicle": {
        "root": BACKEND_DIR / "uploads" / "vehicles",
        "storage_surface": "vehicle-files",
        "financial_evidence": False,
    },
    "finance_audit_evidence": {
        "root": BACKEND_DIR / "uploads" / "finance_audit_evidence",
        "storage_surface": "finance-audit-evidence",
        "financial_evidence": True,
    },
    "payment_receipt": {
        "root": BACKEND_DIR / "uploads" / "operation_payment_receipts",
        "storage_surface": "operation-payment-receipts",
        "financial_evidence": True,
    },
    "template": {
        "root": BACKEND_DIR / "custom_templates",
        "storage_surface": "document-templates",
        "financial_evidence": False,
    },
}


# ----------------------------------------------------------------- detection
_MEDIA_BRANDS = {
    b"qt  ": "video/quicktime",
    b"mp42": "video/mp4",
    b"mp41": "video/mp4",
    b"isom": "video/mp4",
    b"M4V ": "video/x-m4v",
}


def detect_actual_type(data: bytes) -> str:
    """Reporting-only detection. Broader than the upload policy on purpose."""
    sniffed, level = object_storage.sniff_content_type(data)
    if sniffed:
        return sniffed
    if data[4:8] == b"ftyp":
        return _MEDIA_BRANDS.get(data[8:12], f"video/unknown({data[8:12]!r})")
    if level == "text_heuristic":
        head = data[:200].decode("utf-8", errors="replace").lstrip().lower()
        if head.startswith("<!doctype html") or head.startswith("<html"):
            return "text/html"
        return "text/plain"
    return "application/octet-stream"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ------------------------------------------------------------ reference maps
def _json_store(name: str) -> List[Dict[str, Any]]:
    path = BACKEND_DIR / "uploads" / f"{name}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


async def _mongo():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        return None
    from motor.motor_asyncio import AsyncIOMotorClient

    return AsyncIOMotorClient(mongo_url)[db_name]


def _supabase():
    try:
        from supabase_service import SupabaseService

        service = SupabaseService()
        if getattr(service, "mock_mode", False) or not getattr(service, "client", None):
            return None
        return service.client
    except Exception:
        return None


async def build_reference_index() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """path/basename -> {entity, record_id, source}. Read-only."""
    index: Dict[str, Dict[str, Dict[str, Any]]] = {k: {} for k in SURFACES}

    # vehicle files live in the JSON runtime store (mongo collection absent)
    for row in _json_store("vehicle_files"):
        for key in (str(row.get("filePath") or ""), Path(str(row.get("filePath") or "")).name):
            if key:
                index["vehicle"][key] = {
                    "entity": row.get("vehicleId"),
                    "record_id": row.get("id"),
                    "source": "uploads/vehicle_files.json",
                }

    db = await _mongo()
    if db is not None:
        async for row in db.finance_audit_evidence.find({}, {"_id": 0}):
            for key in (str(row.get("file_path") or ""), Path(str(row.get("file_path") or "")).name):
                if key:
                    index["finance_audit_evidence"][key] = {
                        "entity": row.get("finding_id") or row.get("session_id"),
                        "record_id": row.get("evidence_id"),
                        "source": "mongo:finance_audit_evidence",
                    }
        async for row in db.document_templates.find({"filename": {"$exists": True}}, {"_id": 0}):
            key = str(row.get("filename") or "")
            if key:
                index["template"][key] = {
                    "entity": row.get("document_type") or row.get("type"),
                    "record_id": row.get("id"),
                    "source": "mongo:document_templates",
                }

    for row in _json_store("custom_templates_index"):
        key = str(row.get("filename") or "")
        if key:
            index["template"][key] = {
                "entity": row.get("type"),
                "record_id": row.get("id"),
                "source": "uploads/custom_templates_index.json",
            }

    return index


def payment_receipt_reference(client, op_id: str, filename: str) -> Optional[Dict[str, Any]]:
    """A receipt is referenced by its owning journal entry description (read-only)."""
    if client is None:
        return None
    try:
        rows = (
            client.table("journal_entries")
            .select("id,reference_id,description")
            .eq("reference_id", op_id)
            .limit(50)
            .execute()
            .data
            or []
        )
    except Exception:
        return None
    for row in rows:
        if filename in str(row.get("description") or ""):
            return {"entity": op_id, "record_id": row.get("id"), "source": "supabase:journal_entries.description"}
    if rows:
        return {"entity": op_id, "record_id": rows[0].get("id"), "source": "supabase:journal_entries(reference_id only)"}
    return None


def entity_exists(client, surface: str, entity: Optional[str]) -> str:
    """Does the OWNING entity still exist? Separate signal from a record-level reference."""
    if not entity:
        return "N/A"
    if surface == "payment_receipt":
        table, column = "operations", "id"
    elif surface == "vehicle":
        table, column = "vehicles", "id"
    else:
        return "N/A"
    if client is None:
        return "UNKNOWN"
    try:
        rows = client.table(table).select(column).eq(column, entity).limit(1).execute().data or []
        return "YES" if rows else "NO"
    except Exception:
        return "UNKNOWN"


# ------------------------------------------------------------- classification
def propose_action(financial: bool, valid: bool, referenced: bool) -> Tuple[str, str]:
    if financial:
        if valid:
            return "MIGRATE_NORMAL", "دليل مالي صالح — يُرحَّل عادياً"
        return "MIGRATE_LEGACY_QUARANTINE", "دليل مالي يجب حفظه رغم فشل التحقق الحديث"
    if valid and referenced:
        return "MIGRATE_NORMAL", "صالح ومرجعي — يُرحَّل عادياً"
    if valid and not referenced:
        return "MIGRATE_LEGACY_QUARANTINE", "صالح لكن يتيم — يُحفظ دون تعريضه للمستخدمين"
    if referenced:
        return "MIGRATE_LEGACY_QUARANTINE", "غير صالح لكن مرجعي — يُحفظ محجوزاً"
    return "HOLD_FOR_REVIEW", "غير صالح ويتيم — قرار بشري، ولا يُحذف"


async def classify() -> Dict[str, Any]:
    index = await build_reference_index()
    supabase_client = _supabase()
    rows: List[Dict[str, Any]] = []

    for surface, config in SURFACES.items():
        root: Path = config["root"]
        if not root.is_dir():
            continue
        for source in sorted(p for p in root.rglob("*") if p.is_file()):
            data = source.read_bytes()
            entity = source.parent.name if source.parent != root else None
            declared_ext = source.suffix.lower().lstrip(".")
            declared_type = object_storage.EXT_MIME.get(declared_ext, "unknown")
            actual_type = detect_actual_type(data)

            try:
                checked = object_storage.validate_upload(
                    data, source.name, None, config["storage_surface"]
                )
                valid = True
                invalid_reason = None
                verification = checked["verification_level"]
                normal_key = object_storage.build_object_key(
                    config["storage_surface"], entity or "unassigned", checked["ext"]
                )
            except Exception as exc:
                valid = False
                detail = getattr(exc, "detail", None)
                invalid_reason = detail if isinstance(detail, dict) else {"error": str(exc)}
                verification = "unverifiable"
                normal_key = None

            reference = index[surface].get(str(source)) or index[surface].get(source.name)
            if reference is None and surface == "payment_receipt":
                reference = payment_receipt_reference(supabase_client, entity or "", source.name)

            referenced = reference is not None
            financial = bool(config["financial_evidence"])
            action, rationale = propose_action(financial, valid, referenced)

            if action == "MIGRATE_LEGACY_QUARANTINE" or action == "HOLD_FOR_REVIEW":
                proposed_key = (
                    f"{object_storage.APP_NAME}/{QUARANTINE_PREFIX}/{config['storage_surface']}/"
                    f"{entity or 'unassigned'}/{object_storage.safe_basename(source.name)}"
                )
            else:
                proposed_key = normal_key
            if surface == "payment_receipt" and action == "MIGRATE_NORMAL":
                # the serving route resolves this key deterministically
                proposed_key = object_storage.build_named_object_key(
                    config["storage_surface"], entity or "unassigned", source.name
                )

            rows.append({
                "source_path": str(source),
                "surface": surface,
                "size": len(data),
                "sha256": sha256_of(source),
                "detected_actual_type": actual_type,
                "declared_legacy_type": f"{declared_ext or 'none'} => {declared_type}",
                "content_verification": verification,
                "VALID_UNDER_NEW_POLICY": "YES" if valid else "NO",
                "invalid_reason": invalid_reason,
                "DB_REFERENCED": "YES" if referenced else "NO",
                "ENTITY_EXISTS": entity_exists(supabase_client, surface, entity),
                "reference": reference,
                "related_entity": entity,
                "FINANCIAL_EVIDENCE": "YES" if financial else "NO",
                "proposed_object_key": proposed_key,
                "proposed_action": action,
                "rationale": rationale,
            })

    matrix: Dict[str, int] = {}
    for row in rows:
        cell = "|".join([
            row["surface"],
            "referenced" if row["DB_REFERENCED"] == "YES" else "orphan",
            "valid" if row["VALID_UNDER_NEW_POLICY"] == "YES" else "invalid",
            "financial" if row["FINANCIAL_EVIDENCE"] == "YES" else "non-financial",
        ])
        matrix[cell] = matrix.get(cell, 0) + 1

    actions: Dict[str, int] = {}
    for row in rows:
        actions[row["proposed_action"]] = actions.get(row["proposed_action"], 0) + 1

    return {
        "mode": "READ_ONLY_CLASSIFICATION",
        "files_moved": 0,
        "files_deleted": 0,
        "db_references_changed": 0,
        "objects_uploaded": 0,
        "totals": {
            "files": len(rows),
            "bytes": sum(r["size"] for r in rows),
            "valid": sum(1 for r in rows if r["VALID_UNDER_NEW_POLICY"] == "YES"),
            "invalid": sum(1 for r in rows if r["VALID_UNDER_NEW_POLICY"] == "NO"),
            "referenced": sum(1 for r in rows if r["DB_REFERENCED"] == "YES"),
            "orphan": sum(1 for r in rows if r["DB_REFERENCED"] == "NO"),
            "financial_evidence": sum(1 for r in rows if r["FINANCIAL_EVIDENCE"] == "YES"),
        },
        "proposed_actions": actions,
        "matrix_surface_x_reference_x_validity_x_financial": matrix,
        "files": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(classify())

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    t = result["totals"]
    print(f"MODE = {result['mode']}  (moved={result['files_moved']} deleted={result['files_deleted']} "
          f"db_refs_changed={result['db_references_changed']} uploaded={result['objects_uploaded']})")
    print(f"files={t['files']} bytes={t['bytes']} valid={t['valid']} invalid={t['invalid']} "
          f"referenced={t['referenced']} orphan={t['orphan']} financial_evidence={t['financial_evidence']}")
    print("proposed:", result["proposed_actions"])
    print()
    for row in result["files"]:
        print(f"[{row['proposed_action']}] {row['surface']} :: {row['source_path']}")
        print(f"    size={row['size']} sha256={row['sha256'][:16]}… actual={row['detected_actual_type']} "
              f"declared={row['declared_legacy_type']}")
        print(f"    valid={row['VALID_UNDER_NEW_POLICY']} referenced={row['DB_REFERENCED']} "
              f"entity_exists={row['ENTITY_EXISTS']} financial={row['FINANCIAL_EVIDENCE']} "
              f"entity={row['related_entity']}")
        if row["invalid_reason"]:
            print(f"    invalid_reason={row['invalid_reason']}")
        print(f"    proposed_key={row['proposed_object_key']}")
        print(f"    rationale={row['rationale']}")
    print()
    print("MATRIX surface | referenced/orphan | valid/invalid | financial/non-financial")
    for cell, count in sorted(result["matrix_surface_x_reference_x_validity_x_financial"].items()):
        print(f"  {cell} = {count}")


if __name__ == "__main__":
    main()
