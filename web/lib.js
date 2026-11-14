// Pure helpers for the viewer. No DOM here, so `node --test web/tests` covers them.
// Rule throughout: a null from the API renders as "unknown", never as 0, quiet or "fits".

export const LANES = [
  { id: "director", label: "Director", source: "Plans, ranks, explains" },
  { id: "market_scout", label: "Market scout", source: "CoStar" },
  { id: "interior_scout", label: "Interior scout", source: "Matterport" },
  { id: "logistics_scout", label: "Logistics scout", source: "Vexcel" },
  { id: "skeptic", label: "Skeptic", source: "Location manager" },
];

// Tools report under their own name; show them in the lane that calls them.
const LANE_OF = {
  director: "director", runtime: "director", parse: "director", parse_scene: "director",
  market_scout: "market_scout", search_costar: "market_scout", get_property: "market_scout",
  interior_scout: "interior_scout", search_shots: "interior_scout", rerank_shots: "interior_scout", check_shot: "interior_scout",
  logistics_scout: "logistics_scout", plan_logistics: "logistics_scout",
  skeptic: "skeptic",
};

export function laneOf(agent) {
  if (!agent) return "director";
  if (LANE_OF[agent]) return LANE_OF[agent];
  if (agent.startsWith("state.")) return "director";
  if (/market/.test(agent)) return "market_scout";
  if (/interior|shot/.test(agent)) return "interior_scout";
  if (/logistic|vexcel|parking/.test(agent)) return "logistics_scout";
  if (/skeptic/.test(agent)) return "skeptic";
  return "director";
}

// Fixed-order steps, shown when the engine does not publish its own to-do list.
export const STEPS = [
  { id: "parse", label: "Read the scene into requirements" },
  { id: "market", label: "Filter buildings in CoStar" },
  { id: "interior", label: "Search camera views in Matterport scans" },
  { id: "rerank", label: "Rank views by look" },
  { id: "logistics", label: "Check shot fit, parking and noise" },
  { id: "skeptic", label: "Skeptic challenges each pick" },
  { id: "final", label: "Rank and explain the picks" },
];

const STEP_OF = {
  parse: "parse", parse_scene: "parse",
  market_scout: "market", search_costar: "market",
  interior_scout: "interior", search_shots: "interior",
  rerank_shots: "rerank",
  logistics_scout: "logistics", check_shot: "logistics", plan_logistics: "logistics",
  skeptic: "skeptic",
};

function stepOf(e) {
  if (e.type === "final") return "final";
  if (e.type === "skeptic") return "skeptic";
  if (e.type === "rerank") return "rerank";
  return STEP_OF[e.agent] || null;
}

/** Step states derived only from events that actually arrived. */
export function stepStates(events, finished = false) {
  const seen = new Set();
  let furthest = -1;
  for (const e of events) {
    const s = stepOf(e);
    if (!s) continue;
    seen.add(s);
    furthest = Math.max(furthest, STEPS.findIndex((x) => x.id === s));
  }
  return STEPS.map((s, i) => {
    let state;
    if (seen.has(s.id)) state = finished || i < furthest ? "done" : "active";
    else if (i < furthest || finished) state = "skipped";
    else state = "pending";
    return { ...s, state };
  });
}

/** The deep engine's own to-do list (latest "todo" event), or null. */
export function latestTodos(events) {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].type !== "todo") continue;
    try {
      const list = JSON.parse(events[i].text);
      if (Array.isArray(list)) {
        return list.map((t) => (typeof t === "string" ? { text: t, status: "pending" }
          : { text: t.content ?? t.text ?? "", status: t.status || "pending" }));
      }
    } catch { /* not JSON */ }
  }
  return null;
}

