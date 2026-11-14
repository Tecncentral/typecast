# Typecast

Cast real buildings for your script. Text a scene and get back camera frames from inside real, vacant Los Angeles buildings that could play it, with a check that the shot fits the room, where the crew parks, and a drafted note to the owner.

Built at HackPrinceton Fall 2026 on CoStar property data, Matterport 3D scans and Vexcel aerial imagery.

## Status

Scaffold. The pipeline and API run end to end on **fake data** in `mocks/`. No real CoStar, Matterport or Vexcel calls are wired in yet. See `STATUS.md`.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest -q
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
- No message goes to a real property owner. Drafts go to the team inbox after an explicit yes.
- The repo must be public before the Devpost submission (8:00 am Sunday, Nov 15).
