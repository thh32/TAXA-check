#!/usr/bin/env python3
import json,sys
from pathlib import Path
p=Path('extension/generated/names.json')
if not p.exists():raise SystemExit('Run merge_compile.py first')
data=json.loads(p.read_text(encoding='utf-8'))
expected={'Acidobacteria':'Acidobacteriota','Firmicutes':'Bacillota','Proteobacteria':'Pseudomonadota','Bacteroidetes':'Bacteroidota','Tenericutes':'Mycoplasmatota','Crenarchaeota':'Thermoproteota','Chloroflexi':'Chloroflexota','Planctomycetes':'Planctomycetota','Verrucomicrobia':'Verrucomicrobiota'}
fail=[]
for old,current in expected.items():
 row=data.get(old.casefold());hist=[] if not row else [h for h in row.get('history',[]) if h.get('source')=='LPSN']
 matching=[h for h in hist if h.get('superseded') and h.get('correct_name')==current]
 if not matching:fail.append({'name':old,'expected':current,'compiled':row});print(f'FAIL {old} -> {current}')
 else:print(f'PASS {old} -> {current}')
if fail:
 Path('output/phylum_supplement_verification_failures.json').write_text(json.dumps(fail,ensure_ascii=False,indent=2),encoding='utf-8')
 raise SystemExit(f'{len(fail)} phylum supplement checks failed')
print('PASS: representative phylum synonyms resolve correctly')
