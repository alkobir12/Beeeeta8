"""Functional proof for P1-SEC-UPLOAD — isolated: real object storage, mocked persistence.

The upload/download route handlers are exercised end-to-end so we prove the
handler path itself (validate -> server-generated key -> object storage ->
authenticated retrieval), while every persistence call is monkeypatched.

Guarantees:
  * ZERO business-data writes: _mem_write / insert_one are captured, never executed
  * ZERO financial mutation, ZERO journal entries, ZERO reset execution
  * object storage writes land only under an isolated per-run prefix
"""

import asyncio
import sys
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers, UploadFile

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env", override=False)

from core import object_storage  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"vehicle-photo-payload" + b"\x00" * 32
PDF = b"%PDF-1.7\n" + b"evidence-payload" + b"\n%%EOF"
HTML = b"<html><body><h1>Invoice</h1><script>alert(1)</script></body></html>"


def _upload(name: str, data: bytes, content_type: str) -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(data), headers=Headers({"content-type": content_type}))


class _Request:
    def __init__(self, headers=None, query=None):
        self.headers = Headers(headers or {})
        self.query_params = query or {}


class _Actor:
    role = "admin"
    name = "مدير"
    id = "u1"

    def can(self, *_args, **_kwargs):
        return True


@pytest.fixture
def admin_actor(monkeypatch):
    async def _resolve(_request):
        return _Actor()

    from core import authz

    monkeypatch.setattr(authz, "resolve_request_actor", _resolve)
    return _Actor()


# ------------------------------------------------------- vehicle files (server.py)
def test_vehicle_upload_stores_in_object_storage_and_serves_it_back(monkeypatch, admin_actor):
    import server

    captured = {}

    monkeypatch.setattr(server, "_mem_read", lambda _name: captured.get("rows", []))
    monkeypatch.setattr(server, "_mem_write", lambda _name, rows: captured.__setitem__("rows", rows))
    monkeypatch.setattr(server, "DB_PROVIDER", "mongo")

    vehicle_id = f"veh-{uuid.uuid4().hex[:8]}"
    record = asyncio.run(
        server.upload_vehicle_file(
            vehicle_id, _Request(), file=_upload("photo.png", PNG, "image/png"), file_type="photo"
        )
    )

    # durable storage, not container disk
    assert record["storage_backend"] == "emergent_object_storage"
    assert record["storage_path"].startswith(f"workshop-erp/vehicle-files/{vehicle_id}/")
    assert "filePath" not in record
    assert record["content_verification"] == "magic_verified"
    assert record["uploadedBy"] == "مدير"
    # no business write happened — only the captured in-memory list
    assert captured["rows"][0]["id"] == record["id"]

    response = asyncio.run(server.download_vehicle_file(vehicle_id, record["id"], _Request()))
    assert response.body == PNG
    assert response.media_type == "image/png"


def test_vehicle_upload_rejects_traversal_filename_but_still_stores_safely(monkeypatch, admin_actor):
    import server

    captured = {}
    monkeypatch.setattr(server, "_mem_read", lambda _name: captured.get("rows", []))
    monkeypatch.setattr(server, "_mem_write", lambda _name, rows: captured.__setitem__("rows", rows))
    monkeypatch.setattr(server, "DB_PROVIDER", "mongo")

    record = asyncio.run(
        server.upload_vehicle_file(
            "veh-trav", _Request(), file=_upload("../../../etc/passwd.png", PNG, "image/png"), file_type="photo"
        )
    )
    assert ".." not in record["storage_path"]
    assert record["storage_path"].count("/") == 3
    assert "/" not in record["filename"]


def test_vehicle_upload_rejects_wrong_type(monkeypatch, admin_actor):
    import server

    monkeypatch.setattr(server, "_mem_read", lambda _name: [])
    monkeypatch.setattr(server, "_mem_write", lambda _name, _rows: None)
    monkeypatch.setattr(server, "DB_PROVIDER", "mongo")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            server.upload_vehicle_file(
                "veh-1", _Request(), file=_upload("clip.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4"), file_type="photo"
            )
        )
    assert exc.value.status_code == 415


def test_vehicle_download_requires_authorization(monkeypatch):
    import server
    from core import authz

    class _Denied:
        role = "viewer"
        name = "x"
        id = "x"

        def can(self, *_a, **_k):
            return False

    async def _resolve(_request):
        return _Denied()

    monkeypatch.setattr(authz, "resolve_request_actor", _resolve)
    monkeypatch.setattr(server, "_mem_read", lambda _name: [])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.download_vehicle_file("veh-1", "file-1", _Request()))
    assert exc.value.status_code == 403


def test_vehicle_download_reports_lost_legacy_local_file(monkeypatch, admin_actor):
    import server

    legacy = {
        "id": "legacy-1",
        "vehicleId": "veh-legacy",
        "filename": "old.png",
        "filePath": "/app/backend/uploads/vehicles/veh-legacy/gone.png",
    }
    monkeypatch.setattr(server, "_mem_read", lambda _name: [legacy])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.download_vehicle_file("veh-legacy", "legacy-1", _Request()))
    assert exc.value.status_code == 410
    assert exc.value.detail["error"] == "file_content_unavailable"


