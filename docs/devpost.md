# Typecast — cast the space, check the shoot

Submission draft for human review. Main track: **Entertainment and Media**.

Intended special-track targets: **CoStar, LangChain, Amazon and ChatOverflow**. These are targets, not claims of eligibility or awards. Track evidence and remaining checks are below.

Team Discord names: **[MEMBER 1] · [MEMBER 2] · [MEMBER 3] · [MEMBER 4]**.

**[SCREENSHOT PENDING: approved viewer showing real interior frames, source evidence, a parking aerial and a skeptic objection.]**

## Inspiration

A script asks for a tense office confrontation or a warehouse handoff. A location manager has to turn that creative brief into a place a crew can use: the right room, a usable camera position, enough parking, and permission to shoot. Those decisions sit across property listings, interior tours and aerial imagery.

Typecast brings them into one scouting conversation. It treats a building as a possible set and keeps the practical objections beside the picture.

## What it does

Paste a scene set in Los Angeles or Houston. Typecast finds actual interior camera views, joins them to the correct property, and returns a shortlist with source evidence and explicit uncertainty. Change the brief to “Need parking for 5 trucks.” The same conversation reallocates the parking budget and changes ranking or allocation using the retrieved candidate pool.

The deep engine writes a plan, delegates to property, interior and logistics scouts, and asks a read-only skeptic to challenge the shortlist. The scout can inspect why a space was selected and what still needs an on-site check. Explicit approval saves a local inquiry draft with `sent=false`.

The intended Monday user is a location manager or student producer preparing a recce: a shortlist of real rooms to inspect, with the property and crew logistics already connected. We have not measured time saved in a production or completed a customer deployment.

## How we built it

Each data layer answers a different production question:

| Layer | Decision it supports |
| --- | --- |
| **CoStar** | Is this the right property, in the requested city, with recorded building facts and marketed lease availability? Exact property/model mappings connect it to the interior. |
| **Matterport** | What can the camera actually see? Real scan views support visual retrieval, reranking and source geometry checks. Missing depth remains unknown. |
| **Vexcel** | Where could the crew stage? Attributed aerials and actual SAM3 parking masks support estimated parking polygons and one shared car/truck area budget. |
| **OpenStreetMap supplement** | Mapped parking polygons, source-connected walking routes, and freeway, rail or airport/runway proximity screens. Proximity is not a sound measurement. |

We built a Python/FastAPI API, CLIP interior retrieval and permission-gated visual reranking. LangChain `deepagents` supplies the director, separate scout contexts, a persisted plan and an actual human-approval checkpoint for local drafts. A deterministic engine shares the evidence and constraint functions. Real execution events feed the stream; LangSmith links appear only when verified. Both engines preserve the actual mode and report a fallback when one occurs.

Provider downloads and derived imagery stay in private caches. The current index has **10,568 views from 343 properties across 329 models**. It covers all 307 mapped available commercial properties selected in LA and Houston, 20 available multifamily properties, and the retained original set. Sixteen other available commercial properties lack a supplied scan mapping. Availability describes marketed lease space, not filming permission.

See [architecture](architecture.md), [data definitions](../data/SCHEMA.md) and the [evaluation report](team/eval.md).

## Challenges we ran into

The difficult part was keeping attractive images tied to trustworthy evidence. We required exact source mappings, traced real parking-mask pixels instead of using detection rectangles, preserved polygon holes, and charged trucks and cars against one area budget. Unknown parking never became an invented zero. A straight line never became a walking route.

Public Overpass outages initially left noise and walking unknown. A documented regional endpoint and one bounded retry recovered all 343 OSM caches. Five Vexcel property-extract requests still return 404; their unavailable parcel attributes remain explicit. Cached aerials, semantic-search responses and segmentation responses exist for all 343 properties.

The evaluation exposed two retrieval limits: the v1 visual stage reordered the existing first ten candidates, and scenes without a named city searched Los Angeles. We kept that benchmark frozen and reserved five separate tuning scenes for experiments.

## Accomplishments that we're proud of

We verified five authored demo scenes through both live engines, including three source-backed picks per scene, a real skeptic objection, a five-truck refinement with no fresh search, and an unsent local draft. The scenes cover an LA office confrontation, warehouse handoff and empty-shop rehearsal, plus a Houston office meeting and apartment conversation.

