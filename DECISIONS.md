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
