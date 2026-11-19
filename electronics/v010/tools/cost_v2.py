#!/usr/bin/env python3
"""BOM cost per board of the split design from the JLC parts API -> ../fab/cost_v2.json"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jlcq

ROOT = os.path.join(HERE, "..")
cache = {}
res = {}
alllines = {}
for name in ("main", "sensor", "usb"):
    parts = json.load(open(os.path.join(ROOT, "netlist_%s.json" % name)))
    lines = collections.OrderedDict()
    for p in parts:
        if p["bom"] and p["lcsc"]:
            lines.setdefault(p["lcsc"], []).append(p["ref"])
    tot, ext, low, rows = 0.0, 0, [], []
    for code, refs in lines.items():
        if code not in cache:
            d = [x for x in jlcq.post(code, 5) if x["componentCode"] == code]
            cache[code] = d[0] if d else None
        d = cache[code]
        price = d["componentPrices"][0]["productPrice"] if d and d.get("componentPrices") else 0
        tot += price * len(refs)
        if d and d["componentLibraryType"] != "base":
            ext += 1
        if d and d["stockCount"] < 100:
            low.append((code, d["stockCount"]))
        rows.append((code, len(refs), price, d["stockCount"] if d else None, "basic" if d and d["componentLibraryType"] == "base" else "ext"))
        alllines[code] = d["componentLibraryType"] if d else "?"
    res[name] = dict(lines=len(lines), placements=sum(len(r) for r in lines.values()), parts_usd=round(tot, 2), ext_lines=ext, low_stock=low, rows=rows)
res["ext_lines_total_unique"] = sum(1 for v in alllines.values() if v != "base")
json.dump(res, open(os.path.join(ROOT, "fab", "cost_v2.json"), "w"), indent=1)
for k, v in res.items():
    if isinstance(v, dict):
        print(k, {a: b for a, b in v.items() if a != "rows"})
print("unique extended lines over all boards:", res["ext_lines_total_unique"])
