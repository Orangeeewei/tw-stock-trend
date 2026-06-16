"""TWSE(上市)與 TPEX(上櫃)資料抓取:每日收盤行情、三大法人買賣超、月營收(含產業別)。"""
import json
import re
import ssl
import time
import urllib.parse
import urllib.request

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}

# TPEX 部分主機的憑證缺 Subject Key Identifier,過不了 Python 3.13+ 的
# VERIFY_X509_STRICT;關掉 strict 旗標但保留一般憑證驗證。
SSL_CTX = ssl.create_default_context()
SSL_CTX.verify_flags &= ~ssl.VERIFY_X509_STRICT

MI_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALLBUT0999&response=json"
T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86?date={date}&selectType=ALLBUT0999&response=json"
REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"

TPEX_QUOTES_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date={date}&response=json"
TPEX_T86_URL = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=AL&date={date}&response=json"
TPEX_REVENUE_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"

STOCK_ID_RE = re.compile(r"^[1-9]\d{3}$")  # 4 碼且不以 0 開頭 = 一般個股(排除 ETF)


class NoDataError(Exception):
    """資料源以轉址回應(307 等):無資料或暫時擋這個 IP,重試無益。"""


def get_json(url, retries=3):
    """指數退避重試:TPEX 的 Cloudflare 對機房 IP 偶發 525,等一下通常會過。
    轉址(3xx)代表「該日無資料」或「IP 暫時被擋」,立刻放棄不浪費時間退避。"""
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if 300 <= e.code < 400:
                raise NoDataError(f"HTTP {e.code}") from e
            if i == retries - 1:
                raise
            time.sleep(5 * 2 ** i)
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(5 * 2 ** i)  # 5, 10 秒


