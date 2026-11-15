# HANDOFF (coordinated, current)

**Current candidate: draft PR #43, branch `ai/director-production-decisions`** (https://github.com/Tecncentral/typecast/pull/43, targeting `dev`). PR #40 (`ai/director-unified`) is merged history. Root pushed the initial checkpoint `2dd70e8`; the later fixes are in this branch and are **not pushed by the implementing session**: independent-review fixes `7bf5cc0`, docs `dafe706`, `origin/dev` `3bf131a` (PR #42 dressed-set: decisions/status plus `web/viewfinder-cast.js`, walk additions, `web/tests/cast.test.mjs`) merged cleanly by `7f6d6d3` with no conflicts, then the final code commit **`750de74`** (swap-notice wording, system-sans printable sheet). Documentation commits follow it. Root pushes, checks CI and updates PR #43.

What this lane adds (client-side Director only, no dependency, no backend or shared-schema change): per-scene Fit check; one-click candidate location swap (takes copied for review, never calibrated by confirming); production decision sheet inside the existing Shoot pack with both takes as text and staged images; opt-in continuity warnings. Details: `index/UNIFIED-INTEGRATION-HANDOFF.md` ("Production decisions", "Independent review pass", "Final integration"); additive Project JSON fields: `docs/team/CONTRACT-CHANGES.md`.

Final gates at `750de74` (Windows, mock/fixed engine, synthetic fixtures, no private cache, provider or paid call): `python scripts/verify.py` (shared venv `../typecast/.venv`): 667 passed, 7 skipped (Windows: 5 earlier skips plus 2 file-symlink skips; a Linux run skips fewer), smoke/SSE/approval PASS, mock eval 20/20 unlabeled, engine fixed, mode mock. Node, one command: `node --test bridge/core.test.mjs index/tests/director_reel.test.js index/tests/director-project.test.cjs index/tests/director-checks.test.cjs index/tests/director-audit.mjs index/tests/pr30-regressions.mjs web/tests/lib.test.mjs web/tests/viewfinder.test.cjs web/tests/cast.test.mjs`: 170 tests, 169 pass, 0 fail, 1 skip (browser-only surface), 0 todo. Web package script `cd web && node --test tests/*.test.mjs` (includes the new `cast.test.mjs`, 3 tests): 18 pass, 0 fail. Clean Chromium mock checks: `/director` and its assets, `/app/` and the walk/cast modules load together without console errors; swap-notice wording and the printable sheet verified. Earlier 40-check production journey and 27-check review run are in `../manager-drafts/production-decisions-qa/` (not committed).

Not run here: `web/tests/check_walk.py` (needs a live server with a dressed scan point and splat in the private cache; the captain's laptop), live model/trace, real GPU pixels, microphone, CI on the pushed head, Peri evidence (conversation with Mahimn Dave is reported, not a validated consultation; `index/FILM-VALIDATION-HANDOFF.md`) and the human submission (reserve 06:30-08:00 ET Nov 15). Mock fixtures say nothing about live CoStar/Vexcel/Matterport data.

# Historical handoff sections (earlier lanes)

> Update 2026-11-14: unified candidate branch `ai/director-unified` (merges director-restyle 6ba671b and job8-submission-story b89293b onto 6001063). Local only, not pushed. See `index/UNIFIED-INTEGRATION-HANDOFF.md` (goal unchanged; resume with `python scripts/verify.py`, QA scripts in `../manager-drafts/unified-qa/`).

Branch `ai/claude-release-audit` (PR #31), base origin/dev dbceec2. Code head: c5dbfcb (no code changed in the browser pass). Not pushed by this session. Details and per-finding evidence: `index/CLAUDE-RELEASE-REVIEW.md`. Demo script/checks: `index/GEMINI-DEMO-HANDOFF.md`.

> Second pass: PR30 dressed-set fixes (label/prompt, face path allowlist, corruption/decoding) done on `ai/director-unified`; details in `index/UNIFIED-INTEGRATION-HANDOFF.md` section "PR30 dressed-set fixes". Full verify: 649 passed, 7 skipped; Node 116 pass/1 skip. Not pushed.

> Third pass: read-only Compare A/B, explicit authored offline sample, dressed-cache no-spend guard, docs/COMPETITIVE-DECISIONS.md. See index/UNIFIED-INTEGRATION-HANDOFF.md section on Compare A/B. Not pushed; no film consultation claimed.

> Fourth pass: authored-sample origin now follows the take (card, JSON, import, pack, PNG, WebM); mobile compare captions; film anecdote recorded as unverified in index/FILM-VALIDATION-HANDOFF.md. Main code phase ends; not pushed.

> Docs freeze: job8 story 4f62f3b merged (f462f6d, no conflicts, frozen); AI-CONTINUATION/DEMO-SCRIPT refreshed; film contact recorded as pending/unverified (Mahimn Dave, Lagaan mentioned; no claim he worked on it, not Emmy-winning); PR35 audit superseded; submission window starts 06:30 ET. Code head 5519c78. See index/UNIFIED-INTEGRATION-HANDOFF.md. Not pushed.

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
- Film contact: conversation reported by the user (Mahimn Dave, short filmmaker); validated Typecast consultation NOT done (hands-on feedback, affiliation, attribution consent, Peri evidence pending). Template: `index/FILM-VALIDATION-HANDOFF.md` (blanks stay blank; do not edit `docs/peri.md`, owned by Owner 4). Root forwards real feedback and competitor evidence before any new idea is implemented.
- Remaining: live acceptance on the integration captain's laptop (see section 6); human submission before 08:00 ET Sunday 15 Nov.
