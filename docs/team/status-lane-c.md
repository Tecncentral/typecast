# Lane C status

UTC: 2026-11-14T09:31:39.179287+00:00
Baseline commit: 5a449bcc9952d038ce7b0de12a1d401099c62574

## Works
- `git fetch origin && git merge origin/dev`: Already up to date (network sandbox required elevated fetch).
- `.venv/bin/python scripts/verify.py` baseline: 13 passed, 1 warning in 0.28s; PASS mock search -> validated picks -> same-thread refinement -> SSE result -> no-send approval.
- Step 0 verification: 13 passed in 0.16s; same smoke PASS.
- Added shared RunContext/Requirements, transitional engine interfaces, optional evidence/fit/runtime contract fields in Python/TypeScript and fixture updates; separated API tests.

## Broken / not yet implemented
- Real streaming, persistent threads, model parsing/rerank, deep engine and evaluation are next.
- Live lanes currently raise NotImplementedError; no real picks claimed.

## Next
- SA1-SA5 implementations, independent review, API/e2e checks, clean dependency install.

## Blocked on
- Private join and real interior/aerial adapters from A/B remain absent. Matterport credentials are now present and verified (see checks below).
- LangSmith key absent; trace_url stays null.
- Real hand labels absent; no retrieval metric claimed.

## Foundation integrated and access checks

- Foundation commit `d3ab730`; PR #1 merged into dev as `93224a9`.
- Installed/pinned openai 3.51.0, deepagents 0.7.38, langchain-openai 1.8.0.
- Clean `/tmp/typecast-clean-venv` installation from requirements.lock.txt succeeded.
- Clean environment `python scripts/verify.py`: 13 passed in 0.38s; smoke PASS. `pip check`: No broken requirements found.
- `scripts/check_access.py --network`: OpenAI model list confirms requested text/vision model; Matterport HTTP 200, zero GraphQL errors after user supplied secret. No credential values or licensed rows printed.
- User requested gpt-6.1-sol with high app reasoning; configured only in ignored .env. All coding subagents use gpt-6.1-sol xhigh.
- Live data join remains absent. Vexcel auth/verify returned HTTP 404; checking documented WMTS capabilities next.
- SA1, SA2 and SA3 running; SA4/SA5 queued for available slots.

Updated UTC: 2026-11-14T09:36:50.849577+00:00

- Vexcel key validated using documented WMTS GetCapabilities: HTTP 200, XML root Capabilities. Control request without credentials returned HTTP 401. Authentication-only endpoint returned 404 and is not used by the diagnostic.
- Browser SDK key is verified on the official public sample; real matched-building tour remains lane D integration work.

- Matterport SDK browser check at localhost:8766 succeeded using the official SDK bootstrap and public sample model: "PASS: SDK connected and model metadata is readable." This verifies SDK/domain access, not a matched sponsor-building tour. Temporary helper is outside the repository and reads the key only at runtime.

Dependency/access PR #2 merged into dev as eeb2000; both GitHub verify jobs passed (32s and 29s). Updated UTC: 2026-11-14T09:40:44.467675+00:00.

## First runtime/pipeline proof (working tree)

- Live OpenAI structured-output probe: ok=true, 2.899 s.
- Live parser police-station scene: parsed_with_model=true, Los Angeles, 1980s/year_max=1992, 3 trucks, 30 cars, night; 3.565 s.
- Local uvicorn at 127.0.0.1:8765 with models disabled/mock adapters: health 200 (all three adapters mock); POST scout 200 with 3 picks; GET stream first event 1.40 ms and result 4.32 ms (53 events); POST refine 200 same thread and two parking objections; POST approve 200 draft_saved, sent=false; unknown refine thread 404. Every returned pick had all three evidence sources.
- SA2 focused tests: 19 passed in 0.05s. Current full verify while SA1 finishes: 30 passed, one old approval test needs updating for thread validation; not merged as complete.

## M1/M2 integrated verification

