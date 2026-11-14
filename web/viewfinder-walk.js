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
// Four views from one scan point carry no metric scale, so Atlas's world units are arbitrary.
// The scan camera's height above the floor sets the scale; Matterport tripods sit near 1.5 m.
const CAPTURE_HEIGHT_M = 1.5;
// Whole-room sets (several scan points, cameras from the scan itself) arrive with a known scale.
const ROOM_CELL_M = 0.1;
const ROOM_REACH_M = { draft: 2.2, refined: 3.0 }; // how far from the nearest scan point the set holds up
const BODY_M = 0.25;
// Splats at body height in one 10 cm cell that count as something solid, for a draft's
// half-million splats. A denser reconstruction puts more splats on the same surface.
const SOLID_SPLATS = 5;
const DRAFT_SPLATS = 524288;
const DOOR_MAX_DEPTH_M = 0.6; // a door or partition, not a desk
const DOOR_HALF_WIDTH_M = 0.5;
const ICON_WALK = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
const MOVE_KEYS = { w: "forward", arrowup: "forward", s: "back", arrowdown: "back", a: "left", d: "right" };

const rad = (d) => (d * Math.PI) / 180;
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const walks = new WeakMap();

function stateFor(vf) {
  let w = walks.get(vf);
  if (w) return w;
  w = { active: false, loading: false, keys: new Set(), velocity: [0, 0], position: [0, 0, 0], eye: [0, 0, 0], scale: 1, raf: 0 };
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

  w.map = document.createElement("canvas");
  w.map.className = "vf-walk-map";
  w.map.width = w.map.height = 360;
  w.map.setAttribute("role", "img");
  w.map.setAttribute("aria-label", "Floor plan of the set: where you can walk, the scan points, and where you are");
  w.hint.after(w.map);

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
      w.run = e.shiftKey;
      if (!w.active || !MOVE_KEYS[key]) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      w.keys.add(MOVE_KEYS[key]);
    },
    true,
  );
  vf.dialog.addEventListener(
    "keyup",
    (e) => {
      w.run = e.shiftKey;
      w.keys.delete(MOVE_KEYS[e.key.toLowerCase()]);
    },
    true,
  );
  addEventListener("blur", () => w.keys.clear());
  return w;
}

const isCurrent = (vf, generation) =>
  generation === vf.generation && vf.dialog.open && !vf.dialog.classList.contains("is-closing");

function setEdge(vf, w, atEdge) {
  w.atEdge = atEdge;
  w.hint.classList.toggle("at-edge", atEdge);
  if (atEdge) {
    vf.$(".vf-status").textContent = w.grid
      ? "Something solid is in the way, or the scan didn't reach any further."
      : "That's as far as this set goes: a wall, or the edge of what the scan point saw.";
  }
  else vf.updateReadout();
}

// Walls and furniture stop the walk. The splat itself says where they are: for each direction
// from the scan point, the nearest distance at which splats at body height become dense.
// That is also the limit of what the scan point could see, so it is where the set stays honest.
// Returns the reach per sector in world units, and how many world units make a metre.
function measure(mesh, eye, radiusM) {
  const below = [];
  mesh.forEachSplat((index, center, scales, quaternion, opacity) => {
    if (opacity >= 0.3 && center.y < eye[1]) below.push(center.y);
  });
  below.sort((p, q) => p - q);
  // The floor is the lowest dense surface; the 2nd percentile ignores stray splats under it.
  const drop = below.length ? eye[1] - below[Math.floor(below.length * 0.02)] : 0;
  const scale = drop > 0.05 ? drop / CAPTURE_HEIGHT_M : 1;
  const counts = new Uint32Array(BINS * CELLS);
  const totals = new Uint32Array(BINS);
  const low = eye[1] - drop + 0.4 * scale; // skip the floor itself
  const high = eye[1] + 0.1 * scale;
  mesh.forEachSplat((index, center, scales, quaternion, opacity) => {
    if (opacity < 0.3 || center.y < low || center.y > high) return;
    const dx = center.x - eye[0];
    const dz = center.z - eye[2];
    const cell = Math.floor(Math.hypot(dx, dz) / scale / CELL_M);
    if (cell < 3 || cell >= CELLS) return;
    const bin = Math.floor((((Math.atan2(dx, -dz) / (2 * Math.PI)) % 1) + 1) * BINS) % BINS;
    counts[bin * CELLS + cell] += 1;
    totals[bin] += 1;
  });
  const nearest = new Float32Array(BINS).fill(radiusM + WALL_MARGIN_M);
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
    free[bin] = Math.max(0, Math.min(radiusM, around - WALL_MARGIN_M)) * scale;
  }
  return { free, scale };
}

