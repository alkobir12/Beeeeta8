"""تسوية شاملة READ-ONLY: الحقيقة القانونية (unified engine) مقابل دفتر الأستاذ لكل مركبة/زيارة.
يخرج قائمة القيود الزائدة/الناقصة المرشحة للتصحيح العكسي. لا يكتب أي شيء.
"""
import os, sys, json, re
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
from supabase import create_client
from core.unified_financial_engine import build_current_ar_snapshot

sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
WS = 'finmodule-sync'

rows = sb.table('journal_entries').select('*').eq('workshop_id', WS).execute().data or []
reversed_ids = {str(r['reference_id'])[len('reversal::'):] for r in rows if str(r.get('reference_id') or '').startswith('reversal::')}

def ar_delta(r):
    d = 0.0
    for ln in (r.get('lines') or []):
        if str(ln.get('account') or '') == '005':
            d += float(ln.get('debit') or 0) - float(ln.get('credit') or 0)
    return round(d, 2)

VISIT_RE = re.compile(r'\[VISIT:([0-9a-f-]{36})\]')

def visit_of(r):
    ref = str(r.get('reference_id') or '')
    m = VISIT_RE.search(str(r.get('description') or ''))
    if m: return m.group(1)
    if ref.startswith('vehfinal:'): return 'VEH:' + ref.split(':')[1]
    return ref

# canonical snapshot
snap = build_current_ar_snapshot(sb, WS)
veh_rows = snap.get('vehicles') or []

# خرائط زيارات -> مركبة
visits = sb.table('vehicle_visits').select('id, vehicle_id').execute().data or []
visit2veh = {str(v['id']): str(v['vehicle_id']) for v in visits}
ops = sb.table('operations').select('id, visit_id, vehicle_id').execute().data or []
op2visit = {str(o['id']): str(o.get('visit_id') or '') for o in ops}
op2veh = {str(o['id']): str(o.get('vehicle_id') or '') for o in ops}

# تجميع حركة 005 لكل مركبة
from collections import defaultdict
veh_ledger = defaultdict(lambda: {'entries': []})
unattributed = []
for r in rows:
    delta = ar_delta(r)
    if abs(delta) < 0.005: continue
    if str(r['id']) in reversed_ids:  # معكوس = محايد؛ العكس نفسه سيُحتسب أيضاً فيلغيه
        pass
    key = visit_of(r)
    veh = ''
    if key.startswith('VEH:'):
        veh = key[4:]
    elif key in visit2veh:
        veh = visit2veh[key]
    elif key in op2visit and op2visit[key] in visit2veh:
        veh = visit2veh[op2visit[key]]
    elif key in op2veh and op2veh[key] not in ('', 'None'):
        veh = op2veh[key]
    if veh and veh != 'None':
        veh_ledger[veh]['entries'].append((r, delta))
    else:
        unattributed.append((r, delta))

report = {'vehicles': [], 'unattributed_ar': []}
canon_by_veh = {str(v.get('vehicle_id')): v for v in veh_rows}
all_vehs = set(veh_ledger) | set(canon_by_veh)
total_ledger = total_canon = 0.0
for veh in all_vehs:
    led = round(sum(d for _, d in veh_ledger.get(veh, {}).get('entries', [])), 2)
    canon_row = canon_by_veh.get(veh) or {}
    summ = canon_row.get('summary') or canon_row
    canon = None
    for k in ('customer_receivable', 'receivable', 'remaining', 'customer_remaining'):
        if k in summ: canon = float(summ[k] or 0); break
    if canon is None:
        canon = float(canon_row.get('receivable') or 0) if canon_row else 0.0
    gap = round(led - canon, 2)
    total_ledger += led; total_canon += canon
    if abs(gap) > 0.01:
        report['vehicles'].append({
            'vehicle_id': veh,
            'ledger_ar': led, 'canonical_ar': round(canon, 2), 'gap': gap,
            'entries': [
                {'id': r['id'][:8], 'src': r.get('source'), 'type': r.get('transaction_type'),
                 'ar_delta': d, 'date': str(r.get('created_at'))[:16],
                 'desc': str(r.get('description'))[:60]}
                for r, d in sorted(veh_ledger.get(veh, {}).get('entries', []), key=lambda x: str(x[0].get('created_at')))
            ],
        })
for r, d in unattributed:
    report['unattributed_ar'].append({'id': r['id'][:8], 'src': r.get('source'), 'ar_delta': d,
                                      'ref': str(r.get('reference_id'))[:40], 'desc': str(r.get('description'))[:60]})
report['totals'] = {
    'ledger_ar_vehicle_attributed': round(total_ledger, 2),
    'canonical_ar': round(total_canon, 2),
    'unattributed_ar_sum': round(sum(d for _, d in unattributed), 2),
}
print(json.dumps(report['totals'], ensure_ascii=False))
print('vehicles with gap:', len(report['vehicles']))
for v in sorted(report['vehicles'], key=lambda x: -abs(x['gap']))[:12]:
    print(f"VEH {v['vehicle_id'][:8]} ledger={v['ledger_ar']} canon={v['canonical_ar']} GAP={v['gap']}")
    for e in v['entries']:
        print('   ', e['id'], e['src'][:26].ljust(26), e['type'], str(e['ar_delta']).rjust(9), e['date'], e['desc'][:45])
print('--- unattributed:')
for u in report['unattributed_ar'][:15]:
    print('   ', u['id'], str(u['src'])[:28].ljust(28), str(u['ar_delta']).rjust(9), u['ref'][:36], u['desc'][:40])
with open('/app/memory/reconciliation_ar_report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print('saved /app/memory/reconciliation_ar_report.json')
