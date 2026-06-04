"""
🧪 Phase 3C — Live E2E Integration Tester (matches the L16 spec)

Runs against the live FastAPI backend (port 8001) on the /api/runtime alias
endpoints. Not a pytest — invoke directly:

    python3 /app/backend/tests/run_phase_3c_integration.py
"""
import requests
import uuid  # noqa: F401  (kept to mirror the user-provided test contract)
import time  # noqa: F401

BASE_URL = "http://localhost:8001/api/runtime"

REPORT = {
    "passed": 0,
    "failed": 0,
    "tests": [],
    "ids": {
        "drafts": [],
        "approvals": [],
        "executions": [],
    },
}


# ── HTTP helpers ────────────────────────────────────────────────────────────

def post(path, data):
    try:
        r = requests.post(f"{BASE_URL}{path}", json=data, timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def get(path):
    try:
        r = requests.get(f"{BASE_URL}{path}", timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ── Assertion helper ────────────────────────────────────────────────────────

def check(name, condition, response):
    status = "PASS" if condition else "FAIL"
    if condition:
        REPORT["passed"] += 1
    else:
        REPORT["failed"] += 1
    REPORT["tests"].append({"test": name, "status": status, "response": response})
    print(f"[{status}] {name}")


# ── Tests ───────────────────────────────────────────────────────────────────

def test_create_customer():
    res = post("/power", {"text": "أضف عميل أحمد العتيبي 0501234567 بريدة"})
    draft = res.get("draft")
    approval = res.get("approval")
    if draft and approval:
        REPORT["ids"]["drafts"].append(draft["id"])
        REPORT["ids"]["approvals"].append(approval["approval_id"])
    check("Create Customer Draft", draft is not None, res)
    check("Approval Created", approval is not None, res)


def test_approve():
    if not REPORT["ids"]["approvals"]:
        check("Approve Draft", False, {"error": "no approval to test"})
        return
    approval_id = REPORT["ids"]["approvals"][-1]
    res = post(f"/approve/{approval_id}", {})
    check("Approve Draft", res.get("status") == "approved", res)


def test_commit():
    if not REPORT["ids"]["drafts"]:
        check("Commit Execution", False, {"error": "no draft to commit"})
        return
    draft_id = REPORT["ids"]["drafts"][-1]
    res = post(f"/commit/{draft_id}", {})
    if "execution_id" in res:
        REPORT["ids"]["executions"].append(res["execution_id"])
    check("Commit Execution", "execution_id" in res, res)


def test_vehicle():
    res = post("/power", {"text": "أضف مركبة 9935"})
    check("Vehicle Draft", res.get("draft") is not None, res)


def test_visit():
    res = post("/power", {"text": "أنشئ زيارة صيانة"})
    check("Visit Draft", res.get("draft") is not None, res)


def test_data_integrity():
    res = get("/report")
    check("System Report Accessible", isinstance(res, dict) and "mode" in res, res)


def test_rollback():
    if not REPORT["ids"]["executions"]:
        check("Rollback Execution", False, {"error": "no execution to rollback"})
        return
    execution_id = REPORT["ids"]["executions"][-1]
    res = post(f"/rollback/{execution_id}", {})
    check("Rollback Execution", res.get("status") == "rolled_back", res)


# ── Runner ──────────────────────────────────────────────────────────────────

def run_all():
    print("🚀 Starting ERP Auto Tester (Phase 3C)…\n")
    test_create_customer()
    test_approve()
    test_commit()
    test_vehicle()
    test_visit()
    test_data_integrity()
    test_rollback()

    total = REPORT["passed"] + REPORT["failed"]
    score = (REPORT["passed"] / total) * 100 if total else 0

    print("\n📊 FINAL REPORT")
    print("=" * 32)
    print(f"Passed:        {REPORT['passed']}")
    print(f"Failed:        {REPORT['failed']}")
    print(f"Drafts:        {REPORT['ids']['drafts']}")
    print(f"Approvals:     {REPORT['ids']['approvals']}")
    print(f"Executions:    {REPORT['ids']['executions']}")
    print(f"System Score:  {round(score, 2)}%")
    return REPORT


if __name__ == "__main__":
    run_all()
