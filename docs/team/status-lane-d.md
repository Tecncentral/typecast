# Lane D — viewer

## Job 6 — inside-out descent complete

Updated: 2026-11-14 21:22 UTC.

Implementation: `656ec09`; validated aerial metadata: `e72b32a`; latest dev (`886762b`) integrated in `39bdf8f`. Work remains isolated in `../typecast-d` on `lane-d`. Review target: [PR #23 into dev](https://github.com/Tecncentral/typecast/pull/23). No new runtime dependency.

- Fresh live scouts play one approximately three-second map → Vexcel aerial → real Matterport frame → first-card View Transition. Click or any key skips; replay does not rescout. Refinement retains its change summary without automatic descent. Reduced motion uses short fades with no flight or zoom; mocks and missing imagery/georeferencing degrade honestly.
- Supplied parking geometry projects against validated EPSG:3857 extent and exact image dimensions, including holes. Independent comparison checked 7,894 vertices across the three top-pick properties within two pixels. Unreliable metadata uses the existing supplied aerial image; no invented outline. Job 6's explicitly authorized narrow `GET /api/aerial/{property_id}` is documented in `CONTRACT-CHANGES.md`; general cache JSON remains inaccessible.
- Reviewed PR #25 at `6660265`, verified it, and merged it with separate compatibility fixes in `ffac1d0` / `a4f9ca4`. Reopening, stale dismissed loads and mobile controls pass. Original `web/viewfinder.js` and `web/viewfinder.css` remain byte-identical to that PR. Compatibility also keeps `Look around` clear of the frame counter.
- Impeccable animate/overdrive guided the sequence. Run-section padding and source-note line height are corrected. Fresh independent finish review: ship, no blocking visual or interaction findings at 1440×900 and 1280×720. Private design records remain in ignored `cache/viewer-design/`.

### Verification

- Latest integrated branch: `.venv/bin/python scripts/verify.py` — **401 passed**, fixed mock end-to-end passed, 20 unlabeled mock evaluation scenes completed (not an accuracy score). `node --test web/tests/*.test.mjs` — **12 passed**.
- Descent browser: **10 genuine live runs**, five scenes × both desktop sizes; all passed. **30 controlled cases** passed for skip, replay, reduced motion, missing imagery/extent/geometry, unsupported View Transitions, mocks and refinement. Four additional headed checks covered replay from another supplied frame and simulated visibility cleanup. Chrome **157.0.8103.52**, Playwright **1.65.2**.
- After merging the latest backend, **all five genuine live scenes passed again at 1440×900**. Animation duration **2.970–3.010 s**, RAF p95 **16.7–16.8 ms**, maximum sampled interval **33.3–33.4 ms**, no observed long tasks or application JavaScript errors. Initial two-size runs took **2.974–3.079 s**; isolated longer frame gaps were observed. These are animation measurements excluding scouting/preparation, not a guarantee of uninterrupted 60 fps.
- Final viewer regression on a separate mock server: **7/7 passed**, including both desktop sizes, 390×844, same-thread five-truck refinement, unsent drafts, API failure, no matches, unavailable images and pending connection.
- Pre-merge viewfinder gate: **8 fixture / 9 real-cache checks passed**, including normal/reduced motion, reopen and stale-load handling. General mock viewer baseline also passed before the merge.

Reproduce the live descent with private prerequisites:

```sh
TYPECAST_USE_MOCKS=0 TYPECAST_ENGINE=fixed .venv/bin/python -m uvicorn agent.app:app --port 8001 --no-access-log
cache/browser-venv/bin/python web/tests/check_descent.py --base-url http://localhost:8001 --mode live --output cache/screens/descent --executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

Private proof: `cache/screens/descent-first/`, `descent-controls-final/`, `descent-headed-final/`, `descent-latest-dev/`, `job6-viewer-final/`, and `job6-pr25-compat-real-final/`. Phase captures explicitly identify controlled UI replays of real cached responses; they are not fresh engine runs. Reports, screenshots and licensed data are uncommitted.

Next: integrator review and merge of PR #23 into dev. The verified live preview is [localhost:8001/app/](http://localhost:8001/app/). No blocking Job 6 issue remains. Visibility cleanup passed a labelled simulation; actual background-tab visibility could not be established by the local browser runner. The imported viewfinder's uncancellable load must settle before reopening. Heading alignment remains unverified. No deployment, main merge or external contact occurred.

## Earlier viewer handoff — historical

Updated: 2026-11-14 19:53 UTC.

Viewer implementation: `d871894`; shared lane-d history and dev integrated in `a5801a1`. Earlier asset/progress milestone: `de84d15`. Work is isolated in `../typecast-d`; the other session's main checkout is untouched. No bridge, index, backend, contract or API dependency edits.

Review: [PR #23 into dev](https://github.com/Tecncentral/typecast/pull/23), pushed through `ca92c6a`. GitHub reported it mergeable, with both Python 3.13 verification jobs passing at that revision. The later upstream state-handling commit is preserved in history; stream failures retain the verified explicit-retry behavior instead of automatically starting a second scout. The integrated web files are unchanged from the tested `a5801a1` revision.

## Working and verified

- Plain HTML/CSS/ES modules at `/app/`, with local Leaflet and Barlow fonts. Impeccable 4.9.0 guided the dark frame-first remake. The independent finish reviewer scored both requested fixes resolved: concise expandable rationale and compact expandable skeptic caveats. Design context lives in private ignored `cache/viewer-design/` to respect the requested write scope.
- Exact default scene and five text-only demo presets; real EventSource activity, deep todo updates, source/engine labels, real elapsed time, returned trace links and honest relaxed/no-match/error/slow states.
- Three ranked frame cards, frame cycling, explicit unknown geometry, zero-safe counts, evidence statuses, aerials, noise, skeptic notes and availability. A keyboard-accessible drawer retains all supplied evidence and caveats. No owner contacts render.
- Same-thread five-truck refinement shows rank moves/new objections and retains earlier frames. Draft requests happen only on an explicit click and confirm only `draft_saved` with `sent=false`.
- Local Leaflet pins and correctly ordered parking geometry; optional street tiles with local aerial fallback.
- Optional Matterport SDK waits for playing state and idle transitions, matches the exact returned sweep and confirms against `Camera.getPose`. Immediate and repeated scan navigation passed in live Chrome. Image heading alignment remains unverified.

## Verification

On integrated commit `a5801a1`:

```sh
.venv/bin/python scripts/verify.py
node --test web/tests/*.test.mjs
```

Results: **291 Python tests passed**, fixed mock end-to-end passed, 20 mock evaluation scenes completed (unlabeled, not an accuracy score); all **12 inherited helper tests passed**.

Browser fixture server:

```sh
TYPECAST_USE_MOCKS=1 TYPECAST_ENGINE=fixed TYPECAST_ENABLE_MODEL_PARSE=0 TYPECAST_ENABLE_VISION_RERANK=0 LANGSMITH_TRACING=false .venv/bin/python -m uvicorn agent.app:app --host 127.0.0.1 --port 8003
cache/browser-venv/bin/python web/tests/check_viewer.py --base-url http://localhost:8003 --mobile --failure-states --executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

**7/7 passed**, Playwright **1.65.2**, installed Chrome **157.0.8103.52**. Actual mock API flows at 1440×900, 1280×720 and 390×844 verify images, complete disclosure text, evidence, trace rules, same-thread refinement, retained frames and explicit unsent drafts. No application console errors, JavaScript exceptions or horizontal overflow. Four separately labeled controlled cases cover API failure, empty results, missing imagery and a pending connection. They are UI simulations, not live engine evidence.

Live servers used `TYPECAST_USE_MOCKS=0` and respectively `TYPECAST_ENGINE=fixed` on 8001 and `TYPECAST_ENGINE=deep` on 8002. Existing private caches and authorized provider configuration were prerequisites. Both live Chrome runs returned three actual candidates, decoded `/cache/views/` frames and `/cache/vexcel/` aerials at both desktop sizes, provided real traces, and preserved the thread/earlier frames through five-truck refinement. Observed scout times were **9.697 s fixed** and **52.919 s deep**, single-run observations. Deep refinement correctly reports the API's fixed engine. No browser JavaScript exceptions. The live fixed server is left at [localhost:8001/app/](http://localhost:8001/app/) for rehearsal.

Private evidence (never committed): `cache/screens/viewer-report.json`, `viewer-*-scout.png`, `viewer-*-refine.png`, controlled-state screenshots, `live-fixed-report.json`, `live-deep-report.json`, `live-tour-verified.json`, `live-*-scout-*.png`, `live-*-refine-*.png` and `live-deep-activity.png`. Captures exclude contacts. Full design documents and screenshots remain ignored, as do licensed source data, joins and generated drafts.

## Next and limits

Integrator: inspect the lane-d PR into dev and run the browser command with private prerequisites or mock mode as appropriate. No merge to main or deployment performed.

Core UI is local; optional tour/SDK and street tiles require a network. Heading alignment is unverified. Missing dimensions, walk routing, parking permissions and filming access remain visible limitations. A ranked result is not a booking or permission. Individual live runtimes are not latency guarantees. No owner message was sent. No blocking viewer issue remains from the recorded acceptance checks.

## UI simplify (branch ui-simplify)

Updated: 2026-11-15 10:48 UTC. Mode: mock. Only web/ and this file changed.

What moved where:
- Header is just TYPECAST plus the MOCK/LIVE and engine badges. The Interiors / Exteriors / Director's Room nav is gone; /director still works, it is just not linked.
- Brief: one input for a scene or a whole script, an Interiors / Exteriors switch beside it (Exteriors links to the existing oblique page), demo scene chips under it, and one "Scout" button.
- Script mode: 2+ INT./EXT. headings show "Script: N scenes detected". Scout then calls the Director's Room planner (POST /api/production/plan, same body as index/director.js) instead of single-scene scouting. It shows the planner's own summary ("N scenes · N locations · N company moves"), its pool_note caveat, and one group per planned location with its frame, the scenes it covers, parking (estimate/unknown) and the planner's warnings. The scene split is a simple heading-based reading in web/script-mode.js, not the Director's Room parser.
- Scout: the activity log starts collapsed. The status line shows the latest real agent step and elapsed seconds; one click opens the full log.
- Single-scene cards, map, travel and budget, refine and draft note are unchanged in content and order.

Cut (not done):
- Constraints row (trucks, crew cars, production base + max drive) was not moved up. budget.js builds those controls inside renderBudget, and moving them safely did not fit the hard stop.
- Clicking a card to select it and drive the map highlight and cost panel was not wired.
- "Look around" / "Edit (AI)": no change. On mocks the fixture shots show no "Look around" button, so visibility on real scan views is unverified here.

Verification (mock server on port 8013):
- scripts/verify.py: 1082 passed, 1 xfailed. node --test web/tests/*.test.mjs: 24/24.
- web/tests/check_viewer.py --mobile --failure-states: 7/7 passed (Playwright 1.65.2, bundled Chromium; cache/venv-browser on this laptop).
- Manual at 1440x900 and 1280x720: scene, 3 cards, activity collapsed, refine "need parking for 5 trucks" shows What changed, Draft note shows "local draft, not sent", then a 3-scene script shows "Script: 3 scenes detected" and the mock plan "3 scenes · 1 location · 0 company moves" with caveats. No JavaScript errors.
- Before/after screenshots: cache/screens/ui-simplify/ (not committed).

Recommendation: safe to demo on mocks. Not run against live data or the private index.

### UI simplify v2: split landing, in-place modes (11:19 UTC)

- Landing is a split screen: Interiors | Exteriors. Hovering a half widens it; clicking animates (View Transitions) into that mode. No page loads: routes are #interior / #exterior hashes, so Back and the TYPECAST wordmark (home) work.
- Header shows an Interiors/Exteriors pill once a mode is chosen.
- Interiors: "One scene | Whole script" toggle. Pasting 2+ INT./EXT. headings flips it on its own. Whole script runs the planner and offers "Rehearse in the Director's Room", which opens /director in a sheet over the page, prefilled with the pasted script (Build plan stays the user's click). The sheet is created on open and removed on close.
- Exteriors: the existing oblique page is embedded in place (its duplicate header hidden). On mocks its search needs a live Vexcel key and says so.
- Cards lift and push in slightly on hover; reduced-motion users get no motion.
- web/tests/check_viewer.py now opens /app/#interior (the landing no longer shows the scene box first).
- Verified on mocks: verify.py 1082 passed / 1 xfailed; web tests 24/24; check_viewer.py --mobile --failure-states 7/7; walkthrough at 1280x720 (landing, hover, interior, scout, cards, script plan, Director's Room sheet with the pasted script, exteriors, Back, home) with no JavaScript errors. Screenshots: cache/screens/ui-simplify/v2-*.png.
- Not checked: live data, real exterior results, Director's Room behaviour beyond opening with the script.

### UI simplify v3: filters on top, costs on click (11:28 UTC)

- The Travel and budget section under the results is gone. Its four controls (production base, max drive, scene size, shoot days) now sit in a filter bar above the cards. They are the same budget.js elements, moved in web/costs.js, so changing one still re-queries drive times and costs. The drive-time caveat is one line; hovering shows the full text.
- Clicking a card (not its buttons or links) slides in a "Cost savings · estimate" panel for that pick. Headline figures count up from $0 to their exact values, and the range bars grow in. The "Scenario estimate… not verified savings" line stays at the top. Esc, Close or the backdrop closes it.
- Verified on mocks: check_viewer.py --mobile --failure-states 7/7 (fixed a 29 px horizontal overflow at 1440 found by it); verify.py 1082 passed / 1 xfailed; web tests 24/24. Manual: the panel opens per card with the right figures; scene size 2,000 → 5,000 sq ft changes "Build the set" from $34,500 to $79,500. Screenshots: cache/screens/ui-simplify/v3-*.png.

### UI simplify v4: live filters (11:35 UTC)

- The filter bar now filters the shortlist as you drag. budget.js announces its drive times, costs and drive limit with a "budget:data" event (additive; its logic is unchanged). web/costs.js listens and hides cards whose known drive time is over Max drive or whose found-location estimate is over a new Max budget slider (range from the picks' own estimates). Unknown drive time or cost never hides a card.
- Each card shows "N min drive · est. $X" (or "unknown"). A line under the filters says "Showing N of M" and why, with Reset filters.
- On mocks, drive times are unknown (routing is not called), so the drive slider cannot hide anything there; filtering by drive was checked with a routed commute response (25/55/80 min): 60 min left 2 of 3 cards, then a $7,250 budget left 1, and Reset brought back 3.
- Checks: check_viewer.py --mobile --failure-states 7/7; verify.py 1082 passed / 1 xfailed; web tests 24/24. Screenshot: cache/screens/ui-simplify/v4-filtered.png.

### UI simplify v5: budget slider $0 to $250,000 (11:40 UTC)

- Max budget now runs from $0 to $250,000 (or the highest estimate, if larger), starting at the top so nothing is hidden. The track is cubic, so the low end moves in $5 steps ($30 → $35) and arrow keys move one notch; every value is a multiple of $5. A number box beside it takes an exact amount in $5 steps and stays in sync.
- Checked: positions 100/102 give $30/$35, 400/401 give $2,000/$2,015; typing $6,000 hides all three mock picks (each is $6,196 without drive times) and Reset restores them. check_viewer.py 7/7; verify.py 1082 passed / 1 xfailed; web tests 24/24.

### UI simplify v6: examples instead of "Demo scenes" (11:50 UTC)

- The "Demo scenes" row is now "Try an example:", with dashed suggestion chips under the scene box. Hovering a chip previews its full scene text. Clicking fills the box and puts the cursor at the end; it no longer starts scouting (it used to scout immediately). The five validated scenes and Roller disco are unchanged in web/scenes.js.
- Whole script mode starts empty with a placeholder and offers one "Three-scene script" example instead of the single-scene chips.
- Checked: a chip click makes no /scout request and focuses the box; the script example shows "Script: 3 scenes detected"; check_viewer.py --mobile --failure-states 7/7 after two overflow fixes it caught (previews now hang from the examples row, and the preview box uses border-box); verify.py 1082 passed / 1 xfailed; web tests 24/24.

### Whole script: 8-scene planner limit (11:53 UTC)

- POST /api/production/plan rejects more than 8 scenes (HTTP 422, checked: 8 ok, 9 rejected). The brief now reads up to 60 headings, says "Script: N scenes detected. The planner takes 8 at a time, so Scout plans scenes 1–8" when there are more, sends the first 8, and the results say "Planned scenes 1–8 of N … scenes 9–N were not planned".
- Checked in the browser: 3-scene example → one /api/production/plan call, "3 scenes · 1 location · 0 company moves"; 10-scene script → "8 scenes · …" plus the not-planned line, no error; Director's Room sheet opens with the pasted script. Live planning (private index) not checked here.
