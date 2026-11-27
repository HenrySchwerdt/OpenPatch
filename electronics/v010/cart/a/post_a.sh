#!/bin/bash
# usage: post_a.sh routed.kicad_pcb name   (name = cart_a | cart_a6)
# After routing (flow + finish + hand fixes): duplicate vias out, starved thermals -> full connection, refill, DRC, netlist check,
# DEV / CLEAN variants, JLC packages (CPL rotation rule of ../README.md), pad-by-pad CPL verification. TEST PROJECT, water only.
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd $HERE
PY=../../board/kpy; K=$(command -v kicad-cli || echo /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli)
IN=$1; NAME=$2
# the DEV test-pad stubs are routed by finish_route_a.Router: it must see every copper layer of the board
# (the 4-layer board routes signals on In1 too: OP_IN1=1 makes the router respect them)
case $NAME in cart_a6*) export OP_LAYERS=6 ;; *) export OP_LAYERS=${OP_LAYERS:-4} OP_IN1=${OP_IN1:-1} ;; esac
[ "$IN" != "$NAME.kicad_pcb" ] && cp $IN $NAME.kicad_pcb && cp ${IN%.kicad_pcb}.kicad_pro $NAME.kicad_pro
$PY ../dedup_vias.py $NAME.kicad_pcb 2>&1 | grep -v "^\./src" || true
$K pcb drc --format json --severity-all --units mm -o _post_drc.json $NAME.kicad_pcb >/dev/null 2>&1
ST=$(python3 -c "
import json,re
d=json.load(open('_post_drc.json'))
out=set()
for v in d['violations']:
    if v['type']=='starved_thermal':
        for i in v['items']:
            m=re.match(r'Pad (\S+) \[GND\] of (\S+)',i['description'])
            if m: out.add('%s:%s'%(m.group(2),m.group(1)))
print(' '.join(sorted(out)))")
[ -n "$ST" ] && $PY ../zone_fix.py $NAME.kicad_pcb $ST 2>&1 | grep -v "^\./src"
$K pcb drc --format json --severity-all --units mm --all-track-errors -o ${NAME}_drc.json $NAME.kicad_pcb >/dev/null 2>&1
python3 - ${NAME}_drc.json <<'P'
import json,collections,sys
d=json.load(open(sys.argv[1]))
print('master DRC', dict(collections.Counter((v['severity'],v['type']) for v in d['violations'])), 'unconnected', len(d['unconnected_items']))
P
$PY check_board_netlist_a.py $NAME.kicad_pcb 2>&1 | grep -v "^\./src"
mkdir -p variants_$NAME
$PY variants_cart_a.py $NAME.kicad_pcb variants_$NAME 2>&1 | grep -v "^\./src"
for v in clean dev; do
  if [ "$NAME" != "cart_a" ]; then mv variants_$NAME/cart_a_$v.kicad_pcb variants_$NAME/${NAME}_$v.kicad_pcb; rm -f variants_$NAME/cart_a_$v.kicad_pro variants_$NAME/cart_a_$v.kicad_prl; fi
done
for v in clean dev; do
  cp $NAME.kicad_pro variants_$NAME/${NAME}_$v.kicad_pro
  $K pcb drc --format json --severity-all --units mm -o variants_$NAME/drc_$v.json variants_$NAME/${NAME}_$v.kicad_pcb >/dev/null 2>&1
  python3 - variants_$NAME/drc_$v.json $v <<'P'
import json,collections,sys
d=json.load(open(sys.argv[1]))
print(sys.argv[2], 'DRC', dict(collections.Counter((v['severity'],v['type']) for v in d['violations'] if v['severity']=='error')), 'unconnected', len(d['unconnected_items']))
P
done
if [ "$NAME" = "cart_a" ]; then OUTC=jlc; OUTD=jlc-dev; else OUTC=jlc-${NAME#cart_}; OUTD=jlc-${NAME#cart_}-dev; fi
python3 export_cart_a_jlc.py variants_$NAME/${NAME}_clean.kicad_pcb $OUTC
python3 export_cart_a_jlc.py variants_$NAME/${NAME}_dev.kicad_pcb $OUTD
$PY verify_cpl_a.py variants_$NAME/${NAME}_clean.kicad_pcb $OUTC 2>&1 | grep -v "^\./src"
$PY verify_cpl_a.py variants_$NAME/${NAME}_dev.kicad_pcb $OUTD 2>&1 | grep -v "^\./src"
rm -f _post_drc.json
