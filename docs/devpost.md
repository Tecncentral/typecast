# Typecast — cast the space, check the shoot

Submission draft for human review. Main-track intent: **Entertainment and Media**. Special-track candidates with repo evidence: **CoStar**, **LangChain** (deep agents) and **Amazon Best Practical AI Innovation** (the packet allows any stack; AWS is not used or claimed), subject to the current event criteria; see `docs/TRACK-SELECTION.md`. Peri is conditional on real affiliation, event-time consultation and evidence that do not yet exist, and no consultation or endorsement is claimed. No Photon or ChatOverflow claim is made without human-confirmed evidence. Community planning is an honest prototype tested on mock fixtures only, with no established benefit. World Labs is a tool we used, not a competition track.

Team Discord names: **[MEMBER 1] · [MEMBER 2] · [MEMBER 3] · [MEMBER 4]**.

**[SCREENSHOT PENDING: human-approved image of the merged viewer, with source evidence and any AI label legible. Licensed imagery remains private until publication permission is confirmed.]**

## Inspiration

A script asks for a warehouse handoff. A location manager needs a real room that can play the scene, a camera position, enough parking, and permission to shoot. An attractive image alone cannot answer all of that. A whole script adds another question: how many times must the crew pack up and move?

Typecast connects the creative decision with the practical evidence. It treats a building as a possible set and keeps the reasons to visit—and the reasons to pause—beside the picture.

## What it does

Paste a scene set in Los Angeles or Houston. A director plans, property/interior/logistics scouts gather evidence, and a read-only skeptic challenges the shortlist. The inside-out descent connects the chosen property's map position, Vexcel aerial and real Matterport frame in one reveal. Open **Look around** to compose in the viewfinder; when cached AI dressing exists, a wipe compares the scan with an imagined dressed set. Sources: [viewer acceptance](team/status-lane-d.md), [viewfinder](../web/viewfinder.js), [dressing report](team/status-worlds.md).

Ask **“Need parking for 5 trucks.”** The same thread reuses its retrieved candidates and changes their ranking or parking allocation. The Director's Room takes a script, groups scenes by property and compares plans by coverage, company moves and visual similarity. Grouping is optimized within the retrieved pool; company moves assume one visit per property, not a measured travel schedule. Sources: [refinement](../agent/pipeline.py), [production planner](../index/production.py).

The intended Monday user is a location manager or student producer preparing a recce: real rooms to inspect, with property identity and crew logistics connected. Explicit approval saves an unsent local inquiry draft. We have not measured production time saved, completed a booking or deployed to a customer.

## How we built it

| Layer | Decision it supports |
| --- | --- |
| **CoStar** | Is this the right property, in the requested city, with recorded building facts and marketed lease availability? Property identity connects it to the interior and lets the Director's Room group scenes at one location; the planner reports its independent property/model match as unknown when the optional mapping is absent. |
| **Matterport** | What can the camera see? Real scan views support retrieval, visual ranking and the interactive viewfinder. Available geometry is evidence; unmeasured directional depth remains unknown. |
| **Vexcel** | Where could the crew stage? Attributed aerials and traced SAM3 parking-mask pixels support estimated parking polygons and a shared car/truck area budget. |
| **OpenStreetMap supplement** | Mapped parking, source-connected walking routes and proximity to freeway, rail or airport/runway geometry. Proximity is not a sound measurement. |

Python/FastAPI serves a plain JavaScript viewer, CLIP retrieval and permission-gated visual reranking. LangChain `deepagents` supplies the director, separate scout contexts, persisted plan and an actual approval checkpoint for local drafts. The fixed engine shares source and constraint functions. Progress comes from actual execution, and LangSmith links appear only after verification. Sources: [architecture](architecture.md), [API](../agent/app.py), [deep execution](../agent/deep.py).

For the Matterport team's **consistent refurnishing** wishlist item, we use World Labs Atlas to derive posed RGBD from real scan faces and pass the same depth constraints into `atlasChisel` while changing appearance. The UI compares that imagined furnishing with the real room. Depth is derived from the real images; we do not claim it is a measured Matterport depth import or a guarantee of exact geometry. This is a demonstrated approach to consistent refurnishing, not a benchmark of cross-view consistency. Sources: [dressing pipeline](../worlds/dress.py), [owner's verification](team/status-worlds.md).

