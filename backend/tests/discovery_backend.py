"""READ-ONLY static discovery — BACKEND. Parses every router via AST for
(method, path, function, auth-context, request param). Also inventories every
production write path. Writes evidence files to /app/memory/discovery/.
NO DB writes. NO mutation."""
import ast, os, re, json, glob

BE = '/app/backend'
OUT = '/app/memory/discovery'
os.makedirs(OUT, exist_ok=True)

PREFIX_RE = re.compile(r"APIRouter\(([^)]*)\)")
def router_prefixes(path):
    """Map local router var -> prefix string by scanning APIRouter(prefix=...)."""
    try:
        src = open(path, encoding='utf-8').read()
    except Exception:
        return {}
    prefixes = {}
    for m in re.finditer(r"(\w+)\s*=\s*APIRouter\(([^)]*)\)", src):
        var, args = m.group(1), m.group(2)
        pm = re.search(r"prefix\s*=\s*['\"]([^'\"]*)['\"]", args)
        prefixes[var] = pm.group(1) if pm else ""
    return prefixes

endpoints = []
files = sorted(glob.glob(f'{BE}/**/*.py', recursive=True))
for f in files:
    if '/tests/' in f or f.endswith('_test.py') or '/test_' in f:
        continue
    rel = f.replace(BE + '/', '')
    prefixes = router_prefixes(f)
    try:
        tree = ast.parse(open(f, encoding='utf-8').read())
    except Exception:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = [a.arg for a in node.args.args]
        has_request = 'request' in params or any('Request' in ast.dump(a) for a in node.args.args)
        has_depends = 'Depends(' in ast.get_source_segment(open(f,encoding='utf-8').read(), node) if False else False
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            fn = dec.func
            if isinstance(fn, ast.Attribute) and fn.attr in ('get','post','put','patch','delete'):
                method = fn.attr.upper()
                routervar = fn.value.id if isinstance(fn.value, ast.Attribute)==False and isinstance(fn.value, ast.Name) else getattr(fn.value,'attr','?')
                patharg = ''
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    patharg = dec.args[0].value
                prefix = prefixes.get(routervar, '')
                # api_router usually adds /api at include time in server.py; keep raw prefix
                full = (prefix or '') + (patharg or '')
                # dependencies in decorator
                dec_src = ''
                try:
                    dec_src = ast.get_source_segment(open(f,encoding='utf-8').read(), dec) or ''
                except Exception:
                    pass
                endpoints.append({
                    'method': method, 'path': full, 'router': routervar,
                    'func': node.name, 'file': rel,
                    'has_request_param': bool(has_request),
                    'dep_in_decorator': 'Depends(' in dec_src,
                })

# dedup
seen = set(); uniq = []
for e in endpoints:
    k = (e['method'], e['path'], e['func'], e['file'])
    if k in seen: continue
    seen.add(k); uniq.append(e)
uniq.sort(key=lambda x: (x['file'], x['path'], x['method']))

with open(f'{OUT}/endpoints.json','w',encoding='utf-8') as fh:
    json.dump(uniq, fh, ensure_ascii=False, indent=1)

# 09_API_INVENTORY.md
lines = ['# 09_API_INVENTORY (static, AST-extracted)', '', f'Total endpoints: **{len(uniq)}**', '']
by_file = {}
for e in uniq:
    by_file.setdefault(e['file'], []).append(e)
for fl in sorted(by_file):
    lines.append(f'## {fl}  ({len(by_file[fl])})')
    for e in by_file[fl]:
        flags = []
        if e['has_request_param']: flags.append('req')
        if e['dep_in_decorator']: flags.append('dep')
        lines.append(f"- `{e['method']:6}` `{e['path']}` → {e['func']}  [{','.join(flags) or '-'}]")
    lines.append('')
open(f'{OUT}/09_API_INVENTORY.md','w',encoding='utf-8').write('\n'.join(lines))

