# Decisions

One line each: date/time, owner, decision, why.

- Product is Typecast; LookAlike is a second search mode on the same index.
- Main track: Entertainment and Media. Special tracks: CoStar, LangChain, Peri, Photon, Amazon, ChatOverflow.
- Agent harness: LangChain deepagents (Python). A fixed-order pipeline (`agent/pipeline.py`) stays as the fallback.
- World Labs is a stretch goal only.
- Tools return mock data while `TYPECAST_USE_MOCKS=1`, so all lanes can build in parallel.
- No message reaches a real property owner; drafts go to TEAM_INBOX after an explicit yes.
