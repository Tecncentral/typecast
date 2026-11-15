import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { sessions } from "./core.mjs";
import {
  extract, step, buildScene, isDetailed, isStartOver, parseAllowed, isAllowed, buildLink, rewriteLink,
  handleMessage, MAX_QUESTIONS,
} from "./intake.mjs";

const MOCK_PICKS = JSON.parse(readFileSync(new URL("../mocks/pick.json", import.meta.url), "utf8"));
const EXAMPLE_SCENE = "INT. 1980s POLICE STATION, NIGHT. Los Angeles. Gritty. Parking for 3 trucks and 30 crew cars.";

function fakeFetch(calls) {
  return async (url, init) => {
    const path = new URL(url).pathname; const body = JSON.parse(init.body); calls.push([path, body]);
    const json = path === "/approve" ? { sent: false, to: null }
      : { thread_id: "t1", picks: MOCK_PICKS, gave_up: [], source_mode: "mock", engine: "fixed" };
    return { ok: true, json: async () => json, text: async () => "" };
  };
}
const texts = (parts) => parts.filter((p) => p.text).map((p) => p.text);
async function say(key, text, ctx) { return handleMessage(key, text, ctx); }

test("extract reads setting, time, city, era, mood and parking from plain words", () => {
  assert.deepEqual(extract("need a cop station for a night interrogation scene"), { setting: "police station", ie: "INT", time: "NIGHT" });
  const f = extract("LA, 80s, kinda grimy. 3 trucks and 30 cars");
  assert.equal(f.city, "LA"); assert.equal(f.era, "1980s"); assert.equal(f.mood, "Gritty");
  assert.equal(f.trucks, 3); assert.equal(f.cars, 30);
  assert.equal(extract("something in Houston").city, "HOU");
  assert.equal(extract("a 1970s diner").era, "1970s");
  assert.equal(extract("modern office, daytime").era, "modern");
  assert.equal(extract("need an old bakery for a heist").setting, "old bakery");
  assert.equal(extract("rooftop at dusk").ie, "EXT");
  assert.deepEqual(extract(""), {});
});

test("buildScene matches the target string", () => {
  assert.equal(buildScene({ ie: "INT", setting: "police station", time: "NIGHT", era: "1980s", city: "LA", mood: "Gritty", trucks: 3, cars: 30 }), EXAMPLE_SCENE);
  assert.equal(buildScene({ setting: "warehouse", city: "HOU", trucks: 1 }), "INT. WAREHOUSE. Houston. Parking for 1 truck.");
});

test("the example conversation: three questions, one at a time, then one /scout call", async () => {
  sessions.clear(); const calls = []; const f = fakeFetch(calls); const said = [];
  const ctx = { say: async (t) => said.push(t), fetchImpl: f, env: {} };
  let r = await say("p", "need a cop station for a night interrogation scene", ctx);
  assert.deepEqual(texts(r), ["Got it: police station, night. LA or Houston?"]);
  r = await say("p", "LA", ctx);
  assert.deepEqual(texts(r), ["What era? Reply: modern / 80s / 70s / any"]);
  r = await say("p", "80s, kinda grimy", ctx);
  assert.deepEqual(texts(r), ['How many trucks and crew cars? Or "skip".']);
  assert.equal(calls.length, 0, "no API call until the intake is complete");
  r = await say("p", "3 trucks 30 cars", ctx);
  assert.deepEqual(said, [`Searching for: ${EXAMPLE_SCENE}`]);
  assert.deepEqual(calls, [["/scout", { scene: EXAMPLE_SCENE }]]);
  assert.match(texts(r)[0], /^MOCK · fixed engine$/);
  assert.equal(r.filter((p) => p.image).length, 6);
  assert.equal(texts(r).filter((t) => /^\d\. /.test(t)).length, 3);
});

test("a first message that starts INT./EXT. searches immediately with the text unchanged", async () => {
  sessions.clear(); const calls = [];
  const raw = "INT. 1980s POLICE STATION, NIGHT. Parking for 3 trucks and 30 crew cars.";
  const r = await say("a", raw, { fetchImpl: fakeFetch(calls), env: {} });
  assert.deepEqual(calls, [["/scout", { scene: raw }]]);
  assert.ok(r.length > 3);
});