function reach(w, dx, dz) {
  if (!w.free) return 0;
  const turn = (((Math.atan2(dx, -dz) / (2 * Math.PI)) % 1) + 1) * BINS;
  const a = Math.floor(turn) % BINS;
  const t = turn - Math.floor(turn);
  return w.free[a] * (1 - t) + w.free[(a + 1) % BINS] * t;
}

// The heading with the most floor around it: the natural establishing view of the set.
function openHeading(w) {
  let best = 0;
  let most = -1;
  for (let bin = 0; bin < BINS; bin += 1) {
    let sum = 0;
    for (let k = -5; k <= 5; k += 1) sum += w.free[(bin + k + BINS) % BINS];
    if (sum > most) {
      most = sum;
      best = bin;
    }
  }
  return ((best + 0.5) * 360) / BINS;
}

// A whole room is not star-shaped around one point, so its limits are a floor grid: a cell is
// walkable when nothing solid stands in it at body height, it lies within reach of a scan point,
// and it can be reached from where the walk starts.
function measureRoom(mesh, splat, eye) {
  const scale = splat.units_per_m;
  const points = splat.scan_points.map((p) => p.map(Number));
  const cell = ROOM_CELL_M * scale;
  const pad = (ROOM_REACH_M.refined + 1) * scale;
  const minX = Math.min(...points.map((p) => p[0])) - pad;
  const minZ = Math.min(...points.map((p) => p[2])) - pad;
  const nx = Math.min(800, Math.ceil((Math.max(...points.map((p) => p[0])) + pad - minX) / cell));
  const nz = Math.min(800, Math.ceil((Math.max(...points.map((p) => p[2])) + pad - minZ) / cell));
  const counts = new Uint16Array(nx * nz);
  const low = (splat.floor_y ?? 0) + 0.35 * scale;
  const high = (splat.floor_y ?? 0) + 1.5 * scale;
  let total = 0;
  mesh.forEachSplat((index, center, scales, quaternion, opacity) => {
    total += 1;
    if (opacity < 0.3 || center.y < low || center.y > high) return;
    const ix = Math.floor((center.x - minX) / cell);
    const iz = Math.floor((center.z - minZ) / cell);
    if (ix >= 0 && iz >= 0 && ix < nx && iz < nz && counts[iz * nx + ix] < 65535) counts[iz * nx + ix] += 1;
  });
  const solidAt = Math.max(SOLID_SPLATS, Math.round((SOLID_SPLATS * total) / DRAFT_SPLATS));
  // Solid cells, grown by a body's half-width.
  const grow = Math.round(BODY_M / ROOM_CELL_M);
  const solid = new Uint8Array(nx * nz);
  const door = doorways(points, counts, solidAt, { minX, minZ, cell, nx, nz });
  for (let iz = 0; iz < nz; iz += 1) {
    for (let ix = 0; ix < nx; ix += 1) {
      if (counts[iz * nx + ix] < solidAt) continue;
      for (let dz = -grow; dz <= grow; dz += 1) {
        for (let dx = -grow; dx <= grow; dx += 1) {
          const jx = ix + dx;
          const jz = iz + dz;
          if (dx * dx + dz * dz <= grow * grow && jx >= 0 && jz >= 0 && jx < nx && jz < nz) solid[jz * nx + jx] = 1;
        }
      }
    }
  }
  const reachCells = ROOM_REACH_M[splat.mode === "draft" ? "draft" : "refined"] / ROOM_CELL_M;
  const open = new Uint8Array(nx * nz);
  for (const p of points) {
    const cx = (p[0] - minX) / cell;
    const cz = (p[2] - minZ) / cell;
    for (let iz = Math.max(0, Math.floor(cz - reachCells)); iz < Math.min(nz, cz + reachCells); iz += 1) {
      for (let ix = Math.max(0, Math.floor(cx - reachCells)); ix < Math.min(nx, cx + reachCells); ix += 1) {
        const d = Math.hypot(ix + 0.5 - cx, iz + 0.5 - cz);
        // A tripod stood at every scan point, so the floor right there is free whatever the splat says.
        if (d <= reachCells && (!solid[iz * nx + ix] || door[iz * nx + ix] || d <= 0.3 / ROOM_CELL_M)) open[iz * nx + ix] = 1;
      }
    }
  }
  // Keep what can be reached from the start.
  const walk = new Uint8Array(nx * nz);
  const queue = new Int32Array(nx * nz);
  let head = 0;
  let tail = 0;
  const startCell = Math.floor((eye[2] - minZ) / cell) * nx + Math.floor((eye[0] - minX) / cell);
  if (open[startCell]) {
    walk[startCell] = 1;
    queue[tail++] = startCell;
  }
  while (head < tail) {
    const at = queue[head++];
    const ix = at % nx;
    for (const next of [ix > 0 ? at - 1 : -1, ix < nx - 1 ? at + 1 : -1, at - nx, at + nx]) {
      if (next >= 0 && next < walk.length && open[next] && !walk[next]) {
        walk[next] = 1;
        queue[tail++] = next;
      }
    }
  }
  return { scale, free: null, grid: { minX, minZ, cell, nx, nz, walk, cells: tail, points, splats: total, solidAt } };
}

