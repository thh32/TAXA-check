#!/usr/bin/env python3
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--name',default='Xylanibacter');p.add_argument('--names',default='extension/generated/names.json');a=p.parse_args()
data=json.loads(Path(a.names).read_text(encoding='utf-8'));x=data.get(a.name.casefold())
if not x:raise SystemExit(f'{a.name!r} not present in names database')
print(json.dumps(x,ensure_ascii=False,indent=2))
unresolved=[h for h in x.get('history',[]) if h.get('superseded') and not h.get('correct_name')]
if unresolved:raise SystemExit(f'FAILED: {len(unresolved)} superseded source records remain unresolved for {a.name}')
print('PASS: all superseded source records resolve for',a.name)
