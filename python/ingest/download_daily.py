"""
Download long daily price history from Yahoo Finance (via the yfinance library).

Why this exists: Alpaca's free tier only reaches back ~6 years (to ~Aug 2020),
and the rolling 250-day Carhart beta regressions need daily returns *before*
the first minute bar — otherwise the first year of intraday data has no betas
and gets thrown away. Yahoo serves decades of free daily history.

(History note: the first version of this script used Stooq, but Stooq now puts
a JavaScript browser-verification wall in front of its CSV endpoint, which
scripts can't — and shouldn't try to — get through. Yahoo via yfinance is the
standard fallback in research projects.)

Output: data/raw/daily/<SYMBOL>.csv   (date, open, high, low, close, volume)

Notes:
- We request auto_adjust=False and use the unadjusted Close plus Yahoo's
  splits to match Alpaca's split-adjusted-only convention... actually simpler:
  auto_adjust=True gives split-AND-dividend-adjusted prices. For daily
  *returns* fed to beta regressions, total-return (dividend-adjusted) is the
  more correct choice anyway, so we use auto_adjust=True and document it.
- Yahoo symbology uses dashes for class shares: BRK.B -> BRK-B.
- We keep rows from 2018-01-01 on: betas need ~1.5 years of run-up before
  Aug 2020. Change TRIM_FROM for more.
- Downloads are checkpointed per symbol: existing files are skipped.
"""

import csv
import os
import sys
import time

import yfinance as yf

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "daily")
UNIVERSE_CSV = os.path.join(PROJECT_ROOT, "data", "raw", "universe", "universe.csv")

TRIM_FROM = "2018-01-01"
SLEEP_SECS = 0.5


def yahoo_symbol(symbol):
    """AAPL -> AAPL ; BRK.B -> BRK-B"""
    return symbol.replace(".", "-")


def fetch_daily(symbol):
    """Return a DataFrame of daily bars from TRIM_FROM, or None if empty.

    auto_adjust=True means prices are adjusted for splits AND dividends
    (total-return prices) — the right input for return regressions.
    """
    frame = yf.download(yahoo_symbol(symbol), start=TRIM_FROM, interval="1d",
                        auto_adjust=True, progress=False)
    if frame is None or frame.empty:
        return None
    # yfinance>=0.2.40 returns MultiIndex columns even for one ticker; flatten
    if hasattr(frame.columns, "levels"):
        frame.columns = frame.columns.get_level_values(0)
    return frame


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    if len(sys.argv) > 1:
        symbols = sys.argv[1:]
    else:
        with open(UNIVERSE_CSV) as fh:
            symbols = [row["symbol"] for row in csv.DictReader(fh)]
        if "SPY" not in symbols:
            symbols.append("SPY")

    missing = []
    for i, symbol in enumerate(symbols, 1):
        out_path = os.path.join(OUT_DIR, f"{symbol}.csv")
        if os.path.exists(out_path):
            continue
        frame = fetch_daily(symbol)
        time.sleep(SLEEP_SECS)
        if frame is None:
            missing.append(symbol)
            print(f"[{i}/{len(symbols)}] {symbol}: NO DATA")
            continue
        with open(out_path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["date", "open", "high", "low", "close", "volume"])
            for date, row in frame.iterrows():
                writer.writerow([date.date(), round(row["Open"], 6), round(row["High"], 6),
                                 round(row["Low"], 6), round(row["Close"], 6), int(row["Volume"])])
        if i % 20 == 0 or i == len(symbols):
            print(f"[{i}/{len(symbols)}] {symbol}: {len(frame)} days")

    if missing:
        print(f"missing from Yahoo (investigate or drop): {missing}")
    print("daily download complete")


if __name__ == "__main__":
    main()
