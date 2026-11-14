// Platform-agnostic conversation logic. Adapters (terminal, Photon) call handle() and deliver the parts.
// A part is { text } or { image } (image = absolute URL or file path).

const API = () => process.env.TYPECAST_API || "http://localhost:8000";
const VIEWER = () => process.env.TYPECAST_VIEWER || `${API()}/app/`;
const YES = /^\s*(yes|y|send it|approve)\s*[.!]?\s*$/i;
const NO = /^\s*(no|n|cancel|don't send)\s*[.!]?\s*$/i;

/** threadKey -> { threadId, picks, awaitingApproval } */
export const sessions = new Map();

async function post(path, body, fetchImpl) {
  const r = await fetchImpl(`${API()}${path}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.json();
}

export function imageUrl(path) {
  if (!path) return null;
  return /^https?:\/\//.test(path) ? path : `${API()}/${path.replace(/^\/+/, "")}`;
}

export function formatPick(p) {
  const fit = p.shot_fit.fits ? "Shot fits" : "Shot is tight";
  const lines = [
    `${p.rank}. ${p.property.address}${p.property.available ? "" : " (occupied)"}`,
    p.reason,
    `${fit}: needs ${p.shot_fit.needed_depth_m} m, room has ${p.shot_fit.have_depth_m ?? "unknown"} m.`,
    `Parking: ${p.logistics.truck_spaces} trucks, ${p.logistics.car_spaces} cars.`,
  ];
  const objections = (p.skeptic_notes || []).filter((n) => n !== "No objection.");
  if (objections.length) lines.push(`Watch out: ${objections.join(" ")}`);
  return lines.join("\n");
}

function picksToParts(res, intro) {
  const parts = [];
  if (intro) parts.push({ text: intro });
  if (res.gave_up?.length) parts.push({ text: `Nothing matched everything, so I relaxed: ${res.gave_up.join(", ")}.` });
  if (!res.picks.length) return [...parts, { text: "No buildings fit. Try loosening the era, size or parking." }];
  for (const p of res.picks) {
    for (const s of p.shots.slice(0, 2)) { const u = imageUrl(s.image_path); if (u) parts.push({ image: u }); }
    parts.push({ text: formatPick(p) });
  }
  parts.push({ text: `Tour them: ${VIEWER()}#/run/${res.thread_id}\nReply with a change ("need parking for 5 trucks"), or "draft 1" to draft a note to that owner.` });
  return parts;
}

/**
 * Handle one inbound message. `say` is called immediately with the acknowledgement so the
 * adapter can send "On it" before the slow work starts. Returns the remaining parts.
 */
export async function handle(threadKey, textIn, { say = async () => {}, fetchImpl = fetch } = {}) {
  const text = (textIn || "").trim();
  const s = sessions.get(threadKey) || {};
  if (!text) return [{ text: "Send me a scene, like: INT. 1980s POLICE STATION, NIGHT. Parking for 3 trucks and 30 crew cars." }];

  if (s.awaitingApproval && (YES.test(text) || NO.test(text))) {
    const decision = YES.test(text) ? "yes" : "no";
    const rank = s.awaitingApproval; s.awaitingApproval = null; sessions.set(threadKey, s);
    const r = await post("/approve", { thread_id: s.threadId, pick_rank: rank, decision }, fetchImpl);
    if (decision === "no") return [{ text: "Okay, nothing sent." }];
    return [{ text: r.sent ? `Sent to the team inbox (${r.to}).` : `Approved. Delivery to the team inbox is not switched on yet${r.to ? ` (${r.to})` : ""}; nothing went to the owner.` }];
  }

  const draft = text.match(/^\s*draft\s+([123])\s*$/i);
  if (draft && s.picks?.length) {
    const rank = Number(draft[1]); const p = s.picks.find((x) => x.rank === rank);
    if (!p) return [{ text: `There is no pick ${rank}.` }];
    s.awaitingApproval = rank; sessions.set(threadKey, s);
    return [{ text: `Draft to ${p.property.contact || "the listing contact"}:\n\n"Hi, we are scouting a film location and your space at ${p.property.address} fits a scene we are shooting. Could we arrange a visit this week?"\n\nReply YES to send it to our team inbox, or NO to drop it. Nothing goes to the owner.` }];
  }

  try {
    if (s.threadId && s.picks?.length && text.length < 80 && !/^\s*(int|ext)\b/i.test(text)) {
      await say("Re-ranking what I already found.");
      const res = await post("/refine", { thread_id: s.threadId, message: text }, fetchImpl);
      sessions.set(threadKey, { ...s, picks: res.picks });
      return picksToParts(res, "Updated ranking:");
    }
    await say("On it. Casting real buildings for that scene.");
    const res = await post("/scout", { scene: text }, fetchImpl);
    sessions.set(threadKey, { threadId: res.thread_id, picks: res.picks, awaitingApproval: null });
    return picksToParts(res, null);
  } catch (e) {
    return [{ text: `Something broke on my side (${e.message}). Try again in a moment.` }];
  }
}
