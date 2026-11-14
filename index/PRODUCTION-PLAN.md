# Production workflow and prize fit

Target main track: Entertainment & Media. Product direction: turn scenes into a visual, practical shoot plan. Preserve the existing working scouting flow.

**Later council decision:** [Director's Room](DIRECTORS-ROOM.md) supersedes the ranking below for this build. Prioritize the uncalibrated 2D character rehearsal, A/B scene alternatives, reject/replan and shoot-pack export; then reviewable voice brainstorming. Music/remix work is deferred. The list below records possible future directions, not a claim that they are built.

## Features ranked by genuine value

1. Multi-scene location plan: compare the best independent matches with fewer-location alternatives; expose visual compromises and re-plan after rejecting a location. Supports Entertainment, CoStar and Amazon; a real Deep Agents tool integration supports LangChain.
2. Scene rehearsal reel: sequence actual selected views, lens setups, shot durations and creative notes. Audition user-provided or licensed temporary music against the same reel. Save the chosen cue with the storyboard. This is the strongest natural music integration; a general stem-separation/remix product is a separate scope.
3. Director/producer decision view: show the actual visual preference, logistics objection, source evidence and alternative. Reuse the real scout/skeptic pipeline; do not simulate a fake agent debate.
4. Conversational revisions: a text/voice request changes the same shoot plan and yields a new lookbook/draft. Photon is a genuine fit for coordination, but requires a verified real Photon integration and its specific guidelines before claiming eligibility.
5. Production budget scenarios: compare user-entered location quotes and move/setup costs; never invent rental prices or savings. A Nessie-backed production wallet could be relevant to Capital One only if actual sandbox banking endpoints meaningfully drive budget/payment-proposal behavior. Lower priority than finishing the core.
6. Crew accessibility constraints and sound concerns: preserve unknown evidence; aerial proximity is not a measured noise level, and floor boundaries do not certify an accessible route. Useful production constraints, not a pivot to a medical/accessibility product.
7. Physical smart slate: only worthwhile if existing hardware can actually log a take/cue and affect the workflow. A normal laptop or 3D viewer does not satisfy the sponsor's physical-hardware-build requirement.

## Rubric mapping and boundaries

- CoStar: at least two layers AND benefit from combining them. Aim for all three driving the same production decision. Rubric: data30%, agentic depth30%, usefulness25%, demo/polish15%.
- Amazon: creativity, usefulness, implementation and UX each25%; creative production and coordination are legitimate workflow fits. No AWS-specific integration is required by the supplied rubric.
- LangChain: real Deep Agents behavior, complex use case, effective subagents/filesystem and compelling demo. Calling the standalone deterministic solver is not by itself a Deep Agents integration.
- Photon: natural conversational planning/coordination; packet lists main, runner-up and voice prizes, but linked guidelines and actual transport must be verified. Draft-only behavior is not actual message delivery.
- Peri: real business OR student-club consultation during the event, including organization, person/role and supporting evidence. User has no filmmaker contact; do not fabricate consultation or claim eligibility. A genuinely relevant club/business could qualify if a real consultation occurs.
- Capital One: Nessie endpoints must improve a genuine financial workflow. A budget table alone is insufficient. Optional production-wallet work must not degrade the main demo.
- Physical AI: requires a physical hardware build, confirmed by sponsor discussion. Optional smart-slate hardware is lower priority.
- Arlequin forensics/social analysis: production-location search does not meet forensic-pattern or content-plus-network analysis requirements. Do not claim these based on scene evidence or an unrelated dashboard.
- ChatOverflow: separate coding-agent leaderboard/raffle opportunity, not a product feature or project-submission prize. Actual authorized connection and useful non-sensitive contributions are necessary; not connected by this milestone.

Sources: supplied F26 Onsite Hacker Packet.pdf pp13–19; event Discord CoStar, Amazon, LangChain, Peri, Photon, Capital One and founder-office-hours channels reviewed November14. Sponsor conversations/questions do not override official eligibility requirements. Do not claim an unverified track or guarantee a win.

## Implemented draft milestone

`production_solver.solve_plans` enumerates subsets of up to24 candidate properties, eight scenes and four proposed locations. It returns the best candidate assignment for each location budget, missing-scene IDs, raw cosine means and an illustrative company-move count. Company moves assumes one visit per selected property; it is not drive-time or scheduling optimization. Exactness is confined to the supplied candidate pool, not every possible filming location.

Gemini drafted the pure solver and tests. Local review corrected at-most-budget selection, unnecessary unused locations, lossy score rounding and an incorrect expected optimum in its test fixture. Five targeted tests pass. **Not yet wired to the API, agent or viewer.** Candidate association is not verified shootability, availability, permission or a human creative judgment. No new provider calls, dependencies or shared-contract changes were added.

Next implementation: safe retrieval-pool creation and rejection/re-planning API, then the visual storyboard/tradeoff UI and rehearsal-reel music audition. Keep legacy scouting available throughout.
