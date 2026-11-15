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
