#!/usr/bin/env python3
"""雨刷查詢器 — 全目錄尺寸事實查證（兩份獨立台灣來源交叉比對）

來源 A：旭益汽車 secar.com.tw 雨刷尺寸對照參考表（HTML 表格 ＋ HONDA 圖片表判讀）
來源 B：YARK 亞克科技 雨刷規格查詢 yark.jplus.tw（同一年份可能列多組尺寸，全收）

判定規則：
* 差 1 吋不算錯 —— 對照表自己就會同時列 18 吋與 19 吋當同一台車的選項，
  查詢器的 policyA 也早就用「最接近的現貨尺寸」替代過。只有差 ≥2 吋才當問題。
* 只有兩份來源彼此一致、而且都跟型錄差 ≥2 吋，才列為高信心錯誤。

唯讀，只產報告，不改任何資料。
"""
import json, re, unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCRATCH = HERE          # 來源快照與這支腳本放一起
TOL = 1          # 幾吋以內視為相容

data = json.load(open(ROOT / "data.json"))

# ---------------- 名稱正規化 ----------------
# 旭益的 HONDA 表用阿拉伯數字寫世代（"CRV 2代"），其他地方用國字（"第七代"）——
# 只認國字的話，整個 HONDA 品牌會因為 token 對不起來而全部落到「查不到」。
GEN = re.compile(r"(第[一二三四五六七八九十]+代|[一二三四五六七八九十]代|\d+\s*代|前期|後期|改款|小改|國產|進口|系列|年之後|之後)")

def _clean(s):
    s = unicodedata.normalize("NFKC", s).upper()
    s = re.sub(r"\(.*?\)", " ", s)
    s = GEN.sub(" ", s)
    s = re.sub(r"[一-鿿]", " ", s)
    return s

def norm_model(s):
    return re.sub(r"[\s\-_./·、'`’\[\]+]+", "", _clean(s)).strip()

def tokens(s):
    return tuple(t for t in re.sub(r"[\-_./·、'`’\[\]+]", " ", _clean(s)).split() if t)

ALIAS = {
    ("TOYOTA", "FT86"): ["86"],
    ("TOYOTA", "PRADO"): ["LANDCRUISERPRADO"],
    ("TOYOTA", "4RUNNER"): ["SURF"],
    ("LUXGEN", "M7"): ["7MPV"],
    ("LUXGEN", "U7"): ["7SUV"],
    ("MITSUBISHI", "VERYCA"): ["VARICA"],
    ("HYUNDAI", "IONIQ"): ["IONIQHYBRID", "LONIQHYBRID"],
}

def variants(s):
    out = {norm_model(p) for p in re.split(r"[/／]", s)}
    out.add(norm_model(s))
    return {x for x in out if x}

def brand_key(name):
    return re.sub(r"\s+", "", re.sub(r"[一-鿿]", "", name)).upper()

BRAND_ALIAS = {"BENZ": "MERCEDES-BENZ", "VW": "VOLKSWAGEN", "INFINITI": "INFINTI"}

# ---------------- 年份 ----------------
OPEN = 9999
def yy(n): return 1900 + n if n >= 90 else 2000 + n

def our_years(y):
    m = re.match(r"^(\d{2})\s*-\s*(\d{2})?$", y.strip())
    return (yy(int(m.group(1))), yy(int(m.group(2))) if m.group(2) else OPEN) if m else None

def parse_year_text(t):
    ys = re.findall(r"(\d{4})", t)
    if not ys: return None
    a = int(ys[0])
    b = int(ys[1]) if len(ys) >= 2 else (OPEN if re.search(r"[~～\-]\s*$|之後|迄今|以後", t) else a)
    return (a, b)

def clip(y): return 2027 if y >= OPEN else y

def score(a, b):
    """年份吻合度。對照表常有「2016~迄今」這種跨世代的籠統列，它跟任何 2016 後的年段
    都 100% 重疊卻不見得在講同一台車，所以另外要求起始年相差 ≤3 年。"""
    a0, a1, b0, b1 = clip(a[0]), clip(a[1]), clip(b[0]), clip(b[1])
    lo, hi = max(a0, b0), min(a1, b1)
    if hi < lo: return None
    cover = (hi - lo) / min(max(a1 - a0, 1), max(b1 - b0, 1))
    return min(cover, 0.3) * 0.5 if abs(a0 - b0) > 3 else cover

HIGH = 0.6

