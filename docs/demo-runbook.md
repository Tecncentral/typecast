# Typecast demo runbook

Use the **Warehouse handoff** scene, the five-truck follow-up and a visible skeptic objection. The other four validated scenes are backups. The selected configuration is **20 candidates / concurrency 5 / batch size 5**. The five scenes now have refreshed visual caches and completed fixed/deep rehearsals; current warm medians are **10.092 / 44.160 seconds**. Three optional trace links were unavailable and remain recorded; source checks, refinement and local drafts passed.

## Processes and ports

| Process | Port/location | Rule |
| --- | --- | --- |
| Integration API | `localhost:8000`, main `typecast/` checkout | Integration captain owns this process. |
| Viewer rehearsal | `localhost:8001/app/`, separate `typecast-d/` checkout | Viewer owner starts and verifies it; do not edit or restart that worktree from the integration session. |
| Exterior stretch | Port 8003 if separately enabled | Outside the core demo; keep off unless independently accepted. |
| Frozen labeling lab | Port 8765 | Separate from the presentation. Do not change labels or index to rehearse. |

The viewer's final browser gate and screenshot are **PENDING_VIEWER_ACCEPTANCE** until its owner reports success. If `/app/` is not ready on the chosen server, rehearse the API/retained recording and describe that state honestly. The backend's prior Chromium checks verified real image URLs; they do not prove the final viewer is complete.

## Start the selected-default rehearsal

From the main checkout, with the existing private `.env`, `.venv`, source caches, model weights and frozen index provisioned:

```bash
cd /Users/zukhriddin/Documents/HackathonProjects/HackPrinceton/typecast
TYPECAST_USE_MOCKS=0 TYPECAST_ENGINE=deep \
  TYPECAST_ENABLE_MODEL_PARSE=1 TYPECAST_ENABLE_VISION_RERANK=1 \
  TYPECAST_ALLOW_VISION_UPLOAD=1 LANGSMITH_TRACING=true \
  TYPECAST_LLM_PROVIDER=openai TYPECAST_LLM_MODEL=gpt-6.1-sol \
  TYPECAST_VISION_MODEL=gpt-6.1-sol TYPECAST_REASONING_EFFORT=medium \
  TYPECAST_SCOUT_REASONING_EFFORT=low \
  TYPECAST_RERANK_POOL=20 TYPECAST_VISION_CONCURRENCY=5 TYPECAST_VISION_BATCH_SIZE=5 \
  .venv/bin/python -m uvicorn agent.app:app --host 127.0.0.1 --port 8000
```

Use the same environment with `TYPECAST_ENGINE=fixed` for the faster fixed rehearsal. Stop only the process you own before changing engines; restarting loses the active thread and deep approval checkpoint. Begin a new scene before refining or approving after a restart. Keep private credentials in `.env`; do not copy them into commands, screenshots or the recording.

In another terminal:

```bash
curl --fail --silent http://localhost:8000/health
curl --fail --silent http://localhost:8000/config | \
  .venv/bin/python -c 'import json,sys; d=json.load(sys.stdin); print({k:d[k] for k in ("mode","engine","tracing")})'
```

Confirm live source adapters, the intended engine, the frozen 10,568-view index, `cache/demo-set.json`, and cached Vexcel/rerank assets. The `/health` compatibility `engine` field is not a selected-run assertion: check `/config`, then the actual response. For Matterport SDK navigation, open `localhost`, whose configured browser domain is allowed. Heading alignment remains unverified; label scan navigation accurately.

If presenting the separate viewer server on port 8001, coordinate these checks with its owner and use that port for the diagnostics below. Warm the backend process that will serve the stage demo; warming port 8000 does not initialize a separate process on 8001.

Optional operator diagnostics after setup, not during the timed pitch:

```bash
.venv/bin/python scripts/check_demo.py --base-url http://localhost:8000 \
  --engine deep --phase warm --scene-id la-warehouse-handoff --verify-trace
cache/browser-venv/bin/python scripts/check_demo_browser.py --base-url http://localhost:8000 \
  --responses cache/demo-checks \
  --executable "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell"
```

The first command makes actual model calls and exercises explicit local-draft approval. It writes a new private attempt instead of replacing retained evidence. The second uses the team's separate Playwright environment and the verified Chromium headless shell on this Mac; those are not included in the main `.venv` or application locks. On another machine, provision Playwright/Chromium first and adjust `--executable` (or omit it after installing Playwright's default browser). Limit `--responses` to the retained rehearsal directory to avoid reviewing all historical attempts. The recorded browser check below states what was actually exercised.

