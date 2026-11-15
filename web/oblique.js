import * as L from "./vendor/leaflet/leaflet-src.esm.js";
import { el, assetUrl } from "./utils.js";

const $ = (s) => document.querySelector(s);
const DIRECTIONS = ["north", "east", "south", "west"];
const PRESETS = {
  film: [
    "Brick alley with fire escapes and dumpsters for a night chase",
    "Rooftop parking deck with a skyline view",
    "Fountain plaza with wide steps",
    "Industrial loading docks with room for trucks",
    "Hillside trail through dry brush",
    "Palm-lined path along the beach",
  ],
  sites: [
    "Vacant flat dirt lot next to a freeway",
    "Empty paved lot for a pop-up market",
    "Large flat open land for a warehouse",
  ],
};
const ASK_IDEAS = [
  "How tall are the buildings right around here?",
  "Are there pools or parked cars on nearby parcels?",
  "When was the imagery here captured?",
];
const CHAT_IDEAS = [
  "Night, wet pavement, practical street lights",
  "Add a food truck with string lights",
  "Build a small modern warehouse on the empty lot",
];

let current = null; // last search response
let place = null; // open place
let direction = "north";
let map = null;
let markers = [];
let busy = false;
let buildingToken = 0;

const pct = (score) => (typeof score === "number" ? ` (${Math.round(score * 100)}% confidence)` : "");
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function buildingRows(b) {
  const rows = [];
  if (b.type) rows.push(["Type", `${b.type[0].toUpperCase()}${b.type.slice(1)}${pct(b.type_score)}`]);
  const size = [b.footprint_m2 ? `${Math.round(b.footprint_m2).toLocaleString("en-US")} m² footprint` : null,
    b.height_m ? `about ${Math.round(b.height_m)} m tall` : "height unknown",
    b.stories ? plural(b.stories, "storey") : null].filter(Boolean);
  rows.push(["Size", size.join(" · ")]);
  if (b.roof_shape || b.roof_material)
    rows.push(["Roof", [b.roof_shape ? `${b.roof_shape}${pct(b.roof_shape_score)}` : null,
      b.roof_material ? `${b.roof_material}${pct(b.roof_material_score)}` : null].filter(Boolean).join(" · ")]);
  const objects = b.roof_objects.map((o) => plural(o.count, o.label));
  if (b.solar === false && !b.roof_objects.some((o) => o.label.startsWith("solar"))) objects.push("no solar");
  rows.push(["On the roof", objects.length ? objects.join(" · ") : "nothing detected"]);
  rows.push(["Roof issues", b.roof_defects.length
    ? b.roof_defects.map((d) => `${d.label}${typeof d.percent === "number" ? ` on ${Math.round(d.percent)}%` : ""}`).join(" · ")
    : "none detected"]);
  if (typeof b.ground_elevation_m === "number") rows.push(["Ground", `${Math.round(b.ground_elevation_m)} m above sea level`]);
  if (b.imagery?.date) rows.push(["Imagery", `${b.imagery.date}${b.imagery.gsd_m ? ` · ${Math.round(b.imagery.gsd_m * 100)} cm per pixel` : ""}`]);
  return rows;
}

const BUILD_IDEAS = [
  "Add a rooftop solar array across the open flat roof, around the skylights and units",
  "Turn the flat roof into a rooftop bar with string lights",
  "Add one more storey with glass walls on top of the building",
];

async function loadBuilding(r) {
  const token = ++buildingToken;
  const section = $("#ob-building");
  const body = $("#ob-building-body");
  section.hidden = false;
  body.replaceChildren(el("p", "Reading Vexcel Structure for this spot…", "ob-chat-note"));
  try {
    const b = await post("/api/oblique/building", { search_id: current.search_id, index: r.index, direction: "north" }, 90000);
    if (token !== buildingToken) return;
    r.building = b;
    if (!b.found) {
      body.replaceChildren(el("p", b.reason || "No building record here.", "ob-chat-note"));
      return;
    }
    const list = el("dl");
    for (const [k, v] of buildingRows(b)) list.append(el("dt", k), el("dd", v));
    const ideas = el("div", undefined, "ob-chat-suggest");
    for (const idea of BUILD_IDEAS) {
      const chip = el("button", idea, "ob-chip ob-chip--small");
      chip.type = "button";
      chip.addEventListener("click", () => {
        $("#ob-chat-input").value = idea;
        $("#ob-chat-input").scrollIntoView({ block: "center", behavior: "smooth" });
        $("#ob-chat-input").focus({ preventScroll: true });
      });
      ideas.append(chip);
    }
    body.replaceChildren(
      list,
      el("p", `${b.others_nearby ? `${plural(b.others_nearby, "other building")} within 25 m; the nearest is shown. ` : ""}Estimates from imagery: not load capacity, zoning, permits or ownership.`, "ob-fine"),
      el("p", "Plan on this building (sends the building facts with your edit):", "ob-chat-note"),
      ideas,
    );
  } catch (error) {
    if (token === buildingToken) body.replaceChildren(el("p", error.message, "ob-chat-note"));
  }
}
let city = null; // open 3D view
let cityToken = 0;

