# Typecast

**Business/Enterprise · production location decisions.** Compare real spaces before committing scouting days: `/director` adds a home/base pin, one-way commute limit, editable USD cost comparison, and opt-in imagined scene previews. See the [business case and sourced savings scenarios](docs/BUSINESS-CASE.md). Savings are calculated scenarios; no studio savings have been measured.

Typecast turns a screenplay scene into a shortlist of real Los Angeles and Houston buildings, with interior views and evidence for availability, crew parking and shot-fit uncertainty. A location scout or student filmmaker can ask for more truck parking, see the shortlist change, and approve a local inquiry draft that is never sent automatically.

Built at HackPrinceton Fall 2026 on CoStar property data, Matterport 3D scans and Vexcel aerial imagery.

**Try it:** [typecast-2yp7.onrender.com/app/](https://typecast-2yp7.onrender.com/app/) runs the viewer on sample data, so anyone can open it. It shows fixture places labelled as synthetic, not licensed CoStar, Matterport or Vexcel data. The first load can take about a minute while the free server wakes up.

**Devpost:** [devpost.com/software/typecast-vlfhio](https://devpost.com/software/typecast-vlfhio)

**Screenshot placeholder:** add a human-approved screenshot of the merged viewer. Its descent and viewer checks are recorded in [lane D's acceptance report](docs/team/status-lane-d.md); the combined stage judge-path check is a separate gate. Do not publish private contacts or licensed imagery without the applicable sharing permission.

## The judging demo

Start at `/app/` with **Warehouse handoff**. Actual agent activity leads into the **inside-out descent**: the property map gives way to its Vexcel aerial, then its real Matterport frame. Open **Look around** to compose in the **360° viewfinder**, change the lens from **24 to 50 mm**, and press **D** when **AI dressing** is offered. A wipe compares the real scan with the imagined set. Ask for five trucks, then open `/director`: the **Director's Room** groups script scenes across buildings to expose the trade-off between visual similarity and company moves. Sources: [descent](web/descent.js), [viewfinder and lens controls](web/viewfinder.js), [production planner](index/production.py).

The Director's Room optimizes within its retrieved candidate pool, not every building in the catalog. Its move count assumes one visit per chosen property; it is not a timed travel schedule or proof of production savings. The rehearsal script and accepted grouping belong in the [runbook](docs/demo-runbook.md).

## What is real vs AI-generated

- **Real source evidence:** Matterport scan imagery, exact CoStar property associations and attributed Vexcel aerials. Parking is estimated; missing physical measurements remain unknown.
- **AI-imagined dressing:** World Labs Atlas derives posed depth from the real scan faces, then reuses those depth constraints while changing appearance. The comparison always carries **“AI-imagined set dressing, not the real room”**. This addresses consistent refurnishing of a scanned room; it does not certify exact measured geometry, buildability or an art department's budget. Source: [dressing implementation](worlds/dress.py) and [verified scope](docs/team/status-worlds.md).
- **Scope boundary:** the merged evidence verifies image dressing. Walkable interior splats remain unclaimed until the owning session supplies merged implementation and a verified result. World Labs is a tool used by Typecast, not a claimed competition track.

## How it works

1. Parse the scene and crew requirements. The deep director writes a plan, then the market scout loads the city's candidate buildings.
2. Run the interior and logistics scouts concurrently: retrieve camera views, score visual relevance, check geometry and inspect cached parking/noise evidence.
3. Build the shortlist and ask the skeptic to challenge it with source-backed objections. Missing measurements remain unknown.
4. Stream actual tool progress and return the picks. A follow-up reranks the saved candidate pool; approval creates an unsent local draft.

| Data layer | What it decides | What it cannot establish |
| --- | --- | --- |
| CoStar | Property identity, city/type, recorded lease availability and active listing categories | Filming permission, actual vacancy or owner consent |
| Matterport | Interior camera views, visual retrieval and available scan geometry | A verified shot fit when depth/ceiling is missing |
| Vexcel, with OpenStreetMap context | Aerial evidence, estimated parking capacity and proximity to noise sources | Guaranteed access, measured sound levels or quiet |

The fixed engine executes the same source operations in a defined sequence. The deep engine uses actual Deep Agents planner/scout/skeptic graphs. [Architecture](docs/architecture.md) · [Demo runbook](docs/demo-runbook.md) · [Two-minute pitch](docs/pitch.md) · [Devpost draft](docs/devpost.md).

## Evaluation

The same 15 test scenes and one human review support the frozen v1 and **v2 (after changes informed by v1)**. Defaults were selected only on the five separate tune scenes before the single v2 pass.

All figures in this section come from the [frozen evaluation and post-change repeat](docs/team/eval.md).

| Metric | Frozen v1 | v2 after changes informed by v1 |
| --- | ---: | ---: |
| Precision@10 lower bound | **66.00%** — 99/150 | **73.33%** — 110/150 |
| Mean pooled recall@10 | 27.06% | **30.48%** |
| Successful fixed/live requests | 15/15 | 15/15 |
| Median / p95 request seconds | 14.539 / 19.693 | 16.057 / 24.459 |

Precision counts unjudged returns as misses: two in v1, eight in v2. Judgments cover frozen global top-40 pools; 140 of 352 positives are in Houston, while these city-free test prompts default to Los Angeles. Ten results and this city restriction cap macro recall at **37.90%** (or **48.14%** without that city restriction). V2 is a post-change repeat on the same test set, not a new untouched holdout. Neither result establishes exhaustive relevance, reviewer agreement, final-card quality or statistically significant improvement. All requests succeeded; verified trace links were returned for 13/15 v1 requests and 15/15 v2 requests. The [full report](docs/team/eval.md) preserves the original v1 text and documents tune selection, the one-pass v2, costs and a corrected parser-event labeling defect.

## Verified coverage and demo performance

Both fixed and deep engines have completed real-data runs with model parsing, vision reranking, CoStar/Matterport/Vexcel evidence, LangSmith traces, same-thread refinement and local draft approval. Private sources must be provisioned separately; a fresh checkout defaults to explicit fixtures in `mocks/`. See [verified integration status](docs/team/status-lane-c.md) for coverage, timings and remaining evidence limits.

The November 14 private index contains **10,568 views across 343 properties and 329 models**, built in 14.15 minutes while preserving the original 608 views. It covers all 307 mapped, available commercial properties plus 20 available multifamily properties. Sixteen additional available commercial properties have no supplied scan mapping. The counts and city breakdown below are from [lane C's frozen-index coverage report](docs/team/status-lane-c.md#available-interior-coverage-and-frozen-index--2026-11-14-1643-utc).

| City | Available office | Industrial | Flex | Retail | Multifamily | Retained unavailable/unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Los Angeles | 75 | 8 | 3 | 15 | 10 | 16 |
| Houston | 127 | 50 | 9 | 20 | 10 | 0 |

All 343 indexed properties have cached aerials and OSM noise screening. Parking is estimated for 224; 119 remain unknown. Proximity screening flags 128 properties and does not establish measured sound levels or quiet at unflagged sites. One mapped walking route is estimated; 342 remain unknown. Five Vexcel parcel-detail requests returned 404, while imagery succeeded. Shot depth remains unmeasured. Source: [cached evidence coverage](docs/team/status-lane-c.md#expanded-evidence-and-frozen-human-evaluation--2026-11-14-1648-utc).

The historical v1 five-scene rehearsal passed with both engines, including model parsing, vision scoring, three-source evidence, browser imagery, same-pool five-truck refinement and unsent draft approval. On the same scenes, fixed median scouting fell from **22.825 to 9.651 seconds** and deep from **52.875 to 39.988 seconds**. Those v1 final deep runs took 39.490–45.017 seconds, each with ten cached visual scores and independently fetched traces. All 32 scouting attempts across baseline, cache fill and optimization stayed below 90 seconds with no engine fallback. Four earlier trace-diagnostic failures remain documented; final deep passed all five on its first attempt. See [the full measured comparison](docs/team/status-lane-c.md) and [human evaluation status](docs/team/eval.md).

The selected **20/5/5** configuration has now been rehearsed on the same five scenes with both engines. All ten warm searches succeeded with twenty cached visual scores each; median/max were **10.092/12.396 s fixed** and **44.160/49.109 s deep**. The first deep request includes lazy process initialization. All ten five-truck follow-ups reused their candidate pools and saved unsent drafts. Three optional trace links were unavailable (one fixed, two deep); these original attempts remain in the measurements, with follow-ups completed on the same threads. See the [previous rehearsal evidence](docs/team/eval.md#demo-refresh-after-v2) and [current stage report](docs/team/status-lane-c.md).

The newer **Job 8 stage rehearsal** passed **10/10** strict checks, including every trace readback, same-pool five-truck refinement and unsent draft. Warm medians were **8.923 s fixed / 40.923 s deep**; Warehouse handoff took **9.398 / 48.135 s**. All scouts reused **20/20** visual scores with no scoring failure or engine fallback. Fixed’s first request includes lazy initialization; deep was already warmed by **two** partial browser attempts. Cached dressing was offered on the top pick for **four of five** scenes on both engines; the LA office was not offered. These are backend/cache checks, distinct from the complete judge path. Source: [stage report](docs/team/status-lane-c.md), with per-scene timings in the [runbook](docs/demo-runbook.md#current-stage-rehearsal).

## Team agents: start here

Read [AGENTS.md](AGENTS.md), then [your owner handoff](docs/team/START-HERE.md). Python 3.13 is the pinned baseline. Install `requirements.lock.txt` for reproducible setup; run `python scripts/verify.py` before each PR. [Private access and remaining live blockers](docs/team/ACCESS.md) are tracked separately. CI checks mocks; passing CI does not establish sponsor access.

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

The fixture images are labeled synthetic placeholders. Mock runs are for setup and interface checks, not evidence of retrieval quality.

## Setup: private live data

Provision the current private `cache/join.parquet`, frozen `cache/shot-index/` generation, referenced interior frames and `cache/vexcel/` evidence separately. Do not replace the current multi-city join with the older LA-only team archive. A public checkout does not contain these licensed assets. Configure model credentials and model IDs in the ignored `.env`; the verified model is `gpt-6.1-sol`. Matterport/Vexcel keys are needed for acquisition and precomputation; optional LangSmith credentials enable traces.

Install the live retrieval dependencies with `.venv/bin/pip install -r requirements-index.lock.txt`; the smaller baseline lock alone does not include CLIP. Provision `sentence-transformers/clip-ViT-B-32` in the local Hugging Face model cache before rehearsal. Its first load may download weights; use `HF_HUB_OFFLINE=1` only after that cache is complete. The index and text encoder must use the same model. See [index setup](index/README.md).

```bash
TYPECAST_USE_MOCKS=0 TYPECAST_ENGINE=deep \
  TYPECAST_ENABLE_MODEL_PARSE=1 TYPECAST_ENABLE_VISION_RERANK=1 \
  TYPECAST_ALLOW_VISION_UPLOAD=1 \
  .venv/bin/python -m uvicorn agent.app:app --host 127.0.0.1 --port 8000
```

Use a permitted model-processing setup for private imagery. A scene without a city reports: **“No city named; searched Los Angeles. Name Houston to search there.”** Naming Houston selects Houston; no new cross-city filter is introduced. The stage checkout serves the viewer and Director's Room from port 8000; separate lane processes are not the presentation server. Keep caches private and serve them only on the local machine. The [runbook](docs/demo-runbook.md) covers the five validated scenes, exact stage command, checks and backup recording. Dressing is optional and precomputed: its presence depends on the selected scan point, and this setup does not generate assets.

## Layout

| Folder | Owner | What |
| --- | --- | --- |
| `contracts/` | all | Shared data shapes (Python and TypeScript) |
| `mocks/` | all | Fake data every lane builds against |
| `index/` | Owner 1 | Shot index: panorama views, embeddings, geometry, search, shot fit |
| `data/` | Owner 2 | CoStar filter, the join to scans, Vexcel parking and noise |
| `agent/` | Owner 3 | Agent, pipeline, HTTP API |
| `web/`, `bridge/` | Owner 4 | Viewer and messaging bridge |
| `docs/` | Integration captain and team | Handoffs, measured results, submission drafts and pitch |

## How to work

1. Read `docs/HANDOFF.md`, then your owner plan in it.
2. Work on your lane branch (`lane-a` … `lane-d`), in your folder only. Merge small and often into `dev`.
3. Tools return mock data while `TYPECAST_USE_MOCKS=1`. Swap in real code behind the same function signatures.
4. Update your lane's `docs/team/status-lane-*.md` before you stop. Record choices in `DECISIONS.md`.

## Rules

- Never commit keys or CoStar data. `.env` and `cache/` are git-ignored.
- Approval saves a local draft under ignored `cache/outbox/`; it never sends a message.

## Model configuration and access checks

Use the project `.env` for `LLM_API_KEY` and `VISION_API_KEY`, with provider model IDs in `TYPECAST_LLM_MODEL` and `TYPECAST_VISION_MODEL`. `TYPECAST_REASONING_EFFORT` controls director/text reasoning (default `medium`); `TYPECAST_SCOUT_REASONING_EFFORT` controls the four delegate model instances (default `low`). Both use the configured text model. `TYPECAST_ENGINE=fixed|deep` selects execution; responses report the engine that actually finished. Model parse and vision rerank can be disabled with `TYPECAST_ENABLE_MODEL_PARSE=0` and `TYPECAST_ENABLE_VISION_RERANK=0`. Vision upload additionally requires `TYPECAST_ALLOW_VISION_UPLOAD=1`.

The toolkit's visible Matterport API key goes in `MATTERPORT_API_KEY`; its hidden API token goes in `MATTERPORT_API_SECRET`. The SDK key is separate. Check credential presence without exposing values:

```bash
python scripts/check_access.py
python scripts/check_access.py --network  # read-only OpenAI/Matterport/Vexcel checks
```

The verification gate forcibly disables model calls and tracing, even when private keys exist in `.env`. A working key does not mean the real-data adapters or private join are ready. See [lane C status](docs/team/status-lane-c.md) for current evidence and blockers.

## Execution and evaluation

`GET /scout/stream` sends `event: agent` while tools execute, then `event: result`; failures end with `event: error`. `POST /scout` uses the same runtime. `/refine` preserves the thread and reranks saved candidates without new property or shot searches. A known geometric failure is rejected; unknown or estimated fits stay unverified. Blocking alternatives are explicitly labelled.

The deep engine uses actual Deep Agents director/scout/skeptic graphs over the same source tools and ranking logic. After market retrieval, interior and logistics scouts run concurrently; the shortlist combines their full source records from session state. Model-facing tool responses are compact summaries. A failed run or 90-second deadline triggers a visible fixed-engine fallback. Deep approval resumes a human-approval checkpoint; both engines save drafts locally and always report `sent=false`.

The director writes its initial plan once; subsequent progress comes from actual tool/scout events. The application completes the persisted plan only after validating the returned ids, skeptic reviews and staged approval checkpoints. Visual scoring uses the exact authored scene, including follow-ups, while retaining the full retrieval pool; a follow-up that only changes trucks or cars keeps the saved visual order. `TYPECAST_RERANK_POOL` accepts 10, 20, 30 or 40; `TYPECAST_VISION_CONCURRENCY` accepts 5 or 10; `TYPECAST_VISION_BATCH_SIZE` accepts 1, 5 or 10 images per call. The selected defaults are 20/5/5: twenty candidates, concurrency five and five images per request. On the five tune scenes, equal-engine precision lower bound was 37% versus 36% at baseline, with a maximum deep request of 55.494 seconds. This small sample does not establish general improvement. Batch responses must score every supplied image exactly once. Cache checks include provider/model, prompt, image identity and batch context; changing inferred parser wording alone does not cause a miss. Sources: [reranker](agent/rerank.py), [tune results](docs/team/eval.md#tune-experiments).

A provider rate limit stops further model calls in that worker process, including fixed fallback; it is recorded rather than retried. The tuning runner uses a fresh worker and private score cache for each attempt, plus a shared 1,000-image budget ledger. An operator must resolve the rate limit before deliberately restarting a stopped live process. See [tune methodology and results](docs/team/eval.md#tune-experiments).

Configure `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` (default `typecast`) for traces of fixed and deep runs. `LANGSMITH_TRACING=false` disables tracing. A response includes a trace URL only after the client retrieves the completed run and returns its URL; absent credentials or tracing failures leave `trace_url=null`.

`GET /config` gives the viewer exactly `mode`, `engine`, `tracing`, and `matterport_sdk_key`. Mode is `mock`, `live`, or `mixed` when adapters disagree; engine is the configured selection, while scout responses identify the engine that actually finished. The only exposed key is the browser SDK application key, or null when absent/unsafe. Matterport documents its [browser use and domain allowlist](https://developers.matterport.com/embed-sdk/). API credentials are never included.

Compare deep-engine latency with three real-provider runs over fixture data:

```bash
python scripts/benchmark_deep.py --runs 3 --director-effort medium --scout-effort low \
  --output cache/benchmarks/deep-after.json
```

This command uses the configured model API. It disables model parsing and vision reranking; add `--tracing` to include real trace upload and verified link retrieval. Without that flag, it measures director/delegate changes without trace-service latency. Reports count fallbacks separately from successful deep runs and require a verified link on every traced trial. The output contains timing metadata, not source records.

For the private five-scene demo set, run the API in live mode with model parsing and vision enabled, then use `python scripts/check_demo.py --engine fixed --phase baseline --verify-trace` (or `--engine deep` against a deep server). Each scene must return three available picks with known parking, real images, all three evidence sources and a source-grounded skeptic caveat. It also checks five-truck refinement without another search and unsent local drafts. Use `--phase precompute` to fill a changed cache, then `--phase warm` to measure it; every attempt is retained under ignored `cache/demo-checks/`.

`scripts/check_demo_browser.py` uses an optional separate Playwright environment to decode the actual interior and aerial images from saved scout and refinement responses in Chromium. It saves private screenshots and fails on missing images. This verifies API imagery; [viewer acceptance](docs/team/status-lane-d.md) and the combined judge-path gate in the [runbook](docs/demo-runbook.md) cover different interactions. Local evidence caches do not remove the live parser/director model or tracing service's network dependency.

With a mock server running on port 8000 and tracing enabled, verify actual SSE delivery, public configuration, and a fetched LangSmith run with:

```bash
python scripts/check_tracing.py --expected-engine fixed --output cache/benchmarks/fixed-trace.json
# Use --expected-engine deep when the server runs with TYPECAST_ENGINE=deep.
```

Tracing waits at most eight seconds for a run to become readable after upload. If verification fails or takes longer, scouting still succeeds with a null trace URL and a trace-status event. This diagnostic checks the returned link independently and rejects missing links or an unexpected fallback.

```bash
python scripts/e2e.py
python agent/eval/run_eval.py --mode mock --output cache/evaluation/mock-report.md
```

The authored benchmark has 15 test and 5 tuning scenes. Empty labels are skipped, so mock runs never become a retrieval accuracy claim. Keep real labels in ignored `cache/`. The 15 mock frame images are explicitly labelled placeholders, not photographs; regenerate them with `python scripts/make_mock_images.py`.

For a new live blinded study, freeze the exact index and candidate pools before human review. The current benchmark is already frozen and reviewed; do not repeat these steps to rehearse. Use the immutable generation path printed by `freeze` for the lab, export and evaluation:

```bash
python agent/eval/label_bridge.py freeze
# Set TYPECAST_INDEX_DIR to the printed generation path, then start the lab:
TYPECAST_USE_MOCKS=0 uvicorn index.preview:app --port 8765
# Review all 15 test scenes at http://localhost:8765/evaluate as Human review.
python agent/eval/label_bridge.py export --split test
TYPECAST_ENABLE_MODEL_PARSE=1 TYPECAST_ENABLE_VISION_RERANK=1 \
  TYPECAST_ALLOW_VISION_UPLOAD=1 python agent/eval/run_eval.py --mode live --split test \
  --scenes cache/evaluation/agent/scenes.jsonl --labels cache/evaluation/agent/labels.jsonl \
  --index-dir "$TYPECAST_INDEX_DIR" --output cache/evaluation/live-report.md
```

The exporter rejects stale, incomplete, AI or mock reviews. This evaluation measures pipeline recall@10 against human judgments of a frozen global top-40 pool, not exhaustive catalog recall. The pipeline's city filter can exclude relevant views from that global pool; the report includes a city-eligibility diagnostic. Empty judged pools are counted separately and excluded from recall. Never use held-out test judgments for tuning.

## Limits

Marketed lease availability does not establish vacancy or filming permission. Parking is an estimate, unmeasured shot depth stays unknown, and proximity flags are not sound measurements. Cached source evidence reduces provider dependence, but the live parser/director still need a model API connection. The runbook provides an explicitly labeled recording or mock fallback for Wi-Fi loss. AI dressing is an imagined proposal; real-room evidence remains separately accessible. The combined stage check, approved screenshot/video, team handles and track-specific evidence remain human/team completion items; no Peri, Photon, Amazon or ChatOverflow claim is made without human-confirmed evidence.

## Team

| Role | Team member | Discord |
| --- | --- | --- |
| Interiors and retrieval | [Owner 1 name] | [handle] |
| Property and aerial evidence | Udit | [handle] |
| Agent and integration | Zukhriddin | [handle] |
| Viewer and presentation | [Owner 4 name] | [handle] |

Fill the remaining names and handles before the human submits. The repository contains submission drafts; no submission is performed by these tools.
