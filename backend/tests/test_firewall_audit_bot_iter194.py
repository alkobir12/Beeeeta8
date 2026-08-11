"""Iter 194 — Firewall→Auditor + Firewall→Bot integration tests."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://canonical-integrity.preview.emergentagent.com").rstrip("/")
WS = "finmodule-sync"


def test_audit_system_contains_firewall_check():
    r = requests.post(f"{BASE_URL}/api/finance/audit-system", params={"workshop_id": WS}, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True, body
    data = body.get("data") or {}
    details = data.get("details") or {}
    fw = details.get("firewall_check")
    assert fw, f"firewall_check missing from details: {list(details.keys())}"
    assert fw.get("status") in {"ok", "warning", "critical", "error"}, fw
    metrics = fw.get("metrics") or {}
    for k in ["total_entries", "balanced_entries", "balance_health_percent", "lifetime_rejections", "max_drift"]:
        assert k in metrics, f"missing metric {k} in {list(metrics.keys())}"
    print("firewall_check.status =", fw.get("status"), "metrics:", metrics)


def test_finance_bot_chat_uses_firewall_context():
    payload = {
        "workshop_id": WS,
        "message": "هل توجد قيود غير متوازنة في DB حالياً؟",
    }
    r = requests.post(f"{BASE_URL}/api/finance-bot/chat", json=payload, timeout=90)
    assert r.status_code == 200, r.text
    body = r.json()
    resp_text = body.get("response") or ""
    assert isinstance(resp_text, str) and len(resp_text) > 0, body
    # Cannot directly assert firewall context appears in LLM reply, but the call must succeed
    # without 500. The response is a single Arabic question.
    print("bot reply (truncated):", resp_text[:200])


def test_firewall_status_endpoint_live():
    r = requests.get(f"{BASE_URL}/api/firewall/status", params={"workshop_id": WS}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    s = body.get("summary") or {}
    assert "balance_health_percent" in s
    assert "lifetime_rejections" in s
    print("firewall summary:", s)
