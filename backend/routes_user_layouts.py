from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List
import os
import json

from supabase_service import SupabaseService
from core import authz as _authz

router = APIRouter(prefix="/api")

DB_PROVIDER = os.environ.get("DB_PROVIDER", "mongo").lower()

supabase = SupabaseService()
_db = None


def set_db(database):
    global _db
    _db = database


# ---------- models ----------
class LayoutUpdate(BaseModel):
    page: str = Field(..., description="page key, e.g. vehicleDetails")
    blocks: List[str] = Field(..., description="ordered list of block ids")


# ---------- helpers ----------

MEM_FILE = os.path.join(os.path.dirname(__file__), "uploads", "user_layouts.json")


def _mem_read() -> List[dict]:
    try:
        os.makedirs(os.path.join(os.path.dirname(__file__), "uploads"), exist_ok=True)
        if not os.path.exists(MEM_FILE):
            with open(MEM_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        with open(MEM_FILE, "r", encoding="utf-8") as f:
            return json.load(f) or []
    except Exception:
        return []


def _mem_write(rows: List[dict]):
    os.makedirs(os.path.join(os.path.dirname(__file__), "uploads"), exist_ok=True)
    with open(MEM_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


# ---------- routes ----------
@router.get("/user-layouts/{user_id}/{page}")
async def get_layout(user_id: str, page: str, request: Request):
    actor = await _authz.resolve_request_actor(request)
    _authz.ensure_self_actor(actor, user_id)
    try:
        if DB_PROVIDER == "supabase" and not supabase.mock_mode:
            res = (
                supabase.client.table("user_layouts")
                .select("blocks")
                .eq("user_id", user_id)
                .eq("page", page)
                .maybe_single()
                .execute()
            )
            if not res or not res.data:
                return {"userId": user_id, "page": page, "blocks": []}
            return {"userId": user_id, "page": page, "blocks": res.data.get("blocks") or []}

        if DB_PROVIDER == "memory":
            rows = _mem_read()
            row = next((r for r in rows if r.get("userId") == user_id and r.get("page") == page), None)
            return {"userId": user_id, "page": page, "blocks": (row or {}).get("blocks") or []}

        # Mongo fallback
        row = await _db.user_layouts.find_one({"userId": user_id, "page": page}, {"_id": 0})
        if not row:
            return {"userId": user_id, "page": page, "blocks": []}
        return row
    except Exception:
        # fallback to memory
        rows = _mem_read()
        row = next((r for r in rows if r.get("userId") == user_id and r.get("page") == page), None)
        return {"userId": user_id, "page": page, "blocks": (row or {}).get("blocks") or []}


@router.put("/user-layouts/{user_id}/{page}")
async def upsert_layout(user_id: str, page: str, payload: LayoutUpdate, request: Request):
    actor = await _authz.resolve_request_actor(request)
    _authz.ensure_self_actor(actor, user_id)
    if payload.page != page:
        raise HTTPException(status_code=400, detail="Page mismatch")

    doc = {"userId": user_id, "page": page, "blocks": payload.blocks}

    try:
        if DB_PROVIDER == "supabase" and not supabase.mock_mode:
            # upsert by (user_id, page)
            up_doc = {"user_id": user_id, "page": page, "blocks": payload.blocks}
            supabase.client.table("user_layouts").upsert(up_doc).execute()
            return doc

        if DB_PROVIDER == "memory":
            rows = _mem_read()
            idx = next((i for i, r in enumerate(rows) if r.get("userId") == user_id and r.get("page") == page), -1)
            if idx >= 0:
                rows[idx] = doc
            else:
                rows.append(doc)
            _mem_write(rows)
            return doc

        # Mongo
        await _db.user_layouts.update_one(
            {"userId": user_id, "page": page}, {"$set": doc}, upsert=True
        )
        return doc
    except HTTPException:
        raise
    except Exception:
        rows = _mem_read()
        idx = next((i for i, r in enumerate(rows) if r.get("userId") == user_id and r.get("page") == page), -1)
        if idx >= 0:
            rows[idx] = doc
        else:
            rows.append(doc)
        _mem_write(rows)
        return doc
