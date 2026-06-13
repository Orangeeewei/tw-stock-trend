"""HTML 日報產生器:給沒有技術分析背景的讀者,所有指標都附白話說明。

支援 market=tw/us × lang=zh/en;文案集中在 locales.py。
版型:財經雜誌風(使用者於 Claude Design 選定並手動調整)。
"""
import json

from locales import (UI, GLOSSARY, LOOKUP, PART_LABELS, fmt_reason, fmt_parts,
                     display_name, display_sector)

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
       background: #e6dcc6; color: #2a2620; line-height: 1.7; }
.wrap { max-width: 1180px; margin: 0 auto; padding: 44px 26px 72px; }
h1 { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 38px; letter-spacing: 2px;
     border-bottom: 3px double #2a2620; padding-bottom: 10px; margin-bottom: 6px; }
.langbar { float: right; font-size: 13px; margin-top: 16px; }
.langbar a { color: #6d6350; text-decoration: none; border: 1px solid #b07d2b;
             padding: 3px 10px; margin-left: 6px; white-space: nowrap; }
.langbar a:hover { color: #a31621; }
.sub { color: #6d6350; font-size: 13px; margin-bottom: 26px; letter-spacing: 1px; }
.banner { padding: 18px 22px; margin-bottom: 24px; font-size: 15px;
          border-top: 3px solid #2a2620; border-left: 1px solid #d8cdb6; border-right: 1px solid #d8cdb6;
          border-bottom: 1px solid #d8cdb6; background: #fbf8f0; box-shadow: 0 1px 3px rgba(60,48,28,0.06); }
.banner.bull b { color: #a31621; }
.banner.bear b { color: #1d5c3f; }
.banner b { font-size: 18px; font-family: "Noto Serif TC", Georgia, serif; }
/* 每一個區塊是一張獨立紙張,區塊間有明顯間距與陰影,讀起來有段落感 */
.card { background: #fbf8f0; padding: 24px 26px 26px; margin-bottom: 30px;
        border: 1px solid #d8cdb6; border-top: 3px solid #2a2620;
        box-shadow: 0 1px 3px rgba(60,48,28,0.06); }
.card h2 { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 22px;
           margin-bottom: 6px; border-left: 5px solid #a31621; padding-left: 12px; }
.hint { color: #6d6350; font-size: 13px; margin-bottom: 16px; padding-left: 17px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; background: transparent;
        border-top: 1px solid #cabfa6; }
th { text-align: left; color: #2a2620; font-weight: 700; padding: 9px 10px; background: #ece2cd;
     border-bottom: 1px solid #2a2620; white-space: nowrap; font-size: 13px; }
/* 預設不換行,避免中文被擠成直書或零散斷行 */
td { padding: 10px 10px; border-bottom: 1px solid #e0d6c0; vertical-align: top; white-space: nowrap; }
tr:hover td { background: rgba(176,125,43,0.06); }
/* 只有「白話理由」標籤與進場分數明細這兩欄可以換行 */
td.reasons { white-space: normal; }
.parts { white-space: normal; }
.num .parts { white-space: nowrap; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.up { color: #a31621; font-weight: 600; }      /* 紅漲綠跌(台股慣例,兩版一致) */
.down { color: #1d5c3f; font-weight: 600; }
.badge { display: inline-block; min-width: 44px; text-align: center; padding: 2px 10px;
         color: #fbf8f1; font-weight: 700; font-size: 14px; }
.b-hi { background: #a31621; }
.b-mid { background: #b07d2b; }
.b-lo { background: #9a917e; }
.parts { color: #6d6350; font-size: 12px; }
.reasons { font-size: 13px; color: #4a443a; }
.tag { display: inline-block; border: 1px solid #b07d2b; color: #8a5d14;
       padding: 0 8px; font-size: 12px; margin: 1px 4px 1px 0; white-space: nowrap; }
.glossary dt { font-weight: 700; margin-top: 10px; font-family: "Noto Serif TC", Georgia, serif; }
.glossary dd { color: #5d564a; font-size: 14px; }
.disclaimer { color: #9d9380; font-size: 12px; margin-top: 8px;
              border-top: 1px solid #cfc4ab; padding-top: 10px; }
.stockname { font-weight: 700; }
.code { color: #6d6350; font-size: 12px; }
.mkt { display: inline-block; border: 1px solid #6d6350; color: #6d6350;
       font-size: 11px; padding: 0 4px; margin-left: 2px; vertical-align: 1px; }
.slink { color: inherit; text-decoration: none; border-bottom: 1px dotted #b07d2b; }
.slink:hover { color: #a31621; }
.new-tag { color: #a31621; font-size: 12px; font-weight: 700; white-space: nowrap; }
.pseg { white-space: nowrap; }
.hot { color: #a31621; font-weight: 700; }
.spark { display: block; width: 100%; min-width: 172px; height: 52px; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
         background: #d8cdb6; border: 1px solid #d8cdb6; margin-bottom: 30px;
         box-shadow: 0 1px 3px rgba(60,48,28,0.06); }
.stat { background: #fbf8f0; padding: 14px 16px; }
.stat .k { color: #6d6350; font-size: 12px; letter-spacing: 1px; }
.stat .v { font-family: "Noto Serif TC", Georgia, serif; font-size: 22px; font-weight: 700; }
.stat .s { color: #6d6350; font-size: 12px; }

/* 手機:表格改為可橫向滑動,避免撐爆版面 */
.tblwrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.tblwrap table { min-width: 700px; }
@media (max-width: 640px) {
  .wrap { padding: 20px 10px 40px; }
  .card { padding: 16px 14px 18px; }
  .stats { grid-template-columns: repeat(2, 1fr); }
  .stat .v { font-size: 18px; }
  h1 { font-size: 24px; letter-spacing: 1px; }
  .langbar { margin-top: 4px; }
  .stat .k { font-size: 11px; }
  .sub { font-size: 12px; letter-spacing: 0; }
  .banner { padding: 12px 14px; font-size: 14px; }
  .card h2 { font-size: 18px; }
  table { font-size: 13px; }
  th, td { padding: 7px 6px; }
  .reasons { font-size: 12px; }
}

/* 查個股搜尋框 */
.lk-input { width: 100%; font-size: 16px; padding: 11px 14px; border: 1px solid #b07d2b;
            background: #fff; color: #2a2620; font-family: inherit; }
.lk-input:focus { outline: none; border-color: #a31621; }
.lk-card { margin-top: 16px; border-top: 1px solid #cabfa6; padding-top: 14px; }
.lk-head { font-size: 18px; margin-bottom: 4px; }
.lk-head .stockname { font-size: 18px; }
.lk-badge-wrap { float: right; }
.lk-metrics { color: #6d6350; font-size: 13px; margin: 8px 0; }
.lk-metrics b { color: #2a2620; font-weight: 600; }
.lk-why { background: #f3ecdb; border-left: 3px solid #b07d2b; padding: 10px 14px;
          margin-top: 10px; font-size: 14px; color: #4a443a; }
.lk-why ul { margin: 6px 0 0 18px; }
.lk-why li { margin: 4px 0; }
.lk-msg { color: #6d6350; font-size: 14px; padding: 8px 0; }
"""

# 查個股搜尋框的前端邏輯;__DATA__/__L__/__LANG__ 由 render 以 JSON 取代(避免 f-string 大括號衝突)。
_LOOKUP_JS = """
(function(){
var D=__DATA__,L=__L__,LANG=__LANG__,MKT=__MKT__,byId={};
for(var i=0;i<D.length;i++){byId[D[i].i]=D[i];}
function esc(s){return String(s).replace(/[&<>]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
function find(q){q=q.trim();if(!q)return null;if(byId[q])return byId[q];
 var ql=q.toLowerCase(),pre=[],con=[];
 for(var i=0;i<D.length;i++){var r=D[i];
  if(r.n&&r.n.toLowerCase()===ql)return r;
  if(r.i.indexOf(q)===0)pre.push(r);
  else if(r.n&&r.n.toLowerCase().indexOf(ql)>=0)con.push(r);}
 return pre.concat(con)[0]||null;}
function pct(v){if(v==null)return"\\u2014";var c=v>0?"up":v<0?"down":"";
 return'<span class="'+c+'">'+(v>0?"+":"")+(v*100).toFixed(1)+'%</span>';}
function tv(r){var d=LANG=="zh"?"tw.tradingview.com":"www.tradingview.com";
 var p=MKT=="tw"?(r.mk=="tpex"?"TPEX%3A":"TWSE%3A"):"";return"https://"+d+"/chart/?symbol="+p+r.i;}
function badge(sc){var c=sc>=70?"b-hi":sc>=50?"b-mid":"b-lo";return'<span class="badge '+c+'">'+sc+'</span>';}
function why(r){
 if(r.on=="leader")return'<div class="lk-why">'+L.on_leader.replace("{rank}",r.r)+'</div>';
 if(r.on=="candidate")return'<div class="lk-why">'+L.on_candidate.replace("{rank}",r.r)+'</div>';
 if(r.s!="ok")return'<div class="lk-why">'+L.filtered_intro+' '+L["status_"+r.s]+'</div>';
 var items=(r.b||[]).map(function(k){return"<li>"+L["block_"+k]+"</li>";}).join("");
 return'<div class="lk-why">'+L.not_on_intro+'<ul>'+items+'</ul></div>';}
function render(r){
 var tag=r.mk=="tpex"?'<span class="mkt">\\u6ac3</span>':"";
 var head='<div class="lk-head">';
 if(r.s=="ok")head+='<span class="lk-badge-wrap">'+badge(r.sc)+'</span>';
 head+='<a class="slink" href="'+tv(r)+'" target="_blank" rel="noopener"><span class="stockname">'+esc(r.n)+'</span></a> <span class="code">'+r.i+'</span>'+tag+'</div>';
 var body="";
 if(r.s=="ok"){
  var segs=(r.p||[]).map(function(x){return'<span class="pseg">'+esc(x[0])+' '+x[1]+'/'+x[2]+'</span>';}).join(" \\u00b7 ");
  body+='<div class="parts">'+L.score_label+': '+segs+'</div>';
  var mt=[];
  if(r.ind)mt.push(L.metric_industry+': <b>'+esc(r.ind)+'</b>');
  if(r.oh!=null)mt.push(L.metric_off_high+': <b>'+pct(r.oh)+'</b>');
  if(r.vr!=null)mt.push(L.metric_vol+': <b>'+r.vr.toFixed(2)+'\\u00d7</b>');
  body+='<div class="lk-metrics">'+mt.join(" &nbsp;\\u00b7&nbsp; ")+'</div>';}
 return'<div class="lk-card">'+head+body+why(r)+'</div>';}
var inp=document.getElementById("q"),out=document.getElementById("qresult");
function go(){var q=inp.value;if(!q.trim()){out.innerHTML="";return;}
 var r=find(q);out.innerHTML=r?render(r):'<div class="lk-msg">'+L.not_found.replace("{q}",esc(q))+'</div>';}
inp.addEventListener("input",go);
})();
"""


def _lookup_payload(lookup, market, lang, names_en):
    """把 analyze.diagnose_universe 的結果壓成前端用的精簡記錄(名稱/分項/產業已在地化)。"""
    lab = PART_LABELS[lang]
    recs = []
    for r in lookup:
        rec = {"i": r["id"], "n": display_name(market, lang, r["id"], r["name"], names_en),
               "mk": r.get("market", "twse"), "s": r["status"]}
        if r.get("close") is not None:
            rec["c"] = round(r["close"], 2)
        if r["status"] == "ok":
            rec["sc"] = r["score"]
            rec["p"] = [[lab[k], pts, mx] for k, pts, mx in r["parts"]]
            rec["on"] = r["on"]
            if r.get("rank"):
                rec["r"] = r["rank"]
            rec["oh"] = round(r["off_high"], 4) if r["off_high"] is not None else None
            rec["vr"] = round(r["vol_ratio"], 2) if r["vol_ratio"] is not None else None
            rec["ind"] = display_sector(market, lang, r["industry"]) if r["industry"] else None
            if r.get("blocks"):
                rec["b"] = r["blocks"]
        recs.append(rec)
    return recs


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


def stock_cell(m, market="tw", lang="zh", names_en=None):
    """股票名稱連到 TradingView 技術圖(新分頁開啟)。"""
    mkt = '<span class="mkt">櫃</span>' if m.get("market") == "tpex" else ""
    if market == "tw":
        prefix = "TPEX%3A" if m.get("market") == "tpex" else "TWSE%3A"
    else:
        prefix = ""
    domain = "tw.tradingview.com" if lang == "zh" else "www.tradingview.com"
    url = f"https://{domain}/chart/?symbol={prefix}{m['stock_id']}"
    shown = display_name(market, lang, m["stock_id"], m["name"], names_en)
    return (f'<a class="slink" href="{url}" target="_blank" rel="noopener">'
            f'<span class="stockname">{shown}</span></a> '
            f'<span class="code">{m["stock_id"]}</span>{mkt}')


def spark_svg(rows, w=200, h=52):
    """近 60 日收盤線 + 成交量柱的迷你走勢圖(純 SVG,零 JS),自動填滿欄寬。
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
    return (f'<svg class="spark" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
            f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="60d trend">'
            f'<g fill="#b3936b">{bars}</g>'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5" '
            f'vector-effect="non-scaling-stroke"/>'
            f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="2.2" fill="{color}"/></svg>')


def _th(cols, nums):
    """nums: 靠右對齊(數字)欄位的 index 集合。"""
    return "<tr>" + "".join(
        f'<th class="num">{c}</th>' if i in nums else f"<th>{c}</th>"
        for i, c in enumerate(cols)) + "</tr>"


def render(date_str, state, industries, leaders, laggards, rev_month, prices=None,
           tracking=None, market="tw", lang="zh", lang_href=None, other_href=None, names_en=None,
           lookup=None):
    t = UI[lang]
    iso = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
    rev_label = f"{int(rev_month[:3]) + 1911}/{rev_month[3:]}" if len(rev_month) == 5 else rev_month
    prices = prices or {}
    tracking = tracking or []
    idx_name = t["index_name"][market]

    def spark_for(m):
        p = prices.get(m["stock_id"])
        return spark_svg(p["rows"]) if p else "—"

    links = ""
    if lang_href or other_href:
        links = '<div class="langbar">' + \
            (f'<a href="{other_href}">{t["other_market"][market]}</a>' if other_href else "") + \
            (f'<a href="{lang_href}">{t["lang_switch"]}</a>' if lang_href else "") + '</div>'

    if state["bull"] is True:
        banner = (f'<div class="banner bull"><b>{t["bull"]}</b>'
                  + t["bull_body"].format(idx=idx_name, close=state["close"], ma60=state["ma60"]) + '</div>')
    elif state["bull"] is False:
        banner = (f'<div class="banner bear"><b>{t["bear"]}</b>'
                  + t["bear_body"].format(idx=idx_name, close=state["close"], ma60=state["ma60"]) + '</div>')
    else:
        banner = f'<div class="banner">{t["nodata_banner"]}</div>'

    hi_count = sum(1 for m in laggards if m["score"] >= 70)
    state_v = t["stat_bull"] if state["bull"] else t["stat_bear"] if state["bull"] is False else "—"
    ma60_s = t["stat_ma60"].format(v=f'{state["ma60"]:,.0f}') if state.get("ma60") else "—"
    top_ind_v = display_sector(market, lang, industries[0]["industry"]) if industries else "—"
    top_ind_s = (pct(industries[0]["ret20"]) + " " + t["stat_top_suffix"]) if industries else ""
    cands_s = (laggards[0]["name"] + " " + str(laggards[0]["score"])) if laggards else t["stat_none"]
    stats = f'''<div class="stats">
<div class="stat"><div class="k">{idx_name}</div><div class="v">{state["close"]:,.0f}</div><div class="s">{pct(state.get("ret1"), 2)}</div></div>
<div class="stat"><div class="k">{t["stat_state"]}</div><div class="v">{state_v}</div><div class="s">{ma60_s}</div></div>
<div class="stat"><div class="k">{t["stat_top_industry"]}</div><div class="v">{top_ind_v}</div><div class="s">{top_ind_s}</div></div>
<div class="stat"><div class="k">{t["stat_cands"]}</div><div class="v">{t["stat_cands_unit"].format(n=hi_count)}</div><div class="s">{cands_s}</div></div>
</div>'''

    ind_rows = ""
    for ind in industries[:10]:
        streak = ind.get("top3_streak")
        streak_txt = (f'<span class="hot">{t["streak_days"].format(n=streak)}</span>' if streak and streak > 1
                      else t["streak_new"] if streak == 1 else "—")
        ind_rows += (f'<tr><td>{ind["rank"]}</td><td>{display_sector(market, lang, ind["industry"])}</td>'
                     f'<td class="num">{pct(ind["ret20"])}</td>'
                     f'<td class="num">{pct(ind["ret5"])}</td>'
                     f'<td class="num">{ind["value_share"] * 100:.1f}%</td>'
                     f'<td class="num">{ind["count"]}</td>'
                     f'<td class="num">{streak_txt}</td></tr>')

    leader_rows = ""
    for m in leaders:
        tail = ""
        if market == "tw":
            streak = t["days_unit"].format(n=m["trust_streak"]) if m["trust_streak"] else "—"
            tail = (f'<td class="num">{streak}</td>'
                    f'<td class="num">{pct_raw(m["rev_yoy"])}</td>')
        else:
            tail = f'<td class="num">{pct(m["ret5"])}</td>'
        leader_rows += (f'<tr><td>{stock_cell(m, market, lang, names_en)}</td>'
                        f'<td>{display_sector(market, lang, m["industry"])}</td>'
                        f'<td class="num">{m["close"]:,.1f}</td>'
                        f'<td>{spark_for(m)}</td>'
                        f'<td class="num">{pct(m["ret20"])}</td>'
                        f'<td class="num">{pct(m["off_high"])}</td>'
                        + tail + '</tr>')
    n_leader_cols = len(t["s2_cols"][market])

    lag_rows = ""
    for i, m in enumerate(laggards, 1):
        parts = fmt_parts(lang, m["parts"])
        tags = "".join(f'<span class="tag">{fmt_reason(lang, r)}</span>' for r in m["reasons"])
        bs = m.get("board_streak", 1)
        badge_txt = (f'<span class="new-tag">{t["board_new"]}</span>' if bs <= 1
                     else f'<span class="parts">{t["board_streak"].format(n=bs)}</span>')
        lag_rows += (f'<tr><td>{i}</td>'
                     f'<td>{stock_cell(m, market, lang, names_en)}<br>{badge_txt}</td>'
                     f'<td>{display_sector(market, lang, m["industry"])}<br><span class="parts">{t["industry_rank"].format(n=m["industry_rank"])}</span></td>'
                     f'<td class="num">{m["close"]:,.1f}</td>'
                     f'<td>{spark_for(m)}</td>'
                     f'<td class="num">{pct(m["ret20"])}<br><span class="parts">{t["peer"]} {pct(m["industry_ret20"])}</span></td>'
                     f'<td>{score_badge(m["score"])}<br><span class="parts">{parts}</span></td>'
                     f'<td class="reasons">{tags}</td></tr>')

    track_rows = ""
    for tr in tracking:
        d_label = (f'{t["s4_ago"].format(n=tr["days"])}<br>'
                   f'<span class="parts">{tr["date"][5:].replace("-", "/")}</span>')
        beat = (tr["avg_ret"] - tr["taiex_ret"]) if tr["taiex_ret"] is not None else None
        beat_word = t["s4_beat"] if beat is not None and beat > 0 else t["s4_lose"]
        first = True
        for r in tr["rows"]:
            track_rows += ('<tr>'
                           + (f'<td rowspan="{len(tr["rows"])}">{d_label}</td>' if first else '')
                           + f'<td><span class="stockname">{display_name(market, lang, r["id"], r["name"], names_en)}</span> '
                             f'<span class="code">{r["id"]}</span></td>'
                           f'<td class="num">{r["score"]}</td>'
                           f'<td class="num">{r["close"]:,.1f}</td>'
                           f'<td class="num">{r["cur"]:,.1f}</td>'
                           f'<td class="num">{pct(r["ret"])}</td>'
                           + (f'<td class="num" rowspan="{len(tr["rows"])}">{pct(tr["avg_ret"])}<br>'
                              f'<span class="parts">{t["s4_market"]} {pct(tr["taiex_ret"])} · '
                              f'{beat_word} {pct(abs(beat)) if beat is not None else "—"}</span></td>'
                              if first else '')
                           + '</tr>')
            first = False

    tracking_card = f'''
<div class="card">
<h2>{t["s4_title"]}</h2>
<div class="hint">{t["s4_hint"]}</div>
<div class="tblwrap"><table>
{_th(t["s4_cols"], {2, 3, 4, 5, 6})}
{track_rows}
</table></div>
</div>''' if track_rows else ""

    glossary = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in GLOSSARY[(market, lang)])

    lookup_card = lookup_script = ""
    if lookup:
        lk = LOOKUP[(market, lang)]
        data_json = json.dumps(_lookup_payload(lookup, market, lang, names_en),
                               ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        l_json = json.dumps(lk, ensure_ascii=False).replace("</", "<\\/")
        lookup_card = (f'<div class="card" id="lookup"><h2>{lk["title"]}</h2>'
                       f'<div class="hint">{lk["hint"]}</div>'
                       f'<input class="lk-input" id="q" type="search" autocomplete="off" '
                       f'placeholder="{lk["placeholder"]}" aria-label="{lk["title"]}">'
                       f'<div id="qresult"></div></div>')
        lookup_script = ("<script>" + _LOOKUP_JS.replace("__DATA__", data_json)
                         .replace("__L__", l_json).replace("__LANG__", json.dumps(lang))
                         .replace("__MKT__", json.dumps(market)) + "</script>")

    return f"""<!DOCTYPE html>
<html lang="{'zh-Hant' if lang == 'zh' else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t["title"][market]} {iso}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{links}
<h1>{t["title"][market]}</h1>
<div class="sub">{t["meta"][market].format(date=iso, rev=rev_label)}</div>

{banner}

{stats}

{lookup_card}

<div class="card">
<h2>{t["s1_title"]}</h2>
<div class="hint">{t["s1_hint"]}</div>
<div class="tblwrap"><table>
{_th(t["s1_cols"], {2, 3, 4, 5, 6})}
{ind_rows}
</table></div>
</div>

<div class="card">
<h2>{t["s2_title"]}</h2>
<div class="hint">{t["s2_hint"]}</div>
<div class="tblwrap"><table>
{_th(t["s2_cols"][market], {2, 4, 5, 6, 7})}
{leader_rows if leader_rows else f'<tr><td colspan="{n_leader_cols}">{t["s2_empty"]}</td></tr>'}
</table></div>
</div>

<div class="card">
<h2>{t["s3_title"]}</h2>
<div class="hint">{t["s3_hint"].format(mid=t["s3_mid"][market])}</div>
<div class="tblwrap"><table>
{_th(t["s3_cols"], {3, 5})}
{lag_rows if lag_rows else f'<tr><td colspan="8">{t["s3_empty"]}</td></tr>'}
</table></div>
</div>

{tracking_card}

<div class="card glossary">
<h2>{t["glossary_title"]}</h2>
<dl>
{glossary}
</dl>
</div>

<div class="disclaimer">{t["disclaimer"][market]}</div>
</div>
{lookup_script}
</body>
</html>"""
