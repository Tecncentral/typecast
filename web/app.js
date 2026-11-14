import {
  SOURCES, availabilityInfo, evidenceBySource, fitInfo, imageUrl, moveLabel, noiseInfo, objections,
  parkingInfo, rankDiff, sourceStatus, tourLink,
} from "./lib.js";
import { laneStates, latestTodos, stepStates, secs, toolMs } from "./lib.js";

const $ = (id) => document.getElementById(id);

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
  return el;
}

// replaceChildren() would turn null into the text "null"; drop empty kids first.
function fill(el, ...kids) {
  el.replaceChildren(...kids.flat().filter((k) => k != null && k !== false));
  return el;
}

const state = {
  config: null,        // GET /config, or null if unavailable
  events: [],
  running: false,
  startedAt: 0,
  response: null,      // latest ScoutResponse
  previous: null,      // the response before the latest follow-up, for the diff
  followUp: null,      // the follow-up message that produced `response`
  refining: false,
  stream: null,
};

/* ---------------- config + badges ---------------- */

async function loadConfig() {
  try {
    const r = await fetch("/config");
    if (!r.ok) throw new Error(String(r.status));
    state.config = await r.json();
  } catch {
    state.config = null;
  }
  renderBadges();
}

function renderBadges() {
  const box = $("badges");
  box.replaceChildren();
  // The response's own source_mode/engine win over configuration once a run finishes.
  const mode = state.response?.source_mode || state.config?.mode;
  const engine = state.response?.engine || state.config?.engine;
  if (mode) box.append(h("span", { class: `badge ${mode}`, title: "Data source mode" }, mode));
  else box.append(h("span", { class: "badge", title: "GET /config was unavailable" }, "mode unknown"));
  if (engine) box.append(h("span", { class: "badge", title: "Agent engine" }, `${engine} engine`));
  const banner = $("banner");
  if (mode === "mock" || mode === "mixed") {
    banner.className = "banner fixture";
    banner.textContent = mode === "mock"
      ? "Fixture data. These buildings, frames and numbers are fake and only exercise the interface."
      : "Mixed mode. Some sources are fixtures; treat every value as unverified.";
    banner.hidden = false;
  } else if (!banner.classList.contains("error")) banner.hidden = true;
}

function showError(message) {
  const banner = $("banner");
  banner.className = "banner error";
  banner.textContent = message;
  banner.hidden = false;
}

function clearError() {
  if ($("banner").classList.contains("error")) { $("banner").hidden = true; $("banner").className = "banner"; }
  renderBadges();
}

/* ---------------- run ---------------- */

function startRun(scene) {
  if (state.stream) state.stream.close();
  clearError();
  state.events = [];
  state.response = null;
  state.previous = null;
  state.followUp = null;
  state.running = true;
  $("refine-form").hidden = true;
  state.startedAt = performance.now();
  $("empty").hidden = true;
  $("run").hidden = false;
  $("scout-btn").disabled = true;
  renderPlan();
  renderResults();
  tick();

  const qs = new URLSearchParams({ scene });
  const es = new EventSource(`/scout/stream?${qs}`);
  state.stream = es;
  es.addEventListener("agent", (m) => {
    state.events.push(JSON.parse(m.data));
    renderPlan();
  });
  es.addEventListener("result", (m) => {
    es.close();
    finish(JSON.parse(m.data));
  });
  es.addEventListener("error", (m) => {
    es.close();
    // A server "error" event carries data; a dropped connection does not.
    let msg = "Lost the connection to the Typecast API.";
    if (m.data) { try { msg = JSON.parse(m.data).message || msg; } catch { /* keep default */ } }
    fail(msg);
  });
}

function finish(res) {
  state.running = false;
  state.response = res;
  // The response carries the full event list; prefer it so nothing streamed is missing.
  if (Array.isArray(res.events) && res.events.length >= state.events.length) state.events = res.events;
  $("scout-btn").disabled = false;
  $("refine-form").hidden = !res.thread_id;
  renderBadges();
  renderPlan();
  renderResults();
}

