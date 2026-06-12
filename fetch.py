"""TWSE(上市)與 TPEX(上櫃)資料抓取:每日收盤行情、三大法人買賣超、月營收(含產業別)。"""
import json
import re
import ssl
import time
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
        return None

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
    """上櫃股票行情。回傳 [{stock_id, name, close, high, low, volume, value}],非交易日回傳 None。"""
    d = get_json(TPEX_QUOTES_URL.format(date=_slash_date(date)))
    table = None
    for t in d.get("tables", []):
        fields = t.get("fields", [])
        if fields and fields[0] == "代號" and "收盤" in fields:
            table = t
            break
    if table is None or not table.get("data"):
        return None

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
    if not tables or not tables[0].get("data"):
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
