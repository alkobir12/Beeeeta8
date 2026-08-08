"""MongoDB provider for route modules that must not import server.py."""

from __future__ import annotations

import os
from motor.motor_asyncio import AsyncIOMotorClient

_CLIENT = None
_DB = None


def get_mongo_db():
    global _CLIENT, _DB
    if _DB is not None:
        return _DB
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    _CLIENT = AsyncIOMotorClient(mongo_url)
    _DB = _CLIENT[db_name]
    return _DB
