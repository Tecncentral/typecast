# Claude release QA review (branch ai/claude-release-audit)

Base: origin/dev dbceec2 (PR22 Director + PR30 dressed sets). Mock/synthetic only; no network, .env, cache or provider access. No subagents were dispatched; this was a single-agent review.

## Verified defects and fixes
1. **Rejected location reappeared after a failed replan** (index/director.js). Reject added the property to `S.forbidden` then called `build(true)`; if `/api/production/plan` failed, the old response (still assigning the rejected property) stayed on screen and in JSON/shoot-pack/reel exports while the "Rejected:" list claimed otherwise. Fix: the forbidden filter is now `applyForbidden()`, also applied locally on failure; affected scenes show as uncovered and status says the replan failed. Regression: `a failed replan after Reject...` in index/tests/director-audit.mjs (failed before the fix, passes after).
2. **Project import file input not reset on early validation failure**: re-choosing the same corrected file would not fire `change`. Input is now cleared at the start of `importProject`. (No automated test: needs a real file chooser.)

3. **In-flight project import overwrote newer user work** (index/director.js). `importProject` awaited the plan request, then replaced `S.edits`, frame overrides and the script textarea; staging or script typed meanwhile was lost silently. Fix: monotonically increasing `S.rev`, bumped by every staging/frame/script mutation (editor inputs, drag, keyboard, Apply/Undo, frame picker, frame-change notice, script input, demo load); the import compares `S.rev` and the script text before committing and, if changed, replaces nothing and says so. Regression tests in index/tests/director-audit.mjs: typed-while-loading is preserved (fails without the fix), untouched import still commits exact-frame staging. Harness note: the vm injects host Object/Array/JSON, so the test removes them to get same-realm plain objects as in a browser.
4. **Windows symlink test portability** (agent/tests/test_aerial_metadata.py; no production change). Directory-alias tests now use a real symlink when allowed, else a Windows junction (`mklink /J`, no privilege needed); they also assert the alias really resolves elsewhere, so containment is still exercised. File-symlink tests skip with a stated reason when the privilege is missing (junctions cannot alias files) and are backed by new portable `test_rejects_aliased_cache_file` (resolve() seam making one cache file resolve elsewhere). Mutation check: removing the file or directory resolve checks in agent/aerial_metadata.py made those tests fail (4 and 6 failures); production code restored byte-for-byte. Privileges/settings untouched. On Linux/macOS or with symlink privilege all original symlink tests still run for real.

5. **Coordinator review round (all three hypotheses tested).**
   - *Reproduced:* `applyForbidden` assumed `plan.locations` is an array, but the real solver publishes `locations` as a count and the list as `property_ids`. With solver-shaped plans `(p.locations||[]).filter` threw a TypeError (also inside the replan-failure handler), so my earlier fix only worked against the audit's array-shaped mocks. Now `assignments`, `property_ids`, numeric `locations` and `uncovered_scene_ids` are rederived from what remains; `company_moves`/`mean_similarity` become null and `optimal_within_pool` false for changed plans; unrelated plans are returned untouched. `evaluated_subsets` is left as the backend's report of its run. Exports checked: no rejected id, locations=1, null similarity.
   - *Reproduced:* the import snapshot was taken after `await file.text()`, so staging typed during a slow read was overwritten, and a second file choice or Build could run concurrently. Now the operation claims `planBusy` and snapshots rev/script/constraints before the first await; overlapping imports/builds are refused with a status message.
   - *Reproduced:* max_locations/trucks/cars/require_available could change while evidence loaded and the committed result would not match the visible controls. The import now sends the snapshot and rejects the commit (nothing replaced) if any of those four differ at commit time; unchanged constraints still commit (tested for each control and the untouched case).
   - Four new tests fail on the previous commit and pass now. The Gemini draft was not used.

## Reviewed, no defect reproduced
Stale brainstorm/apply/undo guards, reel snapshot immutability and abort/cleanup, project normalize/restore (exact eligible frame only), evidence export (unknown vs estimated vs measured vocabulary), shoot-pack escaping.

## Observed but not changed (design/risk)
- Import silently clears current rejections (the replan uses `forbidden_property_ids: []`); status text does not say so.
- Replan resets manual frame overrides; staging is kept per frame and flagged via the frame-change notice.
- Project export keeps only drafts for the current frame plus `review_needed`; staging on frames no longer assigned is not exported.

## Checks (Windows, existing venv)
- `scripts/verify.py`: exit 0; see final numbers in the commit message / chat report (Python 596 passed, 5 skipped; smoke, SSE/refinement/approval PASS; 20/20 unlabeled mock attempts).
- `node --test index/tests/director-audit.mjs`: 29 pass / 0 fail
- director-project.test.cjs 29/0; director_reel.test.js 16/0; web/tests/viewfinder.test.cjs 4/0; web/tests/lib.test.mjs 12/0.

## Still unverified (genuine human/browser work)
Browser file-picker project import, microphone, live-provider trace for `plan_production_shoot`, real WebGL/WebM on the demo laptop, expanded private cache behaviour.

Head: see `git log -1` of ai/claude-release-audit (not pushed).

## Grok Worker4 leads (viewfinder/dressing provenance), tested offline
1. **Reproduced and fixed: AI-dressed grabs lost their provenance once saved.** `grab()` crops only the WebGL canvas, so the JPEG for a dressed grab had no mark in its pixels, and the Save link was always `typecast-shot-{lens}mm-{yaw}deg.jpg`. Now (web/viewfinder.js): when any dressing is visible (`wipe > -1`) the saved frame is stamped "AI-imagined set dressing · not the real room", and `shotFilename()` appends `-ai-dressed` (also for older stored shots flagged `ai`, and sanitises lens/yaw). Real-scan grabs are unchanged (no stamp). Heading text stays scan-relative. Tests (web/tests/viewfinder.test.cjs) failed before: stamped-pixels, real-grab-unstamped, filename. Limits: thumbnails already in a browser's localStorage from before this change keep their unstamped pixels (their list label and, now, filename say AI-dressed); stamp pixels were checked only through a recording canvas double, not rasterised.
2. **Saved thumbnails lacking AI labels:** same root cause as 1 for the image pixels; the list caption "· AI-dressed" already existed. Covered by the fix.
3. **Close-during-load race: not reproduced.** Existing guards (generation + dialog state + renderer identity) hold; added a regression where dressed faces are still decoding when the scan closes and a new scan opens: nothing from the old dressed set is uploaded, `dressed` stays null, toggle stays hidden.
4. **Director "Matterport" label on every frame: not a bug.** director.js only loads `/image/{shot_id}` (real indexed frames) and never `/api/dressed`; dressing exists only in the viewfinder.
Checks: scripts/verify.py exit 0 (596 passed, 5 skipped on this Windows box); director-audit 29, director-project 29, director_reel 16, viewfinder 8, lib 12, all 0 failures.
