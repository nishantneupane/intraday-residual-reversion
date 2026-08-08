/ schema.q — shared definitions for the whole q layer.
/ Every other q script loads this first, so paths and types live in ONE place.
/ .
/ q reading notes for newcomers:
/   `$"..."      makes a symbol from a string
/   hsym         turns a symbol into a file handle (`:/path/to/thing)
/   0D01         a "timespan" literal meaning 1 hour; 0D05 = 5 hours

/ --- paths (all relative to the project root we launch q from) ------------
.sch.root: first system "pwd";
.sch.rawBars: .sch.root,"/data/raw/bars";
.sch.hdb: hsym `$ .sch.root,"/data/hdb";
.sch.reports: .sch.root,"/data/reports";

/ --- the bars table --------------------------------------------------------
/ Raw CSV columns, in order, with their q parse types:
/   ts P (timestamp)  open/high/low/close F (float)
/   volume/ntrades J (long)  vwap F (float)
.sch.rawTypes: "PFFFFJJF";

/ Columns of the HDB table, in the order they are stored.
/ time  = the bar's start, ALREADY CONVERTED to New York wall-clock time
/ date  = not stored! it is implied by the partition directory name
.sch.barCols: `sym`time`open`high`low`close`volume`ntrades`vwap;
