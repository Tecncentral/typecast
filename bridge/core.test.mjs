import test from "node:test";
import assert from "node:assert/strict";
import { handle, sessions, formatPick, imageUrl } from "./core.mjs";

const pick = (rank, extra = {}) => ({
  rank, reason: "CoStar: office; Matterport: fits; Vexcel: parking.",
  property: { address: `${rank}00 Test St`, available: true, contact: "broker" },
  shots: [{ image_path: `mocks/img/p${rank}.jpg` }],
  shot_fit: { fits: rank !== 2, needed_depth_m: 8.78, have_depth_m: 10 },
  logistics: { truck_spaces: 4, car_spaces: 40 },
  skeptic_notes: rank === 2 ? ["Noise: freeway within 200 m."] : ["No objection."], ...extra,
});
function fakeFetch(calls) {
  return async (url, init) => {
    const path = new URL(url).pathname; const body = JSON.parse(init.body); calls.push([path, body]);
    const json = path === "/approve" ? { sent: false, to: body.decision === "yes" ? "team@example.com" : null }
      : { thread_id: "t1", picks: [pick(1), pick(2), pick(3)], gave_up: path === "/scout" ? ["era"] : [] };
    return { ok: true, json: async () => json, text: async () => "" };
  };
}

test("scene -> ack first, then images and three picks", async () => {
  sessions.clear(); const calls = []; const said = [];
  const parts = await handle("a", "INT. 1980s POLICE STATION, NIGHT. 3 trucks", { say: async (t) => said.push(t), fetchImpl: fakeFetch(calls) });
  assert.match(said[0], /^On it/);
  assert.equal(calls[0][0], "/scout");
  assert.equal(parts.filter((p) => p.image).length, 3);
  assert.equal(parts.filter((p) => p.text && /^\d\. /.test(p.text)).length, 3);
  assert.ok(parts.some((p) => p.text?.includes("relaxed: era")));
  assert.ok(parts.at(-1).text.includes("#/run/t1"));
});

test("short follow-up refines the same thread; a new slug line starts over", async () => {
  sessions.clear(); const calls = []; const f = fakeFetch(calls);
  await handle("a", "INT. OFFICE, DAY", { fetchImpl: f });
  await handle("a", "need parking for 5 trucks", { fetchImpl: f });
  await handle("a", "EXT. WAREHOUSE, NIGHT", { fetchImpl: f });
  assert.deepEqual(calls.map((c) => c[0]), ["/scout", "/refine", "/scout"]);
  assert.equal(calls[1][1].thread_id, "t1");
});

test("draft waits for YES and never claims delivery that did not happen", async () => {
  sessions.clear(); const calls = []; const f = fakeFetch(calls);
  await handle("a", "INT. OFFICE, DAY", { fetchImpl: f });
  const d = await handle("a", "draft 2", { fetchImpl: f });
  assert.match(d[0].text, /Reply YES/); assert.equal(calls.length, 1);
  const y = await handle("a", "yes", { fetchImpl: f });
  assert.deepEqual(calls[1], ["/approve", { thread_id: "t1", pick_rank: 2, decision: "yes" }]);
  assert.match(y[0].text, /nothing went to the owner/);
  await handle("a", "draft 1", { fetchImpl: f });
  assert.match((await handle("a", "No", { fetchImpl: f }))[0].text, /nothing sent/i);
});

test("formatting, urls and failures", async () => {
  assert.match(formatPick(pick(2)), /Shot is tight[\s\S]*Watch out: Noise/);
  assert.ok(!formatPick(pick(1)).includes("Watch out"));
  assert.equal(imageUrl("https://x/y.jpg"), "https://x/y.jpg");
  assert.match(imageUrl("mocks/img/a.jpg"), /\/mocks\/img\/a\.jpg$/);
  sessions.clear();
  const bad = await handle("b", "INT. X", { fetchImpl: async () => ({ ok: false, status: 500, text: async () => "boom" }) });
  assert.match(bad[0].text, /Something broke/);
  assert.match((await handle("c", "   "))[0].text, /Send me a scene/);
});
