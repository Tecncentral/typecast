# Next jobs: real data, a faster deep engine, the viewer

Written Saturday Nov 14, about 5:30 am Eastern. Lane C is finished on mocks; the demo still has no real data and no screen. These three jobs edit different folders (job 1: `index/` and `data/`, job 2: `agent/`, job 3: `web/`), so they can run at the same time in three separate agent sessions.

Each job gets its own checkout and port, so they never touch each other's files or servers:

| Job | Checkout | Branch | Server port |
| --- | --- | --- | --- |
| 1 Real data | `../typecast-a`, `../typecast-b`, plus `../typecast-live` for end-to-end runs | lane-a, lane-b | 8002 |
| 2 Deep engine | this checkout (`typecast/`) | lane-c | 8000 |
| 3 Viewer | `../typecast-d` | lane-d | 8001 |

## Before you start (human, 15 minutes)

1. Ask Owners 1, 2 and 4 for their status. Then edit the `TAKEOVER:` line in jobs 1 and 3 to match what they say. If someone doesn't answer within 30 minutes, take their lane.
2. Download the CoStar zip from Discord and unzip it into `cache/costar/`. Save any sponsor toolkit docs (Matterport, Vexcel, CoStar quick starts, the bot's Python script) into `cache/toolkit/`. Both folders are git-ignored.
3. Get a LangSmith key (free tier), then set `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT=typecast` in `.env`.
4. Write the sponsor engineer's name in `DECISIONS.md`.

---

## Job 1: one real pick end to end (lanes A and B)

```
You are taking the real-data path for Typecast. Lane C (agent and API) is finished on mocks; the demo still has zero real data. Your job: get ONE real pick end to end through the existing API, then three, then 10 to 20 buildings.

TAKEOVER: <edit before pasting, e.g. "Owners 1 and 2 are inactive; you own lane-a (index/) and lane-b (data/)." or "Owner 1 is active on lane-a; coordinate through docs/team/status-lane-a.md and own lane-b only.">

Read first: AGENTS.md, docs/team/START-HERE.md, docs/team/OWNER-1-INTERIORS.md, docs/team/OWNER-2-DATA.md, docs/team/ACCESS.md, docs/team/status-lane-c.md, contracts/schemas.py, index/search.py, index/cut_views.py, index/geometry.py, data/costar_tools.py, data/vexcel_tools.py, data/SCHEMA.md and scripts/check_access.py. If cache/toolkit/ or cache/costar/ exist, read their listings and docs before calling any API. The sponsor toolkit docs outrank anything here.

Work in two git worktrees, so each lane's PR stays in its own folder:
  git fetch origin
  git worktree add ../typecast-a lane-a && git -C ../typecast-a merge origin/dev
  git worktree add ../typecast-b lane-b && git -C ../typecast-b merge origin/dev
Symlink or copy the git-ignored .env and cache/ into each worktree, and reuse the existing .venv. All imagery, records, joins and embeddings stay under cache/. Never print keys, licensed rows or contacts.

Already verified on this laptop with scripts/check_access.py --network: OpenAI; Matterport GraphQL at https://api.matterport.com/api/models/graph with basic auth MATTERPORT_API_KEY:MATTERPORT_API_SECRET, which returns models; and Vexcel WMTS with the api_key query parameter. Everything beyond that is unverified: introspect the Matterport schema and read the Vexcel docs instead of guessing field or endpoint names.

Steps. Run each one and check its real output before moving on:
1. Matterport access proof (lane-a). Introspect the schema to find how a model exposes scan locations (id, position, floor, room), panorama imagery (one equirectangular image or six cube faces), room dimensions and ceiling heights, and address or GPS. Pick ONE Los Angeles model. Download its scan list and 2 to 3 panoramas at about 2k width into cache/matterport/<model_id>/. Record in docs/team/status-lane-a.md the image form, the exact fields used and timings. If panoramas aren't available from the API, try the fallback in OWNER-1-INTERIORS.md, then stop and report (settled decision 8 in docs/HANDOFF.md).
2. Views and Shot rows (lane-a). Convert cube faces to equirectangular (py360convert) if needed. Cut 8 level views per scan with index/cut_views.py into cache/shots/<model_id>/. Open several and check that walls are straight and headings are right. Fill Shot rows with geometry from the API: room area, ceiling, and depth along the heading by ray-casting to the room outline where one exists; otherwise sqrt(area) with measure_on_site=True. image_path must be a relative path the API serves under /cache.
3. Embeddings and real search (lane-a). Encode every view with one open image-text model (open_clip with a SigLIP or CLIP checkpoint), on Apple MPS if available. Store normalized vectors in cache/index/embeddings.npy beside cache/index/shots.parquet. Implement the live branches of _all_shots, search_shots and get_shot in index/search.py: embed the query as "a photo of the interior of " + text, rank by cosine similarity, apply the existing filters, and for LookAlike use the example shot's vector while excluding its own building. Keep the mock path and every signature unchanged. Check that two different queries give different orderings.
4. CoStar (lane-b). If cache/costar/ exists, load every file into DuckDB and write data/SCHEMA.md: file names, row counts, key columns, no rows, no contacts. Find what links a property to a Matterport model: an id column, else a normalized address, else coordinates within about 30 m. Report ambiguous matches rather than picking the nearest. Write cache/join.parquet (never in git) and implement the live branches of search_costar and get_property. If the download is missing, write exactly what is missing in docs/team/status-lane-b.md and continue with steps 5 and 6, using the model's own address and coordinates.
5. Vexcel (lane-b). For the step-1 building, save a top-down image around its coordinates into cache/vexcel/<property_id>/. Then implement plan_logistics:
   - parking area near the footprint, from the documented Vexcel search or attributes (cite the endpoint you used);
   - spaces = area / 30 m², with one truck counting as 4 car spaces;
   - walking distance to the entrance;
   - noise flags for freeways, rail and airports within 200 m, 300 m and 3 km, from Vexcel attributes or OpenStreetMap.
   Mark everything inferred from imagery as estimated, and draw the parking outline on the aerial image for the viewer.
6. One real pick (both lanes). Don't use the main typecast/ checkout; another session works there on lane-c. Make a throwaway worktree: git worktree add --detach ../typecast-live origin/dev, then merge lane-a and lane-b into it locally (never push from it). Symlink .env and cache/, then run TYPECAST_USE_MOCKS=0 TYPECAST_ENGINE=fixed uvicorn agent.app:app --port 8002 and POST /scout with a scene that suits the building you pulled. Confirm that a real frame loads in the browser at its /cache URL, that evidence entries are marked measured, estimated or unknown correctly, and that the skeptic objects to something real. Record timings and a sanitized summary (no licensed text) in both status files.
7. Scale to three buildings, then 10 to 20, choosing types that suit demo scenes: offices, warehouses, lobbies, apartments. Keep at most about 12 scan points per model and skip scan points within 2 m of one already kept. Precompute logistics and aerial images for every demo building.

New packages (likely open_clip_torch, torch, py360convert, duckdb, pyarrow): install them in .venv and list exact versions in the PR. The integration captain adds them to requirements.txt and requirements.lock.txt before merging.
Commit small, push lane-a and lane-b, and open PRs into dev with commands, real output and mode. Update docs/team/status-lane-a.md and status-lane-b.md after every step. Never commit cache/, .env or CoStar data. Never message anyone outside the team. Never fabricate a join, an image, a measurement or a result.
```

---

## Job 2: a faster deep engine, LangSmith and /config (lane C)

```
You are working on Typecast lane C (agent/), which is finished on mocks. Two jobs: make the deepagents engine fast enough for a live demo, and turn on real LangSmith tracing. Read AGENTS.md, docs/team/status-lane-c.md, agent/deep.py, agent/deep_tools.py, agent/prompts/deep_*.md, agent/runtime.py, agent/app.py and agent/tests/test_deep.py first. Work in the main typecast/ checkout on lane-c, and merge origin/dev into it first. Other sessions work in ../typecast-a, ../typecast-b, ../typecast-live and ../typecast-d; don't touch those. Run your server on port 8000.

Baseline: a real deep run over mocks took 87.8 s against the 90 s cutoff. Delegates run one after another (market done at 15.6 s, interior 40.3 s, logistics 57.8 s, skeptic 82.8 s), and every delegate uses the director's model at TYPECAST_REASONING_EFFORT=high. With real data and image reranking, it will hit the cutoff and fall back to the fixed engine, which ruins the LangChain demo.

1. Measure first: run deep 3 times on mocks with the police-station scene. Record p50 total and per-delegate times in status-lane-c.md.
2. Run interior and logistics in parallel. Logistics only needs property ids, so give it the market scout's candidate ids instead of the interior result's. Change the director prompt so that after the market result it launches task(interior_scout) and task(logistics_scout) in the SAME model turn. Confirm in the installed deepagents and LangGraph source that tool calls from one turn run concurrently, and prove it with timestamps: both start before either finishes. build_shortlist then combines the interior shots with the logistics results for the same properties.
3. Cheaper delegates: the scouts and the skeptic get their own model instance with TYPECAST_SCOUT_REASONING_EFFORT (default "low"); the director uses TYPECAST_REASONING_EFFORT (default "medium"). Verify the per-subagent "model" key in the installed package source. Add both settings to .env.example.
4. Fewer tokens: tools return compact summaries to the model (ids, key numbers and flags, about 1 to 2 KB per call at most). Full records stay in session state and files. Remove any extra planning round trip.
5. Target p50 under 45 s on mocks over 3 runs, with real progress events streaming throughout. Record before and after. If you can't get under 60 s, say so plainly and keep fixed as the default.
6. LangSmith: when LANGSMITH_API_KEY is set, trace deep and fixed runs to LANGSMITH_PROJECT (default "typecast"). After a run, read the real run URL from the LangSmith client, return it as trace_url, and verify it by fetching the run back through the client. Without a key, trace_url stays null. Add LANGSMITH_PROJECT to .env.example. Never construct a URL by hand.
7. Viewer support: add GET /config returning only {"mode", "engine", "tracing": bool, "matterport_sdk_key"}. First confirm in Matterport's docs that the Showcase SDK key is a browser key restricted by allowed domains; if it isn't, return null for it. Never return any other credential.
8. Tests (no network): a fake model plus sleeping tools proves interior and logistics overlap; per-subagent effort is applied; trace_url is null without a key; /config contains no other credential (assert against every *_KEY and *_SECRET value in the environment).

python scripts/verify.py must pass. Commit small, push lane-c, and open a PR into dev with before and after timings and the commands you ran. Update status-lane-c.md. No fabricated timings or trace links.
```

---

## Job 3: the viewer (lane D)

```
You are building the Typecast viewer, the screen the judges watch. Nothing exists in web/ yet.

TAKEOVER: <edit before pasting, e.g. "Owner 4 is inactive; you own lane-d (web/)." or "Owner 4 is active; build only what they hand you and coordinate through docs/team/status-lane-d.md.">

Read: AGENTS.md, docs/team/START-HERE.md, docs/team/OWNER-4-VIEWER.md, contracts/schemas.ts, mocks/pick.json, mocks/events.jsonl and agent/app.py. Routes: GET /health, GET /config (being added by lane C; handle its absence), POST /scout, GET /scout/stream, POST /refine and POST /approve. Static: /app serves web/; /mocks and /cache serve images. Work in your own worktree, because another session works in the main checkout:
  git fetch origin && git worktree add ../typecast-d lane-d && git -C ../typecast-d merge origin/dev
Symlink the git-ignored .env and the existing .venv from typecast/ into it, and run the server there with uvicorn agent.app:app --port 8001. Edit web/ only.

Stack: plain HTML, CSS and JavaScript modules served by the existing FastAPI at /app, with no build step, so it runs offline at the venue. Vendor any library (Leaflet for the map) into web/vendor/; don't load from a CDN. Image paths in responses are relative (mocks/img/..., cache/...), so prefix "/".

Build in this order. Check each step in a real browser at http://localhost:8001/app/ at 1440×900 and at a projector-like 1280×720:
1. Run view on fixtures. A scene box prefilled with "INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling, windows on one wall. Parking for 3 trucks and 30 crew cars." Run opens GET /scout/stream with EventSource: "agent" events, then "result"; handle "error". The live plan panel shows the to-do list ticking, one lane per agent (director, market_scout, interior_scout, logistics_scout, skeptic) with start and result rows and tool timings, skeptic objections in a distinct colour, and "relaxed" notices. It must be readable from 2 m: large type, high contrast. Show a MOCK or LIVE badge and the engine from the response; never hide mock mode.
2. Three result cards: the large frame first (second frame on arrow), the one-line reason, a shot-fit badge (fits, tight or unknown, with needed vs available depth and the ceiling), evidence chips per source coloured by measured, estimated or unknown, a parking summary with the aerial image when present, noise flags, skeptic notes, and available or occupied.
3. A detail drawer per pick: every evidence line with its status, and "Open 3D tour". If GET /config returns a matterport_sdk_key, embed the Matterport Showcase with the SDK and move to the shot's sweep_id and heading (confirm the function names in the Showcase SDK reference). Otherwise show a plain link to the model, labelled "opens at the model's start, not this frame". Never claim an alignment you haven't verified.
4. A follow-up box: POST /refine with {thread_id, message}. Show what changed (rank moves, new objections) while keeping the earlier frames visible. This is the demo's punchline: "need parking for 5 trucks".
5. Owner note: "Draft note" calls POST /approve only after an explicit click, then shows "Saved as a local draft, not sent". No "sent" or "delivered" wording anywhere.
6. States: loading, no match (show gave_up and relaxed honestly), missing image, API error, and a slow run (show elapsed seconds).
7. Map: Leaflet with pins from property lat and lon, top three highlighted. If tiles can't load offline, fall back to the aerial images. The contract stores polygons as [lat, lon]; convert where the library expects another order.
8. Browser check: a Python Playwright script, web/tests/check_viewer.py, that runs against a live server on mocks, waits for three cards, a skeptic note and the refine change, and saves a screenshot to cache/screens/. Put the playwright version in the PR for the integration captain.

Design: dark and cinematic, like a film slate. Frames dominate, one accent colour, no icon clutter. It must look finished on fixtures before any real data arrives. Commit small, push lane-d, and open a PR into dev describing the screenshots and the commands you ran. Update docs/team/status-lane-d.md. No fake agent activity, no invented results, no external messages.
```