def parse_num(s):
    if s is None:
        return None
    s = str(s).replace(",", "").strip()
    if s in ("", "--", "---", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fetch_quotes(date):
    """回傳 (taiex_close, [{stock_id, name, close, high, low, volume, value}]),非交易日回傳 None。"""
    d = get_json(MI_INDEX_URL.format(date=date))
    if d.get("stat") != "OK":
        return None

    taiex = None
    quote_table = None
    for t in d.get("tables", []):
        fields = t.get("fields", [])
        if not fields:
            continue
        if fields[0] == "指數" and taiex is None:
            for row in t["data"]:
                if row[0] == "發行量加權股價指數":
                    taiex = parse_num(row[1])
                    break
        if fields[0] == "證券代號" and "收盤價" in fields:
            quote_table = t
    if quote_table is None:
        # stat 是 OK 卻找不到行情表 = 回應格式改變,要報錯而不是當成假日
        raise ValueError(f"TWSE MI_INDEX 回應格式改變,找不到行情表(date={date})")

    f = quote_table["fields"]
    i_id, i_name = f.index("證券代號"), f.index("證券名稱")
    i_vol, i_val = f.index("成交股數"), f.index("成交金額")
    i_high, i_low, i_close = f.index("最高價"), f.index("最低價"), f.index("收盤價")

    rows = []
    for r in quote_table["data"]:
        sid = r[i_id].strip()
        if not STOCK_ID_RE.match(sid):
            continue
        close = parse_num(r[i_close])
        if close is None:
            continue
        rows.append({
            "stock_id": sid,
            "name": r[i_name].strip(),
            "close": close,
            "high": parse_num(r[i_high]) or close,
            "low": parse_num(r[i_low]) or close,
            "volume": int(parse_num(r[i_vol]) or 0),
            "value": int(parse_num(r[i_val]) or 0),
        })
    return taiex, rows


def fetch_t86(date):
    """回傳 [{stock_id, foreign_net, trust_net}](單位:股),非交易日回傳 None。"""
    d = get_json(T86_URL.format(date=date))
    if d.get("stat") != "OK":
        return None
    f = d["fields"]
    i_id = f.index("證券代號")
    i_foreign = f.index("外陸資買賣超股數(不含外資自營商)")
    i_trust = f.index("投信買賣超股數")
    rows = []
    for r in d["data"]:
        sid = r[i_id].strip()
        if not STOCK_ID_RE.match(sid):
            continue
        rows.append({
            "stock_id": sid,
            "foreign_net": int(parse_num(r[i_foreign]) or 0),
            "trust_net": int(parse_num(r[i_trust]) or 0),
        })
    return rows


def _slash_date(date):
    """YYYYMMDD → YYYY/MM/DD(TPEX 用)。"""
    return f"{date[:4]}/{date[4:6]}/{date[6:]}"


def fetch_quotes_tpex(date):
    """上櫃股票行情。回傳 [{stock_id, name, close, high, low, volume, value}];
    該日明確無資料(表格存在但 0 列)回傳 None;格式改變則拋錯。"""
    d = get_json(TPEX_QUOTES_URL.format(date=_slash_date(date)))
    table = None
    for t in d.get("tables", []):
        fields = t.get("fields", [])
        if fields and fields[0] == "代號" and "收盤" in fields:
            table = t
            break
    if table is None:
        raise ValueError(f"TPEX dailyQuotes 回應格式改變,找不到行情表(date={date})")
    if not table.get("data"):
        return None  # 表格在但 0 列 = 該日確定無資料(假日或單邊無交易)

    f = table["fields"]
    i_id, i_name = f.index("代號"), f.index("名稱")
    i_close, i_high, i_low = f.index("收盤"), f.index("最高"), f.index("最低")
    i_vol, i_val = f.index("成交股數"), f.index("成交金額(元)")

    rows = []
    for r in table["data"]:
        sid = r[i_id].strip()
        if not STOCK_ID_RE.match(sid):
            continue
        close = parse_num(r[i_close])
        if close is None:
            continue
        rows.append({
            "stock_id": sid,
            "name": r[i_name].strip(),
            "close": close,
            "high": parse_num(r[i_high]) or close,
            "low": parse_num(r[i_low]) or close,
            "volume": int(parse_num(r[i_vol]) or 0),
            "value": int(parse_num(r[i_val]) or 0),
        })
    return rows


def fetch_t86_tpex(date):
    """上櫃三大法人買賣超。回傳 [{stock_id, foreign_net, trust_net}],非交易日回傳 None。

    TPEX 欄位名稱重複(七組 買進/賣出/買賣超),只能用固定位置:
    idx 2-4 外陸資(不含外資自營) / 11-13 投信。以「買進-賣出=買賣超」驗證位置沒跑掉。
    """
    d = get_json(TPEX_T86_URL.format(date=_slash_date(date)))
    tables = d.get("tables", [])
    if not tables or (tables[0].get("fields") or [None])[0] != "代號":
        raise ValueError(f"TPEX 三大法人回應格式改變(date={date})")
    if not tables[0].get("data"):
        return None
    table = tables[0]

    I_FOREIGN_BUY, I_FOREIGN_SELL, I_FOREIGN_NET = 2, 3, 4
    I_TRUST_BUY, I_TRUST_SELL, I_TRUST_NET = 11, 12, 13
    for r in table["data"][:5]:
        fb, fs, fn = (parse_num(r[i]) or 0 for i in (I_FOREIGN_BUY, I_FOREIGN_SELL, I_FOREIGN_NET))
        tb, ts, tn = (parse_num(r[i]) or 0 for i in (I_TRUST_BUY, I_TRUST_SELL, I_TRUST_NET))
        if fb - fs != fn or tb - ts != tn:
            raise ValueError(f"TPEX 三大法人欄位位置改變,請檢查 API 格式(date={date})")

    rows = []
    for r in table["data"]:
        sid = r[0].strip()
        if not STOCK_ID_RE.match(sid):
            continue
        rows.append({
            "stock_id": sid,
            "foreign_net": int(parse_num(r[I_FOREIGN_NET]) or 0),
            "trust_net": int(parse_num(r[I_TRUST_NET]) or 0),
        })
    return rows


# ── 美股(S&P 500):Yahoo Finance chart API,價格自帶股息還原 ──
SP500_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range}&interval=1d"