// The scan was walked from point to point, so neighbouring scan points are joined by a real
// passage even where the dressed set shows a closed door or a glass partition across it.
// Where the straight line between two neighbours crosses only something thin, a doorway is
// opened there. Furniture and thick walls are left alone.
function doorways(points, counts, solidAt, { minX, minZ, cell, nx, nz }) {
  const door = new Uint8Array(nx * nz);
  const joined = [0];
  const edges = [];
  while (joined.length < points.length) { // shortest links that connect every scan point
    let best = null;
    for (const a of joined) {
      for (let b = 0; b < points.length; b += 1) {
        if (joined.includes(b)) continue;
        const d = Math.hypot(points[a][0] - points[b][0], points[a][2] - points[b][2]);
        if (!best || d < best.d) best = { a, b, d };
      }
    }
    joined.push(best.b);
    edges.push(best);
  }
  const width = Math.round(DOOR_HALF_WIDTH_M / ROOM_CELL_M);
  for (const { a, b, d } of edges) {
    const steps = Math.ceil(d / (cell / 2));
    const hits = [];
    for (let k = 0; k <= steps; k += 1) {
      const ix = Math.floor((points[a][0] + ((points[b][0] - points[a][0]) * k) / steps - minX) / cell);
      const iz = Math.floor((points[a][2] + ((points[b][2] - points[a][2]) * k) / steps - minZ) / cell);
      if (ix >= 0 && iz >= 0 && ix < nx && iz < nz && counts[iz * nx + ix] >= solidAt) hits.push([ix, iz]);
    }
    if (!hits.length || (hits.length * ROOM_CELL_M) / 2 > DOOR_MAX_DEPTH_M) continue;
    for (const [hx, hz] of hits) {
      for (let dz = -width; dz <= width; dz += 1) {
        for (let dx = -width; dx <= width; dx += 1) {
          const jx = hx + dx;
          const jz = hz + dz;
          if (dx * dx + dz * dz <= width * width && jx >= 0 && jz >= 0 && jx < nx && jz < nz) door[jz * nx + jx] = 1;
        }
      }
    }
  }
  return door;
}

function walkable(grid, x, z) {
  const ix = Math.floor((x - grid.minX) / grid.cell);
  const iz = Math.floor((z - grid.minZ) / grid.cell);
  return ix >= 0 && iz >= 0 && ix < grid.nx && iz < grid.nz && grid.walk[iz * grid.nx + ix] === 1;
}

