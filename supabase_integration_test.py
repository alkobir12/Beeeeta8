#!/usr/bin/env python3
"""
Supabase Integration Testing Script for Workshop Management System
اختبار تكامل شامل بين Supabase وبقية الصفحات الرئيسية

Test Focus:
1. Vehicle reception page (VehicleDetails / إنشاء زيارة جديدة أو استقبال مركبة)
2. Customer approval link page (approval link)
3. General consistency verification between site and Supabase
4. Detailed logging of all API calls and responses
"""

import requests
import json
import sys
from datetime import datetime, timedelta
import uuid
import time

# Get backend URL from environment
BACKEND_URL = "https://financial-ssot.preview.emergentagent.com/api"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "total": 0,
    "logs": []
}

def log_api_call(endpoint, method, data=None, response=None, status_code=None):
    """Log API call details for comprehensive reporting"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": endpoint,
        "method": method,
        "data_sent": data,
        "status_code": status_code,
        "response": response
    }
    test_results["logs"].append(log_entry)
    
    print(f"\n📡 API Call: {method} {endpoint}")
    if data:
        print(f"   📤 Data Sent: {json.dumps(data, ensure_ascii=False, indent=2)[:200]}...")
    print(f"   📥 Status: {status_code}")
    if response:
        print(f"   📥 Response: {json.dumps(response, ensure_ascii=False, indent=2)[:300]}...")

def log_test(name, passed, details=""):
    """Log test result"""
    test_results["total"] += 1
    if passed:
        test_results["passed"].append(name)
        print(f"\n✅ {name}")
        if details:
            print(f"   {details}")
    else:
        test_results["failed"].append(name)
        print(f"\n❌ {name}")
        if details:
            print(f"   {details}")

def print_summary():
    """Print comprehensive test summary"""
    print("\n" + "="*80)
    print("📊 SUPABASE INTEGRATION TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {test_results['total']}")
    print(f"Passed: {len(test_results['passed'])} ✅")
    print(f"Failed: {len(test_results['failed'])} ❌")
    
    if test_results['failed']:
        print("\n❌ Failed Tests:")
        for test in test_results['failed']:
            print(f"  - {test}")
    
    print(f"\n📡 Total API Calls: {len(test_results['logs'])}")
    print("="*80)

# ============================================================================
# 1. VEHICLE RECEPTION PAGE TESTING (صفحة استقبال مركبة)
# ============================================================================

def test_vehicle_reception_integration():
    """Test vehicle reception page integration with Supabase"""
    print("\n" + "="*80)
    print("🚗 TESTING VEHICLE RECEPTION PAGE INTEGRATION")
    print("اختبار تكامل صفحة استقبال المركبة مع Supabase")
    print("="*80)
    
    # Test data - realistic Arabic data
    vehicle_data = {
        "plateNumber": f"ت ج ر {str(uuid.uuid4())[:4]}",
        "brand": "تويوتا",
        "model": "كامري",
        "year": 2022,
        "color": "أبيض لؤلؤي",
        "customerName": "أحمد محمد العميل",
        "customerPhone": "0501234567",
        "customerEmail": "ahmed.customer@example.com",
        "status": "diagnosis",
        "mileage": 45000,
        "fuelType": "بنزين",
        "engineSize": "2.5L"
    }
    
    created_vehicle_id = None
    
    # Step 1: Create new vehicle (إنشاء مركبة جديدة)
    print("\n[1] Creating new vehicle via POST /api/vehicles")
    try:
        response = requests.post(f"{BACKEND_URL}/vehicles", json=vehicle_data, timeout=15)
        response_data = response.json() if response.status_code == 200 else response.text
        log_api_call("/api/vehicles", "POST", vehicle_data, response_data, response.status_code)
        
        if response.status_code == 200:
            created_vehicle_id = response_data.get('id')
            log_test("Vehicle Creation", True, 
                    f"Vehicle ID: {created_vehicle_id}, Plate: {response_data.get('plateNumber')}")
        else:
            log_test("Vehicle Creation", False, 
                    f"Status: {response.status_code}, Error: {response_data}")
            return None
    except Exception as e:
        log_test("Vehicle Creation", False, f"Exception: {str(e)}")
        return None
    
    # Step 2: Verify vehicle saved in Supabase via GET /api/vehicles
    print("\n[2] Verifying vehicle saved in Supabase via GET /api/vehicles")
    try:
        response = requests.get(f"{BACKEND_URL}/vehicles", timeout=15)
        response_data = response.json() if response.status_code == 200 else response.text
        log_api_call("/api/vehicles", "GET", None, response_data, response.status_code)
        
        if response.status_code == 200:
            vehicles = response_data
            created_vehicle = next((v for v in vehicles if v.get('id') == created_vehicle_id), None)
            
            if created_vehicle:
                log_test("Vehicle Verification in Supabase", True, 
                        f"Found vehicle with matching data: {created_vehicle.get('plateNumber')}")
                
                # Verify all fields match
                fields_match = True
                for key, expected_value in vehicle_data.items():
                    actual_value = created_vehicle.get(key)
                    if actual_value != expected_value:
                        print(f"   ⚠️ Field mismatch - {key}: expected '{expected_value}', got '{actual_value}'")
                        fields_match = False
                
                if fields_match:
                    print("   ✅ All vehicle fields match expected values")
                else:
                    print("   ⚠️ Some vehicle fields don't match")
            else:
                log_test("Vehicle Verification in Supabase", False, 
                        f"Vehicle with ID {created_vehicle_id} not found in list")
        else:
            log_test("Vehicle Verification in Supabase", False, 
                    f"Status: {response.status_code}, Error: {response_data}")
    except Exception as e:
        log_test("Vehicle Verification in Supabase", False, f"Exception: {str(e)}")
    
    # Step 3: Get specific vehicle details via GET /api/vehicles/{id}
    if created_vehicle_id:
        print(f"\n[3] Getting vehicle details via GET /api/vehicles/{created_vehicle_id}")
        try:
            response = requests.get(f"{BACKEND_URL}/vehicles/{created_vehicle_id}", timeout=15)
            response_data = response.json() if response.status_code == 200 else response.text
            log_api_call(f"/api/vehicles/{created_vehicle_id}", "GET", None, response_data, response.status_code)
            
            if response.status_code == 200:
                vehicle_details = response_data
                log_test("Vehicle Details Retrieval", True, 
                        f"Retrieved vehicle: {vehicle_details.get('plateNumber')} - {vehicle_details.get('brand')} {vehicle_details.get('model')}")
            else:
                log_test("Vehicle Details Retrieval", False, 
                        f"Status: {response.status_code}, Error: {response_data}")
        except Exception as e:
            log_test("Vehicle Details Retrieval", False, f"Exception: {str(e)}")
    
    # Step 4: Create initial operation/visit for the vehicle
    if created_vehicle_id:
        print(f"\n[4] Creating initial operation/visit for vehicle")
        operation_data = {
            "vehicleId": created_vehicle_id,
            "type": "diagnosis",
            "partnerType": "customer",
            "partnerName": "أحمد محمد العميل",
            "items": [
                {
                    "itemType": "service",
                    "itemId": "diag-001",
                    "name": "فحص شامل للمركبة",
                    "qty": 1,
                    "price": 150
                }
            ],
            "paymentMethod": "cash",
            "notes": "فحص أولي عند استقبال المركبة"
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/operations", json=operation_data, timeout=15)
            response_data = response.json() if response.status_code == 200 else response.text
            log_api_call("/api/operations", "POST", operation_data, response_data, response.status_code)
            
            if response.status_code == 200:
                operation_id = response_data.get('id')
                log_test("Initial Operation Creation", True, 
                        f"Operation ID: {operation_id}, Type: {response_data.get('type')}")
            else:
                log_test("Initial Operation Creation", False, 
                        f"Status: {response.status_code}, Error: {response_data}")
        except Exception as e:
            log_test("Initial Operation Creation", False, f"Exception: {str(e)}")
    
    # Step 5: Verify operations linked to vehicle
    if created_vehicle_id:
        print(f"\n[5] Verifying operations linked to vehicle via GET /api/operations?vehicle_id={created_vehicle_id}")
        try:
            response = requests.get(f"{BACKEND_URL}/operations?vehicle_id={created_vehicle_id}", timeout=15)
            response_data = response.json() if response.status_code == 200 else response.text
            log_api_call(f"/api/operations?vehicle_id={created_vehicle_id}", "GET", None, response_data, response.status_code)
            
            if response.status_code == 200:
                operations = response_data
                log_test("Vehicle Operations Verification", True, 
                        f"Found {len(operations)} operations for vehicle")
                
                for op in operations:
                    print(f"   📋 Operation: {op.get('type')} - {op.get('notes', 'No notes')}")
            else:
                log_test("Vehicle Operations Verification", False, 
                        f"Status: {response.status_code}, Error: {response_data}")
        except Exception as e:
            log_test("Vehicle Operations Verification", False, f"Exception: {str(e)}")
    
    return created_vehicle_id

# ============================================================================
# 2. CUSTOMER APPROVAL LINK TESTING (صفحة رابط طلب الاعتماد من العميل)
# ============================================================================

def test_customer_approval_link_integration(vehicle_id):
    """Test customer approval link integration"""
    print("\n" + "="*80)
    print("📋 TESTING CUSTOMER APPROVAL LINK INTEGRATION")
    print("اختبار تكامل صفحة رابط طلب الاعتماد من العميل")
    print("="*80)
    
    if not vehicle_id:
        print("⚠️ Skipping approval tests - no vehicle ID provided")
        return None
    
    # First, get a real customer ID from the system
    print("\n[0] Getting existing customer ID for approval test")
    customer_id = None
    try:
        response = requests.get(f"{BACKEND_URL}/customers", timeout=15)
        if response.status_code == 200:
            customers = response.json()
            if customers:
                customer_id = customers[0].get('id')
                print(f"   ✅ Using customer ID: {customer_id}")
            else:
                print("   ⚠️ No customers found, creating new customer")
                # Create a customer for testing
                customer_data = {
                    "name": "عميل اختبار الاعتماد",
                    "phone": "0501234567",
                    "email": "approval.test@example.com"
                }
                response = requests.post(f"{BACKEND_URL}/customers", json=customer_data, timeout=15)
                if response.status_code == 200:
                    customer_id = response.json().get('id')
                    print(f"   ✅ Created customer ID: {customer_id}")
    except Exception as e:
        print(f"   ⚠️ Error getting customer: {str(e)}")
    
    if not customer_id:
        print("⚠️ Skipping approval tests - no customer ID available")
        return None
    
    # Step 1: Create approval request
    print("\n[1] Creating approval request via POST /api/approvals")
    approval_data = {
        "vehicleId": vehicle_id,
        "customerId": customer_id,
        "title": "طلب اعتماد إصلاح شامل",
        "amount": 2500.0,
        "serviceItems": [
            {"name": "تغيير زيت المحرك", "price": 300},
            {"name": "تغيير فلاتر", "price": 200},
            {"name": "فحص نظام الفرامل", "price": 500},
            {"name": "إصلاح نظام التكييف", "price": 1500}
        ],
        "serviceItemsText": "تغيير زيت المحرك - 300 ريال\nتغيير فلاتر - 200 ريال\nفحص نظام الفرامل - 500 ريال\nإصلاح نظام التكييف - 1500 ريال",
        "expiryDays": 7
    }
    
    approval_token = None
    try:
        response = requests.post(f"{BACKEND_URL}/approvals", json=approval_data, timeout=15)
        response_data = response.json() if response.status_code == 200 else response.text
        log_api_call("/api/approvals", "POST", approval_data, response_data, response.status_code)
        
        if response.status_code == 200:
            approval_token = response_data.get('token')
            approval_link = response_data.get('approvalLink', f"/approval/{approval_token}")
            log_test("Approval Request Creation", True, 
                    f"Token: {approval_token}, Link: {approval_link}")
        else:
            log_test("Approval Request Creation", False, 
                    f"Status: {response.status_code}, Error: {response_data}")
            return None
    except Exception as e:
        log_test("Approval Request Creation", False, f"Exception: {str(e)}")
        return None
    
    # Step 2: Access public approval page
    if approval_token:
        print(f"\n[2] Accessing public approval page via GET /api/approvals/public/{approval_token}")
        try:
            response = requests.get(f"{BACKEND_URL}/approvals/public/{approval_token}", timeout=15)
            response_data = response.json() if response.status_code == 200 else response.text
            log_api_call(f"/api/approvals/public/{approval_token}", "GET", None, response_data, response.status_code)
            
            if response.status_code == 200:
                approval_details = response_data
                log_test("Public Approval Page Access", True, 
                        f"Title: {approval_details.get('title')}, Amount: {approval_details.get('amount')} ريال")
                
                # Verify required data is present
                required_fields = ['title', 'amount', 'vehicleData', 'workshopData']
                missing_fields = [field for field in required_fields if not approval_details.get(field)]
                
                if missing_fields:
                    print(f"   ⚠️ Missing fields in approval data: {missing_fields}")
                else:
                    print("   ✅ All required approval data present")
                    
                # Display workshop and vehicle data
                workshop_data = approval_details.get('workshopData', {})
                vehicle_data = approval_details.get('vehicleData', {})
                
                print(f"   🏪 Workshop: {workshop_data.get('name', 'N/A')}")
                print(f"   🚗 Vehicle: {vehicle_data.get('plateNumber', 'N/A')} - {vehicle_data.get('brand', 'N/A')} {vehicle_data.get('model', 'N/A')}")
                
            else:
                log_test("Public Approval Page Access", False, 
                        f"Status: {response.status_code}, Error: {response_data}")
        except Exception as e:
            log_test("Public Approval Page Access", False, f"Exception: {str(e)}")
    
    # Step 3: Submit customer approval response
    if approval_token:
        print(f"\n[3] Submitting customer approval response via POST /api/approvals/public/{approval_token}/respond")
        response_data_submit = {
            "status": "approved",
            "name": "أحمد محمد العميل",
            "phone": "0501234567",
            "notes": "موافق على جميع الأعمال المطلوبة"
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/approvals/public/{approval_token}/respond", 
                                   json=response_data_submit, timeout=15)
            response_data = response.json() if response.status_code == 200 else response.text
            log_api_call(f"/api/approvals/public/{approval_token}/respond", "POST", 
                        response_data_submit, response_data, response.status_code)
            
            if response.status_code == 200:
                log_test("Customer Approval Response", True, 
                        f"Response submitted successfully: {response_data.get('message', 'Success')}")
            else:
                log_test("Customer Approval Response", False, 
                        f"Status: {response.status_code}, Error: {response_data}")
        except Exception as e:
            log_test("Customer Approval Response", False, f"Exception: {str(e)}")
    
    # Step 4: Verify approval status updated in Supabase
    if approval_token and vehicle_id:
        print(f"\n[4] Verifying approval status updated via GET /api/approvals?vehicle_id={vehicle_id}")
        try:
            response = requests.get(f"{BACKEND_URL}/approvals?vehicle_id={vehicle_id}", timeout=15)
            response_data = response.json() if response.status_code == 200 else response.text
            log_api_call(f"/api/approvals?vehicle_id={vehicle_id}", "GET", None, response_data, response.status_code)
            
            if response.status_code == 200:
                approvals = response_data
                updated_approval = next((a for a in approvals if a.get('token') == approval_token), None)
                
                if updated_approval:
                    status = updated_approval.get('status')
                    responder_name = updated_approval.get('responderName')
                    responded_at = updated_approval.get('respondedAt')
                    
                    log_test("Approval Status Verification", True, 
                            f"Status: {status}, Responder: {responder_name}, Time: {responded_at}")
                    
                    if status == 'approved' and responder_name and responded_at:
                        print("   ✅ Approval status correctly updated in Supabase")
                    else:
                        print("   ⚠️ Approval status update incomplete")
                else:
                    log_test("Approval Status Verification", False, 
                            f"Approval with token {approval_token} not found")
            else:
                log_test("Approval Status Verification", False, 
                        f"Status: {response.status_code}, Error: {response_data}")
        except Exception as e:
            log_test("Approval Status Verification", False, f"Exception: {str(e)}")
    
    return approval_token

# ============================================================================
# 3. GENERAL CONSISTENCY VERIFICATION (التحقق من التطابق العام)
# ============================================================================

def test_general_consistency_verification(vehicle_id):
    """Test general consistency between site and Supabase"""
    print("\n" + "="*80)
    print("🔍 TESTING GENERAL CONSISTENCY VERIFICATION")
    print("اختبار التطابق العام بين الموقع و Supabase")
    print("="*80)
    
    if not vehicle_id:
        print("⚠️ Skipping consistency tests - no vehicle ID provided")
        return
    
    # Step 1: Get operations for specific vehicle
    print(f"\n[1] Getting operations for vehicle via GET /api/operations?vehicle_id={vehicle_id}")
    vehicle_operations = []
    try:
        response = requests.get(f"{BACKEND_URL}/operations?vehicle_id={vehicle_id}", timeout=15)
        response_data = response.json() if response.status_code == 200 else response.text
        log_api_call(f"/api/operations?vehicle_id={vehicle_id}", "GET", None, response_data, response.status_code)
        
        if response.status_code == 200:
            vehicle_operations = response_data
            total_amount = sum(op.get('total', 0) for op in vehicle_operations)
            log_test("Vehicle Operations Retrieval", True, 
                    f"Found {len(vehicle_operations)} operations, Total: {total_amount} ريال")
            
            for op in vehicle_operations:
                print(f"   📋 {op.get('type')}: {op.get('total', 0)} ريال - {op.get('notes', 'No notes')}")
        else:
            log_test("Vehicle Operations Retrieval", False, 
                    f"Status: {response.status_code}, Error: {response_data}")
    except Exception as e:
        log_test("Vehicle Operations Retrieval", False, f"Exception: {str(e)}")
    
    # Step 2: Get financial reports to verify consistency
    print(f"\n[2] Getting financial reports via GET /api/finance/reports/income-statement")
    try:
        # Get current month income statement
        start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        params = {
            'workshop_id': 'finmodule-sync',
            'start_date': start_date,
            'end_date': end_date
        }
        
        response = requests.get(f"{BACKEND_URL}/finance/reports/income-statement", 
                              params=params, timeout=15)
        response_data = response.json() if response.status_code == 200 else response.text
        log_api_call("/api/finance/reports/income-statement", "GET", params, response_data, response.status_code)
        
        if response.status_code == 200:
            financial_data = response_data.get('data', {})
            totals = financial_data.get('totals', {})
            
            revenue = totals.get('revenue', 0)
            expenses = totals.get('expenses', 0)
            net_income = totals.get('net_income', 0)
            
            log_test("Financial Reports Retrieval", True, 
                    f"Revenue: {revenue} ريال, Expenses: {expenses} ريال, Net Income: {net_income} ريال")
            
            # Verify calculations
            calculated_net = revenue - expenses
            if abs(calculated_net - net_income) < 0.01:  # Allow for small rounding differences
                print("   ✅ Financial calculations are consistent")
            else:
                print(f"   ⚠️ Financial calculation mismatch: {calculated_net} vs {net_income}")
                
        else:
            log_test("Financial Reports Retrieval", False, 
                    f"Status: {response.status_code}, Error: {response_data}")
    except Exception as e:
        log_test("Financial Reports Retrieval", False, f"Exception: {str(e)}")
    
    # Step 3: Get balance sheet for consistency check
    print(f"\n[3] Getting balance sheet via GET /api/finance/reports/balance-sheet")
    try:
        params = {
            'workshop_id': 'finmodule-sync',
            'as_of_date': datetime.now().strftime('%Y-%m-%d')
        }
        
        response = requests.get(f"{BACKEND_URL}/finance/reports/balance-sheet", 
                              params=params, timeout=15)
        response_data = response.json() if response.status_code == 200 else response.text
        log_api_call("/api/finance/reports/balance-sheet", "GET", params, response_data, response.status_code)
        
        if response.status_code == 200:
            balance_data = response_data.get('data', {})
            totals = balance_data.get('totals', {})
            
            assets = totals.get('assets', 0)
            liabilities = totals.get('liabilities', 0)
            equity = totals.get('equity', 0)
            liabilities_plus_equity = totals.get('liabilities_plus_equity', 0)
            
            log_test("Balance Sheet Retrieval", True, 
                    f"Assets: {assets} ريال, Liabilities: {liabilities} ريال, Equity: {equity} ريال")
            
            # Verify balance sheet equation
            calculated_total = liabilities + equity
            if abs(calculated_total - liabilities_plus_equity) < 0.01:
                print("   ✅ Balance sheet totals are consistent")
            else:
                print(f"   ⚠️ Balance sheet total mismatch: {calculated_total} vs {liabilities_plus_equity}")
                
            # Check if balanced
            if abs(assets - liabilities_plus_equity) < 0.01:
                print("   ✅ Balance sheet is balanced (Assets = Liabilities + Equity)")
            else:
                print(f"   ⚠️ Balance sheet is not balanced: Assets {assets} ≠ L+E {liabilities_plus_equity}")
                
        else:
            log_test("Balance Sheet Retrieval", False, 
                    f"Status: {response.status_code}, Error: {response_data}")
    except Exception as e:
        log_test("Balance Sheet Retrieval", False, f"Exception: {str(e)}")
    
    # Step 4: Cross-verify operations with journal entries
    print(f"\n[4] Cross-verifying operations with journal entries")
    try:
        # Add required workshop_id parameter for journal entries
        params = {'workshop_id': 'finmodule-sync'}
        response = requests.get(f"{BACKEND_URL}/finance/journal-entries", params=params, timeout=15)
        response_data = response.json() if response.status_code == 200 else response.text
        log_api_call("/api/finance/journal-entries", "GET", params, response_data, response.status_code)
        
        if response.status_code == 200:
            journal_response = response_data
            journal_entries = journal_response.get('data', []) if isinstance(journal_response, dict) else journal_response
            log_test("Journal Entries Cross-Verification", True, 
                    f"Found {len(journal_entries)} journal entries for cross-verification")
            
            # Calculate total debits and credits
            total_debits = 0
            total_credits = 0
            for entry in journal_entries:
                lines = entry.get('lines', [])
                for line in lines:
                    # Handle different line formats
                    if isinstance(line, dict):
                        total_debits += line.get('debit', line.get('debit_amount', 0))
                        total_credits += line.get('credit', line.get('credit_amount', 0))
            
            print(f"   📊 Total Debits: {total_debits} ريال")
            print(f"   📊 Total Credits: {total_credits} ريال")
            
            if abs(total_debits - total_credits) < 0.01:
                print("   ✅ Journal entries are balanced (Debits = Credits)")
            else:
                print(f"   ⚠️ Journal entries imbalance: {total_debits} ≠ {total_credits}")
                
        else:
            log_test("Journal Entries Cross-Verification", False, 
                    f"Status: {response.status_code}, Error: {response_data}")
    except Exception as e:
        log_test("Journal Entries Cross-Verification", False, f"Exception: {str(e)}")

# ============================================================================
# CLEANUP FUNCTION
# ============================================================================

def cleanup_test_data(vehicle_id):
    """Clean up test data"""
    print("\n" + "="*80)
    print("🧹 CLEANING UP TEST DATA")
    print("="*80)
    
    if vehicle_id:
        print(f"\n[Cleanup] Deleting test vehicle: {vehicle_id}")
        try:
            response = requests.delete(f"{BACKEND_URL}/vehicles/{vehicle_id}", timeout=15)
            if response.status_code == 200:
                print("   ✅ Test vehicle deleted successfully")
            else:
                print(f"   ⚠️ Failed to delete vehicle: {response.status_code}")
        except Exception as e:
            print(f"   ⚠️ Error deleting vehicle: {str(e)}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("🏪 WORKSHOP MANAGEMENT SYSTEM - SUPABASE INTEGRATION TESTING")
    print("اختبار تكامل شامل بين Supabase وبقية الصفحات الرئيسية")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Run integration tests
    vehicle_id = test_vehicle_reception_integration()
    approval_token = test_customer_approval_link_integration(vehicle_id)
    test_general_consistency_verification(vehicle_id)
    
    # Clean up test data
    cleanup_test_data(vehicle_id)
    
    # Print comprehensive summary
    print_summary()
    
    # Print detailed API log summary
    print("\n" + "="*80)
    print("📋 DETAILED API CALL LOG")
    print("="*80)
    
    for i, log_entry in enumerate(test_results["logs"], 1):
        print(f"\n[{i}] {log_entry['method']} {log_entry['endpoint']}")
        print(f"    Time: {log_entry['timestamp']}")
        print(f"    Status: {log_entry['status_code']}")
        if log_entry['data_sent']:
            print(f"    Data: {json.dumps(log_entry['data_sent'], ensure_ascii=False)[:100]}...")
    
    print("\n" + "="*80)
    print("🎯 INTEGRATION TEST COMPLETE")
    print("="*80)
    
    # Exit with appropriate code
    if test_results['failed']:
        print("❌ Some tests failed - check logs above for details")
        sys.exit(1)
    else:
        print("✅ All integration tests passed successfully")
        sys.exit(0)

if __name__ == "__main__":
    main()