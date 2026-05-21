
from fastapi import APIRouter, HTTPException, Body, Query, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import uuid
import json
import re
import mimetypes
import requests
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from dotenv import load_dotenv
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorClient

try:
    from supabase_service import SupabaseService
except Exception:
    SupabaseService = None

load_dotenv()

router = APIRouter(prefix="/api/alkabeer-bot", tags=["alkabeer-bot"])

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
BASE_PROMPT_FILE = os.path.join(PROMPTS_DIR, "alkabeer_base.md")
EXT_PROMPT_FILE = os.path.join(PROMPTS_DIR, "alkabeer_extensions.md")

# In-memory session tracking for Developer Mode
# Format: { session_id: { "mode": "user" | "dev", "pending_data": [] } }
session_states = {}

CUSTOMIZATION_FILE = os.path.join(os.path.dirname(__file__), "uploads", "alkabeer_ui_customizations.json")
EDITOR_ASSETS_FILE = os.path.join(os.path.dirname(__file__), "uploads", "alkabeer_editor_assets.json")
EDITOR_COLLAB_FILE = os.path.join(os.path.dirname(__file__), "uploads", "alkabeer_editor_collab.json")
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "alkobir-editor"
storage_key = None

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")
editor_db = AsyncIOMotorClient(MONGO_URL)[DB_NAME] if MONGO_URL and DB_NAME else None
supa_service = SupabaseService() if SupabaseService else None

EDITOR_DRAFTS_TABLE = os.getenv("MOLTBOT_DRAFTS_TABLE", "moltbot_editor_drafts")
EDITOR_HISTORY_TABLE = os.getenv("MOLTBOT_HISTORY_TABLE", "moltbot_editor_history")
EDITOR_COMMENTS_TABLE = os.getenv("MOLTBOT_COMMENTS_TABLE", "moltbot_editor_comments")
_editor_table_status: Dict[str, bool] = {}


