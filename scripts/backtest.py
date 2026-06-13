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

import analyze     # noqa: E402
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


def run(horizons=HORIZONS, warmup=WARMUP, regime=None):
    """regime=None 計全部交易日;regime='bull' 只計大盤站上 60 日線的日子
    (=策略實際會出手的情境;回測顯示空頭時優勢消失,故報告以多頭為準)。"""
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
        state, _, _, laggards, _ = main._analyze(p, ins, tx, revenue, profile="tw")
        if regime == "bull" and not state.get("bull"):
            continue            # 只計大盤多頭日(空頭策略失效,不納入報告數字)
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
        "regime": regime,
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


# 目前的進場分數權重(= entry_score 各 part 的滿分),依維度 key 對應。
# 2026-06-13 已依本優化器走查式驗證由 (25,30,10,15,20) 微調為下值(法人+5、站上三線-5)。
# 注意:_collect_obs 取的 fracs = pts/滿分,滿分即現行權重,故 CURRENT_W 必須與 entry_score 一致。
CURRENT_W = {"industry": 25, "inst": 35, "revenue": 10, "ma3": 10, "vol": 20}

# 候選權重方案(經濟意義導向、小集合,避免在 5 維自由搜尋上過度配適)。
# 全年歸因:法人最乾淨可信、交易量最弱、營收受 look-ahead 汙染存疑、站上三線全年微正。
WEIGHT_SCHEMES = {
    "current":         {"industry": 25, "inst": 35, "revenue": 10, "ma3": 10, "vol": 20},
    "inst+_vol-":      {"industry": 25, "inst": 40, "revenue": 10, "ma3": 10, "vol": 15},
    "inst++":          {"industry": 25, "inst": 45, "revenue": 10, "ma3": 10, "vol": 10},
    "ind+_vol-":       {"industry": 30, "inst": 35, "revenue": 10, "ma3": 10, "vol": 15},
    "ma+back":         {"industry": 25, "inst": 30, "revenue": 10, "ma3": 15, "vol": 20},
    "rev+":            {"industry": 25, "inst": 35, "revenue": 15, "ma3": 10, "vol": 15},
    "drop_vol":        {"industry": 30, "inst": 40, "revenue": 15, "ma3": 15, "vol": 0},
}


def _score(fracs, w):
    return sum(fracs.get(k, 0) * w.get(k, 0) for k in w)


def _spearman(pairs):
    """pairs=[(x,y)] 的等級相關係數(資訊係數 IC)。"""
    n = len(pairs)
    if n < 3:
        return 0.0
    def ranks(vals):
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0] * n
        for rank, i in enumerate(order):
            r[i] = rank
        return r
    rx = ranks([p[0] for p in pairs])
    ry = ranks([p[1] for p in pairs])
    mx, my = mean(rx), mean(ry)
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def _collect_obs(horizon=20, warmup=WARMUP):
    """收集每筆合格候選(截斷前全貌)的 {day, industry, fracs, excess}。供離線重配權重評估。"""
    conn = db.connect()
    prices = db.load_prices(conn)
    inst = db.load_inst(conn)
    taiex = db.load_taiex(conn)
    with open(os.path.join(ROOT, "data", "revenue_cache.json"), encoding="utf-8") as f:
        revenue = json.load(f)
    cal = [d for d, _ in taiex]
    taiex_close = {d: c for d, c in taiex}
    px = _close_lookup(prices)

    obs = []
    for i in range(warmup, len(cal) - horizon):
        D = cal[i]
        p, ins, tx = main._truncate(prices, inst, taiex, D)
        metrics = analyze.build_metrics(p, ins, revenue)
        industries = analyze.build_industries(metrics, p)
        quals = analyze.qualifying_laggards(industries, profile="tw")
        if not quals:
            continue
        fwd = cal[i + horizon]
        if taiex_close.get(D) in (None, 0) or taiex_close.get(fwd) is None:
            continue
        mkt_ret = taiex_close[fwd] / taiex_close[D] - 1
        for c in quals:
            sid = c["stock_id"]
            base = px.get(sid, {}).get(D)
            sp = px.get(sid, {}).get(fwd)
            if not base or sp is None:
                continue
            fracs = {k: (pts / full if full else 0) for k, pts, full in c["parts"]}
            obs.append({"day": i, "industry": c["industry"],
                        "fracs": fracs, "excess": (sp / base - 1) - mkt_ret})
    return obs


