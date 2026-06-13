"""報告多語字典:zh(繁中)/ en(英文)× tw(台股)/ us(美股)。

reasons 與 parts 在 analyze.py 以結構化 key 產生,這裡負責變成人話。
"""

REASONS = {
    "zh": {
        "trust_streak": "投信連買 {v} 天",
        "trust_net5": "投信 5 日買超 {v:,} 張",
        "foreign5": "外資 5 日買超 {v:,} 張",
        "yoy": "營收年增 {v:.0f}%",
        "off_high": "距 60 日高點 {v:.0f}%",
        "vol": "交易量放大至均量 {v:.1f} 倍",
        "ma3": "站上 5/10/20 日均線",
        "spike": "🔥 爆大量:今日量達均量 {v:.1f} 倍",
        "attention": "⚠️ 注意股",
        "ret5": "近 5 日反彈 {v:+.1f}%",
        "beat5": "5 日走勢強於同業",
    },
    "en": {
        "trust_streak": "Trust funds buying {v} days straight",
        "trust_net5": "Trust funds +{v:,} lots in 5d",
        "foreign5": "Foreign investors +{v:,} lots in 5d",
        "yoy": "Revenue {v:+.0f}% YoY",
        "off_high": "{v:.0f}% off 60-day high",
        "vol": "Volume {v:.1f}× its 20d average",
        "ma3": "Above the 5/10/20-day MAs",
        "spike": "🔥 Volume spike: {v:.1f}× the 20d average today",
        "attention": "⚠️ Exchange watchlist",
        "ret5": "{v:+.1f}% rebound in 5d",
        "beat5": "Outpacing sector over 5d",
    },
}

PART_LABELS = {
    "zh": {"industry": "產業", "inst": "法人", "revenue": "營收",
           "level": "位階", "vol": "交易量", "ma3": "站上三線", "momentum": "動能"},
    "en": {"industry": "Sector", "inst": "Institutions", "revenue": "Revenue",
           "level": "Level", "vol": "Volume", "ma3": "3 MAs", "momentum": "Momentum"},
}

