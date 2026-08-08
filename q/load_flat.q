/ load_flat.q — load the two small daily tables into the HDB as SPLAYED tables.
/ .
/ Run from the project root:  ~/.kx/bin/q q/load_flat.q
/ .
/ "Splayed" is partitioning's little sibling: one directory per table, one
/ binary file per column, but NO date directories — the whole table lives in
/ hdb/factors/ and hdb/daily/. Right choice here because these tables are
/ tiny (26k and ~220k rows) next to the 45M-row bars table.
/ .
/ When q opens data/hdb it exposes all three automatically:
/   bars     partitioned by date     (the big one)
/   factors  splayed                 (Carhart four factors, daily, 1926->)
/   daily    splayed                 (Yahoo daily OHLCV, 2018->, for betas)
/ .
/ One rule of splayed tables: any symbol column must be ENUMERATED before
/ writing (raw symbol lists can't be memory-mapped). .Q.en[hdbRoot; table]
/ does that against the same hdb/sym file the bars already use.

\l q/schema.q

/ --- factors ---------------------------------------------------------------
/ carhart_daily.csv columns: date, mkt_rf, smb, hml, wml, rf (decimals)
factors: ("DFFFFF"; enlist ",") 0: hsym `$ .sch.root,"/data/raw/factors/carhart_daily.csv";
(.Q.dd[.sch.hdb; `factors,`]) set factors;            / .Q.dd builds `:path/factors/
-1 "factors : ",string[count factors]," days ",
   string[min factors`date]," -> ",string max factors`date;

/ --- daily -----------------------------------------------------------------
/ one CSV per symbol -> single table with a sym column, enumerated
dailyDir: .sch.root,"/data/raw/daily";
files: key hsym `$ dailyDir;
readOne: {[f]
  t: ("DFFFFJ"; enlist ",") 0: hsym `$ dailyDir,"/",string f;
  update sym: `$ -4_ string f from t };              / "AAPL.csv" -> `AAPL
daily: `sym`date xasc raze readOne each files;
daily: `sym`date`open`high`low`close`volume xcols daily;
(.Q.dd[.sch.hdb; `daily,`]) set .Q.en[.sch.hdb; daily];
-1 "daily   : ",string[count daily]," rows, ",
   string[count distinct daily`sym]," symbols, ",
   string[min daily`date]," -> ",string max daily`date;
exit 0
