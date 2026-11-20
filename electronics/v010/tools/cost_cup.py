#!/usr/bin/env python3
"""Parts cost of the CUP board from cup/jlc_stock_2026-11-20.json (live JLC parts API snapshot) and cup/jlc/BOM-jlcpcb.csv.  usage: python3 cost_cup.py [boards=5]
Prints a markdown table (used for cup/COST.md): per-line quantity, tier unit price, stock, basic/extended, and the totals."""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CUP = os.path.join(HERE, "..", "cup")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
stock = json.load(open(os.path.join(CUP, "jlc_stock_2026-11-20.json")))
rows = list(csv.DictReader(open(os.path.join(CUP, "jlc", "BOM-jlcpcb.csv"))))
tot, ext, basic, lines = 0.0, 0, 0, []
for r in rows:
    refs = r["Designator"].split(",")
    c = r["LCSC Part #"]
    s = stock.get(c)
    q = len(refs) * N
    if not s:
        lines.append((c, r["Comment"], len(refs), None, None, None, None)); continue
    tiers = sorted((int(k), v) for k, v in s["prices"].items())
    price = [v for k, v in tiers if k <= q][-1] if any(k <= q for k, _ in tiers) else tiers[0][1]
    lines.append((c, r["Comment"], len(refs), price, s["stock"], s["type"], price * len(refs)))
    tot += price * len(refs)
    if s["type"] == "expand":
        ext += 1
    else:
        basic += 1
print("| LCSC | Part | Per board | Unit USD (tier for %d boards) | Line USD | JLC stock | Type |" % N)
print("|---|---|---|---|---|---|---|")
for c, name, n, price, st, ty, lt in sorted(lines, key=lambda x: -(x[6] or 0)):
    print("| %s | %s | %d | %s | %s | %s | %s |" % (c, name, n, "%.4f" % price if price else "?", "%.3f" % lt if lt else "?", st, "extended" if ty == "expand" else "basic"))
print()
print("parts per board USD %.2f, %d BOM lines (%d extended, %d basic), %d placements" % (tot, len(rows), ext, basic, sum(len(r["Designator"].split(",")) for r in rows)))
