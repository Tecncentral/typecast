# Director's Room: approved build scope

Status: design approved by Claude, Gemini and Grok Bot on November 14. The standalone Owner 1 studio is implemented and browser-checked. Shared Deep Agents/tool integration remains an Owner 3 handoff; do not present the deterministic planner as a Deep Agents run.

The creative promise is to rehearse a scene in real candidate locations before committing to a shoot. Directors can compare two staging alternatives, move generic characters over a real frame, play timed shots and reject a location to rebuild the plan. Voice brainstorming proposes an alternative for review; it never silently edits the active take.

## Council decisions

- Claude: prioritize the location animatic, reject/replan and usable shoot pack. Export is core; voice is the last step. Keep the rehearsal separate from metric geometry.
- Gemini: approved after withdrawing its initial requirement to constrain image-space actor paths with room metrics. The source image-to-world mapping is unverified; that constraint would fabricate precision. Validate every generated proposal.
- Grok Bot: approved with source-linked logistics decisions and honest sponsor claims. Its initial blanket runtime-API condition does not supersede individual rules: Amazon permits any AI stack, and licensed cached CoStar inputs are valid data use. Actual API integration is necessary where a particular prize requires it.
- All three: at most three generic silhouettes, two variants, linear start/end motion, durations and dialogue. Cut 3D registration, occlusion, lip sync, general music remixing and acapella separation from this milestone.

## Acceptance gates

1. Real retrieval produces candidate frames with exact model/property identities. The bounded multi-scene solver can re-plan after a rejected property; optimality is only within the selected pool. No invented availability, geometry, prices or transport times.
2. The stage says **uncalibrated screen-space rehearsal**. Actor placement is creative illustration, not measured clearance. Separate room/FOV planning preserves its own estimated/unknown status. A/B edits remain independent and survive playback/export.
3. CoStar and Matterport must visibly affect the same production decision; aim to include Vexcel as a third layer. Explicit availability can filter properties, actual image similarity ranks views, and source-backed parking warnings affect logistics. Unknown parking is not a certified capacity. Decorative badges do not satisfy this gate.
4. A brainstorm request returns a validated alternative. Apply changes a selected take; Discard leaves it unchanged. A late response cannot edit a different scene. Text remains available if microphone support fails.
5. Export includes the selected creative staging and provenance/unknowns. Keep all licensed images and joins local or in authorized team delivery. Do not commit generated shoot packs containing licensed imagery.
6. Demonstrate real Deep Agents tool progress separately; never label the deterministic solver or generated UI notices as an agent trace. Record a fallback demo and measure actual latency.

## Prize targets

Entertainment & Media is the one main-track target. CoStar, Amazon and LangChain are the recommended sponsor targets, subject to the actual submission opt-ins and final demonstrated implementation. Photon remains conditional on confirmed guidelines and a working live channel. Other prizes require their own substantive implementation and evidence; assistant use alone is not Gemini API use.

The detailed current eligibility audit is delivered separately. Use the earlier hard deadline of 08:00 Eastern on November 15, despite the public schedule's conflicting 08:30 display. Reserve the final 90 minutes for submission and rehearsal.

## Past-winner inspiration

These are primary Devpost award records, not predictions of judging preferences:

- [Someone Save Us](https://devpost.com/software/faaah), Spring 2026 Entertainment & Media winner: a visible cooperative world reacts to user actions. Our inference: demonstrate a meaningful creative change, not a list of integrations.
- [Lume](https://devpost.com/software/lume-zrlypk), Fall 2025 Education + Entertainment winner: spoken intent leads to visible guidance. Our inference: voice should change the director's actual scene through a clear review step.
- [4Desmos](https://devpost.com/software/4desmos-visualize-4d-in-vr), Spring 2025 Entertainment + Education winner: direct visual manipulation makes an abstract idea explorable. Our inference: character staging and playback should make scene alternatives tangible.

No guaranteed win or comparative score follows from these examples.

## Run and integrate

From this checkout, install the existing lockfile and the Owner 1 encoder requirements. Keep the private index, property/model mapping, optional richer join and Vexcel cache in ignored `cache/`. Use existing private `.env` values; the preview now loads that file without overriding shell variables.

```powershell
python -m uvicorn index.preview:app --host 127.0.0.1 --port 8765
```

Open `http://localhost:8765/director`. The original scout remains at `/`, with a link to the studio. The planner accepts at most eight scenes, 24 pooled properties and four locations. The pool uses the first three retrieved properties per scene; optimum claims apply only inside that pool. Manual frame selection stays within an assigned property and explicitly preserves the original plan score.

Text brainstorming uses the existing `agent.models` structured provider (`LLM_API_KEY`, `TYPECAST_LLM_PROVIDER`, `TYPECAST_LLM_MODEL`). Keys never reach the page. Only user scene text and normalized rehearsal state go to that provider. Browser speech recognition is optional, starts only on a click, and may process audio through the browser's speech service. Microphone capture has not been verified on stage; text input was verified.

Owner 3: expose `production.router` through the shared app, provide the existing indexed `/image/{shot_id}` and separate `/api/plan/{shot_id}` endpoints, and have an actual Deep Agents tool call the bounded planner before claiming the new planner is agent-driven. Owner 4: link or incorporate the studio; preserve proposal Apply/Discard, source labels and frame-change review. New models live in `index/production.py`, so no shared contracts changed. No dependencies were added.

## Verification on this machine

- Full existing gate: **363 passed, one skipped**, smoke, concurrent-progress/cached-refinement/no-send E2E and 20/20 mock evaluation attempts. Mock attempts are not human retrieval accuracy. Production/join/solver tests: 73 passed, using synthetic data and provider fakes.
- Real local two-scene planner: HTTP 200; cold request 24.66 s. A warm initial request plus reject/replan took 2.69 s; the rejected property was absent from all returned plans. These are single observations, not latency percentiles.
- Real structured text brainstorm: HTTP 200 in 4.82 s, two actors, validated changed proposal. Browser proposal review left A unchanged; Apply stored the alternative in B.
- Browser: real three-scene plan, A/B independence, actor editing, timed playback, pause/reset, rejection and an explicit frame-change review notice. When a location changes, staging stays on the old frame until the director chooses to copy or start fresh.
- Actual downloads: project JSON preserved separate A/B takes; a three-scene shoot pack contained six embedded source/staged images. Checks found no scripts, API keys, raw provider rows or private cache/filesystem paths. The HTML pack is a static shoot document; live animation runs in the studio. Video rendering and photorealistic generation are not implemented.

## Remaining limitations and human actions

The supplied local join has 11 columns and does not satisfy the newer market metadata adapter. Exact property/model matching uses the valid supplied mapping; richer availability fields and local Vexcel logistics remain unknown here. Obtain the updated private bundle from Owner 2 to demonstrate availability/parking filtering; do not infer missing values. The original 608-view human evaluation is complete, but it does not establish accuracy for the expanded generation or filmmaker validation.

Before submission: integrate and demonstrate the real Deep Agents path, rehearse microphone behavior or use text, record a short fallback demo, confirm actual sponsor opt-ins, fill team/Discord names and submit before the earlier 08:00 deadline. Peri consultation, Photon live transport and other unimplemented integrations are not eligible claims. The public repository receives code/docs only; generated licensed-image packs stay private.
