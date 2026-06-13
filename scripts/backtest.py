"""進場分數回測:用 DB 既有歷史(不必等 summary.json 累積)直接驗證。

做法(point-in-time,無未來資訊外洩於價量/法人面):
  對歷史每個交易日 D,把資料截到「D 當天以前」重算當天的補漲候選清單
  (重用 main._truncate + main._analyze,與正式報告完全同一套邏輯),
  再用 DB 裡 D 之後的收盤價,算每檔候選 N 個交易日後「相對大盤的超額報酬」。

核心指標:
  命中率 = 超額報酬 > 0 的比例(即「之後比大盤強」的機率)
  平均/中位超額報酬;並按進場分數分桶,看「分數越高是否越強」(模型是否有效)。

⚠️ 已知限制(會影響解讀,不影響價量/法人/均線維度):
  1. 月營收用的是 data/revenue_cache.json 的「當前快照」,非當日點位資料
     → 營收維度(10/100 分)對較近期的日期有輕微未來資訊;產業分類則為靜態,無妨。
  2. 處置/注意股清單無歷史,回測一律以空集合代入(正式報告會排除處置股)。
  3. 早期日期歷史不足 60 天時,60 日高/均線視窗較短,故跳過暖身期。

用法:
  python3 scripts/backtest.py                 # 預設 horizons 5/10/20、暖身 40 日
  python3 scripts/backtest.py --json out.json # 另存機器可讀結果
"""
import argparse
import json
import os
import sys
from statistics import mean, median

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db          # noqa: E402
import main        # noqa: E402

HORIZONS = (5, 10, 20)   # 持有 N 個交易日後評估
WARMUP = 40              # 前 N 個交易日當暖身期(歷史太短指標不可靠),不評估
SCORE_BUCKETS = [(0, 50), (50, 60), (60, 70), (70, 101)]


def _close_lookup(prices):
    """{stock_id: {date: close}},供前瞻報酬查價。"""
    out = {}
    for sid, v in prices.items():
        out[sid] = {r[0]: r[1] for r in v["rows"]}
    return out


def run(horizons=HORIZONS, warmup=WARMUP):
    conn = db.connect()
    prices = db.load_prices(conn)            # 台股上市+上櫃
    inst = db.load_inst(conn)
    taiex = db.load_taiex(conn)
    with open(os.path.join(ROOT, "data", "revenue_cache.json"), encoding="utf-8") as f:
        revenue = json.load(f)

    cal = [d for d, _ in taiex]              # 主交易日曆(升冪)
    taiex_close = {d: c for d, c in taiex}
    px = _close_lookup(prices)

    max_h = max(horizons)
    # 評估日:暖身之後、且後面至少還有 max_h 個交易日可算前瞻報酬
    eval_idx = range(warmup, len(cal) - max_h)
    if not eval_idx:
        print(f"資料不足:交易日僅 {len(cal)} 天,需 > 暖身 {warmup} + 最長持有 {max_h}。")
        return None

    # obs[h] = [超額報酬...];obs_scored[h] = [(score, 超額報酬)...]
    obs = {h: [] for h in horizons}
    obs_scored = {h: [] for h in horizons}
    # 逐維度歸因(以最長 horizon 評估):dim_obs[key] = [(該維度得分比例, 超額報酬)...]
    attr_h = max(horizons)
    dim_obs = {}
    n_cands_total = 0
    eval_days = []

    for i in eval_idx:
        D = cal[i]
        p, ins, tx = main._truncate(prices, inst, taiex, D)
        _, _, _, laggards, _ = main._analyze(p, ins, tx, revenue, profile="tw")
        if not laggards:
            continue
        eval_days.append(D)
        for c in laggards:
            sid = c["stock_id"]
            base = px.get(sid, {}).get(D)
            if base is None or base == 0:
                continue          # 該股當日未成交,跳過
            n_cands_total += 1
            attr_excess = None
            for h in horizons:
                fwd = cal[i + h]
                sp = px.get(sid, {}).get(fwd)
                if sp is None or taiex_close.get(D) in (None, 0) or taiex_close.get(fwd) is None:
                    continue
                stock_ret = sp / base - 1
                mkt_ret = taiex_close[fwd] / taiex_close[D] - 1
                excess = stock_ret - mkt_ret
                obs[h].append(excess)
                obs_scored[h].append((c["score"], excess))
                if h == attr_h:
                    attr_excess = excess
            # 歸因:把每個評分維度的得分比例與該股 attr_h 後超額報酬配對
            if attr_excess is not None:
                for key, pts, full in c.get("parts", []):
                    dim_obs.setdefault(key, []).append((pts / full if full else 0, attr_excess))

    result = {
        "range": [cal[warmup], cal[len(cal) - max_h - 1]] if eval_days else None,
        "eval_days": len(eval_days),
        "candidate_observations": n_cands_total,
        "horizons": {},
    }
    for h in horizons:
        ex = obs[h]
        if not ex:
            continue
        hit = sum(1 for e in ex if e > 0) / len(ex)
        buckets = []
        for lo, hi in SCORE_BUCKETS:
            b = [e for s, e in obs_scored[h] if lo <= s < hi]
            if b:
                buckets.append({
                    "range": f"{lo}-{hi - 1}", "lo": lo, "hi": hi, "n": len(b),
                    "hit_rate": sum(1 for e in b if e > 0) / len(b),
                    "mean_excess": mean(b),
                })
        result["horizons"][h] = {
            "n": len(ex),
            "hit_rate": hit,
            "mean_excess": mean(ex),
            "median_excess": median(ex),
            "buckets": buckets,
        }

    # 逐維度預測力(以最長 horizon):比較「該維度高分(得分≥6成)」vs「低分」的平均超額。
    # 差距(spread)為正且明顯 → 該維度有預測力,值得保留/加重;接近 0 或為負 → 可疑。
    attr = []
    for key, pairs in dim_obs.items():
        hi = [e for frac, e in pairs if frac >= 0.6]
        lo = [e for frac, e in pairs if frac < 0.6]
        if hi and lo:
            attr.append({
                "dim": key, "n_hi": len(hi), "n_lo": len(lo),
                "mean_hi": mean(hi), "mean_lo": mean(lo),
                "spread": mean(hi) - mean(lo),
            })
    attr.sort(key=lambda x: x["spread"], reverse=True)
    result["attribution"] = {"horizon": attr_h, "dims": attr}
    return result


