# Decisions

One line each: date/time, owner, decision, why.

- Product is Typecast; LookAlike is a second search mode on the same index.
- Main track: Entertainment and Media. Special tracks: CoStar, LangChain, Peri, Photon, Amazon, ChatOverflow.
- Agent harness: LangChain deepagents (Python). A fixed-order pipeline (`agent/pipeline.py`) stays as the fallback.
- World Labs is a stretch goal only.
- Tools return mock data while `TYPECAST_USE_MOCKS=1`, so all lanes can build in parallel.
- No message reaches a real property owner; drafts go to TEAM_INBOX after an explicit yes.
- 2026-11-14, Owner 3: the app's model calls use OpenAI (the team's credits expire soon); Anthropic is an optional fallback. Model ids live in .env, never in code.
- 2026-11-14, Owner 3: a sponsor engineer confirmed that Matterport scan images may be sent to a third-party vision model for this hackathon. Engineer's name: TBD. Enabled per laptop with TYPECAST_ALLOW_VISION_UPLOAD=1.

- 2026-11-14, Owner 3: fixed remains the default; deepagents uses the same evidence/ranking tools and announces fixed fallback after errors or 90 seconds. Real deep model proof on mocks took 87.828 seconds.
- 2026-11-14, Owner 3: approval only writes a local outbox draft; no delivery integration or TEAM_INBOX is required. Deep approval uses the actual package checkpoint.

- 2026-11-14 16:00 UTC, Owner 3: “available” means verified active property-attributable marketed lease space with positive area, nonpending status and known timing under data/SCHEMA.md; never vacant or filming-approved. Current joined LA count 216 versus 269 under the older active-listing rule: overlap 215, current-only one, older-only 54. Of those 54, nine lack scans; among the 45 joined properties, 44 are active sale/auction without verified lease space and one lacks sufficient lease-space evidence. Preserve the 13,096-pair join; never replace it with the older LA-only zip.
- 2026-11-14, Owner 3: the team confirmed with the sponsor (Nov 13 evening) that scan photos of the demo rooms may be sent to World Labs. AI-dressed sets use World Labs Atlas (the team's key is an Atlas key; the legacy Marble API rejects it). Dressed frames are depth-guided restyles that keep the real geometry, always labelled "AI-imagined set dressing, not the real room". TYPECAST_ENABLE_DRESSED=0 hides them.
- 2026-11-14, Owner 3: walkable AI sets render Atlas Gaussian splats in the viewfinder with three.js 0.180 and Spark 2.4 (both MIT, vendored in `web/vendor/`, loaded only when a set opens). Drafts cost 500 credits and refined splats 5,000; `worlds.dress --splat` refuses to run without a matching `--allow-spend-credits`. The walk is limited to the floor the scan point could see, read from the splat.
- 2026-11-14, Owner 3: whole-room AI sets take their cameras from Matterport's measured scan positions and rotations, not from Atlas's estimate. On the LA open-plan office Atlas posed 2 of 6 scan points inconsistently (0.8 to 1.9 m RMS against the scan); where it was consistent it agreed with Matterport within 2.4°. Atlas supplies depth and the size of its world unit only. Cube heading 0 is the scan's local +x axis.
- 2026-11-15, Owner 3: stand-ins in walkable sets are six animated figures by Quaternius, each published as CC0 (public domain) on Poly Pizza; source pages and download URLs are in `web/vendor/people/README.typecast.md`. No Mixamo or other restricted character is in the repository. Primitive-built mannequins remain as the fallback. Stand-ins are only offered in whole-room sets, where the scale comes from the scan.
- 2026-11-14 22:30 ET, Owner 3: a follow-up that only changes trucks or cars keeps the saved visual order and makes no new image-scoring calls; picks move only for parking reasons. Other follow-ups still re-score the saved pool. The map shows each pick's nearest traced lot on its Vexcel aerial with demand against floor(area/30 m²), beside CoStar's recorded spaces; the lot is never claimed as the property's own parking.
- 2026-11-15 02:30 ET, Owner 3 (answers the team got from the sponsor, reported by the team lead; contact name TBD): Vexcel imagery (ortho and oblique) may be sent to outside AI models for this hackathon, so the oblique search's vision scoring and the reimagine chat stay on. Property coordinates may be sent to the public OSRM server for drive times. Vexcel's billing unit is still unconfirmed; the team treats access as unmetered for the hackathon, keeps the spending ledger running and raises its caps through TYPECAST_VEXCEL_* environment overrides on demo machines instead of removing the guard.

