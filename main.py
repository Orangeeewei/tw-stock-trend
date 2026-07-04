"""台股趨勢日報 CLI。

  python3 main.py backfill [--days 130]   回補歷史資料
  python3 main.py update                  補抓最近缺漏的交易日
  python3 main.py report                  產生 HTML 報告
  python3 main.py daily                   update + report(給排程用)
"""
import argparse
import json
import os
import sys
import time
from datetime import date, timedelta

import action_config
import adjust
import analyze
import db
import fetch
import locales
import report

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
WIN_DOWNLOADS = "/mnt/c/Users/User/Downloads"
DIVIDENDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "dividends.json")


def _fetch_market(conn, ds, market):
    """抓一個市場一天的行情+法人。回傳 ok / partial / holiday。

    - 法人資料抓不到(未公布或被擋):行情照存,但不標記 fetched,
      下次執行整天重抓補齊 → 籌碼資料不會永久缺漏。
    - 行情明確回空(表格在但 0 列):回 holiday,標記與否交給呼叫端
      (需兩市場互相印證,避免單一來源的異常回應造成永久跳過)。
    """
    if market == "twse":
        q = fetch.fetch_quotes(ds)
        time.sleep(3)
        if q is None:
            return "holiday"
        taiex, quotes = q
        fetch_t86 = fetch.fetch_t86
    else:
        quotes = fetch.fetch_quotes_tpex(ds)
        time.sleep(3)
        if quotes is None:
            # 證交所同日有資料 → 櫃買單邊確定無資料(如 20260220),標記免重查
            if db.has_date(conn, ds, "twse"):
                db.mark_fetched(conn, ds, "tpex")
            return "holiday"
        taiex = None
        fetch_t86 = fetch.fetch_t86_tpex

    try:
        t86 = fetch_t86(ds)
    except fetch.NoDataError:
        t86 = None
    time.sleep(3)
    db.save_day(conn, ds, taiex, quotes, t86, market=market, complete=t86 is not None)
    if t86 is None:
        print(f"{ds} {market} 法人資料未取得,行情已存、下次補抓", flush=True)
        return "partial"
    return "ok"


def cmd_backfill(days):
    conn = db.connect()
    today = date.today()
    fetched = 0
    failures = 0
    for i in range(days, -1, -1):
        d = today - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        ds = d.strftime("%Y%m%d")
        if db.has_date(conn, ds, "holiday"):
            continue
        statuses = []
        for market in ("twse", "tpex"):
            if db.has_date(conn, ds, market):
                statuses.append("skip")
                continue
            # 單日失敗不中斷整批:不標記已抓,下次執行會自動補
            try:
                statuses.append(_fetch_market(conn, ds, market))
            except fetch.NoDataError as e:
                # 轉址回應:可能被暫時擋,也可能無資料;快速跳過,下次再試
                print(f"{d} {market} 跳過({e})", flush=True)
            except Exception as e:
                failures += 1
                print(f"{d} {market} 失敗:{e}", flush=True)
        if "ok" in statuses or "partial" in statuses:
            fetched += 1
            print(f"{d} ok ({fetched})", flush=True)
        elif statuses == ["holiday", "holiday"]:
            # 兩個市場都明確說無資料,才永久標記為非交易日
            db.mark_holiday(conn, ds)
            print(f"{d} 非交易日", flush=True)
        elif "holiday" in statuses:
            print(f"{d} 單邊無資料,暫不標記", flush=True)
    print(f"完成,共更新 {fetched} 個交易日,失敗 {failures} 次", flush=True)
    if failures > 10:
        sys.exit(f"失敗次數過多({failures}),資料可能不完整")


def cmd_update():
    cmd_backfill(10)


ROOT = os.path.dirname(os.path.abspath(__file__))


def _history_dir(market):
    return os.path.join(ROOT, "docs", "history" if market == "tw" else "history-us")


def _iso(ds):
    return f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"


def _truncate(prices, inst, taiex, asof):
    """回傳只含 asof(YYYYMMDD)當天以前資料的視圖,用於歷史快照回推。"""
    p = {sid: {**v, "rows": [r for r in v["rows"] if r[0] <= asof]} for sid, v in prices.items()}
    p = {sid: v for sid, v in p.items() if v["rows"]}
    i = {sid: [r for r in rows if r[0] <= asof] for sid, rows in inst.items()}
    t = [r for r in taiex if r[0] <= asof]
    return p, i, t


