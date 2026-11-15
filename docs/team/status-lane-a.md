# Current Owner 1 integration status

**Business decision update — November 15, 2026:** user chose Business/Enterprise main track. Merged latest dev `dd9a603` into PR #43 branch (`4963076`). Added optional employee-home/base pin and one-way drive range filtering in the production planner; bounded OSRM table routing, unknowns excluded, no live traffic. Added editable cost comparison and day-rate reference example (three assumed billable commercial scout-manager days × $957.58 = $2,872.74 gross labor before tool costs). Added free-form scene directions with approved notes + undo and explicit upload-gated, separately labeled imagined image previews. No source image or 3D geometry overwritten. No private data, home pin or credentials committed. Scope/contract notes in `docs/team/CONTRACT-CHANGES.md`; buyer/pitch/quote provenance in `docs/BUSINESS-CASE.md`.

Verification: `python scripts/verify.py` 693 passed/7 skipped plus smoke/SSE/refine/unsent-draft E2E; full 10 Node suites 233 passed/1 browser-only skip; clean Chromium 19 checks including stale-scene image rejection and clearly SYNTHETIC proposal/image responses, no paid calls. One public-coordinate OSRM table probe returned HTTP 200 (11.655-minute estimated route; no traffic). Production image provider, private-cache commute acceptance and GPU acceptance are not established by these tests. User-reported quote permission now exists; original Peri evidence/affiliation still pending. Human must choose Business/Enterprise on Devpost; no submission, deployment or dev/main merge performed by coordinator.

