// Golden transcripts: whole conversations run through bridge/sim.mjs, which drives the real runner
// (filter, merge window, intake, formatting, ordering, send retry) against a fake client. Offline, mock data only.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { createSim, runScript } from "./sim.mjs";
import { BUDGET, NON_TEXT_NOTICE, RESULTS_FAILED, createConversations } from "./conversations.mjs";
import { buildViewerLink, formatResults, parseBrief } from "./scout-v2.mjs";
import { acceptMessage, makeDryRunClient, parseConfig } from "./watch-beta.mjs";

const VIEWER = "http://192.0.2.10:8000";
const fixture = (name) => readFileSync(new URL(`./fixtures/${name}.txt`, import.meta.url), "utf8").split(/\r?\n/);
const newSim = (env = { PHOTON_VIEWER_URL: VIEWER }) => createSim({ env });
const texts = (sim) => sim.outbound.map((o) => o.text);
const scouts = (sim) => sim.calls.filter((c) => c.path === "/scout");
const QUESTION = /^(?:(?:Updated: .*\n)?(?:Got it: .*? )?(?:LA or Houston\?|Need an exterior too|How many trucks)|What kind of place|Okay, starting over)/;
const questions = (sim) => texts(sim).filter((t) => QUESTION.test(t));
const sentCounts = (sim) => sim.printed.map((l) => l.match(/conversation \d+: (\d+) of 8 outbound/)).filter(Boolean).map((m) => Number(m[1]));
const linkParams = (text) => new URL(text).searchParams;

/** Rules every flow must obey. */
function assertHouseRules(sim) {
  assert.ok(sentCounts(sim).every((n) => n <= BUDGET), `at most ${BUDGET} outbound per flow: ${sentCounts(sim)}`);
  assert.ok(sim.outbound.every((o) => o.type === "text" && o.text.length <= 1500), "plain text only, within the length limit");
  for (const t of texts(sim)) {
    assert.ok(!/blocked alternative/i.test(t), "no internal wording");
    assert.ok(!/delivered/i.test(t), "never claims delivery");
  }
  for (const t of texts(sim).filter((x) => /^MOCK · /.test(x))) assert.match(t, /^MOCK · /);
  assert.equal(new Set(sim.outbound.map((o) => o.key)).size, sim.outbound.length, "every send has its own idempotency key");
}

test("golden: the four-message cop-station example, in order, with the link alone and last", async () => {
  const sim = newSim();
  await runScript(sim, fixture("cop-station"));
  const out = texts(sim);
  assert.equal(out.length, 6);
  assert.equal(out[0], "Got it: police station, night. LA or Houston?");
  assert.match(out[1], /^Need an exterior too/);
  assert.equal(out[2], 'How many trucks and crew cars? Or "skip".');
  assert.equal(questions(sim).length, 3, "at most three questions");
  const scene = "INT. 1980s POLICE STATION, NIGHT. Los Angeles. Gritty. Parking for 3 trucks and 30 crew cars.";
  assert.equal(out[3], `Searching now (MOCK).\nInterior: ${scene}\nExterior: none\nCity: Los Angeles · Trucks: 3 · Crew cars: 30`);
  assert.deepEqual(scouts(sim).map((c) => c.body), [{ scene }], "the interior string exactly as echoed");
  assert.match(out[4], /^MOCK · 3 interior picks\n1\. 300 Placeholder Blvd \(FAKE\)\n.+\n2\. 100 Example St \(FAKE\)\n.+\n3\. 200 Sample Ave \(FAKE\)\n.+$/);
  assert.ok(out[4].split("\n").length <= 7, "header plus two lines per pick");
  assert.match(out[4], /\(est\.\)/);
  assert.match(out[5], /^http:\/\/192\.0\.2\.10:8000\/app\/\?scene=/);
  const q = linkParams(out[5]);
  assert.deepEqual([...q.keys()], ["scene", "city", "trucks", "cars", "autorun"]);
  assert.deepEqual([q.get("scene"), q.get("city"), q.get("trucks"), q.get("cars"), q.get("autorun")], [scene, "LA", "3", "30", "1"]);
  assertHouseRules(sim);
});

