#!/usr/bin/env python3
"""Re-fetch all BOSCH wiper products (price + stock + variants) from Cyberbiz (carmall.com.tw)
via the public sitemap + per-product .json endpoints. Writes wiper_products.json.
Used both locally and by the scheduled GitHub Action to keep price/stock current."""
import urllib.parse, urllib.request, json, os, re, sys
BASE=os.path.dirname(os.path.abspath(__file__))
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
SITE="https://www.carmall.com.tw"
# Product-line singles that must always be fetched even if absent from sitemap (e.g. HELLA not yet in sitemap)
EXTRA_HANDLES=["bosch博世-通用型軟骨雨刷","hella-三節式雨刷-hybrid-wiper"]

def get(url, raw=False):
    req=urllib.request.Request(url, headers={"User-Agent":UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        data=r.read()
    return data if raw else data.decode("utf-8","replace")

def main():
    sm=get(SITE+"/sitemap.xml")
    urls=sorted(set(re.findall(r"https://www\.carmall\.com\.tw/products/[^< ]+", sm)))
    wiper=[]
    for u in urls:
        h=urllib.parse.unquote(u.rsplit("/products/",1)[-1])
        if "雨刷" not in h: continue
        wiper.append(h)
    for h in EXTRA_HANDLES:
        if h not in wiper: wiper.append(h)
    out=[]; fail=[]
    for h in wiper:
        url=SITE+"/products/"+urllib.parse.quote(h, safe="-")+".json"
        try:
            d=json.loads(get(url))
            vs=[{"option1":v.get("option1"),"sku":v.get("sku"),"qty":v.get("inventory_quantity"),
                 "available":v.get("available"),"id":v.get("id"),"price":v.get("price")} for v in d.get("variants",[])]
            out.append({"handle":d.get("handle"),"title":d.get("title"),
                        "url":SITE+(d.get("url") or ("/products/"+h)),
                        "price":d.get("price"),"available":d.get("available"),"variants":vs})
        except Exception as e:
            fail.append((h,str(e)))
    json.dump(out, open(os.path.join(BASE,"wiper_products.json"),"w"), ensure_ascii=False, indent=1)
    print(f"wiper products: {len(out)} | failures: {len(fail)}")
    for f in fail: print("  FAIL", f[0], f[1])
    if not out:
        print("ERROR: no products fetched", file=sys.stderr); sys.exit(1)

if __name__=="__main__":
    main()
