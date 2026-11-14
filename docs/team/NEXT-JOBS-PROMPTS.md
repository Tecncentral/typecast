# Next jobs: real end-to-end integration and the viewer

Updated Saturday Nov 14, 10:40 am Eastern.

| Lane | Owner | State |
| --- | --- | --- |
| A: interiors | Owner 1 | Done and merged (PR #6): real Matterport views from 19 properties, keyed by CoStar property id |
| B: CoStar and Vexcel | Owner 2 (Udit) and your lane-B session | Merged into dev as PR #12 at 10:45 |
| C: agent and API | you | Done and merged (PRs #1–#8 and #11), deep engine at 37 s |
| D: viewer | Owner 4 | `web/` untouched. The messaging bridge was merged from PR #10 |

| Job | When to send | Checkout | Branch | Port |
| --- | --- | --- | --- | --- |
| 3 Viewer | **now**: it touches nothing else | `../typecast-d` | lane-d | 8001 |
| 1 Real end to end | **now**, once the lane-B session has stopped (PR #12 is merged; skip Job 1's step 1 if CI on dev is green) | `typecast/` | lane-c | 8000 |
| 4 Exterior mode | **only after** its gate: one real interior pick shows in the viewer (target 2 pm). Hard stop 7 pm | `../typecast-ext` | ext-mode | 8003 |

The running lane-B session uses `../typecast-b` and `../typecast-live` (port 8002). Leave both alone until it reports done.

## Before you start (human)

1. **Avoid two writers on `lane-b`.** Tell Owner 2 that your agent is also pushing to `lane-b` and already merged their commits. Agree that one of you finishes PR #12 (simplest: your session finishes its current task, then stops, and Udit owns `lane-b`). Whoever pushes next pulls first. No force-push.
2. Get lane A's index here, if the lane-B session hasn't already: Owner 1's `Typecast-Owner1-Team.zip`, extracted into the `typecast/` root.
3. Tell Owner 4 you're taking the web viewer, unless they reply within 15 minutes that they've started.
4. Write the sponsor engineer's name in `DECISIONS.md`.

---

## Job 1: demo-ready real data (integration captain)

```
You are Typecast's integration captain (Owner 3). All lanes have real code merged into dev: lane A (real Matterport views keyed by CoStar property id), lane B (PR #12: CoStar join, live search, cached Vexcel parking and aerial images) and lane C (agent and API). Your job: turn this into a demo-ready set of real buildings and scenes.

Work in the typecast/ checkout on lane-c, and merge origin/dev first. Port 8000. Don't touch ../typecast-d (viewer session) or ../typecast-ext (exterior session, if it exists). Remove ../typecast-b and ../typecast-live only if no session uses them and they hold no uncommitted work.

Read: AGENTS.md, docs/team/status-lane-a.md, docs/team/status-lane-b.md (or the Owner 2 section of STATUS.md), docs/team/status-lane-c.md, index/README.md, data/SCHEMA.md, data/VEXCEL.md, data/build_join.py, data/costar_tools.py and data/vexcel_tools.py.

Where things stand (Nov 14, 11:00 Eastern; verify before relying on it):
- dev passes 240 tests with green CI. A live fixed run took 30.6 s and a live deep run 67.4 s with no fallback; vision calls, LangSmith traces and the five-truck refine worked.
- Private data on this laptop:
  - cache/join.parquet, built by dev's data/build_join.py: 13,096 rows, one per property and scan, 3,288 properties in LA and Houston, with availability_status.
  - Lane A's index in cache/shot-index/CURRENT: 608 views from 19 LA properties.
  - Vexcel aerial images and logistics in cache/vexcel/.
- Keep this cache/join.parquet. Never replace it with the join.parquet from Owner 2's typecast-data.zip: that's an older LA-only format (1,581 rows) without availability_status, which dev's code needs. If lane A wants property_models.parquet, copy only that file from the zip.
- "Available" means availability_status is "available": 216 LA and 227 Houston properties. Owner 2's older file counts 269 in LA; 215 overlap, and the 54 extra are probably sale- or auction-only listings. Confirm that through availability_reason and record the definition in DECISIONS.md.
- Vexcel geofence: for us, calls only work inside LA (lon -119.0134 to -116.8949, lat 33.0945 to 34.3154) and Houston (lon -96.2185 to -94.5758, lat 29.0173 to 30.3804); elsewhere they return HTTP 403. Every row of the join is inside. A 403 must read "outside Vexcel coverage", never a crash or a zero.

Do these in order. Run each one and check its real output before moving on:
1. Coverage, the biggest product gap. Only 3 of the 19 indexed properties are available (14 unknown, 2 not available), and the 19 are 18 multifamily plus 1 office.
   - Extend lane A's index to available properties: every available Office, Industrial, Flex and GeneralRetail property in LA and Houston, plus about 20 available Multifamily properties with distinctive interiors. Keep the existing 19.
   - Use lane A's bootstrap with an explicit model list (index/README.md), at most 8 to 12 scan points per model, and keep the build under about an hour. Then run TYPECAST_USE_MOCKS=0 python -m data.vexcel_precompute for the new properties.
   - Afterwards, report counts by type, city and availability.
   - index/ belongs to Owner 1 and data/ to Owner 2: run their tools, and if code must change, keep it small and in PRs they can see.
2. Fill the evidence gaps.
   - Walking distance and noise are unknown everywhere because the OpenStreetMap (Overpass) call failed, and the freeway warning is a key demo moment. Retry with one other public Overpass instance listed on the OSM wiki, sequentially, with a polite User-Agent. Or get freeway and rail proximity from Vexcel elements/detect, the way lane B already finds parking.
   - Parking exists for only 9 of the original 19. Missing parking must read "unknown", never 0, in the API response and the viewer.
   - Shot depth is unmeasured, so every shot fit is "unknown". Ask through docs/team/status-lane-a.md whether lane A's room outlines can give depth along a heading; otherwise keep "unknown, measure on site".
   - Add an explicit lease, sale or auction field to Property only if it costs under 20 minutes (Owner 2 asked for it).
3. Demo set and scenes. Choose 8 to 10 properties that are indexed, available and have known parking (mostly LA, plus a few Houston ones for variety). Look at their frames, then write 5 scenes they can actually play; use the police station only if a matching room exists. Save the property ids and scene texts to the git-ignored cache/demo-set.json, and tell the human, so the list can go privately to Owners 1 and 2.
4. Real end to end on the demo set, with TYPECAST_USE_MOCKS=0, model parsing and vision rerank on, and both engines. For each scene, confirm:
   - real frames load in the browser;
   - every pick has CoStar, Matterport and Vexcel evidence with an honest measured, estimated or unknown status;
   - the skeptic objects to something real;
   - "need parking for 5 trucks" re-ranks without a new search;
   - approval saves a local draft.
   Record timings per engine.
5. Speed. Bring the deep engine's real-data run from 67 s toward 45 s, for example with 10 rerank candidates instead of 20 and a pre-filled rerank cache for the demo scenes. Record before and after, and stay under the 90 s cutoff on every run.
6. Precompute everything the demo touches (Vexcel logistics and aerial images, the rerank cache for the 5 scenes), so a live run is fast and survives venue Wi-Fi.
7. Evaluation. Ask the human to label the 15 test scenes in lane A's blinded labelling screen; you can't label them yourself. Then run agent/eval/run_eval.py --mode live, and record recall@10 and the sample count in README.md and docs/team/eval.md.

Commit small, open PRs into dev, and merge each one only after inspecting and verifying it, as integration captain. Update status-lane-c.md with commands and real output. Never commit cache/, keys, CoStar rows or contacts. Never message anyone outside the team. Feature freeze is midnight.
```

---

## Job 3: the viewer (lane D)

```
You are building the Typecast viewer, the screen the judges watch. Nothing exists in web/ yet.

TAKEOVER: Owner 4 hasn't started web/; you own web/ on lane-d. The messaging bridge in bridge/ is already merged; don't edit it.

TIME: it's about 2 pm Saturday. Have the run view showing three real result cards by 6 pm, then polish. Feature freeze is midnight. Real data is ready on this laptop: 10,568 indexed views, logistics cached for 343 properties, and five demo scenes that pass on both engines (fixed about 10 s, deep about 40 s).

Read: AGENTS.md, docs/team/START-HERE.md, docs/team/OWNER-4-VIEWER.md, contracts/schemas.ts, mocks/pick.json, mocks/events.jsonl and agent/app.py. Routes: GET /health, GET /config ({mode, engine, tracing, matterport_sdk_key}), POST /scout, GET /scout/stream, POST /refine and POST /approve. Static: /app serves web/; /mocks and /cache serve images. Also read index/README.md and index/studio.js: lane A's Matterport SDK connection and scan navigation were verified in Chrome. Copy what you need into web/; never edit index/.

Work in your own worktree, because another session works in the main checkout:
  git fetch origin && git worktree add ../typecast-d lane-d && git -C ../typecast-d merge origin/dev
Symlink the git-ignored .env, .venv and cache/ from typecast/ into it, and run the server there with uvicorn agent.app:app --port 8001. The Matterport SDK key's allowed domains include localhost but not 127.0.0.1, so open http://localhost:8001/app/. Edit web/ only.

Stack: plain HTML, CSS and JavaScript modules served by the existing FastAPI at /app, with no build step, so it runs offline at the venue. Vendor any library (Leaflet for the map) into web/vendor/; don't load from a CDN. Image paths in responses are relative (mocks/img/..., cache/...), so prefix "/".

Build in this order. Check each step in a real browser at 1440×900 and at a projector-like 1280×720:
1. Run view on fixtures. A scene box prefilled with "INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling, windows on one wall. Parking for 3 trucks and 30 crew cars." Above it, show the five validated demo scenes as one-click buttons: copy their scene texts, text only with no property ids, from the git-ignored cache/demo-set.json into web/scenes.js. Run opens GET /scout/stream with EventSource: "agent" events, then "result"; handle "error". The live plan panel shows the to-do list ticking, one lane per agent (director, market_scout, interior_scout, logistics_scout, skeptic) with start and result rows and tool timings, skeptic objections in a distinct colour, and "relaxed" notices. It must be readable from 2 m: large type, high contrast. Show MOCK or LIVE and the engine from /config and the response; never hide mock mode. If the response has a trace_url, show "View trace"; otherwise show nothing.
2. Three result cards: the large frame first (second frame on arrow), the one-line reason, a shot-fit badge (fits, tight or unknown, with needed vs available depth and the ceiling), evidence chips per source coloured by measured, estimated or unknown, a parking summary with the aerial image when present, noise flags, skeptic notes, and available or occupied.
3. A detail drawer per pick: every evidence line with its status, and "Open 3D tour". With a matterport_sdk_key from /config, embed the Matterport Showcase and move to the shot's sweep_id the way lane A's studio does. Heading alignment is unverified, so label it "opens at this scan point". Without a key, show a plain link to the model, labelled "opens at the model's start".
4. A follow-up box: POST /refine with {thread_id, message}. Show what changed (rank moves, new objections) while keeping the earlier frames visible. This is the demo's punchline: "need parking for 5 trucks".
5. Owner note: "Draft note" calls POST /approve only after an explicit click, then shows "Saved as a local draft, not sent". No "sent" or "delivered" wording anywhere.
6. States: loading, no match (show gave_up and relaxed honestly), missing image, API error, and a slow run (show elapsed seconds; on real data fixed runs take about 10 s and deep runs about 40 s).
7. Map: Leaflet with pins from property lat and lon, top three highlighted. If tiles can't load offline, fall back to the aerial images. The contract stores polygons as [lat, lon]; convert where the library expects another order.
8. Browser check: a Python Playwright script, web/tests/check_viewer.py, that runs against a live server on mocks, waits for three cards, a skeptic note and the refine change, and saves a screenshot to cache/screens/. Put the playwright version in the PR for the integration captain.
9. Real data, once the fixture version looks finished. Restart your server with TYPECAST_USE_MOCKS=0, but only if cache/join.parquet and lane A's index exist on this laptop. Check that real frames (/cache/views/...) and Vexcel aerial images (/cache/vexcel/...) render, that long real addresses and reasons don't break the layout, and that unknown or zero parking reads clearly. Never screenshot contact details into the repo.

Design: dark and cinematic, like a film slate. Frames dominate, one accent colour, no icon clutter. It must look finished on fixtures before any real data arrives. Commit small, push lane-d, and open a PR into dev describing the screenshots and the commands you ran. Update docs/team/status-lane-d.md. No fake agent activity, no invented results, no external messages.
```

---

## Job 4: exterior mode (time-boxed stretch)

Two parts, in priority order:

- **A, exterior frames for buildings already in the join.** Vexcel aerial views of the outside of the same LA or Houston buildings whose Matterport interiors we show, so one address covers both "EXT. POLICE STATION, DAY" and "INT. POLICE STATION, NIGHT". This uses all three data layers and matches the track name, "Inside and Out".
- **B, an outdoor showcase in Vexcel's new Northern California area.** Vineyards, farms and lakes, from Vexcel alone, with no CoStar or Matterport data.

The default stays off (`TYPECAST_ENABLE_EXTERIOR=0`), so nothing here can break the core demo.

What was checked on Nov 14 at 10:50: Vexcel semantic search (`embedding/extract`) works in Northern California. "vineyard rows" with a 2 km buffer around Napa (38.297, -122.287) returned 5 hits, scores 0.115 to 0.142, from collection us-ca-sanfrancisco_rf06-2026. The top two, viewed as top-down tiles about 60 m across, are real vineyards with a farm road and a house, dated September 2026. "wooden cabin by a lake shore" at Lake Tahoe (39.096, -120.032) returned hits scored about 0, from n39w119-us-nv-reno-2024, so effectively no match. The product type came back empty, so whether angled (oblique) views exist there is unknown.

```
You are adding an optional exterior mode to Typecast. It is a time-boxed stretch: the core interior flow and the viewer matter more.

GATE. Check before writing code: (a) docs/team/status-lane-c.md or the human confirms one real interior pick works end to end with TYPECAST_USE_MOCKS=0, and (b) the viewer (lane D) shows picks in a browser. If either isn't true, stop and report. HARD STOP at 7:00 pm Eastern: whatever isn't solid stays behind TYPECAST_ENABLE_EXTERIOR=0 (the default) and gets listed in your status file. Feature freeze for everyone is midnight.

Read first: AGENTS.md, docs/team/START-HERE.md, contracts/schemas.py, docs/team/CONTRACT-CHANGES.md, data/VEXCEL.md, data/vexcel_client.py, data/vexcel_tools.py, data/vexcel_precompute.py, agent/pipeline.py, agent/parse.py, agent/rerank.py, agent/runtime.py, index/README.md, and the section "Job 4: exterior mode" in docs/team/NEXT-JOBS-PROMPTS.md (what was already checked). Read the official Vexcel docs before any call: https://api.vexcelgroup.com/v2/api-docs/embedding, .../ortho, .../property and .../custom-elements, and find in the docs whether angled (oblique or "oriented") imagery has its own endpoint and which product types each region has. The docs outrank anything here.

Checkout: git fetch origin && git worktree add -b ext-mode ../typecast-ext origin/dev. Symlink .env, .venv and cache/ from typecast/ into it. Port 8003. Other sessions work in typecast/ (lane-c), ../typecast-d (viewer) and possibly ../typecast-b and ../typecast-live; don't touch them.

Ownership: you own exterior/ (a new package), exterior tests, mocks/sites.json (new), docs/team/status-exterior.md (new), and the additive contract fields below. In agent/ you may add one small, flag-guarded hook (about 40 lines at most, in a new agent/exterior_hook.py plus a few call lines in the pipeline). Before touching agent/, fetch and merge origin/dev and check that no other open PR edits the same lines. Don't edit data/, index/ or web/: import lane B's client and functions, don't modify them. If you need another Vexcel endpoint that data/vexcel_client.py doesn't allow, write a small client in exterior/ with the same safety rules: fixed documented endpoints only, no redirects, sanitized errors, the key never printed or logged.

Vexcel geofence (sponsor, Nov 14): calls only work inside four boxes; anything else returns HTTP 403 "Unauthorized by Geofencing permission". LA: lon -119.0134 to -116.8949, lat 33.0945 to 34.3154. Houston: lon -96.2185 to -94.5758, lat 29.0173 to 30.3804. Northern California: lon -124.7437 to -118.9869, lat 38.0655 to 41.9596. A fourth box covers the Florida panhandle; don't use it (its draw is hurricane damage, which doesn't fit Typecast). Check point-in-box before every call, and treat a 403 as "outside Vexcel coverage", never as a crash or a zero.

Steps:
1. Probe, at most 30 minutes; record results in docs/team/status-exterior.md.
   - For two LA buildings from cache/join.parquet: footprint via property/extract, a top-down ortho crop, and angled views if the docs offer them.
   - For Napa, confirm the product types available there.
   - No probe outside the boxes.
2. Contract, additive only. Record it in CONTRACT-CHANGES.md first, then update contracts/schemas.py, contracts/schemas.ts and mocks together.
   - ExteriorShot: shot_id; source="vexcel"; lat; lon; view: "top" | "north" | "south" | "east" | "west" | "unknown"; image_path; capture_date; collection; score; reason; property_id (optional).
   - Pick.exterior_shots: list[ExteriorShot] = [].
   - OutdoorSite: site_id; area_label; lat; lon; shots: list[ExteriorShot]; logistics (optional Logistics); evidence: list[Evidence]; caveats: list[str].
   - ScoutResponse.sites: list[OutdoorSite] = [].
   - Add mocks/sites.json and exterior shots on one pick in mocks/pick.json, so the viewer can build against them.
3. Part A, LA and Houston exteriors (the priority).
   - For every property in lane A's index (cache/shot-index/CURRENT), precompute exterior frames into cache/exterior/<property_id>/: one top-down crop about 120 to 200 m across centred on the footprint, plus angled views if the docs provide them. Prefer the side facing the street or entrance; if you can't tell which, keep all and say so.
   - Match exterior scenes by ranking each building's exterior frames against the scene text, using agent/rerank.py's public function (call it, don't edit it) with TYPECAST_ALLOW_VISION_UPLOAD respected. Semantic search around each building (small buffer) can be a second signal.
   - Attach the best one or two as Pick.exterior_shots whenever the scene has an EXT heading or describes the outside.
4. Part B, Northern California outdoor showcase.
   - About five anchor points inside the box: Napa, Sonoma, Sacramento, South Lake Tahoe, and the Mendocino coast or Redding.
   - Rewrite the scene into two or three queries describing what's visible from above, using the existing model adapter. For example, "EXT. VINEYARD, DUSK" becomes "vineyard rows" and "farmhouse with gravel driveway". Words like "cabin" or "cozy" don't show from the air.
   - Run embedding/extract around each anchor with a 2 to 3 km buffer. Set a score threshold by looking at results; the Tahoe example scored about 0, which means no match.
   - Fetch a crop of about 150 m per hit (angled views if available) into cache/exterior/sites/.
   - Logistics: parking lot, dirt lot or open field via elements/detect; access roads; noise from freeways, rail and airports via OpenStreetMap the way lane B does. Mark everything estimated.
   - Return up to three OutdoorSites with caveats: "Aerial view, captured <date>; not a ground-level shot" and "Owner and permission unknown: no CoStar data in this region".
   - Optional, only if A and B are solid before 6 pm: a sunset check from Vexcel's elevation data, showing which slopes face west.
5. Agent hook (fixed engine first). Detect INT., EXT. and INT./EXT. headings. With TYPECAST_ENABLE_EXTERIOR=1:
   - built settings attach Pick.exterior_shots (part A);
   - natural or rural settings, or a scene naming Northern California, return ScoutResponse.sites (part B).
   Emit real events under agent "exterior_scout", with timings. The deep engine gets an exterior_scout subagent only if there's time after the fixed engine works, and the deep run must stay under 60 s.
6. Precompute everything the demo touches, so a live run never waits on Vexcel.
7. Tests (no network): fake HTTP for the clients, the geofence check (inside, outside, 403 handling), contract defaults (old clients unaffected), and heading detection.
8. Viewer handoff: when the contract PR merges, tell the human to paste the "Viewer note for Job 4" (in docs/team/NEXT-JOBS-PROMPTS.md) into the viewer session. Don't edit web/ yourself.
9. Demo assets: one LA or Houston building with a matched exterior and interior, one Northern California vineyard site, the timings for both, and the exact scene texts that produce them.

Honesty: aerial frames are always labelled as aerial (Vexcel, capture date) and never presented as eye-level camera shots. No ownership, availability or permission claims without CoStar data. Never test outside the geofence.

Commit small, push ext-mode, and open a PR into dev with commands, real output, mode, and what's behind the flag. Update docs/team/status-exterior.md after each step. Never commit cache/, keys, imagery, CoStar rows or contacts. Never message anyone outside the team.
```

### Viewer note for Job 4

Paste this into the viewer session once Job 4's contract change is merged into dev:

```
Contract update from the exterior job (additive, on dev): Pick.exterior_shots holds aerial exterior frames of the same building, and ScoutResponse.sites holds outdoor locations that have no CoStar or Matterport data. Merge origin/dev first. On each result card, show exterior frames as a strip labelled "Aerial · Vexcel · <capture date>" next to the interior frames, under the heading "Outside". Render each site as its own card: a large aerial frame, the area label, parking and noise with "estimated" status, and its caveats shown plainly ("Owner and permission unknown: no CoStar data in this region"). Build against mocks/pick.json and mocks/sites.json first. Hide both when empty. Never call aerial frames camera shots.
```

---

## Job 5: rerank experiment, then submission assets (integration captain)

Send this to the free integration session, which works in `typecast/` on lane-c, port 8000. The viewer session keeps running separately.

```
You are Typecast's integration captain (Owner 3), on lane-c in typecast/, port 8000. The viewer session works in ../typecast-d; don't touch it. It's about 2:30 pm Saturday. Feature freeze is midnight; Devpost closes at 8:00 am, and we aim for 7:30.

PART 1, a rerank-depth experiment. The human accepts slower searches; find out how slow better results get. Stop at 4:30 pm whatever the state.
The frozen v1 evaluation (docs/team/eval.md, PR #20) stays exactly as published. It found two weaknesses: (a) vision rerank only reorders the first 10 candidates, so it can never bring a better view into the top 10; (b) scenes that name no city search Los Angeles only.
1. Make the rerank pool size configurable with TYPECAST_RERANK_POOL (default stays 10 until step 4): rerank the top N candidates and return the best 10.
2. Make it faster in two ways, each behind a setting so it can be compared:
   - concurrency: 5 parallel vision calls (today) vs 10. Stop at the first rate-limit error and record it.
   - batched scoring: send 5 or 10 candidate images in ONE vision call and ask for a JSON score and a one-line reason per image, validated so each image gets exactly one score. Keep per-image scoring as the baseline.
3. Using ONLY the 5 tune scenes, never the 15 test scenes, measure every combination worth running from N = 10, 20, 30 and 40 (the judged pool is 40, so 40 is the useful maximum) × the two speed-ups. For each, record recall@10, precision@10 (a lower bound, with unjudged views counted as misses), and uncached latency for both engines, plus the number of vision calls (they cost API credits; keep the total under about 1,000 image scorings). Put the table in docs/team/eval.md under a new heading, "Tune experiments".
4. Pick the setting with the best tune quality whose deep run stays under 75 s; the runtime falls back to fixed at 90 s, so that's the hard limit. Within that, slower is acceptable. If no setting beats N = 10, keep 10 and write down why.
5. Only if you changed the default: run the 15 test scenes exactly once more and publish the result as "v2 (after changes informed by v1)", next to v1, never replacing it. Re-warm the caches for the five demo scenes afterwards, so the stage demo stays fast.
6. City: add no new filter logic. When a scene names no city, emit an event and add a note to the response: "No city named; searched Los Angeles. Name Houston to search there." Confirm that a scene naming Houston searches Houston.
7. Add precision@10 for v1 from the existing frozen run, without rerunning anything: 99 of the 150 returned views were judged relevant, a lower bound. Put it in eval.md with its caveats: one reviewer, pooled labels, unjudged views counted as misses.

PART 2, submission assets. Start by 4:30 pm.
1. README.md: what Typecast does in two sentences; a screenshot placeholder; how it works (the agent steps and what each data layer decides); setup for mocks and for private live data; the evaluation summary (precision lower bound first, then recall@10 with its ceilings); limits; team.
2. docs/devpost.md, with the sections: inspiration, what it does, how we built it, challenges, accomplishments, what we learned, and what's next (rerank depth, city choice, exterior mode, more cities). Write to both rubrics:
   - CoStar: name each data layer and what it decides, plus the agent's plan, scouts, skeptic, and who uses it on Monday.
   - The main track: creativity, utility, charity (free scouting for student crews, and income for empty buildings) and avidity.
   List the main track (Entertainment and Media) and these special tracks: CoStar, LangChain, Amazon and ChatOverflow; add Peri and Photon only if the human confirms the eligibility evidence. Leave a placeholder for team Discord names. Claim nothing that isn't verified in the repo.
3. docs/pitch.md: a 2-minute script timed beat by beat, using the five validated demo scenes, the five-truck follow-up, a skeptic objection and the measured numbers. Also write a 30-second version for CoStar judges that opens on "what can this space play".
4. docs/architecture.md: a Mermaid diagram of the pipeline and the three data layers.
5. docs/demo-runbook.md: start commands, ports, which scenes to click, what to do if the Wi-Fi fails (cached runs), and how to record the backup video.

Commit small, open PRs into dev, run python scripts/verify.py, and merge after inspection. Don't submit anything. Don't message anyone outside the team. Never commit cache/, keys or licensed data.
```

---

## Job 6: inside-out descent (viewer session, lane D)

Send this to the viewer session that owns `web/` (in `../typecast-d`). It builds on the 360° viewfinder in PR #25.

```
You own web/ on lane-d. Goal: one authored cinematic moment, the "inside-out descent", that tells CoStar's track title ("Inside and Out") in about three seconds. Use Impeccable (animate and overdrive playbooks; read craft-floor.md before editing). The human wants bold, not safe.

First: review PR #25 (branch viewfinder, the 360° director's viewfinder plus GET /api/sweep/{shot_id}). Merge it into lane-d if scripts/verify.py and your browser checks pass. Don't edit web/viewfinder.js or web/viewfinder.css; if you need a hook, add it in your own files.

The descent plays once when a run's result arrives, for the top pick:
1. Establishing: the map flies to the top pick's pin (Leaflet flyTo, about 900 ms), with the other two pins dimmed.
2. Aerial: dissolve into that pick's Vexcel aerial (logistics.aerial_image_path), centred on the building, while the parking outline draws itself. Draw it as an SVG stroke-dashoffset animation from logistics.parking_polygon, converted to image pixels with the aerial's saved extent (cache/vexcel/<property_id>/aerial-extent.json, served if needed by a tiny allow-listed read in the API, or precomputed into the response). If the conversion isn't reliable, wipe in the existing aerial-logistics.png with a clip-path instead. Never draw an invented outline.
3. Through the roof: push in on the building, with scale and a bounded blur, then cross-dissolve into the pick's real interior frame (shots[0].image_path). The interior starts slightly zoomed and settles.
4. Land: a View Transition morphs that interior frame into the first result card's frame, so the descent ends exactly where the shortlist begins.

Rules:
- Total about 3 s, and skippable by click, Esc or any key. A "Replay descent" button appears on the first card.
- Label each layer honestly as it appears: "Vexcel aerial", "Matterport scan", "parking estimated".
- prefers-reduced-motion: plain cross-fades of about 200 ms, no flight, no zoom.
- No new dependency, except one already vendored. 60 fps on a laptop. Pause anything offscreen.
- It must work on the five demo scenes in live mode (TYPECAST_USE_MOCKS=0) and degrade gracefully on mocks, which have no aerial.
- Add a Playwright check that the descent runs, can be skipped, and lands on card 1. Run scripts/verify.py.

Then a short polish pass on the existing viewer that Impeccable's detector flagged: run-section padding and line-height in the main CSS. Commit small, push lane-d, update PR #23 or open a new PR into dev, describing what you verified. Feature freeze is midnight.
```

---

## Job 7: World Labs dressed set (new session)

Send this to a new agent session. Before you send it (human): put your World Labs API key in `.env` under the name the World Labs docs use for the header value (store it as `WORLDLABS_API_KEY`). You approved spending about $1.50 per world. The cap for this job is **$15**.

```
You are adding an AI "dressed set" to Typecast, a bold stretch feature. Next to each real scanned room, show a walkable World Labs world of how that room could look dressed for the script. It must always be labelled as AI-imagined, never as the real room.

Setup: git fetch origin && git worktree add -b dressed-set ../typecast-ws origin/dev, then merge origin/viewfinder (PR #25). Symlink .env, .venv and cache/ from typecast/. Port 8006. Your files: a new package worlds/, agent/tests/test_worlds.py, web/dressed.js, web/dressed.css, web/vendor/spark/ (vendored SparkJS), docs/team/status-worlds.md, and one additive allow-listed API route. Don't edit other web files; mount through your own module the way web/viewfinder.js decorates cards.

Read first: AGENTS.md; the World Labs API docs at https://docs.worldlabs.ai/api (quickstart, FAQ and pricing), including request shapes for text, single-image and multi-image (images with azimuths) world generation, operation polling and asset URLs; and SparkJS at https://sparkjs.dev/. Check the exact endpoint names, auth header and model ids in the docs; don't guess. Known from Nov 13 research, to verify: Marble models (marble-1.1 and others), about 5 minutes per world, about $1.20 to $2.50 per standard world, drafts about $0.20, outputs SPZ splats at 100k, 500k and full resolution plus a collider mesh, no edit endpoint.

Budget: at most $15 in total. Use draft quality for every experiment, and standard only for the final five demo worlds. Log every generation with cost in docs/team/status-worlds.md. Stop and ask the human before going over.

Steps:
1. One draft world from one demo scene's top pick. Try multi-image input built from the four real horizon faces at that scan point (GET /api/sweep/{shot_id} returns them; headings 0/90/180/270 are scan-relative and map to azimuths) plus a text prompt for the script's dressing, if the docs allow text with images. If they don't, restyle one real face with the team's OpenAI image model (exact model id from the account's model list) and generate from that single image plus the scene text. Record which input works best and how long it took.
2. Viewer: in web/dressed.js, add a "Dressed set (AI)" button beside "Look around" on cards whose shot has a precomputed world. Open a full-screen SparkJS viewer (vendored, no CDN) with the world. Show a clear, persistent "AI-imagined set dressing, not the real room" badge, a one-click switch back to the real 360° viewfinder at the same scan point, and the capture date of the real scan.
3. API: GET /api/dressed/{shot_id} returns precomputed world assets for that scan point, or 404. Allow-list the shot id, and only serve files under cache/worlds/.
4. Precompute standard-quality worlds for the top pick of each of the five demo scenes (cache/demo-set.json), so the live demo never waits on generation, which takes minutes.
5. Tests with fake HTTP for the client, polling and timeouts, plus the endpoint's allow-list. A browser check that the dressed viewer opens and shows the AI badge. Run scripts/verify.py.

Honesty: never present a generated world as the real room. Never claim a dressing is achievable without an art department. Keep generated assets in cache/ (git-ignored). Stop at 10 pm whatever the state, and leave whatever works behind a flag (TYPECAST_ENABLE_DRESSED=1). Commit small, open a PR into dev with the costs spent and what you verified.
```

## Job 8: demo hardening, Director grouping and the submission story (Codex, parallel subagents)

Send this to the idle Codex agent. Another Claude session owns everything World Labs (walkable sets, re-dressing, splats); this job must not touch it.

```
You are finishing Typecast for HackPrinceton judging. Submission is 08:00 ET Sunday; feature freeze is midnight ET. Run five workstreams in parallel with subagents, each in its own git worktree off origin/dev (symlink .env, .venv and cache/ from typecast/), each with the files listed and nothing else. Read AGENTS.md, docs/team/START-HERE.md and docs/demo-runbook.md first.

Off limits (another session owns World Labs): worlds/, web/viewfinder*.js|css, web/dressed*, cache/worlds/, the dressed-set branch, any Atlas/World Labs call or credit. Don't edit index/ except the Director files in stream 1. Never print keys, commit cache/ or licensed data, force push, merge to main, or merge PRs into dev yourself: open PRs, the human merges. Live model spend: at most two full warm rehearsals of the five demo scenes.

STREAM 1. Director's Room demo script that shows grouping (branch director-restyle, already pushed; files: index/director.js, index/director.html, index/director.css, index/tests/*director*).
The Director's Room plans a whole script across the fewest buildings (fewer company moves = less crew downtime). Today's demo script lands three scenes in three buildings, so the grouping never shows. Find a 3–4 scene script whose best plan covers every scene from ONE building (0 company moves), ideally with a second plan that uses more buildings at higher similarity so the trade-off is visible.
- Method: run the dev app with live data and POST /api/production/plan (see index/production.py for the request shape) with candidate scripts built around building types the index really has (an apartment: kitchen, living room, hallway or bedroom; an office: lobby, glass meeting room, corridor; an industrial unit: open floor, office, loading area). Try LA and Houston.
- Open /image/<shot_id> for every assigned frame and check by eye that each room really plays its scene. Don't accept a match that only fits on paper.
- Replace the DEMO constant in index/director.js with the winner. Make the plan selector and stage header read clearly ("3/3 scenes · 1 location · 0 moves").
- Also fix the latent bug in build(): when a rejected property is filtered out, the code calls (p.locations || []).filter, but locations is a count; the property list is p.property_ids. Keep locations a number.
- Run node --test on index/tests/director-audit.mjs, director-project.test.cjs and director_reel.test.js, plus scripts/verify.py. Check it in a browser at 1440x900. Open a PR director-restyle -> dev with before/after notes.

STREAM 2. Stage server on dev and a warm rehearsal (files: docs/team/status-lane-c.md only).
The stage API on port 8000 still runs from the lane-c checkout and lacks the merged viewer, viewfinder, AI dressing and Director's Room. Commit and push any pending lane-c work first. Then create worktree typecast-stage at origin/dev and run it on port 8000 with the exact runbook command (deep engine, model parse, vision rerank 20/5/5, tracing).
- Run scripts/check_demo.py warm for all five scenes (fixed and deep) and the five-truck follow-up. Record timings, engines, fallbacks and trace links.
- For each scene's top pick, call GET /api/dressed/<shot_id> (read only) and list which top picks have an AI-dressed set. Report the list; don't generate anything.
- Keep this server running for the other streams and the human.

STREAM 3. Judge-path check and a backup recording (files: scripts/check_judge_path.py, its test if any, docs/demo-runbook.md section "Backup recording" only).
- Write scripts/check_judge_path.py using the team's Playwright env (cache/browser-venv). Against the stage server it runs the exact judge path:
  1. /app/: Warehouse handoff, wait for cards.
  2. The inside-out descent plays (and Skip works).
  3. Look around 360°, then press D for AI dressing if offered, then G to grab a frame and Esc.
  4. Refine with "Need parking for 5 trucks." and confirm the thread is kept.
  5. /director: Build plan with stream 1's script, then Play.
- Fail on console errors, missing images or a missing honesty label. Treat dressing and walk mode as optional: log "not offered" and continue.
- Save screenshots privately under cache/demo-checks/judge-path/<UTC timestamp>/.
- Add --record: the same path at human pace, 1440x900 Playwright video to cache/demo-video/<UTC timestamp>.webm. This is the runbook's "recorded live run" fallback for Wi-Fi or model failure. Keep it private: it contains licensed imagery, and only a human may approve publishing it.
- Run it once now, and once more after 01:00 ET when the PRs are merged.

STREAM 4. The submission story (files: README.md, docs/devpost.md, docs/pitch.md, docs/architecture.md, docs/demo-runbook.md except stream 3's section).
The docs don't mention the four features judges will actually see: the inside-out descent, the 360° viewfinder, AI set dressing (World Labs Atlas, depth-guided, always labelled "AI-imagined set dressing, not the real room") and the Director's Room.
- Rewrite docs/pitch.md's two-minute beat sheet around one reveal:
  - 0:00 hook;
  - talk over the live agent run;
  - top card, then descent, then Look around (rack 24 to 50 mm), then D wipes in the dressed set;
  - five trucks;
  - one line on the Director's Room grouping;
  - close on the defended numbers.
- Fix the stale 39.929 s (the measured warm deep warehouse time is 38.286 s; re-take timings from stream 2).
- Devpost, CoStar track: say plainly which Matterport team wishlist items we address. That's "consistent refurnishing" of real scanned rooms, with geometry kept from real depth. Only mention "interior splats from sparse scans" if the World Labs session's walkable set is merged; leave a clearly marked TODO slot for its numbers.
- Add a short "what is real vs AI-generated" section.
- Keep every existing honesty caveat, the eval wording (v2 is a post-change repeat, not a holdout) and the track-claims policy: no Peri, Photon, Amazon or ChatOverflow claims without human evidence. World Labs is a tool we used, not a track.
- Every number cites its source file. Draft by 23:00 ET; final pass after merges at about 01:00 ET.

STREAM 5. Main-app polish and a pre-public audit (files: web/index.html, web/styles.css for the masthead only, a new docs/team/PUBLIC-RELEASE-AUDIT.md).
- web/index.html has an inline style="color:#c6f432" Director's Room link. Replace it with a masthead nav matching the Director page ("Location scouting | Director's Room", current page underlined in --accent), using existing tokens. Check 1440, 1280 and 390 widths.
- Pre-public audit, read only: the repo is made public at the end, so scan the full history of every branch that will be merged. Look for credentials (key patterns, .env files), licensed data (parquet, csv, xlsx, jsonl, anything under cache/ or data/ outputs), real CoStar property IDs and street addresses (cross-check against cache/demo-set.json without printing them), owner contact details, and images.
- Write findings with commit, path and risk to PUBLIC-RELEASE-AUDIT.md (redact values). Don't rewrite history or change visibility: the human decides.

Report when done, per stream: branch and PR, what you verified with real output, what's left, and anything the human must decide. Commit small and push your own branches; never another stream's files.
```