test("golden: an interior and exterior brief searches only the interior and never autoruns the exterior", async () => {
  const sim = newSim();
  await runScript(sim, fixture("interior-and-exterior"));
  const out = texts(sim);
  assert.equal(questions(sim).length, 0);
  assert.equal(out.length, 4);
  assert.match(out[0], /\nInterior: INT\. POLICE STATION, NIGHT\. Los Angeles\. Parking for 3 trucks and 30 crew cars\.\nExterior: EXT\. ALLEY, NIGHT\. Los Angeles\.\n/);
  assert.equal(scouts(sim).length, 1);
  assert.ok(!/ALLEY/.test(scouts(sim)[0].body.scene), "the exterior is not sent to /scout");
  assert.equal(sim.calls.length, 1, "no other backend call, so nothing billable ran");
  assert.equal(out[2], "Exterior search ready on the site: EXT. ALLEY, NIGHT. Los Angeles. (runs live when you open it).");
  const q = linkParams(out[3]);
  assert.equal(q.get("ext"), "EXT. ALLEY, NIGHT. Los Angeles.");
  assert.equal(q.get("autorun"), "1", "autorun applies to the free mock interior search only");
  assertHouseRules(sim);
});

test("golden: one detailed INT. message asks nothing and searches once", async () => {
  const sim = newSim();
  await runScript(sim, fixture("single-int"));
  assert.equal(questions(sim).length, 0);
  const scene = "INT. WAREHOUSE, DAY. Two couriers exchange a case. Parking for 2 trucks.";
  assert.deepEqual(scouts(sim).map((c) => c.body), [{ scene }]);
  assert.match(texts(sim)[0], /^Searching now \(MOCK\)\.\nInterior: INT\. WAREHOUSE/);
  assert.match(texts(sim)[0], /City: Los Angeles \(assumed\) · Trucks: 2 · Crew cars: not given/);
  assert.equal(texts(sim).length, 3);
  assertHouseRules(sim);
});

test("golden: corrections update a slot with a one-line note, during the intake and after results", async () => {
  const sim = newSim();
  await runScript(sim, ["need a diner for a night scene in LA", "actually Houston, make it day"]);
  assert.equal(texts(sim)[1], 'Updated: time of day → day, city → Houston.\nHow many trucks and crew cars? Or "skip".');
  await runScript(sim, ["skip"]);
  assert.equal(scouts(sim).length, 1);
  assert.equal(scouts(sim)[0].body.scene, "INT. DINER, DAY. Houston.");
  await runScript(sim, ["actually make it night"]);
  assert.equal(scouts(sim).length, 2, "a correction after results searches again");
  assert.equal(scouts(sim)[1].body.scene, "INT. DINER, NIGHT. Houston.");
  assert.match(texts(sim).find((t) => /^Updated: time of day → night\./.test(t)), /^Updated: time of day → night\.\nSearching now/);
  assertHouseRules(sim);
});

test("golden: start over resets the conversation, mid-intake and after results", async () => {
  const sim = newSim();
  await runScript(sim, ["need a cop station", "start over"]);
  assert.match(texts(sim)[1], /^Okay, starting over\. What kind of place do you need/);
  await runScript(sim, fixture("single-int"));
  await runScript(sim, ["start over"]);
  assert.match(texts(sim).at(-1), /^Okay, starting over\./);
  await runScript(sim, ["warehouse in Houston"]);
  assert.match(texts(sim).at(-1), /^Need an exterior too/, "the old brief is gone");
  assertHouseRules(sim);
});

test("golden: two messages in the same poll merge into one input and get one reply", async () => {
  const sim = newSim();
  await runScript(sim, ["@burst need a cop station in LA | at night, 80s"]);
  assert.equal(texts(sim).length, 1);
  assert.match(texts(sim)[0], /^Got it: 1980s, police station, night\. Need an exterior too/);
  assertHouseRules(sim);
});

