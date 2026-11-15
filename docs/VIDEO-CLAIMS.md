# Business evidence and video review

Reviewed November 15, 2026, approximately 01:10 ET. Read-only review of the current GitHub-backed checkout and official external sources. No product code changed, provider call made, customer outcome measured, or video watched in this review.

## Argument and recommendation

The business story is more credible as **a producer-reviewed recce decision** than as an AI search engine or a scene generator. Existing location services already find places. Typecast can connect a script's creative requirements to an actual frame, exact property identity, aerial logistics, rejected alternatives, a commute constraint, and a portable production sign-off. The saved artifact is the business result; the beautiful scene preview is supporting evidence of creative intent.

I challenge making “saves $2,873” the headline. The source supports the daily rate, while the app assumes that three entire billable days disappear. A weekly guarantee, salaried staff, or a scout still required elsewhere can leave cash savings at zero. Filtering three properties is not eliminating three scouting days. No film studio has supplied Typecast before/after payroll or invoices.

Buyer reviewer independently agrees on a producer recce authorization memo and a prospective pilot log, rather than an isochrone or more home pins. Recommended bounded additions:

1. **Cash versus capacity semantics.** Separate avoided externally billable labor from internal hours freed. Let the producer identify hourly/day billing, guaranteed or salaried staffing, documented rate versus reference assumption, and incremental tool costs. Zero cash savings must remain possible even with time freed. Display the scenario basis beside every monetary result.
2. **Portable decision and pilot record.** Selected scene/frame/property; considered alternatives and rejection reasons; known/unknown hard constraints; chosen creative concept; questions for owner/technical scout; producer/reviewer name and decision; expected versus actually observed costs/days, with a source or note. Blank actuals remain “not measured.” A local browser session's elapsed time is tool interaction time, not scouting labor avoided. JSON/print export preserves assumptions and unknowns.

This is a stronger reason for a company to try the product than additional generative models. It also gives the pitch a close: “Here is the decision production can review before authorizing the next physical scout.” No fabricated booking, permission, signatures or approvals.

## Claims ledger

