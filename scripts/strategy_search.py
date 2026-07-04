"""策略族系統性搜尋(誠實可驗證的每日行動清單規則)。

設計:一趟 PIT pass 把每日全市場特徵(MA/量比/trust/突破/漲停旗標)算進 numpy 2D 陣列,
再對各策略族掃參數。不改 analyze.py/CURRENT_W/report.py。

PIT 約定(與 backtest.experiment 同口徑):
  • 特徵序列:除權息 asof=None 全還原 close/high/low(總報酬基準);量 vol 未還原;
    漲停判定用「未還原原始」close/high。
  • 訊號在 D=cal[i] 用 ≤i 的資料算;進場一律隔日生效:base=cal[i+1] 收盤,
    持有 h 日 → 出場 cal[i+1+h] 收盤。超額 vs 同窗 TAIEX。
  • 成本:絕對報酬扣台股來回成本 0.585%(賣出證交稅0.3%+來回手續費約0.285%)。
  • 勝率(a)=絕對報酬(扣成本)>0;勝率(b)=超額(vs TAIEX,兩邊皆毛)>0。
  • train: D<20250828(探索);test: D>=20250828(一次性驗證)。

殘留 look-ahead 說明(誠實揭露):特徵用 asof=None 全還原,窗內若有除息事件會讓過去價被
未來股利略微壓低(MA/突破門檻偏鬆 ≲3%/事件),與 repo E 系列同一妥協;前瞻報酬用 asof=None
為已實現總報酬則無 look-ahead。漲停旗標用原始價無此問題。
"""
import json
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import adjust  # noqa: E402
import db      # noqa: E402
import main    # noqa: E402

SPLIT = "20250828"
COST = 0.00585          # 來回成本(賣出證交稅0.3% + 來回手續費約0.285%)
LIMIT_UP = 1.093        # 漲停近似門檻(未還原收盤 >= 前日未還原收盤 × 1.093)
HORIZONS = (1, 5, 10, 20)


def build_arrays():
    conn = db.connect()
    prices = db.load_prices(conn)                       # 原始(未還原)
    inst = db.load_inst(conn)
    taiex = db.load_taiex(conn)
    dividends = adjust.load_dividends(main.DIVIDENDS_PATH)
    prices_adj = adjust.adjust_prices(prices, dividends, asof=None)

    cal = [d for d, _ in taiex]
    di = {d: i for i, d in enumerate(cal)}
    nd = len(cal)
    tx = np.full(nd, np.nan)
    for d, c in taiex:
        tx[di[d]] = c

    sids = sorted(prices_adj.keys())
    # 只保留 twse/tpex(排除 us)
    sids = [s for s in sids if prices_adj[s].get("market") in ("twse", "tpex")]
    ns = len(sids)
    sidx = {s: k for k, s in enumerate(sids)}

    cA = np.full((ns, nd), np.nan)   # adj close
    hA = np.full((ns, nd), np.nan)   # adj high
    lA = np.full((ns, nd), np.nan)   # adj low
    vol = np.full((ns, nd), np.nan)  # raw vol
    cR = np.full((ns, nd), np.nan)   # raw close (limit-up)
    hR = np.full((ns, nd), np.nan)   # raw high (locked)

    for s in sids:
        k = sidx[s]
        for r in prices_adj[s]["rows"]:      # (date, close, high, vol, val, low)
            j = di.get(r[0])
            if j is None:
                continue
            cA[k, j] = r[1]; hA[k, j] = r[2]; vol[k, j] = r[3]; lA[k, j] = r[5]
    for s in sids:
        k = sidx[s]
        for r in prices[s]["rows"]:
            j = di.get(r[0])
            if j is None:
                continue
            cR[k, j] = r[1]; hR[k, j] = r[2]

    trust = np.full((ns, nd), np.nan)
    forn = np.full((ns, nd), np.nan)
    for s, rows in inst.items():
        k = sidx.get(s)
        if k is None:
            continue
        for d, fn, tn in rows:
            j = di.get(d)
            if j is None:
                continue
            trust[k, j] = tn if tn is not None else np.nan
            forn[k, j] = fn if fn is not None else np.nan
    return dict(cal=cal, tx=tx, sids=sids, sidx=sidx, cA=cA, hA=hA, lA=lA,
                vol=vol, cR=cR, hR=hR, trust=trust, forn=forn)


