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
