// Re-homes budget.js output, without changing its logic:
// - its four controls become a filter bar above the shortlist (base, max drive, scene size, days);
// - its cost comparison opens in a side panel when a card is clicked, for that card's pick,
//   with dollar figures counting up from zero.
// Moved nodes keep budget.js's own listeners, so filters still re-query drive times and costs.
const $ = (s) => document.querySelector(s);
const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

let panel = null;
let costBox = null;
let observer = null;

export function arrangeBudget() {
  const budget = $("#budget");
  const shortlist = $("#shortlist-section");
  if (!budget || !shortlist) return;
  $("#budget-section").hidden = true;

  let bar = $("#filter-bar");
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "filter-bar";
    bar.className = "filter-bar";
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "Filter the shortlist");
    shortlist.insertBefore(bar, $("#results"));
  }
  bar.replaceChildren();
  const fields = budget.querySelectorAll(".budget-field");
  if (!fields.length) { bar.hidden = true; return; }
  bar.hidden = false;
  fields.forEach((f) => bar.append(f));
  const travelNote = budget.querySelector(".budget-travel .budget-note");
  const inputNote = budget.querySelector(".budget-input-note");
  const notes = document.createElement("div");
  notes.className = "filter-notes";
  if (travelNote) notes.append(travelNote);
  if (inputNote) notes.append(inputNote);
  bar.append(notes);

  costBox = budget.querySelector(".budget-costs");
  if (panel && costBox) mountCosts();

  // Live filtering: the drive slider (budget.js) and a budget slider (here) hide cards.
  filters.data = { travel: null, costs: null, max: null };
  filters.budget = null;
  filters.budgetField = null;
  document.querySelectorAll(".filter-summary").forEach((n) => n.remove());
  filters.summary = document.createElement("div");
  filters.summary.className = "filter-summary";
  filters.summary.setAttribute("role", "status");
  bar.after(filters.summary);
  if (!budget.__filtersBound) {
    budget.__filtersBound = true;
    budget.addEventListener("budget:data", (e) => {
      filters.data = e.detail;
      ensureBudgetSlider();
      applyFilters();
    });
  }
}

/* ---------------- live filters ---------------- */
const filters = { data: null, budget: null, budgetField: null, summary: null };
const money = (v) => "$" + Math.round(v).toLocaleString("en-US");
const costOf = (i) => {
  const v = filters.data?.costs?.picks?.[i]?.found_location?.total_usd;
  return typeof v === "number" ? v : null;
};
const driveOf = (i, id) => {
  const row = filters.data?.travel?.rows?.[id];
  return typeof row?.minutes === "number" ? row.minutes : null;
};

// Budget runs from $0 to a large ceiling. The track is curved (cubic) so the low end moves in
// about $5 steps while the far right still reaches the ceiling; every value is a multiple of $5.
// The number box beside it takes any exact amount, also in $5 steps.
const BUDGET_FLOOR_MAX = 250000;
const POSITIONS = 2000;
const round5 = (v) => Math.max(0, Math.round(v / 5) * 5);
const toDollars = (pos, max) => round5(max * Math.pow(pos / POSITIONS, 3));
const toPosition = (dollars, max) => Math.round(POSITIONS * Math.cbrt(Math.min(1, Math.max(0, dollars / max))));