def fetch_sp500():
    """S&P 500 成分股。回傳 [{symbol, name, sector}](symbol 已轉 Yahoo 格式)。"""
    import csv
    import io
    req = urllib.request.Request(SP500_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
        text = resp.read().decode("utf-8")
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        sym = row["Symbol"].strip().replace(".", "-")  # BRK.B → BRK-B
        if sym:
            out.append({"symbol": sym, "name": row["Security"].strip(),
                        "sector": row["GICS Sector"].strip()})
    if len(out) < 400:
        raise ValueError(f"S&P 500 成分股清單異常,只有 {len(out)} 檔")
    return out


def fetch_us_chart(symbol, range_="3mo"):
    """單一美股的日線(股息還原後)。回傳 [(YYYYMMDD, adjclose, high, volume, value)]。
    每次抓 3 個月視窗,所以漏抓的日期會自動補齊,不需要 fetched 標記。"""
    import time as _t
    d = get_json(YAHOO_CHART_URL.format(symbol=urllib.parse.quote(symbol), range=range_))
    result = d.get("chart", {}).get("result")
    if not result:
        return []
    r = result[0]
    ts = r.get("timestamp") or []
    q = r["indicators"]["quote"][0]
    adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose") or q["close"]
    rows = []
    for i, t in enumerate(ts):
        c, ac, h, v = q["close"][i], adj[i], q["high"][i], q["volume"][i]
        if c is None or ac is None or not v:
            continue   # v 為 0/None = 該日無成交(假日佔位或盤中未定的當日 K 棒),跳過
        ds = _t.strftime("%Y%m%d", _t.gmtime(t))
        factor = ac / c if c else 1
        rows.append((ds, round(ac, 4), round((h or c) * factor, 4), int(v or 0),
                     int((v or 0) * c)))
    return rows


def fetch_us_index(range_="6mo"):
    """S&P 500 指數(^GSPC)收盤序列。回傳 [(YYYYMMDD, close)]。"""
    rows = fetch_us_chart("^GSPC", range_)
    return [(ds, c) for ds, c, _, _, _ in rows]


RISK_URLS = {
    "twse_disposal": "https://openapi.twse.com.tw/v1/announcement/punish",
    "twse_attention": "https://openapi.twse.com.tw/v1/announcement/notice",
    "tpex_disposal": "https://www.tpex.org.tw/openapi/v1/tpex_disposal_information",
    "tpex_attention": "https://www.tpex.org.tw/openapi/v1/tpex_trading_warning_information",
}


def _roc_to_date(s):
    """'115/06/02' 或 '1150602' → date;解析失敗回 None。"""
    import datetime
    s = s.strip().replace("/", "")
    if len(s) != 7 or not s.isdigit():
        return None
    try:
        return datetime.date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:7]))
    except ValueError:
        return None


def fetch_risk_lists(today):
    """回傳 (處置中股票 set, 今日注意股票 set),上市+上櫃、僅 4 碼個股。
    任一來源失敗只略過該來源(風險清單缺漏不該擋掉整份報告)。"""
    disposal, attention = set(), set()

    for key, code_field, period_field in (
        ("twse_disposal", "Code", "DispositionPeriod"),
        ("tpex_disposal", "SecuritiesCompanyCode", "DispositionPeriod"),
    ):
        try:
            for r in get_json(RISK_URLS[key]):
                sid = r.get(code_field, "").strip()
                if not STOCK_ID_RE.match(sid):
                    continue
                parts = r.get(period_field, "").replace("～", "~").split("~")
                if len(parts) == 2:
                    d1, d2 = _roc_to_date(parts[0]), _roc_to_date(parts[1])
                    if d1 and d2 and d1 <= today <= d2:
                        disposal.add(sid)
        except Exception as e:
            print(f"處置股清單抓取失敗({key}):{e}", flush=True)

    for key, code_field in (("twse_attention", "Code"), ("tpex_attention", "SecuritiesCompanyCode")):
        try:
            for r in get_json(RISK_URLS[key]):
                sid = r.get(code_field, "").strip()
                if STOCK_ID_RE.match(sid):
                    attention.add(sid)
        except Exception as e:
            print(f"注意股清單抓取失敗({key}):{e}", flush=True)

    return disposal, attention


