"""舊版『補漲』引擎回測 — 與現行 buy-strong 實驗(backtest.experiment)完全相同的框架/切點/口徑,
只把候選來源從 main._analyze(現行 find_laggards)換成 legacy_analyze.find_laggards(舊補漲)。

同口徑保證:
  • 評分用 asof=D 還原價 + rev_build(D)(PIT 營收);前瞻報酬用 asof=None 全還原總報酬序列。
  • 產業排名/前8強/percentile 每個 D 用現行 build_industries 重算(PIT)。
  • _sim_policy / _series / _pit_revenue_builder 直接重用 backtest 模組(同一份程式)。
  • train/test 切點硬定 20250828(與現行實驗一致;不可用比例切,否則舊引擎不同 eval-days 會切歪)。

用法:
  python3 scripts/legacy_backtest.py --collect [--warmup 40]   # 跑 PIT pass → legacy_raw.json
  python3 scripts/legacy_backtest.py --analyze                 # 讀 legacy_raw.json → LEGACY_COMPARE.md
"""
import argparse
import json
import os
import sys
from statistics import mean, median

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adjust        # noqa: E402
import analyze       # noqa: E402
import db            # noqa: E402
import main          # noqa: E402
import backtest      # noqa: E402  (重用 _pit_revenue_builder/_series/_sim_policy/EXP_*)
import legacy_analyze  # noqa: E402

SP = "/tmp/claude-1000/-home-orangayge/21b1da87-952e-41ab-a122-c9523e4e3c4c/scratchpad"
RAW = os.path.join(SP, "legacy_raw.json")
SPLIT = "20250828"          # 硬定切點,與現行 buy-strong 實驗一致


def _analyze_legacy(prices, inst, index_rows, revenue):
    """與 main._analyze 相同流程,唯 laggards 用舊補漲引擎。build_metrics/industries/state 沿用現行
    (對舊引擎需要的欄位逐行等價,PIT-safe)。"""
    metrics = analyze.build_metrics(prices, inst, revenue)
    industries = analyze.build_industries(metrics, prices)
    state = analyze.market_state(index_rows)
    laggards = legacy_analyze.find_laggards(industries, profile="tw")
    return state, laggards


def collect(warmup=backtest.WARMUP):
    conn = db.connect()
    prices = db.load_prices(conn)
    inst = db.load_inst(conn)
    taiex = db.load_taiex(conn)
    rev_build, _ = backtest._pit_revenue_builder()
    dividends = adjust.load_dividends(main.DIVIDENDS_PATH)
    cal = [d for d, _ in taiex]
    taiex_close = {d: c for d, c in taiex}
    prices_adj = adjust.adjust_prices(prices, dividends, asof=None)   # 全還原總報酬(前瞻)
    pc, pl, ph, pv = backtest._series(prices_adj)

    max_h = max(backtest.EXP_HORIZONS)
    recs = []
    eval_days = 0
    for i in range(warmup, len(cal) - max_h):
        D = cal[i]
        if taiex_close.get(D) in (None, 0):
            continue
        p, ins, tx = main._truncate(prices, inst, taiex, D)
        p = adjust.adjust_prices(p, dividends, asof=D)               # 評分 asof=D 還原(PIT)
        state, laggards = _analyze_legacy(p, ins, tx, rev_build(D))
        if not laggards:
            continue
        is_bull = bool(state.get("bull"))
        eval_days += 1
        for c in laggards:
            sid = c["stock_id"]
            base = pc.get(sid, {}).get(D)
            if not base:
                continue
            closes10 = [pc[sid].get(cal[k]) for k in range(max(0, i - 9), i + 1)]
            closes10 = [x for x in closes10 if x is not None]
            stop_ref = min(closes10) if closes10 else None
            highs60 = [ph[sid].get(cal[k]) for k in range(max(0, i - 60), i)]
            highs60 = [x for x in highs60 if x is not None]
            neckline = max(highs60) if highs60 else None
            rec = {"D": D, "i": i, "sid": sid, "score": c["score"], "bull": is_bull,
                   "trust_net5": c.get("trust_net5"), "excess": {}, "pol": {}}
            for h in backtest.EXP_HORIZONS:
                fwd = cal[i + h]
                sp = pc.get(sid, {}).get(fwd)
                if sp is None or taiex_close.get(fwd) is None:
                    continue
                mret = taiex_close[fwd] / taiex_close[D] - 1
                rec["excess"][h] = (sp / base - 1) - mret
                if h in (10, 20):
                    rec["pol"][h] = {}
                    for pol in backtest.EXP_POLICIES:
                        s = backtest._sim_policy(pol, sid, base, i, h, cal, pc, pl, ph, pv,
                                                 stop_ref, neckline)
                        if s is not None:
                            ret, early, hold, half = s
                            rec["pol"][h][pol] = {"ex": ret - mret, "early": early,
                                                  "hold": hold, "half": half}
            if rec["excess"]:
                recs.append(rec)
    out = {"warmup": warmup, "eval_days": eval_days, "n_obs": len(recs),
           "range": [cal[warmup], cal[len(cal) - max_h - 1]], "split": SPLIT, "recs": recs}
    with open(RAW, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"寫入 {RAW}:{len(recs)} 筆觀測、{eval_days} 評估日、範圍 {out['range']}、切點 {SPLIT}")
    return out