// The floor plan of the set: where you can walk, where the scan stood, where you are.
function drawMap(w) {
  const { grid, map } = w;
  if (!grid || !map) return;
  const ctx = map.getContext("2d");
  if (!w.plan) {
    let x0 = grid.nx, x1 = 0, z0 = grid.nz, z1 = 0;
    for (let iz = 0; iz < grid.nz; iz += 1) {
      for (let ix = 0; ix < grid.nx; ix += 1) {
        if (!grid.walk[iz * grid.nx + ix]) continue;
        x0 = Math.min(x0, ix); x1 = Math.max(x1, ix); z0 = Math.min(z0, iz); z1 = Math.max(z1, iz);
      }
    }
    if (x1 < x0) return;
    const margin = 4;
    x0 -= margin; z0 -= margin; x1 += margin; z1 += margin;
    const plan = document.createElement("canvas");
    plan.width = x1 - x0 + 1;
    plan.height = z1 - z0 + 1;
    const image = plan.getContext("2d").createImageData(plan.width, plan.height);
    for (let iz = z0; iz <= z1; iz += 1) {
      for (let ix = x0; ix <= x1; ix += 1) {
        if (ix < 0 || iz < 0 || ix >= grid.nx || iz >= grid.nz || !grid.walk[iz * grid.nx + ix]) continue;
        image.data.set([237, 189, 105, 96], ((iz - z0) * plan.width + (ix - x0)) * 4);
      }
    }
    plan.getContext("2d").putImageData(image, 0, 0);
    const fit = Math.min(map.width / plan.width, map.height / plan.height);
    w.plan = { canvas: plan, x0, z0, fit, left: (map.width - plan.width * fit) / 2, top: (map.height - plan.height * fit) / 2 };
  }
  const { canvas, x0, z0, fit, left, top } = w.plan;
  const toMap = (x, z) => [left + ((x - grid.minX) / grid.cell - x0) * fit, top + ((z - grid.minZ) / grid.cell - z0) * fit];
  ctx.clearRect(0, 0, map.width, map.height);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(canvas, left, top, canvas.width * fit, canvas.height * fit);
  ctx.strokeStyle = "rgba(236, 238, 236, 0.7)";
  ctx.lineWidth = 2;
  for (const p of grid.points) {
    const [mx, mz] = toMap(p[0], p[2]);
    ctx.beginPath();
    ctx.arc(mx, mz, 5, 0, Math.PI * 2);
    ctx.stroke();
  }
  const [px, pz] = toMap(w.position[0], w.position[2]);
  const yaw = rad(w.mapYaw || 0);
  ctx.fillStyle = "rgba(237, 189, 105, 0.35)";
  ctx.beginPath();
  ctx.moveTo(px, pz);
  ctx.arc(px, pz, 34, yaw - Math.PI / 2 - 0.6, yaw - Math.PI / 2 + 0.6);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = "#edbd69";
  ctx.beginPath();
  ctx.arc(px, pz, 7, 0, Math.PI * 2);
  ctx.fill();
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
  const radiusM = WALK_RADIUS_M[splat.mode === "draft" ? "draft" : "refined"];
  const eye = (splat.eye || [0, 0, 0]).map(Number);
  w.grid = w.plan = null;
  try {
    const room = splat.units_per_m > 0 && splat.scan_points?.length > 1;
    Object.assign(w, room ? measureRoom(mesh, splat, eye) : measure(mesh, eye, radiusM));
  } catch {
    Object.assign(w, { free: new Float32Array(BINS).fill(0.3), scale: 1 }); // unreadable: stay put
  }
  camera.near = 0.05 * w.scale;
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
  const speed = SPEED_M_S * w.scale * (w.run ? 2 : 1);
  const targetX = ((Math.sin(yaw) * ahead + Math.cos(yaw) * side) / length) * speed;
  const targetZ = ((-Math.cos(yaw) * ahead + Math.sin(yaw) * side) / length) * speed;
  const ease = reducedMotion() ? 1 : 1 - Math.exp(-dt * 10);
  w.velocity[0] += (targetX - w.velocity[0]) * ease;
  w.velocity[1] += (targetZ - w.velocity[1]) * ease;
  if (w.grid) {
    const nextX = w.position[0] + w.velocity[0] * dt;
    const nextZ = w.position[2] + w.velocity[1] * dt;
    const moving = Math.hypot(w.velocity[0], w.velocity[1]) > 0.02 * w.scale;
    let stopped = false;
    if (walkable(w.grid, nextX, nextZ)) {
      w.position[0] = nextX;
      w.position[2] = nextZ;
    } else if (walkable(w.grid, nextX, w.position[2])) {
      w.position[0] = nextX; // slide along the obstacle
      w.velocity[1] = 0;
    } else if (walkable(w.grid, w.position[0], nextZ)) {
      w.position[2] = nextZ;
      w.velocity[0] = 0;
    } else {
      stopped = moving;
      w.velocity = [0, 0];
    }
    if (stopped !== w.atEdge) setEdge(vf, w, stopped);
    w.mapYaw = vf.view.yaw;
    drawMap(w);
    return;
  }
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
  vf.dialog.classList.toggle("is-walking-room", Boolean(w.grid));
  w.mapYaw = vf.view.yaw;
  drawMap(w);
  w.button.classList.add("is-active");
  w.button.setAttribute("aria-pressed", "true");
  const badge = vf.$(".vf-ai-badge");
  w.badgeText = badge.textContent;
  const built = w.grid ? `, built on ${w.grid.points.length} real scan points` : "";
  badge.textContent = `${vf.dressed?.label || "AI-imagined set dressing, not the real room"} · ${w.mode === "draft" ? "draft " : ""}3D reconstruction${built}`;
  vf.$(".vf-status").textContent = w.grid
    ? "Walking the whole set. W A S D to move, Shift to go faster, drag to look, E to leave."
    : "Walking the AI-dressed set. W A S D to move, drag to look, E to leave.";
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
  vf.dialog.classList.remove("is-walking", "is-walking-room");
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
  w.canvas = w.renderer = w.scene = w.spark = w.camera = w.mesh = w.url = w.free = w.grid = w.plan = null;
  w.scale = 1;
}

