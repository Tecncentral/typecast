# What is left to build

Read this after `docs/HANDOFF.md`. It says what exists in the repo today and what does not. Last updated Nov 14, 2026.

## Works today (verified by running it)

- `contracts/`: shared data shapes, Python and TypeScript.
- `mocks/`: fake properties, shots, logistics, picks and agent events. Addresses and ids are invented. The image files the mocks point to (`mocks/img/*.jpg`) do **not** exist yet.
- `index/geometry.py`: shot-fit maths. `index/cut_views.py`: cuts flat views from a 360-degree panorama (tested on a synthetic image, nearest-pixel sampling only).
- `index/search.py`, `data/costar_tools.py`, `data/vexcel_tools.py`: correct signatures, **mock data only**.
- `agent/pipeline.py`: fixed-order pipeline with a rule-based scene parser. `agent/app.py`: `POST /scout`, `GET /scout/stream` (server-sent events), `POST /refine`, `POST /approve`, static files at `/app`, `/mocks`, `/cache`.
- `bridge/core.mjs` and `bridge/terminal.mjs`: the text conversation, run end to end against the API.
- Tests: `pytest -q` (13 pass) and `cd bridge && node --test` (4 pass).

## Written but never run

- `bridge/photon.mjs`: needs Photon credentials.

## Not built (in priority order)

| # | Piece | Owner | Notes |
| --- | --- | --- | --- |
| 1 | Data check: one real panorama and scan positions from Matterport; `data/SCHEMA.md`; the join of CoStar records to scans | 1 and 2 | Decides whether Typecast is buildable. Do first |
| 2 | Real shot index: pull panoramas, cut views, embed with SigLIP or CLIP, store vectors, search with filters, example-shot search | 1 | `index/search.py` has a `NotImplementedError` where the real index loads |
| 3 | Room depth along the view direction (ray to the room outline) | 1 | Today depth comes straight from mock data |
| 4 | Real CoStar filter over the joined table | 2 | `NotImplementedError` in `data/costar_tools.py` |
| 5 | Real parking and noise from Vexcel; aerial image with the parking outline | 2 | `NotImplementedError` in `data/vexcel_tools.py` |
| 6 | deepagents harness: director, market / interior / logistics scouts, skeptic, to-do list, working files, approval on the owner note, LangSmith trace | 3 | Nothing written. Read the installed package for the real argument names. Keep `agent/pipeline.py` as the fallback |
| 7 | Model-based scene parsing and vision reranking of the top 20 shots | 3 | Parser is pattern matching today; there is no rerank |
| 8 | Web viewer: live agent panel, result cards, shot-fit diagram, map, 3D tour, LookAlike view, owner view | 4 | `web/` holds only a README. The API already serves `web/` at `/app/` |
| 9 | Photon line live on a real number | 4 | Ask Photon staff for a line; expose the API through a tunnel |
| 10 | Delivery of an approved note to the team inbox | 3 or 4 | `/approve` returns `sent: false` with a TODO |
| 11 | Evaluation: 20 labelled scenes, recall at 10 | 1 and 3 | No script yet |
| 12 | Peri interview, Devpost text, pitch, backup video | 4 | Templates in `docs/` |
| 13 | Stretch: phone-as-window panorama viewer, voice line, nonprofit search, World Labs | any | Only after 1 to 12 |

## Known gaps in what exists

- The fixed pipeline ranks by a mock score; there is no real relevance yet.
- `/scout/stream` replays events after the run finishes. It is not live step by step.
- Thread state is in memory and is lost on restart.
- Era handling is a simple year cut-off.

## An earlier attempt that left nothing

Three build agents were started for items 2 to 8 and were cut off by a usage limit before committing. None of their work is in the repo. Do not look for it.

## How to continue

Each owner checks out their lane branch, pastes the kickoff prompt from `docs/HANDOFF.md` into their coding agent, and adds: "Read docs/REMAINING.md. Start with the lowest-numbered item for your owner number." Have each agent commit after every passing task so an interruption loses nothing.
