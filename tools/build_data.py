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
# 世代之外還能區分同車款的字眼。gen_label 拿它做顯示，find_combo 拿它做排序 ——
# 「第四代」與「第四代小改款」在 fam / gens 上完全一樣，只有這些字分得出來。
VARIANT_KW=["小改款","Hyper","NEO","電動","進口","美規","日規","卡旺"]

def variant_kw(text):
    return {k for k in VARIANT_KW if k in (text or "")}

def gen_label(model):
    g=[re.sub(r"\s*[/／]\s*","/",x.strip()) for x in re.findall(GENRE,model)]
    pv=[p.strip() for p in re.findall(r"[（(]([^（()）]*)[)）]",model) if p.strip()]
    extra=[kw for kw in VARIANT_KW if kw in model and not any(kw in x for x in g)]
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

# sp-p*.json = 型錄「專用雨刷對照表 美日韓車種」(型錄 22-23 頁)。
# 這些車**已經在查詢器裡**（通用頁把它們列出來但尺寸留白），只是後擋代碼只印在這一段。
# 所以這裡是「補欄位」不是「加車」—— 直接新增會撞到 dedicated 的去重，
# 後來的那筆被丟掉，連帶把剛拿到的後擋代碼一起丟掉。
sp_rows=[]
for p in sorted(glob.glob(os.path.join(BASE,"pages","sp-p*.json"))):
    sp_rows+=json.load(open(p))
# 兩段型錄對同一台車的年份寫法常常差一點（M7 第二代「14-」vs「14-20」、Q30「16」vs「16-22」）。
# 只比對完全相同的字串會把同一台車當成兩台，下拉選單就出現兩個看起來一樣、結果卻不同的選項。
# 所以字串對不上時改用「同車廠同車款＋年份區間有重疊」來認人；認不出唯一一台就報出來不猜。
def yspan(y):
    ns=[int(x) for x in re.findall(r"\d{2,4}", y or "")]
    def full(n): return n if n>=1000 else (1900+n if n>=90 else 2000+n)
    if not ns: return None
    lo=full(ns[0]); hi=full(ns[1]) if len(ns)>1 else (lo if not re.search(r"\d\s*[-~～]\s*$", y or "") else 9999)
    if len(ns)==1 and re.search(r"[-~～]", y or ""): hi=9999
    return (lo,max(lo,hi))
def overlaps(a,b):
    sa,sb=yspan(a),yspan(b)
    return bool(sa and sb and sa[0]<=sb[1] and sb[0]<=sa[1])

# 兩段型錄連車款寫法都會差：「JUKE (第二代)」vs「JUKE 第二代」是同一台車。
# mkey 去掉標點只留字，pkey 再把括號內容整段拿掉（「MODEL X (噴水接頭)」→「MODEL X」），
# 兩層都對不到唯一一台才當成新車款。
def mkey(b,m): return (b.upper().strip(), re.sub(r"[^0-9A-Za-z一-鿿]+","",m or "").upper())
def pkey(b,m): return mkey(b, re.sub(r"[（(][^（()）]*[)）]"," ",m or ""))
by_key={}; by_model={}; by_pmodel={}
for r in fit:
    by_key.setdefault(nkey(r["brand"],r["model"],r.get("year","")),r)
    by_model.setdefault(mkey(r["brand"],r["model"]),[]).append(r)
    by_pmodel.setdefault(pkey(r["brand"],r["model"]),[]).append(r)
sp_filled=sp_added=sp_conflict=0; sp_unresolved=[]
def fill_rear(tgt,r):
    global sp_filled,sp_conflict
    if not r.get("rear"): return
    if not tgt.get("rear"):
        tgt["rear"]=r["rear"]
        if r.get("rearSize") is not None: tgt["rearSize"]=r["rearSize"]
        sp_filled+=1
    elif tgt["rear"]!=r["rear"]:
        sp_conflict+=1
        print(f"  ⚠️ 後擋代碼衝突 {r['brand']} {r['model']} {r.get('year')}: "
              f"既有 {tgt['rear']} vs 專用頁 {r['rear']}（保留既有的）")
for r in sp_rows:
    tgt=by_key.get(nkey(r["brand"],r["model"],r.get("year","")))
    if tgt is not None: fill_rear(tgt,r); continue
    cands=by_model.get(mkey(r["brand"],r["model"])) or by_pmodel.get(pkey(r["brand"],r["model"])) or []
    if not cands:                      # 型錄他處根本沒這台車 → 這才是真的新車款
        fit.append(r)
        by_key[nkey(r["brand"],r["model"],r.get("year",""))]=r
        by_model.setdefault(mkey(r["brand"],r["model"]),[]).append(r)
        by_pmodel.setdefault(pkey(r["brand"],r["model"]),[]).append(r)
        sp_added+=1; continue
    hit=[c for c in cands if overlaps(c.get("year",""),r.get("year",""))]
    if len(hit)==1:
        fill_rear(hit[0],r)
    else:
        sp_unresolved.append((r,[c.get("year","") for c in cands]))
