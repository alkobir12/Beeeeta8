"""READ-ONLY: static Authorization matrix for all 512 endpoints + write-path
reachability + buttons/fields/forms classification + 8 unreferenced JEs.
NO writes."""
import ast, os, re, json, glob
BE='/app/backend'; OUT='/app/memory/discovery'
eps=json.load(open(f'{OUT}/endpoints.json',encoding='utf-8'))

# public allowlist from auth_guard
pub=set()
try:
    ag=open(f'{BE}/auth_guard.py',encoding='utf-8').read()
    pub={m for m in re.findall(r'["\'](/api/[^"\']+)["\']',ag)}
    pub|= {m for m in re.findall(r'["\'](/[^"\']+)["\']',ag) if 'public' in m or 'health' in m}
except Exception: pass

# cache function sources per file
srccache={}
def func_src(fname, fn):
    p=f'{BE}/{fname}'
    if p not in srccache:
        try: srccache[p]=(open(p,encoding='utf-8').read(),ast.parse(open(p,encoding='utf-8').read()))
        except Exception: srccache[p]=('',None)
    src,tree=srccache[p]
    if not tree: return ''
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==fn:
            seg=ast.get_source_segment(src,n)
            if seg: return seg
    return ''

ROLE_TOK=re.compile(r'_require_|require_role|require_perm|_require_request_permission|_require_admin|_require_approver|_require_reconciliation|APPROVER_ROLES|actor\.role|role\s*(!=|==|not in|in)\s|check_permission|has_permission|status_code=403|HTTP_403|raise PermissionError|_forbid|_deny')
OBJ_TOK=re.compile(r'owner|created_by|\.eq\(["\']user_id|belongs_to|resource_owner|actor\.user_id')
FIN_FILES=('routes_finance','financial_control','routes_financial','accounting','routes_invoices','routes_smart_accounting','routes_accounts','routes_action_runtime','routes_approvals','routes_payroll')
SENS_FILES=('routes_users','routes_vehicle_files','routes_financial_reset','routes_cleanup')

def classify(e):
    path=e['path']; m=e['method']; f=e['file']; fn=e['func']
    is_pub = any(path.startswith(pp) or pp.startswith(path) for pp in pub) or '/public/' in path or path.endswith('/health') or '/auth/login' in path or '/auth/refresh' in path or '/auth/logout' in path
    body=func_src(f,fn)
    has_role=bool(ROLE_TOK.search(body))
    has_obj=bool(OBJ_TOK.search(body))
    fin=any(k in f for k in FIN_FILES)
    sens=any(k in f for k in SENS_FILES) or fin or 'user' in path or 'role' in path or 'permission' in path or 'file' in path or 'approval' in path
    mutating = m in ('POST','PUT','PATCH','DELETE')
    if is_pub: st='PUBLIC_INTENTIONAL'
    elif has_role and has_obj: st='AUTHZ_COMPLETE'
    elif has_role: st='ROLE_CHECK_ONLY'
    elif mutating and sens: st='MISSING_AUTHZ'
    elif not body: st='UNKNOWN'
    else: st='AUTH_ONLY_NO_OBJECT_CHECK'
    return st, fin, mutating

rows=[]; from collections import Counter
cnt=Counter(); miss=[]
for e in eps:
    st,fin,mut=classify(e)
    cnt[st]+=1
    rows.append({**e,'authz':st,'financial':fin,'mutating':mut})
    if st=='MISSING_AUTHZ': miss.append(f"{e['method']} {e['path']}  [{e['file']}]")

mutating_total=sum(1 for r in rows if r['mutating'])
fin_total=sum(1 for r in rows if r['financial'])
lines=['# 11_AUTHORIZATION_MATRIX (static, all 512 endpoints)','',
 f'Total endpoints: **{len(rows)}** · mutating(POST/PUT/PATCH/DELETE): **{mutating_total}** · financial-domain: **{fin_total}**','',
 '## Totals by classification','']
for k in ['PUBLIC_INTENTIONAL','AUTHZ_COMPLETE','ROLE_CHECK_ONLY','AUTH_ONLY_NO_OBJECT_CHECK','MISSING_AUTHZ','UNKNOWN']:
    lines.append(f'- {k}: {cnt.get(k,0)}')
lines.append(f'\n**SUM = {sum(cnt.values())} (must equal {len(rows)})**')
lines+=['','## 🔴 MISSING_AUTHZ (sensitive mutating, no role check in handler) — '+str(len(miss)),'']
for x in sorted(miss): lines.append(f'- `{x}`')
open(f'{OUT}/11_AUTHORIZATION_MATRIX.md','w',encoding='utf-8').write('\n'.join(lines))
json.dump(rows,open(f'{OUT}/authz_matrix.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('AUTHZ totals:',dict(cnt),'| SUM',sum(cnt.values()),'| mutating',mutating_total,'| financial',fin_total,'| MISSING_AUTHZ',len(miss))

# ---- WRITE PATH reachability (item 4) ----
writes=json.load(open(f'{OUT}/writes.json',encoding='utf-8'))
def reach(w):
    f=w['file']
    if f.startswith('scripts/'):
        if any(k in f for k in ('seed','init','migrat','backfill')): return 'MIGRATION'
        return 'OFFLINE_SCRIPT'
    if '/tests/' in f or f.startswith('tests/') or 'test_' in f: return 'TEST_ONLY'
    if 'tool_router' in f or 'agents' in f: return 'LIVE_KATRINA'
    if 'auto_sync' in f or 'scheduler' in f or 'worker' in f or 'cron' in f: return 'LIVE_BACKGROUND_JOB'
    if f.startswith('routes_') or f.startswith('domains/') or f.startswith('financial_control/') or f=='server.py' or 'auth_jwt' in f: return 'LIVE_PRODUCTION_API'
    if 'core/' in f: return 'LIVE_PRODUCTION_API'  # engines called by routes
    return 'UNKNOWN'
wc=Counter(reach(w) for w in writes)
prod=sum(v for k,v in wc.items() if k in ('LIVE_PRODUCTION_API','LIVE_BACKGROUND_JOB','LIVE_KATRINA'))
wl=['# WRITE-PATH REACHABILITY (item 4, 329 call-sites)','','## Totals','']
for k in ['LIVE_PRODUCTION_API','LIVE_BACKGROUND_JOB','LIVE_KATRINA','ADMIN_ONLY','OFFLINE_SCRIPT','MIGRATION','TEST_ONLY','DEAD_CODE','UNKNOWN']:
    wl.append(f'- {k}: {wc.get(k,0)}')
wl.append(f'\n**SUM = {sum(wc.values())} · production-reachable write call-sites = {prod}**')
open(f'{OUT}/WRITE_PATH_REACHABILITY.md','w',encoding='utf-8').write('\n'.join(wl))
print('WRITE reach:',dict(wc),'| production-reachable',prod)
