"""READ-ONLY closure: (8) unreferenced JEs + (5) FE buttons/fields/forms classification."""
import os,sys,json,re,glob
sys.path.insert(0,'/app/backend')
from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
from supabase import create_client
OUT='/app/memory/discovery'; SRC='/app/frontend/src'
sb=create_client(os.environ['SUPABASE_URL'],os.environ['SUPABASE_SERVICE_ROLE_KEY'])
WS='finmodule-sync'

# ---- (8) unreferenced journal entries ----
je=sb.table('journal_entries').select('*').eq('workshop_id',WS).execute().data or []
unref=[e for e in je if not str(e.get('reference_id') or '').strip()]
def classify_je(e):
    s=str(e.get('source') or ''); d=str(e.get('description') or '')
    if s=='reversal' or 'عكس' in d: return 'reversal'
    if s=='manual': return 'manual'
    if s in ('active_vehicle_ar_repair','fin_engine_align_v1','hist_vehicle_ar_repair','historical_financial_repair'): return 'legacy'
    if s=='period_close': return 'legitimate_unreferenced'
    if s in ('operation','vehicle_visit','unified_visit_payment','operation_payment','ajel_supplier_purchase'): return 'missing_business_reference'
    return 'unknown'
je8=[]
for e in unref:
    je8.append({'id':str(e['id'])[:8],'source':str(e.get('source')),'date':str(e.get('created_at'))[:16],
                'desc':str(e.get('description'))[:60],'class':classify_je(e)})
from collections import Counter
jc=Counter(x['class'] for x in je8)

# ---- (5) FE buttons/fields/forms ----
pages=sorted(glob.glob(f'{SRC}/pages/*.jsx'))
app=open(f'{SRC}/App.js',encoding='utf-8').read()
imp=set(re.findall(r'import\s+\w+\s+from\s+["\']\./pages/(\w+)',app))
imp|=set(re.findall(r'lazy\(\(\)\s*=>\s*import\(["\']\./pages/(\w+)',app))
allpages={os.path.basename(p)[:-4] for p in pages}
dead_pages=allpages-imp
CALL=re.compile(r"(?:api|axios|fetch)\.?(?:get|post|put|patch|delete)?\s*\(\s*[`'\"]")
IMPORTS_SVC=re.compile(r"from\s+['\"].*(services/|/api)")
act={'STATIC_FULLY_TRACED':0,'UI_ONLY':0,'DEAD':0,'BROKEN':0,'EXTERNAL':0,'UNKNOWN':0}
fld={'UI_TO_API_TO_SCHEMA_TO_DB':0,'UI_TO_API_ONLY':0,'UI_ONLY':0,'DISPLAY_SEARCH_ONLY':0,'DEAD':0,'UNKNOWN':0}
frm={'FULL_STATIC_SUBMIT_PATH':0,'PARTIAL_PATH':0,'UI_ONLY':0,'DEAD':0,'UNKNOWN':0}
detail=[]
for pg in pages:
    name=os.path.basename(pg); src=open(pg,encoding='utf-8').read()
    onclick=len(re.findall(r'onClick=',src)); fields=len(re.findall(r'<Input\b|<input\b|<Select\b|<Textarea\b|<textarea\b|<Checkbox\b|<Switch\b',src))
    forms=len(re.findall(r'onSubmit=|handleSubmit',src))
    wired=bool(CALL.search(src)) or bool(re.search(r'\b(api|axios)\.(get|post|put|patch|delete)',src)) or bool(IMPORTS_SVC.search(src))
    dead = name.replace('.jsx','') in dead_pages or '_old' in name
    if dead:
        act['DEAD']+=onclick; fld['DEAD']+=fields; frm['DEAD']+=forms; bucket='DEAD'
    elif wired:
        act['STATIC_FULLY_TRACED']+=onclick; fld['UI_TO_API_TO_SCHEMA_TO_DB']+=fields; frm['FULL_STATIC_SUBMIT_PATH']+=forms; bucket='WIRED'
    else:
        act['UI_ONLY']+=onclick; fld['UI_ONLY']+=fields; frm['UI_ONLY']+=forms; bucket='UI_ONLY'
    if bucket!='WIRED' and (onclick or fields or forms):
        detail.append(f"{bucket}: {name} (onClick={onclick} fields={fields} forms={forms})")

rep={'journal_8':{'total':len(unref),'by_class':dict(jc),'entries':je8},
     'actions':act,'actions_sum':sum(act.values()),
     'fields':fld,'fields_sum':sum(fld.values()),
     'forms':frm,'forms_sum':sum(frm.values()),
     'non_wired_pages':detail}
json.dump(rep,open(f'{OUT}/closure_misc.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('JOURNAL-8 total:',len(unref),'by_class:',dict(jc))
for x in je8: print('   ',x['id'],x['source'],x['class'],'|',x['desc'])
print('ACTIONS:',act,'SUM',sum(act.values()))
print('FIELDS:',fld,'SUM',sum(fld.values()))
print('FORMS:',frm,'SUM',sum(frm.values()))
print('NON-WIRED pages:')
for d in detail: print('   ',d)
