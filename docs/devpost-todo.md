# Devpost entry: to-do before final edit

This file tracks the preliminary Devpost answers submitted around 6:30 AM ET on Nov 15. It lists what each answer needs once the project is polished and features are locked.

- **Main track:** Entertainment and Media, chosen Nov 15 at about 3:15 AM ET. Select it on the Devpost form itself.
- **Edit window:** the team says edits are allowed until 8:30 AM ET. Confirm this on the Devpost page, because the onsite packet says 8:00 AM.
- **Rule for every answer:** claim only what is merged and verified. Labels like "AI-imagined", "estimate" and "unknown" stay in.

## Whole-entry checklist (do at the end)

- [ ] Fill in the team's Discord names. They are still `[MEMBER 1–4]` in `docs/devpost.md`.
- [ ] Make the GitHub repo public, as the README requires for submission. Then replace the placeholder links with working ones.
- [ ] Upload the demo video (2 minutes or less). Show "recorded live run" on screen; fixture footage must say MOCK.
- [ ] Add a screenshot of the merged viewer that a human has approved, with the AI and source labels legible. No licensed imagery unless permission is confirmed.
- [ ] Peri: add the consultation evidence (name, role, quote, date, permission) and the feature we changed because of it. Claim nothing without it.
  - Nov 15, 7:45 AM ET: we have it. **Mahimn Dave**, filmmaker behind **textbooknotebook** (student film production, @textbooknotebook on Instagram); evidence is a voice recording plus quotes, all in `docs/peri.md`. Still to confirm: his exact title, permission to name him, and when he recorded (decides whether Edit (AI) was "built for him" or "confirmed by him").
- [ ] Do not carry over the Business/Enterprise and Amazon wording from the `ai/claude-business-integration` branch.
- [ ] Bring `docs/devpost.md` in the repo in line with the final submitted answers.

---

## Q: Elevator pitch (short tagline)

**Submitted (preliminary).** This is the recommended option; edit it here if a different one went in.

> An AI location scout: type a scene, get real rooms and outdoor places from 3D scans and aerials, check crew parking, then reimagine the space for your shot.

**Alternatives considered**
- Cast real places for your script, then reimagine them. Typecast finds actual interiors and outdoor locations, checks the logistics, and lets you redress the room with AI.
- From script to set: AI agents scout real buildings and outdoor places, a skeptic flags what won't work, and an image model shows what the space could become.

**To do at the end**
- [ ] If `owner4-costs-commutes` merges, consider ending with "…and compare it against building a set or CGI." Never use "cheaper" or "save", because the rates are public estimates, not quotes.
- [ ] If any feature named in the tagline (outdoor search, reimagine) is cut or broken in the final demo, remove it.

---

## Q: About the project (Markdown + LaTeX)

**Submitted (preliminary):** the full text is in the appendix at the end of this file. It was written from the `dev` commits up to `961a8f6` (Nov 15, 2:51 AM ET). Its numbers come from `docs/team/eval.md` and the lane C reports.

**To do at the end**
- [ ] **Cost and drive time.** If `owner4-costs-commutes` merges and is verified, move the "Cost and travel" bullet from *What's next* into *What it does*. Keep "public estimates, not quotes" and "drive time without live traffic".
- [ ] **Peri.** Add one line under *Inspiration* or *What we learned* with the filmmaker's real feedback. Add the feature we changed because of it under *What it does*, with the commit.
- [ ] **Re-check numbers** if anything was re-measured after 3 AM:
  - 10,568 views, 343 properties, 329 models (LA and Houston index)
  - 73.33% precision@10 lower bound for v2, 66% for v1; 15 scenes, one reviewer
  - Deep engine about 84 s at the start, about 41 s warm median; fixed engine about 9 s
  - Fastest image edit about 4 s (Gemini Lite, on an oblique)
  - Shot fit: 24 mm lens framing 6 m needs 8.78 m; sensor 24.9 mm (`index/geometry.py`)
