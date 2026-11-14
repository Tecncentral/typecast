// Walk the AI-dressed set. When a scan point has a Gaussian-splat reconstruction of its
// dressed frames (World Labs Atlas posedImages2Splats), the viewfinder gains a first-person
// mode: the same look, lens and grab controls, plus W A S D to move through the set.
// three.js and Spark are imported on first use, so the rest of the viewer never pays for them.
// The original viewfinder stays intact: this module only wraps three of its methods.
import { Viewfinder } from "./viewfinder.js";

const WALK_RADIUS_M = { draft: 1.5, refined: 2.5 }; // how far from the scan point the views hold up
const BINS = 90; // 4° sectors around the scan point
const CELL_M = 0.05;
const CELLS = 80; // surfaces are searched out to 4 m
const WALL_MARGIN_M = 0.4;
const SPEED_M_S = 1.1;
const ICON_WALK = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
const MOVE_KEYS = { w: "forward", arrowup: "forward", s: "back", arrowdown: "back", a: "left", d: "right" };

const rad = (d) => (d * Math.PI) / 180;
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const walks = new WeakMap();

function stateFor(vf) {
  let w = walks.get(vf);
  if (w) return w;
  w = { active: false, loading: false, keys: new Set(), velocity: [0, 0], position: [0, 0, 0], eye: [0, 0, 0], raf: 0 };
  walks.set(vf, w);

  w.button = document.createElement("button");
  w.button.type = "button";
  w.button.className = "vf-walk";
  w.button.hidden = true;
  w.button.setAttribute("aria-pressed", "false");
  w.button.innerHTML = `${ICON_WALK}<span>Walk the set</span><kbd>E</kbd>`;
  w.button.addEventListener("click", () => toggle(vf));
  vf.dialog.querySelector(".vf-close").before(w.button);

  w.hint = document.createElement("p");
  w.hint.className = "vf-walk-keys";
  w.hint.setAttribute("aria-hidden", "true");
  w.hint.innerHTML = `<kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd><span>move</span>`;
  vf.dialog.querySelector(".vf-stage").after(w.hint);

  // Capture phase: while walking, the movement keys must not reach the viewfinder's own
  // shortcuts (A cycles the aspect ratio and D toggles the dressing there).
  vf.dialog.addEventListener(
    "keydown",
    (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const key = e.key.toLowerCase();
      if (key === "e" && !w.button.hidden) {
        e.preventDefault();
        e.stopImmediatePropagation();
        if (!e.repeat) toggle(vf);
        return;
      }
      if (!w.active || !MOVE_KEYS[key]) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      w.keys.add(MOVE_KEYS[key]);
    },
    true,
  );
  vf.dialog.addEventListener("keyup", (e) => w.keys.delete(MOVE_KEYS[e.key.toLowerCase()]), true);
  addEventListener("blur", () => w.keys.clear());
  return w;
}

const isCurrent = (vf, generation) =>
  generation === vf.generation && vf.dialog.open && !vf.dialog.classList.contains("is-closing");

function setEdge(vf, w, atEdge) {
  w.atEdge = atEdge;
  w.hint.classList.toggle("at-edge", atEdge);
  if (atEdge) vf.$(".vf-status").textContent = "That's as far as this set goes: a wall, or the edge of what the scan point saw.";
  else vf.updateReadout();
}

// Walls and furniture stop the walk. The splat itself says where they are: for each direction
// from the scan point, the nearest distance at which splats at body height become dense.
// That is also the limit of what the scan point could see, so it is where the set stays honest.
function freeSpace(mesh, eye, radius) {
  const counts = new Uint32Array(BINS * CELLS);
  const totals = new Uint32Array(BINS);
  mesh.forEachSplat((index, center, scales, quaternion, opacity) => {
    if (opacity < 0.3 || center.y < eye[1] - 1.45 || center.y > eye[1] + 0.1) return;
    const dx = center.x - eye[0];
    const dz = center.z - eye[2];
    const cell = Math.floor(Math.hypot(dx, dz) / CELL_M);
    if (cell < 3 || cell >= CELLS) return;
    const bin = Math.floor((((Math.atan2(dx, -dz) / (2 * Math.PI)) % 1) + 1) * BINS) % BINS;
    counts[bin * CELLS + cell] += 1;
    totals[bin] += 1;
  });
  const nearest = new Float32Array(BINS).fill(radius + WALL_MARGIN_M);
  for (let bin = 0; bin < BINS; bin += 1) {
    // A few stray splats are not a wall: wait for 3% of the sector's surface, and at least 25.
    const needed = Math.max(25, totals[bin] * 0.03);
    let seen = 0;
    for (let cell = 0; cell < CELLS; cell += 1) {
      seen += counts[bin * CELLS + cell];
      if (seen >= needed) {
        nearest[bin] = cell * CELL_M;
        break;
      }
    }
  }
  const free = new Float32Array(BINS);
  for (let bin = 0; bin < BINS; bin += 1) {
    const around = Math.min(nearest[(bin + BINS - 1) % BINS], nearest[bin], nearest[(bin + 1) % BINS]);
    free[bin] = Math.max(0, Math.min(radius, around - WALL_MARGIN_M));
  }
  return free;
}

