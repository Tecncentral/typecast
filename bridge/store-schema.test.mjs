import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { tmpdir } from "node:os";
import path from "node:path";
import { openStore, hashSender, SCHEMA_VERSION } from "./store.mjs";

const NUMBER = "+15550100100";
const SALT = "test-salt";
const H = hashSender(NUMBER, SALT);
const ELEVEN = ["users", "briefs", "searches", "auth_tokens", "otp_codes", "conversations", "messages", "picks", "reach_outs", "price_state", "alerts"];
const tableNames = (db) => db.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name").all().map((r) => r.name);
const tempFile = () => path.join(mkdtempSync(path.join(tmpdir(), "typecast-schema-")), "t.db");
/** A user, a conversation, a brief and a search, ready for the other tables. */
function seed(s) {
  const userId = s.upsertUser(H);
  const conversationId = s.upsertConversation("space-opaque-id", userId);
  const briefId = s.saveBrief({ userId, channel: "imessage", interiorScene: "INT. DINER, DAY. Houston.", city: "HOU" });
  const searchId = s.saveSearch({ briefId, userId, threadId: "thread-1", sourceMode: "mock" });
  return { userId, conversationId, briefId, searchId };
}

test("migration on an empty database creates all 11 tables, settings, the index, foreign keys and WAL", () => {
  const file = tempFile();
  const s = openStore(file);
  assert.deepEqual(tableNames(s.db), [...ELEVEN, "settings"].sort());
  assert.equal(s.db.prepare("PRAGMA user_version").get().user_version, SCHEMA_VERSION);
  assert.equal(SCHEMA_VERSION, 2);
  assert.equal(s.db.prepare("PRAGMA foreign_keys").get().foreign_keys, 1);
  assert.equal(s.db.prepare("PRAGMA journal_mode").get().journal_mode, "wal");
  const index = s.db.prepare("SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'one_reminder_per_search'").get();
  assert.match(index.sql, /UNIQUE INDEX one_reminder_per_search ON alerts\(search_id\) WHERE kind = 'reach_out_reminder'/);
  s.close();
});

test("rerunning the migration changes nothing and keeps the data", () => {
  const file = tempFile();
  const first = openStore(file);
  const ids = seed(first);
  first.saveSettings(H, { city: "LA", trucks: 2 });
  const before = tableNames(first.db);
  first.close();
  for (let i = 0; i < 2; i++) {
    const again = openStore(file);
    assert.deepEqual(tableNames(again.db), before);
    assert.equal(again.db.prepare("PRAGMA user_version").get().user_version, 2);
    assert.equal(again.upsertUser(H), ids.userId, "same user, no duplicate");
    assert.equal(again.db.prepare("SELECT COUNT(*) AS n FROM users").get().n, 1);
    assert.equal(again.getSettings(H).trucks, 2, "the settings table and its functions still work");
    again.close();
  }
});

test("a database from before the migration (settings only) upgrades without losing its rows", () => {
  const file = tempFile();
  const old = new DatabaseSync(file);
  old.exec("CREATE TABLE settings (sender_hash TEXT PRIMARY KEY, city TEXT, trucks INTEGER, cars INTEGER, updated_at TEXT)");
  old.prepare("INSERT INTO settings VALUES (?, 'HOU', 4, NULL, '2026-11-15T00:00:00Z')").run(H);
  old.close();
  const s = openStore(file);
  assert.deepEqual([s.getSettings(H).city, s.getSettings(H).trucks, s.getSettings(H).cars], ["HOU", 4, null]);
  assert.ok(tableNames(s.db).includes("alerts"));
  s.close();
});

test("a duplicate photon_msg_id is ignored and recordMessage returns false", () => {
  const s = openStore(":memory:");
  const { conversationId } = seed(s);
  assert.equal(s.recordMessage(conversationId, { photonMsgId: "m-1", direction: "in", kind: "text" }), true);
  assert.equal(s.recordMessage(conversationId, { photonMsgId: "m-1", direction: "in", kind: "text" }), false);
  assert.equal(s.db.prepare("SELECT COUNT(*) AS n FROM messages").get().n, 1);
  assert.equal(s.recordMessage(conversationId, { direction: "out", kind: "text" }), true, "messages without an id are all kept");
  assert.equal(s.recordMessage(conversationId, { direction: "out", kind: "link" }), true);
  assert.equal(s.db.prepare("SELECT COUNT(*) AS n FROM messages").get().n, 3);
  assert.throws(() => s.recordMessage(conversationId, { photonMsgId: "m-2", direction: "sideways", kind: "text" }), /direction/);
  assert.throws(() => s.recordMessage(999, { photonMsgId: "m-3", direction: "in", kind: "text" }), /FOREIGN KEY/i);
});

test("only one reach_out_reminder per search; other alerts and other searches are not blocked", () => {
  const s = openStore(":memory:");
  const { briefId, userId, searchId } = seed(s);
  assert.equal(s.recordAlert(searchId, { kind: "reach_out_reminder" }), true);
  assert.equal(s.recordAlert(searchId, { kind: "reach_out_reminder" }), false);
  assert.equal(s.recordAlert(searchId, { kind: "reach_out_reminder", simulated: true }), false);
  assert.equal(s.recordAlert(searchId, { kind: "price_above", propertyId: "p1" }), true);
  assert.equal(s.recordAlert(searchId, { kind: "price_above", propertyId: "p1" }), true, "price alerts are not limited by this index");
  const other = s.saveSearch({ briefId, userId, threadId: "thread-2", sourceMode: "mock" });
  assert.equal(s.recordAlert(other, { kind: "reach_out_reminder" }), true);
  assert.equal(s.db.prepare("SELECT COUNT(*) AS n FROM alerts WHERE kind = 'reach_out_reminder'").get().n, 2);
  assert.throws(() => s.recordAlert(searchId, { kind: "spam" }), /kind/);
  assert.throws(() => s.recordAlert(999, { kind: "price_above" }), /FOREIGN KEY/i);
});

