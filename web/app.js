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

const state = {
  config: null,        // GET /config, or null if unavailable
  events: [],
  running: false,
  startedAt: 0,
  response: null,      // latest ScoutResponse
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
  state.running = true;
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
  if (!state.running) return;
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
    ? `${res.engine || "?"} engine · ${res.source_mode || "?"} data · thread ${res.thread_id}`
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
  $("relaxed").replaceChildren(
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

/* ---------------- results (placeholder until cards land) ---------------- */

function renderResultsHead() {
  const head = $("results-head");
  if (state.running) {
    const t = elapsed();
    head.replaceChildren(h("p", { class: "loading" }, `Scouting… ${secs(t)}`,
      t > 20 ? h("span", { class: "slow" }, "  Real runs take up to two minutes.") : null));
    return;
  }
  const res = state.response;
  if (!res) { head.replaceChildren(); return; }
  head.replaceChildren(h("h2", {}, res.picks.length ? `${res.picks.length} picks` : "No building fits"));
}

function renderResults() {
  renderResultsHead();
  const cards = $("cards");
  cards.replaceChildren();
  for (const p of state.response?.picks || []) cards.append(h("p", {}, `#${p.rank} ${p.property.address}`));
}

/* ---------------- boot ---------------- */

$("scene-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const scene = $("scene").value.trim();
  if (scene) startRun(scene);
});
$("scene").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("scene-form").requestSubmit();
});

loadConfig();
