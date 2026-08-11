#!/usr/bin/env python3
"""
Detailed Backend Testing for Smart POS Journal Entries
Verifying token parsing and party/vehicle information extraction
"""

import requests
import json

BACKEND_URL = "https://finance-overhaul-7.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

def test_token_parsing():
    """Test that tokens in descriptions are properly parsed"""
    
    print("=" * 80)
    print("SMART POS TOKEN PARSING VERIFICATION")
    print("=" * 80)
    print()
    
    # Get all journal entries
    response = requests.get(
        f"{BACKEND_URL}/finance/journal-entries",
        params={"workshop_id": WORKSHOP_ID, "limit": 100},
        timeout=10
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch journal entries: HTTP {response.status_code}")
        return
    
    data = response.json()
    entries = data.get("data", [])
    smart_pos_entries = [e for e in entries if e.get("source") == "smart_pos"]
    
    print(f"Found {len(smart_pos_entries)} Smart POS entries")
    print()
    
    for i, entry in enumerate(smart_pos_entries[:10], 1):  # Show first 10
        print(f"Entry {i}: {entry.get('id')[:8]}...")
        print(f"  Date: {entry.get('date')}")
        print(f"  Type: {entry.get('transaction_type')}")
        print(f"  Description: {entry.get('description')}")
        print(f"  Party Type: {entry.get('party_type')}")
        print(f"  Party Label: {entry.get('party_label')}")
        print(f"  Vehicle Label: {entry.get('vehicle_label')}")
        print(f"  Total: {entry.get('total')}")
        
        # Verify balance
        lines = entry.get("lines", [])
        total_debit = sum(line.get("debit", 0) for line in lines)
        total_credit = sum(line.get("credit", 0) for line in lines)
        balance_status = "✅ Balanced" if abs(total_debit - total_credit) < 0.01 else "❌ UNBALANCED"
        
        print(f"  Lines: {len(lines)} lines")
        print(f"    Total Debit: {total_debit:.2f}")
        print(f"    Total Credit: {total_credit:.2f}")
        print(f"    Status: {balance_status}")
        print()
    
    # Summary statistics
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    transaction_types = {}
    party_types = {}
    
    for entry in smart_pos_entries:
        tx_type = entry.get("transaction_type", "unknown")
        party_type = entry.get("party_type", "unknown")
        
        transaction_types[tx_type] = transaction_types.get(tx_type, 0) + 1
        party_types[party_type] = party_types.get(party_type, 0) + 1
    
    print(f"\nTransaction Types:")
    for tx_type, count in sorted(transaction_types.items()):
        print(f"  - {tx_type}: {count}")
    
    print(f"\nParty Types:")
    for party_type, count in sorted(party_types.items()):
        print(f"  - {party_type}: {count}")
    
    # Check for entries with vehicle references
    with_vehicle = sum(1 for e in smart_pos_entries if e.get("vehicle_label"))
    print(f"\nEntries with vehicle reference: {with_vehicle}/{len(smart_pos_entries)}")
    
    # Check balance status
    balanced = sum(1 for e in smart_pos_entries 
                   if abs(sum(l.get("debit", 0) for l in e.get("lines", [])) - 
                          sum(l.get("credit", 0) for l in e.get("lines", []))) < 0.01)
    print(f"Balanced entries: {balanced}/{len(smart_pos_entries)}")
    
    print()

if __name__ == "__main__":
    test_token_parsing()
