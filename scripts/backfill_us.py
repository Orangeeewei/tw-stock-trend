"""一次性把美股(S&P 500 成分 + 指數)回補到約 2 年,供美股回測。
Yahoo chart API range=2y;GitHub runner 不被擋、需自訂 UA(fetch 已設)。每檔 sleep 0.25s。
用法:python3 scripts/backfill_us.py [--range 2y]
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import db       # noqa: E402
import fetch    # noqa: E402
import main     # noqa: E402


def run(range_="2y"):
    conn = db.connect()
    idx = fetch.fetch_us_index(range_)
    if idx:
        db.save_us_index(conn, idx)
        print(f"指數回補 {len(idx)} 日({idx[0][0]}~{idx[-1][0]})", flush=True)
    uni = main._us_universe()
    done = fail = 0
    for u in uni:
        try:
            rows = fetch.fetch_us_chart(u["symbol"], range_)
            if rows:
                db.upsert_us(conn, u["symbol"], u["name"], rows)
                done += 1
        except Exception as e:
            fail += 1
            print(f"{u['symbol']} 失敗:{e}", flush=True)
        time.sleep(0.25)
        if done and done % 100 == 0:
            print(f"...{done} 檔", flush=True)
    print(f"美股回補完成:{done} 檔更新、{fail} 檔失敗", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", default="2y")
    run(ap.parse_args().range)