**TODO — optional walkable result:** the merged verification covers image dressing. Before adding the wishlist claim “interior splats from sparse scans,” require the World Labs owner's merged walkable result, source-view count, generation time, asset size, measured cost and observed navigation limits. Leave those numbers blank until verified; no sparse-scan splat achievement is claimed here.

Private source downloads and derived assets stay in ignored caches. The frozen index contains **10,568 views / 343 properties / 329 models**: all **307** mapped available commercial properties selected in LA and Houston, **20** available multifamily properties and the retained original set. **Sixteen** additional available commercial properties lack a supplied scan mapping. Source: [frozen coverage](team/status-lane-c.md). Availability describes marketed lease space, not filming rights.

## What is real vs AI-generated

The scan imagery, property association and aerial are source evidence. Parking capacity is estimated; unknown measurements remain unknown. AI set dressing is an imagined appearance constrained by depth derived from the scanned room, with the persistent label **“AI-imagined set dressing, not the real room”**. Areas outside the dressed image coverage show the real room dimmed, and the in-app frame tray identifies dressed grabs. In this integration candidate (which carries PR #31's viewfinder changes) a grab taken with dressing visible is stamped “AI-imagined set dressing · not the real room” onto the exported pixels and its filename ends `-ai-dressed`. That is verified only against a canvas test double in the Node suite; a rasterized JPEG from a real browser with live dressing has not been inspected, and the claim stays pending [PR #31](https://github.com/Tecncentral/typecast/pull/31) being human-merged and that live check. Sources: [viewfinder](../web/viewfinder.js), [dressing verification](team/status-worlds.md).

A generated dressing does not establish physical feasibility, costs, current furniture or owner consent. An art department must evaluate it. Property availability does not establish vacancy, access or filming permission. The viewer does not turn estimated parking or noise proximity into measured conditions.

## Challenges we ran into

We had to keep the image tied to the evidence. Exact source mappings replaced address guesses. Real mask pixels and preserved holes replaced convenient detection rectangles. Trucks and cars consume one area budget. Missing parking stays unknown; a line between centroids never becomes a walking route. Sources: [data definitions](../data/SCHEMA.md), [Vexcel/OSM methods](../data/VEXCEL.md).

A bounded Overpass retry recovered **343** OSM caches; **five** Vexcel parcel-detail requests still returned 404. Their unavailable attributes remain explicit even though aerial, semantic-search and segmentation caches exist. Source: [coverage report](team/status-lane-c.md). Source caches support venue resilience, but the live parser/director still need a model connection: a retained video must say **recorded live run**, and fixture mode must say **MOCK**.

The frozen evaluation exposed limited rerank depth and the Los Angeles default for city-free scenes. We preserved v1 and selected the next configuration only on separate tune scenes. The visual reveal posed a similar honesty problem: the real scan and imagined dressing must remain distinguishable throughout the wipe and frame capture.

## Accomplishments that we're proud of

The viewer's recorded acceptance covers the real descent, viewfinder, source/mode labels, same-thread refinement and unsent drafts. The dressing owner reports precomputed image dressing for the **five** authored demo anchors; a later scout can select a different scan point, so the actual returned pick must be checked. Sources: [viewer report](team/status-lane-d.md), [dressing report](team/status-worlds.md). The combined stage judge-path gate and backup recording remain separately recorded in the [runbook](demo-runbook.md).

Previous selected-default rehearsals completed **five scenes on each engine**: warm medians **10.092 s fixed / 44.160 s deep**. Every follow-up and local draft passed; **three** optional trace links were unavailable and retained. The first deep request includes lazy initialization. These authored demos are separate from the human benchmark. Source: [retained demo refresh](team/eval.md#demo-refresh-after-v2). The newer Job 8 stage batch passed **10/10** strict checks, every trace readback and every same-pool refinement/local draft. Warm medians were **8.923 s fixed / 40.923 s deep** with **20/20** cached visual scores per scout, no scoring failures and no engine fallback. The first fixed request includes lazy initialization; deep was warmed by **two** partial browser attempts. Dressing was offered for **four of five** top-pick scenes on both engines; LA office returned 404. Source: [lane C stage report](team/status-lane-c.md). These checks do not replace the complete browser-path gate.

The frozen v1 returned **99/150** judged-relevant views: **66% precision@10 lower bound**, **27.06% mean pooled recall@10**, across **15** scenes reviewed by **one** person. Unjudged results count as misses. Global top-40 judging pools and the city filter limit the result; the city-constrained recall ceiling is **37.90%**, global top-ten ceiling **48.14%**. Median request time was **14.539 s** with fresh visual scores and no warmup. Source: [frozen evaluation](team/eval.md).

A separate **five-scene** tune study used **42 requests / 860 image scorings**, selecting **20 candidates / concurrency 5 / batch size 5**. Equal-engine tune precision lower bound was **37%**, versus **36%** baseline; the slowest selected deep run was **55.494 s**. This small difference does not establish general improvement. Source: [tune experiments](team/eval.md#tune-experiments).

The single **v2 (after changes informed by v1)** repeat recovered **110/150**, giving **73.33% precision@10 lower bound / 30.48% macro recall**. **Eight** unjudged returns count as misses; all **15** requests succeeded, with median/p95 **16.057/24.459 s** and **300** fresh image scores in **60** vision calls. This is a post-change repeat on the same single-reviewer set, not an untouched holdout or statistical-significance claim. Neither benchmark evaluates final-card quality or exhaustive catalog relevance. Source: [v2 report](team/eval.md#v2-after-changes-informed-by-v1).

## What we learned

A useful scout needs reasons to visit and reasons to pause. A parking outline can support a recce while still leaving access, truck clearance and current availability unresolved. The skeptic is useful precisely because it exposes those limits.

We also learned to keep retrieval quality, live latency and presentation polish separate. The descent makes the source connection understandable. The dressing comparison makes the creative possibility visible. Neither changes what the benchmark proves.

## What's next

Broader human review should test whether deeper reranking generalizes. A clearer city choice, separately gated exterior mode, more cities and directional geometry would improve the scouting workflow. The Director's Room needs production-user validation before claiming saved company moves or crew time. Optional walkable dressing remains the owning session's separate verification gate.

Our social-good goal is free scouting for student crews and income opportunities for suitable unused buildings. Free access, owner income, a charitable partnership and completed bookings are goals, not demonstrated outcomes.

## Track evidence and human completion

| Target | Evidence available | Remaining confirmation |
| --- | --- | --- |
| **Entertainment and Media** | Creativity: casting and imagining sets. Utility: connected recce evidence and script grouping. Avidity: retained rehearsals, failure records and a benchmark. Charity: proposed student access and reuse of empty space. | Confirm the main-track selection. Social benefit remains a goal. |
| **CoStar** | CoStar/Matterport/Vexcel decisions, plan/scouts/skeptic, the inside-out source reveal and depth-guided consistent refurnishing. | Confirm current sponsor criteria and public-media permission. Wishlist correspondence describes our implementation; it does not assert sponsor acceptance. [Packet notes](HANDOFF.md#rubrics). |
| **LangChain** | Actual `deepagents`, separate delegates, read-only skeptic, approval checkpoint and verified traces where available. | Confirm current sponsor criteria. |
| **Peri, Photon, Amazon, ChatOverflow** | No eligibility claim in this draft. | Human evidence is required before adding any claim. Peri needs consultation evidence; Photon its required live-channel evidence; Amazon its service/eligibility requirements; ChatOverflow agent connection, enrollment and separate leaderboard requirements. |
| **World Labs** | Atlas image dressing, explicitly labeled as AI-imagined. | Tool used, not a claimed track. Walkable/splat result and costs remain subject to the owner's verified report. |

A human supplies Discord names, checks eligibility, approves public media, reviews the repository release audit, and submits. Final factual pass after human merges and the post-01:00 ET judge-path check remains **pending**. Official event references for that human check are the [event](https://www.hackprinceton.com/) and [Devpost](https://hackprinceton-fall-26.devpost.com/); sponsor presence alone does not establish eligibility.
