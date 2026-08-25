"""READ-ONLY: identify legacy-layer AR (005) entries that coexist with a
CANONICAL_BUSINESS entry for the SAME vehicle. Lists reversal candidates.
DOES NOT WRITE ANYTHING. No reverse_entry. No mutation."""
import os, sys, json, re
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
from supabase import create_client
from collections import defaultdict

sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
WS = 'finmodule-sync'

rows = sb.table('journal_entries').select('*').eq('workshop_id', WS).execute().data or []
reversed_ids = {str(r['reference_id'])[len('reversal::'):] for r in rows
                if str(r.get('reference_id') or '').startswith('reversal::')}

LEGACY_SOURCES = {"active_vehicle_ar_repair", "fin_engine_align_v1",
                  "hist_vehicle_ar_repair", "historical_financial_repair"}
CANONICAL_SOURCE = "vehicle_visit"
VISIT_RE = re.compile(r'\[VISIT:([0-9a-f-]{36})\]')
VEH_RE = re.compile(r'\[VEHICLE:([0-9a-f-]{36})\]')

def ar_delta(r):
    d = 0.0
    for ln in (r.get('lines') or []):
        if str(ln.get('account') or '') == '005':
            d += float(ln.get('debit') or 0) - float(ln.get('credit') or 0)
    return round(d, 2)

visits = sb.table('vehicle_visits').select('id, vehicle_id').execute().data or []
visit2veh = {str(v['id']): str(v['vehicle_id']) for v in visits}
ops = sb.table('operations').select('id, visit_id, vehicle_id').execute().data or []
op2visit = {str(o['id']): str(o.get('visit_id') or '') for o in ops}
op2veh = {str(o['id']): str(o.get('vehicle_id') or '') for o in ops}

def veh_of(r):
    desc = str(r.get('description') or '')
    m = VEH_RE.search(desc)
    if m: return m.group(1)
    m = VISIT_RE.search(desc)
    if m and m.group(1) in visit2veh: return visit2veh[m.group(1)]
    ref = str(r.get('reference_id') or '')
    if ref.startswith('vehfinal:'): return ref.split(':')[1]
    if ref.startswith('visitfinal:'):
        vid = ref.split(':')[1]
        return visit2veh.get(vid, '')
    if ref in visit2veh: return visit2veh[ref]
    if ref in op2visit and op2visit[ref] in visit2veh: return visit2veh[op2visit[ref]]
    if ref in op2veh: return op2veh[ref]
    return ''

by_veh = defaultdict(lambda: {"canonical": [], "legacy": [], "operation_temp": []})
for r in rows:
    d = ar_delta(r)
    if abs(d) < 0.005: continue
    if str(r['id']) in reversed_ids: continue  # already reversed
    src = str(r.get('source') or '')
    veh = veh_of(r)
    if not veh: continue
    rec = {"id": str(r['id']), "src": src, "ar_delta": d,
           "date": str(r.get('created_at'))[:16], "desc": str(r.get('description'))[:70],
           "ref": str(r.get('reference_id') or '')[:40]}
    if src == CANONICAL_SOURCE and 'CANONICAL_BUSINESS' in str(r.get('description') or ''):
        by_veh[veh]["canonical"].append(rec)
    elif src in LEGACY_SOURCES:
        by_veh[veh]["legacy"].append(rec)
    elif src == "operation" and '[قيد مؤقت' in str(r.get('description') or ''):
        by_veh[veh]["operation_temp"].append(rec)

candidates = []
total_reversal = 0.0
for veh, g in by_veh.items():
    has_canonical = len(g["canonical"]) > 0
    legacy_all = g["legacy"] + g["operation_temp"]
    if has_canonical and legacy_all:
        canon_sum = round(sum(c["ar_delta"] for c in g["canonical"]), 2)
        legacy_sum = round(sum(l["ar_delta"] for l in legacy_all), 2)
        total_reversal += legacy_sum
        candidates.append({
            "vehicle_id": veh,
            "canonical_ar": canon_sum,
            "legacy_ar_to_reverse": legacy_sum,
            "canonical_entries": g["canonical"],
            "legacy_candidates": legacy_all,
        })

# vehicles with legacy but NO canonical (needs case decision, NOT auto-reverse)
legacy_no_canon = []
for veh, g in by_veh.items():
    legacy_all = g["legacy"] + g["operation_temp"]
    if not g["canonical"] and legacy_all:
        legacy_no_canon.append({
            "vehicle_id": veh,
            "legacy_ar": round(sum(l["ar_delta"] for l in legacy_all), 2),
            "entries": legacy_all,
        })

report = {
    "safe_reversal_candidates": sorted(candidates, key=lambda x: -x["legacy_ar_to_reverse"]),
    "safe_reversal_total": round(total_reversal, 2),
    "safe_reversal_vehicle_count": len(candidates),
    "legacy_without_canonical_review": sorted(legacy_no_canon, key=lambda x: -x["legacy_ar"]),
    "legacy_without_canonical_total": round(sum(x["legacy_ar"] for x in legacy_no_canon), 2),
}
with open('/app/memory/candidate_reversal_ledger.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print("SAFE reversal candidates (canonical exists + legacy present):", len(candidates))
print("SAFE reversal total AR to reverse:", report["safe_reversal_total"])
for c in report["safe_reversal_candidates"]:
    print(f"  VEH {c['vehicle_id'][:8]} canon={c['canonical_ar']} legacy_to_reverse={c['legacy_ar_to_reverse']} ({len(c['legacy_candidates'])} entries)")
    for l in c["legacy_candidates"]:
        print(f"      {l['id'][:8]} {l['src'][:26].ljust(26)} {str(l['ar_delta']).rjust(9)} {l['date']}")
print("--- legacy WITHOUT canonical (review, do NOT auto-reverse):", len(legacy_no_canon), "total", report["legacy_without_canonical_total"])
for x in report["legacy_without_canonical_review"]:
    print(f"  VEH {x['vehicle_id'][:8]} legacy={x['legacy_ar']} ({len(x['entries'])} entries)")
print("saved /app/memory/candidate_reversal_ledger.json")