- [ ] **Re-check features** against the final demo build: Edit (AI) chat, outdoor oblique search, 3D city view, building card, Ask about a place (Vexcel MCP), Director's Room, viewfinder lens change, 5-truck refinement, unsent drafts. Remove anything cut or not working at demo time.
- [ ] **iMessage (Photon).** If the `photon-imessage` branch is verified on a real phone, add to *What it does*: "Text a scene on iMessage, get picks plus a viewer link, re-rank by text, and get a reminder if you haven't drafted an inquiry." Add to *What's next*: "Built so any chat app needs only a small adapter: Discord, Telegram, Slack, WhatsApp next." Also add Photon to Built with. If it isn't verified, leave Photon out entirely.
- [ ] **Phone sign-in (Photon).** Only if verified: "Sign in with your phone; the code arrives over iMessage, and that number gets your reminders." Don't call it a full account system.
- [ ] **Radius / drive time.** Only if `owner4-costs-commutes` merges (optionally with "use my location"): "Set a production base and a max drive time; picks outside it are flagged. Road-network estimate, no live traffic."
- [ ] **Alerts (Photon).** Mention only the stages that were verified. Website reminders: "opt in with a phone number and get a text if you haven't reached out." Price alerts: say the alert logic watches your max-rent limit, that rent data is a CoStar snapshot, and that the demo uses a **simulated** price update. Put a live price feed under *What's next*. Never imply the prices are live.
- [ ] **Walkable interiors from sparse scans** stays under *What's next* unless the World Labs owner merges a verified result.
- [ ] Replace any placeholder or nonfunctional links with working repo links once the repo is public.

---

## Q: Built with (up to 25 tags)

**Submitted (preliminary)**

Python, JavaScript, HTML/CSS, FastAPI, LangChain, LangGraph, deepagents, LangSmith, OpenAI, Gemini, PyTorch, CLIP, DuckDB, Leaflet, three.js, Matterport, CoStar, Vexcel, World Labs, OpenStreetMap, MCP

**To do at the end**
- [ ] Add OSRM if the cost/commute branch merges. Drop the tag for any feature that gets cut.

---

## Appendix: submitted "About the project" text

