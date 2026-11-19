#!/usr/bin/env python3
"""Courtyard area per block / side of netlist_v4_cup.json (KiCad python). Prints a markdown table."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bench", "tools"))
import pcbnew
import benchlib as bl
V010FP = os.path.join(HERE, "..", "footprints", "V010.pretty")
def load(lib, nm):
    if lib == "V010":
        return pcbnew.FootprintLoad(V010FP, nm)
    path = bl.BENCHFP if lib == "Bench" else os.path.join(bl.KL, lib + ".pretty")
    return pcbnew.FootprintLoad(path, nm)
parts = json.load(open(os.path.join(HERE, "..", "netlist_v4_cup.json")))
rows = {}
tot = {"F": 0, "B": 0}
for p in parts:
    f = load(*p["fp"])
    if f is None:
        print("missing fp", p["fp"]); continue
    f.BuildCourtyardCaches()
    c = f.GetCourtyard(pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False, False)
    w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
    # 0201 passives: courtyard of the KiCad lib is 0.3 mm larger than the body (fine for placement: add 0.1 gap)
    a = (w + 0.1) * (h + 0.1)
    p["_a"] = a; p["_w"] = w; p["_h"] = h
    k = (p["group"], p["side"])
    rows[k] = rows.get(k, 0) + a
    tot[p["side"]] += a
if __name__ == "__main__":
    json.dump({p["ref"]: [round(p["_w"], 2), round(p["_h"], 2), round(p["_a"], 2)] for p in parts}, open(os.path.join(HERE, "areas_v4.json"), "w"), indent=0)
    bg = {}
    for (g, s), a in rows.items():
        bg.setdefault(g, {"F": 0, "B": 0})[s] = a
    for g, d in sorted(bg.items(), key=lambda kv: -(kv[1]["F"] + kv[1]["B"])):
        print("| %s | %d | %d | %d |" % (g, round(d["F"]), round(d["B"]), round(d["F"] + d["B"])))
    print("TOTAL F %d B %d sum %d" % (tot["F"], tot["B"], tot["F"] + tot["B"]))
    big = sorted(parts, key=lambda p: -p["_a"])[:14]
    for p in big: print(p["ref"], p["value"][:28], round(p["_w"], 1), "x", round(p["_h"], 1), round(p["_a"], 1))
