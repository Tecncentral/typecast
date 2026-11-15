# Owner 1 / Owner 2 integration check

Imported the supplied private ZIP locally; cache/join.parquet and cache/property_models.parquet are git-ignored and untracked. TYPECAST_USE_MOCKS=0 is set privately. Merged lane-b d5c6581 after preserving lane-a cde7ca8. All19 currently indexed property/model pairs exactly match the supplied property_models mapping; no index reassignment is needed.

DuckDB2.0.0, PyArrow26.0.1 and Shapely2.2.0 installed successfully on Windows / Python3.13. data/tests:41 passed,6 setup errors. The errors originate in the synthetic commercial-properties.csv fixture: csv.writer writes through open("w") without newline="", producing Windows double carriage returns which DuckDB's dialect sniffer rejects. Owner2 should add newline="" to the fixture file open and rerun on Windows; no licensed input needs changing.

The supplied ZIP is an older schema than current lane-b. Its join has11 columns and is missing availability_status, availability_reason and parking_flags required by data/costar_tools.py. Please provide the newly rebuilt pair-grain join for current code. Do not synthesize these evidence fields to conceal the mismatch. The current live property adapter cannot be claimed working with this supplied snapshot.

A private local Owner2-Demo-Properties.csv selects10 LA properties already in the608-view interior index, ranked by human relevance votes, with exact model IDs and indexed coverage. Deliver that file within the registered team for aerial/parking pre-cache. It is intentionally excluded from public GitHub. No source files, keys or private property records are in this commit.