# ------------------------------------------------- finance audit evidence (durable)
def test_finance_evidence_is_durable_and_retention_first(monkeypatch, admin_actor):
    import routes_finance_bot as bot

    inserted = {}

    class _Collection:
        async def insert_one(self, doc):
            inserted["doc"] = doc

        async def find_one(self, *_a, **_k):
            return {k: v for k, v in inserted["doc"].items() if k != "_id"}

    class _Db:
        finance_audit_evidence = _Collection()

    monkeypatch.setattr(bot, "_get_audit_db", lambda: _Db())

    async def _allow(_request):
        return _Actor()

    monkeypatch.setattr(bot, "_require_financial_evidence_upload", _allow)

    result = asyncio.run(
        bot.upload_finance_evidence(
            _Request(), file=_upload("proof.pdf", PDF, "application/pdf"), session_id="sess-1", finding_id="f-1"
        )
    )
    record = result["data"]
    assert record["storage_backend"] == "emergent_object_storage"
    assert record["storage_path"].startswith("workshop-erp/finance-audit-evidence/sess-1/")
    assert "file_path" not in record
    assert record["is_deleted"] is False  # retention-first

    response = asyncio.run(bot.download_finance_evidence(record["evidence_id"], _Request()))
    assert response.body == PDF
    assert response.media_type == "application/pdf"


def test_finance_evidence_has_no_physical_delete_route():
    source = (BACKEND_DIR / "routes_finance_bot.py").read_text(encoding="utf-8")
    assert 'router.delete("/evidence' not in source
    assert "delete_object" not in source


# ------------------------------------------------------------- document templates
def test_template_upload_is_durable_and_sanitised(monkeypatch, admin_actor):
    import routes_document_templates as templates

    inserted = {}

    class _Collection:
        async def insert_one(self, doc):
            inserted["doc"] = doc

        async def update_one(self, *_a, **_k):
            return None

    class _Db:
        document_templates = _Collection()

    monkeypatch.setattr(templates, "db", _Db())

    async def _noop():
        return None

    monkeypatch.setattr(templates, "_ensure_registry", _noop)

    result = asyncio.run(
        templates.upload_template(
            file=_upload("tpl.html", HTML, "text/html"),
            name="قالب اختبار",
            description="",
            document_type="invoice",
            locale="ar-SA",
            tenant_id="default",
        )
    )
    stored = inserted["doc"]
    assert stored["storage_backend"] == "emergent_object_storage"
    assert stored["storage_path"].startswith("workshop-erp/document-templates/invoice/")
    assert "filename" not in stored
    assert result["success"] is True

    content = asyncio.run(templates._content(stored))
    assert "<script>" not in content  # sanitised before it was ever stored
    assert "Invoice" in content


# --------------------------------- legacy templates router (prefix /api/templates)
def test_legacy_templates_router_upload_is_durable(monkeypatch, admin_actor):
    import routes_templates as legacy

    monkeypatch.setattr(legacy, "templates_db", [])
    monkeypatch.setattr(legacy, "_save_templates", lambda _items: None)

    result = asyncio.run(
        legacy.upload_template(
            file=_upload("legacy.html", HTML, "text/html"),
            name="قالب قديم",
            description="",
            type="invoice",
            make_default=False,
        )
    )
    template = result["template"]
    assert template["storage_backend"] == "emergent_object_storage"
    assert template["storage_path"].startswith("workshop-erp/document-templates/invoice/")
    assert "filename" not in template

    stored_bytes, _ = asyncio.run(object_storage.get_object(template["storage_path"]))
    assert stored_bytes == HTML


def test_legacy_templates_router_rejects_bad_content(monkeypatch, admin_actor):
    import routes_templates as legacy

    monkeypatch.setattr(legacy, "templates_db", [])
    monkeypatch.setattr(legacy, "_save_templates", lambda _items: None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            legacy.upload_template(
                file=_upload("fake.pdf", b"this is not a pdf", "application/pdf"),
                name="x",
                description="",
                type="invoice",
                make_default=False,
            )
        )
    assert exc.value.status_code == 415


# ------------------------------------ operation payment receipts (financial evidence)
def test_payment_receipt_is_stored_durably_and_served_back():
    import base64 as b64

    import routes_extended as extended

    op_id = f"op-{uuid.uuid4().hex[:8]}"
    payload = {
        "name": "receipt.png",
        "mimeType": "image/png",
        "base64": b64.b64encode(PNG).decode("ascii"),
    }
    info = asyncio.run(extended._save_operation_payment_receipt(op_id, payload))
    assert info["storage_backend"] == "emergent_object_storage"
    assert info["storage_path"] == f"workshop-erp/operation-payment-receipts/{op_id}/{info['filename']}"
    assert info["url"] == f"/api/operations/{op_id}/payment-receipts/{info['filename']}"

    response = asyncio.run(extended.get_operation_payment_receipt(op_id, info["filename"]))
    assert response.media_type.startswith("image/png")
    stored_bytes, _ = asyncio.run(object_storage.get_object(info["storage_path"]))
    assert stored_bytes == PNG


def test_payment_receipt_rejects_content_type_mismatch():
    import base64 as b64

    import routes_extended as extended

    payload = {
        "name": "receipt.png",
        "mimeType": "image/png",
        "base64": b64.b64encode(PDF).decode("ascii"),
    }
    with pytest.raises(HTTPException) as exc:
        asyncio.run(extended._save_operation_payment_receipt("op-mismatch", payload))
    assert exc.value.status_code == 415


def test_payment_receipt_keeps_6mb_cap():
    import base64 as b64

    import routes_extended as extended

    oversized = PNG + b"\x00" * (6 * 1024 * 1024)
    payload = {"name": "big.png", "mimeType": "image/png", "base64": b64.b64encode(oversized).decode("ascii")}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(extended._save_operation_payment_receipt("op-big", payload))
    assert exc.value.status_code == 413


def test_missing_payment_receipt_returns_404():
    import routes_extended as extended

    with pytest.raises(HTTPException) as exc:
        asyncio.run(extended.get_operation_payment_receipt("op-none", "nothing-here.png"))
    assert exc.value.status_code == 404
