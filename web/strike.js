// Strike: show the same real room emptied of furniture (AI-edited, blended into the scan, model-checked).
// Self-contained: decorates every .shot-stage whose frame has a precomputed struck face. The real <img>
// is never modified; the emptied plate is a separate layer, so the viewfinder and descent keep working.

const LABEL = "AI-edited · furniture removed · not the real room";
const cache = new Map(); // shot id -> Promise<face | null>
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

function shotIdFromSrc(src) {
  try {
    const path = new URL(src, location.href).pathname;
    const match = path.match(/\/cache\/views\/([A-Za-z0-9._-]+)\.(?:jpe?g|png|webp)$/i);
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

const STRUCK_URL = /^\/cache\/strike\/[A-Za-z0-9_-]{1,80}\/[A-Za-z0-9_-]{1,80}\/struck_\d{3}\.jpg$/;

function lookup(id) {
  if (!cache.has(id)) {
    cache.set(id, fetch(`/api/strike/${encodeURIComponent(id)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => (d?.face && STRUCK_URL.test(d.face.struck_url || "") ? d.face : null))
      .catch(() => null));
  }
  return cache.get(id);
}

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

function setOn(stage, on) {
  const ui = stage.querySelector(":scope > .strike-ui");
  const plate = stage.querySelector(":scope > .strike-plate");
  if (!ui || !plate) return;
  ui.querySelector(".strike-real").setAttribute("aria-pressed", String(!on));
  ui.querySelector(".strike-empty").setAttribute("aria-pressed", String(on));
  ui.querySelector(".strike-label").hidden = !on;
  stage.classList.toggle("is-struck", on);
  if (reducedMotion()) {
    plate.style.clipPath = on ? "inset(0 0 0 0)" : "inset(0 100% 0 0)";
    return;
  }
  plate.animate(
    on
      ? [{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)" }]
      : [{ clipPath: "inset(0 0% 0 0)" }, { clipPath: "inset(0 0 0 100%)" }],
    { duration: on ? 900 : 520, easing: "cubic-bezier(0.16, 1, 0.3, 1)", fill: "forwards" },
  );
}

function clear(stage) {
  stage.querySelector(":scope > .strike-ui")?.remove();
  stage.querySelector(":scope > .strike-plate")?.remove();
  stage.classList.remove("is-struck");
  delete stage.dataset.strikeFor;
}

async function decorate(stage) {
  const img = stage.querySelector("img.shot-image");
  const id = img && shotIdFromSrc(img.getAttribute("src") || "");
  if (!id) return clear(stage);
  if (stage.dataset.strikeFor === id) return;
  clear(stage);
  stage.dataset.strikeFor = id;
  const face = await lookup(id);
  if (!face || stage.dataset.strikeFor !== id) return;

  const plate = el("img", "strike-plate");
  plate.alt = `${LABEL}. Same room as the scanned frame.`;
  plate.decoding = "async";
  plate.style.clipPath = "inset(0 100% 0 0)";
  const loaded = await new Promise((resolve) => {
    plate.addEventListener("load", () => resolve(plate.naturalWidth > 0), { once: true });
    plate.addEventListener("error", () => resolve(false), { once: true });
    plate.src = face.struck_url;
  });
  if (!loaded) return; // no plate, no control: never offer a comparison with nothing in it
  if (stage.dataset.strikeFor !== id) return;

  const ui = el("div", "strike-ui");
  const group = el("div", "strike-toggle");
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", "Show the scanned room or an AI-emptied version");
  const real = el("button", "strike-real", "Scan");
  const empty = el("button", "strike-empty", "Empty (AI)");
  for (const b of [real, empty]) {
    b.type = "button";
    b.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      setOn(stage, b === empty);
    });
  }
  real.setAttribute("aria-pressed", "true");
  empty.setAttribute("aria-pressed", "false");
  empty.title = "Furniture removed by an AI image edit, blended into the real scan and checked by a decision model";
  const label = el("p", "strike-label", LABEL);
  label.hidden = true;
  group.append(real, empty);
  ui.append(group, label);
  img.after(plate); // directly above the photo, below every badge and control
  stage.append(ui);
}

let scheduled = false;
function scan() {
  scheduled = false;
  document.querySelectorAll(".shot-stage").forEach((stage) => { decorate(stage); });
}
new MutationObserver(() => {
  if (!scheduled) {
    scheduled = true;
    setTimeout(scan, 30); // a timer, not a frame callback: background tabs still decorate
  }
}).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["src"] });
scan();

export { shotIdFromSrc };
