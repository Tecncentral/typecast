# Claude release QA review (branch ai/claude-release-audit)

Base: origin/dev dbceec2 (PR22 Director + PR30 dressed sets). Mock/synthetic only; no network, .env, cache or provider access. No subagents were dispatched; this was a single-agent review.

## Verified defects and fixes
1. **Rejected location reappeared after a failed replan** (index/director.js). Reject added the property to `S.forbidden` then called `build(true)`; if `/api/production/plan` failed, the old response (still assigning the rejected property) stayed on screen and in JSON/shoot-pack/reel exports while the "Rejected:" list claimed otherwise. Fix: the forbidden filter is now `applyForbidden()`, also applied locally on failure; affected scenes show as uncovered and status says the replan failed. Regression: `a failed replan after Reject...` in index/tests/director-audit.mjs (failed before the fix, passes after).
2. **Project import file input not reset on early validation failure**: re-choosing the same corrected file would not fire `change`. Input is now cleared at the start of `importProject`. (No automated test: needs a real file chooser.)

## Reviewed, no defect reproduced
Stale brainstorm/apply/undo guards, reel snapshot immutability and abort/cleanup, project normalize/restore (exact eligible frame only), evidence export (unknown vs estimated vs measured vocabulary), shoot-pack escaping.

## Observed but not changed (design/risk)
- Import silently clears current rejections (the replan uses `forbidden_property_ids: []`); status text does not say so.
- Replan resets manual frame overrides; staging is kept per frame and flagged via the frame-change notice.
- Project export keeps only drafts for the current frame plus `review_needed`; staging on frames no longer assigned is not exported.
- Editing staging during an in-flight import is overwritten when the import commits.

## Checks (Windows, existing venv)
- `scripts/verify.py`: 590 passed, 1 skipped, 6 failed. All 6 are `agent/tests/test_aerial_metadata.py` symlink tests failing with WinError 1314 (no symlink privilege); environmental, not product. verify.py stops at pytest failure, so its Node steps were run directly:
- `node --test index/tests/director-audit.mjs`: 23 pass / 0 fail (was 22 pass / 1 fail with new test pre-fix)
- director-project.test.cjs 29/0; director_reel.test.js 16/0; web/tests/viewfinder.test.cjs 4/0; web/tests/lib.test.mjs 12/0.

## Still unverified (genuine human/browser work)
Browser file-picker project import, microphone, live-provider trace for `plan_production_shoot`, real WebGL/WebM on the demo laptop, expanded private cache behaviour.

Head: see `git log -1` of ai/claude-release-audit (not pushed).