def roll_mean(a, n):
    """沿 axis=1 的 n 日均值;窗內任一 nan → nan(要求全窗有值)。"""
    ns, nd = a.shape
    filled = np.nan_to_num(a, nan=0.0)
    valid = (~np.isnan(a)).astype(np.float64)
    cs = np.cumsum(filled, axis=1)
    cv = np.cumsum(valid, axis=1)
    out = np.full_like(a, np.nan)
    ssum = cs[:, n - 1:].copy()
    ssum[:, 1:] -= cs[:, :-n]
    scnt = cv[:, n - 1:].copy()
    scnt[:, 1:] -= cv[:, :-n]
    full = scnt >= n
    res = np.full_like(ssum, np.nan)
    res[full] = ssum[full] / n
    out[:, n - 1:] = res
    return out


def roll_max_prior(a, n):
    """cal[t] 之前(不含 t)n 日最大值;不足回 nan。"""
    ns, nd = a.shape
    out = np.full_like(a, np.nan)
    for t in range(1, nd):
        lo = max(0, t - n)
        w = a[:, lo:t]
        with np.errstate(all="ignore"):
            m = np.nanmax(w, axis=1)
        cnt = (~np.isnan(w)).sum(axis=1)
        m[cnt == 0] = np.nan
        out[:, t] = m
    return out


def compute_features(A):
    cA, vol, cR, hR = A["cA"], A["vol"], A["cR"], A["hR"]
    tx = A["tx"]
    F = {}
    F["ma5"] = roll_mean(cA, 5)
    F["ma10"] = roll_mean(cA, 10)
    F["ma20"] = roll_mean(cA, 20)
    F["ma60"] = roll_mean(cA, 60)
    ns, nd = cA.shape
    # ret20
    ret20 = np.full_like(cA, np.nan)
    ret20[:, 20:] = cA[:, 20:] / cA[:, :-20] - 1
    F["ret20"] = ret20
    # vol 20 均量(到 t 含)
    F["vma20"] = roll_mean(vol, 20)
    # vol_ratio 當日 = vol[t]/vma20[t]
    with np.errstate(all="ignore"):
        F["vratio"] = vol / F["vma20"]
    # 前 20 日最大 vratio(不含 t):量安靜判定
    F["vratio_prior_max"] = roll_max_prior(np.nan_to_num(F["vratio"], nan=0.0), 20)
    # 突破:前 60 日最高(不含 t)
    F["high60_prior"] = roll_max_prior(A["hA"], 60)
    # trust_net5 = 近5日 trust 合計(要求至少1日有值)
    tr = A["trust"]
    trf = np.nan_to_num(tr, nan=0.0)
    trv = (~np.isnan(tr)).astype(np.float64)
    cs = np.cumsum(trf, axis=1); cvv = np.cumsum(trv, axis=1)
    tn5 = np.full_like(tr, np.nan); cnt5 = np.full_like(tr, np.nan)
    ssum = cs[:, 4:].copy(); ssum[:, 1:] -= cs[:, :-5]
    scnt = cvv[:, 4:].copy(); scnt[:, 1:] -= cvv[:, :-5]
    tn5[:, 4:] = np.where(scnt >= 1, ssum, np.nan)
    F["trust_net5"] = tn5
    # 當日 trust>0
    F["trust_pos"] = tr > 0
    # 投信連買>=2(近2日皆>0)
    tr_prev = np.full_like(tr, np.nan); tr_prev[:, 1:] = tr[:, :-1]
    F["trust_buy2"] = (tr > 0) & (tr_prev > 0)
    # 漲停旗標(未還原):close_R[t] >= close_R[t-1]*1.093
    cR_prev = np.full_like(cR, np.nan); cR_prev[:, 1:] = cR[:, :-1]
    with np.errstate(all="ignore"):
        limit = cR >= cR_prev * LIMIT_UP
    limit &= ~np.isnan(cR) & ~np.isnan(cR_prev)
    F["limit_up"] = limit
    # 鎖死:close_R == high_R
    with np.errstate(all="ignore"):
        locked = (cR == hR) & ~np.isnan(cR) & ~np.isnan(hR)
    F["locked"] = locked
    # 當日漲幅(還原)ret1
    ret1 = np.full_like(cA, np.nan); ret1[:, 1:] = cA[:, 1:] / cA[:, :-1] - 1
    F["ret1"] = ret1
    # taiex MAs
    def tma(n):
        out = np.full(nd, np.nan)
        for t in range(n - 1, nd):
            w = tx[t - n + 1:t + 1]
            if not np.isnan(w).any():
                out[t] = w.mean()
        return out
    F["tx_ma5"] = tma(5); F["tx_ma10"] = tma(10); F["tx_ma20"] = tma(20); F["tx_ma60"] = tma(60)
    return F