function closeCity() {
  cityToken += 1;
  city?.dispose();
  city = null;
  $("#ob-3d").hidden = true;
  $("#ob-3d").replaceChildren();
  $("#ob-image").hidden = false;
  $("#ob-credit").textContent = "Vexcel oblique imagery · 45° · capture date in the image corner";
  $("#ob-chat-send").disabled = false;
}

async function openCity() {
  closeCity();
  const token = ++cityToken;
  for (const b of document.querySelectorAll("#ob-dirs button"))
    b.setAttribute("aria-pressed", String(b.dataset.dir === "3d"));
  $("#ob-image").hidden = true;
  $("#ob-ai-label").hidden = true;
  $("#ob-compare").hidden = true;
  $("#ob-3d").hidden = false;
  $("#ob-chat-send").disabled = true;
  $("#ob-chat-note").textContent = "Reimagine works on the oblique photos; pick a direction to edit.";
  const loading = $("#ob-loading");
  loading.hidden = false;
  loading.textContent = "Finding Vexcel 3D Cities tiles…";
  try {
    const { mountCity3D } = await import("./city3d.js");
    if (token !== cityToken) return;
    const view = await mountCity3D($("#ob-3d"), place.lat, place.lon, {
      footprint: place.building?.found ? place.building.footprint : null,
      onStatus: (text) => {
        if (token !== cityToken) return;
        loading.hidden = !text;
        loading.textContent = text;
      },
    });
    if (token !== cityToken) return view.dispose();
    city = view;
    const [from, to] = view.place.capture || [];
    $("#ob-credit").textContent = `Vexcel 3D Cities · textured city mesh${from ? ` · captured ${from} – ${to}` : ""} · drag to orbit, scroll to zoom · the pin marks the place`;
  } catch (error) {
    if (token === cityToken) loading.textContent = error.message;
  }
}