function fail(message) {
  state.running = false;
  $("scout-btn").disabled = false;
  showError(`${message} Nothing was invented in its place; try again.`);
  renderPlan();
  renderResults();
}

function elapsed() {
  return (performance.now() - state.startedAt) / 1000;
}

function tick() {
  if (!state.running && !state.refining) return;
  $("clock").textContent = secs(elapsed());
  renderResultsHead();
  setTimeout(tick, 200);
}

/* ---------------- plan panel ---------------- */

const KEEP_ROWS = 4;
const SKEPTIC_ROWS = 5;

function renderPlan() {
  const finished = !state.running && !!state.response;
  const res = state.response;
  if (!state.running) {
    const total = res?.timings?.total_ms;
    $("clock").textContent = total != null ? secs(total / 1000) : state.startedAt ? secs(elapsed()) : "";
  }
  $("run-meta").textContent = res
    ? `${state.followUp ? "Follow-up re-rank · " : ""}${res.engine || "?"} engine · ${res.source_mode || "?"} data · thread ${res.thread_id}`
    : state.running ? "Streaming the agent's real progress events" : "";

  // To-do: the deep engine publishes its own; otherwise derive from events.
  const todos = latestTodos(state.events);
  const todo = $("todo");
  todo.replaceChildren();
  if (todos) {
    $("todo-title").textContent = "Agent's to-do list";
    for (const t of todos) todo.append(h("li", { class: t.status }, t.text));
  } else {
    $("todo-title").textContent = "Plan";
    for (const s of stepStates(state.events, finished)) todo.append(h("li", { class: s.state }, s.label));
  }

  // Several relaxed events can carry the same sentence; show each distinct one once.
  const relaxed = [...new Set(state.events.filter((e) => e.type === "relaxed").map((e) => e.text))];
  const gaveUp = state.response?.gave_up || [];
  $("relaxed").hidden = !relaxed.length && !gaveUp.length;
  fill($("relaxed"), 
    h("strong", {}, gaveUp.length ? `Relaxed: ${gaveUp.join(", ")}` : "Relaxed a requirement"),
    h("ul", {}, relaxed.map((t) => h("li", {}, t))));

  const lanes = $("lanes");
  lanes.replaceChildren();
  for (const lane of laneStates(state.events, finished)) {
    const objectionCount = lane.rows.filter((r) => r.kind === "skeptic").length;
    const keep = lane.id === "skeptic" ? SKEPTIC_ROWS : KEEP_ROWS;
    const shown = lane.rows.slice(-keep);
    const hiddenCount = lane.rows.length - shown.length;
    const span = lane.start != null && lane.end != null && lane.end > lane.start ? ` · ${secs(lane.end - lane.start)}` : "";
    lanes.append(h("div", { class: `lane ${lane.id} ${lane.state}${objectionCount ? " has-objections" : ""}` },
      h("div", { class: "lane-head" },
        h("span", { class: "lane-name" }, lane.label),
        h("span", { class: "lane-src" }, lane.id === "skeptic" && objectionCount
          ? h("span", { class: "objection-count" }, `${objectionCount} objection${objectionCount === 1 ? "" : "s"}`)
          : lane.source),
        h("span", { class: "lane-state" }, lane.state + span)),
      shown.length ? h("ol", { class: "rows" },
        hiddenCount > 0 ? h("li", { class: "more" }, h("span"), `${hiddenCount} earlier`) : null,
        shown.map((r) => h("li", { class: `k-${r.kind}` },
          h("span", { class: "t" }, r.ts != null ? `+${secs(r.ts)}` : ""),
          r.kind === "tool"
            ? h("span", {}, r.text, r.count > 1 ? ` ×${r.count}` : "",
              r.ms != null ? h("span", { class: "ms" }, `  ${toolMs(r.ms)}`) : null)
            : h("span", {}, r.text)))) : null));
  }

  renderTrace();
}

