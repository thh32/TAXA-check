#!/usr/bin/env python3
"""Normalize full SeqCode detail records and emit a diagnostic field map."""
from __future__ import annotations
import argparse,json,re
from collections import Counter
from pathlib import Path

def clean(x):return re.sub(r'\s+',' ',str(x or '')).strip()

PLACEHOLDER_EPITHETS = {
    'species', 'sp', 'spp', 'genus', 'genera', 'family', 'families',
    'order', 'class', 'phylum', 'domain', 'bacterium', 'bacteria',
    'archaeon', 'archaea', 'organism', 'microorganism', 'microbe',
    'strain', 'isolate', 'uncultured', 'unclassified', 'unknown',
    'candidate', 'candidatus'
}

def has_placeholder_epithet(taxon_name):
    parts = clean(taxon_name).strip('\"').lower().split()
    if len(parts) < 2:
        return False
    # The second token is the species epithet in a binomial. Remove records such
    # as "Klebsiella species", "X genus", and "Y family" outright.
    epithet = parts[1].rstrip('.')
    return epithet in PLACEHOLDER_EPITHETS
def first(d,*ks,default=''):
 for k in ks:
  if isinstance(d,dict) and d.get(k) not in (None,'',[],{}):return d[k]
 return default
def text(x):
 if isinstance(x,str):return clean(x)
 if isinstance(x,(int,float,bool)):return str(x)
 if isinstance(x,dict):return text(first(x,'full_name','name','label','value','text','title'))
 return ''
def booltext(x):
 if isinstance(x,bool):return 'yes' if x else 'no'
 return text(x)
def rank(r):
 x=first(r,'rank','category','taxon_rank','taxonomic_rank','name_rank')
 if isinstance(x,dict):x=first(x,'name','label','value','rank')
 return text(x).lower()
def name(r):
 for k in ('full_name','name','taxon_name','scientific_name','proposed_name'):
  x=text(r.get(k))
  if x:return x
 return ''
def classification(r):
 c=first(r,'classification','taxonomy','lineage','taxonomic_classification',default=[]);out=[]
 if isinstance(c,dict):c=[{'rank':k,'name':v} for k,v in c.items()]
 if isinstance(c,list):
  for x in c:
   if isinstance(x,str):out.append({'rank':'','name':clean(x)})
   elif isinstance(x,dict):
    n=text(first(x,'name','full_name','taxon_name','label'));q=text(first(x,'rank','category','taxon_rank')).lower()
    if n:out.append({'rank':q,'name':n,'id':first(x,'id','name_id')})
 return out
def current(r):
 return text(first(r,'correct_name','accepted_name','current_name','replacement_name','later_synonym'))
def status(r):
 vals=[]
 for k in ('status','nomenclatural_status','publication_status','registration_status','state','status_name'):
  v=r.get(k)
  if isinstance(v,list):vals.extend(filter(None,map(text,v)))
  else:
   t=text(v)
   if t:vals.append(t)
 for k,label in [('is_validly_published','validly published'),('is_legitimate','legitimate'),('is_correct_name','correct name'),('is_registered','registered'),('is_endorsed','endorsed')]:
  if k in r:vals.append(f'{label}: {booltext(r[k])}')
 return '; '.join(dict.fromkeys(vals))
def validity(r):
 for k in ('validly_published','is_validly_published','publication_status','status'):
  if k in r:
   x=booltext(r[k]);
   if x:return x
 return ''
def relations(r):
 out=[]
 for k,label in [('basonym','basonym'),('basonyms','basonym'),('synonym','synonym'),('synonyms','synonym'),('correct_name','correct name'),('accepted_name','accepted name'),('replacement_name','replacement name'),('previous_names','previous name')]:
  v=r.get(k);vs=v if isinstance(v,list) else [v]
  for x in vs:
   n=text(x)
   if n:out.append({'relation':label,'name':n,'id':first(x,'id','name_id') if isinstance(x,dict) else ''})
 return out
def warnings(r):
 w=first(r,'qc_warnings','warnings','quality_control_warnings',default=[])
 return w if isinstance(w,list) else ([w] if w else [])
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',default='output/seqcode_names_raw.jsonl');p.add_argument('--output',default='output/seqcode_normalized.json');p.add_argument('--field-report',default='output/seqcode_field_report.json');a=p.parse_args();rows=[];fields=Counter()
 for line in Path(a.input).read_text(encoding='utf-8').splitlines():
  if not line.strip():continue
  r=json.loads(line);fields.update(r.keys());n=name(r)
  if not n or has_placeholder_epithet(n):continue
  rows.append({'name':n.strip('"'),'display_name':n,'rank':rank(r),'source':'SeqCode Registry','code':'SeqCode','record_no':first(r,'id','name_id'),'status':status(r),'current_name':current(r),'validly_published':validity(r),'classification':classification(r),'relations':relations(r),'qc_warnings':warnings(r),'nomenclatural_type':first(r,'nomenclatural_type','type'),'publication':first(r,'publication','effective_publication'),'raw':r})
 rows.sort(key=lambda x:(x['name'].casefold(),x['rank'],str(x['record_no'])))
 Path(a.output).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');Path(a.field_report).write_text(json.dumps(fields.most_common(),indent=2),encoding='utf-8')
 supplied=sum(bool(x['rank'] or x['status'] or x['validly_published']) for x in rows)
 print(f'Normalized {len(rows)} full SeqCode records; {supplied} include rank/status/validity data')
 if rows and supplied==0:raise SystemExit('SeqCode details were downloaded but no expected metadata fields were recognized. Upload seqcode_field_report.json and one redacted raw record for schema adjustment.')
if __name__=='__main__':main()
