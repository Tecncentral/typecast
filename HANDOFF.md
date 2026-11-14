# HANDOFF (coordinated, current)

> Update 2026-11-14: unified candidate branch `ai/director-unified` (merges director-restyle 6ba671b and job8-submission-story b89293b onto 6001063). Local only, not pushed. See `index/UNIFIED-INTEGRATION-HANDOFF.md` (goal unchanged; resume with `python scripts/verify.py`, QA scripts in `../manager-drafts/unified-qa/`).

Branch `ai/claude-release-audit` (PR #31), base origin/dev dbceec2. Code head: c5dbfcb (no code changed in the browser pass). Not pushed by this session. Details and per-finding evidence: `index/CLAUDE-RELEASE-REVIEW.md`. Demo script/checks: `index/GEMINI-DEMO-HANDOFF.md`.

> Second pass: PR30 dressed-set fixes (label/prompt, face path allowlist, corruption/decoding) done on `ai/director-unified`; details in `index/UNIFIED-INTEGRATION-HANDOFF.md` section "PR30 dressed-set fixes". Full verify: 649 passed, 7 skipped; Node 116 pass/1 skip. Not pushed.

> Third pass: read-only Compare A/B, explicit authored offline sample, dressed-cache no-spend guard, docs/COMPETITIVE-DECISIONS.md. See index/UNIFIED-INTEGRATION-HANDOFF.md section on Compare A/B. Not pushed; no film consultation claimed.

> Fourth pass: authored-sample origin now follows the take (card, JSON, import, pack, PNG, WebM); mobile compare captions; film anecdote recorded as unverified in index/FILM-VALIDATION-HANDOFF.md. Main code phase ends; not pushed.

## 1. Goal
Release QA for HackPrinceton Typecast (Director, reel, project import, viewfinder, AI dressing). Fix reproduced failures only; mock/synthetic data only; no push/merge/provider calls/private data. Interior labeling is complete; no more labeling.

## 2. Current state (commits, oldest first)
fb1d54f rejected-location-after-failed-replan · 153c302 portable Windows symlink tests + import overwrite guard · 6823f6d real solver-shape rejection cleanup (`property_ids`, numeric `locations`), import snapshot before first await, constraint guard · b068836 Gemini demo handoff (Claude-reviewed, docs) · 81a8452 AI-dressed viewfinder grab stamp/filename + dressing lifecycle tests (Grok Worker4 leads: provenance fixed; close race and Director-label leads not reproduced) · c5dbfcb Grok Worker5 (PR32 baseline dbceec2) findings fixed: status-authoritative availability, measured-only shot fit, mock-fixture labelling, fixture Look-around explanation, in-page camera metrics panel.

## 3. Verified counts (Windows, existing venv, at c5dbfcb)
`scripts/verify.py` exit 0: 596 passed, 5 skipped (4 file-symlink skips with portable equivalents + 1 prior); smoke, SSE/refinement/no-send approval PASS; 20/20 unlabeled mock attempts, recall N/A. Node: director-audit 32 pass/1 skip (browser-only surface), director-project 29, director_reel 16, viewfinder 8, web lib 15, bridge/core 6; 0 failures. Linux counts from other workers (e.g. 597) are a different context; ignore the stale 539.

## 4. Browser check status (truthful)
RUN in a real Chromium (Playwright 1.65.2 + Chromium 1255, installed only into the test venv; clean ephemeral profiles; loopback mock server, mocks/fixed engine, model/vision/tracing off; tiny synthetic fixture images, not live proof). Evidence and screenshots live outside the repo in `../manager-drafts/browser-qa/` (README, JSON results, scripts, PNGs).
- `web/tests/check_viewer.py --failure-states --mobile`: passed, 7 checks, no assertion edits.
- Director acceptance (my scripts): initial status no longer says "real results"; after Build the status and plan summary say MOCK FIXTURE RESULTS / MOCK FIXTURES; Evidence shows availability, parking, walk, noise as unknown; the camera metric panel renders in-page from /api/plan with unknowns and the assumed-heading label; Look around shows the fixture explanation and opens no dialog; Reject removes mock-p1 ("Rejected: mock-p1", scenes move to mock-p2) and the frame-change notice appears; exported project JSON re-imported through the real file chooser restored staging (dialogue + 7 s duration, 3 drafts restored, 0 for review) with the MOCK label; no page errors.
- Still not browser-verified: WebGL viewfinder / AI dressing / grab stamp (fixtures have no scan geometry), WebM recording, microphone, live-provider traces, the demo laptop's real cache. Cosmetic: the metric panel prints raw floats (e.g. 39.16239859440563); not changed.

## 5. Open items
- Grok Worker4: still pending its own report; compare against review items "Grok Worker4 leads".
- Grok Worker5 (PR32, 2c2b57f at dbceec2): resolved per review. Unchanged by design: fixture limits (one placeholder frame, trucks not excluding, Require-available emptying mock plans), scout ordering among blocked alternatives, deep-engine fallback.
- Older AI-dressed thumbnails saved before the stamp fix keep unstamped pixels.
- A mock run proves nothing about live CoStar/Vexcel/LangChain eligibility.

## 6. Human final demo (integration captain's machine, private cache)
Follow `index/GEMINI-DEMO-HANDOFF.md`: run verify there; time cold/warm Build plan; record Evidence statuses; choose one replan (Reject, or vehicles then Build plan); check Look around/AI dressing exists for the chosen frame; record and open a WebM; real file-chooser project import and microphone only if tested; genuine Deep Agents trace only if completed; sponsor permission before showing licensed imagery; keep a fallback recording; submit before 08:00 ET Sunday 15 Nov.

## 7. Resume
`node --test index/tests/director-audit.mjs web/tests/lib.test.mjs web/tests/viewfinder.test.cjs`; `python scripts/verify.py` with `typecast/.venv`.

## 8. Coordination state (latest)
- PR #31: code head c5dbfcb, docs e99082d; CI passed per coordinator. Demo handoff (`index/GEMINI-DEMO-HANDOFF.md`) is Gemini-drafted and Claude-reviewed.
- Grok Worker5 (PR32 baseline dbceec2) findings: fixed in c5dbfcb; real-browser mock acceptance recorded (section 4).
- Grok Worker4 closeout: pending.
- New Grok competitor worker: requested; treat as UNVERIFIED launched until the manager confirms.
- Film contact: found, NOT consulted. Template: `index/FILM-VALIDATION-HANDOFF.md` (blanks stay blank; do not edit `docs/peri.md`, owned by Owner 4). Root forwards real feedback and competitor evidence before any new idea is implemented.
- Remaining: live acceptance on the integration captain's laptop (see section 6); human submission before 08:00 ET Sunday 15 Nov.
