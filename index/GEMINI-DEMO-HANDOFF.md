# Demo handoff (Gemini draft, Claude-corrected)

Authorship: first draft by Gemini (`manager-drafts/gemini-demo-handoff.md`), written from supplied `director.html` and demo notes with no repo execution. Technical review by Claude against code at head 6823f6d (static reading of `index/director.html`, `index/director.js`, `web/viewfinder.js`, `agent/app.py`, docs). Nothing here was run in a browser, and no private data was read. Companion docs: `index/DEMO-SCRIPT.md`, `index/DIRECTORS-ROOM.md`, `docs/team/status-worlds.md`.

## Corrections to the Gemini draft

| Draft said | Actual |
|---|---|
| Raising `#trucks` then "observe the plan update" | Trucks, Cars, Max locations and Require available are read only when **Build plan** (or Reject, which replans) runs. There is no change listener. After changing a vehicle count, click **Build plan**. Only a Vexcel `insufficient` warning excludes a property; `unknown` parking does not. |
| Dressing toggle on `#stage`/`#framePicker` | Not on the Director actor stage. AI dressing lives in the scan **viewfinder**: select a scene, click **Look around the scan** (`#lookAround`), then the "AI dressing" button (key `D`) appears **only if** `/api/dressed/{shot_id}` has a set for that exact scan point. `docs/team/status-worlds.md` reports sets for the top pick of 5 demo scenes on that machine's cache; whether the demo laptop has one for the chosen frame is unknown until checked. It is AI-imagined (badge: "AI-imagined set dressing, not the real room") and is not the actor stage. `TYPECAST_ENABLE_DRESSED=0` disables it. |
| "Commercial properties" | The expanded index covers mixed types: available commercial plus 20 available Multifamily (`index/README.md`). Say "indexed properties", not "commercial offices". Kitchen/living-room scenes may legitimately resolve to Multifamily. |
| `2.69 s` warm / `24.66 s` cold as dataset benchmark | Single observations on an earlier machine/cache: cold two-scene plan 24.66 s; warm plan plus replan 2.69 s (`DIRECTORS-ROOM.md`, `status-lane-a.md`). Not measured on the 343-property cache, not percentiles. Re-time on the demo laptop; say nothing numeric if not re-measured. |
| `reel/downloads` folder | No such path exists in the repo. The reel is whatever file **Record reel (WebM)** (`#expReel`) downloaded in the browser; keep your own recording and open it first. |
| 343 properties / 10,568 views as verified | Reported by the data owner (`index/README.md` private expansion note); not reproduced by this review. Do not state as tested here. |
| Amazon "deterministic caching", "multi-modal catalog" | Unsupported framing. Amazon fit per `PRIZE-READINESS.md` is the practical scout/rehearsal workflow; no AWS or caching claim. |
| `#frameNotice` always appears after replan | Only when staging existed on the old frame and the new assigned frame differs. |
| Mic/import/trace | Unchanged: microphone, browser file-picker import and a live `plan_production_shoot` trace are all unverified. |

Kept from the draft: pre-flight discipline, one replan beat, fail-closed narration, forbidden-words list.

## Real vs imagined vs 2D (say this distinction out loud)

- **Real:** indexed Matterport frames; CoStar/Vexcel facts only where supplied; unknown stays "unknown".
- **2D rehearsal:** Director actors are generic screen-space figures, badge "UNCALIBRATED SCREEN-SPACE REHEARSAL · GEOMETRIC FIT UNKNOWN". No collision, scale or fit claim.
- **AI-imagined:** viewfinder dressing only; real scan shown beside it; never in the shoot pack as fact.
- **Traces:** only an actual completed Deep Agents trace tab counts. Planner status, proposal card and progress text are not agent traces; `plan_production_shoot` is named only if that call is visible.

## Actual click sequence (as coded)

1. `/director` → **Demo script** (if empty) → **Build plan** (warm it first).
2. Click the kitchen scene in the Scenes list; read Evidence.
3. Variant A on stage: drag a start point / end ring (or `x0,y0,x1,y1` fields) → **Play**.
4. Instruction box → **Generate alternative** → read diff → **Apply to B** → toggle A/B. (**Undo apply** exists.)
5. One replan, verified beforehand: **Reject location** (replans automatically) **or** change Trucks/Cars → **Build plan**.
6. Optional, only if verified for that frame: **Look around the scan** → "AI dressing" (D) → wipe → close.
7. Open the saved WebM in a player, then **Shoot pack**. Live **Record reel** only if durations fit and the tab stays visible.
8. Optional separate real trace tab.

## Practical 2-minute run

0:00 script on screen (10s) · 0:10 Build plan on warmed cache, 12s · 0:22 kitchen + Evidence, point at one `unknown`, 13s · 0:35 drag actor, Play, state the badge, 13s · 0:48 instruction → Generate → diff → Apply to B → A/B, 22s · 1:10 the one verified replan (Reject, or Trucks + Build plan), 15s · 1:25 saved WebM then Shoot pack, 15s · 1:40 **either** Look around + dressing (≤15s, only if verified) **or** real trace tab; not both unless time allows · 1:55 close on the stage. Hard stop 2:00. Cut any beat not verified that day; never narrate a change that did not occur.

## Human/demo checks (exact, on the demo laptop)

- [ ] `python scripts/verify.py` passes on that checkout; `git rev-parse HEAD` recorded.
- [ ] Re-time cold and warm Build plan on the real cache; discard the old 24.66/2.69 s numbers unless matched.
- [ ] Open Evidence for each demo scene: record property type, availability, Vexcel parking status as shown (not assumed).
- [ ] Decide replan: try Reject; else raise Trucks, click **Build plan**, confirm a property actually drops with a real `insufficient` warning. Else cut the beat.
- [ ] For the chosen frame, click Look around: does the "AI dressing" button appear? If not, no dressing beat.
- [ ] Record reel once, open the downloaded file; save a fallback full-run recording.
- [ ] Project JSON import through the real file chooser (unverified); microphone test (unverified). Skip both on stage if untested.
- [ ] Deep Agents trace: open a genuinely completed one; list only calls visibly present.
- [ ] Sponsor permission before showing licensed imagery anywhere public; nothing from `cache/` goes to Git or uploads.
