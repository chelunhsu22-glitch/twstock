# 台股三維選股 App

涵蓋**上市＋上櫃全部股票（約 1,900 檔）**，每個交易日晚上自動更新，用手機瀏覽器打開即可使用，也能「加入主畫面」當成 App。

- 資料來源：證交所、櫃買中心公開資料（免費、不需帳號）
- 自動更新：GitHub Actions，台北時間週一至週五 21:40
- 網站：GitHub Pages（免費）

> 分數、價位、漲跌機率皆為公開規則計算的量化參考，不是投資建議。

## 結構

```
scripts/fetch.py     抓每日價量、三大法人、融資、本益比、月營收
scripts/build.py     計算 MA、RSI、KD、MACD、波動率、法人連買天數等
docs/index.html      網頁（評分、價位、部位、機率、資產試算都在這裡即時計算）
docs/data/latest.json  每日產出的資料
data/history/        每日原始資料（自動保留最近 200 個交易日）
.github/workflows/daily.yml  每日排程
```

## 安裝步驟（約 15 分鐘，建議用電腦操作）

1. **建立儲存庫**：登入 GitHub → 右上角「+」→ New repository → 名稱例如 `twstock` → 選 **Public**（免費方案的 Pages 需公開）→ Create。
2. **上傳檔案**：在新儲存庫頁面點「uploading an existing file」，把解壓縮後資料夾裡的**所有內容**（含 `.github` 資料夾）拖進去 → Commit。
   - 若 `.github` 資料夾沒有上傳成功（部分瀏覽器會略過隱藏資料夾），改用 Add file → Create new file，檔名輸入 `.github/workflows/daily.yml`，貼上該檔內容。
3. **開啟寫入權限**：Settings → Actions → General → Workflow permissions → 選「Read and write permissions」→ Save。
4. **第一次回補歷史資料**：Actions 分頁 → 左側「每日更新台股資料」→ Run workflow → 回補天數填 `120` → Run。
   - 約需 30–60 分鐘（交易所限制每 5 秒 3 次請求）。
5. **開啟網站**：Settings → Pages → Source 選「Deploy from a branch」→ Branch 選 `main`、資料夾選 `/docs` → Save。
   幾分鐘後網址為 `https://你的帳號.github.io/twstock/`。
6. **手機加到主畫面**：用 Safari / Chrome 打開網址 → 分享 → 加入主畫面。

之後每天會自動更新，不用再做任何事。

## 常見問題

- **Actions 執行失敗**：點進失敗的那次，展開紅色步驟，把錯誤訊息複製下來貼給 Claude 修正。
- **某些欄位顯示「—」**：該資料當天未公布或該股無此資料（例如虧損公司沒有本益比）。
- **證交所擋 GitHub 的連線**：極少數情況會發生，重新執行一次通常就好；若持續發生，回報給 Claude 改用其他資料源。
- **想調整評分規則**：在 `docs/index.html` 的 `scores()` 函式。