def _eval_scheme(obs, w, limit=20, cap=5):
    """以權重 w 在每個交易日重排合格池、套產業上限取前 limit,回傳(選中股平均超額, IC)。"""
    by_day = {}
    for o in obs:
        by_day.setdefault(o["day"], []).append(o)
    selected = []
    for day, lst in by_day.items():
        lst = sorted(lst, key=lambda o: _score(o["fracs"], w), reverse=True)
        per_ind, picked = {}, []
        for o in lst:
            if per_ind.get(o["industry"], 0) >= cap:
                continue
            per_ind[o["industry"]] = per_ind.get(o["industry"], 0) + 1
            picked.append(o)
            if len(picked) == limit:
                break
        selected.extend(picked)
    ic = _spearman([(_score(o["fracs"], w), o["excess"]) for o in obs])
    sel_excess = mean([o["excess"] for o in selected]) if selected else 0.0
    return sel_excess, ic


def optimize(horizon=20, warmup=WARMUP, train_frac=0.6):
    """走查式權重優化:訓練段挑最佳方案,測試段驗證是否真的更好(防過度配適)。"""
    obs = _collect_obs(horizon, warmup)
    if not obs:
        print("資料不足,無法優化。")
        return None
    days = sorted({o["day"] for o in obs})
    split = days[int(len(days) * train_frac)]
    train = [o for o in obs if o["day"] < split]
    test = [o for o in obs if o["day"] >= split]

    print("=" * 64)
    print(f"走查式權重優化(持有 {horizon} 日,選中股=每日重排取前20/產業上限5)")
    print(f"訓練段 {len([d for d in days if d < split])} 日 / 測試段 {len([d for d in days if d >= split])} 日")
    print("=" * 64)
    print(f"{'方案':<14}{'訓練選股超額':>12}{'訓練IC':>9}{'測試選股超額':>12}{'測試IC':>9}")
    rows = {}
    for name, w in WEIGHT_SCHEMES.items():
        tr_e, tr_ic = _eval_scheme(train, w)
        te_e, te_ic = _eval_scheme(test, w)
        rows[name] = {"w": w, "tr_e": tr_e, "tr_ic": tr_ic, "te_e": te_e, "te_ic": te_ic}
        print(f"{name:<14}{tr_e*100:>11.2f}%{tr_ic:>9.3f}{te_e*100:>11.2f}%{te_ic:>9.3f}")

    cur = rows["current"]
    best_train = max((n for n in rows if n != "current"), key=lambda n: rows[n]["tr_e"])
    bt = rows[best_train]
    print()
    print(f"訓練段最佳(非 current):{best_train}  權重={bt['w']}")
    improve_test = bt["te_e"] - cur["te_e"]
    print(f"該方案測試段選股超額 {bt['te_e']*100:+.2f}% vs current {cur['te_e']*100:+.2f}%"
          f"  → 樣本外差距 {improve_test*100:+.2f}%(IC {bt['te_ic']:+.3f} vs {cur['te_ic']:+.3f})")
    adopt = improve_test > 0.003 and bt["te_ic"] >= cur["te_ic"] - 0.005
    print()
    if adopt:
        print(f"✅ 通過樣本外驗證(測試段更好且 IC 不退步)→ 建議採用 {best_train}:{bt['w']}")
    else:
        print("❌ 未通過樣本外驗證(測試段沒有明顯更好或 IC 退步)→ 維持 current 權重。")
        print("   依資料,目前權重已接近最佳;憑單維度差距硬調反而會過度配適。")
    return {"rows": rows, "best_train": best_train, "adopt": adopt,
            "recommended": bt["w"] if adopt else CURRENT_W}


def main_cli():
    ap = argparse.ArgumentParser(description="進場分數回測")
    ap.add_argument("--horizons", default="5,10,20", help="持有天數,逗號分隔")
    ap.add_argument("--warmup", type=int, default=WARMUP, help="暖身交易日數")
    ap.add_argument("--json", help="另存 JSON 結果路徑")
    ap.add_argument("--optimize", action="store_true", help="走查式權重優化(訓練/測試驗證)")
    a = ap.parse_args()
    if a.optimize:
        optimize(warmup=a.warmup)
        return
    hs = tuple(int(x) for x in a.horizons.split(","))
    r = run(horizons=hs, warmup=a.warmup)
    report(r)
    if a.json and r:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"\n已寫入 {a.json}")


if __name__ == "__main__":
    main_cli()
