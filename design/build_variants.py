"""用今天的真實資料,把三套主題各 render 成一份完整報告,供 Claude Design 比較。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyze
import db
import fetch
import report
from themes import THEMES

OUT_DIR = os.path.join(ROOT, "design", "build")


def main():
    conn = db.connect()
    prices = db.load_prices(conn)
    inst = db.load_inst(conn)
    taiex = db.load_taiex(conn)
    revenue = fetch.fetch_revenue()
    metrics = analyze.build_metrics(prices, inst, revenue)
    industries = analyze.build_industries(metrics, prices)
    state = analyze.market_state(taiex)
    leaders = analyze.find_leaders(industries)
    laggards = analyze.find_laggards(industries)
    last_date = taiex[-1][0]
    rev_month = next(iter(revenue.values()))["month"] if revenue else ""

    os.makedirs(OUT_DIR, exist_ok=True)
    for key, theme in THEMES.items():
        report.CSS = theme["css"]
        html = report.render(last_date, state, industries, leaders, laggards, rev_month, prices=prices)
        card = (f'<!-- @dsCard group="台股趨勢日報" name="{theme["label"]}" '
                f'subtitle="{theme["subtitle"]}" width="1200" height="900" -->\n')
        path = os.path.join(OUT_DIR, f"{key}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(card + html)
        print(path)


if __name__ == "__main__":
    main()
