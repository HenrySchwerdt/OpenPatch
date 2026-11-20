#!/usr/bin/env python3
"""Netlist <-> footprint pad check (KiCad python): every pin of netlist_v4_cup.json must exist as a pad of the footprint, and every pad must be either in the netlist
or listed as intentionally unconnected.  usage: python3 check_pins_vs_fp.py  (exit 1 on a problem)"""
import json
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..")
KL = os.environ.get("KICAD_FOOTPRINTS") or "/usr/share/kicad/footprints"
# pads that are deliberately not connected (module pins without a function, NC pins)
NC_OK = {"U1": None, "U6": {"3"}, "U30": {"9", "13"}, "U4A": {"3"}, "JU1": {"A8", "B8"}}


def load(lib, nm):
    if lib == "V010":
        path = os.path.join(R, "footprints", "V010.pretty")
    elif lib == "Bench":
        path = os.path.join(R, "..", "bench", "footprints", "Bench.pretty")
    else:
        path = os.path.join(KL, lib + ".pretty")
    return pcbnew.FootprintLoad(path, nm)


bad = 0
for p in json.load(open(os.path.join(R, "netlist_v4_cup.json"))):
    f = load(*p["fp"])
    if f is None:
        print("MISSING footprint", p["ref"], p["fp"]); bad += 1; continue
    pads = {pd.GetNumber() for pd in f.Pads() if pd.GetNumber()}
    pins = {str(k) for k, v in p["pins"].items() if v}
    nopin = {str(k) for k, v in p["pins"].items() if not v}
    for k in sorted(pins - pads):
        print("PIN WITHOUT PAD", p["ref"], k, p["fp"][1]); bad += 1
    ok = NC_OK.get(p["ref"], set())
    if ok is not None:
        for k in sorted(pads - pins - nopin - ok):
            print("PAD WITHOUT PIN", p["ref"], k, p["fp"][1]); bad += 1
print("pin/pad problems:", bad)
sys.exit(1 if bad else 0)
