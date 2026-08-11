"""Iter349: P0-B preview live read-only verification (no writes)."""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pytest
import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from core.unified_financial_engine import build_current_ar_snapshot
from supabase_service import SupabaseService


WORKSHOP_ID = "finmodule-sync"
VEHICLE_A = "b885d618-a2fa-45df-b14f-0a9e9ff1b484"
VISIT_A = "174f49a1-5482-43d5-b333-ede2743a7d79"
VEHICLE_B = "8708bbd6-18be-4fb0-93a4-f9818b2b91ad"
VISIT_B = "3b1ccedf-29c6-4d9e-9108-f11a7bcc5c5e"
P0B_REPORT = Path("/app/test_reports/p0b_targeted_correction.json")


def _round2(value) -> float:
    try:
        return float(Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0.0


def _line_code(line: dict) -> str:
    return str(line.get("account") or line.get("code") or line.get("account_code") or "").strip()


def _impact(rows: list[dict]) -> dict:
    ar = Decimal("0.00")
    revenue = Decimal("0.00")
    for row in rows:
        for line in row.get("lines") or []:
            code = _line_code(line)
            debit = Decimal(str(_round2(line.get("debit"))))
            credit = Decimal(str(_round2(line.get("credit"))))
            if code in {"005", "1103", "113"}:
                ar += debit - credit
            if code in {"024", "025", "026", "027", "041", "042", "4000", "4100", "4101", "4102"}:
                revenue += credit - debit
    return {"ar": float(ar), "revenue": float(revenue)}


def _resolve_base_url() -> str:
    direct = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip()
    if direct:
        return direct.rstrip("/")
    env_file = Path("/app/frontend/.env")
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        if key.strip() == "REACT_APP_BACKEND_URL":
            return value.strip().rstrip("/")
    return ""


@pytest.fixture(scope="session")
def p0b_report() -> dict:
    assert P0B_REPORT.exists(), f"Missing P0-B report: {P0B_REPORT}"
    return json.loads(P0B_REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def supa_client():
    supa = SupabaseService()
    assert not supa.mock_mode, "P0-B live verification requires real Supabase client"
    return supa.client


@pytest.fixture(scope="session")
def auth_headers() -> dict:
    base_url = _resolve_base_url()
    if not base_url:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "مدير", "password": "010101"},
        timeout=30,
    )
    assert response.status_code == 200, response.text[:300]
    payload = response.json() or {}
    token = payload.get("access_token") or payload.get("token")
    assert token, "Login succeeded but no token returned"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _rows_by_reference(client, reference_id: str) -> list[dict]:
    return (
        client.table("journal_entries")
        .select("*")
        .eq("reference_id", reference_id)
        .execute()
        .data
        or []
    )


def test_p0b_report_shape_and_targeted_scope(p0b_report):
    # Module: artifact-level contract for targeted P0-B correction set.
    assert p0b_report.get("mode") == "apply"
    plan = p0b_report.get("plan") or []
    assert len(plan) == 3
    assert {row.get("target", {}).get("visit_id") for row in plan} == {VISIT_A, VISIT_B}
    assert all(bool(row.get("journal_id")) for row in plan)
    assert all(bool(row.get("correction_reference")) for row in plan)


def test_p0b_originals_exist_and_have_single_targeted_reversal_each(supa_client, p0b_report):
    # Module: live lineage verification (originals preserved, exactly one targeted correction per original).
    plan = p0b_report.get("plan") or []
    refs = []
    for row in plan:
        original_id = row["journal_id"]
        original_rows = supa_client.table("journal_entries").select("*").eq("id", original_id).execute().data or []
        assert len(original_rows) == 1, f"Missing original journal: {original_id}"

        correction_ref = row["correction_reference"]
        refs.append(correction_ref)
        correction_rows = (
            supa_client.table("journal_entries")
            .select("*")
            .eq("reference_id", correction_ref)
            .eq("source", "historical_financial_repair")
            .execute()
            .data
            or []
        )
        assert len(correction_rows) == 1, f"Expected 1 correction for {original_id}, got {len(correction_rows)}"

    all_repairs = (
        supa_client.table("journal_entries")
        .select("id,reference_id,source")
        .eq("source", "historical_financial_repair")
        .execute()
        .data
        or []
    )
    assert len(all_repairs) == 3, "Unexpected extra historical_financial_repair rows"
    assert {r.get("reference_id") for r in all_repairs} == set(refs)