def name_match(oc, ot, rc, rt, alias):
    if oc & rc: return True
    if alias and (rc & set(alias)): return True
    if ot and rt:
        n = min(len(ot), len(rt))
        if ot[:n] == rt[:n] or ot[-n:] == rt[-n:]: return True
    return False

def build(rows):
    idx = defaultdict(list)
    for bk, model, y0, y1, sizes, raw in rows:
        idx[bk].append((variants(model), tokens(model), y0, y1, sizes, raw))
    return idx

# --- 來源 A：旭益（每列一組尺寸）---
rowsA = []
for blk in json.load(open(SCRATCH / "secar_table.json")):
    bk = brand_key(blk["brand"])
    for r in blk["rows"]:
        y = parse_year_text(r[1])
        if not y: continue
        y1 = parse_year_text(r[2])
        hi = y1[0] if y1 else (OPEN if "今" in r[2] else y[0])
        try:
            d, p = int(re.search(r"\d+", r[3]).group()), int(re.search(r"\d+", r[4]).group())
        except AttributeError:
            continue
        rowsA.append((bk, r[0], y[0], hi, {(d, p)}, f"{r[0]} {r[1]}~{r[2]} {d}/{p}"))
for r in json.load(open(SCRATCH / "honda_secar.json")):
    y = parse_year_text(r[1]); y1 = parse_year_text(r[2])
    rowsA.append(("HONDA", r[0], y[0], y1[0] if y1 else OPEN,
                  {(int(r[3]), int(r[4]))}, f"{r[0]} {r[1]}~{r[2]} {r[3]}/{r[4]}"))
A = build(rowsA)

# --- 來源 B：YARK（同一年份可有多組尺寸，全部收成一個集合）---
gb = defaultdict(set)
for r in json.load(open(SCRATCH / "yark_table.json")):
    gb[(r["brand"], r["model"], r["years"])].add((r["driver"], r["passenger"]))
rowsB = []
for (br, model, years), sizes in gb.items():
    y = parse_year_text(years)
    if not y: continue
    rowsB.append((brand_key(br), model, y[0], y[1], sizes,
                  f"{model} {years} " + "／".join(f"{d}/{p}" for d, p in sorted(sizes))))
B = build(rowsB)

NEAR = 0.5

# --- 來源 C：網路流傳的舊版 BOSCH 型錄文字版（同一份型錄的另一次抄寫）---
# 它跟我們的型錄同源，所以「不能」拿來當市場事實的第二意見；
# 它能抓的是另一種錯：這次看圖判讀有沒有抄錯行。
rowsC = []
for r in json.load(open(SCRATCH / "pixnet_table.json")):
    y = our_years(r["years"]) or parse_year_text(r["years"])
    if not y: continue
    rowsC.append((brand_key(r["brand"]), r["model"], y[0], y[1],
                  {(r["driver"], r["passenger"])},
                  f"{r['model']} ({r['years']}) {r['driver']}/{r['passenger']}"))
C = build(rowsC)

def lookup(idx, brand, model, yrs):
    """回傳 (最佳列, 分數, 是否同源內互相矛盾)。

    同一份對照表常會有兩列都涵蓋同一個年份（例如 ACCORD 7 代 2002~2006 與 8 代
    2003~2013 重疊）。這種情況下「最高分那列」只是我挑的，不是那份來源的定論，
    所以標成 ambiguous，不能拿去當交叉印證。"""
    bks = {brand_key(brand)}
    if brand in BRAND_ALIAS: bks.add(brand_key(BRAND_ALIAS[brand]))
    oc, ot = variants(model), tokens(model)
    alias = ALIAS.get((brand, "".join(ot)))
    hits = []
    for bk in bks:
        for rc, rt, y0, y1, sizes, raw in idx.get(bk, []):
            if not name_match(oc, ot, rc, rt, alias) or not yrs: continue
            sc = score(yrs, (y0, y1))
            if sc is not None:
                hits.append((sc, sizes, raw))
    if not hits: return None, 0.0, False
    hits.sort(key=lambda x: -x[0])
    best_s, sizes, raw = hits[0]
    near = [h for h in hits if h[0] >= NEAR]
    allsz = set()
    for h in near: allsz |= h[1]
    ambiguous = len(near) > 1 and max(
        max(abs(a[0]-b[0]), abs(a[1]-b[1])) for a in allsz for b in allsz) > TOL
    return (sizes, raw), best_s, ambiguous

