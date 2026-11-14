# Owner 1: real frames and shot retrieval

## Start now
Clone https://github.com/Tecncentral/typecast.git, then fetch and check out your lane branch. Read contracts/schemas.py and your lane's source before changing it. The base scaffold inspected is 6928661; claims in STATUS.md are previous-agent reports, not freshly run tests.
```bash
git clone https://github.com/Tecncentral/typecast.git
cd typecast
git fetch origin
git switch lane-a
git merge origin/dev
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn agent.app:app --reload
```
Copy .env.example to .env locally if needed. The current app does NOT load dotenv automatically: export environment variables in the launching shell (PowerShell: $env:TYPECAST_USE_MOCKS="1"). Never paste or commit credentials.
Work only in your lane directories; coordinate shared-contract changes with the integrator. Open small PRs targeting dev, not main. Fetch dev before each integration. Keep your own docs/team/status-lane-a.md with commit, commands/results, works/broken/next/blockers; avoid everyone editing STATUS.md.
Mocks unblock coding immediately. Never claim mocks are live data. Keep licensed records, joins, imagery and embeddings in ignored cache/; publish code and aggregate diagnostics only. Do not put data/join.parquet in public Git. Coordinate private delivery or a team-local service for integration.
No external messages or submissions are authorized by these documents. Owner inquiries remain drafts. Missing facts stay unknown; parking and dimensions inferred from imagery are estimates.

Own index/ and docs/team/status-lane-a.md.
## First 60 minutes
1. Read index/search.py, geometry.py, cut_views.py and contracts/schemas.py. Run existing index tests.
2. Obtain sponsor toolkit docs and one permitted Matterport model id privately. Prove access to a real panorama or permitted screenshot and its sweep/camera identity. Save only in cache/.
3. Send Owner 2 model id and Owner 3 one Shot-shaped record privately. Owner 2 can work on joins in parallel; you do not wait to prove image access.
## Deliver in order
- Build a reproducible image manifest: source model, sweep, heading, image path, retrieval time, room identity. Make browser URLs usable with Owner 4.
- Verify panorama format before projection. Reuse cut_views only if appropriate. Visually inspect straight walls and camera heading.
- Index 3 shared buildings first, then 10-20 useful ones; deduplicate nearby views. Use a consistent text/image embedding space, normalize, and rank actual query similarity. Preserve search_shots/get_shot/check_shot signatures.
- Preserve unknown geometry. Estimated depth or sqrt(area) must set measure_on_site and cannot become a verified physical-fit claim. Coordinate a tri-state fit if required.
- Provide tour pose/deep-link metadata based on actual SDK support; never promise camera alignment from a model id alone.
- After integration: 20 hand-labelled scenes, documented relevant shots, recall@10 and sample count. Label before tuning; separate tuning examples. LookAlike is optional.
## Acceptance and risks
Real query changes ordering; property filters work; no same-building example results; actual images render; unknown dimensions do not crash. API denial needs a precise error and sponsor escalation in H1, not hours of blind scraping. Add dependencies to a lane-specific file and tell C to consolidate.

## Paste into your coding assistant
You are Typecast Owner 1: real frames and shot retrieval. Read docs/team/START-HERE.md and this entire handoff. Work on lane-a within the owned directories. First run the baseline and deliver the first-hour proof, then implement the listed milestones. Use existing contracts, fixture mode while dependencies arrive, and actual toolkit docs for provider calls. Record exact verification and blockers in your lane status file. Open small PRs into dev. Do not commit secrets/licensed data, send messages, or claim unverified integrations work.