function ensureBudgetSlider() {
  const totals = (filters.data?.costs?.picks || []).map((_, i) => costOf(i)).filter((v) => v != null);
  if (!totals.length || !$("#filter-bar")) return;
  const max = Math.max(BUDGET_FLOOR_MAX, Math.ceil(Math.max(...totals) / 5) * 5);
  if (!filters.budgetField) {
    const label = document.createElement("div");
    label.className = "budget-field budget-field--slider filter-budget";
    const text = document.createElement("span");
    const row = document.createElement("div");
    row.className = "filter-budget-row";
    const input = document.createElement("input");
    input.type = "range";
    input.min = "0";
    input.max = String(POSITIONS);
    input.step = "1";
    input.setAttribute("aria-label", "Max budget");
    const exact = document.createElement("input");
    exact.type = "number";
    exact.min = "0";
    exact.step = "5";
    exact.inputMode = "numeric";
    exact.setAttribute("aria-label", "Max budget in dollars");
    row.append(input, exact);
    label.append(text, row);
    $("#filter-bar").insertBefore(label, $("#filter-bar .filter-notes"));
    input.addEventListener("input", () => {
      filters.budget = toDollars(Number(input.value), filters.budgetMax);
      exact.value = String(filters.budget);
      applyFilters();
    });
    exact.addEventListener("input", () => {
      if (exact.value === "") return;
      filters.budget = round5(Math.min(Number(exact.value), filters.budgetMax));
      input.value = String(toPosition(filters.budget, filters.budgetMax));
      applyFilters();
    });
    exact.addEventListener("change", () => { exact.value = String(filters.budget); });
    filters.budgetField = { label, text, input, exact };
  }
  filters.budgetMax = max;
  filters.budgetField.exact.max = String(max);
  if (filters.budget == null || filters.budget > max) filters.budget = max; // start by showing everything
  filters.budgetField.input.value = String(toPosition(filters.budget, max));
  filters.budgetField.exact.value = String(filters.budget);
}

function tag(card) {
  let t = card.querySelector(".filter-tags");
  if (!t) {
    t = document.createElement("p");
    t.className = "filter-tags";
    const row = card.querySelector(".pick-title-row") || card.querySelector("h3");
    row?.after(t);
  }
  return t;
}

function applyFilters() {
  const cards = [...document.querySelectorAll("#results .pick-card")];
  if (!cards.length || !filters.data) return;
  const ids = (filters.data.costs?.picks || []).map((p) => p.property_id);
  const maxDrive = filters.data.max;
  if (filters.budgetField) filters.budgetField.text.textContent = `Max budget: ${money(filters.budget)}`;
  let overDrive = 0, overBudget = 0, unknownDrive = 0;
  cards.forEach((card, i) => {
    const id = ids[i];
    const minutes = driveOf(i, id);
    const cost = costOf(i);
    // Unknown values never hide a pick: we can't say it is over a limit.
    const driveOut = minutes != null && maxDrive != null && minutes > maxDrive;
    const budgetOut = cost != null && filters.budget != null && cost > filters.budget;
    if (minutes == null) unknownDrive++;
    if (driveOut) overDrive++;
    if (budgetOut && !driveOut) overBudget++;
    card.classList.toggle("is-filtered", driveOut || budgetOut);
    tag(card).textContent = [
      minutes != null ? `${minutes} min drive` : "drive time unknown",
      cost != null ? `est. ${money(cost)}` : "cost unknown",
    ].join(" · ");
  });
  const shown = cards.length - overDrive - overBudget;
  const parts = [`Showing ${shown} of ${cards.length}`];
  if (overDrive) parts.push(`${overDrive} over the ${maxDrive} min drive`);
  if (overBudget) parts.push(`${overBudget} over ${money(filters.budget)}`);
  if (unknownDrive) parts.push(`${unknownDrive} with unknown drive time kept`);
  filters.summary.replaceChildren(document.createTextNode(parts.join(" · ")));
  if (overDrive || overBudget) {
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "filter-reset";
    reset.textContent = "Reset filters";
    reset.addEventListener("click", resetFilters);
    filters.summary.append(reset);
  }
  filters.summary.classList.toggle("is-empty", shown === 0);
}

function resetFilters() {
  const driveSlider = [...document.querySelectorAll('#filter-bar input[type="range"]')].find((x) => !x.closest(".filter-budget"));
  if (driveSlider) { driveSlider.value = driveSlider.max; driveSlider.dispatchEvent(new Event("input", { bubbles: true })); }
  if (filters.budgetField) {
    filters.budget = filters.budgetMax;
    filters.budgetField.input.value = String(POSITIONS);
    filters.budgetField.exact.value = String(filters.budget);
  }
  applyFilters();
}

