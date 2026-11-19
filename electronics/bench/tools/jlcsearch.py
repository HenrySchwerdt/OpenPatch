#!/usr/bin/env python3
"""Query the JLCPCB parts API: jlcsearch.py keyword [keyword...]  (prints code, MPN, stock, type, price, package)."""
import json, sys, urllib.request
URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
def q(kw, n=8):
    req = urllib.request.Request(URL, json.dumps({"keyword": kw, "currentPage": 1, "pageSize": n}).encode(),
                                 {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    for c in (d["data"]["componentPageInfo"]["list"] or []):
        p = c["componentPrices"][0]["productPrice"] if c.get("componentPrices") else None
        print(f'{c["componentCode"]:10} {c["componentModelEn"][:34]:34} stock={c["stockCount"]:<8} {c["componentLibraryType"]:6} ${p} {c.get("componentSpecificationEn")} | {c["componentBrandEn"]}')
for k in sys.argv[1:]:
    print("##", k); q(k)