def _read_customizations() -> Dict[str, Any]:
    try:
        os.makedirs(os.path.dirname(CUSTOMIZATION_FILE), exist_ok=True)
        if not os.path.exists(CUSTOMIZATION_FILE):
            with open(CUSTOMIZATION_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        with open(CUSTOMIZATION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_customizations(data: Dict[str, Any]):
    os.makedirs(os.path.dirname(CUSTOMIZATION_FILE), exist_ok=True)
    with open(CUSTOMIZATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_editor_assets() -> List[Dict[str, Any]]:
    try:
        os.makedirs(os.path.dirname(EDITOR_ASSETS_FILE), exist_ok=True)
        if not os.path.exists(EDITOR_ASSETS_FILE):
            with open(EDITOR_ASSETS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        with open(EDITOR_ASSETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_editor_assets(rows: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(EDITOR_ASSETS_FILE), exist_ok=True)
    with open(EDITOR_ASSETS_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def _read_editor_collab() -> Dict[str, Any]:
    try:
        os.makedirs(os.path.dirname(EDITOR_COLLAB_FILE), exist_ok=True)
        if not os.path.exists(EDITOR_COLLAB_FILE):
            with open(EDITOR_COLLAB_FILE, "w", encoding="utf-8") as f:
                json.dump({"drafts": [], "history": [], "comments": []}, f, ensure_ascii=False, indent=2)
        with open(EDITOR_COLLAB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"drafts": [], "history": [], "comments": []}
            return {
                "drafts": data.get("drafts") if isinstance(data.get("drafts"), list) else [],
                "history": data.get("history") if isinstance(data.get("history"), list) else [],
                "comments": data.get("comments") if isinstance(data.get("comments"), list) else [],
            }
    except Exception:
        return {"drafts": [], "history": [], "comments": []}


def _write_editor_collab(data: Dict[str, Any]):
    os.makedirs(os.path.dirname(EDITOR_COLLAB_FILE), exist_ok=True)
    payload = {
        "drafts": data.get("drafts") if isinstance(data.get("drafts"), list) else [],
        "history": data.get("history") if isinstance(data.get("history"), list) else [],
        "comments": data.get("comments") if isinstance(data.get("comments"), list) else [],
    }
    with open(EDITOR_COLLAB_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _editor_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _editor_supabase_ready() -> bool:
    return bool(supa_service and getattr(supa_service, "client", None) and not getattr(supa_service, "mock_mode", True))


def _editor_table_available(table_name: str) -> bool:
    if table_name in _editor_table_status:
        return _editor_table_status[table_name]
    if not _editor_supabase_ready():
        _editor_table_status[table_name] = False
        return False
    try:
        supa_service.client.table(table_name).select("id").limit(1).execute()
        _editor_table_status[table_name] = True
    except Exception:
        _editor_table_status[table_name] = False
    return _editor_table_status[table_name]


def _guess_content_type(filename: str, fallback: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(filename or "")
    return guessed or fallback


def _init_storage() -> str:
    global storage_key
    if storage_key:
        return storage_key
    emergent_key = os.getenv("EMERGENT_LLM_KEY")
    if not emergent_key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY غير مضبوط للتخزين")
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": emergent_key}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def _put_object(path: str, data: bytes, content_type: str) -> Dict[str, Any]:
    key = _init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def _get_object(path: str) -> tuple[bytes, str]:
    key = _init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def _merge_page_configs(global_cfg: Dict[str, Any], page_cfg: Dict[str, Any]) -> Dict[str, Any]:
    labels = dict(global_cfg.get("labels") or {})
    labels.update(page_cfg.get("labels") or {})

    hidden = dict(global_cfg.get("hidden") or {})
    hidden.update(page_cfg.get("hidden") or {})

    contents = dict(global_cfg.get("contents") or {})
    contents.update(page_cfg.get("contents") or {})

    custom_cards = list(global_cfg.get("custom_cards") or []) + list(page_cfg.get("custom_cards") or [])
    block_order = list(page_cfg.get("block_order") or [])
    positions = dict(global_cfg.get("positions") or {})
    positions.update(page_cfg.get("positions") or {})
    styles = dict(global_cfg.get("styles") or {})
    styles.update(page_cfg.get("styles") or {})
    assets = dict(global_cfg.get("assets") or {})
    assets.update(page_cfg.get("assets") or {})
    page_manifest = dict(page_cfg.get("page_manifest") or {})

    return {
        "labels": labels,
        "hidden": hidden,
        "contents": contents,
        "custom_cards": custom_cards,
        "block_order": block_order,
        "positions": positions,
        "styles": styles,
        "assets": assets,
        "page_manifest": page_manifest,
    }


def _get_user_page_config(user_id: str, path: str) -> Dict[str, Any]:
    data = _read_customizations()
    user_node = data.get(user_id) or {}
    global_cfg = user_node.get("global") or {"labels": {}, "hidden": {}}
    if "contents" not in global_cfg:
        global_cfg["contents"] = {}
    if "custom_cards" not in global_cfg:
        global_cfg["custom_cards"] = []
    if "block_order" not in global_cfg:
        global_cfg["block_order"] = []
    if "positions" not in global_cfg:
        global_cfg["positions"] = {}
    if "styles" not in global_cfg:
        global_cfg["styles"] = {}
    if "assets" not in global_cfg:
        global_cfg["assets"] = {}
    page_cfg = user_node.get(path) or {"labels": {}, "hidden": {}, "contents": {}, "custom_cards": [], "block_order": [], "positions": {}, "styles": {}, "assets": {}, "page_manifest": {}}
    merged = _merge_page_configs(global_cfg, page_cfg)
    return {
        "user_id": user_id,
        "path": path,
        "labels": merged.get("labels") or {},
        "hidden": merged.get("hidden") or {},
        "contents": merged.get("contents") or {},
        "custom_cards": merged.get("custom_cards") or [],
        "block_order": merged.get("block_order") or [],
        "positions": merged.get("positions") or {},
        "styles": merged.get("styles") or {},
        "assets": merged.get("assets") or {},
        "page_manifest": merged.get("page_manifest") or {},
        "global": global_cfg,
        "page": page_cfg,
    }


def _editor_sanitize_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    config = config or {}
    return {
        "labels": config.get("labels") or {},
        "hidden": config.get("hidden") or {},
        "contents": config.get("contents") or {},
        "custom_cards": config.get("custom_cards") or [],
        "block_order": config.get("block_order") or [],
        "positions": config.get("positions") or {},
        "styles": config.get("styles") or {},
        "assets": config.get("assets") or {},
        "page_manifest": config.get("page_manifest") or {},
    }


def _editor_get_latest_draft(user_id: str, path: str) -> Optional[Dict[str, Any]]:
    if _editor_table_available(EDITOR_DRAFTS_TABLE):
        try:
            rows = (
                supa_service.client.table(EDITOR_DRAFTS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("path", path)
                .order("version", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return rows[0]
        except Exception:
            _editor_table_status[EDITOR_DRAFTS_TABLE] = False

    collab = _read_editor_collab()
    candidates = [
        row for row in collab.get("drafts", [])
        if str(row.get("user_id") or "") == user_id and str(row.get("path") or "") == path
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda row: int(row.get("version") or 0), reverse=True)
    return candidates[0]


def _editor_list_history(user_id: str, path: str, limit: int = 40) -> List[Dict[str, Any]]:
    if _editor_table_available(EDITOR_HISTORY_TABLE):
        try:
            return (
                supa_service.client.table(EDITOR_HISTORY_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("path", path)
                .order("version", desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
        except Exception:
            _editor_table_status[EDITOR_HISTORY_TABLE] = False

    collab = _read_editor_collab()
    rows = [
        row for row in collab.get("history", [])
        if str(row.get("user_id") or "") == user_id and str(row.get("path") or "") == path
    ]
    rows.sort(key=lambda row: int(row.get("version") or 0), reverse=True)
    return rows[:limit]


def _editor_get_latest_published(user_id: str, path: str) -> Optional[Dict[str, Any]]:
    if _editor_table_available(EDITOR_HISTORY_TABLE):
        try:
            rows = (
                supa_service.client.table(EDITOR_HISTORY_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("path", path)
                .eq("status", "published")
                .order("version", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return rows[0]
        except Exception:
            _editor_table_status[EDITOR_HISTORY_TABLE] = False

    collab = _read_editor_collab()
    rows = [
        row for row in collab.get("history", [])
        if str(row.get("user_id") or "") == user_id
        and str(row.get("path") or "") == path
        and str(row.get("status") or "").lower() == "published"
    ]
    rows.sort(key=lambda row: int(row.get("version") or 0), reverse=True)
    return rows[0] if rows else None


def _editor_get_latest_published_any(path: str) -> Optional[Dict[str, Any]]:
    if _editor_table_available(EDITOR_HISTORY_TABLE):
        try:
            rows = (
                supa_service.client.table(EDITOR_HISTORY_TABLE)
                .select("*")
                .eq("path", path)
                .eq("status", "published")
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows:
                return rows[0]
        except Exception:
            _editor_table_status[EDITOR_HISTORY_TABLE] = False

    collab = _read_editor_collab()
    rows = [
        row for row in collab.get("history", [])
        if str(row.get("path") or "") == path
        and str(row.get("status") or "").lower() == "published"
    ]
    rows.sort(key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
    return rows[0] if rows else None


def _editor_config_has_content(config: Optional[Dict[str, Any]]) -> bool:
    safe_cfg = _editor_sanitize_config(config or {})
    return any([
        bool(safe_cfg.get("labels")),
        bool(safe_cfg.get("hidden")),
        bool(safe_cfg.get("contents")),
        bool(safe_cfg.get("custom_cards")),
        bool(safe_cfg.get("block_order")),
        bool(safe_cfg.get("positions")),
        bool(safe_cfg.get("styles")),
        bool(safe_cfg.get("assets")),
        bool(safe_cfg.get("page_manifest")),
    ])


def _resolve_customization_with_fallback(user_id: str, path: str) -> Dict[str, Any]:
    normalized_user = str(user_id or "manager").strip() or "manager"
    normalized_path = str(path or "/").strip() or "/"

    direct_cfg = _get_user_page_config(normalized_user, normalized_path)
    direct_payload = _editor_sanitize_config(direct_cfg)
    if _editor_config_has_content(direct_payload):
        return {
            "resolved_user_id": normalized_user,
            "config": direct_payload,
        }

    direct_published = _editor_get_latest_published(normalized_user, normalized_path)
    if direct_published:
        published_cfg = _editor_sanitize_config(direct_published.get("config") or {})
        if _editor_config_has_content(published_cfg):
            return {
                "resolved_user_id": normalized_user,
                "config": published_cfg,
            }

    latest_any = _editor_get_latest_published_any(normalized_path)
    if latest_any:
        published_cfg = _editor_sanitize_config(latest_any.get("config") or {})
        if _editor_config_has_content(published_cfg):
            return {
                "resolved_user_id": str(latest_any.get("user_id") or normalized_user),
                "config": published_cfg,
            }

    return {
        "resolved_user_id": normalized_user,
        "config": direct_payload,
    }


def _editor_save_snapshot(user_id: str, path: str, config: Dict[str, Any], status: str = "draft", note: str = "manual_save") -> Dict[str, Any]:
    safe_cfg = _editor_sanitize_config(config)
    latest = _editor_get_latest_draft(user_id, path)
    version = int(latest.get("version") or 0) + 1 if latest else 1
    now_iso = _editor_now_iso()

    record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "path": path,
        "status": status,
        "version": version,
        "note": note,
        "config": safe_cfg,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    if _editor_table_available(EDITOR_DRAFTS_TABLE) and _editor_table_available(EDITOR_HISTORY_TABLE):
        try:
            supa_service.client.table(EDITOR_DRAFTS_TABLE).insert(record).execute()
            supa_service.client.table(EDITOR_HISTORY_TABLE).insert(record).execute()
            return record
        except Exception:
            _editor_table_status[EDITOR_DRAFTS_TABLE] = False
            _editor_table_status[EDITOR_HISTORY_TABLE] = False

    collab = _read_editor_collab()
    drafts = [
        row for row in collab.get("drafts", [])
        if not (str(row.get("user_id") or "") == user_id and str(row.get("path") or "") == path)
    ]
    drafts.append(record)
    history = collab.get("history", [])
    history.append(record)
    collab["drafts"] = drafts
    collab["history"] = history[-300:]
    _write_editor_collab(collab)
    return record


def _editor_list_comments(path: str, user_id: Optional[str], limit: int = 120) -> List[Dict[str, Any]]:
    if _editor_table_available(EDITOR_COMMENTS_TABLE):
        try:
            q = supa_service.client.table(EDITOR_COMMENTS_TABLE).select("*").eq("path", path)
            if user_id:
                q = q.eq("user_id", user_id)
            return q.order("created_at", desc=True).limit(limit).execute().data or []
        except Exception:
            _editor_table_status[EDITOR_COMMENTS_TABLE] = False

    collab = _read_editor_collab()
    rows = [row for row in collab.get("comments", []) if str(row.get("path") or "") == path]
    if user_id:
        rows = [row for row in rows if str(row.get("user_id") or "") == user_id]
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return rows[:limit]


def _editor_add_comment(path: str, user_id: str, block_id: str, message: str, author_name: Optional[str]) -> Dict[str, Any]:
    now_iso = _editor_now_iso()
    row = {
        "id": str(uuid.uuid4()),
        "path": path,
        "user_id": user_id,
        "block_id": block_id,
        "message": message,
        "author_name": author_name or user_id,
        "resolved": False,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    if _editor_table_available(EDITOR_COMMENTS_TABLE):
        try:
            inserted = supa_service.client.table(EDITOR_COMMENTS_TABLE).insert(row).execute().data or []
            return inserted[0] if inserted else row
        except Exception:
            _editor_table_status[EDITOR_COMMENTS_TABLE] = False

    collab = _read_editor_collab()
    comments = collab.get("comments", [])
    comments.append(row)
    collab["comments"] = comments[-500:]
    _write_editor_collab(collab)
    return row


def _editor_update_comment(comment_id: str, resolved: Optional[bool], message: Optional[str]) -> Optional[Dict[str, Any]]:
    now_iso = _editor_now_iso()
    if _editor_table_available(EDITOR_COMMENTS_TABLE):
        try:
            payload: Dict[str, Any] = {"updated_at": now_iso}
            if resolved is not None:
                payload["resolved"] = bool(resolved)
            if message is not None:
                payload["message"] = str(message)
            rows = supa_service.client.table(EDITOR_COMMENTS_TABLE).update(payload).eq("id", comment_id).execute().data or []
            return rows[0] if rows else None
        except Exception:
            _editor_table_status[EDITOR_COMMENTS_TABLE] = False

    collab = _read_editor_collab()
    updated = None
    next_comments = []
    for row in collab.get("comments", []):
        if str(row.get("id") or "") != str(comment_id):
            next_comments.append(row)
            continue
        updated = dict(row)
        if resolved is not None:
            updated["resolved"] = bool(resolved)
        if message is not None:
            updated["message"] = str(message)
        updated["updated_at"] = now_iso
        next_comments.append(updated)
    collab["comments"] = next_comments
    _write_editor_collab(collab)
    return updated


def _editor_delete_comment(comment_id: str) -> bool:
    if _editor_table_available(EDITOR_COMMENTS_TABLE):
        try:
            supa_service.client.table(EDITOR_COMMENTS_TABLE).delete().eq("id", comment_id).execute()
            return True
        except Exception:
            _editor_table_status[EDITOR_COMMENTS_TABLE] = False

    collab = _read_editor_collab()
    before = len(collab.get("comments", []))
    collab["comments"] = [row for row in collab.get("comments", []) if str(row.get("id") or "") != str(comment_id)]
    _write_editor_collab(collab)
    return len(collab.get("comments", [])) < before


def _extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None
    text = raw_text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    matches = re.findall(r"\{[\s\S]*\}", raw_text)
    for candidate in reversed(matches):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _fallback_parse_actions(message: str, ui_snapshot: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    text = (message or "").strip()
    actions: List[Dict[str, Any]] = []

    show_terms = ["اظهر", "أظهر", "إظهار", "show"]
    hide_terms = ["اخف", "إخفاء", "اخفاء", "hide"]
    rename_terms = ["غير اسم", "تغيير اسم", "rename"]

    add_card_match = re.search(r"(?:اضف|أضف|add)\s+كرت\s+(.+)$", text, re.IGNORECASE)
    if add_card_match:
        title = add_card_match.group(1).strip()
        if title:
            return [{"type": "add_card", "title": title}]

    delete_card_match = re.search(r"(?:احذف|حذف|delete)\s+كرت\s+(.+)$", text, re.IGNORECASE)
    if delete_card_match:
        title = delete_card_match.group(1).strip()
        if title:
            return [{"type": "delete_card", "card_title": title}]

    add_field_match = re.search(r"(?:اضف|أضف)\s+حقل\s+(.+?)\s*[=:]\s*(.+?)\s+في\s+كرت\s+(.+)$", text, re.IGNORECASE)
    if add_field_match:
        return [{
            "type": "add_field",
            "field_label": add_field_match.group(1).strip(),
            "field_value": add_field_match.group(2).strip(),
            "card_title": add_field_match.group(3).strip(),
        }]

    update_field_match = re.search(r"(?:حدث|حدّث|تعديل|update)\s+حقل\s+(.+?)\s*[=:]\s*(.+?)\s+في\s+كرت\s+(.+)$", text, re.IGNORECASE)
    if update_field_match:
        return [{
            "type": "update_field",
            "field_label": update_field_match.group(1).strip(),
            "field_value": update_field_match.group(2).strip(),
            "card_title": update_field_match.group(3).strip(),
        }]

    delete_field_match = re.search(r"(?:احذف|حذف|delete)\s+حقل\s+(.+?)\s+من\s+كرت\s+(.+)$", text, re.IGNORECASE)
    if delete_field_match:
        return [{
            "type": "delete_field",
            "field_label": delete_field_match.group(1).strip(),
            "card_title": delete_field_match.group(2).strip(),
        }]

    def find_target(term_text: str) -> Optional[str]:
        term_text = term_text.strip().lower()
        for item in ui_snapshot or []:
            label = str(item.get("text") or "").lower()
            testid = str(item.get("testid") or "")
            if term_text and term_text in label and testid:
                return testid
        return None

    if any(token in text for token in hide_terms):
        target_text = text
        for token in hide_terms:
            target_text = target_text.replace(token, "")
        target = find_target(target_text)
        if target:
            actions.append({"type": "hide", "target_testid": target})
        return actions

    if any(token in text for token in show_terms):
        target_text = text
        for token in show_terms:
            target_text = target_text.replace(token, "")
        target = find_target(target_text)
        if target:
            actions.append({"type": "show", "target_testid": target})
        return actions

    if any(token in text for token in rename_terms) and "الى" in text:
        parts = re.split(r"الى|إلى", text, maxsplit=1)
        if len(parts) == 2:
            left, right = parts[0], parts[1]
            for token in rename_terms:
                left = left.replace(token, "")
            target = find_target(left)
            new_label = right.strip()
            if target and new_label:
                actions.append({"type": "rename", "target_testid": target, "new_label": new_label})
        return actions

    return actions


async def _parse_actions_with_claude(
    message: str,
    current_path: str,
    ui_snapshot: List[Dict[str, Any]],
    anthropic_key: str,
    session_id: str,
) -> List[Dict[str, Any]]:
    model_prompt = (
        "أنت محلل أوامر واجهة. مهمتك تحويل طلب المستخدم إلى JSON فقط بلا أي نص إضافي.\n"
        "المسار الحالي: " + (current_path or "/") + "\n"
        "العناصر المتاحة (data-testid + النص):\n"
        f"{json.dumps(ui_snapshot[:200], ensure_ascii=False)}\n\n"
        "الـ JSON النهائي بالشكل:\n"
        "{\n"
        "  \"actions\": [\n"
        "    {\"type\": \"rename\", \"target_testid\": \"...\", \"new_label\": \"...\"},\n"
        "    {\"type\": \"hide\", \"target_testid\": \"...\"},\n"
        "    {\"type\": \"show\", \"target_testid\": \"...\"},\n"
        "    {\"type\": \"add_card\", \"title\": \"...\"},\n"
        "    {\"type\": \"delete_card\", \"card_title\": \"...\"},\n"
        "    {\"type\": \"add_field\", \"card_title\": \"...\", \"field_label\": \"...\", \"field_value\": \"...\"},\n"
        "    {\"type\": \"update_field\", \"card_title\": \"...\", \"field_label\": \"...\", \"field_value\": \"...\"},\n"
        "    {\"type\": \"delete_field\", \"card_title\": \"...\", \"field_label\": \"...\"},\n"
        "    {\"type\": \"reset_target\", \"target_testid\": \"...\"},\n"
        "    {\"type\": \"reset_page\"}\n"
        "  ]\n"
        "}\n"
        "لو لا يمكن التنفيذ، أرجع actions فارغة."
    )

    chat = LlmChat(
        api_key=anthropic_key,
        session_id=f"{session_id}-dev-parser",
        system_message=model_prompt,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    raw = await chat.send_message(UserMessage(text=message))
    parsed = _extract_json_object(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
    if not parsed:
        return []
    actions = parsed.get("actions")
    return actions if isinstance(actions, list) else []


def _apply_actions_to_config(current_cfg: Dict[str, Any], actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    labels = dict(current_cfg.get("labels") or {})
    hidden = dict(current_cfg.get("hidden") or {})
    contents = dict(current_cfg.get("contents") or {})
    custom_cards = list(current_cfg.get("custom_cards") or [])
    block_order = list(current_cfg.get("block_order") or [])
    positions = dict(current_cfg.get("positions") or {})
    styles = dict(current_cfg.get("styles") or {})
    assets = dict(current_cfg.get("assets") or {})
    page_manifest = dict(current_cfg.get("page_manifest") or {})

    def _find_card_index(card_title: str) -> int:
        for index, card in enumerate(custom_cards):
            if str(card.get("title") or "").strip() == str(card_title or "").strip():
                return index
        return -1

    for action in actions:
        action_type = str(action.get("type") or "").strip().lower()
        target = str(action.get("target_testid") or "").strip()

        if action_type == "reset_page":
            labels = {}
            hidden = {}
            contents = {}
            custom_cards = []
            block_order = []
            positions = {}
            styles = {}
            assets = {}
            page_manifest = {}
            continue

        if action_type == "add_card":
            title = str(action.get("title") or "كرت جديد").strip() or "كرت جديد"
            custom_cards.append({
                "id": f"card-{uuid.uuid4().hex[:8]}",
                "title": title,
                "description": "",
                "fields": [],
            })
            continue

        if action_type == "delete_card":
            title = str(action.get("card_title") or "").strip()
            custom_cards = [card for card in custom_cards if str(card.get("title") or "").strip() != title]
            continue

        if action_type == "add_field":
            card_index = _find_card_index(str(action.get("card_title") or "").strip())
            if card_index >= 0:
                fields = list(custom_cards[card_index].get("fields") or [])
                fields.append({
                    "id": f"field-{uuid.uuid4().hex[:8]}",
                    "label": str(action.get("field_label") or "حقل").strip(),
                    "value": str(action.get("field_value") or "").strip(),
                })
                custom_cards[card_index]["fields"] = fields
            continue

        if action_type == "update_field":
            card_index = _find_card_index(str(action.get("card_title") or "").strip())
            if card_index >= 0:
                fields = list(custom_cards[card_index].get("fields") or [])
                label = str(action.get("field_label") or "").strip()
                for field in fields:
                    if str(field.get("label") or "").strip() == label:
                        field["value"] = str(action.get("field_value") or "").strip()
                custom_cards[card_index]["fields"] = fields
            continue

        if action_type == "delete_field":
            card_index = _find_card_index(str(action.get("card_title") or "").strip())
            if card_index >= 0:
                label = str(action.get("field_label") or "").strip()
                custom_cards[card_index]["fields"] = [
                    field for field in list(custom_cards[card_index].get("fields") or [])
                    if str(field.get("label") or "").strip() != label
                ]
            continue

        if not target:
            continue

        if action_type == "rename":
            new_label = str(action.get("new_label") or "").strip()
            if new_label:
                labels[target] = new_label
            continue

        if action_type == "hide":
            hidden[target] = True
            continue

        if action_type == "show":
            hidden[target] = False
            continue

        if action_type == "reset_target":
            labels.pop(target, None)
            hidden.pop(target, None)
            contents.pop(target, None)

    return {"labels": labels, "hidden": hidden, "contents": contents, "custom_cards": custom_cards, "block_order": block_order, "positions": positions, "styles": styles, "assets": assets, "page_manifest": page_manifest}

def get_combined_system_prompt():
    base = ""
    ext = ""
    try:
        if os.path.exists(BASE_PROMPT_FILE):
            with open(BASE_PROMPT_FILE, "r", encoding="utf-8") as f:
                base = f.read()
        if os.path.exists(EXT_PROMPT_FILE):
            with open(EXT_PROMPT_FILE, "r", encoding="utf-8") as f:
                ext = f.read()
    except Exception as e:
        print(f"Error reading prompt files: {e}")
    
    combined = base + "\n\n" + "# 9. تحديثات ومعلومات إضافية (تمت إضافتها بواسطة المطور)\n" + ext
    return combined

def append_to_knowledge(text):
    try:
        with open(EXT_PROMPT_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n- {text}")
        return True
    except Exception as e:
        print(f"Error writing to extensions: {e}")
        return False

class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    role: Optional[str] = None
    userId: Optional[str] = None
    currentPath: Optional[str] = "/"
    uiSnapshot: Optional[List[Dict[str, Any]]] = None


class CustomizationUpdateRequest(BaseModel):
    user_id: str = "manager"
    path: str = "/"
    labels: Optional[Dict[str, str]] = None
    hidden: Optional[Dict[str, bool]] = None
    contents: Optional[Dict[str, str]] = None
    custom_cards: Optional[List[Dict[str, Any]]] = None
    block_order: Optional[List[str]] = None
    positions: Optional[Dict[str, Dict[str, Any]]] = None
    styles: Optional[Dict[str, Dict[str, Any]]] = None
    assets: Optional[Dict[str, Dict[str, Any]]] = None
    page_manifest: Optional[Dict[str, Any]] = None


class EditorDraftSaveRequest(BaseModel):
    user_id: str = "manager"
    path: str = "/"
    config: Dict[str, Any] = {}
    note: Optional[str] = "manual_save"
    status: Optional[str] = "draft"


class EditorCommentCreateRequest(BaseModel):
    user_id: str = "manager"
    path: str = "/"
    block_id: Optional[str] = ""
    message: str
    author_name: Optional[str] = None


class EditorCommentUpdateRequest(BaseModel):
    resolved: Optional[bool] = None
    message: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    sessionId: str
    model: str
    mode: str = "user"
    actions: Optional[List[Dict[str, Any]]] = None
    customization: Optional[Dict[str, Any]] = None

@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    try:
        api_key = os.getenv("EMERGENT_LLM_KEY")
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key and not anthropic_api_key:
            raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY not configured")

        session_id = payload.sessionId or str(uuid.uuid4())
        user_role = str(payload.role or "").strip().lower()
        user_id = str(payload.userId or "manager").strip() or "manager"
        current_path = str(payload.currentPath or "/").strip() or "/"
        ui_snapshot = payload.uiSnapshot or []
        
        # Init session state if not exists
        if session_id not in session_states:
            session_states[session_id] = {"mode": "user"}
        
        state = session_states[session_id]
        user_msg = payload.message.strip()

        # --- Developer Mode Logic ---
        # 1. Trigger Entry
        if user_msg == "rrr":
            if user_role not in {"manager", "admin", "مدير"}:
                return ChatResponse(
                    response="⛔ وضع المطور متاح للمدير فقط.",
                    sessionId=session_id,
                    model="system",
                    mode="user",
                )
            state["mode"] = "dev"
            return ChatResponse(
                response=(
                    "🔓 **تم تفعيل وضع المطور (RRR)**\n\n"
                    "أرسل أي أمر تعديل على الصفحة الحالية، مثل:\n"
                    "- اخف كرت صافي الدخل\n"
                    "- غير اسم زر تحديث إلى مزامنة\n"
                    "- اظهر كرت الذمم\n"
                    "- reset_page لإرجاع الصفحة للوضع الأصلي\n\n"
                    "اكتب `EXIT` للخروج من وضع المطور."
                ),
                sessionId=session_id,
                model="system",
                mode="dev"
            )
        
        # 2. Handle Dev Mode Interactions
        if state["mode"] == "dev":
            if user_msg.upper() == "EXIT":
                state["mode"] = "user"
                return ChatResponse(
                    response="🔒 **تم الخروج من وضع المطور.**\nعودة إلى وضع خدمة العملاء (أبو فهد).",
                    sessionId=session_id,
                    model="system",
                    mode="user"
                )

            if user_msg.lower() in {"clear", "reset_page", "مسح", "اعادة الصفحة", "إعادة الصفحة"}:
                data = _read_customizations()
                user_node = data.get(user_id) or {}
                user_node[current_path] = {"labels": {}, "hidden": {}, "contents": {}, "custom_cards": [], "block_order": [], "positions": {}, "styles": {}, "assets": {}, "page_manifest": {}}
                data[user_id] = user_node
                _write_customizations(data)
                cfg = _get_user_page_config(user_id, current_path)
                return ChatResponse(
                    response="✅ تم إعادة الصفحة الحالية للوضع الأصلي.",
                    sessionId=session_id,
                    model="system",
                    mode="dev",
                    actions=[{"type": "reset_page"}],
                    customization={
                        "labels": cfg.get("labels", {}),
                        "hidden": cfg.get("hidden", {}),
                        "contents": cfg.get("contents", {}),
                        "custom_cards": cfg.get("custom_cards", []),
                        "block_order": cfg.get("block_order", []),
                        "positions": cfg.get("positions", {}),
                        "styles": cfg.get("styles", {}),
                        "assets": cfg.get("assets", {}),
                        "page_manifest": cfg.get("page_manifest", {}),
                    },
                )

            actions: List[Dict[str, Any]] = []
            try:
                key_for_claude = anthropic_api_key or api_key
                if key_for_claude:
                    actions = await _parse_actions_with_claude(
                        message=user_msg,
                        current_path=current_path,
                        ui_snapshot=ui_snapshot,
                        anthropic_key=key_for_claude,
                        session_id=session_id,
                    )
            except Exception as parse_err:
                print(f"Developer command parse error: {parse_err}")

            if not actions:
                actions = _fallback_parse_actions(user_msg, ui_snapshot)

            if not actions:
                return ChatResponse(
                    response="لم أفهم الأمر بشكل كافٍ. جرّب: (اخف ... / اظهر ... / غير اسم ... إلى ...)",
                    sessionId=session_id,
                    model="claude-sonnet-4.5",
                    mode="dev",
                    actions=[],
                )

            data = _read_customizations()
            user_node = data.get(user_id) or {}
            page_cfg = user_node.get(current_path) or {"labels": {}, "hidden": {}, "contents": {}, "custom_cards": [], "block_order": [], "positions": {}, "styles": {}, "assets": {}, "page_manifest": {}}
            updated_cfg = _apply_actions_to_config(page_cfg, actions)
            user_node[current_path] = updated_cfg
            data[user_id] = user_node
            _write_customizations(data)

            merged_cfg = _get_user_page_config(user_id, current_path)
            return ChatResponse(
                response=f"✅ تم تطبيق {len(actions)} تعديل على الصفحة الحالية.",
                sessionId=session_id,
                model="claude-sonnet-4.5",
                mode="dev",
                actions=actions,
                customization={
                    "labels": merged_cfg.get("labels", {}),
                    "hidden": merged_cfg.get("hidden", {}),
                    "contents": merged_cfg.get("contents", {}),
                    "custom_cards": merged_cfg.get("custom_cards", []),
                    "block_order": merged_cfg.get("block_order", []),
                    "positions": merged_cfg.get("positions", {}),
                    "styles": merged_cfg.get("styles", {}),
                    "assets": merged_cfg.get("assets", {}),
                    "page_manifest": merged_cfg.get("page_manifest", {}),
                },
            )

        # --- Standard Chat Logic (Abu Fahad) ---
        
        # Load the latest combined prompt
        system_prompt = get_combined_system_prompt()

        if anthropic_api_key:
            chat = LlmChat(
                api_key=anthropic_api_key,
                session_id=session_id,
                system_message=system_prompt,
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            model_used = "claude-sonnet-4.5"
        else:
            chat = LlmChat(
                api_key=api_key,
                session_id=session_id,
                system_message=system_prompt,
            ).with_model("openai", "gpt-4o")
            model_used = "gpt-4o"

        file_contents = []
        if payload.attachments:
            for att in payload.attachments:
                if att.get("base64"):
                    b64 = att["base64"]
                    if "," in b64:
                        b64 = b64.split(",")[1]
                    file_contents.append(ImageContent(image_base64=b64))

        llm_msg = UserMessage(
            text=user_msg,
            file_contents=file_contents if file_contents else None
        )

        response = await chat.send_message(llm_msg)

        return ChatResponse(
            response=response,
            sessionId=session_id,
            model=model_used,
            mode="user"
        )

    except Exception as e:
        print(f"AlKabeer Bot Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
def health():
    return {"status": "ok", "bot": "AlKabeer Abu Fahad (Dev Mode Enabled)"}


@router.get("/customization")
def get_customization(user_id: str = Query("manager"), path: str = Query("/")):
    resolved = _resolve_customization_with_fallback(user_id, path)
    cfg = resolved.get("config") or {}
    resolved_user_id = str(resolved.get("resolved_user_id") or user_id)
    return {
        "success": True,
        "data": {
            "user_id": user_id,
            "resolved_user_id": resolved_user_id,
            "path": path,
            "labels": cfg.get("labels", {}),
            "hidden": cfg.get("hidden", {}),
            "contents": cfg.get("contents", {}),
            "custom_cards": cfg.get("custom_cards", []),
            "block_order": cfg.get("block_order", []),
            "positions": cfg.get("positions", {}),
            "styles": cfg.get("styles", {}),
            "assets": cfg.get("assets", {}),
            "page_manifest": cfg.get("page_manifest", {}),
        },
    }


@router.put("/customization")
def save_customization(payload: CustomizationUpdateRequest):
    user_id = str(payload.user_id or "manager").strip() or "manager"
    path = str(payload.path or "/").strip() or "/"
    data = _read_customizations()
    user_node = data.get(user_id) or {}
    page_cfg = user_node.get(path) or {"labels": {}, "hidden": {}, "contents": {}, "custom_cards": [], "block_order": [], "positions": {}, "styles": {}, "assets": {}, "page_manifest": {}}
    updated_cfg = {
        "labels": payload.labels if payload.labels is not None else page_cfg.get("labels") or {},
        "hidden": payload.hidden if payload.hidden is not None else page_cfg.get("hidden") or {},
        "contents": payload.contents if payload.contents is not None else page_cfg.get("contents") or {},
        "custom_cards": payload.custom_cards if payload.custom_cards is not None else page_cfg.get("custom_cards") or [],
        "block_order": payload.block_order if payload.block_order is not None else page_cfg.get("block_order") or [],
        "positions": payload.positions if payload.positions is not None else page_cfg.get("positions") or {},
        "styles": payload.styles if payload.styles is not None else page_cfg.get("styles") or {},
        "assets": payload.assets if payload.assets is not None else page_cfg.get("assets") or {},
        "page_manifest": payload.page_manifest if payload.page_manifest is not None else page_cfg.get("page_manifest") or {},
    }
    user_node[path] = updated_cfg
    data[user_id] = user_node
    _write_customizations(data)

    cfg = _get_user_page_config(user_id, path)
    return {
        "success": True,
        "data": {
            "user_id": user_id,
            "path": path,
            "labels": cfg.get("labels", {}),
            "hidden": cfg.get("hidden", {}),
            "contents": cfg.get("contents", {}),
            "custom_cards": cfg.get("custom_cards", []),
            "block_order": cfg.get("block_order", []),
            "positions": cfg.get("positions", {}),
            "styles": cfg.get("styles", {}),
            "assets": cfg.get("assets", {}),
            "page_manifest": cfg.get("page_manifest", {}),
        },
    }


@router.get("/editor/draft")
def get_editor_draft(user_id: str = Query("manager"), path: str = Query("/")):
    latest = _editor_get_latest_draft(user_id, path)
    if latest:
        return {
            "success": True,
            "data": {
                "id": latest.get("id"),
                "user_id": user_id,
                "path": path,
                "version": int(latest.get("version") or 0),
                "status": latest.get("status") or "draft",
                "note": latest.get("note") or "",
                "config": _editor_sanitize_config(latest.get("config") or {}),
                "updated_at": latest.get("updated_at") or latest.get("created_at"),
            },
        }

    cfg = _get_user_page_config(user_id, path)
    return {
        "success": True,
        "data": {
            "id": None,
            "user_id": user_id,
            "path": path,
            "version": 0,
            "status": "published",
            "note": "fallback_from_customization",
            "config": _editor_sanitize_config(cfg),
            "updated_at": None,
        },
    }


@router.post("/editor/draft/save")
def save_editor_draft(payload: EditorDraftSaveRequest):
    user_id = str(payload.user_id or "manager").strip() or "manager"
    path = str(payload.path or "/").strip() or "/"
    status = str(payload.status or "draft").strip().lower() or "draft"
    note = str(payload.note or "manual_save").strip() or "manual_save"
    record = _editor_save_snapshot(user_id, path, payload.config or {}, status=status, note=note)
    return {"success": True, "data": record}


@router.post("/editor/publish")
def publish_editor_payload(payload: EditorDraftSaveRequest):
    user_id = str(payload.user_id or "manager").strip() or "manager"
    path = str(payload.path or "/").strip() or "/"
    config = _editor_sanitize_config(payload.config or {})

    # Publish to customization map (source of truth for live website)
    save_customization(
        CustomizationUpdateRequest(
            user_id=user_id,
            path=path,
            labels=config.get("labels"),
            hidden=config.get("hidden"),
            contents=config.get("contents"),
            custom_cards=config.get("custom_cards"),
            block_order=config.get("block_order"),
            positions=config.get("positions"),
            styles=config.get("styles"),
            assets=config.get("assets"),
            page_manifest=config.get("page_manifest"),
        )
    )

    record = _editor_save_snapshot(user_id, path, config, status="published", note="publish")
    return {"success": True, "data": record}


@router.get("/editor/history")
def get_editor_history(user_id: str = Query("manager"), path: str = Query("/"), limit: int = Query(40)):
    safe_limit = max(1, min(200, int(limit or 40)))
    rows = _editor_list_history(user_id, path, safe_limit)
    return {"success": True, "data": rows}


@router.get("/editor/comments")
def get_editor_comments(path: str = Query("/"), user_id: Optional[str] = Query(None), limit: int = Query(120)):
    safe_limit = max(1, min(300, int(limit or 120)))
    rows = _editor_list_comments(path, user_id, safe_limit)
    return {"success": True, "data": rows}


@router.post("/editor/comments")
def add_editor_comment(payload: EditorCommentCreateRequest):
    message = str(payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Comment message is required")
    row = _editor_add_comment(
        path=str(payload.path or "/").strip() or "/",
        user_id=str(payload.user_id or "manager").strip() or "manager",
        block_id=str(payload.block_id or "").strip(),
        message=message,
        author_name=payload.author_name,
    )
    return {"success": True, "data": row}


@router.put("/editor/comments/{comment_id}")
def update_editor_comment(comment_id: str, payload: EditorCommentUpdateRequest):
    row = _editor_update_comment(comment_id, payload.resolved, payload.message)
    if not row:
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"success": True, "data": row}


@router.delete("/editor/comments/{comment_id}")
def delete_editor_comment(comment_id: str):
    ok = _editor_delete_comment(comment_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"success": True}


@router.post("/assets/upload")
async def upload_editor_asset(user_id: str = Query("manager"), file: UploadFile = File(...)):
    ext = (file.filename or "asset.bin").split(".")[-1] if "." in (file.filename or "") else "bin"
    path = f"{APP_NAME}/uploads/{user_id}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    content_type = file.content_type or _guess_content_type(file.filename or "asset.bin")
    result = _put_object(path, data, content_type)

    asset_id = str(uuid.uuid4())
    record = {
        "id": asset_id,
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result.get("size") or len(data),
        "created_at": datetime.utcnow().isoformat(),
        "is_deleted": False,
    }

    if editor_db is not None:
        await editor_db.editor_assets.insert_one(record)
    else:
        rows = _read_editor_assets()
        rows.append(record)
        _write_editor_assets(rows)

    return {
        "success": True,
        "asset": {
            "id": asset_id,
            "filename": file.filename,
            "content_type": content_type,
            "download_url": f"/api/alkabeer-bot/assets/{asset_id}/download",
            "storage_path": result["path"],
        }
    }


@router.get("/assets/{asset_id}/download")
async def download_editor_asset(asset_id: str):
    record = None
    if editor_db is not None:
        record = await editor_db.editor_assets.find_one({"id": asset_id, "is_deleted": False}, {"_id": 0})
    else:
        record = next((row for row in _read_editor_assets() if str(row.get("id")) == asset_id and not row.get("is_deleted")), None)
    if not record:
        raise HTTPException(status_code=404, detail="Asset not found")
    data, content_type = _get_object(record["storage_path"])
    return Response(content=data, media_type=record.get("content_type") or content_type)