function reach(w, dx, dz) {
  if (!w.free) return w.radius;
  const turn = (((Math.atan2(dx, -dz) / (2 * Math.PI)) % 1) + 1) * BINS;
  const a = Math.floor(turn) % BINS;
  const t = turn - Math.floor(turn);
  return w.free[a] * (1 - t) + w.free[(a + 1) % BINS] * t;
}

function sweepWipe(vf, to, duration) {
  cancelAnimationFrame(vf.wipeTween);
  const from = Math.max(vf.wipe, -0.999);
  if (reducedMotion() || from === to) return vf.setWipe(to);
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    vf.setWipe(from + (to - from) * (1 - Math.pow(1 - t, 3)));
    if (t < 1) vf.wipeTween = requestAnimationFrame(step);
  };
  vf.wipeTween = requestAnimationFrame(step);
}

async function build(vf, w, splat) {
  const [THREE, { SparkRenderer, SplatMesh }] = await Promise.all([import("three"), import("@sparkjsdev/spark")]);
  const canvas = document.createElement("canvas");
  canvas.className = "vf-walk-canvas";
  canvas.setAttribute("aria-hidden", "true");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: "high-performance" });
  renderer.setClearColor(0x121516, 1);
  const scene = new THREE.Scene();
  const spark = new SparkRenderer({ renderer });
  scene.add(spark);
  const mesh = new SplatMesh({ url: splat.url });
  scene.add(mesh);
  const camera = new THREE.PerspectiveCamera(60, 16 / 9, 0.05, 500);
  camera.rotation.order = "YXZ";
  Object.assign(w, { canvas, renderer, scene, spark, camera, mesh, url: splat.url });
  vf.canvas.after(canvas);
  await mesh.initialized;
  const radius = WALK_RADIUS_M[splat.mode === "draft" ? "draft" : "refined"];
  try {
    w.free = freeSpace(mesh, (splat.eye || [0, 0, 0]).map(Number), radius);
  } catch {
    w.free = new Float32Array(BINS).fill(0.5); // no readable geometry: stay close to the scan point
  }
}

function render(vf, w) {
  const { canvas, renderer, camera } = w;
  const dpr = Math.min(1.5, devicePixelRatio || 1);
  const width = Math.max(1, Math.round(canvas.clientWidth * dpr));
  const height = Math.max(1, Math.round(canvas.clientHeight * dpr));
  if (canvas.width !== width || canvas.height !== height) renderer.setSize(width, height, false);
  // Same lens model as the 360° view: tx is the tangent of half the horizontal field of view.
  camera.aspect = width / height;
  camera.fov = (2 * Math.atan((vf.view.tx * height) / width) * 180) / Math.PI;
  camera.updateProjectionMatrix();
  // Viewfinder yaw 0 looks down -Z and grows toward +X; Atlas worlds are right/up/back like three.js.
  camera.rotation.set(rad(vf.view.pitch), -rad(vf.view.yaw), 0);
  camera.position.set(w.position[0], w.position[1], w.position[2]);
  renderer.render(w.scene, camera);
}

function step(vf, w, dt) {
  const yaw = rad(vf.view.yaw);
  const ahead = (w.keys.has("forward") ? 1 : 0) - (w.keys.has("back") ? 1 : 0);
  const side = (w.keys.has("right") ? 1 : 0) - (w.keys.has("left") ? 1 : 0);
  const length = Math.hypot(ahead, side) || 1;
  const targetX = ((Math.sin(yaw) * ahead + Math.cos(yaw) * side) / length) * SPEED_M_S;
  const targetZ = ((-Math.cos(yaw) * ahead + Math.sin(yaw) * side) / length) * SPEED_M_S;
  const ease = reducedMotion() ? 1 : 1 - Math.exp(-dt * 10);
  w.velocity[0] += (targetX - w.velocity[0]) * ease;
  w.velocity[1] += (targetZ - w.velocity[1]) * ease;
  let dx = w.position[0] + w.velocity[0] * dt - w.eye[0];
  let dz = w.position[2] + w.velocity[1] * dt - w.eye[2];
  const distance = Math.hypot(dx, dz);
  const limit = reach(w, dx, dz);
  const atEdge = distance > limit;
  if (atEdge) {
    dx *= limit / distance;
    dz *= limit / distance;
  }
  w.position[0] = w.eye[0] + dx;
  w.position[2] = w.eye[2] + dz;
  if (atEdge !== w.atEdge) setEdge(vf, w, atEdge);
}