## Stage sequence

1. Open the accepted viewer, show **LIVE** and the selected engine, and start **Warehouse handoff**. Use the exact saved scene text below.
2. Let real plan/scout events run. Explain CoStar property facts, Matterport camera views and Vexcel crew logistics while waiting. Current cache-warm warehouse deep time: **38.286 s**; fixed: **8.550 s**.
3. Show one real frame and its aerial. The retained final deep warehouse response has a **rail-proximity** objection. Read the actual returned caveat; a later response may select different properties. Camera fit remains unknown in the retained warehouse picks.
4. Enter **Need parking for 5 trucks.** Preserve the returned `thread_id`. Show the changed rank or allocation and the actual response engine. The fixed refinement path retains candidate membership and makes no fresh property/interior search.
5. Explicitly approve rank 1 only if demonstrating the local draft. Show the saved, unsent state. Do not claim a message was delivered or that the owner granted permission.
6. End on the shortlist with source evidence and unknowns visible. Use the [timed pitch](pitch.md); keep five-scene demo timing separate from the human test result.

## Scene texts

Every option below passed the retained real fixed/deep demo checks. The private property IDs and source rows stay in `cache/demo-set.json`; only authored scene text is copied here.

### 1. Glass office confrontation — Los Angeles

> INT. LOS ANGELES OFFICE - DAY. Two colleagues confront each other in an office meeting room with glass partitions, a table, neutral walls and overhead office lighting. A clear view through the glass gives depth behind the actors. Parking for 2 trucks and 10 crew cars. No required building age.

### 2. Warehouse handoff — Los Angeles, main

> INT. LOS ANGELES WAREHOUSE - DAY. Two couriers exchange a case in an industrial warehouse with exposed roof structure, a concrete floor and an open aisle; stored boxes or pallets can remain at the sides. Daylight from high openings. Parking for 2 trucks and 10 crew cars. No required building age.

### 3. Empty shop rehearsal — Los Angeles

> INT. LOS ANGELES EMPTY SHOP - DAY. Two performers rehearse in a long empty room with wood flooring, plain white walls and a suspended ceiling with overhead lights. Keep the floor clear for movement. Parking for 2 trucks and 10 crew cars. No required building age.

### 4. Houston glass office meeting

> INT. HOUSTON OFFICE - DAY. Two colleagues meet in an empty office room with glass partitions, pale walls, carpet and daylight from broad windows. Furniture can be brought in for a tense conversation. Parking for 2 trucks and 10 crew cars. No required building age.

### 5. Houston apartment conversation

> INT. HOUSTON APARTMENT - DAY. Two friends talk in a bright furnished living room with large windows, city views, a sofa and an open kitchen or counter nearby. Natural daylight and a comfortable residential feel. Parking for 2 trucks and 10 crew cars. No required building age.

The default city for an unnamed city is Los Angeles. Name Houston explicitly to select Houston. The API now emits a notice and returns `notes` with “No city named; searched Los Angeles. Name Houston to search there.” This was verified on actual city-free tune/test runs; both named Houston scenes also returned Houston properties in the live fixed/deep rehearsal. The separately owned viewer must render that field before promising the wording on screen. Do not claim that an unspecified scene searches both cities.

## Slow runs, Wi-Fi loss and failure states

| Situation | Operator action and wording |
| --- | --- |
| Cold CLIP/model initialization | Start and rehearse before judging. Current cache-warm medians are **10.092 s fixed / 44.160 s deep** across five authored scenes. The first deep request includes lazy process initialization. The separate post-change v2 fixed median **16.057 s** used fresh visual scores and no warmup; these are different measurements. |
| Deep fails or reaches its 90 s budget | Leave the actual fallback event and fixed response label visible. Never call a fixed result a successful deep run. |
| Provider rate limit | Stop model requests; the worker does not retry through fixed. Use the labeled backup while resolving the limit, then deliberately restart the owned process before a new live rehearsal. |
| Trace link is null | Continue with the source-backed result. Say tracing verification was unavailable; do not create a link or silently replace the timing. |
| Imagery/logistics providers cannot be reached | Precomputed local evidence can still be used. Runtime logistics does not contact Vexcel/OSM; do not refresh caches on stage. |
| Model API or all Wi-Fi is unavailable | Cached images and visual scores do **not** make the parser/director fully offline. Play the retained backup labeled **recorded live run**, or switch to the explicitly labeled fixture mode below. Do not fake streaming progress or present a JSON replay as a fresh run. |
| Server restarted or thread expired | Start a new scout. Disk artifacts alone do not restore the in-memory conversation and approval graph. |
| Missing image, no match or unknown capacity | Keep the failure/unknown visible. Choose another validated scene if needed; do not substitute a real-looking fixture into live mode. |

