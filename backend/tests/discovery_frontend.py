"""READ-ONLY static discovery — FRONTEND. Inventories routes, pages, components,
per-page buttons/fields/forms, extracts FE API calls and reverse-maps them to
backend endpoints. Detects dead/duplicate components. NO writes."""
import os, re, json, glob
from collections import defaultdict

SRC = '/app/frontend/src'
OUT = '/app/memory/discovery'
os.makedirs(OUT, exist_ok=True)

def read(p):
    try: return open(p, encoding='utf-8').read()
    except Exception: return ''

# ---------- ROUTES ----------
app_js = read(f'{SRC}/App.js')
routes = re.findall(r'<Route\s+path="([^"]+)"\s+element=\{<(\w+)', app_js)
index_routes = re.findall(r'<Route\s+index\s+element=\{<(\w+)', app_js)
nav_redirects = re.findall(r'<Route\s+path="([^"]+)"\s+element=\{<Navigate\s+to="([^"]+)"', app_js)
rl = ['# 03_ROUTE_INVENTORY (static)', '', f'Declared <Route path> entries: **{len(routes)}** + index:{len(index_routes)} + redirects:{len(nav_redirects)}','',
      '| path | component |','|---|---|']
for p, c in routes:
    rl.append(f'| `{p}` | {c} |')
rl += ['', '## Redirects', ''] + [f'- `{p}` → `{t}`' for p,t in nav_redirects]
rl += ['', '## Index/fallback', ''] + [f'- index → {c}' for c in index_routes]
open(f'{OUT}/03_ROUTE_INVENTORY.md','w',encoding='utf-8').write('\n'.join(rl))

# ---------- PAGES + COMPONENTS ----------
pages = sorted(glob.glob(f'{SRC}/pages/*.jsx'))
comps = sorted(glob.glob(f'{SRC}/components/**/*.jsx', recursive=True))

API_RE = re.compile(r'/api/([A-Za-z0-9_\-\{\}\$\.:/]+)')
CALL_RE = re.compile(r'(?:api|axios)\.(get|post|put|patch|delete)\s*\(\s*[`\'"]([^`\'"]+)[`\'"]')

def extract_api_paths(src):
    paths = set()
    for m in API_RE.finditer(src):
        p = '/api/' + m.group(1)
        p = re.sub(r'\$\{[^}]+\}', '{x}', p)
        p = p.rstrip('`\'"').rstrip('/')
        paths.add(p)
    return paths

def norm(p):
    p = re.sub(r'\$\{[^}]+\}', '{x}', p)
    p = re.sub(r':\w+', '{x}', p)
    p = re.sub(r'\{[^}]+\}', '{x}', p)
    if not p.startswith('/api'): 
        p = '/api' + (p if p.startswith('/') else '/'+p)
    return p.rstrip('/')

# per-page metrics
page_rows = []
all_fe_paths = set()
for pg in pages:
    src = read(pg)
    name = os.path.basename(pg)
    testids = len(re.findall(r'data-testid=', src))
    onclicks = len(re.findall(r'onClick=', src))
    forms = len(re.findall(r'onSubmit=|handleSubmit', src))
    inputs = len(re.findall(r'<Input\b|<input\b|<Select\b|<Textarea\b|<textarea\b|<Checkbox\b|<Switch\b', src))
    calls = CALL_RE.findall(src)
    fe_paths = extract_api_paths(src)
    all_fe_paths |= {norm(p) for p in fe_paths}
    page_rows.append({'page': name, 'testids': testids, 'onClick': onclicks, 'forms': forms,
                      'fields': inputs, 'api_calls': len(fe_paths)})

pl = ['# 04_PAGE_MATRIX (static counts per page)', '', f'Total pages: **{len(pages)}**','',
      '| page | data-testid | onClick | forms | fields | distinct /api paths |','|---|---|---|---|---|---|']