test("a detailed first message with a setting and a city searches with no questions", async () => {
  sessions.clear(); const calls = [];
  await say("b", "need a gritty 80s diner in Houston for a night scene, 2 trucks", { fetchImpl: fakeFetch(calls), env: {} });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][1].scene, "INT. 1980s DINER, NIGHT. Houston. Gritty. Parking for 2 trucks.");
  assert.equal(isDetailed("hi"), false);
});

test("only missing slots are asked, and at most four questions in all", async () => {
  sessions.clear(); const calls = []; const ctx = { fetchImpl: fakeFetch(calls), env: {} };
  const asked = [];
  let r = await say("c", "hi", ctx); asked.push(texts(r)[0]);
  for (const reply of ["blah", "mumble", "huh", "what?", "nope"]) {
    if (calls.length) break;
    r = await say("c", reply, ctx); if (!calls.length) asked.push(texts(r)[0]);
  }
  assert.ok(asked.length <= MAX_QUESTIONS, `asked ${asked.length}`);
  assert.equal(calls.length, 1, "it gives up asking and searches");
  assert.equal(MAX_QUESTIONS, 4);
});

test("skip and any are accepted on every question", async () => {
  sessions.clear(); const calls = []; const ctx = { fetchImpl: fakeFetch(calls), env: {} };
  await say("d", "need a warehouse", ctx);
  await say("d", "Houston", ctx);
  await say("d", "any", ctx);
  await say("d", "skip", ctx);
  const r = await say("d", "skip", ctx);
  assert.deepEqual(calls, [["/scout", { scene: "INT. WAREHOUSE. Houston." }]]);
  assert.ok(texts(r).length > 0);
});

test("one reply can fill several slots and the next question skips them", async () => {
  sessions.clear(); const ctx = { fetchImpl: fakeFetch([]), env: {} };
  await say("e", "need a bar", ctx);
  const r = await say("e", "LA, 70s", ctx);
  assert.match(texts(r)[0], /Day or night/);
});

test("start over resets, and the next detailed message searches at once", async () => {
  sessions.clear(); const calls = []; const ctx = { fetchImpl: fakeFetch(calls), env: {} };
  await say("f", "INT. OFFICE, DAY", ctx);
  assert.ok(sessions.get("f").threadId);
  let r = await say("f", "start over", ctx);
  assert.match(texts(r)[0], /^Okay, starting over\. What kind of place/);
  assert.equal(sessions.get("f").threadId, undefined);
  assert.equal(isStartOver("New search!"), true); assert.equal(isStartOver("new search please"), false);
  await say("f", "INT. WAREHOUSE, NIGHT", ctx);
  assert.deepEqual(calls.map((c) => c[0]), ["/scout", "/scout"]);
  r = await say("f", "new search", ctx);
  assert.match(texts(r)[0], /^Okay, starting over/);
});

test("after results the existing flows still work: re-rank, draft N, YES", async () => {
  sessions.clear(); const calls = []; const ctx = { fetchImpl: fakeFetch(calls), env: {} };
  await say("g", "INT. OFFICE, DAY", ctx);
  await say("g", "need parking for 5 trucks", ctx);
  assert.deepEqual(calls.map((c) => c[0]), ["/scout", "/refine"]);
  const draft = await say("g", "draft 1", ctx);
  assert.match(texts(draft)[0], /Reply YES to save this as a local draft/);
  const yes = await say("g", "YES", ctx);
  assert.match(texts(yes)[0], /local draft, not sent/);
  assert.deepEqual(calls.map((c) => c[0]), ["/scout", "/refine", "/approve"]);
});

