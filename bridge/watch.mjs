#!/usr/bin/env node
// Photon iMessage line with the conversational intake (Stage 1). MOCK MODE ONLY.
//   cd bridge && npm install        (once)
//   node bridge/watch.mjs           (the API must be running in mock mode: TYPECAST_USE_MOCKS=1)
// Reads PHOTON_PROJECT_ID, PHOTON_PROJECT_SECRET, PHOTON_ALLOWED_SENDERS and PHOTON_VIEWER_URL from .env.
// Values are never printed or logged. Texts from any sender not in PHOTON_ALLOWED_SENDERS are ignored.
// UNVERIFIED on a real phone: the Photon wiring follows spectrum-ts 12.16.0 types, as photon.mjs does.
import { fileURLToPath } from "node:url";
import path from "node:path";
import { existsSync } from "node:fs";
import { handleMessage, parseAllowed, isAllowed } from "./intake.mjs";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
try { process.loadEnvFile(path.join(REPO, ".env")); } catch { /* no .env: the variables may come from the shell */ }

const API = process.env.TYPECAST_API || "http://localhost:8000";

function fail(message) { console.error(`watch: ${message}`); process.exit(1); }

for (const name of ["PHOTON_PROJECT_ID", "PHOTON_PROJECT_SECRET"]) {
  if (!process.env[name]) fail(`${name} is not set in .env`);
}
const allowed = parseAllowed(process.env.PHOTON_ALLOWED_SENDERS);
if (allowed.size === 0) fail("PHOTON_ALLOWED_SENDERS is empty, so every sender would be ignored");

// Mock mode only: no real CoStar or Vexcel data may go through Photon.
try {
  const health = await (await fetch(`${API}/health`, { signal: AbortSignal.timeout(8000) })).json();
  const modes = Object.values(health.source_modes || {});
  if (health.mocks !== true || modes.length === 0 || modes.some((m) => m !== "mock")) {
    fail("the API is not in mock mode (TYPECAST_USE_MOCKS=1 with every source 'mock'); refusing to start");
  }
} catch (e) {
  if (e?.name === "TypeError" || e?.name === "TimeoutError" || e?.name === "SyntaxError") fail(`cannot reach the API health check at ${new URL(API).origin}`);
  throw e;
}

const { Spectrum, attachment } = await import("spectrum-ts");
const { imessage } = await import("spectrum-ts/providers/imessage");

function textOf(message) {
  const c = message.content;
  if (typeof c === "string") return c;
  if (c && typeof c.text === "string") return c.text;
  if (Array.isArray(c)) return c.map((x) => x?.text).filter(Boolean).join(" ");
  return "";
}

/** message.sender is { id, ...extras } and may be undefined; the id is the canonical phone or email handle. */
const senderOf = (message) => message.sender?.id ?? message.sender?.address;

/** Only repo mock images are ever sent. A mock URL becomes the matching file under mocks/; anything else is dropped. */
function mockImagePath(url) {
  try {
    const p = new URL(url).pathname;
    if (!p.startsWith("/mocks/")) return null;
    const file = path.resolve(REPO, `.${p}`);
    return file.startsWith(path.join(REPO, "mocks") + path.sep) && existsSync(file) ? file : null;
  } catch { return null; }
}

const app = await Spectrum({
  projectId: process.env.PHOTON_PROJECT_ID,
  projectSecret: process.env.PHOTON_PROJECT_SECRET,
  providers: [imessage.config()],
  signal: AbortSignal.timeout(20_000),
});
console.log(`Typecast (mock mode) is listening on Photon for ${allowed.size} allowlisted sender(s).`);

let ignored = 0;
for await (const [space, message] of app.messages) {
  if (message.direction !== "inbound") continue;
  if (!isAllowed(senderOf(message), allowed)) {
    ignored += 1;
    if (ignored === 1 || ignored % 25 === 0) console.log(`ignored ${ignored} message(s) from senders not on the allowlist`);
    continue;
  }
  const key = space.id ?? message.id;
  // Not awaited: one slow search must not block other conversations.
  space.responding(async () => {
    const parts = await handleMessage(key, textOf(message), { say: (t) => message.reply(t) });
    for (const part of parts) {
      try {
        if (part.image) {
          const file = mockImagePath(part.image);
          if (file) await space.send(attachment(file));
        } else await space.send(part.text);
      } catch (e) { console.error("send failed:", e?.message); }
    }
  }).catch((e) => console.error("handler failed:", e?.message));
}
