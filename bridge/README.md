# bridge/ (Owner 4)

Turns a text conversation into calls to the Typecast API.

| File | What | Status |
| --- | --- | --- |
| `core.mjs` | Conversation logic: scene, follow-up re-rank, `draft N`, YES / NO approval | Tested (`node --test`), and run end to end against the API |
| `terminal.mjs` | Chat in a terminal with the same logic | Run end to end |
| `photon.mjs` | Photon line (iMessage) through `spectrum-ts` 12.16.0 | **Not run.** Written from the package README and type files. Check `textOf()` on the first real message |

```bash
uvicorn agent.app:app --port 8000
```

```bash
node bridge/terminal.mjs
```

```bash
cd bridge && npm install && PHOTON_PROJECT_ID=... PHOTON_PROJECT_SECRET=... node photon.mjs
```

Env: `TYPECAST_API` (default `http://localhost:8000`), `TYPECAST_VIEWER`. For a phone to load images, the API must be reachable from the internet (a tunnel), and `TYPECAST_API` set to that address.
