# Lane B: live property and aerial evidence

Updated 2026-11-14 15:40 UTC. Implementation complete; final PR integration follows this verified status commit. User assigned this chat Lane B; the viewer remains in another chat. Private data is shared locally through ignored cache/. Current CoStar implementation: 7143d3a; shared contracts and index integration are merged into this checkout.

## Verified CoStar milestones

- Read the supplied eight-dataset kit and enum/model documentation. `data/SCHEMA.md` records exact fields, meanings, source counts, both cities, availability caveats and no personal contact values.
- `TYPECAST_USE_MOCKS=0 .venv/bin/python -m data.build_join` built **13,096 exact PropertyId/MatterportModelId pairs across 3,288 properties** in private `cache/join.parquet`. Source contains 3,339 properties and 13,147 mapping rows; 51 properties lack a scan mapping. 55 model IDs are explicitly shared by more than one PropertyId in the supplied mapping; no nearest-address inference is used.
- Availability: **443 marketed available, 109 not available, 2,736 unknown**. Only an Active lease listing with attributable positive available space, nonpending status and known date/notice is available. Future marketed space is not vacant occupancy or permission to film. Unknown year/size/availability does not pass hard filters.
- All **608 real indexed views / 19 properties / 19 property-model pairs** overlap exactly. Zero missing IDs or pairs. Default LA search prioritizes these 19 IDs before its 500-row limit; actual scouting then uses only the indexed pool.
- Indexed availability: 3 marketed available, 2 not available, 14 unknown. Contact output consists only of decoded role labels; no names, phone numbers or emails are carried into the join/API.
- Validation: 27 new CoStar tests passed. At the CoStar commit, the lane gate passed 160 tests, smoke/SSE/refine/local-draft E2E and the 20-scene fixture evaluation. Actual query/build diagnostics are private in cache/costar-join-report.json.

## Verified aerial milestones

- All **19 indexed properties** have real Vexcel aerials, property extracts, semantic-search responses and SAM3 responses in private cache. All 19 annotated PNGs validate. Visual inspection confirmed the outline follows the actual mask and the provider attribution remains visible.
- **9 parking geometries / capacity estimates**, including 7 with holes preserved; **10 capacities remain unknown**. The geometry traces actual segmentation cells, unions overlapping detections and selects one nearby connected lot within 150 m. A bounding box is never presented as the parking outline.
- Capacity uses one shared budget: floor(area / 30 m²), one truck = four car equivalents. Five cached estimates can cover 3 trucks plus 30 cars. Nearby parking candidates do not establish permission, availability or truck clearance.
- **19 walking distances and 19 noise screens remain unknown**. The documented OSM endpoints returned HTTP 406 and a timeout. After those failures the batch stopped repeating requests. Precompute exits 1 solely for these 19 recorded OSM-unavailable entries; all Vexcel sources succeeded. No zero-distance, no-parking or quiet-location claim substitutes for missing evidence.
- Runtime reads all 19 precomputed logistics records in **19.35 ms**, with zero provider requests. Cached follow-ups allocate requested trucks and remaining cars without changing the source record.
- Restricted entrance nodes cannot form walking routes. A coordinate-changing refresh archives the previous generation before fetching new evidence, so failed refreshes cannot relabel stale imagery or masks. These cases have regression tests.

## Actual API verification

Executed from detached `../typecast-live`, created from origin/dev and merged with lane-b locally; nothing was pushed from that checkout. Both engines used gpt-6.1-sol, model parsing and vision reranking enabled, permitted image upload enabled, and actual LangSmith tracing. Different scenes forced **20 fresh vision scores / zero cached scores / zero failures** in each run. These are single live runs, not the earlier mock-data benchmark.

| Check | Fixed | Deep |
| --- | ---: | ---: |
| POST /scout wall time | 30.639 s | 67.398 s |
| Actual engine | fixed | deep, no fallback |
| Picks / evidence sources per pick | 3 / CoStar, Matterport, Vexcel | 3 / CoStar, Matterport, Vexcel |
| Interior images verified via HTTP/Pillow | 6 | 6 |
| Aerial images verified via HTTP/Pillow | 3 | 3 |
| Model parser succeeded | yes | yes |
| Fresh vision scores / failures | 20 / 0 | 20 / 0 |
| LangSmith independently verified | yes, completed root | yes, 202 spans |

