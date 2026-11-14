# Contract changes

Baseline: contracts/schemas.py and schemas.ts at 6928661. No changes proposed yet.

For each proposal record owner, timestamp, fields/signatures, null semantics, producer/consumer lanes, fixture updates and migration. Integrator coordinates all affected consumers before merging. Prefer additive fields with defaults; never change coordinate order or units silently.

## Lane C additive contract v1 — 2026-11-14
Owner: integration captain. Producers: C; consumers: A/B/D. All new fields have defaults; TypeScript fields are optional for existing clients.
- Event: ts (seconds since run start, default 0), ms (optional duration), engine (optional fixed/deep). Adds tool/error/fallback event types.
- Evidence: source costar/matterport/vexcel, claim, status measured/estimated/unknown; Pick.evidence defaults to [].
- ShotFit.status: fits/tight/unknown. Unknown depth or ceiling is never fits=true; estimated geometry is at most tight.
- ScoutResponse: engine=fixed, source_mode=mock, trace_url=null (real traces only), timings={}.
- Runtime interface: RunContext and Requirements with explicit_fields; parse metadata remains internal.
Migration: existing API event names agent/result remain; consumers should render uncertainty and actual engine/source. Fixtures are updated together. No coordinates or units changed.
