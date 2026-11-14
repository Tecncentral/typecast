# Owner 1 status

Updated 2026-11-14 10:47 UTC. Branch lane-a, PR #6 into dev.

Implemented real cosine retrieval over private CLIP embeddings, strict cache/model
validation, pre-top-k filters, cross-model/property example matching, atomic index
generation builder, bounded/resumable Matterport horizon importer, and evaluation
CLI. Estimated geometry now returns explicit unknown status with current shared
ShotFit schema. No shared schema or root dependency edits.

Verified locally: 51 index tests pass, including recovery and local-image isolation.
The initial integrated baseline passed 46 tests plus API smoke. At fcc9a1d, both
push and PR Linux CI passed the full shared gate (117 tests, smoke, SSE and mock
evaluation). Later recovery/anchor/preview tests are being submitted next.
Controlled vectors cover ranking, null filters, corruption, duplicate IDs and
source exclusion. Synthetic HTTP clients cover retries, partial failure, unsafe
redirect refusal and resume. Import/build/search generation roundtrip passes.

LIVE evidence: individual sponsor keys issued for registered Typecast team;
authentication retrieved 39 panoramas for the sponsor reference model. The private
catalog now indexes 608 actual horizon views from 19 distinct catalog-linked
properties. One additional model denied access and was reported. Real CLIP text
queries change order; source model/property are excluded from example matching;
top images decoded and rendered at 2048 pixels in Chrome. Browser warm query was
0.04 seconds; first encoder load was 5.72 seconds. These are observations, not a
latency benchmark. Official live schema verification found panorama anchor floor
and room references plus source rotations: enrichment now assigns 600 views to
rooms and supplies 488 ceiling estimates. Directional depth remains unknown.
No human-labelled retrieval quality metric has been measured.

Integration: read index/README.md. Property IDs are literal costar_property_id from
the sponsor catalog and need agreement with Owner 2's private records. Image URLs
are /cache/views/...; the standalone preview serves only indexed view files.
Cube-local headings are not compass bearings or validated SDK tour poses.
Owner 3 consolidates optional index/requirements.txt before broad team installation.

One-command bootstrap is live verified: `python -m index.bootstrap --max-models 20
--max-sweeps 8` downloaded the official catalog, resumed 608 views across 19
available models, enriched room evidence with zero room-fetch failures and
published a complete index. No manual catalog/model-pair preparation is required.

Private team bundle: cache/typecast-owner1-team-bundle.zip (no credentials).
Extract into another checkout's repository root to use the prebuilt index. The
bundle must be refreshed after the latest anchor-enriched rebuild. Alternatively
each teammate can re-ingest with their own sponsor key and an agreed model list.

Remaining: 20 human-labelled held-out scenes, Owner 2's property/aerial alignment,
and Owner 4's shared viewer integration. Exact SDK tour-pose alignment is unverified;
links open the correct model without promising a matched camera. Windows-only
shared dev bugs remain: offline harness blocks asyncio's internal socketpair;
rerank treats C: image paths as URL schemes. These are recorded in PR #6 for
Owner 3; Linux CI is green. Grok audited the code and identified recovery and
configuration issues now fixed; Gemini supplied retrieval, ingestion and room
drafts. Claude login works but quota blocks review. User explicitly authorized
the sponsor agreement and confirmed hackathon-demo permission. Raw data/keys
stay out of public GitHub; event-end deletion requirements still apply.
