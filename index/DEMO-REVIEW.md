# Harsh demo review at dbceec2

Reviewed 2026-11-14 22:24 UTC. Read-only. Public code, fixtures, and mock HTTP only. No private cache, licensed rows, provider calls, keys, or browser. This is not a prize prediction and not an organizer eligibility ruling.

Another owner has a source-grounded demo draft under review on PR #31 (`index/GEMINI-DEMO-HANDOFF.md`, commit `b068836`, after `6823f6d`). This file does not replace that draft. The script below records what this checkout actually returned.

## Baseline

| Check | Result |
| --- | --- |
| `git rev-parse HEAD` | `dbceec2f392af037d4123177e8da35e8a3b877a8` |
| Subject | Merge pull request #30 from Tecncentral/dressed-set |
| `origin/dev` at review time | same SHA. Not rebased. No production edits. |
| Python used | 3.12.3. README pins 3.13. The lockfile installed and the gate passed on 3.12.3. |
| Mode | `TYPECAST_USE_MOCKS=1`, `TYPECAST_ENGINE=fixed` unless a command says otherwise. Model keys blank. `LANGSMITH_TRACING=false`. |

Older “539 passed, one skipped” figures are stale for this SHA. This run is **597 passed, zero skipped** in pytest.

## Commands and observed outputs

Interpreter: `/tmp/typecast-venv` built with `python3 -m venv` after `python3.12-venv`, then `pip install -r requirements.lock.txt` (exit 0).

### `python scripts/verify.py`

Exit 0. Pytest line: `597 passed in 12.80s`. Then:

- `PASS: mock search -> validated picks -> same-thread refinement -> SSE result -> no-send approval`
- E2E: first SSE event 4.24 ms, SSE result 13.62 ms, refine 6.65 ms, approve 1.78 ms. Search calls before/after refine stayed `search_shots: 1`, `search_costar: 1`.
- `PASS: progress arrived while search was blocked; refine reused the thread and cached candidates; yes approval saved a draft with sent=false`
- Mock eval: 20 attempted, 20 succeeded, 0 labeled scenes scored, 20 unlabeled skipped, `recall@10: N/A`, p50 4.39 ms, p95 6.31 ms, engine fixed, source mode mock.

### `TYPECAST_USE_MOCKS=1 python -m pytest -q`

Exit 0. `597 passed in 12.60s`. No skip line. Node suites run inside this gate (`index/tests/test_director_reel.py`) because `node` is installed.

### Node

`node --test` on `index/tests/director_reel.test.js`, `index/tests/director-project.test.cjs`, `index/tests/director-audit.mjs`, `web/tests/viewfinder.test.cjs`, `web/tests/lib.test.mjs`, `bridge/core.test.mjs`.

`# tests 90` / `# pass 89` / `# fail 0` / `# skipped 1`. The skip is `real browser surfaces this harness cannot drive` (no display, microphone, or browser HTML parser).

### Mock server

```text
TYPECAST_USE_MOCKS=1 TYPECAST_ENGINE=fixed TYPECAST_ENABLE_MODEL_PARSE=0 \
  TYPECAST_ENABLE_VISION_RERANK=0 TYPECAST_ALLOW_VISION_UPLOAD=0 \
  LANGSMITH_TRACING=false uvicorn agent.app:app --host 127.0.0.1 --port 8000
```

`GET /health` 200: `mocks: true`, source modes all `mock`, `engines_available: ['fixed']`, `langsmith_configured: false`.

`GET /config` 200: `{"mode":"mock","engine":"fixed","tracing":false,"matterport_sdk_key":null}`.

`GET /` 307 `location: /app/`. `HEAD /` 405 (GET works).

Static 200: `/director`, `/director.js`, `/director.css`, `/director-reel.js`, `/director-project.js`, `/app/`, `/app/app.js`, `/app/viewfinder.js`, `/app/viewfinder-compat.js`, `/app/utils.js`, `/app/scenes.js`.

`GET /studio.js` 404. `GET /evaluate` 404. Those routes live on the separate preview app, not on `agent.app`.

Served `director.js` status strings (unconditional):

- line 614: `Demo script loaded. Press Build plan to fetch real results.`
- line 721: `Nothing appears on the stage until the backend returns real results.`

### Director plan (the demo script)

`POST /api/production/plan` with the three `DEMO` lines from `index/director.js` (kitchen, living room, office corridor), `max_locations: 3`, `trucks: 0`, `cars: 0`, `require_available: false`.

