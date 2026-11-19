"""Measure the v010 fits quickly (no Monte Carlo): python3 quick_fits.py [F02 F03 ...]"""
import sys
from pathlib import Path

sys.path.insert(0, ".")
import check_assembly as CA

out = Path("out/v010")
rules, seq = CA.jload(CA.RULES_FILE), CA.jload(CA.seq_path(out))
M = CA.Model(out, "OP-100")
F = CA.Fits(M, rules, seq, "")
want = set(sys.argv[1:])
for f in seq["fits"]:
    if "id" not in f or (want and f["id"] not in want):
        continue
    if f["kind"] == "pilot":
        continue
    f = dict(f)
    f["hole"] = dict(f["hole"])
    f["shaft"] = dict(f["shaft"])
    f["hole"].setdefault("expect", "hole")
    f["shaft"].setdefault("expect", "shaft")
    at = f["at"]
    try:
        dh = F.measure(f["hole"], at)
        ds = F.measure(f["shaft"], f.get("at_shaft", at))
    except Exception as e:      # noqa: BLE001
        dh = ds = f"err {e}"
    print(f["id"], "at", [round(float(x), 2) for x in F.env.vec(at)], "hole", dh, "shaft", ds)
