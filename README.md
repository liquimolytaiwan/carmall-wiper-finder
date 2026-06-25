# CarMall 雨刷快速查詢系統

嵌入式雨刷尺寸查詢器：車廠 → 車款 → 年份 → 正確尺寸 + 一鍵導購到 Cyberbiz（carmall.com.tw）。

純靜態（HTML/CSS/JS + 一份 `data.json`），放 GitHub Pages，用 `<iframe>` 內嵌進 Cyberbiz 部落格文章。

## 結構
```
index.html      查詢器頁面（iframe 內嵌用）
styles.css      樣式（CarMall 深藍風）
app.js          下拉串接 + 結果卡 + 導購邏輯 + iframe 自動高度
data.json       產出的資料（勿手改；由 tools 重建）
tools/
  pages/p26..p31.json   BOSCH 型錄第26–31頁（通用美日韓）逐頁判讀結果（兩次獨立判讀交叉校對）
  corrections.json      型錄錯誤/市場校正（型錄 vs 組合 vs 市場不一致時的正解）
  wiper_products.json    Cyberbiz 雨刷商品快照（價格/庫存/組合，自動更新）
  fetch_products.py      重抓 Cyberbiz 商品（sitemap + /products/*.json）
  build_data.py          合併 → 產生 ../data.json
.github/workflows/refresh-data.yml   排程自動更新價格/庫存
```

## 導購邏輯
1. 車種有「專屬組合（2支/組）」→ 直接導該商品頁
2. 否則 → 導「多尺寸任選」單支頁（自動帶入駕駛座尺寸），並標明需購買的兩個尺寸
3. 尺寸無現貨且無組合 → 顯示「請洽客服」（不亂替代）
4. 車型前擋需專用型 → 顯示提示（專用型為日後擴充）

## 資料來源與校正
- 尺寸來自 BOSCH 2026 通用雨刷型錄（圖片版，視覺判讀，兩次獨立交叉校對）。
- 型錄本身偶有錯誤；當型錄與「Cyberbiz 組合商品 / 市場多來源」不一致時，以查證後的正解寫入 `corrections.json`。
- 價格/庫存由 GitHub Actions 排程重抓 Cyberbiz，近即時；實際成交以 Cyberbiz 商品頁為準。

## 更新資料
```
cd tools && python fetch_products.py && python build_data.py
```

## 嵌入方式（Cyberbiz 部落格 HTML）
見 `embed-snippet.html`（含 iframe 自動高度）。
