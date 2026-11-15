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

export function openStore(file = DEFAULT_DB) {
  if (file !== ":memory:") mkdirSync(path.dirname(file), { recursive: true });
  const db = new DatabaseSync(file);
  db.exec(`CREATE TABLE IF NOT EXISTS settings (
    sender_hash TEXT PRIMARY KEY, city TEXT, trucks INTEGER, cars INTEGER, updated_at TEXT
  )`);
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

  return { getSettings, saveSettings, close: () => db.close() };
}

let shared = null;
const store = () => (shared ??= openStore());
export const getSettings = (senderHash) => store().getSettings(senderHash);
export const saveSettings = (senderHash, fields) => store().saveSettings(senderHash, fields);
