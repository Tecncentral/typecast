# Entertainment competitive review

Reviewed 2026-11-14. Document written at 2026-11-14T22:48:33Z. This file is a judge-style comparison for the Entertainment demo. It is not an eligibility ruling, a Devpost submission, or a prediction that any project wins.

Baseline recorded with `git rev-parse HEAD`: `dbceec2f392af037d4123177e8da35e8a3b877a8` (merge of PR #30, `dressed-set`). PR #31 (`https://github.com/Tecncentral/typecast/pull/31`, head `e99082d8c617abf0709e9a029fc1f18ad4d31761`, draft, not merged) was read with `git diff --stat dbceec2 e99082d` and `git show` of `index/director.js` and `web/viewfinder.js`. PR #32 (`https://github.com/Tecncentral/typecast/pull/32`, head `2c2b57f451300691d965943d0fa92b5076abe1f6` at fetch time) is a separate harsh mock-mode demo review. This file does not replace it. Production code was not edited. `cache/` was not opened. No provider calls, keys, sign-ups, or deployments.

## How a cell was scored

Each cell is an integer from 1 to 5. The score is what this review could support, not a prize forecast.

| Score | Meaning |
| --- | --- |
| 5 | This review ran the judge-facing path, and the behavior was in the command output or on a page this review loaded. |
| 4 | A substantial offline check passed, and the judge path is implemented. Hardware, a browser, a key, or a private cache still sits between this run and the table. |
| 3 | The code and a written demo exist. This review ran a slice, or the slice did not show the moment a judge is meant to see. |
| 2 | The piece is in the repo. The path this review ran did not show it. |
| 1 | The repo names it, and this review exercised little or none of the code. |

Official HackPrinceton criteria, from the rules page fetched in this session, are separate from the table: Creativity, Utility, Charity, Avidity. Judging is in person, at most 2 minutes, at least three judges. Source: `https://hackprinceton-fall-26.devpost.com/rules` (fetched 2026-11-14, before 22:48:33Z). The same site's rules prose says submissions close Sunday Nov 15 at 8:00 AM. The JSON on that page has `endDate` `2026-11-15T08:30:00.000-05:00`. Both strings were on the page. This review does not decide which clock the organizers will enforce.

## Who was compared

The Devpost project gallery says the managers have not published it. Source: `https://hackprinceton-fall-26.devpost.com/project-gallery` (same session). A web search for `site:devpost.com/software` plus these project names returned older hackathons, not a Fall 2026 submission page for any of them. **Devpost submission status is unknown for every project below, including Typecast.** A README line that names a track is the repo's own statement, not proof the project was submitted or accepted onto that track.

The five strongest public projects this review could open, within the named priority list, are below. Helm and Stitch were located. They are not guesses.

| Project | Primary repo | Commit this review cloned or read | Created (GitHub API) | Track claim in a source this review opened | Devpost |
| --- | --- | --- | --- | --- | --- |
| Typecast | `https://github.com/Tecncentral/typecast` | `dbceec2f392af037d4123177e8da35e8a3b877a8` (worktree). PR #31 head `e99082d8c617abf0709e9a029fc1f18ad4d31761` read, not checked out as the server. | repo object not re-fetched for created_at | Entertainment is the pitch in `index/DEMO-SCRIPT.md`. Submission unknown. | Unknown |
| BalanceForge | `https://github.com/yjk82693/balance-forge` | `20425d2c1be82dcc1d9ae0bf8e61bc27fe23f656` | `2026-11-14T02:14:14Z` | README: "Built solo during HackPrinceton Fall 2026." No main-track sentence found in the README or in a markdown search for `Entertainment`. | Unknown |
| OmniRiff | `https://github.com/angelofernand0/omniriff` | `ac8694ef6f35d845e8a9d381ff0acb6795083b0a` | `2026-11-14T02:18:30Z` | `docs/SUBMISSION.md`: main track "Entertainment & Media" is "Current" as of 2026-11-14. That is the team's checklist, not a Devpost record. | Unknown |
| Memoria | `https://github.com/AlexWin0806/memoria` | `6e8e54e1c8bcc8f690265ea04c9e46fbbe902f90` | `2026-11-14T07:25:32Z` | README: "Education track." | Unknown |
| Helm | `https://github.com/Mitanshcodes/Helm` | `62c6922d03250bf043cd601f1b1f17078eae4d15` | `2026-11-14T03:34:52Z` | `docs/SPEC.md` line 40: "Entered: Entertainment (main track)" plus hardware, Amazon, Physical AI, and deepagents. Repo statement only. | Unknown |
| Stitch | `https://github.com/jpark2007/Stitch` | `d6d2fe220264fa0572481b4253f18204862bbba5` | `2026-11-13T21:38:41Z` | README prize-track list includes "Entertainment. An animated pop-up storybook starring your own family." Repo statement only. GitHub description field is `asdf`. | Unknown |

### Also opened, not scored

The cap is five. These were opened so a same-stack or same-track repo would not be skipped silently.

- Haunted Listing, `https://github.com/Drashti0913/Haunted-Listing`, commit `9bc477b911cc89ee6fd9dbce6ac5b611f8b60dcd` (API `list_commits`, 2026-11-14). README title "Haunted Listing: Night Shift" says Entertainment track and names CoStar, Vexcel, Matterport, LangChain deepagents, and Capital One Nessie. The same README says the sample buildings in `data/buildings.json` are made up, not CoStar records, and that every tool has a fallback. Not cloned and not run.
- Jester, `https://github.com/aaron-sulbaran/jester`, commit `f61b59e59c4c6812eb2417d3c99bcd452155899d`. README: "Main track: Entertainment." Status in that README: "Early." The first tree is `spikes/pose-match/`. Not cloned and not run.

Name search for repos created after 2026-11-12 with `helm` or `stitch` in the name returned many unrelated projects (Kubernetes charts, cross-stitch, garment editors). This review opened `https://github.com/Alok2221/StitchLab` (garment MVP, no HackPrinceton sentence in the README) and got an empty body for `https://github.com/zamman-ashfaq/HELM` `README.md`. Those are not treated as the hackathon projects. `https://github.com/jbender083-prog/TrueHelm-Game-Download` appeared in the search description as a shipping-lanes game download and its README was not opened.

## What this review actually ran

Commands finished on this machine on 2026-11-14. Python was 3.12.3. The Typecast README pins 3.13. Node was v22.23.4.

### Typecast at `dbceec2`

`/tmp/tc-venv` from `python3 -m venv` and `pip install -r requirements.lock.txt` (exit 0). Server:

```text
TYPECAST_USE_MOCKS=1 TYPECAST_ENGINE=fixed TYPECAST_ENABLE_MODEL_PARSE=0 \
  TYPECAST_ENABLE_VISION_RERANK=0 TYPECAST_ALLOW_VISION_UPLOAD=0 \
  LANGSMITH_TRACING=false uvicorn agent.app:app --host 127.0.0.1 --port 8771
```

Blank `LLM_API_KEY`, `VISION_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `GOOGLE_API_KEY` were set in that process. `GET /health` 200: `mocks: true`, sources all `mock`, `engines_available: ["fixed"]`. `GET /config` 200: `{"mode":"mock","engine":"fixed","tracing":false,"matterport_sdk_key":null}`. `GET /director` 200, 6863 bytes, `text/html`.

`POST /api/production/plan` with the three `DEMO` lines from `index/director.js` lines 6–10, `max_locations: 3`, `trucks: 0`, `cars: 0`, `require_available: false`:

- 200, `mode: mock`, one plan, `optimal_within_pool: true`, pool `mock-p1`, `mock-p2`, `mock-p3`.
- All three scenes assigned `mock-p1` / `mock-p1-s0` / score `0.9`. `locations: 1`, `company_moves: 0`, `mean_similarity: 0.9`, uncovered empty.
- Top candidate warnings: CoStar availability `unknown` (`availability_status` null, `available: true`), Vexcel parking `unknown` (`parking_status` null, `truck_spaces: 4`, `enough_parking` null).

Same body with `trucks: 5`, `cars: 10`: the same assignment. `mock-p1` stayed eligible.

One kitchen scene with `require_available: true`: `locations: 0`, uncovered `['s1']`, top candidate `eligible: false`.

Same three scenes with `forbidden_property_ids: ['mock-p1']`: every scene moved to `mock-p2` / `mock-p2-s0` / score `0.83`. Still one shot id for all three scenes. `company_moves: 0`.

`POST /api/production/brainstorm` with "Try her entering from the window side, slower." and one actor: **503** `{"detail":"Configured model provider unavailable"}`.

`GET /api/sweep/mock-p1-s0` **422** `This view has no verified horizon cube geometry`. `GET /api/dressed/mock-p1-s0` **404** `No dressed set for this scan point`. `GET /api/plan/mock-p1-s0?heading=0&focal=35` 200 JSON, `status: unknown`. `GET /studio.js` 404. `GET /image/mock-p1-s0` 200 `image/jpeg`, 32662 bytes. The pixels were not opened.

`POST /scout` warehouse sentence: 200, `engine: fixed`, `source_mode: mock`, `trace_url: null`. Three picks. Each `reason` starts `Blocked alternative`. Each reported `shot_fit` status `fits`. Property ids were not in the fields this script printed; the reasons name industrial / retail / office fixture text.

`python scripts/verify.py` in that venv, mocks forced by the script's own environment plus `TYPECAST_USE_MOCKS=1` and tracing off: **597 passed in 12.63s**, exit 0. Smoke line: `PASS: mock search -> validated picks -> same-thread refinement -> SSE result -> no-send approval`. Mock eval: 20 attempted, 20 succeeded, 0 labeled, `recall@10: N/A`. Direct `node --test index/tests/director_reel.test.js index/tests/director-project.test.cjs`: **45 passed, 0 failed**. That node command does not drive a browser `MediaRecorder`.

`git diff --stat dbceec2 e99082d` is 12 files, 622 insertions, 61 deletions. `index/production.py` is not in the diff, so the plan JSON above is the same planner code PR #31 leaves in place. The server that answered was the `dbceec2` worktree. PR #31 was not booted.

PR #31, read at `e99082d`, already does these things. They are not in the top 3:

- Mock plan copy: `MOCK_NOTE` in `index/director.js` (`MOCK FIXTURE RESULTS: placeholder frames...`). The demo-button string no longer says "real results" before a fetch.
- Availability: `web/lib.js` `availabilityInfo` and `web/drawer.js` `availability` treat a missing status as unknown, including when `available` is true. `fitStatus` requires `measure_on_site === false` before it will say the shot fits.
- Camera metrics render inside the Director from `/api/plan/...` instead of navigating to raw JSON. Unknown stays unknown.
- Look around in mock mode returns a status and does not open the viewfinder (`index/director.js` `lookAround` handler).
- Rejection cleanup uses `property_ids` and a numeric `locations` count, and strips a rejected location if replan throws.
- Viewfinder stamp constant `AI_STAMP = "AI-imagined set dressing · not the real room"` at `web/viewfinder.js:45`.

At `dbceec2`, `index/director.js` line 614 still sets the demo button status to `Demo script loaded. Press Build plan to fetch real results.` That string is what the worktree serves today. The browser was not opened, so the pixels of either string were not seen.

### BalanceForge `20425d2`

`npm install` exit 0 (134 packages). npm warned `EBADENGINE`: `package.json` asks for Node `>=24`; this machine is v22.23.4. `npm test` (`node --test`) exit 0: **454 tests, 445 pass, 0 fail, 9 skipped**, 70.4 s. Two skips say they need `RUN_SOCKET_TESTS=1`. The README's "412 pass" was not the count this command printed. The README's win-rate table (79.5%, Gemini 540→450, and the rest) was not re-run. No `GEMINI_API_KEY`. `npm run demo` was not started. Presenter UI is `apps/web/src/screens/Present.tsx`, which renders a large rate (`present-big`) and a step list. Screenshots were not opened. `apps/web/REPORT.md` says four README shots were taken from `?mock=1` and are labeled mock.

### OmniRiff `ac8694ef`

Venv with numpy, scipy, jsonschema, websockets, pyserial. sounddevice and MediaPipe were not installed. `python -m unittest discover -s tests`: **Ran 392 tests in 106.350s, OK (skipped=6, expected failures=2)**, exit 0. `python -m engine.demo --headless` printed `demo: dashboard http://127.0.0.1:8080/`, one status JSON (`samplerate` 48000, filter cutoff 18000.0, reverb target 0.0, `input_peak_dbfs` -180.0, udp/serial/websocket disabled), then `demo: stopped dashboard`, exit 0. The dashboard was not opened in a browser. No guitar, camera, or serial device. `docs/SUBMISSION.md` says the live rig is the Entertainment demo and that latency is reported only once measured. This review did not run `tools/latency`.

### Memoria `6e8e54e`

Cloned at the SHA above. `ffprobe` on `docs/media/demo-pitch.mp4`: duration `82.066667` seconds, size `7981392` bytes, MP4. The file was not played. `https://memoria-five-kappa.vercel.app/?judge=1` timed out on fetch. `npm install`, `npm run check`, and `node scripts/smoke.mjs` were not run. Playwright was not installed. The README's 11.3 s / 13.7 s Architect timings and the "13 of 13" smoke claim were not reproduced. No `ANTHROPIC_API_KEY`.

### Helm `62c6922`

`pytest tests/test_mock.py tests/test_contracts.py tests/test_mapping.py` with numpy and pytest on `PYTHONPATH`: **73 passed in 0.64s**, exit 0. That is a subset. The documented `python -m pytest -q` for the whole tree was not run, and MediaPipe, opencv, and `deepagents` were not installed.

Documented smoke `python -m helm --mock --output null --no-server --seconds 3`:

- First attempt, numpy+pytest only: `ModuleNotFoundError: scipy.spatial.transform`.
- After scipy: `ModuleNotFoundError: sklearn.linear_model`.
- After scikit-learn: exit 0. Log line: `stopped after 92 frames, 30.0 fps, median total latency 0.11 ms`. A warning said pyserial is not available, so there was no breath sensor. No camera and no game. The 0.11 ms figure is that process log for the mock source. `docs/SPEC.md` / the README results table still say the camera-to-screen study is pending. This review does not treat 0.11 ms as that study.

### Stitch `d6d2fe`

`pytest tests/screenplay/test_compiler.py` with pytest, pydantic, and pillow, `PYTHONPATH` set to `api/`: **76 passed, 1 failed**, 0.78 s. The failure is `test_load_compiler_returns_the_real_adapter_and_the_sample_compiles` with `ModuleNotFoundError: No module named 'deepagents'` at `api/agent/tools/compile.py:54`. deepagents was not installed, so this is a missing dependency in this run, not a failed animation assertion. `uv`, MongoDB, the web app, and `python -m seed.serve` were not started. No model key.

## Scored matrix

| Project | Technical novelty | Visible creative interaction | Usefulness to a real user | Polish | Reliability of what ran | What a judge sees in ~2 min |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Typecast `dbceec2` | 4 | 2 | 3 | 3 | 4 | 2 |
| BalanceForge | 4 | 4 | 4 | 3 | 4 | 3 |
| OmniRiff | 4 | 3 | 3 | 3 | 4 | 3 |
| Memoria | 3 | 3 | 3 | 3 | 2 | 2 |
| Helm | 4 | 3 | 4 | 3 | 3 | 3 |
| Stitch | 4 | 3 | 3 | 3 | 4 | 2 |

### Typecast

- **Novelty 4.** `index/production_solver.py` groups scenes into properties and reports `company_moves` inside the candidate pool. `index/production.py` keeps unknown availability and unknown parking visible and drops a candidate when `enough_parking` is false. A/B staging, the silent reel (`index/director-reel.js`), and the shoot pack (`index/director.js` `exportPack`) are in the same studio. `agent/deep.py` has a Deep Agents director; this server's health list was only `fixed`, and brainstorm did not call a model.
- **Creative interaction 2.** The executed plan puts the kitchen, the living room, and the corridor on one JPEG. Brainstorm returned 503, so Apply never ran. Sweep returned 422 and dressed returned 404, so the viewfinder did not open. The reel tests passed with an injected recorder. A judge watching this server does not see a figure move or a take change.
- **Usefulness 3.** The user in `index/DEMO-SCRIPT.md` is a director or student filmmaker checking a scene before a scout. The pieces of that job exist: a plan, a rejection, source warnings, an unsent approval (`sent=false` in the verify smoke). On this mock server, five trucks do not remove a property, and "Require available" uncovers the only scene. A location manager cannot see the constraint work.
- **Polish 3.** `/director` returns a full studio page. The stage badge in source is `UNCALIBRATED SCREEN-SPACE REHEARSAL · GEOMETRIC FIT UNKNOWN` (`index/director.js` line 4). The demo button at this SHA still says "real results" before any fetch (line 614). PR #31 rewrites that sentence. This review did not render either page.
- **Reliability 4.** 597 passed, smoke pass, recall N/A, 45 direct node tests pass. The plan, reject, trucks, brainstorm, sweep, and dressed calls above returned real HTTP bodies. Browser play, WebM download, microphone, file-picker import, and the private cache were not run.
- **Demo 2.** In two minutes on this server a judge sees one fixture frame assigned three times, a rejection that swaps every scene to a second fixture frame, and explicit unknowns. BalanceForge, OmniRiff, and Helm each produced a running offline signal in this review (a test suite that covers a presenter, a headless audio status, a 92-frame mock controller). Typecast's signal does not yet show a different room or a different take.

### BalanceForge

- **Novelty 4.** The README describes a deterministic match contract, a designer counter chart, Wilson intervals, a patch that is kept only after a fresh-seed retest, and versions with a parent hash. This review confirmed the tree and the tests, and did not recompute those rates.
- **Creative interaction 4.** `Present.tsx` is a timed presenter with a large percent and duel frames. `npm test` includes presenter and full-flow cases. Nine tests skipped, including socket tests that need an explicit flag. The browser was not opened, so the score stays under 5.
- **Usefulness 4.** The user is a designer who wants a balance change they can replay. The test run exercises diagnosis, versions, and a recorded human-match path. This review did not play a phone lobby. README measured rates stay README claims.
- **Polish 3.** The README and `REPORT.md` describe labeled mock screenshots. Those PNGs were not opened here, so polish is the docs and the passing tests, not a viewed UI.
- **Reliability 4.** 445 pass, 0 fail, exit 0, on a Node version the package marks unsupported. The process still ran.
- **Demo 3.** A two-minute presenter mode is in the tree. This review did not start `npm run demo`, so a judge's actual pixels are still unseen. The test suite is the evidence that the loop is coded.

### OmniRiff

- **Novelty 4.** A guitar signal, a hand landmark clutch, and a footswitch share one control schema, and the README says unsafe or low-confidence events never reach the audio. The unit run and the headless status show an engine that comes up with serial and vision absent.
- **Creative interaction 3.** The headless process printed a live filter and reverb state and a silent input peak. This review did not hear a sweep and did not see the hand skeleton. The creative moment in `docs/SUBMISSION.md` is a person playing.
- **Usefulness 3.** The user is a guitarist who should not let go of the neck, including a limited-dexterity case named in the submission notes. Usefulness at the table depends on the Scarlett, the camera, and the pedal. Those were not here. The software path did start.
- **Polish 3.** The process announced a dashboard URL and then stopped it. The page was not loaded. Brand and demo docs are present.
- **Reliability 4.** 392 tests OK with 6 skips and 2 expected failures, without the vision or PortAudio packages. Headless demo exit 0.
- **Demo 3.** A judge can be shown the simulator. The submission's own two-minute script is the live instrument. This review saw one status line and silence at -180 dBFS.

### Memoria

- **Novelty 3.** A fixed palace, an encode walk, a hidden-image recall walk, and an offline architect are a complete learning loop. The README argues from published memory research and says the app itself has no efficacy study. The technique is older than the repo. The craft is the ink renderer and the judge-mode timing, which this review did not draw.
- **Creative interaction 3.** The README specifies page-to-page motion, color that fills in after a correct recall, and a two-minute judge mode that is supposed to run with the network off. The evidence in this review is that README plus an 82.07 s MP4 on disk. The MP4 was not played, so the score is not a viewed walk.
- **Usefulness 3.** A student memorizing a list is a real user, and the README puts the project on the Education track. Built-in decks are designed to run from fixtures. This review did not complete a walk, so usefulness is the design, not a session.
- **Polish 3.** The README, GIF names, and QA notes are unusually careful. This review did not build the site. The public URL fetch timed out, which is an access failure here, not a finding that the deployment is down for everyone.
- **Reliability 2.** Clone and `ffprobe` succeeded. The project's own `smoke.mjs` / `npm run check` were not run.
- **Demo 2.** Judge mode is the right shape for a two-minute slot. This review cannot say what a judge sees, because the video was not played and the page did not load.

### Helm

- **Novelty 4.** Head pose and expression scores become a controller, with a per-player range and a mock source that runs without a camera. `docs/SPEC.md` also names a coach. The coach was not called.
- **Creative interaction 3.** The mock smoke produced frames and a latency line. Nothing was on a display. The creative moment is a stranger steering a game with their face. That moment was not run.
- **Usefulness 4.** The user is a player with limited hand and arm movement, and the README says Helm should appear as a normal controller. That is the clearest Charity fit among the five. The same README says no evaluation participant has a motor impairment and that the restricted-range test is a proxy. This review did not put a person in front of a webcam.
- **Polish 3.** Dashboard routes are documented (`/?quick=1`, `/?mock=1`). The smoke used `--no-server`, so the dashboard was not served.
- **Reliability 3.** 73 targeted tests passed. The documented smoke exited 0 only after scipy and scikit-learn were added. The full suite and MediaPipe were not installed. The first command failed.
- **Demo 3.** A no-camera smoke runs in about three seconds. The table demo in the SPEC needs a webcam, a quick calibration, and a game. Those were not run.

### Stitch

- **Novelty 4.** `api/tests/screenplay/test_compiler.py` checks a compiler that rejects impossible handoffs, keeps prop state across shots, and is deterministic. That is a real storytelling engine, and 76 tests passed here. The Deep Agents studio in the README was not imported, because `deepagents` was absent.
- **Creative interaction 3.** The compiler is the interaction's backbone. The thing a judge watches is the pop-up book: page turns, pull tabs, a second telling. `seed.serve` and the web app were not started, so that picture was not seen.
- **Usefulness 3.** A family recording a memory is a real user. The README's offline demo signs in as `david@demo.stitch` with a published demo password and does not need MongoDB. This review did not sign in and did not start that server.
- **Polish 3.** The README is a click-by-click runbook, which is presentation-ready as a document. The UI was not opened.
- **Reliability 4.** 76 compiler tests passed. One test failed on a missing import, not on a wrong timeline. The book server was not run.
- **Demo 2.** If the seeded book plays, Stitch is the visual story a two-minute Entertainment judge will remember. This review did not see it. The score stays at what ran.

### Where Typecast can be the one they remember

None of the five turns a screenplay into a short list of rooms, then shows a blocking change on the indexed frame, then shows a vehicle constraint throw a property out with a source warning. BalanceForge shows a rate move inside a game. OmniRiff shows a sound move on a guitar. Helm shows a face driving a pad. Memoria and Stitch show a place that was authored for the demo. Typecast's advantage is the room changing because the scene and the constraint changed, with the unknown left on screen. That advantage was not visible in the HTTP run above: one fixture frame, trucks did nothing, brainstorm was 503, and the viewfinder did not open.

Charity, from the rules page: Helm's player and OmniRiff's limited-dexterity note sit closer to "a specific societal need" than a film-scout tool does. Typecast's honest unknowns are a Utility argument (a scout can trust the card) once a judge can see two rooms and one rejected property. They are not, by themselves, a Charity argument.

## Top 3 changes

These use the Director, A/B staging, the reel, the shoot pack, the viewfinder, the solver, and the CoStar/Vexcel warnings. They do not add a new sponsor API. They do not copy anyone's code. They do not promise a win. PR #31's label, badge, camera-panel, rejection, and import fixes stay as they are. Owner for the implementation: Claude. This review does not implement them.

### 1. The demo script must show two rooms, and a truck count must change the room

**Why.** BalanceForge's presenter is built to show a number move. OmniRiff's headless status shows a filter value. Helm's smoke shows frames moving. Typecast's executed plan assigns `s1`, `s2`, and `s3` to `mock-p1-s0` with `company_moves: 0`, and `trucks: 5` leaves that plan in place. `index/search.py` lines 365–367 rank fixture scores when embeddings are missing, so the scene text does not pick a room. `index/production.py` lines 293–297 set `enough_parking` only when `parking_status` is `measured` or `estimated` and the counts are ints. `mocks/logistics.json` has `truck_spaces` and `estimated: true` and no `parking_status`, so the warning stays `unknown` and the solver never drops the property (`index/production.py` lines 437–439). `require_available: true` uncovered the scene because `mocks/property.json` has `available: true` and no `availability_status` (`index/production.py` lines 429–436). A judge cannot see the only job the other five do not do.

**Files.** `mocks/property.json`, `mocks/logistics.json`, the mock branch of `index/search.py` or the fixture shot scores it sorts, `index/tests/test_production.py`. Leave `index/director.js` mock copy from PR #31 alone.

**Acceptance.** With `TYPECAST_USE_MOCKS=1` and the other model flags off, boot `uvicorn agent.app:app` on `127.0.0.1:8771`. POST `/api/production/plan` with the three DEMO lines, `max_locations: 3`, `forbidden_property_ids: []`, `require_available: false`, `trucks: 0`, `cars: 0`.

Pass: HTTP 200, `mode` is `mock`, the three assignment `shot_id`s include at least two different ids, and `company_moves` equals `locations - 1` for that plan.

POST the same body with `trucks: 5`.

Pass: at least one candidate whose `truck_spaces` is an int below 5 and whose `parking_status` is `measured` or `estimated` has `eligible: false` and a warning `status` of `insufficient`. The set of assigned `property_id`s differs from the `trucks: 0` plan. A candidate whose parking status is still unknown stays eligible. The response does not say the parking count was measured if `parking_status` is `estimated`.

POST one kitchen scene with `require_available: true` after `availability_status` is `available` on the fixtures that already have `available: true`.

Pass: that scene is covered. A fixture that omits `availability_status` stays ineligible, and the warning status stays `unknown`.

Lock it with `python scripts/verify.py`. The new assertions belong in `index/tests/test_production.py` so the gate fails if the three DEMO lines collapse to one shot again.

### 2. When the model is absent, a labeled offline sample still gives A and B, and the reel can record B

**Why.** This review's brainstorm call returned 503 and changed nothing. BalanceForge's README says an offline proposer is labeled when Gemini is absent. Memoria's judge mode is specified to run with the network off. Stitch's README says the offline demo run is scripted. Typecast already has the creative beat the others lack: variant A stays, a proposal shows a diff, Apply writes only B, Undo restores B (`index/director.js` `generate`, `applyB`, `undoApply`), and `recordReel` / `exportPack` already snapshot the active variant. The 503 path never reaches them. Keep the API fail-closed. Do not invent a trace URL or call the sample a model.

**Files.** A small pure function next to the Director, for example `index/director-offline-sample.js`, required by `index/director.js` in the brainstorm `catch` when the status is 503. Tests in a new `index/tests/director-offline-sample.test.js` and one reel case in `index/tests/director_reel.test.js`. Do not change `post_production_brainstorm` into a fake 200.

**Acceptance.**

1. Same mock server. POST `/api/production/brainstorm` with the window-side instruction and one actor, keys blank. Pass: HTTP 503 and `detail` `Configured model provider unavailable`. The body has no `trace_url` and no `shot`.

2. `node --test index/tests/director-offline-sample.test.js`. Pass: given a shot whose only actor has `x0` 0.40, the sample shot's `x0` or `duration_sec` differs; the summary string contains `offline sample`; the summary string does not contain `the model proposed`; applying the sample replaces variant B and leaves variant A byte-for-byte equal to the input; Discard leaves both variants unchanged.

3. `node --test index/tests/director_reel.test.js`. Pass: a case builds a snapshot on variant B from that sample, `recordReel` resolves with the injected renderer, and the test does not open a browser.

Click path, after the patch, on `/director` with the mock server: Build plan, add one actor on A, type the window-side line, Generate alternative. Pass: the proposal card shows `offline sample`, A on screen is unchanged, Apply to B then the B toggle shows the new position, Undo restores B. This review did not click that path.

### 3. One labeled synthetic cube the existing viewfinder can open, beside the indexed frame

**Why.** Stitch and Memoria are built so a judge sees a place immediately. OmniRiff's tests and Helm's mock run with the hardware absent. Typecast's place is the viewfinder. This review got sweep 422 and dressed 404 for `mock-p1-s0`. `agent/app.py` `_cube_face` accepts a face only when provenance, heading 0/90/180/270, and a square file under `cache/views/` all match. PR #31 then refuses Look around whenever `mode === 'mock'`, which keeps a fixture from being narrated as a surveyed room and also removes the only camera beat. The shoot pack and the reel already draw a provenance line. The viewfinder at `e99082d` already has `AI_STAMP`. Use those. Do not put fixture images in `cache/`. Do not weaken the live cache checks.

**Files.** `agent/app.py` sweep response for one explicit synthetic id, new square images and a provenance file under `mocks/` (not `cache/`), `web/viewfinder.js` badge text, `web/tests/viewfinder.test.cjs`, and the `lookAround` branch in `index/director.js` so mock mode opens only that labeled id.

**Acceptance.** Mock server as above.

`GET /api/sweep/<synthetic-shot-id>` Pass: HTTP 200, four faces, headings 0, 90, 180, 270, each image URL under `/mocks/` or another path outside `cache/`, and a field that says the cube is synthetic. A request for `mock-p1-s0` still returns 422.

`GET /api/dressed/<synthetic-shot-id>` Pass: either 404 with the current "No dressed set" detail, or 200 whose dressed URL is a fixture and whose JSON label contains `AI-imagined`. The body must not call the dressed image the scan.

`node --test web/tests/viewfinder.test.cjs` Pass: the synthetic open path draws `synthetic` (or the same words the sweep JSON uses) and, when a dressed frame is shown, the stamp `AI-imagined set dressing · not the real room`. The test double is enough. A live WebGL window is not required for the pass.

Click path: Build plan so the scene uses the synthetic shot, press Look around. Pass: the dialog opens, a drag changes the heading readout, and the synthetic wording is on the dialog. If dressed data is present, the AI stamp is on the dressed frame and absent on the indexed frame. This review did not click that path.

## Two-minute advantage script

One driver. Hard stop at 2:00. Spoken lines are safe only when the screen matches them. Beats are marked from this review's `dbceec2` server unless the line says `e99082d` source. "EXECUTED" means the command ran. It does not mean the advantage was visible.

| Time | Do this | Why it is the advantage | Status |
| --- | --- | --- | --- |
| 0:00–0:12 | Open `http://127.0.0.1:8771/director`. Say the stage is empty until a plan returns, and that the job is rehearsing a script in real rooms before anyone books one. | The other five open on a game, a guitar, a face, a palace, or a storybook. The empty stage is the promise that the room has to be fetched. | EXECUTED: `GET /director` 200 at `dbceec2`. The sentence was not spoken. At this SHA the demo control's source string still says "real results" before the fetch (`index/director.js` line 614). PR #31 replaces that string; the replaced page was not served. |
| 0:12–0:32 | Press Build plan. Point at two different frames and the company-move count. Say they are candidates from a small pool. | This is the move none of the five ran here: the script chooses rooms, and the move count is property visits. | EXECUTED as POST. Advantage not visible: all three scenes were `mock-p1-s0`, `company_moves` 0, score 0.9, `mode` mock. Say that, if this SHA is what is on screen. After change 1, the pass condition above is the line to speak. |
| 0:32–0:48 | Select the kitchen. Point at CoStar availability and Vexcel parking. | Helm, OmniRiff, and BalanceForge can show a live control. They do not show a listing status and a parking estimate as separate unknowns. | EXECUTED in JSON: availability `unknown`, parking `unknown`, `truck_spaces` 4 stored and not treated as enough. On-screen layout UNEXECUTED (no browser). |
| 0:48–1:05 | Put one figure on A. Generate the window-side line. Apply to B. Toggle A and B. | A stays. B is the new take. BalanceForge changes a number. This changes a mark on the frame, and only after a review. | Brainstorm HTTP EXECUTED: 503, no change. Click path, Apply, and the toggle UNEXECUTED. After change 2, speak `offline sample` when the card says it. Do not say the model proposed it. |
| 1:05–1:22 | Raise trucks until a property with a known short lot drops, or reject one location if that is the verified control. | The room changes because the production constraint changed. Stitch and Memoria change scenes because the story was authored that way. | Trucks POST EXECUTED: plan unchanged, no `insufficient` warning. Forbid-`mock-p1` POST EXECUTED: every scene became `mock-p2-s0`, still one shared frame. Browser Reject click UNEXECUTED. After change 1, speak only the property the JSON actually dropped and the word on its warning (`estimated` or `insufficient`). |
| 1:22–1:40 | Play the short reel or, if recording will not finish, open the shoot pack and show the staged frame, the indexed frame, and the unknown lines. | The pack is the leave-behind. The reel is silent. OmniRiff's headless run was silence at -180 dBFS too; the difference is the frame and the warning on the same page. | UNEXECUTED in the browser. Related EXECUTED check: `node --test` on `director_reel.test.js` and `director-project.test.cjs`, 45 pass, injected recorder, no file played back. |
| 1:40–1:55 | Look around the synthetic cube. If a dressed frame is up, read the AI stamp, then flip back to the indexed frame. | Memoria and Stitch show a beautiful place that was drawn for the demo. The advantage is the split: this face is the fixture cube, this other face is imagined, and the stamp says so. | Sweep and dressed EXECUTED at `dbceec2`: 422 and 404 for `mock-p1-s0`. Dialog UNEXECUTED. At `e99082d` the source refuses Look around in mock mode; that click was not run. After change 3, speak `synthetic` only if it is on the dialog, and read `AI-imagined set dressing · not the real room` only if the stamp is visible. |
| 1:55–2:00 | Stop on the kitchen frame. One sentence: rehearse the scene in the room the plan returned, then take the warnings to the scout. | Stop while the frame and a warning are both on screen. | UNEXECUTED as a performance. Do not add a Deep Agents trace. This server's scout response engine was `fixed` and `trace_url` was null. `plan_production_shoot` was not called. |

Words that stay out of the two minutes, from `index/DEMO-SCRIPT.md` and this run: shootable, verified location, measured fit, optimal outside the pool, music, a filmmaker quote, Peri, and any retrieval percent. This run's recall was N/A.

## Industry consultation: pending, no evidence yet

A film-industry contact was reported by the team. No note, quote, name, or recommendation from that conversation was provided to this review. Nothing in this file is an endorsement or a user test.

## Unverified

- Devpost gallery unpublished. No public Fall 2026 software page was found for these five, for Haunted Listing, or for Jester. Track lines in READMEs are not submissions.
- Browser pixels for Typecast: play, drag, Apply, WebM file, shoot-pack download, file-picker import, microphone, viewfinder dialog. Node harnesses covered reel and project logic without a display.
- Typecast live cache, CLIP, `TYPECAST_USE_MOCKS=0`, LangSmith, and a live `plan_production_shoot` trace. `cache/` was not opened. The JPEG bytes from `/image/mock-p1-s0` were not decoded.
- PR #31's server was not booted. Its JS and the badge diff were read. CI on `e99082d` was not checked.
- BalanceForge: `npm run demo`, the presenter in a browser, phone QR, Gemini, MongoDB, Tiger Data, and the README's 79.5% / 412-test figures. Node 22 ran the suite the package declares for Node 24.
- OmniRiff: browser dashboard, guitar, Scarlett, camera, Arduino, `tools/latency`, sounddevice, MediaPipe. Headless output was one status record and a process exit.
- Memoria: video playback, the Vercel page (fetch timed out), `npm run check`, `smoke.mjs`, Architect timings.
- Helm: full `pytest`, MediaPipe, webcam, ViGEm, dashboard, coach model, the pending human study. Smoke needed scipy and scikit-learn beyond the first venv.
- Stitch: `seed.serve`, the Next.js app, MongoDB, deepagents, any page turn. Compiler failure was a missing module.
- Haunted Listing and Jester: README and commit SHA only.
- `https://github.com/jbender083-prog/TrueHelm-Game-Download` was not opened.
- Whether any of these teams will be in the Entertainment room on Sunday. Unknown.
