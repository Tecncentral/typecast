const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../viewfinder.js'), 'utf8');
const deferred = () => {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
};
const tick = () => new Promise(resolve => setImmediate(resolve));
const response = id => ({ ok: true, json: async () => ({
  shot_id: id, heading_deg: 0,
  faces: [0, 90, 180, 270].map(heading => ({ heading_deg: heading, image_path: `/cache/views/${id}-${heading}.jpg` })),
}) });

// Exercise the production asynchronous lifecycle and renderer against a small
// persistent-canvas WebGL double. It records uploads and models context loss;
// it does not pretend to verify GPU pixels, shader compilation or browser layout.
function harness() {
  const requests = new Map();
  const decodes = new Map();
  const uploads = [];
  let lost = false;
  const gl = new Proxy({
    getShaderParameter: () => !lost,
    getProgramParameter: () => !lost,
    getAttribLocation: () => 0,
    getUniformLocation: () => 0,
    getExtension: name => name === 'WEBGL_lose_context' ? { loseContext() { lost = true; } } : null,
    texImage2D(...args) { if (args.length === 6) uploads.push(args[5].src); },
  }, { get: (object, key) => key in object ? object[key] : () => ({}) });
  const context = {
    document: { body: {}, querySelectorAll: () => [] },
    MutationObserver: class { observe() {} },
    fetch(url) {
      const request = deferred();
      requests.set(decodeURIComponent(url.split('/').at(-1)), request);
      return request.promise;
    },
    Image: class {
      naturalWidth = 32;
      decode() { return decodes.get(this.src)?.promise || Promise.resolve(); }
    },
    matchMedia: () => ({ matches: true }),
    cancelAnimationFrame() {},
  };
  vm.createContext(context);
  vm.runInContext(source.replace('export { Viewfinder, shotIdFromSrc };', 'globalThis.TestViewfinder = Viewfinder;'), context);
  const classes = new Set();
  const dialog = {
    open: false,
    classList: { contains: x => classes.has(x), add: x => classes.add(x), remove: (...xs) => xs.forEach(x => classes.delete(x)) },
    showModal() { this.open = true; }, close() { this.open = false; },
    animate() { return { finished: Promise.resolve() }; }, getAnimations: () => [],
  };
  const nodes = new Map();
  const vf = Object.create(context.TestViewfinder.prototype);
  const reveals = [];
  Object.assign(vf, {
    dialog, generation: 0, animating: false, state: { lens: 24, aspect: {} },
    poster: { style: {}, getAnimations: () => [] },
    canvas: { style: {}, getContext: () => gl },
    $(selector) { if (!nodes.has(selector)) nodes.set(selector, { textContent: '' }); return nodes.get(selector); },
    resize() {}, setAspect() {}, updateReadout() {}, draw() {},
    flyIn: () => Promise.resolve(),
    revealLive(missing) { reveals.push({ shotId: this.sweep.shot_id, missing }); classes.add('is-live'); },
  });
  function open(id) { return vf.open(id, { src: `${id}.jpg`, alt: `Room at ${id}`, closest: () => null }); }
  function respond(id) { requests.get(id).resolve(response(id)); }
  function delayImages(id) {
    const waits = [0, 90, 180, 270].map(h => deferred());
    waits.forEach((wait, i) => decodes.set(`/cache/views/${id}-${i * 90}.jpg`, wait));
    return () => waits.forEach(wait => wait.resolve());
  }
  return { vf, classes, uploads, reveals, nodes, requests, open, respond, delayImages, isLost: () => lost };
}

test('closing before fetch resolves cannot overwrite a newly opened scan', async () => {
  const h = harness();
  const old = h.open('old');
  await h.vf.close();
  const fresh = h.open('fresh');
  h.respond('fresh');
  await fresh;
  const renderer = h.vf.renderer;
  h.respond('old');
  await old;
  assert.equal(h.vf.sweep.shot_id, 'fresh');
  assert.equal(h.vf.renderer, renderer);
  assert.equal(h.classes.has('no-webgl'), false);
  assert.deepEqual(h.reveals, [{ shotId: 'fresh', missing: 0 }]);
  assert.equal(h.uploads.length, 4);
});

test('late image decodes from a closed scan cannot contaminate the new renderer', async () => {
  const h = harness();
  const finishOldImages = h.delayImages('old');
  const old = h.open('old');
  h.respond('old');
  await tick();
  assert.ok(h.vf.renderer);
  assert.equal(h.uploads.length, 0);
  await h.vf.close();
  const fresh = h.open('fresh');
  h.respond('fresh');
  await fresh;
  const renderer = h.vf.renderer;
  finishOldImages();
  await old;
  assert.equal(h.vf.renderer, renderer);
  assert.equal(h.uploads.length, 4);
  assert.ok(h.uploads.every(url => url.includes('/fresh-')));
  assert.deepEqual(h.reveals, [{ shotId: 'fresh', missing: 0 }]);
});

test('the persistent canvas remains usable across normal close and reopen', async () => {
  const h = harness();
  for (const id of ['first', 'second']) {
    const opening = h.open(id);
    h.respond(id);
    await opening;
    assert.ok(h.vf.renderer);
    assert.equal(h.classes.has('no-webgl'), false);
    await h.vf.close();
    assert.equal(h.vf.renderer, null);
    assert.equal(h.isLost(), false);
  }
  assert.equal(h.uploads.length, 8);
  assert.deepEqual(h.reveals.map(item => item.shotId), ['first', 'second']);
});

test('a late AI-dressing response for a closed scan never dresses the next room', async () => {
  const h = harness();
  const old = h.open('old');
  h.respond('old');
  await old;
  const lateDressing = h.requests.get('old'); // the /api/dressed request issued once the old scan went live
  await h.vf.close();
  const fresh = h.open('fresh');
  h.respond('fresh');
  await fresh;
  const faces = [0, 90, 180, 270].map(yaw => ({ yaw_deg: yaw, pitch_deg: 0, tan_h: 1, tan_v: 0.56,
    dressed_url: `/cache/worlds/old/dressed_${yaw}.jpg` }));
  lateDressing.resolve({ ok: true, json: async () => ({ scene: 'INT. OLD ROOM - DAY.', label: 'AI', faces }) });
  await tick(); await tick();
  assert.equal(h.vf.dressed ?? null, null);
  assert.ok(h.uploads.every(url => !url.includes('/worlds/old/')));
  assert.equal(h.uploads.length, 8);
});
