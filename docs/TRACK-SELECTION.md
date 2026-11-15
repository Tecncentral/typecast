# Track selection (planning notes, not an eligibility ruling)

**Current team choice, November 15: Business/Enterprise is the single main track**, replacing Entertainment/Media after judge feedback. See [business case, sourced cost scenarios and quote provenance](BUSINESS-CASE.md). Human Devpost selection is still required. Earlier creative-demo wording below is historical where it conflicts with this decision. CoStar, LangChain and Amazon remain intended sponsor entries. The user has supplied a filmmaker quote and reported permission to quote; affiliation and original evidence remain pending for Peri.

Organizers decide eligibility. Nothing here promises a prize, submits anything, or claims past benefit. Adapted from a read-only audit of the onsite packet against the repo (`../manager-drafts/track-selection-audit.md`, not committed); the audit read the packet and the repo but ran no app, server or test, so repo-evidence statements below are quoted from handoffs and recorded checks, and all gate numbers are mock/fixture results.

Sources, kept separate:
- **Onsite packet** `F26 Onsite Hacker Packet.pdf` (22 PDF pages; page numbers below are PDF index + 1 and were verified by the audit).
- **Public pages** retrieved by the project coordinator by web search on 2026-11-14 (the audit did not browse): https://hackprinceton-fall-26.devpost.com/ and https://hackprinceton-fall-26.devpost.com/rules. The homepage lists MLH and sponsor awards that the packet text does not mention; absence from the packet does not mean an award was cancelled, so the human must read the live prize text before each opt-in.

## Rules that matter
- One of six main tracks plus any number of sponsor tracks (packet p.4, p.12; rules page). Special tracks are judged by company representatives in round 1, and each added track means another demo (p.5-6, p.19).
- Main judging is holistic over Creativity, Utility, Charity and Avidity with no equal 25% weights (p.4-5; rules page). No numeric weights are claimed anywhere in this repo.
- **Deadline: 8 AM ET Sunday 15 Nov 2026, hard stop** (p.3-4; rules body). A banner elsewhere shows 8:30; use 8:00. Reserve the final 90 minutes from **06:30 ET** for submission and rehearsal.
- In-person demo required, presentation at most 2 minutes, optional video at most 2 minutes (p.4). Rules also expect credit for frameworks used and honesty about AI assistance.

## Recommended
| Track | Why, with exact requirement | Repo evidence | Human step still needed |
| --- | --- | --- | --- |
| **Business/Enterprise** (the one main track) | Production planning workflow with an identifiable business buyer and transparent cost assumptions. | Real-location retrieval, commute-constrained production plans, reviewed scene concepts, cost comparison and shoot-pack handoff; see `docs/BUSINESS-CASE.md`. | Select Business/Enterprise as the single main track on Devpost; replace any earlier Entertainment selection. |
| **CoStar: Inside and Out** | At least two of CoStar/Matterport/Vexcel combined meaningfully; agentic; spatial and visual understanding (p.13-14). | All three wired (`data/build_join.py`, `index/production_join.py`, `data/vexcel_tools.py`, `agent/deep.py`); Vexcel logistics are precomputed estimates and most availability is unknown. | Live proof is on the integration captain's laptop with the private cache; rehearse there. Confirm current sponsor criteria. |
| **LangChain: best use of deepagents** | "Build a deepagent" (p.16). | `agent/deep.py` constructs a real deep agent with four subagents and a human-approval step (`create_deep_agent`). The `plan_production_shoot` tool had only a fake-model dispatch check; no live trace of it exists. | Show a real completed run or trace, narrate only visible calls, set `TYPECAST_ENGINE=deep` for that demo. Never call the solver or UI notices an agent trace. |
| **Amazon: Best Practical AI Innovation** | The packet allows any combination of open-source tools, APIs, models and frameworks; **AWS is not required** (p.15). Needs a working prototype, clear user and use case, basic documentation and a pitch. Do not claim AWS use. | The scout/rehearsal workflow, `README.md`, `docs/devpost.md`, `docs/pitch.md`. | Opt in on Devpost; confirm current criteria. |

Best Overall is automatic (p.12); one-main-track rule still applies and Best Overall winners cannot also win a main track (p.10).

## Conditional, optional or skipped
- **Peri Forward Deployed: CONDITIONAL.** Requires a real business or club consulted during the event, the person's name **and** role, and one piece of evidence (p.15). The user reports a conversation with Mahimn Dave (makes short movies). Still pending from the human: his company or club affiliation, event-time timing, attribution and quote permission, an evidence photo or screenshot, and specific Typecast feedback. Until then no consultation, quote or endorsement is claimed, and `docs/peri.md` stays an unfilled template owned by Owner 4. A hands-on test would help but is not an explicit packet requirement.
- **SpaceX AI raffle (Cursor core + GrokBot):** listed on the public homepage, not in the packet. Our workflow is Claude as primary agent with Gemini and Grok/Cursor helpers, so Cursor as the core agent is unproven; eligibility not established.
- **Photon 2.0:** skip unless a live channel works and the external rules are read; the bridge source (`bridge/photon.mjs`) has not been run.
- **ChatOverflow:** separate optional participation (p.19), needs a connected coding agent and no sensitive data; not a product feature.
- **Gemini API prize:** needs product use of the Gemini API; using Gemini as a coding or review assistant does not qualify.
- **Skip (no real integration):** Solana, TigerData, MongoDB Atlas, Vultr, GoDaddy, Arlequin, Nessie, Physical AI, hardware. **DEV writing** is a separate published post. **Best Rookie** depends on members' history, unknown.

## Community planning and the Charity criterion
Community planning (`docs/COMMUNITY-PLANNING.md`) is now implemented as a prototype inside the same Director: pre-incident candidate-site review for volunteer and supply coordination, with human-reported coordinator checks that start unknown, a printable Site Brief and no safe/approved badge. It has been exercised only on mock fixtures (verify.py, Node suites and clean Chromium journeys of both modes) and has had no review by any organization; no benefit, adoption or measured outcome exists, and it is not a Healthcare entry (one main track only). It can support the Charity criterion honestly as a prototype direction, nothing more.

## Pitch
One clear 120-second Entertainment demo (`index/DEMO-SCRIPT.md`): paste a screenplay, see candidate real rooms with unknowns labelled, stage take A and a reviewed take B (a real model proposal only if a provider was tested, otherwise the labelled authored sample), swap or reject a location, and show the exports. Offer the community mode only if asked, in about 20 seconds, never as part of the main tour, and do not cram every sponsor into the pitch: show the CoStar and LangChain evidence only if their reps ask.

## Remaining human opt-in steps
Read the live Devpost prize and rules text for each track; pick the one main track and tick CoStar, LangChain and Amazon if still listed; supply Discord names; decide on Peri only if the real affiliation, timing, permission and evidence exist; capture a real deep-agent trace if LangChain is shown; rehearse on the captain's laptop with the real cache; submit before 08:00 ET.
