#!/bin/bash
# usage: flow_v3.sh main|power [passes]   build (done separately) + prep + route + import + finish + DRC summary
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=$HERE/kpy; export FREEROUTING_JAR=${FREEROUTING_JAR:-/Users/henryschwerdtner/dev/ai-insulin-pump/electronics/tools/freerouting-2.2.4.jar}
N=$1
cd $HERE/$N
$PY ../route_v3.py $N.kicad_pcb prep 2>&1 | grep -v "^\./src"
OP_PASSES=${2:-40} $PY ../route_v3.py $N.kicad_pcb route 2>&1 | grep -v "^\./src"
grep -i "completed\|unrouted\|incomplete" $N.ses.log | tail -3 | cut -c1-200
$PY ../route_v3.py $N.kicad_pcb import 2>&1 | grep -v "^\./src" | tail -1
$PY ../route_v3.py $N.kicad_pcb finish 2>&1 | grep -v "^\./src" | tail -2
$HERE/drc.sh $N