applied=0; corr_used=set()
for r in fit:
    k=nkey(r["brand"],r["model"],r.get("year",""))
    if k in corr:
        c=corr[k]
        if c.get("driver") is not None: r["driver"]=c["driver"]
        if c.get("passenger") is not None: r["passenger"]=c["passenger"]
        # 型錄把後擋欄位留白、但市場查證確定有對應件時，也走 corrections（例如 KAROQ）。
        if c.get("rear") is not None:
            r["rear"]=c["rear"]
            if c.get("rearSize") is not None: r["rearSize"]=c["rearSize"]
        applied+=1
        corr_used.add(k)
# corrections 的 model 要寫型錄原始寫法（"CIVIC 第七代"），不是查詢器顯示的車款名（"CIVIC"）。
# 寫錯的那筆會安靜地什麼都不做 —— 查詢器照樣長出舊尺寸、也不會報錯，只有逐筆去比才看得出來。
# 所以配不到任何車的 correction 一定要吼出來。
corr_unused=[c for k,c in corr.items() if k not in corr_used]

# ---------- row splits ----------
# 型錄有幾列把兩台以上尺寸不同的車併成一列（"G25 / M25"、"MUSTANG / MACH-E"）。
# 那種列填哪個尺寸都會害另一台車的車主買錯 —— 不是 corrections 改得動的，要拆成獨立的列。
#
# 為什麼不直接改 pages/*.json：那些是**型錄逐頁判讀的原文**，README 明講「勿手改」。
# 把查證結論寫進去，日後重新判讀型錄時會跟人工拆分的列衝突，而且分不出哪些是型錄印的、
# 哪些是我們拆的。所以跟 corrections.json 一樣獨立成一份，型錄原文保持可重新判讀。
split_added=0; splits_unused=[]
spath=os.path.join(BASE,"row_splits.json")
if os.path.exists(spath):
    out=[]
    idx={}
    for sp in json.load(open(spath)):
        idx[nkey(sp["brand"],sp["model"],sp.get("year",""))]=sp
    used=set()
    for r in fit:
        k=nkey(r["brand"],r["model"],r.get("year",""))
        sp=idx.get(k)
        if not sp:
            out.append(r); continue
        used.add(k)
        for part in sp["into"]:
            row=dict(r)                       # 後擋代碼等欄位沿用原列
            row["model"]=part["model"]
            if part.get("year"): row["year"]=part["year"]
            for f in ("driver","passenger","rear","rearSize"):
                if f in part: row[f]=part[f]
            out.append(row); split_added+=1
    fit=out
    splits_unused=[sp for k,sp in idx.items() if k not in used]

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

# Multi-fit rear blades: not vehicle-specific parts, so they can never be reached by code
# matching and would sit in the "matched no car" list forever. They are offered instead as
# a same-size substitute when a car's exact part is not stocked.
# This is an explicit allowlist on purpose — telling a customer a blade fits their car is a
# promise, so a part only lands here after its multi-fit claim has been checked by a human.
# AM40H (3397016509) = Bosch multi-clip 400mm, ships with 4 arm adapters.
MULTIFIT_REAR={"AM40H"}

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

# size -> multi-fit product, used only when the car's own part is not stocked
rear_multifit={}
for code in MULTIFIT_REAR:
    pr=rear_by_code.get(code)
    if pr and pr.get("size") is not None: rear_multifit[pr["size"]]=pr

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
      # 車款名同時用「去掉第一個字（品牌）之後」與「整段」兩種切法。
      # 原本只用前者，因為標題慣例是「適用車型 <品牌> <車款>」——
      # 但 MAZDA 的車款名本身就叫「MAZDA 6」，慣例寫出來是「MAZDA MAZDA 6」，
      # 看起來像贅字。2026-08-17 有人把它清成「MAZDA 6」，切完之後車款只剩 "6"，
      # 四個 MAZDA 6 組合當場全部配不到車 —— 而且商品頁看起來完全正常。
      # 兩種切法都收進去，這種「把重複的品牌名拿掉」就不會再打斷比對。
      "fam":fam_tokens(parts[1] if len(parts)>1 else "")|fam_tokens(seg_m),
      "gens":gen_ints(seg_m)|gen_span(raw_m),
      "kw":variant_kw(raw_m),
      # 商品標題裡的年份（"第一代(07~11)"）。世代分不出來時，這是唯一還能分辨
      # 「同車款、同尺寸、不同世代」兩組商品的線索 —— 見 find_combo 的 ymatch。
      "years":yspan(re.search(r"\d{2,4}\s*[~\-～]\s*\d{0,4}", raw_m).group(0))
              if re.search(r"\d{2,4}\s*[~\-～]\s*\d{0,4}", raw_m) else None,
      "_used":False})

