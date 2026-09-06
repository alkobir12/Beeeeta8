"""P1-SEC-UPLOAD + P0-DESTRUCTIVE-RESET-HARDENING regression tests.

Read-only with respect to the shared business database:
  * no business/financial record is created, updated or deleted
  * seed_database.py is never invoked
  * no reset endpoint is ever executed successfully (all paths are denials)
  * the only external write is a self-test blob under an isolated storage prefix
"""

import asyncio
import os
import sys
import uuid
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env", override=False)

from core import destructive_guard, object_storage  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"0" * 64
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 64
HEIC = b"\x00\x00\x00\x18" + b"ftyp" + b"heic" + b"\x00" * 64
TEXT = "code,name\nP0300,misfire\n".encode("utf-8")


def _xlsx_bytes() -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
    return buf.getvalue()


def _docx_bytes() -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    return buf.getvalue()


# ---------------------------------------------------------------- object keys
def test_object_key_never_contains_user_filename():
    key = object_storage.build_object_key("vehicle-files", "veh-1", "png")
    assert key.startswith("workshop-erp/vehicle-files/veh-1/")
    assert key.endswith(".png")
    assert not key.startswith("/")


@pytest.mark.parametrize(
    "hostile",
    ["../../etc/passwd", "..\\..\\windows\\system32", "/etc/shadow", "....//evil.png", "\x00evil"],
)
def test_path_traversal_cannot_escape(hostile):
    safe = object_storage.safe_basename(hostile)
    assert "/" not in safe and "\\" not in safe
    assert not safe.startswith(".")
    key = object_storage.build_object_key("vehicle-files", hostile, "png")
    assert ".." not in key
    assert key.count("/") == 3


def test_entity_id_is_sanitised_into_single_segment():
    key = object_storage.build_object_key("vehicle-files", "a/b/../c", "pdf")
    assert key.count("/") == 3
    assert ".." not in key


# ------------------------------------------------------------------ size gate
def test_oversize_upload_rejected_with_413():
    with pytest.raises(HTTPException) as exc:
        object_storage.validate_upload(
            b"\x89PNG\r\n\x1a\n" + b"0" * object_storage.MAX_UPLOAD_BYTES,
            "big.png",
            "image/png",
            "vehicle-files",
        )
    assert exc.value.status_code == 413
    assert exc.value.detail["error"] == "file_too_large"


def test_empty_upload_rejected():
    with pytest.raises(HTTPException) as exc:
        object_storage.validate_upload(b"", "x.png", "image/png", "vehicle-files")
    assert exc.value.status_code == 400


def test_limit_is_25mb():
    assert object_storage.MAX_UPLOAD_BYTES == 25 * 1024 * 1024


# ------------------------------------------------------------------ type gate
@pytest.mark.parametrize(
    "data,name",
    [(PNG, "a.png"), (JPEG, "a.jpg"), (PDF, "a.pdf"), (WEBP, "a.webp"), (HEIC, "a.heic")],
)
def test_accepted_types_are_magic_verified(data, name):
    result = object_storage.validate_upload(data, name, None, "vehicle-files")
    assert result["verification_level"] == "magic_verified"


def test_declared_content_type_alone_is_not_sufficient():
    # A text payload claiming to be a PNG must be rejected on content, not trusted.
    with pytest.raises(HTTPException) as exc:
        object_storage.validate_upload(b"not really a png at all", "evil.png", "image/png", "vehicle-files")
    assert exc.value.status_code == 415


def test_extension_content_mismatch_rejected():
    with pytest.raises(HTTPException) as exc:
        object_storage.validate_upload(PDF, "actually_a_pdf.png", "image/png", "vehicle-files")
    assert exc.value.status_code == 415
    assert exc.value.detail["error"] == "content_type_mismatch"


