// Tiny store for saved settings, keyed by a SHA-256 hash of the sender. Built-in node:sqlite, no packages.
// Never stores a phone number or email: only the hash. Not wired into the runner.
import { DatabaseSync } from "node:sqlite";
import { createHash } from "node:crypto";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const DEFAULT_DB = path.join(path.dirname(fileURLToPath(import.meta.url)), "data", "typecast.db");
const CITIES = new Set(["LA", "HOU"]);
const MAX_COUNT = 1000;

/** Same matching rule as the allowlist: emails in lower case, phone numbers by digits without a leading US 1. */
function normalize(handle) {
  const v = String(handle ?? "").trim().toLowerCase();
  if (v.includes("@")) return v;
  const digits = v.replace(/\D/g, "");
  return digits.length === 11 && digits.startsWith("1") ? digits.slice(1) : digits;
}

/** SHA-256 hex of the normalised sender. An optional salt (TYPECAST_HASH_SALT) makes the hash harder to reverse. */
export function hashSender(handle, salt = process.env.TYPECAST_HASH_SALT ?? "") {
  const id = normalize(handle);
  if (!id) throw new Error("sender is empty");
  return createHash("sha256").update(`${salt}${id}`).digest("hex");
}

const isHash = (h) => typeof h === "string" && /^[0-9a-f]{64}$/.test(h);
const isCount = (n) => Number.isInteger(n) && n >= 0 && n <= MAX_COUNT;

// Versioned migrations, tracked with PRAGMA user_version. Version 2 is schema.sql (11 tables), unchanged:
// no raw phone numbers (sender_hash only), unknown values stay NULL, no message text, tokens and codes as hashes.
const MIGRATIONS = [
  { version: 1, sql: `CREATE TABLE IF NOT EXISTS settings (
    sender_hash TEXT PRIMARY KEY, city TEXT, trucks INTEGER, cars INTEGER, updated_at TEXT
  )` },
  { version: 2, sql: `
CREATE TABLE users (
  id            INTEGER PRIMARY KEY,
  sender_hash   TEXT NOT NULL UNIQUE,
  verified_at   TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE briefs (
  id             INTEGER PRIMARY KEY,
  user_id        INTEGER REFERENCES users(id),
  channel        TEXT NOT NULL CHECK (channel IN ('imessage','web')),
  interior_scene TEXT,
  exterior_query TEXT,
  city           TEXT CHECK (city IN ('Los Angeles','Houston')),
  trucks         INTEGER,
  crew_cars      INTEGER,
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE searches (
  id             INTEGER PRIMARY KEY,
  brief_id       INTEGER NOT NULL REFERENCES briefs(id),
  user_id        INTEGER REFERENCES users(id),
  thread_id      TEXT NOT NULL UNIQUE,
  source_mode    TEXT NOT NULL CHECK (source_mode IN ('mock','live')),
  max_rent       REAL,
  rent_units     TEXT,
  base_label     TEXT,
  base_lat       REAL,
  base_lon       REAL,
  max_drive_min  INTEGER,
  alerts_on      INTEGER NOT NULL DEFAULT 0,
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE auth_tokens (
  token_hash    TEXT PRIMARY KEY,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  kind          TEXT NOT NULL CHECK (kind IN ('link','session')),
  search_id     INTEGER REFERENCES searches(id),
  expires_at    TEXT NOT NULL,
  used_at       TEXT
);
CREATE TABLE otp_codes (
  id            INTEGER PRIMARY KEY,
  sender_hash   TEXT NOT NULL,
  code_hash     TEXT NOT NULL,
  expires_at    TEXT NOT NULL,
  attempts      INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE conversations (
  id                INTEGER PRIMARY KEY,
  photon_space      TEXT NOT NULL UNIQUE,
  user_id           INTEGER NOT NULL REFERENCES users(id),
  stage             TEXT NOT NULL DEFAULT 'intake' CHECK (stage IN ('intake','searching','results','drafting')),
  intake_json       TEXT NOT NULL DEFAULT '{}',
  current_search_id INTEGER REFERENCES searches(id),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE messages (
  id              INTEGER PRIMARY KEY,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id),
  photon_msg_id   TEXT UNIQUE,
  direction       TEXT NOT NULL CHECK (direction IN ('in','out')),
  kind            TEXT NOT NULL CHECK (kind IN ('text','image','link','other')),
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE picks (
  search_id     INTEGER NOT NULL REFERENCES searches(id),
  rank          INTEGER NOT NULL,
  property_id   TEXT NOT NULL,
  address       TEXT NOT NULL,
  property_type TEXT,
  rent_ref      REAL,
  rent_tier     TEXT,
  drive_min     REAL,
  PRIMARY KEY (search_id, rank)
);
CREATE TABLE reach_outs (
  search_id     INTEGER NOT NULL REFERENCES searches(id),
  rank          INTEGER NOT NULL,
  drafted_at    TEXT NOT NULL,
  PRIMARY KEY (search_id, rank)
);
CREATE TABLE price_state (
  search_id      INTEGER NOT NULL REFERENCES searches(id),
  property_id    TEXT NOT NULL,
  state          TEXT NOT NULL CHECK (state IN ('within','above')),
  streak         INTEGER NOT NULL DEFAULT 0,
  last_rent      REAL,
  last_simulated INTEGER NOT NULL DEFAULT 0,
  checked_at     TEXT NOT NULL,
  PRIMARY KEY (search_id, property_id)
);
CREATE TABLE alerts (
  id            INTEGER PRIMARY KEY,
  search_id     INTEGER NOT NULL REFERENCES searches(id),
  property_id   TEXT,
  kind          TEXT NOT NULL CHECK (kind IN ('reach_out_reminder','price_above','price_back_within')),
  simulated     INTEGER NOT NULL DEFAULT 0,
  sent_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX one_reminder_per_search ON alerts(search_id) WHERE kind = 'reach_out_reminder';` },
];
export const SCHEMA_VERSION = MIGRATIONS.at(-1).version;