# 「查個股」搜尋框文案;字串會內嵌進報告頁的 <script> 給前端 JS 用(故含 {rank} 等佔位符以 JS 取代)。
# 以 (market, lang) 為鍵(同 GLOSSARY):台股/美股關卡門檻不同(低價、流動性、低基期 -10%/-8%、
# 甦醒條件、每產業上限 5/4、美股無法人與處置股),文案必須跟著正確,不能只翻譯。
_LOOKUP_BASE = {
    "zh": {
        "title": "🔍 查個股 — 它現在幾分?為什麼不在榜上?",
        "hint": "輸入股票代號或名稱,看它在最新交易日的進場分數,以及為什麼還沒進補漲候選榜。資料為收盤後計算,僅供參考、非投資建議。",
        "placeholder": "輸入代號或名稱,例:2330 或 台積電",
        "not_found": "查無「{q}」。請輸入 4 碼代號或股名再試。",
        "score_label": "進場分數",
        "no_score": "未評分",
        "on_leader": "🏆 它在「強勢領頭羊」榜上(第 {rank} 名)——已接近 60 日新高、走勢強過同業。補漲候選找的是「還沒漲」的股票,所以它不會出現在補漲榜。",
        "on_candidate": "✅ 它就在「補漲候選」榜上(第 {rank} 名)!往下捲到第③區可看完整資料與走勢圖。",
        "not_on_intro": "目前不在補漲候選榜,原因:",
        "filtered_intro": "這檔沒有被系統評分,原因:",
        "status_low_price": "股價低於 10 元。低價股波動與風險偏高,系統一律不納入評分。",
        "status_illiquid": "近 20 日平均成交值不足 5 千萬,流動性太低,系統不納入評分(怕買賣不掉)。",
        "status_insufficient": "上市/上櫃時間還太短、歷史資料不足 21 個交易日,暫時無法評分。",
        "block_disposal": "它目前是處置股(被交易所列為分盤管制、交易受限),已從候選名單直接排除。",
        "block_industry_cold": "所屬產業不在全市場前 8 強。補漲策略只在「現在資金在流入」的熱門產業裡挑股,冷門產業就算個股不錯也先略過。",
        "block_not_lagging": "在同產業裡它的漲幅不算落後(甚至領先)。補漲找的是「同產業強、但自己還沒跟上」的落後股;它已經跟上了,就不算補漲對象。",
        "block_high_too_close": "離 60 日高點太近(不到 -10%),不算低基期,往上空間有限,不符合「便宜的落後股」設定。",
        "block_not_waking": "還沒出現「甦醒」訊號:最近量沒明顯放大、法人也沒進場。系統會等到有人氣(量增或法人買)才把它列入,避免買在沒人理的股票。",
        "block_capped": "其實它已符合所有條件,但同產業已收錄較高分的個股(每產業最多 5 檔),或被擠出前 20 名,這次才沒列出。分數夠高的話下次很可能上榜。",
        "metric_off_high": "距 60 日高",
        "metric_vol": "量能(5/20 日)",
        "metric_industry": "所屬產業",
    },
    "en": {
        "title": "🔍 Look up a stock — its score & why it's not listed",
        "hint": "Type a ticker or name to see its latest entry score and why it isn't a laggard candidate yet. Computed after the close; for reference only, not investment advice.",
        "placeholder": "Ticker or name, e.g. 2330 or TSMC",
        "not_found": "No match for “{q}”. Try a 4-digit ticker or the name.",
        "score_label": "Entry score",
        "no_score": "Not scored",
        "on_leader": "🏆 It's on the “Sector leaders” list (#{rank}) — already near its 60-day high and outpacing peers. The laggard list is for stocks that haven't moved yet, so it won't appear there.",
        "on_candidate": "✅ It IS on the laggard-candidate list (#{rank})! Scroll to section ③ for the full row and chart.",
        "not_on_intro": "Not a laggard candidate right now, because:",
        "filtered_intro": "This stock isn't scored, because:",
        "status_low_price": "Price is below NT$10. Penny stocks are too volatile/risky, so the system never scores them.",
        "status_illiquid": "20-day average turnover is under NT$50M — too illiquid to score (hard to get in and out).",
        "status_insufficient": "Listed too recently — fewer than 21 trading days of history, can't score yet.",
        "block_disposal": "It's currently under a disposal measure (call-auction / restricted trading), so it's excluded from the candidate list.",
        "block_industry_cold": "Its sector isn't in the market's top 8. The laggard strategy only picks from hot sectors money is flowing into.",
        "block_not_lagging": "Within its sector it isn't actually lagging (it may even be leading). The list targets stocks that trail a strong sector; this one has already caught up.",
        "block_high_too_close": "Too close to its 60-day high (less than -10% below it) — not a low base, limited room to run.",
        "block_not_waking": "No “waking up” signal yet: volume hasn't expanded and institutions aren't buying. The system waits for interest before listing it.",
        "block_capped": "It actually meets every rule, but its sector already filled its quota (max 5 per sector) or it fell outside the top 20 this time. With a high enough score it'll likely list next time.",
        "metric_off_high": "Off 60d high",
        "metric_vol": "Volume (5/20d)",
        "metric_industry": "Sector",
    },
}

