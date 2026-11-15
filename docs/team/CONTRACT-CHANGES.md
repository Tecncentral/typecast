# Contract changes

## Producer recce memo / prospective pilot case — November 15, 2026

`index/producer-brief.js` exposes `TypecastProducerBrief.normalizeCase`, `renderHtml`, `renderText`, `exportJson`, and `importCase` (UMD/Node). Input is a bounded allowlisted `{version:1, project:{name,reviewer,decision,date}, plan:{mode,current,fingerprint,sceneCount,covered,locations,moves,propertyIds,unknowns,constraintsSummary,sceneAssignments}, budget:{assumptions,result}, pilot:{baselineUnits,actualUnits,baselineCost,actualCost,source,notes}}`. Scene assignment keys accept camelCase or existing snake_case identifiers and normalize to camelCase. Financial fields follow the additive economics result contract; optional `assumptions.routeMinutes` records the selected one-way estimate without an origin coordinate. Rendered memos include the units, rates, mileage, travel, crew and avoidability inputs needed to interpret the projection.

All exports require caller-recomputed `plan.current===true` and an opaque plan fingerprint (not raw constraints JSON). Imports are size-bounded, normalized, immutable and forcibly `plan.current=false`; importing never makes saved financial results or reported pilot outcomes source truth. Rebuild the current plan and recompute budget before rendering/export. Unknown fields, source images/raw rows and structured origin coordinates are omitted. Blank pilot values normalize to null; no causal savings percentage is inferred. Financial outputs remain projected, pilot entries remain producer-reported, and the memo explicitly leaves filming permission and post-event data rights unresolved. HTML text is escaped; recognizable credentials in allowed text are rejected without echoing values.

## Production planning / business decision additions — November 15, 2026

Coordinated in PR #43, additive to the shared production router; existing agent tools reuse `PlanRequest` and old clients omit new fields unchanged. No change to Property/Shot/Logistics or dependency locks.

- `POST /api/production/plan`: optional `commute: {lat:number -90..90, lon:number -180..180, max_minutes:number 5..180}`. Degrees and one-way minutes; finite, booleans rejected. Present enables a hard road-time filter; unknown/unreachable routes exclude candidates. Response adds `commute_limit_minutes:number|null` and candidate `commute: {status,minutes:number|null,miles:number|null,source,traffic:false,checked_at?,note?}|null`. No origin is returned or persisted in project exports/drafts. A filtered request considers up to 24 retrieved properties total. Old top-three-per-scene behavior remains without it.
- `POST /api/production/customize-image`: `{shot_id, instruction (1..2000 nonblank chars), confirm_image_upload:true}`. Existing upload env opt-in, real index and configured image provider required. Returns `{image_url, source_shot_id, label, kind:'imagined-single-frame', geometry_verified:false}`. Private no-store image route is UUID-token scoped. Source and project takes remain unchanged; cache ignored. No automatic regeneration or fake fallback.
- Brainstorm UI now uses its existing 2000-character backend limit; output schema unchanged. Approved creative notes are saved as unrendered suggestions. Undo restores prior notes unless subsequently edited by the user.
- Cost arithmetic is browser-local USD scenario math, not a factual savings API. Day-rate preset cites the applicable commercial reference; assumed eliminated days remain editable. No dependency added. `web/index.html` receives only an additive production-planner link.

Baseline: contracts/schemas.py and schemas.ts at 6928661. Accepted additive changes are recorded below.

For each proposal record owner, timestamp, fields/signatures, null semantics, producer/consumer lanes, fixture updates and migration. Integrator coordinates all affected consumers before merging. Prefer additive fields with defaults; never change coordinate order or units silently.

