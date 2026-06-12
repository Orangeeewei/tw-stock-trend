"""三套候選視覺主題,套在同一份報告結構上供比較。"""

# ── A. 深色金融終端風:像 Bloomberg 終端機,深底、等寬數字、霓虹強調 ──
TERMINAL = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
       background: #0a0f1a; color: #d3dce8; line-height: 1.6; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 28px 16px 48px; }
h1 { font-size: 24px; color: #f3f6fb; letter-spacing: 2px; margin-bottom: 4px; }
h1::before { content: "▌"; color: #22d3ee; margin-right: 8px; }
.sub { color: #5b6b80; font-size: 13px; margin-bottom: 22px; font-family: Consolas, monospace; }
.banner { border-radius: 6px; padding: 14px 18px; margin-bottom: 24px; font-size: 14px;
          border-left: 4px solid; background: #101826; }
.banner.bull { border-color: #f87171; color: #fecaca; }
.banner.bear { border-color: #4ade80; color: #bbf7d0; }
.banner b { font-size: 17px; }
.card { background: #0f1726; border: 1px solid #1c2940; border-radius: 8px;
        padding: 18px 20px; margin-bottom: 22px; }
.card h2 { font-size: 16px; color: #22d3ee; letter-spacing: 1px; margin-bottom: 4px; }
.hint { color: #5b6b80; font-size: 12.5px; margin-bottom: 12px; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th { text-align: left; color: #4b5d76; font-weight: 600; padding: 7px 10px;
     border-bottom: 1px solid #233650; white-space: nowrap;
     text-transform: uppercase; font-size: 11.5px; letter-spacing: 1px; }
td { padding: 8px 10px; border-bottom: 1px solid #141f33; vertical-align: top; }
tr:hover td { background: #131e31; }
.num { text-align: right; font-family: Consolas, "JetBrains Mono", monospace;
       font-variant-numeric: tabular-nums; white-space: nowrap; }
.up { color: #f87171; }
.down { color: #4ade80; }
.badge { display: inline-block; min-width: 44px; text-align: center; padding: 2px 10px;
         border-radius: 4px; font-weight: 700; font-size: 14px; font-family: Consolas, monospace; }
.b-hi { background: #7f1d1d; color: #fecaca; box-shadow: 0 0 8px rgba(248,113,113,.45); }
.b-mid { background: #78350f; color: #fde68a; }
.b-lo { background: #1e293b; color: #94a3b8; }
.parts { color: #4b5d76; font-size: 11.5px; white-space: nowrap; font-family: Consolas, monospace; }
.reasons { font-size: 12.5px; color: #9fb0c5; }
.tag { display: inline-block; background: #112033; color: #67e8f9; border: 1px solid #155e75;
       border-radius: 3px; padding: 0 7px; font-size: 11.5px; margin: 1px 4px 1px 0; white-space: nowrap; }
.glossary dt { font-weight: 700; color: #e2e8f0; margin-top: 10px; }
.glossary dd { color: #7c8da3; font-size: 13.5px; }
.disclaimer { color: #3d4c61; font-size: 11.5px; margin-top: 8px; }
.stockname { font-weight: 600; color: #f1f5f9; }
.code { color: #4b5d76; font-size: 11.5px; font-family: Consolas, monospace; }
"""

# ── B. 現代亮色儀表板風:漸層橫幅、大圓角卡片、柔和陰影,像 SaaS dashboard ──
DASHBOARD = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft JhengHei", "PingFang TC", "Noto Sans TC", sans-serif;
       background: #f4f5fb; color: #1f2333; line-height: 1.65; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 28px 16px 56px; }
h1 { font-size: 28px; margin-bottom: 4px;
     background: linear-gradient(90deg, #4f46e5, #9333ea); -webkit-background-clip: text;
     background-clip: text; color: transparent; display: inline-block; }
.sub { color: #8088a3; font-size: 14px; margin-bottom: 22px; }
.banner { border-radius: 16px; padding: 18px 22px; margin-bottom: 26px; font-size: 15px; color: #fff; }
.banner.bull { background: linear-gradient(115deg, #e11d48, #f97316); }
.banner.bear { background: linear-gradient(115deg, #047857, #0d9488); }
.banner b { font-size: 19px; }
.card { background: #fff; border-radius: 18px; padding: 22px 24px; margin-bottom: 26px;
        box-shadow: 0 8px 28px rgba(80, 86, 140, .09); }
.card h2 { font-size: 18px; margin-bottom: 4px; }
.hint { color: #8088a3; font-size: 13px; margin-bottom: 14px; }
table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 14px; }
th { text-align: left; color: #8088a3; font-weight: 600; padding: 8px 10px;
     border-bottom: 2px solid #eef0f7; white-space: nowrap; }
td { padding: 10px; border-bottom: 1px solid #f3f4fa; vertical-align: top; }
tr:hover td { background: #f8f8fe; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.up { color: #e11d48; font-weight: 600; }
.down { color: #059669; font-weight: 600; }
.badge { display: inline-block; min-width: 48px; text-align: center; padding: 4px 12px;
         border-radius: 999px; color: #fff; font-weight: 700; font-size: 14px; }
.b-hi { background: linear-gradient(115deg, #e11d48, #f97316); }
.b-mid { background: linear-gradient(115deg, #d97706, #eab308); }
.b-lo { background: #b3b9cf; }
.parts { color: #8088a3; font-size: 12px; white-space: nowrap; }
.reasons { font-size: 13px; color: #3c4257; }
.tag { display: inline-block; background: #eef2ff; color: #4f46e5; border-radius: 999px;
       padding: 2px 10px; font-size: 12px; margin: 2px 4px 2px 0; white-space: nowrap; }
.glossary dt { font-weight: 700; margin-top: 10px; }
.glossary dd { color: #5a6079; font-size: 14px; }
.disclaimer { color: #aab0c5; font-size: 12px; margin-top: 8px; }
.stockname { font-weight: 700; }
.code { color: #8088a3; font-size: 12px; }
"""

# ── C. 財經雜誌風:米白紙感、襯線標題、細黑分隔線,像實體財經週刊 ──
MAGAZINE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Microsoft JhengHei", "Noto Sans TC", sans-serif;
       background: #f6f2ea; color: #26221c; line-height: 1.7; }
.wrap { max-width: 1000px; margin: 0 auto; padding: 36px 20px 56px; }
h1 { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 34px;
     border-bottom: 3px double #26221c; padding-bottom: 10px; margin-bottom: 6px; }
.sub { color: #8a8170; font-size: 13px; margin-bottom: 26px; letter-spacing: 1px; }
.banner { padding: 16px 20px; margin-bottom: 28px; font-size: 15px;
          border-top: 2px solid #26221c; border-bottom: 1px solid #c9c0ae; background: #fbf8f1; }
.banner.bull b { color: #a31621; }
.banner.bear b { color: #1d5c3f; }
.banner b { font-size: 18px; font-family: "Noto Serif TC", Georgia, serif; }
.card { background: transparent; padding: 0; margin-bottom: 34px; }
.card h2 { font-family: "Noto Serif TC", "PMingLiU", Georgia, serif; font-size: 21px;
           margin-bottom: 4px; border-left: 5px solid #a31621; padding-left: 10px; }
.hint { color: #8a8170; font-size: 13px; margin-bottom: 14px; padding-left: 15px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; background: #fbf8f1;
        border-top: 2px solid #26221c; }
th { text-align: left; color: #26221c; font-weight: 700; padding: 9px 10px;
     border-bottom: 1px solid #26221c; white-space: nowrap; font-size: 13px; }
td { padding: 9px 10px; border-bottom: 1px solid #ddd3bf; vertical-align: top; }
tr:hover td { background: #f3ecdd; }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.up { color: #a31621; font-weight: 600; }
.down { color: #1d5c3f; font-weight: 600; }
.badge { display: inline-block; min-width: 44px; text-align: center; padding: 2px 10px;
         color: #fbf8f1; font-weight: 700; font-size: 14px; }
.b-hi { background: #a31621; }
.b-mid { background: #b07d2b; }
.b-lo { background: #9a917e; }
.parts { color: #8a8170; font-size: 12px; white-space: nowrap; }
.reasons { font-size: 13px; color: #4a443a; }
.tag { display: inline-block; border: 1px solid #b07d2b; color: #8a5d14;
       padding: 0 8px; font-size: 12px; margin: 1px 4px 1px 0; white-space: nowrap; }
.glossary dt { font-weight: 700; margin-top: 10px; font-family: "Noto Serif TC", Georgia, serif; }
.glossary dd { color: #5d564a; font-size: 14px; }
.disclaimer { color: #a89f8c; font-size: 12px; margin-top: 8px;
              border-top: 1px solid #c9c0ae; padding-top: 10px; }
.stockname { font-weight: 700; }
.code { color: #8a8170; font-size: 12px; }
"""

THEMES = {
    "terminal": {"label": "A 深色金融終端風", "subtitle": "深底 · 等寬數字 · 霓虹強調,像看盤終端機", "css": TERMINAL},
    "dashboard": {"label": "B 現代亮色儀表板風", "subtitle": "漸層橫幅 · 圓角卡片 · 柔和陰影,像 SaaS 後台", "css": DASHBOARD},
    "magazine": {"label": "C 財經雜誌風", "subtitle": "米白紙感 · 襯線標題 · 雙線框,像財經週刊", "css": MAGAZINE},
}
