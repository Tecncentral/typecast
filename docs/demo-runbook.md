# Typecast demo runbook

Use **Warehouse handoff** for the source reveal: live agents → inside-out descent → real viewfinder → optional AI dressing → five trucks → Director’s Room grouping. The other authored scenes are backups. Selected configuration: **20 candidates / concurrency 5 / batch size 5**, from the [tune selection](team/eval.md#tune-experiments). Previous warm medians were **10.092 / 44.160 seconds**; **three** optional trace links were unavailable and retained ([earlier rehearsal](team/eval.md#demo-refresh-after-v2)). Current stage measurements and actual dressing availability belong in [lane C’s stage report](team/status-lane-c.md).

## Processes and ports

| Process | Port/location | Rule |
| --- | --- | --- |
| Stage API and both UIs | `localhost:8000/app/` and `/director`, isolated `typecast-stage/` checkout at reviewed `origin/dev` | Integration captain owns this process. Rehearse this exact process. |
| Viewer rehearsal | `localhost:8001/app/`, separate `typecast-d/` checkout | Viewer owner starts and verifies it; do not edit or restart that worktree from the integration session. |
| Exterior stretch | Port 8003 if separately enabled | Outside the core demo; keep off unless independently accepted. |
| Frozen labeling lab | Port 8765 | Separate from the presentation. Do not change labels or index to rehearse. |

The merged viewer and descent have their own [browser acceptance](team/status-lane-d.md). That does not replace the combined judge path on this stage process. Check the latest run’s actual images, mode, engine, optional dressing and grouping. The **post-01:00 ET merged judge-path gate remains pending** until its private report records success; do not infer it from earlier component checks.

## Start the selected-default rehearsal

From the isolated stage checkout based on reviewed `origin/dev`, with `.env`, `.venv` and `cache/` symlinked from `typecast/` and local model weights provisioned:

```bash
cd /Users/zukhriddin/Documents/HackathonProjects/HackPrinceton/typecast-stage
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

Confirm live source adapters, the intended engine, the frozen **10,568-view** index ([coverage](team/status-lane-c.md)), `cache/demo-set.json`, and cached Vexcel/rerank assets. The `/health` compatibility `engine` field is not a selected-run assertion: check `/config`, then the actual response. For Matterport SDK navigation, open `localhost`, whose configured browser domain is allowed. Heading alignment remains unverified; label scan navigation accurately.

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

1. Open `http://localhost:8000/app/`, show **LIVE** and the selected engine, and start **Warehouse handoff**. Use the exact saved scene text below. Talk over actual plan/scout events with the [pitch](pitch.md).
2. Let the automatic inside-out descent connect the property map, **Vexcel aerial** and **Matterport scan**, landing on the top card. Skip with a click or key if needed; **Replay descent** replays the presentation without a new scout. The measured component sequence was about **three seconds**, excluding scouting/preparation ([viewer acceptance](team/status-lane-d.md)). Reduced motion uses fades.
3. Read the actual skeptic objection and unknown shot-fit evidence. The previous deep warehouse result had a rail-proximity warning; a new result can differ. Proximity does not measure sound, and unknown room depth requires an on-site check.
4. Open **Look around**, pan the real scan and change **24 to 50 mm**. Press **D** only when **AI dressing** is offered, keeping **“AI-imagined set dressing, not the real room”** visible. Drag the comparison wipe; press **G** for a marked private frame grab if desired, then **Esc**. These controls are implemented in [the viewfinder](../web/viewfinder.js). Dressing is precomputed and tied to the selected scan point; absence is an honest optional state, never a reason to generate on stage.
5. Enter **Need parking for 5 trucks.** Keep the returned `thread_id`, show the changed rank/allocation and the actual response engine. The fixed refinement path retains the candidate pool without a new property/interior search ([pipeline](../agent/pipeline.py)). Keep the real source caveats visible.
6. Open `http://localhost:8000/director`, use the accepted grouped demo script, click **Build plan**, point to the scene/location/move summary, compare plans if useful, then **Play**. This is whole-script grouping within the retrieved pool, not measured travel savings. Count only the buildings and moves shown in that run.
7. Local-draft approval is optional outside the timed reveal. Click explicitly if demonstrating it, and show the saved, unsent state. Nothing here grants filming permission or delivers a message to an owner.

### Director grouping rehearsal

The authored default comes from the `DEMO` constant in [director.js](../index/director.js). **Pending stream 1 acceptance:** use the updated default only after its PR is human-merged and the assigned frames have been visually checked. Do not claim “all scenes at one location” until the live plan shows that coverage. Record the exact accepted text and summary here after that gate. The planner’s bounded search and one-visit-per-property move assumption are documented in [production.py](../index/production.py).

### What the dressing demonstrates

The real room stays available in the comparison. Atlas derives posed depth from its scan images and reuses those constraints for imagined furnishing ([pipeline](../worlds/dress.py)). This addresses consistent refurnishing; it does not certify measured geometry or buildability. Image dressing is the verified merged scope ([owner report](team/status-worlds.md)). Walkable splats are optional and unclaimed pending the owning session’s merged evidence. No World Labs generation belongs in this rehearsal.

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

The default city for an unnamed city is Los Angeles. Name Houston explicitly to select Houston. The API now emits a notice and returns `notes` with “No city named; searched Los Angeles. Name Houston to search there.” This was verified on actual city-free tune/test runs; both named Houston scenes also returned Houston properties in the live fixed/deep rehearsal. Check that the returned note is visible before promising its wording on screen. Do not claim that an unspecified scene searches both cities.

## Slow runs, Wi-Fi loss and failure states

| Situation | Operator action and wording |
| --- | --- |
| Cold CLIP/model initialization | Start and rehearse before judging. Previous cache-warm medians were **10.092 s fixed / 44.160 s deep** across five authored scenes ([retained rehearsal](team/eval.md#demo-refresh-after-v2)); use [stage evidence](team/status-lane-c.md) for the latest timings. The first deep request includes lazy process initialization. The separate post-change v2 fixed median **16.057 s** used fresh visual scores and no warmup; these are different measurements ([v2 report](team/eval.md#v2-after-changes-informed-by-v1)). |
| Deep fails or reaches its 90 s budget ([runtime](../agent/runtime.py)) | Leave the actual fallback event and fixed response label visible. Never call a fixed result a successful deep run. |
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

## Record the backup video

1. Rehearse the accepted viewer at 1440×900 and projector-like 1280×720. Confirm the exact scene, source/mode labels, main objection and follow-up. Confirm 20/5/5 and the current evidence before recording performance claims.
2. On macOS, use **Shift–Command–5 → Record Selected Portion** and select the app window area. Close terminals, credentials, personal contacts and unrelated tabs. Save locally under ignored `cache/submission/`.
3. Record one continuous take of at most two minutes using the beat sheet: main scene → real progress → frame/aerial/skeptic → five trucks → unsent local draft. Capture narration and readable labels. If showing retained footage, label it as recorded.
4. Watch the complete file locally: check audio, text size, image loads, actual engine/mode, the changed allocation and the unsent state. An interrupted or failed step should remain accurately described.
5. Keep the original recording private. A human confirms sponsor-media permission, chooses the final video and screenshot, adds the final links/Discord names, and submits. No video, licensed imagery or raw cache belongs in Git.

## Evidence locations and final handoff

- Public methodology: [evaluation](team/eval.md), [architecture](architecture.md), [Devpost draft](devpost.md).
- Private authored scenes/property anchors: `cache/demo-set.json`.
- Private historical timings and retained failures: `cache/demo-checks/final-comparison.json` and adjacent per-attempt directories.
- Private frozen v1 human run: `cache/evaluation/runs/20261114T190213Z/`.
- Private source coverage: `cache/vexcel/expanded-final-report.json`; exact indexed demo candidates: `cache/vexcel/expanded-demo-indexed-candidates.json`.
- Merged viewer/descent acceptance: [lane D report](team/status-lane-d.md). Combined judge-path and post-01:00 ET rerun: separate gates; retain private reports and human-approved media.
- Selected 20/5/5, frozen v1, separate v2 and current rehearsal: [evaluation](team/eval.md). Private current rehearsal audit: `cache/experiments/rerank-v2/demo-audit.json`; browser evidence: `cache/experiments/rerank-v2/browser/`.
- Team Discord names, public release/media approval, and any Peri/Photon/Amazon/ChatOverflow eligibility evidence: human completion required; see [track notes](devpost.md#track-evidence-and-human-completion).

Submission target from the event packet recorded in [START-HERE](team/START-HERE.md#event-evidence-and-uncertainty): **07:30 Eastern Sunday November 15**, ahead of the recorded **08:00 deadline**. Confirm live organizer changes before the human submits. The pitch and any optional video should fit two minutes.
