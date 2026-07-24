#!/usr/bin/env python3
"""
Backend Testing Script for Liquid Builder Expansion
Testing AlKabeer Bot endpoints after latest expansion
"""

import requests
import json
import sys
from typing import Dict, Any, Optional

# Backend URL from frontend .env
BACKEND_URL = "https://stamp-approval-flow.preview.emergentagent.com/api"

class LiquidBuilderExpansionTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.results = []
        self.session_id = "test-session-expansion-123"
        
    def log_result(self, test_name: str, status: str, details: str = ""):
        """Log test result"""
        self.results.append({
            'test': test_name,
            'status': status,
            'details': details
        })
        print(f"{status}: {test_name}")
        if details:
            print(f"  Details: {details}")
    
    def test_get_customization_root_page(self) -> bool:
        """Test GET /api/alkabeer-bot/customization for root page /"""
        try:
            url = f"{BACKEND_URL}/alkabeer-bot/customization"
            params = {
                'user_id': 'manager',
                'path': '/'
            }
            
            response = self.session.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'data' in data:
                    self.log_result(
                        "GET /api/alkabeer-bot/customization (root page /)", 
                        "PASS", 
                        f"Status: {response.status_code}, Success: {data.get('success')}"
                    )
                    return True
                else:
                    self.log_result(
                        "GET /api/alkabeer-bot/customization (root page /)", 
                        "FAIL", 
                        f"Invalid response structure: {data}"
                    )
                    return False
            else:
                self.log_result(
                    "GET /api/alkabeer-bot/customization (root page /)", 
                    "FAIL", 
                    f"Status: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_result(
                "GET /api/alkabeer-bot/customization (root page /)", 
                "FAIL", 
                f"Exception: {str(e)}"
            )
            return False
    
    def test_get_customization_customers_page(self) -> bool:
        """Test GET /api/alkabeer-bot/customization for customers page /customers"""
        try:
            url = f"{BACKEND_URL}/alkabeer-bot/customization"
            params = {
                'user_id': 'manager',
                'path': '/customers'
            }
            
            response = self.session.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'data' in data:
                    self.log_result(
                        "GET /api/alkabeer-bot/customization (customers page /customers)", 
                        "PASS", 
                        f"Status: {response.status_code}, Success: {data.get('success')}"
                    )
                    return True
                else:
                    self.log_result(
                        "GET /api/alkabeer-bot/customization (customers page /customers)", 
                        "FAIL", 
                        f"Invalid response structure: {data}"
                    )
                    return False
            else:
                self.log_result(
                    "GET /api/alkabeer-bot/customization (customers page /customers)", 
                    "FAIL", 
                    f"Status: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_result(
                "GET /api/alkabeer-bot/customization (customers page /customers)", 
                "FAIL", 
                f"Exception: {str(e)}"
            )
            return False
    
    def test_put_customization_root_page(self) -> bool:
        """Test PUT /api/alkabeer-bot/customization for root page with specific settings"""
        try:
            url = f"{BACKEND_URL}/alkabeer-bot/customization"
            
            # Test data for root page
            test_data = {
                "user_id": "manager",
                "path": "/",
                "labels": {
                    "root-element": "تسمية الصفحة الرئيسية"
                },
                "hidden": {
                    "root-hidden-element": True
                },
                "contents": {
                    "root-content": "محتوى الصفحة الرئيسية"
                },
                "custom_cards": [
                    {
                        "id": "root-card-1",
                        "title": "كرت الصفحة الرئيسية",
                        "content": "محتوى كرت الصفحة الرئيسية"
                    }
                ]
            }
            
            response = self.session.put(url, json=test_data)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.log_result(
                        "PUT /api/alkabeer-bot/customization (root page /)", 
                        "PASS", 
                        f"Status: {response.status_code}, Data saved for root page"
                    )
                    return True
                else:
                    self.log_result(
                        "PUT /api/alkabeer-bot/customization (root page /)", 
                        "FAIL", 
                        f"Invalid response structure: {data}"
                    )
                    return False
            else:
                self.log_result(
                    "PUT /api/alkabeer-bot/customization (root page /)", 
                    "FAIL", 
                    f"Status: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_result(
                "PUT /api/alkabeer-bot/customization (root page /)", 
                "FAIL", 
                f"Exception: {str(e)}"
            )
            return False
    
    def test_put_customization_customers_page(self) -> bool:
        """Test PUT /api/alkabeer-bot/customization for customers page with different settings"""
        try:
            url = f"{BACKEND_URL}/alkabeer-bot/customization"
            
            # Test data for customers page (different from root)
            test_data = {
                "user_id": "manager",
                "path": "/customers",
                "labels": {
                    "customers-element": "تسمية صفحة العملاء"
                },
                "hidden": {
                    "customers-hidden-element": False
                },
                "contents": {
                    "customers-content": "محتوى صفحة العملاء"
                },
                "custom_cards": [
                    {
                        "id": "customers-card-1",
                        "title": "كرت صفحة العملاء",
                        "content": "محتوى كرت صفحة العملاء"
                    }
                ]
            }
            
            response = self.session.put(url, json=test_data)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.log_result(
                        "PUT /api/alkabeer-bot/customization (customers page /customers)", 
                        "PASS", 
                        f"Status: {response.status_code}, Data saved for customers page"
                    )
                    return True
                else:
                    self.log_result(
                        "PUT /api/alkabeer-bot/customization (customers page /customers)", 
                        "FAIL", 
                        f"Invalid response structure: {data}"
                    )
                    return False
            else:
                self.log_result(
                    "PUT /api/alkabeer-bot/customization (customers page /customers)", 
                    "FAIL", 
                    f"Status: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_result(
                "PUT /api/alkabeer-bot/customization (customers page /customers)", 
                "FAIL", 
                f"Exception: {str(e)}"
            )
            return False
    
    def test_verify_independent_settings(self) -> bool:
        """Test that each page maintains independent settings"""
        try:
            # Get root page settings
            url = f"{BACKEND_URL}/alkabeer-bot/customization"
            params_root = {
                'user_id': 'manager',
                'path': '/'
            }
            
            response_root = self.session.get(url, params=params_root)
            
            # Get customers page settings
            params_customers = {
                'user_id': 'manager',
                'path': '/customers'
            }
            
            response_customers = self.session.get(url, params=params_customers)
            
            if response_root.status_code == 200 and response_customers.status_code == 200:
                data_root = response_root.json()
                data_customers = response_customers.json()
                
                if (data_root.get('success') and data_customers.get('success') and
                    'data' in data_root and 'data' in data_customers):
                    
                    root_data = data_root['data']
                    customers_data = data_customers['data']
                    
                    # Check that settings are different and independent
                    root_label = root_data.get('labels', {}).get('root-element')
                    customers_label = customers_data.get('labels', {}).get('customers-element')
                    
                    root_hidden = root_data.get('hidden', {}).get('root-hidden-element')
                    customers_hidden = customers_data.get('hidden', {}).get('customers-hidden-element')
                    
                    if (root_label == "تسمية الصفحة الرئيسية" and 
                        customers_label == "تسمية صفحة العملاء" and
                        root_hidden == True and 
                        customers_hidden == False):
                        
                        self.log_result(
                            "Verify independent page settings", 
                            "PASS", 
                            "Each page maintains independent customization settings"
                        )
                        return True
                    else:
                        self.log_result(
                            "Verify independent page settings", 
                            "FAIL", 
                            f"Settings not independent. Root: {root_data}, Customers: {customers_data}"
                        )
                        return False
                else:
                    self.log_result(
                        "Verify independent page settings", 
                        "FAIL", 
                        f"Invalid response structure"
                    )
                    return False
            else:
                self.log_result(
                    "Verify independent page settings", 
                    "FAIL", 
                    f"Failed to get settings. Root: {response_root.status_code}, Customers: {response_customers.status_code}"
                )
                return False
                
        except Exception as e:
            self.log_result(
                "Verify independent page settings", 
                "FAIL", 
                f"Exception: {str(e)}"
            )
            return False
    
    def test_chat_rrr_manager(self) -> bool:
        """Test POST /api/alkabeer-bot/chat with message 'rrr' as manager"""
        try:
            url = f"{BACKEND_URL}/alkabeer-bot/chat"
            
            chat_data = {
                "message": "rrr",
                "sessionId": self.session_id,
                "role": "manager",
                "userId": "manager",
                "currentPath": "/ai-financial"
            }
            
            response = self.session.post(url, json=chat_data)
            
            if response.status_code == 200:
                data = response.json()
                if ('response' in data and 
                    'sessionId' in data and 
                    data.get('sessionId') == self.session_id):
                    
                    self.log_result(
                        "POST /api/alkabeer-bot/chat (rrr as manager)", 
                        "PASS", 
                        f"Chat response received with session {data.get('sessionId')}"
                    )
                    return True
                else:
                    self.log_result(
                        "POST /api/alkabeer-bot/chat (rrr as manager)", 
                        "FAIL", 
                        f"Unexpected response: {data}"
                    )
                    return False
            else:
                self.log_result(
                    "POST /api/alkabeer-bot/chat (rrr as manager)", 
                    "FAIL", 
                    f"Status: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_result(
                "POST /api/alkabeer-bot/chat (rrr as manager)", 
                "FAIL", 
                f"Exception: {str(e)}"
            )
            return False
    
    def test_chat_exit_same_session(self) -> bool:
        """Test POST /api/alkabeer-bot/chat with message 'EXIT' on same session"""
        try:
            url = f"{BACKEND_URL}/alkabeer-bot/chat"
            
            chat_data = {
                "message": "EXIT",
                "sessionId": self.session_id,  # Same session as rrr test
                "role": "manager",
                "userId": "manager",
                "currentPath": "/ai-financial"
            }
            
            response = self.session.post(url, json=chat_data)
            
            if response.status_code == 200:
                data = response.json()
                if ('response' in data and 
                    'sessionId' in data and 
                    data.get('sessionId') == self.session_id):
                    
                    self.log_result(
                        "POST /api/alkabeer-bot/chat (EXIT same session)", 
                        "PASS", 
                        f"Exit response received with session {data.get('sessionId')}"
                    )
                    return True
                else:
                    self.log_result(
                        "POST /api/alkabeer-bot/chat (EXIT same session)", 
                        "FAIL", 
                        f"Unexpected response: {data}"
                    )
                    return False
            else:
                self.log_result(
                    "POST /api/alkabeer-bot/chat (EXIT same session)", 
                    "FAIL", 
                    f"Status: {response.status_code}, Response: {response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.log_result(
                "POST /api/alkabeer-bot/chat (EXIT same session)", 
                "FAIL", 
                f"Exception: {str(e)}"
            )
            return False
    
    def run_all_tests(self):
        """Run all backend tests for Liquid Builder expansion"""
        print("=== Backend Testing: Liquid Builder Expansion ===")
        print(f"Backend URL: {BACKEND_URL}")
        print(f"Session ID: {self.session_id}")
        print()
        
        tests = [
            ("1. GET Customization (Root Page /)", self.test_get_customization_root_page),
            ("2. GET Customization (Customers Page /customers)", self.test_get_customization_customers_page),
            ("3. PUT Customization (Root Page /)", self.test_put_customization_root_page),
            ("4. PUT Customization (Customers Page /customers)", self.test_put_customization_customers_page),
            ("5. Verify Independent Page Settings", self.test_verify_independent_settings),
            ("6. Chat RRR (Manager)", self.test_chat_rrr_manager),
            ("7. Chat EXIT (Same Session)", self.test_chat_exit_same_session),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            print(f"\n--- {test_name} ---")
            if test_func():
                passed += 1
            else:
                failed += 1
        
        print(f"\n=== SUMMARY ===")
        print(f"PASSED: {passed}")
        print(f"FAILED: {failed}")
        print(f"TOTAL: {passed + failed}")
        
        if failed > 0:
            print("\nBROKEN ENDPOINTS:")
            for result in self.results:
                if result['status'] == 'FAIL':
                    print(f"- {result['test']}")
        else:
            print("\nNO BROKEN ENDPOINTS DETECTED")
        
        return failed == 0

def main():
    tester = LiquidBuilderExpansionTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()