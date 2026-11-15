# Typecast: current track and evidence audit

**Update 15 November 2026:** the track decision is now summarized in `docs/TRACK-SELECTION.md` (one main track, Entertainment and Media; sponsors CoStar, LangChain deep agents and Amazon, whose packet p.15 accepts any stack and requires no AWS; Peri conditional on real affiliation and evidence; Photon not run). Community planning exists as a mock-tested prototype with no established benefit. The measurements below are the earlier owner-reported record and are preserved unchanged. Previously updated 14 November 2026, 21:12 UTC. Base includes latest dev merge `a982125`, shared production integration `5da12ac` and the merged full viewer; export/hardening code is published in PR #22. **Final integrated gate: 539 passed, one skipped**, smoke, streaming/refinement/unsent-draft E2E and 20/20 unlabeled mock attempts. [Exact-code-head CI passed](https://github.com/Tecncentral/typecast/actions/runs/43641636989). Mock evaluation is not retrieval accuracy.

Recommended slate: **ENTERTAINMENT** (the official main-track name), **CoStar**, **Amazon**, and **LangChain with an actual deep-agent demonstration**. Select one main track and confirm available sponsor opt-ins in the submission form. This is an evidence audit, not a submission or organizer eligibility determination.

## Track slate

| Track | Requirement from the supplied event packet | Current evidence and remaining proof |
| --- | --- | --- |
| ENTERTAINMENT | One main track; a creative media application. | Strong fit: real-location retrieval, multi-scene grouping, reviewed A/B blocking, playback, static shoot pack and silent WebM rehearsal. Shared app and full viewer are integrated. Rehearse the useful creative before/after within two minutes. No filmmaker consultation or endorsement is established. |
| Inside and Out: AI for the Built World — CoStar Group | At least two of CoStar/Matterport/Vexcel combined meaningfully; agentic reasoning and visual/spatial understanding. | Defensible local two-layer path: exact supplied CoStar property/Matterport model identity checks group real Matterport retrieval results into fewer production locations; known mapping conflicts are excluded. Show the identity and its effect on grouping/location budget. Rich availability and Vexcel filtering require the updated private bundle and a current run; root has not verified those richer constraints here. Badges alone do not satisfy the requirement. |
| Best Practical AI Innovation — Amazon | Working prototype, clear user/use case, documentation and pitch; any AI stack is allowed. | Good fit through the implemented scout/rehearsal workflow. AWS is not mandatory under the packet. Demonstrate an actual before/after and document limitations. Local approval retains an unsent draft; it does not deliver an owner inquiry. |
| Best use of deepagents — LangChain | Build a deepagent. | `agent/deep.py` constructs actual deep-agent graphs with source delegates and approval behavior. Older live deep runs/traces are reported in the merged lane-C evidence. The new `plan_production_shoot` tool is implemented in the director graph; fake-model graph dispatch was checked. No live run/trace of that new tool is verified yet. Demonstrate visible real calls, or clearly present the existing scout flow separately. The bounded solver and UI status text are not an agent trace. |
| Photon 2.0 | Sponsor-specific messaging-agent guidelines and a working channel. | Bridge source exists, but live transport, inbound/refinement delivery and exact sponsor-rule compliance are not verified. Do not claim a working Photon integration or eligibility. |
| Peri Forward Deployed | An event-time business/club consultation with a named person, role and evidence. | No human consultation is established. Do not claim eligibility or invent feedback. |
| Gemini API / Cursor + Grok | Substantive qualifying product/API or coding/automation evidence under each track's rules. | Gemini/Claude drafting and Grok review are development assistance. They do not establish Gemini API use in the product or satisfy a separate award's requirements. Grok worker dispatch and inspected regressions are engineering evidence, not automatic prize eligibility. |

No substantive qualifying implementation is established for hardware/Physical AI, Nessie, Arlequin, Solana, Tiger Data, Vultr, MongoDB Atlas or GoDaddy. ChatOverflow connection/contribution and any published DEV entry need their own evidence. Best Rookie depends on actual participant history; automatic overall consideration does not guarantee prize stacking. Do not add decorative integrations to claim optional prizes.

## What has been checked