NAMES_EN_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"


# TWSE 公司基本資料(t187ap03_L)的「產業別」是數字代碼(如 "17"=金融保險業),
# 與月營收端點(t187ap05_L)的中文名稱不同。banks 等無月營收個股會退到本端點當 fallback,
# 若不翻譯,排名表會出現「17」這種裸代碼並自成一桶。名稱對齊營收端點用語以利併桶。
TWSE_INDUSTRY_CODES = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙工業",
    "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業", "14": "建材營造",
    "15": "航運業", "16": "觀光餐旅", "17": "金融保險業", "18": "貿易百貨",
    "19": "綜合", "20": "其他", "21": "化學工業", "22": "生技醫療業",
    "23": "油電燃氣業", "24": "半導體業", "25": "電腦及週邊設備業", "26": "光電業",
    "27": "通信網路業", "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業",
    "31": "其他電子業", "32": "文化創意業", "33": "農業科技", "35": "綠能環保",
    "36": "數位雲端", "37": "運動休閒", "38": "居家生活", "91": "存託憑證",
}


def fetch_names_en():
    """上市公司官方英文簡稱與產業別(上櫃端點無英文欄位,該部分保留中文)。
    回傳 {stock_id: {"en": 英文簡稱, "industry": 產業別}};供英文版與『缺營收個股』的產業 fallback。
    本端點產業別為數字代碼,以 TWSE_INDUSTRY_CODES 翻成中文名(對齊營收端點用語);未知代碼丟棄避免裸碼。"""
    out = {}
    for r in get_json(NAMES_EN_URL):
        sid = r.get("公司代號", "").strip()
        if not STOCK_ID_RE.match(sid):
            continue
        en = r.get("英文簡稱", "").strip()
        ind = TWSE_INDUSTRY_CODES.get(r.get("產業別", "").strip(), "")
        if en or ind:
            out[sid] = {"en": en, "industry": ind}
    return out


# ── 除權息還原:原始收盤價不動,於讀取層用「向後還原因子」消除除權息造成的假跌幅 ──
# TWSE TWT49U 直接給「除權息前收盤價/參考價」→ 因子 = 參考價/前收盤(零公式風險,2 年一次抓)。
# TPEX openapi 僅未來~2 個月、無參考價 → 用 DB 前收盤 + 股利金額依官方參考價公式重建(即日起向前覆蓋)。
DIV_TWSE_URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U?startDate={start}&endDate={end}&response=json"
DIV_TPEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost"


def _roc_ymd(s):
    """'114年06月02日' 或 '1140602' → 'YYYYMMDD';失敗回 None。"""
    digits = re.findall(r"\d+", str(s))
    if len(digits) == 3:
        y, m, d = digits
    elif len(digits) == 1 and len(digits[0]) == 7:
        s2 = digits[0]
        y, m, d = s2[:3], s2[3:5], s2[5:7]
    else:
        return None
    try:
        return f"{int(y) + 1911:04d}{int(m):02d}{int(d):02d}"
    except ValueError:
        return None


def _div_factor(ref, pre):
    """參考價/前收盤 → 還原因子;僅接受 (0.5,1] 的合理除權息(濾掉減資/分割/髒值)。"""
    if not pre or pre <= 0 or ref is None or ref <= 0:
        return None
    f = ref / pre
    if 0.5 < f <= 1.0001:
        return round(min(f, 1.0), 6)
    return None


