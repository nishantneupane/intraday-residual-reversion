/ load_csv.q — build the date-partitioned HDB from the raw Alpaca CSVs.
/ .
/ Run from the project root:
/   ~/.kx/bin/q q/load_csv.q 2024-09        / one month (testing)
/   ~/.kx/bin/q q/load_csv.q                / every month found on disk
/ .
/ The flow, per month (memory never holds more than one month, ~60 MB):
/ .
/   104 files AAPL/2024-09.csv.gz ... XOM/2024-09.csv.gz     (symbol-major)
/        |  gzcat + 0: parse, tag each row with its sym
/        v
/   one in-memory table, ~800k rows, all symbols, UTC
/        |  .cln.month  (NY time, trading hours, dedupe — counts reported)
/        v
/   split by calendar day, each day sorted by sym
/        |  .Q.dpft  (enumerate syms, write columns, apply `p# on sym)
/        v
/   data/hdb/2024.09.03/bars/  ...  data/hdb/2024.09.30/bars/  (date-major)
/ .
/ .Q.dpft[hdbRoot; date; `sym; `tableName] is the standard-library one-call
/ partition writer. It (a) replaces symbol strings with indexes into the
/ shared hdb/sym file ("enumeration"), (b) writes each column as its own
/ binary file, (c) marks the sym column parted (`p#) so per-symbol lookups
/ are O(1). It expects the table in a GLOBAL variable, sorted by the parted
/ column — both handled below.

\l q/schema.q
\l q/clean.q

/ --- discover what's on disk ----------------------------------------------
/ Only DIRECTORIES count as symbols: `key` on a directory returns a list
/ (type 11h) of its contents, on a plain file it returns an atom. Guards
/ against strays like .DS_Store, whose "months" would be garbage.
syms: {x where {11h = type key hsym `$ .sch.rawBars,"/",string x} each x} key hsym `$ .sch.rawBars;
allMonths: asc distinct raze {7#'string key hsym `$ .sch.rawBars,"/",string x} each syms;
months: $[count .z.x; .z.x; allMonths];               / command-line override

/ --- read one symbol-month file, tagging rows with the symbol -------------
/ Missing file (pre-IPO months) -> empty table of the right shape, so raze
/ can glue everything together without special cases.
.ld.emptyBars: ([] ts:`timestamp$(); open:`float$(); high:`float$(); low:`float$();
                   close:`float$(); volume:`long$(); ntrades:`long$(); vwap:`float$();
                   sym:`$());
.ld.readSymMonth: {[s;m]
  path: .sch.rawBars,"/",string[s],"/",m,".csv.gz";
  if[()~key hsym `$path; :.ld.emptyBars];
  t: (.sch.rawTypes; enlist ",") 0: system "gzcat ",path;
  update sym:s from t };

/ --- write one calendar day as a partition --------------------------------
.ld.writeDay: {[t;d]
  day: .sch.barCols xcols `sym`time xasc select from t where (`date$time)=d;
  `bars set day;                                      / global, as .Q.dpft requires
  .Q.dpft[.sch.hdb; d; `sym; `bars];
  d };

/ --- one month, end to end ------------------------------------------------
.ld.loadMonth: {[m]
  t0: .z.p;
  raw: raze .ld.readSymMonth[;m] each syms;
  cleaned: .cln.month raw;                            / (table; report)
  t: cleaned 0;
  days: .ld.writeDay[t;] each asc distinct `date$ t`time;
  ms: (`long$ .z.p - t0) div 1000000;
  report: (`month`daysWritten`msElapsed ! (`$m; count days; ms)), cleaned 1;
  -1 m," : ", string[count days]," days, ",
     string[report`raw]," raw rows, dropped ",
     string[report`droppedOutsideRTH]," outside-RTH + ",
     string[report`droppedDupes]," dupes, ",
     string[ms],"ms";
  report };

/ --- go --------------------------------------------------------------------
system "mkdir -p ",.sch.reports;
reports: .ld.loadMonth each months;
(hsym `$ .sch.reports,"/clean_report.csv") 0: csv 0: reports;
-1 "wrote ",string[count months]," months; report at data/reports/clean_report.csv";
exit 0
