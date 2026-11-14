# Film-industry validation handoff (blanks stay blank until a human fills them)

**Status: the user HAS reported a conversation with Mahimn Dave, a filmmaker who makes short movies. A validated Typecast consultation has NOT happened:** hands-on Typecast feedback, his affiliation (company/club), attribution/quote consent and Peri-qualifying evidence are all pending. No quote, endorsement, Peri eligibility or "tested with filmmakers" claim exists. A reported conversation is not a Typecast consultation, and a consultation is not eligibility (organizers decide).

Peri requirements as recorded in the repo (`docs/HANDOFF.md` lines 70 and 337; `index/PRIZE-READINESS.md` line 16): a named business or club, the person's name and role, one piece of evidence, an event-time consultation; judged on real-world need, usability, execution. The evidence template is `docs/peri.md` (owned by Owner 4; do not edit it from here, copy the answers across by hand once real).

## Record (human fills; leave blank if not real)
- Business/club/production company: ______
- Person name: ______  Role: ______
- Date/time and where (event-time?): ______
- Quote (verbatim, written): ______
- Quote permission (public use? name? company?): ______
- Evidence (screenshot/photo/video) and consent to publish it: ______
- Hands-on or watched-only: ______  Minutes actually used: ______
- One thing changed because of them (see below, only if actually done): ______

## 5-minute real-user test (existing UI, Director at `/director`)
Use the demo laptop with the real cache. Let them drive; stay quiet; note hesitations.
1. (0:30) Paste or type one of THEIR real scene lines into `#script` (format `HEADING | description`) and press **Build plan** (`#build`). Do not use the demo script.
2. (1:00) They open Evidence for the assigned frame. Ask them to find what is unknown (availability, parking) in `#evidence`.
3. (1:30) They stage two actors on `#stage` (**Add** `#addActor`, drag, **Play** `#play`), then type an instruction in `#instr` and **Generate alternative** (`#gen`), review the diff, **Apply to B** (`#applyB`).
4. (1:00) **Reject location** (`#reject`) or change Trucks/Cars then **Build plan** again; note whether the change made sense to them.
5. (1:00) **Shoot pack** (`#expPack`) or **Record reel (WebM)** (`#expReel`): would they send this to a producer or location scout?
Use **Look around the scan** (`#lookAround`) only if it works for that frame.

## Three questions
1. Walk me through how you pick and compare locations for a scene today; what is the slowest or most expensive step?
2. Looking at this output, what would you trust, and what would you refuse to rely on without a site visit? (listen for the "unknown" labels)
3. If this existed on your next project, who on your team would open it first, and what would make you stop using it?

## Who benefits (hypothesis, not a finding)
Early-stage location scouts, line producers and indie/student directors deciding which candidate rooms are worth a scout trip. Typecast shows candidate rooms with unknowns labelled; it does not approve a location.

## Measurable hypothesis (to test, not a result)
H: with Typecast, a person can go from a scene description to a shortlist of candidate frames plus a shoot-pack for a 3-scene script in under N minutes, versus their own current method for the same scene. Measure: stopwatch for both (record N and their method), count of candidates they could name, and whether they would discard any candidate because of a shown "unknown". No savings figure or ROI is claimed until measured with a real person.

## Observed failure and actual change (blanks until real)
- One failure observed during the test (what they stumbled on, verbatim if possible): ______
- One change we actually made in response (commit/PR link, before/after): ______
Do not write this section from imagination; the root coordinator forwards real feedback before any new idea is implemented.

## Hands-on confidence (state honestly in any write-up)
Tested hands-on with real controls by the contact? ☐ yes ☐ no (watched only) ☐ not yet. Browser checks so far are mock-fixture runs by engineers (`HANDOFF.md` section 4), not user validation. Live-cache behavior is verified only on the integration captain's laptop.


## Reported conversation context (user-paraphrased, UNVERIFIED; added 2026-11-14)
Correction (2026-11-14, supplied by the user): the filmmaker is Mahimn Dave and the film is *Lagaan*; his role per the user is that he makes short movies. This does NOT imply he worked on Lagaan. The Academy's primary record (https://www.oscars.org/oscars/ceremonies/2002) confirms Lagaan as a 2002 Foreign Language Film nominee; it is not described here as Emmy-winning. The conversation paraphrase (a search of about seven months, then the set was built) remains an unverified anecdote: not a direct quote, not a Typecast usability test, not an endorsement, not Peri eligibility, and no evidence Typecast would have saved time or solved that production's problem. Still pending from the human: company/club, permission to attribute or quote, evidence photo, and specific Typecast feedback. No attributed quote belongs in the public pitch. `docs/peri.md` stays Owner 4's and was not edited.

Design hypothesis to test (not a result): help producers decide earlier whether to adapt an existing room or build a set, using real indexed frames plus clearly labelled imagined dressing (and the offline authored sample is pre-written blocking, not AI). No savings, ROI or cost figure exists.

## Research lead supplied by the user (pending direct audio review)
The user identifies the documentary *Chale Chalo: The Making of Lagaan* — https://www.youtube.com/watch?v=HUJMRD_-c_c&t=718s — and the segment **11:58–14:50** as a producer discussion relevant to the location-versus-build-the-set question. The coordinator located the exact upload; the Gemini YouTube tool reported that no captions or transcript are available. **Nobody has verified the dialogue, the speaker, or any seven-month duration from this video.** It is a lead, not evidence: a human must listen to the segment directly before anything is written about what is said. No transcription is supplied here and no secondary source is substituted. Do not quote it, attribute statements to anyone, or tie it to Mahimn Dave's conversation until reviewed.
