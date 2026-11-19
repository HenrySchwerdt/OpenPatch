#!/bin/bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
N=$1
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K pcb drc --format json --severity-all --units mm --all-track-errors -o /tmp/drc_$N.json $HERE/$N/$N.kicad_pcb >/dev/null 2>&1
python3 - $N <<'P'
import json,collections,sys
d=json.load(open('/tmp/drc_%s.json'%sys.argv[1]))
c=collections.Counter((v['severity'],v['type']) for v in d['violations'])
print(dict(c),'unconnected',len(d['unconnected_items']))
n=0
for v in d['violations']:
    if v['severity']=='error' and n<25:
        n+=1; print('  ',v['type'],[i['description'][:60] for i in v['items']])
P
