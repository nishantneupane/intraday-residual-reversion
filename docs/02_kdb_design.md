# 02 — The kdb+ database design

*Why the HDB is shaped the way it is, and how a query actually finds its data.*

## The layout

```
data/hdb/
├── sym                    ← every symbol name, once (438 bytes for 105 tickers)
├── factors/               ← splayed: one binary file per column, no partitions
├── daily/                 ← splayed, sym column enumerated
├── 2020.08.03/
│   └── bars/
│       ├── .d             ← column order (57 bytes)
│       ├── sym            ← integers indexing into ../../sym, sorted, `p# flagged
│       ├── time  open  high  low  close  volume  ntrades  vwap
├── 2020.08.04/ …          ← ~1,509 more date directories
```

Loading it is one line — `\l data/hdb` — after which q exposes `bars`, `daily`, and
`factors` as ordinary tables. 45.6M rows "open" instantly because nothing is read yet:
files are **memory-mapped**, and the OS pages in only the bytes a query touches.

## Three design decisions

**1. Partitioned by date.** Every query in this project is date-bounded, so the
partition column must be the date. The `date` column is *virtual* — implied by the
directory name, costing zero bytes and zero I/O.

**2. Columns as files.** `select close from bars where date=X` reads *one* file of
packed floats. Row-oriented storage (CSV, Postgres heap pages) would drag the other
eight columns through the disk and cache for nothing.

**3. Sorted by sym within each day, with `` `p# ``.** The parted attribute stores, per
symbol, where its block starts and ends. `sym=`AAPL` is then two array lookups — O(1),
not a 19,000-row scan. This is why the loader sorts before writing.

### How one query walks the tree

`select from bars where date=2024.09.03, sym=`AAPL, time>12:00`

1. `date=2024.09.03` → enter exactly one directory; 1,508 others never touched
2. `sym=`AAPL` → `p#` index says AAPL's block is rows [0, 389) — jump straight there
3. `time>12:00` → scan only that block of one memory-mapped column
4. Only now do the remaining columns get paged in, only for the surviving rows

Filter order matters: **partition column first, parted column second, everything else
after**. It's the difference between microseconds and minutes.

## The loader (q/load_csv.q)

The raw data is symbol-major (one file per symbol-month); the HDB is date-major.
The loader pivots one month at a time — read all 105 symbols' files, clean
(see [01](01_data.md)), split by day, sort by sym, write with `.Q.dpft` — keeping
peak memory ~tens of MB against KDB-X Community's 16 GB/process cap. Full rebuild:
**~98 seconds** for 6 years, one command (`make hdb`), fully idempotent.

`.Q.dpft[root; date; `sym; `table]` is the standard-library partition writer:
enumerates symbols against `root/sym`, splays columns, applies `` `p# ``. The two
flat tables use the splayed variant (`q/load_flat.q`) — same column files, no date
directories, symbol columns enumerated with `.Q.en`.

## q idioms this phase exercised

| Idiom | Where | What it does |
|---|---|---|
| `("PFFFFJJF"; enlist ",") 0: lines` | load_csv.q | typed CSV parsing (P=timestamp, F=float, J=long) |
| `system "gzcat …"` | load_csv.q | shell out for decompression, capture lines |
| `fby` | clean.q | filter within groups without building the grouped table |
| `xasc` / `xcols` | load_csv.q | sort rows / reorder columns before writing |
| `.Q.dpft`, `.Q.en`, `.Q.dd` | load*.q | partition writer, enumeration, path builder |
| `` `int$date mod 7 `` | clean.q | day-of-week (2000.01.01 = Saturday = 0) |

And the traps, so you never re-learn them the hard way: right-to-left evaluation
(no operator precedence), bare-`/` block comments, keywords like `cov` that
can't be assigned, and `key` behaving differently on files vs. directories.

Next chapter: [03 — the factor model](03_factor_model.md) (Phase 3).
