"""Iter347 live Preview guardrails: blocked mutations + immutable financial fingerprints."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
import requests

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.append(str(BACKEND))

from supabase_service import SupabaseService


WORKSHOP_ID = "finmodule-sync"


def _resolve_base_url() -> str:
    value = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip()
    if value:
        return value.rstrip("/")
    env_file = Path("/app/frontend/.env")
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        if key.strip() == "REACT_APP_BACKEND_URL":
            return val.strip().rstrip("/")
    return ""


def _credentials_from_memory() -> Tuple[str, str]:
    username = (os.environ.get("TEST_MANAGER_USERNAME") or "").strip()
    password = (os.environ.get("TEST_MANAGER_PASSWORD") or "").strip()
    if username and password:
        return username, password

    path = Path("/app/memory/test_credentials.md")
    if not path.exists():
        return "", ""

    text = path.read_text(encoding="utf-8")
    user_match = re.search(r"\|\s*`([^`]+)`\s*\|\s*admin\s*\|", text)
    pass_match = re.search(r"\|\s*`مدير`\s*\|\s*admin\s*\|[^\n]*\|\s*`([^`]+)`\s*\|", text)
    return (
        user_match.group(1).strip() if user_match else "",
        pass_match.group(1).strip() if pass_match else "",
    )


def _table_fetch_all(client: Any, table: str, *, page_size: int = 1000) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    start = 0
    while True:
        rows = (
            client.table(table)
            .select("*")
            .order("id")
            .range(start, start + page_size - 1)
            .execute()
            .data
            or []
        )
        out.extend(rows)
        if len(rows) < page_size:
            break
        start += page_size
    return out


def _fingerprint(rows: List[Dict[str, Any]]) -> str:
    normalized = sorted(rows, key=lambda r: str(r.get("id") or ""))
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _snapshot(client: Any) -> Dict[str, Dict[str, Any]]:
    tables = {
        "journal_entries": _table_fetch_all(client, "journal_entries"),
        "operations": _table_fetch_all(client, "operations"),
        "accounts": _table_fetch_all(client, "accounts"),
        "vehicle_visits": _table_fetch_all(client, "vehicle_visits"),
    }
    return {
        name: {"count": len(rows), "sha256": _fingerprint(rows)}
        for name, rows in tables.items()
    }


@pytest.fixture(scope="session")
def base_url() -> str:
    value = _resolve_base_url()
    if not value:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    return value


@pytest.fixture(scope="session")
def auth_session(base_url: str):
    username, password = _credentials_from_memory()
    if not username or not password:
        pytest.skip("Preview manager credentials missing in /app/memory/test_credentials.md")

    session = requests.Session()
    response = session.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:400]
    token = (response.json() or {}).get("access_token") or (response.json() or {}).get("token")
    assert token, "Missing access token in login response"
    session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def supa_client():
    supa = SupabaseService()
    if supa.mock_mode or not supa.client:
        pytest.skip("Supabase client unavailable for preview fingerprint checks")
    return supa.client


# Module: live blocked endpoints + immutable fingerprint verification
def test_preview_guardrails_block_mutations_and_preserve_fingerprints(auth_session, base_url: str, supa_client):
    before = _snapshot(supa_client)

    blocked_410 = [
        ("/api/finance/reports/reclassify-payment-accounts", {"workshop_id": WORKSHOP_ID, "apply_changes": "true"}),
        ("/api/finance/reports/apply-bank-revenue-policy", {"workshop_id": WORKSHOP_ID, "apply_changes": "true"}),
        ("/api/finance/reports/reclassify-vehicle-workshop-dues", {"workshop_id": WORKSHOP_ID, "apply_changes": "true"}),
        ("/api/finance/reports/migrate-legacy-codes", {"workshop_id": WORKSHOP_ID, "apply_changes": "true"}),
        ("/api/finance/reports/reclassify-revenue-sub-accounts", {"workshop_id": WORKSHOP_ID, "apply_changes": "true"}),
        ("/api/finance/reports/repost-bank-and-fix-imbalance", {"workshop_id": WORKSHOP_ID, "apply_changes": "false"}),
        ("/api/finance/reports/reconciliation/backfill-journals", {"workshop_id": WORKSHOP_ID, "apply_changes": "true"}),
    ]

    for path, params in blocked_410:
        response = auth_session.post(f"{base_url}{path}", params=params, timeout=60)
        assert response.status_code == 410, f"{path} => {response.status_code}: {response.text[:300]}"

    integrity_fix = auth_session.post(
        f"{base_url}/api/operations/integrity/fix-all",
        json={},
        timeout=60,
    )
    assert integrity_fix.status_code == 410, integrity_fix.text[:300]

    manual_update = auth_session.put(
        f"{base_url}/api/finance/journal-entries/non-existent-id",
        params={"workshop_id": WORKSHOP_ID},
        json={"description": "blocked-test"},
        timeout=60,
    )
    assert manual_update.status_code == 410, manual_update.text[:300]

    legacy_vehicle_posting = auth_session.post(
        f"{base_url}/api/vehicles/non-existent-id/save-parts-and-create-journal",
        json=[{"name": "fixture", "price": 1, "quantity": 1}],
        timeout=60,
    )
    assert legacy_vehicle_posting.status_code == 410, legacy_vehicle_posting.text[:300]
    assert (legacy_vehicle_posting.json().get("detail") or {}).get("error") == "legacy_vehicle_parts_auto_posting_disabled"

    reset_execute = auth_session.post(
        f"{base_url}/api/finance/reset/execute",
        json={
            "confirmation_text": "anything",
            "dry_run_token": "anything",
            "workshop_id": WORKSHOP_ID,
        },
        timeout=60,
    )
    assert reset_execute.status_code in {409, 410}, reset_execute.text[:300]

    dry_run = auth_session.post(
        f"{base_url}/api/finance/reports/reconciliation/backfill-journals",
        params={"workshop_id": WORKSHOP_ID, "apply_changes": "false"},
        timeout=120,
    )
    assert dry_run.status_code == 200, dry_run.text[:300]
    dry_data = ((dry_run.json() or {}).get("data") or {})
    assert int(dry_data.get("missing_count") or -1) == 43

    supplier_invalid = auth_session.post(
        f"{base_url}/api/suppliers-ext/import/execute",
        json={
            "rows": [["مورد", "100", "2026-08-11", "credit"], ["مورد", "0", "2026-08-11", "credit"]],
            "mapping": {"name_col": 0, "amount_col": 1, "date_col": 2, "type_col": 3},
            "workshop_id": WORKSHOP_ID,
        },
        timeout=120,
    )
    assert supplier_invalid.status_code == 400, supplier_invalid.text[:400]

    after = _snapshot(supa_client)
    assert after == before
    assert after["journal_entries"]["count"] == 36
    assert after["operations"]["count"] == 56
    assert after["accounts"]["count"] == 192
    assert after["vehicle_visits"]["count"] == 181
