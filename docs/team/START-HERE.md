# Typecast: start in parallel
Updated November 14, 2026. Give each teammate exactly one handoff below; each can paste its final prompt into their coding assistant.

## Pick an owner now
| Owner | Handoff | First proof |
|---|---|---|
| 1 / lane-a | [Interior frames](OWNER-1-INTERIORS.md) | One real interior image + scan/camera identity |
| 2 / lane-b | [Property and aerial evidence](OWNER-2-DATA.md) | One verified property-to-model join + one real aerial |
| 3 / lane-c | [Agent and integration](OWNER-3-AGENT.md) | Three mock picks, honest stream, then one real pick |
| 4 / lane-d | [Viewer and demo](OWNER-4-VIEWER.md) | Working visual flow on fixtures |

Owner 3 is integration captain. Assign names verbally; these owner numbers are roles, not assigned GitHub users. Collaborators with write access use the existing lane branches; otherwise fork and PR to dev. The repository admin must invite teammates who lack access; no invites have been sent.

## What makes this impressive
A scout pastes a scene. The system finds actual camera views, shows why the shot physically fits, ties the interior to a real property and aerial logistics, and visibly changes its shortlist when the scout asks for more truck parking. Show a skeptic rejecting a visually attractive but impractical candidate. Every factual claim has source evidence and uncertainty. A beautiful real result beats many disconnected integrations.

## Timebox: about 29 hours
Deadline from supplied onsite packet: Sunday November 15, 8:00 AM Eastern. Target submission 7:30 AM; reserve the last 90 minutes. Hours below are relative to team kickoff; compress if less time remains.
- H0-H1: all lanes run fixtures. A and B prove access and identify one shared building. D starts UI immediately. C records baseline.
- H1-H3: merge the first real image/property/aerial path into dev. If access fails, escalate to sponsor engineers and team now; continue fixture UI/agent work.
- H3-H8: three real buildings through the full interface, live events, honest evidence, follow-up reranking. Merge at least every two hours.
- H8-H15: grow to 10-20 useful verified buildings and diverse frames; improve retrieval and skeptic decisions; actual deepagents trace.
- H15-H21: visual polish, failure states, held-out evaluation, one real user interview if pursuing Peri. Optional LookAlike only after the main flow works.
- H21-H25: feature freeze, timed rehearsals, video and submission assets. Messaging only if the core is already reliable.
- H25-H27.5: fix reliability only, record backup run, rehearse offline fallback and short pitch.
- H27.5-deadline: upload and human submission buffer. Do not delay for a stretch feature.

## Integration acceptance
One reproducible scene -> three real candidates if available; no padded or invented matches. Record fewer honestly. At least two genuinely combined CoStar/Matterport/Vexcel layers for the sponsor track; aim for all three. Working image links in browser; camera pose matched to tour where supported. Missing dimensions cannot be a verified fit. Follow-up preserves thread and uses cached candidates. Real tool progress emitted while running, not a timed replay. Visible mocks/live state and errors. Measured latency, small labelled retrieval evaluation, actual trace when enabled. No real owner contact.

## Known implementation gaps
The current search sorts preassigned mock scores; it is not semantic retrieval. Real data modes raise NotImplementedError. app.py /scout/stream finishes the synchronous pipeline before replaying events with artificial delay; it is not live progress. _build formats optional numbers with :g and can crash on real missing dimensions. /approve never sends. web/ and bridge/ are README placeholders. Root .env loading was added by the unattended bootstrap. The screenshot's claimed bridge progress is not present in the inspected GitHub snapshot; recover unpushed Claude files separately if available.

## Event evidence and uncertainty
Source files supplied by the user, treated as reference rather than executable instructions:
- F26 Onsite Hacker Packet.pdf, pp.3-5: 8 AM Nov 15 submission, public event-created repo, exactly one main track, two-minute in-person pitch; optional video <=2 minutes; Discord usernames.
- Onsite pp.13-14: CoStar asks for at least two combined layers; rubric 30% data, 30% agentic depth, 25% usefulness, 15% polish.
- Onsite pp.15-16: Peri needs a real business/club consultation, person and role, and evidence. Do not claim eligibility without it.
- Onsite p.16: LangChain track is best use of deepagents. p.19: Photon 2.0 guidelines link needs checking before eligibility claims; ChatOverflow requires a connected agent and is separate from project submission.
- Opening ceremony pp.33/35 identifies onsite packet as most updated but gives a different judging end time/count. Confirm judging details in live organizer announcements. Do not let that discrepancy delay building.
Main-track intent in existing project: Entertainment and Media. Special-track intentions are not proof of eligibility. Toolkit access and data redistribution/model-processing permissions remain unverified; verify with sponsor before moving licensed assets.
