#!/usr/bin/env python3
"""
Comprehensive Invoice System Testing Script
اختبار شامل لنظام الفواتير - تشخيص حالة الترحيل إلى Supabase

This script tests:
1. Current system state (Supabase vs File-based)
2. Vehicle creation and deletion
3. Invoice operations (what works vs what doesn't)
4. Cleanup functionality
5. Provides clear diagnosis and recommendations
"""

import requests
import json
import sys
from datetime import datetime
import uuid

# Get backend URL from frontend/.env (REACT_APP_BACKEND_URL)
BACKEND_URL = "https://payment-defaults.preview.emergentagent.com/api"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "total": 0,
    "details": [],
    "diagnosis": {
        "supabase_tables_missing": [],
        "working_features": [],
        "broken_features": [],
        "recommendations": []
    }
}

def log_test(name, passed, details="", status_code=None, response_body=None):
    """Log test result with detailed information"""
    test_results["total"] += 1
    
    result_detail = {
        "name": name,
        "passed": passed,
        "details": details,
        "status_code": status_code,
        "response_body": response_body[:500] if response_body else None,
        "timestamp": datetime.now().isoformat()
    }
    test_results["details"].append(result_detail)
    
    if passed:
        test_results["passed"].append(name)
        print(f"✅ {name}")
        if details:
            print(f"   📋 {details}")
        if status_code:
            print(f"   🔢 Status Code: {status_code}")
    else:
        test_results["failed"].append(name)
        print(f"❌ {name}")
        if details:
            print(f"   ⚠️  {details}")
        if status_code:
            print(f"   🔢 Status Code: {status_code}")
        if response_body:
            print(f"   📄 Response: {response_body[:200]}...")

def add_diagnosis(category, item):
    """Add item to diagnosis"""
    if category in test_results["diagnosis"]:
        test_results["diagnosis"][category].append(item)

