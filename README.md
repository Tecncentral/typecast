# Typecast

Typecast turns a screenplay scene into a shortlist of real Los Angeles and Houston buildings, with interior views and evidence for availability, crew parking and shot-fit uncertainty. A location scout or student filmmaker can ask for more truck parking, watch the shortlist change, and approve a local inquiry draft. The draft is never sent automatically.

Built at HackPrinceton Fall 2026 on CoStar property data, Matterport 3D scans and Vexcel aerial imagery.

**Try it:** [typecast-2yp7.onrender.com/app/](https://typecast-2yp7.onrender.com/app/) runs the viewer on sample data, so anyone can open it. It shows fixture places labelled as synthetic, not licensed CoStar, Matterport or Vexcel data. The first load can take about a minute while the free server wakes up.

**Devpost:** [devpost.com/software/typecast-vlfhio](https://devpost.com/software/typecast-vlfhio)

For production teams, `/director` adds a home/base pin, a one-way commute limit, an editable USD cost comparison and opt-in imagined scene previews. See the [business case and sourced savings scenarios](docs/BUSINESS-CASE.md). The savings are calculated scenarios. No studio savings have been measured.

## Demo walkthrough

Start at `/app/` with **Warehouse handoff**. Agent activity leads into the **inside-out descent**: the property map gives way to its Vexcel aerial, then to a real Matterport frame. Open **Look around** to compose in the **360° viewfinder**, change the lens from **24 to 50 mm**, and press **D** when **AI dressing** is offered. A wipe compares the real scan with the imagined set. Ask for five trucks, then open `/director`. The Director's Room groups script scenes across buildings to show the trade-off between visual similarity and company moves.

Sources: [descent](web/descent.js), [viewfinder and lens controls](web/viewfinder.js), [production planner](index/production.py). The rehearsal script is in the [runbook](docs/demo-runbook.md).

The Director's Room optimizes within its retrieved candidate pool, not every building in the catalog. Its move count assumes one visit per chosen property. It is not a timed travel schedule or proof of production savings.

The public sample site does not include the private Matterport frames or AI dressing. Those need the licensed data described under [Setup: private live data](#setup-private-live-data).

## What is real and what is AI-generated

- **Real source evidence:** Matterport scan imagery, exact CoStar property associations and attributed Vexcel aerials. Parking is estimated. Missing physical measurements stay unknown.
- **AI-imagined dressing:** World Labs Atlas derives posed depth from the real scan faces, then reuses those depth constraints while changing appearance. The comparison always carries "AI-imagined set dressing, not the real room". It does not certify exact measured geometry, buildability or an art department's budget. Source: [dressing implementation](worlds/dress.py) and [verified scope](docs/team/status-worlds.md).
- **Scope:** Only image dressing is verified. Walkable interior splats are not claimed. World Labs is a tool Typecast uses, not a competition track.

## How it works

1. Parse the scene and crew requirements. The deep director writes a plan, then the market scout loads the city's candidate buildings.
2. Run the interior and logistics scouts at the same time: retrieve camera views, score visual relevance, check geometry and inspect cached parking and noise evidence.
3. Build the shortlist and ask a skeptic to challenge it with source-backed objections. Missing measurements stay unknown.
4. Stream real tool progress and return the picks. A follow-up reranks the saved candidate pool. Approval creates an unsent local draft.

| Data layer | What it decides | What it cannot establish |
| --- | --- | --- |
| CoStar | Property identity, city and type, recorded lease availability, active listing categories | Filming permission, actual vacancy or owner consent |
| Matterport | Interior camera views, visual retrieval, available scan geometry | A verified shot fit when depth or ceiling height is missing |
| Vexcel, with OpenStreetMap context | Aerial evidence, estimated parking capacity, proximity to noise sources | Guaranteed access, measured sound levels or quiet |

The fixed engine runs the same source operations in a defined sequence. The deep engine uses Deep Agents planner, scout and skeptic graphs. More detail: [architecture](docs/architecture.md), [two-minute pitch](docs/pitch.md), [Devpost draft](docs/devpost.md).

## Evaluation

The same 15 test scenes and one human review support the frozen v1 and **v2 (after changes informed by v1)**. Defaults were chosen on five separate tuning scenes before the single v2 pass. All figures come from the [frozen evaluation and post-change repeat](docs/team/eval.md).

| Metric | Frozen v1 | v2 after changes informed by v1 |
| --- | ---: | ---: |
| Precision@10 lower bound | **66.00%** (99/150) | **73.33%** (110/150) |
| Mean pooled recall@10 | 27.06% | **30.48%** |
| Successful fixed/live requests | 15/15 | 15/15 |
| Median / p95 request seconds | 14.539 / 19.693 | 16.057 / 24.459 |

Precision counts unjudged returns as misses: two in v1, eight in v2. Judgments cover frozen global top-40 pools. 140 of 352 positives are in Houston, while the city-free test prompts default to Los Angeles, so ten results and that city restriction cap macro recall at 37.90% (48.14% without the restriction).

V2 is a repeat on the same test set, not a new untouched holdout. Neither result establishes exhaustive relevance, reviewer agreement, final-card quality or statistically significant improvement. Verified trace links were returned for 13/15 v1 requests and 15/15 v2 requests. The [full report](docs/team/eval.md) covers tune selection, the one-pass v2, costs and a corrected parser-event labelling defect.

## Coverage and performance

The November 14 private index holds **10,568 views across 343 properties and 329 models**. It covers all 307 mapped, available commercial properties plus 20 available multifamily properties. Sixteen more available commercial properties have no supplied scan mapping.

| City | Available office | Industrial | Flex | Retail | Multifamily | Retained unavailable/unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Los Angeles | 75 | 8 | 3 | 15 | 10 | 16 |
| Houston | 127 | 50 | 9 | 20 | 10 | 0 |

All 343 indexed properties have cached aerials and OSM noise screening. Parking is estimated for 224 and unknown for 119. Proximity screening flags 128 properties and does not establish measured sound levels at unflagged sites. One mapped walking route is estimated and 342 are unknown. Five Vexcel parcel-detail requests returned 404, though imagery succeeded. Shot depth is unmeasured. Source: [coverage report](docs/team/status-lane-c.md).

On the five-scene demo set, both engines completed real-data runs with model parsing, vision reranking, three-source evidence, LangSmith traces, same-thread refinement and unsent draft approval. In the latest stage rehearsal all 10 strict checks passed. Warm medians were **8.923 s fixed and 40.923 s deep**, and Warehouse handoff took 9.398 s and 48.135 s. These are backend and cache checks, separate from a full judge-path run. Earlier rehearsals, the selected 20/5/5 rerank settings and timing history are in the [stage report](docs/team/status-lane-c.md) and [runbook](docs/demo-runbook.md).

## Setup: mocks

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock.txt
test -f .env || cp .env.example .env
python scripts/verify.py
TYPECAST_USE_MOCKS=1 TYPECAST_ENGINE=fixed TYPECAST_ENABLE_MODEL_PARSE=0 TYPECAST_ENABLE_VISION_RERANK=0 \
  LANGSMITH_TRACING=false uvicorn agent.app:app --host 127.0.0.1 --port 8000
```

```bash
curl -s localhost:8000/scout -H 'content-type: application/json' \
  -d '{"scene":"INT. 1980s POLICE STATION, NIGHT. Parking for 3 trucks and 30 crew cars."}'
```

The fixture images are labelled synthetic placeholders. Mock runs check setup and the interface. They are not evidence of retrieval quality. A fresh checkout defaults to the fixtures in `mocks/`.

## Setup: private live data

Provision the private `cache/join.parquet`, the frozen `cache/shot-index/` generation, the referenced interior frames and `cache/vexcel/` evidence separately. A public checkout does not contain these licensed assets. Keep the caches private and serve them only on the local machine.

Configure model credentials and model IDs in the ignored `.env`. Matterport and Vexcel keys are needed only to acquire and precompute data. Optional LangSmith credentials enable traces.

Install the retrieval dependencies with `.venv/bin/pip install -r requirements-index.lock.txt`, and provision `sentence-transformers/clip-ViT-B-32` in the local Hugging Face cache. The index and text encoder must use the same model. See [index setup](index/README.md).

```bash
TYPECAST_USE_MOCKS=0 TYPECAST_ENGINE=deep \
  TYPECAST_ENABLE_MODEL_PARSE=1 TYPECAST_ENABLE_VISION_RERANK=1 \
  TYPECAST_ALLOW_VISION_UPLOAD=1 \
  .venv/bin/python -m uvicorn agent.app:app --host 127.0.0.1 --port 8000
```

Use a model-processing setup that is permitted for private imagery. A scene without a city searches Los Angeles and says so. Naming Houston searches Houston. The viewer and Director's Room are served from port 8000.

## Configuration

| Variable | What it does |
| --- | --- |
| `LLM_API_KEY`, `VISION_API_KEY` | Model credentials, set in `.env` |
| `TYPECAST_LLM_MODEL`, `TYPECAST_VISION_MODEL` | Provider model IDs |
| `TYPECAST_ENGINE=fixed\|deep` | Execution engine. Responses report the engine that actually finished |
| `TYPECAST_ENABLE_MODEL_PARSE`, `TYPECAST_ENABLE_VISION_RERANK` | Set to `0` to turn off model parsing or vision reranking |
| `TYPECAST_ALLOW_VISION_UPLOAD=1` | Required to send images for vision scoring |
| `TYPECAST_RERANK_POOL`, `TYPECAST_VISION_CONCURRENCY`, `TYPECAST_VISION_BATCH_SIZE` | Rerank tuning. Defaults are 20, 5 and 5 |
| `MATTERPORT_API_KEY`, `MATTERPORT_API_SECRET` | Matterport acquisition. The browser SDK key is separate |
| `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_TRACING` | Optional tracing |

Check that credentials are present without exposing them:

```bash
python scripts/check_access.py
python scripts/check_access.py --network  # read-only OpenAI/Matterport/Vexcel checks
```

## API

- `GET /scout/stream` sends `event: agent` while tools run, then `event: result`. Failures end with `event: error`.
- `POST /scout` uses the same runtime and returns one response.
- `/refine` keeps the thread and reranks the saved candidates without new property or shot searches. A known geometric failure is rejected. Unknown or estimated fits stay unverified.
- `GET /config` returns `mode`, `engine`, `tracing` and `matterport_sdk_key` only. API credentials are never included.

Approval saves a draft under the ignored `cache/outbox/` and always reports `sent=false`. A trace URL is returned only after the completed run is retrieved. If tracing fails, the scout still succeeds with `trace_url=null`.

The deep engine falls back visibly to the fixed engine after a failed run or a 90-second deadline. A provider rate limit stops further model calls in that worker process and is recorded, not retried. More detail on the director, reranker and evaluation tooling is in [architecture](docs/architecture.md) and the [evaluation report](docs/team/eval.md).

## Tests and evaluation

```bash
python scripts/verify.py
python scripts/e2e.py
python agent/eval/run_eval.py --mode mock --output cache/evaluation/mock-report.md
```

The benchmark has 15 test and 5 tuning scenes. Mock runs never produce an accuracy claim, because empty labels are skipped. Keep real labels in the ignored `cache/`. Never use held-out test judgments for tuning. The private demo checks (`scripts/check_demo.py`, `scripts/check_demo_browser.py`, `scripts/check_tracing.py`) are described in the [runbook](docs/demo-runbook.md).

## Layout

| Folder | What |
| --- | --- |
| `contracts/` | Shared data shapes (Python and TypeScript) |
| `mocks/` | Fake data for building and testing |
| `index/` | Shot index: panorama views, embeddings, geometry, search, shot fit |
| `data/` | CoStar filter, the join to scans, Vexcel parking and noise |
| `agent/` | Agent, pipeline, HTTP API |
| `web/`, `bridge/` | Viewer and messaging bridge |
| `docs/` | Handoffs, measured results, pitch and submission drafts |

## Limits

Marketed lease availability does not establish vacancy or filming permission. Parking is an estimate, unmeasured shot depth stays unknown and proximity flags are not sound measurements. Cached evidence reduces provider dependence, but the live parser and director still need a model API connection. AI dressing is an imagined proposal, and the real-room evidence stays separately accessible. Never commit keys or CoStar data. `.env` and `cache/` are git-ignored.

## Team

| Role | Team member |
| --- | --- |
| Interiors and retrieval | Logan |
| Property and aerial evidence | Udit |
| Agent and integration | Zukhriddin |
| Viewer and presentation | Prateek |
