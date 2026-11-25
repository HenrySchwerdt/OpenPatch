#!/bin/bash
# usage: finish_cart.sh routed.kicad_pcb placed.kicad_pcb out.kicad_pcb [rr_rounds]
# after flow_cart.sh: strip the pours, A* for the open connections (finish_route.py), rip-up / re-route (rr_route.py --greedy),
# GND pours + stitching (route_v3 finish), DRC summary. Every board file gets the project file next to it (else KiCad DRC uses default rules).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd $HERE
PY=../board/kpy; K=$(command -v kicad-cli || echo /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli)
IN=$1; PL=$2; OUT=$3; export OP_LAYERS=${OP_LAYERS:-6}
cp $IN $OUT; cp ${IN%.kicad_pcb}.kicad_pro ${OUT%.kicad_pcb}.kicad_pro; cp ${IN%.kicad_pcb}.kicad_pro ${PL%.kicad_pcb}.kicad_pro 2>/dev/null
$PY strip_zones.py $OUT 2>&1 | grep -v "^\./src\|leak"
$K pcb drc --format json --severity-all --units mm -o ${OUT%.kicad_pcb}_drc0.json $OUT >/dev/null 2>&1
$PY finish_route.py $OUT ${OUT%.kicad_pcb}_drc0.json 2>&1 | grep -v "^\./src\|leak" | tail -1
OP_RR_PLATEAU=1 RR_JITTER=0.6 python3 rr_route.py --greedy $OUT $PL ${4:-6} 2>&1 | tail -2
$PY ../board/route_v3.py $OUT finish 2>&1 | grep -v "^\./src" | tail -1
$K pcb drc --format json --severity-all --units mm --all-track-errors -o ${OUT%.kicad_pcb}_drc.json $OUT >/dev/null 2>&1
python3 - ${OUT%.kicad_pcb}_drc.json <<'P'
import json,collections,sys
d=json.load(open(sys.argv[1]))
print(dict(collections.Counter((v['severity'],v['type']) for v in d['violations'] if v['severity']=='error')),'unconnected',len(d['unconnected_items']))
for u in d['unconnected_items']: print('  open',[i['description'][:55] for i in u['items']])
for v in [v for v in d['violations'] if v['severity']=='error']: print('  ',v['type'],[i['description'][:55] for i in v['items']])
P