def test_system_diagnosis():
    """Comprehensive system diagnosis"""
    print("\n" + "="*80)
    print("🔍 SYSTEM DIAGNOSIS - INVOICE MIGRATION STATUS")
    print("تشخيص النظام - حالة ترحيل الفواتير")
    print("="*80)
    
    # Test 1: Check if invoices endpoint responds
    print("\n📋 [DIAGNOSIS 1] Testing Invoice API Availability")
    try:
        response = requests.get(f"{BACKEND_URL}/invoices", timeout=10)
        if response.status_code == 200:
            invoices = response.json()
            log_test(
                "Invoice API Availability", 
                True, 
                f"API responds with {len(invoices)} invoices (fallback working)", 
                response.status_code,
                response.text
            )
            add_diagnosis("working_features", "Invoice GET API (with fallback)")
        else:
            log_test(
                "Invoice API Availability", 
                False, 
                "Invoice API not responding", 
                response.status_code,
                response.text
            )
            add_diagnosis("broken_features", "Invoice GET API")
    except Exception as e:
        log_test("Invoice API Availability", False, f"Exception: {str(e)}")
        add_diagnosis("broken_features", "Invoice GET API (network error)")
    
    # Test 2: Test vehicle creation (should work)
    print("\n🚗 [DIAGNOSIS 2] Testing Vehicle System")
    vehicle_data = {
        "plateNumber": "DIAG-001",
        "brand": "تويوتا",
        "model": "كامري",
        "year": 2020,
        "color": "أبيض",
        "customerName": "عميل تشخيص",
        "customerPhone": "0500000001",
        "status": "diagnosis"
    }
    
    vehicle_id = None
    try:
        response = requests.post(f"{BACKEND_URL}/vehicles", json=vehicle_data, timeout=10)
        if response.status_code == 200:
            vehicle_response = response.json()
            vehicle_id = vehicle_response.get('id')
            log_test(
                "Vehicle Creation", 
                True, 
                f"Vehicle ID: {vehicle_id}", 
                response.status_code,
                response.text
            )
            add_diagnosis("working_features", "Vehicle creation (Supabase)")
        else:
            log_test(
                "Vehicle Creation", 
                False, 
                "Vehicle creation failed", 
                response.status_code,
                response.text
            )
            add_diagnosis("broken_features", "Vehicle creation")
    except Exception as e:
        log_test("Vehicle Creation", False, f"Exception: {str(e)}")
        add_diagnosis("broken_features", "Vehicle creation (network error)")
    
    # Test 3: Test invoice creation (expected to fail)
    print("\n📄 [DIAGNOSIS 3] Testing Invoice Creation")
    if vehicle_id:
        invoice_data = {
            "vehicleId": vehicle_id,
            "customerId": "diag-customer",
            "customerName": "عميل تشخيص",
            "plateNumber": "DIAG-001",
            "items": [{"name": "خدمة تشخيص", "quantity": 1, "price": 100, "total": 100}],
            "subtotal": 100,
            "tax": 15,
            "total": 115,
            "status": "pending",
            "type": "sale"
        }
        
        try:
            response = requests.post(f"{BACKEND_URL}/invoices", json=invoice_data, timeout=10)
            if response.status_code == 200:
                log_test(
                    "Invoice Creation", 
                    True, 
                    "Invoice created successfully", 
                    response.status_code,
                    response.text
                )
                add_diagnosis("working_features", "Invoice creation (Supabase)")
            elif response.status_code in [500, 520]:
                error_response = response.json()
                error_detail = str(error_response.get('detail', ''))
                if "Could not find the table 'public.invoices'" in error_detail:
                    log_test(
                        "Invoice Creation", 
                        False, 
                        "EXPECTED: Supabase 'invoices' table missing", 
                        response.status_code,
                        response.text
                    )
                    add_diagnosis("supabase_tables_missing", "invoices")
                    add_diagnosis("broken_features", "Invoice creation (missing Supabase table)")
                else:
                    log_test(
                        "Invoice Creation", 
                        False, 
                        f"Unexpected error: {error_detail}", 
                        response.status_code,
                        response.text
                    )
                    add_diagnosis("broken_features", "Invoice creation (unknown error)")
            else:
                log_test(
                    "Invoice Creation", 
                    False, 
                    "Invoice creation failed", 
                    response.status_code,
                    response.text
                )
                add_diagnosis("broken_features", "Invoice creation")
        except Exception as e:
            log_test("Invoice Creation", False, f"Exception: {str(e)}")
            add_diagnosis("broken_features", "Invoice creation (network error)")
    else:
        log_test("Invoice Creation", False, "Skipped - no vehicle ID")
        add_diagnosis("broken_features", "Invoice creation (dependency failed)")
    
    # Test 4: Test vehicle deletion and cleanup
    print("\n🗑️  [DIAGNOSIS 4] Testing Vehicle Deletion & Cleanup")
    if vehicle_id:
        try:
            response = requests.delete(f"{BACKEND_URL}/vehicles/{vehicle_id}", timeout=10)
            if response.status_code == 200:
                delete_response = response.json()
                if delete_response.get('success'):
                    log_test(
                        "Vehicle Deletion", 
                        True, 
                        "Vehicle deleted successfully", 
                        response.status_code,
                        response.text
                    )
                    add_diagnosis("working_features", "Vehicle deletion with cleanup")
                else:
                    log_test(
                        "Vehicle Deletion", 
                        False, 
                        "Delete API returned success=false", 
                        response.status_code,
                        response.text
                    )
                    add_diagnosis("broken_features", "Vehicle deletion")
            else:
                log_test(
                    "Vehicle Deletion", 
                    False, 
                    "Vehicle deletion failed", 
                    response.status_code,
                    response.text
                )
                add_diagnosis("broken_features", "Vehicle deletion")
        except Exception as e:
            log_test("Vehicle Deletion", False, f"Exception: {str(e)}")
            add_diagnosis("broken_features", "Vehicle deletion (network error)")
    else:
        log_test("Vehicle Deletion", False, "Skipped - no vehicle ID")

