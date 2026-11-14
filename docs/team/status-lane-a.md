# Owner 1 planning milestone

Updated 2026-11-14 12:32 UTC. Branch lane-a / PR #6.

Added Gemini-drafted and locally reviewed MMR diversity, hard property/scan caps,
visual query briefs, manually oriented floor-plan FOV/clearance estimates, room
polygon retention during enrich/bootstrap, scene lookbook HTML/JSON export, and
20-scene blinded local relevance labeling (15 held-out / 5 tune). Labels remain
empty. Metrics segregate reviewer type, source mode and split and are explicitly
pooled, not whole-catalog recall. Shared contracts are unchanged.

Live enrichment: 19/19 room model requests succeeded, 600 room assignments,
488 ceiling estimates; validated polygon coverage is 25 rooms / 164 indexed views.
All planning fit statuses remain unknown. Missing boundaries have no guessed plan.
Browser SDK connection succeeds at localhost; 127.0.0.1 is outside the key's
existing referrer allowlist. Scan navigation and viewer FOV are under browser
verification; cube-to-world image orientation is not claimed.

Targeted gate: 75 index tests pass; studio.js passes node --check. Full combined
Windows verification and browser/export evidence will be recorded below.

---

# Owner 1 status

Updated 2026-11-14 10:59 UTC. Branch lane-a, PR #6 into dev.

Implemented real cosine retrieval over private CLIP embeddings, strict cache/model
validation, pre-top-k filters, cross-model/property example matching, atomic index
generation builder, bounded/resumable Matterport horizon importer, and evaluation
CLI. Estimated geometry now returns explicit unknown status with current shared
ShotFit schema. No shared schema or root dependency edits.

Verified locally: 65 index tests pass, including recovery and local-image isolation.
The initial integrated baseline passed 46 tests plus API smoke. At fcc9a1d, both
push and PR Linux CI passed the full shared gate (117 tests, smoke, SSE and mock
evaluation). Latest feature code 9faab10 is also green in CI. Combined with the
separate Windows-fix PR #8, local verification passes 139 tests plus API smoke,
SSE/refinement/no-send and the unlabelled 20-scene mock evaluation.
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

A current local Typecast-Owner1-Team.zip (no credentials) was prepared for private
team handoff outside the public repository. Extract into the repository root to
use the prebuilt index. Alternatively re-ingest with your own sponsor key and an
agreed model list through the one-command bootstrap.

Remaining: 20 human-labelled held-out scenes, Owner 2's property/aerial alignment,
and Owner 4's shared viewer integration. Exact SDK tour-pose alignment is unverified;
links open the correct model without promising a matched camera. Windows-only
shared dev bugs have fixes in PR #8: offline harness socketpairs and Windows C:
image paths. Owner 3 should inspect that separate fix; its CI and the combined
Windows gate pass. Grok audited the code and identified recovery and
configuration issues now fixed; Gemini supplied retrieval, ingestion and room
drafts. Claude login works but quota blocks review. User explicitly authorized
the sponsor agreement and confirmed hackathon-demo permission. Raw data/keys
stay out of public GitHub; event-end deletion requirements still apply.
