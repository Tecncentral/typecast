import test from "node:test";
import assert from "node:assert/strict";
import { openStore, hashSender, sqlTime } from "./store.mjs";
import { alertsKeyword, createAlerts, simulatedRentSource, PRICE_LABEL, priceAlertText, reminderText } from "./alerts.mjs";
import { createSim, runScript, SIM_SENDER } from "./sim.mjs";
import { BUDGET } from "./conversations.mjs";

const SENDER_HASH = hashSender(SIM_SENDER);
const T0 = Date.parse("2026-11-15T12:00:00Z");
const MIN = 60_000;
const SCENE = "INT. WAREHOUSE, DAY. Los Angeles. Parking for 2 trucks.";
const live = { PHOTON_ALERTS_REAL: "1", REMINDER_AFTER_MIN: "100000" };      // real sends to the fake client; reminders off unless a test wants them
const texts = (sim) => sim.outbound.map((o) => o.text);
const alertRows = (sim) => sim.store.db.prepare("SELECT kind, simulated, property_id FROM alerts ORDER BY id").all().map((r) => ({ ...r }));
const priceTexts = (sim) => texts(sim).filter((t) => t.startsWith(PRICE_LABEL));
/** A source that plays back one rent per check for the first pick, and null for the others. */
const script = (...rents) => (pick, { checkNo }) => (pick.rank === 1 ? rents[Math.min(checkNo, rents.length - 1)] : null);

/** A search saved straight into a store, for tests that do not need the conversation. */
function seedSearch(store, { hash = SENDER_HASH, space = "space-1", createdAt = T0, maxRent = 20, outbound = 3, alertsOn = true, picks } = {}) {
  const userId = store.upsertUser(hash);
  store.upsertConversation(space, userId);
  const briefId = store.saveBrief({ userId, channel: "imessage" });
  const searchId = store.saveSearch({ briefId, userId, threadId: `t-${space}-${createdAt}`, sourceMode: "mock", maxRent, alertsOn, createdAt: sqlTime(createdAt) });
  store.savePicks(searchId, picks ?? [{ rank: 1, propertyId: "p1", address: "1 Test St (FAKE)", propertyType: "Industrial", rentRef: 15 }]);
  store.setOutboundCount(searchId, outbound);
  return searchId;
}

test("keyword match: ALERTS ON and ALERTS OFF only, any case, nothing else", () => {
  for (const [text, want] of [["ALERTS ON", "on"], ["alerts off", "off"], ["  Alerts On! ", "on"], ["ALERTS   OFF.", "off"]]) assert.equal(alertsKeyword(text), want, text);
  for (const text of ["alerts", "turn alerts on", "alerts on please", "alert on", "ALERTS ONN", "need parking for 5 trucks", "", undefined]) assert.equal(alertsKeyword(text), null, String(text));
});

test("opt-in: ALERTS ON then OFF sets alerts_on on the latest search with one short reply each, and a stranger cannot", async () => {
  const sim = createSim({ alerts: true, env: {} });
  await runScript(sim, ["ALERTS ON"]);
  assert.deepEqual(texts(sim), ["Run a search first, then text ALERTS ON."], "no search yet");
  await runScript(sim, [SCENE, "ALERTS ON"]);
  assert.equal(texts(sim).length, 4);
  assert.match(texts(sim)[3], /^Alerts are ON for your latest search\. This is a simulated demo/);
  const latest = () => sim.store.latestSearch(SENDER_HASH);
  assert.equal(latest().alerts_on, 1);
  await runScript(sim, ["ALERTS OFF"]);
  assert.equal(texts(sim).at(-1), "Alerts are OFF for your latest search.");
  assert.equal(latest().alerts_on, 0);
  await runScript(sim, ["@other ALERTS ON"]);
  assert.equal(texts(sim).length, 5, "a sender who is not allowlisted gets no reply");
  assert.equal(latest().alerts_on, 0);
  await runScript(sim, [SCENE.replace("WAREHOUSE", "DINER"), "ALERTS ON"]);
  assert.equal(sim.store.db.prepare("SELECT COUNT(*) AS n FROM searches WHERE alerts_on = 1").get().n, 1, "only the newest search");
});