function buildPanel() {
  panel = document.createElement("aside");
  panel.className = "cost-panel";
  panel.setAttribute("aria-label", "Cost savings");
  panel.hidden = true;
  panel.innerHTML = `
    <div class="cost-panel-head">
      <div><span class="cost-kicker">Cost savings · estimate</span><h2 class="cost-title"></h2></div>
      <button type="button" class="cost-close" aria-label="Close costs">Close</button>
    </div>
    <div class="cost-body"></div>`;
  const scrim = document.createElement("div");
  scrim.className = "cost-scrim";
  scrim.hidden = true;
  scrim.addEventListener("click", closeCosts);
  panel.querySelector(".cost-close").addEventListener("click", closeCosts);
  document.body.append(scrim, panel);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) closeCosts(); });
}

function mountCosts() {
  const body = panel.querySelector(".cost-body");
  if (costBox && costBox.parentElement !== body) body.replaceChildren(costBox);
  // Re-count whenever budget.js repaints the figures (pick change, new costs, filter change).
  observer?.disconnect();
  const bars = costBox?.querySelector(".budget-bars");
  if (bars) {
    observer = new MutationObserver(() => { if (!panel.hidden) countUp(bars); });
    observer.observe(bars, { childList: true });
  }
}

export function openCosts(index, address) {
  if (!costBox) return;
  if (!panel) buildPanel();
  mountCosts();
  panel.querySelector(".cost-title").textContent = address || "This location";
  panel.hidden = false;
  document.querySelector(".cost-scrim").hidden = false;
  requestAnimationFrame(() => panel.classList.add("is-open"));
  // Select the same pick inside budget.js's own chooser; that repaints and triggers the count-up.
  const choice = costBox.querySelectorAll(".budget-picks button")[index];
  if (choice && choice.getAttribute("aria-pressed") !== "true") choice.click();
  else countUp(costBox.querySelector(".budget-bars"));
  panel.querySelector(".cost-close").focus({ preventScroll: true });
}

function closeCosts() {
  if (!panel) return;
  panel.classList.remove("is-open");
  document.querySelector(".cost-scrim").hidden = true;
  setTimeout(() => { if (!panel.classList.contains("is-open")) panel.hidden = true; }, 300);
}

const MONEY = /\$([\d,]+)/;
/** Animate every "$1,234" in the headline figures from $0 to its real value. Text ends exact. */
function countUp(root) {
  if (!root) return;
  root.querySelectorAll(".budget-bar-head strong").forEach((node, i) => {
    const final = node.textContent;
    const m = final.match(MONEY);
    if (!m || reduceMotion()) return;
    const target = Number(m[1].replace(/,/g, ""));
    const start = performance.now() + i * 90;
    const duration = 900;
    const step = (now) => {
      if (!node.isConnected) return;
      const t = Math.min(1, Math.max(0, (now - start) / duration));
      const eased = 1 - Math.pow(1 - t, 3);
      node.textContent = t >= 1 ? final : final.replace(MONEY, "$" + Math.round(target * eased).toLocaleString("en-US"));
      if (t < 1) requestAnimationFrame(step);
    };
    node.textContent = final.replace(MONEY, "$0");
    requestAnimationFrame(step);
  });
  root.querySelectorAll(".budget-bar-track").forEach((track) => {
    if (reduceMotion()) return;
    track.classList.remove("is-grown");
    void track.offsetWidth;
    track.classList.add("is-grown");
  });
}

// A click on a card (not on its own buttons, links or controls) opens that pick's costs.
document.addEventListener("click", (event) => {
  const card = event.target.closest("#results .pick-card");
  if (!card) return;
  if (event.target.closest("button, a, input, select, textarea, summary, label, details, [role=button], dialog")) return;
  const cards = [...document.querySelectorAll("#results .pick-card")];
  const address = card.querySelector("h3")?.textContent?.trim();
  openCosts(cards.indexOf(card), address);
});