for r in sorted(page_rows, key=lambda x:-x['onClick']):
    pl.append(f"| {r['page']} | {r['testids']} | {r['onClick']} | {r['forms']} | {r['fields']} | {r['api_calls']} |")
tot = lambda k: sum(r[k] for r in page_rows)
pl += ['', f"**Totals (pages only):** testids={tot('testids')} onClick={tot('onClick')} forms={tot('forms')} fields={tot('fields')}"]
open(f'{OUT}/04_PAGE_MATRIX.md','w',encoding='utf-8').write('\n'.join(pl))

# component usage / dead code
all_src = ''.join(read(f) for f in glob.glob(f'{SRC}/**/*.js*', recursive=True))
comp_rows = []
for cp in comps:
    base = os.path.basename(cp).replace('.jsx','')
    refs = len(re.findall(r'\b'+re.escape(base)+r'\b', all_src)) - 1  # minus self
    comp_rows.append({'component': base, 'refs': max(refs,0), 'file': cp.replace(SRC+'/','')})
dead = [c for c in comp_rows if c['refs'] <= 0]
old_files = [c for c in comp_rows if c['component'].endswith('_old') or '_old' in c['file']]
cl = ['# 05_COMPONENT_MATRIX (static)', '', f'Total components: **{len(comps)}**',
      f'Likely-unused (0 external refs): **{len(dead)}**','',
      '## Likely-unused / dead components','']
for c in dead: cl.append(f"- {c['file']}")
open(f'{OUT}/05_COMPONENT_MATRIX.md','w',encoding='utf-8').write('\n'.join(cl))

# dead pages (not referenced in App.js and not *_old)
page_names = {os.path.basename(p).replace('.jsx','') for p in pages}
imported_pages = set(re.findall(r"import\s+(\w+)\s+from\s+['\"]\./pages/", app_js) + re.findall(r"import\s+(\w+)\s+from\s+['\"][^'\"]*pages/", app_js))
dead_pages = sorted(page_names - imported_pages)

# ---------- FE -> BE reverse map ----------
endpoints = json.load(open(f'{OUT}/endpoints.json', encoding='utf-8'))
be_norm = set()
for e in endpoints:
    p = e['path']
    be_norm.add(norm(p))
    # some routers already include /api in prefix; also add without double
be_norm_noparam = be_norm
matched = sorted(p for p in all_fe_paths if p in be_norm)
unmatched = sorted(p for p in all_fe_paths if p not in be_norm)
# fuzzy: unmatched but a BE path startswith it or vice versa
fuzzy = []
still = []
for p in unmatched:
    hit = next((b for b in be_norm if b.startswith(p) or p.startswith(b)), None)
    (fuzzy if hit else still).append(p)

ml = ['# FE→BE API RECONCILIATION (static)', '',
      f'Distinct FE /api paths: **{len(all_fe_paths)}** (pages only)',
      f'BE endpoints (normalized): **{len(be_norm)}**',
      f'Exact-matched: **{len(matched)}** · fuzzy-matched: **{len(fuzzy)}** · UNMATCHED (no BE endpoint found): **{len(still)}**','',
      '## UNMATCHED FE calls (potential dead/typo/missing endpoint)','']
for p in still: ml.append(f'- `{p}`')
open(f'{OUT}/FE_BE_RECONCILIATION.md','w',encoding='utf-8').write('\n'.join(ml))

summary = {
  'routes_declared': len(routes), 'redirects': len(nav_redirects),
  'pages': len(pages), 'dead_pages': dead_pages,
  'components': len(comps), 'likely_unused_components': len(dead),
  'page_testids_total': tot('testids'), 'page_onclick_total': tot('onClick'),
  'page_forms_total': tot('forms'), 'page_fields_total': tot('fields'),
  'fe_distinct_api_paths': len(all_fe_paths),
  'fe_be_matched': len(matched)+len(fuzzy), 'fe_be_unmatched': len(still),
  'unmatched_paths': still,
}
json.dump(summary, open(f'{OUT}/frontend_summary.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