test("unknown values stay NULL, never 0", () => {
  const s = openStore(":memory:");
  const userId = s.upsertUser(H);
  const briefId = s.saveBrief({ channel: "web" });
  const brief = s.db.prepare("SELECT * FROM briefs WHERE id = ?").get(briefId);
  for (const col of ["user_id", "interior_scene", "exterior_query", "city", "trucks", "crew_cars"]) assert.equal(brief[col], null, col);
  const searchId = s.saveSearch({ briefId, threadId: "t", sourceMode: "mock" });
  const search = s.db.prepare("SELECT * FROM searches WHERE id = ?").get(searchId);
  for (const col of ["user_id", "max_rent", "rent_units", "base_label", "base_lat", "base_lon", "max_drive_min"]) assert.equal(search[col], null, col);
  assert.equal(search.alerts_on, 0, "alerts_on is a real yes/no column and defaults to off");
  s.savePicks(searchId, [{ rank: 1, propertyId: "p1", address: "1 Test St (FAKE)" }]);
  const pick = s.db.prepare("SELECT * FROM picks").get();
  for (const col of ["property_type", "rent_ref", "rent_tier", "drive_min"]) assert.equal(pick[col], null, col);
  s.saveSettings(H, { city: "LA" });
  assert.equal(s.getSettings(H).trucks, null);
  assert.equal(s.db.prepare("SELECT verified_at FROM users WHERE id = ?").get(userId).verified_at, null);
  const known = s.saveBrief({ channel: "web", trucks: 0 });
  assert.equal(s.db.prepare("SELECT trucks FROM briefs WHERE id = ?").get(known).trucks, 0, "a stated 0 is kept; only unknown is NULL");
  assert.throws(() => s.saveBrief({ channel: "web", trucks: -1 }), /whole number/);
});

test("the schema CHECKs and foreign keys are enforced", () => {
  const s = openStore(":memory:");
  const { briefId, userId } = seed(s);
  assert.throws(() => s.saveBrief({ channel: "sms" }), /channel/);
  assert.throws(() => s.saveBrief({ channel: "web", city: "Austin" }), /city/);
  assert.throws(() => s.db.prepare("INSERT INTO briefs (channel, city) VALUES ('web', 'Austin')").run(), /CHECK/i);
  assert.throws(() => s.saveSearch({ briefId, threadId: "x", sourceMode: "maybe" }), /sourceMode/);
  assert.throws(() => s.saveSearch({ briefId: 999, threadId: "y", sourceMode: "mock" }), /FOREIGN KEY/i);
  assert.throws(() => s.saveSearch({ briefId, userId, threadId: "thread-1", sourceMode: "mock" }), /UNIQUE/i, "thread_id is unique");
  assert.throws(() => s.upsertConversation("space-x", 999), /FOREIGN KEY/i);
  assert.throws(() => s.upsertUser(NUMBER), /SHA-256/, "a raw phone number is refused");
});

test("savePicks replaces a snapshot in one transaction", () => {
  const s = openStore(":memory:");
  const { searchId } = seed(s);
  const pick = (rank, id) => ({ rank, propertyId: id, address: `${id} St (FAKE)`, propertyType: "Industrial", rentRef: 12.5, rentTier: "A", driveMin: 18.5 });
  assert.equal(s.savePicks(searchId, [pick(1, "a"), pick(2, "b"), pick(3, "c")]), 3);
  assert.equal(s.savePicks(searchId, [pick(1, "z")]), 1);
  assert.deepEqual(s.db.prepare("SELECT rank, property_id FROM picks ORDER BY rank").all().map((r) => [r.rank, r.property_id]), [[1, "z"], [2, "b"], [3, "c"]]);
  assert.throws(() => s.savePicks(searchId, [pick(4, "d"), { rank: 5 }]), /propertyId and address/);
  assert.equal(s.db.prepare("SELECT COUNT(*) AS n FROM picks").get().n, 3, "a failed batch writes nothing");
});

test("no raw phone number in the database file, and no column that could hold message text", () => {
  const file = tempFile();
  const s = openStore(file);
  const { conversationId, searchId } = seed(s);
  s.saveSettings(H, { city: "LA", trucks: 3, cars: 30 });
  s.recordMessage(conversationId, { photonMsgId: "msg-1", direction: "in", kind: "text" });
  s.savePicks(searchId, [{ rank: 1, propertyId: "p1", address: "1 Test St (FAKE)" }]);
  s.recordAlert(searchId, { kind: "reach_out_reminder", simulated: true });
  s.db.exec("PRAGMA wal_checkpoint(TRUNCATE)");
  const columns = tableNames(s.db).flatMap((t) => s.db.prepare(`PRAGMA table_info(${t})`).all().map((c) => c.name));
  for (const banned of ["phone", "number", "text", "body", "content", "message"]) assert.ok(!columns.includes(banned), `no ${banned} column`);
  s.close();
  for (const f of [file, `${file}-wal`].filter(existsSync)) {
    const bytes = readFileSync(f).toString("latin1");
    assert.ok(!bytes.includes("5550100100") && !bytes.includes(NUMBER), `${path.basename(f)} has no phone number`);
  }
  assert.ok(readFileSync(file).toString("latin1").includes(H), "the salted hash is what is stored");
  assert.notEqual(H, hashSender(NUMBER, ""), "the salt changes the hash");
});
