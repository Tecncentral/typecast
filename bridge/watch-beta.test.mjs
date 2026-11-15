import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { sessions } from "./core.mjs";
import {
  POLL_MS, MAX_TEXT, parseConfig, assertMockMode, acceptMessage, createSeen, createRunner, chunkText,
  describeError, retryAfterMs, nextBackoff, isApiError,
} from "./watch-beta.mjs";

const SENDER = "+15550100100";
const AGENT = "+15550100188";
const SECRET = "KEY-SECRET-VALUE";
const PROJECT = "proj-secret-id";
const TEXT = "need a cop station for a night interrogation scene";
const ENV = { PHOTON_PROJECT_ID: PROJECT, PHOTON_PROJECT_SECRET: SECRET, PHOTON_AGENT_HANDLE: AGENT, PHOTON_ALLOWED_SENDERS: `${SENDER}, someone@example.com` };
const cfg = parseConfig(ENV);
const MOCK_PICKS = JSON.parse(readFileSync(new URL("../mocks/pick.json", import.meta.url), "utf8"));
const T0 = Date.parse("2026-11-15T10:00:00Z");

function msg(id, over = {}) {
  return {
    id, platform: "imessage", status: "received", createdAt: new Date(T0 + 1000).toISOString(),
    space: { platform: "imessage", kind: "direct", id: "space-1234" },
    sentBy: { platform: "imessage", kind: "human", handle: SENDER, id: "user-human" },
    receivedBy: { platform: "imessage", kind: "agent", handle: AGENT, id: "user-agent" },
    content: { type: "text", format: "plain", text: TEXT },
    ...over,
  };
}
class FakeApiError extends Error {
  constructor(status, requestId = "req-1", retryAfter) {
    super(`provider body mentioning ${PROJECT} and ${SENDER}`);
    this.name = "ApiError"; this.status = status; this.requestId = requestId;
    this.headers = new Headers(retryAfter ? { "retry-after": String(retryAfter) } : {});
  }
}
/** pages: array of arrays of messages, or functions that return/throw per poll. */
function fakePhoton(polls) {
  const calls = { list: [], send: [] };
  let i = 0;
  return {
    calls,
    projects: {
      async listMessages(input) {
        calls.list.push(input);
        const step = polls[Math.min(i++, polls.length - 1)];
        const out = typeof step === "function" ? step() : step;
        return { items: out, nextPageToken: undefined };
      },
      async sendMessage(input) {
        calls.send.push(input);
        if (calls.failSend) { const e = calls.failSend.shift(); if (e) throw e; }
        return { id: `sent-${calls.send.length}` };
      },
    },
  };
}
function harness(polls, over = {}) {
  const photon = fakePhoton(polls);
  const logs = [], errors = [], waits = [];
  const runner = createRunner({
    photon, cfg, now: () => T0, wait: async (ms) => { waits.push(ms); }, mergeWait: async () => {},
    log: (l) => logs.push(l), logError: (l) => errors.push(l), env: {}, ...over,
  });
  return { photon, logs, errors, waits, runner };
}
const texts = (photon) => photon.calls.send.map((c) => c.body.content.text);
const stopAfter = (n) => { let k = 0; return () => k++ >= n; };

// --- sender filter -------------------------------------------------------------------------------------------
test("a plain text direct message from an allowlisted human to the agent number is accepted", () => {
  const a = acceptMessage(msg("m1"), cfg, T0);
  assert.deepEqual(a, { ok: true, id: "m1", spaceId: "space-1234", senderId: "user-agent", text: TEXT });
});

test("the sender is matched by digits, and emails by lower case", () => {
  for (const handle of ["+1 (555) 010-0100", "5550100100", "1-555-010-0100", "+15550100100"]) {
    assert.equal(acceptMessage(msg("m", { sentBy: { platform: "imessage", kind: "human", handle, id: "u" } }), cfg, T0).ok, true, handle);
  }
  assert.equal(acceptMessage(msg("m", { sentBy: { platform: "imessage", kind: "human", handle: "Someone@Example.com", id: "u" } }), cfg, T0).ok, true);
});

