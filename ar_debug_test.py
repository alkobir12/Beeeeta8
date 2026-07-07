#!/usr/bin/env python3
"""
اختبار سريع للتحقق من حساب الذمم المدينة بعد السداد
Quick test to verify AR calculation after payments
"""

import requests
import json

BACKEND_URL = "https://accounting-engine-6.preview.emergentagent.com/api"
WORKSHOP_ID = "finmodule-sync"

def check_ar_calculation():
    """التحقق من حساب الذمم المدينة"""
    
    # Check journal entries
    print("🔍 فحص القيود المحاسبية...")
    journal_url = f"{BACKEND_URL}/finance/journal-entries"
    journal_params = {"workshop_id": WORKSHOP_ID}
    
    journal_response = requests.get(journal_url, params=journal_params, timeout=30)
    if journal_response.status_code == 200:
        journal_data = journal_response.json()
        entries = journal_data.get("data", [])
        
        print(f"📊 إجمالي القيود: {len(entries)}")
        
        # Calculate AR balance from journal entries
        ar_balance = 0
        for entry in entries:
            lines = entry.get("lines", [])
            for line in lines:
                if line.get("account") == "113":  # AR account
                    debit = line.get("debit", 0)
                    credit = line.get("credit", 0)
                    ar_balance += debit - credit
                    print(f"   قيد AR: مدين={debit}, دائن={credit}, الرصيد الجاري={ar_balance}")
        
        print(f"📊 رصيد الذمم المدينة المحسوب من القيود: {ar_balance}")
        
        # Check trial balance
        print("\n🔍 فحص ميزان المراجعة...")
        trial_url = f"{BACKEND_URL}/finance/reports/trial-balance"
        trial_params = {"workshop_id": WORKSHOP_ID}
        
        trial_response = requests.get(trial_url, params=trial_params, timeout=30)
        if trial_response.status_code == 200:
            trial_data = trial_response.json()
            accounts = trial_data.get("data", {}).get("accounts", [])
            
            ar_account = None
            for account in accounts:
                if account.get("code") == "113":
                    ar_account = account
                    break
            
            if ar_account:
                trial_ar_balance = ar_account.get("debit", 0) - ar_account.get("credit", 0)
                print(f"📊 رصيد الذمم في ميزان المراجعة: {trial_ar_balance}")
            else:
                print("❌ حساب الذمم المدينة غير موجود في ميزان المراجعة")
        
        # Check AR ledger
        print("\n🔍 فحص دفتر الذمم المدينة...")
        ar_ledger_url = f"{BACKEND_URL}/finance/ar/ledger"
        ar_params = {
            "workshop_id": WORKSHOP_ID,
            "start_date": "2024-06-01",
            "end_date": "2024-06-30"
        }
        
        ar_response = requests.get(ar_ledger_url, params=ar_params, timeout=30)
        if ar_response.status_code == 200:
            ar_data = ar_response.json()
            ending_balance = ar_data.get("data", {}).get("ending_balance", 0)
            print(f"📊 الرصيد النهائي في دفتر الذمم: {ending_balance}")
            
            rows = ar_data.get("data", {}).get("rows", [])
            print(f"📊 عدد الحركات في دفتر الذمم: {len(rows)}")
            
            for row in rows:
                print(f"   {row.get('date')}: {row.get('type')} - مدين={row.get('debit', 0)}, دائن={row.get('credit', 0)}")

if __name__ == "__main__":
    check_ar_calculation()