# Lane D — viewer

Updated: 2026-11-14 19:53 UTC.

Viewer implementation: `d871894`; shared lane-d history and dev integrated in `a5801a1`. Earlier asset/progress milestone: `de84d15`. Work is isolated in `../typecast-d`; the other session's main checkout is untouched. No bridge, index, backend, contract or API dependency edits.

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
