# Typecast

Cast real buildings for your script. Text a scene and get back camera frames from inside real, vacant Los Angeles buildings that could play it, with a check that the shot fits the room, where the crew parks, and a drafted note to the owner.

Built at HackPrinceton Fall 2026 on CoStar property data, Matterport 3D scans and Vexcel aerial imagery.

## Status

The API runs end to end on **fake data** in `mocks/`, with real streaming, evidence and uncertainty, cached refinement, and local draft approval. Model parsing and vision reranking use configured providers when enabled. Real property/interior/aerial adapters and the private join still belong to lanes A/B; a working API key alone does not make those adapters live. See [verified lane C status](docs/team/status-lane-c.md).

## Team agents: start here

Read [AGENTS.md](AGENTS.md), then [your owner handoff](docs/team/START-HERE.md). Python 3.13 is the pinned baseline. Install `requirements.lock.txt` for reproducible setup; run `python scripts/verify.py` before each PR. [Private access and remaining live blockers](docs/team/ACCESS.md) are tracked separately. CI checks mocks; passing CI does not establish sponsor access.

## Run it

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock.txt
test -f .env || cp .env.example .env
python scripts/verify.py
uvicorn agent.app:app --reload
```

```bash
curl -s localhost:8000/scout -H 'content-type: application/json' \
  -d '{"scene":"INT. 1980s POLICE STATION, NIGHT. Parking for 3 trucks and 30 crew cars."}'
```

## Layout

| Folder | Owner | What |
| --- | --- | --- |
| `contracts/` | all | Shared data shapes (Python and TypeScript) |
| `mocks/` | all | Fake data every lane builds against |
| `index/` | Owner 1 | Shot index: panorama views, embeddings, geometry, search, shot fit |
| `data/` | Owner 2 | CoStar filter, the join to scans, Vexcel parking and noise |
| `agent/` | Owner 3 | Agent, pipeline, HTTP API |
| `web/`, `bridge/` | Owner 4 | Viewer and messaging bridge |
| `docs/` | Owner 4 | `HANDOFF.md` (read this first), Devpost draft, pitch |

## How to work

1. Read `docs/HANDOFF.md`, then your owner plan in it.
2. Work on your lane branch (`lane-a` … `lane-d`), in your folder only. Merge small and often into `dev`.
3. Tools return mock data while `TYPECAST_USE_MOCKS=1`. Swap in real code behind the same function signatures.
4. Update your section of `STATUS.md` before you stop. Record choices in `DECISIONS.md`.

## Rules

- Never commit keys or CoStar data. `.env` and `cache/` are git-ignored.
- Approval saves a local draft under ignored `cache/outbox/`; it never sends a message.
- The repo must be public before the Devpost submission (8:00 am Sunday, Nov 15).

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

Configure `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` (default `typecast`) for traces of fixed and deep runs. `LANGSMITH_TRACING=false` disables tracing. A response includes a trace URL only after the client retrieves the completed run and returns its URL; absent credentials or tracing failures leave `trace_url=null`.

`GET /config` gives the viewer exactly `mode`, `engine`, `tracing`, and `matterport_sdk_key`. Mode is `mock`, `live`, or `mixed` when adapters disagree; engine is the configured selection, while scout responses identify the engine that actually finished. The only exposed key is the browser SDK application key, or null when absent/unsafe. Matterport documents its [browser use and domain allowlist](https://developers.matterport.com/embed-sdk/). API credentials are never included.

Compare deep-engine latency with three real-provider runs over fixture data:

```bash
python scripts/benchmark_deep.py --runs 3 --director-effort medium --scout-effort low \
  --output cache/benchmarks/deep-after.json
```

This command uses the configured model API. It disables model parsing and vision reranking; add `--tracing` to include real trace upload and verified link retrieval. Without that flag, it measures director/delegate changes without trace-service latency. Reports count fallbacks separately from successful deep runs and require a verified link on every traced trial. The output contains timing metadata, not source records.

With a mock server running on port 8000 and tracing enabled, verify actual SSE delivery, public configuration, and a fetched LangSmith run with:

```bash
python scripts/check_tracing.py --expected-engine fixed --output cache/benchmarks/fixed-trace.json
# Use --expected-engine deep when the server runs with TYPECAST_ENGINE=deep.
```

Tracing waits at most eight seconds for a run to become readable after upload. If verification fails or takes longer, scouting still succeeds with a null trace URL and a trace-status event. This diagnostic checks the returned link independently and rejects missing links or an unexpected fallback.

```bash
python scripts/e2e.py
python agent/eval/run_eval.py --mode mock
# After real data and hand labels exist:
python agent/eval/run_eval.py --mode live --labels cache/eval/labels.jsonl --split test
```

The authored benchmark has 15 test and 5 tuning scenes. Empty labels are skipped, so mock runs never become a retrieval accuracy claim. Keep real labels in ignored `cache/`. The 15 mock frame images are explicitly labelled placeholders, not photographs; regenerate them with `python scripts/make_mock_images.py`.
