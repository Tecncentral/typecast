# Typecast viewer

Plain HTML, CSS and JavaScript modules served by FastAPI at `/app/`. There is no frontend build step. Leaflet and fonts live in `web/vendor/`; the core viewer works without a CDN. Opening the optional interactive Matterport tour explicitly loads its remote SDK and Showcase. Basemap tiles also need a network; supplied local aerials remain available when tiles fail.

From the repository root, start a fixture server:

```sh
TYPECAST_USE_MOCKS=1 TYPECAST_ENGINE=fixed TYPECAST_ENABLE_MODEL_PARSE=0 TYPECAST_ENABLE_VISION_RERANK=0 LANGSMITH_TRACING=false .venv/bin/python -m uvicorn agent.app:app --host 127.0.0.1 --port 8001
```

Open [the local viewer](http://localhost:8001/app/). `MOCK` means invented properties and synthetic placeholder images, including the browser check's data. `LIVE` describes source mode, not filming permission. Parking capacities are estimates; listing availability does not grant filming access. Unknown measurements and noise conditions need on-site confirmation.

`scenes.js` contains only the five authored scene descriptions from the private demo set. It contains no property anchors, result records, images or contact details. Presets set the brief; they do not promise the same result on another index or engine.

The Impeccable design uses local Barlow type, charcoal, ivory and amber, with large uncropped frames and visible source status. Cards show a compact rationale derived from supplied text or fit/parking facts; `Full reason` expands the exact returned rationale. The first three skeptic notes and new refinement objections stay visible, with remaining caveats in an explicit disclosure. Every note remains in the evidence drawer. Design process documents stay in ignored `cache/viewer-design/` under this task's web-only write boundary.

## Inside-out descent

A fresh scout's top pick gets one approximately three-second sequence: the existing map flies to the property, its Vexcel aerial reveals the supplied parking outline, the aerial pushes into the real Matterport frame, and a View Transition lands that frame in card 1. Click or press any key to skip; `Replay descent` repeats it without another scout. Refinement keeps attention on the changed shortlist and offers replay without automatically playing the sequence again.

The narrow `GET /api/aerial/{property_id}` route returns validated georeferencing for one numeric property ID. Its EPSG:3857 extent, image dimensions and source coordinates must match the private cached image and property. The viewer projects supplied parking geometry, including holes, into those pixels. Missing or inconsistent metadata uses the existing aerial image with a wipe; missing imagery skips the unsupported layer. Neither path invents a boundary. The general `/cache/` route still serves images only.

Reduced motion uses approximately 200 ms fades, with no flight, zoom or spatial morph. Mocks show a labelled synthetic frame with no aerial claim. Browsers without View Transitions fade into card 1. Cleanup restores the map, focus and document interaction on completion, skip, supersession or visibility loss.

PR #25's original `viewfinder.js` and `viewfinder.css` are unchanged. Separate compatibility files handle repeated WebGL opening, stale dismissed loads, the narrow-screen layout and placement of `Look around`. Because the imported loader is not cancellable, reopening waits for a dismissed load to settle before opening the requested room.

Run the descent check against a separately started local live server with the private demo prerequisites:

```sh
cache/browser-venv/bin/python web/tests/check_descent.py --base-url http://localhost:8001 --mode live --output cache/screens/descent --executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

It runs the five scene presets through the actual API at 1440×900 and 1280×720, then separately labels controlled response replays for skip, replay, reduced motion, unavailable imagery/georeferencing, missing View Transitions, mocks and refinement. Phase captures are controlled UI replays of real supplied images, excluded from performance measurements. The visibility-cleanup case explicitly simulates `document.hidden`; it is not proof that a particular browser or OS actually hides a background tab. Reports and screenshots remain under ignored private `cache/`.

Ten initial live runs on Chrome 157.0.8103.52 / Playwright 1.65.2 measured 2.974–3.079 seconds for the animation, with RAF p95 of 16.7–16.8 ms and no observed long tasks. Isolated frame gaps occurred, so this is typical 60 Hz cadence rather than uninterrupted 60 fps. These numbers exclude scouting latency and asset preparation. The independent Impeccable finish review found no blocking issue at either desktop size.

## Browser acceptance check

Run against a separately started local mock server. The script refuses live/mixed source mode before taking screenshots and never starts or stops the server. This laptop already has an isolated browser environment with **Playwright 1.65.2**:

```sh
cache/browser-venv/bin/python web/tests/check_viewer.py --base-url http://localhost:8001 --screens-dir cache/screens --executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

For a fresh checkout, keep browser tooling separate from API production dependencies:

```sh
python3 -m venv web/.venv
web/.venv/bin/python -m pip install playwright==1.65.2
web/.venv/bin/python -m playwright install chromium
web/.venv/bin/python web/tests/check_viewer.py --base-url http://localhost:8001
```

Use `--executable /path/to/chromium` to select a compatible installed Chromium or `--headed` to display the check. Add `--mobile` to also run at 390×844. `viewer-report.json` records the actual Playwright and Chromium versions for the PR. No API dependency files were changed.

The check uses the real mock API at 1440×900 and 1280×720. It checks three returned cards, decoded interior images, skeptic objections, the evidence drawer, source/engine/trace labels, elapsed time, same-thread refinement with `need parking for 5 trucks`, rank/objection changes, earlier frames, horizontal overflow and browser errors. It confirms no `/approve` request occurs before an explicit `Draft note` click, then verifies the returned draft is unsent. That click saves a local draft in ignored `cache/outbox/`; it does not contact anyone. Listing contact values and contact links must be absent in both the viewer and drawer. The drawer closes before screenshots are saved.

For additional, explicitly simulated failure checks:

```sh
cache/browser-venv/bin/python web/tests/check_viewer.py --base-url http://localhost:8001 --failure-states --mobile --executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

Those cases intercept requests or keep a browser-only EventSource pending to exercise API error, no match, missing imagery and a slow connection. Their screenshots carry a `CONTROLLED UI CHECK` banner and report entries have `controlled: true`. They are UI checks, not evidence of engine results or performance. Console errors from intentional 503/missing-image requests are recorded; JavaScript exceptions still fail the case. Baseline runs fail on application console errors; known resource failures from OpenStreetMap tile hosts are recorded separately as `expected_map_errors`, since the viewer intentionally handles an offline basemap.

Screenshots and `viewer-report.json` stay under ignored `cache/screens/`, including when `cache/` is a symlink to a private local cache. A failed run replaces the report with its actual failed state. Do not commit screenshots, cached licensed images, joins, generated drafts or credentials.

## Live rehearsal

Start live mode only when the private source cache and index are present and sponsor permissions are established. Restart when changing source configuration. Use `http://localhost:8001/app/` for the Matterport SDK domain allow list; `127.0.0.1` is not an approved SDK browser domain. SDK headings have not been verified: a scan-point tour must be labelled accordingly, and a general model link opens at the model's start.

Check actual `/cache/views/` interiors and `/cache/vexcel/` aerials in a browser, including long addresses, unknown dimensions, zero/unknown parking, empty matches and errors. The mock acceptance report does not establish live-data readiness. Real-data screenshots must exclude contacts and stay private. Trace links may appear only when the response supplies a real `trace_url`. Owner notes remain local drafts.

On November 14, 2026, live Chrome rehearsals returned three real candidates on both engines, decoded their interior and aerial images at both desktop sizes, and preserved the same thread and earlier frames through five-truck refinement. The observed fixed scout took 9.697 seconds; deep took 52.919 seconds. These are individual runs, not guarantees. The deep response's refinement correctly reported the fixed engine. Both runs returned trace links and no browser JavaScript exceptions. Exact Matterport sweep navigation was confirmed against `Camera.getPose`, including immediate and repeated clicks after observable SDK readiness; heading alignment remains unverified. Private reports and screenshots are in `cache/screens/live-*-report.json`, `live-tour-verified.json` and `live-*.png`.
