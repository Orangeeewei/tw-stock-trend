"""核心分析:產業熱度排行、領頭羊、強勢進場候選與進場分數。

進場分數(0~100)以「均線趨勢為主、型態位階與量能為輔、籌碼為次要確認」設計,
以價量結構為核心,不依賴月營收:
  均線結構 30 分:收盤站上 5/10/20 日均線,每多站上一條 +10(趨勢的骨幹與進出依據)
  距前高位階 15 分:越接近或突破 60 日高,型態越成立,給分越高
  缺口確認 10 分:近 40 日有向上跳空缺口且未被填補、今日守住=真突破確認
  量能     25 分:5 日均量放大(12) + 今日爆大量(8) + 守住爆量低點成本支撐(5)
  法人籌碼 10 分:投信連買(5) + 外資近5日買超(3) + 投信近5日買超(2)
  產業強度 10 分:所處產業近 20 日表現在全市場的百分位

設計取向(2026-06-28 改版):以「站上幾條均線」決定趨勢方向、用「距前高 + 向上跳空缺口」
衡量突破型態真假、以「量能放大與守住爆量低點」確認成本支撐,籌碼只當輔助;月營收不計分。
跳空缺口用 K 線窗口(當日最低 > 前日最高)判定,只需高/低價,不需開盤價。
各維度內部比例可自由調整,但六項滿分須維持加總 100。
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
        lows = [r[5] for r in rows]

        close = closes[-1]
        avg_val20 = sum(vals[-20:]) / 20
        if close < min_price or avg_val20 < min_value:
            continue

        high60 = max(highs[-60:])
        vol5 = sum(vols[-5:]) / 5
        vol20 = sum(vols[-20:]) / 20
        ma_above = sum(1 for n in (5, 10, 20) if close > sum(closes[-n:]) / n)
        low10 = min(closes[-10:])  # 近 10 日最低收盤:跌破=近期結構失守,當參考停損
        # 爆量低點:近 20 日成交量最大那根 K 棒的最低價,視為當前的成本支撐。
        # 收盤仍站在此價之上=支撐有效;跌破=結構轉弱(老王均線法的成本線概念)。
        i_spike = max(range(len(vols))[-20:], key=lambda i: vols[i])
        vol_base = lows[i_spike]

        # 向上跳空缺口:某日最低 > 前日最高,K 線圖上留下未成交的窗口。缺口下緣(=前日最高)是支撐。
        # 只看最近一個跳空:之後沒有任何一天跌回缺口內(最低跌破下緣)且今日收盤仍在下緣之上
        # = 缺口守住、真突破;若被跌回填補 = 假突破。下緣(gap_floor)當作型態的防守線。
        gap_up_hold, gap_floor = False, None
        for i in range(len(closes) - 1, max(len(closes) - 40, 0), -1):
            if lows[i] > highs[i - 1]:               # 第 i 日相對前一日向上跳空
                floor = highs[i - 1]                 # 缺口下緣
                filled = any(lows[j] < floor for j in range(i + 1, len(closes)))
                gap_up_hold = (not filled) and close > floor
                gap_floor = floor if gap_up_hold else None
                break                                # 只認最近一個跳空缺口

        # ── 老王負向旗標與出場梯次(顯示/回測儀器用,本次不影響現行計分/篩選) ──
        # 全部用還原後價格;上市未滿天數(資料不足)時回 None/False,不得 crash。
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        exit_half = ma5   # 出場梯次①:跌破 5 日均線先減碼一半(顯示用參考價)
        exit_all = ma10   # 出場梯次②:跌破 10 日均線視為多頭結束、出清(顯示用參考價)
        above_ma60 = (close > sum(closes[-60:]) / 60) if len(closes) >= 60 else None

        # 未封閉空方缺口(down_gap_open):近 20 個交易日內某日向下跳空(當日最高 < 前日最低),
        # 且其後(含當日)沒有任何一天的最高價觸及缺口上緣(= 前日最低),代表缺口尚未回補。
        # 老王:缺口不補、趨勢不轉強。個股某些日 high/low 可能缺值,先做容錯。
        down_gap_open = False
        for d in range(max(1, len(closes) - 20), len(closes)):
            if highs[d] is None or lows[d - 1] is None:
                continue
            if highs[d] < lows[d - 1]:                   # 第 d 日向下跳空,留下空方缺口
                gap_top = lows[d - 1]                     # 缺口上緣(前日最低)
                filled = any(highs[j] is not None and highs[j] >= gap_top
                             for j in range(d, len(closes)))
                if not filled:
                    down_gap_open = True
                    break

        # 假突破(false_break):近 10 個交易日內曾創 60 日新高(突破頸線),但今日收盤同時
        # 跌回 5 日線之下、且跌回被突破的頸線(該前高)之下,並且突破後曾出現向下跳空。
        # = 突破無效、由強轉弱的警訊。資料不足 60 日者無法判定 60 日新高,維持 False。
        false_break = False
        for k in range(len(closes) - 1, max(60, len(closes) - 10) - 1, -1):
            if highs[k] is None:
                continue
            prior = [h for h in highs[k - 60:k] if h is not None]
            if not prior:
                continue
            neckline = max(prior)                        # 突破前的 60 日頸線(壓力/前高)
            if highs[k] > neckline:                       # 第 k 日突破 60 日新高
                gap_after = any(highs[j] is not None and lows[j - 1] is not None
                                and highs[j] < lows[j - 1]
                                for j in range(k + 1, len(closes)))
                if close < ma5 and close < neckline and gap_after:
                    false_break = True
                break                                     # 只認最近一次突破

        m = {
            "stock_id": sid,
            "name": p["name"],
            "market": p.get("market", "twse"),
            "close": close,
            "ret20": _ret(closes, 20),
            "ret5": _ret(closes, 5),
            "off_high": close / high60 - 1 if high60 else None,  # 距60日高,負值
            "vol_ratio": vol5 / vol20 if vol20 else None,
            "vol_spike": vols[-1] / vol20 if vol20 else None,  # 今日量/20日均量,抓單日爆大量
            "ma_above": ma_above,  # 站上幾條均線(5/10/20 日)
            "vol_base": vol_base,  # 爆量低點(近 20 日最大量 K 棒的最低價),成本支撐
            "vol_base_hold": close >= vol_base,  # 收盤是否仍守在爆量低點之上
            "gap_up_hold": gap_up_hold,  # 近 40 日內有向上跳空缺口且未被填補、今日仍守住
            "gap_floor": gap_floor,  # 守住的缺口下緣(防守線),無則 None
            "stop_ref": low10,  # 參考停損(近 10 日最低收盤),當第三道防線
            "exit_half": exit_half,  # 出場梯次①:5 日均線(跌破減碼一半)
            "exit_all": exit_all,    # 出場梯次②:10 日均線(跌破出清)
            "above_ma60": above_ma60,  # 收盤是否站上 60 日均線(資料不足回 None)
            "down_gap_open": down_gap_open,  # 上方有未回補的空方缺口(負向旗標)
            "false_break": false_break,      # 假突破型態(負向旗標)
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
    bull = closes[-1] > ma60
    # 止跌試探(repair):只在空頭(bull=False)時判斷,純顯示、不影響任何計分。
    # 條件:大盤收盤已站回 5/10/20 三條短均線。老王:止跌要「缺口回補 + 站回均線」,
    # 但 taiex/us_index 資料表僅存收盤價、無指數 high/low(見 db.py schema),
    # 無法判定指數是否有未回補空方缺口,故退而求其次只用三短均條件。
    repair = False
    if bull is False and len(closes) >= 20:
        c = closes[-1]
        repair = (c > sum(closes[-5:]) / 5 and c > sum(closes[-10:]) / 10
                  and c > sum(closes[-20:]) / 20)
    return {
        "close": closes[-1],
        "ma60": ma60,
        "bull": bull,
        "repair": repair,
        "ret1": closes[-1] / closes[-2] - 1 if len(closes) >= 2 else None,
        "ret20": closes[-1] / closes[-21] - 1 if len(closes) >= 21 else None,
    }


def entry_score(m, industry_pct):
    """台股進場分數。parts: [(key, 得分, 滿分)];reasons: [(key, 數值...)],由 locales 轉人話。

    以價量結構(均線/位階/缺口/量能)為主、籌碼為輔,不計月營收。
    六項滿分:均線 30 + 位階 15 + 缺口 10 + 量能 25 + 法人 10 + 產業 10 = 100。
    調權重時,各維度內部比例可自由縮放,但六項滿分須維持加總 100。
    """
    reasons = []

    # 均線結構(30):站上 5/10/20 每多一條 +10,趨勢方向的骨幹。
    ma_pts = m["ma_above"] * 10

    # 距前高位階(15):越接近或突破 60 日高,突破型態越成立。
    off = m["off_high"]
    if off is None:
        lvl_pts = 0
    elif off >= -0.12:
        lvl_pts = 15
    elif off >= -0.20:
        lvl_pts = 11
    elif off >= -0.30:
        lvl_pts = 5
    else:
        lvl_pts = 0  # 離前高 >30%,突破型態未成立,不給分

    # 缺口確認(10):近 40 日有向上跳空缺口且未被填補、今日守住=真突破確認。
    gap_pts = 10 if m.get("gap_up_hold") else 0

    # 量能(25):均量放大(12)+ 今日爆大量(8)+ 守住爆量低點成本支撐(5)。
    vr = m["vol_ratio"] or 0
    vol_pts = 12 if vr >= 1.5 else 8 if vr >= 1.2 else 4 if vr >= 1.0 else 0
    spike = m["vol_spike"] or 0
    if spike >= 2:
        vol_pts += 8
    if m.get("vol_base_hold"):
        vol_pts += 5

    # 法人籌碼(10):次要確認。投信連買(5)+ 外資5日買超(3)+ 投信5日買超(2)。
    pts = min(m["trust_streak"], 8) / 8 * 5
    if m["foreign_net5"] > 0:
        pts += 3
    if m["trust_net5"] > 0:
        pts += 2
    inst_pts = round(pts)

    # 產業強度(10):所處產業近 20 日在全市場的百分位。
    ind_pts = round(industry_pct * 10)

    parts = [("ma3", ma_pts, 30), ("level", lvl_pts, 15), ("gap", gap_pts, 10),
             ("vol", vol_pts, 25), ("inst", inst_pts, 10), ("industry", ind_pts, 10)]
    score = sum(p[1] for p in parts)

    if m["ma_above"] == 3:
        reasons.append(("ma3",))
    if m["off_high"] is not None:
        reasons.append(("off_high", m["off_high"] * 100))
    if m.get("gap_up_hold"):
        reasons.append(("gap_up",))
    if spike >= 2:
        reasons.append(("spike", spike))
    elif vr >= 1.2:
        reasons.append(("vol", vr))
    if m.get("vol_base_hold"):
        reasons.append(("vol_base",))
    if m["trust_streak"] >= 2:
        reasons.append(("trust_streak", m["trust_streak"]))
    elif m["trust_net5"] > 0:
        reasons.append(("trust_net5", m["trust_net5"] // 1000))
    if m["foreign_net5"] > 0:
        reasons.append(("foreign5", m["foreign_net5"] // 1000))

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


def _lag_blocks(m, ind, in_top8, excluded, profile="tw"):
    """replay qualifying_laggards 的關卡,回傳這檔未進強勢進場候選的原因代碼(可多個)。
    關卡必須與 qualifying_laggards 完全一致(含 tw/us 差異),否則解釋會與實際選股矛盾。
    順序照篩選管線:處置 → 產業冷 → 趨勢未多頭 → 弱於同業 → 距前高太遠 → 無真突破結構 → 被擠掉。"""
    blocks = []
    if excluded:
        blocks.append("disposal")
    if not in_top8:
        blocks.append("industry_cold")
    if m["ma_above"] < 2:
        blocks.append("trend_weak")
    # 同業比較只在該股有被排名的產業時才有意義
    if ind is not None and m["ret20"] is not None and m["ret20"] < ind["ret20"]:
        blocks.append("weaker_peers")
    off = m["off_high"]
    near_high_thr = -0.12 if profile == "tw" else -0.10  # 與 qualifying_laggards 對齊
    if off is None or off < near_high_thr:
        blocks.append("too_far")
    if profile == "tw":
        structure = bool(m.get("gap_up_hold") or m.get("vol_base_hold"))
    else:  # 美股無真實最低價:結構支撐退回量增或近 5 日轉強
        structure = (m["vol_ratio"] or 0) >= 1.2 or (m["ret5"] is not None and m["ret5"] > 0)
    if not structure:
        blocks.append("no_structure")
    if not blocks:
        blocks.append("capped")  # 全數通過,只是被同產業更高分者或前 20 名上限擠出
    return blocks


def diagnose_universe(prices, metrics, industries, leaders, laggards,
                      exclude=frozenset(), min_price=MIN_PRICE, min_value=MIN_AVG_VALUE,
                      profile="tw"):
    """逐檔產生『查個股』診斷資料,涵蓋所有個股(含被前置過濾者)。
    每筆:分數 + 分項 + 是否在榜 + 未進補漲候選的原因。供報告頁的搜尋框使用。
    profile=tw 用 entry_score;us 用 entry_score_us(無法人/月營收,改價量結構)。"""
    ind_by_name = {i["industry"]: i for i in industries}
    top8 = {i["industry"] for i in industries[:TOP_INDUSTRIES]}
    leader_rank = {m["stock_id"]: r for r, m in enumerate(leaders, 1)}
    lag_rank = {m["stock_id"]: r for r, m in enumerate(laggards, 1)}

    out = []
    for sid, p in prices.items():
        rows = p["rows"]
        rec = {"id": sid, "name": p["name"], "market": p.get("market", "twse")}
        if len(rows) < 21:
            rec["status"] = "insufficient"
            out.append(rec)
            continue
        closes = [r[1] for r in rows]
        vals = [r[4] for r in rows]
        close = closes[-1]
        avg_val20 = sum(vals[-20:]) / 20
        rec["close"] = close
        if close < min_price:
            rec["status"] = "low_price"
            out.append(rec)
            continue
        if avg_val20 < min_value:
            rec["status"] = "illiquid"
            out.append(rec)
            continue

        m = metrics[sid]
        ind = ind_by_name.get(m.get("industry"))
        in_top8 = m.get("industry") in top8
        pct = ind["percentile"] if ind else 0
        if profile == "tw":
            score, parts, _ = entry_score(m, pct)
        else:
            score, parts, _ = entry_score_us(m, pct, ind.get("ret5") if ind else None)
        rec.update({
            "status": "ok", "score": score, "parts": parts,
            "ret20": m["ret20"], "off_high": m["off_high"], "vol_ratio": m["vol_ratio"],
            "industry": m.get("industry"), "ind_ranked": ind is not None, "ind_top8": in_top8,
            "ind_ret20": ind["ret20"] if ind else None,
            "down_gap_open": m.get("down_gap_open"), "false_break": m.get("false_break"),
        })
        if sid in leader_rank:
            rec["on"], rec["rank"] = "leader", leader_rank[sid]
        elif sid in lag_rank:
            rec["on"], rec["rank"] = "candidate", lag_rank[sid]
        else:
            rec["on"] = None
            rec["blocks"] = _lag_blocks(m, ind, in_top8, sid in exclude, profile)
        out.append(rec)
    return out


def find_leaders(industries, exclude=frozenset(), profile="tw"):
    """強勢產業中的領頭羊:接近 60 日新高、表現優於同業。處置股直接排除。

    排序鍵(回測校準):台股用『投信近 5 日買超』(trust_net5,對 20 日續強 IC +0.082)——
    法人挺的領頭羊會續強,而漲最兇的(ret20)反而反轉(IC −0.11)。美股無法人資料,
    退回 ret20。排序也決定 >15 檔時顯示哪 15 檔(法人背書者 vs 最延伸者)。"""
    leaders = []
    for ind in industries[:TOP_INDUSTRIES]:
        for m in ind["members"]:
            if m["stock_id"] in exclude:
                continue
            if m["off_high"] is not None and m["off_high"] >= -0.02 and m["ret20"] > ind["ret20"]:
                leaders.append({**m, "industry_rank": ind["rank"]})
    key = "trust_net5" if profile == "tw" else "ret20"
    leaders.sort(key=lambda x: (x.get(key) or 0), reverse=True)
    return leaders[:15]


def qualifying_laggards(industries, exclude=frozenset(), attention=frozenset(), profile="tw"):
    """強勢進場候選的『完整合格池』(尚未套用產業分散上限與前 20 名截斷)。
    老王式選股:強勢產業 + 趨勢多頭(站上均線) + 接近或突破前高 + 不弱於同業 + 真突破結構支撐。
    tw:結構支撐 = 守住向上跳空缺口 或 守住爆量低點;us(無真實低價)= 量增 或 近 5 日轉正。
    處置股(分盤撮合、交易受限)直接排除;注意股保留但加警示標籤。
    依分數降冪排序回傳;回測權重優化需要看到截斷前的全貌,故與 find_laggards 共用此函式。
    (函式名與資料 key 仍沿用 laggards 以相容呼叫端;語意已於 2026-06-28 改為買強勢突破。)"""
    near_high_thr = -0.12 if profile == "tw" else -0.10
    cands = []
    for ind in industries[:TOP_INDUSTRIES]:
        for m in ind["members"]:
            if m["stock_id"] in exclude:
                continue
            if m["off_high"] is None or m["ret20"] is None:
                continue
            trend_up = m["ma_above"] >= 2                 # 站上至少 2 條均線=趨勢多頭
            near_high = m["off_high"] >= near_high_thr     # 接近或突破 60 日高
            strong = m["ret20"] >= ind["ret20"]            # 不弱於同業中位數
            if profile == "tw":
                structure = bool(m.get("gap_up_hold") or m.get("vol_base_hold"))
            else:  # 美股無真實最低價:結構支撐退回量增或近 5 日轉強
                structure = (m["vol_ratio"] or 0) >= 1.2 or (m["ret5"] is not None and m["ret5"] > 0)
            if trend_up and near_high and strong and structure:
                if profile == "tw":
                    score, parts, reasons = entry_score(m, ind["percentile"])
                else:
                    score, parts, reasons = entry_score_us(m, ind["percentile"], ind.get("ret5"))
                if m["stock_id"] in attention:
                    reasons.insert(0, ("attention",))
                # 老王負向旗標:純警示 tag(本次不當硬性關卡、不影響分數/入選,等回測決定)。
                if m.get("false_break"):
                    reasons.insert(0, ("false_break",))
                if m.get("down_gap_open"):
                    reasons.insert(0, ("down_gap",))
                cands.append({**m, "industry_rank": ind["rank"], "industry_ret20": ind["ret20"],
                              "score": score, "parts": parts, "reasons": reasons})
    cands.sort(key=lambda x: x["score"], reverse=True)
    return cands


def cap_and_limit(cands, profile="tw", limit=20):
    """套用產業分散上限 + 前 N 名截斷。
    資金集中度第①區已呈現,候選清單追求視野全面——最熱產業洗版會蓋掉第 2、3 名
    產業(常是下一棒輪動)的機會。美股只有 11 個 GICS 大類,上限收緊;台股 36 個產業幾乎不觸發。"""
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
    """強勢進場候選:合格池 → 產業分散上限 → 前 20 名。"""
    cands = qualifying_laggards(industries, exclude, attention, profile)
    return cap_and_limit(cands, profile)
