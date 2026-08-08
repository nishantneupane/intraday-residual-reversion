/ load_preds.q — load the out-of-sample predictions into the HDB.
/ .
/ Run from the project root AFTER python/research/04_make_predictions.py:
/   ~/.kx/bin/q q/load_preds.q
/ .
/ Stores data/model/predictions.csv as a splayed `preds` table:
/   date, sym (enumerated), bkt (minute), pred
/ Splayed (not partitioned) is fine at ~10M rows, and keeps the loader dumb.

\l q/schema.q

p: ("DSUF"; enlist ",") 0: hsym `$ .sch.root,"/data/model/predictions.csv";
/ one type letter per column: D=date, S=symbol, U=minute ("09:35"), F=float.
/ (a SPACE in a 0: type string means "skip this column" — easy to misuse.)
p: `date`sym`bkt xasc p;
(.Q.dd[.sch.hdb; `preds,`]) set .Q.en[.sch.hdb; p];
-1 "preds: ",string[count p]," rows, ",string[min p`date]," -> ",string max p`date;
exit 0
