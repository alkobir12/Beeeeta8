#!/usr/bin/env python3
"""
Approvals Flow End-to-End Testing
Tests the complete approvals workflow including vehicle creation, approval listing, 
customer response, and verification of missing endpoints.
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from environment
BACKEND_URL = "https://ar-ledger-ssot.preview.emergentagent.com/api"

def log_test(test_name, status, details=""):
    """Log test results"""
    symbol = "✅" if status == "PASS" else "❌"
    print(f"\n{symbol} {test_name}")
    if details:
        print(f"   {details}")

def test_approvals_flow():
    """Test the complete approvals flow end-to-end"""
    print("\n" + "="*80)
    print("APPROVALS FLOW END-TO-END TESTING")
    print("="*80)
    
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "issues": []
    }
    
    # ============================================================================
    # TEST 1: Create a vehicle and verify auto-generated approval
    # ============================================================================
    results["total"] += 1
    print("\n[TEST 1] Create vehicle and verify auto-approval creation")
    
    try:
        vehicle_data = {
            "customerName": "أحمد محمد الراشد",
            "customerPhone": "+966501234567",
            "customerEmail": "ahmed@example.com",
            "plateNumber": f"ABC-{int(time.time()) % 10000}",
            "brand": "تويوتا",
            "model": "كامري",
            "year": 2022,
            "color": "أبيض",
            "services": ["فحص شامل", "تغيير زيت"],
            "notes": "فحص دوري"
        }
        
        response = requests.post(f"{BACKEND_URL}/vehicles", json=vehicle_data, timeout=10)
        
        if response.status_code == 200:
            vehicle = response.json()
            vehicle_id = vehicle.get("id")
            customer_id = vehicle.get("customerId")
            plate_number = vehicle.get("plateNumber")
            
            log_test("TEST 1.1: Vehicle creation", "PASS", 
                    f"Vehicle created with ID: {vehicle_id}, Plate: {plate_number}")
            
            # Wait a moment for auto-approval to be created
            time.sleep(1)
            
            # Now check if approval was auto-created
            approval_response = requests.get(
                f"{BACKEND_URL}/approvals?vehicle_id={vehicle_id}", 
                timeout=10
            )
            
            if approval_response.status_code == 200:
                approvals = approval_response.json()
                
                if len(approvals) > 0:
                    approval = approvals[0]
                    token = approval.get("token", "")
                    status = approval.get("status", "")
                    expires_at = approval.get("expiresAt", "")
                    
                    if token.startswith("APR-") and status == "pending":
                        log_test("TEST 1.2: Auto-approval creation", "PASS",
                                f"Approval created with token: {token}, status: {status}, expires: {expires_at}")
                        results["passed"] += 1
                        
                        # Store for next tests
                        test_data = {
                            "vehicle_id": vehicle_id,
                            "customer_id": customer_id,
                            "approval_token": token,
                            "approval_id": approval.get("id")
                        }
                    else:
                        log_test("TEST 1.2: Auto-approval creation", "FAIL",
                                f"Approval token format or status incorrect. Token: {token}, Status: {status}")
                        results["failed"] += 1
                        results["issues"].append("Auto-approval token format or status incorrect")
                        return results
                else:
                    log_test("TEST 1.2: Auto-approval creation", "FAIL",
                            "No approval was auto-created for the vehicle")
                    results["failed"] += 1
                    results["issues"].append("No auto-approval created on vehicle creation")
                    return results
            else:
                log_test("TEST 1.2: Auto-approval creation", "FAIL",
                        f"Failed to list approvals: {approval_response.status_code}")
                results["failed"] += 1
                results["issues"].append(f"Failed to list approvals: {approval_response.status_code}")
                return results
        else:
            log_test("TEST 1.1: Vehicle creation", "FAIL",
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
            results["failed"] += 1
            results["issues"].append(f"Vehicle creation failed: {response.status_code}")
            return results
            
    except Exception as e:
        log_test("TEST 1: Vehicle creation and auto-approval", "FAIL", f"Exception: {str(e)}")
        results["failed"] += 1
        results["issues"].append(f"Exception in TEST 1: {str(e)}")
        return results
    
    # ============================================================================
    # TEST 2: List approvals filtered by vehicle_id
    # ============================================================================
    results["total"] += 1
    print("\n[TEST 2] List approvals filtered by vehicle_id")
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/approvals?vehicle_id={test_data['vehicle_id']}", 
            timeout=10
        )
        
        if response.status_code == 200:
            approvals = response.json()
            
            if len(approvals) > 0:
                approval = approvals[0]
                
                # Verify required fields
                has_token = "token" in approval and approval["token"].startswith("APR-")
                has_status = approval.get("status") == "pending"
                has_vehicle_id = approval.get("vehicleId") == test_data["vehicle_id"]
                has_expires = "expiresAt" in approval
                
                if has_token and has_status and has_vehicle_id and has_expires:
                    log_test("TEST 2: List approvals by vehicle_id", "PASS",
                            f"Found {len(approvals)} approval(s) with correct fields")
                    results["passed"] += 1
                else:
                    missing = []
                    if not has_token: missing.append("valid token")
                    if not has_status: missing.append("pending status")
                    if not has_vehicle_id: missing.append("matching vehicle_id")
                    if not has_expires: missing.append("expiresAt")
                    
                    log_test("TEST 2: List approvals by vehicle_id", "FAIL",
                            f"Missing or incorrect fields: {', '.join(missing)}")
                    results["failed"] += 1
                    results["issues"].append(f"Approval missing fields: {', '.join(missing)}")
            else:
                log_test("TEST 2: List approvals by vehicle_id", "FAIL",
                        "No approvals found for vehicle_id")
                results["failed"] += 1
                results["issues"].append("No approvals found when filtering by vehicle_id")
        else:
            log_test("TEST 2: List approvals by vehicle_id", "FAIL",
                    f"Status: {response.status_code}")
            results["failed"] += 1
            results["issues"].append(f"List approvals failed: {response.status_code}")
            
    except Exception as e:
        log_test("TEST 2: List approvals by vehicle_id", "FAIL", f"Exception: {str(e)}")
        results["failed"] += 1
        results["issues"].append(f"Exception in TEST 2: {str(e)}")
    
    # ============================================================================
    # TEST 3: Simulate customer approval response
    # ============================================================================
    results["total"] += 1
    print("\n[TEST 3] Simulate customer approval response")
    
    try:
        # First, verify we can access the public approval link
        public_response = requests.get(
            f"{BACKEND_URL}/approvals/public/{test_data['approval_token']}", 
            timeout=10
        )
        
        if public_response.status_code == 200:
            log_test("TEST 3.1: Public approval access", "PASS",
                    f"Public approval accessible via token")
            
            # Now respond to the approval
            respond_data = {
                "status": "approved",
                "name": "أحمد محمد الراشد",
                "phone": "+966501234567"
            }
            
            respond_response = requests.post(
                f"{BACKEND_URL}/approvals/public/{test_data['approval_token']}/respond",
                params=respond_data,
                timeout=10
            )
            
            if respond_response.status_code == 200:
                updated_approval = respond_response.json()
                
                # Verify response fields
                has_responded_at = "respondedAt" in updated_approval and updated_approval["respondedAt"]
                status_updated = updated_approval.get("status") == "approved"
                has_responder_name = updated_approval.get("responderName") == "أحمد محمد الراشد"
                has_responder_phone = updated_approval.get("responderPhone") == "+966501234567"
                
                if has_responded_at and status_updated and has_responder_name and has_responder_phone:
                    log_test("TEST 3.2: Customer approval response", "PASS",
                            f"Approval updated: status={updated_approval.get('status')}, respondedAt={updated_approval.get('respondedAt')}")
                    results["passed"] += 1
                else:
                    missing = []
                    if not has_responded_at: missing.append("respondedAt")
                    if not status_updated: missing.append("status=approved")
                    if not has_responder_name: missing.append("responderName")
                    if not has_responder_phone: missing.append("responderPhone")
                    
                    log_test("TEST 3.2: Customer approval response", "FAIL",
                            f"Missing or incorrect fields: {', '.join(missing)}")
                    results["failed"] += 1
                    results["issues"].append(f"Approval response missing fields: {', '.join(missing)}")
            else:
                log_test("TEST 3.2: Customer approval response", "FAIL",
                        f"Status: {respond_response.status_code}, Response: {respond_response.text[:200]}")
                results["failed"] += 1
                results["issues"].append(f"Approval response failed: {respond_response.status_code}")
        else:
            log_test("TEST 3.1: Public approval access", "FAIL",
                    f"Status: {public_response.status_code}")
            results["failed"] += 1
            results["issues"].append(f"Public approval access failed: {public_response.status_code}")
            
    except Exception as e:
        log_test("TEST 3: Customer approval response", "FAIL", f"Exception: {str(e)}")
        results["failed"] += 1
        results["issues"].append(f"Exception in TEST 3: {str(e)}")
    
    # ============================================================================
    # TEST 4: Verify GET /api/approvals?vehicle_id shows updated status
    # ============================================================================
    results["total"] += 1
    print("\n[TEST 4] Verify approval status update is reflected")
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/approvals?vehicle_id={test_data['vehicle_id']}", 
            timeout=10
        )
        
        if response.status_code == 200:
            approvals = response.json()
            
            if len(approvals) > 0:
                approval = approvals[0]
                
                if approval.get("status") == "approved" and "respondedAt" in approval:
                    log_test("TEST 4: Approval status update verification", "PASS",
                            f"Status correctly updated to 'approved' with respondedAt: {approval.get('respondedAt')}")
                    results["passed"] += 1
                else:
                    log_test("TEST 4: Approval status update verification", "FAIL",
                            f"Status: {approval.get('status')}, respondedAt present: {'respondedAt' in approval}")
                    results["failed"] += 1
                    results["issues"].append("Approval status not updated after response")
            else:
                log_test("TEST 4: Approval status update verification", "FAIL",
                        "No approvals found")
                results["failed"] += 1
                results["issues"].append("No approvals found after response")
        else:
            log_test("TEST 4: Approval status update verification", "FAIL",
                    f"Status: {response.status_code}")
            results["failed"] += 1
            results["issues"].append(f"Failed to verify approval update: {response.status_code}")
            
    except Exception as e:
        log_test("TEST 4: Approval status update verification", "FAIL", f"Exception: {str(e)}")
        results["failed"] += 1
        results["issues"].append(f"Exception in TEST 4: {str(e)}")
    
    # ============================================================================
    # TEST 5: Check for GET /api/customers/{id}/approvals endpoint
    # ============================================================================
    results["total"] += 1
    print("\n[TEST 5] Check for GET /api/customers/{id}/approvals endpoint")
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/customers/{test_data['customer_id']}/approvals", 
            timeout=10
        )
        
        if response.status_code == 200:
            customer_approvals = response.json()
            log_test("TEST 5: Customer approvals endpoint", "PASS",
                    f"Endpoint exists and returned {len(customer_approvals) if isinstance(customer_approvals, list) else 'data'}")
            results["passed"] += 1
        elif response.status_code == 404:
            log_test("TEST 5: Customer approvals endpoint", "FAIL",
                    "❌ MISSING ENDPOINT: GET /api/customers/{id}/approvals does not exist")
            results["failed"] += 1
            results["issues"].append("MISSING ENDPOINT: GET /api/customers/{id}/approvals - This endpoint should be implemented to allow fetching all approvals for a specific customer")
        else:
            log_test("TEST 5: Customer approvals endpoint", "FAIL",
                    f"Unexpected status: {response.status_code}")
            results["failed"] += 1
            results["issues"].append(f"Customer approvals endpoint returned unexpected status: {response.status_code}")
            
    except Exception as e:
        log_test("TEST 5: Customer approvals endpoint", "FAIL", f"Exception: {str(e)}")
        results["failed"] += 1
        results["issues"].append(f"Exception in TEST 5: {str(e)}")
    
    # ============================================================================
    # SUMMARY
    # ============================================================================
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {results['total']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Pass Rate: {(results['passed']/results['total']*100):.1f}%")
    
    if results["issues"]:
        print("\n❌ ISSUES FOUND:")
        for i, issue in enumerate(results["issues"], 1):
            print(f"  {i}. {issue}")
    
    print("\n" + "="*80)
    
    return results

if __name__ == "__main__":
    results = test_approvals_flow()
    
    # Exit with appropriate code
    exit(0 if results["failed"] == 0 else 1)
