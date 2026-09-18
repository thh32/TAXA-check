#!/usr/bin/env python3
import argparse,json,os,time
from getpass import getpass
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--email');p.add_argument('--output',default='output/lpsn_raw.jsonl');p.add_argument('--restart',action='store_true');a=p.parse_args()
out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
if a.restart:out.unlink(missing_ok=True)
email=a.email or input('LPSN email: ').strip();password=os.getenv('LPSN_PASSWORD') or getpass('LPSN password (hidden and not saved): ')
try: import lpsn
except ImportError: raise SystemExit('Install dependencies: python -m pip install -r requirements.txt')
client=lpsn.LpsnClient(email,password);password=''
seen=set()
if out.exists():
 for line in out.read_text(encoding='utf-8').splitlines():
  try:seen.add(str(json.loads(line).get('id')))
  except Exception:pass
ranks=['domain','phylum','class','order','family','genus','species','subspecies','variety','form']
with out.open('a',encoding='utf-8') as f:
 for rank in ranks:
  try:
   print(rank,client.search(category=rank))
   for item in client.retrieve():
    if isinstance(item,dict) and len(item)==1 and isinstance(next(iter(item.values())),dict):
     k,v=next(iter(item.items()));item=dict(v);item.setdefault('id',k)
    if not isinstance(item,dict):continue
    rid=str(item.get('id',item.get('record_no','')))
    if rid in seen:continue
    item['_requested_rank']=rank;f.write(json.dumps(item,ensure_ascii=False)+'\n');f.flush();seen.add(rid);time.sleep(.05)
  except Exception as e:print(f'WARNING: LPSN rank {rank} failed: {e}')
print('LPSN records:',len(seen))
