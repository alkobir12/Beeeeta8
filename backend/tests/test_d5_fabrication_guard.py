"""🔐 L14-D5 — اختبارات حارس الاختلاق (وحدة، بلا LLM).
إثبات القفل: OP-2025-0187 يُحجَب عندما لا يوجد في أدلة الدورة."""
import sys

sys.path.insert(0, "/app/backend")
from core import provenance_guard as pg


def test_fake_tool_block_is_blocked():
    resp = "نتائج:\n  • operations.recent: {'count': 2, 'items': [...]}\nتمت."
    out, viol = pg.enforce(resp, [{"tool": "customers.search"}])
    assert len(viol) == 1 and viol[0]["claimed_tool"] == "operations.recent"
    assert "operations.recent: {" not in out
    assert "حُجب بلوك نتائج غير موثّق" in out


def test_executed_tool_block_passes():
    resp = "  • operations.recent: {'count': 2}"
    out, viol = pg.enforce(resp, [{"tool": "operations.recent"}])
    assert viol == [] and out == resp


def test_op_2025_0187_is_blocked_without_evidence():
    resp = "آخر عمليتين: OP-2025-0187 لعبدالعزيز الشريف بمبلغ 850، وOP-2025-0186 بمبلغ 620."
    evidence = "أدوات الدورة: operations.search أرجعت [] · رسالة المستخدم: اعرضي آخر عمليتين"
    out, viol = pg.enforce_entities(resp, evidence)
    vals = {v["value"] for v in viol}
    assert "OP-2025-0187" in vals and "OP-2025-0186" in vals
    assert "OP-2025-0187" not in out and "OP-2025-0186" not in out
    assert pg._BLOCKED_MARK in out


def test_entity_present_in_evidence_passes():
    resp = "الفاتورة INV001254 مرتبطة بالقيد 2eec34b3 والزيارة 29b88c69."
    evidence = "tool operations.search → {'invoice_number': 'INV001254', 'entry': '2eec34b3', 'visit': '29b88c69-15a8'}"
    out, viol = pg.enforce_entities(resp, evidence)
    assert viol == [] and out == resp


def test_fabricated_short_id_blocked_real_one_passes():
    resp = "القيدان: 2eec34b3 وdeadbeef."
    evidence = "journal: 2eec34b3"
    out, viol = pg.enforce_entities(resp, evidence)
    assert len(viol) == 1 and viol[0]["value"] == "deadbeef"
    assert "2eec34b3" in out and "deadbeef" not in out


def test_amounts_dates_phones_never_blocked():
    resp = "الإجمالي 8474 ر.س بتاريخ 20260714 وجوال 0553280100 ونسبة 15.5%."
    out, viol = pg.enforce_entities(resp, "لا أدلة")
    assert viol == [] and out == resp


def test_fabricated_trace_and_uuid_blocked():
    resp = "المرجع tr-ffffffffffff والسجل 12345678-abcd-ef01-2345-6789abcdef01."
    out, viol = pg.enforce_entities(resp, "أدلة لا تحويهما")
    assert len(viol) == 2
    assert "tr-ffffffffffff" not in out


def test_empty_response_safe():
    out, viol = pg.enforce_entities("", "x")
    assert out == "" and viol == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print(f"✅ {f.__name__}")
    print(f"\n{len(fns)}/{len(fns)} passed")
