#!/bin/bash
# usage: run_sa.sh iterations seeds...   -> placement_<seed>.json + sa_<seed>.log, picks the best HPWL with zero overlap into placement.json
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd $HERE
N=$1; shift
for s in "$@"; do
  ( sed "s#placement.json#placement_$s.json#" place_cup.py > _pc_$s.py; ../board/kpy _pc_$s.py $N $s 2>&1 | grep -v "^\./src" | tail -3 > sa_$s.log; rm -f _pc_$s.py ) &
done
wait
python3 - "$@" <<'P'
import sys,re
best=None
for s in sys.argv[1:]:
    t=open('sa_%s.log'%s).read()
    m=re.search(r'final hpwl ([\d.]+) overlap ([\d.]+)',t)
    print(s,m.groups() if m else t)
    if m and float(m.group(2))<0.01 and (best is None or float(m.group(1))<best[0]): best=(float(m.group(1)),s)
print('best',best)
if best:
    import shutil; shutil.copy('placement_%s.json'%best[1],'placement.json')
P
