# External coding assignments

Current dispatch, November 15, 2026. Coordinator owns review, integration and publication. Tasks are based on actual PR #43 code at `c549e66`, not the older mock baseline. No dev/main merge, deployment, account access changes, paid provider calls, outside-team messages or submission are delegated.

| Workhorse | Actual dispatch and ownership | Acceptance |
| --- | --- | --- |
| Claude Code | Signed-in local CLI running in isolated `work/claude-business-hardening`, branch `ai/claude-business-hardening`, base `c549e66`. Owns browser budget/import/export/stale-plan reliability in `index/`, related regressions and an acceptance report. | Reproduce material bugs, fix without new integrations, meaningful Node/browser checks, local commit for coordinator inspection. No push/merge. |
| Grok Bot / Cursor W7 | [Actual worker](https://cursor.com/agents/bc-7c64a917-d5b1-5b42-ad56-e7a6c4b07eb1), separate branch from `c549e66`. Owns `index/commute.py`, `index/scene_customization.py` and related tests; essential `production.py` changes must be reported. | Offline provider-boundary reproductions and fixes, preserved source/uncertainty, tests and draft PR/patch. No frontend or economics edits. |
| Gemini browser | Existing signed-in [source review conversation](https://gemini.google.com/app/3c841599e7b2b4a1). Received actual `producer-brief.js` source and a bounded contract-review/patch task. | Return a guarded patch and meaningful regressions for material export/import proof bugs. This browser runtime cannot directly read the repo, execute tests or create real subagents; coordinator must inspect and run its output. No fabricated execution claims. |

Status at dispatch: Claude has begun writing `director-planning.test.cjs` and a fake-DOM harness; Grok W7 reports running; Gemini prompt was sent. These statements do not claim the tasks are complete or their code passes. Later acceptance and integration records supersede this snapshot.

## Business decisions already implemented

The preceding buyer/product/evidence debate produced the cash-versus-capacity calculator and producer decision case in `c549e66`. Local acceptance: Python 693 passed / 7 skipped plus smoke/SSE/refine/unsent-draft E2E; Node 258 passed / 1 skipped; 18 new fixture-only browser checks. Exact-head CI passed. All economics remain scenarios until a producer supplies actual records; no customer savings are measured.

## Video scope

User clarified: content, sources and shot list only for now. Do not generate more full videos. `docs/VIDEO-CLAIMS.md` and `docs/VIDEO-HANDOFF.md` preserve the material. Existing local review assets were made before that clarification and are set aside; they are not a current end-to-end real-data demonstration.

## Required evidence still unavailable here

Real private-cache/GPU/demo-laptop acceptance, actual image-provider generation, a live production-tool trace, original consultation evidence/affiliation and human Devpost selection/submission. Tests and source review cannot create those facts. Do not substitute synthetic QA for live data or assume event-only data licenses establish a commercial service.