test("save after results: brief, search and picks stored as mock with NULL rent and drive, and no message text or number", async () => {
  const sim = createSim({ alerts: true, env: {} });
  await runScript(sim, ["INT. WAREHOUSE, DAY. Two couriers hand over a SECRETCASE near Pat's place. Los Angeles. Parking for 2 trucks."]);
  const db = sim.store.db;
  const search = db.prepare("SELECT * FROM searches").get();
  assert.equal(search.source_mode, "mock");
  for (const col of ["max_rent", "rent_units", "max_drive_min", "base_lat", "base_lon"]) assert.equal(search[col], null, col);
  assert.equal(search.alerts_on, 0);
  assert.equal(search.outbound_count, 2, "the confirmation and the results bubble");
  const picks = db.prepare("SELECT * FROM picks ORDER BY rank").all();
  assert.deepEqual(picks.map((p) => p.rank), [1, 2, 3]);
  for (const p of picks) { assert.equal(p.rent_ref, null); assert.equal(p.rent_tier, null); assert.equal(p.drive_min, null); }
  const brief = db.prepare("SELECT * FROM briefs").get();
  assert.equal(brief.channel, "imessage");
  assert.match(brief.interior_scene, /^INT\. WAREHOUSE, DAY\. Los Angeles\. Parking for 2 trucks\.$/, "a structured scene, not the typed text");
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM users").get().n, 1);
  assert.equal(db.prepare("SELECT sender_hash FROM users").get().sender_hash, SENDER_HASH);
  const dump = JSON.stringify(["users", "conversations", "briefs", "searches", "picks", "messages", "alerts"].map((t) => db.prepare(`SELECT * FROM ${t}`).all()));
  assert.ok(!/SECRETCASE|couriers|5550100100/.test(dump), "no message text and no phone number");
});

test("reminder: one per search, only after REMINDER_AFTER_MIN, only with alerts on and no drafted reach-out", async () => {
  const env = { PHOTON_ALERTS_REAL: "1", REMINDER_AFTER_MIN: "30" };
  const sim = createSim({ alerts: true, env });
  await runScript(sim, [SCENE, "@advance 29"]);
  assert.equal(texts(sim).filter((t) => t.startsWith("Reminder")).length, 0, "alerts are still off");
  await runScript(sim, ["ALERTS ON", "@advance 1"]);
  assert.equal(texts(sim).filter((t) => t.startsWith("Reminder")).length, 1, "past the timer");
  assert.equal(texts(sim).at(-1), reminderText());
  await runScript(sim, ["@advance 500", "@advance 500"]);
  assert.equal(texts(sim).filter((t) => t.startsWith("Reminder")).length, 1, "never a second one");
  assert.deepEqual(alertRows(sim), [{ kind: "reach_out_reminder", simulated: 1, property_id: null }]);
});

test("reminder: the default timer is 1440 minutes, and a drafted reach-out cancels it", async () => {
  const sim = createSim({ alerts: true, env: { PHOTON_ALERTS_REAL: "1" } });
  await runScript(sim, [SCENE, "ALERTS ON", "@advance 1439"]);
  assert.equal(alertRows(sim).length, 0);
  await runScript(sim, ["@advance 1"]);
  assert.equal(alertRows(sim).length, 1, "due at exactly 1440");
  const drafted = createSim({ alerts: true, env: { PHOTON_ALERTS_REAL: "1" } });
  await runScript(drafted, [SCENE, "ALERTS ON", "draft 2", "YES", "@advance 2000"]);
  assert.equal(drafted.store.db.prepare("SELECT COUNT(*) AS n FROM reach_outs").get().n, 1);
  assert.equal(alertRows(drafted).length, 0, "no reminder once a note was drafted");
  const declined = createSim({ alerts: true, env: { PHOTON_ALERTS_REAL: "1" } });
  await runScript(declined, [SCENE, "ALERTS ON", "draft 2", "NO", "@advance 2000"]);
  assert.equal(alertRows(declined).length, 1, "NO drafts nothing, so the reminder still comes");
});

