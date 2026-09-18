#!/usr/bin/env python3
"""Propagate LoRN relevance from species/subspecies records to their genera.

Place in build/ and run after merge_compile.py and after any post-compilation
name deduplication. The script updates extension/generated/names.json in place.

This is generic. Every genus containing at least one LoRN-associated compiled
name receives a lorn_descendants summary used by the extension's green toggle.
"""
from __future__ import annotations
import argparse,json,re
from collections import defaultdict
from pathlib import Path
from typing import Any

LORN_STATUS=re.compile(r'(?:taxonomic(?:ally)?\s+suspend(?:ed|sion)|not\s+recommended\s+for\s+(?:human\s+or\s+veterinary\s+)?medical\s+use|recommended\s+for\s+(?:human\s+or\s+veterinary\s+)?medical\s+use|\bLoRN\b)',re.I)
DISPLACED=re.compile(r'(?:taxonomic(?:ally)?\s+suspend(?:ed|sion)|not\s+recommended\s+for\s+(?:human\s+or\s+veterinary\s+)?medical\s+use)',re.I)

def clean(v:Any)->str:return re.sub(r'\s+',' ',str(v or '')).strip()
def lpsn_lorn_histories(record:dict)->list[dict]:
 return [h for h in record.get('history',[]) if h.get('source')=='LPSN' and LORN_STATUS.search(clean(h.get('status')))]
def genus_of(name:str)->str:
 parts=clean(name).strip('"“”').split();return parts[0] if len(parts)>=2 else ''
def main():
 p=argparse.ArgumentParser();p.add_argument('--database',default='extension/generated/names.json');p.add_argument('--audit',default='output/lorn_genus_propagation.json');a=p.parse_args();dbp=Path(a.database)
 if not dbp.exists():raise SystemExit(f'Missing {dbp}; run merge_compile.py first')
 db=json.loads(dbp.read_text(encoding='utf-8'));by_genus=defaultdict(list)
 for record in db.values():
  genus=genus_of(record.get('name',''))
  if not genus:continue
  histories=lpsn_lorn_histories(record)
  if not histories:continue
  for h in histories:
   recommended=clean(h.get('correct_name') or h.get('current_name'))
   by_genus[genus.casefold()].append({'displayed_name':record.get('name'),'status':h.get('status'),'recommended_name':recommended,'recommended_genus':genus_of(recommended) if recommended else '','displaced':bool(DISPLACED.search(clean(h.get('status')))),'source_url':h.get('source_url','')})
 changed=[]
 for key,entries in by_genus.items():
  genus_record=db.get(key)
  if not genus_record or 'genus' not in [str(r).lower() for r in genus_record.get('rank',[])]:continue
  unique=[];seen=set()
  for e in entries:
   marker=(clean(e['displayed_name']).casefold(),clean(e['recommended_name']).casefold(),clean(e['status']).casefold())
   if marker in seen:continue
   seen.add(marker);unique.append(e)
  genus_record['lorn_descendants']=unique
  genus_record['lorn_medically_relevant']=True
  changed.append({'genus':genus_record.get('name'),'LoRN_descendant_count':len(unique),'recommended_genera':sorted({e['recommended_genus'] for e in unique if e['recommended_genus']})})
 dbp.write_text(json.dumps(db,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 audit=Path(a.audit);audit.parent.mkdir(parents=True,exist_ok=True);audit.write_text(json.dumps({'genera_updated':len(changed),'genera':changed},ensure_ascii=False,indent=2),encoding='utf-8')
 print('LoRN-relevant genera updated:',len(changed));print('Audit:',audit)
 seg=db.get('segatella')
 if seg:print('Segatella LoRN descendants:',len(seg.get('lorn_descendants',[])))
if __name__=='__main__':main()
