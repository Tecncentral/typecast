# Typecast architecture

Typecast joins a scene, actual interior views, exact property identity and cached crew logistics. The fixed engine and the `deepagents` director share source adapters, constraint checks and response contracts. The diagram below shows the deep path; the fixed path runs the same source/ranking stages in application code.

```mermaid
flowchart TD
    Scene["Scene text + city + crew needs"] --> API["FastAPI /scout or /scout/stream"]
    API --> Parse["Validated requirements parser"]
    Parse --> Runtime["Runtime: fixed or deep"]
    Runtime --> Director["Deep director: persisted initial plan"]
    Runtime --> Fixed["Fixed pipeline: shared evidence and constraints"]

    subgraph Private["Private source preparation and caches"]
        CoStar["CoStar records + explicit property/model mappings"] --> Join["Exact-ID private join"]
        Matterport["Matterport scans + source room evidence"] --> Index["Real views + CLIP retrieval index"]
        Vexcel["Vexcel property, aerial, search and SAM3 APIs"] --> Aerial["Attributed aerials + traced parking masks"]
        OSM["OSM Overpass, bounded sequential requests"] --> Mapped["Mapped parking, paths, entrances and noise sources"]
        Aerial --> Cache["Precomputed logistics with evidence statuses"]
        Mapped --> Cache
    end

    Director --> Market["market_scout"]
    Fixed --> Market
    Join --> Market
    Market --> Interior["interior_scout: retrieve, rerank, check"]
    Market --> Logistics["logistics_scout: read cached logistics"]
    Index --> Interior
    Cache --> Logistics
    Interior --> Shortlist["Authoritative shortlist builder"]
    Logistics --> Shortlist
    Shortlist --> Skeptic["Read-only skeptic: source-grounded objections"]
    Skeptic --> Validate["Validate source IDs, reviews and contracts"]
    Validate --> Result["Picks + evidence + unknowns + actual engine/mode"]

    Director -.-> Events["Actual tool/graph events"]
    Fixed -.-> Events
    Events --> SSE["SSE agent/result/error events"]
    Result --> SSE
    Validate -.-> Trace["Optional redacted LangSmith trace; verified link only"]

    SSE --> Viewer["Location scouting viewer: actual mode, engine and caveats"]
    Viewer --> Descent["Inside-out descent: map → attributed aerial → real frame"]
    Descent --> Viewfinder["Look around: real scan-point viewfinder + lens controls"]
    Index --> Sweep["Allow-listed /api/sweep/{shot_id}: real panorama faces"]
    Sweep --> Viewfinder
    Sweep -. "authorized offline preparation" .-> Atlas["World Labs Atlas: posed depth derived from scan images"]
    Atlas --> Chisel["atlasChisel: reuse depth constraints, imagine set dressing"]
    Chisel --> DressedCache["Private precomputed dressing cache"]
    DressedCache --> DressedAPI["Allow-listed /api/dressed/{shot_id}; absent → 404"]
    DressedAPI --> Compare["Optional D wipe: real scan ↔ AI-imagined dressing"]
    Viewfinder --> Compare
    Compare --> Grab["Private frame tray; export-label fix pending"]

    Script["Whole script at /director"] --> Production["/api/production/plan: retrieve scene candidates"]
    Index --> Production
    Join --> Production
    Cache --> Production
    Production --> Group["Exact-property grouping within retrieved pool"]
    Group --> Plans["Coverage, location count, company moves and similarity"]
    Plans --> Reel["Director's Room plan comparison + Play"]

    Result --> State["Private thread requirements, candidates and shortlist"]
    Followup["/refine: explicit follow-up"] --> State
    State --> Refine["Fixed refinement: reuse candidates, update allocation/ranking"]
    Refine --> Result

    Result --> Approval["/approve: explicit human decision"]
    Approval --> Gate["Deep HITL checkpoint or fixed approval gate"]
    Gate --> Draft["Private local inquiry draft: sent=false"]
```

