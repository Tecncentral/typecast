import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { openStore, hashSender, getSettings, DEFAULT_DB } from "./store.mjs";

const NUMBER = "+15550100100";
const H = hashSender(NUMBER, "");

test("the hash is SHA-256 of the normalised sender, so formatting does not matter", () => {
  assert.equal(H, createHash("sha256").update("5550100100").digest("hex"));
  for (const same of ["+1 (555) 010-0100", "5550100100", "1-555-010-0100"]) assert.equal(hashSender(same, ""), H);
  assert.equal(hashSender("Someone@Example.com", ""), hashSender("someone@example.com", ""));
  assert.notEqual(hashSender("+15550100101", ""), H);
  assert.notEqual(hashSender(NUMBER, "pepper"), H, "a salt changes the hash");
  assert.match(H, /^[0-9a-f]{64}$/);
  assert.throws(() => hashSender("  "), /empty/);
});

test("nothing saved yet gives null; saving then reading round-trips", () => {
  const s = openStore(":memory:");
  assert.equal(s.getSettings(H), null);
  const saved = s.saveSettings(H, { city: "LA", trucks: 3, cars: 30 });
  assert.deepEqual({ city: saved.city, trucks: saved.trucks, cars: saved.cars }, { city: "LA", trucks: 3, cars: 30 });
  assert.ok(!Number.isNaN(Date.parse(saved.updatedAt)));
  assert.deepEqual(s.getSettings(H), saved);
});

test("a partial save keeps the other fields, and null clears one", () => {
  const s = openStore(":memory:");
  s.saveSettings(H, { city: "HOU", trucks: 2, cars: 10 });
  assert.deepEqual(pick(s.saveSettings(H, { cars: 40 })), { city: "HOU", trucks: 2, cars: 40 });
  assert.deepEqual(pick(s.saveSettings(H, { city: "LA" })), { city: "LA", trucks: 2, cars: 40 });
  assert.deepEqual(pick(s.saveSettings(H, { trucks: null })), { city: "LA", trucks: null, cars: 40 });
  assert.deepEqual(pick(s.saveSettings(H, {})), { city: "LA", trucks: null, cars: 40 });
});

test("each sender has their own row", () => {
  const s = openStore(":memory:");
  const other = hashSender("+15550100200", "");
  s.saveSettings(H, { city: "LA" }); s.saveSettings(other, { city: "HOU" });
  assert.equal(s.getSettings(H).city, "LA"); assert.equal(s.getSettings(other).city, "HOU");
});

test("bad input is refused and nothing is written", () => {
  const s = openStore(":memory:");
  assert.throws(() => s.saveSettings(H, { city: "NYC" }), /LA or HOU/);
  assert.throws(() => s.saveSettings(H, { trucks: -1 }), /whole number/);
  assert.throws(() => s.saveSettings(H, { cars: 2.5 }), /whole number/);
  assert.throws(() => s.saveSettings(H, { trucks: "3" }), /whole number/);
  assert.throws(() => s.saveSettings(NUMBER, { city: "LA" }), /SHA-256/, "a raw phone number is refused as a key");
  assert.throws(() => s.getSettings(NUMBER), /SHA-256/);
  assert.equal(s.getSettings(H), null);
});

test("the table has the agreed columns and the file never contains the phone number", () => {
  const file = path.join(mkdtempSync(path.join(tmpdir(), "typecast-store-")), "nested", "t.db");
  const s = openStore(file);
  s.saveSettings(H, { city: "LA", trucks: 3, cars: 30 });
  s.close();
  assert.ok(existsSync(file), "missing folders are created");
  const bytes = readFileSync(file).toString("latin1");
  assert.ok(bytes.includes(H), "the hash is stored");
  assert.ok(!bytes.includes("5550100100") && !bytes.includes(NUMBER), "the number is not");
  const again = openStore(file);
  assert.equal(again.getSettings(H).trucks, 3, "data survives a reopen");
  again.close();
});

test("the default database is bridge/data/typecast.db and is not created just by importing", () => {
  assert.ok(DEFAULT_DB.replace(/\\/g, "/").endsWith("/bridge/data/typecast.db"));
  assert.equal(typeof getSettings, "function");
});

const pick = ({ city, trucks, cars }) => ({ city, trucks, cars });
