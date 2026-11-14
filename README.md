# Typecast

Cast real buildings for your script. Text a scene and get back camera frames from inside real, vacant Los Angeles buildings that could play it, with a check that the shot fits the room, where the crew parks, and a drafted note to the owner.

Built at HackPrinceton Fall 2026 on CoStar property data, Matterport 3D scans and Vexcel aerial imagery.

## Status

The API runs end to end on **fake data** in `mocks/`, with real streaming, evidence and uncertainty, cached refinement, and local draft approval. Model parsing and vision reranking use configured providers when enabled. Real property/interior/aerial adapters and the private join still belong to lanes A/B; a working API key alone does not make those adapters live. See [verified lane C status](docs/team/status-lane-c.md).

## Team agents: start here

Read [AGENTS.md](AGENTS.md), then [your owner handoff](docs/team/START-HERE.md). Python 3.13 is the pinned baseline. Install `requirements.lock.txt` for reproducible setup; run `python scripts/verify.py` before each PR. [Private access and remaining live blockers](docs/team/ACCESS.md) are tracked separately. CI checks mocks; passing CI does not establish sponsor access.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
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

Use the project `.env` for `LLM_API_KEY` and `VISION_API_KEY`, with provider model IDs in `TYPECAST_LLM_MODEL` and `TYPECAST_VISION_MODEL`. `TYPECAST_REASONING_EFFORT=high` selects the requested reasoning effort. `TYPECAST_ENGINE=fixed|deep` selects execution; responses report the engine that actually finished. Model parse and vision rerank can be disabled with `TYPECAST_ENABLE_MODEL_PARSE=0` and `TYPECAST_ENABLE_VISION_RERANK=0`. Vision upload additionally requires `TYPECAST_ALLOW_VISION_UPLOAD=1`.

The toolkit's visible Matterport API key goes in `MATTERPORT_API_KEY`; its hidden API token goes in `MATTERPORT_API_SECRET`. The SDK key is separate. Check credential presence without exposing values:

```bash
python scripts/check_access.py
python scripts/check_access.py --network  # read-only OpenAI/Matterport/Vexcel checks
```

The verification gate forcibly disables model calls and tracing, even when private keys exist in `.env`. A working key does not mean the real-data adapters or private join are ready. See [lane C status](docs/team/status-lane-c.md) for current evidence and blockers.
