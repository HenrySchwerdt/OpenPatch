#!/usr/bin/env python3
"""Live JLC parts snapshot for every LCSC number of the cart A board (copy of ../live_stock.py; plain python3, network): cart/a/jlc_stock_<date>.json.

usage: python3 live_stock_a.py   (reads netlist_cart_a.json; JLC parts API through tools/jlcq.py, same format as cup/jlc_stock_*.json)"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import jlcq  # noqa: E402


def main() -> None:
    codes = sorted({p["lcsc"] for p in json.load(open(os.path.join(HERE, "netlist_cart_a.json"))) if p.get("lcsc") and p.get("bom") and not p.get("dnp")})
    out, missing = {}, []
    for c in codes:
        hit = [x for x in jlcq.post(c, 5) if x["componentCode"] == c]
        if not hit:
            missing.append(c)
            continue
        x = hit[0]
        out[c] = {"code": c, "mpn": x["componentModelEn"], "pkg": x.get("componentSpecificationEn"), "type": x["componentLibraryType"],
                  "stock": x["stockCount"], "prices": {str(p["startNumber"]): p["productPrice"] for p in (x.get("componentPrices") or [])},
                  "brand": x.get("componentBrandEn")}
    fn = os.path.join(HERE, "jlc_stock_%s.json" % datetime.date.today().isoformat())
    json.dump(out, open(fn, "w"), indent=1)
    print("snapshot", fn, len(out), "parts; not found:", missing)
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
