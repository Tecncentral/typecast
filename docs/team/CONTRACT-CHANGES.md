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
