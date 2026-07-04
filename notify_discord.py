"""把 summary.json 推到 Discord webhook。

用法:python3 notify_discord.py            # 台股(中文,讀 docs/summary.json)
      python3 notify_discord.py --us       # 美股(英文,讀 docs/us/summary.json)
      python3 notify_discord.py --dry-run  # 只組訊息印出,不發送(驗證用,可配 --us)

環境變數:
  DISCORD_WEBHOOK_URL  必填(--dry-run 時免),Discord 頻道的 webhook 網址
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
        "act_name": "⓪ 今日行動清單",
        "act_pick_strong": "**{name}** `{id}` — 突破60日高、投信連買 {ts} 天{badge}",
        "act_pick": "**{name}** `{id}` **{score}** — 投信5日 {t:+,} 張",
        "act_stats": "嚴選歷史(測試段 {rng},隔日收盤進、抱滿 {hold} 日):絕對勝率 {sw:.1f}%(扣成本)、平均贏大盤 {ex:+.2f}%",
        "act_strong_empty": "今日嚴選 0 檔(正常)— 改列平衡級(補漲引擎)前 3:",
        "act_balanced_stats": "平衡歷史勝率 {fw:.1f}%(贏大盤;盤勢依賴,詳報告警語)",
        "act_none": "📵 今日不進場(大盤非多頭,清單暫停)",
        "act_empty": "多頭但今日無合格標的 — 寧缺勿濫",
        "act_radar": {"lock": " 🚨亮燈", "breakout": " 🚨突破", "vol_surge": " 🚨爆量"},
        "radar_line": "⚡ 今日亮燈 {n} 檔:{names}",
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
        "act_name": "⓪ Action list (current engine, 75+)",
        "act_pick": "**{name}** `{id}` **{score}**",
        "act_stats": "Heads-up: this engine's recent backtest is negative-excess ({sw:.1f}% win, test period) — watchlist, not conviction.",
        "act_none": "📵 No entries today (regime is not bullish).",
        "act_empty": "Bull regime, but no qualifying names today.",
    },
}


def _action_field(t, s, us):
    """⓪ 行動清單欄位(放 fields 最前)。台股:嚴選(突破+投信連買)前5+勝率數字,
    嚴選 0 檔屬正常 → 改列平衡級前 3 附警語;美股:現行引擎候選 + 負超額警語。
    summary.json 無 action(舊檔)時台股顯示不進場、美股略過。"""
    a = s.get("action")
    if us and not a:
        return None
    if not a or a.get("state") != "bull":
        return {"name": t["act_name"], "value": t["act_none"], "inline": False}
    st = a.get("stats") or {}
    if us:
        picks = (a.get("strong") or [])[:5]
        if not picks:
            return {"name": t["act_name"], "value": t["act_empty"], "inline": False}
        lines = [t["act_pick"].format(name=x["name"], id=x["id"], score=x["score"]) for x in picks]
        lines.append(t["act_stats"].format(sw=st.get("us_current", {}).get("win", 0)))
        return {"name": t["act_name"], "value": "\n".join(lines), "inline": False}
    strong = (a.get("strong") or [])[:5]
    if strong:
        lines = [t["act_pick_strong"].format(
                     name=x["name"], id=x["id"], ts=x.get("trust_streak", 0),
                     badge=t["act_radar"].get(x.get("radar"), ""))
                 for x in strong]
        ss = st.get("strong", {})
        lines.append(t["act_stats"].format(sw=ss.get("win_abs", 0), ex=ss.get("excess", 0),
                                           rng=a.get("test_range", ""), hold=a.get("hold_days", 20)))
    else:
        balanced = (a.get("balanced") or [])[:3]
        if not balanced:
            return {"name": t["act_name"], "value": t["act_empty"], "inline": False}
        lines = [t["act_strong_empty"]]
        lines += [t["act_pick"].format(name=x["name"], id=x["id"], score=x["score"],
                                       t=(x.get("trust_net5") or 0) // 1000)
                  for x in balanced]
        lines.append(t["act_balanced_stats"].format(fw=st.get("floor", {}).get("win", 0)))
    return {"name": t["act_name"], "value": "\n".join(lines), "inline": False}


def main():
    us = "--us" in sys.argv
    dry = "--dry-run" in sys.argv
    t = TEXT["us" if us else "tw"]
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook and not dry:
        sys.exit("缺少 DISCORD_WEBHOOK_URL")
    report_url = os.environ.get("REPORT_URL", "").strip()

    path = os.path.join(ROOT, "docs", "us", "summary.json") if us \
        else os.path.join(ROOT, "docs", "summary.json")
    with open(path, encoding="utf-8") as f:
        s = json.load(f)

    bull = s["market"]["bull"]
    key = "bull" if bull is True else "bear" if bull is False else "nodata"
    market_line = t[key].format(close=s["market"]["close"])
    # ⚡ 全市場漲停雷達(僅台股):今日亮燈總數 + 前 3 檔名;0 檔就不加行。
    if not us:
        radar = s.get("radar") or {}
        n = sum((radar.get("counts") or {}).values())
        if n:
            names = [x["name"] for grp in ("lock", "breakout", "vol_surge")
                     for x in radar.get(grp, [])][:3]
            market_line += "\n" + t["radar_line"].format(n=n, names="、".join(names))
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
    act = _action_field(t, s, us)
    if act:
        embed["fields"].insert(0, act)

    if report_url:
        embed["url"] = report_url
        embed["fields"].append({"name": t["report"], "value": report_url, "inline": False})

    if dry:
        print(json.dumps({"embeds": [embed]}, ensure_ascii=False, indent=2))
        return

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
