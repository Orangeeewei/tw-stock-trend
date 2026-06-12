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


def cmd_report():
    conn = db.connect()
    prices = db.load_prices(conn)
    inst = db.load_inst(conn)
    taiex = db.load_taiex(conn)
    if not taiex:
        sys.exit("資料庫沒有資料,請先執行 backfill")

    root = os.path.dirname(os.path.abspath(__file__))
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
    metrics = analyze.build_metrics(prices, inst, revenue)
    industries = analyze.build_industries(metrics, prices)
    state = analyze.market_state(taiex)
    leaders = analyze.find_leaders(industries)
    laggards = analyze.find_laggards(industries)

    last_date = taiex[-1][0]
    rev_month = next(iter(revenue.values()))["month"] if revenue else ""
    html = report.render(last_date, state, industries, leaders, laggards, rev_month, prices=prices)

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
    args = ap.parse_args()

    if args.cmd == "backfill":
        cmd_backfill(args.days)
    elif args.cmd == "update":
        cmd_update()
    elif args.cmd == "report":
        cmd_report()
    elif args.cmd == "daily":
        cmd_update()
        cmd_report()


if __name__ == "__main__":
    main()
