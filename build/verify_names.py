#!/usr/bin/env python3
import json
from pathlib import Path
p=Path('extension/generated/names.json')
if not p.exists():raise SystemExit('Missing extension/generated/names.json')
data=json.loads(p.read_text(encoding='utf-8'))
for name in ('Firmicutes','Protisticellales'):
 row=data.get(name.casefold());print('\n'+name+':');print(json.dumps(row,ensure_ascii=False,indent=2))
 if not row:print('WARNING: absent from compiled data')
 elif not any(str(r).lower() in {'domain','realm','kingdom','subkingdom','phylum','subphylum','class','subclass','order','suborder','family','subfamily','tribe','subtribe','genus','subgenus'} for r in row.get('rank',[])):print('WARNING: present but rank is not a supported monomial rank')

for blocked_epithet in ("not", "assigned"):
    candidates = epithets.get(blocked_epithet, [])

    if candidates:
        raise SystemExit(
            f"FAILED: pseudo-epithet {blocked_epithet!r} "
            f"contains {len(candidates)} candidates"
        )

placeholder_names = [
    key
    for key in names
    if "not assigned to" in key.casefold()
]

if placeholder_names:
    raise SystemExit(
        "FAILED: classification placeholders remain in names.json: "
        + ", ".join(placeholder_names[:10])
    )

print("PASS: classification placeholders are absent")