def _analyze(prices, inst, index_rows, revenue, exclude=frozenset(), attention=frozenset(), profile="tw"):
    if profile == "us":
        metrics = analyze.build_metrics(prices, inst, revenue, min_price=5, min_value=10_000_000)
    else:
        metrics = analyze.build_metrics(prices, inst, revenue)
    industries = analyze.build_industries(metrics, prices)
    state = analyze.market_state(index_rows)
    leaders = analyze.find_leaders(industries, exclude=exclude, profile=profile)
    laggards = analyze.find_laggards(industries, exclude=exclude, attention=attention, profile=profile)
    return state, industries, leaders, laggards, metrics


def _snapshot(date_iso, industries, leaders, laggards):
    """歷史快照:連續上榜計算與候選回顧的原料。"""
    return {
        "date": date_iso,
        "industries": [x["industry"] for x in industries[:10]],
        "leaders": [x["stock_id"] for x in leaders],
        "laggards": [{"id": x["stock_id"], "name": x["name"], "score": x["score"], "close": x["close"]}
                     for x in laggards],
    }


def _write_snapshot(snap, market="tw"):
    d = _history_dir(market)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{snap['date']}.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False)


def _load_history(before_iso, market="tw"):
    """讀取 before_iso 之前的歷史快照,日期升冪。"""
    d = _history_dir(market)
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        if name.endswith(".json") and name[:-5] < before_iso:
            with open(os.path.join(d, name), encoding="utf-8") as f:
                out.append(json.load(f))
    return out


def _streaks(history, industries, laggards):
    """連續上榜:候選股連幾天在榜、產業連幾天前三(皆含今日)。"""
    for m in laggards:
        n = 0
        for snap in reversed(history):
            if any(x["id"] == m["stock_id"] for x in snap["laggards"]):
                n += 1
            else:
                break
        m["board_streak"] = n + 1  # 含今日

    for ind in industries[:10]:
        if ind["rank"] <= 3:
            n = 0
            for snap in reversed(history):
                if ind["industry"] in snap["industries"][:3]:
                    n += 1
                else:
                    break
            ind["top3_streak"] = n + 1
        else:
            ind["top3_streak"] = None


def _tracking(history, prices, taiex):
    """候選回顧:5/10/20 個交易日前的高分候選,至今表現 vs 大盤。
    『當時收盤』與『最新收盤』兩端點都用今日同一份還原序列查,消除快照當時與今日的
    還原基準不一致(否則候選若在回顧窗內除息,報酬會被低估)。查不到才退回快照存值。"""
    close_by_date = {sid: {r[0]: r[1] for r in v["rows"]} for sid, v in prices.items()}
    last_close = {sid: v["rows"][-1][1] for sid, v in prices.items()}
    name_by_id = {sid: v["name"] for sid, v in prices.items()}
    taiex_by_date = {_iso(d): c for d, c in taiex}
    taiex_now = taiex[-1][1]
    snap_by_date = {s["date"]: s for s in history}
    dates = sorted(snap_by_date)

    def _norm(x):
        """快照 picks 可能是 dict(補漲:含 score/close)或 id 字串(領頭羊:僅 id)。"""
        if isinstance(x, dict):
            return x["id"], x.get("name", ""), x.get("score")
        return x, name_by_id.get(x, ""), None

    def track(pick_fn, kind):
        out = []
        for lb in (5, 10, 20):
            if len(dates) < lb:
                continue
            d = dates[-lb]
            snap = snap_by_date[d]
            d_ymd = d.replace("-", "")
            rows = []
            for x in pick_fn(snap):
                sid, name, score = _norm(x)
                cur = last_close.get(sid)
                base = close_by_date.get(sid, {}).get(d_ymd)
                if cur and base:
                    rows.append({"id": sid, "name": name, "score": score,
                                 "close": base, "cur": cur, "ret": cur / base - 1})
            if not rows:
                continue
            t0 = taiex_by_date.get(d)
            out.append({"days": lb, "date": d, "rows": rows, "kind": kind,
                        "avg_ret": sum(r["ret"] for r in rows) / len(rows),
                        "taiex_ret": taiex_now / t0 - 1 if t0 else None})
        return out

    lag_pick = lambda s: ([x for x in s["laggards"] if x["score"] >= 70][:5] or s["laggards"][:3])
    lead_pick = lambda s: s.get("leaders", [])[:5]
    return track(lag_pick, "laggard") + track(lead_pick, "leader")


def _us_universe():
    """S&P 500 成分股(快取於 data/sp500.json,抓取失敗時退回快取)。"""
    cache = os.path.join(ROOT, "data", "sp500.json")
    try:
        uni = fetch.fetch_sp500()
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(uni, f)
    except Exception as e:
        if not os.path.exists(cache):
            raise
        print(f"成分股清單抓取失敗({e}),改用快取", flush=True)
        with open(cache, encoding="utf-8") as f:
            uni = json.load(f)
    return uni


