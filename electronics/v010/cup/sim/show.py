"""Print the result JSONs compactly (helper for writing REPORT.md)."""
import json
import os
import sys

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load(n):
    return json.load(open(os.path.join(R, n)))


which = sys.argv[1]
if which == "1":
    d = load("case1.json")
    print(d["valid"])
    for k, m in d["grid"].items():
        if m.get("collapse"):
            print(k, "COLLAPSE pmax %.2f" % m["p_max_w"])
            continue
        print(k, *(round(m[x], 3) for x in ("t_boost_ms", "inrush_a", "vbat_min_boost", "dip_us_below_2v5", "vbat_min_motor", "icell_peak_motor", "vmot_ss", "p_max_w")))
    print(d["sweep"])
    for k, m in d["bulk"].items():
        print(k, {a: round(b, 3) for a, b in m.items() if isinstance(b, float) and a in ("inrush_a", "vpre_min_motor", "vpre_max_boost", "vbat_min_boost")})
elif which == "2":
    print(json.dumps(load("case2.json"), indent=0))
elif which == "3":
    d = load("case3.json")
    print(d["dc_pass"], d["chain_pass"])
    for sec in ("float_power", "faults"):
        for x in d[sec]:
            print(sec, x["name"], x.get("verdict"), round(x.get("vmot_max", -1), 2), round(x.get("allow_max", -1), 2), round(x.get("vpre_max", -1), 2), round(x.get("i_motor", -1), 2))
elif which == "4":
    d = load("case4.json")
    for sec in ("rates", "L", "rcoil"):
        for k, m in d[sec].items():
            print(sec, k, {a: round(b, 3) if isinstance(b, float) else b for a, b in m.items()})
