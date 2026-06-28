"""除權息向後還原層:原始收盤價永遠不動,於讀取後依除權息因子在記憶體中還原。

為何在讀取層而非改 DB:原始價是審計來源,還原是「視圖」;且回測需要 point-in-time
還原(在歷史日 D 只能用 ex_date<=D 的事件),同一份原始資料要能套不同 asof,改 DB 做不到。

還原數學:股票於 ex_date e 當天起的價格已是除權息後(較低);e 之前的價格要乘上
因子 f=參考價/前收盤(<1)壓低,使整條序列在同一基準可比。某列日期 d 的還原乘數 =
所有「ex_date 嚴格大於 d 且 ex_date<=asof」事件因子的連乘。

三種 asof 用法(關鍵,避免 look-ahead):
  - 正式報告:asof=最新交易日 → 最新價=實際市場價,歷史被等比壓低(業界標準)。
    ⚠️ 不可用 asof=None:dividends.json 含 TPEX prepost 的『未來』除息事件,
       asof=None 會把尚未發生的除息提前套到現價,反製造假低基期候選。
  - 回測評分:asof=該歷史日 D → 只用當時已發生的除權息,模擬投資人當下看到的線型。
  - 回測前瞻報酬:用 asof=None 的全還原序列(總報酬基準),base 與 fwd 同基準、除權息算進
    持有期報酬。此處 asof=None 安全:衡量的是『已實現』報酬,未來事件本就是真實發生的總報酬。
"""
import json
import os


def load_dividends(path):
    """{stock_id: [(ex_date, factor), ...]}(ex_date 升冪);檔案不存在回空 dict。"""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {sid: sorted((str(ex), float(fa)) for ex, fa in evs) for sid, evs in raw.items()}


def adjust_prices(prices, dividends, asof=None):
    """回傳還原後的 prices 視圖(close/high 乘還原乘數;volume/value 不動——除權息不改股數語意)。
    asof=None 用全部事件;否則只用 ex_date<=asof 的事件(point-in-time)。"""
    if not dividends:
        return prices
    out = {}
    for sid, v in prices.items():
        evs = dividends.get(sid)
        rows = v["rows"]
        if not evs:
            out[sid] = v
            continue
        evs = [(e, f) for e, f in evs if asof is None or e <= asof]
        if not evs:
            out[sid] = v
            continue
        total = 1.0
        for _, f in evs:
            total *= f
        new_rows = []
        ei, passed = 0, 1.0
        for r in rows:                      # rows 升冪:(date, close, high, vol, val, low)
            d = r[0]
            while ei < len(evs) and evs[ei][0] <= d:
                passed *= evs[ei][1]
                ei += 1
            mult = total / passed           # = 連乘(ex_date > d 的因子)
            new_rows.append((d, r[1] * mult, r[2] * mult, r[3], r[4], r[5] * mult))
        out[sid] = {**v, "rows": new_rows}
    return out


def refresh_dividends(prices, path):
    """每日增量刷新 data/dividends.json:TWSE 近 90 日 + TPEX prepost(用 prices 前收盤重建),
    與既有種子合併後寫回並回傳。任一來源失敗只略過該來源,不讓報告開天窗。"""
    import datetime
    import fetch
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = {sid: {str(ex): float(fa) for ex, fa in evs}
                        for sid, evs in json.load(f).items()}

    today = datetime.date.today()
    start = (today - datetime.timedelta(days=90)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    try:
        for sid, evs in fetch.fetch_dividends_twse(start, end).items():
            existing.setdefault(sid, {}).update({ex: f for ex, f in evs})
    except Exception as e:
        print(f"TWSE 除權息刷新失敗,沿用既有:{e}", flush=True)
    try:
        series = {sid: sorted(v["rows"]) for sid, v in prices.items()}
        for ex, sid, cash, sr, subr, subp in fetch.fetch_dividends_tpex_raw():
            rows = series.get(sid)
            if not rows:
                continue
            pre = None
            for d, c, *_ in rows:
                if d < ex:
                    pre = c
                else:
                    break
            if pre is None:
                continue
            f = fetch.reconstruct_tpex_factor(pre, cash, sr, subr, subp)
            if f is not None:
                existing.setdefault(sid, {})[ex] = f
    except Exception as e:
        print(f"TPEX 除權息刷新失敗,沿用既有:{e}", flush=True)

    out = {sid: sorted(([ex, f] for ex, f in ev.items()), key=lambda x: x[0])
           for sid, ev in existing.items() if ev}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return {sid: [(ex, f) for ex, f in ev] for sid, ev in out.items()}
