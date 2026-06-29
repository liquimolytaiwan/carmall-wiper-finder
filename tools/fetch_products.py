#!/usr/bin/env python3
"""Re-fetch all BOSCH wiper products (price + stock + variants) from Cyberbiz (carmall.com.tw)
via the public sitemap + per-product .json endpoints. Writes wiper_products.json.
Used both locally and by the scheduled GitHub Action to keep price/stock current."""
import urllib.parse, urllib.request, urllib.error, json, os, re, sys, time
BASE=os.path.dirname(os.path.abspath(__file__))
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
SITE="https://www.carmall.com.tw"
# Product-line singles that must always be fetched even if absent from sitemap (e.g. HELLA not yet in sitemap)
EXTRA_HANDLES=["bosch博世-通用型軟骨雨刷","hella-三節式雨刷-hybrid-wiper"]
# "buy N for $M" promo collections (special_collection). Parsed from the collection's display name.
# key -> collection handle (URL slug may be stale; the collection NAME carries the live price)
PROMO_COLLECTIONS={"bosch_pair":"bosch雨刷-2件859"}

def get(url, raw=False, retries=4):
    # Cyberbiz occasionally times out / drops a connection. Retry transient
    # network errors with incremental backoff so a single blip doesn't fail
    # the whole scheduled job (esp. the very first sitemap fetch, which has no
    # try/except around it in main()).
    last=None
    for attempt in range(retries):
        try:
            req=urllib.request.Request(url, headers={"User-Agent":UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                data=r.read()
            return data if raw else data.decode("utf-8","replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last=e
            if attempt < retries-1:
                time.sleep(3*(attempt+1))   # 3s, 6s, 9s
    raise last

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
    # ---- promos: parse "N件$M" from each promo collection's display name ----
    promos={}
    for key,handle in PROMO_COLLECTIONS.items():
        try:
            html=get(SITE+"/collections/"+urllib.parse.quote(handle,safe="-")+"?page=1")
            m=re.search(r'collectionName"?\s*[:=]\s*"([^"]+)"', html)
            name=m.group(1) if m else ""
            mm=re.search(r'(\d+)\s*件\s*\$?\s*([0-9]+)', name)
            if mm:
                promos[key]={"qty":int(mm.group(1)),"price":int(mm.group(2)),"name":name}
        except Exception as e:
            print(f"  promo fetch fail {key}: {e}")
    json.dump(promos, open(os.path.join(BASE,"promos.json"),"w"), ensure_ascii=False, indent=1)
    print(f"promos: {promos}")
    print(f"wiper products: {len(out)} | failures: {len(fail)}")
    for f in fail: print("  FAIL", f[0], f[1])
    if not out:
        print("ERROR: no products fetched", file=sys.stderr); sys.exit(1)

if __name__=="__main__":
    main()