function renderTrace() {
  const box = $("trace");
  box.replaceChildren();
  const res = state.response;
  const traceEvents = state.events.filter((e) => e.type === "trace");
  if (res?.trace_url) {
    box.append("LangSmith trace: ", h("a", { href: res.trace_url, target: "_blank", rel: "noopener" }, "open the full run"));
  } else if (res) {
    box.append(traceEvents.length ? traceEvents.at(-1).text
      : state.config?.tracing ? "Tracing is on, but no trace link came back for this run."
      : "Tracing is off for this server, so there is no trace link.");
  }
}

/* ---------------- results ---------------- */

function renderResultsHead() {
  const head = $("results-head");
  if (state.running || state.refining) {
    const t = elapsed();
    fill(head, h("p", { class: "loading" },
      state.refining ? `Re-ranking for “${state.pendingFollowUp}”… ${secs(t)}` : `Scouting… ${secs(t)}`,
      t > 20 ? h("span", { class: "slow" }, "  Still working. Real runs can take up to two minutes.") : null));
    return;
  }
  const res = state.response;
  if (!res) { head.replaceChildren(); return; }
  const n = res.picks.length;
  if (state.followUp && state.previous) {
    const { moves, dropped } = rankDiff(state.previous, res);
    const changed = moves.filter((m) => m.move !== "same").length + dropped.length;
    const notes = moves.reduce((a, m) => a + m.newNotes.length, 0);
    fill(head,
      h("h2", {}, `Re-ranked for “${state.followUp}”`),
      h("span", { class: "sub" }, [
        "Same saved candidates, no new search",
        changed ? `${changed} rank change${changed === 1 ? "" : "s"}` : "ranking unchanged",
        notes ? `${notes} new objection${notes === 1 ? "" : "s"}` : null,
      ].filter(Boolean).join(" · ")));
    return;
  }
  fill(head,
    h("h2", {}, n ? `${n} pick${n === 1 ? "" : "s"}` : "No building fits this scene"),
    h("span", { class: "sub" }, n && n < 3 ? `Only ${n} survived. Nothing was padded to make three.`
      : n ? `${res.engine || "?"} engine · ${res.source_mode === "live" ? "live data" : "fixture data"}` : ""));
}

function renderResults() {
  renderResultsHead();
  const cards = $("cards");
  cards.replaceChildren();
  const res = state.response;
  if (!res) return;
  if (!res.picks.length) {
    cards.append(h("div", { class: "nomatch" },
      h("p", {}, "No scanned building passed the checks for this scene."),
      res.gave_up?.length ? h("p", {}, `Already relaxed: ${res.gave_up.join(", ")}. The plan panel shows why each candidate failed.`)
        : h("p", {}, "Try loosening the era, size or parking in the scene.")));
  }
  const diff = state.followUp && state.previous ? rankDiff(state.previous, res) : null;
  for (const p of res.picks) {
    cards.append(card(p, diff?.moves.find((m) => m.property_id === p.property.property_id) || null));
  }
  renderEarlier(diff);
}

/** The picks from before the follow-up stay visible, with what happened to each. */
function renderEarlier(diff) {
  const box = $("earlier");
  if (!diff) { box.hidden = true; box.replaceChildren(); return; }
  const now = new Map(state.response.picks.map((p) => [p.property.property_id, p.rank]));
  box.hidden = false;
  fill(box,
    h("span", { class: "eyebrow" }, "Before the follow-up"),
    h("div", { class: "strip" }, state.previous.picks.map((p) => {
      const rank = now.get(p.property.property_id);
      return h("div", { class: `mini${rank == null ? " dropped" : ""}` },
        frame(p, { mini: true }),
        h("p", {}, h("strong", {}, p.property.address), h("br"),
          rank == null ? h("span", { class: "dropped-label" }, "Dropped from the top three")
            : h("span", { class: "muted" }, rank === p.rank ? `Still #${rank}` : `Now #${rank}`)));
    })));
}

/* ---------------- follow-up (refine) ---------------- */

