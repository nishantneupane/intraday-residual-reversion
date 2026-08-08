/ features.q — build the 5-minute bar table and the model-feature table.
/ .
/ Run from the project root (takes a few minutes):
/   ~/.kx/bin/q q/features.q
/ .
/ Produces two new PARTITIONED tables in the HDB:
/ .
/   bars5  5-min OHLCV per sym: open high low close volume ntrades vwap
/          (78 buckets per day: 09:30, 09:35, ..., 15:55)
/ .
/   sig    everything the models see, per (sym, 5-min bucket):
/          ret5      5-min return (close/prev close - 1, within the day)
/          spyret    SPY's return in the same bucket (the market's move)
/          resid     ret5 - beta_mkt * spyret   <- THE core quantity
/          cumres30  trailing 30-min sum of residuals (6 buckets)
/          cumres60  trailing 60-min sum (12 buckets)
/          rv60      realized vol: sqrt of 60-min sum of squared residuals
/          vsurp     volume / same-bucket 20-day trailing average (RELATIVE,
/                    because IEX volume levels are unrepresentative)
/          gap       overnight gap: today's open / yesterday's daily close - 1
/          fwdres30  LABEL ONLY: next-30-min residual sum, for model training.
/                    Never a feature. Null for the last 6 buckets of each day.
/ .
/ Look-ahead discipline (the sin this file must not commit):
/   - betas are joined AS-OF: a bar on day d gets the newest beta dated < d,
/     via the aj trick of stamping each beta at the midnight FOLLOWING its date
/   - vsurp's baseline EXCLUDES today (1 xprev before the moving average)
/   - fwdres30 is the only forward-looking column and is named to shout it

\l q/schema.q
\l data/hdb
/ NOTE: \l data/hdb cd'd us INTO the hdb. All writes below go through
/ .sch.hdb, which schema.q resolved to an absolute path beforehand.

dates: .Q.pv;
-1 "building bars5 + sig for ",string[count dates]," dates...";

/ ---- pass 1: 5-minute bars, one partition at a time -----------------------
/ Also accumulates the slim columns pass 2 needs (~12M rows x 5 cols in
/ memory — comfortably inside the Community edition's 16GB cap).
slimParts: ();
buildBars5: {[d]
  day: select from bars where date=d;
  b5: select open: first open, high: max high, low: min low, close: last close,
             volume: sum volume, ntrades: sum ntrades, vwap: volume wavg vwap
      by sym, time: 0D00:05 xbar time from day;
  b5: `sym`time xasc 0! b5;
  `bars5 set `sym`time`open`high`low`close`volume`ntrades`vwap xcols b5;
  .Q.dpft[.sch.hdb; d; `sym; `bars5];
  slimParts,: enlist select sym, time, open, close, volume from b5;
  d };
buildBars5 each dates;
slim: raze slimParts;
-1 "bars5 written; slim panel rows: ",string count slim;

/ index rows by calendar day ONCE, so pass 2 is O(1) per date instead of a
/ 12M-row scan per date (1,509 scans = minutes of pure waste).
/ `group v` returns a dict value -> row indices; here: date -> its rows.
dayIdx: group `date$ slim`time;

/ ---- volume baseline: per (sym, bucket-of-day), trailing 20-day mean ------
/ For each (sym, bkt) series sorted by date: 1 xprev shifts one day back, so
/ today's own volume never enters its baseline.
vbase: select sym, date: `date$time, bkt: `minute$time, volume from slim;
vbase: `sym`bkt`date xasc vbase;
vbase: update vb: 20 mavg 1 xprev volume by sym, bkt from vbase;
vbase: `sym`date`bkt xkey select sym, date, bkt, vb from vbase;
-1 "volume baseline ready";

/ ---- betas prepared for as-of joining -------------------------------------
/ A beta estimated from data through day d becomes usable the NEXT midnight.
bt: `sym`ts xasc select sym: value sym, ts: (date+1) + 0D00:00, mkt from betas;

/ ---- daily previous close (for the overnight gap) -------------------------
pc: `sym`date xasc select sym: value sym, date, close from daily;
pc: update pclose: prev close by sym from pc;
pc: `sym`date xkey select sym, date, pclose from pc;

/ ---- pass 2: the sig table ------------------------------------------------
buildSig: {[d]
  day: `sym`time xasc slim dayIdx d;
  day: update ret5: -1 + close % prev close by sym from day;

  / the market's same-bucket move, then SPY leaves the table (ruler, not target)
  spy: `time xkey select time, spyret: ret5 from day where sym=`SPY;
  day: day lj spy;
  day: delete from day where sym=`SPY;

  / as-of join: newest beta strictly before day d
  day: update ts: time from day;
  day: aj[`sym`ts; day; bt];
  day: update resid: ret5 - mkt * spyret from day;

  / trailing windows, PER SYM (msum without the by would smear across stocks)
  day: update r0: 0f^resid from day;
  day: update cumres30: msum[6;r0], cumres60: msum[12;r0],
              rv60: sqrt msum[12;r0*r0] by sym from day;

  / labels: sum of the NEXT k residuals (k = 2, 3, 6 buckets = 10/15/30 min).
  / reverse-msum-reverse gives forward sums; 1 _ ...,0n shifts so bucket t
  / sees t+1..t+k. Bars too close to the close (incomplete windows) nulled.
  / Three horizons because fig 04 showed reversion dying by ~15 minutes —
  / the 30-min label from the original plan was too slow; data won.
  fwd: {[k;v] (1 _ reverse msum[k; reverse v]), 0n};
  day: update fwdres10: fwd[2;r0], fwdres15: fwd[3;r0],
              fwdres30: fwd[6;r0] by sym from day;
  day: update fwdres10: 0n from day where (`minute$time) > 15:45;
  day: update fwdres15: 0n from day where (`minute$time) > 15:40;
  day: update fwdres30: 0n from day where (`minute$time) > 15:25;

  / overnight gap (constant within the day) + relative volume surprise
  day: update date: d, bkt: `minute$time from day;
  day: day lj pc;
  day: update gap: -1 + first[open] % first pclose by sym from day;
  day: day lj vbase;
  day: update vsurp: volume % vb from day;

  `sig set `sym`time xasc select sym, time, ret5, spyret, resid, cumres30,
      cumres60, rv60, vsurp, gap, fwdres10, fwdres15, fwdres30 from day;
  .Q.dpft[.sch.hdb; d; `sym; `sig];
  d };
buildSig each dates;
-1 "sig written for ",string[count dates]," dates";
exit 0
