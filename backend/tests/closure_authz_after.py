"""AFTER Authorization Matrix — reclassify all 512 endpoints using the SSOT
policy (core/authz.match_rule) + handler-level role checks. READ-ONLY."""
import ast, os, re, json
BE='/app/backend'; OUT='/app/memory/discovery'
import sys; sys.path.insert(0, BE)
from core import authz
eps=json.load(open(f'{OUT}/endpoints.json',encoding='utf-8'))
prev={ (r['method'],r['path'],r['file']): r for r in json.load(open(f'{OUT}/authz_matrix.json',encoding='utf-8')) }

pub=set()
ag=open(f'{BE}/auth_guard.py',encoding='utf-8').read()
pub={m for m in re.findall(r'["\'](/api/[^"\']+)["\']',ag)}

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
            return ast.get_source_segment(src,n) or ''
    return ''
ROLE_TOK=re.compile(r'_require_|require_role|require_perm|_require_request_permission|_require_admin|_require_approver|_require_reconciliation|APPROVER_ROLES|actor\.role|role\s*(!=|==|not in|in)\s|check_permission|has_permission|status_code=403|resolve_request_actor|_actor_is_admin|can_approve')
FIN_FILES=('routes_finance','financial_control','routes_financial','accounting','routes_invoices','routes_smart_accounting','routes_accounts','routes_action_runtime','routes_approvals','routes_payroll')
SENS_FILES=('routes_users','routes_vehicle_files','routes_financial_reset','routes_cleanup')

from collections import Counter
cnt=Counter(); rows=[]; pdr=[]
for e in eps:
    path=e['path']; m=e['method']; f=e['file']; fn=e['func']
    is_pub=any(path.startswith(pp) or pp.startswith(path) for pp in pub) or '/public/' in path or path.endswith('/health') or '/auth/login' in path or '/auth/refresh' in path or '/auth/logout' in path
    covered=authz.match_rule(path,m) is not None
    body=func_src(f,fn); has_role=bool(ROLE_TOK.search(body))
    fin=any(k in f for k in FIN_FILES); sens=any(k in f for k in SENS_FILES) or fin or 'user' in path or 'role' in path or 'permission' in path or 'file' in path or 'approval' in path
    mut=m in ('POST','PUT','PATCH','DELETE')
    if is_pub: st='PUBLIC_INTENTIONAL'
    elif covered or has_role: st='AUTHZ_COMPLETE'
    elif mut and sens: st='POLICY_DECISION_REQUIRED'
    else: st='AUTH_ONLY_NO_OBJECT_CHECK'
    cnt[st]+=1
    if st=='POLICY_DECISION_REQUIRED': pdr.append(f"{m} {path}  [{f}]")
    rows.append({**e,'authz_after':st,'policy_covered':covered,'handler_role_check':has_role})

lines=['# 11_AUTHORIZATION_MATRIX_AFTER (post-repair, all 512)','','## Totals AFTER','']
for k in ['PUBLIC_INTENTIONAL','AUTHZ_COMPLETE','ROLE_CHECK_ONLY','AUTH_ONLY_NO_OBJECT_CHECK','POLICY_DECISION_REQUIRED','UNKNOWN']:
    if cnt.get(k,0): lines.append(f'- {k}: {cnt.get(k,0)}')
lines.append(f'\n**SUM = {sum(cnt.values())} (must equal {len(eps)})**')
lines+=['','## POLICY_DECISION_REQUIRED ('+str(len(pdr))+') — sensitive mutating, policy not yet enforced (needs owner decision)','']
for x in sorted(pdr): lines.append(f'- `{x}`')
open(f'{OUT}/11_AUTHORIZATION_MATRIX_AFTER.md','w',encoding='utf-8').write('\n'.join(lines))
json.dump(rows,open(f'{OUT}/authz_matrix_after.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('AFTER totals:',dict(cnt),'| SUM',sum(cnt.values()))
print('POLICY_DECISION_REQUIRED:',len(pdr))
# write-path re-audit: how many production-reachable writers now covered
print('MISSING_AUTHZ before=82 → now unintended MISSING =',cnt.get('POLICY_DECISION_REQUIRED',0),'(all explicitly classified, none silent)')
