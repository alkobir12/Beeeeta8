"""Durable object storage for persistent user uploads (P1-SEC-UPLOAD).

Governing rule for this codebase:
  PERSISTENT_USER_FILES  -> object storage (this module)
  PROCESSING_TEMP_FILES  -> OS temp dir + guaranteed cleanup (never this module)

No file is ever deleted here: the storage API exposes no delete operation, so
callers implement soft-delete in their own metadata records.
"""

import asyncio
import os
import re
import uuid
import zipfile
from io import BytesIO
from typing import Dict, Optional, Tuple

import requests
from fastapi import HTTPException

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "workshop-erp"

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB — approved limit

_storage_key: Optional[str] = None


# --------------------------------------------------------------------------
# transport
# --------------------------------------------------------------------------
def _emergent_key() -> str:
    return (os.environ.get("EMERGENT_LLM_KEY") or "").strip()


def init_storage(force: bool = False) -> str:
    """Mint (or reuse) the session-scoped storage key. force=True replaces a dead key."""
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    key = _emergent_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail={"error": "object_storage_not_configured", "message": "تخزين الملفات الدائم غير مهيأ."},
        )
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": key}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def _put_sync(path: str, data: bytes, content_type: str) -> Dict:
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def _get_sync(path: str) -> Tuple[bytes, str]:
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


async def put_object(path: str, data: bytes, content_type: str) -> Dict:
    return await asyncio.to_thread(_put_sync, path, data, content_type)


async def get_object(path: str) -> Tuple[bytes, str]:
    return await asyncio.to_thread(_get_sync, path)


# --------------------------------------------------------------------------
# keys
# --------------------------------------------------------------------------
def safe_basename(name: str) -> str:
    """Strip any directory component and neutralise traversal / control characters."""
    base = os.path.basename(str(name or "").replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._\-\u0600-\u06FF]", "_", base).strip("._")
    if not base or base in {".", ".."}:
        base = f"upload-{uuid.uuid4().hex[:8]}.bin"
    return base[:120]


def build_object_key(surface: str, entity_id: str, ext: str) -> str:
    """Server-generated key. Original filenames never appear in the key."""
    clean_ext = re.sub(r"[^a-z0-9]", "", str(ext or "bin").lower().lstrip(".")) or "bin"
    return build_named_object_key(surface, entity_id, f"{uuid.uuid4().hex}.{clean_ext}")


def build_named_object_key(surface: str, entity_id: str, name: str) -> str:
    """Deterministic key for callers that must round-trip an already-safe name."""
    surface_part = re.sub(r"[^a-z0-9\-]", "-", str(surface or "misc").lower()).strip("-") or "misc"
    entity_part = re.sub(r"[^A-Za-z0-9_\-]", "-", str(entity_id or "unassigned")).strip("-") or "unassigned"
    return f"{APP_NAME}/{surface_part}/{entity_part}/{safe_basename(name)}"


# --------------------------------------------------------------------------
# type + size validation
# --------------------------------------------------------------------------
EXT_MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp",
    "heic": "image/heic", "heif": "image/heif", "pdf": "application/pdf",
    "txt": "text/plain", "csv": "text/csv", "html": "text/html", "htm": "text/html",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_IMAGE_DOC = {"jpg", "jpeg", "png", "webp", "heic", "heif", "pdf"}
_OFFICE_DOC = {"jpg", "jpeg", "png", "webp", "pdf", "txt", "csv", "doc", "docx", "xls", "xlsx"}

# Storage-layer type policy. Individual endpoints may keep a NARROWER product
# rule of their own; this layer never widens an endpoint's existing contract.
SURFACE_POLICIES = {
    "vehicle-files": _IMAGE_DOC,
    "finance-audit-evidence": _IMAGE_DOC,
    "operation-payment-receipts": _IMAGE_DOC,
    "document-templates": _OFFICE_DOC | {"html", "htm"},
    "references": _OFFICE_DOC,
}

_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1"}


