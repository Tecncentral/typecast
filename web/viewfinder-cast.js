// Stand-ins for a walkable set: life-size people to block a scene against.
// The room's scale is known (its cameras come from the scan), so a 1.78 m man is 1.78 m
// against the desks and doorways, and a framed shot shows what the lens really holds.
// The people are six rigged, animated public-domain figures (web/vendor/people/). If they
// cannot be loaded, jointed mannequins built from primitives stand in for them.
// They stand, shift their weight, and walk the aisles along paths found on the walk's floor grid.

const HEIGHT_M = 1.75;
const WALK_M_S = 1.15;
const STRIDE_M = 1.45; // one full gait cycle: two steps
const TINTS = [0xb9b2a6, 0x8f9aa8, 0xb59f85, 0x9aa596, 0xa894a0, 0xc2b79a];
const KEEP_RIGHT_M = 0.32; // walkers keep to their right, so two can pass
const PEOPLE = [
  { file: "man-in-suit.glb", height: 1.78 },
  { file: "woman-casual.glb", height: 1.66 },
  { file: "business-man.glb", height: 1.8 },
  { file: "long-sleeves.glb", height: 1.75 },
  { file: "woman.glb", height: 1.64 },
  { file: "man.glb", height: 1.77 },
];
let peopleLoading = null;

/** The animated people, loaded once per page. Resolves to [] when they cannot be loaded. */
function loadPeople() {
  peopleLoading ||= (async () => {
    try {
      const [{ GLTFLoader }, SkeletonUtils] = await Promise.all([
        import("three/addons/loaders/GLTFLoader.js"),
        import("three/addons/utils/SkeletonUtils.js"),
      ]);
      const loader = new GLTFLoader();
      return await Promise.all(
        PEOPLE.map(async (person) => {
          const gltf = await loader.loadAsync(new URL(`./vendor/people/${person.file}`, import.meta.url).href);
          const clip = (pattern) => gltf.animations.find((a) => pattern.test(a.name));
          const idle = clip(/(^|[|_ ])idle$/i);
          const walk = clip(/(^|[|_ ])walk(ing)?$/i);
          if (!idle || !walk) throw new Error("missing clips");
          return { ...person, scene: gltf.scene, idle, walk, clone: SkeletonUtils.clone };
        }),
      );
    } catch {
      return [];
    }
  })();
  return peopleLoading;
}

/** One animated person standing at the origin of `root`, facing +z, `heightUnits` tall. */
function buildPerson(THREE, person, heightUnits) {
  const root = new THREE.Group();
  const body = person.clone(person.scene);
  root.add(body);
  body.updateMatrixWorld(true);
  const box = new THREE.Box3();
  body.traverse((node) => {
    if (!node.isMesh) return;
    node.frustumCulled = false; // a skinned mesh's bounds in bind space say little about where it is drawn
    if (node.isSkinnedMesh) {
      node.computeBoundingBox();
      box.union(node.boundingBox.clone().applyMatrix4(node.matrixWorld));
    } else {
      box.expandByObject(node);
    }
  });
  const tall = box.max.y - box.min.y;
  const fit = tall > 0 ? heightUnits / tall : 1;
  body.scale.multiplyScalar(fit);
  body.position.y -= box.min.y * fit;
  const mixer = new THREE.AnimationMixer(body);
  const idle = mixer.clipAction(person.idle);
  const walk = mixer.clipAction(person.walk);
  idle.play();
  walk.play();
  walk.setEffectiveWeight(0);
  return { root, mixer, idle, walk };
}

const rad = (d) => (d * Math.PI) / 180;