## What each layer decides

| Source | Supported evidence | Limit |
| --- | --- | --- |
| CoStar | Exact property/model mapping; city, type and recorded facts; marketed lease availability with explicit unknowns. | A listing does not establish filming permission, vacant occupancy or access. Nearest-address guesses are not joins. |
| Matterport | Actual camera frames, source scan identities and available room evidence; semantic retrieval and visual fit reasons. | Missing directional depth or ceiling measurements cannot become a verified physical fit. Scan navigation and camera-heading alignment are separate claims. |
| Vexcel | Attributed aerials, parcel containment checks, SAM3 mask-derived parking geometry and estimated area capacity. | Search tile footprints and detection rectangles are not parking boundaries. Parking rights, current occupancy and truck clearance remain unverified. |
| OSM supplement | Surface-parking polygons; walking only through an eligible mapped path and building-associated entrance; proximity to freeway, rail and airport/runway geometry. | Missing data stays unknown. Empty proximity results do not establish quiet; distance is not a sound measurement. |

Source downloads run before scouting. Runtime logistics reads normalized cache records and does not wait for Vexcel or Overpass. Credentials and all licensed source/derived files remain private. The public repository contains code, synthetic tests and aggregate evidence.

## From source evidence to a dressed set

The inside-out descent links one property's map position, attributed Vexcel aerial and actual Matterport frame. The parking outline uses supplied geometry and validated aerial georeferencing; an unreliable transform falls back to existing imagery. Reduced motion and skip controls change the presentation without fabricating source evidence. Source: [descent implementation](../web/descent.js) and [browser acceptance](team/status-lane-d.md).

