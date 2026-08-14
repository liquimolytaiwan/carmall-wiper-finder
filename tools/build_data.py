#!/usr/bin/env python3
"""Build data.json for the CarMall wiper finder.
Sources: PDF fitment (pages/) + researched corrections (corrections.json) + Cyberbiz products (wiper_products.json).
Multi product-line: each car shows available options (BOSCH 軟骨 combo-or-single + HELLA 三節式 single).
Availability-gated: out-of-stock product/variant/combo is dropped (kept fresh by the daily refresh Action).
Policy: no mechanical size substitution; catalog<>market conflicts resolved in corrections.json."""
import json, re, glob, os
BASE=os.path.dirname(os.path.abspath(__file__))
OUT=os.path.join(BASE,"carmall-wiper","data.json") if os.path.isdir(os.path.join(BASE,"carmall-wiper")) else os.path.join(BASE,"..","data.json")

BOSCH_SINGLE_HANDLE="bosch博世-通用型軟骨雨刷"
HELLA_HANDLE="hella-三節式雨刷-hybrid-wiper"

CN={"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,"十一":11,"十二":12}
GENRE=r"第[一二三四五六七八九十]+(?:\s*[/／]\s*[一二三四五六七八九十]+)*代?"
def gen_ints(model):
    out=set()
    for blk in re.findall(GENRE,model):
        for m in re.findall(r"[一二三四五六七八九十]+",blk):
            if m in CN: out.add(CN[m])
    return out
# "第三代~第五代通用款" covers generations 3,4,5. Read the range BEFORE the cleanup below
# turns "~" into a space, otherwise only the endpoints survive and the middle generation
# silently loses its combo (CR-V 第四代, FIT 第二代). Sizes are still matched separately,
# so widening the generation set can never pair a car with the wrong-size set.
GEN_RANGE=re.compile(r"第([一二三四五六七八九十]+)代?\s*[~～\-－至]\s*第([一二三四五六七八九十]+)代")
def gen_span(text):
    out=set()
    for a,b in GEN_RANGE.findall(text or ""):
        if a in CN and b in CN:
            lo,hi=sorted((CN[a],CN[b]))
            out|=set(range(lo,hi+1))
    return out
def gen_label(model):
    g=[re.sub(r"\s*[/／]\s*","/",x.strip()) for x in re.findall(GENRE,model)]
    pv=[p.strip() for p in re.findall(r"[（(]([^（()）]*)[)）]",model) if p.strip()]
    extra=[kw for kw in ["小改款","Hyper","NEO","電動","進口","美規","日規","卡旺"] if kw in model and not any(kw in x for x in g)]
    parts=list(g)
    for p in pv:
        if p not in parts: parts.append(p)
    for e in extra:
        if e not in " ".join(parts): parts.append(e)
    return " ".join(parts).strip()
def model_group(model):
    s=re.sub(GENRE,"",model); s=re.sub(r"[（(][^（()）]*[)）]","",s); s=s.replace("小改款","")
    return re.sub(r"\s+"," ",s).strip()
EQUIV=[{"CT200H","CT"},{"S5HYPER","S5"}]
def canon(tok):
    for g in EQUIV:
        if tok in g: return sorted(g)[0]
    return tok
def fam_tokens(model):
    s=model_group(model).upper(); s=re.sub(r"第.+代","",s)
    out=set()
    for t in re.split(r"[/／]",s):
        t=re.sub(r"[\s\-]","",t).strip()
        if t: out.add(canon(t))
    return out
def fit_fam_tokens(model):
    t=fam_tokens(model)
    for p in re.findall(r"[（(]([^（()）]*)[)）]",model):
        p=re.sub(r"[\s\-]","",p.upper()).strip()
        if re.match(r"^[A-Z]+\d",p): t.add(canon(p))
    return t
def nkey(brand,model,year):
    return (brand.upper().strip(), re.sub(r"\s+","",model).upper(), re.sub(r"\s","",year or ""))

# ---------- corrections ----------
corr={}
cpath=os.path.join(BASE,"corrections.json")
if os.path.exists(cpath):
    for c in json.load(open(cpath)):
        corr[nkey(c["brand"],c["model"],c.get("year",""))]=c

# ---------- fitment + corrections ----------
# p*.json  = 型錄「通用雨刷對照表 美日韓車種」(型錄 24-29 頁)：U 型接頭，前擋賣通用型。
# eu-p*.json = 型錄「專用雨刷對照表 歐系車種」(型錄 8-21 頁)：前擋是專用接頭，店上還沒賣，
#              所以 driver/passenger 一律 null（走 dedicated 分支顯示「即將上市」），
#              收錄它們是為了讓歐系車主查得到自己的後擋規格並直接購買。
fit=[]; eu_rows=0
for p in sorted(glob.glob(os.path.join(BASE,"pages","p*.json"))):
    fit+=json.load(open(p))
for p in sorted(glob.glob(os.path.join(BASE,"pages","eu-p*.json"))):
    rows=json.load(open(p)); eu_rows+=len(rows); fit+=rows
applied=0
for r in fit:
    k=nkey(r["brand"],r["model"],r.get("year",""))
    if k in corr:
        c=corr[k]
        if c.get("driver") is not None: r["driver"]=c["driver"]
        if c.get("passenger") is not None: r["passenger"]=c["passenger"]
        applied+=1

# ---------- products ----------
prods=json.load(open(os.path.join(BASE,"wiper_products.json")))
def prod_by_handle(h):
    for p in prods:
        if (p.get("handle") or "")==h: return p
    return None
def variant_ok(v):
    q=v.get("qty"); return bool(v.get("available")) and (q is None or q>0)
def size_variants(p):
    out={}
    if not p: return out
    for v in p.get("variants",[]):
        m=re.search(r"\d+", v.get("option1") or "")
        if not m: continue
        out[int(m.group(0))]={"id":v.get("id"),"price":int(v.get("price") or 0),"ok":variant_ok(v)}
    return out
def prod_url(p,fallback):
    u=p.get("url") if p else None
    if not u: return fallback
    return u if u.startswith("http") else "https://www.carmall.com.tw"+u

promos={}
ppath=os.path.join(BASE,"promos.json")
if os.path.exists(ppath): promos=json.load(open(ppath))
bosch_pair=promos.get("bosch_pair")

bosch_p=prod_by_handle(BOSCH_SINGLE_HANDLE); hella_p=prod_by_handle(HELLA_HANDLE)
bosch_var=size_variants(bosch_p); hella_var=size_variants(hella_p)
BOSCH_URL=prod_url(bosch_p,"https://www.carmall.com.tw/products/"+BOSCH_SINGLE_HANDLE)
HELLA_URL=prod_url(hella_p,"https://www.carmall.com.tw/products/"+HELLA_HANDLE)

# ---------- rear wipers (1支, 專用規格) ----------
# The finder has always known each car's rear blade code — it comes straight from the
# catalogue and lives in each row's "rear" field — but until 2026-08 the store sold no
# rear blades, so the UI could only say "洽客服". Now that it does, the two are joined on
# that code: the store titles print exactly the code the catalogue prints (H261 / A301H /
# AM40H …), and the SKU is the full Bosch part number, so no size guessing is involved.
#
# Codes are compared as whole tokens, NEVER as substrings: H301 (3397004629) and A301H
# (3397016465) are different parts and one contains the other.
REAR_CODE=re.compile(r"\b([A-Z]{1,2}\d{2,3}[A-Z]?)\b")
REAR_SIZE=re.compile(r"(\d{1,2})\s*吋")
def rear_stock_ok(p):
    if not p.get("available"): return False
    vs=p.get("variants") or []
    return True if not vs else any(variant_ok(v) for v in vs)

rear_by_code={}; rear_skipped=[]
for p in prods:
    t=re.sub(r"<[^>]+>","",p.get("title") or "")
    if "後擋" not in t and "後檔" not in t: continue
    cm=REAR_CODE.search(t.replace("BOSCH","").replace("HELLA",""))
    sm_=REAR_SIZE.search(t)
    if not cm:
        rear_skipped.append(("標題找不到規格代碼",p.get("handle"),t)); continue
    if not rear_stock_ok(p): continue
    code=cm.group(1).upper()
    prev=rear_by_code.get(code)
    if prev and prev["price"]<=int(p["price"]): continue   # same code twice -> keep cheaper
    rear_by_code[code]={"code":code,"size":int(sm_.group(1)) if sm_ else None,
                        "price":int(p["price"]),"url":prod_url(p,p.get("url")),
                        "label":t.strip()}

# ---------- combos (2支/組) ----------
# Both product lines title their vehicle-specific sets the same way
# ("… 適用車型 HONDA CIVIC 第九代(12~17)26+18吋"), so a combo must record WHICH line it
# belongs to. Matching on the title alone would let a HELLA set be offered under the
# BOSCH label (today BOSCH merely happens to sort first and win every tie).
LINE_PATTERNS=[("HELLA",r"hella|海拉"),("BOSCH",r"bosch|博世")]
def combo_line(p):
    """Which product line a vehicle-specific set belongs to, or None if unrecognised.
    Looks at handle AND title: Cyberbiz slugs are frozen at creation, so a renamed
    product can keep a slug that no longer names its brand. Returning None (rather than
    defaulting to BOSCH) means a newly-added third line is skipped and reported instead
    of being silently sold under the wrong brand."""
    # Title first, handle only as a fallback. A renamed product keeps its old slug, so a
    # combined haystack would let the stale handle outvote the current title.
    for hay in (re.sub(r"<[^>]+>","",p.get("title") or ""), p.get("handle") or ""):
        for key,pat in LINE_PATTERNS:
            if re.search(pat,hay,re.I): return key
    return None

sz=re.compile(r"(\d{2})\s*\+\s*(\d{2})\s*吋")
combos=[]; skipped=[]
for p in prods:
    t=re.sub(r"<[^>]+>","",p["title"] or "")   # titles may carry an HTML promo banner
    if "適用車型" not in t: continue
    if "-copy" in (p.get("handle") or ""): continue
    line=combo_line(p)
    if line is None:
        skipped.append(("認不出產品線",p.get("handle"),t)); continue
    seg=t.split("適用車型",1)[1]; sm=sz.search(seg)
    if not sm:
        # No "26+16吋" in the title — the set can never match a car (sizes are compared
        # exactly), so report it rather than parking a dead entry in the list.
        skipped.append(("標題找不到「NN+NN吋」尺寸",p.get("handle"),t)); continue
    d,pa=(int(sm.group(1)),int(sm.group(2)))
    seg_m=seg[:sm.start()]
    raw_m=seg_m                       # keep the un-stripped text so ranges stay readable
    seg_m=re.sub(r"[【】]"," ",seg_m); seg_m=re.sub(r"[（(][^（()）]*[)）]"," ",seg_m)
    seg_m=re.sub(r"\d{2,4}\s*[~\-～]\s*\d{0,4}"," ",seg_m)
    for w in ["通用款","_","、","~","～"]: seg_m=seg_m.replace(w," ")
    seg_m=re.sub(r"\s+"," ",seg_m).strip()
    parts=seg_m.split(None,1)
    combos.append({"line":line,
      "brand":(parts[0].upper() if parts else ""),"model":(parts[1].strip() if len(parts)>1 else ""),
      "driver":d,"passenger":pa,"url":prod_url(p,p.get("url")),"price":int(p["price"]),
      "stock":sum((v["qty"] or 0) for v in p["variants"]),"available":p["available"],
      "fam":fam_tokens(parts[1] if len(parts)>1 else ""),
      "gens":gen_ints(seg_m)|gen_span(raw_m),"_used":False})

def find_combo(brand,model,d,p,line,relaxed=False):
    bt=fit_fam_tokens(model); fg=gen_ints(model); fg1=next(iter(fg)) if len(fg)==1 else None
    best=None; bs=-1
    for c in combos:
        if c["line"]!=line: continue
        if c["brand"]!=brand.upper(): continue
        if c["driver"]!=d or c["passenger"]!=p: continue
        if not (c["available"] and c["stock"]>0): continue   # availability gate
        if not (bt & c["fam"]): continue
        if not relaxed and c["gens"] and fg1 and fg1 not in c["gens"]: continue
        score=len(bt & c["fam"])
        if c["gens"] and fg1 and fg1 in c["gens"]: score+=3
        elif not c["gens"]: score+=1
        if score>bs: bs=score; best=c
    return best

def single_option(brand,label,material,url,var,d,p,pair_promo=None):
    dv=var.get(d); pv=var.get(p)
    if not (dv and pv and dv["ok"] and pv["ok"]): return None
    listp=dv["price"]+pv["price"]
    o={"brand":brand,"label":label,"material":material,"kind":"single",
       "url":url+("?variant="+str(dv["id"]) if dv.get("id") else ""),
       "driver":d,"passenger":p,"driverPrice":dv["price"],"passengerPrice":pv["price"],"price":listp}
    if pair_promo and pair_promo.get("qty")==2 and pair_promo.get("price"):
        o["listPrice"]=listp; o["price"]=pair_promo["price"]; o["promo"]=True
    return o

# ---------- build cascade ----------
brands={}; order=[]; seen_ded=set(); rows=[]; ded_rows=[]
for r in fit:
    brand=r["brand"].strip(); mg=model_group(r["model"]) or r["model"]
    lbl=gen_label(r["model"]); year=r.get("year","")
    label=((lbl+" ") if lbl else "")+("("+year+")" if year else ""); label=label.strip() or year or "—"
    entry={"label":label,"year":year}
    if not r.get("driver"):
        entry["fit"]="dedicated"
        dk=(brand,mg,label)
        if dk in seen_ded: continue
        seen_ded.add(dk)
        # A dedicated-front car still has a rear blade we can sell today, so the rear code
        # rides along even though there is no front option to show.
        entry["rear"]=r.get("rear"); ded_rows.append(entry)
    else:
        entry["fit"]="universal"; entry["driver"]=r["driver"]; entry["passenger"]=r["passenger"]
        entry["rear"]=r.get("rear"); entry["_brand"]=brand; entry["_model"]=r["model"]; rows.append(entry)
    if brand not in brands:
        brands[brand]={"name":brand,"models":{},"order":[]}; order.append(brand)
    bb=brands[brand]
    if mg not in bb["models"]:
        bb["models"][mg]={"name":mg,"entries":[]}; bb["order"].append(mg)
    bb["models"][mg]["entries"].append(entry)

# Per-line combo matching: strict pass first, then a relaxed pass for generation-label
# drift that only claims combos the strict pass didn't already take.
LINES=[
  {"key":"BOSCH","label":"BOSCH 通用軟骨 旗艦款","material":"軟骨",
   "url":BOSCH_URL,"var":bosch_var,"pair":bosch_pair},
  {"key":"HELLA","label":"HELLA 三節式 Hybrid","material":"三節式",
   "url":HELLA_URL,"var":hella_var,"pair":None},
]
for L in LINES:
    ck="_combo_"+L["key"]
    for e in rows:
        e[ck]=find_combo(e["_brand"],e["_model"],e["driver"],e["passenger"],L["key"],False)
    for e in rows:
        if e[ck]: e[ck]["_used"]=True
    for e in rows:
        if not e[ck]:
            c=find_combo(e["_brand"],e["_model"],e["driver"],e["passenger"],L["key"],True)
            if c and not c["_used"]: c["_used"]=True; e[ck]=c

# assemble options per row — each line offers its vehicle-specific set when one exists,
# otherwise the self-select single product.
for e in rows:
    d,p=e["driver"],e["passenger"]; opts=[]
    for L in LINES:
        c=e.get("_combo_"+L["key"])
        if c:
            opts.append({"brand":L["key"],"label":L["label"],"material":L["material"],
                         "kind":"combo","url":c["url"],"price":c["price"]})
        else:
            o=single_option(L["key"],L["label"],L["material"],L["url"],L["var"],d,p,L["pair"])
            if o: opts.append(o)
    e["options"]=opts
    if not opts: e["route"]={"type":"contact"}
    # Rear blade: exact code match, otherwise the row keeps only "rear" and the UI falls
    # back to the 洽客服 note it has always shown.
    ro=rear_by_code.get((e.get("rear") or "").upper())
    if ro: e["rearOption"]=ro
    for k in ["_brand","_model"]+["_combo_"+L["key"] for L in LINES]: e.pop(k,None)

# Dedicated-front rows (歐系全部，加上美日韓的專用接頭車) get the same rear treatment.
for e in ded_rows:
    ro=rear_by_code.get((e.get("rear") or "").upper())
    if ro: e["rearOption"]=ro

out_brands=[{"name":bn,"models":[brands[bn]["models"][mn] for mn in brands[bn]["order"]]} for bn in order]
data={"meta":{"updated":"2026-08-14",
              "source":"BOSCH 2026 雨刷型錄（通用美日韓＋專用歐系）＋市場查證校正",
              "lines":["BOSCH 通用軟骨 旗艦款","HELLA 三節式 Hybrid"]},
      "brands":out_brands}
json.dump(data,open(OUT,"w"),ensure_ascii=False,indent=1)

# report
def has(line): return sum(1 for e in rows for o in e["options"] if o["brand"]==line)
def ncombo(line): return sum(1 for e in rows for o in e["options"]
                            if o["brand"]==line and o["kind"]=="combo")
print(f"corrections applied: {applied}")
print(f"BOSCH single-product variants: {sorted(bosch_var)} | HELLA variants: {sorted(hella_var)}")
print(f"combo products parsed: " + " ".join(
      f"{L['key']}={sum(1 for c in combos if c['line']==L['key'])}" for L in LINES))
print(f"universal rows: {len(rows)}")
for L in LINES:
    k=L["key"]
    print(f"  {k:<6} option: {has(k):>4}  (combo {ncombo(k)} / single {has(k)-ncombo(k)})")
print(f"rows with 0 options (contact): {sum(1 for e in rows if not e['options'])}")

# New vehicle-specific sets get added to the store over time. A set that parses but never
# lands on a car is invisible on the site and produces no error, so surface it here — this
# log is the only place a newly-added product that failed to match will show up.
all_rows=rows+ded_rows
rear_rows=sum(1 for e in all_rows if e.get("rearOption"))
rear_with_code=sum(1 for e in all_rows if e.get("rear"))
used_rear={e["rearOption"]["code"] for e in all_rows if e.get("rearOption")}
print(f"專用接頭車款列: {len(ded_rows)}（歐系型錄讀進 {eu_rows} 列，同車款同年份會合併）")
print(f"rear products in stock: {len(rear_by_code)} ({', '.join(sorted(rear_by_code))})")
print(f"  rows with a rear code: {rear_with_code} | now buyable: {rear_rows}"
      + (f" ({rear_rows*100//rear_with_code}%)" if rear_with_code else ""))
print(f"    其中通用美日韓 {sum(1 for e in rows if e.get('rearOption'))}"
      f" / 專用（含歐系）{sum(1 for e in ded_rows if e.get('rearOption'))}")
rear_unused=sorted(set(rear_by_code)-used_rear)
if rear_unused:
    print(f"  配不到任何車的後擋商品：{', '.join(rear_unused)}")
    print("    → 2026 台灣型錄（通用美日韓＋專用歐系）都沒有印這個代碼，不是程式錯誤；"
          "要讓它配到車得先查出它適用哪些車再補進型錄資料")
if rear_skipped:
    print(f"  ⚠️  略過的後擋商品（標題認不出代碼）：{len(rear_skipped)}")
    for why,h,t in rear_skipped: print(f"    - [{why}] {t[:70]}  ({h})")

unmatched=[c for c in combos if not c["_used"]]
if skipped:
    print(f"\n⚠️  略過的組合商品（格式不符，不會出現在查詢器）：{len(skipped)}")
    for why,h,t in skipped: print(f"    - [{why}] {t[:70]}  ({h})")
if unmatched:
    print(f"\n⚠️  解析成功但沒配到任何車的組合：{len(unmatched)}")
    for c in unmatched:
        print(f"    - [{c['line']}] {c['brand']} {c['model']} {c['driver']}+{c['passenger']}吋"
              f"{'' if c['available'] and c['stock']>0 else '  (無庫存，屬正常)'}")
    print("    → 檢查：車廠/車款拼法是否與查詢器一致、尺寸是否與型錄相同")
else:
    print("\n所有組合商品都已配到車 ✓")
print("wrote",OUT)