/** A jointed 1.75 m figure standing at its origin, facing +z. Returns the root and its joints. */
function buildFigure(THREE, tint) {
  const skin = new THREE.MeshStandardMaterial({ color: tint, roughness: 0.82, metalness: 0.02 });
  const dark = new THREE.MeshStandardMaterial({ color: new THREE.Color(tint).multiplyScalar(0.55), roughness: 0.9 });
  const limb = (length, radius, material = skin) => {
    // A capsule hanging down from its pivot.
    const mesh = new THREE.Mesh(new THREE.CapsuleGeometry(radius, Math.max(0.001, length - 2 * radius), 6, 14), material);
    mesh.position.y = -length / 2;
    return mesh;
  };
  const pivot = (parent, x, y, z) => {
    const group = new THREE.Group();
    group.position.set(x, y, z);
    parent.add(group);
    return group;
  };

  const root = new THREE.Group();
  const hips = pivot(root, 0, 0.93, 0);
  const pelvis = new THREE.Mesh(new THREE.CapsuleGeometry(0.105, 0.13, 6, 14), dark);
  pelvis.rotation.z = Math.PI / 2;
  hips.add(pelvis);

  const spine = pivot(hips, 0, 0.06, 0);
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.125, 0.3, 8, 16), skin);
  torso.position.y = 0.26;
  torso.scale.set(1.1, 1, 0.72);
  spine.add(torso);
  const shoulders = new THREE.Mesh(new THREE.CapsuleGeometry(0.075, 0.26, 6, 14), skin);
  shoulders.rotation.z = Math.PI / 2;
  shoulders.position.y = 0.47;
  spine.add(shoulders);
  const neck = pivot(spine, 0, 0.54, 0);
  const throat = limb(0.11, 0.045);
  throat.position.y = 0.045;
  neck.add(throat);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.105, 20, 16), skin);
  head.position.y = 0.2;
  head.scale.set(0.9, 1.12, 1);
  neck.add(head);

  const joints = { hips, spine, neck, arms: [], legs: [] };
  for (const side of [-1, 1]) {
    const shoulder = pivot(spine, side * 0.2, 0.47, 0);
    shoulder.add(limb(0.29, 0.046));
    const elbow = pivot(shoulder, 0, -0.29, 0);
    elbow.add(limb(0.26, 0.04));
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.046, 12, 10), skin);
    hand.position.y = -0.29;
    hand.scale.set(0.8, 1.2, 1);
    elbow.add(hand);
    joints.arms.push({ shoulder, elbow, side });

    const hip = pivot(hips, side * 0.095, -0.02, 0);
    hip.add(limb(0.43, 0.072, dark));
    const knee = pivot(hip, 0, -0.43, 0);
    knee.add(limb(0.42, 0.055, dark));
    const foot = new THREE.Mesh(new THREE.CapsuleGeometry(0.045, 0.15, 4, 10), dark);
    foot.rotation.x = Math.PI / 2;
    foot.position.set(0, -0.435, 0.065);
    knee.add(foot);
    joints.legs.push({ hip, knee, side });
  }
  return { root, joints };
}

/** Pose a figure. `gait` is the walk phase in radians; `blend` 0 is standing, 1 is walking. */
function pose(figure, time, gait, blend, seed) {
  const { hips, spine, neck, arms, legs } = figure.joints;
  const idle = 1 - blend;
  // Standing: breathe, shift weight, look around a little.
  const sway = Math.sin(time * 0.55 + seed) * 0.018 * idle;
  hips.position.x = sway;
  hips.position.y = 0.93 - Math.abs(Math.cos(gait)) * 0.022 * blend - Math.abs(sway) * 0.3;
  hips.rotation.z = -sway * 1.4;
  hips.rotation.y = Math.sin(gait) * 0.07 * blend;
  spine.rotation.x = 0.05 * blend + Math.sin(time * 1.3 + seed) * 0.012 * idle;
  spine.rotation.z = sway * 1.6;
  spine.rotation.y = -Math.sin(gait) * 0.1 * blend;
  neck.rotation.y = Math.sin(time * 0.31 + seed * 2.1) * 0.45 * idle;
  neck.rotation.x = Math.sin(time * 0.23 + seed) * 0.06 * idle;
  for (const { hip, knee, side } of legs) {
    const phase = gait + (side > 0 ? Math.PI : 0);
    hip.rotation.x = -Math.sin(phase) * 0.5 * blend;
    hip.rotation.z = side * 0.02 + sway * 0.6;
    // The knee folds while the leg swings forward, and stays nearly straight on the ground.
    knee.rotation.x = (0.08 + Math.max(0, Math.cos(phase)) * 0.95) * blend + 0.03 * idle;
  }
  for (const { shoulder, elbow, side } of arms) {
    const phase = gait + (side > 0 ? 0 : Math.PI);
    shoulder.rotation.x = -Math.sin(phase) * 0.42 * blend + Math.sin(time * 0.7 + seed + side) * 0.02 * idle;
    shoulder.rotation.z = side * 0.09;
    elbow.rotation.x = -(0.22 + Math.max(0, -Math.sin(phase)) * 0.35) * blend - 0.12 * idle;
  }
}

