# Typecast: location decisions before production commits

**Current product update:** after the buyer/engineering/evidence debate (`docs/BUSINESS-DECISIONS.md`), the calculator now separates projected labor capacity from avoidable cash. Unconfirmed commitments keep cash unknown; salaried/guaranteed staffing can have zero labor cash savings while tool costs remain payable. Optional cancellable-unit caps and vehicle/crew commitment gates are explicit. A current-plan producer decision brief preserves the selected frame, alternatives, assumptions and next checks; JSON imports restore inputs only and require rebuilding. Prospective baseline/outcome fields are producer-reported, never automatically causal evidence. The examples below remain conditional scenarios.

Main track selected by the team: **Business/Enterprise**, superseding Entertainment/Media on November 15, 2026. Human submission is still required; this file does not change Devpost automatically.

Buyer: a producer, production company or location department. User: a location manager or director preparing a physical scout. The workflow connects a script to real candidate frames, property and aerial logistics, a commute constraint, reviewed scene concepts, and a transparent cost comparison. The business outcome is a better-informed shortlist before paying for scouting days. Typecast does not book sites, obtain filming permission or replace a technical scout.

## What savings can we honestly show?

The **2026–2029 AICP / Teamsters Local 399 wage chart**, page 2, lists **$957.58 minimum per day** for covered location scout managers effective June 28, 2026. This is a commercial agreement reference, not an average film-studio cost or a universal indie rate. Source: https://www.ht399.org/app/uploads/2026/06/APPENDIX-A-Wage-Chart-Drivers-and-Locations-final-6.24.26.pdf (checked November 15, 2026).

For one scout at that reference rate:

| Billable scouting days avoided (assumed) | Gross scouting labor potentially avoided |
| --- | ---: |
| 1 | $957.58 |
| 2 | $1,915.16 |
| 3 | $2,872.74 |
| 5 | $4,787.90 |

**These are scenarios, not measured Typecast savings.** The 5-to-2-day example in the app assumes three entire billable days disappear; visiting three fewer properties does not imply saving three day rates. A weekly guarantee or unchanged staffing may mean no cash reduction. Travel and on-site work can already be included in a day rate; the daily mode does not add hourly labor. Actual guarantees, fringes, overtime, software/provider charges and other incremental costs must be considered separately. Enter the actual total Typecast/provider cost to deduct it.

Example pitch: “If our shortlist lets one commercial location scout eliminate three billable scouting days, that is about **$2,873 in gross scouting labor** at the published 2026 reference rate, before tool costs. The calculator exposes that assumption; our pilot still needs to measure days actually avoided.”

The hourly mode calculates `(visits before − visits after) × [people × hourly rate × (on-site hours + round-trip travel hours) + round-trip miles × vehicle cost/mile] − tool cost`. Its starter values are illustrative. Crew travel is a separate opt-in calculation using paid travel only, one starting pin, shoot days, and the slowest routed selected location. A shorter commute is not automatically paid time or cash savings; heterogeneous homes, schedules, guarantees and overtime are not modeled.

The scouting scenario above adds no set-construction savings. Since November 15 a separate, clearly labelled comparison (next section) prices a real location against a standing set and a built set from published rates. We still have no actual construction bid and no proof that Typecast avoided building a set. No automatic permit savings are added: FilmLA says its application covers up to five filming locations, so fewer locations need not remove a permit application fee. Source: https://filmla.com/client-jurisdiction-fee-increases-effective-july-1-2026/ .

## Real location vs. standing set vs. building a set

Answers the filmmaker's own framing ("we either compromise the scene or build a set we can't afford"). Shown on `/director` as the third summary tile and the panel of the same name; arithmetic in `index/location-vs-set.js`. All inputs are editable.

| Option | Default inputs | Source (checked November 15, 2026) | 1 shoot day |
| --- | --- | --- | ---: |
| Real found location | $222/hour x 10 hours | Giggster: average Los Angeles filming location, listed prices. https://giggster.com/find/los-angeles--ca/filming (opened) | $2,220 |
| Rented standing set | $2,000 per 12-hour shoot day; $1,000 per prep or strike day | Affordable Sound Stages, Los Angeles: living room, kitchen or bedroom set. https://affordablesoundstages.com/standing-sets/ (opened) | $2,000 |
| Build a set on a stage | Stage $3,000/day x (5 build + 1 shoot + 1 strike days); 4 propmakers x $57.82/hour x 8 hours x 6 days; materials blank | Stage: Tools for Film glossary, $3,000 to $7,000/day for a 10,000 sq ft LA stage, low end used. https://www.toolsforfilm.com/glossary/soundstage (opened). Labor: IATSE / AICP commercial agreement 2025-2028, LA County Propmaker minimum (two search readings agree; the PDF returned 403 and was not opened). | at least $32,101.44 |

