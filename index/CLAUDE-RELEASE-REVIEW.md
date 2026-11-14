# Claude release QA review (branch ai/claude-release-audit)

Base: origin/dev dbceec2 (PR22 Director + PR30 dressed sets). Mock/synthetic only; no network, .env, cache or provider access. No subagents were dispatched; this was a single-agent review.

## Verified defects and fixes
1. **Rejected location reappeared after a failed replan** (index/director.js). Reject added the property to `S.forbidden` then called `build(true)`; if `/api/production/plan` failed, the old response (still assigning the rejected property) stayed on screen and in JSON/shoot-pack/reel exports while the "Rejected:" list claimed otherwise. Fix: the forbidden filter is now `applyForbidden()`, also applied locally on failure; affected scenes show as uncovered and status says the replan failed. Regression: `a failed replan after Reject...` in index/tests/director-audit.mjs (failed before the fix, passes after).
2. **Project import file input not reset on early validation failure**: re-choosing the same corrected file would not fire `change`. Input is now cleared at the start of `importProject`. (No automated test: needs a real file chooser.)

3. **In-flight project import overwrote newer user work** (index/director.js). `importProject` awaited the plan request, then replaced `S.edits`, frame overrides and the script textarea; staging or script typed meanwhile was lost silently. Fix: monotonically increasing `S.rev`, bumped by every staging/frame/script mutation (editor inputs, drag, keyboard, Apply/Undo, frame picker, frame-change notice, script input, demo load); the import compares `S.rev` and the script text before committing and, if changed, replaces nothing and says so. Regression tests in index/tests/director-audit.mjs: typed-while-loading is preserved (fails without the fix), untouched import still commits exact-frame staging. Harness note: the vm injects host Object/Array/JSON, so the test removes them to get same-realm plain objects as in a browser.
4. **Windows symlink test portability** (agent/tests/test_aerial_metadata.py; no production change). Directory-alias tests now use a real symlink when allowed, else a Windows junction (`mklink /J`, no privilege needed); they also assert the alias really resolves elsewhere, so containment is still exercised. File-symlink tests skip with a stated reason when the privilege is missing (junctions cannot alias files) and are backed by new portable `test_rejects_aliased_cache_file` (resolve() seam making one cache file resolve elsewhere). Mutation check: removing the file or directory resolve checks in agent/aerial_metadata.py made those tests fail (4 and 6 failures); production code restored byte-for-byte. Privileges/settings untouched. On Linux/macOS or with symlink privilege all original symlink tests still run for real.

## Reviewed, no defect reproduced
Stale brainstorm/apply/undo guards, reel snapshot immutability and abort/cleanup, project normalize/restore (exact eligible frame only), evidence export (unknown vs estimated vs measured vocabulary), shoot-pack escaping.

## Observed but not changed (design/risk)
- Import silently clears current rejections (the replan uses `forbidden_property_ids: []`); status text does not say so.
- Replan resets manual frame overrides; staging is kept per frame and flagged via the frame-change notice.
- Project export keeps only drafts for the current frame plus `review_needed`; staging on frames no longer assigned is not exported.

## Checks (Windows, existing venv)
- `scripts/verify.py`: exit 0; 596 passed, 5 skipped (4 file-symlink skips above + 1 pre-existing), smoke/SSE/refinement/approval PASS, 20/20 unlabeled mock attempts. (Before the portability fix: 590 passed, 6 failed with WinError 1314.) Node suites run separately:
- `node --test index/tests/director-audit.mjs`: 25 pass / 0 fail
- director-project.test.cjs 29/0; director_reel.test.js 16/0; web/tests/viewfinder.test.cjs 4/0; web/tests/lib.test.mjs 12/0.

## Still unverified (genuine human/browser work)
Browser file-picker project import, microphone, live-provider trace for `plan_production_shoot`, real WebGL/WebM on the demo laptop, expanded private cache behaviour.

Head: see `git log -1` of ai/claude-release-audit (not pushed).