test("2-checks rule: an alert only on the second consecutive disagreeing check, then again when it flips back", async () => {
  const sim = createSim({ alerts: true, env: { ...live, PRICE_CHECK_MIN: "1" }, rentSource: script(15, 25, 25, 25, 15, 15) });
  await runScript(sim, [SCENE, "ALERTS ON", "@maxrent 20", "@rent 1 15"]);
  const states = [];
  for (const step of [1, 2, 3, 4, 5, 6]) {
    await sim.advance(1);
    const row = sim.store.getPriceState(1, "mock-p3");
    states.push([priceTexts(sim).length, row.state, row.streak]);
  }
  assert.deepEqual(states, [
    [0, "within", 0],   // first check sets the state, no alert
    [0, "within", 1],   // first disagreement: streak 1, no alert
    [1, "above", 0],    // second in a row: alert, state flips
    [1, "above", 0],    // agrees with the new state
    [1, "above", 1],    // disagrees once
    [2, "within", 0],   // twice in a row: back-within alert
  ]);
  assert.deepEqual(alertRows(sim).map((r) => r.kind), ["price_above", "price_back_within"]);
  assert.ok(alertRows(sim).every((r) => r.simulated === 1 && r.property_id === "mock-p3"));
  assert.ok(sim.store.db.prepare("SELECT last_simulated FROM price_state").all().every((r) => r.last_simulated === 1));
});

test("2-checks rule: a single blip that reverts never alerts", async () => {
  const sim = createSim({ alerts: true, env: { ...live, PRICE_CHECK_MIN: "1" }, rentSource: script(15, 25, 15, 25, 15, 25, 15) });
  await runScript(sim, [SCENE, "ALERTS ON", "@maxrent 20", "@rent 1 15"]);
  for (let i = 0; i < 7; i++) await sim.advance(1);
  assert.equal(priceTexts(sim).length, 0);
  assert.equal(alertRows(sim).length, 0);
});

test("every price alert is labelled SIMULATED, says what it compares, and notes multifamily ground-floor retail rents", async () => {
  const sim = createSim({ alerts: true, env: { ...live, PRICE_CHECK_MIN: "1" }, rentSource: script(15, 25, 25) });
  await runScript(sim, [SCENE, "ALERTS ON", "@maxrent 20", "@rent 1 15"]);
  sim.store.db.prepare("UPDATE picks SET property_type = 'Multifamily' WHERE rank = 1").run();
  sim.store.db.prepare("UPDATE searches SET rent_units = '$/SF/yr'").run();
  for (let i = 0; i < 3; i++) await sim.advance(1);
  const [alert] = priceTexts(sim);
  assert.ok(alert.startsWith("SIMULATED price update (demo):"));
  assert.equal(PRICE_LABEL, "SIMULATED price update (demo):");
  assert.match(alert, /300 Placeholder Blvd \(FAKE\) is now above your max rent \(25 \$\/SF\/yr against 20 \$\/SF\/yr\)\./);
  assert.match(alert, /Multifamily rents here are ground-floor retail rents\./);
  const plain = priceAlertText({ address: "A", property_type: "Industrial" }, { rent: 9, maxRent: 10, rentUnits: null, verdict: "within" });
  assert.equal(plain, "SIMULATED price update (demo): A is now back within your max rent (9 against 10). Reply ALERTS OFF to stop.");
});

test("the default simulated source cycles the saved rent so a demo can cross the line", async () => {
  assert.deepEqual([0, 1, 2, 3, 4, 5].map((n) => simulatedRentSource()({ rent_ref: 20 }, { checkNo: n })), [20, 25, 25, 16, 16, 20]);
  assert.equal(simulatedRentSource()({ rent_ref: null }, { checkNo: 1 }), null);
  const sim = createSim({ alerts: true, env: { ...live, PRICE_CHECK_MIN: "1" } });
  await runScript(sim, [SCENE, "ALERTS ON", "@maxrent 22", "@rent 1 20"]);
  for (let i = 0; i < 3; i++) await sim.advance(1);
  assert.equal(priceTexts(sim).length, 1);
});

