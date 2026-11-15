// The camera frame is a tool you pick up, not the first thing you see. A room opens clean,
// the whole view with the AI dressing or the walk, and "Frame a shot" (F) brings on the
// frame lines, the lens and aspect controls and the shot list. The original viewfinder stays
// intact: this module adds one button and one class.
import { Viewfinder } from "./viewfinder.js";

const ICON_FRAME = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 9V6h3M20 9V6h-3M4 15v3h3M20 15v3h-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="12" r="2.4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>`;
const FRAME_KEYS = new Set(["g", "a", "[", "]", "-", "="]); // grab, aspect, lens steps: they act on the frame

let framing = false; // holds for the page: once you are framing shots, the next room opens framed
const buttons = new WeakMap();

function apply(vf) {
  const button = buttons.get(vf);
  vf.dialog.classList.toggle("is-clean", !framing);
  button.classList.toggle("is-active", framing);
  button.setAttribute("aria-pressed", String(framing));
}

function setFraming(vf, on) {
  framing = on;
  apply(vf);
  if (on) vf.resize?.();
}

function ensure(vf) {
  if (buttons.has(vf)) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "vf-framing";
  button.innerHTML = `${ICON_FRAME}<span>Frame a shot</span><kbd>F</kbd>`;
  button.title = "Show what a cinema lens would capture from here, and save framings to a shot list";
  button.addEventListener("click", () => setFraming(vf, !framing));
  vf.dialog.querySelector(".vf-close").before(button);
  buttons.set(vf, button);
  // Capture phase: with the frame put away, its keys must not act on a frame nobody can see.
  vf.dialog.addEventListener("keydown", (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
    const key = event.key.toLowerCase();
    if (key === "f") {
      event.preventDefault();
      event.stopPropagation();
      setFraming(vf, !framing);
    } else if (!framing && FRAME_KEYS.has(key)) {
      event.preventDefault();
      event.stopPropagation();
      if (key === "g") setFraming(vf, true); // asking to grab brings the frame on first
    }
  }, true);
}

const open = Viewfinder.prototype.open;
Viewfinder.prototype.open = function (...args) {
  ensure(this);
  apply(this);
  return open.apply(this, args);
};

// For browser checks.
export const isFraming = () => framing;
