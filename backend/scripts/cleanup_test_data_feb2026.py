"""Test data cleanup script - February 2026 cleanup pass."""
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import os
from supabase import create_client

supa = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
)

print("=" * 60)
print("🧹 TEST DATA CLEANUP — Supabase")
print("=" * 60)

PATTERNS = [
    "TEST_", "DEMO_", "FIREWALL_DEMO", "DEMO_FIREWALL",
    "test-sale-", "test-precision-", "test-cogs-", "test_balanced_iter",
]

je = supa.table("journal_entries").select("*").limit(5000).execute().data or []
to_del_je = []
for r in je:
    hay = " ".join([
        str(r.get("description") or ""),
        str(r.get("source") or ""),
        str(r.get("reference_id") or ""),
    ]).lower()
    if any(p.lower() in hay for p in PATTERNS):
        to_del_je.append(r)

print(f"\n📖 Journal Entries to delete: {len(to_del_je)}")
for r in to_del_je:
    desc = (r.get("description") or "")[:60]
    print(f"  • {r['id'][:8]} | {desc} | total={r.get('total')}")

ops = supa.table("operations").select("*").limit(5000).execute().data or []
to_del_ops = []
for o in ops:
    hay = " ".join([
        str(o.get("partnerName") or ""),
        str(o.get("invoiceNumber") or ""),
        str(o.get("notes") or ""),
    ]).lower()
    if any(p in hay for p in ["demo_firewall", "firewall_demo", "demo-idemp", "test-sale", "test-precision", "test_balanced"]):
        to_del_ops.append(o)

print(f"\n🔄 Operations to delete: {len(to_del_ops)}")
for o in to_del_ops:
    notes = (o.get("notes") or "")[:60]
    print(f"  • {o['id'][:8]} | partner={o.get('partnerName')} | notes={notes}")

print("\n" + "=" * 60)
print("⚙️ EXECUTING DELETES...")
print("=" * 60)

deleted = {"journal_entries": 0, "operations": 0}

for r in to_del_je:
    try:
        supa.table("journal_entries").delete().eq("id", r["id"]).execute()
        deleted["journal_entries"] += 1
    except Exception as e:
        print(f"  ❌ je {r['id'][:8]}: {e}")

for o in to_del_ops:
    try:
        supa.table("operations").delete().eq("id", o["id"]).execute()
        deleted["operations"] += 1
    except Exception as e:
        print(f"  ❌ op {o['id'][:8]}: {e}")

print("\n✅ Deletion Summary:")
for k, v in deleted.items():
    print(f"   {k}: {v}")

print("\n📊 POST-CLEANUP COUNTS:")
for t in ["journal_entries", "operations", "customers", "vehicles", "vehicle_visits", "invoices", "parts", "services", "accounts"]:
    try:
        r = supa.table(t).select("*", count="exact").limit(1).execute()
        print(f"   {t}: {r.count}")
    except Exception:
        print(f"   {t}: error")
