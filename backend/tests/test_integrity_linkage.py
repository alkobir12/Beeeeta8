"""
Test suite for Operations Integrity Check and Linkage features
Tests the /api/operations/integrity/check endpoint and related functionality
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://fleet-audit-system-2.preview.emergentagent.com').rstrip('/')


class TestOperationsIntegrityCheck:
    """Tests for POST /api/operations/integrity/check endpoint"""

    def test_integrity_check_with_op_ids(self):
        """Test integrity check with specific operation IDs"""
        # First get some operations
        ops_response = requests.get(f"{BASE_URL}/api/operations?limit=5")
        assert ops_response.status_code == 200, f"Failed to get operations: {ops_response.text}"
        
        operations = ops_response.json()
        if not operations:
            pytest.skip("No operations available for testing")
        
        op_ids = [op.get('id') for op in operations[:3] if op.get('id')]
        
        # Test integrity check with op_ids
        response = requests.post(
            f"{BASE_URL}/api/operations/integrity/check",
            json={"op_ids": op_ids}
        )
        
        assert response.status_code == 200, f"Integrity check failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert data.get('success') is True
        assert 'data' in data
        assert 'items' in data['data']
        assert 'summary' in data['data']
        
        # Verify summary structure
        summary = data['data']['summary']
        assert 'total' in summary
        assert 'ok' in summary
        assert 'warnings' in summary
        assert 'duplicates' in summary
        
        # Verify items structure
        items = data['data']['items']
        assert len(items) == len(op_ids), f"Expected {len(op_ids)} items, got {len(items)}"
        
        for item in items:
            assert 'op_id' in item
            assert 'status' in item
            assert 'warnings' in item
            assert 'links' in item
            assert item['status'] in ['ok', 'warning']
            
            # Verify links structure
            links = item['links']
            assert 'journal_count' in links
            assert 'has_vehicle' in links
            assert 'has_visit' in links
            assert 'visit_vehicle_match' in links
        
        print(f"✓ Integrity check with op_ids: {summary}")

    def test_integrity_check_with_vehicle_id(self):
        """Test integrity check with vehicle_id filter"""
        # First get a vehicle with operations
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles?limit=10")
        assert vehicles_response.status_code == 200
        
        vehicles = vehicles_response.json()
        if not vehicles:
            pytest.skip("No vehicles available for testing")
        
        # Find a vehicle that might have operations
        vehicle_id = vehicles[0].get('id')
        
        response = requests.post(
            f"{BASE_URL}/api/operations/integrity/check",
            json={"vehicle_id": vehicle_id}
        )
        
        assert response.status_code == 200, f"Integrity check with vehicle_id failed: {response.text}"
        data = response.json()
        
        assert data.get('success') is True
        assert 'data' in data
        assert 'items' in data['data']
        assert 'summary' in data['data']
        
        print(f"✓ Integrity check with vehicle_id: {data['data']['summary']}")

    def test_integrity_check_empty_op_ids(self):
        """Test integrity check with empty op_ids returns all operations (default behavior)"""
        response = requests.post(
            f"{BASE_URL}/api/operations/integrity/check",
            json={"op_ids": []}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('success') is True
        # When op_ids is empty, endpoint returns all operations (up to limit)
        # This is expected behavior - it checks all operations
        assert 'items' in data['data']
        assert 'summary' in data['data']
        
        print(f"✓ Integrity check with empty op_ids returns all operations: {data['data']['summary']}")

    def test_integrity_check_warnings_detection(self):
        """Test that integrity check properly detects warnings"""
        # Get operations
        ops_response = requests.get(f"{BASE_URL}/api/operations?limit=20")
        assert ops_response.status_code == 200
        
        operations = ops_response.json()
        if not operations:
            pytest.skip("No operations available for testing")
        
        op_ids = [op.get('id') for op in operations if op.get('id')]
        
        response = requests.post(
            f"{BASE_URL}/api/operations/integrity/check",
            json={"op_ids": op_ids}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that warnings are properly categorized
        items = data['data']['items']
        summary = data['data']['summary']
        
        # Count warnings manually
        warning_count = sum(1 for item in items if item['status'] == 'warning')
        ok_count = sum(1 for item in items if item['status'] == 'ok')
        
        assert summary['warnings'] == warning_count, f"Warning count mismatch: {summary['warnings']} vs {warning_count}"
        assert summary['ok'] == ok_count, f"OK count mismatch: {summary['ok']} vs {ok_count}"
        assert summary['total'] == len(items)
        
        # Check warning types
        valid_warnings = {
            'missing_journal_entry',
            'vehicle_not_found',
            'visit_not_found',
            'visit_vehicle_mismatch',
            'vehicle_scope_without_vehicle',
            'potential_duplicate'
        }
        
        for item in items:
            for warning in item['warnings']:
                assert warning in valid_warnings, f"Unknown warning type: {warning}"
        
        print(f"✓ Warnings detection: {summary}")


class TestOperationsCRUD:
    """Test basic operations CRUD to ensure no regression"""

    def test_create_sale_operation(self):
        """Test creating a sale operation still works"""
        # Get a business account first
        accounts_response = requests.get(f"{BASE_URL}/api/biz-accounts")
        assert accounts_response.status_code == 200
        
        accounts = accounts_response.json()
        if not accounts:
            pytest.skip("No business accounts available")
        
        account_id = accounts[0].get('id')
        test_id = uuid.uuid4().hex[:6]
        
        payload = {
            "type": "sale",
            "accountId": account_id,
            "partnerType": "customer",
            "partnerName": f"TEST_{test_id}_Customer",
            "items": [
                {"name": f"TEST_{test_id}_Item", "quantity": 1, "price": 100}
            ],
            "paymentMethod": "cash",
            "scope": "workshop",
            "date": "2026-01-10"
        }
        
        response = requests.post(f"{BASE_URL}/api/operations", json=payload)
        assert response.status_code in [200, 201], f"Failed to create sale operation: {response.text}"
        
        data = response.json()
        assert data.get('id'), "Created operation should have an ID"
        assert data.get('type') == 'sale'
        
        print(f"✓ Created sale operation: {data.get('id')}")
        return data.get('id')

    def test_create_purchase_operation(self):
        """Test creating a purchase operation still works"""
        accounts_response = requests.get(f"{BASE_URL}/api/biz-accounts")
        assert accounts_response.status_code == 200
        
        accounts = accounts_response.json()
        if not accounts:
            pytest.skip("No business accounts available")
        
        account_id = accounts[0].get('id')
        test_id = uuid.uuid4().hex[:6]
        
        payload = {
            "type": "purchase",
            "accountId": account_id,
            "partnerType": "supplier",
            "partnerName": f"TEST_{test_id}_Supplier",
            "items": [
                {"name": f"TEST_{test_id}_Purchase", "quantity": 1, "price": 200}
            ],
            "paymentMethod": "cash",
            "scope": "workshop",
            "date": "2026-01-10"
        }
        
        response = requests.post(f"{BASE_URL}/api/operations", json=payload)
        assert response.status_code in [200, 201], f"Failed to create purchase operation: {response.text}"
        
        data = response.json()
        assert data.get('id'), "Created operation should have an ID"
        assert data.get('type') == 'purchase'
        
        print(f"✓ Created purchase operation: {data.get('id')}")
        return data.get('id')

    def test_create_settlement_operation(self):
        """Test creating a settlement operation (payment_order) still works"""
        accounts_response = requests.get(f"{BASE_URL}/api/biz-accounts")
        assert accounts_response.status_code == 200
        
        accounts = accounts_response.json()
        if not accounts:
            pytest.skip("No business accounts available")
        
        account_id = accounts[0].get('id')
        test_id = uuid.uuid4().hex[:6]
        
        # Test customer settlement
        payload = {
            "type": "payment_order",
            "accountId": account_id,
            "partnerType": "customer",
            "partnerName": f"TEST_{test_id}_SettlementCustomer",
            "items": [],
            "paymentMethod": "cash",
            "scope": "workshop",
            "date": "2026-01-10"
        }
        
        response = requests.post(f"{BASE_URL}/api/operations", json=payload)
        assert response.status_code in [200, 201], f"Failed to create settlement operation: {response.text}"
        
        data = response.json()
        assert data.get('id'), "Created operation should have an ID"
        
        print(f"✓ Created settlement operation: {data.get('id')}")
        
        # Test supplier settlement
        payload['partnerType'] = 'supplier'
        payload['partnerName'] = f"TEST_{test_id}_SettlementSupplier"
        
        response = requests.post(f"{BASE_URL}/api/operations", json=payload)
        assert response.status_code in [200, 201], f"Failed to create supplier settlement: {response.text}"
        
        print(f"✓ Created supplier settlement operation")


class TestJournalEntriesLinkage:
    """Test journal entries linkage status"""

    def test_journal_entries_list(self):
        """Test that journal entries endpoint works"""
        response = requests.get(f"{BASE_URL}/api/finance/journal-entries?workshop_id=finmodule-sync&limit=10")
        assert response.status_code == 200, f"Failed to get journal entries: {response.text}"
        
        data = response.json()
        assert data.get('success') is True
        assert 'data' in data
        
        entries = data['data']
        if entries:
            entry = entries[0]
            # Check entry has expected fields
            assert 'id' in entry
            assert 'date' in entry or 'entry_date' in entry
            
        print(f"✓ Journal entries list: {len(entries)} entries")


class TestVehicleDetailsLinkage:
    """Test vehicle details linkage summary"""

    def test_vehicle_details_endpoint(self):
        """Test that vehicle details endpoint works"""
        # Get a vehicle first
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles?limit=1")
        assert vehicles_response.status_code == 200
        
        vehicles = vehicles_response.json()
        if not vehicles:
            pytest.skip("No vehicles available for testing")
        
        vehicle_id = vehicles[0].get('id')
        
        # Get vehicle details
        response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}")
        assert response.status_code == 200, f"Failed to get vehicle details: {response.text}"
        
        data = response.json()
        assert data.get('id') == vehicle_id
        
        print(f"✓ Vehicle details endpoint works for vehicle: {vehicle_id}")

    def test_vehicle_visits_endpoint(self):
        """Test that vehicle visits endpoint works"""
        # Get a vehicle first
        vehicles_response = requests.get(f"{BASE_URL}/api/vehicles?limit=1")
        assert vehicles_response.status_code == 200
        
        vehicles = vehicles_response.json()
        if not vehicles:
            pytest.skip("No vehicles available for testing")
        
        vehicle_id = vehicles[0].get('id')
        
        # Get vehicle visits
        response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}/visits")
        assert response.status_code == 200, f"Failed to get vehicle visits: {response.text}"
        
        visits = response.json()
        assert isinstance(visits, list)
        
        print(f"✓ Vehicle visits endpoint works: {len(visits)} visits")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
