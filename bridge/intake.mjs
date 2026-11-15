// Conversational intake for the iMessage line: brief Typecast like a human location scout.
// Pure functions plus one wrapper (handleMessage) that drives core.mjs unchanged. No LLM call here:
// keyword and regex rules only. The backend parser still reads the final scene text.
import { handle as coreHandle, sessions } from "./core.mjs";

export const MAX_QUESTIONS = 4;
const SKIP = /^\s*(skip|any|anything|no preference|doesn'?t matter|whatever|none|n\/a)\s*[.!]?\s*$/i;
const START_OVER = /^\s*(start over|new search|reset|start again)\s*[.!]?\s*$/i;
const SLUG = /^\s*(int|ext|int\/ext|i\/e)[.\s]/i;
const DRAFT_OR_YES_NO = /^\s*(draft\s+[123]|yes|y|send it|approve|no|n|cancel|don't send)\s*[.!]?\s*$/i;

// [pattern, canonical name, INT or EXT]
const SETTINGS = [
  [/\b(police station|cop station|cop shop|precinct|police department|police headquarters)\b/, "police station", "INT"],
  [/\b(warehouse|loading dock)\b/, "warehouse", "INT"],
  [/\b(diner|coffee shop|cafe|café)\b/, "diner", "INT"],
  [/\b(restaurant|bistro|pizzeria)\b/, "restaurant", "INT"],
  [/\b(nightclub|night club|club)\b/, "nightclub", "INT"],
  [/\b(bar|pub|dive bar|saloon)\b/, "bar", "INT"],
  [/\b(office|cubicles?|open[- ]plan)\b/, "office", "INT"],
  [/\b(apartment|flat|loft)\b/, "apartment", "INT"],
  [/\b(hospital|clinic|emergency room)\b/, "hospital", "INT"],
  [/\b(school|classroom|high school)\b/, "school", "INT"],
  [/\b(church|chapel)\b/, "church", "INT"],
  [/\b(courtroom|courthouse)\b/, "courtroom", "INT"],
  [/\b(jail|prison|holding cell|cell block)\b/, "jail", "INT"],
  [/\b(hotel|motel|lobby)\b/, "hotel", "INT"],
  [/\b(bank|vault)\b/, "bank", "INT"],
  [/\b(laundromat|launderette)\b/, "laundromat", "INT"],
  [/\b(gym|boxing gym)\b/, "gym", "INT"],
  [/\b(library)\b/, "library", "INT"],
  [/\b(factory|plant|machine shop)\b/, "factory", "INT"],
  [/\b(mansion|house|living room|kitchen)\b/, "house", "INT"],
  [/\b(laboratory|lab)\b/, "laboratory", "INT"],
  [/\b(newsroom|studio)\b/, "studio", "INT"],
  [/\b(subway|train station|metro station)\b/, "subway station", "INT"],
  [/\b(parking garage|parking structure)\b/, "parking garage", "INT"],
  [/\b(alley|alleyway)\b/, "alley", "EXT"],
  [/\b(rooftop|roof)\b/, "rooftop", "EXT"],
  [/\b(street|sidewalk|intersection)\b/, "street", "EXT"],
  [/\b(parking lot|car park)\b/, "parking lot", "EXT"],
  [/\b(beach|pier|boardwalk)\b/, "beach", "EXT"],
  [/\b(park|trail|hillside)\b/, "park", "EXT"],
];
const MOODS = [
  [/\b(grimy|gritty|dirty|seedy|run[- ]?down|worn|shabby)\b/, "Gritty"],
  [/\b(clean|polished|pristine|sleek)\b/, "Clean"],
  [/\b(bright|sunny|airy)\b/, "Bright"],
  [/\b(dark|moody|dim)\b/, "Moody"],
];

const CITY_NAMES = { LA: "Los Angeles", HOU: "Houston" };

/** Pull every slot we can from one message. Never throws; unknown slots are simply absent. */
export function extract(text) {
  const t = ` ${String(text || "").toLowerCase()} `;
  const found = {};
  for (const [re, name, ie] of SETTINGS) if (re.test(t)) { found.setting = name; found.ie = ie; break; }
  if (!found.setting) {
    const m = t.match(/\b(?:need|want|looking for|find me|find|get me|got)\s+(?:an?|the|some)?\s*([a-z][a-z' -]{2,40}?)(?=\s+(?:for|in|at|with|that|where|during|near)\b|[,.!?]|\s*$)/);
    if (m && !/^(a |an |the )/.test(m[1])) found.setting = m[1].trim();
  }
  if (/\b(exterior|outdoors?|outside)\b/.test(t)) found.ie = "EXT";
  else if (/\b(interior|indoors?|inside)\b/.test(t) && found.setting) found.ie = "INT";
  if (/\b(los angeles|hollywood)\b/.test(t) || /(^|[^a-z])(la|l\.a\.?)(?![a-z])/.test(t)) found.city = "LA";
  else if (/\b(houston|htx|h-town)\b/.test(t)) found.city = "HOU";
  if (/\b(dawn|sunrise|early morning)\b/.test(t)) found.time = "DAWN";
  else if (/\b(night|nighttime|midnight|after dark)\b/.test(t)) found.time = "NIGHT";
  else if (/\b(dusk|sunset|golden hour|evening)\b/.test(t)) found.time = "DUSK";
  else if (/\b(day|daytime|morning|afternoon|noon|midday)\b/.test(t)) found.time = "DAY";
  const era = t.match(/\b(?:(19|20)(\d)|(\d))0'?s\b/);
  if (era) {
    const decade = era[1] ? `${era[1]}${era[2]}0s` : Number(era[3]) >= 5 ? `19${era[3]}0s` : null;
    if (decade) found.era = decade;
  }
  if (!found.era && /\b(modern|contemporary|present[- ]day|today's)\b/.test(t)) found.era = "modern";
  for (const [re, mood] of MOODS) if (re.test(t)) { found.mood = mood; break; }
  const trucks = t.match(/(\d{1,3})\s*(?:big\s*|production\s*)?trucks?\b/);
  const cars = t.match(/(\d{1,3})\s*(?:crew\s*)?cars?\b/);
  if (trucks) found.trucks = Number(trucks[1]);
  if (cars) found.cars = Number(cars[1]);
  return found;
}

/** A detailed first message needs no questions. */
export function isDetailed(text, found = extract(text)) {
  return SLUG.test(text) || (found.setting && found.city) || String(text).trim().split(/\s+/).length >= 25;
}

function parkingSentence({ trucks, cars }) {
  const parts = [];
  if (trucks != null) parts.push(`${trucks} ${trucks === 1 ? "truck" : "trucks"}`);
  if (cars != null) parts.push(`${cars} crew ${cars === 1 ? "car" : "cars"}`);
  return parts.length ? `Parking for ${parts.join(" and ")}.` : "";
}

/** One scene string for POST /scout, e.g. "INT. 1980s POLICE STATION, NIGHT. Los Angeles. Gritty. Parking for 3 trucks and 30 crew cars." */
export function buildScene(slots) {
  const era = slots.era ? `${slots.era === "modern" ? "MODERN" : slots.era} ` : "";
  const head = `${slots.ie || "INT"}. ${era}${String(slots.setting || "location").toUpperCase()}${slots.time ? `, ${slots.time}` : ""}.`;
  return [head, CITY_NAMES[slots.city] ? `${CITY_NAMES[slots.city]}.` : "", slots.mood ? `${slots.mood}.` : "", parkingSentence(slots)]
    .filter(Boolean).join(" ");
}

export const newIntake = () => ({ slots: {}, skipped: {}, asked: 0, pending: null });

const ORDER = ["setting", "city", "time", "era", "parking"];
const filled = (st, slot) => slot === "parking" ? st.slots.trucks != null || st.slots.cars != null : st.slots[slot] != null;

function questionFor(st, slot, first) {
  const got = [st.slots.era, st.slots.setting, st.slots.time?.toLowerCase()].filter(Boolean).join(", ");
  const lead = first && got ? `Got it: ${got}. ` : "";
  switch (slot) {
    case "setting": return `What kind of place do you need? Reply like: police station / warehouse / diner / office.`;
    case "city": return `${lead}LA or Houston?`;
    case "time": return `${lead}Day or night? Reply: day / night / any`;
    case "era": return `${lead}What era? Reply: modern / 80s / 70s / any`;
    default: return `${lead}How many trucks and crew cars? Or "skip".`;
  }
}

/** Advance the intake with one message. Returns { action: "ask", text } or { action: "search", scene, note }. */
export function step(state, text, { first = false } = {}) {
  const st = state || newIntake();
  st.fresh = false;
  const found = extract(text);
  if (first && isDetailed(text, found)) {
    const scene = SLUG.test(text) ? String(text).trim() : buildScene(found);
    return { action: "search", scene, state: st, note: found.city || SLUG.test(text) ? "" : " No city named, so Los Angeles." };
  }
  Object.assign(st.slots, Object.fromEntries(Object.entries(found).filter(([k]) => st.slots[k] == null)));
  if (st.pending && !filled(st, st.pending)) {
    if (st.pending === "setting" && !SKIP.test(text) && text.trim().length <= 40) st.slots.setting = text.trim().toLowerCase();
    else st.skipped[st.pending] = true;
  }
  const next = ORDER.find((slot) => !filled(st, slot) && !st.skipped[slot]);
  if (next && st.asked < MAX_QUESTIONS) {
    const wasFirst = first || st.asked === 0;
    st.asked += 1; st.pending = next;
    return { action: "ask", text: questionFor(st, next, wasFirst), state: st };
  }
  st.pending = null;
  return { action: "search", scene: buildScene(st.slots), state: st, note: st.slots.city ? "" : " No city named, so Los Angeles." };
}

export const isStartOver = (text) => START_OVER.test(text);

// Allowlist -----------------------------------------------------------------------------------------------
function normalize(handle) {
  const v = String(handle ?? "").trim().toLowerCase();
  if (!v) return "";
  if (v.includes("@")) return v;
  const digits = v.replace(/\D/g, "");
  return digits.length === 11 && digits.startsWith("1") ? digits.slice(1) : digits;
}
export function parseAllowed(list) {
  // Split on commas, semicolons and newlines only: phone numbers contain spaces.
  return new Set(String(list ?? "").split(/[,;\n]+/).map(normalize).filter(Boolean));
}
/** Fail closed: an empty list or an unidentifiable sender is never allowed. */
export function isAllowed(sender, allowed) {
  const id = normalize(sender);
  return id !== "" && allowed instanceof Set && allowed.has(id);
}

// Link ------------------------------------------------------------------------------------------------------
/** viewer link that opens the site and runs the scene live, or null when no usable PHOTON_VIEWER_URL. */
export function buildLink(viewerUrl, scene) {
  try {
    const u = new URL(String(viewerUrl || ""));
    if (!/^https?:$/.test(u.protocol) || !scene) return null;
    u.searchParams.set("scene", scene); u.searchParams.set("autorun", "1");
    return u.toString();
  } catch { return null; }
}
/** core.mjs ends results with "Tour them: <viewer>#/run/<thread>", a route the viewer does not have. Replace it. */
export function rewriteLink(parts, { viewerUrl, scene }) {
  const link = buildLink(viewerUrl, scene);
  return parts.map((p) => {
    if (!p.text?.startsWith("Tour them:")) return p;
    const rest = p.text.split("\n").slice(1).join("\n");
    return { text: link ? `See them in 3D: ${link}\n(opens the site and runs this search live)\n${rest}` : rest };
  });
}

// Wrapper ---------------------------------------------------------------------------------------------------
/**
 * One inbound message from an allowlisted sender. Intake state lives in core's sessions map, under the
 * same conversation key. Results, re-rank, "draft N" and YES/NO are core.mjs unchanged.
 */
export async function handleMessage(key, textIn, { say = async () => {}, fetchImpl = fetch, env = process.env } = {}) {
  const text = (textIn || "").trim();
  const s = sessions.get(key) || {};
  const viewerUrl = env.PHOTON_VIEWER_URL;
  if (isStartOver(text)) {
    sessions.set(key, { intake: { ...newIntake(), asked: 1, pending: "setting", fresh: true } });
    return [{ text: `Okay, starting over. ${questionFor(newIntake(), "setting", false)}` }];
  }
  const hasResults = Boolean(s.threadId && s.picks?.length);
  if (!text || s.awaitingApproval || (hasResults && !s.intake) || (hasResults && DRAFT_OR_YES_NO.test(text))) {
    const parts = await coreHandle(key, text, { say, fetchImpl });
    const scene = SLUG.test(text) ? text : sessions.get(key)?.scene ?? s.scene;
    if (SLUG.test(text)) sessions.set(key, { ...sessions.get(key), scene });
    return rewriteLink(parts, { viewerUrl, scene });
  }
  const r = step(s.intake, text, { first: !s.intake || Boolean(s.intake.fresh) });
  if (r.action === "ask") { sessions.set(key, { ...s, intake: r.state }); return [{ text: r.text }]; }
  sessions.set(key, { ...s, intake: null });
  await say(`Searching for: ${r.scene}${r.note}`);
  const parts = await coreHandle(key, r.scene, { say: async () => {}, fetchImpl });
  sessions.set(key, { ...sessions.get(key), scene: r.scene });
  return rewriteLink(parts, { viewerUrl, scene: r.scene });
}