200. `mode: mock`. One plan. `company_moves: 0`, `locations: 1`, `mean_similarity: 0.9`, `optimal_within_pool: true`, pool `['mock-p1','mock-p2','mock-p3']`.

Assignments, all three scenes:

`s1/s2/s3 → mock-p1 / mock-p1-s0 / score 0.9`

Top three shot ids are the same list on every scene: `mock-p1-s0`, `mock-p1-s1`, `mock-p1-s2`. Reason on the top hit: `MOCK fixture ranking (no semantic model)`. Property `availability_status: null`, `available: true`. Logistics `parking_status: null`, `truck_spaces: 4`, `enough_parking: null`. Warnings: costar availability `unknown`, vexcel parking_capacity `unknown`.

`GET /image/mock-p1-s0` 200 `image/jpeg` 32662 bytes. The stage has a placeholder image. It does not have three rooms.

Same body with `trucks: 5`, `cars: 10`: still `s1/s2/s3 → mock-p1`. Across candidates, parking warnings were `insufficient: 0`, `unknown: 27`.

One-scene body with `require_available: true`: `eligible 0`, uncovered `['s1']`, 9 candidates. The checkbox empties the plan. Fixtures set `available: true` and omit `availability_status` (`mocks/property.json`).

API reject (not the browser): forbidding `mock-p1` returned 200 and assignments on `mock-p2` only. `still_present: false`. That successful API replan is not the client bug PR #31 fixes (see below).

### Look around, dressing, planner link

`GET /api/sweep/mock-p1-s0` 422 `{"detail":"This view has no verified horizon cube geometry"}`.

`GET /api/dressed/mock-p1-s0` 404 `{"detail":"No dressed set for this scan point"}`.

`GET /api/plan/mock-p1-s0?heading=0&focal=35` 200 JSON, `status=unknown`, `note=Missing validated room boundary or scan position. Measure on site.`, `position=null`, `ring=null`. Content-Type `application/json`. The Director link points here (`index/director.html` line 89, `index/director.js` line 395).

### Brainstorm

`POST /api/production/brainstorm` with “Try her entering from the window side, slower.” and one actor.

503 `{"detail":"Configured model provider unavailable"}`. Keys were blank on purpose. Fail-closed. Not treated as a missing-sponsor-API prize failure.

### Scout, refine, approve, SSE

`POST /scout` warehouse scene (Los Angeles, 2 trucks, 10 crew cars). 200. `engine: fixed`, `source_mode: mock`, `trace_url: null`, 3 picks, `notes: []`.

| Rank | Property | `available` | `availability_status` | `shot_fit` | Trucks | Reason prefix | First skeptic note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | mock-p3 | true | null | `fits` / true | 6 | Blocked alternative | Availability is unknown; confirm listing status before booking. |
| 2 | mock-p4 | false | null | `fits` / true | 3 | Blocked alternative | same availability note |
| 3 | mock-p5 | true | null | `fits` / true | 2 | Blocked alternative | same availability note |

Images on disk: `mocks/img/mock-p3-s0.jpg` and siblings, all present, about 33 KB. JPEG bytes were not opened as pictures.

`POST /refine` `Need parking for 5 trucks.` 200, same thread, `engine: fixed`, `gave_up: ['parking distance']`.

| Rank | Property | Trucks / cars | Notes that matter |
| --- | --- | --- | --- |
| 1 | mock-p3 | 6 / 80 | Availability unknown. Still blocked. |
| 2 | mock-p2 | 1 / 12 | Parking short against 5/10. Freeway flag. Walk 220 m, distance preference relaxed. |
| 3 | mock-p4 | 3 / 30 | Parking short against 5/10. Availability unknown. |

A 1-truck site outranks a 3-truck site because both are blocked and the sort then uses the fixture score (`agent/pipeline.py` lines 272–274).

`POST /approve` `decision: yes` 200: `status: draft_saved`, `sent: false`, engine fixed, source mode mock.

`GET /scout/stream?scene=INT. KITCHEN - DAY. Warm kitchen.` 200 `text/event-stream`. 56 events: 55 `agent`, 1 `result`, 0 `error`.

### Deep engine with no model

Separate process, `TYPECAST_ENGINE=deep`, keys blank, mocks on. `POST /scout` kitchen scene. 200.

