/ serve.q — expose the HDB to other processes (C++, Python) over IPC.
/ .
/ Run from the project root, leave it running:
/   ~/.kx/bin/q q/serve.q
/ .
/ What this actually does: q's IPC is built in — ANY q process that sets a
/ port becomes a server. Clients connect via TCP, send a string of q code,
/ and get back the evaluated result in q's binary wire format. The KX C API
/ (cpp/vendor/c.o) speaks that format, which is how our C++ engine reads
/ 45M rows without ever touching a CSV.
/ .
/ Security note: an open q port executes whatever it is sent. Fine on
/ localhost for a research project; never expose such a port to a network.

\l data/hdb
\p 5001

-1 "HDB served on port 5001: ",", " sv string tables[];
-1 "bars: ",string[count bars]," rows, ",string[min date]," -> ",string max date;
