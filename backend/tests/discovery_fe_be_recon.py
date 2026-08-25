"""READ-ONLY: robust FE->BE endpoint reconciliation by comparing path tails."""
import os, re, json, glob
SRC='/app/frontend/src'; OUT='/app/memory/discovery'
endpoints=json.load(open(f'{OUT}/endpoints.json',encoding='utf-8'))

def tail(p):
    p=p.strip()
    # strip leading base-url template var(s) like ${API_BASE}, ${API}, ${API_URL}
    while p.startswith('${'):
        j=p.find('}')
        if j==-1: break
        p=p[j+1:]
    p=re.sub(r'\$\{[^}]+\}','{}',p)         # remaining mid-path vars -> param
    p=p.split('?')[0].split('#')[0]
    p=re.sub(r'//+','/',p)
    p=p.lstrip('/')
    if p.startswith('api/'): p=p[4:]
    p=re.sub(r':\w+','{}',p)                # :id
    p=re.sub(r'\{[^}]*\}','{}',p)           # {id}
    p=re.sub(r'/\d+','/{}',p)               # numeric ids
    return p.strip('/')

be=set()
for e in endpoints:
    t=tail(e['path'])
    if t: be.add((e['method'], t))
be_paths={t for _,t in be}

CALL=re.compile(r"(?:^|[^A-Za-z])(?:api|axios)\.(get|post|put|patch|delete)\s*\(\s*[`'\"]([^`'\"]+)")
fe=set()
files=glob.glob(f'{SRC}/**/*.js',recursive=True)+glob.glob(f'{SRC}/**/*.jsx',recursive=True)
raw=[]
for f in files:
    try: src=open(f,encoding='utf-8').read()
    except Exception: continue
    for meth,url in CALL.findall(src):
        t=tail(url)
        if not t: continue
        fe.add((meth.upper(), t)); raw.append((meth.upper(),t,os.path.basename(f)))

fe_paths={t for _,t in fe}
matched=sorted(t for t in fe_paths if t in be_paths)
unmatched=sorted(t for t in fe_paths if t not in be_paths)
# method-exact match
me_matched=sorted(f"{m} {t}" for m,t in fe if (m,t) in be)
me_unmatched=sorted(f"{m} {t}" for m,t in fe if (m,t) not in be and t in be_paths)

lines=['# FE→BE API RECONCILIATION (path-tail, all src)','',
 f'Distinct FE call tails: **{len(fe_paths)}** (across pages+components+services+hooks)',
 f'Distinct BE endpoint tails: **{len(be_paths)}** (of 512 endpoints)',
 f'FE tails matched to a BE path: **{len(matched)}** · UNMATCHED: **{len(unmatched)}**',
 f'(method+path exact matches: {len(me_matched)}; path matches but method differs: {len(me_unmatched)})','',
 '## UNMATCHED FE call tails (no backend path found — verify: dead/typo/proxy/other service)','']
for t in unmatched: lines.append(f'- `{t}`')
open(f'{OUT}/FE_BE_RECONCILIATION.md','w',encoding='utf-8').write('\n'.join(lines))
print('FE tails:',len(fe_paths),'| BE tails:',len(be_paths),'| matched:',len(matched),'| unmatched:',len(unmatched))
print('UNMATCHED sample:', unmatched[:25])
