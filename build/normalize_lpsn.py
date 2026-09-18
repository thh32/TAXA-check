#!/usr/bin/env python3
"""Normalize LPSN API records with exact support for lpsn_* link fields."""
from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any

RAW=Path('output/lpsn_raw.jsonl')
OUT=Path('output/lpsn_normalized.json')
AUDIT=Path('output/lpsn_normalization_audit.json')
BLOCK={'species','sp','spp','genus','genera','family','families','order','class','phylum','domain','bacterium','bacteria','archaeon','archaea','organism','microorganism','microbe','strain','isolate','uncultured','unclassified','unknown','candidate','candidatus'}
DIRECT_LINK_KEYS={
 'record_lnk','lpsn_correct_name_id','correct_name_id',
 'lpsn_accepted_name_id','accepted_name_id',
 'lpsn_replacement_name_id','replacement_name_id',
 'correct_id','accepted_id','replacement_id'
}
CONTEXT_MARKERS=('correct_name','accepted_name','replacement_name','later_synonym')

def first(d:dict[str,Any],*keys:str,default:Any='')->Any:
 for key in keys:
  if isinstance(d,dict) and d.get(key) not in (None,'',[],{}):return d[key]
 return default

def text(value:Any)->str:
 if isinstance(value,dict):
  return text(first(value,'full_name','name','taxon_name','scientific_name','value','label','text'))
 return re.sub(r'\s+',' ',str(value or '')).strip()

def one_id(value:Any)->str:
 if isinstance(value,bool) or value is None:return ''
 if isinstance(value,int):return str(value)
 if isinstance(value,str):
  match=re.search(r'(?<!\d)-?\d+(?!\d)',value)
  return match.group(0) if match else ''
 if isinstance(value,list):
  for item in value:
   result=one_id(item)
   if result:return result
  return ''
 if isinstance(value,dict):return one_id(first(value,'id','record_no','lpsn_id','name_id','value'))
 return ''

def all_ids(value:Any)->list[str]:
 if isinstance(value,list):
  result=[]
  for item in value:
   candidate=one_id(item)
   if candidate and candidate not in result:result.append(candidate)
  return result
 candidate=one_id(value)
 return [candidate] if candidate else []

def collect_links(obj:Any,path:str='')->list[str]:
 result=[]
 if isinstance(obj,dict):
  for key,value in obj.items():
   low=key.lower().replace('-','_')
   child_path=f'{path}.{low}' if path else low
   contextual_id=low in {'id','record_no','lpsn_id','name_id'} and any(marker in path.lower() for marker in CONTEXT_MARKERS)
   if low in DIRECT_LINK_KEYS or contextual_id:
    for candidate in all_ids(value):
     if candidate not in result:result.append(candidate)
   for candidate in collect_links(value,child_path):
    if candidate not in result:result.append(candidate)
 elif isinstance(obj,list):
  for index,value in enumerate(obj):
   for candidate in collect_links(value,f'{path}[{index}]'):
    if candidate not in result:result.append(candidate)
 return result

def bad_name(name:str)->bool:
 parts=text(name).strip('"').lower().split()
 return len(parts)>1 and parts[1].rstrip('.') in BLOCK

def explicit_correct_name(record:dict[str,Any])->str:
 for key in ('correct_name','accepted_name','replacement_name','later_synonym','correct_name_data'):
  candidate=text(record.get(key))
  if candidate and not candidate.isdigit():return candidate
 return ''

def relations(record:dict[str,Any])->list[dict[str,Any]]:
 result=[]
 for key,label in [('synonyms','synonym'),('basonyms','basonym'),('correct_name','correct name'),('accepted_name','accepted name'),('replacement_name','replacement name')]:
  value=record.get(key);items=value if isinstance(value,list) else [value]
  for item in items:
   if item in (None,'',[],{}):continue
   result.append({'relation':label,'name':text(item),'id':one_id(item)})
 return result

def main()->None:
 if not RAW.exists():raise SystemExit(f'Missing {RAW}')
 rows=[];raw_by_id={};malformed=0;removed_self=0
 for line_number,line in enumerate(RAW.open(encoding='utf-8'),1):
  if not line.strip():continue
  try:record=json.loads(line)
  except json.JSONDecodeError:
   malformed+=1;continue
  own=one_id(first(record,'id','record_no','lpsn_id'))
  if own:raw_by_id[own]=record
  name=text(first(record,'full_name','taxon_name','scientific_name','name','monomial'))
  if not name or bad_name(name):continue
  links=[]
  for candidate in collect_links(record):
   if candidate==own:
    removed_self+=1
    continue
   if candidate not in links:links.append(candidate)
  record_lnk=one_id(record.get('record_lnk'))
  if record_lnk==own:record_lnk=''
  row={'name':name.strip('"'),'display_name':name,'rank':text(first(record,'category','rank','taxon_rank',default=record.get('_requested_rank',''))).lower(),'source':'LPSN','code':'ICNP/LPSN','record_no':own,'status':text(first(record,'lpsn_taxonomic_status','taxonomic_status','status')),'current_name':explicit_correct_name(record),'link_ids':links,'record_lnk':record_lnk,'validly_published':first(record,'validly_published','is_validly_published'),'classification':first(record,'classification','lineage',default=[]),'relations':relations(record),'raw':record}
  rows.append(row)
 OUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 by_id={row['record_no']:row for row in rows if row['record_no']}
 checks={}
 source=by_id.get('516940');target=by_id.get('516385')
 checks['516940_present']=source is not None
 checks['516385_present']=target is not None
 checks['516940_links_to_516385']=bool(source and '516385' in source['link_ids'])
 checks['516385_name_is_Prevotella']=bool(target and target['name']=='Prevotella')
 checks['516385_is_terminal_correct_name']=bool(target and target['status'].casefold()=='correct name' and '516385' not in target['link_ids'])
 audit={'normalized_records':len(rows),'malformed_lines':malformed,'records_with_external_links':sum(bool(x['link_ids'] or x['record_lnk']) for x in rows),'removed_self_links':removed_self,'xylanibacter_checks':checks}
 AUDIT.write_text(json.dumps(audit,indent=2),encoding='utf-8')
 print(f"Normalized LPSN: {len(rows)} records; external links: {audit['records_with_external_links']}; removed self-links: {removed_self}")
 print(json.dumps(checks,indent=2))
 if not all(checks.values()):raise SystemExit('LPSN Xylanibacter/Prevotella normalization validation failed')
if __name__=='__main__':main()
