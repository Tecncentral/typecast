#!/usr/bin/env node
// Local simulator: runs the SAME runner as watch-beta.mjs (allowlist, message filter, merge window, intake,
// formatting, ordering, send retry) against a fake Photon client that sends nothing. Every outbound bubble is
// printed with a counter. Mock data only; synthetic phone numbers.
//   node bridge/sim.mjs                                   interactive
//   node bridge/sim.mjs --script bridge/fixtures/x.txt    scripted
// Script lines: plain text = a message from the allowlisted sender; "#" comment;
//   @other text    from a sender who is not on the allowlist     @photo          a photo (attachment)
//   @tapback       a reaction                                     @dup            re-deliver the previous message id
//   @burst a | b   two messages in the same poll (rapid double-send)
//   @fail N        the next N sends fail                          @nomatch        the next search finds nothing
//   @failresults   every results bubble fails to send (to test the fallback line)
//   Alerts (createSim({ alerts: true }) or --alerts): @advance MIN moves the clock and runs the watcher, @maxrent N, @rent RANK N, @real (PHOTON_ALERTS_REAL=1)
//   @viewer URL    set PHOTON_VIEWER_URL for this run
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import readline from "node:readline";
import { createRunner, parseConfig } from "./watch-beta.mjs";
import { sessions } from "./core.mjs";
import { BUDGET } from "./conversations.mjs";
import { openStore } from "./store.mjs";
import { createAlerts } from "./alerts.mjs";

export const SIM_SENDER = "+15550100100";
export const SIM_OTHER = "+15550100999";
export const SIM_AGENT = "+15550100188";
const MOCK_PICKS = JSON.parse(readFileSync(new URL("../mocks/pick.json", import.meta.url), "utf8"));

/** A stand-in for the backend that serves mocks/pick.json, so the simulator needs no API running. */
export function mockBackend(sim) {
  return async (url, init) => {
    const path = new URL(url).pathname;
    const body = init?.body ? JSON.parse(init.body) : {};
    sim.calls.push({ path, body });
    const ok = (json) => ({ ok: true, status: 200, json: async () => json, text: async () => "" });
    if (path === "/scout" || path === "/refine") {
      const none = sim.flags.nomatch && path === "/scout";
      sim.flags.nomatch = false;
      if (path === "/scout") sim.scouts = (sim.scouts ?? 0) + 1;
      return ok({ thread_id: sim.scouts > 1 ? `sim-thread-${sim.scouts}` : "sim-thread", picks: none ? [] : MOCK_PICKS, gave_up: none ? ["era", "parking"] : [], source_mode: "mock", engine: "fixed" });
    }
    if (path === "/approve") return ok({ sent: false });
    return { ok: false, status: 404, json: async () => ({}), text: async () => "" };
  };
}

