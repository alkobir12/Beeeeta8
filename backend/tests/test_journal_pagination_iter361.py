"""اختبارات انحدار — دفتر اليومية النهائي (Pagination/Search/Filters/KPI/POS Projection).

قواعد: قراءة فقط — صفر تعديل مالي. البيانات حية (الإنتاج يشارك نفس Supabase)
فلا تثبيت أرقام مطلقة؛ الأعداد تُستخرج وقت الاختبار وتُقارن داخلياً.
"""
import os
import sys
from datetime import datetime, timedelta

import pytest
import requests

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

INTERNAL_URL = "http://localhost:8001"
WORKSHOP_ID = "finmodule-sync"
ADMIN_USER = "مدير"
ADMIN_PASS = "010101"


@pytest.fixture(scope="session")
def admin_headers():
    r = requests.post(
        f"{INTERNAL_URL}/api/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.text}"
    tok = r.json().get("access_token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


def _get(headers, **params):
    base = {"workshop_id": WORKSHOP_ID}
    base.update(params)
    r = requests.get(f"{INTERNAL_URL}/api/finance/journal-entries", params=base, headers=headers, timeout=60)
    assert r.status_code == 200, f"journal fetch failed: {r.status_code} {r.text[:200]}"
    return r.json()


def _walk_all_pages(headers, page_size, **extra):
    first = _get(headers, page=1, page_size=page_size, **extra)
    total_count = first["total_count"]
    total_pages = first["total_pages"]
    ids, seq = set(), []
    page = 1
    body = first
    while True:
        items = body["data"]
        for it in items:
            seq.append(str(it["id"]))
            ids.add(str(it["id"]))
        if page >= total_pages or not items:
            break
        page += 1
        body = _get(headers, page=page, page_size=page_size, **extra)
    return total_count, total_pages, ids, seq, first


# ---------- 21: PAGINATION REGRESSION ----------

@pytest.mark.parametrize("page_size", [25, 50])
def test_pagination_no_duplicates_no_missing(admin_headers, page_size):
    total, pages, ids, seq, first = _walk_all_pages(admin_headers, page_size)
    # live data: أعد المحاولة مرة إذا تحرك العدد أثناء المشي
    if len(seq) != total or len(ids) != total:
        total, pages, ids, seq, first = _walk_all_pages(admin_headers, page_size)
    assert len(seq) == total, f"PAGINATION_MISSING/DUP: collected={len(seq)} expected={total}"
    assert len(ids) == total, f"PAGINATION_DUPLICATES: unique={len(ids)} expected={total}"
    expected_pages = (total + page_size - 1) // page_size
    assert pages == expected_pages
    assert len(first["data"]) <= page_size


def test_stable_ordering_two_walks(admin_headers):
    t1, _, _, seq1, _ = _walk_all_pages(admin_headers, 25)
    t2, _, _, seq2, _ = _walk_all_pages(admin_headers, 25)
    if t1 != t2:
        pytest.skip("live data moved between walks — not an ordering bug")
    assert seq1 == seq2, "STABLE_ORDERING failed: sequences differ between identical walks"


def test_invalid_page_size_falls_back_to_25(admin_headers):
    body = _get(admin_headers, page=1, page_size=999)
    assert body["page_size"] == 25


# ---------- 23: KPI REGRESSION (كامل النتائج لا الصفحة) ----------

def test_kpi_constant_across_pages(admin_headers):
    p1 = _get(admin_headers, page=1, page_size=25)
    if p1["total_pages"] < 2:
        pytest.skip("dataset fits one page")
    p2 = _get(admin_headers, page=2, page_size=25)
    plast = _get(admin_headers, page=p1["total_pages"], page_size=25)
    for key in ("total_count", "total_debit", "total_credit", "total_movement",
                "income_count", "income_amount", "outflow_count", "outflow_amount"):
        vals = {p1["kpi"][key], p2["kpi"][key], plast["kpi"][key]}
        if len(vals) != 1:
            # حركة إنتاج حية محتملة — تحقق بإعادة قراءة
            r1 = _get(admin_headers, page=1, page_size=25)
            r2 = _get(admin_headers, page=2, page_size=25)
            assert r1["kpi"][key] == r2["kpi"][key], f"KPI {key} changes with page"
    assert p1["kpi"]["total_count"] == p1["total_count"]
    assert p1["kpi"]["total_count"] > len(p1["data"]) or p1["total_pages"] == 1


# ---------- 22: SEARCH / FILTER REGRESSION ----------

def test_kind_filters_partition_the_journal(admin_headers):
    total_all = _get(admin_headers, page=1, page_size=25)["total_count"]
    parts = 0
    for kind in ("income", "collection", "outflow", "other"):
        parts += _get(admin_headers, page=1, page_size=25, entry_kind=kind)["total_count"]
    if parts != total_all:
        # إعادة قراءة واحدة تحسباً لنشاط حي
        total_all = _get(admin_headers, page=1, page_size=25)["total_count"]
        parts = sum(_get(admin_headers, page=1, page_size=25, entry_kind=k)["total_count"]
                    for k in ("income", "collection", "outflow", "other"))
    assert parts == total_all, f"kind partition mismatch: {parts} != {total_all}"


def test_search_server_side_full_dataset(admin_headers):
    # اختر طرفاً حقيقياً من البيانات الحية
    sample = _get(admin_headers, page=1, page_size=50)
    party = next((e["party_label"] for e in sample["data"]
                  if e.get("party_label") and e["party_label"] not in ("مفتوح",)), None)
    if not party:
        pytest.skip("no party label in first page")
    total, _, ids, seq, first = _walk_all_pages(admin_headers, 25, search=party)
    assert total >= 1
    assert len(ids) == total, "search pagination delta != 0"
    fields = ("id", "reference_id", "description", "party_label", "vehicle_label",
              "operation_type_label", "transaction_type_label_ar", "payment_method_label_ar")
    for e in first["data"]:
        hay = " ".join(str(e.get(f) or "") for f in fields).lower()
        assert party.lower() in hay, f"result does not match search: {e['id']}"


def test_search_by_entry_id_locates_entry(admin_headers):
    sample = _get(admin_headers, page=1, page_size=25)
    target = sample["data"][0]["id"]
    body = _get(admin_headers, page=1, page_size=25, search=target)
    assert body["total_count"] >= 1
    assert any(str(e["id"]) == str(target) for e in body["data"])


def test_search_resets_scope_correctly_with_filter(admin_headers):
    body = _get(admin_headers, page=1, page_size=25, entry_kind="income", search="لا-يوجد-نص-مطابق-قطعاً-12345")
    assert body["total_count"] == 0
    assert body["data"] == []
    assert body["total_pages"] == 0


# ---------- 6: DATE FILTERS APPLIED IN BACKEND ----------

def test_date_filter_boundaries(admin_headers):
    sample = _get(admin_headers, page=1, page_size=25)
    entry = sample["data"][0]
    d = str(entry["date"])[:10]
    same_day = _get(admin_headers, page=1, page_size=50, start_date=d, end_date=d)
    # القيد داخل حدود نفس اليوم (بداية/نهاية اليوم)
    total, _, ids, _, _ = _walk_all_pages(admin_headers, 50, start_date=d, end_date=d)
    assert str(entry["id"]) in ids, "boundary entry missing from same-day filter"
    assert same_day["total_count"] == total
    # نهاية قبل يوم القيد تستبعده
    day_before = (datetime.strptime(d, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    _, _, ids_before, _, _ = _walk_all_pages(admin_headers, 50, end_date=day_before)
    assert str(entry["id"]) not in ids_before, "end_date not applied in backend query"


# ---------- 24: POS REGRESSION (Filtered Projection من الدفتر القانوني) ----------

def _canonical_pos_ids():
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    rows = sb.table("journal_entries").select("id, description").eq("workshop_id", WORKSHOP_ID).execute().data or []
    return {str(r["id"]) for r in rows if "SOURCE:SMART_POS" in str(r.get("description") or "").upper()}


def test_pos_projection_matches_canonical(admin_headers):
    canonical = _canonical_pos_ids()
    total, _, ids, _, first = _walk_all_pages(admin_headers, 25, entry_kind="pos")
    if ids != canonical:
        canonical = _canonical_pos_ids()
        total, _, ids, _, first = _walk_all_pages(admin_headers, 25, entry_kind="pos")
    assert ids == canonical, f"POS_MISSING={len(canonical - ids)} POS_DUPLICATES/extra={len(ids - canonical)}"
    assert total == len(canonical)
    assert first["kpi"]["pos_total_count"] == total
    for e in first["data"]:
        assert e.get("is_pos") is True


def test_pos_journal_parity_same_entry(admin_headers):
    pos_body = _get(admin_headers, page=1, page_size=25, entry_kind="pos")
    if not pos_body["data"]:
        pytest.skip("no POS entries")
    pos_entry = pos_body["data"][0]
    main_body = _get(admin_headers, page=1, page_size=25, search=pos_entry["id"])
    match = next((e for e in main_body["data"] if str(e["id"]) == str(pos_entry["id"])), None)
    assert match, "POS entry not found in main journal search"
    for key in ("total", "date", "transaction_type", "source", "payment_status",
                "is_pos", "is_reversed", "reversed_of"):
        assert match.get(key) == pos_entry.get(key), f"POS parity failed on {key}"
    assert (match.get("origin") or {}).get("creator_label") == (pos_entry.get("origin") or {}).get("creator_label"), \
        "POS_ATTRIBUTION_PARITY failed"


# ---------- 11: REVERSALS VISIBLE + CROSS-LINKED ----------

def test_reversal_cross_links(admin_headers):
    total, _, _, _, first = _walk_all_pages(admin_headers, 50)
    all_items = []
    body = first
    page = 1
    while True:
        all_items.extend(body["data"])
        if page >= body["total_pages"] or not body["data"]:
            break
        page += 1
        body = _get(admin_headers, page=page, page_size=50)
    reversal = next((e for e in all_items if e.get("reversed_of")), None)
    if not reversal:
        pytest.skip("no reversal entries in ledger")
    original = next((e for e in all_items if str(e["id"]) == str(reversal["reversed_of"])), None)
    assert original is not None, "original entry hidden — must remain visible"
    assert original.get("is_reversed") is True
    assert str(original.get("reversal_id")) == str(reversal["id"])
    # إسناد مستقل لكل منهما
    assert (original.get("origin") or {}).get("creator_label")
    assert (reversal.get("origin") or {}).get("creator_label")


# ---------- 25: ATTRIBUTION PRESERVED (Batch على الصفحة فقط) ----------

def test_attribution_preserved_on_paginated_items(admin_headers):
    body = _get(admin_headers, page=1, page_size=25)
    labels = set()
    for e in body["data"]:
        origin = e.get("origin")
        assert origin and origin.get("creator_label"), f"origin missing for {e['id']}"
        assert origin.get("poster_label") == "النظام المحاسبي (المحرك الموحد)"
        labels.add(origin["creator_kind"])
        if origin["creator_kind"] == "unknown":
            assert origin["creator_label"] == "غير مسجل — قيد تاريخي"
            assert "admin" not in origin["creator_label"].lower()
    assert labels, "no attribution resolved"


# ---------- DEEP LINKS: فلتر الحساب (?account=) من دليل الحسابات ----------

def test_account_filter_matches_entry_lines(admin_headers):
    sample = _get(admin_headers, page=1, page_size=25)
    code = None
    for e in sample["data"]:
        for ln in (e.get("lines") or []):
            c = str(ln.get("code") or ln.get("account") or "").strip()
            if c:
                code = c
                break
        if code:
            break
    if not code:
        pytest.skip("no account codes in lines")
    total, _, ids, _, first = _walk_all_pages(admin_headers, 25, account=code)
    assert total >= 1
    assert len(ids) == total
    for e in first["data"]:
        codes = {str(ln.get("code") or ln.get("account") or "").strip() for ln in (e.get("lines") or [])}
        assert code in codes, f"entry {e['id']} lacks account {code}"


def test_search_by_reference_id_deep_link(admin_headers):
    sample = _get(admin_headers, page=1, page_size=50)
    ref_entry = next((e for e in sample["data"] if str(e.get("reference_id") or "").strip() and not str(e.get("reference_id")).startswith("reversal::")), None)
    if not ref_entry:
        pytest.skip("no reference ids on first page")
    body = _get(admin_headers, page=1, page_size=25, search=ref_entry["reference_id"])
    assert body["total_count"] >= 1
    assert any(str(e["id"]) == str(ref_entry["id"]) for e in body["data"])


# ---------- LEGACY MODE UNCHANGED ----------

def test_legacy_mode_shape_unchanged(admin_headers):
    body = _get(admin_headers, limit=5)
    assert body.get("success") is True
    assert "page" not in body and "total_pages" not in body and "kpi" not in body
    assert isinstance(body.get("data"), list) and len(body["data"]) <= 5
    assert body["data"][0].get("origin") is not None
