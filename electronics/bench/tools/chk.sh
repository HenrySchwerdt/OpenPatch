#!/bin/bash
# usage: chk.sh board.kicad_pcb  -> compact DRC summary + courtyard overlaps
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K pcb drc --format json --severity-all --units mm --all-track-errors -o /tmp/chk_$(basename $1).json "$1" >/dev/null 2>&1
python3 - "$1" <<'PY'
import json,collections
import sys,os
d=json.load(open('/tmp/chk_'+os.path.basename(sys.argv[1])+'.json'))
c=collections.Counter((v['severity'],v['type']) for v in d['violations'])
print(dict(c),'unconnected',len(d['unconnected_items']))
seen=set()
for v in d['violations']:
    if v['type'] in('courtyards_overlap','clearance','shorting_items','copper_edge_clearance','hole_clearance','pth_inside_courtyard','npth_inside_courtyard','solder_mask_bridge'):
        k=(v['type'],tuple(sorted(i['description'].split(' of ')[-1].split(' on ')[0] for i in v['items'])))
        if k in seen: continue
        seen.add(k); print(' ',v['type'][:12],k[1])
PY