async function runRefine(message) {
  const res0 = state.response;
  if (!res0?.thread_id || state.refining) return;
  clearError();
  state.refining = true;
  state.pendingFollowUp = message;
  state.startedAt = performance.now();
  $("refine-btn").disabled = true;
  $("scout-btn").disabled = true;
  tick();
  try {
    const r = await fetch("/refine", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ thread_id: res0.thread_id, message }) });
    if (!r.ok) {
      let detail = `The follow-up failed (HTTP ${r.status}).`;
      try { const j = await r.json(); if (typeof j.detail === "string") detail = j.detail; } catch { /* keep */ }
      throw new Error(detail);
    }
    const res = await r.json();
    state.previous = res0;
    state.response = res;
    state.followUp = message;
    if (Array.isArray(res.events)) state.events = res.events;
  } catch (err) {
    showError(`${err.message || "The follow-up failed."} The earlier picks are unchanged.`);
  } finally {
    state.refining = false;
    $("refine-btn").disabled = false;
    $("scout-btn").disabled = false;
    renderBadges();
    renderPlan();
    renderResults();
  }
}

/** A frame that degrades to a labelled placeholder if the image is missing or fails. */
function frameImg(shot, alt) {
  const url = imageUrl(shot?.image_path);
  const missing = () => h("div", { class: "missing" }, "Frame unavailable");
  if (!url) return missing();
  const img = h("img", { src: url, alt, loading: "lazy", decoding: "async" });
  img.addEventListener("error", () => img.replaceWith(missing()), { once: true });
  return img;
}

function frame(pick, { mini = false } = {}) {
  const shots = pick.shots || [];
  let i = 0;
  const box = h("div", { class: "frame" });
  const draw = () => {
    const shot = shots[i];
    fill(box,
      frameImg(shot, `Camera view ${i + 1} inside ${pick.property.address}`),
      h("span", { class: "rank" }, `#${pick.rank}`),
      !mini && shot ? h("span", { class: "frame-id" }, shot.shot_id) : null,
      !mini && shots.length > 1 ? h("div", { class: "frame-nav" },
        h("button", { type: "button", "aria-label": "Previous frame", onclick: () => { i = (i - 1 + shots.length) % shots.length; draw(); } }, "←"),
        h("span", { class: "count" }, `${i + 1}/${shots.length}`),
        h("button", { type: "button", "aria-label": "Next frame", onclick: () => { i = (i + 1) % shots.length; draw(); } }, "→")) : null);
  };
  draw();
  return box;
}

function pill(status, text) { return h("span", { class: `pill ${status}` }, text); }

function fitLine(fit) {
  return h("div", { class: "fit-line" },
    "Needs ", h("b", {}, fit.need == null ? "unknown" : `${fit.need} m`), " depth · room has ",
    h("b", {}, fit.have == null ? "unknown" : `${fit.have} m`), " · ceiling ",
    h("b", {}, fit.ceiling == null ? "unknown" : `${fit.ceiling} m`));
}

function evidenceChips(pick) {
  const by = evidenceBySource(pick);
  return h("div", { class: "chips", "aria-label": "Evidence by source" },
    SOURCES.map((s) => {
      const st = sourceStatus(by[s.id]);
      return h("span", { class: `chip ${st}`, title: by[s.id].map((e) => `${e.status}: ${e.claim}`).join("\n") || "No evidence returned" },
        s.label, h("small", {}, st));
    }));
}

function logistics(pick) {
  const lg = pick.logistics;
  const park = parkingInfo(lg);
  const noise = noiseInfo(lg);
  const aerial = imageUrl(lg?.aerial_image_path);
  return h("div", { class: "logi" },
    h("div", {},
      h("div", { class: "k" }, `Crew parking (${park.status})`),
      h("div", {}, park.label, h("span", { class: "muted" }, ` · ${park.walk}`)),
      h("div", { class: "k", style: "margin-top:6px" }, `Noise (${noise.status})`),
      h("div", { class: noise.flags.length ? "loud" : "" }, noise.label)),
    aerial ? h("img", { class: "aerial", src: aerial, alt: `Aerial view of parking near ${pick.property.address}`,
      onerror: (e) => e.target.remove() }) : null);
}

