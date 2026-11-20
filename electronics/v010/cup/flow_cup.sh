#!/bin/bash
# usage: flow_cup.sh [passes]  prep + Freerouting + import + finish + DRC summary (run after build_cup.py)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd $HERE
PY=../board/kpy; export FREEROUTING_JAR=${FREEROUTING_JAR:-/Users/henryschwerdtner/dev/ai-insulin-pump/electronics/tools/freerouting-2.2.4.jar}
R=../board/route_v3.py
$PY $R cup.kicad_pcb prep 2>&1 | grep -v "^\./src"
OP_PASSES=${1:-40} $PY $R cup.kicad_pcb route 2>&1 | grep -v "^\./src"
grep -i "completed\|unrouted\|incomplete" cup.ses.log | tail -3 | cut -c1-200
$PY $R cup.kicad_pcb import 2>&1 | grep -v "^\./src" | tail -1
$PY $R cup.kicad_pcb finish 2>&1 | grep -v "^\./src" | tail -2
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$K pcb drc --format json --severity-all --units mm --all-track-errors -o drc.json cup.kicad_pcb >/dev/null 2>&1
python3 - <<'P'
import json,collections
d=json.load(open('drc.json'))
c=collections.Counter((v['severity'],v['type']) for v in d['violations'])
print(dict(c),'unconnected',len(d['unconnected_items']))
for v in [v for v in d['violations'] if v['severity']=='error'][:20]: print('  ',v['type'],[i['description'][:60] for i in v['items']])
P