- `engines_available` still `['fixed']` (health was read in that process before the scout).
- Events included: `plan` “Starting the deep scouting engine.”; `error` `Deep scouting failed (RuntimeError); fixed fallback is required.`; `fallback` `Deep engine failed; continuing with the fixed engine.`; later `fallback` `Parsed without a model: model parsing is disabled.`
- Response `engine: fixed`, `trace_url: null`.

No network model call was made. `_chat_model` raises before HTTP when the key or model id is missing (`agent/deep.py` lines 56–57).

## Checked against PR #31, not in the top 3

PR #31 head at fetch time is `b068836` (docs handoff). The fix commit named in the task is `6823f6d` (`Fix rejection cleanup for real solver plan shape…`), ancestor of that head, not merged into `dev`. Read-only diff `dbceec2..6823f6d`. Not checked out over this review.

| Area | At dbceec2 | Label |
| --- | --- | --- |
| Failed replan keeping a rejected location | Solver `locations` is an integer (`index/production_solver.py` line 181). The client, only when a returned assignment is still forbidden, does `(p.locations \|\| []).filter` (`index/director.js` lines 116–122). A number has no `filter`, so that path throws and the catch leaves the old plan on screen. A failed replan likewise keeps the rejected location. Successful API reject of `mock-p1` did **not** hit this path. Browser replan was not run. | **fixed in PR31** (`6823f6d` rederives `property_ids` and numeric `locations`, and strips the location locally if replan throws). Not a top-3 item. |
| Stale or overlapping project import, including a slow file read and constraint changes mid-import | `importProject` awaits `file.text()` before `busy(true)` and reads the checkboxes after that await (`index/director.js` lines 581–595). | **fixed in PR31**. Browser import was not executed here. Not a top-3 item. |
| Windows containment tests | `agent/tests/test_aerial_metadata.py` symlink setup skips or uses a portable stand-in when symlink creation is unavailable. | **fixed in PR31**. This machine was not Windows. Pytest on Linux passed. Not a top-3 item. |

## Per-track verdicts

Packet rubrics used: `docs/HANDOFF.md` lines 64–71 and `index/PRIZE-READINESS.md` lines 9–14. A live sponsor HTTP call is not required. Cached CoStar use counts when the code actually decides from it. This review did not open `cache/`.

### Entertainment — AT RISK

What a judge sees if they follow the Director page on **this** server: a status line that says “real results”, then one JPEG (`mock-p1-s0`) assigned to the kitchen, the living room, and the corridor, with company moves 0. The stage badge in source is honest (`UNCALIBRATED SCREEN-SPACE REHEARSAL · GEOMETRIC FIT UNKNOWN`, `index/director.js` line 4). Look around 422s. AI dressing 404s. Generate alternative 503s. Record reel was not run.

What is real in the product, not decoration: multi-scene solver (`index/production_solver.py`), exact property/model join gate on the live branch of the planner (`index/production.py` lines 416–428), A/B staging, silent WebM recorder (`index/director-reel.js`), shoot pack, and a viewfinder that only draws cube faces it can prove (`agent/app.py` lines 221–246). Node reel tests passed with an injected recorder, not a browser file.

Weakest claim: that this two-minute story shows three different real rooms, a model’s alternate take, a 360° look, and an AI-dressed set. None of those four appeared in the run above. A teammate note in `docs/team/status-worlds.md` says five private scan points were dressed on that machine’s gitignored cache. That note is not this run. `GET /api/dressed/mock-p1-s0` is 404, and the viewfinder only asks for dressing after sweep succeeds (`web/viewfinder.js` lines 768–777 and 820).

### CoStar — AT RISK

What a judge sees on this server: fixture ids (`mock-p1` …), availability warning `unknown` even when `available` is true, parking warning `unknown` even when `truck_spaces` is 4, and a scout shortlist whose every reason starts `Blocked alternative` because listing status is null (`agent/pipeline.py` lines 59–61 and 171–174). Require-available covers nothing. Five trucks excludes nothing in the Director.

What is substantive in code, for a private cache this review did not read: live `get_property` / `search_costar` read `cache/join.parquet` and filter `availability_status='available'` (`data/costar_tools.py` lines 103–133). Live logistics read only `cache/vexcel/<id>/logistics.json` and refuse to fill gaps from fixtures (`data/vexcel_tools.py` lines 30–45). The live planner appends a costar join warning and drops `conflict` pairs (`index/production.py` lines 416–428). That is decision-making, not a badge. It was not executed here.