test("NULL handling: no alert when rent_ref or max_rent is NULL, and nothing is written for them", async () => {
  const noMax = createSim({ alerts: true, env: { ...live, PRICE_CHECK_MIN: "1" }, rentSource: script(15, 99, 99, 15, 99, 99) });
  await runScript(noMax, [SCENE, "ALERTS ON", "@rent 1 15"]);           // max_rent stays NULL
  for (let i = 0; i < 6; i++) await noMax.advance(1);
  assert.equal(priceTexts(noMax).length, 0);
  assert.equal(noMax.store.db.prepare("SELECT COUNT(*) AS n FROM price_state").get().n, 0);
  const noRent = createSim({ alerts: true, env: { ...live, PRICE_CHECK_MIN: "1" }, rentSource: script(15, 99, 99, 15, 99, 99) });
  await runScript(noRent, [SCENE, "ALERTS ON", "@maxrent 20"]);          // rent_ref stays NULL
  for (let i = 0; i < 6; i++) await noRent.advance(1);
  assert.equal(priceTexts(noRent).length, 0);
  assert.equal(noRent.store.db.prepare("SELECT COUNT(*) AS n FROM price_state").get().n, 0);
  const dbNullRent = noRent.store.db.prepare("SELECT rent_ref, drive_min FROM picks").all();
  assert.ok(dbNullRent.every((r) => r.rent_ref === null && r.drive_min === null), "unknown stays NULL, never 0");
});

test("the 8-message cap counts alerts: the results flow, the opt-in reply and each alert share one budget", async () => {
  const sim = createSim({ alerts: true, env: { ...live, PRICE_CHECK_MIN: "1", REMINDER_AFTER_MIN: "1" }, rentSource: script(15, 25, 25, 15, 15) });
  await runScript(sim, [SCENE, "ALERTS ON", "@maxrent 20", "@rent 1 15"]);
  const spent = () => sim.store.latestSearch(SENDER_HASH).outbound_count;
  assert.equal(spent(), 3, "confirmation, results, opt-in reply");
  sim.store.setOutboundCount(1, 6);
  for (let i = 0; i < 6; i++) await sim.advance(1);
  const alerts = texts(sim).filter((t) => t.startsWith("Reminder") || t.startsWith(PRICE_LABEL));
  assert.equal(alerts.length, 2, "6 + reminder + one price alert = 8, then nothing more");
  assert.equal(spent(), BUDGET);
  assert.ok(sim.printed.some((l) => /held back by the 8-message cap/.test(l)));
  const unknown = createSim({ alerts: true, env: { ...live, REMINDER_AFTER_MIN: "1" } });
  await runScript(unknown, [SCENE, "ALERTS ON"]);
  unknown.store.db.prepare("UPDATE searches SET outbound_count = NULL").run();
  await unknown.advance(5);
  assert.equal(texts(unknown).filter((t) => t.startsWith("Reminder")).length, 0, "an unknown count fails closed");
});

test("alerts go only to allowlisted senders", async () => {
  const sim = createSim({ alerts: true, env: { ...live, REMINDER_AFTER_MIN: "1" } });
  const stranger = seedSearch(sim.store, { hash: hashSender("+15550100999"), space: "space-stranger", createdAt: T0 - 600 * MIN });
  assert.ok(stranger > 0);
  await sim.advance(5);
  assert.equal(sim.outbound.length, 0);
  assert.equal(sim.store.db.prepare("SELECT COUNT(*) AS n FROM alerts").get().n, 0);
});

test("dry run is the default: counts only, nothing sent or recorded, and no message text in the log", async () => {
  const sim = createSim({ alerts: true, env: { REMINDER_AFTER_MIN: "1", PRICE_CHECK_MIN: "1" }, rentSource: script(15, 25, 25) });
  await runScript(sim, [SCENE, "ALERTS ON", "@maxrent 20", "@rent 1 15"]);
  const before = sim.outbound.length;
  for (let i = 0; i < 3; i++) await sim.advance(2);
  assert.equal(sim.outbound.length, before, "nothing sent");
  assert.equal(sim.store.db.prepare("SELECT COUNT(*) AS n FROM alerts").get().n, 0);
  assert.equal(sim.store.db.prepare("SELECT COUNT(*) AS n FROM price_state").get().n, 0, "dry-run state is kept in memory only");
  const log = sim.printed.filter((l) => l.includes("[alerts]")).join("\n");
  assert.match(log, /alerts dry run, would send: 1 reminder\(s\), 0 price alert\(s\); nothing was sent/);
  assert.match(log, /would send: 1 reminder\(s\), 1 price alert\(s\)/, "the 2-checks rule runs in memory");
  assert.ok(!/SIMULATED|Placeholder|Reminder \(demo\)/.test(log), "counts only, never message text");
});