def find_combo(brand,model,d,p,line,relaxed=False,year=None):
    """挑出這台車該用的專屬組合。

    分數只用來排名，真正的門檻是上面那幾個 continue。世代（gens）是主要的辨識依據，
    但**型錄的車款名不一定帶世代**（INNOVA 就只寫 "INNOVA"，兩列靠年份區分），
    這時 fg1 是 None，所有候選的分數會完全一樣 —— 誰先被掃到誰贏，另一組永遠配不到車。
    2026-08-17 就是這樣：INNOVA 兩列的尺寸都修正成 26/16 之後，第一代那組同時吃掉兩列，
    第二代那組變成孤兒。所以同分時再比年份，把它當純粹的 tie-break：
    分數已經分出高下的情況完全不受影響。
    """
    bt=fit_fam_tokens(model); fg=gen_ints(model); fg1=next(iter(fg)) if len(fg)==1 else None
    ys=yspan(year) if year else None
    fkw=variant_kw(model)
    best=None; bs=(-1,-1)
    for c in combos:
        if c["line"]!=line: continue
        if c["brand"]!=brand.upper(): continue
        if c["driver"]!=d or c["passenger"]!=p: continue
        if not (c["available"] and c["stock"]>0): continue   # availability gate
        if not (bt & c["fam"]): continue
        if not relaxed and c["gens"] and fg1 and fg1 not in c["gens"]: continue
        ymatch=0
        if ys and c["years"]:
            if c["years"][0]<=ys[0] and ys[1]<=c["years"][1]:
                ymatch=2 if ys==c["years"] else 1
            elif not relaxed:
                # 商品標題自己寫了年份、而且沒涵蓋這一列 —— 那張卡就是在講別台車。
                # INNOVA (11-16) 對上「第一代(07~11)」、LS (12-17) 對上「第四代(07~12)」
                # 都是這樣：尺寸剛好相同、世代也對得上（或分不出來），只有年份在抗議。
                # 商品**能不能用**跟商品**標題有沒有在講這台車**是兩件事，後者不能將就。
                continue
        score=len(bt & c["fam"])
        if c["gens"] and fg1 and fg1 in c["gens"]: score+=3
        elif not c["gens"]: score+=1
        # 「第四代」與「第四代小改款」的 fam 與 gens 一模一樣 —— 這是唯一分得出來的訊號。
        # 2026-08-17：LS 第四代那組年份放寬成 (07~17) 之後，靠年份就贏過了專屬的
        # 「第四代小改款」那組，把後者擠成孤兒 —— 而那組有自己的售價與庫存。
        if fkw and (fkw & c["kw"]): score+=2
        if (score,ymatch)>bs: bs=(score,ymatch); best=c
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

def attach_rear(e):
    """Exact part first; a same-size multi-fit blade only when the exact one is not stocked.

    The substitute is keyed on the size the CATALOGUE prints for that car, never on a size
    inferred from the part code — inferring it would be exactly the mechanical substitution
    this project forbids."""
    ro=rear_by_code.get((e.get("rear") or "").upper())
    if ro:
        e["rearOption"]=ro; return
    alt=rear_multifit.get(e.get("rearSize"))
    if e.get("rear") and alt: e["rearAlt"]=alt

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
        entry["rear"]=r.get("rear")
        if r.get("rearSize") is not None: entry["rearSize"]=r["rearSize"]
        ded_rows.append(entry)
    else:
        entry["fit"]="universal"; entry["driver"]=r["driver"]; entry["passenger"]=r["passenger"]
        entry["rear"]=r.get("rear")
        if r.get("rearSize") is not None: entry["rearSize"]=r["rearSize"]
        entry["_brand"]=brand; entry["_model"]=r["model"]; rows.append(entry)
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
        e[ck]=find_combo(e["_brand"],e["_model"],e["driver"],e["passenger"],L["key"],False,
                         e.get("year"))
    for e in rows:
        if e[ck]: e[ck]["_used"]=True
    for e in rows:
        if not e[ck]:
            c=find_combo(e["_brand"],e["_model"],e["driver"],e["passenger"],L["key"],True,
                         e.get("year"))
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
    attach_rear(e)
    for k in ["_brand","_model"]+["_combo_"+L["key"] for L in LINES]: e.pop(k,None)

# Dedicated-front rows (歐系全部，加上美日韓的專用接頭車) get the same rear treatment.
for e in ded_rows:
    attach_rear(e)