def gap(ours, sizes):
    """型錄尺寸與來源尺寸集合的最小差距（吋）"""
    return min(max(abs(ours[0] - d), abs(ours[1] - p)) for d, p in sizes)

def between(s1, s2):
    return min(max(abs(a[0] - b[0]), abs(a[1] - b[1])) for a in s1 for b in s2)

results = []
for b in data["brands"]:
    for m in b["models"]:
        for e in m["entries"]:
            if not e.get("driver"): continue
            yrs = our_years(e.get("year", ""))
            ours = (e["driver"], e["passenger"])
            ra, sa, amb_a = lookup(A, b["name"], m["name"], yrs)
            rb, sb, amb_b = lookup(B, b["name"], m["name"], yrs)
            rc, sc, _ = lookup(C, b["name"], m["name"], yrs)
            av = ra if ra and sa >= HIGH else None
            bv = rb if rb and sb >= HIGH else None
            cv = rc if rc and sc >= HIGH else None
            ga = gap(ours, av[0]) if av else None
            gbb = gap(ours, bv[0]) if bv else None
            if av and bv:
                if ga <= TOL or gbb <= TOL:
                    verdict = "OK"
                elif between(av[0], bv[0]) <= TOL:
                    verdict = "ERR2"        # 兩來源彼此一致，一起反對型錄
                else:
                    verdict = "CONFLICT"
            elif av or bv:
                g = ga if av else gbb
                verdict = "OK1" if g <= TOL else "ERR1"
            else:
                verdict = "UNKNOWN"
            if verdict == "ERR2" and (amb_a or amb_b):
                verdict = "AMBIG"      # 來源自己內部就對不起來，不能算兩源印證
            results.append({
                "amb_a": amb_a, "amb_b": amb_b,
                "C": sorted(cv[0]) if cv else None, "C_raw": cv[1] if cv else None,
                "C_gap": gap(ours, cv[0]) if cv else None,
                "brand": b["name"], "model": m["name"], "year": e.get("year"), "ours": ours,
                "verdict": verdict,
                "A": sorted(av[0]) if av else None, "A_raw": av[1] if av else None, "A_gap": ga,
                "B": sorted(bv[0]) if bv else None, "B_raw": bv[1] if bv else None, "B_gap": gbb,
                "combo": any(o.get("kind") == "combo" for o in e.get("options", [])),
            })

json.dump(results, open(HERE / "cross_check_results.json", "w"), ensure_ascii=False, indent=1)

from collections import Counter
c = Counter(r["verdict"] for r in results)
LABEL = {"OK": "至少一份來源與型錄相符（差 ≤1 吋）", "OK1": "只查到一份來源，與型錄相符",
         "ERR2": "兩份來源一致、都與型錄差 ≥2 吋 ★", "ERR1": "只有一份來源，與型錄差 ≥2 吋",
         "AMBIG": "來源自己內部就有兩種答案，要逐筆查", "CONFLICT": "兩份來源互相打架",
         "UNKNOWN": "兩份來源都查不到"}
print(f"共 {len(results)} 筆")
for k in ["OK", "OK1", "ERR2", "AMBIG", "ERR1", "CONFLICT", "UNKNOWN"]:
    print(f"  {LABEL[k]:<34} {c[k]:>4}")

def fmt(v): return "／".join(f"{d}/{p}" for d, p in v) if v else "—"

for k in ["ERR2", "AMBIG", "ERR1", "CONFLICT", "UNKNOWN"]:
    rs = [r for r in results if r["verdict"] == k]
    if not rs: continue
    print(f"\n===== {LABEL[k]}（{len(rs)}）=====")
    for r in sorted(rs, key=lambda x: (x["brand"], x["model"], x["year"])):
        print(f"{r['brand']:<11}{r['model']:<24}{r['year']:<8}"
              f"型錄 {r['ours'][0]}/{r['ours'][1]:<6}旭益 {fmt(r['A']):<14}YARK {fmt(r['B']):<16}"
              f"{'[有組合商品]' if r['combo'] else ''}")
        cstr = f"  |  舊版BOSCH文字版: {r['C_raw']}" if r["C_raw"] else ""
        if k != "UNKNOWN":
            print(f"{'':<11}   旭益: {r['A_raw']}  |  YARK: {r['B_raw']}{cstr}")
        elif r["C_raw"]:
            print(f"{'':<11}   舊版BOSCH文字版: {r['C_raw']}"
                  + ("   ← 與現在的型錄判讀不同，可能是判讀錯誤" if r["C_gap"] and r["C_gap"] > TOL else ""))
