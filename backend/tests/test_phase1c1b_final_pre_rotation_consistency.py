"""Phase 1C.1B final pre-rotation consistency checks (read-only artifact validation)."""

import json
from pathlib import Path


ROOT = Path("/app")
DISCOVERY = ROOT / "memory" / "discovery"

REPORT_MD = DISCOVERY / "PHASE_1C1B_FINAL_PRE_ROTATION_CONSISTENCY_REPORT.md"
INVENTORY_JSON = DISCOVERY / "PHASE_1C1B_HISTORICAL_SECRET_EXPOSURE_INVENTORY.json"
INVENTORY_MD = DISCOVERY / "PHASE_1C1B_HISTORICAL_SECRET_EXPOSURE_INVENTORY.md"
ROTATION_JSON = DISCOVERY / "PHASE_1C1B_EXTERNAL_ROTATION_ACTION_LIST.json"
FINGERPRINT_DEF_MD = DISCOVERY / "PHASE_1C_FINANCIAL_FINGERPRINT_DEFINITION.md"
FINGERPRINT_JSON = DISCOVERY / "FINAL_PHASE_1C1B_PREDEPLOY_FINANCIAL_FINGERPRINT.json"
AUTHZ_FP_JSON = DISCOVERY / "PHASE_1C1A_AUTHORIZATION_REPRODUCIBLE_FINGERPRINT.json"

EXPECTED_CHECKSUM = "5fb3453999ae85f5390d977293f5bd5c977e984df574530e92caf5ff981993c7"


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_required_reference_artifacts_exist():
    """Required discovery artifacts should exist for final consistency closure."""
    required = [
        REPORT_MD,
        INVENTORY_JSON,
        INVENTORY_MD,
        ROTATION_JSON,
        FINGERPRINT_DEF_MD,
        FINGERPRINT_JSON,
        AUTHZ_FP_JSON,
    ]
    missing = [str(p) for p in required if not p.exists()]
    assert missing == [], f"Missing required artifact(s): {missing}"


def test_anthropic_api_key_classification_consistent():
    """ANTHROPIC_API_KEY must remain placeholder-only with NO rotation_required and explicit justification."""
    inventory = _read_json(INVENTORY_JSON)
    anthropic = next((x for x in inventory if x.get("key_name") == "ANTHROPIC_API_KEY"), None)
    assert anthropic is not None
    assert anthropic.get("historical_credential_real_nonempty") == "NO"
    assert anthropic.get("historical_nonempty_value_seen") is False
    assert anthropic.get("historical_placeholder_only") is True
    assert anthropic.get("rotation_required") == "NO"
    assert bool((anthropic.get("justification") or "").strip()) is True


def test_no_unknown_or_active_real_credentials_without_justification_when_no_rotation():
    """No active/unknown real historical credential should be marked NO rotation without explicit justification."""
    inventory = _read_json(INVENTORY_JSON)
    bad = []
    for item in inventory:
        is_real_credential = item.get("historical_credential_real_nonempty") == "YES"
        active_or_unknown = item.get("still_active") in {"YES", "UNKNOWN"}
        rotation_no = item.get("rotation_required") == "NO"
        has_justification = bool((item.get("justification") or "").strip())
        if is_real_credential and active_or_unknown and rotation_no and not has_justification:
            bad.append(item.get("key_name"))
    assert bad == []


def test_rotation_required_env_key_count_is_16():
    """Total exposed secret env keys requiring rotation must be 16."""
    inventory = _read_json(INVENTORY_JSON)
    rotation_required = [x for x in inventory if x.get("rotation_required") == "YES"]
    assert len(rotation_required) == 16


def test_rotation_group_count_is_13_and_db_alias_grouping_present():
    """Distinct credential rotation groups should be 13 and DB alias group must be grouped together."""
    groups = _read_json(ROTATION_JSON)
    assert len(groups) == 13

    db_group = next((
        g
        for g in groups
        if g.get("provider") == "Postgres/Supabase DB"
        and g.get("credential") == "Legacy Postgres connection credential"
    ), None)
    assert db_group is not None
    assert set(db_group.get("affected_env_variables", [])) == {
        "DATABASE_URL",
        "DIRECT_URL",
        "POSTGRES_PASSWORD",
    }


def test_public_route_terminology_normalized_and_no_unrestricted_8_public_endpoints_claim():
    """Public route terminology must use normalized 8/7 language and avoid unrestricted '8 public endpoints' claims."""
    report_text = _read_text(REPORT_MD)
    assert "PUBLIC_POLICY_ROWS = 8" in report_text
    assert "PUBLIC_UNIQUE_API_ROUTES = 7" in report_text
    assert "PUBLIC_EXTERNAL_FRAMEWORK_ROUTES = 0" in report_text
    assert "PUBLIC_INTERNAL_HEALTH_ROUTE = 1" in report_text
    assert "8 public endpoints" not in report_text.lower()

    auth_fp = _read_json(AUTHZ_FP_JSON)
    assert auth_fp.get("PUBLIC_POLICY_ROWS") == 8
    assert auth_fp.get("PUBLIC_UNIQUE_API_ROUTES") == 7
    assert auth_fp.get("PUBLIC_EXTERNAL_FRAMEWORK_ROUTES") == 0
    assert auth_fp.get("PUBLIC_INTERNAL_HEALTH_ROUTE") == 1


def test_financial_fingerprint_terminology_and_counts_are_normalized():
    """Financial fingerprint must use normalized row/reversal terminology with expected non-reversal count."""
    fp = _read_json(FINGERPRINT_JSON)
    assert "journal_row_count" in fp
    assert "reversal_entry_count" in fp
    assert "non_reversal_entry_count" in fp
    assert "explicit_reversal_link_count" in fp
    assert fp.get("non_reversal_entry_count") == 170

    definition = _read_text(FINGERPRINT_DEF_MD)
    assert "journal_active_business_record_count" in definition
    assert "is deprecated and must not be used as final terminology" in definition


def test_fingerprint_checksum_matches_expected():
    """Fingerprint checksum must match expected finalized checksum."""
    fp = _read_json(FINGERPRINT_JSON)
    assert fp.get("checksum_sha256") == EXPECTED_CHECKSUM

    report_text = _read_text(REPORT_MD)
    assert EXPECTED_CHECKSUM in report_text


def test_scope_constraints_no_mutation_no_deploy_no_engine_change_no_migration_no_phase2():
    """Scope constraints must remain strict and non-destructive."""
    report_text = _read_text(REPORT_MD)
    assert "NO DEPLOY" in report_text
    assert "NO PHASE 2" in report_text
    assert "NO PRODUCTION DATA MUTATION" in report_text
    assert "NO ACCOUNTINGENGINE CHANGES" in report_text
    assert "NO MIGRATIONS" in report_text

    fp = _read_json(FINGERPRINT_JSON)
    assert fp.get("mutation_performed") == "NO"
    assert fp.get("accounting_engine_changed") == "NO"
