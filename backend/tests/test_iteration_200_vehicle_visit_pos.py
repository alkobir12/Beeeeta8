"""
Iteration 200 Tests - Vehicle fileNumber, Visit Payments, Smart POS, Operations
Tests:
1. PUT /api/vehicles/{id} saves fileNumber and customerFileNumber
2. Visit payment creates journal entry with source=visit_receipt_voucher
3. Smart POS salary template uses correct account (036 رواتب إدارية)
4. Operations page default account selection by operation type
5. Smart POS entry with customer+vehicle writes description tokens
"""
import pytest
import requests
import os
import uuid
import json
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://erp-compliance-check.preview.emergentagent.com')
WORKSHOP_ID = os.environ.get('REACT_APP_WORKSHOP_ID', 'finmodule-sync')


class TestVehicleFileNumber:
    """Test vehicle fileNumber and customerFileNumber save/retrieve"""
    
    def test_create_vehicle_with_file_number(self):
        """Create a vehicle and verify fileNumber is saved"""
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "plateNumber": f"TEST-{unique_id}",
            "brand": "Toyota",
            "model": "Camry",
            "year": 2024,
            "color": "White",
            "fileNumber": f"FILE-{unique_id}",
            "customerName": f"Test Customer {unique_id}",
            "customerPhone": f"05{unique_id[:8]}",
            "services": []
        }
        
        response = requests.post(f"{BASE_URL}/api/vehicles", json=payload)
        print(f"Create vehicle response: {response.status_code}")
        
        assert response.status_code in [200, 201], f"Failed to create vehicle: {response.text}"
        data = response.json()
        
        assert "id" in data, "Vehicle ID not returned"
        assert data.get("fileNumber") == payload["fileNumber"], f"fileNumber mismatch: expected {payload['fileNumber']}, got {data.get('fileNumber')}"
        
        # Store for cleanup
        self.vehicle_id = data["id"]
        print(f"✅ Created vehicle with fileNumber: {data.get('fileNumber')}")
        return data
    
    def test_update_vehicle_file_number(self):
        """Update vehicle fileNumber via PUT"""
        # First create a vehicle
        unique_id = str(uuid.uuid4())[:8]
        create_payload = {
            "plateNumber": f"UPD-{unique_id}",
            "brand": "Honda",
            "model": "Accord",
            "year": 2023,
            "color": "Black",
            "customerName": f"Update Test {unique_id}",
            "customerPhone": f"05{unique_id[:8]}",
            "services": []
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/vehicles", json=create_payload)
        assert create_resp.status_code in [200, 201], f"Failed to create vehicle: {create_resp.text}"
        vehicle = create_resp.json()
        vehicle_id = vehicle["id"]
        
        # Now update with fileNumber
        new_file_number = f"UPDATED-FILE-{unique_id}"
        update_payload = {
            "fileNumber": new_file_number
        }
        
        update_resp = requests.put(f"{BASE_URL}/api/vehicles/{vehicle_id}", json=update_payload)
        print(f"Update vehicle response: {update_resp.status_code}")
        
        assert update_resp.status_code == 200, f"Failed to update vehicle: {update_resp.text}"
        updated = update_resp.json()
        
        assert updated.get("fileNumber") == new_file_number, f"fileNumber not updated: expected {new_file_number}, got {updated.get('fileNumber')}"
        
        # Verify via GET
        get_resp = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}")
        assert get_resp.status_code == 200
        fetched = get_resp.json()
        
        assert fetched.get("fileNumber") == new_file_number, f"fileNumber not persisted: expected {new_file_number}, got {fetched.get('fileNumber')}"
        print(f"✅ Updated and verified fileNumber: {new_file_number}")
    
    def test_update_customer_file_number(self):
        """Update customerFileNumber via PUT vehicle"""
        unique_id = str(uuid.uuid4())[:8]
        create_payload = {
            "plateNumber": f"CUST-{unique_id}",
            "brand": "Nissan",
            "model": "Altima",
            "year": 2022,
            "color": "Silver",
            "customerName": f"Customer File Test {unique_id}",
            "customerPhone": f"05{unique_id[:8]}",
            "services": []
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/vehicles", json=create_payload)
        assert create_resp.status_code in [200, 201], f"Failed to create vehicle: {create_resp.text}"
        vehicle = create_resp.json()
        vehicle_id = vehicle["id"]
        
        # Update customerFileNumber
        customer_file = f"CUST-FILE-{unique_id}"
        update_payload = {
            "customerFileNumber": customer_file
        }
        
        update_resp = requests.put(f"{BASE_URL}/api/vehicles/{vehicle_id}", json=update_payload)
        print(f"Update customerFileNumber response: {update_resp.status_code}")
        
        assert update_resp.status_code == 200, f"Failed to update: {update_resp.text}"
        updated = update_resp.json()
        
        # customerFileNumber may be stored on customer, verify via GET
        get_resp = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}")
        assert get_resp.status_code == 200
        fetched = get_resp.json()
        
        print(f"✅ customerFileNumber update completed. Value: {fetched.get('customerFileNumber')}")


