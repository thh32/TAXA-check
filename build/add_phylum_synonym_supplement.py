#!/usr/bin/env python3
"""Upsert literature-derived historical phylum synonyms into normalized LPSN data.

Missing records are inserted. Existing LPSN phylum records are enriched rather
than skipped, ensuring every mapped historical name resolves to the current
phylum stated in the supplied IJSEM extract.
"""
from __future__ import annotations
import json
from pathlib import Path

NORMALIZED=Path('output/lpsn_normalized.json')
AUDIT=Path('output/phylum_synonym_supplement_audit.json')
PUBLICATION_DOI='10.1099/ijsem.0.005056'
PUBLICATION_URL='https://doi.org/10.1099/ijsem.0.005056'
SYNONYMS={
 'Acidobacteria':'Acidobacteriota','Actinobacteria':'Actinomycetota',
 'Aquificae':'Aquificota','Armatimonadetes':'Armatimonadota',
 'Firmacutes':'Bacillota','Firmicutes':'Bacillota',
 'Bacteroidetes':'Bacteroidota','Balneolaeota':'Balneolota',
 'Caldiserica':'Caldisericota','Calditrichaeota':'Calditrichota',
 'Epsilonbacteraeota':'Campylobacterota','Chlamydiae':'Chlamydiota',
 'Chlorobi':'Chlorobiota','Chloroflexi':'Chloroflexota',
 'Chrysiogenetes':'Chrysiogenota','Deferribacteres':'Deferribacterota',
 'Deinococcus-Thermus':'Deinococcota','Dictyoglomi':'Dictyoglomota',
 'Elusimicrobia':'Elusimicrobiota','Fibrobacteres':'Fibrobacterota',
 'Fusobacteria':'Fusobacteriota','Gemmatimonadetes':'Gemmatimonadota',
 'Ignavibacteriae':'Ignavibacteriota','Kiritimatiellaeota':'Kiritimatiellota',
 'Lentisphaerae':'Lentisphaerota','Tenericutes':'Mycoplasmatota',
 'Thaumarchaeota':'Nitrososphaerota','Nitrospinae':'Nitrospinota',
 'Nitrospirae':'Nitrospirota','Planctomycetes':'Planctomycetota',
 'Proteobacteria':'Pseudomonadota','Rhodothermaeota':'Rhodothermota',
 'Spirochaetes':'Spirochaetota','Synergistetes':'Synergistota',
 'Thermodesulfobacteria':'Thermodesulfobacteriota',
 'Thermomicrobia':'Thermomicrobiota','Crenarchaeota':'Thermoproteota',
 'Thermotogae':'Thermotogota','Verrucomicrobia':'Verrucomicrobiota'
}

def lpsn_url(name):return f'https://lpsn.dsmz.de/phylum/{name.lower()}'
def relation(current):return {'relation':'correct name','name':current,'id':'','source':'literature supplement'}
def inserted_record(old,current):
 return {'name':old,'display_name':f'“{old}”','rank':'phylum','source':'LPSN','code':'ICNP/LPSN','record_no':f'supplement:phylum:{old.lower()}','status':'effectively published or historical phylum name; superseded synonym','current_name':current,'correct_name':current,'link_ids':[],'record_lnk':'','validly_published':'not validly published under the ICNP','classification':[],'relations':[relation(current)],'source_url':lpsn_url(old),'publication_url':PUBLICATION_URL,'raw':{'supplemental_record':True,'publication_doi':PUBLICATION_DOI,'basis':'User-supplied IJSEM paper extract','current_name':current}}
def enrich(record,old,current):
 before={'status':record.get('status'),'current_name':record.get('current_name'),'correct_name':record.get('correct_name'),'source_url':record.get('source_url')}
 record['rank']='phylum';record['source']='LPSN';record['code']='ICNP/LPSN'
 status=str(record.get('status') or '').lower()
 if not any(x in status for x in ('synonym','superseded','not correct','no standing')):
  record['status']='effectively published or historical phylum name; superseded synonym'
 record['current_name']=current;record['correct_name']=current;record['source_url']=lpsn_url(old);record['publication_url']=PUBLICATION_URL
 rels=record.get('relations') if isinstance(record.get('relations'),list) else []
 rels=[r for r in rels if not (isinstance(r,dict) and str(r.get('relation','')).lower() in {'correct name','accepted name'})]
 rels.append(relation(current));record['relations']=rels
 raw=record.get('raw') if isinstance(record.get('raw'),dict) else {}
 raw.setdefault('supplemental_enrichment',{})
 raw['supplemental_enrichment'].update({'publication_doi':PUBLICATION_DOI,'basis':'User-supplied IJSEM paper extract','correct_name':current})
 record['raw']=raw
 return before

def main():
 if not NORMALIZED.exists():raise SystemExit(f'Missing {NORMALIZED}; run normalize_lpsn.py first')
 records=json.loads(NORMALIZED.read_text(encoding='utf-8'));lookup={}
 for i,r in enumerate(records):
  if str(r.get('source','')).casefold()=='lpsn' and str(r.get('rank','')).casefold()=='phylum':lookup.setdefault(str(r.get('name','')).casefold(),[]).append(i)
 inserted=[];updated=[]
 for old,current in SYNONYMS.items():
  indexes=lookup.get(old.casefold(),[])
  if not indexes:
   records.append(inserted_record(old,current));inserted.append(old);continue
  for i in indexes:
   before=enrich(records[i],old,current);updated.append({'name':old,'correct_name':current,'record_no':records[i].get('record_no'),'before':before})
 records.sort(key=lambda r:(str(r.get('name','')).casefold(),str(r.get('source','')),str(r.get('record_no',''))))
 NORMALIZED.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
 audit={'publication_doi':PUBLICATION_DOI,'mapping_count':len(SYNONYMS),'inserted_count':len(inserted),'updated_record_count':len(updated),'inserted':inserted,'updated':updated,'mapping':SYNONYMS}
 AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Inserted missing phylum synonyms:',len(inserted));print('Updated existing phylum records:',len(updated));print('Audit:',AUDIT)
if __name__=='__main__':main()
