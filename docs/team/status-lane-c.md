# Lane C status

Updated UTC: 2026-11-14T19:07:00+00:00
Verified application: `cf716c1` (PR [#19](https://github.com/Tecncentral/typecast/pull/19)).
Current milestone: human evaluation complete, **15/15 live held-out requests scored; mean pooled pipeline recall@10 0.2706**. See [the full report](eval.md) and the final entry below. This integration work includes the expanded index, OSM/Vexcel caches, private team handoff and live demo/performance checks; the viewer remains owned by the other chat.

The sections below retain the earlier milestone history. The initial Job 2 implementation was `e672e70` (PR [#7](https://github.com/Tecncentral/typecast/pull/7)), when this chat owned Job 2 and other chats owned Jobs 1 and 3.

## Outcome

Job 2 is implemented and verified. The deep engine's median decreased from **83.807 s** to **36.967 s**, now including real LangSmith trace upload and verified link retrieval. All three final runs completed with engine=deep, three source-backed fixture picks, and a verified trace URL. No fallback in the final series. The under-45-second target is met with tracing enabled.

The model remains `gpt-6.1-sol`; director effort is medium and the four scout/skeptic instances use low. All coding subagents used `gpt-6.1-sol` xhigh. Default engine remains fixed; set `TYPECAST_ENGINE=deep` for the agent demo.

## Measurements

Both versions use the police-station scene and mock source data, with model parsing and vision reranking disabled to isolate the deep engine. Baseline `a89cbad` used high effort throughout and no tracing. Final `e672e70` uses medium/low effort and **tracing enabled**, including completed-run verification before returning each link.

| Trial | Before: high, untraced | Final: medium/low, traced |
| --- | ---: | ---: |
| 1 | 84.368 s | 38.637 s |
| 2 | 83.807 s | 36.053 s |
| 3 | 77.242 s | 36.967 s |
| Median, all attempts | 83.807 s | 36.967 s |
| Deep completions | 2/3 | 3/3 |
| Verified trace links | disabled | 3/3 |

Baseline trial 3 failed during skeptic work and visibly fell back to fixed. Its total is included, not discarded. Successful baseline deep median was 84.087 s. The initial timing collector mixed fallback-stage events into that trial; its deep stage timestamps were restored at millisecond precision from captured terminal events, and the collector now filters engine=deep.

Completed-delegate medians (sample counts in parentheses):

| Delegate | Before | Final |
| --- | ---: | ---: |
| market_scout | 10.712 s (3) | 5.819 s (3) |
| interior_scout | 18.179 s (3) | 6.293 s (3) |
| logistics_scout | 10.986 s (3) | 5.185 s (3) |
| skeptic | 14.012 s (2) | 3.018 s (3) |

Final trial 3: interior 13.570–21.271 s; logistics 13.570–18.755 s. Both started before either finished. Every final run emitted 69 progress events; first events arrived within 1.2 ms through the runtime callback.

Commands:

```bash
.venv/bin/python scripts/benchmark_deep.py --checkout /tmp/typecast-job2-baseline --runs 3 --director-effort high --scout-effort high --output cache/benchmarks/deep-before.json
.venv/bin/python scripts/benchmark_deep.py --runs 3 --director-effort medium --scout-effort low --tracing --output cache/benchmarks/deep-final-traced.json
```

Baseline exit 1 correctly reports its fallback; final exit 0. Reports retain code revision/source hash, individual runs, delegate event timestamps and counts under ignored cache/. These are fixture latency results, not real-data retrieval accuracy.

## What changed and how it was proved

- Interior and logistics launch in the same director turn after market retrieval. Logistics uses the complete market pool, independent of interior results. The shortlist combines the same properties with cached logistics and never refetches that cache. Actual graph tests with sleeping source tools prove concurrent execution and one source call per property.
- Independent model instances apply medium director / low scout effort. Tests inspect all five instances and their configured reasoning. `.env.example` exposes both effort settings and `LANGSMITH_PROJECT=typecast`.
- Tool summaries are bounded to 2048 bytes; full properties/logistics stay in session state and private sources.json, with full shots/picks in the existing thread files. Tests cover 50-record pools and source identity.
- Initial planning shares the market turn; interior rerank and representative geometry check share one turn; final output follows skeptic review immediately. After validating all ids/reviews and staging real approval checkpoints, the application updates the actual todo checkpoint, reads it back, verifies no pending work, then emits that saved state. Tests prove no extra model call and no premature completion event for invalid output.
- Fixed and deep requests produce a single LangSmith root in project typecast; deep worker context propagates to actual nested model/tool spans. URLs come from the client only after a matching completed root is fetched. Inputs, outputs, attachments and arbitrary metadata are removed; aggregate timings/counts remain.
- Live diagnostics measured about 5.5 s of ingestion visibility delay and read latency exceeding 700 ms. Verification uses 1 s connect / 2 s read limits, paced polling and an 8 s total cap; setup is bounded at 250 ms. Tests reproduce the observed delay with a fake clock. Missing keys, explicit opt-out, failures or timeout produce null links; failures emit a sanitized trace-status event without breaking scouting.
- GET /config returns exactly mode, engine, tracing and matterport_sdk_key. Modes reflect actual adapters, including mixed; invalid engine returns sanitized 503. The only key exposed is the browser SDK key, with private-credential aliases suppressed. [Matterport's official guide](https://developers.matterport.com/embed-sdk/) documents browser applicationKey usage and allowed domains. Tests check every environment *_KEY/*_SECRET value for leakage.

## Live trace and HTTP evidence

- Actual fixed HTTP SSE run: first event 2.86 ms; result 4.735 s; three fixture picks and verified root. [Fixed trace](https://smith.langchain.com/o/2be59dd2-f6bb-48a8-86e6-04feb171e631/projects/p/4a463e7f-b7cb-40ee-8c38-1bf1474943f6/r/01a1d9a5-dab0-7324-9157-7e0769dda593?poll=true).
- Actual deep HTTP SSE check before the final turn reduction: first event 2.70 ms; result 50.781 s; three picks; 255 nested spans independently fetched. The final benchmark above supersedes that latency.
- Final implementation: independently fetched all three completed trace roots and nested spans through the LangSmith client, confirmed ids/URLs/hierarchy, actual LLM and tool spans, and empty inputs/outputs. Nested-span counts: 234, 234, 201. [Final deep trace](https://smith.langchain.com/o/2be59dd2-f6bb-48a8-86e6-04feb171e631/projects/p/4a463e7f-b7cb-40ee-8c38-1bf1474943f6/r/01a1d9b0-0cbf-73b2-874c-651c484a7939?poll=true).
- `scripts/check_tracing.py --expected-engine fixed|deep` reproduces the HTTP/config/SSE check and independent trace read-back against the appropriate server on port 8000. It asserts no private credential appears in /config.

## Verification and API authority

```text
.venv/bin/python scripts/verify.py
133 passed in 2.91s
smoke PASS
SSE/refine/approval e2e PASS: first 1.42 ms, result 4.79 ms, refine 3.48 ms, approval 1.00 ms
search calls after refine unchanged: search_shots=1, search_costar=1
mock evaluation: 20/20 completed; 0 labelled; recall@10 N/A
pip check: No broken requirements found.
```

GitHub verify passed for e672e70. Credential scan found zero configured credential values in tracked files; no .env or cache file is tracked. No new dependency was required.

Installed source verified: deepagents middleware/subagents.py:155/652/673 supports per-subagent model; LangChain agents/factory.py:2032 dispatches pending tool calls with Send; LangGraph pregel/_runner.py:265–267 and _executor.py:71–79 submit concurrent tasks with copied context. Actual source timing tests corroborate concurrency. LangGraph pregel/main.py:1479/2636 provides get_state/update_state; infer the completed node when updating final todos, because explicitly using model would schedule after-model hooks. LangSmith 0.14.17 client.py:3978/4068/4643 supplies flush/read_run/get_run_url; all timings and URLs above came from execution.

## Handoff

No Job 2 implementation or verification remains. PR #7 contains the reviewed work and current evidence. Jobs 1 and 3 own real-data and viewer completion; this report makes no claim about their progress or real-property retrieval quality. No deployment, main merge, inquiry delivery or external submission occurred.

## Lane B integration support — 2026-11-14

- User reassigned this chat to Lane B data; viewer remains in another chat. Lane C supports shared contracts/dependency integration.
- Reviewed incoming PR8/6/10 together. Repaired Matterport token alias, cached model/property remapping, shared-cache image URLs, and bridge uncertainty/local-draft approval state. Combined gate: 193 Python tests plus 6 bridge tests passed. Actual index bootstrap downloaded and encoded 608 views / 19 properties; no private data committed.
- Added availability status/reason, CoStar parking flags, nullable logistics capacity and per-field evidence statuses. Pipeline preserves unknown availability, parking and noise in reasons/evidence/skeptic notes; 135 current lane-C tests and smoke/E2E pass.
- Baseline adds DuckDB 2.0.0, PyArrow 26.0.1 and Shapely 2.2.0. Optional full CLIP environment is pinned separately in requirements-index.lock.txt. Shared environment pip check passes; clean baseline lock installation and final real-data E2E are in progress.
- Follow-up: the live market pool is limited to genuinely indexed PropertyIds before logistics fan-out; Lane B prioritizes these IDs before its 500-row search limit. Deep tool summaries now carry explicit availability/parking/noise uncertainty. Verified 196 tests plus smoke/E2E on Python 3.13; prior clean Python 3.14 baseline gate passed 195 before this added market-pool regression test.

## Integration captain: OSM repair — 2026-11-14 16:00 UTC

Started from dev `9bcc444`; lane-c already contains that exact revision. The current private join and existing 608 views are retained. Viewer and exterior checkouts remain owned by other chats. Subagents use GPT-6.1 Sol with xhigh reasoning.

The documented North America Overpass instance `https://ovp.dresel.systems/api-na/interpreter` returned HTTP 200 in 2.263 s after Private.coffee timed out. Requests are sequential, identify Typecast, never rotate automatically, and send no Vexcel credentials to OSM.

`TYPECAST_USE_MOCKS=0 .venv/bin/python -m data.vexcel_precompute` exited 0: 19/19 OSM sources, 3,688 elements, zero provider failures or partial results. Parking estimates rose 9 to 14 through five real mapped parking polygons. Noise screening completed for all 19: six flagged properties (three freeway, one rail, two airport/runway). No flag does not establish quiet. All 19 walking distances remain unknown because no qualifying connected entrance route exists. All 19 annotated aerials validate; hashes confirm all 95 successful Vexcel source files unchanged. Private report: `cache/vexcel/osm-repair-report.json`.

Reviewed client, docs and regression cases. `scripts/verify.py`: 248 tests plus smoke, SSE/refine/local-draft and mock evaluation gates passed. Independent root rerun: eight OSM tests passed. Vexcel HTTP 403 now reports “outside Vexcel coverage”; missing evidence remains unknown.

Next: 307 mapped available commercial properties plus about 20 available multifamily properties, retaining existing shots. Sixteen additional available commercial properties lack supplied model mappings. Then precompute, inspect frames, validate both engines and obtain human held-out labels.

### Active listing categories — 2026-11-14 16:10 UTC

OSM PR13 is merged into dev (`d6d6e2d`) after live verification and passing GitHub CI. Added optional Property.listing_types in Python and TypeScript, with the contract change announced before adapter use. Categories decode Active commercial listing types as lease, sale or auction; multiple categories coexist and missing categories stay empty. Availability rules are unchanged. Older joins remain readable.

Rebuilt from the same supplied kit with a private pre-change backup: 13,096 pairs / 3,288 properties, **zero row differences across every existing column**. Category counts: empty 2,748; auction 7; auction+lease 8; auction+lease+sale 1; lease 424; lease+sale 35; sale 65. This additive change took under 20 minutes. Data tests: 29 passed. Combined current worktree gate: 254 tests plus smoke/SSE/refine/local-draft/mock-evaluation passed.

### Owner 2 private cache handoff — 2026-11-14T16:22:06+00:00

Verified all 10 requested IDs have complete caches. Packaged 90 source/derived files under cache/vexcel paths into ignored `cache/handoffs/typecast-vexcel-owner2-20261114.zip` (42,904,234 bytes), plus private manifest. ZIP integrity passed; no configured credential values appear in its source files. All 10 have OSM noise screening; seven have parking estimates. Current availability: one available, two not_available, seven unknown. These older human-selected interiors are not the new available-property demo set. The user has the archive and a reply to send privately; no external message was sent by this agent.

Owner 2 plans test/docs changes in test_data.py and their root STATUS.md section; those files remain theirs. Applied the reported Windows CSV fixture fix (`newline=""` for csv.writer). Focused data/evaluation tests: 45 passed. OSM PR13 and listing-category PR14 are merged into dev.

### Expanded evidence and frozen human evaluation — 2026-11-14 16:48 UTC

Vexcel/OSM precompute now covers all 343 frozen indexed properties: 343 aerials, semantic-search and segmentation responses, 343 successful OSM sources, 338 parcel attributes. Parking estimates: 224 (147 SAM3, 77 OSM); 129 meet 3 trucks + 30 cars. Noise screening flags 128 properties: 70 freeway, 54 rail and 28 airport/runway flags, with overlap. One reproducible mapped walking route is estimated; 342 distances remain unknown. Five parcel-detail requests returned HTTP 404 and remain explicit unknowns. All aerials decode and geometry audits pass.

The main sequential batch took 20m33s and reused the original 19 caches. One transient OSM connection failure triggered the outage barrier; one retry pass on the same endpoint recovered all 38 missing sources after cooldown. Hash checks prove all 1,710 successful Vexcel source files remained unchanged during that retry, including all 95 original sources. Private evidence: `cache/vexcel/expanded-final-report.json` and `coverage.json`. There are 327 available indexed candidates; 212 have parking estimates. Their private candidate file uses the actual indexed model ids.

User explicitly authorized private Discord delivery. The 43 MB handoff exceeded Discord's 20 MB file limit, so it was split into three independent ZIPs of 17,161,222 / 16,943,322 / 8,800,013 bytes. Their combined contents were verified byte-for-byte against all 90 original files. Sent all three to the verified four-member HackPrinceton '26 group DM through the signed-in web app; each attachment now has a download link. No server upload or Git data commit. Private evidence: `cache/handoffs/discord-upload-parts.json` and `discord-sent.jpg`.

The labeling bridge freezes exact authored scene text, split, blinded top-40 pools and SHA-256 fingerprints of the immutable index. It accepts complete human/live reviews only, rejecting stale text, pools, timestamps, AI/mock labels and index changes. Exported scenes/labels stay in ignored cache. The live evaluator pins the reviewed generation, checks it before and after execution, and reports pooled pipeline recall with a city-eligibility diagnostic. This does not claim exhaustive catalog or global CLIP recall. README documents the reproducible freeze/review/export/live sequence.

The user agreed to label the 15 test scenes at `http://localhost:8765/evaluate`; the lab remains pinned to the frozen 10,568-view generation. No human reviews are saved yet, so expanded-index recall@10 remains pending. Previous 608-view labels cannot establish this index's accuracy. No test judgments have been invented or used for tuning.

Private `cache/demo-set.json` contains nine inspected, available properties with estimated parking (six Los Angeles, three Houston) and five authored scenes. Initial fixed-engine scouting times: 27.135, 22.825, 22.124, 24.793 and 21.445 seconds. All five used real model parsing and 20 fresh vision scores with zero vision failures, three live picks and all three evidence sources. Each five-truck refinement reused its exact candidate pool with no new search, changed allocation/ranking, and saved unsent local drafts. The same deep-engine baseline is running before speed changes; final matched timings and browser verification follow.

### Available interior coverage and frozen index — 2026-11-14 16:43 UTC

Base dev: `20cb03a`. This milestone adds the bounded private bulk runner and its
incremental import/build support. `index.bulk` uses at most eight workers and one
provider request per worker, selects one explicit supplied catalog model per
property, downloads and encodes shared source views once, and retains all prior
shots and source evidence. Per-model checkpoints support partial-face retries,
source/index interruption recovery, larger scan requests and explicit
`--retry-failed`; request timeouts respect the remaining fetch budget. A partial
run reports its usable coverage and exits nonzero. No-change resumes retain the
published generation. Explicit bootstrap model lists no longer have a 20-model
cap, unchanged embeddings are reused, and failed room refreshes preserve prior
evidence. The store can read a directly pinned immutable generation.

Frozen private generation: `043653ce80184bf4839cf1750c312b42` — **10,568 views /
343 distinct properties / 329 distinct models**. It covers all 307 mapped
available Office, Industrial, Flex and GeneralRetail properties in the current
join, plus 20 available Multifamily properties (10 Los Angeles, 10 Houston),
while retaining all 19 previously indexed properties. Three selected properties
were already indexed. Available commercial coverage is Los Angeles: Office 75,
Industrial 8, Flex 3, GeneralRetail 15; Houston: Office 127, Industrial 50, Flex 9,
GeneralRetail 20. Another 16 available commercial properties have no supplied
model mapping and remain explicitly uncovered. Seven attempted apartment models
were inaccessible and replaced with available selections. Six catalog/property
disagreements remain flagged privately; the supplied exact CSV pair mapping is
retained without address or coordinate inference.

Exactly 302 selected properties have eight scans; 25 have one to seven catalogued
scans. Completed captures have zero failed faces and zero failed room requests.
Every indexed view and source image exists. The original 608 Shot records,
embedding floats, source records and provenance entries compare exactly equal
after expansion. Actual source imagery for all 20 selected apartment properties
was inspected by AI, with representative room/living/amenity images and generic
visual tags saved privately. This is not human-held-out relevance evaluation.

Measured wall time was **849.2 seconds / 14.15 minutes**, from first bulk command
start at `2026-11-14T16:04:35.087743Z` to final immutable-manifest publication at
`2026-11-14T16:18:44.239379Z`, including alternate-selection passes and preservation
checks between them. Evidence stays in ignored
`cache/matterport/bulk-review/preservation-final.json`, `timing-final.json`,
`selection-review.json` and `multifamily-20-representatives.jpg`; no source rows,
contacts, keys, images or embeddings enter Git.

Verification: 99 focused index tests passed. The combined current worktree
`scripts/verify.py` passed 282 tests in 3.98 seconds, API smoke, genuine-progress
SSE, cached same-thread refinement, local-draft/no-send approval, and 20/20
unlabelled mock scenes (recall remains N/A). Read-only final resume inspection
found zero provider tasks and zero views needing preparation. The frozen
generation has not been republished during integration. Other lanes' dirty
files remain outside this index milestone; exact-head GitHub CI is required
before merging its PR into dev. Next: Vexcel precompute and human labels on the
frozen generation, coordinated by the integration captain.

### Five-scene live baseline — 2026-11-14 16:55 UTC

PR16 (index) and PR17 (frozen evaluation) are merged into dev; current base is `67d86a2`. Both exact-head PR17 CI checks passed and an independent source review found no actionable evaluation issues. Combined verification: 282 tests plus all fixture integration gates.

All five scenes passed with both real engines, model parsing and vision enabled. Fixed times in scene order: 27.135, 22.825, 22.124, 24.793, 21.445 seconds (median 22.825). Deep: 59.981, 52.875, 61.165, 44.288, 50.762 seconds (median 52.875). All are below 90 seconds, with no fallback or vision failures. Fixed scored 20 fresh views per scene; deep cached counts were 0, 20, 0, 20, 20, so this is a mixed-cache baseline, not ten uniformly cold runs. Deep traces were independently fetched with 202–235 spans.

All ten requests returned three source-backed picks. Five-truck refinements retained candidate membership/cardinality, made zero new searches, and changed ranking/allocation; all original and refined approvals persisted unsent local drafts. Refinements took 20.328–28.896 seconds for fixed and 6.792–21.894 for deep. Unknown geometry remains unknown. The warehouse scene exposed actual freeway/rail proximity objections. Chromium decoded all 179 images across the 20 initial/refined responses, with zero failures. Private evidence: `cache/demo-checks/baseline/aggregate.json`, individual responses/summaries, screenshots and `browser-report.json`.

Added reproducible live demo and browser diagnostics; synthetic negative cases reject evidence loss, changed pools, over-90-second refinement, non-live responses, missing interiors/aerials and unsafe image paths. Reports cannot retain an earlier success after a failed browser rerun. No application dependency was added.

Removed only the requested unused `typecast-b` and `typecast-live` worktrees after checking clean tracked/untracked status, no unmerged commits, no process working directories in either checkout, and that cache/.env/.venv were symlinks to retained main-checkout files. Main private data remains present; viewer/exterior workspaces were untouched. Next: stable authored-scene vision caching, ten-view rerank budget, cache fill and matched warm measurements. Human test labels remain pending.

### Stable visual cache and ten-view budget — 2026-11-14 17:00 UTC

The shared pipeline now scores ten visual candidates while retaining the full retrieved tail for selection/refinement. Actual visual model payload and cache fingerprint both use the exact authored scene text, including follow-ups; inferred parse wording no longer causes misses. Cache version is 2. Provider/model identity, prompt, image identity, configured/enabled state and explicit upload permission checks remain intact. Physical and logistics requirements still operate independently in parsing/ranking.

Focused models/pipeline/deep tests: 59 passed. Combined gate: 290 tests plus smoke, genuine SSE progress, no-search refinement, local-draft approval and unlabelled mock evaluation; pip check passed. All five actual new-cache precompute scouts and refinements passed, scoring ten fresh views each. Scout times: 19.478, 13.164, 15.915, 16.576, 15.782 seconds. Chromium decoded 88 images across their ten initial/refined responses.

Warm measurements are ongoing. One first warm fixed run returned correct live picks and ten cached scores in 13.356 seconds of server time, but LangSmith verification did not finish within its existing bound, so the response correctly exposed a null trace link and the strict trace diagnostic failed. That attempt is retained; a targeted retry follows. This optional tracing failure does not justify a fabricated link or unbounded wait. Final warm timings and reliability counts will be appended after both engines finish.

### Measured director planning overhead — 2026-11-14 17:13 UTC

The first cache-only warm deep measurement still spent separate model turns updating todos. Its first scene emitted market-result→todo→parallel-scouts, interior-result→todo→shortlist, and shortlist→todo→skeptic; the earlier baseline combined these updates with source actions. Source tools and skeptic each ran once. This is actual trace/event evidence of optional planner overhead, not a duplicated source fetch.

The director now sees write_todos only until a real nonempty plan is persisted. Later calls retain every other tool; actual scout/tool events report progress. The application still completes and reads back the plan only after authoritative ids, every skeptic review and real approval interrupts are validated. Models and reasoning effort are unchanged. A real-graph test captures tool availability across all five director calls and checks parallel scouts, one skeptic result, and every actual HITL interrupt. Full gate: 291 tests plus all fixture integration checks.

Cache-only warm fixed results all passed after two targeted retries for missing optional trace links: 11.569, 9.651, 8.279, 8.240 and 10.432 seconds, each with ten cached scores. The original two null-link attempts remain recorded. Browser verification includes all 12 initial/refined responses from both attempts: 105 images, zero failures.

The intermediate deep batch produced all five real scouting responses; three full diagnostics passed, one lacked its bounded trace link, and one independent trace-tree read raised KeyError. Later read-back of that same existing trace succeeded with 224 redacted spans. The SDK assembles parent links using a dictionary lookup, consistent with temporary partial trace visibility. Diagnostics now retry only this hierarchy read error up to three times and persist measured scout summaries before trace verification; persistent errors still fail. Synthetic transient and persistent cases passed. No application trace timeout or truthfulness rule changed. A final five-scene deep measurement is now running against the reduced planning graph.

### Final live demo and speed acceptance — 2026-11-14 17:20 UTC

Final application changes: `c8c644f` (stable scene cache/ten-view budget) and `eab395d` (initial-plan-only director and bounded diagnostic read-back). Independent review found no material correctness issues; both exact-head CI workflows passed for eab395d. The local complete gate passed 291 tests and all fixture integration checks. Final actual deep execution used the same gpt-6.1-sol model and medium director / low delegate effort as baseline.

| Authored scene | Fixed before, s | Fixed after, s | Deep before, s | Deep after, s |
| --- | ---: | ---: | ---: | ---: |
| Glass office confrontation | 27.135 | 11.569 | 59.981 | 44.768 |
| Warehouse handoff | 22.825 | 9.651 | 52.875 | 39.929 |
| Empty shop rehearsal | 22.124 | 8.279 | 61.165 | 45.017 |
| Houston glass office meeting | 24.793 | 8.240 | 44.288 | 39.988 |
| Houston apartment conversation | 21.445 | 10.432 | 50.762 | 39.490 |
| **Median (5 scenes)** | **22.825** | **9.651** | **52.875** | **39.988** |

Baseline fixed used twenty fresh vision scores per scene; baseline deep cached counts were 0/20/0/20/20. Final runs used ten cached scores per scene. The first deep run in each server process includes cold CLIP initialization. These are five matched authored demo scenes, one fully verified final run each, with tracing enabled; they are not held-out accuracy measurements. Two fixed final scenes required targeted retries for missing trace links. The earlier 67.398-second single run used the old index and is not the matched comparison above.

Final deep passed all five scenes on its first attempt: three real available picks with known parking; all three evidence sources; genuine source-grounded skeptic; model parse and ten cached visual scores with zero failures; independently fetched redacted traces containing 193–204 spans. Five-truck refinement took 5.461–8.603 seconds, kept the exact candidate pool, performed no new search, changed ranking/allocation and saved unsent local drafts. Each actual run had only the initial and verified-complete todo events; all four scouts/skeptic delegates returned before completion.

Chromium loaded 88 images across the ten final deep initial/refined responses with zero failures. Across every retained phase, 530 image loads across 60 responses passed. All 32 scouting attempts returned the requested live engine without fallback and retained honest three-source evidence; maximum recorded server scouting time was 61.158 seconds (maximum recorded client time 61.165). Four strict diagnostic failures remain: two fixed null trace links, one intermediate deep null link, and one intermediate trace-tree KeyError that later read back successfully. No failed attempt was overwritten or silently removed.

Private reproduction/evidence: `cache/demo-set.json`, `cache/demo-checks/final-comparison.json`, all per-attempt summaries/responses/refinements, browser reports/screenshots, Vexcel caches and vision caches for every demo scene/follow-up. The application continues to need the model API for parsing/director execution; cached evidence cannot guarantee an entirely offline agent run.

Only held-out evaluation remains dependent on the human: zero of fifteen test reviews are saved. The frozen lab is running at http://localhost:8765/evaluate and is open in a separate in-app browser tab with the first test scene loaded; no labels were selected or saved by this agent. Export and live scoring are ready, and README/docs/team/eval.md explicitly retain N/A until actual human reviews exist.

### Completed human evaluation — 2026-11-14 19:07 UTC

The user supplied the completed lab export: all 20 reviews are human/live, including 15 test and five tuning scenes. The export exactly matches the saved lab records. Bridge validation passed exact scene text, split, all reviewed pool ids, review timestamps and unchanged frozen index fingerprints. An unmodified private copy and the 15-scene bridge export remain under ignored `cache/evaluation/`; no source identifiers or raw judgments enter Git. No additional human labeling is required for this benchmark.

Ran the existing evaluator on all 15 test scenes with the live fixed engine, `gpt-6.1-sol` parser/vision at medium effort, parsing/vision uploads/tracing enabled, and the frozen 10,568-view index. One attempt per scene, no warmup, no retries and no tuning from the test labels. Every request succeeded with actual model parsing; 150 fresh visual scores, zero cached scores, zero vision failures and zero fallback events. Thirteen responses included trace URLs; two null trace links remain recorded, with their successful requests included in the metrics.

Result: **mean pooled pipeline recall@10 0.2706 across 15 scored scenes**, median **14.539 s**, p95 **19.693 s**. The 600 reviewed scene/view pairs contain 352 positives; the returned first-ten sets recover 99. This is a macro average, not 99/352. All parsed cities defaulted to Los Angeles, leaving 212 eligible positives and 140 Houston positives in the denominator. The city-constrained mathematical ceiling is 0.3790; the global top-ten ceiling is 0.4814 because each scene has 8–37 positives. These diagnostic ceilings do not replace the measured score. The metric measures first-ten set membership, not the visual order inside that set or the final three property cards.

The unchanged harness was wrapped only to retain responses, candidate ids and rows privately. Evidence and code/input fingerprints: `cache/evaluation/runs/20261114T190213Z/`. Independent per-scene arithmetic matches the report. Full gate: **291 tests passed**, plus smoke, actual fixture streaming, same-pool refinement, unsent local-draft approval and mock-evaluation checks. README and `docs/team/eval.md` now publish the actual held-out result and limitations. The five tuning scenes were excluded; all human labels and the frozen index remain unchanged. The human-review blocker is resolved; this completes the requested integration/evaluation milestones.

### Job 5 controls and tune baseline — 2026-11-14 20:20 UTC

Implemented configurable rerank depth (`TYPECAST_RERANK_POOL=10/20/30/40`), physical concurrency (`TYPECAST_VISION_CONCURRENCY=5/10`) and image batches (`TYPECAST_VISION_BATCH_SIZE=1/5/10`). Defaults remain 10/5/1 pending tune selection. Larger pools can promote views beyond the original top ten while retaining the complete candidate pool for refinement. Multi-image responses require exactly one validated score/reason for every supplied image. Single-image v2 cache keys remain compatible; batch caches include the entire ordered image context. Actual provider call/image counters are emitted without payloads.

Added `ScoutResponse.notes` and a streamed `notice` when an unnamed-city scene uses the existing Los Angeles default. Named Houston and Los Angeles requests retain their city selection; example-image requests are not mislabeled. Refinement keeps the original scope note. Shared Python/TypeScript contracts and fixture guidance are updated; no city filtering changed.

The tune-only runner requires the exact five frozen tune exports, pins index fingerprints, isolates each attempt's vision cache/process, reserves a shared 1,000-image budget before calls, and keeps every response/top-ten/attempt privately. A provider 429 stops further calls, including deep-to-fixed retries. Installed OpenAI/Anthropic SDK checks cover both httpx and httpx2 transports. Outer cancellation stops queued scoring and late cache writes. Duplicate trials remain in latency/failure totals but cannot overweight quality or qualify a setting as five unique successful scenes.

Independent review found three issues (outer cancellation, SDK HTTP namespace coverage, duplicate weighting); all were fixed and regression-tested. Full repository gate: **344 tests passed**, plus smoke, streaming/refinement/local-draft and mock-evaluation checks. The architecture experiment responds to v1's limitations, but only tune labels select configurations; any repeat test result must remain labeled as informed by v1.

Actual baseline: five tune scenes on each engine, ten successful requests, 100 fresh image scores / 100 vision calls, zero vision failures, cache hits or engine fallback. Both engines have precision@10 lower bound **0.3600** and macro recall@10 **0.3441**. Fixed median/max **20.225/20.453 s**; deep median/max **53.597/58.911 s**. Each attempt uses a fresh process/vision cache, including lazy encoder initialization in request timing; source imagery/logistics are cached. These are five tune scenes, not the frozen v1 test sample. Early baseline SDK-level deep HTTP telemetry was absent before the namespace fix; its image reservations and vision-call events were present, and no rate limit occurred. No missing deep-text call totals are inferred.

Private protocol, ledger, input/code fingerprints and every attempt: `cache/experiments/rerank-v2/`. Canary comparisons are running under the same budget; only configurations completed on all five tune scenes and both engines with every deep request under 75 s can change the default. The original published v1 report remains byte-for-byte intact, with new material appended separately. Submission drafts are being prepared in parallel; viewer/exterior worktrees remain untouched.