/** One lane per agent, holding start/result/tool/skeptic rows in arrival order. */
export function laneStates(events, finished = false) {
  const lanes = Object.fromEntries(LANES.map((l) => [l.id, { ...l, state: "waiting", rows: [], start: null, end: null }]));
  for (const e of events) {
    if (e.type === "todo" || e.type === "trace") continue;
    const lane = lanes[laneOf(e.agent)];
    // Internal working-memory writes are not agent activity worth a row.
    const internal = e.type === "tool" && e.agent?.startsWith("state.");
    const last = lane.rows.at(-1);
    if (internal || e.type === "relaxed") {
      // Relaxed notices get their own box; still count them as lane activity.
    } else if (e.type === "tool" && last?.kind === "tool" && last.agent === e.agent) {
      // Collapse repeated calls of one tool into a single row with a count and total time.
      last.count += 1;
      if (e.ms != null) last.ms = (last.ms ?? 0) + e.ms;
    } else {
      const ok = e.type === "skeptic" && /:?\s*no objection\.?$/i.test(e.text || "");
      lane.rows.push({ kind: ok ? "ok" : e.type, text: e.type === "tool" ? e.agent : e.text || "",
        ts: e.ts ?? null, ms: e.ms ?? null, agent: e.agent, count: 1 });
    }
    if (lane.start == null && e.ts != null) lane.start = e.ts;
    if (e.ts != null) lane.end = e.ts;
    if (e.type === "subagent_result" || e.type === "final") lane.state = "done";
    else if (lane.state !== "done" || e.type === "subagent_start") lane.state = "working";
  }
  for (const lane of Object.values(lanes)) {
    if (finished && lane.state === "working") lane.state = "done";
  }
  return Object.values(lanes);
}

export function secs(ts) {
  if (ts == null || !Number.isFinite(ts)) return "";
  return ts < 10 ? `${ts.toFixed(1)}s` : `${Math.round(ts)}s`;
}