def test_disallowed_extension_rejected_per_surface():
    # No video in this batch, and executables are never acceptable.
    for name in ("clip.mp4", "payload.exe", "script.sh", "lib.so"):
        with pytest.raises(HTTPException) as exc:
            object_storage.validate_upload(PNG, name, "image/png", "vehicle-files")
        assert exc.value.status_code == 415
        assert exc.value.detail["error"] == "unsupported_file_type"


def test_office_containers_are_container_verified():
    xlsx = object_storage.validate_upload(_xlsx_bytes(), "book.xlsx", None, "references")
    assert xlsx["verification_level"] == "container_verified"
    docx = object_storage.validate_upload(_docx_bytes(), "doc.docx", None, "references")
    assert docx["verification_level"] == "container_verified"


def test_ooxml_subtype_mismatch_rejected():
    with pytest.raises(HTTPException) as exc:
        object_storage.validate_upload(_xlsx_bytes(), "pretend.docx", None, "references")
    assert exc.value.status_code == 415


def test_text_formats_use_declared_weaker_verification():
    result = object_storage.validate_upload(TEXT, "codes.csv", "text/csv", "references")
    assert result["verification_level"] == "text_heuristic"


def test_binary_masquerading_as_text_rejected():
    with pytest.raises(HTTPException) as exc:
        object_storage.validate_upload(b"\x00\x01\x02binary", "notes.txt", "text/plain", "references")
    assert exc.value.status_code == 415


def test_surface_policies_cover_every_migrated_surface():
    assert set(object_storage.SURFACE_POLICIES) == {
        "vehicle-files",
        "finance-audit-evidence",
        "operation-payment-receipts",
        "document-templates",
        "references",
    }
    for surface in ("vehicle-files", "finance-audit-evidence", "operation-payment-receipts"):
        assert "pdf" in object_storage.SURFACE_POLICIES[surface]
        assert "mp4" not in object_storage.SURFACE_POLICIES[surface]


# ------------------------------------------------------- durability round-trip
@pytest.mark.skipif(
    not (os.environ.get("EMERGENT_LLM_KEY") or "").strip(),
    reason="object storage not configured in this environment",
)
def test_storage_round_trip_is_durable():
    """Isolated self-test prefix only — never touches business data."""
    key = f"workshop-erp/_selftest/{uuid.uuid4().hex}.png"
    stored = asyncio.run(object_storage.put_object(key, PNG, "image/png"))
    assert stored["path"] == key
    data, content_type = asyncio.run(object_storage.get_object(key))
    assert data == PNG
    assert content_type.startswith("image/png")


# ------------------------------------------------ destructive reset guard
class _FakeRequest:
    def __init__(self, headers=None, query=None):
        self.headers = headers or {}
        self.query_params = query or {}


def _run(coro):
    return asyncio.run(coro)


def test_reset_denied_when_enable_flag_absent(monkeypatch):
    monkeypatch.delenv(destructive_guard.ENABLE_FLAG_ENV, raising=False)
    with pytest.raises(HTTPException) as exc:
        _run(destructive_guard.require_destructive_authorization(_FakeRequest(), "delete_all_operations", "DELETE_ALL"))
    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "destructive_operations_disabled"


def test_enable_flag_is_not_set_in_this_environment():
    """Contract: the flag is documented but never populated here."""
    assert (os.environ.get(destructive_guard.ENABLE_FLAG_ENV) or "").strip().lower() not in {
        "1", "true", "yes", "on"
    }


def test_reset_denied_when_database_not_authorized(monkeypatch):
    monkeypatch.setenv(destructive_guard.ENABLE_FLAG_ENV, "true")
    monkeypatch.delenv(destructive_guard.ALLOWED_DB_ENV, raising=False)
    with pytest.raises(HTTPException) as exc:
        _run(destructive_guard.require_destructive_authorization(_FakeRequest(), "delete_all_operations", "DELETE_ALL"))
    assert exc.value.detail["error"] == "destructive_database_not_authorized"