def _accumulate_revenue_history(revenue):
    """把本次月營收併入 data/revenue_history.json {month:{sid:{yoy,mom,industry,name}}}。
    供回測做 point-in-time 營收(只用當時已公布月份);月更,平日多為同月覆寫。"""
    path = os.path.join(ROOT, "data", "revenue_history.json")
    hist = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            hist = json.load(f)
    for sid, v in revenue.items():
        m = v.get("month")
        if not m:
            continue
        hist.setdefault(m, {})[sid] = {"yoy": v.get("yoy"), "mom": v.get("mom"),
                                       "industry": v.get("industry"), "name": v.get("name")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False)


def _load_names_en():
    """上市公司英文簡稱 + 產業別,失敗退回快取。回傳 ({sid: 英文簡稱}, {sid: 產業別})。
    快取存完整形狀 {sid:{en,industry}};相容舊格式 {sid: 英文字串}。"""
    cache = os.path.join(ROOT, "data", "names_en.json")
    full = None
    try:
        full = fetch.fetch_names_en()
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(full, f, ensure_ascii=False)
    except Exception as e:
        if os.path.exists(cache):
            print(f"英文簡稱/產業抓取失敗({e}),改用快取", flush=True)
            with open(cache, encoding="utf-8") as f:
                full = json.load(f)
    if not full:
        return {}, {}
    names_en, industry_map = {}, {}
    for sid, v in full.items():
        if isinstance(v, str):           # 舊格式:只有英文簡稱
            if v:
                names_en[sid] = v
            continue
        if v.get("en"):
            names_en[sid] = v["en"]
        if v.get("industry"):
            industry_map[sid] = v["industry"]
    return names_en, industry_map


def _us_sector_dict(universe):
    """把 GICS sector 塞進 revenue 形狀的 dict,讓分析引擎共用(美股無月營收)。"""
    return {u["symbol"]: {"name": u["name"], "industry": u["sector"],
                          "yoy": None, "mom": None, "month": ""} for u in universe}


def _accumulate_sp500_history(universe, iso):
    """每日記錄當天 S&P 500 成分股 → data/sp500_history.json {date:[symbols]}。
    免費資料源只有『當前』成分,直接拿來回測會有存活者偏誤(被剔除者消失、新進者帶滿歷史)。
    從現在起累積每日成分,未來美股回測可改用『當時成分』做 point-in-time,逐步消除偏誤。"""
    path = os.path.join(ROOT, "data", "sp500_history.json")
    hist = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            hist = json.load(f)
    hist[iso] = sorted(u["symbol"] for u in universe)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False)


def cmd_history_backfill(market="tw"):
    """用既有資料庫回推每個交易日的候選快照(一次性;台股營收以現有月份近似)。"""
    conn = db.connect()
    if market == "tw":
        prices = db.load_prices(conn)
        inst = db.load_inst(conn)
        index_rows = db.load_taiex(conn)
        with open(os.path.join(ROOT, "data", "revenue_cache.json"), encoding="utf-8") as f:
            revenue = json.load(f)
        dividends = adjust.load_dividends(DIVIDENDS_PATH)
        profile = "tw"
    else:
        prices = db.load_prices(conn, markets=("us",))
        inst = {}
        index_rows = db.load_us_index(conn)
        revenue = _us_sector_dict(_us_universe())
        dividends = {}            # 美股價已由 Yahoo 還原
        profile = "us"
    hist_dir = _history_dir(market)
    dates = [d for d, _ in index_rows]
    done = 0
    for ds in dates[21:]:  # 至少要 21 天資料才能算 20 日漲跌
        iso = _iso(ds)
        if os.path.exists(os.path.join(hist_dir, f"{iso}.json")):
            continue
        p, i, t = _truncate(prices, inst, index_rows, ds)
        p = adjust.adjust_prices(p, dividends, asof=ds)   # point-in-time 還原
        _, industries, leaders, laggards, _ = _analyze(p, i, t, revenue, profile=profile)
        _write_snapshot(_snapshot(iso, industries, leaders, laggards), market)
        done += 1
        print(f"{iso} 快照完成 ({done})", flush=True)
    print(f"歷史快照回推完成,共 {done} 天", flush=True)


