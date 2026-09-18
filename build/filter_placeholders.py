#!/usr/bin/env python3
"""Remove placeholder pseudo-taxa before compiling TAXA-check indexes."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path

PLACEHOLDER_EPITHETS = {
    'species','sp','spp','genus','genera','family','families','order','class',
    'phylum','domain','bacterium','bacteria','archaeon','archaea','organism',
    'microorganism','microbe','strain','isolate','uncultured','unclassified',
    'unknown','candidate','candidatus'
}

def bad(name: str) -> bool:
    parts=re.sub(r'\s+',' ',str(name or '')).strip().strip('"').lower().split()
    return len(parts)>1 and parts[1].rstrip('.') in PLACEHOLDER_EPITHETS

def main():
    p=argparse.ArgumentParser()
    p.add_argument('files',nargs='+',help='Normalized JSON arrays to clean in place')
    p.add_argument('--report',default='output/placeholder_filter_report.json')
    a=p.parse_args();report={}
    for filename in a.files:
        path=Path(filename)
        if not path.exists():continue
        rows=json.loads(path.read_text(encoding='utf-8'));kept=[];removed=[]
        for row in rows:
            (removed if bad(row.get('name','')) else kept).append(row)
        path.write_text(json.dumps(kept,ensure_ascii=False,indent=2),encoding='utf-8')
        report[str(path)]={'before':len(rows),'after':len(kept),'removed_count':len(removed),'removed_names':sorted({x.get('name','') for x in removed})}
        print(f'{path}: removed {len(removed)} placeholder pseudo-taxa')
    rp=Path(a.report);rp.parent.mkdir(parents=True,exist_ok=True);rp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
