"""核心分析:產業熱度排行、領頭羊、補漲候選與進場分數。

進場分數(0~100)組成,全部以籌碼/營收/位階/量能判斷,不需技術分析背景:
  產業熱度 25 分:所處產業近 20 日表現在全市場的百分位
  法人動向 30 分:投信連續買超天數(15) + 外資近5日買超(10) + 投信近5日買超(5)
  營收動能 20 分:月營收年增率(15) + 月增率轉正(5)
  位階量能 25 分:距 60 日高點的低基期甜蜜帶(12) + 量能放大倍數(13)
"""
from statistics import median

MIN_PRICE = 10            # 過濾低價股
MIN_AVG_VALUE = 50_000_000  # 20 日均成交值至少 5 千萬,確保流動性
TOP_INDUSTRIES = 8        # 取前幾名產業做選股池


def _ret(closes, n):
    if len(closes) < n + 1 or closes[-n - 1] == 0:
        return None
    return closes[-1] / closes[-n - 1] - 1


def build_metrics(prices, inst, revenue, min_price=MIN_PRICE, min_value=MIN_AVG_VALUE):
    """逐檔計算指標。回傳 {stock_id: metrics dict}。"""
    out = {}
    for sid, p in prices.items():
        rows = p["rows"]
        if len(rows) < 21:
            continue
        closes = [r[1] for r in rows]
        highs = [r[2] for r in rows]
        vols = [r[3] for r in rows]
        vals = [r[4] for r in rows]

        close = closes[-1]
        avg_val20 = sum(vals[-20:]) / 20
        if close < min_price or avg_val20 < min_value:
            continue

        high60 = max(highs[-60:])
        vol5 = sum(vols[-5:]) / 5
        vol20 = sum(vols[-20:]) / 20

        m = {
            "stock_id": sid,
            "name": p["name"],
            "market": p.get("market", "twse"),
            "close": close,
            "ret20": _ret(closes, 20),
            "ret5": _ret(closes, 5),
            "off_high": close / high60 - 1 if high60 else None,  # 距60日高,負值
            "vol_ratio": vol5 / vol20 if vol20 else None,
            "value_today": vals[-1],
            "trust_streak": 0,
            "trust_net5": 0,
            "foreign_net5": 0,
        }

        irows = inst.get(sid, [])
        for _, _, tn in reversed(irows):
            if tn > 0:
                m["trust_streak"] += 1
            else:
                break
        m["trust_net5"] = sum(r[2] for r in irows[-5:])
        m["foreign_net5"] = sum(r[1] for r in irows[-5:])

        rev = revenue.get(sid)
        m["industry"] = rev["industry"] if rev else None
        m["rev_yoy"] = rev["yoy"] if rev else None
        m["rev_mom"] = rev["mom"] if rev else None
        out[sid] = m
    return out


def build_industries(metrics, prices):
    """以成分股中位數計算產業強弱,回傳依 ret20 降冪排序的 list。"""
    groups = {}
    for m in metrics.values():
        ind = m.get("industry")
        if ind and m["ret20"] is not None:
            groups.setdefault(ind, []).append(m)

    total_value = sum(m["value_today"] for m in metrics.values()) or 1
    industries = []
    for ind, members in groups.items():
        if len(members) < 3:  # 成分太少的不具代表性
            continue
        industries.append({
            "industry": ind,
            "count": len(members),
            "ret20": median(m["ret20"] for m in members),
            "ret5": median(m["ret5"] for m in members if m["ret5"] is not None),
            "value_share": sum(m["value_today"] for m in members) / total_value,
            "members": members,
        })
    industries.sort(key=lambda x: x["ret20"], reverse=True)
    n = len(industries)
    for i, ind in enumerate(industries):
        ind["rank"] = i + 1
        ind["percentile"] = 1 - i / n  # 第1名 ≈ 1.0
    return industries


def market_state(taiex):
    """大盤總開關:加權指數是否站上 60 日均線。"""
    closes = [c for _, c in taiex]
    if len(closes) < 60:
        return {"close": closes[-1], "ma60": None, "bull": None}
    ma60 = sum(closes[-60:]) / 60
    return {
        "close": closes[-1],
        "ma60": ma60,
        "bull": closes[-1] > ma60,
        "ret1": closes[-1] / closes[-2] - 1 if len(closes) >= 2 else None,
        "ret20": closes[-1] / closes[-21] - 1 if len(closes) >= 21 else None,
    }