const CARD_OBJECTIONS = 2;

function objectionList(pick, fresh = [], limit = Infinity) {
  // New objections from a follow-up come first, so the change is visible on the card.
  const list = objections(pick).sort((a, b) => fresh.includes(b) - fresh.includes(a));
  const shown = list.slice(0, limit);
  return h("ul", { class: "objections", "aria-label": "Skeptic notes" },
    list.length ? shown.map((n) => h("li", { class: fresh.includes(n) ? "new" : "" }, fresh.includes(n) ? `New: ${n}` : n))
      : h("li", { class: "none" }, "Skeptic: no objection"),
    list.length > shown.length ? h("li", { class: "more" }, `+${list.length - shown.length} more in details`) : null);
}

function card(pick, move = null) {
  const p = pick.property;
  const fit = fitInfo(pick.shot_fit);
  const avail = availabilityInfo(p);
  const facts = [p.type, p.year_built ? `built ${p.year_built}` : "year unknown",
    p.size_sqft ? `${Math.round(p.size_sqft).toLocaleString()} sq ft` : null, p.city].filter(Boolean).join(" · ");
  return h("article", { class: `card${move && move.move !== "same" ? " moved" : ""}`, "data-property": p.property_id },
    frame(pick),
    h("div", { class: "info" },
      h("div", {},
        h("div", { class: "addr" }, p.address),
        h("div", { class: "facts" }, facts)),
      h("div", { class: "row-badges" },
        move ? pill("move", moveLabel(move)) : null,
        pill(fit.status, fit.label),
        pill(avail.status, avail.label)),
      fitLine(fit),
      h("p", { class: "reason", title: pick.reason }, pick.reason),
      evidenceChips(pick),
      logistics(pick),
      objectionList(pick, move?.newNotes || [], CARD_OBJECTIONS),
      h("div", { class: "card-actions" },
        h("button", { type: "button", class: "details-btn", onclick: () => openDrawer(pick) }, "Details and 3D tour"),
        draftButton(pick))));
}

/* ---------------- owner note approval ---------------- */

// Keyed by thread and rank, so a re-rank does not carry a draft badge to another building.
const drafts = new Map();
const draftKey = (pick) => `${state.response?.thread_id}:${pick.rank}:${pick.property.property_id}`;

function draftButton(pick) {
  const saved = drafts.get(draftKey(pick));
  if (saved) return h("span", { class: "draft-state" }, saved);
  return h("button", { type: "button", class: "draft-btn", onclick: () => askApproval(pick) }, "Draft note to owner");
}

let approving = null;

function askApproval(pick) {
  approving = pick;
  $("approve-title").textContent = `Draft a note about ${pick.property.address}?`;
  $("approve-body").textContent = `Typecast drafts an inquiry to the listing contact for pick #${pick.rank}, `
    + "asking about filming availability, permissions and parking access.";
  $("approve-result").textContent = "";
  $("approve-yes").hidden = false;
  $("approve-yes").disabled = false;
  $("approve-close").textContent = "Cancel";
  $("approve").showModal();
}

async function approve() {
  const pick = approving;
  const threadId = state.response?.thread_id;
  if (!pick || !threadId) return;
  $("approve-yes").disabled = true;
  $("approve-result").textContent = "Saving the draft…";
  try {
    const r = await fetch("/approve", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, pick_rank: pick.rank, decision: "yes" }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : `HTTP ${r.status}`);
    if (j.status !== "draft_saved") throw new Error(`the server answered “${j.status || "unknown"}”`);
    const msg = "Saved as a local draft, not sent.";
    drafts.set(draftKey(pick), msg);
    $("approve-result").textContent = `${msg} It is in the team's local outbox for review.`;
    $("approve-yes").hidden = true;
    $("approve-close").textContent = "Done";
    renderResults();
  } catch (err) {
    $("approve-result").textContent = `No draft was saved: ${err.message}.`;
    $("approve-yes").disabled = false;
  }
}