- `.venv/bin/python scripts/verify.py`: 59 passed in 0.51s; mock API smoke PASS.
- SA1 runtime/API tests: 22 passed in 0.21s. SA2 pipeline tests: 19 passed in 0.05s. SA3 fake provider/rerank tests: 11 passed in 0.31s.
- Live vision request on a synthetic test image: 1/1 scored, zero failures, 5.259 s. Second call: 1 cached, identical score, 0.0004 s.
- Live-mode error probe: all adapters report live; stream HTTP 200, agent error then terminal error, no result. Sanitized terminal text: "Scouting failed. Please try again." Actual current adapter prerequisite is `NotImplementedError: Owner 2: query the joined table here`. No mock fallback.
- Working directory still has no private join; no real property pick or retrieval accuracy claim. Mock frame paths supplied by the scaffold point at missing image files; viewer fixtures need local placeholders or lane D assets.
- Deep engine + evaluation work remain in progress; no deep success claimed yet.

## Integration review fixes
- Reviewing lane A PR #3 at db0daf6 in an isolated checkout merged with current dev and lane C exposed a fresh-checkout /cache RuntimeError (77 tests passed, one failed). Fixed cache serving to return 404 when no cache exists yet and to pick up later images.
- Fixed pipeline failed-fit filtering to use unrounded geometric depth, compatible with lane A's precision fix. Focused API/pipeline regressions: 27 passed in 0.28s.
- Independent review also found vision workers could overrun the configured deadline; SA3 is adding a wall-clock watchdog before PR #4 is merged.

## Evaluation and remaining deep validation
- Full verification including real-graph fake-model tests: 73 passed in 1.27s; smoke PASS; gated ASGI e2e first event 1.43 ms, result 5.45 ms, refine 3.75 ms, approval 1.29 ms. Search counts remain 1 each after refine.
- Eval: 20/20 authored scenes completed on mocks; 0 labeled/20 skipped; recall@10 N/A, p50 2.80 ms and p95 3.13 ms. These are local fixture timings, not retrieval results.
- Added 15 explicitly labelled synthetic mock image placeholders to repair scaffold image URLs; all return HTTP 200. No real building imagery represented.
- First real deepagents/gpt-6.1-sol-high attempt reached market and interior delegates, then failed at 56.26 s; runtime transparently returned fixed-engine picks at 56.267 s. No deep success or trace claimed. Tightening summaries and capturing sanitized failure details before retry.

## M3 live model proof — 2026-11-14T09:59:11.452829+00:00

- Second real gpt-6.1-sol/high deepagents run completed successfully over mock data in **87.828 s**, returning engine=deep, source_mode=mock, 3 picks, trace_url=null.
- Observed delegate completion: market 15.57 s, interior 40.34 s, logistics 57.78 s, skeptic 82.84 s; final 87.83 s. Actual stream updates, not invented progress.
- HTTP POST /approve on this run resumed the real human-approval checkpoint and returned draft_saved, sent=false. No additional model generation was required for approval.
- Latency is close to the 90 s deep cutoff. Default remains fixed; failures/timeouts explicitly return fixed with a fallback event.
- Installed API confirmed from package source: create_deep_agent with declarative subagents, StateBackend virtual files, explicit TodoListMiddleware, InMemorySaver, stream_mode=updates/subgraphs=True, interrupt_on and Command(resume) for approval.
- Deep tests: 10 passed in 1.04 s, including real graph/tool execution with deterministic chat, HTTP approval, rejection, source errors, invalid output, and cancellation.
- Final lane C gate so far: **78 passed in 1.69 s**, smoke PASS, e2e PASS (first1.85 ms/result5.98 ms; zero new search on refine), mock evaluation20/20 with no labels and recall N/A.

## Current milestone state
- M1 complete: shared interfaces, null safety, real streaming, shared runtime.
- M2 complete: model parse/vision with announced fallback; explicit zero refine; validated threads; local drafts only.
- M3 complete on mocks with a real provider run and actual four delegates. LangSmith is optional and unconfigured, so no trace URL is claimed.
- M4 blocked: lane A/B live adapters and private cache/join.parquet are absent. Credential access is verified; a joined real pick is not.
- M5 harness complete:20 scenes, split15/5, recall@10 and p50/p95, proven cache-only refine. Actual labelled retrieval result awaits private real corpus and human labels.
- No remaining lane C implementation task is known; finish current PR integration and rerun combined lane A regression gate.
