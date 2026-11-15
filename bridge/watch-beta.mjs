#!/usr/bin/env node
// Photon BETA (2.0) iMessage line with the conversational intake. MOCK MODE ONLY.
// Follows https://photon.codes/docs/beta/get-started/imessage.md: @photon-ai/api, Bearer auth,
// projects.listMessages polling, projects.sendMessage with a stable idempotency key.
//   node bridge/watch-beta.mjs     (API running in mock mode; PHOTON_* in .env)
// Never prints a key, project id, phone number, space id or message text: errors show only
// the status and request id. Unverified on a real phone.
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import { setTimeout as sleep } from "node:timers/promises";
import { handleMessage, parseAllowed, isAllowed } from "./intake.mjs";

export const POLL_MS = 2000;
export const MAX_TEXT = 1500;
const BACKOFF_START_MS = 5000;
const BACKOFF_MAX_MS = 120_000;
const WINDOW_OVERLAP_MS = 60_000;
const SEEN_LIMIT = 10_000;
const FATAL_STATUSES = new Set([400, 401, 403, 404, 422]);

export function parseConfig(env = process.env) {
  for (const name of ["PHOTON_PROJECT_ID", "PHOTON_PROJECT_SECRET", "PHOTON_AGENT_HANDLE", "PHOTON_ALLOWED_SENDERS"]) {
    if (!env[name]) throw new Error(`${name} is not set`);
  }
  const allowed = parseAllowed(env.PHOTON_ALLOWED_SENDERS);
  if (allowed.size === 0) throw new Error("PHOTON_ALLOWED_SENDERS has no usable sender");
  const agent = parseAllowed(env.PHOTON_AGENT_HANDLE);
  if (agent.size !== 1) throw new Error("PHOTON_AGENT_HANDLE must be exactly one number");
  return { projectId: env.PHOTON_PROJECT_ID, key: env.PHOTON_PROJECT_SECRET, allowed, agent };
}

/** Mock only: no real CoStar or Vexcel data may go through Photon. */
export async function assertMockMode(api, fetchImpl = fetch) {
  let health;
  try { health = await (await fetchImpl(`${api}/health`, { signal: AbortSignal.timeout(8000) })).json(); }
  catch { throw new Error("cannot reach the API health check"); }
  const modes = Object.values(health?.source_modes ?? {});
  if (health?.mocks !== true || modes.length === 0 || modes.some((m) => m !== "mock")) {
    throw new Error("the API is not in mock mode (TYPECAST_USE_MOCKS=1 with every source 'mock'); refusing to start");
  }
}

/** A message we may answer: a plain text direct iMessage from an allowlisted human to our agent number. */
export function acceptMessage(m, cfg, startedAt = 0) {
  const no = (reason) => ({ ok: false, reason });
  if (m?.platform !== "imessage" || m.status !== "received") return no("not_received_imessage");
  if (m.space?.platform !== "imessage" || m.space?.kind !== "direct") return no("not_direct");
  if (m.sentBy?.platform !== "imessage" || m.sentBy?.kind !== "human") return no("not_human");
  if (!isAllowed(m.sentBy.handle, cfg.allowed)) return no("sender_not_allowed");
  if (m.receivedBy?.platform !== "imessage" || m.receivedBy?.kind !== "agent" || !isAllowed(m.receivedBy.handle, cfg.agent)) return no("wrong_agent");
  if (m.sentBy.id === m.receivedBy.id) return no("own_message");
  if (!(Date.parse(m.createdAt) >= startedAt)) return no("too_old");
  if (!m.id || !m.space.id || !m.receivedBy.id) return no("incomplete");
  const text = m.content?.type === "text" && m.content.format === "plain" ? String(m.content.text ?? "").trim() : "";
  if (!text) return no("not_text");
  return { ok: true, id: m.id, spaceId: m.space.id, senderId: m.receivedBy.id, text };
}

export function createSeen(limit = SEEN_LIMIT) {
  const ids = new Set();
  return {
    has: (id) => ids.has(id),
    add(id) { ids.add(id); if (ids.size > limit) ids.delete(ids.values().next().value); },
  };
}

export const isApiError = (e) => typeof e?.status === "number" && e?.headers != null;
/** Status and request id only; never the message, which can echo ids or secrets. */
export const describeError = (e) => isApiError(e)
  ? `Photon API error ${e.status} (request ${e.requestId ?? "unknown"}).`
  : `Request failed (${e?.name ?? "error"}).`;

export function retryAfterMs(e, now = Date.now()) {
  const h = e?.headers?.get?.("retry-after");
  if (!h) return null;
  const ms = /^\d+$/.test(h.trim()) ? Number(h) * 1000 : Date.parse(h) - now;
  return Number.isFinite(ms) ? Math.min(Math.max(ms, 1000), BACKOFF_MAX_MS) : null;
}
export const nextBackoff = (previous) => Math.min(previous ? previous * 2 : BACKOFF_START_MS, BACKOFF_MAX_MS);