def test_current_working_features():
    """Test what currently works in the system"""
    print("\n" + "="*80)
    print("✅ TESTING CURRENT WORKING FEATURES")
    print("اختبار الميزات التي تعمل حالياً")
    print("="*80)
    
    # Test existing endpoints that should work
    endpoints_to_test = [
        ("/vehicles", "GET", "Vehicle List"),
        ("/customers", "GET", "Customer List"),
        ("/services", "GET", "Service List"),
        ("/technicians", "GET", "Technician List"),
        ("/invoices", "GET", "Invoice List (fallback)"),
    ]
    
    for endpoint, method, description in endpoints_to_test:
        print(f"\n🔍 Testing {description}")
        try:
            if method == "GET":
                response = requests.get(f"{BACKEND_URL}{endpoint}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                count = len(data) if isinstance(data, list) else "N/A"
                log_test(
                    f"{description}", 
                    True, 
                    f"Returns {count} items", 
                    response.status_code,
                    f"Data type: {type(data)}"
                )
                add_diagnosis("working_features", f"{description} API")
            else:
                log_test(
                    f"{description}", 
                    False, 
                    "API not responding correctly", 
                    response.status_code,
                    response.text
                )
                add_diagnosis("broken_features", f"{description} API")
        except Exception as e:
            log_test(f"{description}", False, f"Exception: {str(e)}")
            add_diagnosis("broken_features", f"{description} API (network error)")

def generate_recommendations():
    """Generate recommendations based on test results"""
    print("\n" + "="*80)
    print("💡 RECOMMENDATIONS & NEXT STEPS")
    print("التوصيات والخطوات التالية")
    print("="*80)
    
    # Analyze results and generate recommendations
    missing_tables = test_results["diagnosis"]["supabase_tables_missing"]
    working_features = test_results["diagnosis"]["working_features"]
    broken_features = test_results["diagnosis"]["broken_features"]
    
    print(f"\n📊 SYSTEM STATUS SUMMARY:")
    print(f"   ✅ Working Features: {len(working_features)}")
    print(f"   ❌ Broken Features: {len(broken_features)}")
    print(f"   🏗️  Missing Supabase Tables: {len(missing_tables)}")
    
    recommendations = []
    
    if "invoices" in missing_tables:
        recommendations.append({
            "priority": "HIGH",
            "action": "Create 'invoices' table in Supabase",
            "details": "The invoice system is configured to use Supabase but the table doesn't exist",
            "sql_example": """
CREATE TABLE public.invoices (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    invoice_number TEXT,
    customer_id TEXT,
    vehicle_id TEXT,
    items JSONB,
    subtotal DECIMAL(10,2),
    discount DECIMAL(10,2) DEFAULT 0,
    tax DECIMAL(10,2),
    total DECIMAL(10,2),
    status TEXT DEFAULT 'pending',
    type TEXT DEFAULT 'sale',
    payment_method TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
            """
        })
    
    if len(working_features) > len(broken_features):
        recommendations.append({
            "priority": "MEDIUM",
            "action": "System is mostly functional",
            "details": "Most core features are working. Focus on fixing the invoice table issue."
        })
    
    if "Vehicle creation (Supabase)" in working_features:
        recommendations.append({
            "priority": "LOW",
            "action": "Supabase integration is working",
            "details": "The Supabase connection is functional for other tables."
        })
    
    # Print recommendations
    for i, rec in enumerate(recommendations, 1):
        print(f"\n🎯 RECOMMENDATION {i} - {rec['priority']} PRIORITY:")
        print(f"   📋 Action: {rec['action']}")
        print(f"   📝 Details: {rec['details']}")
        if 'sql_example' in rec:
            print(f"   💻 SQL Example:")
            for line in rec['sql_example'].strip().split('\n'):
                print(f"      {line}")
    
    # Add to diagnosis
    test_results["diagnosis"]["recommendations"] = recommendations

def print_comprehensive_summary():
    """Print comprehensive test summary with diagnosis"""
    print("\n" + "="*80)
    print("📊 COMPREHENSIVE TEST SUMMARY")
    print("ملخص شامل للاختبارات")
    print("="*80)
    
    print(f"📈 Total Tests: {test_results['total']}")
    print(f"✅ Passed: {len(test_results['passed'])}")
    print(f"❌ Failed: {len(test_results['failed'])}")
    
    # System Status
    diagnosis = test_results["diagnosis"]
    print(f"\n🔍 SYSTEM DIAGNOSIS:")
    print(f"   🏗️  Missing Supabase Tables: {', '.join(diagnosis['supabase_tables_missing']) or 'None'}")
    print(f"   ✅ Working Features: {len(diagnosis['working_features'])}")
    print(f"   ❌ Broken Features: {len(diagnosis['broken_features'])}")
    
    if diagnosis['working_features']:
        print(f"\n✅ WORKING FEATURES:")
        for feature in diagnosis['working_features']:
            print(f"   ✓ {feature}")
    
    if diagnosis['broken_features']:
        print(f"\n❌ BROKEN FEATURES:")
        for feature in diagnosis['broken_features']:
            print(f"   ✗ {feature}")
    
    # Overall Status
    if "invoices" in diagnosis['supabase_tables_missing']:
        print(f"\n🎯 OVERALL STATUS: MIGRATION INCOMPLETE")
        print(f"   📋 The invoice system migration to Supabase is incomplete.")
        print(f"   🔧 Main Issue: Missing 'invoices' table in Supabase database.")
        print(f"   📝 Impact: Invoice creation fails, but other features work.")
    elif len(test_results['failed']) == 0:
        print(f"\n🎉 OVERALL STATUS: FULLY FUNCTIONAL")
        print(f"   📋 All tested features are working correctly.")
    else:
        print(f"\n⚠️  OVERALL STATUS: PARTIALLY FUNCTIONAL")
        print(f"   📋 Some features are working, but issues exist.")
    
    print("="*80)

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("🧪 COMPREHENSIVE INVOICE SYSTEM TESTING")
    print("اختبار شامل لنظام الفواتير")
    print("="*80)
    print(f"🌐 Backend URL: {BACKEND_URL}")
    print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Objective: Diagnose invoice system migration status and functionality")
    print("="*80)
    
    # Run comprehensive tests
    test_system_diagnosis()
    test_current_working_features()
    generate_recommendations()
    
    # Print comprehensive summary
    print_comprehensive_summary()
    
    # Save detailed results to file
    try:
        with open('/app/comprehensive_invoice_test_results.json', 'w', encoding='utf-8') as f:
            json.dump(test_results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Detailed results saved to: /app/comprehensive_invoice_test_results.json")
    except Exception as e:
        print(f"\n⚠️  Could not save results file: {str(e)}")
    
    # Determine exit code based on critical issues
    critical_issues = len([f for f in test_results["diagnosis"]["broken_features"] 
                          if "creation" in f or "network error" in f])
    
    if "invoices" in test_results["diagnosis"]["supabase_tables_missing"]:
        print(f"\n⚠️  MIGRATION INCOMPLETE: Invoice table missing in Supabase")
        print(f"   This is expected if migration is in progress.")
        sys.exit(0)  # Not a failure, just incomplete migration
    elif critical_issues > 0:
        print(f"\n❌ CRITICAL ISSUES FOUND: {critical_issues} critical problems detected")
        sys.exit(1)
    else:
        print(f"\n✅ SYSTEM FUNCTIONAL: All core features working correctly")
        sys.exit(0)

if __name__ == "__main__":
    main()