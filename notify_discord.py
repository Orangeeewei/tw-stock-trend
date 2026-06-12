"""把 docs/summary.json 推到 Discord webhook。

環境變數:
  DISCORD_WEBHOOK_URL  必填,Discord 頻道的 webhook 網址
  REPORT_URL           選填,完整報告的網頁連結(GitHub Pages)
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        sys.exit("缺少 DISCORD_WEBHOOK_URL")
    report_url = os.environ.get("REPORT_URL", "").strip()

    with open(os.path.join(ROOT, "docs", "summary.json"), encoding="utf-8") as f:
        s = json.load(f)

    if s["market"]["bull"]:
        market_line = f"🟢 **多頭** — 加權指數 {s['market']['close']:,.0f} 點,站上 60 日線,補漲策略可執行"
        color = 0xA31621
    else:
        market_line = f"🔴 **空頭** — 加權指數 {s['market']['close']:,.0f} 點,跌破 60 日線,建議觀望"
        color = 0x1D5C3F

    ind_lines = "\n".join(
        f"{i}. {x['industry']}(20日 {x['ret20'] * 100:+.1f}%)"
        for i, x in enumerate(s["industries"], 1))

    lag_lines = "\n".join(
        f"**{x['name']}** `{x['id']}` 分數 **{x['score']}** — {'、'.join(x['reasons'][:3])}"
        for x in s["laggards"][:5]) or "今日無符合條件的候選"

    embed = {
        "title": f"台股趨勢日報 {s['date']}",
        "description": market_line,
        "color": color,
        "fields": [
            {"name": "🔥 強勢產業", "value": ind_lines, "inline": False},
            {"name": "🎯 補漲候選(進場分數 70 以上才值得研究)", "value": lag_lines, "inline": False},
        ],
        "footer": {"text": "公開資料自動產生,僅供研究參考,不構成投資建議"},
    }
    if report_url:
        embed["url"] = report_url
        embed["fields"].append({"name": "完整報告", "value": report_url, "inline": False})

    payload = json.dumps({"embeds": [embed]}).encode("utf-8")
    req = urllib.request.Request(webhook, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        print("Discord 推播完成:", resp.status)


if __name__ == "__main__":
    main()