def test_reset_denied_when_database_name_mismatches(monkeypatch):
    monkeypatch.setenv(destructive_guard.ENABLE_FLAG_ENV, "true")
    monkeypatch.setenv("DB_NAME", "real_db")
    monkeypatch.setenv(destructive_guard.ALLOWED_DB_ENV, "some_other_db")
    with pytest.raises(HTTPException) as exc:
        _run(destructive_guard.require_destructive_authorization(_FakeRequest(), "delete_all_operations", "DELETE_ALL"))
    assert exc.value.detail["error"] == "destructive_database_not_authorized"


def test_reset_denied_for_non_admin_role(monkeypatch):
    monkeypatch.setenv(destructive_guard.ENABLE_FLAG_ENV, "true")
    monkeypatch.setenv("DB_NAME", "db1")
    monkeypatch.setenv(destructive_guard.ALLOWED_DB_ENV, "db1")

    class _Actor:
        role = "accountant"
        name = "احمد"
        id = "u2"

    async def _resolve(_request):
        return _Actor()

    monkeypatch.setattr(destructive_guard._authz, "resolve_request_actor", _resolve)
    with pytest.raises(HTTPException) as exc:
        _run(destructive_guard.require_destructive_authorization(_FakeRequest(), "delete_all_operations", "DELETE_ALL"))
    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "destructive_privilege_required"


def _admin(monkeypatch):
    monkeypatch.setenv(destructive_guard.ENABLE_FLAG_ENV, "true")
    monkeypatch.setenv("DB_NAME", "db1")
    monkeypatch.setenv(destructive_guard.ALLOWED_DB_ENV, "db1")

    class _Actor:
        role = "admin"
        name = "مدير"
        id = "u1"

    async def _resolve(_request):
        return _Actor()

    monkeypatch.setattr(destructive_guard._authz, "resolve_request_actor", _resolve)


