import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  laneStates, stepStates, latestTodos, imageUrl, fitInfo, availabilityInfo, parkingInfo,
  noiseInfo, objections, sourceStatus, rankDiff, moveLabel, tourLink, parkingRings, parseJsonl,
} from "../lib.js";

const mockEvents = parseJsonl(readFileSync(new URL("../../mocks/events.jsonl", import.meta.url), "utf8"));
const mockPicks = JSON.parse(readFileSync(new URL("../../mocks/pick.json", import.meta.url), "utf8"));

test("lanes collapse repeated tools, hide internal writes and keep skeptic objections", () => {
  const events = [
    { type: "subagent_start", agent: "interior_scout", text: "Searching", ts: 0.1 },
    { type: "tool", agent: "check_shot", text: "", ts: 0.2, ms: 1 },
    { type: "tool", agent: "check_shot", text: "", ts: 0.3, ms: 2 },
    { type: "tool", agent: "state.save.candidates", text: "", ts: 0.4, ms: 1 },
    { type: "subagent_result", agent: "interior_scout", text: "12 views", ts: 0.5 },
    { type: "skeptic", agent: "skeptic", text: "A St: Noise: freeway within 200 m.", ts: 0.6 },
    { type: "skeptic", agent: "skeptic", text: "B St: No objection.", ts: 0.7 },
  ];
  const lanes = Object.fromEntries(laneStates(events).map((l) => [l.id, l]));
  const tools = lanes.interior_scout.rows.filter((r) => r.kind === "tool");
  assert.equal(tools.length, 1);
  assert.equal(tools[0].count, 2);
  assert.equal(tools[0].ms, 3);
  assert.equal(lanes.interior_scout.state, "done");
  assert.ok(!lanes.director.rows.some((r) => r.text.startsWith("state.")));
  assert.deepEqual(lanes.skeptic.rows.map((r) => r.kind), ["skeptic", "ok"]);
  assert.equal(lanes.skeptic.state, "working");
  assert.equal(laneStates(events, true).find((l) => l.id === "skeptic").state, "done");
});

test("steps only advance on real events", () => {
  assert.ok(stepStates([]).every((s) => s.state === "pending"));
  const mid = stepStates([{ type: "subagent_start", agent: "market_scout" }]);
  assert.equal(mid.find((s) => s.id === "market").state, "active");
  assert.equal(mid.find((s) => s.id === "parse").state, "skipped");
  assert.equal(mid.find((s) => s.id === "final").state, "pending");
  const fixture = stepStates(mockEvents, true);
  assert.equal(fixture.find((s) => s.id === "skeptic").state, "done");
});

test("deep to-do list parsed from the latest todo event", () => {
  const todos = latestTodos([
    { type: "todo", text: JSON.stringify([{ content: "a", status: "pending" }]) },
    { type: "todo", text: JSON.stringify([{ content: "a", status: "completed" }, { content: "b", status: "in_progress" }]) },
  ]);
  assert.deepEqual(todos, [{ text: "a", status: "completed" }, { text: "b", status: "in_progress" }]);
  assert.equal(latestTodos([{ type: "todo", text: "not json" }]), null);
});

test("image urls only for served folders, never filesystem paths", () => {
  assert.equal(imageUrl("mocks/img/a.jpg"), "/mocks/img/a.jpg");
  assert.equal(imageUrl("cache/views/x y.jpg"), "/cache/views/x%20y.jpg");
  assert.equal(imageUrl("/Users/me/cache/a.jpg"), null);
  assert.equal(imageUrl("C:\\data\\a.jpg"), null);
  assert.equal(imageUrl("cache/../.env"), null);
  assert.equal(imageUrl(null), null);
});

test("unknown depth is never 'fits'", () => {
  assert.equal(fitInfo({ fits: true, needed_depth_m: 8.78, have_depth_m: null, status: "fits" }).status, "unknown");
  assert.equal(fitInfo({ fits: false, needed_depth_m: 8.78, have_depth_m: 6, ceiling_m: null }).status, "tight");
  assert.equal(fitInfo({ fits: false, needed_depth_m: 8.78, have_depth_m: 6, ceiling_m: null }).ceiling, null);
  assert.equal(fitInfo(null).status, "unknown");
});

test("availability honours availability_status over the legacy boolean", () => {
  assert.equal(availabilityInfo({ available: false, availability_status: "unknown" }).status, "unknown");
  assert.equal(availabilityInfo({ available: true }).status, "available");
  assert.equal(availabilityInfo({ available: false }).status, "occupied");
});

test("null parking is unknown, not zero", () => {
  assert.equal(parkingInfo({ truck_spaces: null, car_spaces: null, noise_flags: [] }).label, "Parking unknown");
  assert.match(parkingInfo({ truck_spaces: 0, car_spaces: null, estimated: true }).label, /^0 trucks · unknown cars$/);
  assert.equal(parkingInfo({ truck_spaces: 1, car_spaces: 2, walk_m: null }).walk, "walk unknown");
});

test("empty noise flags with unknown status is not quiet", () => {
  assert.equal(noiseInfo({ noise_flags: [], noise_status: "unknown" }).label, "Noise not screened");
  assert.equal(noiseInfo({ noise_flags: [], noise_status: "estimated" }).label, "No freeway, rail or airport flagged");
  assert.equal(noiseInfo({ noise_flags: ["rail line within 300 m"] }).flags.length, 1);
});

test("objections drop 'No objection.' and sources take their weakest status", () => {
  assert.deepEqual(objections({ skeptic_notes: ["No objection.", "Noise"] }), ["Noise"]);
  assert.equal(sourceStatus([]), "unknown");
  assert.equal(sourceStatus([{ status: "measured" }, { status: "estimated" }]), "estimated");
});

test("rank diff by property id, with new objections and dropped picks", () => {
  const before = { picks: mockPicks };
  const after = { picks: [
    { ...mockPicks[1], rank: 1, skeptic_notes: [...mockPicks[1].skeptic_notes, "Parking short: 5 trucks needed."] },
    { ...mockPicks[0], rank: 2 },
    { rank: 3, property: { property_id: "brand-new" }, skeptic_notes: [] },
  ] };
  const { moves, dropped } = rankDiff(before, after);
  assert.equal(moves[0].move, "up");
  assert.deepEqual(moves[0].newNotes, ["Parking short: 5 trucks needed."]);
  assert.equal(moves[1].move, "down");
  assert.equal(moves[2].move, "new");
  assert.equal(moveLabel(moves[0]), "Up from #2");
  assert.equal(dropped.length, mockPicks.length - 2);
});

test("tour links only for real-looking model ids", () => {
  assert.equal(tourLink("mock-m1"), null);
  assert.equal(tourLink("SxQL3iGyoDo"), "https://my.matterport.com/show/?m=SxQL3iGyoDo");
  assert.equal(tourLink("x\"><script>"), null);
});

test("parking rings prefer GeoJSON and flip it to [lat, lon]", () => {
  const lg = { parking_polygon: [[34, -118], [34.1, -118], [34.1, -118.1]],
    parking_geometry: { type: "Polygon", coordinates: [[[-118.2, 34.2], [-118.3, 34.2], [-118.3, 34.3]]] } };
  assert.deepEqual(parkingRings(lg)[0][0], [34.2, -118.2]);
  assert.deepEqual(parkingRings({ parking_polygon: lg.parking_polygon }), [lg.parking_polygon]);
  assert.deepEqual(parkingRings({ parking_polygon: [] }), []);
});
