# HANDOFF (coordinated, current)

## Visibility and cost pass, November 15 2026 ~03:15 ET (Claude Code) — read this first

Stopped here because the usage limit was reached.

### 1. Goal
User asked to make the distance control and cost savings visible, to find any lease-cost data (API key, spreadsheet, Vexcel, database) and tell the producer whether a real apartment beats building a set, and to check the hackathon tracks. Standing rule: every number real and sourced. Deadline 08:00 ET Nov 15.

### 2. Current state
- Branch `ai/claude-business-integration`, PR #57 against `dev`. **This pass is committed locally and NOT pushed** (check `git status -sb`).
- `/director` shows three tiles above the stage: Drive limit (for example "6 of 19 within 10 min", excluded counts, minutes and miles per selected property), Scouting scenario ($2,872.74 at the Local 399 rate by default), Real location vs. building a set (at least $29,881.44 less for one shoot day). Files: `index/director-impact.js`, `index/location-vs-set.js`, hook in `index/director-planning.js`, markup in `index/director.html`, styles in `index/director.css`.
- Releasing the drive slider or toggling the filter rebuilds the plan. Drive section open by default.
- New panel "Real location vs. standing set vs. building a set" with editable inputs, arithmetic, break-even line and source links.
- New endpoint `GET /api/production/lease/{property_id}` in `index/production.py`: reads only `cache/rent/<id>.json`, unknown when absent.
- `data/costar_tools.py` reads an older join (no availability columns) and reports availability unknown instead of failing. Before this, live mode on this laptop had no property data, so any drive limit excluded everything.
- Verified: `python scripts/verify.py` 785 passed, 7 skipped; Node 306 tests, 305 pass, 1 skip. Live browser check with the real cache and real OSRM routing: 20 min gave 14 of 19, slider to 10 min rebuilt to 6 of 19 and moved the pick to a property 6 min away. No console errors, no paid provider call.

### 3. Key decisions and why
- Data on this laptop: `..\owner1\cache` (real views, shot index, older `join.parquet` with 1,581 LA properties) is linked into this worktree's ignored `cache/`. There is no CoStar kit, no rent cache and no Vexcel key here, so lease evidence reads "unknown" on this machine.
- Comparison uses published prices: location $222/h (Giggster LA), standing set $2,000/shoot day (Affordable Sound Stages), stage $3,000/day (Tools for Film, low end), propmaker $57.82/h (IATSE/AICP 2025-2028). Build days, strike days and crew size are unsourced and labelled "your assumption". Blank materials make the build total a lower bound. The teammate's `data/cost_model.py` placeholders are still not shown anywhere.
- Lease rate is a reference floor only and never enters a total.
- Default scouting inputs are now the sourced Local 399 example unless the browser has a stored budget case.
- Tracks: main Best Business and Enterprise Hack; sponsor tracks CoStar, LangChain deepagents, Amazon; Peri conditional. See `docs/TRACK-SELECTION.md`.

