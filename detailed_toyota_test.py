#!/usr/bin/env python3
"""
Detailed Toyota Manual Content Testing
Verifying the content/by-file endpoint returns full document with title, content, images, procedures
"""

import requests
import json

BACKEND_URL = "https://finance-overhaul-7.preview.emergentagent.com/api"

def test_content_by_file_detailed():
    """Test the content/by-file endpoint in detail"""
    print("🔍 Detailed Toyota Manual Content/By-File Testing")
    print("=" * 60)
    
    # Test files to check
    test_files = [
        "repair2/html/contents/local_rm000003a7j001x.html",
        # Let's get a few more files from the content endpoint
    ]
    
    # First, get some actual files from the content endpoint
    print("Getting sample files from /toyota-manual/content...")
    try:
        response = requests.get(f"{BACKEND_URL}/toyota-manual/content", params={"limit": 5}, timeout=30)
        if response.status_code == 200:
            content_data = response.json()
            if "content" in content_data and isinstance(content_data["content"], list):
                for doc in content_data["content"][:3]:
                    if isinstance(doc, dict) and "file" in doc:
                        test_files.append(doc["file"])
            print(f"Found {len(test_files)} files to test in detail")
        else:
            print(f"Failed to get content list: HTTP {response.status_code}")
    except Exception as e:
        print(f"Error getting content list: {e}")
    
    # Remove duplicates
    test_files = list(dict.fromkeys(test_files))
    
    print()
    
    for i, file_path in enumerate(test_files[:3], 1):  # Test up to 3 files
        print(f"📄 Test {i}: Testing file '{file_path}'")
        print("-" * 50)
        
        try:
            response = requests.get(
                f"{BACKEND_URL}/toyota-manual/content/by-file",
                params={"file": file_path},
                timeout=30
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"Response Type: {type(data).__name__}")
                    
                    if isinstance(data, dict):
                        print("Response Structure:")
                        for key, value in data.items():
                            if isinstance(value, str):
                                print(f"  • {key}: {type(value).__name__} ({len(value)} chars)")
                                if len(value) > 100:
                                    print(f"    Preview: {value[:100]}...")
                                else:
                                    print(f"    Content: {value}")
                            elif isinstance(value, list):
                                print(f"  • {key}: {type(value).__name__} ({len(value)} items)")
                                if value and len(value) > 0:
                                    print(f"    First item type: {type(value[0]).__name__}")
                            elif isinstance(value, dict):
                                print(f"  • {key}: {type(value).__name__} ({len(value)} keys)")
                                print(f"    Keys: {list(value.keys())}")
                            else:
                                print(f"  • {key}: {type(value).__name__} = {value}")
                        
                        # Check for expected fields
                        expected_fields = ["title", "content", "images", "procedures"]
                        found_fields = []
                        missing_fields = []
                        
                        for field in expected_fields:
                            if field in data:
                                found_fields.append(field)
                            else:
                                missing_fields.append(field)
                        
                        print(f"\nField Analysis:")
                        if found_fields:
                            print(f"  ✅ Found: {', '.join(found_fields)}")
                        if missing_fields:
                            print(f"  ❌ Missing: {', '.join(missing_fields)}")
                        
                        # Check if it's a nested structure
                        if "doc" in data and isinstance(data["doc"], dict):
                            print(f"\nNested 'doc' structure found:")
                            doc_data = data["doc"]
                            for key, value in doc_data.items():
                                if isinstance(value, str):
                                    print(f"  • doc.{key}: {type(value).__name__} ({len(value)} chars)")
                                elif isinstance(value, list):
                                    print(f"  • doc.{key}: {type(value).__name__} ({len(value)} items)")
                                else:
                                    print(f"  • doc.{key}: {type(value).__name__}")
                            
                            # Check expected fields in nested doc
                            doc_found = []
                            doc_missing = []
                            for field in expected_fields:
                                if field in doc_data:
                                    doc_found.append(field)
                                else:
                                    doc_missing.append(field)
                            
                            if doc_found:
                                print(f"  ✅ Doc has: {', '.join(doc_found)}")
                            if doc_missing:
                                print(f"  ❌ Doc missing: {', '.join(doc_missing)}")
                        
                        print(f"✅ SUCCESS: File content retrieved successfully")
                        
                    else:
                        print(f"❌ Unexpected response type: {type(data)}")
                        print(f"Response: {str(data)[:200]}...")
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    print(f"Response text: {response.text[:200]}...")
                    
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text[:200]}...")
                
        except requests.exceptions.Timeout:
            print("❌ Request timeout")
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {e}")
        
        print()

if __name__ == "__main__":
    test_content_by_file_detailed()