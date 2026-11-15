# Owner 3: agent, API and integration captain

## Start now
Clone https://github.com/Tecncentral/typecast.git, then fetch and check out your lane branch. Read contracts/schemas.py and your lane's source before changing it. The base scaffold inspected is 6928661; claims in STATUS.md are previous-agent reports, not freshly run tests.
```bash
git clone https://github.com/Tecncentral/typecast.git
cd typecast
git fetch origin
git switch lane-c
git merge origin/dev
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m pytest -q
python -m uvicorn agent.app:app --reload
```
Copy .env.example to .env locally if needed. The app loads the root .env; explicit shell environment takes precedence. To override in the launching shell (PowerShell: $env:TYPECAST_USE_MOCKS="1"). Never paste or commit credentials.
Work only in your lane directories; coordinate shared-contract changes with the integrator. Open small PRs targeting dev, not main. Fetch dev before each integration. Keep your own docs/team/status-lane-c.md with commit, commands/results, works/broken/next/blockers; avoid everyone editing STATUS.md.
Mocks unblock coding immediately. Never claim mocks are live data. Keep licensed records, joins, imagery and embeddings in ignored cache/; publish code and aggregate diagnostics only. Do not put data/join.parquet in public Git. Coordinate private delivery or a team-local service for integration.
No external messages or submissions are authorized by these documents. Owner inquiries remain drafts. Missing facts stay unknown; parking and dimensions inferred from imagery are estimates.

Own agent/, integration dependency changes by agreement, and docs/team/status-lane-c.md.
## First 60 minutes
1. Read pipeline.py, app.py and contracts; run baseline tests and record actual output.
2. Reproduce POST /scout, POST /refine and GET /scout/stream on fixtures. Tell D the current event names: SSE event: agent with Event JSON, then event: result with ScoutResponse.
3. Fix null formatting in _build before real records land. Do not format None with :g or imply unknown geometry fits.
4. Arrange private data provisioning with B and image paths with A/D. Merge small reviewed lane PRs into dev; main stays under team control.
## Deliver in order
- Make stream events arrive during tool execution. Current implementation runs everything then replays at TYPECAST_EVENT_DELAY; remove fake-live behavior. Use one shared execution path for regular and streamed requests.
- Build actual deepagents planner/scout/skeptic execution using verified package docs. Keep deterministic fallback and identify which engine ran. Do not label fixed-order Python events as independent AI agents.
- Tool evidence and errors survive into UI. Coordinate additive contract changes with all owners, including provenance, unknown vs estimated vs measured, trace URL and runtime source mode.
- Integrate one real pick by H3, then 3 if data permits by H8. No silent fixture fallback in live mode.
- Refine cached candidates: allow explicit zero trucks/cars, preserve original constraints, report insufficient parking rather than only a small penalty. Verify no new shot search.
- Isolate thread state; validate missing/expired thread and invalid pick approval. Owner notes remain drafts; UI may approve a local draft but must not claim delivery.
- LangSmith trace from actual execution if credentials are provisioned; useful error if absent. Add latency and tool timings.
## Acceptance and risks
One browser-to-API-to-real-data flow with A/B/D. Tests for null geometry, all candidates failing constraints, unknown thread, tool timeout, zero parking update and cache reuse; event timing confirms early progress before completion. Retain safe error states. Coordinate dependencies centrally and avoid global mocks/real modes giving a misleading health response.

## Paste into your coding assistant
You are Typecast Owner 3: agent, API and integration captain. Read docs/team/START-HERE.md and this entire handoff. Work on lane-c within the owned directories. First run the baseline and deliver the first-hour proof, then implement the listed milestones. Use existing contracts, fixture mode while dependencies arrive, and actual toolkit docs for provider calls. Record exact verification and blockers in your lane status file. Open small PRs into dev. Do not commit secrets/licensed data, send messages, or claim unverified integrations work.
