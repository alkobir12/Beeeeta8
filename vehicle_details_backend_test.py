#!/usr/bin/env python3
"""
Backend API Testing for VehicleDetails Page Functionality
Testing Arabic review request requirements
"""

import requests
import json
import os
import tempfile
from pathlib import Path

# Get backend URL from frontend .env
BACKEND_URL = "https://finance-overhaul-7.preview.emergentagent.com/api"

def test_get_vehicles():
    """Get available vehicles to use for testing"""
    print("🔍 Testing GET /api/vehicles...")
    try:
        response = requests.get(f"{BACKEND_URL}/vehicles")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            vehicles = response.json()
            print(f"✅ Found {len(vehicles)} vehicles")
            if vehicles:
                vehicle = vehicles[0]
                print(f"First vehicle ID: {vehicle.get('id')}")
                print(f"Plate: {vehicle.get('plateNumber')}")
                print(f"Customer: {vehicle.get('customerName')}")
                return vehicle.get('id')
            else:
                print("❌ No vehicles found - cannot proceed with tests")
                return None
        else:
            print(f"❌ Failed to get vehicles: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error getting vehicles: {e}")
        return None

def test_add_simple_services(vehicle_id):
    """Test 1: إضافة خدمة نصية بسيطة"""
    print(f"\n🔧 Test 1: Adding simple text services to vehicle {vehicle_id}...")
    
    try:
        # Test data as specified in Arabic review
        test_data = {
            "services": ["خدمة تجريبية 1", "خدمة تجريبية 2"]
        }
        
        response = requests.put(f"{BACKEND_URL}/vehicles/{vehicle_id}", json=test_data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            # Check for _id leakage
            if '_id' in str(result):
                print("❌ WARNING: _id found in response - potential MongoDB leakage")
            else:
                print("✅ No _id leakage detected")
            
            # Verify services were saved
            if 'services' in result and result['services'] == test_data['services']:
                print("✅ Services saved correctly in Supabase")
                return True
            else:
                print("❌ Services not saved correctly")
                return False
        else:
            print(f"❌ Failed to add services: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error adding services: {e}")
        return False

def test_add_parts_items(vehicle_id):
    """Test 2: إضافة بند (خدمة أو قطعة)"""
    print(f"\n🔧 Test 2: Adding parts/items to vehicle {vehicle_id}...")
    
    try:
        # Test data as specified in Arabic review - jsonb format
        test_data = {
            "parts": [
                {
                    "id": "test1",
                    "itemType": "service", 
                    "name": "تغيير زيت",
                    "quantity": 1,
                    "price": 0
                }
            ]
        }
        
        response = requests.put(f"{BACKEND_URL}/vehicles/{vehicle_id}", json=test_data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            # Check for _id leakage
            if '_id' in str(result):
                print("❌ WARNING: _id found in response - potential MongoDB leakage")
            else:
                print("✅ No _id leakage detected")
            
            # Verify parts were saved as jsonb
            if 'parts' in result and len(result['parts']) > 0:
                saved_part = result['parts'][0]
                if (saved_part.get('name') == 'تغيير زيت' and 
                    saved_part.get('itemType') == 'service'):
                    print("✅ Parts saved correctly as jsonb in Supabase")
                    return True
                else:
                    print("❌ Parts not saved correctly")
                    return False
            else:
                print("❌ Parts not found in response")
                return False
        else:
            print(f"❌ Failed to add parts: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error adding parts: {e}")
        return False

def test_delete_items(vehicle_id):
    """Test 3: حذف بند"""
    print(f"\n🗑️ Test 3: Deleting items from vehicle {vehicle_id}...")
    
    try:
        # Test with empty parts array to delete items
        test_data = {
            "parts": []
        }
        
        response = requests.put(f"{BACKEND_URL}/vehicles/{vehicle_id}", json=test_data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            # Check for _id leakage
            if '_id' in str(result):
                print("❌ WARNING: _id found in response - potential MongoDB leakage")
            else:
                print("✅ No _id leakage detected")
            
            # Verify parts were deleted
            if 'parts' in result and len(result['parts']) == 0:
                print("✅ Items deleted successfully")
                return True
            else:
                print("❌ Items not deleted properly")
                return False
        else:
            print(f"❌ Failed to delete items: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error deleting items: {e}")
        return False

def test_upload_file(vehicle_id):
    """Test 4: رفع ملف مرفق"""
    print(f"\n📎 Test 4: Uploading file to vehicle {vehicle_id}...")
    
    try:
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test invoice file content\nملف فاتورة تجريبي")
            temp_file_path = f.name
        
        # Upload file with file_type=invoice as specified
        with open(temp_file_path, 'rb') as f:
            files = {'file': ('test_invoice.txt', f, 'text/plain')}
            params = {'file_type': 'invoice'}
            
            response = requests.post(
                f"{BACKEND_URL}/vehicles/{vehicle_id}/upload-file",
                files=files,
                params=params
            )
        
        # Clean up temp file
        os.unlink(temp_file_path)
        
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            # Check for _id leakage
            if '_id' in str(result):
                print("❌ WARNING: _id found in response - potential MongoDB leakage")
            else:
                print("✅ No _id leakage detected")
            
            # Verify file upload response
            if ('filename' in result and 'fileType' in result and 
                result.get('fileType') == 'invoice'):
                print("✅ File uploaded successfully")
                return True, result.get('id')
            else:
                print("❌ File upload response incomplete")
                return False, None
        else:
            print(f"❌ Failed to upload file: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ Error uploading file: {e}")
        return False, None

def test_get_files(vehicle_id):
    """Test 5: قراءة الملفات المرفقة"""
    print(f"\n📋 Test 5: Getting uploaded files for vehicle {vehicle_id}...")
    
    try:
        response = requests.get(f"{BACKEND_URL}/vehicles/{vehicle_id}/files")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            # Check for _id leakage
            if '_id' in str(result):
                print("❌ WARNING: _id found in response - potential MongoDB leakage")
            else:
                print("✅ No _id leakage detected")
            
            # Verify files list structure
            if 'files' in result and 'count' in result:
                files_count = result.get('count', 0)
                files_list = result.get('files', [])
                print(f"✅ Files retrieved successfully - Count: {files_count}")
                
                # Check file structure
                if files_list:
                    first_file = files_list[0]
                    required_fields = ['id', 'vehicleId', 'filename', 'fileType', 'uploadedAt']
                    missing_fields = [field for field in required_fields if field not in first_file]
                    
                    if not missing_fields:
                        print("✅ File structure is complete")
                        return True
                    else:
                        print(f"❌ Missing fields in file structure: {missing_fields}")
                        return False
                else:
                    print("✅ No files found (empty list is valid)")
                    return True
            else:
                print("❌ Invalid files response structure")
                return False
        else:
            print(f"❌ Failed to get files: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error getting files: {e}")
        return False

def run_comprehensive_vehicle_details_test():
    """Run all VehicleDetails backend tests as requested in Arabic review"""
    print("🚀 Starting VehicleDetails Backend API Testing")
    print("=" * 60)
    
    # Get first available vehicle
    vehicle_id = test_get_vehicles()
    if not vehicle_id:
        print("❌ Cannot proceed - no vehicles available for testing")
        return
    
    print(f"\n🎯 Using vehicle ID: {vehicle_id}")
    print("=" * 60)
    
    # Track test results
    results = []
    
    # Test 1: Add simple services
    results.append(("Add Simple Services", test_add_simple_services(vehicle_id)))
    
    # Test 2: Add parts/items
    results.append(("Add Parts/Items", test_add_parts_items(vehicle_id)))
    
    # Test 3: Delete items
    results.append(("Delete Items", test_delete_items(vehicle_id)))
    
    # Test 4: Upload file
    upload_success, file_id = test_upload_file(vehicle_id)
    results.append(("Upload File", upload_success))
    
    # Test 5: Get files
    results.append(("Get Files", test_get_files(vehicle_id)))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nOverall Result: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All VehicleDetails backend tests PASSED!")
    else:
        print("⚠️ Some tests failed - check individual results above")

if __name__ == "__main__":
    run_comprehensive_vehicle_details_test()