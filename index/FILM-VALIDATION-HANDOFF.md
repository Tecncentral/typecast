# Film-industry validation handoff (blanks stay blank until a human fills them)

**Status: a contact has been FOUND. No consultation has happened. No feedback, quote, endorsement, Peri eligibility or "tested with filmmakers" claim exists.** Finding a contact is not a completed consultation; a consultation is not eligibility (organizers decide).

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