def fwd_returns(A):
    """進場 cal[i+1] 收盤,持有 h → 出場 cal[i+1+h]。回傳 {h: ret2d}, taiex {h: 1d}。
    ret2d[s,i] 為在訊號日 i 產生訊號、隔日進場、持有 h 的毛絕對報酬。"""
    cA, tx = A["cA"], A["tx"]
    ns, nd = cA.shape
    R = {}; TR = {}
    for h in HORIZONS:
        r = np.full((ns, nd), np.nan)
        # entry index e=i+1, exit e+h=i+1+h ; valid i: i+1+h<=nd-1
        hi = nd - 1 - (h + 1)
        if hi < 0:
            R[h] = r; TR[h] = np.full(nd, np.nan); continue
        ent = cA[:, 1:hi + 2]           # e for i in 0..hi  → cols 1..hi+1
        ext = cA[:, 1 + h:hi + 2 + h]
        with np.errstate(all="ignore"):
            r[:, :hi + 1] = ext / ent - 1
        R[h] = r
        tr = np.full(nd, np.nan)
        te = tx[1:hi + 2]; tx2 = tx[1 + h:hi + 2 + h]
        with np.errstate(all="ignore"):
            tr[:hi + 1] = tx2 / te - 1
        TR[h] = tr
    return R, TR


def stats(ret, txret):
    """ret: 1d 毛絕對報酬陣列;txret: 對應同窗 taiex 報酬。回傳指標 dict。"""
    m = ~np.isnan(ret) & ~np.isnan(txret)
    ret = ret[m]; txret = txret[m]
    n = len(ret)
    if n == 0:
        return None
    net = ret - COST
    excess = ret - txret
    return dict(n=int(n),
                win_a=float((net > 0).mean()),        # 絕對報酬(扣成本)>0
                win_b=float((excess > 0).mean()),     # 贏大盤
                mean_excess=float(excess.mean()),
                mean_abs_net=float(net.mean()),
                p10=float(np.percentile(net, 10)))


def exit_sim(A, cand_idx, target, stop, tmax=20, half=False):
    """出場工程:進場 cal[i+1] 收盤;走 cal[i+2..i+1+tmax] 收盤。
    首個收盤 >= base*(1+target) 觸目標;<= base*(1-stop) 觸停損;否則 tmax 收盤出。
    half=True: 觸目標賣半、剩餘續走(再觸停損/tmax 出;若後續再 >= 目標不重複賣,抱到條件)。
    回傳 (毛絕對報酬陣列, taiex 同窗報酬陣列)。保守:全用收盤判定。"""
    cA, tx = A["cA"], A["tx"]
    nd = cA.shape[1]
    rets = []; txr = []; ivals = []
    for (s, i) in cand_idx:
        e = i + 1
        if e + 1 > nd - 1:
            continue
        base = cA[s, e]
        if np.isnan(base) or base <= 0:
            continue
        tgt = base * (1 + target); stp = base * (1 - stop)
        realized = None; sold_half = False; acc = 0.0; rem = 1.0
        last_t = min(e + tmax, nd - 1)
        for t in range(e + 1, last_t + 1):
            c = cA[s, t]
            if np.isnan(c):
                continue
            r = c / base - 1
            if c <= stp:
                acc += rem * r; rem = 0.0; realized = (acc, t); break
            if c >= tgt:
                if half and not sold_half:
                    acc += 0.5 * r; rem -= 0.5; sold_half = True
                else:
                    acc += rem * r; rem = 0.0; realized = (acc, t); break
        if realized is None:
            c = cA[s, last_t]
            if np.isnan(c):
                continue
            acc += rem * (c / base - 1); realized = (acc, last_t)
        ret, tt = realized
        te = tx[e]; tx2 = tx[tt]
        if np.isnan(te) or np.isnan(tx2):
            continue
        rets.append(ret); txr.append(tx2 / te - 1); ivals.append(i)
    return np.array(rets), np.array(txr), np.array(ivals)


def split_mask(A, i_arr):
    cal = A["cal"]
    train = np.array([cal[i] < SPLIT for i in i_arr])
    return train, ~train


# ════════════════════════════ 搜尋驅動 ════════════════════════════

