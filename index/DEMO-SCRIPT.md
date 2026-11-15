# Typecast Director: 2-minute judge demo

Track: Entertainment & Media (sponsor slate: CoStar, LangChain Deep Agents, Amazon; Peri conditional on event-time consultation evidence). Hard cap: 120 seconds. One presenter drives, one watches the clock. Scenes are the `DEMO` text in `index/director.js` (kitchen, living room, bedroom) unless you load your own.

Framing (a design hypothesis, not a measured result): Typecast helps a producer judge earlier whether to adapt an existing room or build a set, using real indexed frames, real source constraints, and clearly labeled 2D rehearsal or cached AI dressing. It makes no savings claim, no win guarantee, and no filmmaker endorsement claim.

## Pre-demo checklist (integration captain's laptop)
- [ ] Server: `python -m uvicorn agent.app:app --host 127.0.0.1 --port 8771`; open `http://localhost:8771/director` on the integration captain's laptop with the real private cache. Verify the top badge shows `LIVE DATA` (never present synthetic QA interception as real API proof).
- [ ] Warm the cache: press **Build plan** once and wait. Never demo a cold build. Re-measure timings yourself; teammate-reported numbers are not ours.
- [ ] Precheck the **Save the scene** constraint on the captain's real dataset today: test `5` trucks ONLY if a real alternative is verified in that cache; otherwise precheck a `cars` or **Require an available listing** constraint that the dataset actually supports. Know in advance whether it yields a real alternative or an honest no-result.
- [ ] Pre-stage the kitchen scene (`s1`): two stand-ins and one dialogue line on Take A.
- [ ] Take B choice (pick one honestly): a real model proposal via **Generate alternative** ONLY if a provider is configured and tested on this laptop; otherwise use **Load authored sample alternative** (`AUTHORED SAMPLE · not AI`).
- [ ] Chrome desktop, tab visible (WebM records in real time). Test **Record reel (WebM)** once and keep the saved file ready.
- [ ] AI dressing only if a real cached dressed set exists for the chosen frame and appeared when tested; otherwise skip that beat.
- [ ] If showing Deep Agents (LangChain), open a genuinely completed trace in a separate tab; narrate only visible tool calls. The Director `/director` solver and **Save the scene** are deterministic planner flows, not an agent trace, and a live `plan_production_shoot` trace is unverified.
- [ ] Save a local fallback screen recording privately. Keep licensed images, joins, and exports out of Git and public uploads.

## Run of show (120 s — Primary Film Flow)
| Time | On screen | Spoken line | If it fails |
|---|---|---|---|
| 0:00–0:10 | Director open in **Film production** mode, script visible | "A production has to decide: adapt an existing room or build a set. Typecast lets you block the scene in real indexed rooms and test real logistics constraints before paying for a scout." | Start the private fallback recording and narrate over it. |
| 0:10–0:22 | Press **Build plan**; rail shows property and frame per scene; open **Fit check** | "Real Matterport frames tied to CoStar properties and Vexcel logistics. The fit check separates visual similarity from source facts—and unknowns stay unknown." | Point directly to the `Unknown` labels. |
| 0:22–0:36 | Stage two stand-ins on Take A, press **Play** | "Screen-space blocking on the real frame. The badge stays honest: uncalibrated screen-space rehearsal, geometric fit unknown." | Use the numeric `x0, y0, x1, y1` fields. |
| 0:36–0:52 | Take B: **Generate alternative** (diff → **Apply to B**) OR **Load authored sample alternative**, then **Compare A/B** | Genuine: "The model proposes a blocking diff; nothing moves until I apply it to Take B." Sample: "Without a live model, I load the pre-written authored sample—explicitly tagged not AI—and compare A and B side by side." | If provider errors, state it failed closed and use the authored sample button. |
| 0:52–1:18 | Click **Save the scene** on Scene 1; enter the prechecked constraint (`5` trucks if verified on real cache, else supported cars/available listing); click **Find an alternative**; inspect Before/After; click **Apply alternative** | "Now we add a real production constraint with **Save the scene**. Typecast re-plans across the pool—unknown capacity never counts as met—shows the exact before-and-after differences, and only updates when I click **Apply alternative**. Both takes stay preserved as unreviewed drafts." | Honest fallback: if the dataset has no satisfied candidate, read the honest non-result ("unknown capacity is not treated as met, original kept") and continue without claiming a change. |
| 1:18–1:33 | Toggle Take A/B on the new frame, expand **Saved decision (historical record)** in Fit check, and note **Undo Save the scene** | "Both takes carry over to the new frame for review, and the decision is logged as a historical record—not an approval or an agent trace—with full one-click Undo." | Skip Undo click to keep momentum; show the historical record card. |
| 1:33–1:48 | Play the saved silent WebM reel, then open **Shoot pack** print preview showing both takes and the decision sheet | "The silent WebM exports the active take in real time, and the printable Shoot pack exports both takes, every source warning, the historical decision sheet, and an on-site verification checklist." | If WebM playback stalls, show the Shoot pack HTML/PDF directly. |
| 1:48–2:00 | Optional: real cached AI dressing wipe in **Look around 360°** OR separate completed Deep Agents trace tab; close on stage at 2:00 | Dressing: "AI set dressing is clearly labeled imagined, with the real scan one click away." Trace: "In a separate tab is an actual completed Deep Agents scouting trace." | Close cleanly on the stage at 1:48 if neither is pre-verified on this laptop. |

