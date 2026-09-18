#!/usr/bin/env python3
import json
from pathlib import Path
p=Path('extension/generated/names.json')
if not p.exists():raise SystemExit('Missing extension/generated/names.json')
data=json.loads(p.read_text(encoding='utf-8'))
for name in ('Firmicutes','Protisticellales'):
 row=data.get(name.casefold());print('\n'+name+':');print(json.dumps(row,ensure_ascii=False,indent=2))
 if not row:print('WARNING: absent from compiled data')
 elif not any(str(r).lower() in {'domain','realm','kingdom','subkingdom','phylum','subphylum','class','subclass','order','suborder','family','subfamily','tribe','subtribe','genus','subgenus'} for r in row.get('rank',[])):print('WARNING: present but rank is not a supported monomial rank')