def _idx_stats(ret, txret, ivals, cal_np):
    """把一組觀測(毛報酬/taiex報酬/訊號日 index)切 train/test 各算指標。"""
    tr = cal_np[ivals] < SPLIT
    out = {}
    out["train"] = stats(ret[tr], txret[tr])
    out["test"] = stats(ret[~tr], txret[~tr])
    return out


def eval_mask(mask2d, h, R, TR, cal_np, bull1d=None):
    valid = mask2d & ~np.isnan(R[h]) & ~np.isnan(TR[h])[None, :]
    rows, cols = np.where(valid)
    if bull1d is not None:
        keep = bull1d[cols]
        rows, cols = rows[keep], cols[keep]
    ret = R[h][rows, cols]; txret = TR[h][cols]
    return _idx_stats(ret, txret, cols, cal_np), (rows, cols)


def pick_top2(configs):
    """configs: list of dict(name, train, ...). 取 train n>=30 且期望(mean_abs_net)>0,
    以 win_a 降冪前2;若無正期望者則以 win_a 降冪前2 並標記。"""
    ok = [c for c in configs if c["train"] and c["train"]["n"] >= 30 and c["train"]["mean_abs_net"] > 0]
    pool = ok if ok else [c for c in configs if c["train"] and c["train"]["n"] >= 30]
    pool = sorted(pool, key=lambda c: c["train"]["win_a"], reverse=True)
    return pool[:2], bool(ok)


def fmt(s):
    if not s:
        return "n<有效樣本"
    return (f"n={s['n']} winA={s['win_a']*100:.1f}% winB={s['win_b']*100:.1f}% "
            f"exc={s['mean_excess']*100:+.2f}% abs_net={s['mean_abs_net']*100:+.2f}% p10={s['p10']*100:+.1f}%")