# 美股覆寫:S&P 500、價格 USD、門檻 $5 / $1,000 萬美元、低基期 -8%、每產業上限 4、
# 無法人(甦醒改看量增或近 5 日轉正)、無處置股、無上櫃。其餘沿用 base。
_LOOKUP_US_OVERRIDE = {
    "zh": {
        "title": "🔍 查個股 — 它現在幾分?為什麼不在榜上?",
        "hint": "輸入美股代號或名稱,看它在最新交易日的進場分數,以及為什麼還沒進補漲候選榜。資料為收盤後計算,僅供參考、非投資建議。",
        "placeholder": "輸入代號或名稱,例:AAPL 或 蘋果",
        "not_found": "查無「{q}」。請輸入美股代號(如 AAPL)或名稱再試。",
        "on_candidate": "✅ 它就在「補漲候選」榜上(第 {rank} 名)!往下捲到第③區可看完整資料與走勢圖。",
        "status_low_price": "股價低於 5 美元。低價股波動與風險偏高,系統一律不納入評分。",
        "status_illiquid": "近 20 日平均成交值不足 1,000 萬美元,流動性太低,系統不納入評分。",
        "status_insufficient": "掛牌時間還太短、歷史資料不足 21 個交易日,暫時無法評分。",
        "block_high_too_close": "離 60 日高點太近(不到 -8%),不算低基期,往上空間有限,不符合「便宜的落後股」設定。",
        "block_not_waking": "還沒出現「甦醒」訊號:最近量沒明顯放大、近 5 日股價也還沒回升(美股無法人資料,改看價量)。系統會等到有人氣再把它列入。",
        "block_capped": "其實它已符合所有條件,但同產業已收錄較高分的個股(美股每產業最多 4 檔),或被擠出前 20 名,這次才沒列出。分數夠高的話下次很可能上榜。",
    },
    "en": {
        "hint": "Type a US ticker or name to see its latest entry score and why it isn't a laggard candidate yet. Computed after the close; for reference only, not investment advice.",
        "placeholder": "Ticker or name, e.g. AAPL or Apple",
        "not_found": "No match for “{q}”. Try a US ticker (e.g. AAPL) or the name.",
        "status_low_price": "Price is below $5. Penny stocks are too volatile/risky, so the system never scores them.",
        "status_illiquid": "20-day average turnover is under $10M — too illiquid to score.",
        "status_insufficient": "Listed too recently — fewer than 21 trading days of history, can't score yet.",
        "block_high_too_close": "Too close to its 60-day high (less than -8% below it) — not a low base, limited room to run.",
        "block_not_waking": "No “waking up” signal yet: volume hasn't expanded and the price hasn't started rebounding over the last 5 days (US has no institutional-flow data, so it uses price/volume). It waits for momentum before listing it.",
        "block_capped": "It actually meets every rule, but its sector already filled its quota (max 4 per sector for US) or it fell outside the top 20 this time. With a high enough score it'll likely list next time.",
    },
}

LOOKUP = {
    ("tw", "zh"): _LOOKUP_BASE["zh"],
    ("tw", "en"): _LOOKUP_BASE["en"],
    ("us", "zh"): {**_LOOKUP_BASE["zh"], **_LOOKUP_US_OVERRIDE["zh"]},
    ("us", "en"): {**_LOOKUP_BASE["en"], **_LOOKUP_US_OVERRIDE["en"]},
}


# GICS 11 大產業中文(台灣慣用譯名)
SECTOR_ZH = {
    "Information Technology": "資訊科技",
    "Health Care": "醫療保健",
    "Financials": "金融",
    "Consumer Discretionary": "非必需消費",
    "Consumer Staples": "必需性消費",
    "Industrials": "工業",
    "Energy": "能源",
    "Utilities": "公用事業",
    "Real Estate": "房地產",
    "Materials": "原物料",
    "Communication Services": "通訊服務",
}