def entry_score(m, industry_pct):
    """台股進場分數。parts: [(key, 得分, 滿分)];reasons: [(key, 數值...)],由 locales 轉人話。"""
    reasons = []

    ind_pts = round(industry_pct * 25)
    pts = min(m["trust_streak"], 8) / 8 * 15
    if m["foreign_net5"] > 0:
        pts += 10
    if m["trust_net5"] > 0:
        pts += 5
    inst_pts = round(pts)

    yoy, mom = m["rev_yoy"], m["rev_mom"]
    pts = 0
    if yoy is not None and yoy > 0:
        pts = 8 + min(yoy, 50) / 50 * 7
    if mom is not None and mom > 0:
        pts += 5
    rev_pts = round(pts)

    off = m["off_high"]
    if off is None:
        base_pts = 0
    elif -0.35 <= off <= -0.10:
        base_pts = 12   # 低基期甜蜜帶:離高點還有空間,又沒跌到面目全非
    elif off < -0.35:
        base_pts = 6    # 跌太深,要提防基本面真的出問題
    else:
        base_pts = 4    # 離高點太近,補漲空間有限
    vr = m["vol_ratio"] or 0
    vol_pts = 13 if vr >= 1.5 else 9 if vr >= 1.2 else 5 if vr >= 1.0 else 0

    parts = [("industry", ind_pts, 25), ("inst", inst_pts, 30),
             ("revenue", rev_pts, 20), ("levelvol", base_pts + vol_pts, 25)]
    score = sum(p[1] for p in parts)

    if m["trust_streak"] >= 2:
        reasons.append(("trust_streak", m["trust_streak"]))
    elif m["trust_net5"] > 0:
        reasons.append(("trust_net5", m["trust_net5"] // 1000))
    if m["foreign_net5"] > 0:
        reasons.append(("foreign5", m["foreign_net5"] // 1000))
    if yoy is not None and yoy > 0:
        reasons.append(("yoy", yoy))
    if off is not None:
        reasons.append(("off_high", off * 100))
    if vr >= 1.2:
        reasons.append(("vol", vr))

    return score, parts, reasons


def entry_score_us(m, industry_pct, industry_ret5):
    """美股進場分數:沒有法人/月營收資料,改用價量結構(產業30/位階20/量能25/動能25)。"""
    reasons = []

    ind_pts = round(industry_pct * 30)

    off = m["off_high"]
    if off is None:
        level_pts = 0
    elif -0.35 <= off <= -0.08:
        level_pts = 20
    elif off < -0.35:
        level_pts = 10
    else:
        level_pts = 6

    vr = m["vol_ratio"] or 0
    vol_pts = 25 if vr >= 1.5 else 18 if vr >= 1.2 else 10 if vr >= 1.0 else 0

    mom_pts = 0
    ret5 = m["ret5"]
    if ret5 is not None and ret5 > 0:
        mom_pts += 13
        if industry_ret5 is not None and ret5 > industry_ret5:
            mom_pts += 12
            reasons.append(("beat5",))
        reasons.append(("ret5", ret5 * 100))

    parts = [("industry", ind_pts, 30), ("level", level_pts, 20),
             ("vol", vol_pts, 25), ("momentum", mom_pts, 25)]
    score = sum(p[1] for p in parts)

    if off is not None:
        reasons.append(("off_high", off * 100))
    if vr >= 1.2:
        reasons.append(("vol", vr))

    return score, parts, reasons


def find_leaders(industries, exclude=frozenset()):
    """強勢產業中的領頭羊:接近 60 日新高、表現優於同業。處置股直接排除。"""
    leaders = []
    for ind in industries[:TOP_INDUSTRIES]:
        for m in ind["members"]:
            if m["stock_id"] in exclude:
                continue
            if m["off_high"] is not None and m["off_high"] >= -0.02 and m["ret20"] > ind["ret20"]:
                leaders.append({**m, "industry_rank": ind["rank"]})
    leaders.sort(key=lambda x: x["ret20"], reverse=True)
    return leaders[:15]


def find_laggards(industries, exclude=frozenset(), attention=frozenset(), profile="tw"):
    """補漲候選:強勢產業 + 漲幅落後同業 + 低基期 + 出現甦醒跡象。
    tw:甦醒 = 量增或法人轉買;us:甦醒 = 量增或 5 日轉正(無法人資料)。
    處置股(分盤撮合、交易受限)直接排除;注意股保留但加警示標籤。"""
    cands = []
    for ind in industries[:TOP_INDUSTRIES]:
        for m in ind["members"]:
            if m["stock_id"] in exclude:
                continue
            if m["off_high"] is None or m["ret20"] is None:
                continue
            lagging = m["ret20"] < ind["ret20"]
            low_base = m["off_high"] <= -0.10 if profile == "tw" else m["off_high"] <= -0.08
            if profile == "tw":
                waking = (m["vol_ratio"] or 0) >= 1.2 or m["trust_streak"] >= 2 or m["trust_net5"] > 0
            else:
                waking = (m["vol_ratio"] or 0) >= 1.2 or (m["ret5"] is not None and m["ret5"] > 0)
            if lagging and low_base and waking:
                if profile == "tw":
                    score, parts, reasons = entry_score(m, ind["percentile"])
                else:
                    score, parts, reasons = entry_score_us(m, ind["percentile"], ind.get("ret5"))
                if m["stock_id"] in attention:
                    reasons.insert(0, ("attention",))
                cands.append({**m, "industry_rank": ind["rank"], "industry_ret20": ind["ret20"],
                              "score": score, "parts": parts, "reasons": reasons})
    cands.sort(key=lambda x: x["score"], reverse=True)
    return cands[:20]