/* ---------------- Viewfinder hooks ---------------- */

const loadDressed = Viewfinder.prototype.loadDressed;
Viewfinder.prototype.loadDressed = async function (shotId, generation, renderer) {
  await loadDressed.call(this, shotId, generation, renderer);
  if (!isCurrent(this, generation) || !this.dressed?.splat?.url) return;
  const w = stateFor(this);
  w.button.hidden = false;
  this.$(".vf-status").textContent = "An AI-dressed version of this room is ready: press D to compare it, or E to walk through it.";
  if (w.autoWalk) {
    w.autoWalk = false;
    await toggle(this);
    // A one-point set opens on its most open side. A whole room keeps the frame's own heading:
    // there is no single best view of a room, and a demo link can name one.
    const yaw = w.linkYaw ?? (w.grid ? null : openHeading(w));
    if (w.active && yaw != null) {
      this.state.yaw = yaw;
      this.animateTo({ yaw }, reducedMotion() ? 1 : 900);
    }
  }
};

const close = Viewfinder.prototype.close;
Viewfinder.prototype.close = function () {
  const w = walks.get(this);
  if (w && this.dialog.open) {
    if (w.active && w.badgeText != null) this.$(".vf-ai-badge").textContent = w.badgeText;
    this.dialog.classList.remove("is-walking", "is-walking-room", "is-walk-loading");
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

/* ---------------- Direct link ---------------- */

// /app/#walk=<shot id> opens that scan point and steps straight into its set, for demos.
// &yaw=<degrees> sets the scan-relative heading to face on entry.
const linked = location.hash.match(/^#walk=([A-Za-z0-9._-]{1,440})(?:&yaw=(\d{1,3}))?$/);
if (linked) {
  const vf = new Viewfinder();
  Object.assign(stateFor(vf), { autoWalk: true, linkYaw: linked[2] == null ? null : Number(linked[2]) % 360 });
  vf.open(linked[1], null);
}

// For browser checks: the walk state of a viewfinder (limits, position).
export const walkState = (vf) => walks.get(vf) || null;
