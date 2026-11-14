// Keep the original viewfinder intact while making its async sessions reusable.
import { Viewfinder } from "./viewfinder.js";

const originalOpen = Viewfinder.prototype.open;
const originalClose = Viewfinder.prototype.close;
const sessions = new WeakMap();

function session(viewfinder) {
  let state = sessions.get(viewfinder);
  if (!state) {
    state = { opening: null, closing: null, request: 0 };
    sessions.set(viewfinder, state);
  }
  return state;
}

function pendingButton(sourceImage, pending) {
  const button = sourceImage?.closest(".shot-stage")?.querySelector(".vf-open");
  if (!button) return;
  button.disabled = pending;
  button.setAttribute("aria-busy", String(pending));
  const label = button.querySelector("span");
  if (label) label.textContent = pending ? "Opening…" : "Look around";
}

Viewfinder.prototype.open = async function (shotId, sourceImage) {
  const state = session(this);
  if (this.dialog.open && !state.closing) return state.opening;
  const request = ++state.request;
  pendingButton(sourceImage, true);
  try {
    // The original module has no cancellation hook. Let a dismissed session finish
    // before reusing its DOM, so its response/decodes cannot replace the next room.
    if (state.closing) await state.closing;
    if (request !== state.request) return;
    state.opening = originalOpen.call(this, shotId, sourceImage);
    // showModal() has already run. Keep the source focusable if loading is dismissed.
    pendingButton(sourceImage, false);
    await state.opening;
  } finally {
    pendingButton(sourceImage, false);
  }
};

Viewfinder.prototype.close = function () {
  const state = session(this);
  if (state.closing) return state.closing;
  if (!this.dialog.open) return Promise.resolve();
  ++state.request;
  const opening = state.opening;
  const closing = originalClose.call(this);
  state.closing = (async () => {
    try {
      await closing;
      await opening;
    } finally {
      // An open dismissed during fetch can create a renderer after close returned.
      cancelAnimationFrame(this.raf);
      cancelAnimationFrame(this.tween);
      cancelAnimationFrame(this.coastRaf);
      this.raf = 0;
      this.renderer?.dispose();
      this.renderer = null;
      this.poster.getAnimations().forEach((animation) => animation.cancel());
      this.dialog.getAnimations().forEach((animation) => animation.cancel());
      this.poster.style.visibility = "";
      this.dialog.classList.remove("is-live", "is-closing", "shows-gap", "no-webgl");
      // dispose() permanently loses the old canvas's GL context. The original
      // handlers read this.canvas at use time, so only the canvas needs replacing.
      const canvas = this.canvas.cloneNode(false);
      this.canvas.replaceWith(canvas);
      this.canvas = canvas;
      state.opening = null;
      state.closing = null;
    }
  })();
  return state.closing;
};
