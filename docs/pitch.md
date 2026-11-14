# Typecast: two-minute pitch

This is an authored rehearsal plan, not a recorded performance result. Use **Warehouse handoff** on the warmed stage server. The previous selected-default warehouse run took **38.286 s deep / 8.550 s fixed** ([retained rehearsal](team/eval.md#demo-refresh-after-v2)); replace the timing assumption with the latest [stage report](team/status-lane-c.md) before judging. Keep the actual engine, source mode and real progress visible.

## Two-minute beat sheet

The reveal is the same space: property → aerial → real room → imagined dressing. The times below are speaking targets, not measured feature latency.

| Time | Screen/action | Spoken script |
| --- | --- | --- |
| **0:00–0:10** | Select **Warehouse handoff** and start immediately. | “What can this space play? A film needs a warehouse for a handoff. Typecast casts a real building for the scene—and checks whether the crew can work there.” |
| **0:10–0:42** | Talk over the actual plan and scout events. | “The director plans. CoStar checks property identity and marketed availability. Matterport supplies real interior views. Vexcel supplies the aerial and estimated parking. The scouts combine them, and a skeptic challenges the result. Missing measurements stay unknown.” |
| **0:42–0:53** | Results arrive: let the automatic descent land on the top card. If already complete, use **Replay descent**. | “One property, outside and in. The aerial becomes the actual scanned room. This is a real scanned place to inspect.” |
| **0:53–1:13** | Open **Look around**. Pan, rack from **24 to 50 mm**, then press **D** only if AI dressing is offered. Leave the honesty badge visible; drag the wipe briefly. | “Compose the camera view. Now imagine the set dressing. Atlas uses depth derived from this scanned room to constrain the restyle. This is AI-imagined dressing, not the real room—and not a promise that an art department can build it.” |
| **1:13–1:31** | Press **G** for an in-app private frame if useful, **Esc**, then **Need parking for 5 trucks.** Preserve the thread. Point to the changed rank/allocation and an actual skeptic caveat. | “Now we need five trucks. The same candidates are reconsidered against one parking budget. The objection stays visible: access, noise and physical fit still need a recce.” |
| **1:31–1:44** | Open `/director`, **Build plan**, show scene/location/move summary, then **Play**. Use the accepted script in the runbook. | “For a whole script, the Director's Room groups scenes into fewer buildings. Compare company moves with visual similarity before moving the crew.” |
| **1:44–2:00** | End on the plan or source-backed shortlist. | “Our post-change test reached a seventy-three-percent precision lower bound across fifteen scenes reviewed by one person. It is a repeat, not a new holdout. Typecast gives a location manager real places to inspect—and a clear line between evidence and imagination.” |

Lens controls and the D/G shortcuts come from [the viewfinder](../web/viewfinder.js). Descent behavior comes from [its implementation](../web/descent.js) and [browser acceptance](team/status-lane-d.md). Dressing scope comes from [the owning session's report](team/status-worlds.md). The grouping count must match the current plan; never read a memorized count over a different result.

If the live run is late, shorten the composition segment and use the closing line; do not invent a finished step. If dressing is not offered, say so and show the real viewfinder. If the app falls back, name the displayed engine. Read the current skeptic note: a previous rail/freeway objection does not belong to a different pick. The in-app frame tray identifies AI dressing; saved JPEG labeling is stamped in this candidate but verified only with a canvas test double; do not claim it until [PR #31](https://github.com/Tecncentral/typecast/pull/31) is human-merged and a real-browser JPEG is inspected. Frame grabs and recordings remain private pending a human's media approval.

## Five validated scene choices

These are the previous selected-default warm measurements, retained separately from the current stage rehearsal. Every figure below comes from [Demo refresh after v2](team/eval.md#demo-refresh-after-v2).

| Scene | What to point out | Previous warm fixed / deep request time |
| --- | --- | --- |
| **Glass office confrontation** — Los Angeles | Glass partitions, meeting table and view depth behind actors. | 10.092 / 49.109 s |
| **Warehouse handoff** — Los Angeles, main | Exposed roof, concrete floor and open aisle; that retained deep response has a rail-proximity objection. | 8.550 / 38.286 s |
| **Empty shop rehearsal** — Los Angeles | Long, clear room, wood flooring and suspended ceiling. | 9.738 / 38.043 s |
| **Houston glass office meeting** | Empty glass-partitioned office, carpet and broad windows. | 12.396 / 44.160 s |
| **Houston apartment conversation** | Furnished living room, large windows, sofa and adjoining kitchen/counter. | 10.526 / 46.578 s |

Scene texts are in the [runbook](demo-runbook.md#scene-texts). These authored anchors are not human evaluation labels. Use rooms that match the evidence; do not substitute an unverified police-station claim. AI dressing is tied to a cached scan point, so its availability must be checked on the actual returned pick.

## Thirty seconds for CoStar judges

“**What can this space play?** CoStar identifies the property; Matterport shows the real room; Vexcel estimates crew logistics. Typecast connects them, then a skeptic exposes what still needs checking. Look around, compare depth-guided AI dressing with the scan, and group script scenes into fewer buildings. That addresses consistent refurnishing while keeping the real evidence visible. On Monday, a location manager has a recce shortlist—not a filming permit.”

## Numbers the presenter can defend

| Claim | Scope, caveat and source |
| --- | --- |
| **73.33% precision@10 lower bound, post-change v2** | 110/150 returns, eight unjudged counted as misses; 15 scenes, one reviewer. Same test set repeated once after changes informed by v1, not a new holdout. [Evaluation](team/eval.md#v2-after-changes-informed-by-v1). |
| **66% precision@10 lower bound, frozen v1** | 99/150 returns; one reviewer and pooled judgments; unjudged returns counted as misses. [Frozen-run supplement](team/eval.md#v1-supplemental-precision-existing-frozen-run-no-rerun). |
| **30.48% mean pooled recall@10, post-change v2** | Same labels and city constraint; median/p95 16.057/24.459 s with fresh vision scores. No further tuning from this repeat. [Evaluation](team/eval.md#v2-after-changes-informed-by-v1). |
| **27.06% mean pooled recall@10, frozen v1** | City-constrained ceiling 37.90%; global top-ten ceiling 48.14%. Measures returned-view membership, not final-card quality or general accuracy. [Frozen evaluation](team/eval.md). |
| **10.092 s fixed / 44.160 s deep, previous warm medians** | Five authored scenes per engine with twenty cached visual scores. First deep request includes lazy initialization. Three optional trace links were missing and retained. [Previous rehearsal](team/eval.md#demo-refresh-after-v2); use [stage report](team/status-lane-c.md) for current execution. |
| **Five-truck follow-up** | Previous ten warmed refinements took 6.202–10.816 s, used the fixed path, retained candidates, made no new property/interior search and saved unsent drafts. [Rehearsal](team/eval.md#demo-refresh-after-v2). |
| **10,568 views / 343 properties** | Private exact-ID-linked LA/Houston index; 327 properties have marketed lease availability. Availability is not filming permission. [Coverage](team/status-lane-c.md). |

Selected defaults are **20 candidates / concurrency 5 / batch size 5**, chosen on separate tune scenes ([selection record](team/eval.md#tune-experiments)). A favorable cached demo time is not retrieval accuracy. Source evidence, commands and failure wording are in the [runbook](demo-runbook.md).

## Final pass after merges

**Pending:** after the feature PRs are human-merged and the post-01:00 ET stage check completes, use its actual timing, grouping summary and optional-dressing availability. Do not claim a walkable splat until its owner supplies merged code and verified output. The combined recording and public media permission are separate gates.
