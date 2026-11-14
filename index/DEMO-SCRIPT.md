# Typecast Director: 2-minute judge demo

Track: Entertainment & Media. Hard cap: 120 seconds. One presenter drives, one watches the clock. Scenes are the `DEMO` text in `index/director.js` (kitchen, living room, bedroom) unless you load your own.

Framing (a design hypothesis, not a result): Typecast helps a producer judge earlier whether to adapt an existing room or build a set, using real indexed frames plus clearly imagined dressing. It makes no savings claim and does not claim it would have solved any particular production's search. A film-industry conversation is reported but unverified; do not mention it as endorsement or testing.

## Pre-demo checklist
- [ ] Server: `python -m uvicorn agent.app:app --host 127.0.0.1 --port 8771`; open `http://localhost:8771/director` on the integration captain's laptop with the real private cache. Check the data badge says LIVE/real, not MOCK.
- [ ] Warm the cache: press Build plan once and wait. Never demo a cold build. Re-measure timings yourself; teammate-reported timings are not ours.
- [ ] Pick ONE constraint beat and confirm it changes the plan today: Reject location, or raise Trucks until a property with a real insufficient-parking warning drops out. Unknown parking does not exclude a property. If neither changes the plan, cut the beat.
- [ ] Pre-stage the kitchen scene: two stand-ins and one dialogue line on take A.
- [ ] Take B choices (pick one honestly): a real model proposal ONLY if a provider is configured and tested on this laptop; otherwise the optional authored sample (see below).
- [ ] Chrome desktop, tab visible (WebM records in real time). Test Record reel (WebM) once and keep the file ready.
- [ ] AI dressing only if a real cached dressed set exists for the chosen frame, and only if it appeared when tested. Otherwise skip that beat.
- [ ] If showing Deep Agents, open a completed real trace in another tab; narrate only the calls visible. The live `plan_production_shoot` trace is unverified.
- [ ] Fallback screen recording saved privately and ready. Keep licensed images, joins and exports out of Git and public uploads.

## Run of show (120 s)
| Time | On screen | Spoken line | If it fails |
|---|---|---|---|
| 0:00-0:10 | Director, script visible | "A production has to decide: adapt a room that exists, or build a set. Typecast lets you stage the scene in real indexed rooms first." | Play fallback. |
| 0:10-0:25 | Build plan; rail shows property and frame per scene; open the one-line **Fit check** under the frame picker | "Real Matterport frames tied to CoStar properties. The fit check lists what the sources support and what is unknown. Visual similarity is not a fit score." | Point at the unknown labels. |
| 0:25-0:40 | Stage two stand-ins on take A, Play | "Blocking on the real frame. The badge is honest: screen-space rehearsal, geometric fit unknown." | Use the numeric fields. |
| 0:40-1:00 | Take B: genuine proposal (Generate alternative, show diff, Apply to B) OR the optional sample (below) | Genuine: "The model proposes, I review the diff, nothing changes until I apply." Sample: "No model here, so I load the authored sample alternative. It is pre-written blocking, not AI, and it is tagged that way everywhere." | If the provider errors, say it failed closed and use the sample button, naming it as the authored sample. |
| 1:00-1:15 | Compare A/B, press Play | "Both takes on the same frame. Durations differ, so the shorter one holds; the labels say so. Compare is a preview, not an export." | Skip if time is short. |
| 1:15-1:30 | The one confirmed constraint (Reject or Trucks), then optionally **Try another location** on that scene | "The owner says no. I reject this location and the plan rebuilds. Or I try another candidate in one click: my takes come along as a draft I must confirm on the new frame." | If the plan does not change, say it holds. If no alternative appears, say the pool has none. Never claim a change that did not happen. |
| 1:30-1:45 | Play the saved WebM, show Shoot pack (print preview of one scene's decision sheet) | "The shoot pack is now a decision sheet: the choice, both takes, open unknowns and an on-site checklist. It has no prices or permissions. Sample-derived takes carry the AUTHORED SAMPLE tag." | If recording fails, show the pack. |
| 1:45-2:00 | Optional: real AI dressing wipe, or the trace | "AI dressing is imagined and labelled so; the real room stays one click away." Only if tested with the real cache. | Close at 1:45 on the stage. |

## Optional continuity beat (skip unless time remains)
Only scenes you tag with the same "Continuity link" (Shot panel, Production notes) are compared; nothing appears otherwise. Say: "Link two scenes as one setting and Typecast flags a provable mismatch, such as different properties, and only suggests a fix." Do not present it as vision analysis.

## Optional AUTHORED SAMPLE fallback
In the AI take tab the button "Load authored sample alternative" appears next to Generate. It never calls a model, ignores the direction text, derives a mirror-and-cross from take A (or one generic performer), goes through the same review, and Apply writes only B. The brainstorm API still returns 503 without a model; the sample is never substituted automatically. Say "authored sample, not AI" out loud.

## Words and claims we do not use
- No "shootable", "verified location", "3D", "collision", "accurate fit", "measured clearance", "optimal" (outside "within this candidate pool").
- No savings, ROI or time-saved figures, and no overall suitability score or percentage: the fit check lists conflicts and unknowns only. No claim that Typecast would solve any specific production's location search.
- No filmmaker endorsement, consultation or user-testing claim, and no attributed quote. Peri, Photon and other eligibility are not claimed.
- No retrieval numbers unless asked; keep generations separate (see `docs/team/eval.md`); the expanded v2 review was not a fresh holdout and was not reproduced by root.
- Do not call the planner, status text, proposal card or authored sample an agent trace or AI.
- No audio claims; the reel is silent. Camera numbers are assumed heading 0, unverified.

## Likely judge questions
1. **Do the actors fit?** We don't know and the stage says so: 2D rehearsal on the frame; room figures are index estimates.
2. **What does the AI decide?** Retrieval ranks real frames, a bounded solver groups scenes, a language model may propose blocking you review, and AI dressing is an imagined appearance from a cached run, always labelled.
3. **Would a production use it?** Unknown; an informal conversation with a filmmaker is reported but not a test. The hypothesis is earlier adapt-versus-build judgment.
