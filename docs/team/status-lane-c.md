# Lane C status

Updated UTC: 2026-11-14T10:55:57.323407+00:00
Verified implementation: `e672e70` (PR [#7](https://github.com/Tecncentral/typecast/pull/7)).
Scope confirmed by the user: **Job 2 only** in `NEXT-JOBS-PROMPTS.md`; other chats own Jobs 1 and 3.

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
