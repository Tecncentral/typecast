# Unified Director integration handoff (candidate, not merged)

Branch `ai/director-unified`, local only (not pushed, not merged to dev/main). Prepared by Claude on 2026-11-14. Mock/fixture evidence only; no provider calls, private cache, secrets or user profiles.

## Source snapshots (as fetched at start; origin may have moved since)
- Base: `ai/claude-release-audit` head `6001063` (my accepted fixes: rejection cleanup with solver shape, import races/constraints, authoritative badges, mock labels, fixture Look-around explanation, in-page camera metrics, AI-grab labels, portable Windows tests).
- `origin/job8-submission-story` `b89293b`: docs only (README, architecture, demo-runbook, devpost, pitch). Merged clean, no conflicts.
- `origin/director-restyle` `6ba671b`: director.css/html/js, director-ui.js (new tab chrome), production.py (route for director-ui.js), director-audit.mjs. Merged with 2 conflicted files (below).
- Merge commit: `c6e7b26` (candidate head when this was written; `git log -1` for the final head including this doc).

## Conflict resolution
`index/director.html` (right column): took restyle's tabbed panels (Shot / AI take / Evidence / Export). Restore: relabelled planner link to "Show camera metric panel (heading 0° assumed, unverified)" and re-added `#plannerOut` (restyle dropped it; my in-page metrics code needs it). Verified every `$('id')` used by director.js/director-ui.js exists in the HTML.
`index/director.js` (8 hunks): kept restyle's `orderPlans` (coverage, then fewest locations, then similarity) and its plan-meta wording, and applied it on both Build and project import. Kept my `MOCK_NOTE`/`modeNote`, the "MOCK FIXTURES ·" prefix (added to restyle's new planMeta text), the rejection comments, my import snapshot/constraint guards (`limits`, `rev`), and the "check its mode label" start status (restyle's "returns real results" wording is false in mock mode, so it was rejected).
Test updates (director-audit.mjs, my solver-shape test): second fixture plan is now partial coverage so coverage-first ordering keeps the intended plan first; summary regex changed to restyle's "1/2 scenes · 1 location" wording. No assertion on rejection, cleanup or claims was weakened.

## Behavior change to know about
Restyle reorders solver plans client-side (full coverage first, then fewer locations). Solver order was similarity-first. The planMeta text says so. It is presentation only; similarity stays labelled "not shootability". Captain: accept or revert `orderPlans` as a product decision.

## Actual results
- `scripts/verify.py`: 596 passed, 5 skipped (same counts as base); smoke/eval ran in fixed/mock.
- Node: director-audit 33 pass / 1 skip (browser-only surface), director_reel pass (50 pass, 1 skip combined with reel test run). Other suites unchanged by this merge (not rerun individually).
- Real Chromium 1255 via Playwright 1.65.2, clean ephemeral profile, loopback `127.0.0.1:8001`, `TYPECAST_USE_MOCKS=1 TYPECAST_ENGINE=fixed`, model parse/vision/tracing off; server stopped afterward. Artifacts: `../manager-drafts/unified-qa/` (`qa_unified.py`, `qa_copy.py`, `unified-result.json`, `copy-result.json`, `screens/*.png`, project.json, stage.png, reel.webm; bulky, not in Git).
  - Build: status and plan meta carry the MOCK FIXTURES label; plan summary 3/3 scenes, 1 location.
  - A/B independence: A "A_TEXT", B "B_TEXT" persisted separately.
  - Evidence: availability/parking/crew walk/noise render Unknown; source warnings listed; parking "Not a parking approval".
  - Camera metrics: in-page panel renders from /api/plan with heading-0 assumed/unverified and unknowns kept.
  - Look around (fixture): explains no scan geometry; no dialog opens.
  - AI take (model disabled): honest "Brainstorm unavailable ... No changes made", no proposal, so Apply/Discard/Undo not exercisable in the browser. They are covered by Node suites only; needs a live-model check.
  - Reject: `Rejected: mock-p1`, replan to mock-p2, changed-frame notice shown; staging stays on old frame; "Copy old staging" restored KEEP_ME in the browser.
  - Exports: Project JSON (honesty text, review_needed, source_mode), Stage PNG `typecast-s1-A.png`, WebM `typecast-reel-variant-A.webm` all download. File-chooser import reports mock label, 0 restored / 3 retained for review (saved frame no longer matches), rejected list not carried.
  - Layout: no horizontal overflow at 390px mobile (scrollWidth 390) or 820px tablet; desktop screenshots reviewed in `screens/`.
  - Browser errors: no page errors; one expected console 503 from the disabled model provider.

## Not verified / remaining live checks (integration captain, real-data laptop)
1. Live mode: no MOCK label, real frames, Apply/Discard/Undo with a real model proposal, AI-vs-real labels through the wipe and in saved grabs/filename.
2. Look around on a real scan point; dressed-grab pixel/filename label in a real browser.
3. Real Reject replan on live solver data (solver-shaped tests pass; no live run here).
4. WebM reel of real frames; file contents of reel.webm were not decoded here beyond download success.
5. Visual review of restyled desktop layout by a human (screenshots only checked by this session for overflow/controls).
6. Story docs claim (devpost.md ~line 42) that downloaded JPEGs do not yet carry the dressed label pending PR #31. This branch contains the label (81a8452, Node-tested), so the text is stale only if PR #31 merges; do not promote the claim before a live pixel check. Left unchanged, since docs belong to the story lane.
7. No film-industry contact, consultation or endorsement claim exists in these docs and none was added (name/role/feedback/quote permission pending).

## Captain next steps
Re-fetch both source branches (if they moved, rerun the merge on a fresh candidate), run `python scripts/verify.py` and the Node suites, repeat the browser script against live data, decide on `orderPlans`, then push/PR to dev through the normal lane flow. This session did not push.

## PR30 dressed-set fixes (second pass)
Source audit: PR35 baseline `origin/cursor/pr30-regression-audit-c56a` head `02f5d64` (baseline dev `dbceec2`), read via `git show`; its tests were ported, its suggested patch was not applied (the fix is stricter). Mock/synthetic only; no provider calls, no private cache.

Fixes (files: `worlds/dress.py`, `agent/app.py`, `web/viewfinder.js`):
1. Label/prompt: `/api/dressed` always returns `dress.LABEL`; `prompt`/`prompt_used`, camera and asset ids are no longer returned; scene text bounded (200 chars, printable), `scene_id` simple-id only. Viewfinder badge uses its own canonical constant, never `data.label`.
2. Face paths: faces must be a single basename `[A-Za-z0-9_-]{1,64}.(jpg|jpeg|png|webp)` naming an existing regular, non-symlink file directly inside the exact `worlds/<model>/<sweep>/dressed` dir (symlinked/junctioned dir rejected). Record must carry the same `model_id`/`sweep_id` as the shot (genuine records always do) and ids must equal their `_safe` form. Splat file likewise (`.spz`). Client re-validates `dressed_url` against `/cache/worlds/<id>/<id>/dressed/<name>`.
3. Corruption: bad JSON, wrong types, >1 MB, NaN/inf/out-of-range yaw/pitch/FOV, missing faces: `load_dressed` returns None -> clean 404 `No dressed set for this scan point`; an individually bad face is dropped (max 4 faces). Client: `this.dressed`, the badge, `.vf-dress` and the "ready" status are set only if at least one dressed image decoded. Partial coverage says "covers N of M views; the real room shows dimmed elsewhere".
Side effect to know: a cached record that fails validation now looks "absent" to `worlds/dress.py` batch skip logic, so a rerun without `--force` would regenerate (spend) for it; genuine records are unaffected.

Tests: `index/tests/test_pr30_regressions.py` (Grok's 7 xfails now plain passes + positive, traversal x17, symlink, scan-point mismatch, corruption x15, splat, bounds), `index/tests/pr30-regressions.mjs` (2 todos now pass), 6 new lifecycle cases in `web/tests/viewfinder.test.cjs`; `agent/tests/test_worlds.py` fixture now writes synthetic image bytes and model/sweep ids; existing viewfinder test URLs moved to the valid dressed path shape.
Before (baseline source, same tests): Python 50 failed / 12 passed in those two files; Node viewfinder+pr30 6 failed / 10 passed. After: 62 passed, 2 skipped (symlink tests need privilege on Windows); Node 116 pass, 0 fail, 1 skip, 0 todo across the 7 listed suites.
Full `scripts/verify.py`: 649 passed, 7 skipped (5 earlier + 2 Windows symlink), fixed/mock engine. Windows dir junction rejection checked manually (`unified-qa/junction_check.py`); file-symlink tests run on Linux CI only.
Chromium acceptance (synthetic PNGs written to an ignored, previously absent `cache/worlds`, deleted afterwards; real fetch + real `Image.decode`, WebGL stubbed): valid set -> controls shown, canonical badge, 4 textures, no leaks (`sk-SYNTH`, home path, "Real captured", prompt, camera all absent); 1 undecodable -> "covers 3 of 4 views"; all undecodable -> controls hidden, no ready; traversal name, corrupt JSON, missing yaw, wrong scan point -> API 404 and no controls; 0 page errors. Artifacts `../manager-drafts/unified-qa/dressed-result.json`, `qa_dressed.py`, `before-*.txt`. Not live World Labs output.
Docs: devpost/demo-runbook/architecture/pitch now say the AI-grab stamp exists in this candidate but is verified only with a canvas test double (Node), not a rasterized real-browser JPEG; do not claim labeled exports until PR #31 is human-merged and a live JPEG is inspected.
Snapshot note: `origin/job8-submission-story` has since moved b89293b -> 4f62f3b (not merged here); re-merge on a fresh candidate if wanted.
Remaining live checks: real World Labs dressed assets (full-size decode, WebGL pixels of wipe/dimmed partial coverage), a rasterized grab JPEG with the stamp, Look-around on a real scan.

## Compare A/B, authored sample, and cache no-spend (third pass)
Independent inputs: Gemini patch `../manager-drafts/gemini-compare-ab.patch` (untested draft; used as the idea only, see `docs/COMPETITIVE-DECISIONS.md` for what was rejected) and Grok review PR39 `b8cd2a1` (peer README/offline claims; stale `dbceec2` baseline). No workers were spawned by this session.

Built (`index/director.js`, `director.html`, `director.css`): (1) `Compare A/B`, a read-only preview of the same frame/playing scene: two natively sized panes, per-take label/duration, one real-time clock where scene length = longer take and the shorter take holds ("ended at Ns, holding last pose"), uncalibrated label kept, canvas drag/keys and take fields locked, selecting A/B leaves compare, PNG exports the active take only (single layout forced at capture), JSON/pack carry both. (2) `Load authored sample alternative`: no network, fixed mirror-and-cross from take A (generic performer if empty), labelled not-AI, through the existing proposal review; Apply writes B only; Undo/Discard unchanged; loading cancels any in-flight model request; scene/edit changes drop it. The 503 path is unchanged and never substitutes.

Cache no-spend (`worlds/dress.py`): new `dressed_cache_state`; `main` now fails closed (exit 1, "no credits were spent") on an existing invalid cache unless `--force`; a valid cache is still skipped, an absent cache still generates. Regression in `index/tests/test_pr30_regressions.py` uses a provider-client stub that fails on any use. The live generator was not run.

Tests: 9 new Compare/sample cases in `index/tests/director-audit.mjs` (mutation-checked: removing the compare guards or the single-layout PNG makes them fail) and 5 no-spend cases. Final counts are in the commit message / final report.

Clean Chromium mock acceptance (`../manager-drafts/unified-qa/qa_compare.py`, `compare-result.json`, `screens/c0*.png`): mock labels kept; brainstorm 503 shown honestly with no proposal; sample review text labelled authored/not AI; Apply changed only B (A stayed 0.30/0.30 with its dialogue and duration); compare strip stated 3s vs 6s; clock ran 4.2s / 16.0s with take A "ended at 3s, holding last pose" and B "4.2s / 6s"; canvas drag and arrow keys changed nothing; PNG while comparing was `typecast-s1-A.png`; JSON recorded active take B with both variants and source_mode mock; file-chooser re-import restored take B and 3 exact-frame drafts; mobile 390px has no horizontal overflow; the only console error is the expected 503. Limits: on mobile the two panes are small and in-pane badges are cramped (usable, not pretty).

Remaining live film-demo checks: run with live data on the captain laptop (real frames, live labels); a human judgment of compare readability; the film contact's feedback and permission (pending, no consultation claimed); real-browser JPEG stamp and real World Labs assets; WebM reel with real frames; introduce the sample as offline sample blocking, not AI.
