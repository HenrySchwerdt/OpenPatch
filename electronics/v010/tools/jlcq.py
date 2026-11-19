#!/usr/bin/env python3
"""JLCPCB parts lookup with retries.  jlcq.py kw [kw...]  (search)   |  jlcq.py -c C123 C456 (exact code, full description)"""
import json
import sys
import time
import urllib.request

U = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"


def post(kw, n=8):
    for i in range(6):
        try:
            r = urllib.request.Request(U, json.dumps({"keyword": kw, "currentPage": 1, "pageSize": n}).encode(),
                                       {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            return json.load(urllib.request.urlopen(r, timeout=30))["data"]["componentPageInfo"]["list"] or []
        except Exception:
            time.sleep(1.5 + i)
    return []


def line(c, full=False):
    p = c["componentPrices"][0]["productPrice"] if c.get("componentPrices") else None
    s = (f'{c["componentCode"]:10} {c["componentModelEn"][:30]:30} stock={c["stockCount"]:<7} '
         f'{"BASIC" if c["componentLibraryType"]=="base" else "ext  "} ${p} {c.get("componentSpecificationEn")} | {c["componentBrandEn"][:14]}')
    if full:
        s += " | " + (c.get("describe") or "")[:170]
    return s


if __name__ == "__main__":
    if sys.argv[1] == "-c":
        for code in sys.argv[2:]:
            L = [x for x in post(code, 5) if x["componentCode"] == code]
            print(line(L[0], True) if L else code + " NOT FOUND")
    else:
        for k in sys.argv[1:]:
            print("##", k)
            for c in post(k):
                print(line(c))
