"""舊版『補漲(低基期均值回歸)』選股引擎 — 從 commit 18ed8ec^ (parent) 的 analyze.py 原封搬出。
用途:回測對照。只搬「與現行 buy-strong 引擎不同」的三塊——entry_score / qualifying_laggards /
find_laggards——其餘(build_metrics / build_industries / market_state)沿用現行 analyze,因為現行
build_metrics 是舊版的『超集』:舊 entry_score / qualifying_laggards 讀的每個欄位
(ret20, ret5, off_high, vol_ratio, vol_spike, ma_above, trust_streak, trust_net5, foreign_net5,
rev_yoy, rev_mom, industry, percentile)在現行 build_metrics 都以『完全相同公式』計算(逐行比對過),
故不需複製舊 build_metrics,也不會污染新舊指標定義。

⚠️ 不進正式報告路徑。只給 scripts/legacy_backtest.py 呼叫。
無 look-ahead:所有欄位皆來自 _truncate(asof=D) 的價/量/法人與 rev_build(D)(publish_date<=D 營收),
與現行 backtest 同一 PIT 管線;此模組不新增任何讀價邏輯,只換計分/篩選公式。
"""


def entry_score(m, industry_pct):
    """舊版台股進場分數(commit 18ed8ec^:analyze.py L131-184 原文)。
    產業 25 + 法人 35(投信連買 17.5 + 外資5日 35/3 + 投信5日 35/6)+ 營收 10 + 站上三線 10 + 量能 20。
    """
    reasons = []

    ind_pts = round(industry_pct * 25)
    pts = min(m["trust_streak"], 8) / 8 * 17.5  # 投信連買(占法人 35 分的一半)
    if m["foreign_net5"] > 0:
        pts += 35 / 3
    if m["trust_net5"] > 0:
        pts += 35 / 6
    inst_pts = round(pts)

    yoy, mom = m["rev_yoy"], m["rev_mom"]
    pts = 0
    if yoy is not None and yoy > 0:
        pts = 5 + min(yoy, 50) / 50 * 3
    if mom is not None and mom > 0:
        pts += 2
    rev_pts = round(pts)

    ma_pts = round(m["ma_above"] * 10 / 3)  # 站上 5/10/20 三線各約 3.3 分,滿分 10

    vr = m["vol_ratio"] or 0
    vol_pts = 12 if vr >= 1.5 else 8 if vr >= 1.2 else 4 if vr >= 1.0 else 0
    spike = m["vol_spike"] or 0
    if spike >= 2:
        vol_pts += 8

    parts = [("industry", ind_pts, 25), ("inst", inst_pts, 35),
             ("revenue", rev_pts, 10), ("ma3", ma_pts, 10), ("vol", vol_pts, 20)]
    score = sum(p[1] for p in parts)

    if m["trust_streak"] >= 2:
        reasons.append(("trust_streak", m["trust_streak"]))
    elif m["trust_net5"] > 0:
        reasons.append(("trust_net5", m["trust_net5"] // 1000))
    if m["foreign_net5"] > 0:
        reasons.append(("foreign5", m["foreign_net5"] // 1000))
    if yoy is not None and yoy > 0:
        reasons.append(("yoy", yoy))
    if m["ma_above"] == 3:
        reasons.append(("ma3",))
    if m["off_high"] is not None:
        reasons.append(("off_high", m["off_high"] * 100))
    if spike >= 2:
        reasons.append(("spike", spike))
    elif vr >= 1.2:
        reasons.append(("vol", vr))

    return score, parts, reasons


def qualifying_laggards(industries, exclude=frozenset(), attention=frozenset(), profile="tw"):
    """舊版補漲候選合格池(commit 18ed8ec^:analyze.py L331-361 原文)。
    合格條件:強勢產業(前8) + 漲幅落後同業(lagging) + 低基期(low_base:離60日高<=-10%) + 甦醒(waking)。
    tw:甦醒 = 量增(vol_ratio>=1.2) 或 爆量(vol_spike>=2) 或 投信連買>=2 或 投信5日買超>0。"""
    cands = []
    for ind in industries[:8]:  # TOP_INDUSTRIES
        for m in ind["members"]:
            if m["stock_id"] in exclude:
                continue
            if m["off_high"] is None or m["ret20"] is None:
                continue
            lagging = m["ret20"] < ind["ret20"]
            low_base = m["off_high"] <= -0.10 if profile == "tw" else m["off_high"] <= -0.08
            if profile == "tw":
                waking = ((m["vol_ratio"] or 0) >= 1.2 or (m["vol_spike"] or 0) >= 2
                          or m["trust_streak"] >= 2 or m["trust_net5"] > 0)
            else:
                waking = (m["vol_ratio"] or 0) >= 1.2 or (m["ret5"] is not None and m["ret5"] > 0)
            if lagging and low_base and waking:
                score, parts, reasons = entry_score(m, ind["percentile"])
                if m["stock_id"] in attention:
                    reasons.insert(0, ("attention",))
                cands.append({**m, "industry_rank": ind["rank"], "industry_ret20": ind["ret20"],
                              "score": score, "parts": parts, "reasons": reasons})
    cands.sort(key=lambda x: x["score"], reverse=True)
    return cands


def cap_and_limit(cands, profile="tw", limit=20):
    """產業分散上限 + 前 N 名截斷(commit 18ed8ec^:analyze.py L364-378 原文)。"""
    cap = 5 if profile == "tw" else 4
    per_ind = {}
    out = []
    for c in cands:
        if per_ind.get(c["industry"], 0) >= cap:
            continue
        per_ind[c["industry"]] = per_ind.get(c["industry"], 0) + 1
        out.append(c)
        if len(out) == limit:
            break
    return out


def find_laggards(industries, exclude=frozenset(), attention=frozenset(), profile="tw"):
    """舊版補漲候選:合格池 → 產業分散上限 → 前 20 名(commit 18ed8ec^:analyze.py L381-384 原文)。"""
    cands = qualifying_laggards(industries, exclude, attention, profile)
    return cap_and_limit(cands, profile)
