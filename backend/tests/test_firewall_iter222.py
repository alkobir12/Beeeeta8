"""
Firewall Center backend tests — iter222.
Covers: dashboard, health-score, alerts (+filters), dismiss/resolve, auto-fix dry_run, ai-insights.
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://workshop-engine.preview.emergentagent.com").rstrip("/")
WORKSHOP_ID = "finmodule-sync"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ----- Module: Dashboard -----
class TestDashboard:
    def test_dashboard_full_payload(self, session):
        r = session.get(f"{BASE_URL}/api/firewall/dashboard", params={"workshop_id": WORKSHOP_ID}, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True
        d = body["data"]
        assert "health" in d and "alerts" in d and "cash_flow" in d and "live_activity" in d and "stats" in d
        assert isinstance(d["health"]["score"], (int, float))
        assert 0 <= d["health"]["score"] <= 100
        assert d["alerts_count"] >= 0
        assert isinstance(d["alerts"], list)
        # health breakdown — 8 keys
        bk = d["health"].get("breakdown", {})
        for key in ["balance_integrity", "no_duplicates", "consistency", "no_anomalies",
                    "data_integrity", "positive_cash_flow", "audit_coverage", "overdue_control"]:
            assert key in bk, f"missing breakdown key: {key}"
        # stats sanity
        assert d["stats"]["total_journals"] >= 0
        assert d["stats"]["total_operations"] >= 0
        assert d["stats"]["total_visits"] >= 0


# ----- Module: Health Score -----
class TestHealthScore:
    def test_health_score_endpoint(self, session):
        r = session.get(f"{BASE_URL}/api/firewall/health-score", params={"workshop_id": WORKSHOP_ID}, timeout=60)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        h = body["data"]["health"]
        assert 0 <= h["score"] <= 100
        assert h["status"] in {"ممتاز", "جيد", "متوسط", "ضعيف", "حرج"}
        assert len(h["breakdown"]) == 8


# ----- Module: Alerts list + filters -----
class TestAlerts:
    def test_alerts_unfiltered(self, session):
        r = session.get(f"{BASE_URL}/api/firewall/alerts", params={"workshop_id": WORKSHOP_ID}, timeout=60)
        assert r.status_code == 200
        b = r.json()
        assert b["success"] is True
        assert isinstance(b["data"], list)
        assert "total" in b

    def test_alerts_filter_by_severity_critical(self, session):
        r = session.get(f"{BASE_URL}/api/firewall/alerts",
                        params={"workshop_id": WORKSHOP_ID, "severity": "critical"}, timeout=60)
        assert r.status_code == 200
        b = r.json()
        assert b["success"] is True
        for a in b["data"]:
            assert a["severity"] == "critical"

    def test_alerts_filter_by_category_duplicate(self, session):
        r = session.get(f"{BASE_URL}/api/firewall/alerts",
                        params={"workshop_id": WORKSHOP_ID, "category": "duplicate_detection"}, timeout=60)
        assert r.status_code == 200
        b = r.json()
        assert b["success"] is True
        for a in b["data"]:
            assert a["category"] == "duplicate_detection"


# ----- Module: Dismiss + Resolve -----
class TestAlertActions:
    @pytest.fixture(scope="class")
    def some_alert_id(self, session):
        r = session.get(f"{BASE_URL}/api/firewall/alerts", params={"workshop_id": WORKSHOP_ID}, timeout=60)
        alerts = r.json().get("data", [])
        if not alerts:
            pytest.skip("no alerts available to act upon")
        return alerts[0]["id"]

    def test_dismiss_alert_writes_expiry(self, session, some_alert_id):
        r = session.post(f"{BASE_URL}/api/firewall/alerts/{some_alert_id}/dismiss",
                         params={"workshop_id": WORKSHOP_ID},
                         json={"expires_in_hours": 1, "reason": "TEST_iter222"}, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("success") is True
        assert b.get("alert_id") == some_alert_id
        assert b.get("expires_at")

    def test_resolve_alert(self, session, some_alert_id):
        r = session.post(f"{BASE_URL}/api/firewall/alerts/{some_alert_id}/resolve",
                         params={"workshop_id": WORKSHOP_ID},
                         json={"user": "TEST_iter222", "notes": "test"}, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("success") is True
        assert b.get("alert_id") == some_alert_id


# ----- Module: Auto-fix (dry_run) -----
class TestAutoFix:
    def test_auto_fix_dry_run_unbalanced(self, session):
        r = session.get(f"{BASE_URL}/api/firewall/alerts",
                        params={"workshop_id": WORKSHOP_ID, "category": "balance_integrity"}, timeout=60)
        alerts = [a for a in r.json().get("data", []) if a.get("auto_fix") == "auto"]
        if not alerts:
            # try orphan integrity alerts (also auto)
            r2 = session.get(f"{BASE_URL}/api/firewall/alerts",
                             params={"workshop_id": WORKSHOP_ID, "category": "integrity"}, timeout=60)
            alerts = [a for a in r2.json().get("data", []) if a.get("auto_fix") == "auto"]
        if not alerts:
            pytest.skip("no auto-fixable alert present")
        alert = alerts[0]
        r = session.post(f"{BASE_URL}/api/firewall/auto-fix",
                         params={"workshop_id": WORKSHOP_ID},
                         json={"alert_id": alert["id"], "dry_run": True}, timeout=60)
        assert r.status_code == 200, r.text
        b = r.json()
        # success may be False if provider is not supabase; accept that with clear message
        if b.get("success"):
            assert b.get("dry_run") is True
            assert ("would_create_adjustment" in b) or ("would_delete" in b)
        else:
            # acceptable only if provider not supabase
            assert "Supabase" in (b.get("error") or "") or "غير مدعوم" in (b.get("error") or "")

    def test_auto_fix_unknown_alert_404(self, session):
        r = session.post(f"{BASE_URL}/api/firewall/auto-fix",
                         params={"workshop_id": WORKSHOP_ID},
                         json={"alert_id": "DOES-NOT-EXIST-xyz", "dry_run": True}, timeout=30)
        # Either HTTP 404 or success=False
        if r.status_code == 200:
            assert r.json().get("success") is False
        else:
            assert r.status_code == 404


# ----- Module: AI Insights -----
class TestAIInsights:
    def test_ai_insights_rules_only(self, session):
        r = session.get(f"{BASE_URL}/api/firewall/ai-insights",
                        params={"workshop_id": WORKSHOP_ID, "use_ai": "false"}, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["success"] is True
        d = b["data"]
        assert "insights" in d
        assert d.get("ai_enabled") is False
        assert isinstance(d["insights"], list)

    def test_ai_insights_use_ai_true(self, session):
        r = session.get(f"{BASE_URL}/api/firewall/ai-insights",
                        params={"workshop_id": WORKSHOP_ID, "use_ai": "true"}, timeout=90)
        assert r.status_code == 200
        b = r.json()
        assert b["success"] is True
        d = b["data"]
        assert "insights" in d
        assert "ai_enabled" in d
        # ai_enabled is True if Emergent key worked; we accept either
        assert isinstance(d["ai_enabled"], bool)


# ----- Module: Live activity -----
class TestLive:
    def test_live_activity_endpoint(self, session):
        r = session.get(f"{BASE_URL}/api/firewall/live-activity",
                        params={"workshop_id": WORKSHOP_ID, "limit": 10}, timeout=30)
        assert r.status_code == 200
        b = r.json()
        assert b["success"] is True
        assert isinstance(b["data"], list)
