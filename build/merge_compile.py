#!/usr/bin/env python3
"""Compile dual-code names with terminal-record and self-link-safe resolution."""
from __future__ import annotations
import json,re
from collections import defaultdict
from pathlib import Path

BLOCK={'species','sp','spp','genus','genera','family','families','order','class','phylum','domain','bacterium','bacteria','archaeon','archaea','organism','microorganism','microbe','strain','isolate','uncultured','unclassified','unknown','candidate','candidatus'}
SUPERSEDED=('synonym','superseded','rejected','illegitimate','not correct name','replaced by','replacement name required')
CURRENT=('correct name','accepted name','valid (icnp)','valid name','current name')

def load(path):
    p=Path(path);return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
def text(v):
    if isinstance(v,dict):
        for key in ('full_name','name','taxon_name','scientific_name','value','label','text'):
            if v.get(key) not in (None,'',[],{}): return text(v[key])
        return ''
    return re.sub(r'\s+',' ',str(v or '')).strip()
def ident(v): return str(v).strip() if v not in (None,'') else ''
def bad(name):
    parts=text(name).strip('"').lower().split();return len(parts)>1 and parts[1].rstrip('.') in BLOCK

def normalize_seq(row):
    raw=row.get('raw') if isinstance(row.get('raw'),dict) else row
    links=[]
    own=ident(row.get('record_no',row.get('id')))
    for key in ('correct_name_id','accepted_name_id','replacement_name_id','record_lnk'):
        value=ident(row.get(key) or raw.get(key))
        if value and value!=own and value not in links: links.append(value)
    return {'name':text(row.get('name') or row.get('full_name')).strip('"'),'display_name':text(row.get('display_name') or row.get('name')),'rank':text(row.get('rank')).lower(),'source':'SeqCode Registry','code':'SeqCode','record_no':own,'status':text(row.get('status')),'current_name':text(row.get('current_name') or row.get('accepted_name') or row.get('correct_name') or row.get('replacement_name')),'link_ids':links,'record_lnk':'','validly_published':row.get('validly_published'),'classification':row.get('classification',[]),'relations':row.get('relations',row.get('history',[])),'qc_warnings':row.get('qc_warnings',[]),'raw':raw}

def status_current(row):
    status=text(row.get('status')).lower()
    return any(word in status for word in CURRENT) and not any(word in status for word in SUPERSEDED)
def source_superseded(row):
    status=text(row.get('status')).lower();current=text(row.get('current_name'))
    if status_current(row): return False
    return any(word in status for word in SUPERSEDED) or bool(current and current.casefold()!=row['name'].casefold()) or bool(row.get('record_lnk'))
def relation_target(row):
    for rel in row.get('relations',[]):
        if not isinstance(rel,dict): continue
        kind=text(rel.get('relation') or rel.get('type') or rel.get('relationship')).lower()
        if any(word in kind for word in ('correct','accepted','replacement','later synonym')):
            name=text(rel.get('name') or rel.get('full_name') or rel.get('taxon_name'))
            rid=ident(rel.get('id') or rel.get('record_no') or rel.get('name_id'))
            if name:return name,''
            if rid:return '',rid
    return '',''

def resolve(rows):
    lookup={(row['source'],ident(row.get('record_no'))):row for row in rows if ident(row.get('record_no'))}
    def terminal_name(candidate):
        # A record explicitly designated as the correct/accepted/current name is
        # terminal even if its API object contains a self-pointing correct_name_id.
        if status_current(candidate): return candidate['name']
        own=ident(candidate.get('record_no'))
        outgoing=[ident(x) for x in candidate.get('link_ids',[]) if ident(x) and ident(x)!=own]
        record_lnk=ident(candidate.get('record_lnk'))
        if record_lnk and record_lnk!=own:outgoing.append(record_lnk)
        if not outgoing and not source_superseded(candidate):return candidate['name']
        return ''
    def target(row):
        direct=text(row.get('current_name'))
        if direct and direct.casefold()!=row['name'].casefold():return direct
        rel_name,rel_id=relation_target(row)
        if rel_name:return rel_name
        own=ident(row.get('record_no'));queue=[]
        queue.extend(ident(x) for x in row.get('link_ids',[]) if ident(x) and ident(x)!=own)
        record_lnk=ident(row.get('record_lnk'))
        if record_lnk and record_lnk!=own:queue.append(record_lnk)
        if rel_id and rel_id!=own:queue.append(rel_id)
        seen=set()
        while queue and len(seen)<50:
            rid=queue.pop(0);key=(row['source'],rid)
            if key in seen:continue
            seen.add(key);candidate=lookup.get(key)
            if not candidate:continue
            terminal=terminal_name(candidate)
            if terminal:return terminal
            direct=text(candidate.get('current_name'))
            if direct and direct.casefold()!=candidate['name'].casefold():return direct
            rel_name,next_rel_id=relation_target(candidate)
            if rel_name:return rel_name
            candidate_own=ident(candidate.get('record_no'))
            queue.extend(ident(x) for x in candidate.get('link_ids',[]) if ident(x) and ident(x)!=candidate_own)
            nxt=ident(candidate.get('record_lnk'))
            if nxt and nxt!=candidate_own:queue.append(nxt)
            if next_rel_id and next_rel_id!=candidate_own:queue.append(next_rel_id)
        return ''
    for row in rows:
        row['superseded']=source_superseded(row)
        row['correct_name']=(text(row.get('correct_name') or row.get('current_name')) or target(row)) if row['superseded'] else ''
    return rows


