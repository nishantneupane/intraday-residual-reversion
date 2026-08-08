"""
Download the Carhart four factors from the Ken French Data Library.

Two files from https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/:
  1. "Fama/French 3 Factors [Daily]"  -> Mkt-RF, SMB, HML, RF
  2. "Momentum Factor (Mom) [Daily]"  -> WML (French calls it "Mom")

Merged on date into one tidy file:

    data/raw/factors/carhart_daily.csv
    columns: date, mkt_rf, smb, hml, wml, rf   (decimal returns, not percent)

Parsing notes (French's CSVs are famously scruffy):
- Several banner lines precede the data; the data block starts at the first
  line whose first field is an 8-digit date (YYYYMMDD).
- The block ends at the first non-date line after it (a blank line followed by
  "Copyright..." or an annual-summary section).
- Values are in PERCENT (e.g. -11.98 on 2020-03-16); we divide by 100 so every
  downstream formula can treat returns as plain decimals.
"""

import csv
import io
import os
import re
import urllib.request
import zipfile

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
FILES = {
    "ff3": f"{BASE}/F-F_Research_Data_Factors_daily_CSV.zip",
    "mom": f"{BASE}/F-F_Momentum_Factor_daily_CSV.zip",
}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "factors")
DATE_LINE = re.compile(r"^\s*(\d{8})\s*$")


def fetch_csv_text(url):
    """Download a zip from French's site and return the CSV inside as text."""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    # each zip contains exactly one CSV
    name = archive.namelist()[0]
    return archive.read(name).decode("latin-1")


def parse_daily_block(text):
    """Extract {date: [values...]} from a French CSV, percent -> decimal."""
    table = {}
    for line in text.splitlines():
        fields = [f.strip() for f in line.split(",")]
        if fields and DATE_LINE.match(fields[0]):
            date = fields[0]
            values = [float(v) / 100.0 for v in fields[1:] if v]
            # -99.99 and -999 are French's missing-data markers
            if any(v <= -0.99 for v in values):
                continue
            table[date] = values
        elif table:
            break   # a non-date line after data began = end of the daily block
    return table


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    ff3 = parse_daily_block(fetch_csv_text(FILES["ff3"]))   # Mkt-RF SMB HML RF
    mom = parse_daily_block(fetch_csv_text(FILES["mom"]))   # Mom

    common_dates = sorted(set(ff3) & set(mom))
    out_path = os.path.join(OUT_DIR, "carhart_daily.csv")
    with open(out_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "mkt_rf", "smb", "hml", "wml", "rf"])
        for date in common_dates:
            mkt_rf, smb, hml, rf = ff3[date]
            (wml,) = mom[date]
            iso = f"{date[:4]}-{date[4:6]}-{date[6:]}"
            writer.writerow([iso, mkt_rf, smb, hml, wml, rf])

    print(f"wrote {len(common_dates)} days ({common_dates[0]} .. {common_dates[-1]}) "
          f"to {out_path}")


if __name__ == "__main__":
    main()
