"""LEGACY FILES PRESERVATION MIGRATION — post-migration invariants.

Asserts against the real manifest and real object storage. Performs no DB write,
no deletion, and no reset.
"""

import asyncio
import hashlib
import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env", override=False)

from core import object_storage  # noqa: E402

MANIFEST = APP_DIR / "memory" / "discovery" / "LEGACY_FILES_PRESERVATION_MANIFEST.json"
CLASSIFICATION = APP_DIR / "memory" / "discovery" / "LEGACY_UPLOAD_FILES_CLASSIFICATION.json"
SCRIPT = APP_DIR / "scripts" / "preserve_legacy_upload_files.py"

EXPECTED_FILES = 28
EXPECTED_BYTES = 21_945_944


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_exists_and_covers_every_legacy_file(manifest):
    assert manifest["mode"] == "APPLY"
    assert manifest["totals"]["files"] == EXPECTED_FILES
    assert len(manifest["entries"]) == EXPECTED_FILES


def test_migration_was_non_destructive(manifest):
    assert manifest["files_deleted"] == 0
    assert manifest["files_moved"] == 0
    assert manifest["db_references_changed"] == 0
    assert manifest["db_writes"] == 0
    assert manifest["totals"]["sources_modified"] == 0
    assert manifest["totals"]["sources_unchanged"] == EXPECTED_FILES


def test_every_entry_is_verified_by_sha256(manifest):
    for entry in manifest["entries"]:
        assert entry["verified"] is True, entry["source_path"]
        assert entry["sha256_readback"] == entry["sha256_source"], entry["source_path"]
        assert entry["result"] in {"UPLOADED_VERIFIED", "SKIP_ALREADY_PRESENT"}


def test_no_conflicts_and_no_failures(manifest):
    assert manifest["totals"]["conflict"] == 0
    assert manifest["totals"]["failed"] == 0


def test_every_source_file_still_exists_with_the_same_hash(manifest):
    for entry in manifest["entries"]:
        source = Path(entry["source_path"])
        assert source.is_file(), f"source disappeared: {source}"
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        assert actual == entry["sha256_source"], f"source mutated: {source}"


def test_total_preserved_bytes_match_the_classification(manifest):
    assert sum(e["size"] for e in manifest["entries"]) == EXPECTED_BYTES


def test_object_keys_are_unique_and_well_formed(manifest):
    keys = [e["object_key"] for e in manifest["entries"]]
    assert len(set(keys)) == EXPECTED_FILES
    for key in keys:
        assert key.startswith(f"{object_storage.APP_NAME}/")
        assert ".." not in key
        assert not key.startswith("/")
        assert "//" not in key


def test_quarantined_files_use_the_private_nested_prefix(manifest):
    quarantined = [e for e in manifest["entries"] if e["classified_action"] == "MIGRATE_LEGACY_QUARANTINE"]
    assert len(quarantined) == 17
    for entry in quarantined:
        assert entry["object_key"].startswith(f"{object_storage.APP_NAME}/legacy-quarantine/")


def test_normally_migrated_files_use_their_surface_prefix(manifest):
    normal = [e for e in manifest["entries"] if e["classified_action"] == "MIGRATE_NORMAL"]
    assert len(normal) == 11
    for entry in normal:
        assert "legacy-quarantine" not in entry["object_key"]


def test_quarantine_prefix_is_unreachable_from_application_code():
    hits = []
    for root in (BACKEND_DIR, APP_DIR / "frontend" / "src"):
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".js", ".jsx"} or not path.is_file():
                continue
            rel = path.as_posix()
            if "/tests/" in rel or "/scripts/" in rel:
                continue
            if "legacy-quarantine" in path.read_text(encoding="utf-8", errors="replace"):
                hits.append(rel)
    assert not hits, f"quarantine prefix is referenced by application code: {hits}"


def test_all_financial_evidence_was_preserved(manifest):
    financial = [e for e in manifest["entries"] if e["financial_evidence"] == "YES"]
    assert len(financial) == 15
    for entry in financial:
        assert entry["verified"] is True
        # invalid-under-new-policy evidence must still have been preserved
        assert entry["result"] in {"UPLOADED_VERIFIED", "SKIP_ALREADY_PRESENT"}
    assert sum(1 for e in financial if e["valid_under_new_policy"] == "NO") == 14


def test_migrated_payment_receipt_uses_the_key_the_serving_route_resolves(manifest):
    receipts = [
        e for e in manifest["entries"]
        if e["surface"] == "payment_receipt" and e["classified_action"] == "MIGRATE_NORMAL"
    ]
    assert len(receipts) == 1
    entry = receipts[0]
    op_id = Path(entry["source_path"]).parent.name
    filename = Path(entry["source_path"]).name
    assert entry["object_key"] == object_storage.build_named_object_key(
        "operation-payment-receipts", op_id, filename
    )


def test_objects_are_actually_retrievable_from_storage(manifest):
    """Independent durability proof: pull a sample straight out of object storage."""
    sample = manifest["entries"][:2] + manifest["entries"][-2:]
    for entry in sample:
        data, _ = asyncio.run(object_storage.get_object(entry["object_key"]))
        assert hashlib.sha256(data).hexdigest() == entry["sha256_source"], entry["object_key"]


def test_script_is_non_destructive_by_construction():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("os.remove", "shutil.rmtree", "shutil.move", ".unlink(", "insert_one", "update_one", "delete_one", "delete_many"):
        assert forbidden not in source, f"preservation script contains {forbidden}"
    assert "--i-understand-this-writes" in source
    assert '"--dry-run", action="store_true", default=True' in source


def test_classification_and_manifest_agree(manifest):
    classification = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    by_path = {r["source_path"]: r for r in classification["files"]}
    assert len(by_path) == EXPECTED_FILES
    for entry in manifest["entries"]:
        row = by_path[entry["source_path"]]
        assert row["sha256"] == entry["sha256_source"]
        assert row["proposed_action"] == entry["classified_action"]
        assert row["FINANCIAL_EVIDENCE"] == entry["financial_evidence"]
