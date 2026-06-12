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

import analyze
import db
import fetch
import report

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
WIN_DOWNLOADS = "/mnt/c/Users/User/Downloads"


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
HISTORY_DIR = os.path.join(ROOT, "docs", "history")


def _iso(ds):
    return f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"


def _truncate(prices, inst, taiex, asof):
    """回傳只含 asof(YYYYMMDD)當天以前資料的視圖,用於歷史快照回推。"""
    p = {sid: {**v, "rows": [r for r in v["rows"] if r[0] <= asof]} for sid, v in prices.items()}
    p = {sid: v for sid, v in p.items() if v["rows"]}
    i = {sid: [r for r in rows if r[0] <= asof] for sid, rows in inst.items()}
    t = [r for r in taiex if r[0] <= asof]
    return p, i, t


def _analyze(prices, inst, taiex, revenue, exclude=frozenset(), attention=frozenset()):
    metrics = analyze.build_metrics(prices, inst, revenue)
    industries = analyze.build_industries(metrics, prices)
    state = analyze.market_state(taiex)
    leaders = analyze.find_leaders(industries, exclude=exclude)
    laggards = analyze.find_laggards(industries, exclude=exclude, attention=attention)
    return state, industries, leaders, laggards


def _snapshot(date_iso, industries, leaders, laggards):
    """歷史快照:連續上榜計算與候選回顧的原料。"""
    return {
        "date": date_iso,
        "industries": [x["industry"] for x in industries[:10]],
        "leaders": [x["stock_id"] for x in leaders],
        "laggards": [{"id": x["stock_id"], "name": x["name"], "score": x["score"], "close": x["close"]}
                     for x in laggards],
    }


