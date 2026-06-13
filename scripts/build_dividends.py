"""一次性回補除權息事件 → data/dividends.json(版控種子,比照 revenue_cache.json)。

格式:{stock_id: [[ex_date(YYYYMMDD), factor], ...]},factor = 除權息參考價/前收盤(0<f<=1)。
讀取層(adjust.py)以「ex_date 之後的因子連乘」向後還原歷史價,消除除權息造成的假跌幅。

資料源:
  TWSE  TWT49U  直接有前收盤+參考價 → 2 年一次抓,零公式風險(上市完整)。
  TPEX  openapi prepost  僅未來~2 月、無參考價 → 用 DB 前收盤依官方公式重建(上櫃即日起向前覆蓋)。
        ⚠️ 上櫃歷史(prepost 視窗以前)無免費點位來源,維持未還原並於報告/回測標註。

用法:python3 scripts/build_dividends.py [--start YYYYMMDD] [--end YYYYMMDD]
每日報告會用 fetch.fetch_dividends + 既有 JSON 增量刷新,平日不需重跑此腳本。
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db       # noqa: E402
import fetch    # noqa: E402

OUT = os.path.join(ROOT, "data", "dividends.json")


def _tpex_factors(raw, prices):
    """用 DB 前收盤把 TPEX 原始股利重建成 {sid: {ex: factor}}(只算 ex 已過、DB 有前收盤者)。"""
    series = {sid: sorted(v["rows"]) for sid, v in prices.items()}  # rows: (date,close,high,vol,val)
    out = {}
    for ex, sid, cash, sr, subr, subp in raw:
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
            continue  # ex 之前無交易資料(未來事件),等該日過後的每日刷新再補
        f = fetch.reconstruct_tpex_factor(pre, cash, sr, subr, subp)
        if f is not None:
            out.setdefault(sid, {})[ex] = f
    return out


def merge(base, add):
    for sid, events in add.items():
        d = base.setdefault(sid, {})
        for ex, f in (events.items() if isinstance(events, dict) else events):
            d[ex] = f
    return base


def main():
    ap = argparse.ArgumentParser()
    today = date.today()
    ap.add_argument("--start", default=(today - timedelta(days=760)).strftime("%Y%m%d"))
    ap.add_argument("--end", default=today.strftime("%Y%m%d"))
    a = ap.parse_args()

    conn = db.connect()
    prices = db.load_prices(conn)  # 上市+上櫃

    print(f"TWSE 除權息 {a.start}~{a.end} ...", flush=True)
    twse = fetch.fetch_dividends_twse(a.start, a.end)
    print(f"  {sum(len(v) for v in twse.values())} 筆 / {len(twse)} 檔", flush=True)

    print("TPEX 除權息(prepost,以 DB 前收盤重建)...", flush=True)
    tpex = _tpex_factors(fetch.fetch_dividends_tpex_raw(), prices)
    print(f"  {sum(len(v) for v in tpex.values())} 筆 / {len(tpex)} 檔", flush=True)

    merged = {}
    merge(merged, twse)   # {sid: [(ex,factor),...]}
    merge(merged, tpex)   # {sid: {ex: factor}}
    # 排序輸出
    out = {sid: sorted(([ex, f] for ex, f in ev.items()), key=lambda x: x[0])
           for sid, ev in merged.items()}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"寫入 {OUT}:{len(out)} 檔、{sum(len(v) for v in out.values())} 事件", flush=True)


if __name__ == "__main__":
    main()
