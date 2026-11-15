# Photon iMessage line (branch `photon-imessage`)

Updated 2026-11-15 05:35 ET. Stage 1 only: "Text your location scout" (conversational intake). Stages 2 and 3 are not started.

**Mode: mock only.** The line replies from `mocks/` data. `bridge/watch.mjs` refuses to start unless the API's `/health` says `mocks: true` with every source `mock`. No real CoStar or Vexcel data can go through Photon. Only images under `mocks/` are ever attached; anything else is dropped.

**Not verified on a real phone.** Everything below was tested with fakes and against the real mock API. The Photon wiring follows the `spectrum-ts` 12.16.0 types (as `bridge/photon.mjs` does) and has not run against a live Photon project.

## What is new (new files, plus one added line in `web/index.html` and two empty names in `.env.example`; no other existing file is edited)
| File | What |
| --- | --- |
| `bridge/intake.mjs` | Pure intake functions plus `handleMessage`, which drives `core.mjs` unchanged. State lives in core's `sessions` map under the same conversation key. |
| `bridge/intake.test.mjs` | 15 tests, mock data only. |
| `bridge/watch.mjs` | Photon runner: sender allowlist, mock-mode check, mock-image attachments. |
| `web/deeplink.js` + `web/tests/deeplink.test.mjs` | Fallback link hook, loaded by the one script line in `web/index.html` (see below). 5 tests. |
| `web/index.html` | One added line, approved and applied: `<script type="module" src="./deeplink.js"></script>`, after `strike.js`. Nothing else in the file changes. |
| `.env.example` | Adds the names `PHOTON_ALLOWED_SENDERS` and `PHOTON_VIEWER_URL` (empty). `PHOTON_PROJECT_ID` and `PHOTON_PROJECT_SECRET` were already there. |

## How the intake works
- No LLM call in the bridge: keyword and regex rules only. The backend parser still reads the final scene text.
- Slots: setting (required), city LA or Houston (required), time of day, era, trucks, cars. Mood words such as "grimy" become "Gritty".
- Every slot the director already gave is filled. Only missing ones are asked, one question per message, at most 4, in this order: setting, city, time, era, trucks and cars. Each question offers short options and accepts "skip" or "any". An answer that fills other slots too ("LA, 80s") fills them all.
- A first message that starts `INT.` or `EXT.`, or already has a setting and a city, or is long, searches at once with no questions. An `INT.`/`EXT.` message goes to `/scout` unchanged.
- When ready it builds one scene string, replies `Searching for: <scene>` and calls `POST /scout` with it, for example `INT. 1980s POLICE STATION, NIGHT. Los Angeles. Gritty. Parking for 3 trucks and 30 crew cars.`
- "start over" or "new search" resets the conversation. After results, `core.mjs` behaviour is unchanged: re-rank text ("need parking for 5 trucks"), "draft N" then YES or NO (local draft only).
- Stage 1 replies show no prices. Any price added later must carry "scenario estimate, not verified savings".

## Senders and secrets
- `PHOTON_ALLOWED_SENDERS` is a comma, semicolon or newline separated list of phone numbers or emails. A number is matched on its digits, so spaces, dashes, brackets and a leading +1 do not matter. An empty list, or a message whose sender cannot be identified, is ignored (fail closed). The sender is `message.sender.id`.
- Texts from any other sender get no reply and are only counted in the log. Values from `.env` are never printed or logged.

## Where the link goes (the check you asked for)
1. **Does the viewer open a finished search from a link?** No. `core.mjs` linked to `<viewer>#/run/<thread_id>`, but `web/app.js` has no hash routing; the only hash the viewer reads is `#walk=` for the viewfinder. That link opened the site and did nothing.
2. **Does the backend return a saved thread's results?** No. `agent/app.py` has `POST /scout`, `GET /scout/stream` (needs a scene), `POST /refine` and `POST /approve`, and no read-only route for a saved thread.
3. **So the fallback is used.** `web/deeplink.js` reads `?scene=<encoded>&autorun=1`, fills the scene box and presses the normal run button. The reply says "See them in 3D: <link> (opens the site and runs this search live)" because it is a second live search, not the same thread. The link is built from `PHOTON_VIEWER_URL`; if that is empty or not an http(s) URL, the link is left out. No public tunnel is opened.

