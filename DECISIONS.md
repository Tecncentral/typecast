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