# 美股常見公司的台灣慣用中文名(查無慣用譯名者保留英文)
US_STOCK_ZH = {
    "AAPL": "蘋果", "MSFT": "微軟", "NVDA": "輝達", "GOOGL": "Google(Alphabet)", "GOOG": "Google(Alphabet)",
    "AMZN": "亞馬遜", "META": "Meta", "TSLA": "特斯拉", "BRK-B": "波克夏", "AVGO": "博通",
    "JPM": "摩根大通", "V": "Visa", "MA": "萬事達卡", "UNH": "聯合健康", "XOM": "埃克森美孚",
    "CVX": "雪佛龍", "LLY": "禮來", "JNJ": "嬌生", "PG": "寶僑", "HD": "家得寶",
    "COST": "好市多", "WMT": "沃爾瑪", "KO": "可口可樂", "PEP": "百事", "MRK": "默克",
    "ABBV": "艾伯維", "PFE": "輝瑞", "ORCL": "甲骨文", "CRM": "Salesforce", "ADBE": "Adobe",
    "NFLX": "Netflix", "DIS": "迪士尼", "INTC": "英特爾", "AMD": "AMD", "QCOM": "高通",
    "TXN": "德州儀器", "MU": "美光", "AMAT": "應用材料", "IBM": "IBM", "CSCO": "思科",
    "BA": "波音", "CAT": "開拓重工", "DE": "迪爾", "MMM": "3M", "GE": "奇異航太",
    "HON": "漢威", "LMT": "洛克希德馬丁", "RTX": "雷神", "FDX": "聯邦快遞", "UPS": "UPS",
    "DAL": "達美航空", "UAL": "聯合航空", "F": "福特", "GM": "通用汽車",
    "GS": "高盛", "MS": "摩根士丹利", "BAC": "美國銀行", "WFC": "富國銀行", "C": "花旗",
    "SCHW": "嘉信理財", "BLK": "貝萊德", "SPGI": "標普全球", "MCO": "穆迪", "AXP": "美國運通",
    "PYPL": "PayPal", "SBUX": "星巴克", "NKE": "耐吉", "MCD": "麥當勞",
    "T": "AT&T", "VZ": "威訊", "TMUS": "T-Mobile", "CMCSA": "康卡斯特",
    "AMGN": "安進", "GILD": "吉利德", "BMY": "必治妥施貴寶", "TMO": "賽默飛世爾", "ABT": "亞培",
    "DHR": "丹納赫", "MDT": "美敦力", "ISRG": "直覺手術", "CVS": "CVS 健康", "CI": "信諾",
    "MO": "奧馳亞", "PM": "菲利普莫里斯", "CL": "高露潔", "KMB": "金百利克拉克",
    "GIS": "通用磨坊", "KHC": "卡夫亨氏", "MDLZ": "億滋", "HSY": "好時", "EL": "雅詩蘭黛",
    "TGT": "塔吉特", "LOW": "勞氏", "BKNG": "Booking", "MAR": "萬豪", "HLT": "希爾頓",
    "ABNB": "Airbnb", "UBER": "Uber", "CMG": "Chipotle 墨式燒烤", "YUM": "百勝餐飲",
    "DPZ": "達美樂", "LULU": "Lululemon", "EBAY": "eBay",
    "NOW": "ServiceNow", "INTU": "Intuit", "SNPS": "新思科技", "CDNS": "益華電腦",
    "KLAC": "科磊", "LRCX": "科林研發", "ADI": "亞德諾", "NXPI": "恩智浦", "MCHP": "微芯科技",
    "ON": "安森美", "MRVL": "邁威爾", "PANW": "Palo Alto Networks", "CRWD": "CrowdStrike",
    "FTNT": "Fortinet", "PLTR": "Palantir", "SMCI": "美超微", "DELL": "戴爾", "HPQ": "惠普",
    "HPE": "HPE", "WDC": "威騰電子", "STX": "希捷", "ANET": "Arista", "MSI": "摩托羅拉系統",
    "GLW": "康寧", "APH": "安費諾", "TEL": "泰科電子",
    "NEE": "新世代能源", "DUK": "杜克能源", "SO": "南方公司", "AEP": "美國電力",
    "COP": "康菲石油", "SLB": "斯倫貝謝", "OXY": "西方石油", "PSX": "菲利普斯 66",
    "VLO": "瓦萊羅能源", "MPC": "馬拉松石油", "KMI": "金德摩根", "HAL": "哈利伯頓",
    "FCX": "自由港礦業", "NEM": "紐曼礦業", "LIN": "林德", "APD": "空氣化工", "SHW": "宣偉",
    "DOW": "陶氏", "DD": "杜邦", "ECL": "藝康",
    "PLD": "普洛斯", "AMT": "美國電塔", "EQIX": "Equinix", "CCI": "冠城國際",
    "SPG": "西蒙地產", "PSA": "公共倉儲", "O": "Realty Income",
    "UNP": "聯合太平洋", "CSX": "CSX 運輸", "NSC": "諾福克南方", "WM": "廢棄物管理",
    "EMR": "艾默生電氣", "ETN": "伊頓", "ITW": "伊利諾工具", "PH": "派克漢尼汾",
    "GD": "通用動力", "NOC": "諾斯洛普格魯曼", "ADP": "ADP", "PAYX": "Paychex",
    "TRV": "旅行者保險", "AIG": "美國國際集團", "MET": "大都會人壽", "PRU": "保德信",
    "ALL": "好事達", "PGR": "前進保險", "CB": "安達", "COF": "第一資本", "USB": "合眾銀行",
    "PNC": "PNC 金融", "BK": "紐約梅隆銀行", "ICE": "洲際交易所", "CME": "芝商所",
    "NDAQ": "那斯達克", "MSCI": "MSCI", "ACN": "埃森哲", "CTSH": "高知特", "WDAY": "Workday",
    "REGN": "再生元", "VRTX": "福泰製藥", "MRNA": "莫德納", "BIIB": "百健",
    "ZTS": "碩騰", "SYK": "史賽克", "BSX": "波士頓科學", "EW": "愛德華生命科學",
    "HCA": "HCA 醫療", "MCK": "麥克森", "ELV": "Elevance 健康",
}


