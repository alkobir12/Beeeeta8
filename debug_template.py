#!/usr/bin/env python3
"""
Debug script to check what's stored in the invoice templates
"""

import requests
import json

BASE_URL = "https://workshop-helper-7.preview.emergentagent.com/api"

def debug_templates():
    print("🔍 Debugging Invoice Templates...")
    
    # Get list of templates
    response = requests.get(f"{BASE_URL}/invoice-templates")
    
    if response.status_code == 200:
        templates = response.json()
        print(f"Found {len(templates)} templates:")
        
        for i, template in enumerate(templates):
            print(f"\nTemplate {i+1}:")
            print(f"  ID: {template.get('id')}")
            print(f"  Name: {template.get('name')}")
            print(f"  Format: {template.get('format')}")
            print(f"  FileId: {template.get('fileId')}")
            print(f"  IsDefault: {template.get('isDefault')}")
            print(f"  Fields: {template.get('fields', [])}")
            
            # Check if this is the default template
            if template.get('isDefault'):
                print(f"  ⭐ This is the default template")
                
                # Try to test the print endpoint with this template
                print(f"  🧪 Testing print with this template...")
                
                sample_data = {
                    "templateId": template.get('id'),
                    "data": {
                        "CUSTOMER_NAME": "Test Customer",
                        "INVOICE_NUMBER": "INV-001",
                        "TOTAL": "100.00",
                        "ITEMS": [
                            {
                                "name": "Test Item",
                                "quantity": 1,
                                "price": 100.00,
                                "total": 100.00
                            }
                        ]
                    }
                }
                
                try:
                    print_response = requests.post(
                        f"{BASE_URL}/print/invoice-xlsx",
                        json=sample_data,
                        timeout=30
                    )
                    
                    print(f"  Print Response Status: {print_response.status_code}")
                    if print_response.status_code != 200:
                        print(f"  Print Response: {print_response.text}")
                    else:
                        print(f"  Print Success: {len(print_response.content)} bytes")
                        
                except Exception as e:
                    print(f"  Print Error: {e}")
    else:
        print(f"Failed to get templates: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    debug_templates()