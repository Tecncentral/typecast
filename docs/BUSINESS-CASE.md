# Typecast: location decisions before production commits

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

No set-construction savings are added. We have no actual construction bid or proof that Typecast avoided building a set. No automatic permit savings are added: FilmLA says its application covers up to five filming locations, so fewer locations need not remove a permit application fee. Source: https://filmla.com/client-jurisdiction-fee-increases-effective-july-1-2026/ .

## New decision tools

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
