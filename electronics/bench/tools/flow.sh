#!/bin/bash
# usage: flow.sh controller|pod [passes]   build + route + pour + DRC   (macOS and Linux)
if [ -n "$KICAD_PY" ]; then PY="$KICAD_PY"
elif [ -x /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 ]; then PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
else PY=/usr/bin/python3; fi
cd "$(dirname "$0")/../$1" || exit 1
$PY -X faulthandler build_$1.py 2>&1 | grep -v "^\./src"
$PY ../tools/route.py $1.kicad_pcb prep 2>&1 | grep -v "^\./src" >/dev/null
$PY ../tools/route.py $1.kicad_pcb route ${2:-40} 2>&1 | grep -v "^\./src" >/dev/null
grep -i "session completed" $1.ses.log | sed 's/.*completed in/completed in/'
$PY ../tools/route.py $1.kicad_pcb import 2>&1 | grep -v "^\./src"
$PY ../tools/route.py $1.kicad_pcb finish 2>&1 | grep -v "^\./src"
$PY ../tools/route.py $1.kicad_pcb fix 2>&1 | grep -v "^\./src"
$PY ../tools/silkfix.py $1.kicad_pcb 2>&1 | grep "silk violations\|remaining"
../tools/chk.sh $1.kicad_pcb | head -20
