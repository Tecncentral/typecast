// App shell: split landing → Interiors or Exteriors, with no page loads.
// Routes are hashes (#interior, #exterior, none = home) so Back works. Exteriors and the
// Director's Room are existing pages, embedded same-origin instead of linked away.
const $ = (s) => document.querySelector(s);
const ROUTES = new Set(["interior", "exterior"]);

const SAMPLE_SCRIPT = `INT. LOS ANGELES WAREHOUSE - DAY
Two couriers exchange a case on a concrete floor under an exposed roof.

INT. GLASS OFFICE - DAY
A tense meeting behind glass partitions, city light through broad windows.

INT. EMPTY SHOP - NIGHT
The crew rehearses in a long, clear room with wood flooring.`;

function routeFromHash() {
  const r = location.hash.replace("#", "");
  return ROUTES.has(r) ? r : "home";
}

function apply(route) {
  document.body.dataset.mode = route;
  $("#home").hidden = route !== "home";
  $("#interior-app").hidden = route !== "interior";
  $("#exterior-app").hidden = route !== "exterior";
  document.querySelectorAll(".mode-pill [data-go]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.go === route)));
  if (route === "exterior") loadFrame($("#exterior-frame"), hideEmbeddedChrome);
  if (route === "interior") requestAnimationFrame(() => $("#scene")?.focus({ preventScroll: true }));
  window.scrollTo({ top: 0 });
}

function go(route) {
  const hash = route === "home" ? " " : "#" + route;
  if (routeFromHash() === route) return;
  history.pushState(null, "", hash === " " ? location.pathname + location.search : hash);
  transition(() => apply(route));
}

function transition(update) {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (document.startViewTransition && !reduce) document.startViewTransition(update);
  else update();
}

function loadFrame(frame, onload) {
  if (!frame || frame.src) return;
  if (onload) frame.addEventListener("load", () => onload(frame));
  frame.src = frame.dataset.src;
}

// The embedded page keeps its own app; only its duplicate header and mode links are hidden.
function hideEmbeddedChrome(frame) {
  try {
    const doc = frame.contentDocument;
    const style = doc.createElement("style");
    style.textContent = "body > header.masthead, body > footer, .skip-link { display: none !important; }";
    doc.head.append(style);
  } catch { /* cross-origin would block this; same-origin here */ }
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-go]");
  if (target) {
    event.preventDefault();
    go(target.dataset.go);
    return;
  }
  if (event.target.closest("[data-open-room]")) openRoom();
  if (event.target.closest("[data-close-room]")) $("#room-sheet")?.close();
});
window.addEventListener("popstate", () => transition(() => apply(routeFromHash())));

/* ---------- Director's Room as a sheet ---------- */
// Built on first use so the page carries no idle dialog; removed again on close.
function buildRoom() {
  const sheet = document.createElement("dialog");
  sheet.id = "room-sheet";
  sheet.className = "room-sheet";
  sheet.setAttribute("aria-label", "Director's Room");
  sheet.innerHTML = `<div class="room-sheet-bar"><div><strong>Director's Room</strong><span>Rehearse scenes in the planned locations, reject one and replan, export a shoot pack.</span></div><button type="button" class="room-close" data-close-room>Close</button></div><iframe id="room-frame" title="Director's Room" data-src="/director"></iframe>`;
  sheet.addEventListener("click", (e) => { if (e.target === sheet) sheet.close(); });
  sheet.addEventListener("close", () => sheet.remove());
  document.body.append(sheet);
  return sheet;
}
function openRoom() {
  const sheet = $("#room-sheet") || buildRoom();
  const frame = $("#room-frame");
  if (frame.src) handOverScript(frame);
  else loadFrame(frame, (f) => { hideEmbeddedChrome(f); handOverScript(f); });
  sheet.showModal();
}
// The room opens on the script the director pasted here, not its own demo. Build plan stays theirs to press.
function handOverScript(frame) {
  try {
    const box = frame.contentDocument.getElementById("script");
    const text = $("#scene").value.trim();
    if (box && text && scope === "script" && box.value !== text) {
      box.value = text;
      box.dispatchEvent(new Event("input", { bubbles: true }));
    }
  } catch { /* same-origin; nothing to do if the room changed its markup */ }
}

/* ---------- One scene / Whole script ---------- */
const drafts = { scene: $("#scene").value, script: "" };
let scope = "scene";
function setScope(next, { swap = true } = {}) {
  if (next === scope && swap) return;
  if (swap) {
    drafts[scope] = $("#scene").value;
    $("#scene").value = drafts[next];
    $("#scene").dispatchEvent(new Event("input", { bubbles: true }));
  }
  scope = next;
  document.querySelectorAll("[data-scope]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.scope === next)));
  $("#scene").rows = next === "script" ? 8 : 3;
  document.querySelectorAll(".scene-presets[data-for]").forEach((row) => { row.hidden = row.dataset.for !== next; });
  $("#scene").placeholder = next === "script"
    ? "Paste a script. Each INT. or EXT. heading becomes a scene."
    : "Describe the scene: the room, the era, the mood, and how many trucks and crew cars.";
}
document.querySelectorAll("[data-scope]").forEach((b) => b.addEventListener("click", () => setScope(b.dataset.scope)));
$("#example-script")?.addEventListener("click", () => {
  const box = $("#scene");
  box.value = SAMPLE_SCRIPT;
  box.dispatchEvent(new Event("input", { bubbles: true }));
  box.focus();
  box.setSelectionRange(box.value.length, box.value.length);
});
// Pasting a real script flips the toggle on its own; nothing is swapped out.
$("#scene").addEventListener("input", () => {
  const headings = ($("#scene").value.match(/^\s*(?:\d+\s*[.)]?\s*)?(INT\.|EXT\.|I\/E)/gim) || []).length;
  const detected = headings >= 2 ? "script" : "scene";
  if (detected !== scope) setScope(detected, { swap: false });
});

apply(routeFromHash());