export function toolMs(ms) {
  if (ms == null || !Number.isFinite(ms)) return "";
  return ms < 1000 ? `${ms < 10 ? ms.toFixed(1) : Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** Image paths from the API are repo-relative. Only the two served folders become URLs. */
export function imageUrl(path) {
  if (!path || typeof path !== "string") return null;
  if (/^https?:\/\//.test(path)) return path;
  const clean = path.replace(/^\/+/, "");
  if (!/^(mocks|cache)\//.test(clean) || clean.split("/").includes("..")) return null;
  return "/" + clean.split("/").map(encodeURIComponent).join("/");
}

const n1 = (v) => (v == null || !Number.isFinite(Number(v)) ? null : Math.round(Number(v) * 10) / 10);

// `shot` is optional; when given, only explicitly measured geometry (measure_on_site === false)
// can yield fits/tight. Estimated or unsupplied geometry stays unknown.
export function fitInfo(fit, shot) {
  if (!fit) return { status: "unknown", label: "Fit unknown", need: null, have: null, ceiling: null, note: "" };
  const have = n1(fit.have_depth_m);
  // Unknown depth can never be "fits", whatever the boolean says; a missing status needs a real boolean.
  let status = fit.status || (typeof fit.fits === "boolean" ? (fit.fits ? "fits" : "tight") : "unknown");
  if (have == null || (shot !== undefined && shot?.measure_on_site !== false)) status = "unknown";
  const label = { fits: "Shot fits", tight: "Shot is tight", unknown: "Fit unknown" }[status] || "Fit unknown";
  return { status, label, need: n1(fit.needed_depth_m), have, ceiling: n1(fit.ceiling_m), note: fit.note || "" };
}

export function availabilityInfo(p) {
  const s = p?.availability_status;
  if (s === "unknown") return { status: "unknown", label: "Availability unknown" };
  if (s === "not_available") return { status: "occupied", label: "Occupied" };
  if (s === "available") return { status: "available", label: "Available" };
  // The legacy boolean is not evidence: a missing or null status is unknown (matches agent/pipeline.py).
  return { status: "unknown", label: "Availability unknown" };
}

const count = (v, one, many) => (v == null ? `unknown ${many}` : `${v} ${v === 1 ? one : many}`);

export function parkingInfo(lg) {
  if (!lg) return { label: "Parking unknown", status: "unknown", walk: "walk unknown" };
  const t = lg.truck_spaces, c = lg.car_spaces;
  const status = lg.parking_status || (t == null && c == null ? "unknown" : lg.estimated ? "estimated" : "measured");
  const label = t == null && c == null ? "Parking unknown" : `${count(t, "truck", "trucks")} · ${count(c, "car", "cars")}`;
  const walk = lg.walk_m == null || lg.walk_status === "unknown" ? "walk unknown" : `${Math.round(lg.walk_m)} m walk`;
  return { label, status, walk };
}

export function noiseInfo(lg) {
  const flags = lg?.noise_flags || [];
  if (flags.length) return { flags, label: flags.join(" · "), status: lg.noise_status || (lg.estimated ? "estimated" : "measured") };
  // Empty flags only mean "nothing found" when screening actually ran.
  if (!lg || lg.noise_status === "unknown") return { flags: [], label: "Noise not screened", status: "unknown" };
  return { flags: [], label: "No freeway, rail or airport flagged", status: lg.noise_status || "estimated" };
}

export function objections(pick) {
  return (pick?.skeptic_notes || []).filter((n) => n && !/^no objection\.?$/i.test(n.trim()));
}

export const SOURCES = [
  { id: "costar", label: "CoStar" },
  { id: "matterport", label: "Matterport" },
  { id: "vexcel", label: "Vexcel" },
];

export function evidenceBySource(pick) {
  const out = { costar: [], matterport: [], vexcel: [] };
  for (const e of pick?.evidence || []) if (out[e.source]) out[e.source].push(e);
  return out;
}

/** Weakest status wins, so one chip per source never overstates certainty. */
export function sourceStatus(items) {
  if (!items.length) return "unknown";
  if (items.some((e) => e.status === "unknown")) return "unknown";
  if (items.some((e) => e.status === "estimated")) return "estimated";
  return "measured";
}

/** Rank movement between two responses by property_id, plus new skeptic notes. */
export function rankDiff(before, after) {
  const old = new Map((before?.picks || []).map((p) => [p.property.property_id, p]));
  const now = new Set();
  const moves = (after?.picks || []).map((p) => {
    const id = p.property.property_id;
    now.add(id);
    const prev = old.get(id);
    const was = prev ? prev.rank : null;
    const prevNotes = new Set(prev?.skeptic_notes || []);
    return {
      property_id: id, rank: p.rank, was,
      move: was == null ? "new" : was > p.rank ? "up" : was < p.rank ? "down" : "same",
      newNotes: prev ? objections(p).filter((n) => !prevNotes.has(n)) : [],
    };
  });
  const dropped = (before?.picks || []).filter((p) => !now.has(p.property.property_id));
  return { moves, dropped };
}

export function moveLabel(m) {
  if (m.move === "new") return "New in the top three";
  if (m.move === "same") return `Still #${m.rank}`;
  return `${m.move === "up" ? "Up" : "Down"} from #${m.was}`;
}

/** Matterport general tour link. Fixture ids get none. */
export function tourLink(modelId) {
  if (!modelId || /^mock-/i.test(modelId) || !/^[A-Za-z0-9]{6,32}$/.test(modelId)) return null;
  return `https://my.matterport.com/show/?m=${encodeURIComponent(modelId)}`;
}

/** Parking outline rings as [lat, lon], preferring GeoJSON parking_geometry ([lon, lat]). */
export function parkingRings(lg) {
  const g = lg?.parking_geometry;
  const flip = (ring) => ring.map(([lon, lat]) => [lat, lon]);
  if (g?.type === "Polygon") return g.coordinates.map(flip);
  if (g?.type === "MultiPolygon") return g.coordinates.flatMap((poly) => poly.map(flip));
  if (Array.isArray(lg?.parking_polygon) && lg.parking_polygon.length >= 3) return [lg.parking_polygon];
  return [];
}

export function parseJsonl(text) {
  return text.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => JSON.parse(l));
}