test("the link: built from PHOTON_VIEWER_URL, labelled honestly, left out when empty or unsafe", async () => {
  sessions.clear();
  const url = "https://viewer.example/app/";
  let r = await say("h", "INT. OFFICE, DAY", { fetchImpl: fakeFetch([]), env: { PHOTON_VIEWER_URL: url } });
  const last = texts(r).at(-1);
  assert.match(last, /^See them in 3D: https:\/\/viewer\.example\/app\/\?scene=INT\.\+OFFICE%2C\+DAY&autorun=1\n\(opens the site and runs this search live\)/);
  assert.doesNotMatch(last, /#\/run/);
  sessions.clear();
  for (const env of [{}, { PHOTON_VIEWER_URL: "" }, { PHOTON_VIEWER_URL: "javascript:alert(1)" }, { PHOTON_VIEWER_URL: "not a url" }]) {
    sessions.clear();
    r = await say("h", "INT. OFFICE, DAY", { fetchImpl: fakeFetch([]), env });
    assert.ok(!r.some((p) => p.text?.includes("See them in 3D") || p.text?.includes("Tour them") || p.text?.includes("#/run")));
    assert.match(texts(r).at(-1), /^Reply with a change/);
  }
  assert.equal(buildLink("", "x"), null);
  assert.equal(buildLink(url, ""), null);
  assert.deepEqual(rewriteLink([{ text: "other" }], { viewerUrl: url, scene: "x" }), [{ text: "other" }]);
});

test("no reply contains a price (any price must carry the scenario-estimate label)", async () => {
  sessions.clear(); const ctx = { fetchImpl: fakeFetch([]), env: { PHOTON_VIEWER_URL: "https://v.example/app/" } };
  const all = [];
  for (const m of ["need a cop station for a night scene", "LA", "80s", "skip", "need parking for 5 trucks", "draft 1", "YES", "start over"]) {
    all.push(...texts(await say("i", m, ctx)));
  }
  assert.ok(all.length > 8);
  assert.ok(!all.some((t) => /[$€£]|\bUSD\b|\bsavings?\b/i.test(t)), "no price or savings text in Stage 1 replies");
});

test("allowlist: normalizes phones and emails, and fails closed", () => {
  const allowed = parseAllowed("+1 (555) 010-0100, Director@Example.com ; 5550100200");
  assert.ok(isAllowed("+15550100100", allowed));
  assert.ok(isAllowed("555-010-0100", allowed));
  assert.ok(isAllowed("director@example.COM", allowed));
  assert.ok(isAllowed("+1 555 010 0200", allowed));
  assert.ok(!isAllowed("+15550100999", allowed));
  assert.ok(!isAllowed("", allowed) && !isAllowed(undefined, allowed) && !isAllowed(null, allowed));
  assert.ok(!isAllowed("+15550100100", parseAllowed("")) && !isAllowed("+15550100100", parseAllowed(undefined)));
  assert.ok(!isAllowed("+15550100100", undefined));
  assert.equal(parseAllowed(" , ; ").size, 0);
  assert.equal(parseAllowed("+1 555 010 0100\n+1 555 010 0200").size, 2, "newline separated, spaces kept inside a number");
});

test("intake.mjs makes no network or model call of its own and reads no secrets", () => {
  const source = readFileSync(new URL("./intake.mjs", import.meta.url), "utf8");
  const imports = [...source.matchAll(/^import .* from "(.+)";$/gm)].map((m) => m[1]);
  assert.deepEqual(imports, ["./core.mjs"]);
  assert.ok(!/PHOTON_PROJECT|SECRET|API_KEY|openai|anthropic|llm/i.test(source.replace(/No LLM call here/, "")));
  assert.deepEqual([...source.matchAll(/env\.([A-Z_]+)/g)].map((m) => m[1]), ["PHOTON_VIEWER_URL"]);
});

test("step never asks more than four questions even when nothing is understood", () => {
  let state = null, asks = 0, action = "ask", text = "hello";
  for (let i = 0; i < 12 && action === "ask"; i++) {
    const r = step(state, text, { first: i === 0 }); state = r.state; action = r.action; if (action === "ask") asks++; text = "???";
  }
  assert.ok(asks <= MAX_QUESTIONS && action === "search");
});
