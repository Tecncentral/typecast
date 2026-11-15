# Owner 3 prompts: agent, API and integration captain (lane-c)

Paste the **lead prompt** into your main coding agent. It does step 0 itself, then hands the five **subagent briefs** to subagents that run in parallel. Each subagent owns its own files, so none of them edit the same file. If your tool can't spawn subagents from a prompt, open five subagent sessions yourself and paste one brief into each, after the lead has merged step 0.

The **review prompt** and the **go-live prompt** are for later in the day.

## Before you paste (human, 10 minutes)

1. Tell the team you are Owner 3 and integration captain.
2. Fill your private `.env` (git-ignored; copy `.env.example` if it doesn't exist yet):
   - `LLM_API_KEY` and `VISION_API_KEY`: the same **OpenAI API** key (from platform.openai.com, not the ChatGPT app). `TYPECAST_LLM_PROVIDER=openai` is already set.
   - `TYPECAST_LLM_MODEL` and `TYPECAST_VISION_MODEL`: the exact model ids as they appear in your OpenAI models list. The vision model must accept image input. If one model is slow, use a faster one for `TYPECAST_LLM_MODEL` (parsing, skeptic) and the strong one for `TYPECAST_VISION_MODEL` (rerank).
   - Optional backup: `TYPECAST_FALLBACK_PROVIDER=anthropic`, `TYPECAST_FALLBACK_MODEL` (exact id) and `FALLBACK_API_KEY`, used only if OpenAI fails or rate-limits.
   - `LANGSMITH_API_KEY` if you have one.

   A ChatGPT subscription powers your coding agent. It does not pay for the app's own model calls, which need the API key.
3. Done: a sponsor engineer allowed sending scan images to a vision model, and `TYPECAST_ALLOW_VISION_UPLOAD=1` is set. Add the engineer's name in `DECISIONS.md`.
4. Ask Owner 2 how they will hand over the private join (`cache/join.parquet`), since it can't go in git.

---

## Lead prompt

```
You are the lead engineer for Typecast lane C (Owner 3): the agent, the HTTP API, and integration captain for a four-person HackPrinceton team. Devpost closes 08:00 Eastern, Sunday Nov 15; aim to submit at 07:30. Feature freeze is 00:00 Sunday; after that, reliability fixes only.

Read these fully, in this order, before writing code: AGENTS.md, docs/team/START-HERE.md, docs/team/OWNER-3-AGENT.md, docs/team/ACCESS.md, docs/team/CONTRACT-CHANGES.md, docs/team/OWNER-3-PROMPTS.md (this file), and in docs/HANDOFF.md the sections "Settled; do not reopen", "Agent tools", "Subagents" and "Owner 3 plan". Then read contracts/schemas.py, contracts/schemas.ts, agent/pipeline.py, agent/app.py, agent/tests/, scripts/verify.py and scripts/smoke.py. AGENTS.md overrides anything below if they conflict.

Setup, once:
  git fetch origin && git switch lane-c && git merge origin/dev
  python3.13 -m venv .venv && source .venv/bin/activate
  python -m pip install -r requirements.lock.txt
  python scripts/verify.py
Write the real output into docs/team/status-lane-c.md (create it) with commit hash and UTC time.

You personally own: agent/interfaces.py, contracts/ (additive changes by agreement), mocks/ (only to match contract changes), requirements.txt, requirements.lock.txt, scripts/ (except scripts/e2e.py, which SA5 creates), .github/, docs/team/status-lane-c.md, docs/team/CONTRACT-CHANGES.md, all commits, PRs and merges. Subagents own everything else in agent/ as listed in their briefs.

STEP 0 (you, before any subagent starts, about 30 minutes)
1. Create agent/interfaces.py with:
   - Emit = Callable[[Event], None], and null_emit.
   - RunContext (dataclass): thread_id, emit, engine ("fixed" | "deep"), source_mode ("mock" | "live"), timings: dict[str, float], started_at.
   - Requirements (pydantic): scene, city, era_label, year_min, year_max, trucks, cars, min_area_m2, min_ceiling_m, focal_mm=24.0, frame_width_m=6.0, look, mood, time_of_day, explicit fields set (so "0 trucks" differs from "not mentioned").
   - timed(ctx, name) context manager that records ms in ctx.timings and emits Event(type="tool", agent=name, ms=...).
   - The signatures the subagents implement, as stubs that call today's behaviour so nothing breaks:
       runtime.run_scout(ctx, scene=None, example_shot_id=None) -> ScoutResponse
       runtime.run_refine(ctx, message) -> ScoutResponse
       pipeline.scout(ctx, req_or_example) -> ScoutResponse   and   pipeline.refine(ctx, state, message) -> ScoutResponse
       parse.parse_scene(scene) -> Requirements
       rerank.rerank_shots(ctx, req, shots, k=20) -> list[Shot]
       deep.run_deep(ctx, req) -> ScoutResponse
       state.save(thread_id, name, obj) / state.load(thread_id, name)
2. Propose additive, optional contract fields in docs/team/CONTRACT-CHANGES.md, then apply them to contracts/schemas.py, contracts/schemas.ts and the mocks together:
   - Event: ts (float, seconds since run start), ms (optional tool duration), engine (optional).
   - Evidence: {source: "costar" | "matterport" | "vexcel", claim: str, status: "measured" | "estimated" | "unknown"}; Pick.evidence: list[Evidence] = [].
   - ShotFit.status: "fits" | "tight" | "unknown" (keep the fits bool for old readers; unknown geometry is never fits=True).
   - ScoutResponse: engine, source_mode, trace_url (None unless a real trace exists), timings: dict[str, float].
   All fields get defaults, so lanes A, B and D keep working.
3. Move the HTTP-level tests (anything using TestClient) from agent/tests/test_pipeline.py into a new agent/tests/test_app.py, so SA1 owns the API tests and SA2 owns the pipeline tests.
4. python scripts/verify.py must pass. Commit "lane-c: interfaces and additive contract fields", push lane-c, and open a PR into dev that lists the new fields for lanes A, B and D. Tell me (the human) to notify them. Merge it into dev yourself once verify passes, so the subagents start from it.

STEP 1: start the five subagents with the briefs SA1 to SA5 from docs/team/OWNER-3-PROMPTS.md. Give each its brief verbatim, plus: "Only edit the files you own. If you need a change in a file you don't own, put it in your final report instead. Run the tests you wrote and paste their real output in your report."

STEP 2: integration loop, repeated until the deadline.
- When a subagent reports: read its diff yourself, run python scripts/verify.py, start uvicorn agent.app:app and hit /health, POST /scout, GET /scout/stream, POST /refine and POST /approve with the scene "INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling, windows on one wall. Parking for 3 trucks and 30 crew cars." Check the actual output, not just status codes. Commit small coherent changes, push lane-c, and open or update a PR into dev covering: behaviour change, commands and results, mode (mock or live), prerequisites, remaining risks.
- At least every two hours: merge origin/dev into lane-c. Review open PRs from lane-a, lane-b and lane-d. For each one: read the diff, merge latest dev into it locally, run verify plus the end-to-end flow above, and merge into dev without force only if it passes. Leave a review comment with what you ran. Never merge into main.
- New packages: subagents report them; you add them to requirements.txt, regenerate requirements.lock.txt, and test a clean venv before merging.
- When lane A's search_shots/get_shot or lane B's search_costar/get_property/plan_logistics return real data: run with TYPECAST_USE_MOCKS=0 on one known building and confirm one real pick end to end. Record timings. In live mode a failing adapter must surface as an error event, never a silent switch to mocks.

Milestones. Check each yourself by running it, then record the command and output in status-lane-c.md:
M1 (about 2 hours in): interfaces merged; pipeline null-safe; /scout/stream emits events while tools run (first event within 5 s, before the result); /scout and /scout/stream share one code path.
M2 (about 5 hours): model-based parse_scene and vision rerank behind env flags, with the rule-based fallback announced in events; refine fixed; thread validation; /approve saves a local draft and never claims it was sent.
M3 (about 8 hours): the deepagents engine runs the director, market scout, interior scout, logistics scout and skeptic over the same tools. TYPECAST_ENGINE=deep|fixed; the response names the engine that actually ran; trace_url only from a real LangSmith run.
M4 (as soon as lanes A and B have one real building; START-HERE targets about 3 hours in, 8 at the latest): one real pick end to end, then three if the data allows. Fewer than three is reported honestly, never padded. This milestone can land before M2 and M3.
M5 (about 15 hours): eval reports recall@10 on hand-labelled scenes plus median and p95 latency; "need parking for 5 trucks" re-ranks without a new search, and a test proves it.

Never print or commit keys. .env and cache/ stay local. Licensed CoStar rows never appear in git, logs, PR text or chat. No message to anyone outside the team. No spending beyond the keys already in .env. No force-push; no merge to main. Never fabricate events, traces, timings, test results or delivery. If access is missing, finish the interface against fixtures, record the exact sanitized error in the status file, and keep going on independent work.

End every session with: a committed status-lane-c.md (works, with commands and output; broken; next; blocked on) and a reviewable PR. Never end with only a chat report.
```

---

## SA1: runtime, streaming and thread state

```
You are subagent SA1 on Typecast lane C. Read AGENTS.md, docs/team/OWNER-3-AGENT.md, contracts/schemas.py, agent/interfaces.py, agent/app.py and agent/pipeline.py first.

You own only: agent/runtime.py (new), agent/state.py (new), agent/app.py, agent/tests/test_runtime.py (new), agent/tests/test_app.py (the lead creates it in step 0). Do not edit other files.

Build:
1. One execution path. runtime.run_scout(ctx, ...) chooses the engine (TYPECAST_ENGINE, default "fixed"; "deep" calls deep.run_deep and falls back to fixed on error or after 90 s, emitting an event that says so). POST /scout and GET /scout/stream both call it.
2. Real streaming. In /scout/stream, run the work in a worker thread; ctx.emit pushes each Event into an asyncio.Queue; yield "event: agent" for each event as it arrives, then "event: result" with the ScoutResponse. On failure yield "event: error" with a short sanitized message. Delete the TYPECAST_EVENT_DELAY replay. Keep the event names agent/result unchanged because lane D depends on them.
3. state.py: per-thread working memory under cache/threads/<thread_id>/ (requirements.json, candidates.json, shortlist.json, skeptic.md), plus an in-memory index with a 6-hour TTL. thread_id must match ^[a-z0-9-]{4,40}$ (no path tricks).
4. /refine: unknown or expired thread -> 404 with a clear message; otherwise runtime.run_refine(ctx, message) using saved state.
5. /approve: validate thread and pick_rank (unknown thread 404, bad rank 422). On "yes", write the drafted note to cache/outbox/<thread_id>-<rank>.md and return {"status": "draft_saved", "sent": false, "path": "<relative path>"}. Anything else returns {"status": "cancelled", "sent": false}. Never send anything anywhere, and never claim delivery.
6. /health: per-adapter source mode (mock or live) read at request time, the engines available, and whether LangSmith is configured (true or false only, never the key). Keep the existing top-level "mocks" boolean, because scripts/smoke.py checks it.
7. Every response carries engine, source_mode and timings from ctx.

Tests (no network, no keys): the first streamed event arrives before the result and its ts is less than the result's; /scout and /scout/stream return the same picks for the same scene; unknown thread 404; bad pick_rank 422; a tool that raises produces an error event and a 500-free stream end; approve "yes" writes the draft file and returns sent=false.

Finish by running python scripts/verify.py and your tests. Report: files changed, real test output, anything you needed from a file you don't own.
```

## SA2: pipeline hardening, skeptic and refine

```
You are subagent SA2 on Typecast lane C. Read AGENTS.md, docs/team/OWNER-3-AGENT.md, docs/team/START-HERE.md ("Known implementation gaps"), contracts/schemas.py, agent/interfaces.py and agent/pipeline.py first.

You own only: agent/pipeline.py, agent/tests/test_pipeline.py, agent/tests/test_pipeline_edges.py (new). Do not edit other files.

Build, keeping pipeline.py the deterministic "fixed" engine:
1. Signatures from agent/interfaces.py: scout(ctx, ...) and refine(ctx, state, message). Emit every event through ctx.emit at the moment it happens (also keep them for the response). Wrap each tool call in interfaces.timed(ctx, name).
2. Replace the regex parse_scene in this file with calls to parse.parse_scene, and call rerank.rerank_shots after search. Both come through their interfaces; SA3 implements them. Keep a pipeline.parse_scene alias so old imports still work.
3. Null safety: never format None. Unknown room depth or ceiling gives ShotFit.status "unknown" with the note "measure on site", never fits=True. Estimated geometry (measure_on_site) is at most "tight".
4. Evidence: each Pick gets Evidence entries for CoStar (type, year built, availability), Matterport (room area, ceiling, depth, fit) and Vexcel (truck and car spaces, walk distance, noise), each marked measured, estimated or unknown. The reason sentence cites all three layers, or says plainly which layer is missing.
5. Skeptic (fixed engine): for each pick, at least one concrete objection or exactly "No objection." Not enough parking, an unknown shot fit and an occupied space are blocking objections that lower the rank clearly, not small penalties.
6. Relaxing: when fewer than three picks survive, loosen in this order: parking distance, then era, then minimum size. Emit Event(type="relaxed") naming each thing given up, and add it to gave_up. Never hide a failed shot fit. Fewer than three after relaxing is returned honestly.
7. refine: parse the follow-up; explicit values override, including zero ("no trucks" means 0); unmentioned constraints keep their original values. Re-rank cached candidates from state; never call search_shots or search_costar again.

Tests (no network): None geometry doesn't crash and isn't "fits"; all candidates failing gives fewer picks plus relaxed events; "need parking for 5 trucks" changes ranking and skeptic notes; "no trucks" sets trucks to 0; refine makes zero search calls (monkeypatch counters); every pick has three evidence sources or names the missing one; events reach ctx.emit in order while running.

Finish by running python scripts/verify.py and your tests. Report: files changed, real test output, anything you need from files you don't own.
```

## SA3: model adapters, parse_scene and vision rerank

```
You are subagent SA3 on Typecast lane C. Read AGENTS.md, docs/team/ACCESS.md, contracts/schemas.py, agent/interfaces.py and agent/pipeline.py (the rule-based parse_scene) first.

You own only: agent/models.py (new), agent/parse.py (new), agent/rerank.py (new), agent/prompts/parse_scene.md and agent/prompts/rerank.md (new), agent/tests/test_models.py (new). Do not edit other files.

Build:
1. models.py: a small provider adapter. Read TYPECAST_LLM_PROVIDER (team default: openai), TYPECAST_LLM_MODEL, TYPECAST_VISION_MODEL, LLM_API_KEY and VISION_API_KEY from the environment. Implement openai first with the official openai Python SDK: structured output validated against the pydantic model, and image input for rerank. Check the installed SDK's docs or source for exact method and parameter names; don't guess endpoints, and never hard-code a model id. Then, only if simple, add an anthropic adapter used when TYPECAST_FALLBACK_PROVIDER=anthropic and the primary call fails, times out or is rate-limited (TYPECAST_FALLBACK_MODEL, FALLBACK_API_KEY). Emit an event whenever the fallback is used. If a key or model is missing, configured() returns False and callers use the rule-based fallbacks. Never log keys or full prompts containing licensed data.
2. parse.py: parse_scene(scene) -> Requirements via one structured-output call with prompts/parse_scene.md. Extract city (default Los Angeles; Houston if named), era to year range, trucks, cars, min area, min ceiling, focal length (default 24 mm), frame width (default 6 m), look, mood and time of day. Record which fields the scene stated explicitly. Validate with pydantic. On any failure or no key, fall back to a copy of the regex parser now in agent/pipeline.py (copy it here; don't edit pipeline.py, SA2 switches it to call yours) and set a flag the pipeline can emit as an event ("parsed without a model").
3. rerank.py: rerank_shots(ctx, req, shots, k=20). Send the top k views with the scene to the vision model, at most 5 requests at a time with a 20 s timeout each. Each returns score 0 to 1 plus a one-line reason ("drop ceiling and fluorescent panels: right for the 1980s"). Cache results under cache/rerank/<sha of scene>/<shot_id>.json. Read images from the local cache path or the served URL. Only send images if TYPECAST_ALLOW_VISION_UPLOAD=1, the sponsor permission from ACCESS.md. Otherwise keep the embedding order and emit an event explaining why rerank was skipped. Per-shot failures keep the original score and are counted in an event.

Tests with a fake provider (no network, no keys): structured parse of the police-station scene; fallback when unconfigured; "no trucks" gives 0 with explicit=True; rerank respects the upload flag, the cache (second call makes no provider calls) and the concurrency limit; a timeout on one shot doesn't fail the batch.

Report: files changed, real test output, and any package to add to requirements (name and version) for the lead.
```

## SA4: deepagents engine

```
You are subagent SA4 on Typecast lane C. Read AGENTS.md, docs/team/OWNER-3-AGENT.md, the "Agent tools", "Subagents" and "Owner 3 plan" sections of docs/HANDOFF.md, contracts/schemas.py, agent/interfaces.py and agent/pipeline.py first.

You own only: agent/deep.py (new), agent/deep_tools.py (new), agent/prompts/deep_director.md, deep_market.md, deep_interior.md, deep_logistics.md and deep_skeptic.md (new), agent/tests/test_deep.py (new). Do not edit other files.

First, install deepagents into the local venv (do not edit requirements; report the exact version to the lead). Read the installed package's README and source to confirm the real API: create_deep_agent arguments, how subagents are declared, tools, the filesystem backend, interrupts or human approval, and streaming. Names in the handoff came from a summary and may be wrong; the installed code wins. Record the verified API in your report.

Build deep.run_deep(ctx, req) -> ScoutResponse:
0. Model: the same provider and model the rest of the app uses (TYPECAST_LLM_PROVIDER, default openai; TYPECAST_LLM_MODEL; key in LLM_API_KEY), through the LangChain chat-model integration that the installed deepagents version documents. Never hard-code a model id. The skeptic and the scouts may use TYPECAST_LLM_MODEL; nothing here needs the vision model, because rerank_shots is a tool.
1. Director: system prompt (prompts/deep_director.md) stating the job, the tool order, the output shape, and the rule that every pick cites CoStar, Matterport and Vexcel evidence. It writes its to-do list first and keeps it updated.
2. Subagents: market_scout (search_costar, get_property), interior_scout (search_shots, check_shot, rerank_shots), logistics_scout (plan_logistics), skeptic (read-only over the shortlist; for each pick, a concrete objection or "No objection.").
3. deep_tools.py: thin wrappers over the same functions the fixed pipeline uses, with clear docstrings and typed inputs, each inside interfaces.timed(ctx, name). No duplicated business logic.
4. Events: map the package's stream output to Event types plan, todo, subagent_start, subagent_result, skeptic, relaxed and final, with engine="deep". Emit them live through ctx.emit. Never invent events that didn't happen.
5. Working memory: write candidates.json, shortlist.json and skeptic.md per thread through state.save (interface only).
6. Approval: put draft_inquiry behind the package's interrupt or approval mechanism, so it only resumes through /approve. The draft never goes anywhere but a local file.
7. LangSmith: enable tracing only when LANGSMITH_API_KEY is set; read the real run URL from the client after the run and return it as trace_url. Never construct or guess a URL.
8. Convert the final state into the Pick contract with evidence. If parsing the agent's output fails or the run passes 90 s, raise, so runtime falls back to the fixed engine and says so.

Tests with a fake, deterministic chat model (no network, no keys): the director calls all three scouts and the skeptic; events arrive in order through ctx.emit; output validates as ScoutResponse with engine="deep"; a tool error surfaces as an event plus a raised error for fallback.

Report: verified deepagents API notes, package versions for the lead, files changed, real test output.
```

## SA5: evaluation and end-to-end checks

```
You are subagent SA5 on Typecast lane C. Read AGENTS.md, docs/team/START-HERE.md, docs/team/OWNER-1-INTERIORS.md (the evaluation part), contracts/schemas.py, agent/app.py and scripts/smoke.py first.

You own only: agent/eval/ (new folder), agent/tests/test_integration.py (new), scripts/e2e.py (new), docs/team/eval.md (new). Do not edit other files.

Build:
1. agent/eval/scenes.jsonl: 20 realistic script scenes across the space types the data most likely holds (offices, open-plan floors, lobbies, retail, warehouses, apartments), each with id, scene text, and split "test" (15) or "tune" (5). Vary era, size, parking and time of day. Write them from general screenwriting knowledge; they are not data.
2. agent/eval/labels.template.jsonl: one line per scene with relevant_shot_ids: [] and labeler: "", to be filled by hand once real shots exist. Label before tuning.
3. agent/eval/run_eval.py: runs each scene through the app in-process and records recall@10 against labels (skipping unlabelled scenes and reporting how many were scored), p50 and p95 latency, engine and source mode. It writes docs/team/eval.md with the numbers, sample count and date. On mocks, the file says "mock run: not a result" at the top.
4. scripts/e2e.py: runs the police-station scene through /scout/stream, then /refine ("need parking for 5 trucks"), then /approve ("yes"). It asserts that the first event arrived before the result, that refine kept the thread_id and made no search call (patch counters on search_shots and search_costar), and that approve returned sent=false. It prints a timing table and exits non-zero on failure.
5. agent/tests/test_integration.py: the same checks in pytest form, mock mode, no network.

Report: files changed, real output of run_eval.py and e2e.py on mocks, and anything the lead should add to scripts/verify.py or CI.
```

---

## Review prompt (when a lane PR arrives)

```
Review PR <number> from <lane> into dev as Typecast integration captain. Read the diff fully. Fetch it, merge latest origin/dev into it locally, run python scripts/verify.py and scripts/e2e.py, then start the API and run the police-station scene end to end in the mode the PR claims (mock or live). Check that it only touches its lane's folders, adds no keys or licensed data (grep for keys and CoStar-looking rows), keeps contract fields additive, and labels mock versus live honestly. If everything passes, merge without force and comment with the commands and results. If not, comment with the exact failure and leave it unmerged. Never merge into main.
```

## Go-live prompt (when lanes A and B have real data)

```
Lanes A and B report real data. In lane-c, with TYPECAST_USE_MOCKS=0, run one known shared building through /scout/stream with both engines. Confirm: real frames load in the browser through the API's /cache route, every pick's evidence entries are marked measured, estimated or unknown correctly, the skeptic objects to something real, and timings are recorded. Then scale to three buildings and run agent/eval/run_eval.py on the labelled scenes. Fix integration bugs in files you own; for other lanes' files, write the exact issue in their PR or status file. Update status-lane-c.md with commands and real output, and open or update the PR into dev.
```
