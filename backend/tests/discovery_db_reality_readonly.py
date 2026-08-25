"""READ-ONLY production reality inventory. No writes. Counts + integrity probes."""
import os, sys, json
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
from supabase import create_client

sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
WS = os.environ.get('WORKSHOP_ID', 'finmodule-sync')

out = {"supabase": {}, "mongo": {}, "integrity": {}}

sb_tables = ["vehicles","vehicle_visits","operations","journal_entries","accounts",
             "customers","suppliers","parts","services","invoices","approval_requests",
             "business_accounts","transactions","technicians","users","workshop_settings"]
for t in sb_tables:
    try:
        r = sb.table(t).select('id', count='exact').limit(1).execute()
        out["supabase"][t] = r.count
    except Exception as e:
        out["supabase"][t] = f"ERR:{str(e)[:60]}"

# workshop-scoped journal + AR snapshot
try:
    je = sb.table('journal_entries').select('*').eq('workshop_id', WS).execute().data or []
    out["integrity"]["journal_entries_ws"] = len(je)
    # balance check
    td = tc = 0.0
    unbalanced = 0
    for e in je:
        d = sum(float(l.get('debit') or 0) for l in (e.get('lines') or []))
        c = sum(float(l.get('credit') or 0) for l in (e.get('lines') or []))
        td += d; tc += c
        if abs(d - c) > 0.01:
            unbalanced += 1
    out["integrity"]["total_debit"] = round(td, 2)
    out["integrity"]["total_credit"] = round(tc, 2)
    out["integrity"]["ledger_balanced"] = abs(td - tc) < 0.01
    out["integrity"]["unbalanced_entries"] = unbalanced
    # AR account 005 raw balance
    ar = 0.0
    for e in je:
        for l in (e.get('lines') or []):
            if str(l.get('account') or '') == '005':
                ar += float(l.get('debit') or 0) - float(l.get('credit') or 0)
    out["integrity"]["raw_ledger_ar_005"] = round(ar, 2)
    # source distribution
    from collections import Counter
    src = Counter(str(e.get('source')) for e in je)
    out["integrity"]["source_distribution"] = dict(src)
except Exception as e:
    out["integrity"]["error"] = str(e)[:200]

# canonical AR snapshot
try:
    from core.unified_financial_engine import build_current_ar_snapshot
    snap = build_current_ar_snapshot(sb, WS)
    out["integrity"]["canonical_ar_total"] = snap.get('total_ar') or snap.get('total') or sum(
        float((v.get('summary') or v).get('customer_receivable', 0) or 0) for v in (snap.get('vehicles') or []))
    out["integrity"]["canonical_ar_debtors"] = len(snap.get('vehicles') or [])
except Exception as e:
    out["integrity"]["canonical_error"] = str(e)[:200]

print(json.dumps(out, ensure_ascii=False, indent=1))
