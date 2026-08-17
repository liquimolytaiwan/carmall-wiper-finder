#!/usr/bin/env python3
"""抓 YARK（亞克科技）雨刷規格對照表，當作第二份獨立來源。

只抓我們目錄裡有尺寸的 18 個品牌，每個請求之間有間隔，不打整站。
輸出 yark_table.json：[{brand, model, years, driver, passenger}]
"""
import json, re, time, urllib.request, urllib.parse
from pathlib import Path

# 輸出就寫在這支腳本旁邊 —— cross_check.py 讀的就是這份 yark_table.json，
# 寫到別的地方等於重抓完也刷新不了稽核用的快照。
HERE = Path(__file__).resolve().parent
OUT = HERE / "yark_table.json"
BASE = "https://yark.jplus.tw/DyDd.php"

BRANDS = {
    "CMC": ["B9"], "DAIHATSU": ["B11"], "FORD": ["B13"], "HONDA": ["B14"],
    "HYUNDAI": ["B15"], "INFINITI": ["B52", "B16"], "ISUZU": ["B17"],
    "KIA": ["B20"], "LEXUS": ["B22"], "LUXGEN": ["B23"], "MAZDA": ["B25"],
    "MITSUBISHI": ["B28"], "NISSAN": ["B29"], "PROTON": ["B33"],
    "SSANGYONG": ["B39"], "SUBARU": ["B38"], "SUZUKI": ["B40"], "TOYOTA": ["B42"],
}

class ScrapeIncomplete(RuntimeError):
    """抓不到就要炸。

    以前這裡是「重試三次還不行就回空字串」—— 那會讓那個品牌／車款／年份整段從快照消失，
    腳本還是 exit 0。接著 cross_check.py 會把受影響的車判成「查不到第二來源」，
    看起來跟「台灣對照表本來就沒收這台車」一模一樣 —— 型錄真的有錯也會被這樣蓋掉。
    寧可整批失敗重跑，也不要產出一份看起來完整的殘缺快照。
    """


def post(cid):
    data = urllib.parse.urlencode({"cid": cid}).encode()
    req = urllib.request.Request(BASE, data=data,
                                 headers={"User-Agent": "Mozilla/5.0",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            if attempt < 2:
                time.sleep(1.5)
    raise ScrapeIncomplete(f"cid={cid} 重試三次都失敗：{last}")

def options(htmltxt):
    out = []
    for v, t in re.findall(r'<option value="([^"]*)"[^>]*>(.*?)</option>', htmltxt, re.S):
        t = re.sub(r"\s+", " ", t).strip()
        if v and v != "0" and "選擇" not in t:
            out.append((v, t))
    return out

# 全部抓完才寫檔。中途炸掉時舊的 yark_table.json 原封不動，不會被半份新的蓋掉。
rows = []
for brand, ids in BRANDS.items():
    for bid in ids:
        models = options(post("1" + bid))
        # HTTP 200 但回一頁空的（改版、擋爬、id 失效）不會丟例外，車款清單會是空的。
        # 這時整個品牌會從快照消失，而總列數還撐得過下面的門檻 —— 所以每個品牌都要各自檢查。
        if not models:
            raise ScrapeIncomplete(f"{brand} ({bid}) 回傳 0 個車款 —— 不覆蓋既有快照")
        print(f"{brand} ({bid}): {len(models)} models")
        time.sleep(0.15)
        for mid, mname in models:
            years = options(post("2" + mid))
            time.sleep(0.15)
            for yid, yname in years:
                wipers = options(post("3" + yid))
                time.sleep(0.15)
                for _, wname in wipers:
                    m = re.match(r"^\s*(\d{1,2})\s*\+\s*(\d{1,2})", wname)
                    if m:
                        rows.append({"brand": brand, "model": mname, "years": yname,
                                     "driver": int(m.group(1)), "passenger": int(m.group(2)),
                                     "raw": wname})

got = {r["brand"] for r in rows}
missing = sorted(set(BRANDS) - got)
if missing:
    raise ScrapeIncomplete(f"這些品牌一列都沒抓到：{missing} —— 不覆蓋既有快照")
if len(rows) < 500:
    raise ScrapeIncomplete(f"只抓到 {len(rows)} 列，上次是 782 列 —— 不覆蓋既有快照")
OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
print("total rows", len(rows), "->", OUT)
