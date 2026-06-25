#!/usr/bin/env python3
"""Build data.json for the CarMall wiper finder.
Sources: PDF fitment (pages/) + researched corrections (corrections.json) + Cyberbiz combo products (wiper_products.json).
Policy (per client): no mechanical size substitution. Where catalog<>combo/market disagree, corrections.json holds the
researched correct size. A correct-but-unstocked size routes to 'contact' (洽客服), never silently swapped."""
import json, re, glob, os
BASE=os.path.dirname(os.path.abspath(__file__))
# layout-flexible: scratchpad has carmall-wiper/ subdir; in the deployed repo, tools/ sits next to the web root
OUT=os.path.join(BASE,"carmall-wiper","data.json") if os.path.isdir(os.path.join(BASE,"carmall-wiper")) else os.path.join(BASE,"..","data.json")
STOCK=[14,16,18,19,20,21,22,24,26,28]
STOCKSET=set(STOCK)

SINGLE={
  "short":"BOSCH 通用型軟骨雨刷 旗艦款",
  "title":"BOSCH博世 通用型軟骨雨刷 旗艦款 (多尺寸任選)",
  "url":"https://www.carmall.com.tw/products/bosch博世-通用型軟骨雨刷",
  "price":499,"compare":800,
  "variants":{"14":{"id":82955922},"16":{"id":82956929},"18":{"id":82957036},"19":{"id":82957309},
    "20":{"id":82957310},"21":{"id":82957311},"22":{"id":82957312},"24":{"id":82957313},
    "26":{"id":82957314},"28":{"id":83147076}}
}