### 4. Open issues and risks
- Not pushed; CI on PR #57 not checked.
- Propmaker rate PDF returned 403; figure rests on two matching search readings.
- Scripted Chromium QA suites in `..\manager-drafts\` not rerun; some may assume the old default cost inputs.
- Mock mode never calls routing, so the drive tile shows real numbers only in live mode. A restored browser draft shows "Filter off" until the next Build plan.
- A live server may still be running on port 8012 from this session.

### 5. Next steps
1. Push the branch so PR #57 carries this work; check CI.
2. On the laptop with the CoStar kit: `python -m data.build_join`, `python -m data.rent_precompute`, confirm the lease line shows a real rate.
3. Rehearse the demo on real data: pin, drag the slider, read the three tiles with "scenario" wording.
4. Put the numbers into the video script and Devpost text; submit before 08:00 ET.

### 6. How to resume
- Live server (Git Bash, this folder): `TYPECAST_USE_MOCKS=0 TYPECAST_ENGINE=fixed TYPECAST_ENABLE_MODEL_PARSE=0 TYPECAST_ENABLE_VISION_RERANK=0 LANGSMITH_TRACING=false HF_HUB_OFFLINE=1 ../typecast/.venv/Scripts/python.exe -m uvicorn agent.app:app --host 127.0.0.1 --port 8012`, open http://localhost:8012/director , click Los Angeles, tick the drive filter, Build plan.
- Gates: `TYPECAST_USE_MOCKS=1 ../typecast/.venv/Scripts/python.exe scripts/verify.py`; `node --test bridge/core.test.mjs index/tests/*.test.js index/tests/*.test.cjs index/tests/*.mjs web/tests/*.test.mjs web/tests/*.test.cjs`.
- Sources and arithmetic: `docs/BUSINESS-CASE.md`, `docs/BUSINESS-STATS.md`.

---

## Integration pass, November 15 2026 ~02:00 ET (Claude Code, continuing the Codex coordinator session)

### 1. Goal
User's words: "continue what chatgpt was doing which was fixing my hackprinceton project to be more on the business track." Hard requirements carried over from the Codex session: Business/Enterprise is the main track; **every number must be real, sourced data** (no invented savings); be careful with usage limits; other agents (Claude, Grok/Cursor, Gemini) are the coding workhorses and the coordinator verifies before integrating. Human Devpost submission is due **08:00 ET Sunday Nov 15**.

### 2. Current state
- Branch **`ai/claude-business-integration`** (pushed to `origin/ai/claude-business-integration` on Nov 15 ~02:20 ET at the user's request; PR #57 opened against `dev`), created from `ai/director-production-decisions` at `0580a8a` (itself 2 commits ahead of the pushed PR #43 head: Claude's hardening `90c9528` and its merge). The original branch is untouched.
- Merged here, in order: `origin/cursor/provider-boundary-audit-7eb1` (Grok W7: commute router and unreadable-frame fixes, `c56bfd8`); `origin/lane-b-cost` (teammate Udit: `data/rent_precompute.py`, `data/cost_model.py` and tests, `32123ae`); `origin/map-parking` (PR #50, teammate Zukhriddin: parking on the map and seam repair, `9c334aa`). One conflict, `docs/team/CONTRACT-CHANGES.md`, resolved by keeping both appended sections.
- Added the one still-missing idea from Gemini's review: `index/producer-brief.js` rejects DEL and bidi override/isolate characters in exported memo text, with a regression in `index/tests/producer-brief.test.cjs` (`3c757bc`).
- **`docs/BUSINESS-STATS.md`** (new): sourced problem and cost figures from a web search on Nov 15 (FilmLA shoot days, BLS producer/director pay, union and trade scout and location-manager rates), scenario arithmetic and pitch-ready lines. Each row says whether the source was opened or only seen in a search summary.
- Browser smoke on the merged tree (mock server on port 8011, built-in browser): `/app/` scouts and shows 3 picks with the parking map section; `/director` builds a mock plan, shows the drive slider and the $957.58 source link; no console errors.
- Verified on the merged head (Windows, shared venv `../typecast/.venv`, `TYPECAST_USE_MOCKS=1`, fixed engine, zero provider calls): `python scripts/verify.py` **764 passed, 7 skipped**, smoke and mock E2E PASS; all Node suites **289 tests, 288 pass, 0 fail, 1 browser-only skip**.
- Later the same night `origin/dev` `ef4c111` (PR #51 oblique search) was merged in (`2895cf3`). One conflict in `web/index.html`: kept dev's masthead nav and added the Director link to it. Re-run on that head: **779 passed, 7 skipped**, smoke/E2E PASS; Node 288 pass / 1 skip. The browser smoke was NOT repeated after this merge.

### 3. Key decisions and why
- **Cost model merged as code only, not wired into `/director` or the pitch.** `data/cost_model.py` labels its own inputs "benchmark (supplied, unverified)" and "ASSUMPTION, needs a real quote" (set construction $40/sq ft, CGI $1,500/shot and scouting trip $400 are placeholders). Showing them as savings would break the real-data rule and contradict `docs/BUSINESS-CASE.md` ("No set-construction savings are added"). The only sourced dollar figure for the pitch remains the AICP / Teamsters Local 399 **$957.58/day** scout-manager rate and the 3-day scenario **$2,872.74**, always stated as a scenario.
- **Gemini's returned patcher script was not run.** It targets `producer-brief.js` as of `c549e66`; its anchors no longer exist after `90c9528`, which already screens AWS keys, bearer tokens and private keys. Only the bidi-control check was missing, and it was written by hand.
- **PR #50 merged into this branch** because Grok W8's read-only review (`docs/PR50-INTEGRATION-REVIEW.md` on `origin/cursor/pr50-integration-review-f212`) found only the docs conflict, and the gate passes here. This does not merge PR #50 into `dev`; that is the teammate's call.
- No new features: the buyer/product/evidence debates (`../manager-drafts/business-*-debate.md`) chose honest cash-versus-capacity economics and the producer memo over feature sprawl.

### 4. Open issues and risks
- PR #57 carries this branch; CI on it was not checked at the time of writing. Draft PR #43 (`ai/director-production-decisions`) still ends at `dd6223c` on GitHub. The `gh` CLI is not installed on this machine, so PR and CI state were not checked.
- Browser check was a mock-mode smoke only, not the scripted QA suites in `../manager-drafts/` and not real data.
- In `docs/BUSINESS-STATS.md`, the FilmLA Q1/Q2 totals and the Peerspace/Giggster rental averages come from search summaries and were not opened; open them before putting them on a slide. The Local 399 chart was checked by the Codex coordinator, not reopened.
- Not possible from this machine: real private-cache/GPU demo-laptop acceptance, a live OSRM route rehearsal, a live image-provider preview, the original Discord evidence for the filmmaker quote, Devpost track selection and submission.
- `data/cost_model.py` placeholders must not be quoted in the video or Devpost text.

### 5. Next steps
1. **PR #57** is open against `dev` (ready for review, not draft): https://github.com/Tecncentral/typecast/pull/57 . Watch its CI, and close or retarget draft PR #43, which it supersedes.
2. Put the `docs/BUSINESS-STATS.md` pitch lines into the video script and Devpost text (`docs/VIDEO-CLAIMS.md`, `docs/devpost.md`), keeping the scenario wording.
3. On the demo laptop with the private cache: rehearse one real-data commute filter and the day-rate recalculation per the two-minute script in `docs/BUSINESS-CASE.md`.
4. Record the video from `docs/VIDEO-CLAIMS.md` and `docs/VIDEO-HANDOFF.md` (content only was requested; no more generated full videos).
5. Human: select Business/Enterprise on Devpost and submit before 08:00 ET.

### 6. How to resume
- Repo worktree: `C:\Users\lfitz\Documents\Codex\2026-11-14\i-r\work\claude-unified` (remote `https://github.com/Tecncentral/typecast`). Coordinator notes and debates: `..\manager-drafts\`. Deliverables: `..\..\outputs\` (start with `Typecast-Business-Case.md`).
- Gates, from Git Bash so globs expand: `TYPECAST_USE_MOCKS=1 ../typecast/.venv/Scripts/python.exe scripts/verify.py` and `node --test bridge/core.test.mjs index/tests/*.test.js index/tests/*.test.cjs index/tests/*.mjs web/tests/*.test.mjs web/tests/*.test.cjs`.
- Prior coordinator transcript: `~/.codex/sessions/2026/11/14/rollout-2026-11-14T03-39-21-*.jsonl`. Gemini review conversation: https://gemini.google.com/app/3c841599e7b2b4a1 . Grok worker link: `docs/EXTERNAL-AI-WORK.md`.

---

## Earlier coordinated notes

**November 15 business update:** the team chose **Business/Enterprise**. See `docs/BUSINESS-CASE.md`, `docs/TRACK-SELECTION.md` and `index/AI-CONTINUATION.md` before the historical notes below. PR #43 now includes real road-time constraint plumbing, an editable cost scenario with a sourced commercial day-rate example, broader scene direction and explicit imagined-image previews. Quoted filmmaker feedback and permission are user-reported, not measured savings. Local acceptance: 693 Python pass/7 skip, 233 Node pass/1 skip, 19 browser checks (SYNTHETIC proposal/image responses, no paid calls). Real cache/route rehearsal and live image-provider preview remain for the demo laptop. Human Devpost track selection/submission is still needed.

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
