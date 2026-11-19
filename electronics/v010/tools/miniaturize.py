#!/usr/bin/env python3
"""Minimum-area study from the real netlist (KiCad python). Prints scenario table; written to ../MINIATURIZATION.md by hand from this output."""
import json
import os

import pcbnew

KL = "/usr/share/kicad/footprints"
HERE = os.path.dirname(os.path.abspath(__file__))
parts = json.load(open(os.path.join(HERE, "..", "netlist.json")))


def area(lib, name, extra=None):
    fp = pcbnew.FootprintLoad((extra if extra else KL + "/" + lib + ".pretty"), name)
    c = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    return pcbnew.ToMM(c.GetWidth()) * pcbnew.ToMM(c.GetHeight())


BENCH = os.path.join(HERE, "..", "..", "bench", "footprints", "Bench.pretty")
V010 = os.path.join(HERE, "..", "footprints", "V010.pretty")
A = {}
tot = 0.0
cat = {}
for p in parts:
    if p["dnp"]:
        continue
    lib, name = p["fp"]
    key = (lib, name)
    if key not in A:
        A[key] = area(lib, name, BENCH if lib == "Bench" else V010 if lib == "V010" else None)
    a = A[key]
    c = "passive 0402/0603/0805" if lib in ("Resistor_SMD", "Capacitor_SMD") else "other"
    cat.setdefault(c, [0, 0.0])
    cat[c][0] += 1
    cat[c][1] += a
    tot += a
a0402 = area("Resistor_SMD", "R_0402_1005Metric")
a0201 = area("Resistor_SMD", "R_0201_0603Metric")
print("courtyard areas: 0402 %.2f  0201 %.2f mm2" % (a0402, a0201))
print("total (no DNP) %.0f mm2" % tot, {k: (v[0], round(v[1])) for k, v in cat.items()})
big = sorted(((A[(p["fp"][0], p["fp"][1])], p["ref"], p["value"]) for p in parts if not p["dnp"]), reverse=True)[:12]
for a, r, v in big:
    print("%6.1f %s %s" % (a, r, v))