# ── 分析(mirror analyze_exp.py 的 stat/pctile/fmt;切點硬定 20250828)──
def _pctile(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * q
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def _stat(xs):
    if not xs:
        return None
    return {"n": len(xs), "hit": sum(1 for e in xs if e > 0) / len(xs),
            "mean": mean(xs), "med": median(xs), "p10": _pctile(xs, 0.10)}


def _row(label, s):
    if not s:
        return f"| {label} | 0 | - | - | - | - |"
    flag = " ⚠️不足" if s["n"] < 30 else ""
    return (f"| {label} | {s['n']}{flag} | {s['hit']*100:.1f}% | {s['mean']*100:+.2f}% | "
            f"{s['med']*100:+.2f}% | {s['p10']*100:+.2f}% |")


def analyze_raw():
    d = json.load(open(RAW))
    recs = d["recs"]
    for r in recs:
        r["excess"] = {int(k): v for k, v in r["excess"].items()}
        r["pol"] = {int(k): v for k, v in r["pol"].items()}
    dates = sorted({r["D"] for r in recs})
    split = d.get("split", SPLIT)
    ntr = sum(1 for x in dates if x < split)
    nte = sum(1 for x in dates if x >= split)

    def seg(r):
        return "train" if r["D"] < split else "test"

    L = []
    L.append(f"# 舊版補漲策略回測 — 與現行 buy-strong 同框架對照 (2026-07-04)\n")
    L.append(f"資料:{d['n_obs']} 筆觀測 / {d['eval_days']} 評估日 / 範圍 {d['range']} / 暖身 {d['warmup']}。")
    L.append(f"train/test 切點 **{split}**(train {ntr} 評估日 / test {nte} 評估日;硬定,同現行實驗)。")
    L.append("指標:相對 TAIEX 超額,PIT(評分 asof=D、前瞻 asof=None 全還原)。舊 find_laggards 候選 cohort。")
    L.append("欄位:n / 命中(超額>0)/ 平均超額 / 中位 / p10(左尾)。n<30 標⚠️不足。\n")

    BUCKETS = [(60, 70), (70, 75), (75, 80), (80, 101)]
    BLAB = {(60, 70): "60-69", (70, 75): "70-74", (75, 80): "75-79", (80, 101): "80+"}

    def sub(cond, h, sg, regime):
        return [r["excess"][h] for r in recs if h in r["excess"] and cond(r)
                and seg(r) == sg and (regime == "all" or r["bull"])]

    # ══ L1 舊 cohort 分桶 ══
    L.append("## L1 舊補漲候選分桶(60-69/70-74/75-79/80+)\n")
    for regime in ("bull", "all"):
        L.append(f"### regime={regime}")
        for h in (5, 10, 20):
            L.append(f"\n**h={h}** — 桶×段")
            L.append("| 桶/段 | n | 命中 | 平均 | 中位 | p10 |")
            L.append("|---|---|---|---|---|---|")
            for lo, hi in BUCKETS:
                for sg in ("train", "test"):
                    s = _stat(sub(lambda r, lo=lo, hi=hi: lo <= r["score"] < hi, h, sg, regime))
                    L.append(_row(f"{BLAB[(lo,hi)]} {sg}", s))
            # 累積門檻 >=70 / >=80
            for T in (70, 80):
                for sg in ("train", "test"):
                    s = _stat(sub(lambda r, T=T: r["score"] >= T, h, sg, regime))
                    L.append(_row(f">={T} {sg}", s))
        L.append("")

    # ══ L2 舊 cohort + trust_net5>0 覆疊 ══
    L.append("## L2 舊 cohort × trust_net5>0 覆疊(score>=70 & regime)\n")
    for regime in ("bull", "all"):
        L.append(f"### regime={regime}")
        for h in (5, 10, 20):
            L.append(f"\n**h={h}**")
            L.append("| trust/段 | n | 命中 | 平均 | 中位 | p10 |")
            L.append("|---|---|---|---|---|---|")
            for grp, cond in (("net>0", lambda r: r["trust_net5"] is not None and r["trust_net5"] > 0),
                              ("net<=0", lambda r: r["trust_net5"] is not None and r["trust_net5"] <= 0)):
                for sg in ("train", "test"):
                    s = _stat(sub(lambda r, cond=cond: r["score"] >= 70 and cond(r), h, sg, regime))
                    L.append(_row(f"{grp} {sg}", s))
        L.append("")

    # ══ L3 出場政策(cohort 70+ 與 80+;P0 vs PA2)══
    L.append("## L3 出場政策 P0 vs PA2(bull;cohort score>=70 與 >=80;h=10/20)\n")
    for TH in (70, 80):
        L.append(f"### cohort score>={TH} & bull")
        for h in (20, 10):
            L.append(f"\n**h={h}**")
            L.append("| 政策/段 | n | 命中 | 平均 | 中位 | p10 | 提前出場 | 平均持有 |")
            L.append("|---|---|---|---|---|---|---|---|")
            for pol in ("P0", "PA2"):
                for sg in ("train", "test"):
                    subr = [r for r in recs if r["score"] >= TH and r["bull"] and seg(r) == sg
                            and h in r["pol"] and pol in r["pol"][h]]
                    xs = [r["pol"][h][pol]["ex"] for r in subr]
                    s = _stat(xs)
                    if s:
                        early = mean([1 if r["pol"][h][pol]["early"] else 0 for r in subr]) * 100
                        hold = mean([r["pol"][h][pol]["hold"] for r in subr])
                        flag = " ⚠️不足" if s["n"] < 30 else ""
                        L.append(f"| {pol} {sg} | {s['n']}{flag} | {s['hit']*100:.1f}% | "
                                 f"{s['mean']*100:+.2f}% | {s['med']*100:+.2f}% | {s['p10']*100:+.2f}% | "
                                 f"{early:.1f}% | {hold:.1f} |")
                    else:
                        L.append(f"| {pol} {sg} | 0 | - | - | - | - | - | - |")
        L.append("")

    txt = "\n".join(L)
    with open(os.path.join(SP, "LEGACY_COMPARE.md"), "w", encoding="utf-8") as f:
        f.write(txt)
    # 另存機器可讀關鍵格(供 L4 頭對頭引用)
    key = {}
    for regime in ("bull", "all"):
        for h in (5, 10, 20):
            for T in (70, 75, 80):
                for sg in ("train", "test"):
                    s = _stat(sub(lambda r, T=T: r["score"] >= T, h, sg, regime))
                    key[f"{regime}|h{h}|>={T}|{sg}"] = s
    json.dump({"split": split, "eval_days": d["eval_days"], "n_obs": d["n_obs"],
               "range": d["range"], "thresh": key},
              open(os.path.join(SP, "legacy_key.json"), "w"), ensure_ascii=False, indent=1)
    print(f"寫入 {SP}/LEGACY_COMPARE.md 與 legacy_key.json")
    print(f"split={split} train={ntr} test={nte} eval_days={d['eval_days']} n_obs={d['n_obs']}")


def main_cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--warmup", type=int, default=backtest.WARMUP)
    a = ap.parse_args()
    if a.collect:
        collect(warmup=a.warmup)
    if a.analyze:
        analyze_raw()
    if not (a.collect or a.analyze):
        ap.print_help()


if __name__ == "__main__":
    main_cli()