CN={"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,"十一":11,"十二":12}
GENRE=r"第[一二三四五六七八九十]+(?:\s*[/／]\s*[一二三四五六七八九十]+)*代?"
def gen_ints(model):
    out=set()
    for blk in re.findall(GENRE,model):
        for m in re.findall(r"[一二三四五六七八九十]+",blk):
            if m in CN: out.add(CN[m])
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

# ---------- load fitment + apply corrections ----------
fit=[]
for p in sorted(glob.glob(os.path.join(BASE,"pages","p*.json"))):
    fit+=json.load(open(p))
applied=0
for r in fit:
    k=nkey(r["brand"],r["model"],r.get("year",""))
    if k in corr:
        c=corr[k]
        if c.get("driver") is not None: r["driver"]=c["driver"]
        if c.get("passenger") is not None: r["passenger"]=c["passenger"]
        r["_src"]=c.get("source"); r["_srcnote"]=c.get("note"); applied+=1

# ---------- parse combos ----------
prods=json.load(open(os.path.join(BASE,"wiper_products.json")))
sz=re.compile(r"(\d{2})\s*\+\s*(\d{2})\s*吋")
combos=[]
for p in prods:
    t=p["title"]
    if "適用車型" not in t: continue
    if "-copy" in (p.get("handle") or ""): continue
    seg=t.split("適用車型",1)[1]; sm=sz.search(seg)
    d,pa=(int(sm.group(1)),int(sm.group(2))) if sm else (None,None)
    seg_m=seg[:sm.start()] if sm else seg
    seg_m=re.sub(r"[【】]"," ",seg_m); seg_m=re.sub(r"[（(][^（()）]*[)）]"," ",seg_m)
    seg_m=re.sub(r"\d{2,4}\s*[~\-～]\s*\d{0,4}"," ",seg_m)
    for w in ["通用款","_","、","~","～"]: seg_m=seg_m.replace(w," ")
    seg_m=re.sub(r"\s+"," ",seg_m).strip()
    parts=seg_m.split(None,1)
    combos.append({"brand":(parts[0].upper() if parts else ""),"model":(parts[1].strip() if len(parts)>1 else ""),
      "driver":d,"passenger":pa,"url":p["url"],"price":int(p["price"]),
      "stock":sum((v["qty"] or 0) for v in p["variants"]),"available":p["available"],
      "fam":fam_tokens(parts[1] if len(parts)>1 else ""),"gens":gen_ints(seg_m),"title":t,"_used":False})

def find_combo(brand,model,d,p,relaxed=False):
    bt=fit_fam_tokens(model); fg=gen_ints(model); fg1=next(iter(fg)) if len(fg)==1 else None
    best=None; bs=-1
    for c in combos:
        if c["brand"]!=brand.upper(): continue
        if c["driver"]!=d or c["passenger"]!=p: continue
        if not (bt & c["fam"]): continue
        if not relaxed and c["gens"] and fg1 and fg1 not in c["gens"]: continue
        score=len(bt & c["fam"])
        if c["gens"] and fg1 and fg1 in c["gens"]: score+=3
        elif not c["gens"]: score+=1
        if c["available"] and c["stock"]>0: score+=0.5
        if score>bs: bs=score; best=c
    return best

# ---------- build cascade (strict pass) ----------
brands={}; order=[]; seen_ded=set(); rows=[]
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
    else:
        entry["fit"]="universal"; entry["driver"]=r["driver"]; entry["passenger"]=r["passenger"]
        entry["driver_ok"]=r["driver"] in STOCKSET; entry["passenger_ok"]=r["passenger"] in STOCKSET
        entry["rear"]=r.get("rear")
        if r.get("_src"): entry["src"]=r["_src"]
        entry["_brand"]=brand; entry["_model"]=r["model"]
        rows.append(entry)
    if brand not in brands:
        brands[brand]={"name":brand,"models":{},"order":[]}; order.append(brand)
    bb=brands[brand]
    if mg not in bb["models"]:
        bb["models"][mg]={"name":mg,"entries":[]}; bb["order"].append(mg)
    bb["models"][mg]["entries"].append(entry)

def route_for(entry, relaxed=False):
    c=find_combo(entry["_brand"],entry["_model"],entry["driver"],entry["passenger"],relaxed)
    if c:
        c["_used"]=True
        return {"type":"combo","url":c["url"],"price":c["price"],"stock":c["stock"]}
    if entry["driver_ok"] and entry["passenger_ok"]:
        return {"type":"single"}
    return {"type":"contact"}

# strict pass
for e in rows: e["route"]=route_for(e, relaxed=False)
# relaxed second pass: link remaining unused combos to still-single rows (same brand+family+size), for gen-label drift
for e in rows:
    if e["route"]["type"]=="single":
        c=find_combo(e["_brand"],e["_model"],e["driver"],e["passenger"],relaxed=True)
        if c and not c["_used"]:
            c["_used"]=True
            e["route"]={"type":"combo","url":c["url"],"price":c["price"],"stock":c["stock"]}

# strip internal keys
for e in rows:
    e.pop("_brand",None); e.pop("_model",None)

out_brands=[{"name":bn,"models":[brands[bn]["models"][mn] for mn in brands[bn]["order"]]} for bn in order]
data={"meta":{"updated":"2026-06-25","source":"BOSCH 2026 通用雨刷型錄（美日韓車種）＋市場查證校正",
              "product_line":"BOSCH 通用型軟骨雨刷 旗艦款"},
      "stock_sizes":STOCK,"single":SINGLE,"brands":out_brands}
json.dump(data,open(OUT,"w"),ensure_ascii=False,indent=1)

# report
ncombo=sum(1 for e in rows if e["route"]["type"]=="combo")
nsingle=sum(1 for e in rows if e["route"]["type"]=="single")
ncontact=sum(1 for e in rows if e["route"]["type"]=="contact")
nded=sum(len(m["entries"]) for b in out_brands for m in b["models"])-len(rows)
print(f"corrections applied: {applied}")
print(f"universal rows: {len(rows)} | combo: {ncombo} | single: {nsingle} | contact(洽客服): {ncontact} | dedicated entries: {nded}")
unused=[c for c in combos if not c["_used"]]
print(f"combos: {len(combos)} | unused: {len(unused)}")
for c in unused: print("  UNUSED",c["brand"],c["model"],c["driver"],"+",c["passenger"],"->",c["url"].split('/products/')[-1])
contacts=[e for e in rows if e["route"]["type"]=="contact"]
if contacts:
    print("CONTACT (size not stocked):")
    for e in contacts: print("   ",e["label"],e["driver"],"/",e["passenger"])
print("wrote",OUT)
