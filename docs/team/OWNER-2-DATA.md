# Owner 2: trustworthy property and aerial evidence

## Start now
Clone https://github.com/Tecncentral/typecast.git, then fetch and check out your lane branch. Read contracts/schemas.py and your lane's source before changing it. The base scaffold inspected is 6928661; claims in STATUS.md are previous-agent reports, not freshly run tests.
```bash
git clone https://github.com/Tecncentral/typecast.git
cd typecast
git fetch origin
git switch lane-b
git merge origin/dev
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m pytest -q
python -m uvicorn agent.app:app --reload
```
Copy .env.example to .env locally if needed. The app loads the root .env; explicit shell environment takes precedence. To override in the launching shell (PowerShell: $env:TYPECAST_USE_MOCKS="1"). Never paste or commit credentials.
Work only in your lane directories; coordinate shared-contract changes with the integrator. Open small PRs targeting dev, not main. Fetch dev before each integration. Keep your own docs/team/status-lane-b.md with commit, commands/results, works/broken/next/blockers; avoid everyone editing STATUS.md.
Mocks unblock coding immediately. Never claim mocks are live data. Keep licensed records, joins, imagery and embeddings in ignored cache/; publish code and aggregate diagnostics only. Do not put data/join.parquet in public Git. Coordinate private delivery or a team-local service for integration.
No external messages or submissions are authorized by these documents. Owner inquiries remain drafts. Missing facts stay unknown; parking and dimensions inferred from imagery are estimates.

Own data/ and docs/team/status-lane-b.md.
## First 60 minutes
1. Read costar_tools.py, vexcel_tools.py, data/SCHEMA.md and contracts.
2. Inspect toolkit schemas privately. Write SCHEMA.md with filenames/schema only, no licensed rows or contact data.
3. Produce one verified CoStar property -> Matterport model join with method and confidence. Send model id to A privately immediately.
4. Fetch one real Vexcel aerial for that building through the documented toolkit. Save under cache/.
## Deliver in order
- Real implementations of search_costar/get_property/plan_logistics preserving signatures. First 3 common buildings, then 10-20.
- Store join under cache/join.parquet, not data/join.parquet. Address proximity is a candidate match; verify identity, report ambiguous joins, do not silently equate nearest buildings.
- Document private data provisioning for C and permitted cache lifecycle. Do not assume other laptops can read your filesystem.
- Expose aerial image, footprint/parking polygon, estimated capacity and access/noise caveats. Coordinate source timestamps/evidence metadata with C/D.
- Separate measured facts from imagery inference. An aerial cannot establish parking permission, truck clearance, current availability or sound level. Unknown is not zero and not confirmed.
- Handle unknown year, vacancy and dimensions explicitly; do not let unknowns pass hard requirements without a visible caveat.
## Acceptance and risks
A known property yields matching interior/aerial evidence; missing joins return a clear failure; filters do not invent availability; polygons use the contract's [lat,lon] order (convert for map libraries). Test null fields, missing imagery and bad join. Give C aggregate join coverage and privately usable demo records, never raw public commits.

## Paste into your coding assistant
You are Typecast Owner 2: trustworthy property and aerial evidence. Read docs/team/START-HERE.md and this entire handoff. Work on lane-b within the owned directories. First run the baseline and deliver the first-hour proof, then implement the listed milestones. Use existing contracts, fixture mode while dependencies arrive, and actual toolkit docs for provider calls. Record exact verification and blockers in your lane status file. Open small PRs into dev. Do not commit secrets/licensed data, send messages, or claim unverified integrations work.
