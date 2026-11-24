#!/usr/bin/env bash
# Slice an STL for the Sovol SV01 Pro (0.4 nozzle, Titan direct drive, PLA) with CuraEngine from UltiMaker Cura.
# TEST ONLY - NOT FOR HUMAN USE (see ../../DISCLAIMER.md).
# usage: slice_sv01pro.sh <bed-layout.stl> <out.gcode>
# The STL must be laid out centred on the origin (CuraEngine adds the bed centre), e.g. from make_x2_housing.py.
set -euo pipefail
cd "$(dirname "$0")"; IN=$(cd "$(dirname "${1:?stl}")" && pwd)/$(basename "$1"); OUT=$(cd "$(dirname "${2:?gcode}")" && pwd)/$(basename "$2")
APP="/Applications/UltiMaker Cura.app/Contents"
ENGINE="$APP/Frameworks/CuraEngine"
RES="$APP/Resources/share/cura/resources"
export CURA_ENGINE_SEARCH_PATH="$RES/definitions:$RES/extruders"

# First-layer fixes (the usual SV01 Pro problems):
#  - fresh bed mesh on every print: heat the bed, then G29 (the stock start code only loads a mesh with M420 S1,
#    which does nothing if no G29 + M500 was ever saved), mesh fade over 10 mm
#  - thick, wide, slow first layer: 0.28 mm, 120 % line width, 15 mm/s, no fan, hotter nozzle/bed for the first layer
#  - 6 mm brim against corner lift; purge line kept
BED0=65; NOZ0=210  # first-layer temperatures (keep equal to sv01pro_pla_firstlayer.json)
START="M140 S$BED0 ; bed on
M104 S150 ; nozzle warm but not oozing during probing
M190 S$BED0 ; wait bed (probe the bed at print temperature)
G28 ; home
G29 ; probe a fresh bed mesh (adds about 2 min)
M420 S1 Z10 ; use the mesh, fade out over 10 mm
M109 S$NOZ0 ; wait nozzle
G92 E0
G1 Z2.0 F3000
G1 X10.1 Y20 Z0.28 F5000.0
G1 X10.1 Y200.0 Z0.28 F1500.0 E15 ; purge line 1
G1 X10.4 Y200.0 Z0.28 F5000.0
G1 X10.4 Y20 Z0.28 F1500.0 E30 ; purge line 2
G92 E0
G1 Z2.0 F3000"

OV=$(mktemp); python3 - "$OV" "$START" <<'PY'
import json,sys
d=json.load(open("sv01pro_pla_firstlayer.json"))
d["machine_start_gcode"]=sys.argv[2]
json.dump(d,open(sys.argv[1],"w"))
PY
ARGS=()
while IFS= read -r -d '' kv; do ARGS+=(-s "$kv"); done < <(python3 cura_resolve.py "$RES" sovol_sv01pro sovol_titan_extruder_0 "$OV")
rm -f "$OV"
"$ENGINE" slice -j "$RES/definitions/fdmprinter.def.json" "${ARGS[@]}" \
  -e0 -j "$RES/definitions/fdmextruder.def.json" "${ARGS[@]}" -s extruder_nr=0 \
  -l "$IN" -o "$OUT" > "${OUT%.gcode}.log" 2>&1
echo "written $OUT"