**Update 2026-11-15 (draft PR #43, lane `ai/director-production-decisions`, not merged at the time of writing):** Film | Community mode control, Community planning, screenplay intake and per-mode draft recovery, plus a second independent-review pass (colon-safe site keys, incomplete capacity never counted as verified, per-mode draft holds, unreadable drafts set aside, literal clear, community files drop film data) and the published track decision `docs/TRACK-SELECTION.md`. `origin/dev` `4b4f92c` merged. Code head `b666fc5`; gates: verify.py 672 passed / 7 skipped; Node 209 pass / 0 fail / 1 skip (210 tests, incl. `web/tests/cast.test.mjs`); web package tests 18 pass; clean Chromium mock journeys (49 + 20 checks). Root pushed `9bbd456`; later commits unpushed. Blockers: none for code; real cache (`check_walk.py`), live model/trace, microphone, CI, real organizer review and Peri evidence are laptop/human checks. See `HANDOFF.md`. Older entries below are historical.

Updated 2026-11-14 21:10 UTC. Published feature head a982125 in PR #22: full gate 539 passed / one skipped, smoke, fixture SSE/refinement/unsent-draft checks and exact-head CI success. Final documentation closeout follows. Earlier entries below are historical snapshots.

Shared `agent.app` serves Director and the merged full viewer on port 8771. Commit `5da12ac` adds the actual `plan_production_shoot` Deep Agents tool; fake-model graph dispatch is tested. A live trace of this new tool is not yet verified. The deterministic planner and UI notices are not an agent trace.

Browser verified: real plans/rejection, independent A/B staging, reviewed text proposals, playback and exports. Scan viewfinder lens/ratio/drag/frame grab/reopen were checked with four horizon cube faces. Orientation is scan-relative, not world-aligned; the 6 m depth illustration is an assumption. An actual silent 1280×720, 4.921 s WebM downloaded and played with a real frame and moving Mara. Project import has 29 pure tests, but browser import remains untested after extension file upload was blocked.

Grok audit fixes now have passing regressions for rejected properties resurfacing in faulty backend responses, missing/invalid statuses revealing availability or parking claims, unsafe exported provenance IDs and negative-time actor extrapolation. Adapted the audit DOM fixture to current reel/import/viewfinder controls. Playback progress remains display-only. Final combined gate is recorded in PR.

Private data limit: the older local 11-column join lacks richer availability fields and local Vexcel logistics. PRs #12/#21 provide no private bundle link; PR #21 says the data is on Owner 2's laptop. Exact property/model mapping remains separately checked. Discord checked: the integration captain's 14 November 15:01 Eastern reply about PR #21 says the expanded private index/Vexcel caches and final demo are on that teammate's laptop. The reported inventory is 343 properties, 10,568 views, 327 available indexed properties, Vexcel caches for 344 properties and nine available demo properties. These are teammate-reported counts, not a local reproduction. A second copy is unnecessary for the planned demo; pull this lane on the demo laptop and verify its current data there. This local checkout retains the older 11-column join and no Vexcel cache. The judged demo may show user-authorized licensed imagery; no private bundle or licensed-image export goes into public Git or public uploads.

Labeling is complete. Expanded v2 PR #27 reports 73.33% precision lower bound and 30.48% macro recall, with repeated review by the same reviewer rather than a new holdout. Root did not reproduce it. Keep this separate from original 608-view and earlier expanded results; these do not measure general accuracy, Director/solver quality or filmmaker validation. No further labeling is needed.

Next: live new-tool trace if claimed, browser project-import verification when upload is available, demo rehearsal/fallback and human submission/sponsor opt-ins. See [Director's Room](../../index/DIRECTORS-ROOM.md) and [demo script](../../index/DEMO-SCRIPT.md).

---

# Owner 1 planning milestone

Updated 2026-11-14 12:32 UTC. Branch lane-a / PR #6.

Added Gemini-drafted and locally reviewed MMR diversity, hard property/scan caps,
visual query briefs, manually oriented floor-plan FOV/clearance estimates, room
polygon retention during enrich/bootstrap, scene lookbook HTML/JSON export, and
20-scene blinded local relevance labeling (15 held-out / 5 tune). Labels remain
empty. Metrics segregate reviewer type, source mode and split and are explicitly
pooled, not whole-catalog recall. Shared contracts are unchanged.

Live enrichment: 19/19 room model requests succeeded, 600 room assignments,
488 ceiling estimates; validated polygon coverage is 25 rooms / 164 indexed views.
All planning fit statuses remain unknown. Missing boundaries have no guessed plan.
Browser SDK connection succeeds at localhost; 127.0.0.1 is outside the key's
existing referrer allowlist. Scan navigation and viewer FOV are under browser
verification; cube-to-world image orientation is not claimed.

Targeted gate: 75 index tests pass; studio.js passes node --check. Full combined
Windows verification and browser/export evidence will be recorded below.

---

# Owner 1 status

Updated 2026-11-14 10:59 UTC. Branch lane-a, PR #6 into dev.

Implemented real cosine retrieval over private CLIP embeddings, strict cache/model
validation, pre-top-k filters, cross-model/property example matching, atomic index
generation builder, bounded/resumable Matterport horizon importer, and evaluation
CLI. Estimated geometry now returns explicit unknown status with current shared
ShotFit schema. No shared schema or root dependency edits.

Verified locally: 65 index tests pass, including recovery and local-image isolation.
The initial integrated baseline passed 46 tests plus API smoke. At fcc9a1d, both
push and PR Linux CI passed the full shared gate (117 tests, smoke, SSE and mock
evaluation). Latest feature code 9faab10 is also green in CI. Combined with the
separate Windows-fix PR #8, local verification passes 139 tests plus API smoke,
SSE/refinement/no-send and the unlabelled 20-scene mock evaluation.
Controlled vectors cover ranking, null filters, corruption, duplicate IDs and
source exclusion. Synthetic HTTP clients cover retries, partial failure, unsafe
redirect refusal and resume. Import/build/search generation roundtrip passes.

LIVE evidence: individual sponsor keys issued for registered Typecast team;
authentication retrieved 39 panoramas for the sponsor reference model. The private
catalog now indexes 608 actual horizon views from 19 distinct catalog-linked
properties. One additional model denied access and was reported. Real CLIP text
queries change order; source model/property are excluded from example matching;
top images decoded and rendered at 2048 pixels in Chrome. Browser warm query was
0.04 seconds; first encoder load was 5.72 seconds. These are observations, not a
latency benchmark. Official live schema verification found panorama anchor floor
and room references plus source rotations: enrichment now assigns 600 views to
rooms and supplies 488 ceiling estimates. Directional depth remains unknown.
No human-labelled retrieval quality metric has been measured.

Integration: read index/README.md. Property IDs are literal costar_property_id from
the sponsor catalog and need agreement with Owner 2's private records. Image URLs
are /cache/views/...; the standalone preview serves only indexed view files.
Cube-local headings are not compass bearings or validated SDK tour poses.
Owner 3 consolidates optional index/requirements.txt before broad team installation.

One-command bootstrap is live verified: `python -m index.bootstrap --max-models 20
--max-sweeps 8` downloaded the official catalog, resumed 608 views across 19
available models, enriched room evidence with zero room-fetch failures and
published a complete index. No manual catalog/model-pair preparation is required.

A current local Typecast-Owner1-Team.zip (no credentials) was prepared for private
team handoff outside the public repository. Extract into the repository root to
use the prebuilt index. Alternatively re-ingest with your own sponsor key and an
agreed model list through the one-command bootstrap.

Remaining: 20 human-labelled held-out scenes, Owner 2's property/aerial alignment,
and Owner 4's shared viewer integration. Exact SDK tour-pose alignment is unverified;
links open the correct model without promising a matched camera. Windows-only
shared dev bugs have fixes in PR #8: offline harness socketpairs and Windows C:
image paths. Owner 3 should inspect that separate fix; its CI and the combined
Windows gate pass. Grok audited the code and identified recovery and
configuration issues now fixed; Gemini supplied retrieval, ingestion and room
drafts. Claude login works but quota blocks review. User explicitly authorized
the sponsor agreement and confirmed hackathon-demo permission. Raw data/keys
stay out of public GitHub; event-end deletion requirements still apply.


Browser milestone: SDK connected at localhost; selected scan was confirmed against
Camera.getPose().sweep after matching observed SDK IDs. Lens zoom returned an
observed 58.1 degree FOV against 54.8 requested, displayed honestly; a live projection
readout was added to reflect subsequent camera changes. Current SDK camera pose
can be captured in lookbook JSON. Self-contained lookbook saved/inspected locally:
567,910 bytes, embedded image, source facts and lens setup, no image-server dependency.
76 index tests pass including export containment/escaping and reviewer attribution.
The combined pre-export gate passed 185 tests; final gate is recorded next.
Human labeling remains a requested teammate action, and image-heading alignment
remains explicitly unverified. No accuracy metric has been fabricated.


Final combined gate: scripts/verify.py exits 0 with 186 passed, API smoke,
concurrent-progress SSE/refinement/no-send checks, and 20/20 unlabelled mock scenes.
GitHub push and PR checks at bcb9c39 succeeded. A final browser fix makes lens edits
recalculate on input (35 mm / Super35 shows 39.2 degrees and 4.22 m subject distance).
The refreshed team ZIP passes integrity validation: 619 files, 608 images,
300,445,311 bytes. Output handoff and standalone lookbook are updated.


Current integration and human-action handoff: [index/HANDOFF.md](../../index/HANDOFF.md). User will label later; no labels or accuracy claim were added.


Human evaluation complete:20/20 live scenes saved,15 test/5 tune. Held-out pooled recall@10:38.9% cosine,30.5% diverse. Aggregate methodology/results are in index/EVALUATION.md; labels remain private. Human labeling is no longer a blocker.
## Owner 3 geometry question — 2026-11-14 16:00 UTC

Can room outlines establish depth along each indexed view heading using a verified room-to-panorama coordinate transform? Cube headings are local and image-heading alignment remains unverified. Please provide the transform and a checked example before asserting directional depth. Until then `depth_m=null` and shot fit remains “unknown, measure on site.” Coverage expansion preserves existing shot IDs, vectors and provenance.

## Director's Room milestone — 2026-11-14T19:28:18Z

Based on dev cf716c1 and solver d3ba812. Claude/Gemini/Grok independently critiqued and approved the bounded animatic scope; Claude drafted the UI, Gemini the API/join helper, and Sol medium reviewed lifecycle/privacy/validation with root integration. Implemented standalone `/director`: real multi-scene candidate plans, reject/replan, exact CoStar property/model join checks, manual frame choice within a property, three generic actors, linear motion, two independent variants, durations/dialogue, validated text/optional-speech brainstorm proposals with Apply/Discard/Undo, PNG/JSON/static embedded-image shoot-pack export. No 3D registration, occlusion, video render, music tool or fake agent trace.

Verified: 363 passed/1 skipped + smoke/offline E2E/mock evaluation gate; node syntax and UI snapshot/privacy checks; browser real three-scene build, A/B isolation, playback/pause, reviewed real proposal, actual downloaded exports and rejected-location frame review. Real API observations: cold two-scene plan24.66s; warm plan+replan2.69s; brainstorm4.82s. These are individual timings. Exports and licensed frames remain local, outside Git.

Handoff and actual limits: [index/DIRECTORS-ROOM.md](../../index/DIRECTORS-ROOM.md). Owner 3 must integrate the new planner as a genuine Deep Agents tool/shared endpoint; Owner 4 can link/incorporate the studio. Updated Owner 2 private join/Vexcel cache is needed for richer availability/logistics proof; current11-column join produces unknown metadata. Exact property/model mapping is checked separately and known conflicts are excluded. Source-image heading/metric actor fit remain unverified. Text provider reuses the user's authorized existing key privately; no credentials changed in Git. Next: integration review, stage rehearsal/fallback recording and human sponsor opt-ins/submission.

Published studio commit5a38d63 in PR#22, then merged updated dev3a49aad cleanly. The merged report completes the expanded frozen human benchmark (15test of20reviews, macro pooled pipeline recall@10 .2706, p50/p95 14.539/19.693s). These are Owner 3's retained live measurements, not a reproduction from this checkout's smaller private cache. No further labeling is required for that benchmark. Original608-view results remain separate. Eligibility and integration notes were updated after reading the new report.

## Update — Save the scene (`39077b6ca7bafd0f127dbbb307ff1fc69fbbdef3`)

- **State:** Code complete at `39077b6ca7bafd0f127dbbb307ff1fc69fbbdef3` on draft PR #43 (`ai/director-production-decisions`, includes frozen `origin/dev` `4b4f92c`), prepared for publication. PR #43 remote head and CI are authoritative once published; no `dev`/`main` merge.
- **Gates:** `python scripts/verify.py` **672 passed / 7 skipped** (including 2 Windows symlink cases); 9 Node suites **228 passed / 1 browser-only skip / 0 failed / 0 TODO**; clean Chromium QA **33/33 checks true** (honest non-result on default unknown-capacity mock fixtures; positive QA used clearly labeled `SYNTHETIC` intercepted complete plans). No provider calls.
- **Pending Human/Live Items:** Captain's laptop real-cache check (343 properties / 10,568 views), GPU/splat walk, live model / `plan_production_shoot` trace, microphone, filmmaker feedback, track opt-ins, and Devpost submission.

## Producer workflow reliability pass — 2026-11-15 (UTC, see commit)

- **Base:** `c549e66`. Branch `ai/claude-business-hardening` (local only; no push, no dev/main merge).
- **Done:** fixed stale/unbound producer decisions (rejected-list staleness, decision text bound to plan fingerprint), import races and project mixing, hourly-mode blank day rate, cent-accurate currency, negative-savings wording, literal storage opt-in/clear, broader credential screening. Details, base-failure evidence and limits: [docs/BUSINESS-ACCEPTANCE.md](../BUSINESS-ACCEPTANCE.md).
- **Verified:** Node 281 pass / 0 fail / 1 skip; Python 693 pass / 7 skip; clean Chromium against a local synthetic mock server 13/13. New Node tests failed 12/22 on base.
- **Mock/synthetic:** browser check uses a fabricated mock-mode plan; no live data, routing, provider or paid call was made.
- **Next:** coordinator review of the diff; optional real-browser timing check of a slow file read; confirm with a producer which labor/vehicle terms are actually cancelable.
- **Blocker:** none.
