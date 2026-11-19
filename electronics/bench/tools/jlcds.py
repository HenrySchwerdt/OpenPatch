#!/usr/bin/env python3
"""Download the datasheet of an LCSC code: jlcds.py C2856801 outname"""
import json, sys, urllib.request
U="https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
code, out = sys.argv[1], sys.argv[2]
r=urllib.request.Request(U,json.dumps({"keyword":code,"currentPage":1,"pageSize":1}).encode(),{"Content-Type":"application/json","User-Agent":"Mozilla/5.0"})
d=json.load(urllib.request.urlopen(r))['data']['componentPageInfo']['list'][0]
u=d.get('dataManualFileAccessIdUrl') or d.get('dataManualUrl')
b=urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})).read()
open(out,'wb').write(b); print(code,d['componentModelEn'],len(b))