Weakest claim: that the runnable demo shows CoStar or Vexcel changing a location. On public fixtures the Director hides the numeric truck counts whenever `parking_status` is missing (`index/director.js` lines 276–288) and will not treat `estimated: true` plus a count as known (`index/production.py` lines 293–297 and 437–439). The scout pipeline does the opposite for parking: null status is not the string `"unknown"`, so `enough_parking` uses the counts (`agent/pipeline.py` lines 161–169). Same fixtures, two products, two answers.

### Amazon — AT RISK

Packet bar used here: a working prototype with a clear user, any AI stack (`docs/HANDOFF.md` line 69; `index/PRIZE-READINESS.md` line 13). No AWS integration is claimed, and none was found in the app (`docs/architecture.md` line 89).

What a judge sees: a scout that returns three cards and an unsent local draft (`sent: false`), plus a Director rehearsal. The prototype runs. The mock scout’s practical story does not: zero viable picks, and the viewer will paint rank 1 as Available.

`web/drawer.js` lines 25–26 and `web/lib.js` lines 155–160 return “Available” when `availability_status` is missing and `available` is true. `web/tests/lib.test.mjs` line 71 locks that. The pipeline blocks the same object. `web/cards.js` lines 164–167 render that badge next to `reasonSummary`, which keeps the “Blocked alternative” lead (`web/cards.js` lines 35–50). `fitStatus` will also say “Shot fits” because the payload’s `shot_fit.status` is `fits` and `measure_on_site` is false on these fixtures (`web/drawer.js` lines 31–36; `index/geometry.py` lines 43–54). Placeholder JPEGs plus “Shot fits” is the opposite of the project’s own uncertainty rule.

Weakest claim: a location manager could use Monday’s shortlist as shown on the public server. The draft is unsent by design (`agent/app.py` lines 172–206). The cards disagree with the skeptic.

### LangChain — AT RISK

What a judge sees if the entertainment script is all they watch: a deterministic solver and, on this server, fixture scores. That is not a deep agent. `index/director.js` posts `/api/production/plan` directly. It never calls `plan_production_shoot`.

What is real: `create_deep_agent` with market, interior, logistics, and skeptic subagents, plus `plan_production_shoot` on the director tool list (`agent/deep.py` lines 168–186; `agent/deep_tools.py` lines 270–304). Tests in the 597 cover a fake-model dispatch. This run did not.

Weakest claim: narrating the Director status line, the proposal card, or the fixed-engine fallback as a Deep Agents trace. With `TYPECAST_ENGINE=deep` and no model configured, the response engine is `fixed` and `trace_url` is null. The error text is the one quoted above.

## Two-minute run

Server the commands above actually hit: `http://127.0.0.1:8000`. Director docs also mention port 8771; it is the same app. One driver, one clock. Hard stop at 2:00.

Spoken lines below are safe for **this mock run**. Beats marked UNEXECUTED were not clicked. Do not speak a live-cache or browser result unless that beat is repeated on the demo laptop and the screen matches the sentence.

