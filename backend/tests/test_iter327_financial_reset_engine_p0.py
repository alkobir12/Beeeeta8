"""P0 Financial Reset Engine regression: dry-run, execute guard, legacy routes, invariants."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")

pytestmark = pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL is required")


EXPECTED_DRY_RUN = {
    "active_vehicle_count": 14,
    "vehicles_with_receivables": 11,
    "total_receivables_before_reset": 13475.84,
    "total_opening_receivables_after_reset": 13475.84,
    "operations_to_archive": 55,
    "journal_entries_to_archive": 33,
    "vehicle_visits_to_mark_archived_period": 180,
}


def _assert_close(actual: float, expected: float, tol: float = 0.01) -> None:
    assert abs(float(actual) - float(expected)) <= tol, f"expected {expected}, got {actual}"


@pytest.fixture
def client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def admin_token(client: requests.Session) -> str:
    response = client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "مدير", "pin": "123123"},
        timeout=20,
    )
    assert response.status_code == 200, f"login failed: {response.status_code} {response.text[:300]}"
    data = response.json()
    token = data.get("access_token")
    assert token and isinstance(token, str)
    return token


@pytest.fixture
def admin_client(client: requests.Session, admin_token: str) -> requests.Session:
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return client


def _dry_run(admin_client: requests.Session) -> dict:
    response = admin_client.get(
        f"{BASE_URL}/api/finance/reset/dry-run",
        params={"workshop_id": "finmodule-sync"},
        timeout=30,
    )
    assert response.status_code == 200, f"dry-run failed: {response.status_code} {response.text[:300]}"
    payload = response.json()
    assert payload.get("success") is True
    data = payload.get("data") or {}
    assert data.get("mode") == "dry_run"
    return data


def test_dry_run_admin_returns_expected_summary(admin_client: requests.Session):
    """GET /api/finance/reset/dry-run should match expected preview numbers and be executable."""
    data = _dry_run(admin_client)
    summary = data.get("summary") or {}

    assert data.get("can_execute") is True
    assert (data.get("needs_review") or []) == []

    assert summary.get("active_vehicle_count") == EXPECTED_DRY_RUN["active_vehicle_count"]
    assert summary.get("vehicles_with_receivables") == EXPECTED_DRY_RUN["vehicles_with_receivables"]
    _assert_close(
        summary.get("total_receivables_before_reset"),
        EXPECTED_DRY_RUN["total_receivables_before_reset"],
    )
    _assert_close(
        summary.get("total_opening_receivables_after_reset"),
        EXPECTED_DRY_RUN["total_opening_receivables_after_reset"],
    )


def test_execute_rejects_wrong_confirmation_and_counts_unchanged(admin_client: requests.Session):
    """POST /api/finance/reset/execute with wrong confirmation must fail and keep counters unchanged."""
    before = _dry_run(admin_client)
    token = before.get("generated_at")
    assert token

    execute_response = admin_client.post(
        f"{BASE_URL}/api/finance/reset/execute",
        json={
            "workshop_id": "finmodule-sync",
            "dry_run_token": token,
            "confirmation_text": "عبارة خاطئة",
        },
        timeout=30,
    )
    assert execute_response.status_code == 409
    detail = (execute_response.json() or {}).get("detail") or {}
    assert detail.get("error") == "reset_blocked"
    assert "confirmation_text_invalid" in str(detail.get("msg") or "")

    after = _dry_run(admin_client)
    before_summary = before.get("summary") or {}
    after_summary = after.get("summary") or {}

    for field in (
        "operations_to_archive",
        "journal_entries_to_archive",
        "vehicle_visits_to_mark_archived_period",
        "total_receivables_before_reset",
        "total_opening_receivables_after_reset",
    ):
        _assert_close(after_summary.get(field), before_summary.get(field))

    assert after.get("can_execute") is True
    assert (after.get("needs_review") or []) == []


def test_legacy_keep_debts_only_routes_return_410(admin_client: requests.Session):
    """Legacy keep-debts-only delete routes are disabled and must return HTTP 410."""
    r1 = admin_client.delete(
        f"{BASE_URL}/api/cleanup/keep-debts-only",
        params={"confirm": "KEEP_DEBTS_ONLY"},
        timeout=20,
    )
    assert r1.status_code == 410
    d1 = (r1.json() or {}).get("detail") or {}
    assert d1.get("error") == "legacy_keep_debts_only_disabled"

    r2 = admin_client.delete(
        f"{BASE_URL}/api/finance/reset-ops-journals-keep-debts",
        params={"workshop_id": "finmodule-sync", "confirm": "KEEP_DEBTS_ONLY"},
        timeout=20,
    )
    assert r2.status_code == 410
    d2 = (r2.json() or {}).get("detail") or {}
    assert d2.get("error") == "legacy_keep_debts_only_disabled"


def test_proof_script_after_dry_run_reports_overall_pass_and_unchanged_counts():
    """Run all-pages proof script and assert expected invariants after dry-run-only testing."""
    result = subprocess.run(
        ["python", "/app/scripts/prove_financial_system_all_pages.py"],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, f"script failed: {result.stdout}\n{result.stderr}"

    proof_path = Path("/app/test_reports/financial_system_all_pages_proof.json")
    assert proof_path.exists()
    proof = json.loads(proof_path.read_text(encoding="utf-8"))

    assert proof.get("overall_pass") is True
    counts = proof.get("readiness_counts") or {}
    assert counts.get("operations") == EXPECTED_DRY_RUN["operations_to_archive"]
    assert counts.get("journal_entries") == EXPECTED_DRY_RUN["journal_entries_to_archive"]
    assert counts.get("vehicle_visits") == EXPECTED_DRY_RUN["vehicle_visits_to_mark_archived_period"]
