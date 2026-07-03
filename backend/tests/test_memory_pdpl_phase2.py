"""🧪 RRR المرحلة 2 — اختبارات محرك الذاكرة (قواعد الترقية الخمس) + منقّح PDPL."""
import time
import uuid

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from core import memory_engine as me
from core.pdpl_redactor import redact_pii


# ─────────────────────────── PDPL Redactor ───────────────────────────

class TestPdplRedactor:
    def test_saudi_phone_masked_keeps_tail(self):
        out = redact_pii("جوال العميل 0545443355 للتواصل")
        assert "0545443355" not in out
        assert "05****3355" in out

    def test_intl_phone_masked(self):
        out = redact_pii("رقم +966545443355 مسجل")
        assert "545443355" not in out.replace("****", "")
        assert "3355" in out

    def test_national_id_masked(self):
        out = redact_pii("هوية رقم 1023456789")
        assert "1023456789" not in out
        assert out.count("89") >= 1

    def test_iban_masked(self):
        out = redact_pii("آيبان SA0380000000608010167519")
        assert "SA0380000000608010167519" not in out
        assert "SA****7519" in out

    def test_email_partially_masked(self):
        out = redact_pii("البريد ahmad.saleh@example.com")
        assert "ahmad.saleh@example.com" not in out
        assert "@example.com" in out

    def test_amounts_and_names_untouched(self):
        src = "فاتورة عمر الخضيري بمبلغ 4500.50 ر.س بتاريخ 2026-06-29"
        assert redact_pii(src) == src

    def test_empty_safe(self):
        assert redact_pii("") == ""


# ─────────────────────────── Memory Engine ───────────────────────────

@pytest.fixture()
def mem(monkeypatch):
    """عزل الاختبارات في collection مستقلة ثم تنظيفها."""
    monkeypatch.setattr(me, "_ENABLED", None)
    monkeypatch.setattr(me, "_db", None)
    monkeypatch.setattr(me, "_client", None)
    if not me.is_enabled():
        pytest.skip("MongoDB غير متاح")
    test_col = f"assistant_memory_test_{uuid.uuid4().hex[:6]}"
    monkeypatch.setattr(me, "COL", test_col)
    yield me
    me._database()[test_col].drop()


class TestRule1SessionToShort:
    def test_classified_item_recorded_as_short(self, mem):
        d = mem.record("decision", "اعتماد شراء فلتر 40 ريال", session_id="s1", user="مدير")
        assert d and d["layer"] == "short" and d["kind"] == "decision"

    def test_empty_content_not_recorded(self, mem):
        assert mem.record("decision", "", session_id="s1") is None


class TestRule2ShortToLong:
    def test_promotes_after_three_sessions(self, mem):
        c = "المورد الفهد يفضل التحويل البنكي"
        mem.record("fact", c, session_id="s1")
        mem.record("fact", c, session_id="s2")
        d = mem.record("fact", c, session_id="s3")
        assert d["layer"] == "long"

    def test_two_sessions_not_enough(self, mem):
        c = "الزيت المفضل شل هيلكس"
        mem.record("fact", c, session_id="s1")
        d = mem.record("fact", c, session_id="s2")
        assert d["layer"] == "short"

    def test_admin_correction_promotes_immediately(self, mem):
        d = mem.record("correction", "التصنيف الصحيح للبواجي: قطع غيار",
                       session_id="s1", user="مدير", admin=True)
        assert d["layer"] == "long"

    def test_expired_short_deleted_after_30_days(self, mem):
        d = mem.record("fact", "معلومة قديمة ستنتهي", session_id="s1")
        col = mem._database()[mem.COL]
        col.update_one({"id": d["id"]},
                       {"$set": {"created_at": time.time() - 31 * 86400}})
        mem.record("fact", "معلومة جديدة تطلق التنظيف", session_id="s2")
        assert col.find_one({"id": d["id"]}) is None


class TestRule3HumanApprovalOnly:
    def test_propose_creates_draft_and_approval(self, mem):
        res = mem.propose_knowledge(content="ساعة العمل تبدأ 8 صباحاً",
                                    topic="دوام", proposer="مدير")
        assert res.get("draft") and res.get("approval")
        assert res["draft"]["action"] == "memory_promote"
        assert res["draft"]["status"] == "pending_approval"
        # لم تُرقَّ للمعرفة قبل الاعتماد
        doc = mem._database()[mem.COL].find_one({"id": res["memory"]["id"]})
        assert doc["layer"] == "long"

    def test_no_auto_promotion_to_knowledge(self, mem):
        c = "معلومة متكررة كثيراً"
        for i in range(6):
            d = mem.record("fact", c, session_id=f"s{i}")
        assert d["layer"] == "long"  # تقف عند long — لا knowledge تلقائياً


class TestRule4Contamination:
    def test_conflicting_older_knowledge_marked_disputed(self, mem):
        col = mem._database()[mem.COL]
        old = mem.record("fact", "نسبة الضريبة 5%", topic="ضريبة")
        col.update_one({"id": old["id"]}, {"$set": {"layer": "knowledge"}})
        new = mem.record("fact", "نسبة الضريبة 15%", topic="ضريبة")
        res = mem.promote_to_knowledge(new["id"])
        assert res.get("promoted") == new["id"]
        assert old["id"] in res.get("disputed", [])
        assert col.find_one({"id": old["id"]})["status"] == "disputed"

    def test_disputed_frozen_from_injection(self, mem):
        col = mem._database()[mem.COL]
        d = mem.record("fact", "معلومة متنازع عليها للحقن", topic="نزاع")
        col.update_one({"id": d["id"]},
                       {"$set": {"layer": "knowledge", "status": "disputed"}})
        assert "متنازع عليها للحقن" not in mem.retrieve("معلومة نزاع")


class TestRule5KnowledgeCap:
    def test_cap_blocks_new_promotion(self, mem, monkeypatch):
        monkeypatch.setattr(mem, "KNOWLEDGE_TOKEN_CAP", 50)
        col = mem._database()[mem.COL]
        big = mem.record("fact", "م" * 200, topic="كبيرة")
        col.update_one({"id": big["id"]}, {"$set": {"layer": "knowledge"}})
        res = mem.propose_knowledge(content="معلومة جديدة فوق السقف", proposer="مدير")
        assert res.get("error") == "knowledge_cap_full"

    def test_injection_respects_cap(self, mem, monkeypatch):
        monkeypatch.setattr(mem, "KNOWLEDGE_TOKEN_CAP", 40)
        col = mem._database()[mem.COL]
        for i in range(3):
            d = mem.record("fact", f"معرفة رقم {i} " + "ن" * 90, topic=f"t{i}")
            col.update_one({"id": d["id"]}, {"$set": {"layer": "knowledge",
                                                      "promoted_at": time.time() + i}})
        out = mem.retrieve("معرفة")
        assert out.count("★") <= 1  # السقف يمنع حقن الكل


class TestTopKRetrieval:
    def test_retrieve_selective_not_full(self, mem):
        for i in range(10):
            mem.record("decision", f"قرار مختلف تماماً رقم {i} بشأن موضوع {i}",
                       session_id=f"s{i}")
        out = mem.retrieve("قرار بشأن موضوع", k=3)
        assert out.count("•") <= 3

    def test_unrelated_query_returns_no_noise(self, mem):
        mem.record("decision", "اعتماد شراء زيت", session_id="s1")
        assert mem.retrieve("xyz123 nothing", k=5) == ""
