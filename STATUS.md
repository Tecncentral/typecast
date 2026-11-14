# Status

Full list of what is and is not built: `docs/REMAINING.md`.

Update your own section before you stop. Keep it short: works / broken / next / waiting on.

## Shared
- works: repo scaffold, contracts, mocks, shot-fit maths, panorama view cutter, fixed-order pipeline and `/scout` endpoint running on mocks. `pytest` passes.
- next: first hour together: agree contracts, set `.env`, Owner 2 publishes `data/join.parquet`.

## Owner 1 (index/)
- works: `check_shot`, `cut_views` (tested on a synthetic panorama), `search_shots` on mocks
- next: access test against one real Matterport model

## Owner 2 (data/)
- works: tool signatures on mocks
- next: `data/SCHEMA.md`, then `data/join.parquet`

## Owner 3 (agent/)
- works: fixed-order pipeline + FastAPI endpoints on mocks
- next: deepagents harness with the four subagents

## Owner 4 (web/, bridge/, docs/)
- works: text conversation logic and terminal chat (bridge/), run end to end; Photon adapter written, not run
- next: run view on `mocks/pick.json` and `mocks/events.jsonl`
