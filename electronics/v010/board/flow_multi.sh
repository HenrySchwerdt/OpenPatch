#!/bin/bash
# usage: flow_multi.sh name [passes]  (build + route + pour + DRC), KiCad python = /usr/bin/python3
PY=${KICAD_PY:-/usr/bin/python3}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$HERE/../../bench/tools/route.py"
cd "$HERE"
$PY build_multi.py $1 2>&1 | grep -v "^\./src" | tail -2
cd $1
$PY $R $1.kicad_pcb prep 2>&1 | grep -v "^\./src" >/dev/null
$PY $R $1.kicad_pcb route ${2:-20} 2>&1 | grep -v "^\./src" >/dev/null
grep -i "completed in" $1.ses.log | tail -1 | sed 's/.*Auto-router/Auto-router/' | cut -c1-200
for s in import finish fix; do $PY $R $1.kicad_pcb $s 2>&1 | grep -v "^\./src" | tail -1; done
kicad-cli pcb drc --format json --severity-all --units mm --all-track-errors -o /tmp/drc_$1.json $1.kicad_pcb >/dev/null 2>&1
python3 - $1 <<'P'
import json,collections,sys
d=json.load(open('/tmp/drc_%s.json'%sys.argv[1]))
print(dict(collections.Counter((v['severity'],v['type']) for v in d['violations'])),'unconnected',len(d['unconnected_items']))
for v in d['violations']:
    if v['severity']=='error': print('  ',v['type'],[i['description'][:50] for i in v['items']])
P
