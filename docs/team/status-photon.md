# Photon iMessage line (branch `photon-imessage`)

Updated 2026-11-15, branch `photon-v2` (v1 was verified on a phone; v2 is offline only). Stage 1 only: "Text your location scout" (conversational intake). Stages 2 and 3 are not started.

**Platform: Photon 2.0 Beta.** The project is on Photon Beta, so the runner is **`bridge/watch-beta.mjs`**: `@photon-ai/api` 0.6.0, Bearer auth, `projects.listMessages` polling and `projects.sendMessage`, following the [Beta iMessage guide](https://photon.codes/docs/beta/get-started/imessage.md). `bridge/watch.mjs` was my first runner and uses the **Stable** SDK `spectrum-ts`; Photon rejected the Beta project ID with it (HTTP 422). It, and the older `bridge/photon.mjs`, do not work with a Beta project and are **kept only as history**. Beta iMessage supports text and images only, and the runner sends plain text only.

**Mode: mock only.** Replies come from `mocks/` data. `bridge/watch-beta.mjs` refuses to start unless the API's `/health` says `mocks: true` with every source `mock`. No real CoStar or Vexcel data can go through Photon.

**Verified on a real phone, mock data only.** Three tests passed on a real iPhone, run by Udit against the Beta runner and the mock-mode API; every reply came from `mocks/` data:
1. The example conversation (a short brief, then the follow-up questions, ending in a search) got replies.
2. A first message starting `INT.` searched immediately and got a reply.
3. "start over" got a reply.

**Still UNVERIFIED** (not tested on a phone): the "See them in 3D" link, images (the runner sends plain text only), a text from a non-allowlisted sender getting no reply, no message answered twice after a restart, and long unattended runs. Real CoStar or Vexcel data has never gone through Photon.

## Photon v2 (branch `photon-v2`): offline only, real-phone run NOT DONE
v2 adds compact results, a local simulator and a dry-run mode on top of the verified runner. **It has not been run against a real phone and no Photon message was sent while building it.** The three passed phone tests above were v1. Everything below is tested offline only (fakes and the simulator) until someone says "go real".

### Credit model (what the Photon docs say)
- Photon Beta [Plans and billing](https://docs.photon.codes/docs/beta/plans-and-billing.md): "Photon does not charge per-message usage fees for iMessage, WhatsApp, or Telegram sends." Per-message rates are listed only for SMS, MMS, voice and email.
- The [Billing](https://docs.photon.codes/docs/beta/billing.md) page's "How usage is counted" covers SMS parts, MMS, voice minutes and email recipients; it does not list iMessage.
- The Free plan includes up to 25 shared iMessage assignments. That limits seats (identities assigned to the shared line), not messages.
- **Not documented:** any per-message allowance, quota or credit for iMessage, and a numeric send rate limit. The API can answer 429, and the SDK has a `message_rate_limited` failure; the runner already honours `Retry-After`.
- So there is no documented per-send cost, and the cap below is a safety and readability limit, not a billing control. Delivery is still unconfirmed by the API (it confirms acceptance only).

### Send budget: at most 8 outbound messages per search
Counted per conversation across questions, the confirmation, the results bubble, the exterior line and the link. Anything past 8 is dropped and counted in the log (`conversation 1: 6 of 8 outbound in this search`; the log shows an ordinal, never an id).

| Flow | Outbound messages |
| --- | --- |
| Cop-station example (city, exterior and look, parking, search) | 6: 3 questions, confirmation, results, link |
| Interior plus exterior in one brief, with a link | 4: confirmation, results, exterior line, link |
| One detailed `INT.` message, with a link | 3: confirmation, results, link |
| Worst case | 7 (3 questions, confirmation, results, exterior line, link), plus at most 1 non-text notice = 8 |
| Re-rank, `draft N`, YES or NO | 1 each |

### What v2 does
- **Intake** (`bridge/scout-v2.mjs`, keyword and regex only): interior slots (place, era, time, mood), an optional exterior, and shared city (LA or Houston, required), trucks and crew cars. Every message is parsed for all slots. `INT.` and `EXT.` headings route text; the words outside, street, alley, rooftop, exterior, parking lot, establishing go to the exterior. At most **3 questions**, each asked once: (A) place and/or city if missing, (B) an exterior plus era or mood, (C) trucks and crew cars. "skip", "any" and "no" are accepted. A message with an `INT.`/`EXT.` heading asks nothing.
- **Corrections** ("actually Houston", "make it day") overwrite the slot and add a one-line `Updated: ...` note; after results they search again. "start over" resets.
- **Rapid messages** that arrive together are merged into one input after a 2 s window (`bridge/conversations.mjs`). Replies are queued per conversation and awaited in order. Duplicate message ids, the agent's own echoes, tapbacks, read receipts and typing updates are ignored. A photo or voice note from an allowlisted person gets "I can only read text for now: describe the scene in words." once (until their next text); a stranger's photo gets nothing.
- **Before searching:** one confirmation bubble (Interior / Exterior / city, trucks, crew cars), then the search runs at once.
- **Results:** the interior scene string goes to `POST /scout` exactly as echoed. The exterior is **never searched** from the phone: the reply says "Exterior search ready on the site: <query> (runs live when you open it)." Order: (a) one bubble `MOCK · 3 interior picks` with picks 1, 2, 3 in rank order, two lines each, keeping `(FAKE)`, `est.` and `unknown` wording and dropping internal wording; (b) the exterior line if requested; (c) the link alone, last, only if `PHOTON_VIEWER_URL` is set. A failed send is retried once with the same idempotency key, then "Pick list couldn't be sent, open the link instead." If there are no picks or something was relaxed, one line says what, and the link is still sent.
- **After results:** "need parking for 5 trucks" goes to `/refine` with one compact bubble; "draft 1" then YES gives "Saved as a local draft, not sent"; anything unclear gets a one-line help message.
- **Images:** none are sent. Beta iMessage accepts an `attachment` content type, but it needs a prior upload (`uploadAttachment`, a two-part body with an exact JSON header plus the file bytes) that the Beta guide does not document, so it is skipped rather than guessed. A mock image would also cost an extra send.

### Link contract
`PHOTON_VIEWER_URL` + `/app/?scene=<interior>&ext=<exterior>&city=<LA|HOU>&trucks=<n>&cars=<n>&autorun=1`, every value URL-encoded, empty parameters omitted. `PHOTON_VIEWER_URL` may or may not end in `/app/`; the bridge normalises it. `autorun=1` is added only when `scene` is present and means "run the free mock interior search"; **an exterior never autoruns** because it is a billable Vexcel search. The viewer reads `scene` and `autorun` today (`web/deeplink.js`); `ext`, `city`, `trucks` and `cars` are accepted for the hand-off proposed below and are otherwise ignored.

### Web changes: proposed, NOT applied
The exact diffs for `web/deeplink.js` (an exterior hand-off note with a link to the outdoors page), `web/oblique.js` (pre-fill `?q=&city=`, never submit) and `web/index.html` (Open Graph tags) were shown to Udit for a yes. Nothing under `web/` changed on this branch. Owner 4 allows only one-line hooks in `index.html`; the proposal is one added line.

### Simulator and dry run
- `node bridge/sim.mjs` (interactive) or `node bridge/sim.mjs --script bridge/fixtures/<name>.txt`. It runs the **same runner** (allowlist, message filter, merge window, intake, formatting, ordering, retry) against a fake Photon client that sends nothing, and prints every outbound bubble with a counter. The fake backend serves `mocks/pick.json`, so no API needs to be running. It uses synthetic numbers. Script commands are listed at the top of `bridge/sim.mjs` (`@other`, `@photo`, `@tapback`, `@dup`, `@burst a | b`, `@fail N`, `@failresults`, `@nomatch`, `@viewer URL`).
- `PHOTON_DRY_RUN=1 node bridge/watch-beta.mjs` reads real messages and sends nothing. It still calls the mock API. It logs only a running count and a length (`dry run: would send reply 3 (214 characters); nothing was sent`), never the text, because real inbound text must not be printed.

### v2 tests (offline, mock data only)
- Bridge: 67 pass (6 core, 15 intake v1, 22 `watch-beta`, 24 golden). Web: 29 pass (no web file changed).
- Golden transcripts through the simulator: the four-message cop-station example; interior plus exterior; one detailed `INT.` message (0 questions); corrections; start over; rapid double-send merge; duplicate message id; photo and tapback; no matches; refine; draft YES and NO; unclear text; a failed send (retried once) and a failed results bubble (fallback line); an unallowlisted sender (no reply, no search); junk answers (at most 3 questions); no viewer URL. Every flow asserts at most 8 outbound, picks in order, a `MOCK` label, no "Blocked alternative" or "delivered", plain text only, unique idempotency keys, and correct link parameters.
- **Real-phone run of v2: NOT DONE.** To do it, someone must say "go real", then run the checklist below with v2 on the allowlisted phone.

## What is new (new files, plus one added line in `web/index.html`, one added dependency in `bridge/package.json` and three empty names in `.env.example`; no other existing file is edited)
| File | What |
| --- | --- |
| `bridge/intake.mjs` | Pure intake functions plus `handleMessage`, which drives `core.mjs` unchanged. State lives in core's `sessions` map under the same conversation key. |
| `bridge/intake.test.mjs` | 15 tests, mock data only. |
| `bridge/watch-beta.mjs` | **The Photon 2.0 Beta runner** (see below). |
| `bridge/watch-beta.test.mjs` | 22 offline tests with fakes. |
| `bridge/package.json` | One dependency added: `@photon-ai/api` 0.6.0, pinned exactly like `spectrum-ts`. No npm lockfile is tracked, so none is added. |
| `bridge/watch.mjs` | **History.** Stable SDK runner; does not work with a Beta project. |
| `web/deeplink.js` + `web/tests/deeplink.test.mjs` | Fallback link hook, loaded by the one script line in `web/index.html` (see below). 5 tests. |
| `web/index.html` | One added line, approved and applied: `<script type="module" src="./deeplink.js"></script>`, after `strike.js`. Nothing else in the file changes. |
| `bridge/scout-v2.mjs`, `bridge/conversations.mjs` (v2) | The v2 conversation engine and the per-conversation delivery (merge, order, budget). New files. |
| `bridge/sim.mjs`, `bridge/fixtures/*.txt`, `bridge/golden.test.mjs` (v2) | Simulator, scripted conversations and 24 golden tests. New files. |
| `bridge/watch-beta.mjs`, `bridge/watch-beta.test.mjs` (v2 edits) | Small edits: uses the v2 engine and manager, accepts non-text for the one-time notice, retries a failed send once, adds `PHOTON_DRY_RUN`. Five tests updated for the new wording. |
| `.env.example` | Adds the names `PHOTON_ALLOWED_SENDERS`, `PHOTON_AGENT_HANDLE` and `PHOTON_VIEWER_URL` (empty). `PHOTON_PROJECT_ID` and `PHOTON_PROJECT_SECRET` were already there. |

## How the Beta runner works
- **Environment** (read from `.env`): `PHOTON_PROJECT_ID`, `PHOTON_PROJECT_SECRET` (used as the Bearer API key), `PHOTON_AGENT_HANDLE` (the number Photon assigned), `PHOTON_ALLOWED_SENDERS`, and optionally `PHOTON_VIEWER_URL`. A missing variable stops it with only the variable's name.
- **Polling:** `projects.listMessages` every 2 seconds for received iMessages, oldest first, 100 per page, following `nextPageToken`. It starts from 5 seconds before launch and ignores anything created before it started; a restart does not recover older messages. The query window slides forward with a 60 second overlap, and processed ids are remembered, so overlap never causes a second answer.
- **Which messages it answers:** only plain text, in a direct iMessage space, sent by a human whose handle is on `PHOTON_ALLOWED_SENDERS` and received by an agent whose handle is `PHOTON_AGENT_HANDLE`, and not sent by the agent itself. Phone numbers are matched on their digits (spaces, dashes, brackets and a leading +1 do not matter) and emails in lower case. Everything else is ignored and only counted.
- **No duplicates:** processed message ids are kept in memory (bounded to 10,000). A message is marked before it is answered, so a failed send is never retried as a new answer.
- **Replies:** the text goes to `handleMessage` under the space id as the thread key. Each reply part is sent as plain text with `projects.sendMessage` (the incoming message's space, the agent's user id as sender, the incoming message as parent). Images are not sent. Replies over 1,500 characters are split. One conversation is handled at a time so its replies stay in order.
- **Idempotency:** the key is `typecast-reply:<incoming message id>:<n>`, stable per incoming message. It has a number because reusing one key for a different request is a 422, and one intake reply is several messages. A retry reuses the exact same key.
- **Rate limits and errors:** a 429 waits for `Retry-After` (or 5 seconds, doubling up to 2 minutes) and never polls faster than every 2 seconds. Server and network errors back off the same way. 400, 401, 403, 404 and 422 on polling stop the runner. A failed send is logged and the runner carries on.
- **Output:** it never prints a key, project id, phone number, space id, message id or message text. An API error prints only `Photon API error <status> (request <id>).` Counts of ignored messages are printed, nothing else.

## How the v1 intake works (verified on a phone; replaced on `photon-v2` by the section above)
- No LLM call in the bridge: keyword and regex rules only. The backend parser still reads the final scene text.
- Slots: setting (required), city LA or Houston (required), time of day, era, trucks, cars. Mood words such as "grimy" become "Gritty".
- Every slot the director already gave is filled. Only missing ones are asked, one question per message, at most 4, in this order: setting, city, time, era, trucks and cars. Each question offers short options and accepts "skip" or "any". An answer that fills other slots too ("LA, 80s") fills them all.
- A first message that starts `INT.` or `EXT.`, or already has a setting and a city, or is long, searches at once with no questions. An `INT.`/`EXT.` message goes to `/scout` unchanged.
- When ready it builds one scene string, replies `Searching for: <scene>` and calls `POST /scout` with it, for example `INT. 1980s POLICE STATION, NIGHT. Los Angeles. Gritty. Parking for 3 trucks and 30 crew cars.`
- "start over" or "new search" resets the conversation. After results, `core.mjs` behaviour is unchanged: re-rank text ("need parking for 5 trucks"), "draft N" then YES or NO (local draft only).
- Stage 1 replies show no prices. Any price added later must carry "scenario estimate, not verified savings".

## Where the link goes
1. **Does the viewer open a finished search from a link?** No. `core.mjs` linked to `<viewer>#/run/<thread_id>`, but `web/app.js` has no hash routing; the only hash the viewer reads is `#walk=` for the viewfinder. That link opened the site and did nothing.
2. **Does the backend return a saved thread's results?** No. `agent/app.py` has `POST /scout`, `GET /scout/stream` (needs a scene), `POST /refine` and `POST /approve`, and no read-only route for a saved thread.
3. **So the fallback is used.** `web/deeplink.js` reads `?scene=<encoded>&autorun=1`, fills the scene box and presses the normal run button. The reply says "See them in 3D: <link> (opens the site and runs this search live)" because it is a second live search, not the same thread. The link is built from `PHOTON_VIEWER_URL`; if that is empty or not an http(s) URL, the link is left out. No public tunnel is opened. The link is plain text in the reply, so a phone can open it only if `PHOTON_VIEWER_URL` is an address the phone can reach.

The one added line in `web/index.html` (approved and applied):

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
1. In the Photon Beta dashboard, add the identity you will send from and assign the shared number (see the Beta iMessage guide). You must start the conversation yourself: a shared line cannot send first.
2. Put the five variables above in this worktree's `.env` (never commit it).
3. Start the API in mock mode: `$env:TYPECAST_USE_MOCKS="1"; $env:TYPECAST_ENGINE="fixed"; $env:TYPECAST_ENABLE_MODEL_PARSE="0"; $env:TYPECAST_ENABLE_VISION_RERANK="0"; $env:LANGSMITH_TRACING="false"; .\.venv\Scripts\python -m uvicorn agent.app:app --host 127.0.0.1 --port 8000`
4. `cd bridge; npm install --no-package-lock; cd ..; node bridge/watch-beta.mjs`. It prints `Ready: ...` after its first successful poll.
5. From the allowlisted identity, start a new direct iMessage (not SMS) to the assigned number, after it prints Ready.

## Verification so far
- Bridge tests: 43 pass (6 existing in `core.test.mjs`, 15 intake, 22 `watch-beta`). Web node tests: 29 pass (24 existing, 5 new).
- The example conversation, a re-rank, "start over" and a detailed first message were run through `handleMessage` against the real mock API (no fakes): three questions, then one `/scout` call with the exact target scene string.
- `watch-beta.mjs` was started against the Photon Beta project in mock mode: it authenticated, completed its first poll and kept polling.
- **On a real iPhone (mock data only), passed:** the example conversation, an immediate `INT.` search, and "start over". Real inbound messages matched the fields the sender filter reads, and the replies arrived.
- Not verified: the "See them in 3D" link on a phone, images, a non-allowlisted sender getting no reply, no double answers across a restart, and the idempotency-key and text-length limits (the tests did not reach them).

## Real-phone checklist
- [x] The example conversation end to end: "need a cop station for a night interrogation scene", "LA", "80s, kinda grimy", "3 trucks 30 cars". Passed.
- [x] One detailed first message that searches immediately (`INT.` form). Passed.
- [x] "start over". Passed.
- [ ] Tap the "See them in 3D" link from the text (needs `PHOTON_VIEWER_URL` set to an address the phone can reach): the site should open and start the search live. Not tested.
- [ ] A text from a number that is not on the allowlist gets no reply. Not tested.
- [ ] No message is answered twice, including after a restart. Not tested.
- [ ] Screenshots to `cache/screens/photon/`. Not recorded here.
- If a reply does not arrive, check the conversation and API Activities in the Photon dashboard; the runner only knows a send was accepted.
- A message starting `INT.` or `EXT.` searches directly with no questions, so the original single-scene Stage 1 behaviour is still available through the same runner.

## Known limits
- The Beta guide calls polling "a bounded connection test, not a production inbox consumer" and recommends live events with replay cursors for long runs. This runner polls, as requested. It does not recover messages sent while it was stopped.
- `core.mjs` prints "1 trucks" when there is one truck space; not changed here.
- The intake knows about 30 kinds of place; an unknown one is taken from phrases like "need a ...", and a short reply to the setting question is used as the setting as typed.
- City is LA or Houston only. A skipped or unclear city leaves it out and the backend searches Los Angeles; the "Searching for" line says so.