- Shared server: `python -m uvicorn agent.app:app --host 127.0.0.1 --port 8771`; Director at `http://localhost:8771/director`, full viewer at `/app/`.
- Browser checks cover real plans, rejected-location replanning, independent A/B edits, actor movement, timed playback and proposal review before Apply. Text brainstorming was exercised; microphone capture is not verified.
- Actual project JSON and static embedded-image shoot-pack downloads were inspected. A silent **1280×720, 4.921 s WebM** downloaded and played with a real room frame and moving Mara. This is an uncalibrated 2D rehearsal, not photorealistic video generation.
- Viewfinder lens, aspect ratio, drag, frame grab and close/reopen were browser verified. Four horizon cube faces were checked. Headings are **scan-relative**, not world-aligned; the depth illustration assumes **6 m**. Missing floor/ceiling and geometric fit remain unknown.
- Project import has **29 pure tests** for validation, exact-frame restoration and retained review drafts. Browser import remains untested after extension file upload was blocked; a complete browser save/load round trip is not claimed.
- Grok audit reproduced and now regression-tests four repaired defects: rejected properties resurfacing in faulty backend responses, missing/invalid status fields exposing availability/parking claims, unsafe provenance IDs and negative-time actor extrapolation. The test DOM was adapted for current reel/import/viewfinder controls. Progress is a display-only indicator, not a seek control.
- Reel/project/viewfinder and audit suites passed during this work. The combined repository gate passed: 539 tests, one skipped, plus smoke and fixture E2E checks; exact-code-head CI passed.

## Private data and demo scope

The older local join has 11 columns and does not supply the richer availability adapter fields or local Vexcel cache. Exact supplied property/model identity is separately checked. Missing availability, parking and depth remain unknown; estimates do not establish filming permission, measured clearance or certified truck capacity.

Discord checked: the integration captain's 14 November 15:01 Eastern reply about PR #21 says the expanded private index/Vexcel caches and final demo are on that teammate's laptop. The reported inventory is 343 properties, 10,568 views, 327 available indexed properties, Vexcel caches for 344 properties and nine available demo properties. These are teammate-reported counts, not a local reproduction. A second copy is unnecessary for the planned demo; pull this lane on the demo laptop and verify its current data there. This local checkout retains the older 11-column join and no Vexcel cache.

The user authorized licensed imagery in the judged demo. Keep keys, private records/bundles and licensed-image exports out of public Git and public uploads. No transport delivery, owner consent or approval message is invented.

## Retrieval measurements: keep the generations separate

- Original **608-view** evaluation: 20 human-labeled scenes, 15 test / 5 tune; held-out pooled recall@10 **38.9% cosine / 30.5% diverse**. See `index/EVALUATION.md`.
- Expanded frozen **10,568-view v1**: merged lane-C report gives fixed-engine macro pooled recall@10 **27.06%**. This is a distinct dataset/method.
- Latest **expanded v2, PR #27**: reported precision@10 lower bound **73.33% (110/150)** and macro pooled recall@10 **30.48%**, 15 fixed/live requests. Eight unjudged returns count as misses. The same frozen scenes and single reviewer's judgments were reused after changes informed by v1; **this is not a new untouched holdout**. Root did not reproduce the run or its private evidence. See `docs/team/eval.md` for timing, city-filter and sampled-pool limits.
- No further labeling is needed for this completed work. These metrics do not establish exhaustive catalog relevance, general accuracy, statistical significance, Director/solver quality, final-card quality or filmmaker validation. Warm demo timings are separate from retrieval benchmarks.

## Remaining human/demo actions

1. Integration captain: inspect PR #22, run the gate and rehearse the shared app using the existing expanded cache on the judging laptop; keep a local fallback recording.
2. Demonstrate a live `plan_production_shoot` call if claiming that specific new agent path. Otherwise show only the actual trace available.
3. Verify browser import when upload is available; use text unless the microphone is rehearsed. Obtain the richer private bundle only if demonstrating those constraints.
4. Confirm sponsor opt-ins, participant eligibility, team/Discord names and public-code submission requirements. Prepare the in-person pitch and optional video within two minutes each.
5. Plan around the earlier packet deadline: **08:00 Eastern, Sunday 15 November**. Submit through the authorized human flow; no submission has been performed by this audit.

## Evidence sources

Supplied `work/F26 Onsite Hacker Packet.txt` (pp.3–5, 12–19) supplies the track names, sponsor rules and deadline used here. Earlier audit references: [event/rules](https://hackprinceton-fall-26.devpost.com/rules), [event/prizes](https://hackprinceton-fall-26.devpost.com/) and [schedule](https://hackprinceton-fall-26.devpost.com/details/dates); this update does not claim a fresh organizer ruling. Exact Photon rules remain unverified.

Implementation/evidence: `agent/app.py`, `agent/deep.py`, `agent/deep_tools.py`, `agent/tests/test_production_integration.py`, `index/production.py`, `index/production_join.py`, Director/reel/project assets and tests, `web/viewfinder.js`, `docs/team/eval.md`, `index/EVALUATION.md`, PRs #12/#21/#27 and the root integrator's retained browser observations. Reported teammate benchmarks are distinguished from root verification above.
