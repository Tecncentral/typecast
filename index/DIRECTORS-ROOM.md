# Director's Room: approved build scope

Status: implemented in the shared app with the full viewer. Commit `5da12ac` exposes the production planner and adds the actual Deep Agents tool `plan_production_shoot`; a fake-model graph test verifies dispatch. A live trace of this new tool has not yet been demonstrated. The deterministic planner UI alone is not a Deep Agents run.

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
5. Export includes the selected creative staging and provenance/unknowns. Licensed images may be shown in the user-authorized judged demo. Keep joins, generated licensed-image packs and private bundles out of the public repository and public uploads.
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
python -m uvicorn agent.app:app --host 127.0.0.1 --port 8771
```

Open `http://localhost:8771/director`; the integrated viewer is at `/app/`. The shared app serves the production endpoints, indexed images and separate metric planner. The planner accepts at most eight scenes, 24 pooled properties and four locations. The pool uses the first three retrieved properties per scene; optimum claims apply only inside that pool. Manual frame selection stays within an assigned property and explicitly preserves the original plan score.

Text brainstorming uses the existing `agent.models` structured provider (`LLM_API_KEY`, `TYPECAST_LLM_PROVIDER`, `TYPECAST_LLM_MODEL`). Keys never reach the page. Only user scene text and normalized rehearsal state go to that provider. Browser speech recognition is optional, starts only on a click, and may process audio through the browser's speech service. Microphone capture has not been verified on stage; text input was verified.

Shared integration and the full viewer are merged. Director also opens the scan viewfinder through Look around. Preserve proposal Apply/Discard, source labels and frame-change review when extending either surface.

## Verification on this machine

- Browser verified: real multi-scene plans, independent A/B staging, actor editing, timed playback, pause/reset, rejection and explicit frame-change review. A reviewed real text proposal applied to B while A stayed unchanged. Microphone capture remains unverified.
- Actual downloads: project JSON retained both variants; the static shoot pack embedded source/staged images and warnings. A silent WebM was downloaded and played at **1280×720, 4.921 s**, with a real room frame and moving Mara. This is a browser recording of the 2D rehearsal.
- Scan viewfinder: browser verified lens, aspect ratio, drag, frame grab and close/reopen. Four horizon cube faces were checked. Headings are scan-relative, not world bearings; the depth/FOV illustration assumes **6 m**, not measured room depth. Unscanned floor/ceiling are not invented.
- Project import: **29 pure tests** cover validation, exact-frame restoration and retained drafts after replacement. Actual browser import remains untested because extension file upload was blocked; export success does not establish import success.
- Grok audit regressions now pass for rejected locations in faulty replan responses, unknown evidence displayed as factual availability/parking, unsafe provenance identifiers and negative-time interpolation. The progress bar remains a display-only indicator. Reel, project and viewfinder regression suites also pass; final integrated gate: 539 passed, one skipped, smoke, fixture E2E and exact-code-head CI passed.
- Prior single-request observations: cold two-scene plan 24.66 s; warm plan plus replan 2.69 s; structured text brainstorm 4.82 s. These are not latency percentiles. Shared `plan_production_shoot` dispatch has a fake-model graph test, with no live new-tool trace yet.

## Remaining limitations and human actions

The older local join has 11 columns and lacks the richer availability adapter fields and local Vexcel cache. Exact property/model mapping is checked separately; missing availability and logistics remain unknown. PRs #12/#21 contain no private bundle link; PR #21 explicitly locates the data on Owner 2's laptop. Discord checked: the integration captain's 14 November 15:01 Eastern reply about PR #21 says the expanded private index/Vexcel caches and final demo are on that teammate's laptop. The reported inventory is 343 properties, 10,568 views, 327 available indexed properties, Vexcel caches for 344 properties and nine available demo properties. These are teammate-reported counts, not a local reproduction. A second copy is unnecessary for the planned demo; pull this lane on the demo laptop and verify its current data there. This local checkout retains the older 11-column join and no Vexcel cache.

Human labeling is complete; no further labeling is required. Keep the original 608-view benchmark separate from expanded evaluations. PR #27 reports expanded v2 precision lower bound **73.33%** and macro recall **30.48%**, using repeated review by the same reviewer rather than a new holdout. Root did not reproduce those results. These sampled-pool retrieval measurements do not establish general accuracy, Director/solver quality or filmmaker validation; see `docs/team/eval.md` for methodology and limits.

Before submission: demonstrate a real `plan_production_shoot` trace if claiming that new agent path, rehearse microphone behavior or use text, verify browser project import when file upload is available, record a short fallback demo, confirm sponsor opt-ins, fill team/Discord names and submit before the earlier 08:00 deadline. Peri consultation, Photon live transport and other unimplemented integrations are not eligible claims. Public Git and public uploads receive code/docs only; the judged demo may show the authorized licensed imagery.
