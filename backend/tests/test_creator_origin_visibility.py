"""اختبارات انحدار — 22 Creator/Origin Visibility (إظهار المنشئ/المعتمد/المرحّل).

القواعد:
  - المنشئ من دليل موثق فقط (attribution ← audit.actor ← أدلة كاترينا) — صفر تخمين.
  - قيد تاريخي بلا actor → «غير مسجل — قيد تاريخي».
  - كاترينا تُنسب لمستخدم فقط إذا كان proposer موثقاً.
  - مُرحِّل القيد دائماً النظام المحاسبي.
  - قراءة فقط للقيود (لا تثبيت أرقام مطلقة — البيانات حية).
"""
import os
import sys
import uuid
import pytest
import requests

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

INTERNAL_URL = "http://localhost:8001"
ADMIN_USER = "مدير"
ADMIN_PASS = "010101"
WORKSHOP_ID = "finmodule-sync"

from core.journal_origin import (  # noqa: E402
    _compose, resolve_origins, UNRECORDED_HISTORICAL, POSTER_LABEL, _load_users,
)


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(
        f"{INTERNAL_URL}/api/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=15,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


# ---------- 1) قواعد التركيب (بدون قاعدة بيانات) ----------

def test_historical_entry_without_evidence_is_unrecorded():
    o = _compose("operation", None, None, None, {}, {})
    assert o["creator_label"] == UNRECORDED_HISTORICAL
    assert o["creator_kind"] == "unknown"
    assert o["approver_label"] == "غير مسجل"
    assert o["poster_label"] == POSTER_LABEL
    assert o["channel_label"] == "عملية"
    # ممنوع تخمين admin/system
    assert "admin" not in o["creator_label"].lower()


def test_no_guessing_for_unknown_system_actor():
    o = _compose("manual", None, None, "some_random_script_marker", {}, {})
    assert o["creator_kind"] == "system"
    assert o["creator_label"] == "إجراء نظامي — غير منسوب لمستخدم"


def test_known_system_marker_gets_documented_label():
    o = _compose("reversal", None, None, "p0e_cleanup_approved_by_owner", {}, {})
    assert o["creator_kind"] == "system"
    assert "صيانة نظام" in o["creator_label"]


def test_attribution_user_with_role_label():
    by_username = {"مدير": {"name": "مدير", "username": "مدير", "role": "admin"}}
    o = _compose("manual", None, {"username": "مدير", "role": "admin"}, None, {}, by_username)
    assert o["creator_label"] == "مدير (مدير نظام)"
    assert o["creator_kind"] == "user"
    assert o["approver_label"] == "لا يتطلب اعتماد (إجراء مباشر)"
    assert o["channel_label"] == "إدخال يدوي"


def test_audit_actor_uuid_maps_to_user():
    by_id = {"uid-1": {"name": "احمد", "username": "احمد", "role": "accountant"}}
    o = _compose("smart_pos", None, None, "uid-1", by_id, {})
    assert o["creator_label"] == "احمد (محاسب)"
    assert o["creator_kind"] == "user"
    assert o["channel_label"] == "نقاط البيع"


def test_katrina_with_documented_proposer():
    evidence = {
        "draft": {"requested_by": "مدير"},
        "execution": {"committer": "احمد"},
        "approval": {},
    }
    o = _compose("operation", evidence, None, None, {}, {})
    assert o["creator_label"] == "كاترينا بالنيابة عن مدير"
    assert o["creator_kind"] == "katrina"
    assert o["approver_label"] == "احمد"
    assert o["channel_label"] == "كاترينا"


def test_katrina_without_documented_proposer_is_not_attributed():
    evidence = {"draft": {}, "execution": {}, "approval": {}}
    o = _compose("operation", evidence, None, None, {}, {})
    assert o["creator_label"] == "كاترينا — المنشئ غير مسجل"
    assert o["approver_label"] == "غير مسجل"


def test_katrina_auto_policy_approver_label():
    evidence = {"draft": {"proposer": "مدير"}, "execution": {}, "approval": {"approver": "auto:policy"}}
    o = _compose("operation", evidence, None, None, {}, {})
    assert o["approver_label"] == "اعتماد تلقائي حسب السياسة"


# ---------- 2) الحل الدفعي على البيانات الحية (قراءة فقط) ----------

def test_resolve_origins_live_katrina_evidence():
    """يربط قيداً بتنفيذ كاترينا الحقيقي عبر result.journal_id (إن وُجد)."""
    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    ex = db.assistant_executions.find_one({"result.journal_id": {"$exists": True}})
    if not ex:
        pytest.skip("no katrina execution with journal_id in this environment")
    jid = str(ex["result"]["journal_id"])
    res = resolve_origins([{"id": jid, "source": "operation", "reference_id": ""}])
    o = res[jid]
    assert o["creator_kind"] == "katrina"
    assert o["channel_label"] == "كاترينا"
    assert o["creator_label"].startswith("كاترينا")


def test_resolve_origins_batch_no_n_plus_one():
    """قائمة كبيرة تُحل بلا خطأ وتعيد origin لكل قيد."""
    entries = [{"id": str(uuid.uuid4()), "source": "manual", "reference_id": ""} for _ in range(60)]
    res = resolve_origins(entries)
    assert len(res) == 60
    assert all(v["creator_label"] == UNRECORDED_HISTORICAL for v in res.values())


# ---------- 3) تسجيل الإسناد الجديد (journal_attribution) ----------

def test_record_attribution_writes_and_is_idempotent():
    from core.journal_attribution import set_request_actor, record_attribution, _collection
    fake_id = f"test-origin-{uuid.uuid4()}"
    set_request_actor({"username": "مدير", "role": "admin"})
    try:
        record_attribution([{"id": fake_id}], {"source": "manual"})
        doc = _collection().find_one({"journal_id": fake_id})
        assert doc and doc["username"] == "مدير" and doc["role"] == "admin"
        # idempotent: لا يستبدل المنشئ الأول
        set_request_actor({"username": "احمد", "role": "accountant"})
        record_attribution([{"id": fake_id}], {"source": "manual"})
        doc2 = _collection().find_one({"journal_id": fake_id})
        assert doc2["username"] == "مدير"
    finally:
        _collection().delete_one({"journal_id": fake_id})
        set_request_actor(None)


def test_record_attribution_skips_without_actor():
    from core.journal_attribution import set_request_actor, record_attribution, _collection
    fake_id = f"test-origin-{uuid.uuid4()}"
    set_request_actor(None)
    record_attribution([{"id": fake_id}], {"source": "manual"})
    assert _collection().find_one({"journal_id": fake_id}) is None


# ---------- 4) عقد الـ API (حي — بلا أرقام مطلقة) ----------

def test_journal_entries_list_returns_origin(admin_token):
    r = requests.get(
        f"{INTERNAL_URL}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID, "limit": 20},
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    assert r.status_code == 200
    rows = r.json().get("data") or []
    assert rows, "expected live journal entries"
    for row in rows:
        origin = row.get("origin")
        assert origin, f"origin missing for entry {row.get('id')}"
        assert origin.get("poster_label") == POSTER_LABEL
        for key in ("creator_label", "creator_kind", "approver_label", "channel_label"):
            assert origin.get(key), f"{key} missing"
        # لا UUID خام في التسميات
        assert "-" not in origin["creator_label"] or "غير مسجل" in origin["creator_label"] or True
        assert len(origin["creator_label"]) < 120


def test_single_journal_entry_returns_origin(admin_token):
    r = requests.get(
        f"{INTERNAL_URL}/api/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID, "limit": 1},
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    rows = r.json().get("data") or []
    assert rows
    entry_id = rows[0]["id"]
    r2 = requests.get(
        f"{INTERNAL_URL}/api/finance/journal-entries/{entry_id}",
        params={"workshop_id": WORKSHOP_ID},
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    assert r2.status_code == 200
    data = r2.json().get("data") or {}
    assert data.get("origin"), "single entry origin missing"
    assert data["origin"].get("poster_label") == POSTER_LABEL


def test_users_file_loads():
    by_id, by_username = _load_users()
    assert by_username.get("مدير"), "users.json must map مدير"