async function post(path, body, timeout = 180000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
      cache: "no-store",
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw Error(data.detail || `The request failed (${response.status}).`);
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw Error("This is taking too long. Please try again.");
    if (error instanceof TypeError) throw Error("Cannot reach the local service. Check that it is running.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function status(text, kind = "") {
  const node = $("#ob-status");
  node.hidden = !text;
  node.textContent = text || "";
  node.dataset.kind = kind;
}

function fmt(value, unit, digits = 0) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value.toLocaleString("en-US", { maximumFractionDigits: digits })}${unit}`
    : "unknown";
}

function terrainText(t) {
  if (!t || t.status !== "estimated") return "Terrain unknown";
  const height =
    typeof t.above_ground_m === "number"
      ? t.above_ground_m < 2
        ? "open ground at the centre"
        : `${fmt(t.above_ground_m, " m")} structure or canopy at the centre`
      : "";
  return `Ground ${fmt(t.ground_m, " m")} · relief ${fmt(t.relief_m, " m", 1)} over 200 m · steepest ${fmt(t.max_slope_deg, "°", 1)}${height ? " · " + height : ""}`;
}

function matchLine(result) {
  return result.match
    ? `${Math.round(result.match.score * 100)}% match · ${result.match.reason}`
    : "Not scored by the vision model; ordered by Vexcel similarity";
}

function presetButtons(host, list) {
  for (const text of list) {
    const button = el("button", text, "ob-chip");
    button.type = "button";
    button.addEventListener("click", () => {
      $("#ob-query").value = text;
      run();
    });
    host.append(button);
  }
}

function renderMap(result) {
  if (!map) {
    map = L.map($("#ob-map"), { scrollWheelZoom: false, zoomAnimation: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    }).addTo(map);
  }
  markers.forEach((m) => m.remove());
  markers = result.results.map((r) =>
    L.marker([r.lat, r.lon], {
      icon: L.divIcon({
        className: `ob-pin${r.rank <= 3 ? " ob-pin--top" : ""}`,
        html: `<span>${r.rank}</span>`,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
      }),
      title: `Place ${r.rank}`,
    })
      .on("click", () => open(r))
      .addTo(map),
  );
  const bounds = L.latLngBounds(result.results.map((r) => [r.lat, r.lon]));
  if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
  requestAnimationFrame(() => map.invalidateSize());
}

function renderResults(result) {
  current = result;
  const grid = $("#ob-grid");
  grid.replaceChildren();
  $("#ob-results").hidden = !result.results.length;
  $("#ob-meta").textContent = `${result.area_label} · ${result.results.length} places · ${result.seconds}s · Vexcel search, obliques, terrain`;
  if (!result.results.length) {
    status("Vexcel found nothing like that in this area. Try other words or another area.", "warn");
    return;
  }
  status("");
  for (const r of result.results) {
    const card = el("li", undefined, "ob-card");
    const button = el("button", undefined, "ob-card-button");
    button.type = "button";
    button.setAttribute("aria-label", `Open place ${r.rank}`);
    const media = el("span", undefined, "ob-card-media");
    const src = r.image ? assetUrl(r.image.path) : "";
    if (src) {
      const img = el("img");
      img.src = src;
      img.alt = `45-degree oblique of place ${r.rank}`;
      img.loading = "lazy";
      media.append(img);
    } else media.append(el("span", "No oblique in Vexcel coverage here", "ob-card-missing"));
    media.append(el("span", String(r.rank).padStart(2, "0"), "ob-rank"));
    const body = el("span", undefined, "ob-card-body");
    const score = r.match ? Math.round(r.match.score * 100) : null;
    const head = el("span", undefined, "ob-card-head");
    head.append(
      el("span", score === null ? "Unscored" : `${score}% match`, `ob-score${score !== null && score >= 50 ? " is-good" : ""}`),
      el("span", `${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}`, "ob-coords"),
    );
    body.append(
      head,
      el("span", r.match?.reason || "Ordered by Vexcel similarity", "ob-reason"),
      el("span", terrainText(r.terrain), "ob-terrain"),
    );
    button.append(media, body);
    button.addEventListener("click", () => open(r));
    card.append(button);
    grid.append(card);
  }
  renderMap(result);
}

async function run(event) {
  event?.preventDefault();
  if (busy) return;
  const query = $("#ob-query").value.trim();
  if (!query) return;
  busy = true;
  $("#ob-run").disabled = true;
  status("Searching Vexcel aerials, fetching 45° obliques and terrain, then scoring what is visible… about 15 s.", "busy");
  try {
    renderResults(await post("/api/oblique/search", { query, area: $("#ob-area").value }));
    $("#ob-results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    status(error.message, "error");
  } finally {
    busy = false;
    $("#ob-run").disabled = false;
  }
}

function facts(r) {
  const host = $("#ob-facts");
  host.replaceChildren();
  const rows = [
    ["Match", r.match ? `${Math.round(r.match.score * 100)}% · ${r.match.reason}` : "Not scored"],
    ["Vexcel similarity", r.vexcel_score.toFixed(3)],
    ["Ground", r.terrain?.status === "estimated" ? `${fmt(r.terrain.ground_m, " m")} above sea level` : "unknown"],
    ["Relief", r.terrain?.status === "estimated" ? `${fmt(r.terrain.relief_m, " m", 1)} over a 200 m cross · steepest ${fmt(r.terrain.max_slope_deg, "°", 1)}` : "unknown"],
    ["At the centre", r.terrain?.status === "estimated" && typeof r.terrain.above_ground_m === "number"
      ? (r.terrain.above_ground_m < 2 ? "Open ground (surface ≈ terrain)" : `${fmt(r.terrain.above_ground_m, " m")} structure or canopy`)
      : "unknown"],
    ["Location", `${r.lat.toFixed(5)}, ${r.lon.toFixed(5)}`],
  ];
  const list = el("dl");
  for (const [k, v] of rows) list.append(el("dt", k), el("dd", v));
  host.append(list, el("p", "Terrain and heights are Vexcel estimates; they do not establish access, permission or clearance.", "ob-fine"));
}

let chatState = { label: "", versions: [] };
let showing = "imagined";
let selected = null; // index of the version on screen; null = latest

function paint() {
  const latest = chatState.versions[selected ?? chatState.versions.length - 1];
  const imagined = showing === "imagined" && latest;
  const path = imagined ? latest.path : place.views?.[direction];
  const img = $("#ob-image");
  $("#ob-loading").hidden = Boolean(path);
  if (path) img.src = assetUrl(path);
  img.alt = imagined ? `AI-imagined version: ${latest.message}` : `Vexcel oblique, ${direction}`;
  $("#ob-ai-label").hidden = !imagined;
  $("#ob-ai-label").textContent = imagined ? `${chatState.label || "AI-imagined, not the real place"} · ${latest.model}` : "";
  $("#ob-compare").hidden = !latest;
  for (const b of document.querySelectorAll("#ob-compare button"))
    b.setAttribute("aria-pressed", String(b.dataset.show === showing));
  const log = $("#ob-chat-log");
  log.replaceChildren();
  for (const [i, v] of chatState.versions.entries()) {
    const item = el("li", undefined, "ob-msg");
    item.append(el("span", v.message, "ob-msg-text"));
    const thumb = el("button", undefined, "ob-msg-thumb");
    thumb.type = "button";
    const t = el("img");
    t.src = assetUrl(v.path);
    t.alt = `Version ${i + 1}`;
    thumb.append(t);
    thumb.setAttribute("aria-pressed", String(v === latest && showing === "imagined"));
    thumb.addEventListener("click", () => {
      selected = i;
      showing = "imagined";
      paint();
    });
    item.append(thumb);
    log.append(item);
  }
}

async function loadView(dir) {
  closeCity();
  direction = dir;
  for (const b of document.querySelectorAll("#ob-dirs button"))
    b.setAttribute("aria-pressed", String(b.dataset.dir === dir));
  place.views ||= {};
  showing = "imagined";
  selected = null;
  chatState = { label: "", versions: [] };
  $("#ob-loading").hidden = false;
  $("#ob-loading").textContent = "Loading the oblique…";
  paint();
  try {
    const data = await post("/api/oblique/view", { search_id: current.search_id, index: place.index, direction: dir });
    if (place && direction === dir) {
      if (!data.path) {
        $("#ob-loading").textContent = "No Vexcel oblique from this side here.";
        return;
      }
      place.views[dir] = data.path;
      chatState = data.chat || chatState;
      paint();
    }
  } catch (error) {
    $("#ob-loading").textContent = error.message;
  }
}

function open(r) {
  place = r;
  $("#ob-place-eyebrow").textContent = `Place ${r.rank} · ${current.area_label}`;
  $("#ob-place-title").textContent = current.query;
  facts(r);
  const dirs = $("#ob-dirs");
  dirs.replaceChildren();
  for (const dir of DIRECTIONS) {
    const b = el("button", dir[0].toUpperCase() + dir.slice(1));
    b.type = "button";
    b.dataset.dir = dir;
    b.addEventListener("click", () => loadView(dir));
    dirs.append(b);
  }
  const three = el("button", "3D");
  three.type = "button";
  three.dataset.dir = "3d";
  three.title = "Vexcel 3D Cities: the textured city mesh around this place";
  three.addEventListener("click", openCity);
  dirs.append(three);
  loadBuilding(r);
  $("#ob-answer").hidden = true;
  $("#ob-answer").replaceChildren();
  const askSuggest = $("#ob-ask-suggest");
  askSuggest.replaceChildren();
  for (const idea of ASK_IDEAS) {
    const b = el("button", idea, "ob-chip ob-chip--small");
    b.type = "button";
    b.addEventListener("click", () => {
      $("#ob-ask-input").value = idea;
      $("#ob-ask-form").requestSubmit();
    });
    askSuggest.append(b);
  }
  const suggest = $("#ob-chat-suggest");
  suggest.replaceChildren();
  for (const idea of CHAT_IDEAS) {
    const b = el("button", idea, "ob-chip ob-chip--small");
    b.type = "button";
    b.addEventListener("click", () => {
      $("#ob-chat-input").value = idea;
      $("#ob-chat-input").focus();
    });
    suggest.append(b);
  }
  $("#ob-chat-note").textContent = `Each message edits the latest version with ${window.__obModel || "the image model"}. Every result is labelled AI-imagined.`;
  if (r.image) place.views = { [r.image.direction]: r.image.path };
  $("#ob-place").showModal();
  loadView(r.image?.direction || "north");
}

// Minimal, safe rendering of the model's answer: lines, "- " bullets, **bold** and `code`, as DOM nodes.
function inline(text) {
  const frag = document.createDocumentFragment();
  for (const part of String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/)) {
    if (!part) continue;
    if (part.startsWith("**")) frag.append(el("strong", part.slice(2, -2)));
    else if (part.startsWith("`")) frag.append(el("code", part.slice(1, -1)));
    else frag.append(document.createTextNode(part));
  }
  return frag;
}
function renderAnswer(host, data) {
  host.replaceChildren();
  let list = null;
  for (const line of String(data.answer || "").split("\n")) {
    const text = line.trim();
    if (!text) { list = null; continue; }
    if (/^[-*] /.test(text)) {
      list ||= host.appendChild(el("ul"));
      const item = el("li");
      item.append(inline(text.slice(2)));
      list.append(item);
    } else {
      list = null;
      const para = el("p");
      para.append(inline(text));
      host.append(para);
    }
  }
  const tools = el("p", undefined, "ob-tools");
  tools.append(el("span", "Vexcel MCP", "ob-tools-label"));
  for (const call of data.calls || [])
    tools.append(el("span", `${call.tool}${call.ok ? "" : " (not run)"}`, `ob-tool${call.ok ? "" : " is-skipped"}`));
  if (!(data.calls || []).length) tools.append(el("span", "no tool calls", "ob-tool is-skipped"));
  host.append(tools);
  host.hidden = false;
}