def sniff_content_type(data: bytes) -> Tuple[Optional[str], str]:
    """Content-based detection. Returns (mime_or_None, verification_level)."""
    if not data:
        return None, "unverifiable"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "magic_verified"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "magic_verified"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "magic_verified"
    if data[:5] == b"%PDF-":
        return "application/pdf", "magic_verified"
    if data[4:8] == b"ftyp" and data[8:12].lower() in _HEIF_BRANDS:
        return "image/heic", "magic_verified"
    if data[:4] == b"PK\x03\x04":
        # OOXML is a zip container; the concrete sub-type is read from the container.
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                names = archive.namelist()
            if any(n.startswith("word/") for n in names):
                return EXT_MIME["docx"], "container_verified"
            if any(n.startswith("xl/") for n in names):
                return EXT_MIME["xlsx"], "container_verified"
        except Exception:
            return None, "unverifiable"
        return "application/zip", "container_verified"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        # Legacy OLE compound file — .doc / .xls share one magic.
        return "application/x-ole-storage", "container_verified"
    if b"\x00" not in data[:4096]:
        try:
            data[:4096].decode("utf-8")
            return None, "text_heuristic"
        except UnicodeDecodeError:
            return None, "unverifiable"
    return None, "unverifiable"


def validate_upload(
    data: bytes,
    filename: Optional[str],
    declared_content_type: Optional[str],
    surface: str,
) -> Dict[str, str]:
    """Enforce size + type. The browser-declared content type is never sufficient alone.

    Returns {content_type, ext, verification_level}.
    """
    allowed = SURFACE_POLICIES.get(surface)
    if allowed is None:
        raise HTTPException(status_code=500, detail={"error": "unknown_upload_surface", "surface": surface})

    if not data:
        raise HTTPException(status_code=400, detail={"error": "empty_file", "message": "الملف فارغ."})
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "file_too_large",
                "max_bytes": MAX_UPLOAD_BYTES,
                "message": "الملف أكبر من الحد المسموح (25 ميجابايت).",
            },
        )

    ext = safe_basename(filename or "").rsplit(".", 1)[-1].lower() if "." in safe_basename(filename or "") else ""
    ext = re.sub(r"[^a-z0-9]", "", ext)
    if ext not in allowed:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "unsupported_file_type",
                "extension": ext or "unknown",
                "allowed": sorted(allowed),
                "message": "نوع الملف غير مسموح به.",
            },
        )

    sniffed, level = sniff_content_type(data)
    expected = EXT_MIME.get(ext, "application/octet-stream")

    if sniffed and level == "magic_verified":
        # HEIC and HEIF share one magic family; accept either extension for it.
        heif_pair = {"image/heic", "image/heif"}
        if sniffed != expected and not (sniffed in heif_pair and expected in heif_pair):
            raise HTTPException(
                status_code=415,
                detail={
                    "error": "content_type_mismatch",
                    "declared_extension": ext,
                    "detected": sniffed,
                    "message": "محتوى الملف لا يطابق امتداده.",
                },
            )
        return {"content_type": sniffed, "ext": ext, "verification_level": level}

    if level == "container_verified":
        if ext in {"docx", "xlsx"} and sniffed != expected:
            raise HTTPException(
                status_code=415,
                detail={"error": "content_type_mismatch", "declared_extension": ext, "detected": sniffed},
            )
        if ext in {"doc", "xls"} and sniffed != "application/x-ole-storage":
            raise HTTPException(
                status_code=415,
                detail={"error": "content_type_mismatch", "declared_extension": ext, "detected": sniffed},
            )
        return {"content_type": expected, "ext": ext, "verification_level": level}

    if ext in {"txt", "csv", "html", "htm"} and level == "text_heuristic":
        return {"content_type": expected, "ext": ext, "verification_level": level}

    raise HTTPException(
        status_code=415,
        detail={
            "error": "file_content_not_verifiable",
            "declared_extension": ext,
            "message": "تعذر التحقق من محتوى الملف؛ لم يُقبل الرفع.",
        },
    )
