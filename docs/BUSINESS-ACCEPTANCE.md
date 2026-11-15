# Producer workflow acceptance (reliability pass)

Base: `c549e66` (Typecast PR #43, branch `ai/claude-business-hardening`). Scope: `index/director-planning.js`, `producer-brief.js`, `production-costs.js`, the plan snapshot in `director.js`, and their tests. Everything below was reproduced against the base before it was changed. Historical hashes in older documents are not current behavior.

## What a producer can and cannot rely on

- The memo is a **projection** for deciding what to scout next. It is not a filming approval, booking, permission or verified saving, and exports say so.
- `$957.58/day` is a sourced covered commercial reference (Local 399 / AICP, effective 2026-06-28), not a universal rate. **Days avoided are hypothetical** until a producer supplies evidence; nothing here measures them.
- Unknown commitments stay unknown: cash impact shows "unconfirmed" and the memo lists what is unresolved. Guaranteed salary releases *capacity* but no labor *cash*.
- A memo exists only for a current, complete, non-community plan, and its source mode (mock/live) is printed in the screen card, JSON and HTML.

## Issues found and fixed

| # | Defect (reproduced on base) | Effect for a producer | Fix |
|---|---|---|---|
| 1 | Rejected-property list was not part of plan staleness (`director.js` snapshot). During the replan after a rejection, and after "Clear rejections", the old plan still read as current. | A memo could be exported for a shortlist built under different exclusions, omitting the rejections it depended on. | `PLANNING_FORBIDDEN` records the list each plan response was built with (build, save-the-scene and project-import paths); snapshot is stale while it differs. |
| 2 | Late import races: only text/number inputs bumped the edit revision, so ticking "paid crew travel" or switching billing while a file was being read was overwritten. Two overlapping imports applied in *completion* order, so the earlier-selected file could win. | Newer producer input silently replaced; wrong project's numbers in the budget. | Edit revision now covers the checkbox and billing select; an import sequence token makes the most recently chosen file win and discards superseded reads silently. |
| 3 | Import kept the previous project's value for every field the file lacked (`if (a[k]!=null)`). | Budget/project confusion: crew count, visits or rate source from another project mixed into an imported case. | Absent fields become blank (unknown). The estimate then refuses and asks for the value; no invented default. |
| 4 | Blank day rate in **hourly** mode became `NaN`, which the memo validator rejects with a cryptic message. | A legitimate case could not be exported at all. | Blank is `null`. Day-rate mode still refuses a blank rate. |
| 5 | Currency rounded to whole dollars: the sourced rate displayed as `$958/day`, `$0.70/mile` as `$1/mi`. | The memo's own arithmetic line did not reproduce its inputs. | Up to cents, whole amounts unchanged. |
| 6 | More visits after Typecast than before displayed "-2 fewer days", "-2 person-days released", "Labor capacity value: -$1,915". | A cost increase read as a saving with a sign error. | Worded as "N more … (added cost)" / "Additional labor required"; memo says "Scenario adds labor … This is not a saving." |
| 7 | Opt-in said "stored in this browser" and Clear said "cleared" even when the browser refused the write/delete. | Producer believes data is saved or removed when it is not (shared machines). | Refused write withdraws the opt-in with an honest message; removal is verified by reading the key back; a refused delete says so. Oversize saved case now reports that it was ignored. |
| 8 | Free-text decision ("Why shortlist this plan?") stayed attached after the plan changed or after a file import. | A memo could present an earlier plan's reasoning as the reason for a different shortlist. | Text is bound to the plan fingerprint it was typed against; otherwise the memo's open checks say it was written for an earlier plan, or restored/typed before the plan existed. |
| 9 | Credential screen missed Google API keys, GitHub tokens, AWS key ids, bearer tokens, URL credentials, private-key headers and `password=`/`secret=` strings in free-text fields. | A producer pasting a quote or note with a secret could email it in the memo. | Added those patterns. `password policy discussed` and similar prose still export. |

Checked and found **not** to be bugs (no change made): plan-limit changes (locations/trucks/cars/availability) and commute origin/limit changes already make a plan stale via the planner's constraint signature; selector/mode switches that stash plans stash the response and rejections together; exports re-render from the live snapshot at click time rather than reusing a cached case; HTML export escapes all producer text; "committed" costs never become cash; the cancellable-unit cap cannot hide added cost and is rejected if it exceeds modeled units.

## Verification

All run from this worktree (Windows, Node v24.21.0, shared `../typecast/.venv`).

| Command | Result |
|---|---|
| `node --test index/tests/director-planning.test.cjs` | 22/22. On the base code the same file failed **12 of 22** (the cases behind issues 2–9). |
| `node --test index/tests/director-audit.mjs` | 112 pass / 1 skip (new rejected-list staleness test failed on base: "false !== true" while replan in flight). |
| All Node suites (`index/tests/*` plus `web/tests/*`, `bridge/core.test.mjs`) | 281 pass, 0 fail, 1 skip. Previous baseline 258 pass / 1 skip + 23 added here. |
| `../typecast/.venv/Scripts/python.exe -m pytest -q` | 693 passed, 7 skipped (unchanged; no Python edited). |
| `python index/tests/browser_producer_check.py` (clean Chromium, local static server) | 13/13 checks; 0 external requests attempted. |

The Node tests drive the **real** `director-planning.js`, `production-costs.js`, `producer-brief.js` and `director.js` in a fake DOM (`index/tests/planning-harness.cjs`); late file reads are modeled with deferred promises. The browser check exercises the same flow in Chromium: mock plan label, `$957.58/day`, blank-rate export, actual downloaded JSON, reject → in-flight replan → clear-rejections staleness, literal opt-in/clear against real `localStorage`, and an import missing a field.

## Mock / synthetic / not tested

- **Synthetic:** the browser check answers `/api/production/plan` itself with a fabricated *mock-mode* plan (placeholder ids `P_A`, `P_B`) and a 1×1 PNG for images. Nothing in it is real inventory, a real room or evidence.
- **Not tested:** live mode, real Matterport/CoStar/Vexcel data, OSRM routing (commute minutes appear only as hand-built fixtures in Node), image generation, map tiles (blocked), any provider or paid call, printing the HTML memo, mobile layout.
- **Not tested in a real browser:** the interleaving of a slow *real* file read with edits. The race is exercised with deferred promises in the fake DOM only.
- The browser script was not re-run against the base commit; the base failures reported above come from the Node tests.

## Remaining limitations

- The plan fingerprint is a 32-bit non-cryptographic hash of the selected assignments, routes and mode. It identifies a plan within a session; it is not tamper evidence.
- Only the decision text is bound to a plan. Reviewer name and the pilot record are carried as entered (the pilot record is outcome data and is labeled producer-reported).
- The memo "review date" is the export time, not a recorded review time.
- Any new plan response (including Save-the-scene or undo to an earlier response) releases the post-import rebuild gate; it does not prove the producer re-read the imported assumptions.
- An opted-in browser copy also stores whatever was imported from a file. Clear removes it; separate projects still need separate JSON files.
- "Committed" labor and vehicle commitments are never counted as cash, including when a scenario *adds* work beyond what is guaranteed; the memo lists capacity instead. A producer with real overage terms must model that outside this tool.
- Hours per scouting day is not entered in the UI, so day-rate scenarios report person-days only.
- Commute figures use one starting point and no live traffic and cannot represent different employees' homes; crew travel uses the slowest selected location.
