# Typecast Director: 2-minute judge demo

Track: Entertainment & Media. Hard cap: 120 seconds. One presenter drives, one watches the clock.
Script scenes are the `DEMO` text in `index/director.js`: kitchen, living room, office corridor.

## Pre-demo checklist (do all of these before judges arrive)

- [ ] Server running: `python -m uvicorn agent.app:app --host 127.0.0.1 --port 8771`; studio open at `http://localhost:8771/director`.
- [ ] Warm cache: press Build plan once with the demo script and wait. The root integrator observed 24.66 s cold and 2.69 s for a warm request plus replan (single observations, `DIRECTORS-ROOM.md`); re-measure on the demo laptop. Never demo a cold build.
- [ ] Decide the ONE constraint replan and confirm it on this machine today:
  - Option R (Reject): select a scene, press Reject location, confirm the rejected property is gone and a different property or frame appears for that scene.
  - Option T (Trucks): raise Trucks until a property whose Vexcel parking is known to be insufficient becomes ineligible and the plan changes. Unknown parking does NOT exclude a property, so Option T only works if a real `insufficient` warning exists in the warm data.
  - Write down which option changed the plan and what changed. If neither changes the plan, cut the beat and say nothing about replanning.
- [ ] Pre-stage the kitchen scene: two silhouettes on variant A with a start and end point and one line of dialogue. Keep B blank or different.
- [ ] Brainstorm provider configured (text was verified; 4.82 s single observation). Type the instruction. Use the mic only if permission was granted earlier and tested on this laptop; otherwise skip it.
- [ ] Chrome desktop, current version, studio tab in front and visible. WebM recording runs in real time and may fail or stall if the tab is hidden.
- [ ] Do one test of Record reel (WebM) and open the file. An actual silent 1280×720, 4.921 s reel with a real frame and moving Mara was downloaded and played. Recheck on the demo laptop; keep a recorded file ready because recording takes real time.
- [ ] If showing Deep Agents, open an actual completed trace in a separate tab. The shared `plan_production_shoot` tool is implemented and fake-model graph tested, but a live trace of this new tool is not yet verified. Only narrate the calls actually visible in the chosen trace.
- [ ] Fallback screen recording of this whole demo saved locally and opened in a paused player.
- [ ] Close other tabs and notifications. The user authorized licensed imagery in this judged demo; keep private bundles and licensed-image exports out of public Git and public uploads.
- [ ] Optional Look around beat: lens, aspect ratio, drag, frame grab and reopen were browser verified. Describe the four-face view as scan-relative; its 6 m depth illustration is assumed.
- [ ] Project JSON export is verified. Import has 29 pure tests, but browser import is unverified after extension upload was blocked; do not promise a demonstrated round trip.

## Run of show

| Time | On screen | Spoken line | If it fails |
|---|---|---|---|
| 0:00-0:10 | Studio, demo script visible, stage dark | "Directors pick locations from photos and hope the scene works there. Typecast lets you watch your script play in real rooms before you book one." | Start the fallback video and narrate over it. |
| 0:10-0:22 | Press Build plan. Plan selector fills; scene rail shows a property and frame per scene | "Three scenes in, and the planner returns candidate plans: which properties cover which scenes, and how many company moves. These are candidates, chosen from a small retrieved pool." | If the plan stalls past 10 s, switch to the fallback video at 0:22. |
| 0:22-0:35 | Click the kitchen scene. Point to Evidence: Matterport frame, CoStar property, Vexcel logistics, source warnings | "The frame is a real indexed Matterport view, tied to a CoStar property. The logistics panel uses Vexcel evidence when supplied; missing availability or parking stays unknown." | If a field is missing, point at the unknown label; that is the intended behavior. |
| 0:35-0:50 | Stage: two silhouettes on variant A. Drag one start point, press Play | "This is blocking. Generic figures, start and end marks, timed to the shot. The badge is honest: it's a screen-space rehearsal, and geometric fit is unknown." | If dragging misbehaves, use the numeric x/y fields. |
| 0:50-1:08 | Type: "Try her entering from the window side, slower." Generate alternative. Proposal card shows the diff. Press Apply to B, then toggle A and B | "I ask for an alternative. The model proposes a change and shows me the diff. Nothing moves until I apply it. A stays as it was; B is the new take." | If the provider errors, say "It fails closed, no change was made," and move on. |
| 1:08-1:25 | The one verified replan (R or T from the checklist). Plan updates; frame-change notice appears if staging existed | Option R: "Say the owner says no. I reject this location, and the plan rebuilds without it." Option T: "Now we need two trucks. The property with too little estimated parking drops out and the plan changes." Then: "My staging stays on the old frame until I choose to copy it." | If the plan does not change, say "Same plan holds under this constraint," and continue. Never claim a change that didn't happen. |
| 1:25-1:40 | Play the short saved WebM, then show Shoot pack; record live only if the prepared shot durations fit the clock | "Here's the whole sequence played back, and I can record it as a silent WebM in Chrome. It records in real time. The shoot pack is a static page with each frame, the staging and every source warning." | If recording is unsupported or fails, say "Recording isn't supported here; the shoot pack still exports," and click Shoot pack. |
| 1:40-1:55 | If available, SWITCH to the separate actual Deep Agents trace and point only to visible calls | "This is the actual agent trace. These are the tools and source checks it performed." Mention `plan_production_shoot` only if that live call is visible; otherwise describe the shown scout flow separately. | If the trace window fails, skip this beat and close at 1:40. |
| 1:55-2:00 | Back to the studio stage, reel paused on the kitchen frame | "Typecast: rehearse the scene in real rooms, then take the plan to the scout." | None. Stop at 2:00. |

## Words and claims we do not use

- No "shootable", "verified location", "3D", "collision", "accurate fit", "measured clearance", "optimal" (outside "within this candidate pool").
- No retrieval numbers unless asked. Keep generations separate: original 608-view held-out pooled recall@10 38.9% cosine / 30.5% diverse; expanded v2 PR #27 reports 73.33% precision lower bound and 30.48% macro recall. The v2 review repeated the same reviewer, not a new holdout, and root did not reproduce it. See `docs/team/eval.md` for sampled-pool limits.
- Do not call the planner, status text or proposal card an agent trace. The Deep Agents segment needs an actual trace; implementation and fake-model tests do not establish a live call.
- No music, soundtrack or audio claims. The reel is silent.
- No filmmaker endorsement or user testing claims. None has happened.
- No claim of Peri, Photon, Capital One, Arlequin or Physical AI eligibility.
- No availability, price, permit or drive-time claims. Company moves count property visits only.

## Likely judge questions

1. **"How do you know the actors fit in the room?"** We don't, and the stage says so. The figures are a 2D rehearsal on the image; room size and ceiling come from the index separately and are marked as estimates.
2. **"What does the AI actually decide?"** Retrieval ranks real frames against each scene, a bounded solver groups scenes into fewer properties, and a language model proposes blocking alternatives that you review before applying. The deep-agent scout run is a separate flow with its own trace.
3. **"Would a real production use this?"** We haven't tested it with a filmmaker yet. The intended use is early pre-production on student and indie shoots, before anyone pays for a scout visit.
