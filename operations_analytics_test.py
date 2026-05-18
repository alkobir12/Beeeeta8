#!/usr/bin/env python3
"""
Backend Integration Test for Operations and Analytics
Testing operations integration with analytics after modifications as requested in Arabic review.

Test Plan:
1. Use base URL from REACT_APP_BACKEND_URL
2. Call GET /api/transactions and ensure it returns an array (even if empty)
3. Call GET /api/stats and ensure thisMonth.income and thisMonth.expenses are calculated from transactions table (for current Supabase setup)
4. Call POST /api/operations with a 'sale' operation with specific data
5. After creating the operation:
   - Call GET /api/transactions again and ensure there's a new item with type='income' and amount=100
   - Call GET /api/stats again and ensure thisMonth.income increased by at least 100
6. Provide a brief report on whether new operations show up in /api/transactions and reflect in /api/stats
"""

import requests
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, List

# Get base URL from environment
def get_base_url():
    """Get the backend URL from frontend .env file"""
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"❌ Error reading frontend .env: {e}")
    
    # Fallback
    return "https://vehicle-accounting-2.preview.emergentagent.com"

BASE_URL = get_base_url()
API_BASE = f"{BASE_URL}/api"

print(f"🔗 Using base URL: {BASE_URL}")
print(f"🔗 API base: {API_BASE}")