test("real sends need PHOTON_ALERTS_REAL=1 and the mock-only guard, and PHOTON_DRY_RUN wins", async () => {
  const sent = [], logs = [];
  const store = openStore(":memory:");
  seedSearch(store, { createdAt: T0 - 2000 * MIN });
  const send = async (space, key, text) => { sent.push([space, key, text]); return "sent"; };
  const make = (extra, env = { PHOTON_ALERTS_REAL: "1" }) => createAlerts({ store, allowed: new Set(["5550100100"]), env, now: () => T0, log: (l) => logs.push(l), ...extra });
  assert.equal((await make({ guard: async () => { throw new Error("live"); } }).tick({ send })).reminders, 0);
  assert.deepEqual(logs, ["alerts paused: the API is not in mock mode"]);
  assert.equal(sent.length, 0);
  assert.equal((await make({}, {}).tick({ send })).reminders, 1, "counted in a dry run");
  assert.equal(sent.length, 0, "but not sent");
  assert.equal((await make({ dryRun: true }).tick({ send })).reminders, 1);
  assert.equal(sent.length, 0, "PHOTON_DRY_RUN wins");
  assert.equal((await make({}).tick({ send })).reminders, 1);
  assert.equal(sent.length, 1, "now it is real");
  assert.deepEqual([sent[0][0], sent[0][1]], ["space-1", "typecast-alert:reminder:1"]);
});

test("a failed or unroutable alert is not recorded, so it can be tried again", async () => {
  const store = openStore(":memory:");
  seedSearch(store, { createdAt: T0 - 2000 * MIN });
  const alerts = createAlerts({ store, allowed: new Set(["5550100100"]), env: { PHOTON_ALERTS_REAL: "1" }, now: () => T0, log: () => {} });
  assert.equal((await alerts.tick({ send: async () => "no_route" })).noRoute, 1);
  assert.equal((await alerts.tick({ send: async () => "failed" })).failed, 1);
  assert.equal(store.db.prepare("SELECT COUNT(*) AS n FROM alerts").get().n, 0);
  assert.equal((await alerts.tick({ send: async () => "sent" })).reminders, 1);
  assert.equal((await alerts.tick({ send: async () => "sent" })).reminders, 0, "recorded once");
  assert.equal(store.db.prepare("SELECT COUNT(*) AS n FROM alerts").get().n, 1);
});

test("golden transcript: search, ALERTS ON, a reminder and a 2-checks price alert, within the cap", async () => {
  const sim = createSim({ alerts: true, env: { ...live, PHOTON_VIEWER_URL: "http://192.0.2.10:8000", REMINDER_AFTER_MIN: "60", PRICE_CHECK_MIN: "30" }, rentSource: script(15, 25, 25) });
  await runScript(sim, [
    "need a warehouse in LA, day, no exterior, 2 trucks and 10 cars", "@maxrent 20", "@rent 1 15",
    "ALERTS ON", "@advance 31", "@advance 31", "@advance 31", "@advance 31",
  ]);
  const out = texts(sim);
  assert.match(out[0], /^Searching now \(MOCK\)\./);
  assert.match(out[1], /^MOCK · 3 interior picks/);
  assert.match(out[2], /^http:\/\/192\.0\.2\.10:8000\/app\//);
  assert.match(out[3], /^Alerts are ON for your latest search\./);
  assert.equal(out[4].startsWith("Reminder (demo):"), true, "first tick past 60 minutes");
  assert.match(out[5], /^SIMULATED price update \(demo\): 300 Placeholder Blvd \(FAKE\) is now above your max rent \(25 against 20\)\./);
  assert.equal(out.length, 6);
  assert.equal(sim.store.latestSearch(SENDER_HASH).outbound_count, 6, "4 flow bubbles + reminder + alert");
  assert.ok(sim.store.latestSearch(SENDER_HASH).outbound_count <= BUDGET);
  assert.ok(!out.some((t) => /delivered/i.test(t)));
  assert.deepEqual(alertRows(sim).map((r) => [r.kind, r.simulated]), [["reach_out_reminder", 1], ["price_above", 1]]);
});