def seqcode_is_valid(row):
    if row.get("source") != "SeqCode Registry": return False
    status=text(row.get("status")).casefold()
    validity=str(row.get("validly_published", "")).casefold()
    return ("valid (seqcode)" in status or "validly published under the seqcode" in status or validity in {"true","yes","seqcode"})


def record_url(row):
    explicit=text(row.get("source_url") or row.get("url"))
    if explicit:return explicit
    rid=ident(row.get("record_no"))
    if row.get("source")=="SeqCode Registry" and rid and rid.isdigit():return f"https://registry.seqco.de/names/{rid}"
    if row.get("source")=="LPSN" and rid and rid.isdigit():return f"https://doi.org/10.83108/rn.{rid}"
    return ""

def main():
    lpsn=load('output/lpsn_normalized.json');seq=[normalize_seq(x) for x in load('output/seqcode_normalized.json')]
    rows=resolve([x for x in lpsn+seq if x.get('name') and not bad(x['name'])]);groups=defaultdict(list)
    for row in rows:
        row['source_url']=record_url(row)
        groups[row['name'].casefold()].append(row)
    def state(items):
        ranks={x['rank'] for x in items if x['rank']};correct={x['correct_name'].casefold() for x in items if x['superseded'] and x['correct_name']}
        if len(ranks)>1 or len(correct)>1:return 'conflict'
        if any(x['superseded'] for x in items):return 'superseded'
        if len({x['source'] for x in items})>1:return 'both'
        return ('seqcode' if any(seqcode_is_valid(x) for x in items) else 'seqcode-unverified') if items[0]['source']=='SeqCode Registry' else 'lpsn'
    index={};epithet=defaultdict(list);unresolved=[]
    for key,items in groups.items():
        history=[{q:x.get(q) for q in ('source','code','record_no','display_name','rank','status','correct_name','superseded','validly_published','classification','relations','qc_warnings','source_url')} for x in items]
        for x in items:
            if x['superseded'] and not x['correct_name']:unresolved.append({'name':x['name'],'source':x['source'],'record_no':x['record_no'],'status':x['status'],'link_ids':x.get('link_ids',[]),'record_lnk':x.get('record_lnk','')})
        index[key]={'name':items[0]['name'],'state':state(items),'rank':sorted({x['rank'] for x in items if x['rank']}),'history':history}
        parts=key.split()
        if len(parts)>1 and parts[1].rstrip('.') not in BLOCK:epithet[parts[1]].append(key)
    out=Path('extension/generated');out.mkdir(parents=True,exist_ok=True)
    (out/'names.json').write_text(json.dumps(index,ensure_ascii=False,separators=(',',':')),encoding='utf-8');(out/'epithets.json').write_text(json.dumps(epithet,ensure_ascii=False,separators=(',',':')),encoding='utf-8');(out/'metadata.json').write_text(json.dumps({'written_names':len(index),'lpsn_records':len(lpsn),'seqcode_records':len(seq),'superseded_records':sum(x['superseded'] for x in rows),'unresolved_superseded_records':len(unresolved)},indent=2),encoding='utf-8');Path('output/unresolved_correct_names.json').write_text(json.dumps(unresolved,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Compiled written names:',len(index));print('Unresolved superseded records:',len(unresolved))
if __name__=='__main__':main()
