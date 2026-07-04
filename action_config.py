"""每日行動清單(⓪ 區)的所有參數與績效數字,集中一檔。

數字來源:scratchpad/STRATEGY_SEARCH.md 策略族系統性搜尋定案(2026-07-04)+
scratchpad/LEGACY_COMPARE.md 回測裁決;同框架 PIT、train/test 切點 20250828、
test 段 2025-08-28 ~ 2026-05-22、成本 0.585% 扣在絕對報酬。
- 嚴選 = F2「突破前60日高(不含當日)+ 投信連買>=2」:train/test 皆正的唯一預註冊規則。
- 平衡 = 舊補漲引擎(scripts/legacy_analyze.py)score>=60:test 正但 train 負,
  屬盤勢依賴,必附警語並靠滾動命中率監控。
之後策略再定案,只改這一檔,報告與 Discord 文案自動跟著換。
win/excess/p10 單位皆為 %;win_abs=絕對報酬(扣成本)>0 比例,excess=相對 TAIEX。
"""

CONFIG = {
    "floor": 60,          # 平衡級門檻(legacy score;test 段唯一 n 夠大且正超額的門檻)
    "strong_rule": {      # 嚴選級訊號(F2):非分數制,三條件同時成立
        "breakout_window": 60,   # 還原收盤突破「前 60 日收盤最高」(不含當日)
        "trust_streak_min": 2,   # 投信連買 >= 2 日
        "max_rows": 10,          # 報告顯示上限(依投信連買/買超排序後截斷)
    },
    "hold_days": 20,      # 建議持有(方案A:抱滿,不設停損)
    "sort": "trust_net5",  # 平衡清單排序鍵:投信5日買超>0 優先(回測:當排序鍵、不當硬排除)
    "regime": "bull",     # 只在大盤多頭出清單
    "stats": {
        # 嚴選(F2 h20 test):絕對勝率(扣成本)/平均絕對報酬/平均超額/絕對報酬p10
        "strong": {"win_abs": 53.1, "ret_net": 6.72, "excess": 0.69, "p10": -15.9, "n": 885},
        # 嚴選方案B(F3:+5% 停利 / −10% 停損 / 20 日時間停損,test)
        "strong_planB": {"win_abs": 59.7, "ret_net": 0.82, "excess": -1.07},
        # 平衡(legacy >=60、bull、h20、test;win=贏大盤比例)
        "floor":  {"win": 51.2, "excess": 4.82, "p10": -17.54, "n": 404},
        # 出場政策對照(legacy cohort >=70 & bull、h20、test):PA2 = 5/10MA 停損、P0 = 抱滿
        "exit_ma_stop":   {"win": 11.8, "excess": -9.03},
        "exit_hold_full": {"win": 56.9, "excess": 9.21},
        # 現行買強引擎 >=75、bull、h20、test 段 — 美股行動區塊的誠實註記用
        "us_current": {"win": 33.8, "excess": -2.76, "p10": -24.15, "n": 2796},
    },
    # 漲停雷達(F6b):訊號出現者隔日漲停率相對全市場基準(2.1%)的倍數
    "limit_radar": {"baseline": 2.1, "lock": 6.9, "breakout": 5.2, "vol_surge": 4.6},
    "test_range": "2025-08-28 ~ 2026-05-22",
}
