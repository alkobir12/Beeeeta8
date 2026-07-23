"""Iteration 285 — verify UI-emitted template_incomplete audit for CUSTOMER_NAME.

Modules/features covered:
- Read runtime template_id produced in Iter285 setup
- Validate Mongo audit contains template_incomplete with CUSTOMER_NAME from UI flow
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv("/app/backend/.env")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
RUNTIME_PATH = Path("/app/test_reports/iter285_runtime.json")


def test_ui_logged_template_incomplete_with_customer_name():
    # Module: Mongo audit evidence for UI guard event payload.
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL/DB_NAME missing")
    if not RUNTIME_PATH.exists():
        pytest.skip("Iter285 runtime file missing")

    runtime = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
    template_id = runtime.get("template_id")
    if not template_id:
        pytest.skip("template_id missing in runtime file")

    client = MongoClient(MONGO_URL)
    try:
        col = client[DB_NAME]["document_template_resolution_audit"]
        row = col.find_one(
            {
                "template_id": template_id,
                "event": "template_incomplete",
                "missing_variables": {"$in": ["CUSTOMER_NAME"]},
            },
            sort=[("created_at", -1)],
        )
        assert isinstance(row, dict), "No UI/template audit row found for CUSTOMER_NAME"
        assert row.get("event") == "template_incomplete"
        assert "CUSTOMER_NAME" in (row.get("missing_variables") or [])
    finally:
        client.close()