def test_p0b_case_a_canonical_and_net_impact_are_exact(supa_client, p0b_report):
    # Module: Case-A canonical uniqueness + net AR/revenue effect (2300).
    plan = p0b_report.get("plan") or []
    case_a = [row for row in plan if row.get("target", {}).get("vehicle_id") == VEHICLE_A]
    original_ids = [row["journal_id"] for row in case_a]
    correction_refs = [row["correction_reference"] for row in case_a]

    originals = []
    for journal_id in original_ids:
        originals.extend(supa_client.table("journal_entries").select("*").eq("id", journal_id).execute().data or [])
    corrections = []
    for ref in correction_refs:
        corrections.extend(_rows_by_reference(supa_client, ref))

    canonical_ref = f"vehfinal:{VEHICLE_A}"
    canonical = _rows_by_reference(supa_client, canonical_ref)
    assert len(canonical) == 1, f"Expected one canonical {canonical_ref}, got {len(canonical)}"
    assert _round2(canonical[0].get("total")) == 2300.00

    net = _impact(originals + corrections + canonical)
    assert net == {"ar": 2300.0, "revenue": 2300.0}


def test_p0b_case_b_supplier_effect_zero_and_no_customer_canonical_sale(supa_client, auth_headers, p0b_report):
    # Module: Case-B net AR/revenue zero, supplier archive retained, and no canonical customer sale.
    plan = p0b_report.get("plan") or []
    case_b = next(row for row in plan if row.get("target", {}).get("vehicle_id") == VEHICLE_B)

    original = supa_client.table("journal_entries").select("*").eq("id", case_b["journal_id"]).execute().data or []
    correction = _rows_by_reference(supa_client, case_b["correction_reference"])
    assert len(original) == 1
    assert len(correction) == 1
    assert _impact(original + correction) == {"ar": 0.0, "revenue": 0.0}

    assert len(_rows_by_reference(supa_client, f"vehfinal:{VEHICLE_B}")) == 0
    assert len(_rows_by_reference(supa_client, f"visitfinal:{VISIT_B}")) == 0

    base_url = _resolve_base_url()
    response = requests.get(
        f"{base_url}/api/vehicles/{VEHICLE_B}/financial-summary",
        headers=auth_headers,
        timeout=45,
    )
    assert response.status_code == 200, response.text[:300]
    summary = response.json() or {}
    assert _round2(summary.get("supplier_archive_total")) == 167.84


def test_p0b_income_statement_and_ar_core_targets(auth_headers):
    # Module: legal post-P0-B totals (Income Statement + AR core).
    base_url = _resolve_base_url()
    income = requests.get(
        f"{base_url}/api/finance/reports/income-statement",
        params={"workshop_id": WORKSHOP_ID, "start_date": "2026-08-01", "end_date": "2026-08-31"},
        headers=auth_headers,
        timeout=60,
    )
    assert income.status_code == 200, income.text[:300]
    payload = income.json() or {}
    assert payload.get("success") is True
    totals = (payload.get("data") or {}).get("totals") or {}
    audit = (payload.get("data") or {}).get("revenue_source_audit") or {}

    assert _round2(totals.get("revenue")) == 9794.00
    assert _round2(totals.get("expenses")) == 2274.00
    assert _round2(totals.get("net_income")) == 7520.00
    assert int(audit.get("unknown_entries_count") or len(audit.get("unknown_entries") or [])) == 0

    snapshot = build_current_ar_snapshot(SupabaseService().client, WORKSHOP_ID)
    assert _round2(snapshot.get("total_ar")) == 9181.00