At these inputs one shoot day at the real location costs **at least $29,881.44 less than building** and $220 more than the standing set. "At least" because materials are unknown until entered. Build days, strike days and crew size are **our assumptions**, labelled as such on screen; they are not sourced. A long shoot can reverse the result, and the tool says so (it reports the break-even shoot days, or that none exists). No crew, lighting, permits, insurance, travel or fringes are in any column. This is a scenario, not a quote, a bid or a measured saving.

**CoStar lease evidence.** `GET /api/production/lease/{property_id}` reads only the precomputed private rent cache (`python -m data.rent_precompute`, which needs the CoStar kit). When a record exists, the panel shows the property's lease rate per square foot per year and a prorated daily floor from its real size, as a reference that never enters a total. Without a record it says unknown. **This machine has no kit and no rent cache**, so every property here reads unknown; run the precompute on the laptop that holds the kit to light this up.

## New decision tools

- `/director` now opens with three summary tiles above the stage: what the drive limit did (for example "6 of 19 within 10 min", how many were too far or had no route, and the one-way minutes and miles to each selected property), the scouting scenario, and real location vs. building a set. Releasing the drive slider or toggling the filter rebuilds the plan automatically. The page starts on the sourced Local 399 day-rate example unless the browser holds a stored budget case.
- `/director`: employee-home or production-base map pin, explicit optional one-way drive slider (5–180 minutes). OSRM road routing filters the actual candidate pool. Unknown/unreachable/far-snapped routes are excluded when a limit is enabled. No live traffic or departure-time forecast. The circle is illustrative; it is not an isochrone. At most 24 retrieved properties are checked, not the entire metro. Mock fixtures do not call routing.
- Routing uses one table request, a five-minute bounded memory cache and a replaceable `TYPECAST_OSRM_URL` endpoint (public demonstration default). Home coordinates are not included in project JSON or browser drafts. They are sent to routing when the user builds a filtered plan. A deployment needs its own suitable routing service; the public demo is not an SLA.
- Savings update on cost inputs and plan selection. Stale, partial or manually swapped plans do not produce a savings claim. Day-rate reference preset and all assumptions remain editable. Negative outcomes remain negative.
- Free-form scene direction: reviewed B-take proposals for character blocking, dialogue and pacing; approved creative notes retain unrendered set suggestions. Apply/Discard/Undo remain explicit.
- Single-frame customization: an explicit image-upload checkbox and `TYPECAST_ALLOW_VISION_UPLOAD` plus a configured existing OpenAI image provider are required. Real indexed images only. New preview saved under ignored `cache/customizations/`, visibly and pixel-stamped as AI-imagined; the original and A/B takes remain unchanged. Arbitrary props/lighting/characters are concept art, not guaranteed geometry, animation, booking rights or an automatic new walkable world. No paid call was used in local verification.

## Filmmaker feedback supplied by the team

The user identifies the contact as **Mahimn Dave**, a short filmmaker, and supplies Discord handle **Taserface014**. On November 15 the user reported that he permitted quoting him (“feel free to”). The following quotation is supplied by the user; the coordinator has not independently read its original Discord message or verified affiliation, event timing or a hands-on product trial:

> “For a low-budget shoot, the way things usually work is: the director finds the location, set design adapts it, and production signs off because they hold the budget. If we can’t find a space that matches the vision, we either compromise the scene or build a set we can’t afford. If you guys came up with a tool that finds real spaces that fit any scene I paste, with sample shots of the area, that would change how we scout. I could save time and money and spend that elsewhere on the film.”

This supports the problem and desired workflow. It does not establish measured savings, current product accuracy or deployment. For Peri retain the actual message screenshot, person/role, business or club affiliation and event-time consultation evidence; organizers decide eligibility. Quote permission is now reported, rather than pending.

## Two-minute Business/Enterprise demonstration

1. Producer's problem: find a visually plausible room without wasting scouting days; name the actual user.
2. Paste one scene, show the actual interior/property/aerial sources and remaining uncertainty.
3. Choose a starting pin, change the drive limit, rebuild and show what was excluded. Use a rehearsed real-data route, not a synthetic positive case presented as live.
4. Show the real frame beside a previously generated, labeled imagined scene concept if available. Do not wait for an untested live image call during the pitch.
5. Open the day-rate example, show 5 to 2 assumed billable days and $2,872.74 gross potential savings. Change an assumption so the number visibly recalculates. State what must be measured in a pilot.
6. Close with the reviewed shortlist and next physical scout. The business case is qualified decisions, rather than replacing location professionals.
