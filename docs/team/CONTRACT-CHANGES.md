# Contract changes

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

## Oblique search (exteriors and outdoors) — 2026-11-15

New, additive endpoints; consumer: `web/oblique.html`.
- `GET /api/oblique/areas` lists metro presets (LA, Houston) and the configured image model.
- `POST /api/oblique/search {query, area}` runs Vexcel semantic search over ortho-tile embeddings in the
  preset (capped at 16 records; oblique embeddings are not indexed for these collections), merges hits
  within 140 m, fetches one Vexcel oblique per place, reads Vexcel DTM along a 200 m cross and DSM at the
  centre (estimated terrain; never access or permission), and scores each oblique with one batched vision
  call. Cached privately under `cache/oblique/<search id>/`; a repeat query makes no provider calls.
- `POST /api/oblique/view {search_id, index, direction}` fetches one cardinal oblique once.
- `POST /api/oblique/reimagine {..., message}` edits the latest version with
  `TYPECAST_OBLIQUE_IMAGE_MODEL` (default `gpt-image-1-mini`) at `TYPECAST_OBLIQUE_IMAGE_QUALITY`
  (default `low`); every result is labelled "AI-imagined, not the real place".
No existing endpoint or response changes.

## Vexcel 3D Cities and the MCP place assistant — 2026-11-15

Additive; consumer: `web/oblique.html` place view.
- `GET /api/vexcel3d/place?lat&lon` returns the 3D collection, capture dates and tile URLs (zoom 19, ~280 m box)
  that point at `GET /api/vexcel3d/tile?zoom&tile-x&tile-y&childAOI`, a validated proxy to Vexcel `3d/tile`.
  Tilesets and tiles are cached under `cache/vexcel3d/`. The key never reaches the browser.
- `POST /api/oblique/ask {search_id, index, question}` answers with `TYPECAST_LLM_MODEL` calling Vexcel MCP
  tools (`https://api.vexcelgroup.com/v2/mcp`, key only to Vexcel). Read-only allowlist, trimmed parameters,
  geometry within ~2 km of the place, clamped buffers/records, at most 5 calls; the answer lists the tools used.