# 台股產業別英譯(證交所/櫃買分類)
TW_SECTOR_EN = {
    "水泥工業": "Cement", "食品工業": "Food", "塑膠工業": "Plastics", "紡織纖維": "Textiles",
    "電機機械": "Electric Machinery", "電器電纜": "Electrical & Cable", "化學工業": "Chemicals",
    "生技醫療業": "Biotech & Medical", "玻璃陶瓷": "Glass & Ceramics", "造紙工業": "Paper & Pulp",
    "鋼鐵工業": "Steel", "橡膠工業": "Rubber", "汽車工業": "Automotive", "半導體業": "Semiconductors",
    "電腦及週邊設備業": "Computers & Peripherals", "光電業": "Optoelectronics",
    "通信網路業": "Communications & Internet", "電子零組件業": "Electronic Components",
    "電子通路業": "Electronics Distribution", "資訊服務業": "IT Services",
    "其他電子業": "Other Electronics", "建材營造": "Construction", "航運業": "Shipping & Transport",
    "觀光餐旅": "Tourism & Hospitality", "金融保險業": "Financials & Insurance", "金融業": "Financials",
    "貿易百貨": "Trading & Department Stores", "油電燃氣業": "Oil, Gas & Utilities",
    "綜合": "Conglomerates", "其他": "Others", "存託憑證": "TDRs",
    "數位雲端": "Digital & Cloud", "居家生活": "Home Living", "綠能環保": "Green Energy",
    "運動休閒": "Sports & Leisure", "文化創意業": "Cultural & Creative", "農業科技": "AgriTech",
    "電子商務": "E-Commerce",
}


def display_name(market, lang, stock_id, name, names_en=None):
    """美股中文版用台灣慣用譯名;台股英文版用證交所官方英文簡稱(上櫃無英文名則保留中文)。"""
    if market == "us" and lang == "zh":
        return US_STOCK_ZH.get(stock_id, name)
    if market == "tw" and lang == "en" and names_en:
        return names_en.get(stock_id, name)
    return name


def display_sector(market, lang, sector):
    if market == "us" and lang == "zh":
        return SECTOR_ZH.get(sector, sector)
    if market == "tw" and lang == "en":
        return TW_SECTOR_EN.get(sector, sector)
    return sector


def fmt_reason(lang, r):
    key, *args = r
    t = REASONS[lang].get(key, key)
    return t.format(v=args[0]) if args else t


def fmt_parts(lang, parts):
    """各分項包成不可斷行的小段,只允許在「·」之間換行,避免分數欄擠成一直條。"""
    lab = PART_LABELS[lang]
    return " · ".join(f'<span class="pseg">{lab[k]} {pts}/{mx}</span>' for k, pts, mx in parts)


