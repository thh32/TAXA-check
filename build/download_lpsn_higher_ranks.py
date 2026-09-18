#!/usr/bin/env python3
"""Retrieve all LPSN higher-rank records exposed by advanced and flexible search.

Fixes:
- never sends invalid validly_published=ICNP;
- treats the official client's KeyError('results') as an empty result set;
- unions advanced and flexible searches;
- preserves query provenance and audits incomplete rank coverage;
- never claims success merely because a category-only query returned records.
"""
from __future__ import annotations
import argparse,json,os,time
from getpass import getpass
from pathlib import Path
from typing import Any,Callable

DEFAULT_RANKS=['domain','kingdom','phylum','class','order','family']

def parse_args():
 p=argparse.ArgumentParser()
 p.add_argument('--email')
 p.add_argument('--raw',default='output/lpsn_raw.jsonl')
 p.add_argument('--audit',default='output/lpsn_higher_rank_completion.json')
 p.add_argument('--ranks',nargs='+',default=DEFAULT_RANKS)
 p.add_argument('--delay',type=float,default=.15)
 p.add_argument('--retries',type=int,default=3)
 return p.parse_args()

def rid(r):
 for k in ('id','record_no','lpsn_id'):
  if isinstance(r,dict) and r.get(k) not in (None,''):return str(r[k])
 return ''
def unpack(item):
 if not isinstance(item,dict):return []
 if len(item)==1:
  k,v=next(iter(item.items()))
  if isinstance(v,dict) and str(k).lstrip('-').isdigit():
   x=dict(v);x.setdefault('id',int(k));return [x]
 if item and all(str(k).lstrip('-').isdigit() and isinstance(v,dict) for k,v in item.items()):
  out=[]
  for k,v in item.items():x=dict(v);x.setdefault('id',int(k));out.append(x)
  return out
 return [item]
def existing_ids(path):
 out=set()
 if path.exists():
  for line in path.open(encoding='utf-8'):
   try:
    value=rid(json.loads(line))
    if value:out.add(value)
   except Exception:pass
 return out
def atomic(path,obj):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
def retrieve(client,prepare:Callable[[],Any],retries):
 last=None
 for attempt in range(1,retries+1):
  try:
   count=prepare();records=[]
   for item in client.retrieve():records.extend(unpack(item))
   return int(count or 0),records,None
  except KeyError as error:
   # lpsn 1.0.0 accesses response['results'] even when the API returns a
   # legitimate no-results object without that key.
   if str(error)=="'results'":return 0,[],None
   last=error
  except Exception as error:last=error
  if attempt<retries:time.sleep(min(20,2**attempt))
 return 0,[],repr(last)
def queries(client,rank):
 # Advanced endpoint. yes/no are the only valid values for validly_published.
 yield 'advanced:category',{'category':rank},lambda:client.search(category=rank)
 yield 'advanced:valid=yes',{'category':rank,'validly_published':'yes'},lambda:client.search(category=rank,validly_published='yes')
 yield 'advanced:valid=no',{'category':rank,'validly_published':'no'},lambda:client.search(category=rank,validly_published='no')
 yield 'advanced:correct=yes',{'category':rank,'correct_name':'yes'},lambda:client.search(category=rank,correct_name='yes')
 yield 'advanced:correct=no',{'category':rank,'correct_name':'no'},lambda:client.search(category=rank,correct_name='no')
 # Flexible endpoint searches record content and can include records omitted by
 # the advanced endpoint's nomenclatural filters.
 if hasattr(client,'flex_search'):
  yield 'flex:category',{'category':rank},lambda:client.flex_search(search={'category':rank},negate=False)
  yield 'flex:rank',{'rank':rank},lambda:client.flex_search(search={'rank':rank},negate=False)

def main():
 a=parse_args();raw=Path(a.raw);auditp=Path(a.audit);raw.parent.mkdir(parents=True,exist_ok=True)
 known=existing_ids(raw);email=a.email or input('LPSN email: ').strip();password=os.getenv('LPSN_PASSWORD') or getpass('LPSN password (hidden and not saved): ')
 try:import lpsn
 except ImportError:raise SystemExit('Install dependencies: python -m pip install -r requirements.txt')
 client=lpsn.LpsnClient(email,password);password=''
 audit={'initial_records':len(known),'ranks':{},'errors':[]};added_total=0
 with raw.open('a',encoding='utf-8') as handle:
  for rank in a.ranks:
   seen_rank=set();added_rank=0;stats=[]
   for method,params,prepare in queries(client,rank):
    count,records,error=retrieve(client,prepare,a.retries)
    stat={'method':method,'parameters':params,'reported_count':count,'returned_records':len(records),'error':error};stats.append(stat)
    if error:audit['errors'].append({'rank':rank,**stat});print(f'WARNING {rank} {method}: {error}');continue
    for record in records:
     record_id=rid(record)
     if not record_id:continue
     seen_rank.add(record_id)
     if record_id in known:continue
     record.setdefault('_requested_rank',rank);record.setdefault('_retrieval_method',method)
     handle.write(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n');handle.flush();known.add(record_id);added_rank+=1;added_total+=1
    print(f'{rank} {method}: {len(records)} records, {count} reported')
    time.sleep(a.delay)
   audit['ranks'][rank]={'unique_ids_seen':len(seen_rank),'new_records_added':added_rank,'queries':stats}
   atomic(auditp,audit);print(f'{rank}: union {len(seen_rank)}, added {added_rank}')
 audit.update({'final_records':len(known),'new_records_added':added_total});atomic(auditp,audit)
 print('Higher-rank completion added',added_total,'records');print('Audit:',auditp)
if __name__=='__main__':main()
