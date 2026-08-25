"""READ-ONLY DB schema + relationship + financial-link discovery. NO writes."""
import os, sys, json, re
sys.path.insert(0,'/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
from supabase import create_client
OUT='/app/memory/discovery'; os.makedirs(OUT,exist_ok=True)
sb=create_client(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'])
WS='finmodule-sync'
out={'tables':{},'relationships':[],'financial':{},'orphans':{}}

tables=['vehicles','vehicle_visits','operations','journal_entries','accounts','customers',
        'parts','services','invoices','approval_requests','business_accounts','transactions','technicians']
for t in tables:
    try:
        r=sb.table(t).select('*').limit(1).execute().data
        cols=sorted(r[0].keys()) if r else []
        fks=[c for c in cols if c.endswith('_id') or c.endswith('Id')]
        out['tables'][t]={'columns':cols,'fk_like':fks,'sampled':bool(r)}
    except Exception as e:
        out['tables'][t]={'error':str(e)[:80]}

# relationship + orphan checks (read-only)
try:
    vehicles={str(v['id']) for v in sb.table('vehicles').select('id').execute().data or []}
    visits=sb.table('vehicle_visits').select('id,vehicle_id').execute().data or []
    ops=sb.table('operations').select('id,vehicle_id,visit_id').execute().data or []
    out['orphans']['visits_bad_vehicle']=sum(1 for v in visits if str(v.get('vehicle_id')) not in vehicles)
    out['orphans']['ops_bad_vehicle']=sum(1 for o in ops if o.get('vehicle_id') and str(o.get('vehicle_id')) not in vehicles)
    visit_ids={str(v['id']) for v in visits}
    out['orphans']['ops_bad_visit']=sum(1 for o in ops if o.get('visit_id') and str(o.get('visit_id')) not in visit_ids)
except Exception as e:
    out['orphans']['error']=str(e)[:120]

# financial-link integrity
try:
    je=sb.table('journal_entries').select('*').eq('workshop_id',WS).execute().data or []
    def has_link(e):
        d=str(e.get('description') or ''); ref=str(e.get('reference_id') or '')
        return bool(re.search(r'\[VEHICLE:|\[VISIT:|vehfinal:|visitfinal:',d+ref) or ref)
    reversal=[e for e in je if str(e.get('source'))=='reversal' or str(e.get('reference_id') or '').startswith('reversal::')]
    reversed_targets=[str(e['reference_id'])[len('reversal::'):] for e in je if str(e.get('reference_id') or '').startswith('reversal::')]
    from collections import Counter
    dup_rev=Counter(reversed_targets)
    ar005=lambda e: any(str(l.get('account'))=='005' for l in (e.get('lines') or []))
    legacy_srcs={'active_vehicle_ar_repair','fin_engine_align_v1','hist_vehicle_ar_repair','historical_financial_repair'}
    out['financial']={
      'journal_entries':len(je),
      'with_business_link':sum(1 for e in je if has_link(e)),
      'without_any_reference':sum(1 for e in je if not str(e.get('reference_id') or '')),
      'reversal_entries':len(reversal),
      'duplicate_reversal_targets':{k:v for k,v in dup_rev.items() if v>1},
      'entries_touching_AR005':sum(1 for e in je if ar005(e)),
      'legacy_source_entries':sum(1 for e in je if str(e.get('source')) in legacy_srcs),
      'source_distribution':dict(Counter(str(e.get('source')) for e in je)),
    }
except Exception as e:
    out['financial']['error']=str(e)[:150]

json.dump(out,open(f'{OUT}/db_schema_relationships.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
# markdown
ml=['# 13/14/15 DATABASE + RELATIONSHIP + FINANCIAL-LINK (read-only)','','## Tables (Supabase) columns','']
for t,info in out['tables'].items():
    if 'error' in info: ml.append(f'- **{t}**: ERR {info["error"]}'); continue
    ml.append(f"- **{t}** ({len(info['columns'])} cols) FK-like: {', '.join(info['fk_like']) or '—'}")
ml+=['','## Orphan / referential integrity (application-level FKs)','']
for k,v in out['orphans'].items(): ml.append(f'- {k}: {v}')
ml+=['','## Financial link integrity','']
for k,v in out['financial'].items():
    if k in ('source_distribution','duplicate_reversal_targets'): 
        ml.append(f'- {k}: {json.dumps(v,ensure_ascii=False)}'); continue
    ml.append(f'- {k}: {v}')
open(f'{OUT}/13_14_15_DATABASE_RELATIONSHIPS.md','w',encoding='utf-8').write('\n'.join(ml))
print(json.dumps({'orphans':out['orphans'],'financial':{k:out['financial'].get(k) for k in ('journal_entries','with_business_link','without_any_reference','reversal_entries','duplicate_reversal_targets','legacy_source_entries')}},ensure_ascii=False,indent=1))
