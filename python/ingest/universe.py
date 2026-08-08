"""
Write the trading universe to data/raw/universe.csv.

The universe is the S&P 100 (index ticker: OEX) membership as recorded on
2026-08-07 — around 100 of the largest, most liquid US stocks. We hardcode the
list rather than scraping it live so the project is reproducible: anyone
running this later gets the exact same universe we backtested.

KNOWN LIMITATION (documented in PLAN.md §7): this is *today's* membership.
Stocks that were in the index in 2021 but fell out (or went bankrupt) are
missing, which biases backtests upward ("survivorship bias"). We measure and
report that bias rather than pretending it isn't there.

Note: BRK.B and BF.B use a dot in Alpaca's symbology, matching how we list
them here. Any symbol Alpaca doesn't recognize simply downloads zero bars and
is reported by download_bars.py, so a stale entry fails loudly, not silently.
"""

import csv
import os

RECORDED_ON = "2026-08-07"

SP100 = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "AIG", "AMD", "AMGN", "AMT", "AMZN",
    "AVGO", "AXP", "BA", "BAC", "BNY", "BKNG", "BLK", "BMY", "BRK.B", "C",
    "CAT", "CHTR", "CL", "CMCSA", "COF", "COP", "COST", "CRM", "CSCO", "CVS",
    "CVX", "DE", "DHR", "DIS", "DOW", "DUK", "EMR", "EXC", "F", "FDX",
    "GD", "GE", "GILD", "GM", "GOOG", "GOOGL", "GS", "HD", "HON", "IBM",
    "INTC", "INTU", "ISRG", "JNJ", "JPM", "KHC", "KO", "LIN", "LLY", "LMT",
    "LOW", "MA", "MCD", "MDLZ", "MDT", "MET", "META", "MMM", "MO", "MRK",
    "MS", "MSFT", "NEE", "NFLX", "NKE", "NVDA", "ORCL", "PEP", "PFE", "PG",
    "PLTR", "PM", "PYPL", "QCOM", "RTX", "SBUX", "SCHW", "SO", "SPG", "T",
    "TGT", "TMO", "TMUS", "TSLA", "TXN", "UNH", "UNP", "UPS", "USB", "V",
    "VZ", "WFC", "WMT", "XOM",
]

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "data", "raw", "universe", "universe.csv")

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["symbol", "recorded_on"])
        for symbol in SP100:
            writer.writerow([symbol, RECORDED_ON])
    print(f"wrote {len(SP100)} symbols to {OUT}")
