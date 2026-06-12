"""SQLite 儲存層。"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "market.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    date TEXT, stock_id TEXT, name TEXT,
    close REAL, high REAL, low REAL,
    volume INTEGER, value INTEGER,
    PRIMARY KEY (date, stock_id)
);
CREATE TABLE IF NOT EXISTS inst (
    date TEXT, stock_id TEXT,
    foreign_net INTEGER, trust_net INTEGER,
    PRIMARY KEY (date, stock_id)
);
CREATE TABLE IF NOT EXISTS taiex (
    date TEXT PRIMARY KEY, close REAL
);
CREATE TABLE IF NOT EXISTS fetched (
    date TEXT, market TEXT,
    PRIMARY KEY (date, market)
);
"""


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(prices)")]
    if "market" not in cols:
        conn.execute("ALTER TABLE prices ADD COLUMN market TEXT DEFAULT 'twse'")
    # 舊資料庫只有上市資料:把既有日期標記為 twse 已抓
    conn.execute("INSERT OR IGNORE INTO fetched SELECT date, 'twse' FROM taiex")
    conn.commit()
    return conn


def has_date(conn, date, market="twse"):
    return conn.execute("SELECT 1 FROM fetched WHERE date=? AND market=?", (date, market)).fetchone() is not None


def mark_holiday(conn, date):
    """非交易日永久標記,之後的執行不再重查。"""
    conn.execute("INSERT OR IGNORE INTO fetched VALUES (?, 'holiday')", (date,))
    conn.commit()


def save_day(conn, date, taiex_close, quotes, t86, market="twse"):
    conn.executemany(
        "INSERT OR REPLACE INTO prices (date, stock_id, name, close, high, low, volume, value, market) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [(date, q["stock_id"], q["name"], q["close"], q["high"], q["low"], q["volume"], q["value"], market)
         for q in quotes],
    )
    if t86:
        conn.executemany(
            "INSERT OR REPLACE INTO inst VALUES (?,?,?,?)",
            [(date, r["stock_id"], r["foreign_net"], r["trust_net"]) for r in t86],
        )
    if taiex_close is not None:
        conn.execute("INSERT OR REPLACE INTO taiex VALUES (?,?)", (date, taiex_close))
    conn.execute("INSERT OR IGNORE INTO fetched VALUES (?,?)", (date, market))
    conn.commit()


def trading_dates(conn):
    return [r[0] for r in conn.execute("SELECT date FROM taiex ORDER BY date")]


def load_prices(conn):
    """回傳 {stock_id: {"name": str, "market": str, "rows": [(date, close, high, volume, value), ...]}},日期升冪。"""
    out = {}
    cur = conn.execute(
        "SELECT stock_id, name, market, date, close, high, volume, value FROM prices ORDER BY stock_id, date")
    for sid, name, market, date, close, high, vol, val in cur:
        s = out.setdefault(sid, {"name": name, "market": market, "rows": []})
        s["name"] = name      # 取最新名稱
        s["market"] = market
        s["rows"].append((date, close, high, vol, val))
    return out


def load_inst(conn):
    """回傳 {stock_id: [(date, foreign_net, trust_net), ...]},日期升冪。"""
    out = {}
    cur = conn.execute("SELECT stock_id, date, foreign_net, trust_net FROM inst ORDER BY stock_id, date")
    for sid, date, fn, tn in cur:
        out.setdefault(sid, []).append((date, fn, tn))
    return out


def load_taiex(conn):
    return [(r[0], r[1]) for r in conn.execute("SELECT date, close FROM taiex ORDER BY date")]
