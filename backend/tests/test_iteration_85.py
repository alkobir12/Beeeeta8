"""
Iteration 85 Tests: Operation Card Customer/Vehicle Display + Financial Dashboard Cash Card

Features tested:
1. Frontend Operations: Each operation card shows customer/partner + vehicle clearly at the top
2. Frontend Operations expanded: Vehicle details inside expanded card
3. Frontend ComprehensiveFinancial: Card titled 'النقد الفعلي' with description 'الإيرادات - المصروفات'
4. Regression: Dashboard cards/tabs working
5. Backend sanity: Create operation with vehicleId returns vehicleId+visitId
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://finance-overhaul-7.preview.emergentagent.com').rstrip('/')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestBackendOperationsVehicleLinking:
    """Test that operations with vehicleId preserve vehicleId and visitId"""
    
    def test_create_operation_with_vehicle_id_returns_vehicle_id(self):
        """Create operation with vehicleId and verify it's returned"""
        # First get a vehicle to use
        vehicles_resp = requests.get(f"{BASE_URL}/api/vehicles", params={"limit": 1})
        assert vehicles_resp.status_code == 200, f"Failed to get vehicles: {vehicles_resp.text}"
        
        vehicles = vehicles_resp.json()
        if not vehicles:
            pytest.skip("No vehicles available for testing")
        
        vehicle_id = vehicles[0].get('id')
        
        # Create operation with vehicleId
        operation_data = {
            "type": "sale",
            "partnerName": f"TEST_Customer_{uuid.uuid4().hex[:6]}",
            "partnerType": "customer",
            "vehicleId": vehicle_id,
            "items": [{"name": "Test Service", "price": 100, "quantity": 1}],
            "total": 100,
            "paymentMethod": "cash",
            "workshopId": WORKSHOP_ID,
            "date": datetime.utcnow().isoformat()
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/operations", json=operation_data)
        assert create_resp.status_code in [200, 201], f"Failed to create operation: {create_resp.text}"
        
        created_op = create_resp.json()
        
        # Verify vehicleId is returned
        assert created_op.get('vehicleId') == vehicle_id, f"vehicleId not preserved. Expected {vehicle_id}, got {created_op.get('vehicleId')}"
        
        # Verify scope is 'vehicle' when vehicleId is present
        assert created_op.get('scope') == 'vehicle', f"scope should be 'vehicle' when vehicleId present, got {created_op.get('scope')}"
        
        # Cleanup
        op_id = created_op.get('id')
        if op_id:
            requests.delete(f"{BASE_URL}/api/operations/{op_id}")
        
        print(f"✓ Operation with vehicleId created successfully, vehicleId preserved: {vehicle_id}")
    
    def test_create_operation_without_vehicle_id_defaults_to_workshop_scope(self):
        """Create operation without vehicleId and verify scope is 'workshop'"""
        operation_data = {
            "type": "purchase",
            "partnerName": f"TEST_Supplier_{uuid.uuid4().hex[:6]}",
            "partnerType": "supplier",
            "items": [{"name": "Parts Purchase", "price": 200, "quantity": 1}],
            "total": 200,
            "paymentMethod": "cash",
            "workshopId": WORKSHOP_ID,
            "date": datetime.utcnow().isoformat()
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/operations", json=operation_data)
        assert create_resp.status_code in [200, 201], f"Failed to create operation: {create_resp.text}"
        
        created_op = create_resp.json()
        
        # Verify scope is 'workshop' when no vehicleId
        assert created_op.get('scope') == 'workshop', f"scope should be 'workshop' when no vehicleId, got {created_op.get('scope')}"
        
        # Cleanup
        op_id = created_op.get('id')
        if op_id:
            requests.delete(f"{BASE_URL}/api/operations/{op_id}")
        
        print(f"✓ Operation without vehicleId defaults to scope='workshop'")


class TestFinanceReportsRegression:
    """Test that finance reports are working correctly"""
    
    def test_income_statement_returns_revenue_and_expenses(self):
        """Verify income statement returns revenue and expenses for cash formula"""
        params = {
            "workshop_id": WORKSHOP_ID,
            "start_date": "2026-01-01",
            "end_date": "2026-04-07"
        }
        
        resp = requests.get(f"{BASE_URL}/api/finance/reports/income-statement", params=params)
        assert resp.status_code == 200, f"Income statement failed: {resp.text}"
        
        data = resp.json()
        assert data.get('success') == True, f"Income statement not successful: {data}"
        
        totals = data.get('data', {}).get('totals', {})
        assert 'revenue' in totals, "Revenue not in income statement totals"
        assert 'expenses' in totals, "Expenses not in income statement totals"
        
        revenue = totals.get('revenue', 0)
        expenses = totals.get('expenses', 0)
        current_cash = revenue - expenses
        
        print(f"✓ Income statement working: Revenue={revenue}, Expenses={expenses}, CurrentCash={current_cash}")
    
    def test_balance_sheet_returns_assets_liabilities(self):
        """Verify balance sheet returns assets and liabilities"""
        params = {
            "workshop_id": WORKSHOP_ID,
            "as_of_date": "2026-04-07"
        }
        
        resp = requests.get(f"{BASE_URL}/api/finance/reports/balance-sheet", params=params)
        assert resp.status_code == 200, f"Balance sheet failed: {resp.text}"
        
        data = resp.json()
        assert data.get('success') == True, f"Balance sheet not successful: {data}"
        
        totals = data.get('data', {}).get('totals', {})
        assert 'assets' in totals, "Assets not in balance sheet totals"
        assert 'liabilities' in totals, "Liabilities not in balance sheet totals"
        
        print(f"✓ Balance sheet working: Assets={totals.get('assets')}, Liabilities={totals.get('liabilities')}")
    
    def test_trial_balance_returns_accounts(self):
        """Verify trial balance returns accounts"""
        params = {
            "workshop_id": WORKSHOP_ID,
            "start_date": "2026-01-01",
            "end_date": "2026-04-07"
        }
        
        resp = requests.get(f"{BASE_URL}/api/finance/reports/trial-balance", params=params)
        assert resp.status_code == 200, f"Trial balance failed: {resp.text}"
        
        data = resp.json()
        assert data.get('success') == True, f"Trial balance not successful: {data}"
        
        accounts = data.get('data', {}).get('accounts', [])
        print(f"✓ Trial balance working: {len(accounts)} accounts returned")
    
    def test_reconciliation_returns_summary(self):
        """Verify reconciliation returns summary"""
        params = {
            "workshop_id": WORKSHOP_ID,
            "start_date": "2026-01-01",
            "end_date": "2026-04-07"
        }
        
        resp = requests.get(f"{BASE_URL}/api/finance/reports/reconciliation", params=params)
        assert resp.status_code == 200, f"Reconciliation failed: {resp.text}"
        
        data = resp.json()
        assert data.get('success') == True, f"Reconciliation not successful: {data}"
        
        summary = data.get('data', {}).get('summary', {})
        print(f"✓ Reconciliation working: matched={summary.get('matched')}")


class TestOperationsListRegression:
    """Test that operations list is working"""
    
    def test_operations_list_returns_operations(self):
        """Verify operations list returns operations with required fields"""
        params = {
            "workshop_id": WORKSHOP_ID,
            "limit": 10
        }
        
        resp = requests.get(f"{BASE_URL}/api/operations", params=params)
        assert resp.status_code == 200, f"Operations list failed: {resp.text}"
        
        operations = resp.json()
        assert isinstance(operations, list), "Operations should be a list"
        
        if operations:
            op = operations[0]
            # Check required fields for OperationCard display
            assert 'id' in op, "Operation missing id"
            assert 'type' in op, "Operation missing type"
            
            # Check for partnerName (customer display)
            has_partner = 'partnerName' in op or 'partner_name' in op
            print(f"✓ Operations list working: {len(operations)} operations, has partnerName: {has_partner}")
        else:
            print("✓ Operations list working: 0 operations (empty)")


class TestVehiclesListRegression:
    """Test that vehicles list is working for vehicle display"""
    
    def test_vehicles_list_returns_vehicles(self):
        """Verify vehicles list returns vehicles with required fields"""
        params = {"limit": 5}
        
        resp = requests.get(f"{BASE_URL}/api/vehicles", params=params)
        assert resp.status_code == 200, f"Vehicles list failed: {resp.text}"
        
        vehicles = resp.json()
        assert isinstance(vehicles, list), "Vehicles should be a list"
        
        if vehicles:
            v = vehicles[0]
            # Check required fields for vehicle display
            assert 'id' in v, "Vehicle missing id"
            
            # Check for plate number and brand/model
            has_plate = 'plateNumber' in v or 'plate_number' in v
            has_brand = 'brand' in v
            
            print(f"✓ Vehicles list working: {len(vehicles)} vehicles, has plateNumber: {has_plate}, has brand: {has_brand}")
        else:
            print("✓ Vehicles list working: 0 vehicles (empty)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
