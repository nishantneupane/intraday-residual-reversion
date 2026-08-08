/ clean.q — timezone conversion and row-level cleaning rules.
/ Loaded by load_csv.q. Every rule REPORTS what it drops; nothing vanishes silently.
/ .
/ ---------------------------------------------------------------------------
/ UTC -> New York time, the honest way.
/ .
/ q has no timezone database, so we implement the one rule we need:
/ US Eastern Time is UTC-5 (EST), except during daylight saving when it is
/ UTC-4 (EDT). Since 2007, DST runs from the second Sunday of March to the
/ first Sunday of November (transitions at 2am local, always on a Sunday,
/ always while the market is closed — which is why date-level granularity
/ is exact for our purposes).
/ .
/ Date trivia that makes the code work: q day-of-week is (`int$date) mod 7,
/ where 2000.01.01 (a Saturday) is day 0. So Saturday=0, Sunday=1, ...
/ ---------------------------------------------------------------------------

/ first Sunday on or after date x     (works on lists of dates too)
.cln.firstSunday: {x + (1 - (`int$x) mod 7) mod 7};

/ is date d inside US daylight saving time?
.cln.isDST: {[d]
  yr: (`int$ `month$ d) div 12;                     / years since 2000
  dstStart: .cln.firstSunday 7 + `date$ `month$ 2 + 12*yr;   / 2nd Sun of March = 1st Sun on/after Mar 8
  dstEnd:   .cln.firstSunday     `date$ `month$ 10 + 12*yr;  / 1st Sun of November
  (d >= dstStart) & d < dstEnd };

/ UTC timestamp -> New York wall-clock timestamp.
/ We guess the local date using the winter offset (-5h), check DST on that
/ date, then apply the true offset. The one-hour guess error can only matter
/ within an hour of a 2am-Sunday transition — never during trading hours.
/ .
/ PARENTHESES ARE LOAD-BEARING: q evaluates RIGHT-TO-LEFT with no operator
/ precedence, so  ts - 0D05 + 0D01*dst  means  ts - (0D05 + 0D01*dst) = -6h.
/ That exact bug shipped in the first version of this file.
.cln.toNY: {[ts]
  approxDate: `date$ ts - 0D05;
  (ts - 0D05) + 0D01 * .cln.isDST approxDate };

/ ---------------------------------------------------------------------------
/ Cleaning: takes a parsed month of bars (all symbols, raw UTC), returns
/ (cleanTable; reportDict). Rules, in order:
/   1. convert ts -> New York time
/   2. keep regular trading hours only: bars stamped 09:30-15:59
/      (early-close half days need no special rule here: their afternoon
/       bars simply don't exist, so there is nothing to drop)
/   3. de-duplicate on (sym, time), keeping the first occurrence
/   4. count (but keep) bars with high < low, as a data-quality signal
/ ---------------------------------------------------------------------------
.cln.month: {[t]
  nRaw: count t;
  t: update time: .cln.toNY ts from t;
  t: delete ts from t;                              / NY time is now the only clock
  t: select from t where (`minute$time) within 09:30 15:59u;
  nRTH: count t;
  t: select from t where i = ({first x};i) fby ([] sym; time);
  nDedup: count t;
  nBadHL: count select from t where high < low;
  report: `raw`droppedOutsideRTH`droppedDupes`badHighLow ! (nRaw; nRaw-nRTH; nRTH-nDedup; nBadHL);
  (t; report) };
