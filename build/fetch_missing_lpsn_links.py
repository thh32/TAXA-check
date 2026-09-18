#!/usr/bin/env python3
"""Fetch all LPSN records referenced by downloaded records but not yet present.

The rank searches do not necessarily return every target record referenced by
correct-name, accepted-name, replacement-name, or record-link fields. This
script closes that graph recursively using the official LPSN client.
"""
from __future__ import annotations
import argparse,json,os,re,time
from getpass import getpass
from pathlib import Path
from typing import Any

LINK_KEY_EXACT={
 'record_lnk','correct_name_id','accepted_name_id','replacement_name_id',
 'correct_id','accepted_id','replacement_id','basonym_id','homotypic_synonym_id'
}
LINK_KEY_SUFFIXES=('_id','_ids')
LINK_HINTS=('correct','accepted','replacement','synonym','basonym','record_lnk')
SELF_ID_KEYS={'id','record_no','lpsn_id'}

def args():
 p=argparse.ArgumentParser()
 p.add_argument('--email')
 p.add_argument('--raw',default='output/lpsn_raw.jsonl')
 p.add_argument('--audit',default='output/lpsn_link_completion.json')
 p.add_argument('--batch-size',type=int,default=100)
 p.add_argument('--max-rounds',type=int,default=20)
 p.add_argument('--delay',type=float,default=.2)
 p.add_argument('--retries',type=int,default=4)
 return p.parse_args()

def scalar_ids(value:Any)->set[str]:
 out=set()
 if isinstance(value,bool) or value is None:return out
 if isinstance(value,int):out.add(str(value))
 elif isinstance(value,str):
  for token in re.findall(r'(?<!\d)-?\d+(?!\d)',value):out.add(token)
 elif isinstance(value,list):
  for x in value:out.update(scalar_ids(x))
 elif isinstance(value,dict):
  for k in ('id','record_no','lpsn_id','name_id','value'):out.update(scalar_ids(value.get(k)))
 return {x for x in out if x not in {'','0'}}

def own_id(record):
 for k in ('id','record_no','lpsn_id'):
  values=scalar_ids(record.get(k))
  if values:return sorted(values)[0]
 return ''

def linked_ids(obj:Any,path='')->set[str]:
 out=set()
 if isinstance(obj,dict):
  for key,value in obj.items():
   low=key.lower().replace('-','_')
   # Do not reinterpret each record's own top-level identifier as a link.
   is_top_self=(not path and low in SELF_ID_KEYS)
   context=(f'{path}.{low}' if path else low).lower()
   # An ordinary nested key named `id` is a relationship target when its parent
   # path contains correct_name, accepted_name, replacement, synonym, or basonym.
   contextual_id=(low in SELF_ID_KEYS or low.endswith(LINK_KEY_SUFFIXES)) and any(h in context for h in LINK_HINTS)
   is_link=(low in LINK_KEY_EXACT) or contextual_id or (low.endswith(LINK_KEY_SUFFIXES) and any(h in low for h in LINK_HINTS))
   if is_link and not is_top_self:out.update(scalar_ids(value))
   out.update(linked_ids(value,context))
 elif isinstance(obj,list):
  for i,value in enumerate(obj):out.update(linked_ids(value,f'{path}[{i}]'))
 return out

def load_raw(path:Path):
 records={};malformed=0
 if not path.exists():return records,malformed
 for line in path.read_text(encoding='utf-8').splitlines():
  if not line.strip():continue
  try:r=json.loads(line)
  except json.JSONDecodeError:malformed+=1;continue
  rid=own_id(r)
  if rid:records[rid]=r
 return records,malformed

def chunks(values,n):
 values=list(values)
 for i in range(0,len(values),n):yield values[i:i+n]

def unpack(item):
 if not isinstance(item,dict):return []
 if len(item)==1:
  key,value=next(iter(item.items()))
  if isinstance(value,dict) and str(key).lstrip('-').isdigit():
   record=dict(value);record.setdefault('id',int(key));return [record]
 # Some client versions return several ID->record pairs in one dict.
 if item and all(str(k).lstrip('-').isdigit() and isinstance(v,dict) for k,v in item.items()):
  out=[]
  for key,value in item.items():
   record=dict(value);record.setdefault('id',int(key));out.append(record)
  return out
 return [item]

def fetch_batch(client,batch,retries):
 last=None
 for attempt in range(1,retries+1):
  try:
   client.search(id=batch)
   records=[]
   for item in client.retrieve():records.extend(unpack(item))
   return records,None
  except Exception as error:
   last=error
   if attempt<retries:time.sleep(min(30,2**attempt))
 return [],repr(last)

def atomic(path,value):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8');tmp.replace(path)

def main():
 a=args();raw=Path(a.raw);auditp=Path(a.audit);raw.parent.mkdir(parents=True,exist_ok=True)
 records,malformed=load_raw(raw)
 email=a.email or input('LPSN email: ').strip();password=os.getenv('LPSN_PASSWORD') or getpass('LPSN password (hidden and not saved): ')
 try:import lpsn
 except ImportError:raise SystemExit('Install dependencies: python -m pip install -r requirements.txt')
 client=lpsn.LpsnClient(email,password);password=''
 audit={'initial_records':len(records),'malformed_lines':malformed,'rounds':[],'failed_ids':{}}
 with raw.open('a',encoding='utf-8') as handle:
  for round_no in range(1,a.max_rounds+1):
   referenced=set()
   for record in records.values():referenced.update(linked_ids(record))
   missing=sorted(referenced-set(records),key=lambda x:int(x) if x.lstrip('-').isdigit() else x)
   info={'round':round_no,'referenced_ids':len(referenced),'missing_before':len(missing),'requested':0,'added':0,'still_missing':0}
   if not missing:
    audit['rounds'].append(info);break
   print(f'Link completion round {round_no}: {len(missing)} missing target records')
   for batch in chunks(missing,a.batch_size):
    info['requested']+=len(batch);fetched,error=fetch_batch(client,batch,a.retries)
    if error:
     for rid in batch:audit['failed_ids'][rid]=error
     continue
    returned=set()
    for record in fetched:
     rid=own_id(record)
     if not rid:continue
     returned.add(rid)
     if rid not in records:
      handle.write(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n');handle.flush();records[rid]=record;info['added']+=1
    for rid in set(batch)-returned:audit['failed_ids'][rid]='API returned no record for requested ID'
    time.sleep(a.delay)
   referenced_after=set()
   for record in records.values():referenced_after.update(linked_ids(record))
   info['still_missing']=len(referenced_after-set(records));audit['rounds'].append(info);atomic(auditp,audit)
   print(f"Added {info['added']}; still missing {info['still_missing']}")
   if info['added']==0:break
 audit['final_records']=len(records);audit['completed_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());atomic(auditp,audit)
 print(f'LPSN link completion finished with {len(records)} records')
 print('Audit:',auditp)
if __name__=='__main__':main()
