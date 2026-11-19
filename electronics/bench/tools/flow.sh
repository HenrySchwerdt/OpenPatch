#!/bin/bash
# usage: flow.sh controller|pod [passes]   build + route + pour + DRC
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
cd "$(dirname "$0")/../$1" || exit 1
$PY -X faulthandler build_$1.py 2>&1 | grep -v "^\./src"
$PY ../tools/route.py $1.kicad_pcb prep 2>&1 | grep -v "^\./src" >/dev/null
$PY ../tools/route.py $1.kicad_pcb route ${2:-40} 2>&1 | grep -v "^\./src" >/dev/null
grep -i "session completed" $1.ses.log | sed 's/.*completed in/completed in/'
$PY ../tools/route.py $1.kicad_pcb import 2>&1 | grep -v "^\./src"
$PY ../tools/route.py $1.kicad_pcb finish 2>&1 | grep -v "^\./src"
../tools/chk.sh $1.kicad_pcb | head -20
