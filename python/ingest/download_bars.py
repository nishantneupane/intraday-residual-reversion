"""
Download 1-minute bars from Alpaca's free (IEX-feed) data API.

What it does
------------
For every symbol in the universe (plus SPY, our intraday market proxy), walk
month by month from START_MONTH to the present and save each (symbol, month)
of 1-minute bars as one compressed CSV:

    data/raw/bars/<SYMBOL>/<YYYY-MM>.csv.gz

Design decisions, spelled out:
- CHECKPOINTING: a (symbol, month) file that already exists is skipped, so the
  script can be killed and re-run at any time and it resumes where it left off.
- RAW MEANS RAW: we store every bar Alpaca returns, including pre/post-market.
  Filtering to regular trading hours (09:30-16:00 ET) happens later, in q
  (q/clean.q) — downloading and cleaning are separate, auditable steps.
- RATE LIMIT: the free tier allows 200 requests/min. We sleep SLEEP_SECS
  between requests to stay safely under it.
- ADJUSTMENT: bars are split-adjusted (adjustment=split) so a 4-for-1 split
  doesn't look like a -75% crash. Dividends are ignored (negligible intraday).

Discovered empirically (2026-08-07): the free tier serves ~6 years of history;
requests before ~Aug 2020 return empty. Hence START_MONTH below.

Usage:  python3 download_bars.py            # everything in the universe file
        python3 download_bars.py AAPL SPY   # just these symbols (for testing)
"""

import csv
import gzip
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

# --- configuration -----------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "bars")
UNIVERSE_CSV = os.path.join(PROJECT_ROOT, "data", "raw", "universe", "universe.csv")

START_MONTH = (2020, 8)      # free-tier history floor, verified by probing
SLEEP_SECS = 0.35            # ~170 requests/min, under the 200/min cap
PAGE_LIMIT = 10000           # max bars per request (one month fits in one page)
BAR_COLUMNS = ["ts", "open", "high", "low", "close", "volume", "ntrades", "vwap"]


def load_env():
    """Read API keys from the project's .env file into os.environ.

    We parse the file ourselves (KEY=VALUE lines) rather than pulling in a
    dependency for something this small.
    """
    env_path = os.path.join(PROJECT_ROOT, ".env")
    with open(env_path) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key, value)


def api_get(url):
    """One GET request with auth headers. Retries on transient failures.

    Alpaca returns HTTP 429 if we ever exceed the rate limit; we back off and
    retry rather than crash a multi-hour download.
    """
    request = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": os.environ["APCA_API_KEY_ID"],
        "APCA-API-SECRET-KEY": os.environ["APCA_API_SECRET_KEY"],
    })
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as err:
            if err.code == 429:                      # rate-limited: wait it out
                time.sleep(10 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):  # network blip: brief pause
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"giving up after 5 attempts: {url}")


def month_range(start, end):
    """Yield (year, month) tuples from start to end inclusive."""
    year, month = start
    while (year, month) <= end:
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def fetch_month(symbol, year, month):
    """Download all 1-minute bars for one symbol-month. Returns list of rows.

    Follows Alpaca's pagination: each response carries a next_page_token until
    the window is exhausted. Timestamps stay in UTC exactly as Alpaca sends
    them; q converts to New York time during cleaning.
    """
    first_day = date(year, month, 1)
    next_first = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    rows, page_token = [], None
    while True:
        params = {
            "timeframe": "1Min",
            "start": f"{first_day}T00:00:00Z",
            "end": f"{next_first}T00:00:00Z",
            "limit": PAGE_LIMIT,
            "feed": "iex",
            "adjustment": "split",
        }
        if page_token:
            params["page_token"] = page_token
        url = (f"https://data.alpaca.markets/v2/stocks/{symbol}/bars?"
               + urllib.parse.urlencode(params))
        payload = api_get(url)
        time.sleep(SLEEP_SECS)

        for bar in payload.get("bars") or []:
            rows.append([bar["t"], bar["o"], bar["h"], bar["l"], bar["c"],
                         bar["v"], bar["n"], bar["vw"]])
        page_token = payload.get("next_page_token")
        if not page_token:
            return rows


def write_month(symbol, year, month, rows):
    """Write one symbol-month to data/raw/bars/<SYM>/<YYYY-MM>.csv.gz."""
    sym_dir = os.path.join(RAW_DIR, symbol)
    os.makedirs(sym_dir, exist_ok=True)
    path = os.path.join(sym_dir, f"{year:04d}-{month:02d}.csv.gz")
    # write to a temp name then rename, so a killed process never leaves a
    # half-written file that the checkpoint check would wrongly trust
    tmp_path = path + ".tmp"
    with gzip.open(tmp_path, "wt", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(BAR_COLUMNS)
        writer.writerows(rows)
    os.replace(tmp_path, path)
    return path


def month_done(symbol, year, month):
    return os.path.exists(os.path.join(RAW_DIR, symbol, f"{year:04d}-{month:02d}.csv.gz"))


def main():
    load_env()

    if len(sys.argv) > 1:                      # explicit symbols on the command line
        symbols = sys.argv[1:]
    else:                                      # full universe + SPY market proxy
        with open(UNIVERSE_CSV) as fh:
            symbols = [row["symbol"] for row in csv.DictReader(fh)]
        if "SPY" not in symbols:
            symbols.append("SPY")

    today = datetime.now(timezone.utc).date()
    last_month = (today.year, today.month)
    months = list(month_range(START_MONTH, last_month))

    total = len(symbols) * len(months)
    done = 0
    print(f"{len(symbols)} symbols x {len(months)} months = {total} tasks")

    for symbol in symbols:
        empty_months = 0
        for year, month in months:
            done += 1
            if month_done(symbol, year, month):
                continue
            rows = fetch_month(symbol, year, month)
            if rows:
                write_month(symbol, year, month, rows)
            else:
                empty_months += 1        # legitimate for pre-listing months (e.g. new tickers)
            if done % 25 == 0:
                print(f"[{done}/{total}] {symbol} {year}-{month:02d}: {len(rows)} bars")
        if empty_months:
            print(f"note: {symbol} had {empty_months} empty months (pre-listing or missing)")

    print("download complete")


if __name__ == "__main__":
    main()