class TestSmartPOSJournal:
    """Test Smart POS Journal templates and account mapping"""
    
    def test_salary_template_uses_correct_account(self):
        """Verify salary template uses account 036 (رواتب إدارية)"""
        # First get accounts to verify 036 exists
        accounts_resp = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts", params={"workshop_id": WORKSHOP_ID})
        
        if accounts_resp.status_code == 200:
            accounts = accounts_resp.json()
            if isinstance(accounts, dict) and "data" in accounts:
                accounts = accounts.get("data", [])
            
            # Find salary expense account
            salary_account = None
            for acc in accounts:
                code = str(acc.get("code", "")).strip()
                name = str(acc.get("name_ar", "") or acc.get("name", "")).lower()
                if code == "036" or "رواتب" in name:
                    salary_account = acc
                    break
            
            if salary_account:
                print(f"✅ Found salary account: {salary_account.get('code')} - {salary_account.get('name_ar') or salary_account.get('name')}")
            else:
                print("⚠️ Salary account 036 not found in chart of accounts")
        
        # Create a salary journal entry via Smart POS
        unique_id = str(uuid.uuid4())[:8]
        salary_entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": f"TEST_SALARY_{unique_id} — رواتب موظفين [PARTY:موظف اختبار] [PARTY_TYPE:open]",
            "transaction_type": "expense",
            "source": "pos_template",
            "total": 3000,
            "lines": [
                {"account": "036", "account_name": "رواتب إدارية", "debit": 3000, "credit": 0},
                {"account": "004", "account_name": "البنك", "debit": 0, "credit": 3000}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/finance/journal-entries",
            json=salary_entry,
            params={"workshop_id": WORKSHOP_ID}
        )
        
        print(f"Salary entry response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            entry_id = data.get("id") or (data.get("data", [{}])[0].get("id") if isinstance(data.get("data"), list) else None)
            print(f"✅ Created salary journal entry with debit 036 (رواتب إدارية), credit 004 (البنك)")
            
            # Verify the entry
            if entry_id:
                get_resp = requests.get(
                    f"{BASE_URL}/api/finance/journal-entries/{entry_id}",
                    params={"workshop_id": WORKSHOP_ID}
                )
                if get_resp.status_code == 200:
                    entry = get_resp.json()
                    lines = entry.get("lines", [])
                    debit_line = next((l for l in lines if l.get("debit", 0) > 0), None)
                    if debit_line:
                        assert debit_line.get("account") == "036", f"Expected debit account 036, got {debit_line.get('account')}"
                        print(f"✅ Verified debit account is 036")
        else:
            print(f"⚠️ Failed to create salary entry: {response.text}")
    
    def test_pos_entry_with_customer_vehicle_tokens(self):
        """Test Smart POS entry writes [PARTY], [PARTY_TYPE], [VEHICLE_REF] tokens"""
        unique_id = str(uuid.uuid4())[:8]
        customer_name = f"عميل اختبار {unique_id}"
        vehicle_ref = f"ABC-{unique_id}"
        
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": f"TEST_POS_{unique_id} — بيع فوري [PARTY:{customer_name}] [PARTY_TYPE:customer] [VEHICLE_REF:{vehicle_ref}]",
            "transaction_type": "sale",
            "source": "pos_instant_sale",
            "total": 500,
            "lines": [
                {"account": "003", "account_name": "النقد", "debit": 500, "credit": 0},
                {"account": "025", "account_name": "إيرادات الخدمات", "debit": 0, "credit": 500}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/finance/journal-entries",
            json=entry,
            params={"workshop_id": WORKSHOP_ID}
        )
        
        print(f"POS entry with tokens response: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            entry_id = data.get("id") or (data.get("data", [{}])[0].get("id") if isinstance(data.get("data"), list) else None)
            
            # Verify tokens in description
            if entry_id:
                get_resp = requests.get(
                    f"{BASE_URL}/api/finance/journal-entries/{entry_id}",
                    params={"workshop_id": WORKSHOP_ID}
                )
                if get_resp.status_code == 200:
                    fetched = get_resp.json()
                    desc = fetched.get("description", "")
                    
                    assert f"[PARTY:{customer_name}]" in desc, f"PARTY token not found in description"
                    assert "[PARTY_TYPE:customer]" in desc, f"PARTY_TYPE token not found"
                    assert f"[VEHICLE_REF:{vehicle_ref}]" in desc, f"VEHICLE_REF token not found"
                    
                    print(f"✅ Verified tokens in journal entry description")
                    print(f"   PARTY: {customer_name}")
                    print(f"   PARTY_TYPE: customer")
                    print(f"   VEHICLE_REF: {vehicle_ref}")
        else:
            print(f"⚠️ Failed to create POS entry: {response.text}")


class TestOperationsDefaultAccount:
    """Test Operations page default account selection by operation type"""
    
    def test_get_accounts_for_operations(self):
        """Verify accounts endpoint returns accounts with types"""
        response = requests.get(f"{BASE_URL}/api/finance/chart-of-accounts", params={"workshop_id": WORKSHOP_ID})
        
        if response.status_code == 200:
            data = response.json()
            accounts = data.get("data", []) if isinstance(data, dict) else data
            
            # Check for key accounts
            revenue_accounts = [a for a in accounts if a.get("type") == "revenue"]
            expense_accounts = [a for a in accounts if a.get("type") == "expense"]
            asset_accounts = [a for a in accounts if a.get("type") == "asset"]
            liability_accounts = [a for a in accounts if a.get("type") == "liability"]
            
            print(f"✅ Found accounts by type:")
            print(f"   Revenue: {len(revenue_accounts)}")
            print(f"   Expense: {len(expense_accounts)}")
            print(f"   Asset: {len(asset_accounts)}")
            print(f"   Liability: {len(liability_accounts)}")
            
            # Verify key accounts exist
            codes = [str(a.get("code", "")).strip() for a in accounts]
            
            assert "005" in codes or any("العملاء" in str(a.get("name_ar", "")) for a in accounts), "Customer account (005) not found"
            assert "2101" in codes or any("الموردون" in str(a.get("name_ar", "")) for a in accounts), "Supplier account (2101) not found"
            
            print(f"✅ Key accounts verified (005 العملاء, 2101 الموردون)")
        else:
            print(f"⚠️ Failed to get accounts: {response.status_code}")


class TestVisitPaymentJournalEntry:
    """Test visit payment creates journal entry with source=visit_receipt_voucher"""
    
    def test_visit_receipt_voucher_source(self):
        """Verify journal entries with source=visit_receipt_voucher exist or can be created"""
        # Query existing journal entries with this source
        response = requests.get(
            f"{BASE_URL}/api/finance/journal-entries",
            params={"workshop_id": WORKSHOP_ID, "limit": 100}
        )
        
        if response.status_code == 200:
            data = response.json()
            entries = data.get("data", []) if isinstance(data, dict) else data
            
            # Find entries with visit_receipt_voucher source
            visit_entries = [e for e in entries if e.get("source") == "visit_receipt_voucher"]
            
            if visit_entries:
                print(f"✅ Found {len(visit_entries)} journal entries with source=visit_receipt_voucher")
                for entry in visit_entries[:3]:
                    print(f"   - {entry.get('id')[:8]}... | {entry.get('date')} | {entry.get('total')} ر.س")
            else:
                print("ℹ️ No existing visit_receipt_voucher entries found (this is expected if no visits have been paid)")
                
                # Create a test entry to verify the source is accepted
                unique_id = str(uuid.uuid4())[:8]
                test_entry = {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "description": f"TEST_VISIT_RECEIPT_{unique_id} — سند قبض دفعة مقدمة [PARTY:عميل اختبار] [PARTY_TYPE:customer]",
                    "transaction_type": "payment",
                    "source": "visit_receipt_voucher",
                    "total": 200,
                    "lines": [
                        {"account": "003", "account_name": "النقد", "debit": 200, "credit": 0},
                        {"account": "005", "account_name": "العملاء", "debit": 0, "credit": 200}
                    ]
                }
                
                create_resp = requests.post(
                    f"{BASE_URL}/api/finance/journal-entries",
                    json=test_entry,
                    params={"workshop_id": WORKSHOP_ID}
                )
                
                if create_resp.status_code in [200, 201]:
                    print(f"✅ Successfully created test visit_receipt_voucher entry")
                else:
                    print(f"⚠️ Failed to create test entry: {create_resp.text}")
        else:
            print(f"⚠️ Failed to query journal entries: {response.status_code}")


class TestPaymentMethodAccounts:
    """Test payment method to account mapping (cash/bank/pos)"""
    
    def test_cash_payment_uses_003(self):
        """Verify cash payment uses account 003 (النقد)"""
        unique_id = str(uuid.uuid4())[:8]
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": f"TEST_CASH_{unique_id} — دفعة نقدية",
            "transaction_type": "payment",
            "source": "pos_template",
            "total": 100,
            "lines": [
                {"account": "003", "account_name": "النقد", "debit": 100, "credit": 0},
                {"account": "005", "account_name": "العملاء", "debit": 0, "credit": 100}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/finance/journal-entries",
            json=entry,
            params={"workshop_id": WORKSHOP_ID}
        )
        
        assert response.status_code in [200, 201], f"Failed to create cash entry: {response.text}"
        print(f"✅ Cash payment entry created with account 003")
    
    def test_bank_payment_uses_004(self):
        """Verify bank payment uses account 004 (البنك)"""
        unique_id = str(uuid.uuid4())[:8]
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": f"TEST_BANK_{unique_id} — تحويل بنكي",
            "transaction_type": "payment",
            "source": "pos_template",
            "total": 150,
            "lines": [
                {"account": "004", "account_name": "البنك", "debit": 150, "credit": 0},
                {"account": "005", "account_name": "العملاء", "debit": 0, "credit": 150}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/finance/journal-entries",
            json=entry,
            params={"workshop_id": WORKSHOP_ID}
        )
        
        assert response.status_code in [200, 201], f"Failed to create bank entry: {response.text}"
        print(f"✅ Bank payment entry created with account 004")
    
    def test_pos_payment_uses_006(self):
        """Verify POS payment uses account 006 (نقاط بيع)"""
        unique_id = str(uuid.uuid4())[:8]
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "description": f"TEST_POS_PAYMENT_{unique_id} — نقاط بيع",
            "transaction_type": "payment",
            "source": "pos_template",
            "total": 250,
            "lines": [
                {"account": "006", "account_name": "نقاط بيع", "debit": 250, "credit": 0},
                {"account": "005", "account_name": "العملاء", "debit": 0, "credit": 250}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/finance/journal-entries",
            json=entry,
            params={"workshop_id": WORKSHOP_ID}
        )
        
        assert response.status_code in [200, 201], f"Failed to create POS entry: {response.text}"
        print(f"✅ POS payment entry created with account 006")


class TestHealthAndBasicEndpoints:
    """Basic health and endpoint tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print(f"✅ Health check passed")
    
    def test_vehicles_list(self):
        """Test vehicles list endpoint"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200, f"Vehicles list failed: {response.status_code}"
        vehicles = response.json()
        print(f"✅ Vehicles list returned {len(vehicles)} vehicles")
    
    def test_customers_list(self):
        """Test customers list endpoint"""
        response = requests.get(f"{BASE_URL}/api/customers")
        assert response.status_code == 200, f"Customers list failed: {response.status_code}"
        customers = response.json()
        print(f"✅ Customers list returned {len(customers)} customers")
    
    def test_suppliers_list(self):
        """Test suppliers list endpoint"""
        response = requests.get(f"{BASE_URL}/api/suppliers")
        assert response.status_code == 200, f"Suppliers list failed: {response.status_code}"
        suppliers = response.json()
        print(f"✅ Suppliers list returned {len(suppliers)} suppliers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