def cmd_us_update():
    """更新 S&P 500 全部成分股 + 指數。Yahoo 每次給 3 個月視窗,缺漏自動補齊。"""
    conn = db.connect()
    idx = fetch.fetch_us_index()
    if idx:
        db.save_us_index(conn, idx)
    latest = idx[-1][0] if idx else None
    universe = _us_universe()
    have = {sid: v["rows"][-1][0] for sid, v in db.load_prices(conn, markets=("us",)).items()}
    done = failures = skipped = 0
    for u in universe:
        sym = u["symbol"]
        if latest and have.get(sym) == latest:
            skipped += 1
            continue
        try:
            rows = fetch.fetch_us_chart(sym)
            if rows:
                db.upsert_us(conn, sym, u["name"], rows)
                done += 1
        except Exception as e:
            failures += 1
            print(f"{sym} 失敗:{e}", flush=True)
        time.sleep(0.25)
        if done and done % 100 == 0:
            print(f"...{done} 檔完成", flush=True)
    print(f"美股更新完成:{done} 檔更新、{skipped} 檔已最新、{failures} 檔失敗", flush=True)
    if failures > 50:
        sys.exit(f"失敗過多({failures}),Yahoo 可能在限流")


def _backtest_summary():
    """跑進場分數回測,回傳報告用的精簡 dict;任何失敗都回 None,絕不讓報告開天窗。"""
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import backtest as bt_mod
        # 只計大盤多頭日:回測顯示策略在空頭時優勢消失,報告數字以實際會出手的情境為準
        bt = bt_mod.run(regime="bull")
        h = bt["horizons"].get(20) if bt else None
        if not h or not h.get("buckets"):
            return None
        return {
            "horizon": 20,
            "regime": bt.get("regime"),
            "range": bt.get("range"),
            "eval_days": bt.get("eval_days"),
            "hit_rate": h["hit_rate"],
            "mean_excess": h["mean_excess"],
            "buckets": [{"lo": b["lo"], "hi": b["hi"], "n": b["n"],
                         "hit_rate": b["hit_rate"], "mean_excess": b["mean_excess"]}
                        for b in h["buckets"]],
            "attribution": [{"dim": d["dim"], "spread": d["spread"], "mean_hi": d["mean_hi"]}
                            for d in (bt.get("attribution") or {}).get("dims", [])],
        }
    except Exception as e:
        print(f"回測計算失敗,報告略過回測區({e})", flush=True)
        return None


