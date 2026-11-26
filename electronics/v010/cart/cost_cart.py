#!/usr/bin/env python3
"""Board cost of the CART main board per pump at 5 / 10 / 20 boards (plain python3) -> prints the markdown tables of cart/COST.md.

Inputs: newest cart/jlc_stock_<date>.json (live JLC parts API, live_stock.py), cart/jlc/BOM-jlcpcb.csv, and the PCB prices read live on
the JLC quote page (PCB below, EUR incl. nothing else). Assembly fees are JLC's published standard-PCBA fee model (ESTIMATE, the exact
figure appears only after the gerber / BOM upload). USD -> EUR 0.92."""
import csv
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
USD = 0.92
# JLC quote page 2026-11-25 (V), the board as routed: FR-4 6 layers, 57 x 10.6 mm, 0.8 mm, ENIG 1 U", 1 oz / 0.5 oz, via covering "Epoxy Filled
# & Capped" (POFV, default and free on 6 layers), min via 0.2 / (0.3-0.35) mm -> "high precision": TG155 + via tier + 4-wire Kelvin test
# charged; 7-8 days build. EUR incl. those options.
PCB_EUR = {5: 77.85, 10: 91.91, 20: 111.47}
PCB4_EUR = {5: 22.79, 10: 28.56, 20: 40.54}   # same outline, 4 layers, ENIG, 0.3 mm via tier, 3-4 days (V 2026-11-24): did not route
SHIP_EUR = 21.42             # DHL Express estimate on the quote page (V), PCB + PCBA in one parcel
# standard PCBA (both sides) ESTIMATE in USD: setup per side, stencil per side, extended-part loading fee per unique extended part
SETUP_USD, STENCIL_USD, EXT_USD, JOINT_USD = 25.0, 7.0, 3.0, 0.0017
SIDES = 2
IMPORT_VAT = 0.19


def bom() -> list:
    snap = json.load(open(sorted(glob.glob(os.path.join(HERE, "jlc_stock_*.json")))[-1]))
    rows = []
    for r in csv.DictReader(open(os.path.join(HERE, "jlc", "BOM-jlcpcb.csv"))):
        c = r["LCSC Part #"]; s = snap[c]; n = len(r["Designator"].split(","))
        rows.append((c, r["Comment"], n, s))
    return rows


def unit(s: dict, q: int) -> float:
    tiers = sorted((int(k), v) for k, v in s["prices"].items())
    ok = [v for k, v in tiers if k <= q]
    return ok[-1] if ok else tiers[0][1]


def main() -> None:
    rows = bom()
    ext = sum(1 for *_, s in rows if s["type"] == "expand")
    joints = 0
    pads = json.load(open(os.path.join(HERE, "netlist_cart.json")))
    for p in pads:
        if p.get("bom") and p.get("lcsc") and not p.get("dnp"):
            joints += max(2, len([v for v in p["pins"].values()]))
    print("| LCSC | Part | qty / board | stock | type | unit USD (5 boards) |\n|---|---|---|---|---|---|")
    for c, name, n, s in sorted(rows, key=lambda r: r[3]["stock"]):
        print("| %s | %s | %d | %d | %s | %.4f |" % (c, s["mpn"], n, s["stock"], "basic" if s["type"] == "base" else "extended", unit(s, 5 * n)))
    print("\n%d BOM lines, %d extended, %d solder joints per board (approx.)\n" % (len(rows), ext, joints))
    print("| Boards (= pumps) | PCB (V) | parts | PCBA fees (E) | shipping (V) | import VAT 19 % | **total** | **per board** |\n|---|---|---|---|---|---|---|---|")
    for n in (5, 10, 20):
        parts = sum(unit(s, n * k) * k for _, _, k, s in rows) * n * USD
        fees = (SIDES * (SETUP_USD + STENCIL_USD) + ext * EXT_USD + joints * JOINT_USD * n) * USD
        sub = PCB_EUR[n] + parts + fees + SHIP_EUR
        tot = sub * (1 + IMPORT_VAT)
        print("| %d | %.2f | %.2f | %.2f | %.2f | %.2f | **%.0f** | **%.1f** |" % (n, PCB_EUR[n], parts, fees, SHIP_EUR, sub * IMPORT_VAT, tot, tot / n))
    print("\nFor comparison, 4 layers (did not route): PCB %s EUR at 5 / 10 / 20 (V)" % " / ".join("%.2f" % PCB4_EUR[n] for n in (5, 10, 20)))


if __name__ == "__main__":
    main()
