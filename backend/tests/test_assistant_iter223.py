"""
Iter223 — Unified Assistant Kernel backend tests
Covers: /api/assistant/{stats,tools,chat,tool/{name},alerts,session/{id}}
+ Firewall regression: /api/firewall/dashboard still works and publishes alerts to alert_bus.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ar-ledger-ssot.preview.emergentagent.com").rstrip("/")
WORKSHOP_ID = "finmodule-sync"
TIMEOUT = 60


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ---------- /api/assistant/stats ----------
class TestAssistantStats:
    def test_stats_shape(self, s):
        r = s.get(f"{BASE_URL}/api/assistant/stats", timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        d = body["data"]
        assert "memory" in d and "alert_bus" in d
        assert d["tools_registered"] == 5, f"expected 5 tools, got {d['tools_registered']}"
        assert isinstance(d["ai_enabled"], bool)
        # memory + alert_bus sub-shape
        assert "active_sessions" in d["memory"] and "total_messages" in d["memory"]
        assert "subscribers_count" in d["alert_bus"] and "alerts_tracked" in d["alert_bus"]


# ---------- /api/assistant/tools ----------
class TestAssistantTools:
    def test_list_all_tools(self, s):
        r = s.get(f"{BASE_URL}/api/assistant/tools", timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 5
        names = {t["name"] for t in data}
        assert names == {
            "firewall.health_score", "firewall.top_alerts", "firewall.cash_flow",
            "finance.ar_summary", "workshop.active_visits",
        }
        # validate each has agent + description
        for t in data:
            assert t["agent"] in {"FinanceAgent", "WorkshopAgent", "FirewallAgent"}
            assert t["description"]

    def test_filter_by_firewall_agent(self, s):
        r = s.get(f"{BASE_URL}/api/assistant/tools", params={"agent": "FirewallAgent"}, timeout=TIMEOUT)
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 3
        assert all(t["agent"] == "FirewallAgent" for t in data)

    def test_filter_by_finance_agent(self, s):
        r = s.get(f"{BASE_URL}/api/assistant/tools", params={"agent": "FinanceAgent"}, timeout=TIMEOUT)
        data = r.json()["data"]
        assert len(data) == 1 and data[0]["name"] == "finance.ar_summary"

    def test_filter_by_workshop_agent(self, s):
        r = s.get(f"{BASE_URL}/api/assistant/tools", params={"agent": "WorkshopAgent"}, timeout=TIMEOUT)
        data = r.json()["data"]
        assert len(data) == 1 and data[0]["name"] == "workshop.active_visits"


# ---------- /api/assistant/tool/{name} (direct) ----------
class TestDirectToolCall:
    def test_finance_ar_summary(self, s):
        r = s.post(f"{BASE_URL}/api/assistant/tool/finance.ar_summary",
                   json={"workshop_id": WORKSHOP_ID}, timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True, body
        assert body["tool"] == "finance.ar_summary"
        assert body["agent"] == "FinanceAgent"
        result = body["result"]
        assert "total_customers_with_debt" in result
        assert "total_ar" in result
        assert "top_debtors" in result
        # Expected from problem statement: ~3569 SAR / 2 debtors
        assert result["total_customers_with_debt"] >= 1
        assert result["total_ar"] > 0

    def test_firewall_health_score(self, s):
        r = s.post(f"{BASE_URL}/api/assistant/tool/firewall.health_score",
                   json={"workshop_id": WORKSHOP_ID}, timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        result = body["result"]
        assert "score" in result and 0 <= result["score"] <= 100
        assert "status" in result
        assert "alerts_count" in result

    def test_firewall_top_alerts(self, s):
        r = s.post(f"{BASE_URL}/api/assistant/tool/firewall.top_alerts",
                   json={"workshop_id": WORKSHOP_ID, "limit": 3}, timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        result = body["result"]
        assert isinstance(result, list)
        assert len(result) <= 3
        if result:
            assert "title" in result[0] and "severity" in result[0]

    def test_unknown_tool_returns_error(self, s):
        r = s.post(f"{BASE_URL}/api/assistant/tool/does.not.exist",
                   json={}, timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert "tool not found" in (body.get("error") or "").lower()


# ---------- /api/assistant/chat ----------
class TestAssistantChat:
    def test_chat_health_score_intent(self, s):
        r = s.post(f"{BASE_URL}/api/assistant/chat",
                   json={"message": "كم درجة الصحة المالية؟", "workshop_id": WORKSHOP_ID, "use_ai": False},
                   timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True, body
        d = body["data"]
        assert d["agent"] == "FirewallAgent", f"expected FirewallAgent, got {d['agent']}"
        tool_names = [t.get("tool") for t in d.get("tool_results", [])]
        assert "firewall.health_score" in tool_names, f"tools used: {tool_names}"
        assert d.get("response")
        assert d.get("session_id")

    def test_chat_top_alerts_intent(self, s):
        r = s.post(f"{BASE_URL}/api/assistant/chat",
                   json={"message": "أعطني أهم التنبيهات", "workshop_id": WORKSHOP_ID, "use_ai": False},
                   timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        d = body["data"]
        assert d["agent"] == "FirewallAgent"
        tool_names = [t.get("tool") for t in d.get("tool_results", [])]
        assert "firewall.top_alerts" in tool_names, f"tools used: {tool_names}"

    def test_chat_ar_intent(self, s):
        r = s.post(f"{BASE_URL}/api/assistant/chat",
                   json={"message": "كم ذمم العملاء المستحقة؟", "workshop_id": WORKSHOP_ID, "use_ai": False},
                   timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        d = body["data"]
        assert d["agent"] == "FinanceAgent", f"expected FinanceAgent, got {d['agent']}"
        tool_names = [t.get("tool") for t in d.get("tool_results", [])]
        assert "finance.ar_summary" in tool_names, f"tools used: {tool_names}"

    def test_chat_missing_message_returns_400(self, s):
        r = s.post(f"{BASE_URL}/api/assistant/chat", json={"message": ""}, timeout=TIMEOUT)
        assert r.status_code == 400


# ---------- /api/assistant/session/{id} ----------
class TestSessionPersistence:
    def test_create_session_and_retrieve(self, s):
        # create via chat
        r = s.post(f"{BASE_URL}/api/assistant/chat",
                   json={"message": "TEST_iter223 ما هي درجة الصحة؟", "workshop_id": WORKSHOP_ID, "use_ai": False},
                   timeout=TIMEOUT)
        assert r.status_code == 200
        sid = r.json()["data"]["session_id"]
        assert sid

        # retrieve
        r2 = s.get(f"{BASE_URL}/api/assistant/session/{sid}", timeout=TIMEOUT)
        assert r2.status_code == 200
        d = r2.json()["data"]
        assert d["session_id"] == sid
        msgs = d["messages"]
        assert len(msgs) >= 2  # user + assistant
        roles = [m["role"] for m in msgs]
        assert "user" in roles and "assistant" in roles


# ---------- /api/assistant/alerts ----------
class TestAlertBus:
    def test_alerts_populated_after_firewall_dashboard(self, s):
        # Trigger firewall analysis (publishes to alert_bus)
        r0 = s.get(f"{BASE_URL}/api/firewall/dashboard",
                   params={"workshop_id": WORKSHOP_ID, "use_ai": False}, timeout=120)
        assert r0.status_code == 200, r0.text[:300]
        fw = r0.json()
        assert fw.get("success") is True
        # Some firewall endpoints return shape {success, data:{health,alerts,...}}
        fw_data = fw.get("data", fw)
        assert "health" in fw_data and 0 <= fw_data["health"]["score"] <= 100
        assert isinstance(fw_data.get("alerts"), list)

        # allow alert_bus to ingest
        time.sleep(0.5)

        r = s.get(f"{BASE_URL}/api/assistant/alerts", params={"limit": 20}, timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        # alerts may be empty if firewall produced none, but typically >=1
        # check it's at least matching the type
        if body["total"] > 0:
            a = body["data"][0]
            assert "severity" in a or "title" in a or "id" in a

    def test_alerts_filter_severity(self, s):
        r = s.get(f"{BASE_URL}/api/assistant/alerts",
                  params={"severity": "critical", "limit": 10}, timeout=TIMEOUT)
        assert r.status_code == 200
        for a in r.json()["data"]:
            assert a.get("severity") == "critical"


# ---------- Firewall regression ----------
class TestFirewallRegression:
    def test_firewall_dashboard(self, s):
        r = s.get(f"{BASE_URL}/api/firewall/dashboard",
                  params={"workshop_id": WORKSHOP_ID, "use_ai": False}, timeout=120)
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True
        d = body.get("data", body)
        assert 0 <= d["health"]["score"] <= 100
        assert isinstance(d.get("alerts"), list)
