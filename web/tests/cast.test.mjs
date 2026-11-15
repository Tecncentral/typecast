import test from "node:test";
import assert from "node:assert/strict";
import { findPath, HEIGHT_M } from "../viewfinder-cast.js";

// A 12 x 8 floor, 10 cm cells, with a wall across column 6 that has a one-cell door at row 6.
function room() {
  const nx = 12, nz = 8;
  const walk = new Uint8Array(nx * nz).fill(1);
  for (let iz = 0; iz < nz; iz += 1) if (iz !== 6) walk[iz * nx + 6] = 0;
  return { nx, nz, cell: 0.1, minX: 0, minZ: 0, walk };
}

test("stand-ins are life size", () => {
  assert.equal(HEIGHT_M, 1.75);
});

test("a stand-in's path goes through the door, never through the wall", () => {
  const grid = room();
  const path = findPath(grid, [0.15, 0, 0.15], [1.05, 0, 0.15]);
  assert.ok(path && path.length >= 3);
  assert.deepEqual(path[0].map((v) => +v.toFixed(2)), [0.15, 0.15]);
  assert.deepEqual(path.at(-1).map((v) => +v.toFixed(2)), [1.05, 0.15]);
  // Walk the whole polyline in 1 cm steps: every step is on the floor, and the wall is crossed at the door.
  let crossedAtDoor = false;
  for (let i = 1; i < path.length; i += 1) {
    const [a, b] = [path[i - 1], path[i]];
    const steps = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.01);
    for (let k = 0; k <= steps; k += 1) {
      const x = a[0] + ((b[0] - a[0]) * k) / steps, z = a[1] + ((b[1] - a[1]) * k) / steps;
      const ix = Math.floor(x / grid.cell), iz = Math.floor(z / grid.cell);
      assert.equal(grid.walk[iz * grid.nx + ix], 1, `path crosses a solid cell at ${x.toFixed(2)}, ${z.toFixed(2)}`);
      if (ix === 6) crossedAtDoor = iz === 6;
    }
  }
  assert.ok(crossedAtDoor, "the door was not used");
});

test("no path when the room is sealed or an end is not on the floor", () => {
  const grid = room();
  grid.walk[6 * grid.nx + 6] = 0;
  assert.equal(findPath(grid, [0.15, 0, 0.15], [1.05, 0, 0.15]), null);
  assert.equal(findPath(room(), [0.65, 0, 0.15], [1.05, 0, 0.15]), null);
});
