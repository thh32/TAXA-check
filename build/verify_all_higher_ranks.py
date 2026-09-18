#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path
p=Path('output/lpsn_normalized.json')
if not p.exists():raise SystemExit('Run normalize_lpsn.py first')
rows=json.loads(p.read_text(encoding='utf-8'));ranks={'domain','kingdom','phylum','class','order','family'};allc=Counter();nonstanding=Counter();missing_targets=[]
for r in rows:
 rank=str(r.get('rank','')).lower()
 if rank not in ranks:continue
 allc[rank]+=1;status=str(r.get('status','')).lower();valid=str(r.get('validly_published','')).lower()
 if any(x in status for x in ('synonym','no standing','rejected','not correct')) or valid in ('','false','no','not validly published'):
  nonstanding[rank]+=1
  if ('synonym' in status or 'not correct' in status) and not r.get('current_name') and not r.get('link_ids'):missing_targets.append({'name':r.get('name'),'rank':rank,'status':r.get('status')})
print('Higher ranks:',dict(allc));print('Non-standing/synonym:',dict(nonstanding));print('Superseded without target link:',len(missing_targets))
firm=[r for r in rows if str(r.get('name','')).casefold()=='firmicutes' and str(r.get('rank','')).lower()=='phylum']
if not firm:
 raise SystemExit('INCOMPLETE: Firmicutes is absent, proving no-standing phylum coverage is still incomplete. Inspect output/lpsn_higher_rank_completion.json. Do not compile or publish this database as complete.')
print('Firmicutes:',json.dumps(firm[0],ensure_ascii=False,indent=2))
if nonstanding['phylum']==0:raise SystemExit('INCOMPLETE: no non-standing/synonym phyla retrieved')
print('PASS: no-standing higher-rank coverage regression checks passed')