## Lane C additive contract v1 — 2026-11-14
Owner: integration captain. Producers: C; consumers: A/B/D. All new fields have defaults; TypeScript fields are optional for existing clients.
- Event: ts (seconds since run start, default 0), ms (optional duration), engine (optional fixed/deep). Adds tool/error/fallback event types.
- Evidence: source costar/matterport/vexcel, claim, status measured/estimated/unknown; Pick.evidence defaults to [].
- ShotFit.status: fits/tight/unknown. Unknown depth or ceiling is never fits=true; estimated geometry is at most tight.
- ScoutResponse: engine=fixed, source_mode=mock, trace_url=null (real traces only), timings={}.
- Runtime interface: RunContext and Requirements with explicit_fields; parse metadata remains internal.
Migration: existing API event names agent/result remain; consumers should render uncertainty and actual engine/source. Fixtures are updated together. No coordinates or units changed.

## Integration clarification — 2026-11-14
- Event type `rerank` reports actual skipped/completed visual ranking, with existing generic Event shape. Added to TypeScript union.
- Concurrent callbacks serialize timestamp assignment and emission so streamed timestamps preserve event order.
- `POST /approve` on a deep-engine thread resumes the saved deepagents human-approval checkpoint; fixed-engine threads save a local draft directly. Both always return sent=false.

- Event type `trace` reports a traced run whose real URL could not be retrieved. It does not supply or invent a URL.

## Viewer configuration — 2026-11-14

Owner: C; consumer: D. Additive `GET /config` returns exactly four fields:

- `mode`: `mock`, `live`, or `mixed` if adapter settings disagree.
- `engine`: configured `fixed` or `deep`; the completed scout response still reports the actual engine after any fallback. Invalid engine configuration returns a sanitized 503.
- `tracing`: boolean reflecting configured/enabled tracing; it does not guarantee a trace will succeed.
- `matterport_sdk_key`: public browser SDK application key or null. No model/API secret is returned. SDK values that alias private credential values are suppressed.

Matterport's [official Embed SDK guide](https://developers.matterport.com/embed-sdk/) documents applicationKey in browser code and domains in the key allowlist. Lane D may use this key for its browser viewer; `/health` and all existing response contracts remain compatible.

## Lane B live uncertainty — 2026-11-14

Owner: C integration captain, coordinated with both B adapter implementers. Producers B; consumers C/D and bridge.

- Property adds optional `availability_status` (`available`, `not_available`, `unknown`), `availability_reason`, and `parking_flags` (documented boolean CoStar fields). Legacy `available` stays boolean; unknown is false and must be rendered as unknown using the status. A missing status preserves legacy fixture behavior.
- Logistics `truck_spaces` and `car_spaces` may now be null: unknown capacity is not zero. Existing numeric fixtures remain valid. Consumers must use an unknown label for null, and cannot accept unknown capacity against a positive requirement.
- Logistics adds optional per-field `parking_status`, `walk_status`, `noise_status` (measured/estimated/unknown), `parking_area_m2`, `source_notes`, and `source_evidence`. Explicit status overrides the legacy `estimated` flag. Empty noise flags with unknown status do not mean quiet.
- Coordinates remain `[lat, lon]`, area is square metres, walk is metres. Source evidence separates recorded CoStar parking flags from imagery estimates; no personal contact fields are added.
- C updates evidence, ranking and skeptic wording; D should render these optional fields and nulls. All new fields default to absent/empty, except missing capacity defaults null.
- SAM3 mask follow-up: optional Logistics.parking_geometry is standard GeoJSON Polygon/MultiPolygon with **[longitude, latitude]** coordinates and interior rings, so real mask holes and disjoint regions survive. The legacy parking_polygon remains **[latitude, longitude]** and is empty when a single ring cannot accurately express the geometry. The annotated aerial always depicts the actual mask; consumers should prefer parking_geometry when available.

## Active listing categories — 2026-11-14

Owner: C integration captain, requested by Owner 2; producers B, consumers C/D.
Property adds `listing_types: list["lease" | "sale" | "auction"]`, default empty.
It records distinct categories of linked **Active** commercial listings, decoded
from the supplied ListingType enum. Multiple categories can coexist. Empty means
no recognized active category, not proof that the property is off market.
Sale/auction never imply lease-space availability; availability rules are unchanged.
Older private joins without this additive column return an empty list until rebuilt.

