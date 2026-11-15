import { el, formatNumber } from "./utils.js";

const LANES = [
  ["director", "Director"],
  ["market_scout", "Market"],
  ["interior_scout", "Interior"],
  ["logistics_scout", "Logistics"],
  ["skeptic", "Skeptic"],
];

function laneFor(event) {
  if (event.type === "tool") {
    const tool = typeof event.agent === "string" ? event.agent : "";
    if (/search_costar|get_property/.test(tool)) return "market_scout";
    if (/search_shots|get_shot|rerank|check_shot/.test(tool))
      return "interior_scout";
    if (/plan_logistics/.test(tool)) return "logistics_scout";
    return "director";
  }
  if (event.type === "skeptic") return "skeptic";
  return LANES.some(([name]) => name === event.agent)
    ? event.agent
    : "director";
}

function parseTodos(text) {
  try {
    const todos = JSON.parse(text);
    return Array.isArray(todos) &&
      todos.every(
        (todo) =>
          todo && typeof todo === "object" && typeof todo.content === "string",
      )
      ? todos
      : null;
  } catch {
    return null;
  }
}

const TOOL_NAMES = {
  search_costar: "Search CoStar",
  get_property: "Read CoStar record",
  search_shots: "Search interiors",
  get_shot: "Read interior",
  rerank: "Visual re-rank",
  check_shot_fit: "Check shot fit",
  plan_logistics: "Plan parking",
};
const humanKey = (key) => key.replaceAll("_", " ");
/** What a person can read in a lane; the raw text stays on the row's data-event-text. */
function readable(text) {
  const trimmed = text.trim();
  if (!/^[[{]/.test(trimmed)) return trimmed.length > 160 ? `${trimmed.slice(0, 157)}…` : trimmed;
  let value;
  try {
    value = JSON.parse(trimmed);
  } catch {
    return trimmed.length > 160 ? `${trimmed.slice(0, 157)}…` : trimmed;
  }
  const todos = parseTodos(trimmed);
  if (todos) {
    const done = todos.filter((todo) => todo.status === "completed").length;
    return `${done} of ${todos.length} plan steps done`;
  }
  if (Array.isArray(value)) return `${value.length} item${value.length === 1 ? "" : "s"} returned`;
  if (!value || typeof value !== "object") return String(value);
  const keys = Object.keys(value);
  // Records keyed by identifiers (e.g. one note per property) read as a count, never as raw ids.
  if (keys.length && keys.every((key) => /^[0-9a-z_-]{5,}$/i.test(key) && /\d/.test(key)))
    return `${keys.length} record${keys.length === 1 ? "" : "s"} checked`;
  const parts = [];
  for (const key of keys) {
    const item = value[key];
    if (Array.isArray(item)) parts.push(`${item.length} ${humanKey(key)}`);
    else if (typeof item === "number" || typeof item === "boolean") parts.push(`${humanKey(key)} ${item}`);
    else if (typeof item === "string" && item.length <= 40) parts.push(`${humanKey(key)}: ${item}`);
    if (parts.length === 3) break;
  }
  return parts.length ? parts.join(" · ") : `${keys.length} fields returned`;
}

function eventLabel(event) {
  const names = {
    plan: "Plan",
    todo: "To-do update",
    subagent_start: "Started",
    subagent_result: "Result",
    skeptic: "Skeptic review",
    relaxed: "Relaxed",
    fallback: "Fallback",
    final: "Final",
    error: "Error",
    rerank: "Re-rank",
    trace: "Trace",
  };
  const parts = [
    event.type === "tool"
      ? TOOL_NAMES[event.agent] || event.agent || "Tool"
      : names[event.type] || event.type || "Event",
  ];
  if (typeof event.ms === "number" && Number.isFinite(event.ms))
    parts.push(`${formatNumber(event.ms)} ms`);
  return parts.join(" · ");
}

/** Render received events directly, without replay delays or inferred agent work. */
export class Progress {
  constructor() {
    this.host = document.getElementById("agent-lanes");
    this.plan = document.getElementById("plan-text");
    this.todos = document.getElementById("todo-list");
    this.notices = document.getElementById("run-notices");
    if (!this.host || !this.plan || !this.todos || !this.notices) {
      throw new Error(
        "Progress requires #agent-lanes, #plan-text, #todo-list and #run-notices.",
      );
    }
    this.reset();
  }

  reset(refine = false) {
    this.seen = new Set();
    this.lanes = new Map();
    this.finished = false;
    this.host.replaceChildren();
    this.notices.replaceChildren();
    this.todos.replaceChildren();
    this.todos.hidden = true;
    this.plan.textContent = refine
      ? "Waiting for the refinement service."
      : "Waiting for the scouting service.";
    for (const [name, label] of LANES) {
      const section = el("section", null, "agent-lane");
      section.dataset.agent = name;
      section.setAttribute("aria-label", `${label} activity`);
      const header = el("div", null, "lane-header");
      const state = el("span", "No events", "lane-state");
      state.dataset.state = "idle";
      header.append(el("span", label, "lane-name"), state);
      const log = el("ul", null, "lane-log");
      log.setAttribute("role", "log");
      log.setAttribute("aria-live", "polite");
      log.setAttribute("aria-relevant", "additions");
      log.setAttribute("aria-label", `${label} events`);
      section.append(header, log);
      this.host.append(section);
      this.lanes.set(name, { section, state, log, observed: false });
    }
  }

  renderTodos(todos) {
    this.todos.replaceChildren();
    this.todos.hidden = todos.length === 0;
    for (const todo of todos) {
      const status = typeof todo.status === "string" ? todo.status : "unknown";
      const item = el("li");
      item.dataset.status = status;
      const mark = el(
        "span",
        status === "completed" ? "✓" : status === "in_progress" ? "•" : "○",
        "todo-mark",
      );
      mark.setAttribute("aria-hidden", "true");
      const statusText = status.replaceAll("_", " ");
      item.title = statusText;
      item.append(
        mark,
        el("span", `${statusText}: `, "sr-only"),
        el("span", todo.content),
      );
      this.todos.append(item);
    }
  }

  add(event) {
    if (!event || typeof event !== "object") return false;
    const key = JSON.stringify([
      event.type,
      event.agent,
      event.text,
      event.ts,
      event.ms,
      event.engine,
    ]);
    if (this.seen.has(key)) return false;
    this.seen.add(key);
    const text = event.text == null ? "" : String(event.text);
    const lane = this.lanes.get(laneFor(event));
    lane.observed = true;
    const row = el("li", null, "event-row");
    row.dataset.eventText = text;
    row.dataset.eventType = event.type || "";
    if (event.engine) row.dataset.engine = event.engine;
    if (event.type === "tool") row.classList.add("event-tool");
    if (event.type === "skeptic" || lane === this.lanes.get("skeptic"))
      row.classList.add("event-skeptic");
    row.append(
      el("span", eventLabel(event), "event-label"),
      el("span", readable(text), "event-text"),
    );
    if (readable(text) !== text) row.title = text.length > 600 ? `${text.slice(0, 597)}…` : text;
    const followLog =
      lane.log.scrollHeight - lane.log.scrollTop - lane.log.clientHeight < 32;
    lane.log.append(row);
    if (followLog) lane.log.scrollTop = lane.log.scrollHeight;

    if (this.finished) {
      lane.state.textContent = "Reported";
      lane.state.dataset.state = "reported";
    } else if (event.type === "subagent_start") {
      lane.state.textContent = "Running";
      lane.state.dataset.state = "active";
    } else if (event.type === "subagent_result" || event.type === "final") {
      lane.state.textContent = "Reported";
      lane.state.dataset.state = "complete";
    } else if (event.type === "error") {
      lane.state.textContent = "Error reported";
      lane.state.dataset.state = "error";
    } else if (lane.state.dataset.state === "idle") {
      lane.state.textContent = "Observed";
      lane.state.dataset.state = "observed";
    }

    if (event.type === "plan" || event.type === "todo") {
      const todos = parseTodos(text);
      if (todos) {
        this.plan.textContent = "Director to-do plan";
        this.renderTodos(todos);
      } else {
        this.plan.textContent = text;
        this.todos.replaceChildren();
        this.todos.hidden = true;
      }
    }
    if (event.type === "relaxed" || event.type === "fallback") {
      const notice = el(
        "p",
        text,
        event.type === "relaxed" ? "relaxed-notice" : "fallback-notice",
      );
      this.notices.append(notice);
    }
    return true;
  }

  finish() {
    this.finished = true;
    for (const lane of this.lanes.values()) {
      if (!lane.observed) continue;
      lane.state.textContent = "Reported";
      lane.state.dataset.state = "reported";
    }
  }
}
