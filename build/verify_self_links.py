#!/usr/bin/env python3
import json
from pathlib import Path
rows=json.loads(Path('output/lpsn_normalized.json').read_text(encoding='utf-8'))
self_links=[]
for row in rows:
 own=str(row.get('record_no',''))
 if own and (own in set(map(str,row.get('link_ids',[]))) or str(row.get('record_lnk',''))==own):self_links.append({'name':row.get('name'),'record_no':own})
print('Self-linked normalized records:',len(self_links))
if self_links:raise SystemExit(json.dumps(self_links[:20],indent=2))