def test_reset_denied_for_admin_without_confirmation(monkeypatch):
    _admin(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        _run(destructive_guard.require_destructive_authorization(_FakeRequest(), "delete_all_operations", None))
    assert exc.value.status_code == 428
    assert exc.value.detail["error"] == "destructive_confirmation_required"


def test_reset_denied_for_admin_without_double_confirmation(monkeypatch):
    _admin(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        _run(destructive_guard.require_destructive_authorization(_FakeRequest(), "delete_all_operations", "DELETE_ALL"))
    assert exc.value.status_code == 428
    assert exc.value.detail["error"] == "destructive_double_confirmation_required"


def test_reset_denied_when_double_confirmation_token_is_wrong_action(monkeypatch):
    _admin(monkeypatch)
    wrong = destructive_guard.expected_confirmation_token("reset_inventory")
    request = _FakeRequest(headers={destructive_guard.CONFIRM_HEADER: wrong})
    with pytest.raises(HTTPException) as exc:
        _run(destructive_guard.require_destructive_authorization(request, "delete_all_operations", "DELETE_ALL"))
    assert exc.value.detail["error"] == "destructive_double_confirmation_required"


def test_fully_authorized_path_returns_audit_context_with_correlation_id(monkeypatch):
    _admin(monkeypatch)
    token = destructive_guard.expected_confirmation_token("delete_all_operations")
    request = _FakeRequest(
        headers={destructive_guard.CONFIRM_HEADER: token, "X-Correlation-ID": "corr-123"}
    )
    ctx = _run(
        destructive_guard.require_destructive_authorization(request, "delete_all_operations", "DELETE_ALL")
    )
    assert ctx["correlation_id"] == "corr-123"
    assert ctx["actor_role"] == "admin"
    assert ctx["database"] == "db1"


def test_correlation_id_generated_when_header_absent(monkeypatch):
    _admin(monkeypatch)
    token = destructive_guard.expected_confirmation_token("reset_inventory")
    request = _FakeRequest(headers={destructive_guard.CONFIRM_HEADER: token})
    ctx = _run(destructive_guard.require_destructive_authorization(request, "reset_inventory", "DELETE_ALL"))
    assert ctx["correlation_id"].startswith("dc-")


# ------------------------------------------------------------- static contract
def _read(name: str) -> str:
    return (BACKEND_DIR / name).read_text(encoding="utf-8")


def test_migrated_surfaces_no_longer_write_uploads_to_container_disk():
    assert 'UPLOAD_DIR / "vehicles"' not in _read("server.py")
    assert "uploads/vehicles" not in _read("routes_vehicle_files.py")
    assert "uploads/finance_audit_evidence" not in _read("routes_finance_bot.py")
    templates = _read("routes_document_templates.py")
    assert "target.write_text(" not in templates
    assert "shutil.copyfileobj(file.file" not in templates
    # second templates router (prefix /api/templates)
    legacy_templates = _read("routes_templates.py")
    assert "shutil.copyfileobj(file.file" not in legacy_templates
    assert "temp_path.write_text(" not in legacy_templates
    # operation payment receipts (financial evidence class)
    extended = _read("routes_extended.py")
    assert 'os.path.join(os.path.dirname(__file__), "uploads", "operation_payment_receipts", op_id)' not in extended
    assert 'with open(file_path, "wb") as f:' not in extended


def test_every_persistent_upload_surface_uses_object_storage():
    assert "object_storage.put_object" in _read("routes_vehicle_files.py")
    assert "_object_storage.put_object" in _read("server.py")
    assert "object_storage.put_object" in _read("routes_finance_bot.py")
    assert "object_storage.put_object" in _read("routes_document_templates.py")
    assert "object_storage.put_object" in _read("routes_templates.py")
    assert "object_storage.put_object" in _read("routes_extended.py")


def test_payment_receipt_surface_is_policy_covered():
    assert "operation-payment-receipts" in object_storage.SURFACE_POLICIES
    allowed = object_storage.SURFACE_POLICIES["operation-payment-receipts"]
    assert "pdf" in allowed and "png" in allowed
    assert "mp4" not in allowed and "exe" not in allowed


def test_named_object_key_round_trips_safely():
    key = object_storage.build_named_object_key("operation-payment-receipts", "op-1", "20260101_abc.png")
    assert key == "workshop-erp/operation-payment-receipts/op-1/20260101_abc.png"
    hostile = object_storage.build_named_object_key("operation-payment-receipts", "op-1", "../../../etc/passwd")
    assert ".." not in hostile
    assert hostile.count("/") == 3


def test_reference_import_uses_managed_temp_dir_with_cleanup():
    source = _read("routes_references.py")
    assert "tempfile.TemporaryDirectory" in source
    assert 'Path("/tmp") / file.filename' not in source
    assert "uuid.uuid4().hex" in source


def test_no_token_is_ever_placed_in_a_file_url():
    """TOKEN_IN_FILE_URL must stay NO on every file-serving route."""
    for name in ("server.py", "routes_vehicle_files.py", "routes_finance_bot.py", "routes_document_templates.py"):
        source = _read(name)
        for forbidden in ("auth: str = Query", "token: str = Query", "access_token: str = Query", "?auth="):
            assert forbidden not in source, f"{name} exposes a token in a file URL"


def test_destructive_routes_are_guarded():
    assert "require_destructive_authorization" in _read("routes_extended.py")
    assert "require_destructive_authorization" in _read("server.py")


def test_seed_script_has_no_destructive_operations():
    seed = _read("seed_database.py")
    for forbidden in ("delete_many", "insert_many", ".drop(", "drop_database"):
        assert forbidden not in seed


def test_migration_script_is_dry_run_by_default():
    script = (BACKEND_DIR.parent / "scripts" / "migrate_local_uploads_to_object_storage.py").read_text()
    assert "--i-understand-this-writes" in script
    assert '"--dry-run", action="store_true", default=True' in script
    assert "source_files_deleted" in script
    for forbidden in ("os.remove", "shutil.rmtree", "unlink("):
        assert forbidden not in script