| Time | Action | What this review saw | Say | If it fails |
| --- | --- | --- | --- | --- |
| 0:00–0:12 | Open `http://127.0.0.1:8000/director`. Demo script is the default value in `director.js` lines 6–10. | Page 200. Status string in the served file claims “real results” before any plan. Render UNEXECUTED. | “The stage stays empty until a plan comes back. I have not fetched anything yet.” | If the page does not load, stop. Do not narrate a recording. |
| 0:12–0:28 | Click **Build plan**. | EXECUTED as `POST /api/production/plan`. One plan, moves 0, all three scenes `mock-p1-s0`, score 0.9, mode `mock`. | “Mock mode. The score is a fixture rank, not a kitchen match. All three scenes landed on one placeholder frame. That is not three rooms.” | If the request errors, read the status line and move to Evidence only if a frame is actually assigned. |
| 0:28–0:42 | Click scene 1. Look at Evidence. | EXECUTED in the JSON: availability unknown, parking unknown, `truck_spaces` 4 hidden by the Director summary. Image URL 200. On-screen layout UNEXECUTED. | “CoStar availability is unknown. Vexcel parking is unknown. The JPEG is a labeled synthetic placeholder.” | Point at whatever warning is actually on screen. Do not fill a blank with a truck count. |
| 0:42–0:55 | Add two actors on variant A and press **Play**. | UNEXECUTED. Needs a browser. Node playback tests passed in a harness. | Say nothing about motion until the figures move. If they do: “Screen-space rehearsal. The badge says geometric fit is unknown.” | Use the numeric x/y fields if dragging fails. If Play does nothing, skip. |
| 0:55–1:10 | Type “Try her entering from the window side, slower.” **Generate alternative**. | EXECUTED: 503 `Configured model provider unavailable`. | “The model is not configured. Nothing changed.” | Do not describe a diff you do not see. |
| 1:10–1:25 | **Reject location** on the kitchen scene. | API-only EXECUTED: forbidding `mock-p1` moves every scene to `mock-p2-s0`, still one shared frame. Browser click UNEXECUTED. The client bug that throws when `locations` is numeric is **fixed in PR31** and was not the path this successful response took. | “Reject drops that property. In this fixture run the next frame is still one placeholder for every scene.” | If the status says the replan failed and the old property is still assigned, say that, and do not claim PR31’s fix is on this SHA. |
| 1:25–1:38 | Set Trucks to 5 and click **Build plan** again. | EXECUTED: plan unchanged, 0 insufficient, 27 unknown. | “Five trucks did not remove anyone. Unknown parking is not a no.” | If a property actually disappears and the warning says insufficient, describe that property only. |
| 1:38–1:50 | **Look around the scan**, then AI dressing if a button appears. | EXECUTED as HTTP: sweep 422, dressed 404 for `mock-p1-s0`. Dialog UNEXECUTED. | “This frame has no verified cube, so there is no 360 and no dressed set.” | If a live frame opens a viewfinder, say “scan-relative, not compass” and “AI-imagined” only if that badge is visible. Otherwise skip. |
| 1:50–2:00 | Do not open the camera-planner link. End on the stage. | EXECUTED: that link’s URL returns JSON `status=unknown`, and `/studio.js` is 404. Reel record UNEXECUTED. | “Typecast can rehearse on a real indexed frame when one is actually returned. This run did not return three rooms, a take, or a dressed set.” | Stop at 2:00. |

Optional, only with time stolen from 1:50, and only on a **separate** tab that is already a completed trace: point at calls that are visible. This review has no such tab. `plan_production_shoot` was not invoked.

Do not say: shootable, verified location, measured fit, optimal outside this pool, music, filmmaker endorsement, Peri, Photon, or any raffle. Do not quote 73.33% or 10,568 views; this run did not reproduce them.

## Top 3 demo-breakers

Independent of the three PR #31 areas.

### 1. The demo script does not produce a scene, and the constraint controls do not bite

Command: `POST http://127.0.0.1:8000/api/production/plan` with the three `DEMO` lines, `trucks: 0`.

Observed: one plan, `company_moves: 0`, every scene `mock-p1` / `mock-p1-s0` / `0.9`.

Expected for the entertainment story in `index/DEMO-SCRIPT.md`: a property and a frame per scene that a presenter can distinguish.

Same endpoint with `trucks: 5`, `cars: 10`: still `mock-p1` on every scene, `insufficient` count 0.

Expected if the fixture truck counts were allowed to decide: `mock-p2` (1 truck) would be ineligible for 5 trucks. The Director requires `parking_status` in `{measured, estimated}` before it will (`index/production.py` lines 293–297). The fixture file has counts and `estimated: true` and no `parking_status` (`mocks/logistics.json`).

`require_available: true` on one kitchen scene: `eligible 0`, uncovered `['s1']`.

Expected from the checkbox label “Require available listing” plus `available: true` on the fixtures: a non-empty plan. The planner also requires `availability_status == "available"` (`index/production.py` lines 429–436). The fixtures omit that field.

Mock search is specified to ignore the words and sort fixture scores (`index/search.py` lines 365–367; `index/README.md` lines 127–128). The status line still says “real results” (`index/director.js` lines 614 and 721). Together, the opening minute of the Director demo is one placeholder and two controls that either do nothing or wipe the plan.

### 2. Look around, AI dressing, and “Open existing camera planner” do not show those things for the plan this server returns

Commands and outputs:

- `GET /api/sweep/mock-p1-s0` → 422 `This view has no verified horizon cube geometry`
- `GET /api/dressed/mock-p1-s0` → 404 `No dressed set for this scan point`
- `GET /api/plan/mock-p1-s0?heading=0&focal=35` → 200 `application/json`, `status=unknown`, no room boundary
- `GET /studio.js` → 404

Expected from the button and the link sitting under Evidence: a scan view, and a planner page. The viewfinder fetches sweep first and only then dressing (`web/viewfinder.js` lines 768–820). Cube acceptance requires provenance, heading 0/90/180/270, image path `/cache/views/<shot_id>.jpg`, and a square file (`agent/app.py` lines 221–246). Mock shots are `mocks/img/...` and fail that test. The shared app mounts the JSON plan route, not the preview studio (`index/production_integration.py` lines 21–32; `index/preview.py` lines 47–68).