/* ---------------- detail drawer + tour ---------------- */

function openDrawer(pick) {
  const p = pick.property;
  const fit = fitInfo(pick.shot_fit);
  const lg = pick.logistics || {};
  const park = parkingInfo(lg);
  const noise = noiseInfo(lg);
  const by = evidenceBySource(pick);
  const aerial = imageUrl(lg.aerial_image_path);
  const body = $("drawer-body");
  fill(body,
    h("div", { class: "drawer-top" },
      h("div", {},
        h("span", { class: "eyebrow" }, `Pick #${pick.rank}`),
        h("h2", {}, p.address),
        h("div", { class: "facts" }, [p.type, p.year_built ? `built ${p.year_built}` : "year unknown",
          p.size_sqft ? `${Math.round(p.size_sqft).toLocaleString()} sq ft` : null, p.city,
          p.listing_types?.length ? `listed for ${p.listing_types.join(", ")}` : null].filter(Boolean).join(" · "))),
      h("button", { type: "button", class: "ghost", onclick: closeDrawer, "aria-label": "Close details" }, "Close")),
    tourBox(pick),
    h("section", {},
      h("span", { class: "eyebrow" }, "Frames from the scan"),
      h("div", { class: "frames-row" }, (pick.shots || []).map((s) => h("figure", {},
        h("div", { class: "frame" }, frameImg(s, `Camera view ${s.shot_id}`)),
        h("figcaption", {}, `${s.shot_id} · heading ${s.heading_deg}° · `,
          [s.room_area_m2 != null ? `${s.room_area_m2} m²` : "area unknown",
            s.depth_m != null ? `depth ${s.depth_m} m` : "depth unknown",
            s.ceiling_m != null ? `ceiling ${s.ceiling_m} m` : "ceiling unknown"].join(" · "),
          s.measure_on_site ? " · measure on site" : ""))))),
    h("section", {},
      h("span", { class: "eyebrow" }, "Why this pick"),
      h("p", { style: "margin:0" }, pick.reason)),
    h("section", {},
      h("span", { class: "eyebrow" }, "Shot fit"),
      h("div", { class: "row-badges" }, pill(fit.status, fit.label), pill(availabilityInfo(p).status, availabilityInfo(p).label)),
      fitLine(fit),
      fit.note ? h("p", { class: "muted", style: "margin:6px 0 0" }, fit.note) : null,
      p.availability_reason ? h("p", { class: "muted", style: "margin:6px 0 0" }, p.availability_reason) : null),
    h("section", {},
      h("span", { class: "eyebrow" }, "Crew logistics"),
      h("div", { class: "logi" },
        h("div", {},
          h("div", {}, `${park.label} (${park.status}) · ${park.walk}`),
          lg.parking_area_m2 != null ? h("div", { class: "muted" }, `Paved area about ${Math.round(lg.parking_area_m2)} m²`) : null,
          h("div", { class: noise.flags.length ? "loud" : "" }, `Noise: ${noise.label} (${noise.status})`),
          (lg.source_notes || []).map((n) => h("div", { class: "muted" }, n))),
        aerial ? h("img", { class: "aerial big", src: aerial, alt: `Aerial view near ${p.address}`, onerror: (e) => e.target.remove() }) : null)),
    h("section", { class: "evidence" },
      h("span", { class: "eyebrow" }, "Evidence, line by line"),
      SOURCES.map((s) => h("div", {},
        h("h3", {}, s.label),
        by[s.id].length ? h("ul", {}, by[s.id].map((e) => h("li", {},
          h("span", { class: `chip ${e.status}` }, e.status), h("span", {}, e.claim))))
          : h("p", { class: "muted", style: "margin:0" }, "No evidence returned from this source.")))),
    h("section", {},
      h("span", { class: "eyebrow" }, "Skeptic"),
      objectionList(pick)));
  $("drawer").hidden = false;
  $("scrim").hidden = false;
  $("drawer").scrollTop = 0;
  body.querySelector(".drawer-top button")?.focus();
}

