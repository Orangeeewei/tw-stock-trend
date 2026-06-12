"""HTML 日報產生器:給沒有技術分析背景的讀者,所有指標都附白話說明。

正式版型:C 財經雜誌風(使用者於 Claude Design 三選一選定)。
"""

# 米白紙感、襯線標題、細黑分隔線,像實體財經週刊
CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
       background: #f6f2ea; color: #26221c; line-height: 1.7; }
.wrap { max-width: 1020px; margin: 0 auto; padding: 40px 22px 64px; }
h1 { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 38px; letter-spacing: 2px;
     border-bottom: 3px double #26221c; padding-bottom: 10px; margin-bottom: 6px; }
.sub { color: #6d6350; font-size: 13px; margin-bottom: 26px; letter-spacing: 1px; }
.banner { padding: 16px 20px; margin-bottom: 28px; font-size: 15px;
          border-top: 2px solid #26221c; border-bottom: 1px solid #c9c0ae; background: #fbf8f1; }
.banner.bull b { color: #a31621; }
.banner.bear b { color: #1d5c3f; }
.banner b { font-size: 18px; font-family: "Noto Serif TC", Georgia, serif; }
.card { background: transparent; padding: 0; margin-bottom: 40px; }
.card h2 { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 21px;
           margin-bottom: 4px; border-left: 5px solid #a31621; padding-left: 10px; }
.hint { color: #6d6350; font-size: 13px; margin-bottom: 14px; padding-left: 15px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; background: #fef9f0;
        border-top: 2px solid #26221c; }
th { text-align: left; color: #26221c; font-weight: 700; padding: 9px 10px; background: #f0e9dc;
     border-bottom: 1px solid #26221c; white-space: nowrap; font-size: 13px; }
td { padding: 9px 10px; border-bottom: 1px solid #ddd3bf; vertical-align: top; }
tr:hover td { background: #f5ede0; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.up { color: #a31621; font-weight: 600; }      /* 台股習慣:紅漲綠跌 */
.down { color: #1d5c3f; font-weight: 600; }
.badge { display: inline-block; min-width: 44px; text-align: center; padding: 2px 10px;
         color: #fbf8f1; font-weight: 700; font-size: 14px; }
.b-hi { background: #a31621; }
.b-mid { background: #b07d2b; }
.b-lo { background: #9a917e; }
.parts { color: #6d6350; font-size: 12px; white-space: nowrap; }
.reasons { font-size: 13px; color: #4a443a; }
.tag { display: inline-block; border: 1px solid #b07d2b; color: #8a5d14;
       padding: 0 8px; font-size: 12px; margin: 1px 4px 1px 0; white-space: nowrap; }
.glossary dt { font-weight: 700; margin-top: 10px; font-family: "Noto Serif TC", Georgia, serif; }
.glossary dd { color: #5d564a; font-size: 14px; }
.disclaimer { color: #9d9380; font-size: 12px; margin-top: 8px;
              border-top: 1px solid #c9c0ae; padding-top: 10px; }
.stockname { font-weight: 700; }
.code { color: #6d6350; font-size: 12px; }
.mkt { display: inline-block; border: 1px solid #6d6350; color: #6d6350;
       font-size: 11px; padding: 0 4px; margin-left: 2px; vertical-align: 1px; }

.slink { color: inherit; text-decoration: none; border-bottom: 1px dotted #b07d2b; }
.slink:hover { color: #a31621; }
.spark { display: block; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
         background: #c9c0ae; border: 1px solid #c9c0ae; margin-bottom: 28px; }
.stat { background: #fbf8f1; padding: 12px 14px; }
.stat .k { color: #6d6350; font-size: 12px; letter-spacing: 1px; }
.stat .v { font-family: "Noto Serif TC", Georgia, serif; font-size: 22px; font-weight: 700; }
.stat .s { color: #6d6350; font-size: 12px; }

/* 手機:表格改為可橫向滑動,避免撐爆版面 */
.tblwrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.tblwrap table { min-width: 700px; }
@media (max-width: 640px) {
  .wrap { padding: 20px 10px 40px; }
  .stats { grid-template-columns: repeat(2, 1fr); }
  .stat .v { font-size: 18px; }
  h1 { font-size: 24px; letter-spacing: 1px; }
  .stat .k { font-size: 11px; }
  .sub { font-size: 12px; letter-spacing: 0; }
  .banner { padding: 12px 14px; font-size: 14px; }
  .card h2 { font-size: 18px; }
  table { font-size: 13px; }
  th, td { padding: 7px 6px; }
  .reasons { font-size: 12px; }
}
"""


def pct(v, digits=1):
    if v is None:
        return "—"
    cls = "up" if v > 0 else "down" if v < 0 else ""
    return f'<span class="{cls}">{v * 100:+.{digits}f}%</span>'


def pct_raw(v, digits=0):
    if v is None:
        return "—"
    cls = "up" if v > 0 else "down" if v < 0 else ""
    return f'<span class="{cls}">{v:+.{digits}f}%</span>'


def score_badge(score):
    cls = "b-hi" if score >= 70 else "b-mid" if score >= 50 else "b-lo"
    return f'<span class="badge {cls}">{score}</span>'


def stock_cell(m):
    """股票名稱連到 TradingView 技術圖(新分頁開啟)。"""
    mkt = '<span class="mkt">櫃</span>' if m.get("market") == "tpex" else ""
    prefix = "TPEX" if m.get("market") == "tpex" else "TWSE"
    url = f"https://tw.tradingview.com/chart/?symbol={prefix}%3A{m['stock_id']}"
    return (f'<a class="slink" href="{url}" target="_blank" rel="noopener">'
            f'<span class="stockname">{m["name"]}</span></a> '
            f'<span class="code">{m["stock_id"]}</span>{mkt}')


def spark_svg(rows, w=200, h=52):
    """近 60 日收盤線 + 成交量柱的迷你走勢圖(純 SVG,零 JS)。
    rows: [(date, close, high, volume, value), ...]"""
    rows = rows[-60:]
    if len(rows) < 2:
        return "—"
    closes = [r[1] for r in rows]
    vols = [r[3] for r in rows]
    n = len(closes)
    vol_h, pad = 11, 2
    price_h = h - vol_h - pad
    lo, hi = min(closes), max(closes)
    rng = (hi - lo) or 1
    xs = [pad + i * (w - 2 * pad) / (n - 1) for i in range(n)]
    ys = [pad + (price_h - 2 * pad) * (1 - (c - lo) / rng) for c in closes]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    color = "#a31621" if closes[-1] >= closes[0] else "#1d5c3f"  # 紅漲綠跌
    vmax = max(vols) or 1
    bw = max((w - 2 * pad) / n - 0.6, 0.8)
    bars = "".join(
        f'<rect x="{x - bw / 2:.1f}" y="{h - vol_h * v / vmax:.1f}" '
        f'width="{bw:.1f}" height="{max(vol_h * v / vmax, 0.5):.1f}"/>'
        for x, v in zip(xs, vols))
    return (f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="近60日走勢">'
            f'<g fill="#b3936b">{bars}</g>'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/>'
            f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="2.2" fill="{color}"/></svg>')


def render(date_str, state, industries, leaders, laggards, rev_month, prices=None):
    iso = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
    rev_label = f"{int(rev_month[:3]) + 1911}/{rev_month[3:]}" if len(rev_month) == 5 else rev_month
    prices = prices or {}

    def spark_for(m):
        p = prices.get(m["stock_id"])
        return spark_svg(p["rows"]) if p else "—"

    hi_count = sum(1 for m in laggards if m["score"] >= 70)
    stats = f'''<div class="stats">
<div class="stat"><div class="k">加權指數</div><div class="v">{state["close"]:,.0f}</div><div class="s">{pct(state.get("ret1"), 2)}</div></div>
<div class="stat"><div class="k">大盤狀態</div><div class="v">{"多頭" if state["bull"] else "空頭" if state["bull"] is False else "—"}</div><div class="s">60 日線 {f"{state['ma60']:,.0f}" if state.get("ma60") else "—"}</div></div>
<div class="stat"><div class="k">最強產業</div><div class="v">{industries[0]["industry"] if industries else "—"}</div><div class="s">{pct(industries[0]["ret20"]) if industries else ""} / 20日</div></div>
<div class="stat"><div class="k">補漲候選 ≥70 分</div><div class="v">{hi_count} 檔</div><div class="s">{laggards[0]["name"] + " " + str(laggards[0]["score"]) + " 分" if laggards else "今日從缺"}</div></div>
</div>'''

    if state["bull"] is True:
        banner = (f'<div class="banner bull"><b>🟢 大盤多頭</b> — 加權指數 {state["close"]:,.0f} 點,'
                  f'站在 60 日均線({state["ma60"]:,.0f})之上。'
                  f'白話:過去三個月買進的人平均是賺錢的,市場氣氛偏樂觀,補漲策略此時勝率較高。</div>')
    elif state["bull"] is False:
        banner = (f'<div class="banner bear"><b>🔴 大盤空頭</b> — 加權指數 {state["close"]:,.0f} 點,'
                  f'跌破 60 日均線({state["ma60"]:,.0f})。'
                  f'白話:市場整體在退潮,「還沒漲的股票」常常變成「接著跌的股票」,建議觀望、降低部位。</div>')
    else:
        banner = '<div class="banner">資料不足 60 日,暫無法判斷大盤多空。</div>'

    ind_rows = ""
    for ind in industries[:10]:
        ind_rows += (f'<tr><td>{ind["rank"]}</td><td>{ind["industry"]}</td>'
                     f'<td class="num">{pct(ind["ret20"])}</td>'
                     f'<td class="num">{pct(ind["ret5"])}</td>'
                     f'<td class="num">{ind["value_share"] * 100:.1f}%</td>'
                     f'<td class="num">{ind["count"]}</td></tr>')

    leader_rows = ""
    for m in leaders:
        streak = f'{m["trust_streak"]} 天' if m["trust_streak"] else "—"
        leader_rows += (f'<tr><td>{stock_cell(m)}</td>'
                        f'<td>{m["industry"]}</td>'
                        f'<td class="num">{m["close"]:,.1f}</td>'
                        f'<td>{spark_for(m)}</td>'
                        f'<td class="num">{pct(m["ret20"])}</td>'
                        f'<td class="num">{pct(m["off_high"])}</td>'
                        f'<td class="num">{streak}</td>'
                        f'<td class="num">{pct_raw(m["rev_yoy"])}</td></tr>')

    lag_rows = ""
    for i, m in enumerate(laggards, 1):
        p = m["parts"]
        parts = (f'產業 {p["產業熱度"]}/25 · 法人 {p["法人動向"]}/30 · '
                 f'營收 {p["營收動能"]}/20 · 位階量能 {p["位階量能"]}/25')
        tags = "".join(f'<span class="tag">{r}</span>' for r in m["reasons"])
        lag_rows += (f'<tr><td>{i}</td>'
                     f'<td>{stock_cell(m)}</td>'
                     f'<td>{m["industry"]}<br><span class="parts">產業第 {m["industry_rank"]} 強</span></td>'
                     f'<td class="num">{m["close"]:,.1f}</td>'
                     f'<td>{spark_for(m)}</td>'
                     f'<td class="num">{pct(m["ret20"])}<br><span class="parts">同業 {pct(m["industry_ret20"])}</span></td>'
                     f'<td>{score_badge(m["score"])}<br><span class="parts">{parts}</span></td>'
                     f'<td class="reasons">{tags}</td></tr>')

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>台股趨勢日報 {iso}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<h1>台股趨勢日報</h1>
<div class="sub">資料日期:{iso}(上市 + 上櫃,上櫃標示「櫃」)· 月營收資料:{rev_label}</div>

{banner}

{stats}

<div class="card">
<h2>① 資金往哪裡去 — 產業熱度排行</h2>
<div class="hint">以各產業成分股近 20 日漲跌幅的中位數排名。連續多日排在前面的產業,就是現在市場資金集中的主流。</div>
<div class="tblwrap"><table>
<tr><th>排名</th><th>產業</th><th class="num">20 日漲跌</th><th class="num">5 日漲跌</th><th class="num">今日成交佔比</th><th class="num">檔數</th></tr>
{ind_rows}
</table></div>
</div>

<div class="card">
<h2>② 誰在帶頭衝 — 強勢產業領頭羊</h2>
<div class="hint">熱門產業中已創(或逼近)60 日新高的股票。它們不是買進建議,而是「風向標」:領頭羊還在創新高,代表這個產業的行情還沒結束。點股票名稱可開啟完整技術圖(TradingView)。</div>
<div class="tblwrap"><table>
<tr><th>股票</th><th>產業</th><th class="num">收盤</th><th>近 60 日走勢</th><th class="num">20 日漲跌</th><th class="num">距 60 日高</th><th class="num">投信連買</th><th class="num">營收年增</th></tr>
{leader_rows if leader_rows else '<tr><td colspan="8">今日無符合條件的領頭羊</td></tr>'}
</table></div>
</div>

<div class="card">
<h2>③ 還沒漲的同業 — 補漲候選(核心)</h2>
<div class="hint">條件:熱門產業 + 漲幅落後同業 + 離高點還有空間 + 已出現甦醒跡象(量增或法人開始買)。
進場分數越高,代表「產業對、籌碼對、營收對、位置對」四件事同時成立的程度越高。<b>70 分以上才值得認真研究。</b>點股票名稱可開啟完整技術圖。</div>
<div class="tblwrap"><table>
<tr><th>#</th><th>股票</th><th>產業</th><th class="num">收盤</th><th>近 60 日走勢</th><th class="num">20 日漲跌</th><th>進場分數</th><th>白話理由</th></tr>
{lag_rows if lag_rows else '<tr><td colspan="8">今日無符合條件的補漲候選</td></tr>'}
</table></div>
</div>

<div class="card glossary">
<h2>名詞白話解釋</h2>
<dl>
<dt>投信連買</dt><dd>投信 = 台灣的基金公司。他們買股票要寫報告、過內部審核,所以「連續好幾天買同一檔」通常代表做過功課、打算做一個波段,是台股最值得跟蹤的籌碼訊號。</dd>
<dt>外資買超</dt><dd>外國機構投資人買進比賣出多。外資部位大、動向慢,轉買往往是中期趨勢的開始。</dd>
<dt>營收年增率(YoY)</dt><dd>這個月營收跟去年同月比成長多少。正的代表公司生意越做越大,是最簡單可靠的基本面指標。</dd>
<dt>距 60 日高</dt><dd>現在股價離最近三個月最高點還有多遠。-20% 代表還在相對低的位置(低基期),補漲空間較大;但跌超過 -35% 要小心是不是公司本身出了問題。</dd>
<dt>量能放大</dt><dd>最近 5 天平均成交量是過去 20 天平均的幾倍。超過 1.2 倍代表開始有人注意到這檔股票,「沉睡的股票醒了」。</dd>
<dt>60 日均線</dt><dd>過去三個月所有買進者的平均成本。大盤站在它上面 = 多數人賺錢、願意續抱;跌破 = 多數人套牢、隨時想賣。</dd>
</dl>
</div>

<div class="disclaimer">本報告由公開資料(臺灣證券交易所、證券櫃檯買賣中心)自動產生,僅供研究參考,不構成任何投資建議。補漲候選為「值得研究的名單」而非買進訊號,進場前請自行確認公司基本面與消息面。</div>
</div>
</body>
</html>"""
