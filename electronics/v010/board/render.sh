#!/bin/bash
# render.sh board.kicad_pcb out.png [layers]
K=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
L=${3:-F.Cu,F.Silkscreen,Edge.Cuts,F.Courtyard}
$K pcb export svg --layers $L --page-size-mode 2 --mode-single -o /tmp/_r.svg "$1" >/dev/null 2>&1
rsvg-convert -w ${4:-1200} -b white /tmp/_r.svg -o "$2"
