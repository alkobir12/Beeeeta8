"""READ-ONLY static discovery — KATRINA tools. Imports the tool registry and
dumps every registered tool with metadata. NO writes."""
import os, sys, json
sys.path.insert(0, '/app/backend')
os.chdir('/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
OUT = '/app/memory/discovery'
os.makedirs(OUT, exist_ok=True)

try:
    from core import tool_router
    tool_router._bootstrap()
    tools = tool_router.list_tools()
except Exception as e:
    tools = []
    print('IMPORT/LIST ERROR:', e)

lines = ['# 19_KATRINA_TOOL_MATRIX (static, from registry)', '',
         f'Total registered tools: **{len(tools)}**',
         f'Write-capable tools: **{sum(1 for t in tools if t.get("write"))}** '
         f'(require BOT_ALLOW_WRITES=1; env currently={os.environ.get("BOT_ALLOW_WRITES","unset")})','',
         '| tool | agent | sensitivity | write | params |','|---|---|---|---|---|']
for t in sorted(tools, key=lambda x: (x['agent'], x['name'])):
    params = ', '.join((t.get('params') or {}).keys())
    lines.append(f"| `{t['name']}` | {t['agent']} | {t['sensitivity']} | {'YES' if t.get('write') else 'no'} | {params} |")
# sensitivity counts
from collections import Counter
sens = Counter(t['sensitivity'] for t in tools)
lines += ['', '## Sensitivity distribution', ''] + [f'- {k}: {v}' for k,v in sens.items()]
open(f'{OUT}/19_KATRINA_TOOL_MATRIX.md','w',encoding='utf-8').write('\n'.join(lines))
with open(f'{OUT}/katrina_tools.json','w',encoding='utf-8') as fh:
    json.dump(tools, fh, ensure_ascii=False, indent=1)
print('katrina tools:', len(tools), '| write:', sum(1 for t in tools if t.get('write')))
print('sensitivity:', dict(sens))