/** Apply every migration newer than the database's user_version, each in its own transaction. Safe to rerun. */
function migrate(db) {
  const current = db.prepare("PRAGMA user_version").get().user_version;
  for (const m of MIGRATIONS.filter((x) => x.version > current)) {
    db.exec("BEGIN");
    try { db.exec(m.sql); db.exec(`PRAGMA user_version = ${m.version}`); db.exec("COMMIT"); }
    catch (e) { db.exec("ROLLBACK"); throw e; }
  }
}

const CITY_NAMES = { LA: "Los Angeles", HOU: "Houston", "Los Angeles": "Los Angeles", Houston: "Houston" };
/** Unknown stays NULL, never 0. */
const orNull = (v) => (v === undefined ? null : v);
function intOrNull(v, name) {
  if (v === undefined || v === null) return null;
  if (!Number.isInteger(v) || v < 0) throw new Error(`${name} must be a whole number of 0 or more, or null`);
  return v;
}
function realOrNull(v, name) {
  if (v === undefined || v === null) return null;
  if (typeof v !== "number" || !Number.isFinite(v)) throw new Error(`${name} must be a number or null`);
  return v;
}
function oneOf(v, allowed, name) {
  if (!allowed.includes(v)) throw new Error(`${name} must be one of ${allowed.join(", ")}`);
  return v;
}
const needId = (v, name) => { if (!Number.isInteger(v) || v < 1) throw new Error(`${name} must be a row id`); return v; };

