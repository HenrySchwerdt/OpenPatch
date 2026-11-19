#!/usr/bin/env python3
"""BOM cost and stock check from the JLCPCB parts API: writes ../fab/bom_prices.csv and ../COST.md (fee lines are ESTIMATES)."""
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jlcq

ROOT = os.path.join(HERE, "..")
PARTS = json.load(open(os.path.join(ROOT, "netlist.json")))
lines = collections.OrderedDict()
for p in PARTS:
    if not p["bom"] or not p["lcsc"]:
        continue
    k = p["lcsc"]
    lines.setdefault(k, dict(value=p["value"], fp=p["fp"][1], refs=[], mpn=p["mpn"]))["refs"].append(p["ref"])
rows = []
for code, l in lines.items():
    d = [x for x in jlcq.post(code, 5) if x["componentCode"] == code]
    d = d[0] if d else None
    price = d["componentPrices"][0]["productPrice"] if d and d.get("componentPrices") else None
    rows.append(dict(code=code, value=l["value"], qty=len(l["refs"]), refs=" ".join(l["refs"]), price=price, stock=d["stockCount"] if d else None,
                     basic=bool(d and d["componentLibraryType"] == "base"), found=bool(d)))
os.makedirs(os.path.join(ROOT, "fab"), exist_ok=True)
with open(os.path.join(ROOT, "fab", "bom_prices.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["LCSC", "Value", "Qty/board", "Unit USD (tier 1)", "JLC stock", "Basic", "Refs"])
    for r in rows:
        w.writerow([r["code"], r["value"], r["qty"], r["price"], r["stock"], "basic" if r["basic"] else "ext", r["refs"]])
tot = sum((r["price"] or 0) * r["qty"] for r in rows)
ext = [r for r in rows if not r["basic"]]
low = [r for r in rows if r["stock"] is not None and r["stock"] < 100]
nf = [r for r in rows if not r["found"]]
print("lines", len(rows), "components per board USD %.2f" % tot, "extended lines", len(ext), "low stock", [(r["code"], r["stock"]) for r in low], "not found", [r["code"] for r in nf])
json.dump(dict(total=tot, ext=len(ext), lines=len(rows), low=[(r["code"], r["stock"]) for r in low], nf=[r["code"] for r in nf],
               ext_total=sum((r["price"] or 0) * r["qty"] for r in ext)), open(os.path.join(ROOT, "fab", "cost.json"), "w"))
