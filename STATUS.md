# Status

Update your own section before you stop. Keep it short: works / broken / next / waiting on.

## Shared
- works: repo scaffold, contracts, mocks, shot-fit maths, panorama view cutter, fixed-order pipeline and `/scout` endpoint running on mocks. `pytest` passes.
- next: first hour together: agree contracts, set `.env`, Owner 2 publishes `data/join.parquet`.

## Owner 1 (index/)
- works: `check_shot`, `cut_views` (tested on a synthetic panorama), `search_shots` on mocks
- next: access test against one real Matterport model

## Owner 2 (data/)
Details: `docs/team/status-lane-b.md` and `data/VEXCEL.md`. Live data exists only on Owner 2's laptop; mock mode is unchanged.
- works: `python -m data.build_join` (`data/join.py` is a shim) builds the private `cache/join.parquet` from exact PropertyId/MatterportModelId pairs, one row per pair, Los Angeles and Houston: 13,096 pairs across 3,288 properties. `search_costar` and `get_property` read it in live mode; unknown year, size or availability never pass a hard filter. Contacts are decoded role labels only.
- availability: `available` / `not_available` / `unknown` (443 / 109 / 2,736). Available means an Active lease listing with positive attributable space, nonpending, with a known date or notice. It is marketed availability, not vacancy or permission to film. Sale and auction listings do not verify lease space.
- vexcel: `plan_logistics` reads only precomputed `cache/vexcel/<property_id>/logistics.json` and never calls a provider at request time. A missing cache raises `VexcelUnavailable` (a `FileNotFoundError`), which the pipeline skips. Parking is floor(area / 30 m2); one truck counts as four cars.
- demo set: 10 properties cached in `cache/vexcel/` (from Owner 2's private handoff). All 10 load live; parking is estimated for 7 and unknown for 3; noise screening is present (estimated) for all 10.
- osm repair: the German Overpass endpoint returned HTTP 406 and Private.coffee timed out. The default is now the North America regional endpoint, and 19 of 19 indexed properties have OSM cached. Noise screening is estimated for all 19 (six with proximity flags) and parking estimates rose from 9 to 14 using mapped OSM polygons. OSM is used only in precompute, never during a scout request.
- private cache setup: put the sponsor kit at `cache/costar-hackathon-kit/` (or pass `--kit <path>`); it needs both mapping CSVs, `schemas/enums.json` and all eight JSONL files. Put `VEXCEL_API_KEY` in `.env`. Nothing under `cache/` is committed. Keep it out of cloud-synced folders and share the join and Vexcel cache by direct private copy.
- commands: `python -m data.build_join`, then `TYPECAST_USE_MOCKS=0 python -m data.vexcel_precompute` (default input is `cache/shot-index/CURRENT`; `--property-id <id>` picks one; `--refresh` after a coordinate change; `--offline` makes no network calls; rerun without `--refresh` to fill only missing OSM).
- tests: `pytest data/tests` in both modes. In live mode the one mock-only test in `test_data.py` skips with a reason.
- gaps: parking is unknown for some properties (5 of the 19 indexed, 3 of the 10 cached here). Walking distance is unknown for all, because sources do not establish a connected route and entrance. Shot-fit is unknown because directional Matterport depth is unmeasured (Lane A). Most availability is unknown. Imagery cannot show permission, truck clearance, current availability or sound level; noise is a proximity estimate.
- waiting on: Lane A's shot index for default precompute.
- done: `data/rent_precompute.py` grades each property's rent A, B or C by reliability. `data/cost_model.py` compares a found location, a build set, a standing set and CGI as scenario estimates, not verified savings. Both have tests. PR #54 is merged.
- done: a spending guard and 429 retry for Vexcel oblique calls, with tests. PR #55. It depends on #51.
- open: construction per sq ft and CGI per shot now use public estimates (tagged PUBLIC ESTIMATE, not a quote) and still need real studio quotes. Multifamily rents are mostly ground-floor retail, not apartment rent. Sending Vexcel imagery to outside AI models is unconfirmed. The Vexcel billing unit is unconfirmed.
- done: an offline radius filter, `data/radius.py`, straight-line distance and not drive time, in PR #58, which is merged. The 9 QA buildings now all have Vexcel caches with `logistics.json`: parking and noise are estimated and walking distance is unknown.

## Owner 3 (agent/)
- works: fixed-order pipeline + FastAPI endpoints on mocks
- next: deepagents harness with the four subagents

## Owner 4 (web/, bridge/, docs/)
- works: nothing yet
- next: run view on `mocks/pick.json` and `mocks/events.jsonl`
