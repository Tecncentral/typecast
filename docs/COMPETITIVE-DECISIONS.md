# Competitive decisions for the Entertainment demo

Concise decision record for the integration candidate `ai/director-unified`. It is not a prediction of any result and no outcome is guaranteed. The user has reported a conversation with a filmmaker (Mahimn Dave, short movies), but a validated Typecast consultation has not happened: hands-on feedback, affiliation, attribution consent and Peri-qualifying evidence are pending, so **no consultation result or endorsement is claimed anywhere in this repo.** A user-supplied documentary segment (see `index/FILM-VALIDATION-HANDOFF.md`) is an unverified research lead.

## Inputs and how far each can be trusted
| Input | What it is | Limit |
| --- | --- | --- |
| Gemini A/B draft, `manager-drafts/gemini-compare-ab.patch` (9,294 bytes) | Proposed split-canvas Compare A/B, generated from supplied unified Director source | Never executed or tested by its author; treated as untrusted. |
| Grok competitive review PR #39, `origin/cursor/competitive-review-1fff` at `b8cd2a1` (copy: `manager-drafts/grok-competitive-review.md`) | Public-repo comparison of Typecast with BalanceForge, OmniRiff, Memoria, Helm, Stitch; offline test slices | Peer README claims and offline tests, not observed live demos. No confirmed Devpost submission for any project. Its Typecast baseline `dbceec2` is stale versus this candidate and must not be repeated as current proof. |
| Gemini source-snapshot review | Recommends an immediate A/B comparison and an offline preset | Snapshot opinion only. |

Primary links (peer repos as cited by the Grok review; not re-opened by this session): https://github.com/yjk82693/balance-forge, https://github.com/angelofernand0/omniriff, https://github.com/AlexWin0806/memoria, https://github.com/Mitanshcodes/Helm, https://github.com/jpark2007/Stitch; HackPrinceton rules https://hackprinceton-fall-26.devpost.com/rules. Observed live behavior of those projects is unknown to us.

## Decisions
1. **Compare A/B: built, reduced to a read-only preview.** Gemini's idea kept; its code was not applied. Rejected from the draft: scaling the whole stage horizontally by 0.5 (distorts frames and figures), keeping the single-take inspector editable while comparing (a form edit would silently change the active take), a playback clock that follows only the active take (would imply equal timing), and a PNG export that would capture the split layout. Built instead: two natively sized panes of the same indexed frame, per-pane label and duration, one real-time clock whose scene length is the longer take (the shorter holds its last pose and says so), locked canvas/keys/take fields, PNG and WebM = active take, Project JSON and Shoot pack = both takes.
2. **Authored sample alternative: built, explicit opt-in.** Grok and Gemini both pointed to an offline fallback. The brainstorm API still returns 503 without a model and is never substituted. The button loads a fixed, pre-written mirror-and-cross pattern derived from take A (or one generic performer), labelled "pre-authored, not AI-generated", through the existing review step; only Apply writes B. It is an offline convenience, not prize evidence.
3. **Not built:** the labeled synthetic cube/viewfinder sample and the room/constraint visualisation changes from the Grok report. Out of scope for this bounded milestone; a synthetic live-looking source would risk weakening provenance. No source capacity or availability is fabricated.

## Reported film-industry conversation (unverified)
Correction (2026-11-14, supplied by the user): the filmmaker is Mahimn Dave and the film is *Lagaan*; his role per the user is that he makes short movies. This does NOT imply he worked on Lagaan. The Academy's primary record (https://www.oscars.org/oscars/ceremonies/2002) confirms Lagaan as a 2002 Foreign Language Film nominee; it is not described here as Emmy-winning. The conversation paraphrase (a search of about seven months, then the set was built) remains an unverified anecdote: not a direct quote, not a Typecast usability test, not an endorsement, not Peri eligibility, and no evidence Typecast would have saved time or solved that production's problem. Still pending from the human: company/club, permission to attribute or quote, evidence photo, and specific Typecast feedback. No attributed quote belongs in the public pitch. The design hypothesis is only that Typecast might help producers judge adapt-an-existing-room versus build-a-set earlier with real frames and clearly imagined dressing. No ROI or cost figure is claimed.

## Authored sample gate
Grok's conditional approval required the sample's origin to follow the take. It now does (per-take validated `origin`, drawn into PNG, WebM, shoot pack and Compare, saved in Project JSON); see `index/UNIFIED-INTEGRATION-HANDOFF.md`.

## Honest positioning
Strengths we can show with evidence in this repo: real-source provenance and Unknown handling, exact-frame staging, rejection guarantees, labelled mock vs live, AI-vs-real labelling. Whether any of that matters to judges or a film professional is unknown until a live demo and the pending feedback.
