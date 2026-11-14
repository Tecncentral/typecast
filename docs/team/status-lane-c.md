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
