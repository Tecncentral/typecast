// Photon v2 conversation engine: interior and exterior intake, one compact results bubble, link contract.
// Keyword and regex rules only (no LLM in the bridge). Same contract as intake.handleMessage:
//   handleMessage(key, text, { say, fetchImpl, env }) -> parts [{ text, role?, flow? }]
// Parts and say() calls may carry meta: role "results" (a failed send gets a fallback line) and
// flow "start" / "end" (the first and last bubble of one search, used for the per-search send budget).
import { handle as coreHandle, sessions } from "./core.mjs";
import { extract, isStartOver, buildScene } from "./intake.mjs";

export const MAX_QUESTIONS = 3;
export const PICK_LIMIT = 3;
export const HELP = 'Not sure what you mean. Try: "need parking for 5 trucks", "draft 1" or "start over".';

const CITY_NAME = { LA: "Los Angeles", HOU: "Houston" };
const SLOT_KEYS = ["setting", "time", "era", "mood", "city", "trucks", "cars"];
const LABEL = { setting: "place", time: "time of day", era: "era", mood: "mood", city: "city", trucks: "trucks", cars: "crew cars", exterior: "exterior" };
const YES_NO = /^\s*(yes|y|send it|approve|no|n|cancel|don't send)\s*[.!]?\s*$/i;
const DRAFT = /^\s*draft\s+([123])\s*$/i;
const CORRECTION = /^\s*(?:actually|make it|change (?:it )?to|switch to|instead|correction|no,? (?:make it|it'?s|i meant))\b/i;
const DECLINE_EXT = /\b(?:no|without|skip|don'?t need)\s+(?:an?\s+|the\s+|any\s+)?(?:exterior|outside|outdoors?)\b|\b(?:interior|inside)\s+only\b|\bjust\s+(?:the\s+)?interior\b/i;
const EXT_ANY = /\b(?:exterior|outside|outdoors?|establishing|alley(?:way)?|rooftop|roof|street|sidewalk|intersection|parking lot|car park)\b/i;
const EXT_WORDS = [
  [/\balley(?:way)?\b/i, "alley"], [/\b(?:rooftop|roof)\b/i, "rooftop"],
  [/\b(?:street|sidewalk|intersection)\b/i, "street"], [/\b(?:parking lot|car park)\b/i, "parking lot"],
];
const REFINE_HINT = /\b(need|want|must|prefer|bigger|larger|smaller|more|less|closer|farther|older|newer|parking|ceiling|height|trucks?|cars?|era|quieter|cheaper)\b/i;

// --- parsing -----------------------------------------------------------------------------------------------
/** Every slot we can read from one message. INT./EXT. headings route text; exterior words go to the exterior. */
export function parseBrief(text) {
  const raw = String(text || "").trim();
  const out = {};
  const shared = extract(raw);
  for (const k of ["city", "time", "era", "mood", "trucks", "cars"]) if (shared[k] != null) out[k] = shared[k];
  const declined = DECLINE_EXT.test(raw);
  if (declined) out.declineExterior = true;
  if (/\b(?:INT|EXT)\./i.test(raw)) {
    out.heading = true;
    const segments = raw.split(/(?=\b(?:INT|EXT)\.)/i).map((s) => s.trim());
    const ints = segments.filter((s) => /^INT\./i.test(s));
    const exts = segments.filter((s) => /^EXT\./i.test(s));
    if (ints.length) { out.interiorScene = ints.join(" "); out.setting = extract(out.interiorScene).setting ?? "location"; }
    if (exts.length) out.exteriorQuery = exts.join(" ");
    return out;
  }
  const clauses = (declined ? raw.replace(new RegExp(DECLINE_EXT.source, "gi"), " ") : raw).split(/[,;.!?\n]+|\b(?:with|plus|also|and|including)\b/i).map((s) => s.trim()).filter(Boolean);
  const exteriorClauses = clauses.filter((c) => EXT_ANY.test(c));
  const interior = extract(clauses.filter((c) => !EXT_ANY.test(c)).join(", "));
  if (interior.setting) out.setting = interior.setting;
  if (exteriorClauses.length) {
    const hit = EXT_WORDS.find(([re]) => re.test(exteriorClauses.join(" ")));
    out.exterior = hit ? hit[1] : `${out.setting ?? "building"} exterior`;
  }
  return out;
}

const gotAnySlot = (b) => SLOT_KEYS.some((k) => b[k] != null) || Boolean(b.exterior || b.declineExterior || b.heading);

export function buildExterior(slots) {
  const era = slots.era ? `${slots.era === "modern" ? "MODERN" : slots.era} ` : "";
  return [`EXT. ${era}${String(slots.exterior).toUpperCase()}${slots.time ? `, ${slots.time}` : ""}.`, CITY_NAME[slots.city] ? `${CITY_NAME[slots.city]}.` : ""].filter(Boolean).join(" ");
}

// --- intake state ------------------------------------------------------------------------------------------
export const newBrief = () => ({
  slots: {}, interiorScene: null, exteriorQuery: null, exteriorAnswered: false,
  asked: 0, askedA: false, askedB: false, askedC: false, pending: null,
});

const show = (k, v) => (k === "city" ? CITY_NAME[v] : k === "time" ? String(v).toLowerCase() : v);

function applyBrief(st, b, overwrite) {
  const notes = [];
  for (const k of SLOT_KEYS) {
    if (b[k] == null) continue;
    if (st.slots[k] == null) st.slots[k] = b[k];
    else if (overwrite && st.slots[k] !== b[k]) { notes.push(`${LABEL[k]} → ${show(k, b[k])}`); st.slots[k] = b[k]; }
  }
  if (b.interiorScene) st.interiorScene = b.interiorScene;
  if (b.exteriorQuery) { st.exteriorQuery = b.exteriorQuery; st.exteriorAnswered = true; }
  if (b.exterior && (overwrite || !st.slots.exterior)) {
    if (overwrite && st.slots.exterior && st.slots.exterior !== b.exterior) notes.push(`${LABEL.exterior} → ${b.exterior}`);
    st.slots.exterior = b.exterior; st.exteriorAnswered = true;
  }
  if (b.declineExterior) {
    st.exteriorAnswered = true;
    if (overwrite && (st.slots.exterior || st.exteriorQuery)) { st.slots.exterior = null; st.exteriorQuery = null; notes.push("no exterior"); }
  }
  if (overwrite && notes.length) st.interiorScene = null;
  return notes;
}

function nextQuestion(st) {
  if (st.interiorScene || st.exteriorQuery || st.asked >= MAX_QUESTIONS) return null;
  const hasPlace = Boolean(st.slots.setting || st.slots.exterior);
  if ((!hasPlace || !st.slots.city) && !st.askedA) return "A";
  if (!st.exteriorAnswered && !st.askedB) return "B";
  if (st.slots.trucks == null && st.slots.cars == null && !st.askedC) return "C";
  return null;
}

function questionText(st, q, first) {
  const got = [st.slots.era, st.slots.setting, st.slots.time?.toLowerCase()].filter(Boolean).join(", ");
  const lead = first && got ? `Got it: ${got}. ` : "";
  const hasPlace = Boolean(st.slots.setting || st.slots.exterior);
  if (q === "A") {
    if (!hasPlace && !st.slots.city) return "What kind of place do you need (police station, warehouse, diner...), and LA or Houston?";
    if (!hasPlace) return "What kind of place do you need? Reply like: police station / warehouse / diner / office.";
    return `${lead}LA or Houston?`;
  }
  if (q === "B") return `${lead}Need an exterior too (street, alley, rooftop, parking lot)? Add an era or mood if you like. Reply like "alley, 80s, grimy" or "no".`;
  return `${lead}How many trucks and crew cars? Or "skip".`;
}

/** Advance the intake with one message. Returns { action: "ask", text, notes } or { action: "search", notes }. */
export function advance(st, text, { correction = false } = {}) {
  const b = parseBrief(text);
  const notes = applyBrief(st, b, correction);
  if (st.pending === "A" && !st.slots.setting && !st.slots.exterior && !st.interiorScene && !gotAnySlot(b)
      && text.trim().length <= 40 && !/^\s*(skip|any|none|no)\s*[.!]?\s*$/i.test(text)) {
    st.slots.setting = text.trim().toLowerCase().replace(/[.!?]+$/, "");
  }
  const first = st.asked === 0;
  st.pending = null;
  const q = nextQuestion(st);
  if (!q) return { action: "search", notes };
  st.asked += 1; st[`asked${q}`] = true; st.pending = q;
  return { action: "ask", text: questionText(st, q, first), notes };
}

// --- results and link --------------------------------------------------------------------------------------
function pickLines(p) {
  const availability = p.property.availability_status === "unknown" ? " (availability unknown)" : p.property.available === false ? " (not listed as available)" : "";
  const sf = p.shot_fit ?? {};
  const fit = sf.status === "unknown" || sf.have_depth_m == null ? "Shot fit unknown" : sf.fits ? "Shot fits" : "Shot is tight";
  const depth = sf.have_depth_m == null ? "" : ` (needs ${sf.needed_depth_m} m, room ${sf.have_depth_m} m)`;
  const L = p.logistics ?? {};
  const count = (n, one, many) => (n == null ? `unknown ${many}` : `${n} ${n === 1 ? one : many}`);
  const parking = `Parking${L.estimated ? " (est.)" : ""}: ${count(L.truck_spaces, "truck", "trucks")}, ${count(L.car_spaces, "car", "cars")}.`;
  return [`${p.rank}. ${p.property.address}${availability}`, `${fit}${depth}. ${parking}`];
}

/** One bubble: header, then picks in rank order, two lines each. */
export function formatResults(res, { updated = false } = {}) {
  const picks = [...(res.picks ?? [])].sort((a, b) => a.rank - b.rank).slice(0, PICK_LIMIT);
  const label = (res.source_mode || "mock").toUpperCase();
  const word = `interior ${picks.length === 1 ? "pick" : "picks"}`;
  const relaxed = res.gave_up?.length ? `Relaxed: ${res.gave_up.join(", ")}.` : null;
  if (!picks.length) {
    return [`${label} · 0 interior picks`, `Nothing matched.${relaxed ? ` ${relaxed}` : ""} Try loosening the era, size or parking.`].join("\n");
  }
  return [`${label} · ${updated ? "updated ranking, " : ""}${picks.length} ${word}`, ...(relaxed ? [relaxed] : []), ...picks.flatMap(pickLines)].join("\n");
}

/** viewer link: PHOTON_VIEWER_URL + /app/?scene=&ext=&city=&trucks=&cars=&autorun=1. Empty params are omitted. */
export function buildViewerLink(viewerUrl, { scene, ext, city, trucks, cars } = {}) {
  let u;
  try { u = new URL(String(viewerUrl || "")); } catch { return null; }
  if (!/^https?:$/.test(u.protocol) || (!scene && !ext)) return null;
  const query = [["scene", scene], ["ext", ext], ["city", city], ["trucks", trucks], ["cars", cars], ["autorun", scene ? "1" : null]]
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");
  const base = u.pathname.replace(/\/app\/?$/, "").replace(/\/+$/, "");
  return `${u.origin}${base}/app/?${query}`;
}

const confirmation = ({ interior, exterior, slots, notes }) => [
  ...(notes.length ? [`Updated: ${notes.join(", ")}.`] : []),
  "Searching now (MOCK).",
  `Interior: ${interior ?? "none"}`,
  `Exterior: ${exterior ?? "none"}`,
  `City: ${CITY_NAME[slots.city] ?? "Los Angeles (assumed)"} · Trucks: ${slots.trucks ?? "not given"} · Crew cars: ${slots.cars ?? "not given"}`,
].join("\n");

// --- main entry --------------------------------------------------------------------------------------------
async function post(api, path, body, fetchImpl) {
  const r = await fetchImpl(`${api}${path}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

export async function handleMessage(key, textIn, { say = async () => {}, fetchImpl = fetch, env = process.env } = {}) {
  const text = String(textIn || "").trim();
  const api = env.TYPECAST_API || "http://localhost:8000";
  const s = sessions.get(key) || {};
  let flowStart = false;
  const take = (extra = {}) => { const m = flowStart ? { ...extra, flow: "start" } : extra; flowStart = false; return m; };
  const reply = (t, extra) => [{ text: t, ...take(extra) }];

  if (!text) return reply("Send me a scene, like: INT. 1980s POLICE STATION, NIGHT. Parking for 3 trucks and 30 crew cars.");

  if (isStartOver(text)) {
    const st = newBrief(); st.asked = 1; st.askedA = true; st.pending = "A";
    sessions.set(key, { v2: { phase: "intake", st } });
    flowStart = true;
    return reply(`Okay, starting over. ${questionText(st, "A", false)}`);
  }

  if ((s.awaitingApproval && YES_NO.test(text)) || (s.picks?.length && DRAFT.test(text))) {
    try { return (await coreHandle(key, text, { say, fetchImpl })).filter((p) => p.text); }
    catch { return reply("Couldn't save that draft. Try again in a moment."); }
  }

  const afterSearch = s.v2?.phase === "done";
  let st = s.v2?.phase === "intake" ? s.v2.st : null;
  let notes = [];
  if (afterSearch) {
    const b = parseBrief(text);
    const words = text.split(/\s+/).length;
    const changes = CORRECTION.test(text) && ["setting", "time", "era", "mood", "city", "exterior", "declineExterior"].some((k) => b[k] != null);
    if (changes) { st = s.v2.st; notes = applyBrief(st, b, true); flowStart = true; }
    else if (b.heading || words >= 25) { st = newBrief(); flowStart = true; }
    else if (s.threadId && s.picks?.length && REFINE_HINT.test(text)) {
      try {
        const res = await post(api, "/refine", { thread_id: s.threadId, message: text }, fetchImpl);
        sessions.set(key, { ...s, picks: res.picks, awaitingApproval: null });
        return reply(formatResults(res, { updated: true }));
      } catch (e) { return reply(`Couldn't re-rank right now (${e.message}). Try again in a moment.`); }
    } else return reply(HELP);
  }

  if (!st) { st = newBrief(); flowStart = true; }
  if (!notes.length) {
    const correction = Boolean(s.v2?.phase === "intake") && CORRECTION.test(text);
    const r = advance(st, text, { correction });
    notes = r.notes;
    if (r.action === "ask") {
      sessions.set(key, { ...s, v2: { phase: "intake", st } });
      return reply([...(notes.length ? [`Updated: ${notes.join(", ")}.`] : []), r.text].join("\n"));
    }
  }

  const interior = st.interiorScene || (st.slots.setting ? buildScene({ ...st.slots, ie: "INT" }) : null);
  const exterior = st.exteriorQuery || (st.slots.exterior ? buildExterior(st.slots) : null);
  if (!interior && !exterior) {
    st.pending = "A";
    sessions.set(key, { ...s, v2: { phase: "intake", st } });
    return reply("I still need a kind of place to search for. Describe it in words, like: warehouse or INT. WAREHOUSE, DAY.");
  }
  await say(confirmation({ interior, exterior, slots: st.slots, notes }), take());

  const parts = [];
  let res = null;
  if (interior) {
    try { res = await post(api, "/scout", { scene: interior }, fetchImpl); }
    catch (e) { parts.push({ text: `Search failed on my side (${e.message}). Try again in a moment.`, role: "results" }); }
    if (res) parts.push({ text: formatResults(res), role: "results" });
  }
  const link = buildViewerLink(env.PHOTON_VIEWER_URL, { scene: interior, ext: exterior, city: st.slots.city, trucks: st.slots.trucks, cars: st.slots.cars });
  if (exterior) parts.push({ text: link ? `Exterior search ready on the site: ${exterior} (runs live when you open it).` : `Exterior search not run (no site link is configured): ${exterior}` });
  if (link) parts.push({ text: link });
  if (parts.length) parts[parts.length - 1] = { ...parts[parts.length - 1], flow: "end" };

  sessions.set(key, { threadId: res?.thread_id, picks: res?.picks ?? [], awaitingApproval: null, v2: { phase: "done", st } });
  return parts;
}