async function ask(event) {
  event.preventDefault();
  const input = $("#ob-ask-input");
  const question = input.value.trim();
  if (!question || !place) return;
  const button = $("#ob-ask-send");
  const host = $("#ob-answer");
  button.disabled = input.disabled = true;
  host.hidden = false;
  host.replaceChildren(el("p", "Asking Vexcel… about 15–30 s.", "ob-chat-note"));
  try {
    renderAnswer(host, await post("/api/oblique/ask", { search_id: current.search_id, index: place.index, question }, 120000));
  } catch (error) {
    host.replaceChildren(el("p", error.message, "ob-chat-note"));
  } finally {
    button.disabled = input.disabled = false;
  }
}

async function send(event) {
  event.preventDefault();
  const input = $("#ob-chat-input");
  const message = input.value.trim();
  if (!message || !place) return;
  const button = $("#ob-chat-send");
  button.disabled = true;
  input.disabled = true;
  $("#ob-chat-note").textContent = "Reimagining… about 10–30 s.";
  try {
    chatState = await post("/api/oblique/reimagine", {
      search_id: current.search_id,
      index: place.index,
      direction,
      message,
    }, 300000);
    input.value = "";
    showing = "imagined";
    selected = null;
    paint();
    $("#ob-chat-note").textContent = "Done. Send another change to build on it, or switch Real / Imagined.";
  } catch (error) {
    $("#ob-chat-note").textContent = error.message;
  } finally {
    button.disabled = false;
    input.disabled = false;
  }
}

async function init() {
  presetButtons($("#ob-film"), PRESETS.film);
  presetButtons($("#ob-sites"), PRESETS.sites);
  $("#ob-form").addEventListener("submit", run);
  $("#ob-chat-form").addEventListener("submit", send);
  $("#ob-ask-form").addEventListener("submit", ask);
  $("#ob-close").addEventListener("click", () => $("#ob-place").close());
  $("#ob-place").addEventListener("close", closeCity);
  for (const b of document.querySelectorAll("#ob-compare button"))
    b.addEventListener("click", () => {
      showing = b.dataset.show;
      paint();
    });
  try {
    const response = await fetch("/api/oblique/areas", { cache: "no-store" });
    const data = await response.json();
    window.__obModel = `${data.image_model} (${data.image_quality})`;
    for (const area of data.areas) {
      const option = el("option", `${area.label} · ${area.city}`);
      option.value = area.id;
      $("#ob-area").append(option);
    }
  } catch {
    status("Cannot reach the local service. Check that it is running.", "error");
  }
}

init();
