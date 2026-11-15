# HANDOFF (coordinated, current)

## Current Status — Save the scene (`39077b6ca7bafd0f127dbbb307ff1fc69fbbdef3`)

- **Branch / PR:** Open draft PR #43 on `ai/director-production-decisions` (includes frozen `origin/dev` `4b4f92c`; prepared for publication from code head `39077b6ca7bafd0f127dbbb307ff1fc69fbbdef3`; PR #43 remote head and CI are authoritative once published; no `dev`/`main` merge).
- **What changed:** Added Film-mode **Save the scene** (`index/director.html`, `index/director.css`, `index/director.js`, `index/director-checks.js`, `index/director-project.js`, `index/SAVE-THE-SCENE.md`), hardening pass for complete valid revised solver plans (all scenes covered, `max_locations` and rejections preserved, unknown positive parking never met, `swapStale` exact assignment match, `dest_kept` status truthfulness, `#saveBtn` re-enabled after `busy(false)` / import / draft restore), and historical decision persistence across JSON, local drafts, and Shoot pack.
- **Verified gates (local Windows venv, mock/fixed engine, zero provider calls):**
  - `python scripts/verify.py`: **672 passed, 7 skipped** (including 2 Windows symlink cases).
  - Node suites (9 suites): **228 passed, 1 browser-only skip, 0 failed, 0 TODO**.
  - Clean Chromium QA (`../manager-drafts/save-scene-qa/qa_save.py`): **33/33 checks true** (default mock fixtures produced an honest non-result due to unknown capacity; positive flow verified via clearly labeled `SYNTHETIC` intercepted responses).
- **Remaining human/live checks:** Captain's real-data laptop verification (343 properties / 10,568 views cache), GPU/splat walk, live model / `plan_production_shoot` trace, microphone, filmmaker feedback, track opt-ins, and Devpost submission before 08:00 ET Sunday Nov 15.

---

**Current candidate: draft PR #43, branch `ai/director-production-decisions`** (https://github.com/Tecncentral/typecast/pull/43, targeting `dev`; not merged: `HEAD` is not an ancestor of `origin/dev`). Root pushed head `9bbd456`; everything after it is **unpushed by the implementing session**: `origin/dev` `4b4f92c` merged (`2052ba3`), the Community planning / screenplay intake / draft recovery milestone (through `70ab022`), then the independent-review fixes at code head **`b666fc5`**, plus documentation commits. Root reviews, pushes, checks CI and updates PR #43 (a new PR only if #43 has merged by then).

This pass (peer reports were untrusted static analysis; each alleged bug was reproduced on the previous head before fixing and rejected with a reason otherwise): fixed colon-containing ids truncating site reports (keys are now `site:<scene>|<property>`); a capacity typed without a source vanishing (now an incomplete note, never counted as verified, kept through scene/mode/export/import/draft); a community project smuggling film takes, notes or sample provenance (ignored on import and restore); community first-line pipe dropping text; one failed draft restore freezing autosave for both modes (holds are per mode); unreadable or newer-version drafts being wiped (set aside with download/discard); `Clear saved draft` being undone by the next autosave (now literal); restore success judged by English status text (now a structured result); a script edited after a build being saved as if the old plan matched it (`plan_script` recorded and flagged). Rejected: "one pipe forces the original format" (the code requires every line to contain a pipe), "control characters are XSS" (all output uses `textContent` under a restrictive CSP), "remove the 8-draft or size caps" (bounded refusals that keep current work), and speculative localization failures. Full list and evidence: `index/UNIFIED-INTEGRATION-HANDOFF.md`.

Track decision published: `docs/TRACK-SELECTION.md` (main: Entertainment and Media; sponsors CoStar, LangChain deep agents, Amazon; Peri conditional; Photon, SpaceX raffle, Gemini API and the rest skipped or unproven). `docs/devpost.md` (candidate-track sentence only) and `index/PRIZE-READINESS.md` (header note only) were refreshed; other owners' measurements and story were left intact. No eligibility ruling, win, consultation, adoption or latency claim is made.

Final independent-review pass at `b666fc5`: `python scripts/verify.py` (shared venv `../typecast/.venv`): 672 passed, 7 skipped (Windows: 5 earlier skips plus 2 file-symlink skips), smoke/SSE/approval PASS, engine fixed, mode mock. Node, one command: `node --test bridge/core.test.mjs index/tests/director_reel.test.js index/tests/director-project.test.cjs index/tests/director-checks.test.cjs index/tests/director-audit.mjs index/tests/pr30-regressions.mjs web/tests/lib.test.mjs web/tests/viewfinder.test.cjs web/tests/cast.test.mjs`: 210 tests, 209 pass, 0 fail, 1 skip (browser-only surface), 0 todo. `cd web && node --test tests/*.test.mjs` (incl. cast): 18 pass. Clean Chromium mock journeys (no saved profile, loopback, no provider call): both modes 49 checks (intake, mode separation, community checks, Site Brief and print, JSON with real file chooser, refresh recovery, keyboard, blocked storage, failed fetch, corrupt draft, mobile 390) and a 20-check recovery run (failed restore then other-mode edit then refresh, incomplete capacity, literal clear, future-version draft set aside with download and discard, plan-text mismatch). Screenshots and the printed brief were inspected for clipping and legibility.

Not run here: `web/tests/check_walk.py` and anything needing the real private cache (captain's laptop), live model/trace, real GPU pixels, microphone, CI on the pushed head, real organizer review of Community mode, Peri evidence (the Mahimn Dave conversation is reported, not a validated consultation; `index/FILM-VALIDATION-HANDOFF.md`) and the human submission (reserve 06:30-08:00 ET Nov 15). Local drafts are plain text in the browser (clear on shared computers); no external model was called and nothing was spent.

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
