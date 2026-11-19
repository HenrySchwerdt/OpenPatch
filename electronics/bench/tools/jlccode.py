#!/usr/bin/env python3
"""jlccode.py C25905 C72043 ... -> exact code lookup (stock/type/desc)."""
import json, sys, urllib.request, time
U="https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
def get(code):
    for _ in range(4):
        try:
            r=urllib.request.Request(U,json.dumps({"keyword":code,"currentPage":1,"pageSize":5}).encode(),{"Content-Type":"application/json","User-Agent":"Mozilla/5.0"})
            L=json.load(urllib.request.urlopen(r,timeout=30))['data']['componentPageInfo']['list'] or []
            for x in L:
                if x['componentCode']==code: return x
            return None
        except Exception: time.sleep(1.5)
if __name__=="__main__":
    for c in sys.argv[1:]:
        d=get(c)
        if not d: print(c,"NOT FOUND"); continue
        p=d["componentPrices"][0]["productPrice"] if d.get("componentPrices") else None
        print(f'{c:9} {d["componentModelEn"][:30]:30} stock={d["stockCount"]:<8} {"BASIC" if d["componentLibraryType"]=="base" else "ext":5} ${p} {d.get("componentSpecificationEn")} | {d["componentBrandEn"][:18]} | {(d.get("describe") or "")[:60]}')
