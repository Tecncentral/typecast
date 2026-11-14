# Lane C status

Updated UTC: 2026-11-14T10:03:32Z
Verified integrated commit: `d3ca338f12f29bb0ef318a9b88ea5960a344edb2` (dev and local lane-c).
Verified tree: `d6bd490d8580b7967a68a7160c9a1871989265cb`.

## Works

- M1 complete: shared interfaces, null-safe geometry, real streaming during execution, and one runtime for JSON/SSE requests.
- M2 complete: structured model parsing, bounded vision reranking with cache and explicit fallback events, cached refinement including explicit zero, thread validation, and local approval drafts with `sent=false`.
- M3 complete over mocks using the real provider: actual deepagents director, market, interior, logistics and skeptic delegates; real approval checkpoint; response identifies the engine that ran. No trace URL is invented.
- M5 implementation complete: 20 authored scenes (15 test / 5 tune), private human-label input, recall@10 and p50/p95 reporting, and a test proving refinement makes no new search. Actual retrieval quality remains unmeasured until real data and labels exist.
- Fifteen labelled synthetic mock frames make fixture image URLs work. Private thread/outbox data cannot be served through `/cache`.
- User-requested `gpt-6.1-sol` with high app reasoning is configured in ignored `.env`. All five coding subagents used `gpt-6.1-sol` with xhigh reasoning.

## Verification

Final combined lane A/C checkout used `/tmp/typecast-review-lane-a` and the clean environment `/tmp/typecast-clean-venv`. Its tree exactly matches the integrated dev commit above.

```text
/tmp/typecast-clean-venv/bin/python scripts/verify.py
97 passed in 2.28s
PASS mock search -> validated picks -> same-thread refinement -> SSE result -> no-send approval
e2e: first event 1.46 ms; result 5.91 ms; refine 3.66 ms; approval 1.13 ms
search counts after scout/refine: 1 each, unchanged by refine
mock evaluation: 20/20 completed; 0 labelled / 20 skipped; recall@10 N/A
mock evaluation latency: p50 2.79 ms; p95 3.24 ms

/tmp/typecast-clean-venv/bin/python -m pip check
No broken requirements found.
```

These evaluation timings describe local fixture execution, not real retrieval performance. The evaluation report explicitly says "mock run: not a result".

Actual uvicorn HTTP checks on the combined checkout, using the police-station scene with model calls disabled:

- `/health`: 200, all three adapters mock.
- `POST /scout` and `GET /scout/stream`: same three picks; first event 1.10 ms, result 4.73 ms. Every pick carried all three evidence sources.
- `POST /refine`: same thread, updated parking objections, no new search.
- `POST /approve`: `draft_saved`, `sent=false`; invalid rank 422 and unknown thread 404.
- All mock image URLs: 200. Private cache paths: 404.

Clean installation from `requirements.lock.txt` succeeded. Pinned direct integrations: openai 3.51.0, deepagents 0.7.38, langchain-openai 1.8.0. GitHub verification passed for PR #4 (35 s and 32 s). No tracked file contains any configured credential value; `.env` and private cache remain ignored.

## Provider checks and real model execution

- `python scripts/check_access.py --network`: OpenAI model-list access succeeded and includes the requested model; Matterport HTTP 200 with zero GraphQL errors; Vexcel WMTS GetCapabilities HTTP 200 with XML Capabilities (unauthenticated control 401). No keys or licensed records were printed.
- Matterport browser SDK connected to the official public sample and read model metadata. This verifies SDK/domain access, not a matched sponsor-building tour.
- Live structured-output probe: 2.899 s. Live police-station parsing: 3.565 s, model parsed Los Angeles / 1980s / 3 trucks / 30 cars / night correctly.
- Live vision request on a synthetic test image: one scored, zero failures, 5.259 s; identical cached result in 0.0004 s.
- Real deepagents run with `gpt-6.1-sol` / high reasoning completed in **87.828 s**, `engine=deep`, `source_mode=mock`, three picks, `trace_url=null`. Delegate completion: market 15.57 s, interior 40.34 s, logistics 57.78 s, skeptic 82.84 s. HTTP approval resumed its actual checkpoint and saved a local draft without another model generation.
- An earlier deep attempt failed after 56.26 s and explicitly fell back to fixed at 56.267 s. The successful run is close to the 90 s cutoff, so the default remains fixed. Deep failure/timeout is surfaced in a fallback event.
- Verified deepagents APIs from installed source: declarative subagents, StateBackend, explicit TodoListMiddleware, InMemorySaver, streamed updates/subgraphs, interrupt_on and Command(resume).

## Broken / blocked on

- **M4:** `cache/join.parquet` is absent, and lane A/B live adapters remain stubs. Sanitized implementation errors: `Owner 1: load the real index here`, `Owner 2: query the joined table here`, `Owner 2: call Vexcel here and cache the result`. Credentials work; a real joined pick has not been validated.
- Live-mode failure probe with `TYPECAST_USE_MOCKS=0`: health reported live adapters; SSE emitted an agent error and terminal error, no result and no silent mock fallback. Client message: `Scouting failed. Please try again.`
- **M5 measurement:** no real shot corpus or human relevance labels. Recall@10 remains N/A; no accuracy claim.
- LangSmith key absent. Tracing is optional; no live trace validation or URL is claimed.
- Sponsor engineer name remains TBD in DECISIONS.md. Existing sponsor permission is recorded; no name was invented.

## Integration and next handoff

- PR #1 (interfaces/contracts) merged as `93224a9`; PR #2 (dependencies/access checks) as `eeb2000`.
- [PR #4](https://github.com/Tecncentral/typecast/pull/4) (complete lane C implementation) merged into dev as `cdaac5c`.
- [PR #3](https://github.com/Tecncentral/typecast/pull/3) (reviewed lane A geometry fixes) merged into dev as `d3ca338`. Integration exposed and fixed fresh-cache serving and unrounded depth filtering before merge. A separate review fixed vision requests overrunning their wall-clock deadline.
- Latest dev was merged into lane-c. No main merge, deployment, delivery, or external submission was performed. No other lane PR was open at this check.
- No independent lane C implementation task remains. When A/B supply real adapters and the private join, run the go-live prompt in `docs/team/OWNER-3-PROMPTS.md`: one known building through both engines, then three where supported, real frame browser checks, and labelled evaluation before tuning. Keep the source mode and measured/estimated/unknown evidence explicit.