UI = {
    "zh": {
        "title": {"tw": "台股趨勢日報", "us": "美股趨勢日報"},
        "meta": {"tw": "資料日期:{date}(上市 + 上櫃,上櫃標示「櫃」)· 月營收資料:{rev}",
                 "us": "資料日期:{date}(S&P 500 成分股)· 價格已還原股息調整"},
        "index_name": {"tw": "加權指數", "us": "S&P 500"},
        "lang_switch": "English",
        "other_market": {"tw": "→ 美股版", "us": "→ 台股版"},
        "bull": "🟢 大盤多頭",
        "bull_body": " — {idx} {close:,.0f} 點,站在 60 日均線({ma60:,.0f})之上。白話:過去三個月買進的人平均是賺錢的,市場氣氛偏樂觀,補漲策略此時勝率較高。",
        "bear": "🔴 大盤空頭",
        "bear_body": " — {idx} {close:,.0f} 點,跌破 60 日均線({ma60:,.0f})。白話:市場整體在退潮,「還沒漲的股票」常常變成「接著跌的股票」,建議觀望、降低部位。",
        "nodata_banner": "資料不足 60 日,暫無法判斷大盤多空。",
        "stat_state": "大盤狀態", "stat_bull": "多頭", "stat_bear": "空頭",
        "stat_ma60": "60 日線 {v}", "stat_top_industry": "最強產業", "stat_top_suffix": "/ 20日",
        "stat_cands": "補漲候選 ≥70 分", "stat_cands_unit": "{n} 檔", "stat_none": "今日從缺",
        "s1_title": "① 資金往哪裡去 — 產業熱度排行",
        "s1_hint": "以各產業成分股近 20 日漲跌幅的中位數排名。連續多日排在前面的產業,就是現在市場資金集中的主流。",
        "s1_cols": ["排名", "產業", "20 日漲跌", "5 日漲跌", "今日成交佔比", "檔數", "連續前三"],
        "streak_days": "連 {n} 天", "streak_new": "今日進榜",
        "s2_title": "② 誰在帶頭衝 — 強勢產業領頭羊",
        "s2_hint": "熱門產業中已創(或逼近)60 日新高的股票。它們不是買進建議,而是「風向標」:領頭羊還在創新高,代表這個產業的行情還沒結束。點股票名稱可開啟完整技術圖(TradingView)。",
        "s2_cols": {"tw": ["股票", "產業", "收盤", "近 60 日走勢", "20 日漲跌", "距 60 日高", "投信連買", "營收年增"],
                    "us": ["股票", "產業", "收盤", "近 60 日走勢", "20 日漲跌", "距 60 日高", "5 日漲跌"]},
        "s2_empty": "今日無符合條件的領頭羊", "days_unit": "{n} 天",
        "s3_title": "③ 還沒漲的同業 — 補漲候選(核心)",
        "s3_hint": "條件:熱門產業 + 漲幅落後同業 + 離高點還有空間 + 已出現甦醒跡象。為了視野全面,同一產業最多收錄數檔,其他強勢產業的機會才看得到。進場分數越高,代表「產業對、{mid}」同時成立的程度越高。<b>70 分以上才值得認真研究。</b>點股票名稱可開啟完整技術圖。",
        "s3_mid": {"tw": "籌碼對、營收對、站上均線、量能放大", "us": "量能對、動能對、位置對"},
        "s3_cols": ["#", "股票", "產業", "收盤", "近 60 日走勢", "20 日漲跌", "進場分數", "白話理由"],
        "s3_empty": "今日無符合條件的補漲候選",
        "board_new": "🆕 新進榜", "board_streak": "連 {n} 天上榜",
        "industry_rank": "產業第 {n} 強", "peer": "同業",
        "s4_title": "④ 之前的候選表現如何 — 候選回顧",
        "s4_hint": "5/10/20 個交易日前的高分候選(70 分以上,不足則取前三),至今的實際報酬 vs 同期大盤。這一區是系統的成績單:如果高分候選長期沒贏過大盤,代表分數不值得信。",
        "s4_cols": ["回顧", "股票", "當時分數", "當時收盤", "最新收盤", "至今報酬", "平均 vs 大盤"],
        "s4_ago": "{n} 天前", "s4_market": "大盤", "s4_beat": "贏大盤", "s4_lose": "輸大盤",
        "glossary_title": "名詞白話解釋",
        "disclaimer": {"tw": "本報告由公開資料(臺灣證券交易所、證券櫃檯買賣中心)自動產生,僅供研究參考,不構成任何投資建議。補漲候選為「值得研究的名單」而非買進訊號,進場前請自行確認公司基本面與消息面。",
                       "us": "本報告由公開資料(Yahoo Finance、S&P 500 成分股清單)自動產生,僅供研究參考,不構成任何投資建議。補漲候選為「值得研究的名單」而非買進訊號。"},
    },
    "en": {
        "title": {"tw": "Taiwan Stock Trend Daily", "us": "US Stock Trend Daily"},
        "meta": {"tw": "Data as of {date} (TWSE + TPEX listed; OTC marked 櫃) · Monthly revenue: {rev}",
                 "us": "Data as of {date} (S&P 500 constituents) · Prices are dividend-adjusted"},
        "index_name": {"tw": "TAIEX", "us": "S&P 500"},
        "lang_switch": "中文",
        "other_market": {"tw": "→ US edition", "us": "→ Taiwan edition"},
        "bull": "🟢 Bull market",
        "bull_body": " — {idx} at {close:,.0f}, above its 60-day moving average ({ma60:,.0f}). Plainly: the average buyer of the past three months is in profit, sentiment is constructive, and catch-up plays have better odds.",
        "bear": "🔴 Bear market",
        "bear_body": " — {idx} at {close:,.0f}, below its 60-day moving average ({ma60:,.0f}). Plainly: the tide is going out — \"stocks that haven't risen yet\" tend to become \"stocks that fall next\". Stay cautious and keep positions small.",
        "nodata_banner": "Fewer than 60 days of data — market regime unavailable.",
        "stat_state": "Market state", "stat_bull": "Bull", "stat_bear": "Bear",
        "stat_ma60": "60-day MA {v}", "stat_top_industry": "Hottest sector", "stat_top_suffix": "/ 20d",
        "stat_cands": "Candidates ≥70 pts", "stat_cands_unit": "{n}", "stat_none": "none today",
        "s1_title": "① Where the Money Flows — Sector Heat Ranking",
        "s1_hint": "Sectors ranked by the median 20-day return of their members. A sector that stays near the top for days is where the market's money is concentrating.",
        "s1_cols": ["Rank", "Sector", "20d", "5d", "Value share", "Stocks", "Top-3 streak"],
        "streak_days": "{n} days", "streak_new": "new today",
        "s2_title": "② Who's Leading — Sector Leaders",
        "s2_hint": "Stocks in hot sectors at (or near) 60-day highs. Not buy ideas — they are the weather vane: as long as leaders keep making highs, the sector's run isn't over. Click a name for a full chart (TradingView).",
        "s2_cols": {"tw": ["Stock", "Sector", "Close", "60-day trend", "20d", "Off 60d high", "Trust streak", "Rev YoY"],
                    "us": ["Stock", "Sector", "Close", "60-day trend", "20d", "Off 60d high", "5d"]},
        "s2_empty": "No qualifying leaders today", "days_unit": "{n}d",
        "s3_title": "③ Laggards in Hot Sectors — Catch-up Candidates (Core)",
        "s3_hint": "Criteria: hot sector + trailing its peers + room below the high + early signs of waking up. For breadth, each sector contributes at most a few names, so other hot sectors stay visible. A higher entry score means more of \"right sector, {mid}\" hold at once. <b>Only scores of 70+ deserve real research.</b> Click a name for a full chart.",
        "s3_mid": {"tw": "right chips, right revenue, MAs reclaimed, volume picking up", "us": "right volume, right momentum, right level"},
        "s3_cols": ["#", "Stock", "Sector", "Close", "60-day trend", "20d", "Entry score", "Why (plain words)"],
        "s3_empty": "No qualifying candidates today",
        "board_new": "🆕 New on list", "board_streak": "{n} days on list",
        "industry_rank": "sector #{n}", "peer": "peers",
        "s4_title": "④ How Past Picks Did — Track Record",
        "s4_hint": "High-score candidates from 5/10/20 trading days ago (70+, else top three) and their returns since, versus the index. This is the system's report card: if high scorers don't beat the market over time, don't trust the score.",
        "s4_cols": ["Lookback", "Stock", "Score then", "Close then", "Latest close", "Return", "Avg vs index"],
        "s4_ago": "{n}d ago", "s4_market": "Index", "s4_beat": "beat index by", "s4_lose": "trailed index by",
        "glossary_title": "Glossary (plain words)",
        "disclaimer": {"tw": "Auto-generated from public data (TWSE, TPEX). For research only — not investment advice. Candidates are a research list, not buy signals.",
                       "us": "Auto-generated from public data (Yahoo Finance, S&P 500 constituents). For research only — not investment advice. Candidates are a research list, not buy signals."},
    },
}

