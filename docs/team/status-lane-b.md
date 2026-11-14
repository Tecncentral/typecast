# Lane B: live property and aerial evidence

Updated 2026-11-14, integration in progress. User assigned this chat Lane B; the viewer remains in another chat. Private data is shared locally through ignored cache/. Current CoStar implementation: 7143d3a; shared contracts and index integration are merged into this checkout.

## Verified CoStar milestones

- Read the supplied eight-dataset kit and enum/model documentation. `data/SCHEMA.md` records exact fields, meanings, source counts, both cities, availability caveats and no personal contact values.
- `TYPECAST_USE_MOCKS=0 .venv/bin/python -m data.build_join` built **13,096 exact PropertyId/MatterportModelId pairs across 3,288 properties** in private `cache/join.parquet`. Source contains 3,339 properties and 13,147 mapping rows; 51 properties lack a scan mapping. 55 model IDs are explicitly shared by more than one PropertyId in the supplied mapping; no nearest-address inference is used.
- Availability: **443 marketed available, 109 not available, 2,736 unknown**. Only an Active lease listing with attributable positive available space, nonpending status and known date/notice is available. Future marketed space is not vacant occupancy or permission to film. Unknown year/size/availability does not pass hard filters.
- All **608 real indexed views / 19 properties / 19 property-model pairs** overlap exactly. Zero missing IDs or pairs. Default LA search prioritizes these 19 IDs before its 500-row limit; actual scouting then uses only the indexed pool.
- Indexed availability: 3 marketed available, 2 not available, 14 unknown. Contact output consists only of decoded role labels; no names, phone numbers or emails are carried into the join/API.
- Validation: 27 new CoStar tests passed. At the CoStar commit, the lane gate passed 160 tests, smoke/SSE/refine/local-draft E2E and the 20-scene fixture evaluation. Actual query/build diagnostics are private in cache/costar-join-report.json.

## Aerial milestones in progress

- Live Vexcel property extract, ortho extract, semantic search and SAM3 parking segmentation returned HTTP 200 using the supplied key. The actual segmentation contains a raster mask; geometry is being derived from mask cells, not a bounding box.
- OpenStreetMap Overpass attempts returned HTTP 406 and a timeout. Batch requests will stop repeating these failed endpoints. Missing walking/noise evidence remains explicitly unknown, never a zero distance or a quiet-location claim.
- Runtime reads precomputed cache only. Capacity uses one shared budget: floor(area / 30 m²), one truck = four car equivalents. Geometry and imagery estimates do not establish access, current availability or truck clearance.
- Remaining: finish segmentation tests and precompute all 19 properties; reconcile the concurrently received remote Lane B commits without discarding their research; run actual fixed/deep API checks with model parsing and vision rerank enabled; publish and merge the verified Lane B PR.

## Dependencies and private reproduction

The integration captain pins duckdb 2.0.0, pyarrow 26.0.1 and shapely 2.2.0 in the root baseline lock. Optional CLIP dependencies are in requirements-index.lock.txt. Shared Python 3.13 environment passes pip check; clean Python 3.14 baseline installation and integration gate also pass. Sponsor files, joins, imagery, masks and embeddings are never committed.

## Concurrent Owner 2 contribution preserved

Merged remote lane-b through 496d0a7 (Udit Sahoo / Claude), preserving its history and schema research. Its SAM3 mask work informed the tested segmentation precompute. Earlier remote tests used synthetic tables; earlier Vexcel checks covered 8 properties on that contributor's laptop. These are attributed historical reports, not this laptop's final verification.

Integration supersedes active-any-listing availability, unknown-pass filters, personal-name contact labels, bounding-box parking outlines, double allocation of cars/trucks and provider calls inside API requests. data/join.py remains a compatibility entry point to the single pair-grain builder. Current suites cover geofencing, missing imagery, unknown capacity, caching and mask areas. Root STATUS.md is unchanged; this file is the current lane status.