## Default-city notice — 2026-11-14, Job 5

Owner: C integration captain; producers C, consumers D and bridge. Additive
`ScoutResponse.notes: list[str] = []` carries factual search-scope notices.
The TypeScript field is optional for existing clients. An event with type
`notice` and agent `runtime` also streams the same text when a scene has no
explicit city and the existing parser selected Los Angeles:
"No city named; searched Los Angeles. Name Houston to search there."
This does not change filtering, city defaults, source data or reranking. Refine
responses retain the original search-scope note. Named-city and example-image
queries do not receive this default-city notice. Viewer consumers may render
notes above the result cards; ignoring the optional field remains compatible.

Vision accounting remains in the existing `rerank` event shape. `rate_limit`
reports a real provider HTTP 429 and stops additional model calls in the worker
process; a deep failure caused by that limit must not retry through fixed.
No credentials or raw provider responses are exposed in these events.
`model_request` reports only provider-call and image-count accounting; it never
contains the scene, image payload, property identifiers or credentials.

## Aerial extent metadata — 2026-11-14, Job 6

Owner: D, explicitly authorized by the inside-out descent brief; consumer: viewer.
Additive `GET /api/aerial/{property_id}` returns only `property_id`,
`crs: "EPSG:3857"`, `extent: [west,south,east,north]` in metres, actual PNG
`width`/`height`, the matching `image_path`, and source `coordinates: [lat,lon]`.
The route accepts only numeric property ids with a validated, bound local cache.
Missing, stale, mismatched, symlinked or malformed metadata returns a sanitized
404. Responses use `Cache-Control: no-store`; general `/cache/` JSON access stays
blocked. No listing records, contacts or provider payloads are returned.

The viewer projects standard GeoJSON `[lon,lat]` rings, including holes, or the
legacy `[lat,lon]` ring into the matching unannotated image. It rejects unsupported
or out-of-bounds geometry and falls back to revealing the supplied annotated
aerial unchanged. No new polygon or building-centroid claim is inferred. No
existing response schema or endpoint behavior changes.


## Director project JSON: production decisions (client-only, additive) - 2026-11-14

Owner: lane-a (Director). Producer and consumer: `index/director.js` and `index/director-project.js`; no backend, `contracts/schemas.py` or TypeScript change, no coordinate or unit change.
- Optional per-scene `location_choice`: `{shot_id, property_id, from_shot_id, from_property_id, staging_reviewed}`. Identifiers match `^[\w.:-]+$` (<=120), `staging_reviewed` is a required boolean; requires `evidence.frame`. Meaning: the user swapped this scene to another candidate; `staging_reviewed:false` means the staging was carried over and not verified on the new frame.
- Optional per-scene `notes`: `{dressing, group}`; `dressing` <=600 characters (control characters stripped on import), `group` <=12 characters `[A-Za-z0-9_-]`. User text only; never sent to a model.
- Optional per-variant `origin: "authored-sample"` (already recorded in the sample work) is the only accepted origin value.
- Null semantics: absent means none; old files import unchanged. A saved choice is restored only if the same exact frame is an eligible candidate in the fresh plan response; otherwise the staging is retained for review. Rejections are reset by import, so none can leak back. Top-level `locations`, `company_moves` and `mean_similarity` are null (with `plan_note`) when a hand swap exists.
- Migration: none required; files without these fields behave as before.


## Director project JSON: community planning and local drafts (client-only, additive) - 2026-11-15

