# Status

Update your own section before you stop. Keep it short: works / broken / next / waiting on.

## Shared
- works: repo scaffold, contracts, mocks, shot-fit maths, panorama view cutter, fixed-order pipeline and `/scout` endpoint running on mocks. `pytest` passes.
- next: first hour together: agree contracts, set `.env`, Owner 2 publishes `data/join.parquet`.

## Owner 1 (index/)
- works: `check_shot`, `cut_views` (tested on a synthetic panorama), `search_shots` on mocks
- next: access test against one real Matterport model

## Owner 2 (data/)
Mode: real data on Owner 2's laptop only (`TYPECAST_USE_MOCKS=0`); mock mode unchanged. Verified 2026-11-14 on branch `lane-b`.

### Works (verified by running it)
- `data/SCHEMA.md`: all 8 datasets, columns and types, Los Angeles scope, field sources, open questions answered. Names, types and counts only.
- `python data/join.py` builds `cache/join.parquet` (Property shape) and `cache/property_models.parquet` (every property and scan pair).
- `search_costar` and `get_property` read `cache/join.parquet` when `TYPECAST_USE_MOCKS=0`; every filter is honoured; results validate as `Property`.
- `plan_logistics` and `aerial_image` call Vexcel: parcel from `property/extract`, parking from `elements/detect` ("parking lot", mask area), freeway and rail from `elements/detect`. Results and a 1600 px aerial JPEG with the lot outlined are cached under `cache/vexcel/`; `aerial_image_path` is filled.
- `pytest data/tests`: 22 passed with `TYPECAST_USE_MOCKS=1`; 21 passed, 1 skipped (mock-only test) with `=0`. Real-branch tests use synthetic tables in a temp dir.

### Numbers (Los Angeles, `researchMarketId` 20)
- CoStar commercial properties: 3,339 (1,581 Los Angeles). Active Los Angeles listings: 380 (lease 313, sale 56, auction 11).
- Join method: shared id (`commercial-properties.csv` PropertyId to MatterportModelId). 1,554 of 1,581 have a scan; 269 are available; 260 are both. 1,270 properties have more than one scan, so `model_id` is the lowest id and `property_models.parquet` lists all.
- 46 of the 269 available properties have only a sale or auction listing and no lease listing; they are not confirmed vacant space.
- Matterport: the keys list 14,945 models; 5,919 of the 5,920 Los Angeles model ids in the kit are in that list; every `model_id` in the join is in it.
- By type with a scan: Multifamily 1,402, Office 90, Industrial 24, GeneralRetail 23, Flex 9, Specialty 3, Hospitality 1, Healthcare 1, Land 1.
- Vexcel live check: 8 available, scanned properties. Surface parking detected at 4; the other 4 returned 0 spaces with a caveat flag. An earlier 12-property probe: parcel plus 30 m found parking at 6 of 12. Geofencing probe: Princeton NJ and London both return HTTP 403 "Unauthorized by Geofencing permission".

### How to run the real branch
```bash
pip install -r data/requirements.txt
python data/join.py                         # needs cache/costar/ on this laptop
TYPECAST_USE_MOCKS=0 python -m pytest data/tests -q
TYPECAST_USE_MOCKS=0 python -c "from data.costar_tools import search_costar; print(len(search_costar()))"
# Vexcel: VEXCEL_API_KEY in the environment or .env. One property, cached after the first call:
TYPECAST_USE_MOCKS=0 python -c "from data.vexcel_tools import plan_logistics; print(plan_logistics('<property_id>'))"
```

### Owner 1 and Owner 3: join location and delivery
The join is `cache/join.parquet`, not `data/join.parquet`, and it must never be committed (it is CoStar-derived). It exists only on Owner 2's laptop. Owner 2 sends `cache/join.parquet` and `cache/property_models.parquet` to you privately (direct file copy, not Git); put them at `cache/join.parquet` and `cache/property_models.parquet` in your own checkout. Owner 1: use `property_models.parquet` for every scan of a property.

### Caveats (read before relying on the numbers)
- Parking is an estimate (`estimated` is always True): mask area of "parking lot" detections on the parcel plus 30 m, at 30 m2 per car; trucks are cars // 4. It cannot show permission, garages, street parking or truck clearance.
- Zero detections means unknown, not zero. The result is 0 spaces plus the flag "no surface parking detected in imagery; garage and street parking unknown". That flag sits in `noise_flags` only because the contract has no better field (see requests).
- Noise: freeway and rail are open-vocabulary detections within about 150 m, thresholds calibrated on only 3 known tiles and 12 ordinary properties (rail 3+ detections, freeway 6+). Embedding-search scores were tested and cannot separate real freeways from background, so they are not used. Airport noise is not implemented because it could not be validated.
- `walk_m` is the straight-line distance from the lot outline's centre to CoStar's point, not to an entrance.
- `year_built` is the ConstructionComplete year only (6 Los Angeles properties have none and stay None). Unknown year or size passes the year and size filters and stays None on the Property.
- Property types are CoStar names (`GeneralRetail`, not `Retail`).
- If Vexcel is geofenced or has no imagery, `plan_logistics` raises `VexcelUnavailable`, a `FileNotFoundError`, which the existing pipeline already skips as a missing source record.

### Contract change requests (for Owner 3; not made by Owner 2)
- Logistics: `truck_spaces` and `car_spaces` should allow None (unknown) and there should be a `caveats: list[str]` so "no parking detected" is not stored as 0 or as a noise flag.
- Property: an optional field saying the listing is for lease or only for sale, so sale-only listings are not shown as vacant space.

### Not done or not verified
- `python scripts/verify.py` was not run: this environment lacks `langchain_core` and `httpx`. Only `pytest data/tests` ran. Other lanes' tests were not run.
- origin/dev was not fetched or merged (no remote access this session).
- Demo-set precompute: cached for 8 properties only; no demo property list exists yet. Run `plan_logistics` for each demo id to cache it.
- `docs/team/OWNER-2-DATA.md` asks for `docs/team/status-lane-b.md`; this section is the lane status because docs/ is outside Owner 2's allowed files this session.
- Owner view data (step 9) not started.