| Candidate number or statement | Category and allowed wording | Necessary limit | Source |
| --- | --- | --- | --- |
| **$957.58/day** | Sourced commercial labor reference: “2026 covered location scout-manager daily minimum.” | Local 399/AICP commercial agreement, effective June 28, 2026. Not a universal studio, feature-film, student, indie or market-average rate; fringes/overtime/guarantees not included by this number. | [Official wage chart, p.2](https://www.ht399.org/app/uploads/2026/06/APPENDIX-A-Wage-Chart-Drivers-and-Locations-final-6.24.26.pdf) |
| **$2,872.74** | Arithmetic scenario: “Gross labor potentially avoided **if three billable commercial scouting days are eliminated**.” | One scout × 3 assumed days × $957.58/day. Not observed customer savings. Deduct actual incremental tool costs; guaranteed compensation may not disappear. | Same wage chart + explicit app inputs in `index/production-costs.js` and `docs/BUSINESS-CASE.md` |
| **$1,915.16–$4,787.90** | Sensitivity scenario for 2–5 whole billable days avoided. | Not a predicted range of Typecast outcomes. It varies an assumed input, rather than measuring uncertainty statistically. | Same source + multiplication |
| **4,171 on-location shoot days, Q3 2026** | External industry activity context: substantial recurring location work in FilmLA-served Greater LA jurisdictions. | FilmLA counts one crew's permission to film at one or more locations within a 24-hour period. Not number of productions, locations, potential customers or nationwide market size. Excludes certified sound stages and other jurisdictions. | [FilmLA Q3 report, Oct 21, 2026](https://filmla.com/filmla-q3-report-tax-credit-projects-now-make-up-40-percent-of-scripted-on-location-filming-in-los-angeles-nearly-double-last-years-share/) |
| **562 commercial shoot days, Q3 2026** | Optional narrower activity context for the commercial wage reference. | Same FilmLA jurisdiction and shoot-day definition. Do not multiply by the scouting rate to invent an addressable market or aggregate savings. | Same FilmLA Q3 report |
| **10,568 views / 343 properties / 329 models** | Repo-recorded indexed coverage in a frozen LA/Houston generation. | Not 343 bookable or film-permitted locations. Multiple views of one space are not independent properties. Private cache not reproduced by this reviewer. | [`docs/team/status-lane-c.md`](https://github.com/Tecncentral/typecast/blob/ae1f1e0a085d80c241025b05f0e81e71af058025/docs/team/status-lane-c.md), frozen generation and Job 8 |
| **8.923 s fixed / 40.923 s deep** | Repo-recorded warm request medians over five authored demo scenes per engine. | All visual scores cached; one request per scene/engine. First fixed request included lazy initialization; deep had earlier warmups. Not a general SLA, cold-start comparison or measured human time saved. Recheck after final merge. | Same lane-C source, Job 8 stage rehearsal |
| **73.33% precision@10 lower bound** | Repo-recorded post-change repeated evaluation, 110/150 returned slots judged relevant. | 15 scenes, one human reviewer, same labels after v1-informed changes; 8 unjudged slots counted as misses. Not a new untouched holdout, general accuracy, final-card precision or proof of money saved. Probably omit from the 2-minute video to avoid an explanation detour; retain in technical appendix. | [`docs/team/eval.md`, v2](https://github.com/Tecncentral/typecast/blob/ae1f1e0a085d80c241025b05f0e81e71af058025/docs/team/eval.md#v2-after-changes-informed-by-v1) |
| **66% precision@10 lower bound** | Frozen v1 evaluation, 99/150 returned slots. | Same small single-reviewer study; pooled judgments, not exhaustive catalog accuracy. Preserve beside v2 in the appendix instead of silently replacing it. | Same evaluation source, v1 supplement |
| “I could save time and money and spend that elsewhere on the film.” | User-supplied filmmaker feedback, permission to quote reported by user. | Mahimn Dave / reported Discord handle Taserface014. Conditional value statement, not observed product use, endorsement, willingness to pay or measured savings. Original screenshot, affiliation and event-time evidence remain unverified in this review. | `docs/BUSINESS-CASE.md` user-supplied quotation and provenance |
| **693 Python / 233 Node / 19 browser checks** | Engineering validation recorded in current release checkpoint. | Helps readiness; does not establish customer importance, adoption, business ROI, image quality or real private-data commute acceptance. Do not spend video time listing tests. | [`index/RELEASE-CHECKPOINT.json`](https://github.com/Tecncentral/typecast/blob/ae1f1e0a085d80c241025b05f0e81e71af058025/index/RELEASE-CHECKPOINT.json) |

The governor's July 7, 2026 announcement projects $6.6B production spending and 34,921 cast/crew jobs across 170 tax-credit-awarded projects. This is a projected selected-program total, not Typecast's market size or realized savings. I recommend omitting it from the main video. [Official announcement](https://www.gov.ca.gov/2026/07/07/lights-camera-action-first-year-of-californias-expanded-film-tv-tax-credit-projected-to-bring-6-6-billion-in-economic-impact/).

FilmLA says one application fee coordinates up to five filming locations; this directly undermines automatic “fewer locations means fewer permit fees” claims. [Official 2026 fee notice](https://filmla.com/client-jurisdiction-fee-increases-effective-july-1-2026/). Do not add unquoted permit, construction, insurance, rental or delayed-production savings.

## Proposed 116-second video

Use a real product recording from the demo laptop. Edit waiting time only with an obvious “time compressed” caption and show actual captured elapsed time. A recorded replay is labeled recorded. Keep the displayed source mode and AI-image label visible. A synthetic mock UI or AI-generated movie must never pose as a live private-data success. An AI visual could be an opening concept illustration, but actual product footage is more valuable.

| Time | Picture and number | Voiceover direction |
| --- | --- | --- |
| 0–10 | One scene description, scattered location references, then producer's question. Small label: “Which real location deserves the next scout?” | “A director has a scene in mind. Production needs a real place, workable logistics and a budget before sending people out.” |
| 10–22 | Brief user-supplied filmmaker quotation, attributed with permission provenance. | “A short filmmaker told us that when a space does not match the vision, teams compromise the scene or build a set they cannot afford. We built Typecast for the decision before that commitment.” |
| 22–43 | Actual scene → shortlist → exact Matterport frame / CoStar property / Vexcel aerial. Brief overlay “10,568 indexed views · 343 properties · LA/Houston snapshot.” | “Paste a scene. Typecast connects actual camera views to their property and aerial logistics. Unknown dimensions and permission stay unknown. The shortlist is a reason to inspect, not a filming approval.” |
| 43–61 | Real rejected alternative, home/base pin, drive limit and rebuilt result. Show actual known route or honest unknown; do not rehearse a synthetic positive as real. | “A pretty room can still fail production. Set a one-way drive limit and crew needs. The planner excludes conflicting or unknown routes and preserves the reasoning behind the alternatives.” |
| 61–75 | Real frame beside cached or actually generated AI preview; visible “AI-imagined, not the real room.” | “Preview the creative intent without confusing imagination with evidence. Review a new take or an imagined set while keeping the real room visible.” |
| 75–96 | Editable cost comparison; big $2,872.74 with equally visible “SCENARIO: 3 whole billable days avoided × $957.58 commercial reference.” Show zero-cash case if salary/guarantee mode is added. | “Here is the business case, with its assumptions exposed. Eliminate three whole billable commercial scouting days at the published reference rate and gross labor avoided would be about twenty-eight hundred seventy-three dollars. Guaranteed staff may save time without reducing payroll. We calculate both honestly.” |
| 96–109 | Producer decision memo / export if implemented; otherwise show existing shoot pack and call it that. Select next physical-scout checks. | “Production gets a reviewable decision: chosen frame, alternatives, constraints, cost basis and exactly what the next physical scout must verify.” |
| 109–116 | Logo + one line: “Preserve the scene. Qualify the location. Explain the decision.” | “Typecast helps a production team choose what to scout next, with evidence it can review.” |

Approximate narrated length is 240–270 words. Do not guarantee timing until read aloud and timed. Prefer one speaker, legible cursor movement, 1080p landscape, quiet background, and hard subtitles. Real-time audience action—not an agent-org chart—is the central demonstration.

## Numbers to capture now without inventing customer data

- Exact selected-plan scene coverage and location count from the actual final demo response; no memorized three-scenes/one-location overlay if the result differs.
- Actual request elapsed time and mode for that recording; do not substitute an older faster benchmark.
- A manual-versus-assisted timed task can be measured only if a human actually performs comparable tasks. A new unsupervised stopwatch proves session duration, not baseline savings. Until performed, label pilot outcome “not measured.”
- Actual eliminated invoices, labor days or costs require a real follow-up and producer confirmation; no autonomous agent can create that evidence retrospectively.

## Debate conclusion

The rate and coverage are defensible; the efficacy assumption is the weak link. Make that visible and give production a useful decision artifact. One honest before/after decision is more persuasive than dozens of claimed features, unsourced “industry wastes billions” graphics, or a generated cinematic trailer.

Winner-video examples are not verified yet in this review. The Fall 2025 Devpost winners-gallery fetch failed; search snippets were insufficient to certify both an award and the exact video. Do not label unverified YouTube clips as winners. This can be a separate follow-up after the business proof and recording are ready.
