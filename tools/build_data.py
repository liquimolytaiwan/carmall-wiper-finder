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

bosch_p=prod_by_handle(BOSCH_SINGLE_HANDLE); hella_p=prod_by_handle(HELLA_HANDLE)
bosch_var=size_variants(bosch_p); hella_var=size_variants(hella_p)
BOSCH_URL=prod_url(bosch_p,"https://www.carmall.com.tw/products/"+BOSCH_SINGLE_HANDLE)
HELLA_URL=prod_url(hella_p,"https://www.carmall.com.tw/products/"+HELLA_HANDLE)

# ---------- combos (BOSCH 軟骨, 2支/組) ----------
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
      "driver":d,"passenger":pa,"url":prod_url(p,p.get("url")),"price":int(p["price"]),
      "stock":sum((v["qty"] or 0) for v in p["variants"]),"available":p["available"],
      "fam":fam_tokens(parts[1] if len(parts)>1 else ""),"gens":gen_ints(seg_m),"_used":False})

def find_combo(brand,model,d,p,relaxed=False):
    bt=fit_fam_tokens(model); fg=gen_ints(model); fg1=next(iter(fg)) if len(fg)==1 else None
    best=None; bs=-1
    for c in combos:
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

def single_option(brand,label,material,url,var,d,p):
    dv=var.get(d); pv=var.get(p)
    if not (dv and pv and dv["ok"] and pv["ok"]): return None
    return {"brand":brand,"label":label,"material":material,"kind":"single",
            "url":url+("?variant="+str(dv["id"]) if dv.get("id") else ""),
            "driver":d,"passenger":p,"driverPrice":dv["price"],"passengerPrice":pv["price"],
            "price":dv["price"]+pv["price"]}

# ---------- build cascade ----------
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
        entry["rear"]=r.get("rear"); entry["_brand"]=brand; entry["_model"]=r["model"]; rows.append(entry)
    if brand not in brands:
        brands[brand]={"name":brand,"models":{},"order":[]}; order.append(brand)
    bb=brands[brand]
    if mg not in bb["models"]:
        bb["models"][mg]={"name":mg,"entries":[]}; bb["order"].append(mg)
    bb["models"][mg]["entries"].append(entry)

# BOSCH combo: strict then relaxed (gen-label drift)
for e in rows: e["_combo"]=find_combo(e["_brand"],e["_model"],e["driver"],e["passenger"],False)
for e in rows:
    if e["_combo"]: e["_combo"]["_used"]=True
for e in rows:
    if not e["_combo"]:
        c=find_combo(e["_brand"],e["_model"],e["driver"],e["passenger"],True)
        if c and not c["_used"]: c["_used"]=True; e["_combo"]=c

# assemble options per row
for e in rows:
    d,p=e["driver"],e["passenger"]; opts=[]
    if e["_combo"]:
        c=e["_combo"]
        opts.append({"brand":"BOSCH","label":"BOSCH 通用軟骨 旗艦款","material":"軟骨","kind":"combo","url":c["url"],"price":c["price"]})
    else:
        o=single_option("BOSCH","BOSCH 通用軟骨 旗艦款","軟骨",BOSCH_URL,bosch_var,d,p)
        if o: opts.append(o)
    oh=single_option("HELLA","HELLA 三節式 Hybrid","三節式",HELLA_URL,hella_var,d,p)
    if oh: opts.append(oh)
    e["options"]=opts
    if not opts: e["route"]={"type":"contact"}
    for k in ("_brand","_model","_combo"): e.pop(k,None)

out_brands=[{"name":bn,"models":[brands[bn]["models"][mn] for mn in brands[bn]["order"]]} for bn in order]
data={"meta":{"updated":"2026-06-25","source":"BOSCH 2026 通用雨刷型錄（美日韓）＋市場查證校正",
              "lines":["BOSCH 通用軟骨 旗艦款","HELLA 三節式 Hybrid"]},
      "brands":out_brands}
json.dump(data,open(OUT,"w"),ensure_ascii=False,indent=1)

# report
def has(line): return sum(1 for e in rows for o in e["options"] if o["brand"]==line)
ncombo=sum(1 for e in rows if any(o["kind"]=="combo" for o in e["options"]))
print(f"corrections applied: {applied}")
print(f"BOSCH single-product variants: {sorted(bosch_var)} | HELLA variants: {sorted(hella_var)}")
print(f"universal rows: {len(rows)} | BOSCH option: {has('BOSCH')} | HELLA option: {has('HELLA')} | combos used: {ncombo}")
print(f"rows with 0 options (contact): {sum(1 for e in rows if not e['options'])}")
print("wrote",OUT)
