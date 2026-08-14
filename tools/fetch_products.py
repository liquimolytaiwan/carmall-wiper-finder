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
# Wiper collections. sitemap.xml lags behind (2026-08-14: it listed 7 of the 10 rear
# wipers, missing the three newest), so the collections are enumerated as well and both
# sources are merged. Every product in these collections is a wiper, so no handle filter
# is applied to them.
WIPER_COLLECTIONS=["bosch-後檔雨刷","bosch-旗艦款雨刷","hella-三節式雨刷"]

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

def plain(t):
    """Title with its HTML promo banner stripped, for log lines."""
    return re.sub(r"<[^>]+>","",t or "").strip()

def collection_handles(handle):
    """Product handles listed by a collection's .json endpoint.

    This is the only storefront endpoint that returns real handles for products the
    sitemap has not picked up yet. It caps at 24 items and ignores ?page / ?limit /
    sort params, so it cannot replace the sitemap — it supplements it. Completeness is
    covered separately by collection_titles() + the audit in main()."""
    url=SITE+"/collections/"+urllib.parse.quote(handle,safe="-")+".json"
    out=[]
    for p in json.loads(get(url)):
        u=p.get("url") or ""
        if "/products/" in u:
            out.append(urllib.parse.unquote(u.rsplit("/products/",1)[-1]))
    return out

def collection_items(handle, max_pages=40):
    """Every (product id, title) in a collection, read from the paginated HTML page's
    analytics payload. Unlike the .json endpoint this honours ?page, so it is the only
    complete listing the storefront exposes — used to prove nothing was missed.

    The audit keys on the numeric id, never the title: renaming a product changes both
    its title and its handle, and the HTML listing can serve a cached older title than
    the .json endpoint. Comparing titles made that skew look like a missing product."""
    items=[]; seen=set()
    for page in range(1,max_pages+1):
        html=get(SITE+"/collections/"+urllib.parse.quote(handle,safe="-")+"?page="+str(page))
        pairs=re.findall(r'"id"\s*:\s*(\d+)\s*,\s*"name"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
        new=0
        for pid,raw in pairs:
            if pid in seen: continue
            seen.add(pid); new+=1
            try: title=json.loads('"'+raw+'"')
            except ValueError: title=raw
            items.append((int(pid),title))
        if not new: break
    return items

def main():
    sm=get(SITE+"/sitemap.xml")
    urls=sorted(set(re.findall(r"https://www\.carmall\.com\.tw/products/[^< ]+", sm)))
    wiper=[]
    for u in urls:
        h=urllib.parse.unquote(u.rsplit("/products/",1)[-1])
        if "雨刷" not in h: continue
        wiper.append(h)
    from_sitemap=len(wiper)
    for h in EXTRA_HANDLES:
        if h not in wiper: wiper.append(h)
    coll_items={}; audit_broken=[]
    for c in WIPER_COLLECTIONS:
        try:
            added=[h for h in collection_handles(c) if h not in wiper]
            wiper+=added
            if added: print(f"  collection {c}: +{len(added)} not in sitemap")
        except Exception as e:
            print(f"  collection handles fail {c}: {e}")
        # An audit that cannot run must not read as an audit that passed. Both a raised
        # error and an empty listing (the storefront changing its embedded payload would
        # make the regex match nothing without raising) mean this collection proved
        # nothing, so it is reported exactly like a missing product.
        try:
            items=collection_items(c)
            if not items:
                audit_broken.append((c,"清單是空的（版面可能改了）")); continue
            coll_items[c]=items
        except Exception as e:
            audit_broken.append((c,str(e)))
            print(f"  collection listing fail {c}: {e}")
    print(f"handles: {from_sitemap} from sitemap, {len(wiper)} after collections+extras")
    out=[]; fail=[]
    for h in wiper:
        url=SITE+"/products/"+urllib.parse.quote(h, safe="-")+".json"
        try:
            d=json.loads(get(url))
            vs=[{"option1":v.get("option1"),"sku":v.get("sku"),"qty":v.get("inventory_quantity"),
                 "available":v.get("available"),"id":v.get("id"),"price":v.get("price")} for v in d.get("variants",[])]
            out.append({"id":d.get("id"),"handle":d.get("handle"),"title":d.get("title"),
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

    # ---- completeness audit ----
    # build_data.py can only prove "everything fetched is correct"; it cannot prove
    # "everything on the shelf was fetched". Comparing against each collection's own
    # listing closes that gap: anything the store shows but we never fetched is named
    # here instead of quietly missing from the finder.
    fetched_ids=set(p["id"] for p in out if p.get("id") is not None)
    missing=[]
    for c,items in coll_items.items():
        for pid,t in items:
            # The wiper collections also carry a few accessories (e.g. the glass film
            # remover bundled into 旗艦款). Only wipers belong in the finder, so keeping
            # them out of the audit is what stops this warning from becoming noise.
            if "雨刷" not in t: continue
            if pid not in fetched_ids: missing.append((c,pid,t))
    # A gap must not merely be logged. It also must not abort the run: the other ~200
    # products' prices and stock are still worth publishing, and killing the step here
    # would leave them stale on top of the missing one. So finish the refresh, then drop
    # a marker the workflow checks AFTER the commit — data stays fresh and the job still
    # goes red (which is what actually reaches Jerry; a log line does not).
    flag=os.path.join(BASE,".fetch_incomplete")
    if os.path.exists(flag): os.remove(flag)
    lines=[]
    if missing:
        print(f"\n⚠️  集合裡有、但沒抓到的商品：{len(missing)}（查詢器不會有這些）")
        for c,pid,t in missing: print(f"    - [{c}] #{pid} {plain(t)[:80]}")
        print("    → 通常是 handle 與標題不一致且 sitemap 還沒收錄，需加進 EXTRA_HANDLES")
        lines+= [f"沒抓到 [{c}] #{pid} {plain(t)}" for c,pid,t in missing]
    if audit_broken:
        print(f"\n⚠️  這些集合查不到清單，等於沒檢查：{len(audit_broken)}")
        for c,why in audit_broken: print(f"    - [{c}] {why}")
        lines+= [f"查不到清單 [{c}] {why}" for c,why in audit_broken]
    if lines:
        print("::error::" + "；".join(lines[:5]))
        with open(flag,"w") as fh: fh.write("\n".join(lines))
    elif coll_items:
        print(f"完整性檢查：{sum(len(v) for v in coll_items.values())} 個集合商品全部抓到 ✓")

    if not out:
        print("ERROR: no products fetched", file=sys.stderr); sys.exit(1)

if __name__=="__main__":
    main()
