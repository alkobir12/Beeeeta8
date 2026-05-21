"""
🔥 Rakan Radical Removal — Phase 1 (Data Purge)

Removes from Supabase ALL Rakan-related data:
  • 9 chart-of-accounts entries (043, 044, 053-058, 21010001)
  • Any operation/invoice/part mentioning Rakan
  • Creates new account 041 "تكلفة قطع الورشة" (expense)

Pre-checked: balances are zero, no journal_entries reference these accounts.
"""

from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import os
from supabase import create_client

supa = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

RAKAN_ACCOUNT_CODES = ["043", "044", "053", "054", "055", "056", "057", "058", "21010001"]

print("=" * 65)
print("🔥 RAKAN RADICAL REMOVAL — Data Purge Phase")
print("=" * 65)

# ---- 1) Delete Rakan-tagged operations ----
print("\n[1/5] Purging operations with Rakan references...")
ops = supa.table("operations").select("*").limit(5000).execute().data or []
deleted_ops = 0
for o in ops:
    hay = " ".join([
        str(o.get("partnerName") or o.get("partner_name") or ""),
        str(o.get("notes") or ""),
    ]).lower()
    if "راكان" in hay or "rakan" in hay or "21010001" in hay:
        try:
            supa.table("operations").delete().eq("id", o["id"]).execute()
            deleted_ops += 1
        except Exception as e:
            print(f"  ❌ op {o['id'][:8]}: {e}")
print(f"  ✅ Deleted operations: {deleted_ops}")

# ---- 2) Delete Rakan-tagged parts ----
print("\n[2/5] Purging parts with Rakan references...")
parts = supa.table("parts").select("*").limit(5000).execute().data or []
deleted_parts = 0
for p in parts:
    name = str(p.get("name") or "").lower()
    sup = str(p.get("supplier") or p.get("supplier_name") or "").lower()
    if "راكان" in name or "rakan" in name or "راكان" in sup or "rakan" in sup:
        try:
            supa.table("parts").delete().eq("id", p["id"]).execute()
            deleted_parts += 1
        except Exception as e:
            print(f"  ❌ part {p['id'][:8]}: {e}")
print(f"  ✅ Deleted parts: {deleted_parts}")

# ---- 3) Delete Rakan-tagged invoices ----
print("\n[3/5] Purging invoices with Rakan references...")
try:
    inv = supa.table("invoices").select("*").limit(5000).execute().data or []
    deleted_inv = 0
    for i in inv:
        hay = " ".join([
            str(i.get("partnerName") or i.get("partner_name") or ""),
            str(i.get("supplier") or i.get("supplier_name") or ""),
            str(i.get("notes") or ""),
        ]).lower()
        if "راكان" in hay or "rakan" in hay:
            supa.table("invoices").delete().eq("id", i["id"]).execute()
            deleted_inv += 1
    print(f"  ✅ Deleted invoices: {deleted_inv}")
except Exception as e:
    print(f"  ⚠️ invoices: {e}")

# ---- 4) Delete the 9 Rakan accounts ----
print("\n[4/5] Deleting 9 Rakan accounts from chart of accounts...")
deleted_accs = 0
for code in RAKAN_ACCOUNT_CODES:
    try:
        # Find first
        rows = supa.table("accounts").select("id, code, name").eq("code", code).execute().data or []
        for r in rows:
            supa.table("accounts").delete().eq("id", r["id"]).execute()
            print(f"  ✅ Deleted [{r['code']}] {r['name']}")
            deleted_accs += 1
    except Exception as e:
        print(f"  ❌ [{code}]: {e}")
print(f"  Total accounts deleted: {deleted_accs}")

# ---- 5) Create new account 041 "تكلفة قطع الورشة" ----
print("\n[5/5] Creating new account 041 'تكلفة قطع الورشة' (expense)...")
try:
    # Check if exists
    existing = supa.table("accounts").select("id, code, name").eq("code", "041").execute().data or []
    if existing:
        print(f"  ⚠️ Account 041 already exists: {existing[0].get('name')}")
    else:
        new_acc = {
            "code": "041",
            "name": "تكلفة قطع الورشة",
            "name_ar": "تكلفة قطع الورشة",
            "type": "expense",
            "balance": 0,
        }
        res = supa.table("accounts").insert(new_acc).execute()
        print("  ✅ Created: 041 — تكلفة قطع الورشة (expense)")
        if res.data:
            print(f"     id={res.data[0].get('id')}")
except Exception as e:
    print(f"  ❌ Failed to create 041: {e}")

print("\n" + "=" * 65)
print("✅ DATA PURGE COMPLETE")
print("=" * 65)
print(f"\nSummary: -{deleted_ops} ops, -{deleted_parts} parts, -{deleted_accs} accounts, +1 new account (041)")
