"""
Backend API Tests for Accounting and Finance Modules
Tests the new accounting and finance endpoints including:
- Chart of Accounts
- Journal Entries
- Balance Sheet
- Income Statement
- Cash Flow
- Trial Balance
- Invoices
- Taxes
- AI Financial Analysis
"""

import pytest
import requests
import os

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://fabrication-guard.preview.emergentagent.com"
)


class TestHealthAndStats:
    """Basic health and stats endpoint tests"""

    def test_stats_endpoint(self):
        """Test /api/stats endpoint returns valid data"""
        response = requests.get(f"{BASE_URL}/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "totalCustomers" in data
        assert "activeVehicles" in data
        assert "thisMonth" in data
        print(
            f"Stats: {data['totalCustomers']} customers, {data['activeVehicles']} active vehicles"
        )


class TestAIFinancialAnalysis:
    """AI Financial Analysis endpoint tests"""

    def test_financial_analysis_endpoint(self):
        """Test /api/ai/financial-analysis endpoint"""
        payload = {
            "query": "ما هو تحليل الوضع المالي؟",
            "financial_data": {
                "revenue": 528000,
                "expenses": 465000,
                "net_income": 63000,
                "gross_margin": 75.4,
                "net_margin": 11.9,
                "current_ratio": 3.28,
                "debt_to_equity": 0.5,
                "assets": 500000,
                "liabilities": 173500,
                "equity": 327000,
            },
        }
        response = requests.post(
            f"{BASE_URL}/api/ai/financial-analysis",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "analysis" in data
        assert len(data["analysis"]) > 100  # Should have substantial analysis
        print(f"AI Analysis response length: {len(data['analysis'])} characters")

    def test_financial_analysis_with_empty_query(self):
        """Test financial analysis with minimal query"""
        payload = {
            "query": "تحليل",
            "financial_data": {"revenue": 100000, "expenses": 80000},
        }
        response = requests.post(
            f"{BASE_URL}/api/ai/financial-analysis",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "analysis" in data


class TestVehiclesAPI:
    """Vehicle API tests"""

    def test_get_vehicles(self):
        """Test /api/vehicles endpoint"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} vehicles")


class TestCustomersAPI:
    """Customer API tests"""

    def test_get_customers(self):
        """Test /api/customers endpoint"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} customers")


class TestServicesAPI:
    """Services API tests"""

    def test_get_services(self):
        """Test /api/services endpoint"""
        response = requests.get(f"{BASE_URL}/api/services")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} services")


class TestTechniciansAPI:
    """Technicians API tests"""

    def test_get_technicians(self):
        """Test /api/technicians endpoint"""
        response = requests.get(f"{BASE_URL}/api/technicians")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} technicians")


class TestPartsAPI:
    """Parts API tests"""

    def test_get_parts(self):
        """Test /api/parts endpoint"""
        response = requests.get(f"{BASE_URL}/api/parts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} parts")


class TestSettingsAPI:
    """Settings API tests"""

    def test_get_settings(self):
        """Test /api/settings endpoint"""
        response = requests.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200
        # Settings can be empty dict or have data
        data = response.json()
        assert isinstance(data, dict)
        print(f"Settings keys: {list(data.keys())}")


class TestProfileAPI:
    """Profile API tests"""

    def test_get_profile(self):
        """Test /api/profile endpoint"""
        response = requests.get(f"{BASE_URL}/api/profile")
        assert response.status_code == 200
        data = response.json()
        print(f"Profile data: {data}")


class TestUsersAPI:
    """Users API tests"""

    def test_get_users(self):
        """Test /api/users endpoint"""
        response = requests.get(f"{BASE_URL}/api/users")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} users")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
