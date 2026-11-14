# HANDOFF
1. Goal: harsh-judge release QA of Director/reel/import/viewfinder/AI-dressing; fix reproducible bugs, mock-only, no push/merge.
2. State (update 3: solver-shaped Reject cleanup, import snapshot before first await, constraint guard; see review item 5). (update 2): symlink-test portability fixed (junction/skip+portable seam), import edit-overwrite race fixed with S.rev guard + 2 tests; verify.py green 596/5 skipped. Earlier: fixed rejected-location-after-failed-replan bug in index/director.js + regression in index/tests/director-audit.mjs; import input reset. Details/checks: index/CLAUDE-RELEASE-REVIEW.md.
3. Decisions: filter extracted to applyForbidden(); no schema/dependency changes.
4. Risks: browser import, mic, live trace unverified.
5. Next: integration captain reviews diff, runs verify on Linux/demo laptop, browser-test import and Reject with backend down; push when authorized.
6. Resume: `node --test index/tests/director-audit.mjs`; python scripts/verify.py with the typecast .venv.

Update 4: docs-only index/GEMINI-DEMO-HANDOFF.md (Gemini draft + Claude cross-check; no code changed).

Update 5: viewfinder provenance fix (AI-dressed grabs stamped + filename marker); close race and Director label leads not reproduced. See review doc.