function start(vf, w) {
  w.active = true;
  w.keys.clear();
  w.velocity = [0, 0];
  w.position = [...w.eye];
  w.atEdge = false;
  w.hint.classList.remove("at-edge");
  render(vf, w);
  vf.dialog.classList.add("is-walking");
  w.button.classList.add("is-active");
  w.button.setAttribute("aria-pressed", "true");
  const badge = vf.$(".vf-ai-badge");
  w.badgeText = badge.textContent;
  badge.textContent = `${vf.dressed?.label || "AI-imagined set dressing, not the real room"} · ${w.mode === "draft" ? "draft " : ""}3D reconstruction`;
  vf.$(".vf-status").textContent = "Walking the AI-dressed set. W A S D to move, drag to look, E to leave.";
  let last = performance.now();
  const tick = (now) => {
    if (!w.active) return;
    w.raf = requestAnimationFrame(tick);
    step(vf, w, Math.min(0.05, (now - last) / 1000));
    last = now;
    render(vf, w);
  };
  w.raf = requestAnimationFrame(tick);
}

function stop(vf, w) {
  if (!w.active) return;
  w.active = false;
  cancelAnimationFrame(w.raf);
  w.keys.clear();
  vf.dialog.classList.remove("is-walking");
  w.button.classList.remove("is-active");
  w.button.setAttribute("aria-pressed", "false");
  if (w.badgeText != null) vf.$(".vf-ai-badge").textContent = w.badgeText;
  // Back in the 360° view the comparison divider returns where it was, or at its resting place.
  sweepWipe(vf, w.wipeBefore > -1 ? w.wipeBefore : 0.15, 420);
  vf.updateReadout();
}

async function toggle(vf) {
  const w = stateFor(vf);
  if (w.loading) return;
  if (w.active) return stop(vf, w);
  const splat = vf.dressed?.splat;
  if (!splat?.url || !vf.dialog.classList.contains("is-live")) return;
  const generation = vf.generation;
  w.loading = true;
  w.button.setAttribute("aria-busy", "true");
  vf.dialog.classList.add("is-walk-loading");
  w.wipeBefore = vf.wipe;
  w.mode = splat.mode === "draft" ? "draft" : "refined";
  w.radius = WALK_RADIUS_M[w.mode];
  w.eye = (splat.eye || [0, 0, 0]).map(Number);
  // The 360° view finishes dressing while the reconstruction loads, so the cut into 3D matches.
  sweepWipe(vf, 1, 900);
  try {
    if (w.url !== splat.url) {
      vf.$(".vf-status").textContent = "Loading the walkable set…";
      dispose(w);
      await build(vf, w, splat);
    }
    if (!isCurrent(vf, generation)) return dispose(w);
    start(vf, w);
  } catch {
    dispose(w);
    if (isCurrent(vf, generation)) {
      sweepWipe(vf, w.wipeBefore, 300);
      vf.$(".vf-status").textContent = "The walkable set couldn't load here. The 360° comparison still works.";
    }
  } finally {
    w.loading = false;
    w.button.removeAttribute("aria-busy");
    vf.dialog.classList.remove("is-walk-loading");
  }
}

function dispose(w) {
  cancelAnimationFrame(w.raf);
  w.active = false;
  try {
    w.scene?.clear();
    w.mesh?.dispose?.();
    w.spark?.dispose?.();
    w.renderer?.dispose();
    w.renderer?.forceContextLoss?.();
  } catch {
    /* a half-built scene has nothing more to release */
  }
  w.canvas?.remove();
  w.canvas = w.renderer = w.scene = w.spark = w.camera = w.mesh = w.url = w.free = null;
}

/* ---------------- Viewfinder hooks ---------------- */

const loadDressed = Viewfinder.prototype.loadDressed;
Viewfinder.prototype.loadDressed = async function (shotId, generation, renderer) {
  await loadDressed.call(this, shotId, generation, renderer);
  if (!isCurrent(this, generation) || !this.dressed?.splat?.url) return;
  const w = stateFor(this);
  w.button.hidden = false;
  this.$(".vf-status").textContent = "An AI-dressed version of this room is ready: press D to compare it, or E to walk through it.";
};

const close = Viewfinder.prototype.close;
Viewfinder.prototype.close = function () {
  const w = walks.get(this);
  if (w && this.dialog.open) {
    if (w.active && w.badgeText != null) this.$(".vf-ai-badge").textContent = w.badgeText;
    this.dialog.classList.remove("is-walking", "is-walk-loading");
    w.button.classList.remove("is-active");
    w.button.setAttribute("aria-pressed", "false");
    w.button.hidden = true;
    dispose(w);
  }
  return close.call(this);
};

const grab = Viewfinder.prototype.grab;
Viewfinder.prototype.grab = function () {
  const w = walks.get(this);
  if (!w?.active) return grab.call(this);
  // Grab what the director sees: the splat canvas stands in for the 360° canvas for this call.
  const panorama = this.canvas;
  render(this, w);
  this.canvas = w.canvas;
  try {
    return grab.call(this);
  } finally {
    this.canvas = panorama;
  }
};

// For browser checks: the walk state of a viewfinder (limits, position).
export const walkState = (vf) => walks.get(vf) || null;