# ---- WRITE PATH INVENTORY ----
writes = []
WRITE_RE = re.compile(r"\.table\(['\"](\w+)['\"]\)\.(insert|update|upsert|delete)\b")
MONGO_RE = re.compile(r"\bdb\.(\w+)\.(insert_one|insert_many|update_one|update_many|delete_one|delete_many|replace_one|find_one_and_update|bulk_write)\b")
MONGO_RE2 = re.compile(r"\b_db\.(\w+)\.(insert_one|insert_many|update_one|update_many|delete_one|delete_many|replace_one|find_one_and_update)\b")
POST_ENTRY_RE = re.compile(r"\bpost_entry\(")
for f in files:
    rel = f.replace(BE + '/', '')
    is_script = rel.startswith('scripts/')
    try:
        src = open(f, encoding='utf-8').read()
    except Exception:
        continue
    for i, line in enumerate(src.splitlines(), 1):
        for m in WRITE_RE.finditer(line):
            writes.append({'file': rel, 'line': i, 'kind': 'supabase', 'table': m.group(1), 'op': m.group(2), 'script': is_script})
        for m in MONGO_RE.finditer(line):
            writes.append({'file': rel, 'line': i, 'kind': 'mongo', 'table': m.group(1), 'op': m.group(2), 'script': is_script})
        for m in MONGO_RE2.finditer(line):
            writes.append({'file': rel, 'line': i, 'kind': 'mongo', 'table': m.group(1), 'op': m.group(2), 'script': is_script})
        if POST_ENTRY_RE.search(line) and 'def post_entry' not in line:
            writes.append({'file': rel, 'line': i, 'kind': 'accounting_engine', 'table': 'journal_entries', 'op': 'post_entry', 'script': is_script})

# journal_entries direct writes NOT via accounting_engine == SSOT violation
je_direct = [w for w in writes if w['table']=='journal_entries' and w['kind']=='supabase' and 'accounting_engine' not in w['file']]
with open(f'{OUT}/writes.json','w',encoding='utf-8') as fh:
    json.dump(writes, fh, ensure_ascii=False, indent=1)

wl = ['# 42_WRITE_PATH_INVENTORY (static)', '', f'Total write call-sites: **{len(writes)}** (live routes + offline scripts)','']
wl.append(f'- Supabase writes: {sum(1 for w in writes if w["kind"]=="supabase")}')
wl.append(f'- Mongo writes: {sum(1 for w in writes if w["kind"]=="mongo")}')
wl.append(f'- post_entry (AccountingEngine) call-sites: {sum(1 for w in writes if w["kind"]=="accounting_engine")}')
wl.append(f'- **journal_entries DIRECT writes OUTSIDE accounting_engine: {len(je_direct)}**')
for w in je_direct:
    wl.append(f"   - {w['file']}:{w['line']} {w['op']} (script={w['script']})")
wl.append('')
# writes to financial tables from live (non-script) code
fin_tables = {'journal_entries','operations','accounts','vehicle_visits','invoices','transactions','business_accounts'}
wl.append('## Live (non-script) writes to financial/business tables by table')
agg = {}
for w in writes:
    if w['script']: continue
    agg.setdefault(w['table'], {}).setdefault(w['op'], 0)
    agg[w['table']][w['op']] += 1
for t in sorted(agg):
    ops = ', '.join(f"{k}={v}" for k,v in sorted(agg[t].items()))
    star = ' 💰' if t in fin_tables else ''
    wl.append(f"- **{t}**{star}: {ops}")
open(f'{OUT}/42_WRITE_PATH_INVENTORY.md','w',encoding='utf-8').write('\n'.join(wl))

print('endpoints:', len(uniq))
print('write call-sites:', len(writes), '| supabase', sum(1 for w in writes if w['kind']=='supabase'),
      '| mongo', sum(1 for w in writes if w['kind']=='mongo'), '| post_entry', sum(1 for w in writes if w['kind']=='accounting_engine'))
print('journal_entries DIRECT (non-engine):', len(je_direct), [w['file'] for w in je_direct])