```markdown
## Inspiration

A script says *"INT. 1980s POLICE STATION, NIGHT."* Somebody now has to find that room. It has to look right on camera, be deep enough for the lens, have space nearby for three trucks and thirty crew cars, and belong to a building that could actually be rented. Today that means hours of searching listings, scrolling photos, and driving to places that turn out to be wrong.

Student crews and small productions feel this most. They can't afford a location team, and when a found location doesn't work, they can't afford to build a set or pay for CGI either. We wanted to give them the first pass of a location scout in minutes, plus a way to see what a real room *could become* before anyone paints a wall. We also wanted it to be honest about what it knows and what still needs a site visit (a recce).

## What it does

**Type a scene. Typecast finds real places that can play it, and then helps you imagine what they could become.**

- **Real interiors.** AI agents search **10,568 camera views from Matterport 3D scans** of **343 CoStar properties** in Los Angeles and Houston. They return three ranked buildings with real frames from inside each one.
- **Physical checks.** For each frame, Typecast checks whether the shot physically fits the room, given the lens and the room's depth and ceiling. It estimates crew parking from **Vexcel aerial imagery** and flags nearby freeways, rail lines and airports.
- **A skeptic.** A separate agent argues against the shortlist with source-backed objections, such as *"Parking short: 1 truck against 3 needed."* An attractive room that the crew can't work in gets called out.
- **Follow-ups.** Say *"need parking for 5 trucks"* and the same conversation re-ranks the candidates it already found, without searching again.
- **Look around.** A 360° viewfinder lets you compose the shot inside the scan and switch lenses from 24 to 50 mm.
- **Reimagine.** An **Edit (AI)** chat restyles the real room view: *"dress it as a 1970s precinct"*, then *"night, desk lamps"*. The walls, doors and roof trusses stay where they are. A wipe compares the real scan with the imagined set, and every AI image is labelled *"AI-imagined set dressing, not the real room."*
- **Exteriors and outdoor places.** Vexcel oblique search finds rooftops, alleys and hillsides, shows them from real 45° angles and in a 3D city view, and reports terrain slope and relief. A building card shows roof type, height, skylights and defects. You can ask questions about a place and get answers drawn from live Vexcel data, then reimagine the exterior (*"rooftop bar at night"*).
- **Director's Room.** Give it a whole script and it groups scenes by building to reduce *company moves*, the times the whole crew packs up and relocates.
- **Inquiry drafts.** Approving a pick saves a local inquiry draft for the owner. Nothing is ever sent automatically.

## How we built it

| Layer | What it decides |
|---|---|
| **CoStar** | Which property it is, its type and era, and whether it has marketed lease availability |
| **Matterport** | What the camera can see: real scan views for retrieval, ranking, the viewfinder and reimagining |
| **Vexcel** | Where the crew can stage: aerials, parking masks, oblique exteriors, 3D cities, terrain, building structure |
| **OpenStreetMap** | Mapped parking, walking routes, and distance to noise sources (an estimate, not a sound measurement) |

**Agents.** LangChain `deepagents` runs a director that writes a plan. It hands work to market, interior and logistics scouts, with the interior and logistics scouts running at the same time, and then to a read-only skeptic. Draft approval goes through a real human-approval checkpoint. A simpler fixed-order engine uses the same tools and serves as a fallback. Progress updates in the UI are streamed from the real tool calls, not replayed, and runs are traced in LangSmith.

**Retrieval.** CLIP embeddings over cut perspective views from each scan's panoramas, then a vision model that re-ranks the top candidates against the exact scene text.

**Shot fit.** For a lens with focal length $f$, a sensor of width $s = 24.9\,\text{mm}$ and a frame of width $W$, the camera has to stand

$$d_{\text{camera}} = \frac{W \cdot f}{s}$$

from the actors. Adding a fixed margin for space behind the actors and for the operator gives the room depth the shot needs. A 24 mm lens framing 6 m needs about **8.78 m**. If the room's depth or ceiling is unknown, the result is *unknown*, never *fits*.

**Reimagining.** Edits go through a switchable image model (Gemini or OpenAI) that keeps the parts of the photo it wasn't asked to change. On a real oblique, the fastest model finished a full edit in about **4 seconds**. Separately, World Labs Atlas uses depth derived from the scan to keep AI set dressing consistent with the room's geometry.

**Stack.** Python and FastAPI for the backend. Plain JavaScript modules with Leaflet and three.js for the viewer, with no build step so it runs offline at the venue. Licensed data stays in a private cache.

## Challenges we ran into

- **Keeping images honest.** It's easy to make a beautiful picture that implies things nobody checked. We had to keep "real scan", "estimated from aerial" and "AI-imagined" visibly separate throughout, including during the wipe animation.
- **Unknown is not zero.** Missing parking, depth or ceiling data had to stay *unknown* end to end. That meant no zero values, no "fits" based on guesses, and no straight line between two points passed off as a walking route.
- **Linking three datasets.** Joining CoStar properties, Matterport scans and Vexcel imagery to the same building required exact source mappings rather than address guesses. Parking used real segmentation-mask pixels, holes included, instead of rough bounding boxes.
- **Speed.** The multi-agent engine started at about 84 s per run. Running the scouts in parallel, sending the model short summaries instead of full records, and lowering the scouts' reasoning effort brought the warm median down to about **41 s** (about **9 s** for the fixed engine).
- **Measuring retrieval fairly.** We froze the index and candidate pools before human review and tuned only on separate tuning scenes, so we couldn't grade our own homework.

## Accomplishments that we're proud of

- A creative loop on top of real evidence: find a real room, compose the shot, then reimagine it as the set you need, with the real architecture kept and the AI clearly labelled.
- A working end-to-end flow on real data: scene → agent plan → real interior frames → parking → skeptic → follow-up → reimagine.
- **73.33% precision@10 (lower bound)** on 15 held-out scenes judged by a person, up from 66% before our changes. That's one reviewer, and the second number is a repeat on the same scenes, so we report it as a measurement rather than a general accuracy claim.
- All five rehearsed demo scenes passed on both engines, including the follow-up re-rank and the unsent drafts.
- Outdoor scouting built on Vexcel's own MCP server, with read-only tools and a cap on how much each question can query.

## What we learned

A useful scout gives you reasons to visit *and* reasons to hold off. The skeptic turned out to be one of the most valuable parts because it shows where the evidence runs out.

We also learned to keep three things separate: retrieval quality, live latency, and how good the demo looks. The visual reveal makes the sources easy to understand, but it doesn't change what the benchmark proves.

## What's next for TypeCast

- **Cost and travel:** compare the found location against building a set or using CGI, with editable assumptions and drive times from a production base. This is built and in review. The rates are public estimates, not quotes.
- More cities, more scanned buildings, and wider human evaluation with more than one reviewer.
- Interiors you can walk through, generated from sparse scans.
- Validation with working location managers before we claim time saved.
- Free access for student crews, and a way for owners of unused buildings to list them for filming. These are goals, not results yet.
```