class OperationsAnalyticsTest:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.test_results = []
        self.initial_stats = None
        self.initial_transactions = None
        self.operation_created = None
        
    def log_result(self, test_name: str, success: bool, message: str, details: Dict = None):
        """Log test result"""
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {test_name} - {message}")
        
        result = {
            'test': test_name,
            'success': success,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        if details:
            result['details'] = details
        self.test_results.append(result)
        
    def test_get_transactions_initial(self):
        """Test 1: GET /api/transactions - ensure it returns an array"""
        try:
            response = self.session.get(f"{API_BASE}/transactions")
            
            if response.status_code != 200:
                self.log_result(
                    "GET /api/transactions (initial)",
                    False,
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    {'status_code': response.status_code, 'response': response.text[:500]}
                )
                return False
                
            data = response.json()
            
            if not isinstance(data, list):
                self.log_result(
                    "GET /api/transactions (initial)",
                    False,
                    f"Expected array, got {type(data).__name__}",
                    {'response_type': type(data).__name__, 'data': str(data)[:200]}
                )
                return False
                
            self.initial_transactions = data
            self.log_result(
                "GET /api/transactions (initial)",
                True,
                f"Returns array with {len(data)} transactions",
                {'transaction_count': len(data), 'sample': data[:2] if data else []}
            )
            return True
            
        except Exception as e:
            self.log_result(
                "GET /api/transactions (initial)",
                False,
                f"Exception: {str(e)}",
                {'exception': str(e)}
            )
            return False
    
    def test_get_stats_initial(self):
        """Test 2: GET /api/stats - ensure thisMonth.income and expenses are calculated"""
        try:
            response = self.session.get(f"{API_BASE}/stats")
            
            if response.status_code != 200:
                self.log_result(
                    "GET /api/stats (initial)",
                    False,
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    {'status_code': response.status_code, 'response': response.text[:500]}
                )
                return False
                
            data = response.json()
            
            # Check structure
            if 'thisMonth' not in data:
                self.log_result(
                    "GET /api/stats (initial)",
                    False,
                    "Missing 'thisMonth' field in response",
                    {'response_structure': list(data.keys()) if isinstance(data, dict) else str(type(data))}
                )
                return False
                
            this_month = data['thisMonth']
            if 'income' not in this_month or 'expenses' not in this_month:
                self.log_result(
                    "GET /api/stats (initial)",
                    False,
                    "Missing 'income' or 'expenses' in thisMonth",
                    {'thisMonth_structure': list(this_month.keys()) if isinstance(this_month, dict) else str(type(this_month))}
                )
                return False
                
            self.initial_stats = data
            self.log_result(
                "GET /api/stats (initial)",
                True,
                f"thisMonth.income={this_month['income']}, thisMonth.expenses={this_month['expenses']}",
                {
                    'initial_income': this_month['income'],
                    'initial_expenses': this_month['expenses'],
                    'full_stats': data
                }
            )
            return True
            
        except Exception as e:
            self.log_result(
                "GET /api/stats (initial)",
                False,
                f"Exception: {str(e)}",
                {'exception': str(e)}
            )
            return False
    
    def test_create_sale_operation(self):
        """Test 3: POST /api/operations with sale operation"""
        try:
            operation_data = {
                "accountId": None,
                "type": "sale",
                "partnerType": "customer",
                "partnerName": "عميل اختبار تكامل",
                "items": [
                    {
                        "itemType": "service",
                        "itemId": None,
                        "name": "خدمة اختبار",
                        "quantity": 1,
                        "price": 100
                    }
                ],
                "paymentMethod": "cash",
                "notes": "test integration"
            }
            
            response = self.session.post(f"{API_BASE}/operations", json=operation_data)
            
            if response.status_code not in [200, 201]:
                self.log_result(
                    "POST /api/operations (sale)",
                    False,
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    {
                        'status_code': response.status_code,
                        'response': response.text[:500],
                        'request_data': operation_data
                    }
                )
                return False
                
            data = response.json()
            
            # Validate response structure
            if not isinstance(data, dict) or 'id' not in data:
                self.log_result(
                    "POST /api/operations (sale)",
                    False,
                    "Invalid response structure - missing 'id' field",
                    {'response': str(data)[:300]}
                )
                return False
                
            self.operation_created = data
            self.log_result(
                "POST /api/operations (sale)",
                True,
                f"Operation created with ID: {data.get('id')}, total: {data.get('total', 'N/A')}",
                {
                    'operation_id': data.get('id'),
                    'operation_type': data.get('type'),
                    'total': data.get('total'),
                    'partner_name': data.get('partnerName'),
                    'full_response': data
                }
            )
            return True
            
        except Exception as e:
            self.log_result(
                "POST /api/operations (sale)",
                False,
                f"Exception: {str(e)}",
                {'exception': str(e)}
            )
            return False
    
    def test_get_transactions_after_operation(self):
        """Test 4: GET /api/transactions after operation - check for new income transaction"""
        try:
            response = self.session.get(f"{API_BASE}/transactions")
            
            if response.status_code != 200:
                self.log_result(
                    "GET /api/transactions (after operation)",
                    False,
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    {'status_code': response.status_code}
                )
                return False
                
            data = response.json()
            
            if not isinstance(data, list):
                self.log_result(
                    "GET /api/transactions (after operation)",
                    False,
                    f"Expected array, got {type(data).__name__}",
                    {'response_type': type(data).__name__}
                )
                return False
                
            # Check if we have more transactions than initially
            initial_count = len(self.initial_transactions) if self.initial_transactions else 0
            current_count = len(data)
            
            if current_count <= initial_count:
                self.log_result(
                    "GET /api/transactions (after operation)",
                    False,
                    f"No new transactions found. Initial: {initial_count}, Current: {current_count}",
                    {
                        'initial_count': initial_count,
                        'current_count': current_count,
                        'transactions': data[:3]  # Show first 3 for debugging
                    }
                )
                return False
                
            # Look for income transaction with amount ~100
            income_transactions = [t for t in data if t.get('type') == 'income']
            new_income_100 = [t for t in income_transactions if abs(float(t.get('amount', 0)) - 100) < 0.01]
            
            if not new_income_100:
                self.log_result(
                    "GET /api/transactions (after operation)",
                    False,
                    f"No income transaction with amount=100 found. Income transactions: {len(income_transactions)}",
                    {
                        'total_transactions': current_count,
                        'income_transactions': len(income_transactions),
                        'income_amounts': [t.get('amount') for t in income_transactions],
                        'sample_transactions': data[:3]
                    }
                )
                return False
                
            self.log_result(
                "GET /api/transactions (after operation)",
                True,
                f"Found new income transaction with amount=100. Total transactions: {current_count} (was {initial_count})",
                {
                    'initial_count': initial_count,
                    'current_count': current_count,
                    'new_income_transaction': new_income_100[0],
                    'total_income_transactions': len(income_transactions)
                }
            )
            return True
            
        except Exception as e:
            self.log_result(
                "GET /api/transactions (after operation)",
                False,
                f"Exception: {str(e)}",
                {'exception': str(e)}
            )
            return False
    
    def test_get_stats_after_operation(self):
        """Test 5: GET /api/stats after operation - check if thisMonth.income increased"""
        try:
            response = self.session.get(f"{API_BASE}/stats")
            
            if response.status_code != 200:
                self.log_result(
                    "GET /api/stats (after operation)",
                    False,
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    {'status_code': response.status_code}
                )
                return False
                
            data = response.json()
            
            if 'thisMonth' not in data or 'income' not in data['thisMonth']:
                self.log_result(
                    "GET /api/stats (after operation)",
                    False,
                    "Missing thisMonth.income in response",
                    {'response_structure': list(data.keys()) if isinstance(data, dict) else str(type(data))}
                )
                return False
                
            current_income = float(data['thisMonth']['income'])
            initial_income = float(self.initial_stats['thisMonth']['income']) if self.initial_stats else 0
            income_increase = current_income - initial_income
            
            if income_increase < 100:
                self.log_result(
                    "GET /api/stats (after operation)",
                    False,
                    f"Income did not increase by at least 100. Initial: {initial_income}, Current: {current_income}, Increase: {income_increase}",
                    {
                        'initial_income': initial_income,
                        'current_income': current_income,
                        'income_increase': income_increase,
                        'expected_minimum_increase': 100
                    }
                )
                return False
                
            self.log_result(
                "GET /api/stats (after operation)",
                True,
                f"Income increased by {income_increase}. Initial: {initial_income}, Current: {current_income}",
                {
                    'initial_income': initial_income,
                    'current_income': current_income,
                    'income_increase': income_increase,
                    'current_stats': data
                }
            )
            return True
            
        except Exception as e:
            self.log_result(
                "GET /api/stats (after operation)",
                False,
                f"Exception: {str(e)}",
                {'exception': str(e)}
            )
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Operations & Analytics Integration Test")
        print("=" * 60)
        
        tests = [
            self.test_get_transactions_initial,
            self.test_get_stats_initial,
            self.test_create_sale_operation,
            self.test_get_transactions_after_operation,
            self.test_get_stats_after_operation
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                if test():
                    passed += 1
                print()  # Add spacing between tests
            except Exception as e:
                print(f"❌ CRITICAL ERROR in {test.__name__}: {e}")
                print()
        
        print("=" * 60)
        print(f"📊 TEST SUMMARY: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        # Generate detailed report
        self.generate_report()
        
        return passed == total
    
    def generate_report(self):
        """Generate detailed test report"""
        print("\n📋 DETAILED TEST REPORT")
        print("=" * 60)
        
        # Summary by test
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"{status} {result['test']}: {result['message']}")
        
        # Check for 4xx/5xx errors
        print("\n🔍 ERROR ANALYSIS:")
        errors_found = []
        for result in self.test_results:
            if not result['success'] and 'details' in result:
                details = result['details']
                if 'status_code' in details:
                    status_code = details['status_code']
                    if 400 <= status_code < 600:
                        errors_found.append(f"{result['test']}: HTTP {status_code}")
        
        if errors_found:
            print("❌ HTTP Errors found:")
            for error in errors_found:
                print(f"   - {error}")
        else:
            print("✅ No 4xx/5xx errors during POST /api/operations or analytics queries")
        
        # Integration status
        print("\n🔗 INTEGRATION STATUS:")
        
        # Check if operations show up in transactions
        transactions_test = next((r for r in self.test_results if 'after operation' in r['test'] and 'transactions' in r['test']), None)
        if transactions_test and transactions_test['success']:
            print("✅ New operations DO show up in /api/transactions")
        else:
            print("❌ New operations DO NOT show up in /api/transactions")
        
        # Check if operations reflect in stats
        stats_test = next((r for r in self.test_results if 'after operation' in r['test'] and 'stats' in r['test']), None)
        if stats_test and stats_test['success']:
            print("✅ New operations DO reflect in /api/stats analytics")
        else:
            print("❌ New operations DO NOT reflect in /api/stats analytics")
        
        print("\n" + "=" * 60)

def main():
    """Main test execution"""
    tester = OperationsAnalyticsTest()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 ALL TESTS PASSED - Operations and Analytics integration is working correctly!")
        sys.exit(0)
    else:
        print("💥 SOME TESTS FAILED - Operations and Analytics integration has issues")
        sys.exit(1)

if __name__ == "__main__":
    main()