export function createSim({ env = {}, print = () => {}, fetchImpl, alerts: withAlerts = false, rentSource } = {}) {
  sessions.clear();
  const sim = { calls: [], outbound: [], flags: { nomatch: false }, failures: 0, failTexts: null, inbox: [], printed: [] };
  const cfg = parseConfig({ PHOTON_PROJECT_ID: "sim-project", PHOTON_PROJECT_SECRET: "sim-secret", PHOTON_AGENT_HANDLE: SIM_AGENT, PHOTON_ALLOWED_SENDERS: SIM_SENDER });
  let clock = Date.parse("2026-11-15T12:00:00Z"), nextId = 1;
  const emit = (line) => { sim.printed.push(line); print(line); };

  const photon = { projects: {
    listMessages: async () => ({ items: [...sim.inbox], nextPageToken: undefined }),
    sendMessage: async (input) => {
      if (sim.failures > 0) { sim.failures -= 1; throw Object.assign(new Error("simulated failure"), { name: "ApiError", status: 500, requestId: "sim", headers: new Headers() }); }
      const text = input.body.content.text;
      if (sim.failTexts?.test(text)) throw Object.assign(new Error("simulated failure"), { name: "ApiError", status: 500, requestId: "sim", headers: new Headers() });
      sim.outbound.push({ n: sim.outbound.length + 1, text, key: input.headers["idempotency-key"], type: input.body.content.type });
      emit(`  bot #${sim.outbound.length}: ${text.replace(/\n/g, "\n          ")}`);
      return { id: `sent-${sim.outbound.length}` };
    },
  } };
  // Optional alerts: an in-memory store and a fake clock, so reminders and price checks run offline.
  const store = withAlerts ? openStore(":memory:") : null;
  const alerts = withAlerts ? createAlerts({ store, allowed: cfg.allowed, env, now: () => clock, log: (l) => emit(`  [alerts] ${l}`), ...(rentSource ? { rentSource } : {}) }) : null;
  const runner = createRunner({
    alerts, photon, cfg, now: () => clock, wait: async () => {}, log: (l) => emit(`  [runner] ${l}`), logError: (l) => emit(`  [runner error] ${l}`),
    env, fetchImpl: fetchImpl ?? mockBackend(sim),
  });

  function build(content, { sender = SIM_SENDER, id } = {}) {
    clock += 1000;
    return {
      id: id ?? `sim-msg-${nextId++}`, platform: "imessage", status: "received", createdAt: new Date(clock).toISOString(),
      space: { platform: "imessage", kind: "direct", id: `sim-space-${sender === SIM_SENDER ? 1 : 2}` },
      sentBy: { platform: "imessage", kind: "human", handle: sender, id: "sim-human" },
      receivedBy: { platform: "imessage", kind: "agent", handle: SIM_AGENT, id: "sim-agent" },
      content,
    };
  }
  const text = (t, opts) => build({ type: "text", format: "plain", text: t }, opts);
  sim.step = async () => { await runner.pollOnce(); await runner.idle(); };
  sim.push = (...messages) => { sim.inbox.push(...messages); };
  sim.say = async (t) => { emit(`you: ${t}`); sim.push(text(t)); await sim.step(); };
  sim.other = async (t) => { emit(`stranger: ${t}`); sim.push(text(t, { sender: SIM_OTHER })); await sim.step(); };
  sim.photo = async () => { emit("you: [photo]"); sim.push(build({ type: "attachment", attachmentId: "sim-attachment" })); await sim.step(); };
  sim.tapback = async () => { emit("you: [tapback]"); sim.push(build({ type: "reaction", action: "added", reaction: "love" })); await sim.step(); };
  sim.dup = async () => { const last = sim.inbox[sim.inbox.length - 1]; emit("you: [same message delivered again]"); sim.push({ ...last }); await sim.step(); };
  sim.burst = async (...texts) => { for (const t of texts) emit(`you (rapid): ${t}`); sim.push(...texts.map((t) => text(t))); await sim.step(); };
  sim.failNext = (n) => { sim.failures = n; };
  sim.advance = async (minutes) => { clock += minutes * 60_000; emit(`  [clock] +${minutes} min`); return runner.alertTick(); };
  sim.setMaxRent = (maxRent, rentUnits = null) => store.setMaxRent(store.db.prepare("SELECT MAX(id) AS id FROM searches").get().id, { maxRent, rentUnits });
  sim.setRent = (rank, rentRef) => store.db.prepare("UPDATE picks SET rent_ref = ? WHERE rank = ? AND search_id = (SELECT MAX(id) FROM searches)").run(rentRef, rank);
  sim.runner = runner; sim.env = env; sim.cfg = cfg; sim.store = store; sim.alerts = alerts;
  return sim;
}

/** Run script lines against a sim. Returns the sim. */
export async function runScript(sim, lines) {
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const [, cmd, arg = ""] = line.match(/^@(\w+)\s*(.*)$/) ?? [];
    if (!cmd) await sim.say(line);
    else if (cmd === "other") await sim.other(arg);
    else if (cmd === "photo") await sim.photo();
    else if (cmd === "tapback") await sim.tapback();
    else if (cmd === "dup") await sim.dup();
    else if (cmd === "burst") await sim.burst(...arg.split("|").map((t) => t.trim()).filter(Boolean));
    else if (cmd === "fail") sim.failNext(Number(arg) || 1);
    else if (cmd === "nomatch") sim.flags.nomatch = true;
    else if (cmd === "failresults") sim.failTexts = /^MOCK ·/;
    else if (cmd === "advance") await sim.advance(Number(arg));
    else if (cmd === "maxrent") sim.setMaxRent(Number(arg));
    else if (cmd === "rent") { const [rank, value] = arg.split(/\s+/).map(Number); sim.setRent(rank, value); }
    else if (cmd === "real") sim.env.PHOTON_ALERTS_REAL = "1";
    else if (cmd === "viewer") sim.env.PHOTON_VIEWER_URL = arg.trim();
    else throw new Error(`unknown script command @${cmd}`);
  }
  return sim;
}

async function main() {
  const argv = process.argv.slice(2);
  const scriptAt = argv.indexOf("--script");
  const sim = createSim({ env: { PHOTON_VIEWER_URL: process.env.PHOTON_VIEWER_URL ?? "" }, print: console.log, alerts: argv.includes("--alerts") });
  console.log(`Simulator: nothing is sent to Photon. Mock data only. Budget ${BUDGET} outbound messages per search.`);
  if (scriptAt >= 0) {
    await runScript(sim, readFileSync(argv[scriptAt + 1], "utf8").split(/\r?\n/));
    console.log(`\n${sim.outbound.length} outbound message(s) in total; ${sim.calls.filter((c) => c.path === "/scout").length} /scout call(s).`);
    return;
  }
  console.log("Type a message and press Enter. Commands: @other text, @photo, @tapback, @dup, @burst a | b, @fail N, @nomatch, @viewer URL. Ctrl+C to stop.");
  const rl = readline.createInterface({ input: process.stdin });
  for await (const line of rl) await runScript(sim, [line]);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