test("everything else is rejected: other senders, non-humans, groups, other agents, own messages, old ones, non-text", () => {
  const reject = (over, reason) => {
    const r = acceptMessage(msg("m", over), cfg, T0);
    assert.equal(r.ok, false); assert.equal(r.reason, reason);
  };
  reject({ sentBy: { platform: "imessage", kind: "human", handle: "+15550100999", id: "u" } }, "sender_not_allowed");
  reject({ sentBy: { platform: "imessage", kind: "human", handle: "", id: "u" } }, "sender_not_allowed");
  reject({ sentBy: { platform: "imessage", kind: "human" , id: "u" } }, "sender_not_allowed");
  reject({ sentBy: { platform: "imessage", kind: "agent", handle: SENDER, id: "u" } }, "not_human");
  reject({ sentBy: { platform: "imessage", kind: "system", handle: SENDER, id: "u" } }, "not_human");
  reject({ sentBy: { platform: "email", kind: "human", handle: SENDER, id: "u" } }, "not_human");
  reject({ space: { platform: "imessage", kind: "group", id: "g" } }, "not_direct");
  reject({ space: { platform: "email", kind: "direct", id: "g" } }, "not_direct");
  reject({ receivedBy: { platform: "imessage", kind: "agent", handle: "+15550100777", id: "a" } }, "wrong_agent");
  reject({ receivedBy: { platform: "imessage", kind: "human", handle: AGENT, id: "a" } }, "wrong_agent");
  reject({ receivedBy: undefined }, "wrong_agent");
  reject({ receivedBy: { platform: "imessage", kind: "agent", handle: AGENT, id: "user-human" } }, "own_message");
  reject({ platform: "email" }, "not_received_imessage");
  reject({ status: "sent" }, "not_received_imessage");
  reject({ createdAt: new Date(T0 - 60_000).toISOString() }, "too_old");
  reject({ createdAt: undefined }, "too_old");
  reject({ content: { type: "image", url: "x" } }, "not_text");
  reject({ content: { type: "text", format: "html", text: TEXT } }, "not_text");
  reject({ content: { type: "text", format: "plain", text: "   " } }, "not_text");
  reject({ id: "" }, "incomplete");
  assert.equal(acceptMessage(undefined, cfg, T0).ok, false);
  assert.equal(acceptMessage(null, cfg, T0).ok, false);
});

test("rejected messages get no reply and are only counted", async () => {
  const { photon, runner, logs } = harness([[
    msg("a", { sentBy: { platform: "imessage", kind: "human", handle: "+15550100999", id: "u" } }),
    msg("b", { space: { platform: "imessage", kind: "group", id: "g" } }),
    msg("c", { content: { type: "image", url: "x" } }),
  ]]);
  await runner.pollOnce(); await runner.idle();
  assert.equal(photon.calls.send.length, 0);
  assert.equal(runner.stats.ignored, 3);
  assert.deepEqual(logs, ["ignored 3 message(s) that did not pass the sender, agent or text checks"]);
});

// --- duplicate guard -----------------------------------------------------------------------------------------
test("a message seen again on a later poll, or twice on one page, is answered once", async () => {
  const same = msg("dup");
  const { photon, runner } = harness([[same, same], [same], [same]]);
  await runner.pollOnce(); await runner.pollOnce(); await runner.pollOnce(); await runner.idle();
  assert.equal(photon.calls.send.length, 1);
  assert.equal(runner.stats.answered, 1);
});

test("a message is not retried after a failed send, so it can never be answered twice", async () => {
  const same = msg("flaky");
  const { photon, runner, errors } = harness([[same], [same]]);
  photon.calls.failSend = [new FakeApiError(500, "req-9")];
  await runner.pollOnce(); await runner.idle();
  const afterFailure = photon.calls.send.length;
  await runner.pollOnce(); await runner.idle();
  assert.equal(photon.calls.send.length, afterFailure);
  assert.deepEqual(errors, ["Photon API error 500 (request req-9)."]);
});

test("the seen set is bounded", () => {
  const seen = createSeen(3);
  for (const id of ["a", "b", "c", "d"]) seen.add(id);
  assert.equal(seen.has("a"), false); assert.equal(seen.has("d"), true);
});

