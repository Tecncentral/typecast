// Script mode for the brief: 2+ INT./EXT. headings send the text to the Director's Room
// planner (POST /api/production/plan) instead of single-scene scouting. Counts in the summary
// come from the plan response only. The scene split here is a simple heading-based reading;
// the Director's Room has the fuller parser.
import { el, assetUrl } from "./utils.js";

const HEADING = /^\s*(?:\d+\s*[.)]?\s*)?(INT\.?\/EXT\.?|EXT\.?\/INT\.?|I\/E\.?|INT\.|EXT\.)\s+\S/i;
const MAX_SCENES = 24;
const MAX_DESCRIPTION = 4000;

/** Scene headings in the text, as [{id, heading, description}]. */
export function parseScript(text) {
  const scenes = [];
  let current = null;
  for (const line of String(text || "").split(/\r?\n/)) {
    if (HEADING.test(line)) {
      current = { id: `s${scenes.length + 1}`, heading: line.trim(), body: [] };
      scenes.push(current);
    } else if (current && line.trim()) current.body.push(line.trim());
  }
  return scenes.slice(0, MAX_SCENES).map(({ id, heading, body }) => ({
    id, heading, description: (body.join(" ") || heading).slice(0, MAX_DESCRIPTION),
  }));
}

export function isScript(text) {
  return parseScript(text).length >= 2;
}

async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
  const data = await r.json().catch(() => null);
  if (!r.ok) {
    const d = data && (data.detail ?? data.error);
    const msg = Array.isArray(d) ? d.map((x) => x?.msg).filter(Boolean).join("; ") : d;
    throw Error(typeof msg === "string" && msg ? msg.slice(0, 300) : `The planner request failed (HTTP ${r.status}).`);
  }
  if (!data || !Array.isArray(data.scenes) || !Array.isArray(data.plans)) throw Error("The planner returned a malformed response.");
  return data;
}

export async function requestPlan(scenes, { trucks = 0, cars = 0 } = {}) {
  return post("/api/production/plan", {
    scenes, max_locations: 3, forbidden_property_ids: [], require_available: false,
    trucks: Math.max(0, Math.floor(trucks) || 0), cars: Math.max(0, Math.floor(cars) || 0),
  });
}

const plural = (n, one, many = one + "s") => `${n} ${n === 1 ? one : many}`;

/** Summary + one group per planned location. Nothing here is counted by the browser. */
export function renderPlan(host, data, scenes) {
  host.replaceChildren();
  const plan = data.plans[0];
  if (data.mode === "mock")
    host.append(el("p", "MOCK fixture plan: placeholder frames and fixture rankings, not real rooms.", "plan-mock"));
  if (!plan) {
    host.append(el("p", "The planner returned no plan for this script. Nothing is shown in its place.", "plan-empty"));
    return;
  }
  const headings = new Map(scenes.map((s, i) => [s.id, { n: i + 1, heading: s.heading }]));
  host.append(el("p",
    `${plural(data.scenes.length, "scene")} · ${plural(plan.locations, "location")} · ${plural(plan.company_moves, "company move")}` +
      (plan.uncovered_scene_ids?.length ? ` · ${plural(plan.uncovered_scene_ids.length, "scene")} uncovered` : ""),
    "plan-summary"));
  const caveat = [data.pool_note, data.optimal_within_pool ? "Best plan within the retrieved pool, not the whole catalogue." : null]
    .filter(Boolean).join(" ");
  if (caveat) host.append(el("p", caveat, "plan-caveat"));

  const byScene = new Map(data.scenes.map((s) => [s.id, s]));
  plan.property_ids.forEach((pid, i) => {
    const assigned = plan.assignments.filter((a) => a.property_id === pid);
    const sceneNums = assigned.map((a) => headings.get(a.scene_id)?.n).filter(Boolean);
    const first = assigned[0];
    const cand = first && (byScene.get(first.scene_id)?.candidates || []).find((c) => c.shot?.shot_id === first.shot_id);
    const prop = cand?.property;
    const group = el("section", undefined, "plan-group");
    group.append(el("h3", `Location ${i + 1}: ${prop?.address || pid}, covers ${sceneNums.length === 1 ? "scene" : "scenes"} ${sceneNums.join(", ")}`));
    const card = el("article", undefined, "plan-card");
    const frame = el("div", undefined, "plan-frame");
    const src = cand?.shot?.image_path ? assetUrl(cand.shot.image_path) : null;
    if (src) {
      const img = el("img");
      img.src = src;
      img.alt = `Planned frame at ${prop?.address || pid}`;
      img.addEventListener("error", () => img.replaceWith(el("span", "Frame unavailable", "plan-missing")), { once: true });
      frame.append(img);
    } else frame.append(el("span", "Frame unavailable", "plan-missing"));
    const info = el("div", undefined, "plan-info");
    info.append(el("p", [prop?.city, prop?.type, prop?.year_built ? `Built ${prop.year_built}` : null].filter(Boolean).join(" · "), "plan-facts"));
    const list = el("ul", undefined, "plan-scenes");
    for (const a of assigned) {
      const h = headings.get(a.scene_id);
      list.append(el("li", `${h ? h.n + ". " + h.heading : a.scene_id}`));
    }
    info.append(list);
    const lg = cand?.logistics;
    if (lg) {
      const t = lg.truck_spaces == null ? "unknown" : lg.truck_spaces;
      const c = lg.car_spaces == null ? "unknown" : lg.car_spaces;
      info.append(el("p", `Parking: ${t} truck spaces · ${c} car spaces${lg.estimated ? " · estimate" : ""}`, "plan-facts"));
    }
    for (const w of cand?.warnings || []) {
      const text = typeof w === "string" ? w : [w.source, w.field, w.status].filter(Boolean).join(" · ");
      if (text) info.append(el("p", text, "plan-warning"));
    }
    info.append(el("p", "From the production plan. Scout one scene for full shot fit and skeptic review.", "plan-note"));
    card.append(frame, info);
    group.append(card);
    host.append(group);
  });
}
