"""Phase 1B final consistency checks on discovery artifacts (read-only, no DB/API mutation)."""

import json
from collections import Counter
from pathlib import Path


ROOT = Path("/app")
DISCOVERY = ROOT / "memory" / "discovery"

MATRIX_PATH = DISCOVERY / "authz_matrix_phase1b.json"
WRITERS_PATH = DISCOVERY / "write_path_audit_phase1b_consistency.json"
REPORT_PATH = DISCOVERY / "PHASE_1B_FINAL_CONSISTENCY_REPORT.md"


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_text(path: Path):
    return path.read_text(encoding="utf-8")


def test_canonical_totals_and_closure_counters():
    matrix = _read_json(MATRIX_PATH)
    assert len(matrix) == 512

    counts = Counter(r.get("phase1b_authz") for r in matrix)
    assert counts["PUBLIC_INTENTIONAL"] == 8
    assert counts["GENERAL_AUTHENTICATED_READ"] == 109
    assert counts["SELF_ONLY_READ"] == 6
    assert counts["ROLE_RESTRICTED_READ"] == 16
    assert counts["PERMISSION_RESTRICTED_READ"] == 106
    assert counts["AUTHZ_COMPLETE"] == 267

    allowed = {
        "PUBLIC_INTENTIONAL",
        "GENERAL_AUTHENTICATED_READ",
        "SELF_ONLY_READ",
        "ROLE_RESTRICTED_READ",
        "PERMISSION_RESTRICTED_READ",
        "AUTHZ_COMPLETE",
    }
    unknown = [r for r in matrix if r.get("phase1b_authz") not in allowed]
    assert len(unknown) == 0

    report = _read_text(REPORT_PATH)
    assert "- MISSING_AUTHZ: 0" in report
    assert "- POLICY_DECISION_REQUIRED: 0" in report
    assert "- AUTH_ONLY_NO_OBJECT_CHECK: 0" in report
    assert "- UNKNOWN: 0" in report


def test_public_allowlist_is_exactly_8_and_explanations_present():
    report = _read_text(REPORT_PATH)

    assert "العدد النهائي الصحيح Canonical هو 8 public endpoints" in report
    assert "رقم 17 كان من closure script legacy" in report
    assert "495 في closure_authz_after.py ليس تصنيفاً Canonical" in report

    expected_public = [
        "GET /api/approvals/public/{token}",
        "POST /api/approvals/public/{token}/respond",
        "POST /api/auth/google/session",
        "POST /api/auth/login",
        "POST /api/auth/logout",
        "POST /api/auth/refresh",
        "GET /api/health",
    ]
    for item in expected_public:
        assert item in report

    numbered = [line for line in report.splitlines() if line.strip().startswith(tuple(f"{i:02d}." for i in range(1, 9)))]
    assert len(numbered) == 8


def test_writer_audit_286_rows_corrected_fields_and_no_unknown_or_fake_defaults():
    rows = _read_json(WRITERS_PATH)
    assert len(rows) == 286

    required_fields = [
        "actor_scope",
        "route_service_caller",
        "permission_source",
        "object_resource_scope",
        "payload_validation_mechanism",
        "mass_assignment_protection_mechanism",
        "canonical_business_path",
        "financial_effect",
    ]

    for row in rows:
        for field in required_fields:
            assert field in row
            assert isinstance(row[field], str)
            assert row[field].strip() != ""
            assert row[field] != "UNKNOWN"

    blob = json.dumps(rows, ensure_ascii=False)
    assert "\"S\":\"self\"" not in blob
    assert "\"V\":\"alw\"" not in blob
    assert "\"M\":\"guard\"" not in blob
    assert "S=self" not in blob
    assert "V=alw" not in blob
    assert "M=guard" not in blob