GLOSSARY = {
    ("tw", "zh"): [
        ("投信連買", "投信 = 台灣的基金公司。他們買股票要寫報告、過內部審核,所以「連續好幾天買同一檔」通常代表做過功課、打算做一個波段,是台股最值得跟蹤的籌碼訊號。"),
        ("外資買超", "外國機構投資人買進比賣出多。外資部位大、動向慢,轉買往往是中期趨勢的開始。"),
        ("營收年增率(YoY)", "這個月營收跟去年同月比成長多少。正的代表公司生意越做越大,是最簡單可靠的基本面指標。"),
        ("距 60 日高", "現在股價離最近三個月最高點還有多遠。-20% 代表還在相對低的位置(低基期),補漲空間較大;但跌超過 -35% 要小心是不是公司本身出了問題。"),
        ("交易量放大", "最近 5 天平均成交量是過去 20 天平均的幾倍。超過 1.2 倍代表開始有人注意到這檔股票,「沉睡的股票醒了」。"),
        ("爆大量 🔥", "今天一天的成交量就達到 20 日均量的 2 倍以上,代表有大資金在進出。若伴隨股價上漲,常是波段啟動的訊號。"),
        ("站上三線", "收盤價同時站上 5 日、10 日、20 日均線。代表最近一週到一個月內買進的人平均都賺錢,上方少有套牢賣壓,股價比較容易續漲。"),
        ("60 日均線", "過去三個月所有買進者的平均成本。大盤站在它上面 = 多數人賺錢、願意續抱;跌破 = 多數人套牢、隨時想賣。"),
        ("注意股 ⚠️", "交易所認定近期交易異常(漲太兇、週轉率過高等)而公告周知的股票。不代表不能買,但波動風險明顯偏高,候選清單會標示警告。"),
        ("處置股", "異常情節更重、被改為人工管制撮合的股票,流動性大幅受限。處置期間內的股票已從本報告的候選與領頭羊中直接排除。"),
        ("連續上榜", "連續多天出現在候選清單。「新進榜」代表訊號剛成立;連續多天上榜卻一直不漲,反而要懷疑訊號是假的。"),
    ],
    ("tw", "en"): [
        ("Trust fund streak", "\"Trust funds\" are Taiwan's domestic mutual funds. Their buys go through research and compliance, so several consecutive days of buying the same stock usually means homework was done — the most reliable smart-money signal in this market."),
        ("Foreign net buying", "Foreign institutions bought more than they sold. Their positions are large and slow-moving; a turn to buying often marks the start of a medium-term trend."),
        ("Revenue YoY", "Taiwan companies report revenue monthly (rare globally). Positive year-over-year growth is the simplest reliable fundamental signal."),
        ("Off 60-day high", "How far the price sits below its 3-month high. Around -20% means a low base with catch-up room; below -35%, suspect something is genuinely wrong."),
        ("Volume surge", "5-day average volume vs the 20-day average. Above 1.2× means the sleeping stock is waking up."),
        ("Volume spike 🔥", "Today's volume alone is 2×+ the 20-day average — big money is moving. Paired with a rising price, it often marks the start of a swing move."),
        ("Above 3 MAs", "Close is above the 5-, 10- and 20-day moving averages at once: recent buyers are all in profit, so there's little overhead supply."),
        ("60-day moving average", "The average cost of everyone who bought in the past three months. Index above it = most holders in profit; below = most are trapped and eager to sell."),
        ("Watchlist ⚠️", "Flagged by the exchange for unusual trading (excessive moves or turnover). Not unbuyable, but clearly higher risk."),
        ("Disposition stocks", "Stocks moved to managed matching (trades every 5–20 minutes) for repeated abnormal trading. Excluded from this report's candidates entirely."),
        ("Days on list", "\"New on list\" means the signal just fired; many days on the list without a move is a reason for suspicion, not confidence."),
    ],
    ("us", "zh"): [
        ("產業輪動", "資金在 11 個 GICS 產業之間輪流移動。本報告追蹤錢「正在流入」哪個產業,再從那個產業裡找還沒漲的。"),
        ("距 60 日高", "現在股價離最近三個月最高點多遠。-15% 上下是有補漲空間的低基期;跌太深則要懷疑基本面。"),
        ("量能放大", "最近 5 天平均成交量是 20 天平均的幾倍,超過 1.2 倍代表開始有人進場。"),
        ("動能轉折", "近 5 日由跌轉漲、且走勢強於同產業,是落後股「開始動了」的訊號。"),
        ("60 日均線", "過去三個月買進者的平均成本,S&P 500 在其上為多頭、跌破為空頭,是本報告的總開關。"),
        ("與台股版的差異", "美股沒有台股的每日法人買賣超和月營收公開資料,所以評分只用價量結構;價格已自動還原股息。"),
    ],
    ("us", "en"): [
        ("Sector rotation", "Money rotates among the 11 GICS sectors. This report tracks where money is flowing in, then hunts the stocks in that sector that haven't moved yet."),
        ("Off 60-day high", "Distance below the 3-month high. Around -15% is a low base with room to catch up; much deeper, suspect the fundamentals."),
        ("Volume surge", "5-day average volume vs the 20-day average; above 1.2× means buyers are showing up."),
        ("Momentum turn", "A positive 5-day return that also beats the sector — the classic sign a laggard is waking up."),
        ("60-day moving average", "Average cost of the past three months' buyers. S&P 500 above it = bull regime; below = bear. This is the report's master switch."),
        ("vs the Taiwan edition", "The US lacks Taiwan's daily institutional flow and monthly revenue disclosures, so scoring here uses price/volume structure only. Prices are dividend-adjusted automatically."),
    ],
}
