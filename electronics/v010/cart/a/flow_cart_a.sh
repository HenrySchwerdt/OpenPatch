#!/bin/bash
# usage: flow_cart_a.sh [passes]  prep + Freerouting + import + finish + DRC summary for the cart A board (run after build_cart_a.py).
# Copy of ../flow_cart.sh (B). TEST PROJECT, water only.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd $HERE
PY=../../board/kpy; export FREEROUTING_JAR=${FREEROUTING_JAR:-$HERE/../../../tools/freerouting-2.2.4.jar}   # the 57 MB jar is not committed: set FREEROUTING_JAR
R=../../board/route_v3.py
B=${OP_BOARD:-cart_a.kicad_pcb}
if [ "${OP_IN1_SIGNAL:-0}" = 1 ]; then      # 4-layer lever: In1 a signal layer too (no GND plane in the DSN)
  $PY ../strip_zones.py $B 2>&1 | grep -v "^\./src\|leak"
  $PY prep_signal_a.py $B 2>&1 | grep -v "^\./src"
else
  $PY $R $B prep 2>&1 | grep -v "^\./src"
fi
S=${B%.kicad_pcb}.ses
# Freerouting directly, optimizer off, analytics and crash reports off (-da -dct), headless (2.2.4 opens a modal dialog with a display)
D=${B%.kicad_pcb}.dsn
( java -Djava.awt.headless=true -jar $FREEROUTING_JAR -de $D -do $S -mp ${1:-60} -mt ${OP_FR_THREADS:-1} --router.optimizer.enabled=false -da -dct > $S.log 2>&1 & echo $! > $S.pid; wait )

grep -i "completed\|unrouted\|incomplete" $S.log | tail -3 | cut -c1-200
$PY $R $B import 2>&1 | grep -v "^\./src" | tail -1
$PY $R $B finish 2>&1 | grep -v "^\./src" | tail -2
K=$(command -v kicad-cli || echo /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli)
J=${B%.kicad_pcb}_flowdrc.json
$K pcb drc --format json --severity-all --units mm --all-track-errors -o $J $B >/dev/null 2>&1
python3 - $J <<'P'
import json,collections,sys
d=json.load(open(sys.argv[1]))
c=collections.Counter((v['severity'],v['type']) for v in d['violations'] if v['severity']=='error')
print(dict(c),'unconnected',len(d['unconnected_items']))
P