**Applied (approved): one added line in an existing file.** `web/index.html` now loads `web/deeplink.js`; without that line the hook would be inert. The change:

```
--- a/web/index.html
+++ b/web/index.html
@@ -205,5 +205,6 @@
     <script type="module" src="./viewfinder-frame.js"></script>
     <script type="module" src="./viewfinder-edit.js"></script>
     <script type="module" src="./strike.js"></script>
+    <script type="module" src="./deeplink.js"></script>
   </body>
 </html>
```

### Proposal for Owner 3: read-only saved-thread route
Add `GET /thread/{thread_id}` that returns the thread's last `ScoutResponse` without running anything. Threads are already in `agent/state.py` (in memory, 6 hour expiry, `UnknownThread` when absent) with the shortlist and sources saved. It would validate the id with `THREAD_ID_PATTERN`, return 404 for an unknown or expired thread, and make no provider call. The viewer could then open `/app/#/run/<thread_id>` and render the same results, so the existing `core.mjs` link would work as written. Until then the live-search fallback above is the honest option. Note the 6 hour expiry: a saved link only works while the server still holds the thread.

## To run it (Windows, PowerShell, from the repo root)
1. Put `PHOTON_PROJECT_ID`, `PHOTON_PROJECT_SECRET`, `PHOTON_ALLOWED_SENDERS` and, optionally, `PHOTON_VIEWER_URL` in this worktree's `.env`.
2. Start the API in mock mode: `$env:TYPECAST_USE_MOCKS="1"; $env:TYPECAST_ENGINE="fixed"; $env:TYPECAST_ENABLE_MODEL_PARSE="0"; $env:TYPECAST_ENABLE_VISION_RERANK="0"; $env:LANGSMITH_TRACING="false"; .\.venv\Scripts\python -m uvicorn agent.app:app --host 127.0.0.1 --port 8000`
3. `cd bridge; npm install; cd ..; node bridge/watch.mjs`

## Verification so far
- Bridge tests: 21 pass (6 existing in `core.test.mjs`, 15 new). Web node tests: 29 pass (24 existing, 5 new).
- The example conversation, a re-rank, "start over" and a detailed first message were run through `handleMessage` against the real mock API (no fakes): three questions, then one `/scout` call with the exact target scene string.
- `watch.mjs` was dry-run: it exits with a clear message when credentials or the allowlist are missing, when the API is unreachable, and when the API is not in mock mode. It was not run against Photon.

## Still to do on a real phone (screenshots to `cache/screens/photon/`)
- [ ] The example conversation end to end: "need a cop station for a night interrogation scene", "LA", "80s, kinda grimy", "3 trucks 30 cars".
- [ ] One detailed first message that searches immediately.
- [ ] "start over".
- [ ] Tap the "See them in 3D" link from the text (needs `PHOTON_VIEWER_URL` set to an address the phone can reach): the site should open and start the same search live.
- [ ] Check the first inbound message's text and sender on the phone (`textOf` and `message.sender.id` are unverified), and whether image attachments from a file path arrive.
- If the intake is not working on a real phone by 5:45, fall back to the original Stage 1 (`bridge/photon.mjs`, a single scene text searches directly).

## Known limits
- `core.mjs` prints "1 trucks" when there is one truck space; not changed here.
- The intake knows about 30 kinds of place; an unknown one is taken from phrases like "need a ...", and a short reply to the setting question is used as the setting as typed.
- City is LA or Houston only. A skipped or unclear city leaves it out and the backend searches Los Angeles; the "Searching for" line says so.
