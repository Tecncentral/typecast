# HANDOFF
1. Goal: harsh-judge release QA of Director/reel/import/viewfinder/AI-dressing; fix reproducible bugs, mock-only, no push/merge.
2. State: fixed rejected-location-after-failed-replan bug in index/director.js + regression in index/tests/director-audit.mjs; import input reset. Details/checks: index/CLAUDE-RELEASE-REVIEW.md.
3. Decisions: filter extracted to applyForbidden(); no schema/dependency changes.
4. Risks: 6 Windows symlink test failures (env); browser import, mic, live trace unverified.
5. Next: integration captain reviews diff, runs verify on Linux/demo laptop, browser-test import and Reject with backend down; push when authorized.
6. Resume: `node --test index/tests/director-audit.mjs`; python scripts/verify.py with the typecast .venv.