/** Shortest walkable path between two world points on the floor grid, as smoothed world points. */
function findPath(grid, from, to) {
  const { nx, nz, cell, minX, minZ, walk } = grid;
  const cellOf = (p) => Math.floor((p[2] - minZ) / cell) * nx + Math.floor((p[0] - minX) / cell);
  const start = cellOf(from);
  const goal = cellOf(to);
  if (!walk[start] || !walk[goal]) return null;
  const came = new Int32Array(nx * nz).fill(-1);
  const queue = new Int32Array(nx * nz);
  let head = 0;
  let tail = 0;
  came[start] = start;
  queue[tail++] = start;
  const steps = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];
  while (head < tail && came[goal] < 0) {
    const at = queue[head++];
    const ix = at % nx;
    const iz = (at - ix) / nx;
    for (const [dx, dz] of steps) {
      const jx = ix + dx;
      const jz = iz + dz;
      if (jx < 0 || jz < 0 || jx >= nx || jz >= nz) continue;
      const next = jz * nx + jx;
      // No cutting corners between two solid cells.
      if (came[next] >= 0 || !walk[next] || !walk[iz * nx + jx] || !walk[jz * nx + ix]) continue;
      came[next] = at;
      queue[tail++] = next;
    }
  }
  if (came[goal] < 0) return null;
  const cells = [];
  for (let at = goal; at !== start; at = came[at]) cells.push(at);
  cells.push(start);
  cells.reverse();
  const centres = cells.map((c) => [minX + ((c % nx) + 0.5) * cell, minZ + (Math.floor(c / nx) + 0.5) * cell]);
  const onFloor = (x, z) => {
    const ix = Math.floor((x - minX) / cell);
    const iz = Math.floor((z - minZ) / cell);
    return ix >= 0 && iz >= 0 && ix < nx && iz < nz && walk[iz * nx + ix] === 1;
  };
  const clear = (a, b) => {
    // Fine steps: a line can clip the corner of a solid cell between two coarse samples.
    const steps = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / (cell / 10));
    for (let k = 0; k <= steps; k += 1) {
      if (!onFloor(a[0] + ((b[0] - a[0]) * k) / steps, a[1] + ((b[1] - a[1]) * k) / steps)) return false;
    }
    return true;
  };
  // Pull the stair-stepped cell path tight: from each corner, head for the furthest one in clear sight.
  let points = [centres[0]];
  for (let i = 0; i < centres.length - 1; ) {
    let j = centres.length - 1;
    while (j > i + 1 && !clear(centres[i], centres[j])) j -= 1;
    points.push(centres[j]);
    i = j;
  }
  for (let pass = 0; pass < 2; pass += 1) {
    // Round the corners (Chaikin), keeping the ends, only while the rounded path stays on the floor.
    const next = [points[0]];
    for (let i = 0; i < points.length - 1; i += 1) {
      const [a, b] = [points[i], points[i + 1]];
      next.push([a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25], [a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75]);
    }
    next.push(points.at(-1));
    if (!next.every((point, i) => i === 0 || clear(next[i - 1], point))) break;
    points = next;
  }
  return points;
}