def _write_snapshot(snap):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    with open(os.path.join(HISTORY_DIR, f"{snap['date']}.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False)


def _load_history(before_iso):
    """讀取 before_iso 之前的歷史快照,日期升冪。"""
    if not os.path.isdir(HISTORY_DIR):
        return []
    out = []
    for name in sorted(os.listdir(HISTORY_DIR)):
        if name.endswith(".json") and name[:-5] < before_iso:
            with open(os.path.join(HISTORY_DIR, name), encoding="utf-8") as f:
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
    """候選回顧:5/10/20 個交易日前的高分候選,至今表現 vs 大盤。"""
    last_close = {sid: v["rows"][-1][1] for sid, v in prices.items()}
    taiex_by_date = {_iso(d): c for d, c in taiex}
    taiex_now = taiex[-1][1]
    snap_by_date = {s["date"]: s for s in history}
    dates = sorted(snap_by_date)
    out = []
    for lb in (5, 10, 20):
        if len(dates) < lb:
            continue
        d = dates[-lb]
        snap = snap_by_date[d]
        picks = [x for x in snap["laggards"] if x["score"] >= 70][:5] or snap["laggards"][:3]
        rows = []
        for x in picks:
            cur = last_close.get(x["id"])
            if cur and x["close"]:
                rows.append({**x, "cur": cur, "ret": cur / x["close"] - 1})
        if not rows:
            continue
        t0 = taiex_by_date.get(d)
        out.append({
            "days": lb, "date": d, "rows": rows,
            "avg_ret": sum(r["ret"] for r in rows) / len(rows),
            "taiex_ret": taiex_now / t0 - 1 if t0 else None,
        })
    return out


def cmd_history_backfill():
    """用既有資料庫回推每個交易日的候選快照(一次性;營收以現有月份近似)。"""
    conn = db.connect()
    prices = db.load_prices(conn)
    inst = db.load_inst(conn)
    taiex = db.load_taiex(conn)
    with open(os.path.join(ROOT, "data", "revenue_cache.json"), encoding="utf-8") as f:
        revenue = json.load(f)
    dates = [d for d, _ in taiex]
    done = 0
    for ds in dates[21:]:  # 至少要 21 天資料才能算 20 日漲跌
        iso = _iso(ds)
        if os.path.exists(os.path.join(HISTORY_DIR, f"{iso}.json")):
            continue
        p, i, t = _truncate(prices, inst, taiex, ds)
        _, industries, leaders, laggards = _analyze(p, i, t, revenue)
        _write_snapshot(_snapshot(iso, industries, leaders, laggards))
        done += 1
        print(f"{iso} 快照完成 ({done})", flush=True)
    print(f"歷史快照回推完成,共 {done} 天", flush=True)


def cmd_report():
    conn = db.connect()
    prices = db.load_prices(conn)
    inst = db.load_inst(conn)
    taiex = db.load_taiex(conn)
    if not taiex:
        sys.exit("資料庫沒有資料,請先執行 backfill")

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

    disposal, attention = fetch.fetch_risk_lists(date.today())
    if disposal or attention:
        print(f"風險清單:處置 {len(disposal)} 檔、注意 {len(attention)} 檔", flush=True)

    state, industries, leaders, laggards = _analyze(
        prices, inst, taiex, revenue, exclude=disposal, attention=attention)

    last_date = taiex[-1][0]
    today_iso = _iso(last_date)
    history = _load_history(today_iso)
    _streaks(history, industries, laggards)
    tracking = _tracking(history, prices, taiex)
    _write_snapshot(_snapshot(today_iso, industries, leaders, laggards))
    rev_month = next(iter(revenue.values()))["month"] if revenue else ""
    html = report.render(last_date, state, industries, leaders, laggards, rev_month,
                         prices=prices, tracking=tracking)

    os.makedirs(REPORTS_DIR, exist_ok=True)
    iso = f"{last_date[:4]}-{last_date[4:6]}-{last_date[6:]}"
    path = os.path.join(REPORTS_DIR, f"{iso}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    latest = os.path.join(REPORTS_DIR, "latest.html")
    with open(latest, "w", encoding="utf-8") as f:
        f.write(html)
    print(path)

    if os.path.isdir(WIN_DOWNLOADS):
        win_path = os.path.join(WIN_DOWNLOADS, f"台股趨勢日報_{iso}.html")
        with open(win_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(win_path)

    # GitHub Pages 輸出:docs/index.html 永遠是最新報告,歷史報告與摘要一併保存
    root = os.path.dirname(os.path.abspath(__file__))
    docs = os.path.join(root, "docs")
    os.makedirs(os.path.join(docs, "reports"), exist_ok=True)
    for p in (os.path.join(docs, "index.html"), os.path.join(docs, "reports", f"{iso}.html")):
        with open(p, "w", encoding="utf-8") as f:
            f.write(html)

    summary = {
        "date": iso,
        "market": {"bull": state["bull"], "close": state["close"], "ma60": state.get("ma60")},
        "industries": [{"industry": x["industry"], "ret20": x["ret20"]} for x in industries[:5]],
        "leaders": [{"id": x["stock_id"], "name": x["name"], "ret20": x["ret20"]} for x in leaders[:5]],
        "laggards": [{"id": x["stock_id"], "name": x["name"], "score": x["score"],
                      "close": x["close"], "industry": x["industry"], "reasons": x["reasons"]}
                     for x in laggards[:8]],
    }
    with open(os.path.join(docs, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(os.path.join(docs, "index.html"))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_back = sub.add_parser("backfill")
    p_back.add_argument("--days", type=int, default=130)
    sub.add_parser("update")
    sub.add_parser("report")
    sub.add_parser("daily")
    sub.add_parser("history-backfill")
    args = ap.parse_args()

    if args.cmd == "backfill":
        cmd_backfill(args.days)
    elif args.cmd == "history-backfill":
        cmd_history_backfill()
    elif args.cmd == "update":
        cmd_update()
    elif args.cmd == "report":
        cmd_report()
    elif args.cmd == "daily":
        cmd_update()
        cmd_report()


if __name__ == "__main__":
    main()
