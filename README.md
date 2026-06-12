# 台股 / 美股趨勢日報 · TW & US Stock Trend Daily

每個交易日收盤後自動產生的趨勢報告:**資金流向哪些產業、誰在帶頭漲、同產業還有誰沒漲**。
給沒有技術分析背景的人看——指標只用籌碼、營收、價格位階、量能,並附白話解釋。中英雙語。

📰 **台股報告**:https://orangeeewei.github.io/tw-stock-trend/([English](https://orangeeewei.github.io/tw-stock-trend/en.html))
🗽 **美股報告(S&P 500)**:https://orangeeewei.github.io/tw-stock-trend/us/([中文](https://orangeeewei.github.io/tw-stock-trend/us/zh.html))

美股版差異:美國沒有台股的每日法人買賣超與月營收公開資料,評分改用價量結構
(產業熱度 30 / 位階 20 / 量能 25 / 動能轉折 25);價格由 Yahoo Finance 提供、自帶股息還原。

## 報告內容

1. **大盤紅綠燈** — 加權指數是否站上 60 日線,決定補漲策略該不該執行
2. **產業熱度排行** — 各產業近 20 日表現(成分股中位數),看資金往哪去
3. **強勢產業領頭羊** — 創 60 日新高的風向標
4. **補漲候選** — 熱門產業 + 落後同業 + 低基期 + 甦醒跡象,附 0~100 進場分數:
   產業熱度 25 + 法人動向 30 + 營收動能 20 + 位階量能 25

## 資料來源(全部免費公開)

- 臺灣證券交易所:每日收盤行情(MI_INDEX)、三大法人買賣超(T86)、上市月營收
- 證券櫃檯買賣中心:上櫃行情、上櫃三大法人、上櫃月營收

涵蓋上市 + 上櫃 4 碼個股(排除 ETF),報告中上櫃標「櫃」。

## 自動化

GitHub Actions 每個交易日跑兩次:台北 17:00(台股)與美東收盤後(美股,台北清晨 5:30)。
流程:更新資料 → 產生雙語報告 → 發佈到 GitHub Pages → 推播摘要到 Discord
(台股中文、美股英文;設定 `DISCORD_WEBHOOK_URL` secret 即啟用)。
歷史資料庫存於 Actions cache,遺失時自動還原 Release 種子。

## 本機使用

```bash
python3 main.py backfill --days 130   # 台股:回補歷史資料
python3 main.py daily                 # 台股:更新 + 產生報告
python3 main.py us-daily              # 美股:更新 + 產生報告
```

純 Python 標準庫,零外部依賴。報告輸出到 `reports/` 與 `docs/`。

## 免責聲明

本專案由公開資料自動產生,僅供研究參考,不構成任何投資建議。
