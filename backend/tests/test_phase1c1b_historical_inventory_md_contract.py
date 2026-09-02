"""Read-only contract checks for PHASE_1C1B historical inventory markdown export."""

import json
from pathlib import Path


DISCOVERY = Path("/app/memory/discovery")
INVENTORY_JSON = DISCOVERY / "PHASE_1C1B_HISTORICAL_SECRET_EXPOSURE_INVENTORY.json"
INVENTORY_MD = DISCOVERY / "PHASE_1C1B_HISTORICAL_SECRET_EXPOSURE_INVENTORY.md"


def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_inventory_markdown_exists_and_declares_no_secret_values():
    """Markdown artifact must exist and explicitly state no secret values are shown."""
    assert INVENTORY_MD.exists(), f"Missing artifact: {INVENTORY_MD}"
    text = _read_text(INVENTORY_MD)
    assert "No secret values are shown." in text


def test_inventory_markdown_matches_json_metadata_rows():
    """Each JSON inventory item should be represented in markdown metadata table (no value checks)."""
    items = _read_json(INVENTORY_JSON)
    md = _read_text(INVENTORY_MD)

    for item in items:
        key_name = item["key_name"]
        file_name = item["file"]
        first_commit_short = item["first_exposure_commit"][:12]
        last_commit_short = item["last_exposure_commit"][:12]
        credential_class = item["credential_class"]
        still_active = item["still_active"]
        rotation_required = item["rotation_required"]
        rotation_status = item["rotation_status"]
        justification = item["justification"]

        expected_row = (
            f"| `{key_name}` | `{file_name}` | `{first_commit_short}` | `{last_commit_short}` | "
            f"{credential_class} | {still_active} | {rotation_required} | {rotation_status} | {justification} |"
        )
        assert expected_row in md, f"Missing/changed markdown metadata row for key: {key_name}"


def test_inventory_markdown_row_count_matches_json_length():
    """Markdown table should contain one metadata row per JSON item."""
    items = _read_json(INVENTORY_JSON)
    md_lines = _read_text(INVENTORY_MD).splitlines()
    table_rows = [ln for ln in md_lines if ln.startswith("| `")]
    assert len(table_rows) == len(items)
