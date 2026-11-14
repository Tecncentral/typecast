# Typecast: two-minute pitch

This is a rehearsal script, not a recorded timing result. Use **Warehouse handoff** for the main run; keep the other four validated scene options ready. The timing plan assumes a warmed deep run near its measured 39.929 seconds for this scene. Keep talking through real progress; leave the displayed engine and source mode visible.

## Two-minute beat sheet

| Time | Screen/action | Spoken script |
| --- | --- | --- |
| **0:00–0:12** | Scene entry and the five scene options visible. | “A film crew needs a warehouse for a handoff. The room has to play the scene, and the crew has to work there. Typecast checks both together.” |
| **0:12–0:20** | Select **Warehouse handoff** and start the deep engine. | “This is our Los Angeles warehouse scene: two couriers, an open aisle, two trucks and ten crew cars.” |
| **0:20–0:48** | Let the actual plan and scout events appear. Point to the three source lanes as they execute. | “The director writes a plan. CoStar supplies the property facts and marketed lease availability. Matterport supplies actual interior camera views. Vexcel supplies the aerial and estimated parking. Interior and logistics scouts work together, then a skeptic challenges the shortlist.” |
| **0:48–1:09** | When results arrive, show one real frame, the aerial and its skeptic notes. | “Here are the rooms we can inspect. This warehouse result has a rail-proximity warning. That is a location screen, not a sound measurement. Camera fit still says unknown: measure on site. The objection stays beside the image.” |
| **1:09–1:30** | Enter **Need parking for 5 trucks.** Keep the existing thread. Show changed ranking or allocation. | “Now the production grows: five trucks. Typecast keeps the retrieved candidates and recalculates one shared parking budget. Ranking or allocation changes, with no new property or interior search. The response shows the engine that actually handled the follow-up.” |
| **1:30–1:45** | Explicitly approve a local draft. Show the unsent state. | “The scout stays in control. Approval saves a local inquiry draft. Permission to film, usable parking and present-day access still need confirmation with the property.” |
| **1:45–2:00** | End on the shortlist, evidence and source/mode labels. | “Five warm demos had medians of ten seconds fixed and forty-four deep. Our post-change human benchmark has a seventy-three-percent precision lower bound. Typecast gives scouts real places to inspect, with evidence and caveats.” |

If results arrive late, shorten the frame comparison rather than inventing a completed step. If the app visibly falls back, name the actual engine. If no rail/freeway objection is visible in a later run, use the displayed unknown camera-fit or access caveat. Never attach an old objection to a new result.

## Five validated scene choices

| Scene | What to point out | Verified warm fixed / deep request time |
| --- | --- | --- |
| **Glass office confrontation** — Los Angeles | Glass partitions, a meeting table and view depth behind the actors. | 10.092 / 49.109 s |
| **Warehouse handoff** — Los Angeles, main | Exposed roof, concrete floor and open aisle; the retained final deep run contains a rail-proximity objection. | 8.550 / 38.286 s |
| **Empty shop rehearsal** — Los Angeles | Long, clear room with wood flooring and suspended ceiling. | 9.738 / 38.043 s |
| **Houston glass office meeting** | Empty glass-partitioned office, carpet and broad windows; names Houston explicitly. | 12.396 / 44.160 s |
| **Houston apartment conversation** | Furnished living room, large windows, sofa and adjoining kitchen/counter. | 10.526 / 46.578 s |

These authored scene texts are reproduced in the [runbook](demo-runbook.md#scene-texts). They were visually inspected as demo anchors, not human evaluation labels. Use the scenes that match the evidence; do not substitute an unverified police-station claim.

## Thirty seconds for CoStar judges

“**What can this space play?** Typecast turns a scene into a real location shortlist. CoStar checks the property and marketed availability; Matterport shows the camera view; Vexcel estimates crew parking. A director plans, scouts inspect, and a skeptic exposes constraints. Ask for five trucks and the same candidates change. A location manager can start a recce with the room, property and logistics connected. Permission stays with the owner.”

## Numbers the presenter can defend

| Claim | Scope and caveat |
| --- | --- |
| **73.33% precision@10 lower bound, post-change v2** | 110/150 returns, eight unjudged counted as misses; 15 scenes, one reviewer. Same test set repeated once after changes informed by v1, not a new holdout. |
| **66% precision@10 lower bound, frozen v1** | Frozen v1: 99 judged-relevant returns / 150 top-ten returns; 15 test scenes, one human reviewer, pooled judgments; unjudged returns counted as misses. |
| **30.48% mean recall@10, post-change v2** | Same pooled labels and city constraints; median/p95 16.057/24.459 s with 300 fresh image scorings. No further tuning from these results. |
| **27.06% mean recall@10, frozen v1** | Mean pooled pipeline recall, not overall accuracy. City-constrained ceiling 37.90%; global top-ten ceiling 48.14%. Does not evaluate the final three cards. |
| **10.092 s fixed / 44.160 s deep** | Medians of five authored scenes per engine with twenty cached visual scores. First deep request includes lazy initialization. Three optional trace links were missing; every original search is retained. |
| **14.539 s median / 19.693 s p95** | Separate frozen v1 fixed-engine test run: 15 scenes, fresh vision scores, no warmup or retries; local in-process request time. Source imagery/index/logistics were cached. |
| **Five-truck follow-up** | All ten warmed demo refinements took 6.202–10.816 s, used the fixed refinement path, retained the candidate pool, made zero new searches and saved unsent local drafts. |
| **10,568 views / 343 properties** | Private, exact-ID-linked LA/Houston index; 327 properties have marketed lease availability. Availability does not establish filming rights. |

Selected defaults are **20 candidates / concurrency 5 / batch size 5**. Warm source/refinement/draft checks passed for all five scenes on both engines. Optional trace-link checks passed for four of five fixed and three of five deep requests; missing links remain visible and their follow-ups were completed on the original threads. Full methods: [evaluation](team/eval.md). Commands and fallback: [runbook](demo-runbook.md).
