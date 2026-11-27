#!/usr/bin/env python3
"""Board cost of the cart A main board per pump at 5 / 10 / 20 boards (copy of ../cost_cart.py; plain python3) -> tables of cart/a/COST.md.

Inputs: newest cart/a/jlc_stock_<date>.json (live JLC parts API, live_stock_a.py), cart/a/jlc/BOM-jlcpcb.csv, and the PCB price below
(ESTIMATE from B's live quotes). Assembly fees are JLC's published standard-PCBA fee model (ESTIMATE, the exact figure appears only after
the gerber / BOM upload). USD -> EUR 0.92."""
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
USD = 0.92
# A board, 4 layers, 31.4 x 21.4 mm bounding box, 0.8 mm, ENIG, min via 0.4 / 0.2, filled + capped vias in the HJ-840 / USB D- pads
# (POFV). ESTIMATE from the live quotes of the B board (V 2026-11-24 / 25; JLC prices boards up to 50 x 50 mm alike): B on 4 layers with
# the 0.3 mm via tier = 22.79 / 28.56 / 40.54 EUR; the 0.2 mm drill made B's 6-layer quote "high precision": via tier +15.2, 4-wire Kelvin
# test +15.1, TG155 +3.0 EUR; added here (EXTRA_EUR). POFV is free on 6 layers but an option on 4 layers: NOT priced (re-quote).
EXTRA_EUR = 15.2 + 15.1 + 3.0
VIA_TIER_EUR = EXTRA_EUR
PCB4_EUR = {5: 22.79, 10: 28.56, 20: 40.54}
PCB_EUR = {n: round(v + EXTRA_EUR, 2) for n, v in PCB4_EUR.items()}
PCB6_EUR = {5: 77.85, 10: 91.91, 20: 111.47}  # B as routed (6 layers, V 2026-11-25), for comparison
SHIP_EUR = 21.42             # DHL Express estimate on the quote page (V), PCB + PCBA in one parcel
# standard PCBA (both sides) ESTIMATE in USD: setup per side, stencil per side, extended-part loading fee per unique extended part
SETUP_USD, STENCIL_USD, EXT_USD, JOINT_USD = 25.0, 7.0, 3.0, 0.0017
SIDES = 2
IMPORT_VAT = 0.19


LAYERS = int(sys.argv[1]) if len(sys.argv) > 1 else 4      # usage: python3 cost_cart_a.py [4|6]
JLC_DIR = {4: "jlc", 6: "jlc-a6"}[LAYERS]                     # same BOM on both boards (same netlist); the PCB line differs
if not os.path.isdir(os.path.join(HERE, JLC_DIR)):            # no 4-layer package (board not closed): price its PCB with the 6-layer BOM
    JLC_DIR = "jlc-a6"
PCB_SEL = PCB_EUR if LAYERS == 4 else PCB6_EUR


def bom() -> list:
    snap = json.load(open(sorted(glob.glob(os.path.join(HERE, "jlc_stock_*.json")))[-1]))
    rows = []
    for r in csv.DictReader(open(os.path.join(HERE, JLC_DIR, "BOM-jlcpcb.csv"))):
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
    pads = json.load(open(os.path.join(HERE, "netlist_cart_a.json")))
    for p in pads:
        if p.get("bom") and p.get("lcsc") and not p.get("dnp"):
            joints += max(2, len([v for v in p["pins"].values()]))
    print("| LCSC | Part | qty / board | stock | type | unit USD (5 boards) |\n|---|---|---|---|---|---|")
    for c, name, n, s in sorted(rows, key=lambda r: r[3]["stock"]):
        print("| %s | %s | %d | %d | %s | %.4f |" % (c, s["mpn"], n, s["stock"], "basic" if s["type"] == "base" else "extended", unit(s, 5 * n)))
    print("\n%d BOM lines, %d extended, %d solder joints per board (approx.)\n" % (len(rows), ext, joints))
    print("| Boards (= pumps) | PCB (E) | parts | PCBA fees (E) | shipping (V) | import VAT 19 % | **total** | **per board** |\n|---|---|---|---|---|---|---|---|")
    for n in (5, 10, 20):
        parts = sum(unit(s, n * k) * k for _, _, k, s in rows) * n * USD
        fees = (SIDES * (SETUP_USD + STENCIL_USD) + ext * EXT_USD + joints * JOINT_USD * n) * USD
        sub = PCB_SEL[n] + parts + fees + SHIP_EUR
        tot = sub * (1 + IMPORT_VAT)
        print("| %d | %.2f | %.2f | %.2f | %.2f | %.2f | **%.0f** | **%.1f** |" % (n, PCB_SEL[n], parts, fees, SHIP_EUR, sub * IMPORT_VAT, tot, tot / n))
    print("\n%d-layer board (BOM from %s/)." % (LAYERS, JLC_DIR))
    print("\nPCB (E): 4 layers %s EUR at 5 / 10 / 20 (B's 4-layer quote + %.1f high-precision extras, POFV not priced); B's 6-layer board for comparison %s EUR (V)" % (
        " / ".join("%.2f" % PCB_EUR[n] for n in (5, 10, 20)), VIA_TIER_EUR, " / ".join("%.2f" % PCB6_EUR[n] for n in (5, 10, 20))))


if __name__ == "__main__":
    main()