After selecting 20/5/5, all ten warm searches across those five scenes succeeded with twenty cached visual scores each. Median times were **10.092 seconds fixed** and **44.160 seconds deep**; the first deep request included lazy process initialization. All five-truck refinements and unsent drafts passed. Three optional trace links were unavailable (one fixed, two deep); original timings were retained and those follow-ups used the same threads without scouting again. These authored rehearsals are separate from the human benchmark.

The frozen **v1** human evaluation returned **99 judged-relevant views out of 150 top-ten results: a 66% precision@10 lower bound**, counting unjudged returns as misses. Mean pooled pipeline **recall@10 was 27.06%** across **15 test scenes reviewed by one person**. The labels came from global top-40 pools, not the whole catalog. The city-constrained mean recall ceiling was **37.90%**, and the global top-ten ceiling **48.14%**. Those ceilings explain the benchmark constraints; they do not replace the observed score. Median request latency was **14.539 seconds**, with fresh visual scores and no warmup. This metric evaluates retrieved-view membership, not the final three cards.

A budgeted experiment used only the five separate tune scenes: 42 real requests and 860 image scorings. It selected twenty candidates scored in batches of five, with concurrency five. Equal-engine tune precision lower bound was 37% versus 36% at baseline; the slowest selected deep request was 55.494 seconds.

The single **v2 (after changes informed by v1)** pass then recovered **110/150 relevant returns: 73.33% precision lower bound and 30.48% macro recall**, with eight unjudged returns counted as misses. All fifteen requests succeeded; median/p95 were 16.057/24.459 seconds, using 300 fresh image scores in 60 vision calls. This is a post-change repeat on the same single-reviewer test set, not a new untouched holdout or a statistical-significance claim. The original v1 remains unchanged in the report.

## What we learned

A useful scouting result needs reasons to visit and reasons to pause. An estimated parking outline can help a producer plan a recce while still leaving access, truck clearance and current availability unresolved. A skeptic that exposes those limits is part of the product.

We also learned to keep relevance, latency and demo polish separate. A cached rehearsal can be fast while a frozen human benchmark still reveals a narrow search pool or a city mismatch. We publish those differences instead of combining them into one accuracy claim.

## What's next

We selected a deeper rerank pool through five-scene tuning; broader human review is needed to establish whether the modest tune gain generalizes. Next steps include a clearer city choice, a separately gated exterior mode, more cities, and source geometry that can support additional camera-fit checks.

Our social-good goal is to offer free scouting access to student crews and help owners earn income from suitable unused space, subject to verified access and filming permission. That is a proposed direction: we have not demonstrated free access, a completed booking, owner income or a charitable partnership.

## Track evidence and human completion

| Target | Evidence available | Remaining confirmation |
| --- | --- | --- |
| **Entertainment and Media** | Creativity: casting spaces from scenes. Utility: connected recce evidence. Avidity: repeatable rehearsals, retained failures and a measured benchmark. Charity: proposed student access and opportunities for empty space. | Confirm the single main-track selection in Devpost. Social benefit remains a goal; final viewer polish awaits its browser acceptance gate. |
| **CoStar** | Three combined data layers with distinct decisions; plan, scouts, skeptic and a practical location-manager workflow. | Confirm current sponsor submission requirements and permitted public screenshots/video. Packet-derived rubric notes are in [HANDOFF](HANDOFF.md#rubrics). |
| **LangChain** | Actual `deepagents` director/delegates, read-only skeptic, checkpointed draft approval and verified LangSmith traces. | Confirm the event's current sponsor criteria. |
| **Amazon** | The repository handoff records equal weights for creativity, usefulness, implementation and user experience. | Official eligibility/service requirements remain unverified. No AWS or other Amazon integration is claimed. |
| **ChatOverflow** | Intended target only. | Agent connection, enrollment, scoring and eligibility evidence are unverified. Its leaderboard participation is separate from the project submission. |

**Peri and Photon are conditional additions only.** Peri needs human-confirmed consultation evidence; Photon needs human-confirmed eligibility and the required live-channel evidence. Neither is claimed in this draft.

Before submission, a human fills the Discord names, resolves the track notes, approves publishable media, and submits the entry. Official references for confirmation: [event](https://www.hackprinceton.com/), [Devpost](https://hackprinceton-fall-26.devpost.com/) and [ChatOverflow leaderboard](https://chatoverflow.dev/leaderboard/hackprinceton). Sponsor presence on the event page alone does not establish project eligibility.