export function chunkText(text, max = MAX_TEXT) {
  const chunks = [];
  let current = "";
  for (const line of String(text).split("\n")) {
    for (let rest = line; ; ) {
      const piece = rest.slice(0, max); rest = rest.slice(max);
      if (current && current.length + 1 + piece.length > max) { chunks.push(current); current = ""; }
      current = current ? `${current}\n${piece}` : piece;
      if (!rest) break;
      chunks.push(current); current = "";
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

export function createRunner({
  photon, cfg, handle = handleMessage, wait = sleep, now = Date.now,
  log = console.log, logError = console.error, env = process.env, fetchImpl,
}) {
  const startedAt = now();
  const seen = createSeen();
  const queues = new Map();
  const stats = { ignored: 0, answered: 0 };
  let newest = startedAt - 5000;

  async function sendText(m, n, text) {
    const headers = { "idempotency-key": `typecast-reply:${m.id}:${n}` };
    for (let attempt = 0; ; attempt++) {
      try {
        await photon.projects.sendMessage({
          path: { id: cfg.projectId }, headers,
          body: { spaceId: m.spaceId, senderId: m.senderId, parentMessageId: m.id, content: { type: "text", format: "plain", text } },
        });
        return true;
      } catch (e) {
        logError(describeError(e));
        if (e?.status === 429 && attempt < 3) { await wait(retryAfterMs(e, now()) ?? BACKOFF_START_MS * 2 ** attempt); continue; }
        return false;
      }
    }
  }

  async function answer(m) {
    let n = 0;
    const out = async (text) => { for (const piece of chunkText(text)) await sendText(m, n++, piece); };
    try {
      const parts = await handle(m.spaceId, m.text, { say: out, fetchImpl, env });
      for (const part of parts) if (part.text) await out(part.text);
      stats.answered += 1;
    } catch (e) { logError(describeError(e)); }
  }

  // One conversation at a time keeps its replies in order; different conversations run side by side.
  function enqueue(m) {
    const next = (queues.get(m.spaceId) ?? Promise.resolve()).then(() => answer(m));
    queues.set(m.spaceId, next);
  }

  async function pollOnce() {
    const createdSince = new Date(Math.max(startedAt - 5000, newest - WINDOW_OVERLAP_MS)).toISOString();
    const before = stats.ignored;
    let pageToken;
    do {
      const page = await photon.projects.listMessages({
        path: { id: cfg.projectId },
        query: { createdSince, direction: "received", order: "asc", pageSize: 100, platform: "imessage", ...(pageToken ? { pageToken } : {}) },
      });
      for (const raw of page.items) {
        const created = Date.parse(raw?.createdAt);
        if (created > newest) newest = created;
        if (!raw?.id || seen.has(raw.id)) continue;
        seen.add(raw.id);
        const accepted = acceptMessage(raw, cfg, startedAt);
        if (accepted.ok) enqueue(accepted); else stats.ignored += 1;
      }
      pageToken = page.nextPageToken;
    } while (pageToken);
    if (stats.ignored > before && (before === 0 || Math.floor(stats.ignored / 25) > Math.floor(before / 25))) {
      log(`ignored ${stats.ignored} message(s) that did not pass the sender, agent or text checks`);
    }
  }

  /** Poll every POLL_MS. A 429 or other transient error waits longer, never shorter. Returns an exit code. */
  async function run({ shouldStop = () => false } = {}) {
    let backoff = 0, ready = false;
    while (!shouldStop()) {
      try {
        await pollOnce();
        backoff = 0;
        if (!ready) { ready = true; log(`Ready: Photon Beta, polling every ${POLL_MS / 1000} s, mock mode, ${cfg.allowed.size} allowlisted sender(s).`); }
      } catch (e) {
        logError(describeError(e));
        if (isApiError(e) && FATAL_STATUSES.has(e.status)) return 1;
        backoff = nextBackoff(backoff);
        await wait(Math.max(backoff, retryAfterMs(e, now()) ?? 0));
        continue;
      }
      await wait(POLL_MS);
    }
    return 0;
  }

  return { pollOnce, run, stats, idle: () => Promise.all([...queues.values()]) };
}

async function main() {
  const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  try { process.loadEnvFile(path.join(repo, ".env")); } catch { /* the variables may come from the shell */ }
  const fail = (message) => { console.error(`watch-beta: ${message}`); process.exit(1); };
  let cfg;
  try { cfg = parseConfig(); } catch (e) { fail(e.message); }
  try { await assertMockMode(process.env.TYPECAST_API || "http://localhost:8000"); } catch (e) { fail(e.message); }
  const { Photon } = await import("@photon-ai/api");
  const photon = new Photon({ headers: { Authorization: `Bearer ${cfg.key}` } });
  let stop = false;
  process.on("SIGINT", () => { stop = true; });
  const runner = createRunner({ photon, cfg });
  process.exitCode = await runner.run({ shouldStop: () => stop });
  await runner.idle();
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
