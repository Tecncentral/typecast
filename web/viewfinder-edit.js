// Edit this view: take the view you are looking at in a scanned room (the framed shot when the
// frame is on), then change it from chat messages with an image model, each building on the last
// version. Every result is labelled AI-imagined. The original viewfinder stays intact: this module
// adds one button (R) and one panel.
import { Viewfinder } from "./viewfinder.js";

const ICON_EDIT = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 20h4l10-10-4-4L4 16v4zM13.5 6.5l4 4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const IDEAS = [
  "Dress it as a 1970s police precinct: wooden desks, filing cabinets, fluorescent light",
  "Night: practical lamps on, city lights through the windows",
  "Add a long table set for a tense board meeting",
];
const states = new WeakMap();

const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};
const asset = (path) => "/" + String(path).replace(/^\/+/, "");

// Keys typed in the edit panel must not reach the viewfinder's shortcuts (walk, aspect, dressing).
for (const type of ["keydown", "keyup"])
  addEventListener(type, (e) => e.target?.closest?.(".vf-edit") && e.key !== "Escape" && e.stopPropagation(), true);

function capture(vf) {
  vf.draw();
  const c = vf.canvas;
  let sx = 0, sy = 0, sw = c.width, sh = c.height;
  if (!vf.dialog.classList.contains("is-clean") && vf.frame) {
    const fr = vf.frame.getBoundingClientRect();
    const cr = c.getBoundingClientRect();
    sx = (c.width / cr.width) * (fr.left - cr.left);
    sy = (c.height / cr.height) * (fr.top - cr.top);
    sw = (c.width / cr.width) * fr.width;
    sh = (c.height / cr.height) * fr.height;
  }
  const scale = Math.min(1, 1536 / sw);
  const out = document.createElement("canvas");
  out.width = Math.max(64, Math.round(sw * scale));
  out.height = Math.max(64, Math.round(sh * scale));
  out.getContext("2d").drawImage(c, sx, sy, sw, sh, 0, 0, out.width, out.height);
  return out.toDataURL("image/jpeg", 0.9);
}

function viewKey(vf) {
  const st = vf.state || {};
  const round = (v) => (typeof v === "number" ? v.toFixed(3) : String(v));
  return [vf.sweep?.shot_id || vf.shotId || "", round(st.yaw), round(st.pitch), round(st.lens), st.aspect?.id ?? "",
    vf.dialog.classList.contains("is-clean")].join("|");
}