A private dressed cache reported in `docs/team/status-worlds.md` was not read and was not addressed by these mock ids.

### 3. The scout shortlist is entirely blocked, and the viewer badge disagrees

Command: `POST /scout` with the warehouse sentence (2 trucks, 10 cars).

Observed: 3 picks, every `reason` starts `Blocked alternative`, every first skeptic note is `Availability is unknown…`, rank 1 has `available: true` and `availability_status: null`, and `shot_fit.status` is `fits`.

Expected for the authored warehouse beat: three picks a presenter can defend, with the availability badge matching the skeptic.

`agent/pipeline.py` lines 59–61 treat a missing status as unknown and lines 171–174 add a blocker. `web/drawer.js` lines 25–26 and `web/lib.js` lines 155–160, locked by `web/tests/lib.test.mjs` line 71, render the bare boolean as Available. The card prints both (`web/cards.js` lines 164–189).

Follow-up command: `POST /refine` with `Need parking for 5 trucks.`

Observed: still three blocked picks; rank 2 is `mock-p2` with 1 truck space, rank 3 is `mock-p4` with 3. `gave_up` is `parking distance`.

Expected if “need 5 trucks” is the decision on screen: the ordering among failures would not promote the smaller lot, or the UI would say the order is look-score among blocked alternatives. The reason prefix does say blocked. The rank numbers do not say why a 1-truck site is above a 3-truck site.

## Unexecuted

- Any browser: clicks, drag, Play, canvas pixels, WebGL viewfinder, wipe, file-picker import, microphone, WebM `MediaRecorder`, shoot-pack download. Node harnesses covered some of this without a display. The one skipped node test says so.
- `HEAD` is not how a browser opens `/`. `GET /` redirects to `/app/`.
- Live index, CLIP, `TYPECAST_USE_MOCKS=0`, private `cache/join.parquet`, Vexcel cache, cube provenance, and `cache/worlds`. Not opened.
- Configured-model brainstorm, live `plan_production_shoot`, LangSmith, World Labs generation.
- Playwright `web/tests/check_viewer.py` and `check_viewfinder.py`.
- Windows.
- The demo laptop’s warmed timings. None measured here.
- CI on the review commit. Local gate only.

## Handoff for the fix owner

Baseline to patch is `dbceec2f392af037d4123177e8da35e8a3b877a8` unless PR #31 has since merged. Do not redo these three; they are in `6823f6d`: failed-replan rejection cleanup (`property_ids` plus numeric `locations`), import snapshot before the first await, Windows symlink-test portability.

Remaining, in the order a two-minute demo dies:

1. On `TYPECAST_USE_MOCKS=1`, the demo script’s three scenes share `mock-p1-s0`, trucks never exclude, and Require available uncovers every scene. Either give the public fixtures real `availability_status` / `parking_status` values that match their booleans and counts, or make the Director say “fixture rank” and disable those two controls in mock mode. Change the status strings at `index/director.js` lines 614 and 721 so they do not say “real results” before a response, and so they do not say it in mock mode at all.
2. The Evidence link must not open raw `/api/plan/{shot_id}` JSON. Hide it on `agent.app`, or serve an HTML planner on this app. Until a public shot passes `/api/sweep`, the two-minute script cannot include Look around or AI dressing. A synthetic four-face cube under `mocks/` would make that beat runnable without licensed images. Do not point dressing at a mock id and expect `cache/worlds`.
3. Make `web/drawer.js` `availability()` and `web/lib.js` `availabilityInfo()` use the same rule as `agent/pipeline.py` `_availability_status`: missing status is unknown, including when `available` is true. Update `web/tests/lib.test.mjs` line 71 with that rule. Separately, mock shots that are placeholders should not come back `shot_fit.status == "fits"` (`index/geometry.py` lines 43–54 with `measure_on_site: false` and a filled depth). The warehouse card should not be able to show Available, Blocked alternative, and Shot fits at once.
4. Do not demo `TYPECAST_ENGINE=deep` without a configured model. This SHA answers 200 with `engine: fixed`, an error event, and `trace_url: null`. Show a trace only from a run whose response engine is `deep`.

`python scripts/verify.py` on this SHA: 597 passed, smoke and mock E2E pass, recall N/A. That green gate did not catch the three demo-breakers above.
