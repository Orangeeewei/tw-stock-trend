"""法人籌碼特徵深挖 — 找能進一步提高勝率的訊號變體(收尾加碼研究)。

只做研究,不改正式程式。重用 strategy_search 的特徵管線(build_arrays/compute_features/
fwd_returns/stats/eval_mask)與同一 PIT 口徑:
  • 訊號在 D=cal[i] 用 <=i 資料算;隔日進場 base=cal[i+1] 收盤;持有 h → 出場 cal[i+1+h]。
  • 除權息 asof=None 全還原(價),量未還原;成本 0.585% 扣在絕對報酬。
  • win_a=絕對報酬(扣成本)>0;win_b=超額(vs TAIEX)>0。
  • train D<20250828 探索、test D>=20250828 一次驗證;n<30 不下結論。
基準(要贏過才有意義):嚴選 = 突破前60日高 & 投信連買>=2,h20/bull/test =
  win_a 53.1% / abs_net +6.72% / excess +0.69% / n=885。

協議:每方向 train 探索所有變體 → 以 train win_a(n>=30 且期望正)自動預註冊 top2 →
只對這 2 個揭露 test。方向6(背離)為固定診斷假設,直接雙段揭露。
"""
import json
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_search as ss  # noqa: E402

SP = "/tmp/claude-1000/-home-orangayge/21b1da87-952e-41ab-a122-c9523e4e3c4c/scratchpad"
SPLIT = ss.SPLIT


def roll_sum(a, n, minvalid=1):
    """沿 axis=1 的 n 日合計;窗內有效值數 >= minvalid 才回值,否則 nan。"""
    filled = np.nan_to_num(a, nan=0.0)
    valid = (~np.isnan(a)).astype(np.float64)
    cs = np.cumsum(filled, axis=1)
    cvv = np.cumsum(valid, axis=1)
    out = np.full_like(a, np.nan)
    ssum = cs[:, n - 1:].copy(); ssum[:, 1:] -= cs[:, :-n]
    scnt = cvv[:, n - 1:].copy(); scnt[:, 1:] -= cvv[:, :-n]
    out[:, n - 1:] = np.where(scnt >= minvalid, ssum, np.nan)
    return out


def streak_pos(a):
    """連買長度:以 t 結尾、連續 (值>0) 的天數。nan 或 <=0 打斷歸零。"""
    pos = (np.nan_to_num(a, nan=0.0) > 0).astype(np.int32)
    ns, nd = a.shape
    out = np.zeros((ns, nd), dtype=np.int32)
    out[:, 0] = pos[:, 0]
    for t in range(1, nd):
        out[:, t] = (out[:, t - 1] + 1) * pos[:, t]
    return out


def build():
    A = ss.build_arrays()
    F = ss.compute_features(A)
    R, TR = ss.fwd_returns(A)
    cal_np = np.array(A["cal"])
    bull1d = (A["tx"] > F["tx_ma60"])
    cA = A["cA"]
    trust = A["trust"]; forn = A["forn"]

    ext = {}
    ext["brk"] = cA > F["high60_prior"]
    ext["trust_pos"] = trust > 0
    ext["foreign_pos"] = forn > 0
    ext["trust_buy2"] = F["trust_buy2"]                       # 基準用
    ext["trust_net5"] = F["trust_net5"]
    ext["foreign_net5"] = roll_sum(forn, 5, minvalid=1)
    # 外資連買>=2
    fprev = np.full_like(forn, np.nan); fprev[:, 1:] = forn[:, :-1]
    ext["foreign_buy2"] = (forn > 0) & (fprev > 0)
    # 首度轉買:今日 trust>0 且前 N 日皆無 trust>0
    tpos_f = (np.nan_to_num(trust, nan=0.0) > 0).astype(float)
    for N in (10, 20):
        prior = ss.roll_max_prior(tpos_f, N)     # 前 N 日(不含今日)最大 = 1 表示曾買
        ext[f"trust_first_{N}"] = (trust > 0) & (np.nan_to_num(prior, nan=0.0) == 0)
    # 連買長度
    ext["trust_streak"] = streak_pos(trust)
    ext["foreign_streak"] = streak_pos(forn)
    # 買超強度正規化:trust_net5 / 5日均量
    vma5 = ss.roll_mean(A["vol"], 5)
    with np.errstate(all="ignore"):
        ext["trust_ratio5"] = ext["trust_net5"] / vma5       # 佔 5日均量比
    return A, F, R, TR, cal_np, bull1d, ext