function build(vf) {
  const s = { open: false, editId: null, base: null, versions: [], selected: null, showing: "imagined", busy: false };
  const button = el("button", "vf-edit-open");
  button.type = "button";
  button.innerHTML = `${ICON_EDIT}<span>Edit (AI)</span><kbd>R</kbd>`;
  button.title = "Change this view with an image model: describe the set dressing, time of day or props";
  vf.dialog.querySelector(".vf-close").before(button);

  const panel = el("section", "vf-edit");
  panel.hidden = true;
  panel.setAttribute("aria-label", "Edit this view with AI");
  const head = el("header", "vf-edit-head");
  const title = el("div");
  title.append(el("p", "vf-edit-eyebrow", "Edit this view"), el("h3", "vf-edit-title", "Describe the change"));
  const back = el("button", "vf-edit-back", "Back to 360°");
  back.type = "button";
  head.append(title, back);
  const stage = el("div", "vf-edit-stage");
  const img = el("img", "vf-edit-image");
  img.alt = "";
  const label = el("p", "vf-edit-label");
  label.hidden = true;
  const toggle = el("div", "vf-edit-toggle");
  toggle.setAttribute("role", "group");
  toggle.setAttribute("aria-label", "Real or imagined");
  const realBtn = el("button", "", "Real");
  const imagBtn = el("button", "", "Imagined");
  for (const [b, show] of [[realBtn, "real"], [imagBtn, "imagined"]]) {
    b.type = "button";
    b.addEventListener("click", () => {
      s.showing = show;
      paint();
    });
    toggle.append(b);
  }
  toggle.hidden = true;
  stage.append(img, label, toggle);
  const side = el("div", "vf-edit-side");
  const note = el("p", "vf-edit-note");
  const ideas = el("div", "vf-edit-ideas");
  for (const idea of IDEAS) {
    const chip = el("button", "vf-edit-chip", idea);
    chip.type = "button";
    chip.addEventListener("click", () => {
      input.value = idea;
      input.focus();
    });
    ideas.append(chip);
  }
  const log = el("ol", "vf-edit-log");
  const form = el("form", "vf-edit-form");
  const input = el("input");
  input.maxLength = 600;
  input.autocomplete = "off";
  input.placeholder = "e.g. warm practical light, a worn leather sofa, rain on the windows";
  input.setAttribute("aria-label", "What should change?");
  const send = el("button", "vf-edit-send", "Send");
  send.type = "submit";
  form.append(input, send);
  side.append(note, ideas, log, form);
  panel.append(head, stage, side);
  vf.dialog.append(panel);

  function current() {
    return s.versions[s.selected ?? s.versions.length - 1];
  }
  function paint() {
    const v = current();
    const imagined = s.showing === "imagined" && v;
    img.src = imagined ? asset(v.path) : s.base;
    img.alt = imagined ? `AI-imagined version: ${v.message}` : "The view as captured from the scan";
    label.hidden = !imagined;
    label.textContent = imagined ? `AI-imagined set dressing, not the real room · ${v.model}` : "";
    toggle.hidden = !v;
    realBtn.setAttribute("aria-pressed", String(!imagined));
    imagBtn.setAttribute("aria-pressed", String(Boolean(imagined)));
    log.replaceChildren();
    s.versions.forEach((version, i) => {
      const item = el("li", "vf-edit-msg");
      item.append(el("span", "vf-edit-msg-text", version.message));
      const thumb = el("button", "vf-edit-thumb");
      thumb.type = "button";
      thumb.setAttribute("aria-label", `Show version ${i + 1}`);
      thumb.setAttribute("aria-pressed", String(version === v && Boolean(imagined)));
      const t = el("img");
      t.src = asset(version.path);
      t.alt = "";
      thumb.append(t);
      thumb.addEventListener("click", () => {
        s.selected = i;
        s.showing = "imagined";
        paint();
      });
      item.append(thumb);
      log.append(item);
    });
  }
  function setOpen(on) {
    if (on && vf.dialog.classList.contains("is-walking")) {
      vf.$(".vf-status").textContent = "Leave the walk (E) to edit a view.";
      return;
    }
    if (on && !vf.dialog.classList.contains("is-live")) return;
    s.open = on;
    panel.hidden = !on;
    button.classList.toggle("is-active", on);
    button.setAttribute("aria-pressed", String(on));
    if (on) {
      // Edits belong to the view they started from. Opened on a different scan point, angle, lens or
      // frame, the panel starts a new edit of what is on screen now.
      const moved = s.editId && s.viewKey !== viewKey(vf);
      if (!s.editId || moved) {
        s.editId = null;
        s.base = capture(vf);
        s.viewKey = viewKey(vf);
        s.versions = [];
        s.selected = null;
        s.showing = "imagined";
        note.textContent = (moved ? "This is a different view, so the next message starts a new edit. " : "")
          + `Each message edits the latest version with ${window.__editModel || "the image model"}. The first message sends this view.`;
      }
      paint();
      input.focus();
    } else button.focus({ preventScroll: true });
  }
  async function submit(event) {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || s.busy) return;
    s.busy = true;
    send.disabled = input.disabled = true;
    note.textContent = "Editing… about 10–30 s.";
    try {
      const body = { message, ...(s.editId ? { edit_id: s.editId } : {
        shot_id: vf.sweep?.shot_id || vf.shotId || "view", address: vf.$(".vf-address").textContent.slice(0, 120), image: s.base,
      }) };
      const response = await fetch("/api/frame/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw Error(data.detail || `The edit failed (${response.status}).`);
      s.editId = data.edit_id;
      s.versions = data.versions || [];
      s.selected = null;
      s.showing = "imagined";
      input.value = "";
      note.textContent = "Done. Send another change to build on it, or compare Real / Imagined.";
      paint();
    } catch (error) {
      note.textContent = error.message;
    } finally {
      s.busy = false;
      send.disabled = input.disabled = false;
      input.focus();
    }
  }
  button.addEventListener("click", () => setOpen(!s.open));
  back.addEventListener("click", () => setOpen(false));
  form.addEventListener("submit", submit);
  vf.dialog.addEventListener("keydown", (e) => {
    // Esc with the panel open closes only the panel, even while typing in it; the viewer stays open
    // and the chain of versions is kept.
    if (e.key === "Escape" && s.open) {
      e.preventDefault();
      e.stopImmediatePropagation();
      setOpen(false);
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey || e.target instanceof HTMLInputElement) return;
    if (e.key.toLowerCase() === "r") {
      e.preventDefault();
      setOpen(!s.open);
    }
  }, true);
  // A native <dialog> also closes on Esc through "cancel"; keep it open while the panel handles the key.
  vf.dialog.addEventListener("cancel", (e) => {
    if (s.open) {
      e.preventDefault();
      e.stopImmediatePropagation();
      setOpen(false);
    }
  }, true);
  s.reset = () => {
    s.editId = null;
    s.versions = [];
    s.selected = null;
    s.open = false;
    panel.hidden = true;
    button.classList.remove("is-active");
  };
  states.set(vf, s);
  return s;
}

const open = Viewfinder.prototype.open;
Viewfinder.prototype.open = function (...args) {
  (states.get(this) || build(this)).reset();
  return open.apply(this, args);
};

fetch("/api/oblique/areas", { cache: "no-store" })
  .then((r) => r.json())
  .then((d) => (window.__editModel = `${d.image_model} (${d.image_quality})`))
  .catch(() => {});