// --- text in, text out ---------------------------------------------------------------------------------------
test("text goes to handleMessage under the space id and every reply is plain text sent as a reply", async () => {
  const seen = [];
  const handle = async (key, text, ctx) => {
    seen.push([key, text]);
    await ctx.say("Searching for: INT. OFFICE.");
    return [{ text: "MOCK · fixed engine" }, { image: "http://localhost:8000/mocks/img/x.jpg" }, { text: "1. 100 Test St\nShot fits." }, { text: "" }];
  };
  const { photon, runner } = harness([[msg("m-1")]], { handle });
  await runner.pollOnce(); await runner.idle();
  assert.deepEqual(seen, [["space-1234", TEXT]]);
  assert.deepEqual(texts(photon), ["Searching for: INT. OFFICE.", "MOCK · fixed engine", "1. 100 Test St\nShot fits."]);
  for (const [n, call] of photon.calls.send.entries()) {
    assert.deepEqual(call.path, { id: PROJECT });
    assert.deepEqual(call.headers, { "idempotency-key": `typecast-reply:m-1:${n}` });
    assert.deepEqual(Object.keys(call.body).sort(), ["content", "parentMessageId", "senderId", "spaceId"]);
    assert.equal(call.body.spaceId, "space-1234"); assert.equal(call.body.senderId, "user-agent"); assert.equal(call.body.parentMessageId, "m-1");
    assert.deepEqual(Object.keys(call.body.content).sort(), ["format", "text", "type"]);
    assert.equal(call.body.content.type, "text"); assert.equal(call.body.content.format, "plain");
  }
});

test("the real intake answers the first message with its first question, as plain text", async () => {
  sessions.clear();
  const { photon, runner } = harness([[msg("m-2")]]);
  await runner.pollOnce(); await runner.idle();
  assert.deepEqual(texts(photon), ["Got it: police station, night. LA or Houston?"]);
  assert.ok(sessions.get("space-1234").v2.st, "the intake state lives under the space id");
});

test("a whole conversation through the real intake: three questions, one search, text only", async () => {
  sessions.clear();
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push([new URL(url).pathname, JSON.parse(init.body)]);
    return { ok: true, json: async () => ({ thread_id: "t1", picks: MOCK_PICKS, gave_up: [], source_mode: "mock", engine: "fixed" }), text: async () => "" };
  };
  const turns = ["LA", "80s, kinda grimy", "3 trucks 30 cars"].map((t, i) => msg(`m-${i + 3}`, { content: { type: "text", format: "plain", text: t } }));
  const { photon, runner } = harness([[msg("m-first")], turns.slice(0, 1), turns.slice(1, 2), turns.slice(2)], { fetchImpl });
  for (let i = 0; i < 4; i++) { await runner.pollOnce(); await runner.idle(); }
  assert.deepEqual(calls, [["/scout", { scene: "INT. 1980s POLICE STATION, NIGHT. Los Angeles. Gritty. Parking for 3 trucks and 30 crew cars." }]]);
  const sent = texts(photon);
  assert.equal(sent[0], "Got it: police station, night. LA or Houston?");
  assert.match(sent[1], /^Need an exterior too/);
  assert.equal(sent[2], 'How many trucks and crew cars? Or "skip".');
  assert.match(sent[3], /^Searching now \(MOCK\)\.\nInterior: INT\. 1980s POLICE STATION/);
  assert.ok(sent.some((t) => /^MOCK · 3 interior picks\n1\. /.test(t)) && sent.some((t) => /\n3\. /.test(t)));
  assert.ok(photon.calls.send.every((c) => c.body.content.type === "text"), "no images are sent");
  assert.ok(!sent.some((t) => /localhost:8000\/mocks\/img/.test(t)), "no image links either");
});

test("long replies are split into chunks of at most 1500 characters, in order", () => {
  const long = `${"a".repeat(1000)}\n${"b".repeat(1000)}\n${"c".repeat(3200)}`;
  const chunks = chunkText(long);
  assert.ok(chunks.every((c) => c.length <= MAX_TEXT));
  assert.equal(chunks.join("\n").replace(/\n/g, ""), long.replace(/\n/g, ""));
  assert.deepEqual(chunkText("short"), ["short"]);
  assert.deepEqual(chunkText(""), []);
});