Owner: lane-a (Director). Producer/consumer: `index/director.js`, `index/director-project.js`; no backend, `contracts/` or coordinate/unit change.
- Optional top-level `mode`: only the exact string `"community"` is accepted (absent means film; any other value is refused). Optional `brief`: `{reviewer<=40, date<=20, notes<=600}`; optional `needs[]` (<=8, unique `scene_id` that exists): `{scene_id, requested_count: integer 0..100000 or null, note<=600}`; optional `sites[]` (<=48, unique `scene_id`+`property_id`, both id-pattern checked): `{checks: {permission|capacity|exits|access|toilets|utilities|hazards: {state: unknown|ok|issue, note<=200}}, verified: {capacity: integer, source<=80} (kept only with a non-empty source), tasks[] (<=6): {text 1..120, owner<=40}}`. Unknown check keys, states, extra shapes and duplicates are refused; control characters are stripped.
- Meaning: all values are human-reported by the coordinator and never source-measured; `ok` is never verification. On import they are restored with `ok` marked "restored; re-verify". Community scenes export `variants: null`.
- Local draft (browser storage, not a file contract): keys `typecast.director.draft.v1.film|community` and `typecast.director.draft.optout`; value `{v:1, mode, script, constraints{maxLoc,trucks,cars,reqAvail}, project (this schema, evidence reduced to frame identifiers), saved_at}`; <=300 KB; anything else is discarded.
- Migration: none; old files import unchanged.


### Amendment (independent review) - 2026-11-15
- `sites[].verified` is now `{capacity: integer or null, source: string <=80, may be empty}` (null overall when both are empty): a capacity without a source, or a source without a number, is kept as incomplete input and is **not** treated as verified anywhere. Previously a number without a source was dropped.
- Community files never restore film data: on import in community mode `variants`, `notes`, `location_choice` and review drafts are ignored.
- Local draft value additionally carries `plan_script` (the script text the saved plan was built from). Unreadable or newer-version drafts are moved to `typecast.director.draft.v1.<mode>.unreadable` (one slot per mode, at most 400,000 characters) rather than deleted.
- Internal only: community site records are keyed `site:<scene>|<property>` (ids never contain `|`), so ids containing colons round-trip intact.

### Save the scene decision record (`v: 1`, commit `39077b6ca7bafd0f127dbbb307ff1fc69fbbdef3`)

- **Additive Project JSON / Draft Recovery Field (`scenes[].decision`):** Optional Film-mode object validated by `decisionOf` in `index/director-project.js` and produced by `TypecastChecks.decisionRecord` in `index/director-checks.js`. Absent in Community mode and omitted when no Save decision was applied.
- **Shape & Bounds:**
  - `v`: `1` (integer)
  - `decided_at`: ISO timestamp string (`<= 30` chars)
  - `original` / `revised`: `{ trucks: int 0..20, cars: int 0..200, require_available: boolean }`
  - `before` / `after`: `null` or `{ shot_id, property_id, parking_status ('measured'|'estimated'|'unknown'), enough_parking (boolean|null), availability ('available'|'not_available'|'unknown'), area_m2 (number|null), ceiling_m (number|null), similarity (number 0..1|null) }`
  - `scope`: `'whole_plan'`, `totals_recalculated`: boolean, `moved_scenes`: int `0..8`, `differences`: array of `<= 8` strings (`<= 240` chars), `unresolved`: array of `<= 8` strings (`<= 200` chars).
- **Trust Boundary:** Treated strictly as a historical review note in UI and Shoot pack exports; re-importing re-queries `/api/production/plan` and never promotes cached `decision` fields into current source evidence.

## Crew vehicles and CoStar recorded parking — 2026-11-14

Additive, optional; consumer: viewer map and change summary.
- `ScoutResponse.vehicles: {trucks, cars} | null` is the crew demand the picks were
  checked against (both engines). The viewer draws demand against each lot with it;
  without it the viewer shows trucks from the allocation and leaves the fit unconfirmed.
- `Property.parking_spaces: {type: count}` is CoStar's recorded `parking[].totalSpaces`
  by labelled `ParkingType` (e.g. `{"Surface": 73, "Covered": 129}`), read from the
  private extract `cache/costar-parking.json` (`python -m data.costar_parking`, about
  1 s). Absent file or record means `{}`. The pipeline adds it as CoStar evidence and,
  when trucks are requested and recorded surface spaces are below the demand, a
  caveat that is not a blocker.
No existing field or endpoint behavior changes.