The viewfinder presents real horizon faces from the selected scan point. Its lens controls compose a view; they do not establish unknown room depth, verified camera fit or absolute world heading. The optional dressing comparison loads already generated assets, so a stage click does not start Atlas generation. The **D** toggle wipes the imagined appearance over the scan and keeps **“AI-imagined set dressing, not the real room”** visible. **G** grabs a frame; the in-app tray marks dressing. In this integration candidate (which carries PR #31's viewfinder changes) a grab taken with dressing visible is stamped “AI-imagined set dressing · not the real room” onto the exported pixels and its filename ends `-ai-dressed`. That is verified only against a canvas test double in the Node suite; a rasterized JPEG from a real browser with live dressing has not been inspected, so do not claim labeled exports until [PR #31](https://github.com/Tecncentral/typecast/pull/31) is human-merged and that live check is done. `/api/dressed` always returns the canonical label, omits the generation prompt, serves only validated, exact-scan-point face files and answers 404 for corrupt or invalid cache records; the viewfinder shows AI controls only after at least one dressed image actually decodes (partial coverage is stated as partial). Source: [viewfinder](../web/viewfinder.js), [allow-listed APIs](../agent/app.py).

Atlas `images2PosedRGBD` derives cameras and depth from the real scan images. `atlasChisel` receives those same depth constraints and an authored scene prompt to propose a new appearance. This supports the consistent-refurnishing use case; it is not a measured Matterport depth import, exact metric-geometry guarantee or proof that the dressing can be built. The merged verification covers image dressing. **TODO:** add sparse-scan walkable results and their measured scope only after the owning session's implementation and evidence are merged. Sources: [dressing pipeline](../worlds/dress.py), [verified scope and cost limits](team/status-worlds.md).

## Whole-script grouping

The Director's Room uses exact property identity to assign scenes to buildings and show alternative plans. It currently retrieves **120** views per scene, considers the first **three** retrieved properties per scene up to **24** total, and accepts up to **eight** scenes and **four** locations. These are implementation limits, not benchmark results. Source: [production request validation and pool builder](../index/production.py).

The plan exposes coverage, location count, company moves and mean similarity. Its optimality applies only to that bounded candidate pool, and moves assume one visit per selected property. It does not model road travel, shooting order, access permissions or actual crew downtime. Unknown evidence stays visible; a successful creative grouping is not a verified booking. Sources: [production planner](../index/production.py), [solver](../index/production_solver.py).

## Execution and human control

The deep director uses separate `market_scout`, `interior_scout`, `logistics_scout` and `skeptic` contexts. After the market pool returns, interior and logistics work in parallel. Tools keep exact retrieved IDs authoritative; the language model cannot replace the shortlist with invented properties. The skeptic can read the verified shortlist and object; it does not mutate source data.

The runtime bounds deep execution at 90 seconds and visibly falls back to fixed after ordinary failures or timeouts. A provider rate limit stops further model calls instead of retrying through fixed. Streaming uses actual events from the running work. The final response carries the engine and source mode that actually produced it. A configured or missing trace link is never proof of a successful trace; only verified links are exposed. Source: [runtime](../agent/runtime.py).

Follow-ups reuse the same retrieved candidate pool and apply explicit changed requirements. They can rerank cached views and reallocate parking without a new property/interior search. The current refinement engine is fixed, including after an initial deep run. Private thread memory has a six-hour process lifetime; restarting the server requires a new scout conversation. Saved files are not a durable graph-resume guarantee. Sources: [pipeline](../agent/pipeline.py), [thread state](../agent/state.py).

Deep approval uses an actual interrupted `draft_inquiry` tool checkpoint. `/approve` resumes it after an explicit decision. Fixed approval follows the application gate. Both save a local draft with `sent=false`; there is no owner-delivery claim in this flow.

## Evidence arithmetic and coverage

Parking uses `floor(area_m2 / 30)` car equivalents, with each truck consuming four equivalents from that same budget. Actual mask cells or mapped polygons determine the outline; holes are preserved. A connected mapped route is required for walking, rather than a line between centroids. See [Vexcel/OSM details](../data/VEXCEL.md).

The verified private index contains 10,568 views, 343 properties and 329 models. Every indexed property has a validated aerial, segmentation response, semantic-search response and OSM cache. There are 224 parking estimates, 128 properties with proximity flags, one estimated mapped walking route and 342 unknown walking distances. Five property-extract 404s leave parcel attributes unavailable. These counts describe cached source coverage, not successful bookings or a relevance score. Source: [coverage verification](team/status-lane-c.md).

The frozen v1 visual stage reranked the existing first ten candidates. The selected default now scores twenty candidates in four validated five-image requests, with a concurrency limit of five, then ranks the full scored pool so later views can enter the top ten. The rest of the candidate pool remains available for refinement. An explicit setting can restore the 10/5/1 baseline. On five tune scenes and both engines, precision lower bound increased from 36% to 37%; the slowest selected deep request was 55.494 seconds. This is a small tune result, not a general accuracy claim. Evaluation scope, city ceilings and the separate post-tuning v2 test are in [the benchmark](team/eval.md). Demo timings are in [the pitch](pitch.md#numbers-the-presenter-can-defend).

## Implementation references

- API/runtime: `agent/app.py`, `agent/runtime.py`, `agent/interfaces.py`.
- Fixed evidence/ranking/refinement: `agent/pipeline.py`; validated source/response shapes: `contracts/schemas.py`.
- Director, delegates, plan and approval: `agent/deep.py`, `agent/deep_tools.py`, `agent/prompts/deep_*.md`.
- Retrieval/reranking: `index/search.py`, `index/store.py`, `agent/rerank.py`.
- Private sources: `data/build_join.py`, `data/costar_tools.py`, `data/vexcel_precompute.py`, `data/vexcel_geometry.py`, `data/vexcel_tools.py`.
- Private working memory and redacted tracing: `agent/state.py`, `agent/tracing.py`.

No Amazon, ChatOverflow or Photon integration is implied by this diagram. Their submission eligibility requires separate evidence.