All returned picks have actual skeptic caveats. Directional Matterport depth is still unmeasured, so all three shot-fit badges are unknown; no geometry certainty was invented. Trace payloads were independently checked for redaction.

Live follow-up **“Need parking for 5 trucks and 3 crew cars”** returned three picks in **26.003 s** on the same thread, with zero fresh property/interior searches. All three picks changed rank or parking allocation; all three area budgets were verified. Refinement correctly reports the fixed engine.

Private summaries/responses are in `cache/live-checks/{fixed,deep,refine}.json` and adjacent `.response.json` files. Completed traces: [fixed](https://smith.langchain.com/o/2be59dd2-f6bb-48a8-86e6-04feb171e631/projects/p/4a463e7f-b7cb-40ee-8c38-1bf1474943f6/r/01a1dab2-854e-7ae4-943a-feed4a3cd46c?poll=true), [deep](https://smith.langchain.com/o/2be59dd2-f6bb-48a8-86e6-04feb171e631/projects/p/4a463e7f-b7cb-40ee-8c38-1bf1474943f6/r/01a1dab4-151c-737b-bfbf-f21595ff5f03?poll=true).

Commands (run from repository root, with private .env/cache):

```sh
.venv/bin/python -m data.build_join
TYPECAST_USE_MOCKS=0 .venv/bin/python -m data.vexcel_precompute --without-osm
TYPECAST_USE_MOCKS=0 .venv/bin/python -m data.vexcel_precompute --offline --without-osm
.venv/bin/python scripts/verify.py
node --test bridge/core.test.mjs
TYPECAST_USE_MOCKS=0 TYPECAST_ENGINE=fixed TYPECAST_ENABLE_MODEL_PARSE=1 TYPECAST_ENABLE_VISION_RERANK=1 TYPECAST_ALLOW_VISION_UPLOAD=1 LANGSMITH_TRACING=true .venv/bin/python -m uvicorn agent.app:app --port 8002
.venv/bin/python scripts/check_live.py --engine fixed --verify-trace
# Restart the server with TYPECAST_ENGINE=deep, then use a different scene:
.venv/bin/python scripts/check_live.py --engine deep --verify-trace --scene 'INT. LOS ANGELES APARTMENT, DAY. A bright living room with windows, neutral walls and an adjoining kitchen for a two-person conversation. Warm daylight and a dining table in the frame. Parking for 1 truck and 3 crew cars. No required construction era.'
```

Final implementation commit **a5a8a08**: **240 Python tests**, smoke/SSE/refine/local-draft E2E, 20-scene fixture evaluation gate and 6 bridge tests pass. The fixture evaluation is not a real relevance score. The data suite contains 47 tests. Incoming PRs 8, 6 and 10 and shared integration PR11 are merged into dev. Lane B is reviewed in PR12. Viewer changes and Photon message delivery remain outside this chat's assigned lane; no external messages were sent.

## Dependencies and private reproduction

The integration captain pins duckdb 2.0.0, pyarrow 26.0.1 and shapely 2.2.0 in the root baseline lock. Optional CLIP dependencies are in requirements-index.lock.txt. Shared Python 3.13 environment passes pip check; clean Python 3.14 baseline installation and integration gate also pass. Sponsor files, joins, imagery, masks and embeddings are never committed.

## Concurrent Owner 2 contribution preserved

Merged remote lane-b through 496d0a7 (Udit Sahoo / Claude), preserving its history and schema research. Its SAM3 mask work informed the tested segmentation precompute. Earlier remote tests used synthetic tables; earlier Vexcel checks covered 8 properties on that contributor's laptop. These are attributed historical reports, not this laptop's final verification.

Integration supersedes active-any-listing availability, unknown-pass filters, personal-name contact labels, bounding-box parking outlines, double allocation of cars/trucks and provider calls inside API requests. data/join.py remains a compatibility entry point to the single pair-grain builder. Current suites cover geofencing, missing imagery, unknown capacity, caching and mask areas. Root STATUS.md is unchanged; this file is the current lane status.
