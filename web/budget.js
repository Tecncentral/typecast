// Travel and budget for the shortlist: drive minutes from a production base (OSRM, no traffic;
// straight-line distance only as a labelled fallback) with a max-minutes slider that dims picks on
// the map, and Owner 2's cost comparison (found location vs build a set vs standing set vs CGI,
// low / likely / high) with each building's CoStar rent as a reference. Every dollar figure carries
// the scenario-estimate line.
import { el } from "./utils.js";
import { setMapTravel } from "./map.js";

const money = (v) => (typeof v === "number" ? `$${Math.round(v).toLocaleString("en-US")}` : "unknown");
const rate = (v) => `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const DEFAULT_BASE = { "Los Angeles": "la-studio-zone", Houston: "hou-downtown" };
const OPTIONS = [
  ["found_location", "Shoot at the found location"],
  ["standing_set", "Rent a standing set"],
  ["build_set", "Build the set on a stage"],
  ["cgi", "Create it in CGI"],
];

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(data.detail || `The request failed (${response.status}).`);
  return data;
}

export function renderBudget(host, mapHost, picks) {
  const token = (host.__token = (host.__token || 0) + 1);
  const live = () => host.__token === token;
  host.replaceChildren();
  if (!picks?.length) return;
  const city = picks[0]?.property?.city;
  const state = { base: DEFAULT_BASE[city] || "la-studio-zone", max: 90, sqft: 2000, days: 2, travel: null, costs: null, selected: 0 };
  const rows = picks.map((p) => ({ property_id: p.property.property_id, address: p.property.address, lat: p.property.lat, lon: p.property.lon }));

  const travelBox = el("section", undefined, "budget-travel");
  const travelHead = el("div", undefined, "budget-row");
  const baseLabel = el("label", undefined, "budget-field");
  baseLabel.append(el("span", "Production base"));
  const baseSelect = el("select");
  baseLabel.append(baseSelect);
  const maxLabel = el("label", undefined, "budget-field budget-field--slider");
  const maxText = el("span");
  const slider = el("input");
  slider.type = "range";
  slider.min = "10";
  slider.max = "120";
  slider.step = "5";
  slider.value = String(state.max);
  maxLabel.append(maxText, slider);
  travelHead.append(baseLabel, maxLabel);
  const travelNote = el("p", "Loading drive times…", "budget-note");
  travelBox.append(el("h3", "Travel from your base"), travelHead, travelNote);

  const costBox = el("section", undefined, "budget-costs");
  const costHead = el("div", undefined, "budget-row");
  const sqftLabel = el("label", undefined, "budget-field");
  sqftLabel.append(el("span", "Scene size (sq ft)"));
  const sqft = el("input");
  sqft.type = "number";
  sqft.min = "100";
  sqft.step = "100";
  sqft.value = String(state.sqft);
  sqftLabel.append(sqft);
  const daysLabel = el("label", undefined, "budget-field");
  daysLabel.append(el("span", "Shoot days"));
  const days = el("input");
  days.type = "number";
  days.min = "1";
  days.max = "60";
  days.value = String(state.days);
  daysLabel.append(days);
  costHead.append(sqftLabel, daysLabel);
  const pickChoice = el("div", undefined, "budget-picks");
  const bars = el("div", undefined, "budget-bars");
  const table = el("div", undefined, "budget-table");
  const line = el("p", "Scenario estimate from public pricing ranges and CoStar rent data, not verified savings.", "budget-dollar-line");
  costBox.append(el("h3", "What this scene costs"), costHead, line, pickChoice, bars, table);
  host.append(travelBox, costBox);

  function paintTravel() {
    maxText.textContent = `Max drive: ${state.max} min`;
    if (!state.travel) return;
    setMapTravel(mapHost, state.travel.rows, state.max);
    const within = rows.filter((r) => {
      const m = state.travel.rows[r.property_id]?.minutes;
      return typeof m !== "number" || m <= state.max;
    }).length;
    travelNote.textContent = `${within} of ${rows.length} picks within ${state.max} min of ${state.travel.base.label}. ${state.travel.note}`;
  }

  function paintCosts() {
    const c = state.costs;
    if (!c) return;
    pickChoice.replaceChildren(el("span", "Found location:", "budget-picks-label"));
    c.picks.forEach((p, i) => {
      const b = el("button", p.address || p.property_id);
      b.type = "button";
      b.setAttribute("aria-pressed", String(i === state.selected));
      b.addEventListener("click", () => {
        state.selected = i;
        paintCosts();
      });
      pickChoice.append(b);
    });
    const chosen = c.picks[state.selected] || c.picks[0];
    const options = { found_location: chosen.found_location, ...c.alternatives };
    const scale = Math.max(...Object.values(options).map((o) => o.total_high_usd || 0), 1);
    bars.replaceChildren();
    for (const [key, label] of OPTIONS) {
      const o = options[key];
      if (!o) continue;
      const row = el("div", undefined, `budget-bar${key === "found_location" ? " is-found" : ""}`);
      const head = el("div", undefined, "budget-bar-head");
      head.append(el("span", label), el("strong", money(o.total_usd)));
      const track = el("div", undefined, "budget-bar-track");
      const range = el("span", undefined, "budget-bar-range");
      range.style.left = `${(o.total_low_usd / scale) * 100}%`;
      range.style.width = `${Math.max(0.6, ((o.total_high_usd - o.total_low_usd) / scale) * 100)}%`;
      const mark = el("span", undefined, "budget-bar-mark");
      mark.style.left = `${(o.total_usd / scale) * 100}%`;
      track.append(range, mark);
      row.append(head, track, el("span", `range ${money(o.total_low_usd)} – ${money(o.total_high_usd)}`, "budget-bar-range-text"));
      row.title = (o.lines || []).map((l) => `${l.label}: ${money(l.amount_usd)} (${l.formula})`).join("\n");
      bars.append(row);
    }
    table.replaceChildren(el("p", c.note, "budget-note"));
    const list = el("ul");
    for (const p of c.picks) {
      const t = state.travel?.rows?.[p.property_id];
      const drive = typeof t?.minutes === "number" ? `${t.minutes} min drive`
        : typeof t?.straight_line_km === "number" ? `${t.straight_line_km} km straight-line` : "drive time unknown";
      const zone = t?.studio_zone ? (t.studio_zone.inside ? "inside LA studio zone" : "outside LA studio zone") : null;
      const rent = p.rent.shown
        ? `${p.rent.label}: ${rate(p.rent.usd_per_sf_year)}/sq ft/yr · ${p.rent.source}${p.rent.age_years > 3 ? ` · ${p.rent.age_years} years old` : ""}`
        : "No reliable rent for this building (not shown)";
      const item = el("li");
      item.append(el("strong", p.address || p.property_id), el("span", [drive, zone].filter(Boolean).join(" · ")), el("span", rent, p.rent.shown ? "" : "is-muted"));
      list.append(item);
    }
    table.append(list);
  }

  async function loadTravel() {
    travelNote.textContent = "Loading drive times…";
    try {
      const data = await post("/api/shortlist/commutes", { base: state.base, picks: rows });
      if (!live()) return;
      state.travel = data;
      paintTravel();
      loadCosts();
    } catch (error) {
      if (live()) travelNote.textContent = error.message;
      loadCosts();
    }
  }

  async function loadCosts() {
    const minutes = {};
    for (const [pid, row] of Object.entries(state.travel?.rows || {}))
      if (typeof row.minutes === "number") minutes[pid] = row.minutes;
    try {
      const data = await post("/api/shortlist/costs", {
        picks: rows.map(({ property_id, address }) => ({ property_id, address })),
        scene_sqft: state.sqft,
        shoot_days: state.days,
        drive_minutes: minutes,
      });
      if (!live()) return;
      state.costs = data;
      paintCosts();
    } catch (error) {
      if (live()) bars.replaceChildren(el("p", error.message, "budget-note"));
    }
  }

  fetch("/api/shortlist/bases", { cache: "no-store" })
    .then((r) => r.json())
    .then((d) => {
      if (!live()) return;
      for (const b of d.bases || []) {
        const option = el("option", b.label);
        option.value = b.id;
        option.selected = b.id === state.base;
        baseSelect.append(option);
      }
    })
    .catch(() => {});
  baseSelect.addEventListener("change", () => {
    state.base = baseSelect.value;
    loadTravel();
  });
  slider.addEventListener("input", () => {
    state.max = Number(slider.value);
    paintTravel();
  });
  let timer;
  const recost = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const s = Number(sqft.value), d = Number(days.value);
      if (s >= 100 && d >= 1 && d <= 60) {
        state.sqft = s;
        state.days = Math.round(d);
        loadCosts();
      }
    }, 350);
  };
  sqft.addEventListener("input", recost);
  days.addEventListener("input", recost);
  paintTravel();
  loadTravel();
}
