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
.b-top { background: #7a0010; box-shadow: inset 0 0 0 2px #d4af37; }
.b-hi { background: #a31621; }
.b-mid { background: #b07d2b; }
.b-lo { background: #9a917e; }
.toptag { color: #8a5d14; font-weight: 700; font-size: 12px; white-space: nowrap; }
.s3top { background: #f7f0dd; border-left: 4px solid #7a0010; padding: 9px 14px;
         margin-bottom: 14px; font-size: 14px; color: #4a443a; }
.s3top b { color: #7a0010; }
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

/* ⓪ 今日行動清單 */
.a-tier { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 17px; font-weight: 700;
          margin: 18px 0 8px; }
.a-perf { background: #f3ecdb; border-left: 3px solid #b07d2b; padding: 8px 12px;
          margin: 10px 0 4px; font-size: 13px; color: #4a443a; }
.a-note { color: #4a443a; font-size: 13px; margin-top: 12px; }

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
.lk-warn { background: #fbeee0; border-left: 3px solid #a31621; padding: 10px 14px;
           margin-top: 10px; font-size: 14px; color: #4a443a; }
.lk-warn b { color: #a31621; }
.lk-warn ul { margin: 6px 0 0 18px; }
.lk-warn li { margin: 4px 0; }
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
function badge(sc){var c=sc>=80?"b-top":sc>=70?"b-hi":sc>=50?"b-mid":"b-lo";return'<span class="badge '+c+'">'+sc+'</span>';}
function why(r){
 if(r.on=="leader")return'<div class="lk-why">'+L.on_leader.replace("{rank}",r.r)+'</div>';
 if(r.on=="candidate")return'<div class="lk-why">'+L.on_candidate.replace("{rank}",r.r)+'</div>';
 if(r.s!="ok")return'<div class="lk-why">'+L.filtered_intro+' '+L["status_"+r.s]+'</div>';
 var items=(r.b||[]).map(function(k){return"<li>"+L["block_"+k]+"</li>";}).join("");
 return'<div class="lk-why">'+L.not_on_intro+'<ul>'+items+'</ul></div>';}
function warn(r){
 if(!r.w||!r.w.length)return"";
 var items=r.w.map(function(k){return"<li>"+L["warn_"+k]+"</li>";}).join("");
 return'<div class="lk-warn"><b>'+L.warn_title+'</b><ul>'+items+'</ul></div>';}
function render(r){
 var tag=r.mk=="tpex"?'<span class="mkt">\\u6ac3</span>':"";
 var head='<div class="lk-head">';
 if(r.s=="ok")head+='<span class="lk-badge-wrap">'+badge(r.sc)+'</span>';
 head+='<a class="slink" href="'+tv(r)+'" target="_blank" rel="noopener"><span class="stockname">'+esc(r.n)+'</span></a> <span class="code">'+r.i+'</span>'+tag+'</div>';
 var body=warn(r);
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
            # 老王負向旗標警示(down_gap / false_break),前端以 L.warn_* 轉人話
            warns = []
            if r.get("down_gap_open"):
                warns.append("down_gap")
            if r.get("false_break"):
                warns.append("false_break")
            if warns:
                rec["w"] = warns
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
    cls = ("b-top" if score >= 80 else "b-hi" if score >= 70
           else "b-mid" if score >= 50 else "b-lo")
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
           lookup=None, backtest=None, rev_stars=None, action=None):
    t = UI[lang]
    rev_stars = rev_stars or []

    def bucket_for(score):
        """回測分數分桶中,該分數所屬的桶(取 lo<=score 的最高桶)。"""
        chosen = None
        for b in (backtest["buckets"] if backtest else []):
            if score >= b["lo"]:
                chosen = b
        return chosen
    iso = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:]}"
    rev_label = f"{int(rev_month[:3]) + 1911}/{rev_month[3:]}" if len(rev_month) == 5 else rev_month
    prices = prices or {}
    tracking = tracking or []
    idx_name = t["index_name"][market]

    def spark_for(m):
        p = prices.get(m["stock_id"])
        return spark_svg(p["rows"]) if p else "—"

    def stop_html(m):
        """老王兩段式出場梯次(顯示於收盤欄下):跌破 5 日線減碼一半、跌破 10 日線出清;
        近 10 日最低收盤(stop_ref)保留為第三道防線。"""
        c = m.get("close")
        if not c:
            return ""
        eh, ea, s = m.get("exit_half"), m.get("exit_all"), m.get("stop_ref")
        segs = []
        if eh:
            segs.append(t["exit_half_label"].format(v=f"{eh:,.1f}"))
        if ea:
            segs.append(t["exit_all_label"].format(v=f"{ea:,.1f}"))
        out = f'<br><span class="parts">{" / ".join(segs)}</span>' if segs else ""
        if s:
            out += (f'<br><span class="parts">{t["stop_label"]} {s:,.1f} '
                    f'({pct(s / c - 1)})</span>')
        return out

    links = ""
    if lang_href or other_href:
        links = '<div class="langbar">' + \
            (f'<a href="{other_href}">{t["other_market"][market]}</a>' if other_href else "") + \
            (f'<a href="{lang_href}">{t["lang_switch"]}</a>' if lang_href else "") + '</div>'

    if state["bull"] is True:
        banner = (f'<div class="banner bull"><b>{t["bull"]}</b>'
                  + t["bull_body"].format(idx=idx_name, close=state["close"], ma60=state["ma60"]) + '</div>')
    elif state["bull"] is False:
        bear_body = t["bear_body"].format(idx=idx_name, close=state["close"], ma60=state["ma60"])
        if state.get("repair"):   # 空頭中站回三短均的止跌試探(純顯示,不影響計分)
            bear_body += t["repair_line"]
        banner = f'<div class="banner bear"><b>{t["bear"]}</b>' + bear_body + '</div>'
    else:
        banner = f'<div class="banner">{t["nodata_banner"]}</div>'

    # 候選分層(顯示/通知層;底層 laggards 不動,快照/回測/查個股維持完整)。
    # 台股:回測校準的 ≥60 為正期望主清單、50–59 低信心觀察、<50 不顯示。
    # 美股:評分與台股不同尺度且尚未回測,不套台股門檻→改顯示相對強度前 8 強、其餘摺疊。
    if market == "tw":
        main_lags = [m for m in laggards if m["score"] >= 60]
        watch_lags = [m for m in laggards if 50 <= m["score"] < 60]
    else:
        # 美股 2 年回測:分數確實能排序,約 75+ 才轉正(含存活者偏誤、偏樂觀)。
        main_lags = [m for m in laggards if m["score"] >= 75]
        watch_lags = [m for m in laggards if m["score"] < 75]

    hi_count = sum(1 for m in laggards if m["score"] >= 70)
    state_v = t["stat_bull"] if state["bull"] else t["stat_bear"] if state["bull"] is False else "—"
    ma60_s = t["stat_ma60"].format(v=f'{state["ma60"]:,.0f}') if state.get("ma60") else "—"
    top_ind_v = display_sector(market, lang, industries[0]["industry"]) if industries else "—"
    top_ind_s = (pct(industries[0]["ret20"]) + " " + t["stat_top_suffix"]) if industries else ""
    cands_s = (main_lags[0]["name"] + " " + str(main_lags[0]["score"])) if main_lags else t["stat_none"]
    stats = f'''<div class="stats">
<div class="stat"><div class="k">{idx_name}</div><div class="v">{state["close"]:,.0f}</div><div class="s">{pct(state.get("ret1"), 2)}</div></div>
<div class="stat"><div class="k">{t["stat_state"]}</div><div class="v">{state_v}</div><div class="s">{ma60_s}</div></div>
<div class="stat"><div class="k">{t["stat_top_industry"]}</div><div class="v">{top_ind_v}</div><div class="s">{top_ind_s}</div></div>
<div class="stat"><div class="k">{t["stat_cands"]}</div><div class="v">{t["stat_cands_unit"].format(n=hi_count)}</div><div class="s">{cands_s}</div></div>
</div>'''

    # ⓪ 今日行動清單:大盤一句話 + 嚴選(F2 突破+投信連買,方案A/B)/平衡(補漲引擎,附警語)
    # 兩級 + 漲停雷達 + 出場說明 + 誠實註 + 三規則滾動命中率小表。美股=現行引擎(負超額警語)。
    # 所有績效數字由 action["stats"](action_config.CONFIG)帶入,此處不寫死。
    action_card = ""
    if action:
        ast = action["state"]
        astats = action["stats"]
        hold = action["hold_days"]
        radar_cfg = action.get("radar")

        def _radar_badge(m):
            key = m.get("radar")
            if not key or not radar_cfg:
                return "—"
            return f'<span class="tag">{t["a_radar_" + key].format(x=radar_cfg[key])}</span>'

        def _a_row_strong(m, i):
            return (f'<tr><td>{i} 🔥</td>'
                    f'<td>{stock_cell(m, market, lang, names_en)}</td>'
                    f'<td class="num">{m["close"]:,.1f}{stop_html(m)}</td>'
                    f'<td>{t["a_entry_val_strong"]}</td>'
                    f'<td>{t["a_hold_val"].format(n=hold)}</td>'
                    f'<td class="num">{m["close"] * 1.05:,.1f} / {m["close"] * 0.90:,.1f}</td>'
                    f'<td class="num">{t["days_unit"].format(n=m["trust_streak"])}</td>'
                    f'<td>{_radar_badge(m)}</td></tr>')

        def _a_row(m, i):
            tn = m.get("trust_net5") or 0
            mid = (f'<td class="num">{t["a_trust_val"].format(v=tn // 1000) if tn else "—"}</td>'
                   f'<td>{score_badge(m["score"])}</td><td>{_radar_badge(m)}</td>'
                   if market == "tw" else f'<td>{score_badge(m["score"])}</td>')
            return (f'<tr><td>{i}</td>'
                    f'<td>{stock_cell(m, market, lang, names_en)}</td>'
                    f'<td class="num">{m["close"]:,.1f}{stop_html(m)}</td>'
                    f'<td>{t["a_entry_val"]}</td>'
                    f'<td>{t["a_hold_val"].format(n=hold)}</td>'
                    + mid + '</tr>')

        def _a_table(cols, nums, rows):
            body = rows or f'<tr><td colspan="{len(cols)}">{t["a_empty"]}</td></tr>'
            return f'<div class="tblwrap"><table>{_th(cols, nums)}{body}</table></div>'

        a_cls = "bull" if ast == "bull" else "bear" if ast in ("bear", "repair") else ""
        state_line = f'<div class="banner {a_cls}">{t["a_state_" + ast]}</div>'

        if ast == "bull":
            if market == "tw":
                # 嚴選:訊號制(非分數),附方案A/B與每檔停利/停損參考價
                ss, sb = astats["strong"], astats["strong_planB"]
                strong_rows = "".join(_a_row_strong(m, i) for i, m in enumerate(action["strong"], 1))
                strong_perf = t["a_perf_strong"].format(
                    rng=action["test_range"], hold=hold, win=ss["win_abs"], ret=ss["ret_net"],
                    ex=ss["excess"], p10=ss["p10"], n=ss["n"])
                plans = (f'<div class="a-perf"><b>{t["a_plans_title"]}</b><br>'
                         + t["a_plan_a"].format(hold=hold, win=ss["win_abs"], ret=ss["ret_net"], ex=ss["excess"])
                         + "<br>"
                         + t["a_plan_b"].format(hold=hold, win=sb["win_abs"], ret=sb["ret_net"], lose=abs(sb["excess"]))
                         + f'<br>{t["a_plan_note"]}</div>')
                strong_block = (f'<div class="a-tier">{t["a_strong_title"][market]}</div>'
                                + _a_table(t["a_cols_strong"], {2, 5, 6}, strong_rows)
                                + f'<div class="a-perf">{strong_perf}</div>' + plans)
                # 平衡:補漲引擎 >=60(與嚴選去重),附盤勢依賴警語
                fl = astats["floor"]
                bal_rows = "".join(_a_row(m, i) for i, m in enumerate(action["balanced"], 1))
                bal_perf = t["a_perf"].format(rng=action["test_range"], win=fl["win"],
                                              ex=fl["excess"], p10=fl["p10"], n=fl["n"])
                bal_block = (f'<div class="a-tier">{t["a_balanced_title"]}</div>'
                             + _a_table(t["a_cols"][market], {2, 5}, bal_rows)
                             + f'<div class="a-perf">{bal_perf}</div>'
                             + f'<div class="a-note">{t["a_balanced_caveat"]}</div>')
                exit_note = t["a_exit_body"].format(
                    hold=hold, ma_win=astats["exit_ma_stop"]["win"],
                    ma_lose=abs(astats["exit_ma_stop"]["excess"]),
                    hold_win=astats["exit_hold_full"]["win"],
                    hold_ex=astats["exit_hold_full"]["excess"])
                radar_note = (f'<div class="a-note">{t["a_radar_note"].format(base=radar_cfg["baseline"], hold=hold)}</div>'
                              if radar_cfg else "")
                a_inner = (strong_block + bal_block + radar_note
                           + f'<div class="a-note"><b>{t["a_exit_title"]}</b> {exit_note}</div>')
            else:
                us = astats["us_current"]
                us_rows = "".join(_a_row(m, i) for i, m in enumerate(action["strong"], 1))
                us_perf = t["a_perf"].format(rng=action["test_range"], win=us["win"],
                                             ex=us["excess"], p10=us["p10"], n=us["n"])
                a_inner = (f'<div class="a-tier">{t["a_strong_title"][market]}</div>'
                           + _a_table(t["a_cols"][market], {2, 5}, us_rows)
                           + f'<div class="a-perf">{us_perf}</div>'
                           + f'<div class="a-note"><b>{t["a_exit_title"]}</b> {t["a_exit_us"]}</div>')
            a_inner += f'<div class="a-note">{t["a_honest"][market]}</div>'
        else:
            # 空頭/止跌試探/資料不足:不出清單,收合說明「今日不進場」
            a_inner = (f'<details><summary>{t["a_nolist"]}</summary>'
                       f'<div class="a-note">{t["a_nolist_body"]}</div></details>')

        hr = action.get("hitrate")
        hr_html = ""
        if hr:
            if any(hr.get(k, {}).get("n") for k in ("strong", "legacy", "current")):
                def _hr_row(label, d):
                    hit = f'{d["hit"] * 100:.1f}%' if d["hit"] is not None else "—"
                    return (f'<tr><td>{label}</td><td class="num">{hit}</td>'
                            f'<td class="num">{d["n"]}</td><td class="num">{hr["days"]}</td></tr>')
                hr_rows = ""
                if hr.get("strong"):
                    hr_rows += _hr_row(t["a_hr_strong"], hr["strong"])
                hr_rows += _hr_row(t["a_hr_legacy"], hr["legacy"]) + _hr_row(t["a_hr_current"], hr["current"])
                hr_html = (f'<div class="a-tier">{t["a_hr_title"]}</div>'
                           f'<div class="hint">{t["a_hr_hint"]}</div>'
                           f'<div class="tblwrap"><table>{_th(t["a_hr_cols"], {1, 2, 3})}'
                           f'{hr_rows}</table></div>')
            else:
                hr_html = f'<div class="a-note">{t["a_hr_pending"].format(n=hr.get("horizon", 20))}</div>'

        action_card = (f'<div class="card"><h2>{t["a_title"]}</h2>'
                       f'<div class="hint">{t["a_hint"][market]}</div>'
                       f'{state_line}{a_inner}{hr_html}</div>')

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
                        f'<td class="num">{m["close"]:,.1f}{stop_html(m)}</td>'
                        f'<td>{spark_for(m)}</td>'
                        f'<td class="num">{pct(m["ret20"])}</td>'
                        f'<td class="num">{pct(m["off_high"])}</td>'
                        + tail + '</tr>')
    n_leader_cols = len(t["s2_cols"][market])
    # 領頭羊實證註記(回測數字源自台股,僅台股顯示):動能整體有效但屬右尾、勿追最噴
    s2_note = f'<div class="hint">{t["s2_note"]}</div>' if market == "tw" else ""

    def _lag_row(m, i):
        parts = fmt_parts(lang, m["parts"])
        tags = "".join(f'<span class="tag">{fmt_reason(lang, r)}</span>' for r in m["reasons"])
        bs = m.get("board_streak", 1)
        badge_txt = (f'<span class="new-tag">{t["board_new"]}</span>' if bs <= 1
                     else f'<span class="parts">{t["board_streak"].format(n=bs)}</span>')
        bk = bucket_for(m["score"])
        expect = ""
        if bk:
            hit_pct = f'{bk["hit_rate"] * 100:.0f}'
            expect = (f'<br><span class="parts">'
                      f'{t["s3_expect"].format(h=backtest["horizon"], hit=hit_pct)}</span>')
        top_tag = f' <span class="toptag">{t["s3_top_tag"]}</span>' if m["score"] >= 80 else ""
        return (f'<tr><td>{i}</td>'
                f'<td>{stock_cell(m, market, lang, names_en)}<br>{badge_txt}</td>'
                f'<td>{display_sector(market, lang, m["industry"])}<br><span class="parts">{t["industry_rank"].format(n=m["industry_rank"])}</span></td>'
                f'<td class="num">{m["close"]:,.1f}{stop_html(m)}</td>'
                f'<td>{spark_for(m)}</td>'
                f'<td class="num">{pct(m["ret20"])}<br><span class="parts">{t["peer"]} {pct(m["industry_ret20"])}</span></td>'
                f'<td>{score_badge(m["score"])}{top_tag}<br><span class="parts">{parts}</span>{expect}</td>'
                f'<td class="reasons">{tags}</td></tr>')

    lag_rows = "".join(_lag_row(m, i) for i, m in enumerate(main_lags, 1))
    watch_rows = "".join(_lag_row(m, i) for i, m in enumerate(watch_lags, 1))

    # 強推分級(多頭、台股):80+ 強推清單或提示。回測數字源自台股,故僅台股顯示。
    s3_notice = ""
    if market == "tw" and state["bull"] is not False:
        tops = [m for m in main_lags if m["score"] >= 80]
        if tops:
            names = "、".join(f'{m["name"]} {m["score"]}' for m in tops) if lang == "zh" \
                else ", ".join(f'{display_name(market, lang, m["stock_id"], m["name"], names_en)} {m["score"]}' for m in tops)
            s3_notice = f'<div class="s3top">{t["s3_top_line"].format(names=names)}</div>'
        else:
            s3_notice = f'<div class="s3top">{t["s3_top_none"]}</div>'

    # 候選卡:門檻說明 + 主清單(≥60);50–59 摺疊觀察;空頭時整段摺疊(警示當把手)。
    def _s3_table(rows):
        body = rows or f'<tr><td colspan="8">{t["s3_empty_floor"]}</td></tr>'
        return f'<div class="tblwrap"><table>{_th(t["s3_cols"], {3, 5})}{body}</table></div>'

    watch_block = (f'<details class="watchfold"><summary>{t["s3_watch_title"][market]}</summary>'
                   f'{_s3_table(watch_rows)}</details>') if watch_rows else ""
    floor_note = f'<div class="hint">{t["s3_floor_note"][market]}</div>'
    if state["bull"] is False:
        bear_sum = t["s3_bear_warn"] if market == "tw" else t["s3_bear_us"]
        s3_inner = (f'<details class="bearfold"><summary class="banner bear">{bear_sum}</summary>'
                    f'{_s3_table(lag_rows)}{watch_block}</details>')
    else:
        s3_inner = f'{s3_notice}{_s3_table(lag_rows)}{watch_block}'
    s3_card = (f'<div class="card"><h2>{t["s3_title"]}</h2>'
               f'<div class="hint">{t["s3_hint"].format(mid=t["s3_mid"][market])}</div>'
               f'{floor_note}{s3_inner}</div>')

    track_rows = ""
    for tr in tracking:
        kind = t["s4_kind"][tr.get("kind", "laggard")]
        d_label = (f'<span class="parts">{kind}</span><br>{t["s4_ago"].format(n=tr["days"])}<br>'
                   f'<span class="parts">{tr["date"][5:].replace("-", "/")}</span>')
        beat = (tr["avg_ret"] - tr["taiex_ret"]) if tr["taiex_ret"] is not None else None
        # 贏大盤=好(紅/✓)、輸大盤=不好(綠/✗):符號+顏色雙重標示,不靠紅綠記憶也能看懂
        if beat is None:
            beat_html = "—"
        elif beat >= 0:
            beat_html = f'<b class="up">✓ {t["s4_beat"]} {beat * 100:.1f}%</b>'
        else:
            beat_html = f'<b class="down">✗ {t["s4_lose"]} {abs(beat) * 100:.1f}%</b>'
        first = True
        for r in tr["rows"]:
            track_rows += ('<tr>'
                           + (f'<td rowspan="{len(tr["rows"])}">{d_label}</td>' if first else '')
                           + f'<td><span class="stockname">{display_name(market, lang, r["id"], r["name"], names_en)}</span> '
                             f'<span class="code">{r["id"]}</span></td>'
                           f'<td class="num">{r["score"] if r["score"] is not None else "—"}</td>'
                           f'<td class="num">{r["close"]:,.1f}</td>'
                           f'<td class="num">{r["cur"]:,.1f}</td>'
                           f'<td class="num">{pct(r["ret"])}</td>'
                           + (f'<td class="num" rowspan="{len(tr["rows"])}">{pct(tr["avg_ret"])}<br>'
                              f'<span class="parts">{t["s4_market"]} {pct(tr["taiex_ret"])}</span><br>{beat_html}</td>'
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

    backtest_card = ""
    if backtest and backtest.get("buckets"):
        bt_rows = ""
        for b in backtest["buckets"]:
            label = f'{b["lo"]}+' if b.get("hi", 0) >= 101 else f'{b["lo"]}–{b["hi"] - 1}'
            bt_rows += (f'<tr><td>{label}</td>'
                        f'<td class="num">{b["n"]}</td>'
                        f'<td class="num">{b["hit_rate"] * 100:.0f}%</td>'
                        f'<td class="num">{pct(b["mean_excess"])}</td></tr>')
        rng = backtest.get("range") or ["", ""]
        fmt_d = lambda s: f"{s[:4]}/{s[4:6]}/{s[6:]}" if len(s) == 8 else s
        period = t["s5_period"].format(
            start=fmt_d(rng[0]), end=fmt_d(rng[1]),
            days=backtest.get("eval_days", "—"), h=backtest["horizon"])
        if backtest.get("regime") == "bull":
            period += t["s5_bull_only"]
        overall = t["s5_overall"].format(
            hit=f'{backtest["hit_rate"] * 100:.0f}', ex=pct(backtest["mean_excess"]))
        attr_block = ""
        if backtest.get("attribution"):
            names = t["s5_dim_names"]
            attr_rows = ""
            for d in backtest["attribution"]:
                attr_rows += (f'<tr><td>{names.get(d["dim"], d["dim"])}</td>'
                              f'<td class="num">{pct(d["spread"])}</td></tr>')
            attr_block = (f'<h2>{t["s5_attr_title"]}</h2>'
                          f'<div class="hint">{t["s5_attr_hint"]}</div>'
                          f'<div class="tblwrap"><table>{_th(t["s5_attr_cols"], {1})}'
                          f'{attr_rows}</table></div>'
                          f'<div class="hint">{t["s5_attr_note"]}</div>')
        backtest_card = f'''
<div class="card">
<h2>{t["s5_title"]}</h2>
<div class="hint">{t["s5_hint"]}</div>
<div class="sub">{period}<br>{overall}</div>
<div class="tblwrap"><table>
{_th(t["s5_cols"], {1, 2, 3})}
{bt_rows}
</table></div>
<div class="hint">{t["s5_caveat"]}</div>
{attr_block}
</div>'''

    rev_card = ""
    if rev_stars:
        rs_rows = "".join(
            f'<tr><td>{stock_cell(m, market, lang, names_en)}</td>'
            f'<td>{display_sector(market, lang, m["industry"])}</td>'
            f'<td class="num">{m["close"]:,.1f}</td>'
            f'<td>{spark_for(m)}</td>'
            f'<td class="num">{pct_raw(m["rev_yoy"])}</td>'
            f'<td class="num">{pct_raw(m["rev_mom"])}</td></tr>' for m in rev_stars)
        rev_card = (f'<div class="card"><h2>{t["s6_title"]}</h2>'
                    f'<div class="hint">{t["s6_hint"]}</div>'
                    f'<div class="tblwrap"><table>{_th(t["s6_cols"], {2, 4, 5})}{rs_rows}</table></div></div>')

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

{action_card}

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
{s2_note}
<div class="tblwrap"><table>
{_th(t["s2_cols"][market], {2, 4, 5, 6, 7})}
{leader_rows if leader_rows else f'<tr><td colspan="{n_leader_cols}">{t["s2_empty"]}</td></tr>'}
</table></div>
</div>

{s3_card}

{tracking_card}

{backtest_card}

{rev_card}

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