## Optional community extension (20 s max, only if judges ask about public benefit; never replaces the film flow)
Click **Community planning** (`Save the scene` is hidden in Community mode), click **Load example needs**, click **Find candidate sites**, and open the **Site** tab:
- **Say:** "The same indexed frames and source evidence can support pre-incident volunteer and supply coordination. Every coordinator check starts unknown, requested headcount is never treated as room capacity, and the printable Site Brief lists everything still unverified."
- Show the printed Site Brief only if asked. Never describe it as evacuation or emergency routing, never claim any organization uses it, and switch back to **Film production** afterward (your film work remains intact).

## Safety net & fallbacks
- **Local draft recovery:** Reloading restores each mode's script, constraints, takes, and historical decisions from browser storage and rebuilds fresh evidence from `/api/production/plan` (re-enabling **Save the scene** once loaded).
- **Authored sample fallback:** Next to **Generate alternative**, **Load authored sample alternative** works offline without calling a model and tags outputs `AUTHORED SAMPLE · not AI`.

## Words and claims we do not use
- No "shootable", "verified location", "collision", "accurate fit", "measured clearance", "optimal" (outside "within this candidate pool"), or claiming 3D registration, occlusion, or measured geometry for 2D stand-ins.
- No savings, ROI, or time-saved claims, and no overall suitability percentage or score. Carried-over takes are "aligned by eye" after review, never "measured fit".
- Never present synthetic QA interception (`qa_save.py`) as real API proof, and never call the deterministic planner or **Save the scene** a Deep Agents trace.
- No filmmaker endorsement or user-testing claims; no Peri eligibility claim without documented consultation evidence, and no Photon eligibility claim without verified live channel/rules.
- No audio claims (the WebM reel is silent). Camera metrics assume heading `0°` and are unverified.

## Likely judge questions
1. **Do the actors physically fit in the room?** We don't know, and the stage states `Geometric fit: unknown`. Stand-ins are 2D screen-space blocking proxies; room dimensions in Evidence are index estimates to verify on site.
2. **What happens if parking capacity is unknown when you require 5 trucks?** Unknown is never treated as met. **Save the scene** refuses to propose an alternative with unknown parking for a positive vehicle request and leaves the original plan untouched.
3. **Where is the AI versus deterministic code?** Retrieval ranks real frames, the bounded solver groups scenes into plans, **Save the scene** deterministically compares revised solver plans, an optional LLM proposes Take B diffs that require explicit Apply, and Deep Agents runs a separate multi-agent scouting flow with its own trace.