export function openStore(file = DEFAULT_DB) {
  if (file !== ":memory:") mkdirSync(path.dirname(file), { recursive: true });
  const db = new DatabaseSync(file);
  db.exec("PRAGMA foreign_keys = ON");
  db.exec("PRAGMA journal_mode = WAL");
  migrate(db);
  const get = db.prepare("SELECT city, trucks, cars, updated_at FROM settings WHERE sender_hash = ?");
  const upsert = db.prepare(`INSERT INTO settings (sender_hash, city, trucks, cars, updated_at) VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(sender_hash) DO UPDATE SET
      city = CASE WHEN ? THEN excluded.city ELSE settings.city END,
      trucks = CASE WHEN ? THEN excluded.trucks ELSE settings.trucks END,
      cars = CASE WHEN ? THEN excluded.cars ELSE settings.cars END,
      updated_at = excluded.updated_at`);

  /** { city, trucks, cars, updatedAt } or null when nothing is saved for this sender. */
  function getSettings(senderHash) {
    if (!isHash(senderHash)) throw new Error("senderHash must be a SHA-256 hex string");
    const row = get.get(senderHash);
    return row ? { city: row.city, trucks: row.trucks, cars: row.cars, updatedAt: row.updated_at } : null;
  }

  /** Save only the fields given (city LA|HOU, trucks, cars); others keep their value. null clears a field. */
  function saveSettings(senderHash, fields = {}) {
    if (!isHash(senderHash)) throw new Error("senderHash must be a SHA-256 hex string");
    const has = (k) => Object.hasOwn(fields, k);
    const { city = null, trucks = null, cars = null } = fields;
    if (has("city") && city !== null && !CITIES.has(city)) throw new Error("city must be LA or HOU");
    for (const [k, v] of [["trucks", trucks], ["cars", cars]]) if (has(k) && v !== null && !isCount(v)) throw new Error(`${k} must be a whole number from 0 to ${MAX_COUNT}`);
    upsert.run(senderHash, city, trucks, cars, new Date().toISOString(), Number(has("city")), Number(has("trucks")), Number(has("cars")));
    return getSettings(senderHash);
  }

  const tx = (fn) => {
    db.exec("BEGIN");
    try { const out = fn(); db.exec("COMMIT"); return out; } catch (e) { db.exec("ROLLBACK"); throw e; }
  };

  /** Row id for this sender hash, creating the user on first sight. Takes the hash, never a phone number. */
  function upsertUser(senderHash) {
    if (!isHash(senderHash)) throw new Error("senderHash must be a SHA-256 hex string");
    db.prepare("INSERT INTO users (sender_hash) VALUES (?) ON CONFLICT(sender_hash) DO NOTHING").run(senderHash);
    return db.prepare("SELECT id FROM users WHERE sender_hash = ?").get(senderHash).id;
  }

  /** Row id for this Photon space, creating it for the user on first sight. */
  function upsertConversation(photonSpace, userId) {
    if (!photonSpace || typeof photonSpace !== "string") throw new Error("photonSpace is required");
    db.prepare(`INSERT INTO conversations (photon_space, user_id) VALUES (?, ?)
      ON CONFLICT(photon_space) DO UPDATE SET updated_at = datetime('now')`).run(photonSpace, needId(userId, "userId"));
    return db.prepare("SELECT id FROM conversations WHERE photon_space = ?").get(photonSpace).id;
  }

  /** The finished brief. Missing fields are stored as NULL. city may be LA, HOU or the full name. Returns the row id. */
  function saveBrief({ userId, channel, interiorScene, exteriorQuery, city, trucks, crewCars } = {}) {
    const cityName = city == null ? null : CITY_NAMES[city] ?? (() => { throw new Error("city must be LA, HOU, Los Angeles or Houston"); })();
    return Number(db.prepare(`INSERT INTO briefs (user_id, channel, interior_scene, exterior_query, city, trucks, crew_cars)
      VALUES (?, ?, ?, ?, ?, ?, ?)`).run(
      userId == null ? null : needId(userId, "userId"), oneOf(channel, ["imessage", "web"], "channel"),
      orNull(interiorScene), orNull(exteriorQuery), cityName, intOrNull(trucks, "trucks"), intOrNull(crewCars, "crewCars"),
    ).lastInsertRowid);
  }

  /** One scout run. Limits and the base point are optional (NULL when unknown). Returns the row id. */
  function saveSearch({ briefId, userId, threadId, sourceMode, maxRent, rentUnits, baseLabel, baseLat, baseLon, maxDriveMin, alertsOn } = {}) {
    if (!threadId || typeof threadId !== "string") throw new Error("threadId is required");
    return Number(db.prepare(`INSERT INTO searches (brief_id, user_id, thread_id, source_mode, max_rent, rent_units, base_label, base_lat, base_lon, max_drive_min, alerts_on)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(
      needId(briefId, "briefId"), userId == null ? null : needId(userId, "userId"), threadId, oneOf(sourceMode, ["mock", "live"], "sourceMode"),
      realOrNull(maxRent, "maxRent"), orNull(rentUnits), orNull(baseLabel), realOrNull(baseLat, "baseLat"), realOrNull(baseLon, "baseLon"),
      intOrNull(maxDriveMin, "maxDriveMin"), alertsOn ? 1 : 0,
    ).lastInsertRowid);
  }

  /** Replace the shortlist snapshot for a search. Each pick: { rank, propertyId, address, propertyType, rentRef, rentTier, driveMin }. Returns the count saved. */
  function savePicks(searchId, picks) {
    needId(searchId, "searchId");
    const insert = db.prepare(`INSERT INTO picks (search_id, rank, property_id, address, property_type, rent_ref, rent_tier, drive_min)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(search_id, rank) DO UPDATE SET property_id = excluded.property_id, address = excluded.address,
        property_type = excluded.property_type, rent_ref = excluded.rent_ref, rent_tier = excluded.rent_tier, drive_min = excluded.drive_min`);
    return tx(() => {
      for (const p of picks) {
        if (!p.propertyId || !p.address) throw new Error("each pick needs propertyId and address");
        insert.run(searchId, needId(p.rank, "rank"), p.propertyId, p.address, orNull(p.propertyType), realOrNull(p.rentRef, "rentRef"), orNull(p.rentTier), realOrNull(p.driveMin, "driveMin"));
      }
      return picks.length;
    });
  }

  /** Log one message (no content stored). Returns false, and writes nothing, when photonMsgId was already recorded. */
  function recordMessage(conversationId, { photonMsgId, direction, kind } = {}) {
    const result = db.prepare(`INSERT INTO messages (conversation_id, photon_msg_id, direction, kind) VALUES (?, ?, ?, ?)
      ON CONFLICT(photon_msg_id) DO NOTHING`).run(
      needId(conversationId, "conversationId"), orNull(photonMsgId),
      oneOf(direction, ["in", "out"], "direction"), oneOf(kind, ["text", "image", "link", "other"], "kind"));
    return result.changes === 1;
  }

  /** Log an alert that was actually sent. Returns false, and writes nothing, for a second reach_out_reminder on the same search. */
  function recordAlert(searchId, { kind, propertyId, simulated } = {}) {
    const result = db.prepare(`INSERT INTO alerts (search_id, property_id, kind, simulated) VALUES (?, ?, ?, ?)
      ON CONFLICT DO NOTHING`).run(
      needId(searchId, "searchId"), orNull(propertyId), oneOf(kind, ["reach_out_reminder", "price_above", "price_back_within"], "kind"), simulated ? 1 : 0);
    return result.changes === 1;
  }

  return {
    db, getSettings, saveSettings, upsertUser, upsertConversation, saveBrief, saveSearch, savePicks, recordMessage, recordAlert,
    close: () => db.close(),
  };
}

let shared = null;
const store = () => (shared ??= openStore());
export const getSettings = (senderHash) => store().getSettings(senderHash);
export const saveSettings = (senderHash, fields) => store().saveSettings(senderHash, fields);
export const upsertUser = (senderHash) => store().upsertUser(senderHash);
export const upsertConversation = (photonSpace, userId) => store().upsertConversation(photonSpace, userId);
export const saveBrief = (fields) => store().saveBrief(fields);
export const saveSearch = (fields) => store().saveSearch(fields);
export const savePicks = (searchId, picks) => store().savePicks(searchId, picks);
export const recordMessage = (conversationId, fields) => store().recordMessage(conversationId, fields);
export const recordAlert = (searchId, fields) => store().recordAlert(searchId, fields);
