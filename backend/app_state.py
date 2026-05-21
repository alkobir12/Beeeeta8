"""
🌐 Shared App State

Holds runtime references used by routers that were extracted from server.py:
  • db                 — MongoDB AsyncIO database (or None for memory/supabase)
  • DB_PROVIDER        — "mongo" | "memory" | "supabase"
  • supabase_service   — SupabaseService instance

Plus shared helpers:
  • mem_read(name)     — read from uploads/<name>.json (seeded for known names)
  • mem_write(name)    — write list to uploads/<name>.json (datetime-safe)

server.py initializes this on startup; extracted routers import lazily.
"""

import json
import os
import uuid
from pathlib import Path
from typing import Any, List


# Public, mutable state — set by server.py at startup.
db = None
DB_PROVIDER: str = os.environ.get("DB_PROVIDER", "mongo").lower()
supabase_service = None  # type: Optional[Any]


def configure(database, provider: str, supa) -> None:
    """Initialize/refresh app state. Called once from server.py on startup."""
    global db, DB_PROVIDER, supabase_service
    db = database
    DB_PROVIDER = (provider or "mongo").lower()
    supabase_service = supa


# --- File-based memory store (seeded for known datasets) ---
_ROOT_DIR = Path(__file__).parent
_MEM_DIR = _ROOT_DIR / "uploads"
_MEM_DIR.mkdir(exist_ok=True)


def _mem_path(name: str) -> Path:
    return _MEM_DIR / f"{name}.json"


def mem_read(name: str) -> List[Any]:
    """Read a JSON list from uploads/<name>.json. Seeds known datasets on first read."""
    p = _mem_path(name)
    if not p.exists():
        seed: List[Any] = []
        if name == "services":
            seed = [
                {"id": str(uuid.uuid4()), "name": "تغيير زيت", "category": "زيوت", "price": 120, "duration": 30, "active": True},
                {"id": str(uuid.uuid4()), "name": "فحص كمبيوتر", "category": "تشخيص", "price": 150, "duration": 40, "active": True},
            ]
        elif name == "technicians":
            seed = [
                {"id": str(uuid.uuid4()), "name": "فني أحمد", "phone": "", "specialty": "ميكانيكا"},
                {"id": str(uuid.uuid4()), "name": "فني علي", "phone": "", "specialty": "كهرباء"},
            ]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(seed, f, ensure_ascii=False, indent=2)
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def mem_write(name: str, items: List[Any]) -> None:
    """Write list to uploads/<name>.json with datetime-to-ISO conversion."""
    p = _mem_path(name)
    cleaned_items: List[Any] = []
    for item in items:
        if isinstance(item, dict):
            cleaned = {}
            for k, v in item.items():
                if hasattr(v, "isoformat"):
                    cleaned[k] = v.isoformat()
                else:
                    cleaned[k] = v
            cleaned_items.append(cleaned)
        else:
            cleaned_items.append(item)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cleaned_items, f, ensure_ascii=False, indent=2)
