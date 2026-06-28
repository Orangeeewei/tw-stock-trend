"""把 summary.json 推到 Discord webhook。

用法:python3 notify_discord.py        # 台股(中文,讀 docs/summary.json)
      python3 notify_discord.py --us   # 美股(英文,讀 docs/us/summary.json)

環境變數:
  DISCORD_WEBHOOK_URL  必填,Discord 頻道的 webhook 網址
  REPORT_URL           選填,完整報告的網頁連結(GitHub Pages)
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))

TEXT = {
    "tw": {
        "title": "台股趨勢日報 {date}",
        "bull": "🟢 **多頭** — 加權指數 {close:,.0f} 點,站上 60 日線,順勢選股可執行",
        "bear": "🔴 **空頭** — 加權指數 {close:,.0f} 點,跌破 60 日線,建議觀望",
        "nodata": "⚪ 資料不足 60 日,暫無法判斷大盤多空(加權指數 {close:,.0f} 點)",
        "industries": "🔥 強勢產業",
        "laggards": "🎯 強勢進場候選(進場分數 70 以上才值得研究)",
        "empty": "今日無符合條件的候選",
        "report": "完整報告",
        "footer": "公開資料自動產生,僅供研究參考,不構成投資建議",
        "ind_line": "{i}. {name}(20日 {ret:+.1f}%)",
    },
    "us": {
        "title": "US Stock Trend Daily {date}",
        "bull": "🟢 **Bull** — S&P 500 at {close:,.0f}, above its 60-day MA. Trend-following setups are in season.",
        "bear": "🔴 **Bear** — S&P 500 at {close:,.0f}, below its 60-day MA. Stay cautious.",
        "nodata": "⚪ Fewer than 60 days of data — regime unavailable (S&P 500 at {close:,.0f})",
        "industries": "🔥 Hot sectors",
        "laggards": "🎯 Strong-entry picks (only 70+ deserves research)",
        "empty": "No qualifying candidates today",
        "report": "Full report",
        "footer": "Auto-generated from public data. Research only — not investment advice.",
        "ind_line": "{i}. {name} ({ret:+.1f}% / 20d)",
    },
}


def main():
    us = "--us" in sys.argv
    t = TEXT["us" if us else "tw"]
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        sys.exit("缺少 DISCORD_WEBHOOK_URL")
    report_url = os.environ.get("REPORT_URL", "").strip()

    path = os.path.join(ROOT, "docs", "us", "summary.json") if us \
        else os.path.join(ROOT, "docs", "summary.json")
    with open(path, encoding="utf-8") as f:
        s = json.load(f)

    bull = s["market"]["bull"]
    key = "bull" if bull is True else "bear" if bull is False else "nodata"
    market_line = t[key].format(close=s["market"]["close"])
    color = {"bull": 0xA31621, "bear": 0x1D5C3F, "nodata": 0x9A917E}[key]

    ind_lines = "\n".join(
        t["ind_line"].format(i=i, name=x["industry"], ret=x["ret20"] * 100)
        for i, x in enumerate(s["industries"], 1))

    lag_lines = "\n".join(
        f"**{x['name']}** `{x['id']}` **{x['score']}** — {', '.join(x['reasons'][:3])}"
        for x in s["laggards"][:5]) or t["empty"]

    embed = {
        "title": t["title"].format(date=s["date"]),
        "description": market_line,
        "color": color,
        "fields": [
            {"name": t["industries"], "value": ind_lines, "inline": False},
            {"name": t["laggards"], "value": lag_lines, "inline": False},
        ],
        "footer": {"text": t["footer"]},
    }
    if report_url:
        embed["url"] = report_url
        embed["fields"].append({"name": t["report"], "value": report_url, "inline": False})

    payload = json.dumps({"embeds": [embed]}).encode("utf-8")
    req = urllib.request.Request(webhook, data=payload, headers={
        "Content-Type": "application/json",
        # Discord 的 Cloudflare 會 403 Python 預設 UA
        "User-Agent": "Mozilla/5.0 (compatible; tw-stock-trend/1.0)",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        print("Discord 推播完成:", resp.status)


if __name__ == "__main__":
    main()