def report(r):
    if not r:
        return
    print("=" * 60)
    print("進場分數回測(台股,相對大盤超額報酬)")
    print("=" * 60)
    print(f"評估期間:{r['range'][0]} ~ {r['range'][1]}")
    print(f"評估交易日數:{r['eval_days']} 天")
    print(f"候選觀測樣本:{r['candidate_observations']} 筆(候選股×評估日)")
    print()
    print("白話:命中率 = 「進場後比大盤強」的比例;超額報酬 = 該股漲幅減大盤漲幅。")
    print("      若分數越高、命中率與超額報酬越高,代表進場分數真的有鑑別力。\n")
    for h, d in r["horizons"].items():
        print(f"── 持有 {h} 個交易日 ──  樣本 {d['n']} 筆")
        print(f"   命中率(贏大盤):{d['hit_rate']*100:5.1f}%")
        print(f"   平均超額報酬  :{d['mean_excess']*100:+5.2f}%   中位 {d['median_excess']*100:+5.2f}%")
        if d["buckets"]:
            print("   依進場分數分桶:")
            for b in d["buckets"]:
                print(f"     {b['range']:>6} 分 | n={b['n']:>4} | 命中 {b['hit_rate']*100:5.1f}%"
                      f" | 平均超額 {b['mean_excess']*100:+5.2f}%")
        print()
    attr = r.get("attribution")
    if attr and attr["dims"]:
        names = {"industry": "產業熱度", "inst": "法人動向", "revenue": "營收動能",
                 "ma3": "站上三線", "vol": "交易量"}
        print(f"── 逐維度預測力(持有 {attr['horizon']} 日)──")
        print("   每個評分維度:該維度『高分股』vs『低分股』之後的平均超額報酬差距。")
        print("   差距越大越正 = 這個維度越能預測強弱;接近 0 或為負 = 該維度可疑。\n")
        for d in attr["dims"]:
            print(f"   {names.get(d['dim'], d['dim']):>5} | 高分平均 {d['mean_hi']*100:+6.2f}%"
                  f" | 低分平均 {d['mean_lo']*100:+6.2f}% | 差距 {d['spread']*100:+6.2f}%"
                  f"  (n高={d['n_hi']}, n低={d['n_lo']})")
        print()
    print("⚠️ 限制:月營收用當前快照(近期日期營收維度有輕微未來資訊)、處置股清單無歷史(以空集合代入)。")


def main_cli():
    ap = argparse.ArgumentParser(description="進場分數回測")
    ap.add_argument("--horizons", default="5,10,20", help="持有天數,逗號分隔")
    ap.add_argument("--warmup", type=int, default=WARMUP, help="暖身交易日數")
    ap.add_argument("--json", help="另存 JSON 結果路徑")
    a = ap.parse_args()
    hs = tuple(int(x) for x in a.horizons.split(","))
    r = run(horizons=hs, warmup=a.warmup)
    report(r)
    if a.json and r:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"\n已寫入 {a.json}")


if __name__ == "__main__":
    main_cli()