test("golden: a message id delivered twice is answered once", async () => {
  const sim = newSim();
  await runScript(sim, ["need a cop station in LA", "@dup"]);
  assert.equal(texts(sim).length, 1);
});

test("golden: a photo gets one notice, tapbacks get nothing, and a later photo after text gets the notice again", async () => {
  const sim = newSim();
  await runScript(sim, ["@photo", "@photo", "@tapback"]);
  assert.deepEqual(texts(sim), [NON_TEXT_NOTICE]);
  assert.equal(NON_TEXT_NOTICE, "I can only read text for now: describe the scene in words.");
  assert.equal(sim.calls.length, 0);
  await runScript(sim, ["hi", "@photo"]);
  assert.equal(texts(sim).filter((t) => t === NON_TEXT_NOTICE).length, 2);
});

test("golden: no picks says what was relaxed in one line and still sends the link", async () => {
  const sim = newSim();
  await runScript(sim, ["@nomatch", "INT. BANK VAULT, NIGHT. Los Angeles."]);
  const out = texts(sim);
  assert.equal(out[1], "MOCK · 0 interior picks\nNothing matched. Relaxed: era, parking. Try loosening the era, size or parking.");
  assert.match(out.at(-1), /^http:\/\/192\.0\.2\.10:8000\/app\/\?scene=/);
  assertHouseRules(sim);
});

test("golden: a refine goes to /refine and gets one compact bubble", async () => {
  const sim = newSim();
  await runScript(sim, [...fixture("single-int"), "need parking for 5 trucks"]);
  const refine = sim.calls.filter((c) => c.path === "/refine");
  assert.deepEqual(refine.map((c) => c.body), [{ thread_id: "sim-thread", message: "need parking for 5 trucks" }]);
  assert.equal(texts(sim).length, 4, "exactly one new bubble");
  assert.match(texts(sim)[3], /^MOCK · updated ranking, 3 interior picks\n1\. /);
  assertHouseRules(sim);
});

test("golden: draft then YES saves a local draft; draft then NO drops it; nothing is ever sent", async () => {
  const sim = newSim();
  await runScript(sim, [...fixture("single-int"), "draft 1", "YES", "draft 2", "NO"]);
  const out = texts(sim);
  assert.match(out[3], /Reply YES to save this as a local draft, or NO to drop it\. Nothing will be sent\./);
  assert.match(out[4], /^Saved as a local draft, not sent/);
  assert.equal(out[6], "Okay, nothing sent.");
  assert.deepEqual(sim.calls.filter((c) => c.path === "/approve").map((c) => c.body), [
    { thread_id: "sim-thread", pick_rank: 1, decision: "yes" }, { thread_id: "sim-thread", pick_rank: 2, decision: "no" },
  ]);
  assertHouseRules(sim);
});

test("golden: unclear text after results gets a one-line help message", async () => {
  const sim = newSim();
  await runScript(sim, [...fixture("single-int"), "hmm ok"]);
  assert.equal(texts(sim).at(-1), 'Not sure what you mean. Try: "need parking for 5 trucks", "draft 1" or "start over".');
  assert.equal(sim.calls.filter((c) => c.path === "/refine").length, 0);
});

