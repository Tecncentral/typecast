# Owner 4: cinematic viewer and two-minute demo

## Start now
Clone https://github.com/Tecncentral/typecast.git, then fetch and check out your lane branch. Read contracts/schemas.py and your lane's source before changing it. The base scaffold inspected is 6928661; claims in STATUS.md are previous-agent reports, not freshly run tests.
```bash
git clone https://github.com/Tecncentral/typecast.git
cd typecast
git fetch origin
git switch lane-d
git merge origin/dev
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn agent.app:app --reload
```
Copy .env.example to .env locally if needed. The current app does NOT load dotenv automatically: export environment variables in the launching shell (PowerShell: $env:TYPECAST_USE_MOCKS="1"). Never paste or commit credentials.
Work only in your lane directories; coordinate shared-contract changes with the integrator. Open small PRs targeting dev, not main. Fetch dev before each integration. Keep your own docs/team/status-lane-d.md with commit, commands/results, works/broken/next/blockers; avoid everyone editing STATUS.md.
Mocks unblock coding immediately. Never claim mocks are live data. Keep licensed records, joins, imagery and embeddings in ignored cache/; publish code and aggregate diagnostics only. Do not put data/join.parquet in public Git. Coordinate private delivery or a team-local service for integration.
No external messages or submissions are authorized by these documents. Owner inquiries remain drafts. Missing facts stay unknown; parking and dimensions inferred from imagery are estimates.

Own web/, bridge/, pitch/docs assets and docs/team/status-lane-d.md. Do not edit other owner handoffs.
## First 60 minutes
1. Read contracts/schemas.ts, mocks/pick.json and mocks/events.jsonl plus app.py routes. web/ has no implemented viewer in the inspected commit.
2. Build a browser flow against fixtures immediately: script input, plan/progress, three frame cards, detail evidence, logistics and follow-up input.
3. Coordinate image paths and tour pose with A and real event timing with C. Use mock mode clearly labelled while waiting.
## Deliver in order
- Strong visual hierarchy: large real interior frame, shortlist, visible physical-fit measurement/unknown state, aerial parking evidence, skeptic objection and source badges.
- Use the existing /scout response, /refine body {thread_id,message}, GET /scout/stream SSE agent/result events. Maintain thread id. An unknown trace must not be a fake link.
- Add usable loading, empty, missing-image, no-match and API-error states. Don't replace failures with invented results.
- Matterport tour opens at verified pose where SDK permits; otherwise label a general tour link accurately. Browser must render image paths served by API.
- Show the punchline: more trucks changes feasibility and ranking, while the original frames remain available. Clear reasons for changes.
- Owner inquiry preview with explicit approval UI; no sent confirmation because delivery is unimplemented. No external sending.
- Capture 2-minute demo and Devpost draft with actual implemented features, measured numbers, team Discord names and eligibility evidence. Check event packet checklist in START-HERE.
- Optional Photon bridge only after stable web demo; verify current sponsor guidelines and credentials. No owner messaging. Cut voice/World Labs/owner dashboard first.
## Acceptance and risks
Usable on a teammate's browser; fixture run and real run both correctly labelled; no local filesystem paths as browser image URLs; follow-up works end to end; no fake agent activity. Rehearse live and save a clearly labelled recorded backup. Reserve last 90 minutes for uploads/submission. Ask team lead to conduct Peri interview; do not fabricate evidence or send outreach yourself.

## Paste into your coding assistant
You are Typecast Owner 4: cinematic viewer and two-minute demo. Read docs/team/START-HERE.md and this entire handoff. Work on lane-d within the owned directories. First run the baseline and deliver the first-hour proof, then implement the listed milestones. Use existing contracts, fixture mode while dependencies arrive, and actual toolkit docs for provider calls. Record exact verification and blockers in your lane status file. Open small PRs into dev. Do not commit secrets/licensed data, send messages, or claim unverified integrations work.
