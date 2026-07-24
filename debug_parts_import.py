#!/usr/bin/env python3
"""
Debug Parts Import Issue
"""

import requests
import os
from io import BytesIO

BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'https://stamp-approval-flow.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

# Create CSV content
csv_content = """partNumber,name,category,purchasePrice,sellingPrice,quantity,minQuantity,supplier
TEST001,قطعة اختبار 1,محرك,50.0,75.0,10,5,مورد الاختبار
TEST002,قطعة اختبار 2,كهرباء,30.0,45.0,15,3,مورد الاختبار"""

print("Testing parts import...")
print(f"API URL: {API_BASE}/import/parts")

# Try with different approaches
session = requests.Session()

# Approach 1: Simple file upload
try:
    files = {'file': ('test_parts.csv', csv_content, 'text/csv')}
    resp = session.post(f"{API_BASE}/import/parts", files=files)
    print(f"Approach 1 - Status: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Approach 1 failed: {e}")

# Approach 2: With mode parameter
try:
    files = {'file': ('test_parts.csv', csv_content, 'text/csv')}
    data = {'mode': 'skip'}
    resp = session.post(f"{API_BASE}/import/parts", files=files, data=data)
    print(f"Approach 2 - Status: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Approach 2 failed: {e}")

# Approach 3: Check if pandas is available
try:
    resp = session.get(f"{API_BASE}/parts")
    print(f"Parts endpoint - Status: {resp.status_code}")
    parts = resp.json() if resp.status_code == 200 else []
    print(f"Current parts count: {len(parts)}")
except Exception as e:
    print(f"Parts check failed: {e}")