def _load_legacy():
    """載入舊補漲引擎(scripts/legacy_analyze.py):⓪ 每日行動清單的主引擎。
    回測裁決(LEGACY_COMPARE.md 2026-07-04):test 段唯一正期望且樣本足的組合是
    舊補漲 >=60 / bull / 抱滿 20 日,現行買強引擎降為第二視角(③ 區照舊)。"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import legacy_analyze
    return legacy_analyze


def _action_state(state):
    """行動清單的大盤一句話狀態:bull(可進場)/ repair(空頭但止跌試探)/ bear / nodata。"""
    if state["bull"] is True:
        return "bull"
    if state["bull"] is False:
        return "repair" if state.get("repair") else "bear"
    return "nodata"


def _breakout60(rows, window=60):
    """還原收盤是否突破「前 window 日收盤最高」(不含當日)——F2 嚴選訊號的價格條件。"""
    closes = [r[1] for r in rows]
    return len(closes) >= window + 1 and closes[-1] > max(closes[-window - 1:-1])


def _strong_picks(metrics, prices_adj, exclude):
    """⓪ 嚴選(F2):還原收盤突破前60日高(不含當日)+ 投信連買>=2 + 非處置。
    掃全 metrics(過流動性門檻的個股),不限前8強產業;依投信連買天數、5日買超排序。
    註:回測 universe 為全上市櫃 1990 檔,報告端沿用 build_metrics 流動性門檻(略嚴、偏安全)。"""
    rule = action_config.CONFIG["strong_rule"]
    out = []
    for sid, m in metrics.items():
        if sid in exclude or m["trust_streak"] < rule["trust_streak_min"]:
            continue
        p = prices_adj.get(sid)
        if not p or not _breakout60(p["rows"], rule["breakout_window"]):
            continue
        out.append(m)
    out.sort(key=lambda m: (m["trust_streak"], m["trust_net5"]), reverse=True)
    return out


def _limit_radar(raw_rows, adj_rows):
    """漲停雷達(F6b):回傳今日命中的最高倍數徽章 key(lock/breakout/vol_surge)或 None。
    - lock:原始價漲幅 >= 9.3% 且收在最高(鎖死),且前一日非漲停(首板)。
      必須用未還原原始價:還原價會扭曲漲停幅度。
    - breakout:還原收盤突破前 60 日收盤高(同嚴選價格條件)。
    - vol_surge:今日量 >= 20日均量 3 倍且原始漲幅 > 4%,且前期安靜——本實作定義
      「前期安靜」= 前 5 日均量 <= 前 20 日均量(皆不含今日),即量能此前未動。"""
    badges = []
    # rows: (date, close, high, vol, val, low)
    if len(raw_rows) >= 3:
        c0, c1, c2 = raw_rows[-1][1], raw_rows[-2][1], raw_rows[-3][1]
        gain = c0 / c1 - 1 if c1 else 0
        locked = c0 >= raw_rows[-1][2] - 1e-9
        prev_limit = bool(c2) and c1 / c2 - 1 >= 0.093
        if gain >= 0.093 and locked and not prev_limit:
            badges.append("lock")
    if _breakout60(adj_rows):
        badges.append("breakout")
    if len(raw_rows) >= 21:
        vols = [r[3] for r in raw_rows]
        v20 = sum(vols[-21:-1]) / 20
        v5 = sum(vols[-6:-1]) / 5
        c0, c1 = raw_rows[-1][1], raw_rows[-2][1]
        if v20 and c1 and vols[-1] >= 3 * v20 and c0 / c1 - 1 > 0.04 and v5 <= v20:
            badges.append("vol_surge")
    if not badges:
        return None
    lifts = action_config.CONFIG["limit_radar"]
    return max(badges, key=lambda b: lifts[b])


def _build_action_tw(state, metrics, prices_adj, prices_raw, legacy_cands, exclude, hitrate=None):
    """台股 ⓪ 行動清單:參數與績效數字全部來自 action_config.CONFIG(再定案只改那檔)。
    嚴選 = F2 突破前60日高+投信連買>=2(STRATEGY_SEARCH.md:train/test 皆正的唯一預註冊規則);
    平衡 = 舊補漲引擎 score>=floor(test 正、train 負,盤勢依賴,報告端必附警語)。
    兩級去重(嚴選優先);只在大盤多頭出清單;各股附漲停雷達徽章。"""
    cfg = action_config.CONFIG
    st = _action_state(state)
    strong, balanced = [], []
    if st == "bull":
        strong = _strong_picks(metrics, prices_adj, exclude)[:cfg["strong_rule"]["max_rows"]]
        sids = {m["stock_id"] for m in strong}
        pool = [c for c in legacy_cands if c["score"] >= cfg["floor"] and c["stock_id"] not in sids]
        key = lambda c: ((c.get(cfg["sort"]) or 0) > 0, c.get(cfg["sort"]) or 0, c["score"])
        balanced = sorted(pool, key=key, reverse=True)
        for m in strong + balanced:
            raw, adj = prices_raw.get(m["stock_id"]), prices_adj.get(m["stock_id"])
            m["radar"] = _limit_radar(raw["rows"], adj["rows"]) if raw and adj else None
    return {"state": st, "engine": "f2+legacy", "strong": strong, "balanced": balanced,
            "hold_days": cfg["hold_days"], "stats": cfg["stats"], "radar": cfg["limit_radar"],
            "test_range": cfg["test_range"], "hitrate": hitrate}


def _build_action_us(state, laggards):
    """美股 ⓪ 行動清單:沿用現行買強引擎 score>=75(legacy 補漲引擎為台股專屬)。
    報告端會附現行引擎的已知回測註記(test 段負超額)以示誠實。"""
    cfg = action_config.CONFIG
    st = _action_state(state)
    strong = [c for c in laggards if c["score"] >= 75] if st == "bull" else []
    return {"state": st, "engine": "current", "strong": strong, "balanced": [],
            "hold_days": cfg["hold_days"], "stats": cfg["stats"], "radar": None,
            "test_range": cfg["test_range"], "hitrate": None}


def _engine_hitrate(prices_raw, prices_adj, inst, taiex, dividends, floor=60, horizon=20, window=60):
    """雙引擎近 window 個交易日的 20 日滾動命中率(方案A:報告產生時 PIT 重算)。
    對 D−(window+horizon)..D−(horizon+1) 每個評估日,用只含 <=D 的資料重建兩引擎合格候選
    (legacy>=floor、current>=floor;與行動清單一致只計大盤多頭日),前瞻報酬用今日還原
    序列結算(base/fwd 同基準,同 _tracking 的理由)。實測單日約 0.33s、60 日約 20s。
    哪個引擎近期命中率高 = 目前盤勢性格較適合哪套邏輯(regime 切換偵測)。"""
    legacy = _load_legacy()
    try:
        import backtest as bt_mod          # scripts/ 已在 _load_legacy 加入 sys.path
        rev_build, _ = bt_mod._pit_revenue_builder()
    except Exception as e:
        print(f"PIT 營收 builder 失敗,命中率改用當前營收快照({e})", flush=True)
        with open(os.path.join(ROOT, "data", "revenue_cache.json"), encoding="utf-8") as f:
            _rev = json.load(f)
        rev_build = lambda D: _rev
    cal = [d for d, _ in taiex]
    if len(cal) < horizon + 2:
        return None
    window = min(window, len(cal) - horizon - 1)
    tx_close = {d: c for d, c in taiex}
    close_by = {sid: {r[0]: r[1] for r in v["rows"]} for sid, v in prices_adj.items()}
    rule = action_config.CONFIG["strong_rule"]
    stats = {"legacy": [0, 0], "current": [0, 0], "strong": [0, 0]}   # [命中, 樣本]
    eval_days = 0
    for i in range(len(cal) - horizon - window, len(cal) - horizon):
        D, D1 = cal[i], cal[i + horizon]
        p, ins, tx = _truncate(prices_raw, inst, taiex, D)
        p = adjust.adjust_prices(p, dividends, asof=D)
        state, industries, _, cur_lags, mets = _analyze(p, ins, tx, rev_build(D))
        if state["bull"] is not True:
            continue
        eval_days += 1
        mret = tx_close[D1] / tx_close[D] - 1
        lg = legacy.find_laggards(industries, profile="tw")
        picks = {"legacy": [c["stock_id"] for c in lg if c["score"] >= floor],
                 "current": [c["stock_id"] for c in cur_lags if c["score"] >= floor],
                 # 嚴選規則(F2)一併回放:突破前60日高(PIT 還原)+ 投信連買
                 "strong": [sid for sid, mm in mets.items()
                            if mm["trust_streak"] >= rule["trust_streak_min"]
                            and sid in p and _breakout60(p[sid]["rows"], rule["breakout_window"])]}
        for eng, sids in picks.items():
            for sid in sids:
                cb = close_by.get(sid, {})
                base, fwd = cb.get(D), cb.get(D1)
                if base and fwd:
                    stats[eng][1] += 1
                    if fwd / base - 1 - mret > 0:
                        stats[eng][0] += 1

    def _pack(eng):
        hit, n = stats[eng]
        return {"hit": hit / n if n else None, "n": n}
    return {"days": eval_days, "window": window, "horizon": horizon,
            "legacy": _pack("legacy"), "current": _pack("current"), "strong": _pack("strong")}


def cmd_report():
    conn = db.connect()
    prices = db.load_prices(conn)
    inst = db.load_inst(conn)
    taiex = db.load_taiex(conn)
    if not taiex:
        sys.exit("資料庫沒有資料,請先執行 backfill")

    # 除權息向後還原:刷新事件種子後還原到「最新資料日」,之後所有分析都用還原價,
    # 避免除權息造成的假跌幅把正常股誤判成低基期補漲候選(Q3 除息旺季尤其關鍵)。
    # ⚠️ asof 必須是最新交易日而非 None:dividends.json 含 TPEX prepost 的『未來』除息事件,
    #    asof=None 會把尚未發生的除息提前套到現價,反而製造假低基期候選。
    dividends = adjust.refresh_dividends(prices, DIVIDENDS_PATH)
    prices_raw = prices   # 未還原原始價:⓪ 滾動命中率的 PIT 重算要逐日 asof=D 還原,不能用下行的視圖
    prices = adjust.adjust_prices(prices, dividends, asof=taiex[-1][0])

    root = ROOT
    rev_cache = os.path.join(root, "data", "revenue_cache.json")
    try:
        revenue = fetch.fetch_revenue()
        with open(rev_cache, "w", encoding="utf-8") as f:
            json.dump(revenue, f, ensure_ascii=False)
    except Exception as e:
        # 營收 API 暫時失敗不該讓整份報告開天窗:退回上次成功的快取
        if not os.path.exists(rev_cache):
            raise
        print(f"營收抓取失敗({e}),改用上次快取", flush=True)
        with open(rev_cache, encoding="utf-8") as f:
            revenue = json.load(f)

    _accumulate_revenue_history(revenue)  # 向前累積月營收,供未來 point-in-time 回測

    # 上市公司英文簡稱 + 產業別(失敗退回快取)。產業別供「無月營收個股」的 fallback,
    # 否則它們 industry=None 會被永久排除在產業排名/候選之外。
    names_en, industry_map = _load_names_en()
    for sid, ind in industry_map.items():
        if ind and sid not in revenue:
            revenue[sid] = {"name": "", "industry": ind, "yoy": None, "mom": None, "month": ""}

    disposal, attention = fetch.fetch_risk_lists(date.today())
    if disposal or attention:
        print(f"風險清單:處置 {len(disposal)} 檔、注意 {len(attention)} 檔", flush=True)

    state, industries, leaders, laggards, metrics = _analyze(
        prices, inst, taiex, revenue, exclude=disposal, attention=attention)
    lookup = analyze.diagnose_universe(prices, metrics, industries, leaders, laggards, exclude=disposal)

    # 月營收亮點:年增 30~300% 且月增>0(持續成長)、流動性足、排除處置股,依年增降冪前 12。
    # 上限 300% 是為了濾掉建設/工程認列大案造成的基期失真(動輒上千 %、不具參考意義)。
    rev_stars = sorted(
        (m for m in metrics.values()
         if m.get("rev_yoy") is not None and 30 <= m["rev_yoy"] <= 300
         and m.get("rev_mom") is not None and m["rev_mom"] > 0
         and m["stock_id"] not in disposal),
        key=lambda m: m["rev_yoy"], reverse=True)[:12]

    last_date = taiex[-1][0]
    today_iso = _iso(last_date)
    history = _load_history(today_iso)
    _streaks(history, industries, laggards)
    tracking = _tracking(history, prices, taiex)
    _write_snapshot(_snapshot(today_iso, industries, leaders, laggards))

    rev_month = next((v["month"] for v in revenue.values() if v.get("month")), "")
    bt = _backtest_summary()

    # ⓪ 每日行動清單:對同一份 PIT metrics(industries)以舊補漲引擎跑第二組候選。
    # 不動上面 analyze 買強候選的計算與顯示(③ 區照舊),兩引擎並存、互為對照。
    legacy_cands = []
    try:
        legacy_cands = _load_legacy().find_laggards(
            industries, exclude=disposal, attention=attention, profile="tw")
    except Exception as e:
        print(f"行動清單引擎失敗,⓪ 區降級為空清單({e})", flush=True)
    hitrate = None
    try:
        t0 = time.time()
        hitrate = _engine_hitrate(prices_raw, prices, inst, taiex, dividends)
        print(f"雙引擎滾動命中率計算完成:{time.time() - t0:.1f}s", flush=True)
    except Exception as e:
        print(f"滾動命中率計算失敗,報告略過該小表({e})", flush=True)
    action = _build_action_tw(state, metrics, prices, prices_raw, legacy_cands, disposal, hitrate)

    html_zh = report.render(last_date, state, industries, leaders, laggards, rev_month,
                            prices=prices, tracking=tracking, market="tw", lang="zh",
                            lang_href="en.html", other_href="us/", lookup=lookup, backtest=bt,
                            rev_stars=rev_stars, action=action)
    html_en = report.render(last_date, state, industries, leaders, laggards, rev_month,
                            prices=prices, tracking=tracking, market="tw", lang="en",
                            lang_href="index.html", other_href="us/", names_en=names_en, lookup=lookup,
                            backtest=bt, rev_stars=rev_stars, action=action)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    iso = _iso(last_date)
    path = os.path.join(REPORTS_DIR, f"{iso}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_zh)
    with open(os.path.join(REPORTS_DIR, "latest.html"), "w", encoding="utf-8") as f:
        f.write(html_zh)
    print(path)

    if os.path.isdir(WIN_DOWNLOADS):
        win_path = os.path.join(WIN_DOWNLOADS, f"台股趨勢日報_{iso}.html")
        with open(win_path, "w", encoding="utf-8") as f:
            f.write(html_zh)
        print(win_path)

    # GitHub Pages 輸出:docs/index.html(中)+ docs/en.html(英)+ 歷史報告與摘要
    docs = os.path.join(ROOT, "docs")
    os.makedirs(os.path.join(docs, "reports"), exist_ok=True)
    for p, content in ((os.path.join(docs, "index.html"), html_zh),
                       (os.path.join(docs, "en.html"), html_en),
                       (os.path.join(docs, "reports", f"{iso}.html"), html_zh)):
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    _write_summary(docs, "summary.json", iso, state, industries, leaders, laggards, lang="zh",
                   action=action)
    print(os.path.join(docs, "index.html"))


def _write_summary(docs, fname, iso, state, industries, leaders, laggards, lang, min_score=60,
                   action=None):
    summary = {
        "date": iso,
        "market": {"bull": state["bull"], "close": state["close"], "ma60": state.get("ma60")},
        "industries": [{"industry": x["industry"], "ret20": x["ret20"]} for x in industries[:5]],
        "leaders": [{"id": x["stock_id"], "name": x["name"], "ret20": x["ret20"]} for x in leaders[:5]],
        # 只摘要達門檻的候選:summary.json 餵 Discord,不把弱訊號股推給使用者(台股≥60、美股≥75)
        "laggards": [{"id": x["stock_id"], "name": x["name"], "score": x["score"],
                      "close": x["close"], "industry": x["industry"],
                      "reasons": [locales.fmt_reason(lang, r) for r in x["reasons"]]}
                     for x in laggards if x["score"] >= min_score][:8],
    }
    if action is not None:
        # ⓪ 行動清單摘要:餵 Discord 開頭區塊(嚴選前 5 + 大盤狀態 + 歷史勝率數字)。
        # 嚴選(F2)非分數制,score 可為 None;radar = 漲停雷達徽章 key。
        def _pick(xs):
            return [{"id": x["stock_id"], "name": x["name"], "score": x.get("score"),
                     "close": x["close"], "trust_net5": x.get("trust_net5", 0),
                     "trust_streak": x.get("trust_streak", 0), "radar": x.get("radar")}
                    for x in xs[:8]]
        summary["action"] = {"state": action["state"], "engine": action["engine"],
                             "hold_days": action["hold_days"], "test_range": action["test_range"],
                             "strong": _pick(action["strong"]), "balanced": _pick(action["balanced"]),
                             "stats": action["stats"], "radar": action.get("radar"),
                             "plans": {"A": action["stats"]["strong"],
                                       "B": action["stats"]["strong_planB"]}}
    with open(os.path.join(docs, fname), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)


def cmd_us_report():
    conn = db.connect()
    prices = db.load_prices(conn, markets=("us",))
    index_rows = db.load_us_index(conn)
    if not index_rows or not prices:
        sys.exit("沒有美股資料,請先執行 us-update")

    universe = _us_universe()
    sector = _us_sector_dict(universe)
    state, industries, leaders, laggards, metrics = _analyze(
        prices, {}, index_rows, sector, profile="us")
    lookup = analyze.diagnose_universe(prices, metrics, industries, leaders, laggards,
                                       min_price=5, min_value=10_000_000, profile="us")

    last_date = index_rows[-1][0]
    today_iso = _iso(last_date)
    _accumulate_sp500_history(universe, today_iso)  # 累積成分股,供未來 PIT 美股回測
    history = _load_history(today_iso, market="us")
    _streaks(history, industries, laggards)
    tracking = _tracking(history, prices, index_rows)
    _write_snapshot(_snapshot(today_iso, industries, leaders, laggards), market="us")

    # ⓪ 美股行動清單:沿用現行買強引擎 score>=75(legacy 補漲引擎為台股專屬,不跑美股)
    action = _build_action_us(state, laggards)

    html_en = report.render(last_date, state, industries, leaders, laggards, "",
                            prices=prices, tracking=tracking, market="us", lang="en",
                            lang_href="zh.html", other_href="../en.html", lookup=lookup, action=action)
    html_zh = report.render(last_date, state, industries, leaders, laggards, "",
                            prices=prices, tracking=tracking, market="us", lang="zh",
                            lang_href="index.html", other_href="../", lookup=lookup, action=action)

    docs_us = os.path.join(ROOT, "docs", "us")
    os.makedirs(os.path.join(docs_us, "reports"), exist_ok=True)
    for p, content in ((os.path.join(docs_us, "index.html"), html_en),
                       (os.path.join(docs_us, "zh.html"), html_zh),
                       (os.path.join(docs_us, "reports", f"{today_iso}.html"), html_en)):
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
    _write_summary(docs_us, "summary.json", today_iso, state, industries, leaders, laggards, lang="en",
                   min_score=75, action=action)
    print(os.path.join(docs_us, "index.html"))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_back = sub.add_parser("backfill")
    p_back.add_argument("--days", type=int, default=130)
    sub.add_parser("update")
    sub.add_parser("report")
    sub.add_parser("daily")
    p_hist = sub.add_parser("history-backfill")
    p_hist.add_argument("--market", choices=("tw", "us"), default="tw")
    sub.add_parser("us-update")
    sub.add_parser("us-report")
    sub.add_parser("us-daily")
    args = ap.parse_args()

    if args.cmd == "backfill":
        cmd_backfill(args.days)
    elif args.cmd == "history-backfill":
        cmd_history_backfill(args.market)
    elif args.cmd == "update":
        cmd_update()
    elif args.cmd == "report":
        cmd_report()
    elif args.cmd == "daily":
        cmd_update()
        cmd_report()
    elif args.cmd == "us-update":
        cmd_us_update()
    elif args.cmd == "us-report":
        cmd_us_report()
    elif args.cmd == "us-daily":
        cmd_us_update()
        cmd_us_report()


if __name__ == "__main__":
    main()
