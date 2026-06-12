"""設計方向候選(v2):三套完整主題,套在同一份報告結構上供 Claude Design 比較。
v1 三選一已由使用者選定雜誌風;v2 是在雜誌風基礎上的三個深化方向。"""

# 共用:手機與元件的結構性 CSS(三套主題共用,避免漏掉新元件)
_STRUCTURAL = """
.tblwrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.tblwrap table { min-width: 700px; }
.spark { display: block; }
@media (max-width: 640px) {
  .wrap { padding: 20px 10px 40px; }
  .stats { grid-template-columns: repeat(2, 1fr); }
  .stat .v { font-size: 18px; }
  h1 { font-size: 25px; }
  .sub { font-size: 12px; letter-spacing: 0; }
  .banner { padding: 12px 14px; font-size: 14px; }
  .card h2 { font-size: 18px; }
  table { font-size: 13px; }
  th, td { padding: 7px 6px; }
  .reasons { font-size: 12px; }
}
"""

# ── v2-classic 經典精裝:現行雜誌風的精修版(字階、留白、細節對齊)──
CLASSIC = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
       background: #f6f2ea; color: #26221c; line-height: 1.7; }
.wrap { max-width: 1020px; margin: 0 auto; padding: 40px 22px 64px; }
h1 { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 38px; letter-spacing: 2px;
     border-bottom: 3px double #26221c; padding-bottom: 12px; margin-bottom: 6px; }
.sub { color: #8a8170; font-size: 13px; margin-bottom: 24px; letter-spacing: 1.5px; }
.banner { padding: 16px 20px; margin-bottom: 22px; font-size: 15px;
          border-top: 2px solid #26221c; border-bottom: 1px solid #c9c0ae; background: #fbf8f1; }
.banner.bull b { color: #a31621; }
.banner.bear b { color: #1d5c3f; }
.banner b { font-size: 18px; font-family: "Noto Serif TC", Georgia, serif; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
         background: #c9c0ae; border: 1px solid #c9c0ae; margin-bottom: 34px; }
.stat { background: #fbf8f1; padding: 14px 16px; }
.stat .k { color: #8a8170; font-size: 12px; letter-spacing: 1.5px; }
.stat .v { font-family: "Noto Serif TC", Georgia, serif; font-size: 24px; font-weight: 700; }
.stat .s { color: #8a8170; font-size: 12px; }
.card { margin-bottom: 40px; }
.card h2 { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 22px;
           margin-bottom: 6px; border-left: 5px solid #a31621; padding-left: 12px; }
.hint { color: #8a8170; font-size: 13px; margin-bottom: 14px; padding-left: 17px; max-width: 760px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; background: #fbf8f1;
        border-top: 2px solid #26221c; }
th { text-align: left; color: #26221c; font-weight: 700; padding: 10px; border-bottom: 1px solid #26221c;
     white-space: nowrap; font-size: 13px; }
td { padding: 10px; border-bottom: 1px solid #ddd3bf; vertical-align: middle; }
tr:hover td { background: #f3ecdd; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.up { color: #a31621; font-weight: 600; }
.down { color: #1d5c3f; font-weight: 600; }
.badge { display: inline-block; min-width: 46px; text-align: center; padding: 3px 10px;
         color: #fbf8f1; font-weight: 700; font-size: 14px; }
.b-hi { background: #a31621; } .b-mid { background: #b07d2b; } .b-lo { background: #9a917e; }
.parts { color: #8a8170; font-size: 12px; white-space: nowrap; }
.reasons { font-size: 13px; color: #4a443a; }
.tag { display: inline-block; border: 1px solid #b07d2b; color: #8a5d14;
       padding: 0 8px; font-size: 12px; margin: 1px 4px 1px 0; white-space: nowrap; }
.glossary dt { font-weight: 700; margin-top: 10px; font-family: "Noto Serif TC", Georgia, serif; }
.glossary dd { color: #5d564a; font-size: 14px; }
.disclaimer { color: #a89f8c; font-size: 12px; margin-top: 8px; border-top: 1px solid #c9c0ae; padding-top: 10px; }
.stockname { font-weight: 700; }
.code { color: #8a8170; font-size: 12px; }
.mkt { display: inline-block; border: 1px solid #8a8170; color: #8a8170;
       font-size: 11px; padding: 0 4px; margin-left: 2px; vertical-align: 1px; }
.slink { color: inherit; text-decoration: none; border-bottom: 1px dotted #b07d2b; }
.slink:hover { color: #a31621; }
""" + _STRUCTURAL

# ── v2-ink 墨韻典藏:深墨重對比、紅印章刊頭、章節感更強 ──
INK = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
       background: #f1ebdd; color: #1a1713; line-height: 1.75; }
.wrap { max-width: 1020px; margin: 0 auto; padding: 44px 22px 64px; }
h1 { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 40px; letter-spacing: 6px;
     border-top: 6px solid #1a1713; border-bottom: 1px solid #1a1713;
     padding: 14px 0 12px; margin-bottom: 6px; position: relative; }
h1::after { content: "日報"; position: absolute; right: 0; top: 16px; background: #9e1b1b; color: #f1ebdd;
            font-size: 15px; letter-spacing: 3px; padding: 6px 8px 6px 11px; font-weight: 700; }
.sub { color: #7d7461; font-size: 13px; margin-bottom: 26px; letter-spacing: 2px; }
.banner { padding: 16px 20px; margin-bottom: 22px; font-size: 15px;
          background: #1a1713; color: #e8e0cf; }
.banner b { font-size: 18px; font-family: "Noto Serif TC", Georgia, serif; }
.banner.bull b { color: #e98b8b; }
.banner.bear b { color: #8fce9f; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin-bottom: 36px;
         border-top: 2px solid #1a1713; border-bottom: 1px solid #1a1713; }
.stat { padding: 14px 16px 12px 0; border-right: 1px solid #cfc4a9; }
.stat:last-child { border-right: none; }
.stat .k { color: #7d7461; font-size: 12px; letter-spacing: 2px; }
.stat .v { font-family: "Noto Serif TC", Georgia, serif; font-size: 26px; font-weight: 700; }
.stat .s { color: #7d7461; font-size: 12px; }
.card { margin-bottom: 44px; }
.card h2 { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 23px; letter-spacing: 1px;
           margin-bottom: 6px; padding-bottom: 6px; border-bottom: 2px solid #1a1713; }
.hint { color: #7d7461; font-size: 13px; margin: 8px 0 14px; max-width: 760px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; color: #f1ebdd; background: #1a1713; font-weight: 700; padding: 9px 10px;
     white-space: nowrap; font-size: 13px; letter-spacing: 1px; }
td { padding: 10px; border-bottom: 1px solid #cfc4a9; vertical-align: middle; }
tr:hover td { background: #e9e1cd; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.up { color: #9e1b1b; font-weight: 700; }
.down { color: #205c38; font-weight: 700; }
.badge { display: inline-block; min-width: 46px; text-align: center; padding: 3px 10px;
         color: #f1ebdd; font-weight: 700; font-size: 14px; }
.b-hi { background: #9e1b1b; } .b-mid { background: #8a6519; } .b-lo { background: #6f6757; }
.parts { color: #7d7461; font-size: 12px; white-space: nowrap; }
.reasons { font-size: 13px; color: #3c362c; }
.tag { display: inline-block; background: #e9e1cd; border: 1px solid #b3a37c; color: #6d5512;
       padding: 0 8px; font-size: 12px; margin: 1px 4px 1px 0; white-space: nowrap; }
.glossary dt { font-weight: 700; margin-top: 10px; font-family: "Noto Serif TC", Georgia, serif; }
.glossary dd { color: #564f41; font-size: 14px; }
.disclaimer { color: #978c74; font-size: 12px; margin-top: 8px; border-top: 1px solid #cfc4a9; padding-top: 10px; }
.stockname { font-weight: 700; }
.code { color: #7d7461; font-size: 12px; }
.mkt { display: inline-block; border: 1px solid #7d7461; color: #7d7461;
       font-size: 11px; padding: 0 4px; margin-left: 2px; vertical-align: 1px; }
.slink { color: inherit; text-decoration: none; border-bottom: 1px dotted #8a6519; }
.slink:hover { color: #9e1b1b; }
""" + _STRUCTURAL

# ── v2-modern 現代編輯檯:亮底細線、藏青標題、數字優先(FT/日經混血)──
MODERN = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
       background: #faf8f4; color: #20242c; line-height: 1.65; }
.wrap { max-width: 1040px; margin: 0 auto; padding: 36px 22px 60px; }
h1 { font-size: 30px; font-weight: 800; letter-spacing: 1px; color: #1f2a44;
     padding-bottom: 12px; border-bottom: 3px solid #1f2a44; margin-bottom: 6px; }
.sub { color: #8b8f99; font-size: 13px; margin-bottom: 24px; }
.banner { padding: 14px 18px; margin-bottom: 22px; font-size: 15px; border-left: 6px solid; background: #fff; box-shadow: 0 1px 2px rgba(31,42,68,.08); }
.banner.bull { border-color: #c0392b; }
.banner.bear { border-color: #1e6b46; }
.banner b { font-size: 18px; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 32px; }
.stat { background: #fff; padding: 14px 16px; box-shadow: 0 1px 2px rgba(31,42,68,.08); border-top: 3px solid #1f2a44; }
.stat .k { color: #8b8f99; font-size: 12px; letter-spacing: 1px; }
.stat .v { font-size: 26px; font-weight: 800; color: #1f2a44; font-variant-numeric: tabular-nums; }
.stat .s { color: #8b8f99; font-size: 12px; }
.card { margin-bottom: 36px; }
.card h2 { font-size: 19px; font-weight: 800; color: #1f2a44; margin-bottom: 4px; }
.hint { color: #8b8f99; font-size: 13px; margin-bottom: 12px; max-width: 760px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; background: #fff; box-shadow: 0 1px 2px rgba(31,42,68,.08); }
th { text-align: left; color: #5a6070; font-weight: 700; padding: 9px 10px;
     border-bottom: 2px solid #1f2a44; white-space: nowrap; font-size: 12.5px; letter-spacing: .5px; }
td { padding: 10px; border-bottom: 1px solid #eceae4; vertical-align: middle; }
tr:hover td { background: #f5f3ec; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.up { color: #c0392b; font-weight: 700; }
.down { color: #1e6b46; font-weight: 700; }
.badge { display: inline-block; min-width: 46px; text-align: center; padding: 3px 10px; border-radius: 3px;
         color: #fff; font-weight: 700; font-size: 14px; }
.b-hi { background: #c0392b; } .b-mid { background: #b9770e; } .b-lo { background: #9aa0ab; }
.parts { color: #8b8f99; font-size: 12px; white-space: nowrap; }
.reasons { font-size: 13px; color: #3e4450; }
.tag { display: inline-block; background: #eef1f7; color: #1f2a44; border-radius: 3px;
       padding: 1px 8px; font-size: 12px; margin: 1px 4px 1px 0; white-space: nowrap; }
.glossary dt { font-weight: 800; margin-top: 10px; color: #1f2a44; }
.glossary dd { color: #5a6070; font-size: 14px; }
.disclaimer { color: #a6aab3; font-size: 12px; margin-top: 8px; border-top: 1px solid #e3e1da; padding-top: 10px; }
.stockname { font-weight: 700; }
.code { color: #8b8f99; font-size: 12px; }
.mkt { display: inline-block; border: 1px solid #8b8f99; color: #8b8f99;
       font-size: 11px; padding: 0 4px; margin-left: 2px; vertical-align: 1px; }
.slink { color: inherit; text-decoration: none; border-bottom: 1px dotted #1f2a44; }
.slink:hover { color: #c0392b; }
""" + _STRUCTURAL

THEMES = {
    "v2-classic": {"label": "v2 經典精裝", "subtitle": "現行雜誌風精修:字階放大、留白與細節對齊", "css": CLASSIC},
    "v2-ink": {"label": "v2 墨韻典藏", "subtitle": "深墨重對比、紅印章刊頭、墨色表頭,章節感最強", "css": INK},
    "v2-modern": {"label": "v2 現代編輯檯", "subtitle": "亮底細線、藏青標題、數字優先,FT/日經混血", "css": MODERN},
}
