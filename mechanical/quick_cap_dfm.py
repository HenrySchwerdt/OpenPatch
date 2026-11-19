"""Fast DFM loop of the fluid sandwich: python3 quick_cap_dfm.py  (builds end_cap / end_cap_lid alone, runs check_assembly.DFM.analyse on the STL)"""
import copy
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".")
import check_assembly as CA
import op_pod
from op_cap import build_cap
from op_cmds import Script
from op_dock import build_needle
from op_layout import find_cli

p = op_pod.prepare(json.load(open("params.json")))
if len(sys.argv) > 1:
    for kv in sys.argv[1:]:
        k, v = kv.split("=")
        node = p
        ks = k.split(".")
        for kk in ks[:-1]:
            node = node[kk]
        node[ks[-1]] = json.loads(v)
L = op_pod.layout(p, "OP-100")
L["geo"] = op_pod.geometry(p, L)
s = Script()
build_cap(s, p, L)
out = Path("/tmp/claude-0/-home-user-ai-insulin-pump/81d3c0e6-4bc1-5e65-bb19-a2d3a00bcb66/scratchpad/qc")
out.mkdir(exist_ok=True)
for nm in ("end_cap", "end_cap_lid"):
    s.export_stl(str(out / f"{nm}.stl"), [nm])
tmp = out / "s.json"
tmp.write_text(json.dumps(s.dumps()))
r = subprocess.run([find_cli(), "run", str(tmp), "--quiet"], capture_output=True, text=True)
if r.returncode:
    print(r.stdout[-300:], r.stderr[-300:])
    sys.exit(1)
rules = CA.jload(CA.RULES_FILE)
M = type("M", (), {})()
D = CA.DFM(M, rules, Path("out/v010"), "OP-100", n_samples=40000)
for nm in ("end_cap", "end_cap_lid"):
    rec = D.analyse({"name": nm, "file": out / f"{nm}.stl", "process": "SLA", "qty": 2, "kind": "order"})
    print(nm, "wall_min", round(rec.get("wall_min", -1), 3), "violations:")
    for v in rec.get("violations", []):
        if "FAIL" in str(v) or (isinstance(v, dict) and v.get("level") == "FAIL"):
            print("   ", str(v)[:230])