// --- polling, rate limits, errors ---------------------------------------------------------------------------
test("each poll asks for received iMessages, oldest first, 100 per page, and waits 2 seconds between polls", async () => {
  const { photon, runner, waits, logs } = harness([[], [], []]);
  const code = await runner.run({ shouldStop: stopAfter(3) });
  assert.equal(code, 0);
  assert.deepEqual(waits, [POLL_MS, POLL_MS, POLL_MS]); assert.equal(POLL_MS, 2000);
  const q = photon.calls.list[0];
  assert.deepEqual(q.path, { id: PROJECT });
  assert.deepEqual(Object.keys(q.query).sort(), ["createdSince", "direction", "order", "pageSize", "platform"]);
  assert.equal(q.query.direction, "received"); assert.equal(q.query.order, "asc");
  assert.equal(q.query.pageSize, 100); assert.equal(q.query.platform, "imessage");
  assert.equal(q.query.createdSince, new Date(T0 - 5000).toISOString());
  assert.deepEqual(logs, ["Ready: Photon Beta, polling every 2 s, mock mode, 2 allowlisted sender(s)."]);
});

test("pages are followed with nextPageToken", async () => {
  const other = { platform: "imessage", kind: "direct", id: "space-other" };
  const pages = [{ items: [msg("p1")], nextPageToken: "tok" }, { items: [msg("p2", { space: other })], nextPageToken: undefined }];
  const queries = [];
  const photon = { calls: { send: [] }, projects: {
    listMessages: async (i) => { queries.push(i.query); return pages.shift(); },
    sendMessage: async (i) => { photon.calls.send.push(i); return {}; },
  } };
  const runner = createRunner({ photon, cfg, now: () => T0, wait: async () => {}, log: () => {}, logError: () => {}, handle: async () => [{ text: "ok" }] });
  await runner.pollOnce(); await runner.idle();
  assert.equal(queries[1].pageToken, "tok"); assert.equal(queries[0].pageToken, undefined);
  assert.equal(photon.calls.send.length, 2);
});

test("429 waits for Retry-After, backs off further on repeats, never polls faster, and resumes", async () => {
  const limited = (retry) => () => { throw new FakeApiError(429, "req-429", retry); };
  const { runner, waits, errors, logs } = harness([limited(90), limited(), limited(), []]);
  const code = await runner.run({ shouldStop: stopAfter(5) });
  assert.equal(code, 0);
  assert.deepEqual(waits.slice(0, 3), [90_000, 10_000, 20_000]);
  assert.ok(waits.every((ms) => ms >= POLL_MS), "never faster than every 2 seconds");
  assert.equal(waits[3], POLL_MS, "back to the normal pace after a good poll");
  assert.deepEqual(errors, ["Photon API error 429 (request req-429)."].concat(Array(2).fill("Photon API error 429 (request req-429).")));
  assert.equal(logs.length, 1);
});

test("a 429 while sending is retried later with the same idempotency key", async () => {
  const { photon, runner, waits } = harness([[msg("m-429")]], { handle: async () => [{ text: "hello" }] });
  photon.calls.failSend = [new FakeApiError(429, "req-s", 7)];
  await runner.pollOnce(); await runner.idle();
  assert.equal(photon.calls.send.length, 2);
  assert.equal(photon.calls.send[0].headers["idempotency-key"], photon.calls.send[1].headers["idempotency-key"]);
  assert.deepEqual(waits, [7000]);
});

test("auth and validation errors stop the runner with only the status and request id printed", async () => {
  for (const status of [400, 401, 403, 404, 422]) {
    const { runner, errors, waits } = harness([() => { throw new FakeApiError(status, "req-fatal"); }]);
    assert.equal(await runner.run({ shouldStop: stopAfter(5) }), 1);
    assert.deepEqual(errors, [`Photon API error ${status} (request req-fatal).`]);
    assert.deepEqual(waits, []);
  }
});