function measurePath(points) {
  const lengths = [0];
  for (let i = 1; i < points.length; i += 1) {
    lengths.push(lengths[i - 1] + Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]));
  }
  return lengths;
}

function along(points, lengths, distance) {
  let i = 1;
  while (i < lengths.length - 1 && lengths[i] < distance) i += 1;
  const span = lengths[i] - lengths[i - 1] || 1;
  const t = Math.min(1, Math.max(0, (distance - lengths[i - 1]) / span));
  const [a, b] = [points[i - 1], points[i]];
  return { x: a[0] + (b[0] - a[0]) * t, z: a[1] + (b[1] - a[1]) * t, heading: Math.atan2(b[0] - a[0], b[1] - a[1]) };
}

/**
 * The cast of one set. `scale` is world units per metre, `floorY` the floor's height,
 * `grid` the walk's floor grid.
 */
export function createCast(THREE, scene, { scale, floorY, grid }) {
  const group = new THREE.Group();
  const sky = new THREE.HemisphereLight(0xfff0dc, 0x2b2622, 1.15);
  const key = new THREE.DirectionalLight(0xffe2bd, 1.5);
  key.position.set(0.4, 1, 0.3);
  group.add(sky, key);
  scene.add(group);
  const members = [];
  let people = [];
  const ready = loadPeople().then((loaded) => {
    people = loaded;
  });
  const isWalkable = (x, z) => {
    const ix = Math.floor((x - grid.minX) / grid.cell);
    const iz = Math.floor((z - grid.minZ) / grid.cell);
    return ix >= 0 && iz >= 0 && ix < grid.nx && iz < grid.nz && grid.walk[iz * grid.nx + ix] === 1;
  };

  function add(x, z, heading, route = null) {
    const person = people.length ? people[members.length % people.length] : null;
    const heightM = person ? person.height : HEIGHT_M;
    let body;
    if (person) {
      body = buildPerson(THREE, person, heightM * scale);
    } else {
      const figure = buildFigure(THREE, TINTS[members.length % TINTS.length]);
      figure.root.scale.setScalar(scale * (heightM / 1.75));
      body = { root: figure.root, figure };
    }
    body.root.position.set(x, floorY, z);
    body.root.rotation.y = heading;
    group.add(body.root);
    const member = { ...body, x, z, heading, route, heightM, travelled: 0, direction: 1, pause: 0, blend: 0, gait: 0, side: 0,
      seed: members.length * 1.7 };
    members.push(member);
    return member;
  }

  function nearestFloor(x, z) {
    for (let r = 0; r <= 12; r += 1) {
      for (let k = 0; k < (r ? 12 : 1); k += 1) {
        const px = x + Math.sin((k / 12) * Math.PI * 2) * r * grid.cell;
        const pz = z + Math.cos((k / 12) * Math.PI * 2) * r * grid.cell;
        if (isWalkable(px, pz)) return [px, pz];
      }
    }
    return null;
  }

  return {
    members,
    ready,
    get size() {
      return members.length;
    },
    /** Stand someone as near as possible to a point, facing a viewfinder heading (degrees). */
    async place(x, z, facingDeg) {
      await ready;
      const spot = nearestFloor(x, z);
      if (!spot) return null;
      const yaw = rad(facingDeg);
      return add(spot[0], spot[1], Math.atan2(Math.sin(yaw), -Math.cos(yaw)));
    },
    /** Two people walking the room from scan point to scan point in opposite directions, and three standing off their route. */
    async populate() {
      await ready;
      const stops = grid.points.map((p) => [p[0], p[1], p[2]]);
      let route = [];
      for (let i = 0; i < stops.length - 1; i += 1) {
        const leg = findPath(grid, stops[i], stops[i + 1]);
        if (leg) route = route.concat(route.length ? leg.slice(1) : leg);
      }
      if (route.length > 1) {
        const lengths = measurePath(route);
        for (const [share, direction] of [[0.3, 1], [0.8, -1]]) {
          const start = along(route, lengths, lengths.at(-1) * share);
          const walker = add(start.x, start.z, start.heading + (direction < 0 ? Math.PI : 0), { points: route, lengths });
          walker.travelled = lengths.at(-1) * share;
          walker.direction = direction;
        }
      }
      // Standers: beside scan points, on the walkable spot furthest from the walkers' route.
      const reach = 1.3 * scale;
      const beside = [stops[Math.min(1, stops.length - 1)], stops[Math.floor(stops.length / 2)], stops.at(-1)];
      for (const stop of beside.filter((s, i) => beside.indexOf(s) === i)) {
        let best = null;
        for (let k = 0; k < 16; k += 1) {
          const px = stop[0] + Math.sin((k / 16) * Math.PI * 2) * reach;
          const pz = stop[2] + Math.cos((k / 16) * Math.PI * 2) * reach;
          if (!isWalkable(px, pz)) continue;
          const clear = route.reduce((least, p) => Math.min(least, Math.hypot(p[0] - px, p[1] - pz)), Infinity);
          if (!best || clear > best.clear) best = { px, pz, clear };
        }
        if (best) add(best.px, best.pz, Math.atan2(stop[0] - best.px, stop[2] - best.pz));
      }
      return members.length;
    },
    update(dt, time) {
      for (const m of members) {
        let walking = 0;
        if (m.route) {
          const total = m.route.lengths.at(-1);
          if (m.pause > 0) {
            m.pause -= dt;
          } else {
            walking = 1;
            m.travelled += m.direction * WALK_M_S * scale * dt;
            if (m.travelled >= total || m.travelled <= 0) {
              m.travelled = Math.min(total, Math.max(0, m.travelled));
              m.direction *= -1;
              m.pause = 2.5; // stop, look around, walk back
            }
            m.gait += ((WALK_M_S * dt) / STRIDE_M) * Math.PI * 2;
          }
          const at = along(m.route.points, m.route.lengths, m.travelled);
          const want = at.heading + (m.direction < 0 ? Math.PI : 0);
          const turn = ((want - m.heading + Math.PI * 3) % (Math.PI * 2)) - Math.PI;
          m.heading += turn * Math.min(1, dt * 6);
          // Keep right of the route's centre line where the floor allows, so walkers pass each other.
          const rightX = -Math.cos(want);
          const rightZ = Math.sin(want);
          const room = isWalkable(at.x + rightX * KEEP_RIGHT_M * scale * 1.6, at.z + rightZ * KEEP_RIGHT_M * scale * 1.6) ? 1 : 0;
          m.side += (room - m.side) * Math.min(1, dt * 2);
          m.x = at.x + rightX * KEEP_RIGHT_M * scale * m.side;
          m.z = at.z + rightZ * KEEP_RIGHT_M * scale * m.side;
        }
        m.blend += (walking - m.blend) * Math.min(1, dt * 5);
        m.root.position.set(m.x, floorY, m.z);
        m.root.rotation.y = m.heading;
        if (m.mixer) {
          m.walk.setEffectiveWeight(m.blend);
          m.idle.setEffectiveWeight(1 - m.blend);
          m.mixer.update(dt);
        } else {
          pose(m.figure, time, m.gait, m.blend, m.seed);
        }
      }
    },
    clear() {
      for (const m of members) {
        group.remove(m.root);
        m.mixer?.stopAllAction();
        // A person shares its geometry with the loaded model; only a mannequin owns what it is made of.
        if (m.figure) m.root.traverse((node) => node.geometry?.dispose());
      }
      members.length = 0;
    },
    dispose() {
      this.clear();
      scene.remove(group);
    },
  };
}

export { findPath, HEIGHT_M };