For an entirely offline fixture demonstration, stop the owned server and start a separate clearly labeled mock run:

```bash
TYPECAST_USE_MOCKS=1 TYPECAST_ENGINE=fixed \
  TYPECAST_ENABLE_MODEL_PARSE=0 TYPECAST_ENABLE_VISION_RERANK=0 \
  LANGSMITH_TRACING=false \
  .venv/bin/python -m uvicorn agent.app:app --host 127.0.0.1 --port 8000
```

Verify the **MOCK** label. Fixtures demonstrate interaction only; none of their timings or relevance counts are real-data results.

## Backup recording

Run the exact judging path against the already-running LIVE deep stage server. This spends one Warehouse scout, one five-truck refinement and one Director production plan; coordinate with the integration captain so it does not overlap the full warm rehearsal. It does not approve an owner draft, generate dressing or call World Labs.

```bash
cache/browser-venv/bin/python scripts/check_judge_path.py \
  --base-url http://localhost:8000 --record \
  --executable "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell"
```

The check follows Warehouse handoff → actual inside-out descent → Replay/Skip → Look around at 24 then 50 mm → D if precomputed AI dressing is offered → G → Escape → **Need parking for 5 trucks.** on the same thread → Director demo script → one-location plan → Play. It fails on JavaScript/console errors, missing images, a missing honesty label, a lost thread, or a Director plan that does not cover three or four scenes from one location with zero company moves. An explicit 404 from the optional dressed-set lookup is logged **not offered**; broken offered assets still fail. Walk mode is reported as offered/not offered and is optional.

Screenshots and `report.json` stay under `cache/demo-checks/judge-path/<UTC timestamp>/`. With `--record`, the same path runs at human pace at 1440×900 and writes `cache/demo-video/<UTC timestamp>.webm`. A failed check also retains its recording for diagnosis: only a report with `passed: true` is an accepted backup. The video has no narration; record narration separately if the human wants a narrated submission video. Do not call cached images or scores a fully offline fresh run: keep a visible **recorded live run** label alongside the accepted video throughout fallback playback. The raw private recording is not a publication-ready submission video.

Before the Director PR merges, pass `--director-script-file cache/demo-checks/director-grouping/winner-script.txt` to use stream 1's visually checked authored script. The checker selects the actual zero-move plan through the candidate selector. After the merge, omit that option to exercise the served **Demo script** itself. Chromium and Playwright live in the separate private browser environment; omit `--executable` only when its default Chromium is installed.

The initial run is tracked in the stream 3 PR. Repeat this command after the human merges the Job 8 PRs and after **01:00 ET Sunday November 15**; a pre-merge run does not satisfy that final gate. Watch the complete accepted recording locally for readable evidence, actual engine/mode, uncertainty labels, framing and refinement. Keep the original private: it contains licensed imagery. Only a human may approve publication after checking sponsor-media permission, choose the final video/screenshot, add team Discord names and submit. No video, licensed imagery or raw cache belongs in Git.

## Evidence locations and final handoff

- Public methodology: [evaluation](team/eval.md), [architecture](architecture.md), [Devpost draft](devpost.md).
- Private authored scenes/property anchors: `cache/demo-set.json`.
- Private historical timings and retained failures: `cache/demo-checks/final-comparison.json` and adjacent per-attempt directories.
- Private frozen v1 human run: `cache/evaluation/runs/20261114T190213Z/`.
- Private source coverage: `cache/vexcel/expanded-final-report.json`; exact indexed demo candidates: `cache/vexcel/expanded-demo-indexed-candidates.json`.
- Final viewer acceptance/screenshot: **PENDING_VIEWER_ACCEPTANCE**.
- Selected 20/5/5, frozen v1, separate v2 and current rehearsal: [evaluation](team/eval.md). Private current rehearsal audit: `cache/experiments/rerank-v2/demo-audit.json`; browser evidence: `cache/experiments/rerank-v2/browser/`.
- Team Discord names and Amazon/ChatOverflow eligibility evidence: human completion required; see [track notes](devpost.md#track-evidence-and-human-completion).

Submission target from the event packet recorded in [START-HERE](team/START-HERE.md#event-evidence-and-uncertainty): **07:30 Eastern Sunday November 15**, ahead of the recorded **08:00 deadline**. Confirm live organizer changes before the human submits. The pitch and any optional video should fit two minutes.