test("server errors and network failures are retried with a growing wait and no details printed", async () => {
  const net = Object.assign(new Error(`connect failed to host with ${SECRET}`), { name: "TransportError" });
  const { runner, errors, waits } = harness([() => { throw new FakeApiError(503); }, () => { throw net; }, []]);
  assert.equal(await runner.run({ shouldStop: stopAfter(4) }), 0);
  assert.deepEqual(errors, ["Photon API error 503 (request req-1).", "Request failed (TransportError)."]);
  assert.deepEqual(waits.slice(0, 2), [5000, 10_000]);
});

test("helpers: retry-after parsing, backoff and error text", () => {
  assert.equal(retryAfterMs(new FakeApiError(429, "r", 5)), 5000);
  assert.equal(retryAfterMs(new FakeApiError(429, "r", "0")), 1000);
  assert.equal(retryAfterMs(new FakeApiError(429, "r", 99999)), 120_000);
  assert.equal(retryAfterMs(new FakeApiError(429)), null);
  assert.equal(retryAfterMs({ headers: new Headers({ "retry-after": new Date(T0 + 30_000).toUTCString() }) }, T0), 30_000);
  assert.deepEqual([nextBackoff(0), nextBackoff(5000), nextBackoff(100_000)], [5000, 10_000, 120_000]);
  assert.equal(isApiError(new FakeApiError(500)), true); assert.equal(isApiError(new Error("x")), false);
  assert.equal(describeError({ status: 500, headers: new Headers() }), "Photon API error 500 (request unknown).");
});

test("nothing printed contains a key, project id, phone number, space id, message id or message text", async () => {
  sessions.clear();
  const { runner, logs, errors } = harness([[msg("secret-msg-id"), msg("other", { sentBy: { platform: "imessage", kind: "human", handle: "+15550100999", id: "u" } })], () => { throw new FakeApiError(429, "req-x"); }, []]);
  await runner.run({ shouldStop: stopAfter(3) });
  const output = [...logs, ...errors].join("\n");
  for (const secret of [SECRET, PROJECT, "5550100100", "5550100188", "5550100999", "space-1234", "secret-msg-id", "cop station", "someone@example.com"]) {
    assert.ok(!output.includes(secret), `output must not contain ${secret}`);
  }
});

// --- startup guards ------------------------------------------------------------------------------------------
test("config names the missing variable only, and needs one agent number and at least one sender", () => {
  for (const name of Object.keys(ENV)) {
    const env = { ...ENV, [name]: "" };
    assert.throws(() => parseConfig(env), (e) => e.message === `${name} is not set`);
  }
  assert.throws(() => parseConfig({ ...ENV, PHOTON_ALLOWED_SENDERS: " , ; " }), /no usable sender/);
  assert.throws(() => parseConfig({ ...ENV, PHOTON_AGENT_HANDLE: "+15550100188,+15550100189" }), /exactly one number/);
  assert.equal(parseConfig(ENV).key, SECRET);
});

test("it refuses to start unless the API is in mock mode with every source mock", async () => {
  const health = (body) => async () => ({ json: async () => body });
  await assertMockMode("http://x", health({ mocks: true, source_modes: { costar: "mock", matterport: "mock", vexcel: "mock" } }));
  for (const body of [{ mocks: false, source_modes: { costar: "mock" } }, { mocks: true, source_modes: { costar: "live", vexcel: "mock" } }, { mocks: true }, {}]) {
    await assert.rejects(assertMockMode("http://x", health(body)), /not in mock mode/);
  }
  await assert.rejects(assertMockMode("http://x", async () => { throw new Error("down"); }), /cannot reach the API health check/);
});

test("the runner uses the documented SDK pattern and imports only what it needs", () => {
  const source = readFileSync(new URL("./watch-beta.mjs", import.meta.url), "utf8");
  assert.match(source, /import\("@photon-ai\/api"\)/);
  assert.match(source, /Authorization: `Bearer \$\{cfg\.key\}`/);
  assert.match(source, /photon\.projects\.listMessages/); assert.match(source, /photon\.projects\.sendMessage/);
  assert.match(source, /"idempotency-key"/);
  assert.deepEqual([...source.matchAll(/^import .* from "(.+)";$/gm)].map((m) => m[1]).sort(), ["./conversations.mjs", "./intake.mjs", "./scout-v2.mjs", "node:path", "node:timers/promises", "node:url"]);
});
