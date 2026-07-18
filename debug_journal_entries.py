#!/usr/bin/env python3
"""
Debug Journal Entries Retrieval
"""

import requests
import json
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = "https://payment-defaults.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

def debug_journal_entries():
    """Debug journal entries retrieval"""
    print("="*80)
    print("DEBUG: Journal Entries Retrieval")
    print("="*80)
    
    # Test GET request
    try:
        response = requests.get(
            f"{BACKEND_URL}/finance/journal-entries?workshop_id={WORKSHOP_ID}&limit=10",
            timeout=15
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Keys: {list(data.keys())}")
            
            if 'entries' in data:
                entries = data['entries']
                print(f"Number of entries: {len(entries)}")
                
                for i, entry in enumerate(entries[:3]):  # Show first 3 entries
                    print(f"\nEntry {i+1}:")
                    print(f"  ID: {entry.get('id')}")
                    print(f"  Date: {entry.get('date')}")
                    print(f"  Description: {entry.get('description')}")
                    print(f"  Transaction Type: {entry.get('transaction_type')}")
                    print(f"  Source: {entry.get('source')}")
                    print(f"  Total: {entry.get('total')}")
            else:
                print("No 'entries' key in response")
                print(f"Full response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"Error response: {response.text}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    debug_journal_entries()