function closeDrawer() {
  $("drawer").hidden = true;
  $("scrim").hidden = true;
  $("drawer-body").replaceChildren(); // drops any tour iframe and its SDK connection
}

const SDK_BOOTSTRAP = "https://api.matterport.com/sdk/bootstrap/3.1.0-0-g1cd7e0997a/sdk.es6.js";

/**
 * 3D tour. With an SDK key: embed Showcase, connect, and move to the shot's sweep if exactly one
 * SDK sweep matches its id. Heading alignment is not verified (index headings are cube-face
 * relative), so the note says so. Without a key: a plain link, labelled honestly.
 */
function tourBox(pick) {
  const shot = pick.shots?.[0];
  const link = tourLink(shot?.model_id || pick.property.model_id);
  const key = state.config?.matterport_sdk_key;
  const box = h("section", { class: "tour-box" }, h("span", { class: "eyebrow" }, "3D tour"));
  if (!link) {
    box.append(h("p", { class: "muted", style: "margin:0" }, "No 3D tour: this pick has no real Matterport model id (fixture data)."));
    return box;
  }
  if (!key) {
    box.append(h("a", { href: link, target: "_blank", rel: "noopener", class: "tour-link" }, "Open the 3D tour"),
      h("p", { class: "tour-note" }, "Opens at the model's start, not this frame. No Matterport SDK key is configured for this viewer."));
    return box;
  }
  const note = h("p", { class: "tour-note" }, "Connecting to the 3D tour…");
  const src = new URL("https://my.matterport.com/show");
  src.search = new URLSearchParams({ m: shot?.model_id || pick.property.model_id, play: "1", applicationKey: key });
  const iframe = h("iframe", { src: src.href, title: `3D tour of ${pick.property.address}`, allow: "fullscreen; xr-spatial-tracking" });
  box.append(iframe, note, h("a", { href: link, target: "_blank", rel: "noopener", class: "tour-note" }, "Open the tour in a new tab"));
  connectTour(iframe, key, shot, note);
  return box;
}

async function connectTour(iframe, key, shot, note) {
  try {
    const { connect } = await import(`${SDK_BOOTSTRAP}?applicationKey=${encodeURIComponent(key)}`);
    const sdk = await Promise.race([connect(iframe),
      new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), 25000))]);
    const sweeps = new Map();
    await new Promise((resolve) => {
      sdk.Sweep.data.subscribe({
        onAdded: (id, v) => sweeps.set(id, v), onUpdated: (id, v) => sweeps.set(id, v),
        onRemoved: (id) => sweeps.delete(id), onCollectionUpdated: () => resolve(),
      });
      setTimeout(resolve, 4000);
    });
    const matches = [...sweeps.entries()].filter(([id, v]) => [id, v.sid, v.uuid].includes(shot.sweep_id));
    if (matches.length !== 1) {
      note.textContent = "Tour loaded at the model's start. This frame's scan point has no unique match in the tour, so explore manually.";
      return;
    }
    const transition = sdk.Camera?.TransitionType?.FLY ?? sdk.Sweep?.Transition?.FLY;
    await sdk.Sweep.moveTo(matches[0][0], { rotation: { x: 0, y: Number(shot.heading_deg) || 0 }, transition });
    note.textContent = "Moved to this frame's scan point. Facing direction is approximate: the frame's heading has not been verified against the tour's camera.";
  } catch {
    if (!note.isConnected) return;
    note.textContent = "Interactive tour control is unavailable (SDK did not connect). The tour opens at the model's start.";
  }
}

/* ---------------- boot ---------------- */

$("scene-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const scene = $("scene").value.trim();
  if (scene) startRun(scene);
});
$("refine-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const message = $("refine").value.trim();
  if (message) runRefine(message);
});
$("approve-yes").addEventListener("click", approve);
$("scrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("drawer").hidden) closeDrawer(); });
$("scene").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("scene-form").requestSubmit();
});

loadConfig();