def run_all():
    import time
    t0 = time.time()
    A = build_arrays()
    F = compute_features(A)
    R, TR = fwd_returns(A)
    cal = A["cal"]; cal_np = np.array(cal)
    bull1d = (A["tx"] > F["tx_ma60"])
    cA = A["cA"]
    fam = {}          # family -> {"tried":int, "configs":[...], "top2":[...], "has_pos":bool}
    verified = []     # 所有 test 驗證過的配置(給總表)

    def register(family, name, mask2d, h, bull=True):
        st, _ = eval_mask(mask2d, h, R, TR, cal_np, bull1d if bull else None)
        return {"name": name, "h": h, "bull": bull, "train": st["train"], "test": st["test"]}

    # ---------- F1 趨勢拉回 ----------
    cfgs = []
    base = (cA > F["ma60"]) & (F["ret20"] > 0)
    volshrink = F["vratio"] < 1.0
    trustpos = F["trust_net5"] > 0
    for mapull, mname in ((F["ma10"], "10MA"), (F["ma20"], "20MA")):
        with np.errstate(all="ignore"):
            near = np.abs(cA / mapull - 1) <= 0.02
        for vlabel, vmask in (("base", None), ("+trust", trustpos), ("+量縮", volshrink)):
            m = base & near
            if vmask is not None:
                m = m & vmask
            for h in (5, 10, 20):
                cfgs.append(register("F1", f"站上60+ret20>0+近{mname}2%{'' if vlabel=='base' else vlabel}", m, h))
    top2, hp = pick_top2(cfgs)
    fam["F1"] = {"tried": len(cfgs), "top2": top2, "has_pos": hp, "configs": cfgs}
    verified += top2

    # ---------- F2 投信+突破 ----------
    cfgs = []
    brk = cA > F["high60_prior"]
    for tlabel, tmask in (("trust5>0", trustpos), ("連買>=2", F["trust_buy2"])):
        m = brk & tmask
        for h in (5, 10, 20):
            cfgs.append(register("F2", f"突破60高+{tlabel}", m, h))
    top2, hp = pick_top2(cfgs)
    fam["F2"] = {"tried": len(cfgs), "top2": top2, "has_pos": hp, "configs": cfgs}
    verified += top2

    # ---------- F5 爆量初動 ----------
    cfgs = []
    for vr in (3.0, 2.5):
        spike = (F["vratio"] >= vr) & (F["ret1"] > 0.04) & (F["vratio_prior_max"] < 1.5)
        for h in (5, 10, 20):
            cfgs.append(register("F5", f"爆量{vr}x+漲>4%+前20安靜(隔日)", spike, h))
    top2, hp = pick_top2(cfgs)
    fam["F5"] = {"tried": len(cfgs), "top2": top2, "has_pos": hp, "configs": cfgs}
    verified += top2

    # ---------- F6a 首板續攻 ----------
    cfgs = []
    lu = F["limit_up"]
    # 首次漲停:今日漲停且前20日無漲停
    lu_prior = roll_max_prior(lu.astype(float), 20)
    first_lu = lu & (np.nan_to_num(lu_prior, nan=0.0) == 0)
    for vr in (2.0, 3.0):
        m = first_lu & F["locked"] & (F["vratio"] >= vr)
        for h in (1, 5, 10):
            cfgs.append(register("F6a", f"首次漲停+鎖死+爆量{vr}x(隔日)", m, h))
    top2, hp = pick_top2(cfgs)
    fam["F6a"] = {"tried": len(cfgs), "top2": top2, "has_pos": hp, "configs": cfgs}
    verified += top2

    # ---------- F3 出場工程(疊加 F1best/F2best/補漲>=60) ----------
    # 候選集:F1 與 F2 的 train 最佳配置遮罩(不分 horizon,以進場訊號為準),再加補漲>=60
    def best_mask(cfglist):
        # 以 train win_a 最高的配置的遮罩重建
        return cfglist[0] if cfglist else None
    cand_sets = {}
    # F1 最佳訊號遮罩(取 F1 top1 名稱重建 mask):簡化用 base+近10MA2%
    with np.errstate(all="ignore"):
        near10 = np.abs(cA / F["ma10"] - 1) <= 0.02
    cand_sets["F1(站上60+近10MA)"] = base & near10
    cand_sets["F2(突破+trust5>0)"] = brk & trustpos
    # 補漲>=60(來自 exp_recs.json,若存在)
    SP = os.environ.get("SP", os.path.dirname(os.path.abspath(__file__)))
    # 舊補漲(legacy)引擎候選為基準來源;無則退回現行 buy-strong exp_recs
    exp_path = os.path.join(SP, "legacy_raw.json")
    if not os.path.exists(exp_path):
        exp_path = os.path.join(SP, "exp_recs.json")
    lag_idx = None
    if os.path.exists(exp_path):
        with open(exp_path, encoding="utf-8") as f:
            exp = json.load(f)
        di = {d: k for k, d in enumerate(cal)}
        pts = []
        for r in exp.get("recs", []):
            if r.get("score", 0) >= 60 and r["D"] in di and r["sid"] in A["sidx"]:
                pts.append((A["sidx"][r["sid"]], di[r["D"]]))
        lag_idx = pts
        # 舊補漲基準(同 experiment 口徑:同日進場、excess=vs taiex、h20):供對照
        def _lbase(pred):
            e = [r["excess"].get("20") for r in exp.get("recs", [])
                 if pred(r) and "20" in r.get("excess", {}) and r["excess"].get("20") is not None]
            e = np.array(e)
            if len(e) == 0:
                return None
            return {"n": int(len(e)), "hit_exc": float((e > 0).mean()), "mean_exc": float(e.mean())}
        fam.setdefault("_legacy_baseline", {})
        fam["_legacy_baseline"] = {
            ">=60 bull TEST": _lbase(lambda r: r["score"] >= 60 and r["bull"] and r["D"] >= SPLIT),
            ">=60 bull TRAIN": _lbase(lambda r: r["score"] >= 60 and r["bull"] and r["D"] < SPLIT),
            ">=60+trust>0 bull TEST": _lbase(lambda r: r["score"] >= 60 and r["bull"] and (r.get("trust_net5") or 0) > 0 and r["D"] >= SPLIT),
        }
    f3cfgs = []
    f3sources = {"F1": cand_sets["F1(站上60+近10MA)"], "F2": cand_sets["F2(突破+trust5>0)"]}
    for label, m in f3sources.items():
        cand = list(zip(*np.where(m)))
        cand = [(int(s), int(i)) for s, i in cand]
        for target in (0.05, 0.08):
            for stop in (0.07, 0.10):
                for half in (False, True):
                    ret, txr, iv = exit_sim(A, cand, target, stop, 20, half)
                    st = _idx_stats(ret, txr, iv, cal_np)
                    f3cfgs.append({"name": f"{label}+目標{int(target*100)}%停損{int(stop*100)}%{'半出' if half else '全出'}",
                                   "h": "exit20", "bull": False, "train": st["train"], "test": st["test"]})
    if lag_idx:
        for target in (0.05, 0.08):
            for stop in (0.07, 0.10):
                for half in (False, True):
                    ret, txr, iv = exit_sim(A, lag_idx, target, stop, 20, half)
                    st = _idx_stats(ret, txr, iv, cal_np)
                    f3cfgs.append({"name": f"補漲>=60+目標{int(target*100)}%停損{int(stop*100)}%{'半出' if half else '全出'}",
                                   "h": "exit20", "bull": False, "train": st["train"], "test": st["test"]})
    top2, hp = pick_top2(f3cfgs)
    fam["F3"] = {"tried": len(f3cfgs), "top2": top2, "has_pos": hp, "configs": f3cfgs}
    verified += top2

    # ---------- F4 大盤守門疊加(比較:bull60 vs +三生無奈排除) ----------
    # 三生無奈日:指數 C < ma5 & ma10 & ma20 → 不進場
    sansheng = (A["tx"] < F["tx_ma5"]) & (A["tx"] < F["tx_ma10"]) & (A["tx"] < F["tx_ma20"])
    gate = bull1d & (~sansheng)
    f4rows = []
    for label, m in (("F1(站上60+近10MA)", base & near10), ("F2(突破+trust5>0)", brk & trustpos)):
        for h in (10,):
            s_bull, _ = eval_mask(m, h, R, TR, cal_np, bull1d)
            s_gate, _ = eval_mask(m, h, R, TR, cal_np, gate)
            f4rows.append({"name": f"{label} h{h}", "bull_only": s_bull, "gated": s_gate})
    fam["F4"] = {"rows": f4rows, "tried": len(f4rows) * 2}

    # ---------- F6b 漲停預測 lift ----------
    # 基準漲停率(全市場 stock-day, D+1 漲停)= P(limit_up[s,i+1])
    lu = F["limit_up"]
    lu_next = np.zeros_like(lu); lu_next[:, :-1] = lu[:, 1:]
    validnext = ~np.isnan(cA)
    validnext[:, -1] = False
    def lift(sigmask, regime=None):
        m = sigmask & validnext
        if regime is not None:
            m = m & regime[None, :]
        n = int(m.sum())
        if n == 0:
            return None
        rate = float(lu_next[m].mean())
        return {"n": n, "rate": rate}
    base_rate = lift(validnext)
    sigs6b = {
        "trust>0": F["trust_pos"],
        "F5爆量初動": (F["vratio"] >= 3.0) & (F["ret1"] > 0.04) & (F["vratio_prior_max"] < 1.5),
        "突破60高": brk,
        "首次漲停(次板機率)": first_lu,
    }
    if lag_idx:
        lagmask = np.zeros_like(lu, dtype=bool)
        for s, i in lag_idx:
            lagmask[s, i] = True
        sigs6b["補漲>=60"] = lagmask
    f6b = {"base": base_rate, "sigs": {}}
    for name, sm in sigs6b.items():
        r = lift(sm)
        if r and base_rate:
            r["lift"] = r["rate"] / base_rate["rate"] if base_rate["rate"] else None
        f6b["sigs"][name] = r
    fam["F6b"] = f6b

    out = {"split": SPLIT, "cost": COST, "families": fam,
           "verified": verified, "elapsed": round(time.time() - t0, 1),
           "n_stocks": len(A["sids"]), "n_days": len(cal),
           "lag_recs": len(lag_idx) if lag_idx else 0}
    return out


if __name__ == "__main__":
    res = run_all()
    SP = os.environ.get("SP", ".")
    with open(os.path.join(SP, "search_raw.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, default=float)
    print("done", res["elapsed"], "s ; stocks", res["n_stocks"], "days", res["n_days"], "lag_recs", res["lag_recs"])
    for fam, d in res["families"].items():
        print("=====", fam, "tried", d.get("tried"))
        for c in d.get("top2", []):
            print(f"  [{c['name']}] h{c['h']}")
            print(f"    train: {fmt(c['train'])}")
            print(f"    test : {fmt(c['test'])}")
        if fam == "F4":
            for r in d["rows"]:
                print(f"  {r['name']}  bull_only: {fmt(r['bull_only']['test'])}")
                print(f"  {r['name']}  gated    : {fmt(r['gated']['test'])}")
        if fam == "F6b":
            b = d["base"]; print(f"  base limit-up next-day rate: {b['rate']*100:.3f}% (n={b['n']})")
            for nm, rr in d["sigs"].items():
                if rr:
                    print(f"  {nm}: rate={rr['rate']*100:.2f}% lift={rr.get('lift',0):.2f}x n={rr['n']}")