def fetch_dividends_twse(start, end):
    """TWSE 除權息事件。回傳 {stock_id: [(ex_date, factor), ...]}。start/end 為 YYYYMMDD。"""
    d = get_json(DIV_TWSE_URL.format(start=start, end=end))
    if d.get("stat") != "OK" or not d.get("data"):
        return {}
    f = d["fields"]
    i_date, i_id = f.index("資料日期"), f.index("股票代號")
    i_pre, i_ref = f.index("除權息前收盤價"), f.index("除權息參考價")
    out = {}
    for r in d["data"]:
        sid = r[i_id].strip()
        if not STOCK_ID_RE.match(sid):
            continue
        ex = _roc_ymd(r[i_date])
        factor = _div_factor(parse_num(r[i_ref]), parse_num(r[i_pre]))
        if ex and factor is not None:
            out.setdefault(sid, []).append((ex, factor))
    return out


def fetch_dividends_tpex_raw():
    """TPEX 除權息預告(未來~2 個月 + 近期)。回傳 [(ex_date, sid, cash, stock_ratio, subs_ratio, subs_price)]。
    無前收盤/參考價,需配合 DB 前收盤用官方參考價公式重建(見 reconstruct_tpex_factor)。"""
    rows = []
    for r in get_json(DIV_TPEX_URL):
        sid = (r.get("SecuritiesCompanyCode") or "").strip()
        if not STOCK_ID_RE.match(sid):
            continue
        ex = _roc_ymd(r.get("ExRrightsExDividendDate"))
        if not ex:
            continue
        cash = parse_num(r.get("CashDividend")) or 0.0
        stock_ratio = parse_num(r.get("StockDividendRatio")) or 0.0
        subs_ratio = parse_num(r.get("SubscriptionRatioToNewSharesIssued")) or 0.0
        subs_price = parse_num(r.get("SubscriptionPricePerShare")) or 0.0
        rows.append((ex, sid, cash, stock_ratio, subs_ratio, subs_price))
    return rows


def reconstruct_tpex_factor(pre_close, cash, stock_ratio, subs_ratio, subs_price):
    """官方除權息參考價公式 → 還原因子。比例皆為「每股」。
    參考價 =(前收盤 - 現金股利 + 現增認購率×認購價)/(1 + 無償配股率 + 現增認購率)。"""
    denom = 1.0 + stock_ratio + subs_ratio
    if not pre_close or pre_close <= 0 or denom <= 0:
        return None
    ref = (pre_close - cash + subs_ratio * subs_price) / denom
    return _div_factor(ref, pre_close)


def revenue_publish_date(month_roc):
    """月營收『資料年月』(ROC 'YYYMM',如 11505=2026/05)→ 公布截止日 YYYYMMDD。
    台股規定每月營收須於次月 10 日前公布,故回測在某日 D 只能採 publish_date<=D 的營收
    (避免用到當時尚未公布的數字)。解析失敗回 None。"""
    s = str(month_roc).strip()
    if len(s) < 5 or not s.isdigit():
        return None
    yyy, mm = int(s[:-2]) + 1911, int(s[-2:])
    if not 1 <= mm <= 12:
        return None
    ny, nm = (yyy + 1, 1) if mm == 12 else (yyy, mm + 1)
    return f"{ny:04d}{nm:02d}10"


def fetch_revenue():
    """最新月營收彙總(上市 + 上櫃)。回傳 {stock_id: {name, industry, yoy, mom, month}}。"""
    out = {}
    for url in (REVENUE_URL, TPEX_REVENUE_URL):
        for r in get_json(url):
            sid = r.get("公司代號", "").strip()
            if not STOCK_ID_RE.match(sid):
                continue
            out[sid] = {
                "name": r.get("公司名稱", "").strip(),
                "industry": r.get("產業別", "").strip() or "其他",
                "yoy": parse_num(r.get("營業收入-去年同月增減(%)")),
                "mom": parse_num(r.get("營業收入-上月比較增減(%)")),
                "month": r.get("資料年月", "").strip(),
            }
    return out