test("golden: a results bubble that fails twice is replaced by a short line, and the link is still sent", async () => {
  const sim = newSim();
  await runScript(sim, ["@failresults", "INT. WAREHOUSE, DAY. Los Angeles."]);
  const out = texts(sim);
  assert.ok(out.includes(RESULTS_FAILED));
  assert.equal(RESULTS_FAILED, "Pick list couldn't be sent, open the link instead.");
  assert.ok(!out.some((t) => /^MOCK · /.test(t)));
  assert.match(out.at(-1), /^http:\/\/192\.0\.2\.10:8000\/app\//);
  assert.equal(sim.printed.filter((l) => /\[runner error\] Photon API error 500 \(request sim\)\./.test(l)).length, 2, "tried twice, then gave up");
});

test("golden: a single failed send is retried once with the same key and the flow carries on", async () => {
  const sim = newSim();
  await runScript(sim, ["@fail 1", "need a cop station in LA"]);
  assert.equal(texts(sim).length, 1);
  assert.equal(sim.outbound[0].key, "typecast-reply:sim-msg-1:0");
});

test("golden: a sender who is not on the allowlist gets no reply and triggers no search", async () => {
  const sim = newSim();
  await runScript(sim, ["@other INT. WAREHOUSE, DAY. Los Angeles.", "@other hello"]);
  assert.equal(sim.outbound.length, 0);
  assert.equal(sim.calls.length, 0);
});

test("golden: junk answers never produce more than three questions", async () => {
  const sim = newSim();
  await runScript(sim, ["hi", "asdf", "qwerty", "xyz"]);
  assert.ok(questions(sim).length <= 3);
  assert.equal(scouts(sim).length, 1);
  assertHouseRules(sim);
});

test("golden: without PHOTON_VIEWER_URL there is no link and the exterior line says so", async () => {
  const sim = newSim({});
  await runScript(sim, ["need a police station in LA at night with an alley outside, 3 trucks and 30 cars"]);
  const out = texts(sim);
  assert.equal(out.length, 3);
  assert.match(out[2], /^Exterior search not run \(no site link is configured\): EXT\. ALLEY/);
  assert.ok(!out.some((t) => /^https?:\/\//.test(t)));
});

test("every fixture obeys the house rules, and the simulator CLI runs them", () => {
  for (const name of ["cop-station", "interior-and-exterior", "single-int", "correction"]) {
    const out = execFileSync(process.execPath, [new URL("./sim.mjs", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"), "--script", new URL(`./fixtures/${name}.txt`, import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")], { encoding: "utf8" });
    assert.match(out, /Nothing is sent to Photon|nothing is sent to Photon/i);
    assert.match(out, /outbound message\(s\) in total/);
    assert.ok(!/delivered|blocked alternative/i.test(out));
    assert.ok([...out.matchAll(/conversation \d+: (\d+) of 8/g)].every((m) => Number(m[1]) <= 8));
  }
});

// --- units ---------------------------------------------------------------------------------------------------
test("the budget stops a flow at 8 bubbles and says how many were over the limit", async () => {
  const sent = [], logs = [];
  const conv = createConversations({
    handle: async () => Array.from({ length: 11 }, (_, i) => ({ text: `bubble ${i}` })),
    send: async (m, n, text) => { sent.push(text); return true; }, wait: async () => {}, log: (l) => logs.push(l),
  });
  conv.submit({ id: "m", spaceId: "s", senderId: "a", text: "hi" });
  await conv.idle();
  assert.equal(sent.length, BUDGET);
  assert.deepEqual(logs, [`conversation 1: 8 of 8 outbound in this search, 3 over the limit were not sent`]);
});

test("link contract: URL-encoded, empty params omitted, /app/ normalised, exterior-only never autoruns", () => {
  const link = buildViewerLink(`${VIEWER}/app/`, { scene: "INT. A & B, DAY.", ext: "", city: "HOU", trucks: 0, cars: undefined });
  assert.equal(link, `${VIEWER}/app/?scene=INT.%20A%20%26%20B%2C%20DAY.&city=HOU&trucks=0&autorun=1`);
  assert.equal(buildViewerLink(VIEWER, { ext: "EXT. ALLEY, NIGHT.", city: "LA" }), `${VIEWER}/app/?ext=EXT.%20ALLEY%2C%20NIGHT.&city=LA`);
  for (const bad of ["", undefined, "not a url", "ftp://x/y", "javascript:alert(1)"]) assert.equal(buildViewerLink(bad, { scene: "INT. X." }), null);
  assert.equal(buildViewerLink(VIEWER, {}), null);
});

test("results formatting keeps FAKE, est. and unknown wording and drops internal wording", () => {
  const pick = (rank, over = {}) => ({
    rank, property: { address: `${rank} Test St (FAKE)`, available: true }, shot_fit: { status: "fits", fits: true, needed_depth_m: 5, have_depth_m: 9 },
    logistics: { truck_spaces: 2, car_spaces: null, estimated: true }, skeptic_notes: ["Blocked alternative: another site"], ...over,
  });
  const text = formatResults({ source_mode: "mock", picks: [pick(3), pick(1), pick(2, { shot_fit: { status: "unknown", have_depth_m: null }, property: { address: "2 Test St (FAKE)", availability_status: "unknown" } })], gave_up: [] });
  const lines = text.split("\n");
  assert.equal(lines[0], "MOCK · 3 interior picks");
  assert.deepEqual([lines[1][0], lines[3][0], lines[5][0]], ["1", "2", "3"], "rank order");
  assert.match(text, /2 Test St \(FAKE\) \(availability unknown\)\nShot fit unknown\. Parking \(est\.\): 2 trucks, unknown cars\./);
  assert.ok(!/blocked alternative/i.test(text));
  assert.equal(lines.length, 7, "no more than two lines per pick");
});

test("parsing: INT./EXT. headings route text and exterior words go to the exterior", () => {
  assert.deepEqual(parseBrief("INT. WAREHOUSE, DAY. EXT. LOADING YARD, DAY."), { heading: true, time: "DAY", interiorScene: "INT. WAREHOUSE, DAY.", setting: "warehouse", exteriorQuery: "EXT. LOADING YARD, DAY." });
  const b = parseBrief("a bar with a rooftop, houston");
  assert.deepEqual([b.setting, b.exterior, b.city], ["bar", "rooftop", "HOU"]);
  assert.equal(parseBrief("need a diner, no exterior").exterior, undefined);
  assert.equal(parseBrief("need a diner, no exterior").declineExterior, true);
});

test("a photo from an allowlisted person is flagged non-text; tapbacks, receipts and typing are ignored", () => {
  const cfg = parseConfig({ PHOTON_PROJECT_ID: "p", PHOTON_PROJECT_SECRET: "k", PHOTON_AGENT_HANDLE: "+15550100188", PHOTON_ALLOWED_SENDERS: "+15550100100" });
  const base = { id: "m", platform: "imessage", status: "received", createdAt: "2026-11-15T12:00:01Z",
    space: { platform: "imessage", kind: "direct", id: "s" }, sentBy: { platform: "imessage", kind: "human", handle: "+15550100100", id: "h" },
    receivedBy: { platform: "imessage", kind: "agent", handle: "+15550100188", id: "a" } };
  const at = Date.parse("2026-11-15T12:00:00Z");
  assert.equal(acceptMessage({ ...base, content: { type: "attachment", attachmentId: "x" } }, cfg, at).nonText, true);
  assert.equal(acceptMessage({ ...base, content: { type: "voice", attachmentId: "x" } }, cfg, at).nonText, true);
  for (const content of [{ type: "reaction", action: "added", reaction: "love" }, { type: "message.read" }, { type: "space.typing.update" }]) {
    assert.deepEqual(acceptMessage({ ...base, content }, cfg, at), { ok: false, reason: "not_text" });
  }
  const stranger = { ...base, sentBy: { ...base.sentBy, handle: "+15550100999" }, content: { type: "attachment", attachmentId: "x" } };
  assert.equal(acceptMessage(stranger, cfg, at).reason, "sender_not_allowed", "a stranger's photo gets no notice either");
});

test("dry run reads but never sends, and logs only a count and a length", async () => {
  const logs = [], real = { sent: 0, projects: { listMessages: async () => ({ items: [] }), sendMessage: async () => { real.sent += 1; } } };
  const dry = makeDryRunClient(real, (l) => logs.push(l));
  assert.deepEqual(await dry.projects.listMessages({}), { items: [] });
  await dry.projects.sendMessage({ body: { content: { text: "a private message body" } } });
  await dry.projects.sendMessage({ body: { content: { text: "x" } } });
  assert.equal(real.sent, 0);
  assert.equal(dry.stats.wouldSend, 2);
  assert.deepEqual(logs, ["dry run: would send reply 1 (22 characters); nothing was sent", "dry run: would send reply 2 (1 characters); nothing was sent"]);
  assert.ok(!logs.join(" ").includes("private"));
});
