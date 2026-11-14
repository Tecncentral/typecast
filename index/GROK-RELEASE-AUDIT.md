# Grok release audit: prize evidence and 2-minute demo readiness

Audited **2026-11-14T20:45:06Z** at commit `6c73d5759c206ddf235db5a55d799e9e8cfb09ff` (`6c73d57`, PR #22 head, `origin/lane-a` at fetch time). Docs only. No implementation file was changed. No live index, licensed cache, API key, paid call, or browser click-through was used.

Verdicts mean: **MET** the cited requirement is implemented and this audit executed a supporting mock path; **AT RISK** the code exists but the judging demo can miss it, overclaim it, or depend on unrun live setup; **NOT MET** this tree does not do the thing the prize asks for; **UNVERIFIED** the requirement or the evidence was not established here.

Numbers in [README.md](../README.md), [docs/team/eval.md](../docs/team/eval.md), [docs/team/status-lane-c.md](../docs/team/status-lane-c.md), and [DIRECTORS-ROOM.md](DIRECTORS-ROOM.md) (10,568 views, recall@10 0.2706, 24.66 s / 2.69 s / 4.82 s, 363 passed / 1 skipped) are **user-reported**. This audit did not reproduce them. Commands this audit actually ran are in [Commands this audit ran](#commands-this-audit-ran).

## What was re-fetched

Fetched during this audit:

- https://hackprinceton-fall-26.devpost.com/rules
- https://hackprinceton-fall-26.devpost.com/
- https://hackprinceton-fall-26.devpost.com/details/dates

CoStar, Amazon, and LangChain **rubric percentages are not on those pages**. Where this doc cites 30/30/25/15 or four 25% Amazon quarters, the source is the onsite packet as already quoted in [PRODUCTION-PLAN.md](PRODUCTION-PLAN.md) and [docs/team/START-HERE.md](../docs/team/START-HERE.md), marked **packet-as-quoted-in-repo**.

### Quoted public rules (rules page)

> Final submissions are due Sunday, Nov 15 at 8:00 AM. Submissions are only through Devpost.

> Maximum Team Size of 4 for prizes. No exceptions will be made. All Team members must be added to the Devpost submission in order to recieve prizes.

> Projects must be submitted on or before the deadline Sunday, November 15 at 8:00 AM. This is a HARD stop and submissions after this time will NOT be considered.

> You must submit a project that was built during Nov 13 at 8:00 PM ET - Nov 15 at 8:00 AM ET, 2026.

> All projects must submit their code in a public GitHub repository

> At least 85% of code should be written during the event. While we do not restrict the use of LLMs in developing your project, we advise the importance of human direction in your projects and strongly discourage completely LLM-created projects. Participants should be able to understand their code and explain the technical decisions that they made. Overly embellishing your contributions -- in Devpost, Github, or your pitch -- may result in project disqualification.

> You may only opt into ONE of the main six HackPrinceton tracks. However, you are free to opt-in to any number of our sponsor tracks in addition to one of our tracks.

> Judging will occur in-person and every submission is required to conduct a maximum 2-minute presentation in front of judges during the judging period (9:30 AM - 2 PM on Sunday, Nov 15).

Creativity, Utility, Charity, and Avidity on that page match the wording in the task (ah-ha / does it function / societal need / visible passion). The overview page also says an optional video demo must not exceed 2 minutes, and that the in-person presentation must not exceed 2 minutes even if a video is attached.

### Quoted public overview (track name and two prizes)

The only main-track name that matches this product is **ENTERTAINMENT**:

> This category celebrates projects that creatively integrate entertainment and media elements. Examples include storytelling applications, interactive experiences, and media literacy platforms.

The repo’s phrase “Entertainment & Media” is a paraphrase. The Devpost control is the track named **ENTERTAINMENT**. One main track only.

CoStar, public overview:

> CoStar is looking for at least 2/3 layers, agentic capabilities, the ability to solve a real problem for a real person, and for it to involve spatial and visual understanding.

Amazon, public overview:

> The task is to build an AI that solves a real problem for real people. Create AI-powered tools that go beyond demos: applications that reason, plan, take action, and adapt.

MLH Gemini, public overview, is an API prize (“Check out the Gemini API”, “what will you build with the Google Gemini API”). Team correction applied below: a Gemini web chat used while coding does not count. MLH SpaceXSI, public overview, requires Cursor as the core coding agent, a Grok Bot automation in the workflow, a description of both, and an opt-in. That fit is **not established** here.

LangChain / Deep Agents does **not** appear in the fetched overview prize list. Treat it as packet-only until a human sees it on the live Devpost form.

### Deadline conflict (use 8:00 AM)

| Surface | What it says | Source |
| --- | --- | --- |
| Rules | Sunday Nov 15 at **8:00 AM**, HARD stop | https://hackprinceton-fall-26.devpost.com/rules |
| Schedule table | Submissions end November 15 at **8:30am EST**; submissions begin November 13 at **5:00pm EST** | https://hackprinceton-fall-26.devpost.com/details/dates |
| Overview header / schema.org | Deadline Nov 15, 2026 @ 8:30am EST; `endDate` `2026-11-15T08:30:00.000-05:00`; `startDate` `2026-11-13T17:00:00.000-05:00` | https://hackprinceton-fall-26.devpost.com/ |
| Rules build window | Nov 13 at **8:00 PM ET** through Nov 15 at **8:00 AM ET** | rules page |
| Packet, as quoted in START-HERE | 8:00 AM Nov 15 | packet-as-quoted-in-repo |

Submit against **8:00 AM Eastern**. The later clock is a conflicting public display, not a reason to use it.

GitHub repository object observed on the pulls API during this audit: `Tecncentral/typecast`, `private: false`, `created_at: 2026-11-14T08:31:18Z`. That timestamp is inside the rules build window (after 2026-11-14T01:00:00Z, which is Nov 13 8:00 PM ET). **85% event-written code was not measured.** Do not invent a percentage.

## Which datasets change a decision

Three layers, and what each one actually does at this commit. “Changes a decision” means the solver assignment, eligibility flag, or skeptic rank/blocker changes. A badge or sentence that does not change those is display.

### Director solver — `POST /api/production/plan`

Route: `index/preview.py:18-19` mounts `production.router`. Handler: `post_production_plan` (`index/production.py:323`). The shared agent app does **not** mount this router (this audit: `POST /api/production/plan` on `agent.app` returned **404**).

| Layer | What the code does with it | Changes the plan? | Evidence |
| --- | --- | --- | --- |
| Matterport view rank | `search_shots` order builds a pool of at most the first three properties per scene, cap 24 (`production.py:357-365`). `solve_plans` assigns the best cosine in each property subset (`production_solver.py:155-170`) and sorts by coverage, then mean score, then fewer locations (`production_solver.py:36-45`). | **Yes, when scores differ.** | In **mock** mode embeddings are `None` and the order is the fixture `score`, reason string `MOCK fixture ranking (no semantic model)` (`index/search.py:365-391`). This audit posted two different scene texts and the shot scores did not change (`QUERY_TEXT_CHANGED_SCORES False`). |
| CoStar `property_id` / `model_id` join | Live mode only. A pair in `cache/property_models.parquet` is `matched`. A conflicting id sets `eligible = False` and the shot never enters `solver_candidates` (`production.py:393-405`, `425-431`). Mock mode does not read the parquet (`production.py:334-335`; test `test_mock_plan_never_claims_private_join_evidence`). | **Yes, live conflict only.** Mock: no join decision. | `load_property_model_pairs` (`production_join.py:23`). |
| CoStar availability | Warning always. `availability_status` outside `{available, not_available}` → warning `costar` / `availability` / `unknown` (`production.py:276-277`). Exclusion only if `require_available` is true, and only when `available is True` **and** `availability_status == "available"` (`production.py:406-413`). | **Yes, only with the checkbox, and only for rows that carry the status enum.** | Public fixtures omit `availability_status`. This audit set `require_available: true` on the demo scenes and got **zero assignments** for `mock-p1`, `mock-p2`, and `mock-p3`, including rows with `"available": true`. The checkbox is fail-closed. It does not demonstrate “keep the available listing, drop the other one” on these fixtures. |
| CoStar type, year, size, parking flags | Copied onto the candidate `property` object. The solver never reads them. | **No** on this route. | `solve_plans` reads `scene_id`, `property_id`, `shot_id`, `score` only (`production_solver.py:91-96`). |
| Matterport geometry | Missing area, ceiling, depth, or `measure_on_site` adds warning `matterport` / `geometry` / `unknown` (`production.py:387-388`). Eligibility is unchanged. | **No.** | Stage badge is separate and also does not feed the solver. |
| Vexcel parking | `enough_parking is False` sets `eligible = False` when `trucks + cars > 0` (`production.py:414-416`). Unknown capacity (`enough_parking is None`) stays eligible and warns. | **Yes, when a count comparison returns false.** | This audit, `trucks: 3`, `cars: 30`: `mock-p2` (`truck_spaces: 1`, `car_spaces: 12`) `eligible: false`, warning `vexcel` / `parking_capacity` / `insufficient`. Forbidding `mock-p1` then assigned **`mock-p3`**, not `mock-p2`. With `trucks: 0`, `cars: 0` the same scenes assigned **`mock-p1`** and did not exclude `mock-p2`. Default Director inputs are 0 and 0 (`director.html:22-23`), so the pitch must type the vehicles or this layer does not change the plan. |
| Vexcel walk and noise | Returned on `logistics` and shown in the evidence panel. Not read by `solve_plans`. | **No** on this route. | Walk/noise change the **scout** skeptic, below. |
| Human reject | `forbidden_property_ids` are dropped before the pool and again inside the solver (`production.py:333-354`, `production_solver.py:102-103`). | **Yes.** | `director.js:117-122` `reject()` pushes the assigned `property_id` and calls `build(true)`. |

`parking_status` on every mock logistics row in that smoke was JSON `null`, while `enough_parking: false` still excluded `mock-p2`. The panel maps a null status through `sourceStatus` to the word **unknown** (`director.js:254`, `266`) at the same time the warning says the property was excluded. That contradiction is bug 1 in the appendix.

### Scout skeptic — `POST /scout` (fixed engine unless `TYPECAST_ENGINE=deep`)

This is a different route from Director. `runtime.run_scout` (`agent/runtime.py:139-155`) calls `pipeline.scout` (`agent/pipeline.py:317`) for the fixed engine. `_skeptic` (`agent/pipeline.py:144-176`) adds blockers. `_select` sorts by blocker count before score (`agent/pipeline.py:264-266`), so a blocker changes rank. `_failed_fit` (`agent/pipeline.py:98-102`) drops a view from the shortlist when the numeric depth is below `needed_depth_m`.

| Layer | Decision this audit observed on public mocks | Code |
| --- | --- | --- |
| CoStar `available` boolean | Scene `INT. 1980s POLICE STATION, NIGHT. Parking for 3 trucks and 30 crew cars.` Rank 3 was `mock-p4` (`available: false`, `availability_status: null`) with note **“Space is occupied, not listed as available.”** and reason text **“occupied”**. That blocker is why it is labeled “Blocked alternative”. | `_availability` (`pipeline.py:59-64`) returns `"occupied"` when status is missing and `available` is false. `_skeptic` (`pipeline.py:162-167`) uses that branch. A test locks the word `occupied` (`agent/tests/test_pipeline_edges.py:133-142`). When status is the enum `unknown`, the same file expects the reason **not** to say occupied (`test_pipeline_edges.py:249-263`). |
| CoStar year | `gave_up` included `era`. Year bounds exclude, then relax (`pipeline.py:245-251`, `277-288`). | Parser-off mock still recorded era relaxation for that scene text. |
| Matterport depth numbers | `needed_depth_m(24, 6)` is **8.783 m**. Every `mock-p1` shot is depth 6–8 m with `measure_on_site: false`, so `check_fit` status is `tight` and `_failed_fit` removes the property. It was absent from the three picks. `mock-p3` depth 11 m was rank 1, `fit_status: "fits"`. | `index/geometry.py:43-53`, `pipeline.py:83-102`. These fixture numbers are marked measured. Saying “the room fits” on the offline scout is a fixture result, not a survey. |
| Matterport estimated geometry | `check_fit(..., measure_on_site=True)` returns status **unknown** (`geometry.py:53`; test `index/tests/test_geometry_evidence.py:6-9`). If depth and ceiling are both present, `_fit` **replaces** that with status **tight** (`pipeline.py:90-91`). `_failed_fit` still compares the estimated number and can drop the view. Current room enrichment writes `depth_m: None` (`index/rooms.py:331`, `384`), so a null-depth live shot stays on the unknown branch (`pipeline.py:87-89`). The overwrite is live only for a shot that has estimated depth and ceiling together. | Bug 2 in the appendix. Test `test_estimated_geometry_is_at_most_tight` currently expects `tight`. |
| Vexcel counts | Rank 2 `mock-p2`: note “Parking short: 1 truck / 12 car spaces against 3 / 30 needed.” and a relaxed 220 m walk. `parking_status` was null. | `_skeptic` (`pipeline.py:152-161`), walk gate (`pipeline.py:168-171`, `258-261`). |
| Vexcel noise | Same pick: “Noise: freeway within 200 m.” Noise adds a score penalty (`pipeline.py:263`), not a hard drop. | `mocks/logistics.json` flag on `mock-p2`. |

Fixed-engine events use agent names `market_scout`, `interior_scout`, `logistics_scout`, and `skeptic` (`pipeline.py:344-354`, `216-218`) while those steps are ordinary Python. The first plan event says “Fixed engine”. This audit’s scout response was `engine: "fixed"`, `source_mode: "mock"`, `trace_url: null`. Do not call that trace a Deep Agents run.

### Deep Agents vs the Director path

`create_deep_agent` is real code on the scout engine only:

- `agent/deep.py:145` imports it; `_build_graph` (`deep.py:144-197`) builds director plus `market_scout`, `interior_scout`, `logistics_scout`, and `skeptic` subagents, a `StateBackend`, and `InMemorySaver`.
- Tools in `agent/deep_tools.py` call the same CoStar / Matterport / Vexcel functions. `build_shortlist` (`deep_tools.py:230-258`) then calls `pipeline._evaluate` and `pipeline._rank`. The model does not get to invent the shortlist. The skeptic subagent’s tool `get_shortlist` (`deep_tools.py:261-267`) is read-only; the objection text is model output on top of that shortlist.
- `runtime._deep_or_fixed` (`runtime.py:59-100`) runs that graph only when `TYPECAST_ENGINE=deep`, and on failure or 90 s falls back to `pipeline.scout` with a `fallback` event.
- `is_available` (`deep.py:42-47`) needs `deepagents`, a LangChain OpenAI or Anthropic integration, `LLM_API_KEY`, and `TYPECAST_LLM_MODEL`. Providers are only `openai` and `anthropic` (`deep.py:53-56`).

`post_production_plan` never calls this graph. `post_production_brainstorm` (`production.py:456-491`) calls `agent.models.get_provider().structured`. That adapter’s `_call` (`agent/models.py:75-107`) is OpenAI or Anthropic only. `configured()` (`models.py:33-34`) returns false for any other provider name, including a Gemini name.

This audit did **not** execute `TYPECAST_ENGINE=deep` and did **not** import a live LangSmith run. Unit tests that patch `create_deep_agent` are not a judging trace. Packet line, quoted in PRODUCTION-PLAN: “Calling the standalone deterministic solver is not by itself a Deep Agents integration.”

### Gemini API

No application module imports `google.genai`, `langchain_google_genai`, or a Gemini client. `rg` over the tree finds `GEMINI_API_KEY` / `GOOGLE_API_KEY` only where tests blank them (`agent/eval/harness.py`, `agent/tests/test_app.py`, `agent/tests/test_runtime.py`). Installed lockfile packages: `google-genai 3.3.0` required by `langchain-google-genai 4.5.0`, which is required by `deepagents`. That is a transitive dependency, not a call. Brainstorm and deep chat both refuse a provider other than OpenAI or Anthropic. **No runtime Gemini call exists at this commit.** Gemini-drafted source mentioned in lane status is coding assistance, which the team correction says does not qualify.

## Prize and track tables

### ENTERTAINMENT (the one main track)

| Requirement | Evidence at 6c73d57 | Demo moment | Gap | Verdict |
| --- | --- | --- | --- | --- |
| Opt into one main track. Public name is ENTERTAINMENT (overview URL above). Rules: only one of the six. | Product is a scene-to-shoot rehearsal: `GET /director` (`production.py:308`), `POST /api/production/plan`, stage in `director.js`. Repo prose says “Entertainment & Media”. | Open `http://127.0.0.1:8765/director` (server command in DIRECTORS-ROOM). Build the three-line demo script. Show two staging variants on a real indexed frame. | Devpost form was not opened here. `docs/devpost.md` is still headings. Select the control named ENTERTAINMENT, not a second main track. | **AT RISK** until a human selects that one track on the form. Thematic fit of the code is MET. |
| In-person pitch ≤ 2 minutes, judging 9:30 AM–2 PM (rules URL). Optional video ≤ 2 minutes (overview URL). | No pitch timer and no video file in this commit. | Time the script in [2-minute demo](#2-minute-demo-readiness). | Nobody on this audit timed a spoken pass or exported a video. | **UNVERIFIED** |
| ≥85% of code written in-window; credit libraries; do not embellish (rules URL). | Public repo `created_at` above is inside the window. README credits CoStar, Matterport, Vexcel, and the model providers. | If asked, point at README “How to work” and say which pieces humans directed. | Percentage not measured. | **UNVERIFIED** |
| Creativity / Utility / Charity / Avidity (rules URL). | Working mock plan, local A/B staging, reject/replan, labeled animatic, local export. Charity is the filming-logistics use (permission and unknowns stay unlabeled), not a scored claim. | One rejection that changes the assigned property, then play the animatic. | Utility on a scout’s real job is user-reported, not re-interviewed here. | **AT RISK** (demo must be rehearsed; charity should be one honest sentence, not a stretch) |

The other five main tracks (HEALTHCARE, SUSTAINABILITY, BUSINESS & ENTERPRISE, EDUCATION, SCIENCE & DISCOVERY) are **not** this submission. Choosing a second one violates the rules quote above.

### CoStar — Inside and Out

Public requirement (overview URL): at least 2 of 3 layers, agentic capabilities, a real person’s problem, spatial and visual understanding. Packet-as-quoted-in-repo (PRODUCTION-PLAN): data 30%, agentic depth 30%, usefulness 25%, demo/polish 15%. Team correction: cached licensed data counts when it substantively drives decisions and at least two of the three datasets do that.

| Requirement | Evidence at 6c73d57 | Demo moment | Gap | Verdict |
| --- | --- | --- | --- | --- |
| Matterport changes a decision | Solver pool and assignment use retrieval scores (`production.py:341-365`, `production_solver.py:155-170`). Scout drops `mock-p1` because fixture depth fails `needed_depth_m` (see dataset table). | Director: the assigned frame is the top fixture score (`mock-p1-s0` at trucks 0). Say “mock order is the fixture score” if `mode` is `mock`. Live: user-reported index, not rerun. | Mock mode ignores the typed scene (`search.py:365-368`). This audit confirmed identical scores for two different descriptions. | **AT RISK** on the offline fallback. **MET** as a code path when a real embedding index is loaded (`search.py:369-375`). Not re-executed live. |
| CoStar property/model identity changes a decision | Live conflict sets `eligible = False` (`production.py:399-401`). | Only on a machine with `cache/property_models.parquet`. Show a `costar` / `property_id/model_id` warning whose status is `conflict` and point at the property missing from `plans`. | Mock plan never emits `matched` (test, and `production.py:334-335`). This audit had no parquet. | **AT RISK** (implemented, not demonstrated in this run) |
| CoStar availability changes a decision | Checkbox path excludes unless status enum is `available` (`production.py:406-413`). Scout boolean adds a blocker (`pipeline.py:162-167`). | Director checkbox on **these fixtures wipes the plan** (executed). Scout rank 3 shows the CoStar sentence for `mock-p4`. | Director warning `availability/unknown` does not by itself remove the property. Scout says “occupied” when the status enum is absent (bug 2). | **AT RISK** |
| Vexcel parking changes a decision | `production.py:414-416`. Executed: `mock-p2` ineligible at 3 trucks / 30 cars; successor plan is `mock-p3`. Scout note “Parking short”. | Set Trucks 3 and Cars 30, Build, Reject `mock-p1`, show `mock-p2` excluded and `mock-p3` assigned. Read the warning `[vexcel] parking_capacity · insufficient`. | Default 0/0 does not exclude. `parking_status` is null while the UI also prints unknown (bug 1). Walk and noise do not change the Director plan. | **MET** for the count gate on the mock endpoint. Label the counts estimated. |
| Two layers on the same decision | Matterport score picks the property; Vexcel counts remove another property from that same plan. CoStar join/availability can remove a property when the live fields exist. | The trucks/reject sequence above is two layers (Matterport rank + Vexcel exclusion) on one plan response. | Do not claim all three on the offline checkbox. Join and status-enum availability were not executed. | **AT RISK** for a three-layer live pitch. **MET** for two layers on the executed mock plan. |
| Agentic (public) / 30% agentic (packet) | Director planner is `solve_plans`, not an agent. Scout fixed engine is deterministic Python with agent-shaped event names. Deep Agents exists on `/scout` only. | If the CoStar judge is at the Director table, say the planner is deterministic and the skeptic sentences on `/scout` are the fixed engine unless the response `engine` field is `deep`. | Showing Director status text as an agent trace would overclaim. | **AT RISK** |
| Cached licensed data | Live adapters read `cache/join.parquet` and `cache/vexcel/...` (`data/costar_tools.py:65-68`, `data/vexcel_tools.py:39-45`). They do not silently substitute fixtures (`costar_tools.py:68`, `vexcel_tools.py:45`). | Only with the private cache present and `TYPECAST_USE_MOCKS=0`. | This audit did not open licensed files. User-reported 343-property index stays user-reported. | **UNVERIFIED** in this run; the code path is present |

### Amazon — Best Practical AI Innovation

Public (overview URL): an AI that reasons, plans, takes action, and adapts for a real person. Packet-as-quoted-in-repo (PRODUCTION-PLAN): creativity, usefulness, implementation, UX each 25%. Team correction: any AI stack; no AWS-specific integration. Confirmed: no AWS SDK usage is required by the code that exists, and none was found as a product dependency in `requirements.txt`.

| Requirement | Evidence at 6c73d57 | Demo moment | Gap | Verdict |
| --- | --- | --- | --- | --- |
| Reason and plan | `solve_plans` enumerates location subsets and returns covered vs `uncovered_scene_ids` (`production_solver.py:147-188`). Fixed scout plans, ranks, and relaxes (`pipeline.py:274-294`). | Build a two-scene script. Read “Plan 1” and the pool note under the selector (`director.js:300`). | Mock fixtures often return **one** plan because one property covers every scene at the best fixture score (executed: only `mock-p1`). The dropdown is not an A/B location comparison until a second subset wins the sort. | **AT RISK** for the “two plans” beat on public fixtures. The planner itself ran. |
| Take action | Apply writes variant B only (`director.js:427-431`). Discard leaves state (`director.js:587`). Reject rebuilds with a forbidden id. Approval on `/approve` writes a local draft and returns `sent: false` (`scripts/smoke.py` assertion, re-run by `verify.py`). | Apply to B, switch to B, Reject location. | Do not say an inquiry was sent. | **MET** for local actions |
| Adapt | Same client state: `forbidden` survives and `build(true)` resubmits it (`director.js:102-103`, `117-122`). Edits are keyed `sceneId::shot_id` (`director.js:40-47`) and are not wiped by a new plan. `noteFrameChanges` (`director.js:50-56`) keeps old staging off the new frame until the director copies it. `/refine` reranks cached shots (`pipeline.py:361-385`). | Reject, see the old staging notice if the frame id changes, play the surviving variant. | Brainstorm does not run without a configured OpenAI or Anthropic model (executed 503). | **AT RISK** if the pitch needs the model beat offline |
| No AWS requirement | Team correction + PRODUCTION-PLAN line 20. Code uses the configured OpenAI/Anthropic adapters, local files, and FastAPI. | Say the stack in one sentence if asked. | None for AWS. | **MET** as a non-requirement |
| Someone would use it | User-reported scout scenes and the Director browser notes in DIRECTORS-ROOM. | The 2-minute story. | No new user interview in this audit. | **UNVERIFIED** |

### LangChain — best use of Deep Agents

Source: **packet-as-quoted-in-repo** (START-HERE p.16 note; PRODUCTION-PLAN: real Deep Agents behavior, subagents/filesystem, compelling demo; the deterministic solver alone does not qualify). **Not on the fetched public prize list.** Confirm the opt-in exists before entering.

| Requirement | Evidence at 6c73d57 | Demo moment | Gap | Verdict |
| --- | --- | --- | --- | --- |
| A real Deep Agents graph | `create_deep_agent` in `_build_graph` (`deep.py:179-197`) and the approval graph (`deep.py:261-265`). | `TYPECAST_ENGINE=deep` and `POST /scout`. The JSON `engine` field must be `deep`. A `fallback` event means the fixed engine finished the request (`runtime.py:91-100`). | Not run here. Director `/api/production/plan` does not call it. Default engine is fixed (`runtime.py:143`). | **AT RISK** |
| Subagents and filesystem | Four subagents and `StateBackend` (`deep.py:168-181`). Tools enforce call order (`deep_tools.py:233-241`). | A trace or the SSE `subagent_*` events **from a deep run**, after the response says `engine: deep`. | Fixed-engine events reuse those names. Tests monkeypatch `create_deep_agent` (`agent/tests/test_deep.py`). | **AT RISK** |
| Compelling demo of this flow | User-reported deep timings in the README. | Not the Director animatic. | Those timings were not reproduced. `trace_url` is null unless LangSmith returns one (README). This scout smoke’s `trace_url` was null. | **NOT MET** as a demo this audit can stand behind |

### MLH — Best Use of Gemini API

Source: public overview URL. Team correction: the running app must call the Gemini API. Coding in Gemini’s web chat does not count.

| Requirement | Evidence at 6c73d57 | Demo moment | Gap | Verdict |
| --- | --- | --- | --- | --- |
| Runtime Gemini API use | No call site. `ModelProvider` and deep chat accept only `openai` and `anthropic` (`agent/models.py:33-34`, `75-107`; `agent/deep.py:56-64`). Lockfile Gemini packages are required by `deepagents`, not imported by this app. | There is no honest Gemini moment. | Adding a decorative import would not be substantive and is out of scope for this docs change. | **NOT MET** |

### MLH — SpaceXSI raffle

Source: public overview URL. Qualify by using Cursor as the core coding agent, integrating a Grok Bot automation, describing both, and opting in.

| Requirement | Evidence at 6c73d57 | Demo moment | Gap | Verdict |
| --- | --- | --- | --- | --- |
| Cursor as core coding agent and a Grok Bot automation, described in the project | Lane status mentions Grok review comments. This file is one audit document. Neither fact is a workflow integration. | Do not spend pitch time on this. | Fit is **not established**. Conditional README text is in the appendix and must stay unused until it is true. | **NOT MET** |

### Other public prizes

Same columns, one row each. “No code path” means this audit found no substantive use.

| Prize | Requirement (source) | Evidence at 6c73d57 | Demo moment | Gap | Verdict |
| --- | --- | --- | --- | --- | --- |
| Best Overall Hack | Public overview: must excel on all four rubrics; track winners are not eligible for overall | Same product as ENTERTAINMENT | Do not promise stacking with a track win | Judging outcome | **UNVERIFIED** |
| Best Rookie Hack | Public overview: first-time hackathon participants | No participant-history record in the repo | Ask every member | History not in git | **UNVERIFIED** |
| Best Hardware Hack | Public overview: hardware / physical computing | No hardware project | None | Laptop UI is not hardware | **NOT MET** |
| MLH Solana | Public overview: Solana app | No Solana code | None | — | **NOT MET** |
| MLH Tiger Data | Public overview: Tiger Data / Postgres | No Tiger Data client | None | — | **NOT MET** |
| MLH Vultr | Public overview: Vultr deployment | No Vultr integration | None | — | **NOT MET** |
| MLH DEV writing | Public overview: publish on DEV | `docs/devpost.md` is blank; no DEV post | After the event, if at all | Not published | **NOT MET** |
| MLH MongoDB Atlas | Public overview: MongoDB Atlas | No MongoDB client | None | — | **NOT MET** |
| MLH GoDaddy domain | Public overview: register a domain | No domain artifact | None | — | **NOT MET** |
| ChatOverflow | Public overview: connected agent leaderboard, separate from the project | No connection evidence in the tree | None | Do not connect during the pitch | **NOT MET** |
| Photon 2.0 | Public overview, plus a guidelines URL. Packet quotes prizes; the guidelines page was **not** fetched here | `bridge/photon.mjs` header says it has not been run live. `bridge/README.md` says the same | None | Drafts are not delivery. Guidelines **UNVERIFIED** | **NOT MET** |
| Physical AI (Justin Bojarski) | Public overview: AI in a physical hardware build | No physical build | None | — | **NOT MET** |
| Capital One Nessie | Public overview: Nessie API endpoints must be used | No Nessie client. A budget table is not in the Director path | None | PRODUCTION-PLAN says a budget table would not qualify | **NOT MET** |
| Peri | Packet-as-quoted-in-repo: a real business or club consultation during the event, with person, role, and evidence. Public overview: intro to hiring partners | `docs/peri.md` is an empty template (cited by PRIZE-READINESS; not re-audited as a consultation) | None | Do not invent a filmmaker conversation | **NOT MET** |
| Arlequin forensics | Public overview: AI-driven forensics | Location search is not a forensic pattern tool | None | — | **NOT MET** |
| Arlequin social | Public overview: content plus connectivity | No social-graph analysis | None | — | **NOT MET** |

## 2-minute demo readiness

Serve the studio with mocks and no model, from a machine that has this commit and the lockfile environment:

```bash
TYPECAST_USE_MOCKS=1 TYPECAST_ENABLE_MODEL_PARSE=0 TYPECAST_ENABLE_VISION_RERANK=0 \
  uvicorn index.preview:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/director`. This audit did **not** open that page in a browser. The endpoint behavior below was executed with `TestClient` and blocked sockets.

The story order in the task starts with brainstorm. The code will not brainstorm until a scene has an assigned frame (`director.js:404-407`). Use this order. It is the same beats, in an order the UI can perform.

| Step | What to do and say | Code path | Offline / mock | If it fails |
| --- | --- | --- | --- | --- |
| 1. Script | Click **Demo script** (`director.html:26`, `director.js:522`). Three lines are already in the textarea (`director.js:5-10`). Say this is a shoot plan, not a listing search. | Local only | Works with no network | Empty script throws “Add at least one scene line.” (`director.js:70`) |
| 2. Plan | Set **Trucks 3**, **Cars 30**. Leave **Require available listing** unchecked on public fixtures. Click **Build plan**. | `build` → `POST /api/production/plan` (`director.js:97-108`, `production.py:323`) | Executed. `mode: "mock"`. One plan, property `mock-p1`, both scenes, shot `mock-p1-s0`. Scores are fixture scores. Reason on each shot: `MOCK fixture ranking (no semantic model)`. CoStar warning: `availability` / `unknown`. Vexcel warning on `mock-p1`: `parking_capacity` / `estimated` (`enough_parking: true`, 4 trucks / 45 cars). `mock-p2` is ineligible (`insufficient`, 1 / 12). | Network: `director.js:79-88` throws, status “Plan request failed”, previous `S.resp` is kept. Index down: HTTP 503 “Shot retrieval index unavailable” (`production.py:328-329`). Mixed mock/live adapters: HTTP 503 before search (`production.py:330-331`). |
| 3. A/B staging | Variant **A** and **B** are local (`director.js:382-386`, `shotData` at `43-47`). Add an actor on A. Switch to B: B is still empty. This is staging A/B, not two solver plans. | No route | Works offline | The plan dropdown has one option on these fixtures. Do not say “two location budgets” unless `plans.length` is greater than 1. Solver tests can return two budgets (`index/tests/test_production_solver.py:21-51`); the public mock catalog does not, because one property wins on score and coverage. |
| 4. Brainstorm | Type an instruction, or Start mic, then edit the transcript, then **Generate alternative**. | `generate` → `POST /api/production/brainstorm` (`director.js:404-425`, `production.py:456`) | **Model unavailable.** This audit: HTTP **503** `Configured model provider unavailable`. No `_call`, no socket. The proposal panel stays hidden. | Mic missing: `director.js:442` appends “type instead” and disables Start. Mic error: `director.js:450` “Type your instruction instead.” Abort or scene change drops the late response (`director.js:415`, `377-380`). Invalid model JSON: HTTP 502 (`production.py:488-489`). **Pitch fallback:** skip Generate. Drag actors on A and on B yourself (`director.js:559-574`). Say the model step needs the configured OpenAI or Anthropic key and is not Gemini. |
| 5. Apply or Discard | If a proposal returned: read the diff (“Changes versus current B”). **Apply to B** copies into B only (`director.js:427-431`). **Discard** clears it (`director.js:587`). Undo restores the previous B (`director.js:433-435`). | Local after the POST | Cannot be shown while step 4 is 503 | A late proposal whose scene key does not match is discarded (`director.js:428`). |
| 6. Reject with a source field, then replan | Narrate the evidence panel: `[vexcel] parking_capacity · insufficient` on the ineligible property (`director.js:270-277`, `282-291`). That exclusion already happened in step 2. Click **Reject location** on `mock-p1`. | `reject` → same plan route with `forbidden_property_ids` (`director.js:117-122`) | Executed equivalent: forbid `mock-p1` with 3/30. Plan properties become `['mock-p3']`. `mock-p2` stays ineligible. Edits for `s1::mock-p1-s0` remain in `S.edits`. If the new shot id differs and the old take has work, `noteFrameChanges` shows the frame notice (`director.js:50-56`, `333-346`). Staging is not auto-copied onto the new frame. | No assignment: button disabled (`director.js:369`). Clear rejections does **not** rebuild until Build is clicked (`director.js:527`). |
| 7. CoStar field, said honestly | Point at `[costar] availability · unknown` (`production.py:276-277`). Say the listing status enum is absent, so this is not a confirmed available set and not a rejection. Do not check **Require available listing** on these fixtures: this audit did, and both scenes came back uncovered. | Display plus the checkbox gate | Executed | On a live cache, a `property_id/model_id` status `conflict` is an actual exclusion (`production.py:399-401`). A status `available` plus the checkbox is the availability exclusion. Say those only when the warning status is on screen. |
| 8. Scout skeptic, only if you leave Director | `POST /scout` on the agent app (port 8000, not 8765). This audit: engine `fixed`, rank 3 note “Space is occupied…”. | `pipeline._skeptic` | Executed, sockets blocked, `trace_url: null` | If you say this sentence, say the status field was null and the word “occupied” is the boolean branch (bug 2), not a measured occupancy. Prefer the Director vexcel line for the 2-minute cut. |
| 9. Play | **Play** runs assigned scenes in order using each variant’s `duration_sec` (`director.js:203-218`). Canvas badge is constant: `UNCALIBRATED SCREEN-SPACE REHEARSAL · GEOMETRIC FIT UNKNOWN` (`director.js:4`, drawn at `185`). Header badges repeat it (`director.html:37-38`). | Local canvas | Works without a model. Needs the plan’s images from `GET /image/{shot_id}` (`director.js:125-132`, `preview.py:102-112`). | No assigned frame: “Nothing to play”. Image 404: “Indexed image unavailable”. Pause and Reset are local (`director.js:229-237`). |
| 10. Export | **Shoot pack** builds a static HTML file in the browser (`director.js:481-517`). Images are fetched and inlined. CSP is `default-src 'none'`. Copy says candidate plan, uncalibrated, geometric fit unknown. **Project JSON** is `exportSnapshot` (`director.js:471-479`). **Stage PNG** is the canvas. | `GET /image/{shot_id}` plus local download | Works for mock images if those files exist. This audit did not download a pack in a browser. | Export status string on failure (`director.js:517`). Licensed live frames must stay off the public repo (DIRECTORS-ROOM). |

### Honest-labels checklist

Say these out loud if a judge looks at the corresponding control.

- Mode comes from the response. Mock plan text includes “MOCK fixture ranking”. Mean similarity on that response is the fixture score, not a new embedding of the typed scene.
- `optimal_within_pool: true` means optimal inside the capped pool (`production.py:452`), not optimal over Los Angeles.
- Company moves are `max(0, locations - 1)` (`production_solver.py:179`). Not drive time.
- Unknown availability stays a warning unless the checkbox is on, and the checkbox demands the status enum.
- Unknown parking stays eligible. A false `enough_parking` excludes. Do not call a null `parking_status` both “unknown” and “insufficient” without the bug-1 caveat.
- Geometry warning on the Director plan does not change eligibility. The stage badge is not a lens calculation. Actor `scale` is screen space (`director.js:148-163`). No FOV, no clearance, no “fits” on a silhouette.
- The separate camera planner link is labeled unverified (`director.html:86`). `index/geometry.py` can return `fits` only when `measure_on_site` is false (`geometry.py:43-53`). Do not paste that word onto the animatic.
- No fake Deep Agents trace on Director. Fixed `/scout` events are labeled “Fixed engine” in the plan text (`pipeline.py:329`). `trace_url` stays null unless a real run URL comes back.
- Approval `sent` is false. Marketed availability is not vacancy and not a film permit (README).
- Brainstorm audio, if the mic is started, is the browser speech engine (`director.js:439-452`). The page already says the speech service may process audio (`director.html:74`). That is not the Gemini API.

### Likely judge questions

**Why these buildings?**  
Matterport retrieval order fills a pool of three properties per scene (`production.py:357-365`). The solver picks the subset with the best coverage and mean score (`production_solver.py:36-45`). On the mock server the order is the fixture score and the reason string says so (`search.py:390-391`). On a live index the same function uses the embedding dot product (`search.py:369-375`). This audit ran the mock branch only.

**What did CoStar change?**  
On the executed mock plan, the availability field produced a `costar` / `availability` / `unknown` warning and did not remove anyone until “Require available listing” was checked, which removed everyone because the enum is missing. The live join removes a candidate only on id conflict (`production.py:399-401`). The scout rank-3 line for `mock-p4` is the `available: false` boolean, worded “occupied” (bug 2).

**What did the aerial data change?**  
With 3 trucks and 30 cars, `mock-p2` left the feasible set and the plan after rejecting `mock-p1` was `mock-p3`. The warning source is `vexcel`, field `parking_capacity`. Counts are `estimated: true`. Walk and noise are visible and, on this route, do not change the assignment.

**Is this Deep Agents?**  
The Director button is `solve_plans`. Deep Agents is `create_deep_agent` behind `TYPECAST_ENGINE=deep` on `/scout` (`deep.py:179`, `runtime.py:155`). We did not run that engine in this audit. If the response `engine` is `fixed`, say so.

**Where is Gemini?**  
It is not called. The brainstorm provider is OpenAI or Anthropic (`agent/models.py:75-107`).

**Does the character block the doorway?**  
No. The badge says geometric fit is unknown (`director.js:4`). Room metrics on the evidence card are “not calibrated to stage” (`director.js:286`).

**Did you email the landlord?**  
No. `/approve` saves a local file and returns `sent: false`. The smoke inside `verify.py` checked that.

**What is the accuracy number?**  
Do not quote 0.2706 unless you are holding [docs/team/eval.md](../docs/team/eval.md) and you describe it the way that file does: user-reported fixed-engine macro pooled pipeline recall@10 on 15 held-out scenes, first-ten membership in a judged top-40 pool, not final-card quality. This audit’s mock eval printed `recall@10: N/A` because zero scenes were labeled. The mock latency in that run (p50 3.54 ms) is a fixture timing, not the live 14.539 s figure.

**Can we see it with the network off?**  
Plan, reject, A/B staging, playback, and export of mock images do not need a model. Brainstorm returns 503. Query text will not reshuffle mock results.

## Ranked release risks

1. **Parking label contradicts the exclusion** — `index/production.py:288-292` and `414-416`, displayed at `index/director.js:254` and `266`. Executed: `parking_status: null`, `enough_parking: false`, warning `insufficient`, property removed from the successor plan. The panel’s status word for that null is “unknown”. A judge can hear both. Patch in the appendix. **Release risk for the CoStar/Vexcel sentence.**

2. **Scout says “occupied” and “available” with a null status enum** — `agent/pipeline.py:59-64` and `162-167`. Executed on `mock-p4` and on rank 1 `mock-p3` (reason says “available” while `availability_status` is null). The Director path warns unknown instead. A test currently requires the word “occupied” when the boolean is false and the enum is absent. Patch in the appendix. **Do not read the rank-3 sentence as a measured occupancy.**

3. **Estimated geometry can be relabeled `tight` and hard-failed** — `index/geometry.py:53` returns `unknown` when `measure_on_site` is true. `agent/pipeline.py:90-91` overwrites that to `tight` once depth and ceiling exist, and `_failed_fit` (`pipeline.py:98-102`) still compares the number. Current enrichment stores `depth_m: None` (`index/rooms.py:384`), so today’s null-depth shots stay unknown. The overwrite is still the wrong word the moment an estimated depth is stored. Public mock shots set `measure_on_site: false`, so the offline scout says `fits` / `tight` on invented depths (p1 removed, p3 “shot fits”). **Do not say those mock fits are surveys.**

4. **“Require available listing” empties the public-fixture plan** — `production.py:406-413`, `director.html:25`. Executed: zero assignments. Fail-closed is honest. It will look like a crash if someone checks the box during the offline pitch. Leave it unchecked unless the loaded properties have `availability_status: "available"`.

5. **Mock Director ranking ignores the scene text** — `index/search.py:365-368`. Executed: two descriptions, identical scores. A live embedding index is a different branch and was not run. If the laptop is on mocks, do not claim the kitchen line outranked the hallway line.

6. **One solver plan on the demo fixtures** — executed `plans` length 1 (`mock-p1`, or `mock-p3` after the parking reject). Variant A/B still works. The “two location budgets” beat is not on screen until the catalog produces a dominating second subset.

7. **Deep Agents is not on the Director path, and this audit did not run it** — `production.py:323` vs `deep.py:179` and `runtime.py:143-155`. Fixed-engine SSE names look like subagents (`pipeline.py:344`). LangChain is packet-only on the public pages fetched here. Enter it only if the form lists it and a deep response is in hand.

8. **Brainstorm is a hard dependency on a non-Gemini model and the network** — executed 503 with keys blanked and sockets blocked (`production.py:464-465`, `agent/models.py:33-34`). The 2-minute fallback is manual A/B staging.

9. **Gemini API and SpaceXSI are not met.** Saying either in the pitch is an embellishment under the rules quote. Conditional SpaceXSI wording is in the appendix and is not a claim.

10. **Submission surface** — `docs/devpost.md` is empty (Discord names blank). 85% authorship, check-in, and the live Devpost form were not verified. Use 8:00 AM, not the 8:30 schedule cell. Licensed frames and `cache/` stay out of the public repo.

## Commands this audit ran

Python **3.12.3**. Virtualenv `/tmp/typecast-venv` from `requirements.lock.txt` (the tree’s `.venv` module was missing; `python3.12-venv` was installed in the VM). Working directory `/workspace`. Commit `6c73d57`.

### `TYPECAST_USE_MOCKS=1 python -m pytest -q`

```text
364 passed in 6.69s
PYTEST_EXIT:0
```

No failures, no skips in this run. The user-reported “363 passed, 1 skipped” was not this process.

### `python scripts/verify.py`

Exit **0**. Pytest inside the gate: `364 passed in 6.09s`. Then:

```text
PASS: mock search -> validated picks -> same-thread refinement -> SSE result -> no-send approval
```

E2E (fixed engine; model calls, tracing, and network disabled by the script):

| Stage | elapsed ms |
| --- | ---: |
| First SSE event | 3.57 |
| SSE result | 7.72 |
| Refine request | 6.82 |
| Approve request | 1.71 |

Search calls before and after refine stayed `search_shots: 1`, `search_costar: 1`. The script printed that progress arrived while search was blocked, refine reused the thread, and a yes approval saved a draft with `sent=false`.

Mock evaluation (the script’s own line is `mock run: not a result`):

```text
Scenes: 20 attempted, 20 succeeded; 0 labeled scenes scored, 20 unlabeled skipped
recall@10: N/A
Latency: p50=3.54 ms, p95=6.99 ms
Engine: fixed; source mode: mock
```

Those milliseconds are the unlabeled mock harness, not a retrieval-quality result and not the user-reported live benchmark.

### Offline production and scout smoke

Not a committed test. In-process `TestClient` after `socket.socket.connect` and `connect_ex` were patched to raise, and `ModelProvider._call` was patched to raise. Keys blanked, including `GEMINI_API_KEY` and `GOOGLE_API_KEY`. `TYPECAST_USE_MOCKS=1`, model parse and vision off. **`ATTEMPTS []`** at the end: no socket and no model call.

| Call | Result |
| --- | --- |
| `POST /api/production/plan` on `index.preview:app`, two scenes, trucks 0, cars 0 | 200, `mode: mock`, pool `mock-p1, mock-p2, mock-p3`, one plan `mock-p1`, both scenes `mock-p1-s0`, mean about 0.900 (float32 0.8999999761581421), every shot reason `MOCK fixture ranking (no semantic model)`, CoStar warning `availability/unknown`, Vexcel warning `parking_capacity/estimated` |
| Same route, descriptions replaced with an unrelated submarine line and a desert line | 200, **scores unchanged** |
| Same route, trucks 3, cars 30 | 200, `mock-p2` `eligible: false`, `enough_parking: false`, `parking_status: null`, warning `insufficient`; plan still `mock-p1` because that property still has 4/45 |
| Same route, `require_available: true`, trucks 0 | 200, **no assignments**, uncovered `s1` and `s2`, ineligible `mock-p1`, `mock-p2`, `mock-p3` |
| Same route, `forbidden_property_ids: ["mock-p1"]`, trucks 3, cars 30 | 200, plan `['mock-p3']`, `mock-p2` still ineligible |
| `POST /api/production/brainstorm` | **503** `Configured model provider unavailable` |
| `POST /api/production/plan` on `agent.app` | **404** |
| `POST /scout` scene `INT. 1980s POLICE STATION, NIGHT. Parking for 3 trucks and 30 crew cars.` | 200, `engine: fixed`, `source_mode: mock`, `trace_url: null`, `gave_up: ['parking distance', 'era']`. Rank 1 `mock-p3` note “No objection.”, reason says “available” with `availability_status: null`, `fit_status: fits`. Rank 2 `mock-p2` parking-short and 220 m. Rank 3 `mock-p4` “Space is occupied, not listed as available.” |

`check_fit` on the mock catalog in the same environment: `needed_depth_m(24, 6) == 8.783`. All three `mock-p1` shots are `tight` / `fits: false`. `mock-p3-s0` is `fits: true`. `measure_on_site` is false on those rows.

### Not executed

- Browser load of `/director`, click-through, playback, or a downloaded shoot pack.
- `TYPECAST_USE_MOCKS=0`, private join, Vexcel cache, or the embedding index.
- `TYPECAST_ENGINE=deep`, LangSmith, OpenAI, Anthropic, or Gemini.
- A timed spoken two minutes, a video, or the Devpost form.
- Authorship percentage, team check-in, or sponsor opt-in state.
- Photon guidelines page, CoStar/Amazon/LangChain packet PDFs (only the repo’s existing quotations).

## Appendix — proposed patches (not applied)

### Bug 1 — null parking status still excludes, and the UI prints “unknown”

`_lookup_logistics` treats every status other than the string `"unknown"` as known, so a missing status with integer counts sets `enough_parking` and can set `eligible = False`. `director.js` `sourceStatus` then renders null as `unknown`.

Promote legacy estimated counts to status `estimated` so the label matches the decision, and do not treat a missing status as known.

```diff
--- a/index/production.py
+++ b/index/production.py
@@ -286,10 +286,17 @@ def _lookup_logistics(property_id: str, trucks: int, cars: int) -> tuple[dict[s
         logi = _as_dict(evidence)
         if logi is not None:
             # The shared Logistics contract has counts and a status, not a feasibility flag.
-            known = (logi.get("parking_status") != "unknown"
+            status = logi.get("parking_status")
+            if (status is None and logi.get("estimated") is True
+                    and logi.get("truck_spaces") is not None
+                    and logi.get("car_spaces") is not None):
+                # Public fixtures store estimated counts without the status enum.
+                status = "estimated"
+                logi["parking_status"] = status
+            known = (status in {"measured", "estimated"}
                      and logi.get("truck_spaces") is not None
                      and logi.get("car_spaces") is not None)
             logi["enough_parking"] = enough_parking(evidence, trucks, cars) if known else None
```

`enough_parking` still compares counts when status is `estimated` (`data/vexcel_tools.py:92-98`). A true `unknown` or a null status that was not promoted stays eligible. Update `test_known_insufficient_parking_prevents_assignment` only if a fixture relied on a null status to exclude; the existing test sets `parking_status="measured"`, so it should keep failing closed. Add one fixture with `parking_status=None`, `estimated=True`, and short counts, and expect status `estimated` plus `eligible is False`.

### Bug 2 — missing availability enum is spoken as “available” or “occupied”

Director already warns `unknown` (`production.py:276-277`). The scout reason does not. `_availability` maps a missing enum through the boolean. `_skeptic` then says “occupied” on the boolean-false branch. `test_occupied_unknown_fit_and_parking_short_are_blocking_not_small_score_penalties` asserts the substring `occupied` and would need that assertion pointed at “not listed as available” or “unknown”. `test_live_unknown_availability_capacity_and_noise_are_visible` already forbids “occupied” when the enum is `unknown`; keep that.

```diff
--- a/agent/pipeline.py
+++ b/agent/pipeline.py
@@ -57,11 +57,11 @@ def _number(value, unit: str = "") -> str:
 
 def _availability(prop: Property) -> str:
-    if prop.availability_status is not None:
-        return {"available": "available", "not_available": "not listed as available",
-                "unknown": "unknown"}[prop.availability_status]
-    return "available" if prop.available else "occupied"
+    return {
+        "available": "available",
+        "not_available": "not listed as available",
+        "unknown": "unknown",
+        None: "unknown",
+    }[prop.availability_status]
 
 
 def _noise(logi: Logistics) -> str:
@@ -160,11 +160,12 @@ def _skeptic(prop: Property, fit: ShotFit, logi: Logistics, req: Requirements)
                      f"against {req.trucks} / {req.cars} needed.")
         blockers += 1
     if not prop.available:
-        notes.append("Availability is unknown; confirm listing status before booking."
-                     if prop.availability_status == "unknown" else
-                     "Space is not listed as available." if prop.availability_status == "not_available" else
-                     "Space is occupied, not listed as available.")
+        if prop.availability_status in {None, "unknown"}:
+            notes.append("Availability is unknown; confirm listing status before booking.")
+        else:
+            notes.append("Space is not listed as available.")
         blockers += 1
```

The boolean still adds a blocker when `available` is false, so rank order for `mock-p4` stays a blocked alternative. The sentence stops claiming occupancy. When `available` is true and the enum is missing, the reason text becomes “unknown” instead of “available”, matching the Director warning. That is a wording change on rank 1 of the mock scout, not a rank change.

### Conditional SpaceXSI README paragraph

**CONDITIONAL.** Do not paste this into the README unless the team has actually used Cursor as the core coding agent for this repository and has integrated a specific Grok Bot automation, and intends to opt into the raffle. This audit did not establish that.

```markdown
## SpaceXSI raffle (conditional)

We used Cursor as the core AI coding agent while building Typecast during HackPrinceton Fall 2026. We integrated a Grok Bot automation into that workflow by <one concrete sentence: what the bot watched or did, and where the result landed>. This note is only for the MLH SpaceXSI raffle opt-in. The Typecast application does not call Cursor or Grok at runtime. Brainstorm and the deep scout use the configured OpenAI or Anthropic model. There is no Gemini API call.
```

Replace the angle-bracket sentence with a true one, or leave this paragraph out.