def ev(mask, h, R, TR, cal_np, bull1d):
    st, _ = ss.eval_mask(mask, h, R, TR, cal_np, bull1d)
    return st


def reg_top2(variants, R, TR, cal_np, bull1d, h=20):
    """variants: list[(name, mask)]. 回傳 (all_train_rows, registered[list of (name, train, test)]).
    以 train win_a(n>=30 且 mean_abs_net>0)降冪取 top2 揭露 test。"""
    rows = []
    for name, m in variants:
        st = ev(m, h, R, TR, cal_np, bull1d)
        rows.append({"name": name, "train": st["train"], "test": st["test"]})
    ok = [r for r in rows if r["train"] and r["train"]["n"] >= 30 and r["train"]["mean_abs_net"] > 0]
    pool = ok if ok else [r for r in rows if r["train"] and r["train"]["n"] >= 30]
    pool = sorted(pool, key=lambda r: r["train"]["win_a"], reverse=True)
    reg = pool[:2]
    reg_names = {r["name"] for r in reg}
    for r in rows:
        r["registered"] = r["name"] in reg_names
    return rows, reg


def s2d(s):
    return None if not s else {k: (float(v) if isinstance(v, (np.floating, float, int)) else v)
                               for k, v in s.items()}


def main():
    A, F, R, TR, cal_np, bull1d, E = build()
    H = 20
    brk = E["brk"]
    out = {"split": SPLIT, "cost": ss.COST, "h": H,
           "n_stocks": len(A["sids"]), "n_days": len(A["cal"]),
           "range": [A["cal"][0], A["cal"][-1]], "directions": {}, "total_variants": 0}

    # ---- 基準重現(brk & 連買>=2)----
    base_st = ev(brk & E["trust_buy2"], H, R, TR, cal_np, bull1d)
    out["baseline"] = {"name": "嚴選:突破60高 & 投信連買>=2", "train": s2d(base_st["train"]),
                       "test": s2d(base_st["test"])}

    tried = 0

    def record(dkey, title, variants, note=""):
        nonlocal tried
        rows, reg = reg_top2(variants, R, TR, cal_np, bull1d, H)
        tried += len(variants)
        out["directions"][dkey] = {
            "title": title, "note": note, "n_variants": len(variants),
            "rows": [{"name": r["name"], "train": s2d(r["train"]),
                      "test": s2d(r["test"]) if r["registered"] else None,
                      "registered": r["registered"]} for r in rows]}

    # ── D1 投信首度轉買 vs 已連買 ──
    record("D1", "投信首度轉買(前N日無買後首次)vs 已連買", [
        ("brk & 首度轉買(前10日無買)", brk & E["trust_first_10"]),
        ("brk & 首度轉買(前20日無買)", brk & E["trust_first_20"]),
        ("brk & 投信當日買超>0", brk & E["trust_pos"]),
    ])

    # ── D2 投信+外資同步 vs 只投信 ──
    record("D2", "投信+外資同步買超 vs 只投信", [
        ("brk & 連買>=2 & 外資5日淨>0", brk & E["trust_buy2"] & (E["foreign_net5"] > 0)),
        ("brk & 投信5日>0 & 外資5日>0", brk & (E["trust_net5"] > 0) & (E["foreign_net5"] > 0)),
        ("brk & 投信當日>0 & 外資當日>0", brk & E["trust_pos"] & E["foreign_pos"]),
    ])

    # ── D3 買超強度正規化(trust_net5/5日均量 分位覆疊嚴選)──
    cohort = brk & E["trust_buy2"]
    tr_train = cal_np < SPLIT
    ratio = E["trust_ratio5"]
    m_all = cohort & ~np.isnan(ratio)
    rows_c, cols_c = np.where(m_all)
    keeptr = tr_train[cols_c] & bull1d[cols_c]
    rvals = ratio[rows_c[keeptr], cols_c[keeptr]]
    rvals = rvals[~np.isnan(rvals)]
    q50 = float(np.percentile(rvals, 50)) if len(rvals) else 0.0
    q66 = float(np.percentile(rvals, 66)) if len(rvals) else 0.0
    with np.errstate(all="ignore"):
        record("D3", f"買超強度=trust_net5/5日均量 分位覆疊嚴選(train中位={q50:.3f} p66={q66:.3f})", [
            (f"嚴選 & 佔比>=中位({q50:.3f})", cohort & (ratio >= q50)),
            (f"嚴選 & 佔比>=p66({q66:.3f})", cohort & (ratio >= q66)),
        ], note=f"train cohort ratio: median={q50:.4f} p66={q66:.4f} n={len(rvals)}")

    # ── D4 連買長度分段 ──
    stk = E["trust_streak"]
    record("D4", "投信連買長度分段(找最佳段)", [
        ("brk & 連買==2", brk & (stk == 2)),
        ("brk & 連買3~4", brk & (stk >= 3) & (stk <= 4)),
        ("brk & 連買>=5", brk & (stk >= 5)),
        ("brk & 連買>=3", brk & (stk >= 3)),
    ])

    # ── D5 外資單獨訊號(突破股)──
    record("D5", "外資單獨訊號在突破股的增益", [
        ("brk & 外資連買>=2", brk & E["foreign_buy2"]),
        ("brk & 外資5日淨>0", brk & (E["foreign_net5"] > 0)),
        ("brk & 外資連買>=3", brk & (E["foreign_streak"] >= 3)),
    ])

    # ── D6 背離(法人賣超但創高)診斷:固定假設、雙段直接揭露 ──
    div = {}
    for nm, m in (("突破 & 投信5日淨<0", brk & (E["trust_net5"] < 0)),
                  ("突破 & 外資5日淨<0", brk & (E["foreign_net5"] < 0)),
                  ("突破 & 投信&外資皆<0", brk & (E["trust_net5"] < 0) & (E["foreign_net5"] < 0)),
                  ("突破(全體,對照)", brk)):
        st = ev(m, H, R, TR, cal_np, bull1d)
        div[nm] = {"train": s2d(st["train"]), "test": s2d(st["test"])}
    out["directions"]["D6"] = {"title": "背離:法人賣超但股價創高(警示旗標,診斷)",
                               "diagnostic": div}
    tried += 4

    out["total_variants"] = tried
    with open(os.path.join(SP, "inst_raw.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)

    # ---- console 摘要 ----
    def fl(s):
        return "n<門檻" if not s else (f"n={s['n']} winA={s['win_a']*100:.1f}% winB={s['win_b']*100:.1f}% "
                                       f"exc={s['mean_excess']*100:+.2f}% abs={s['mean_abs_net']*100:+.2f}% p10={s['p10']*100:+.1f}%")
    b = out["baseline"]
    print(f"總嘗試變體數(含背離4)= {tried}")
    print("\n基準 " + b["name"])
    print("  train:", fl(b["train"])); print("  test :", fl(b["test"]))
    for dk in ("D1", "D2", "D3", "D4", "D5"):
        d = out["directions"][dk]
        print(f"\n==== {dk} {d['title']}")
        if d.get("note"):
            print("  note:", d["note"])
        for r in d["rows"]:
            tag = " [註冊→test]" if r["registered"] else ""
            print(f"  [{r['name']}]{tag}")
            print("    train:", fl(r["train"]))
            if r["registered"]:
                print("    test :", fl(r["test"]))
    print("\n==== D6 背離診斷")
    for nm, v in out["directions"]["D6"]["diagnostic"].items():
        print(f"  [{nm}]")
        print("    train:", fl(v["train"])); print("    test :", fl(v["test"]))
    print(f"\n寫入 {SP}/inst_raw.json")


if __name__ == "__main__":
    main()
