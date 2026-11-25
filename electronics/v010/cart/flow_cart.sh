#!/bin/bash
# usage: flow_cart.sh [passes]  prep + Freerouting (timeout OP_TIMEOUT s) + import + finish + DRC summary (run after build_cart.py)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd $HERE
PY=../board/kpy; export FREEROUTING_JAR=${FREEROUTING_JAR:-$HERE/../../tools/freerouting-2.2.4.jar}   # the 57 MB jar is not committed: set FREEROUTING_JAR
R=../board/route_v3.py
B=${OP_BOARD:-cart.kicad_pcb}
$PY $R $B prep 2>&1 | grep -v "^\./src"
S=${B%.kicad_pcb}.ses
# Freerouting directly, optimizer off, analytics and crash reports off (-da -dct), headless: with a display 2.2.4 opens a modal user-profile dialog after the routing passes and waits on it (no SES)
D=${B%.kicad_pcb}.dsn
( java -Djava.awt.headless=true -jar $FREEROUTING_JAR -de $D -do $S -mp ${1:-60} -mt ${OP_FR_THREADS:-1} --router.optimizer.enabled=false -da -dct > $S.log 2>&1 & echo $! > $S.pid; wait )

grep -i "completed\|unrouted\|incomplete" $S.log | tail -3 | cut -c1-200
$PY $R $B import 2>&1 | grep -v "^\./src" | tail -1
$PY $R $B finish 2>&1 | grep -v "^\./src" | tail -2
K=$(command -v kicad-cli || echo /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli)
$K pcb drc --format json --severity-all --units mm --all-track-errors -o drc.json $B >/dev/null 2>&1
python3 - <<'P'
import json,collections
d=json.load(open('drc.json'))
c=collections.Counter((v['severity'],v['type']) for v in d['violations'])
print(dict(c),'unconnected',len(d['unconnected_items']))
for v in [v for v in d['violations'] if v['severity']=='error'][:20]: print('  ',v['type'],[i['description'][:60] for i in v['items']])
P
