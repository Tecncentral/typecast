#!/usr/bin/env node
// Photon line (iMessage and others) through spectrum-ts.
// UNVERIFIED: written from the spectrum-ts 12.16.0 README and type files; it has not been run
// against a live Photon project. Check the inbound text extraction (textOf) on the first real message.
//   npm install            (in bridge/)
//   PHOTON_PROJECT_ID=... PHOTON_PROJECT_SECRET=... node bridge/photon.mjs
import { Spectrum, attachment } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";
import { handle } from "./core.mjs";

function textOf(message) {
  const c = message.content;
  if (typeof c === "string") return c;
  if (c && typeof c.text === "string") return c.text;
  if (Array.isArray(c)) return c.map((x) => x?.text).filter(Boolean).join(" ");
  console.warn("Unrecognised inbound content shape; no message content was logged.");
  return "";
}

const app = await Spectrum({
  projectId: process.env.PHOTON_PROJECT_ID,
  projectSecret: process.env.PHOTON_PROJECT_SECRET,
  providers: [imessage.config()],
  signal: AbortSignal.timeout(20_000),
});
console.log("Typecast is listening on Photon.");

for await (const [space, message] of app.messages) {
  if (message.direction !== "inbound") continue;
  const key = space.id ?? message.id;
  // Not awaited: one slow scene must not block other conversations.
  space.responding(async () => {
    const parts = await handle(key, textOf(message), { say: (t) => message.reply(t) });
    for (const p of parts) {
      try { await space.send(p.image ? attachment(p.image) : p.text); }
      catch (e) { console.error("send failed:", e?.message); if (p.image) await space.send(p.image).catch(() => {}); }
    }
  }).catch((e) => console.error("handler failed:", e));
}