# 顯示用中文名。**只加欄位，不動 name** —— brands[].name / models[].name 是跨專案的鍵，
# carmall-blog-automation 的 vehicles.py 靠它比對車款，改名等於打壞別人的資料契約
# （2026-08-06 已經因此壞過一次）。
zh={}
zpath=os.path.join(BASE,"brand_names.json")
if os.path.exists(zpath):
    zh={k:v for k,v in json.load(open(zpath)).items() if not k.startswith("_")}
missing_zh=sorted(b for b in brands if b not in zh)

# 2026-08-14 Jerry 指定：車廠與車款都照英文字母排序（原本是型錄出現順序）。
# 年份選項不排 —— 那是世代順序，照字母排會變成亂序。
# casefold 而不是預設排序：預設是照碼位排，大寫字母全部排在小寫前面，
# HYUNDAI 的 i10／i30 會掉到 VERNA 後面、BMW 的 i3／i4 會掉到所有大寫車款後面。
out_brands=[{"name":bn,"tw":zh.get(bn,""),
             "models":[brands[bn]["models"][mn] for mn in sorted(brands[bn]["order"], key=str.casefold)]}
            for bn in sorted(order, key=str.casefold)]
# 這是「資料查證日」不是「重建日」—— 排程每天重抓價格庫存也會重建，
# 如果改成自動抓當天，每次價格刷新都會宣稱重新查證過一次。改尺寸／校正時才手動更新。
data={"meta":{"updated":"2026-08-17",
              "source":"BOSCH 2026 雨刷型錄（通用美日韓＋專用歐系）＋市場查證校正",
              "lines":["BOSCH 通用軟骨 旗艦款","HELLA 三節式 Hybrid"]},
      "brands":out_brands}
json.dump(data,open(OUT,"w"),ensure_ascii=False,indent=1)

# report
def has(line): return sum(1 for e in rows for o in e["options"] if o["brand"]==line)
def ncombo(line): return sum(1 for e in rows for o in e["options"]
                            if o["brand"]==line and o["kind"]=="combo")
print(f"車廠中文名: {sum(1 for b in brands if zh.get(b))}/{len(brands)} 有中文"
      + (f"｜brand_names.json 沒收錄: {missing_zh}" if missing_zh else ""))
print(f"corrections applied: {applied}/{len(corr)}"
      + (f"｜拆列：{split_added} 列（原 {split_added and len(json.load(open(spath)))} 列併車拆開）" if split_added else ""))
if splits_unused:
    print(f"  ⚠️  配不到任何車、完全沒作用的 row_split：{len(splits_unused)}")
    for sp in splits_unused:
        print(f"    - {sp['brand']} {sp['model']} {sp.get('year')}"
              f"（型錄裡沒有這個 車廠+車款+年份 的組合，model 要寫型錄原文）")
if corr_unused:
    print(f"  ⚠️  配不到任何車、完全沒作用的 correction：{len(corr_unused)}")
    for c in corr_unused:
        print(f"    - {c['brand']} {c['model']} {c.get('year')}"
              f"（型錄裡沒有這個 車廠+車款+年份 的組合；model 要寫型錄原文，例如「CIVIC 第七代」不是「CIVIC」）")
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
print(f"美日韓專用頁: 補上既有車款的後擋代碼 {sp_filled} 筆、新增 {sp_added} 列"
      + (f"、代碼衝突 {sp_conflict} 筆" if sp_conflict else ""))
if sp_unresolved:
    print(f"  ⚠️ 對不到唯一一台車、已略過（沒有猜）：{len(sp_unresolved)}")
    for r,yrs in sp_unresolved:
        print(f"    - {r['brand']} {r['model']} {r.get('year')}"
              f"（後擋 {r.get('rear') or '無'}）｜型錄他處同車款年份：{yrs}")
print(f"rear products in stock: {len(rear_by_code)} ({', '.join(sorted(rear_by_code))})")
print(f"  rows with a rear code: {rear_with_code} | now buyable: {rear_rows}"
      + (f" ({rear_rows*100//rear_with_code}%)" if rear_with_code else ""))
print(f"    其中通用美日韓 {sum(1 for e in rows if e.get('rearOption'))}"
      f" / 專用（含歐系）{sum(1 for e in ded_rows if e.get('rearOption'))}")
alt_rows=sum(1 for e in all_rows if e.get("rearAlt"))
if rear_multifit:
    print(f"  多用途替代款: {', '.join(sorted(MULTIFIT_REAR))} → 補上 {alt_rows} 個"
          f"「專用款沒貨但尺寸相同」的車款列")
used_rear|={e["rearAlt"]["code"] for e in all_rows if e.get("rearAlt")}
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
