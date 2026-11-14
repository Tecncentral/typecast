'use strict';
// Contract tests for index/director-reel.js. Deterministic fakes only: no browser, network, audio or GPU.
const test = require('node:test');
const assert = require('node:assert/strict');
const R = require('../director-reel.js');

function makeEnv(opt = {}) {
  const env = { tracks: [], recorders: [], canvases: [], clock: 0, renders: [], loads: [], hiddenAfter: opt.hiddenAfter ?? Infinity, ticks: 0 };
  class FakeStream { constructor() { this.t = [{ stops: 0, stop() { this.stops++; } }]; env.tracks.push(...this.t); } getTracks() { return this.t; } }
  class FakeCanvas {
    constructor(w, h) { this.width = w; this.height = h; env.canvases.push(this); }
    getContext() { return { calls: 0 }; }
  }
  if (!opt.noCaptureStream) FakeCanvas.prototype.captureStream = function (fps) { env.fps = fps; return new FakeStream(); };
  class FakeMediaRecorder {
    static isTypeSupported(t) { return (opt.supported ?? ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']).includes(t); }
    constructor(stream, o) { this.stream = stream; this.options = o; this.state = 'inactive'; env.recorders.push(this); }
    start(slice) {
      this.slice = slice; this.state = 'recording';
      if (opt.recorderError) setImmediate(() => this.onerror && this.onerror({ error: new Error('boom') }));
    }
    stop() {
      if (this.state === 'inactive') return;
      this.state = 'inactive';
      if (!opt.empty && this.ondataavailable) this.ondataavailable({ data: new Blob(['frame']) });
      queueMicrotask(() => this.onstop && this.onstop());
    }
  }
  env.deps = {
    createCanvas: (w, h) => new FakeCanvas(w, h),
    MediaRecorder: opt.noMediaRecorder ? undefined : FakeMediaRecorder,
    now: () => env.clock,
    requestFrame: (cb) => { env.clock += 1000 / 30; env.ticks++; return setImmediate(cb); },
    cancelFrame: (id) => clearImmediate(id),
    isHidden: () => env.ticks > env.hiddenAfter,
  };
  env.render = (ctx, W, H, o) => env.renders.push({ W, H, ...o });
  env.loadImage = opt.loadImage || ((id) => { env.loads.push(id); return Promise.resolve({ id, width: 1024, height: 768 }); });
  return env;
}
const input = (n = 2, extra = {}) => ({ variant: 'A', scenes: Array.from({ length: n }, (_, i) => ({
  id: `s${i + 1}`, heading: `INT. ROOM ${i + 1}`, shot_id: `shot_${i + 1}`, prov: `Scene ${i + 1}`,
  shot: { duration_sec: 1, dialogue: 'Hi.', actors: [{ id: 'a1', name: 'Ada', pose: 'walk', x0: 0.2, y0: 0.8, x1: 0.6, y1: 0.8, scale: 1 }] } })), ...extra });
const run = (env, snap, extra = {}) => R.recordReel(snap, { render: env.render, loadImage: env.loadImage, deps: env.deps, ...extra });
const code = (c) => (e) => { assert.ok(e instanceof R.ReelError, `expected ReelError, got ${e}`); assert.equal(e.code, c); return true; };
const cleaned = (env) => {
  for (const t of env.tracks) assert.ok(t.stops >= 1, 'every track stopped');
  for (const c of env.canvases) { assert.equal(c.width, 0); assert.equal(c.height, 0); }
};

test('pickMimeType order, fallback, null and throwing', () => {
  assert.equal(R.pickMimeType({ isTypeSupported: () => true }), R.MIME_CANDIDATES[0]);
  assert.equal(R.pickMimeType({ isTypeSupported: (t) => t === 'video/webm' }), 'video/webm');
  assert.equal(R.pickMimeType({ isTypeSupported: () => false }), null);
  assert.equal(R.pickMimeType(undefined), null);
  assert.equal(R.pickMimeType({ isTypeSupported: () => { throw new Error('x'); } }), null);
  assert.equal(R.MIME_CANDIDATES.every((m) => m.startsWith('video/webm')), true);
});

test('buildSnapshot rejects invalid input', () => {
  assert.throws(() => R.buildSnapshot({ variant: 'A', scenes: [] }), (e) => code('invalid')(e) && /No assigned scenes/.test(e.message));
  assert.throws(() => R.buildSnapshot(input(9)), code('invalid'));
  assert.throws(() => R.buildSnapshot(input(1, { variant: 'C' })), code('invalid'));
  const bad = input(1); bad.scenes[0].shot_id = '../etc/passwd'; assert.throws(() => R.buildSnapshot(bad), code('invalid'));
  const none = input(1); none.scenes[0].shot_id = undefined; assert.throws(() => R.buildSnapshot(none), code('invalid'));
  assert.doesNotThrow(() => R.buildSnapshot(input(8)));
});

test('buildSnapshot sanitizes, clamps, deep-freezes and copies', () => {
  const src = input(3);
  src.scenes[0].shot.duration_sec = 0; src.scenes[1].shot.duration_sec = 99; src.scenes[2].shot.duration_sec = NaN;
  src.scenes[0].shot.dialogue = 'x'.repeat(900);
  src.scenes[1].shot.actors = [1, 2, 3, 4].map((i) => ({ name: `N${i}`, pose: 'dance', x0: -1, y0: 2, x1: 5, y1: -3, scale: 9 }));
  src.scenes[2].shot.actors = [{ name: 'Tiny', scale: 0.01, x0: 0.5, y0: 0.5 }];
  const s = R.buildSnapshot(src);
  assert.deepEqual(s.scenes.map((x) => x.shot.duration_sec), [1, 30, 5]);
  assert.deepEqual(s.scenes.map((x) => x.start), [0, 1, 31]);
  assert.equal(s.total_sec, 36);
  assert.equal(s.scenes[0].shot.dialogue.length, 800);
  const a = s.scenes[1].shot.actors;
  assert.equal(a.length, 3);
  assert.deepEqual([a[0].pose, a[0].x0, a[0].y0, a[0].x1, a[0].y1, a[0].scale], ['stand', 0, 1, 1, 0, 2]);
  assert.equal(s.scenes[2].shot.actors[0].scale, 0.3);
  assert.ok(Object.isFrozen(s) && Object.isFrozen(s.scenes) && Object.isFrozen(s.scenes[1].shot.actors[0]));
  assert.throws(() => { 'use strict'; s.scenes[0].shot.dialogue = 'changed'; }, TypeError);
  src.scenes[1].shot.actors[0].name = 'MUTATED'; src.scenes.push(input(1).scenes[0]); src.variant = 'B';
  assert.equal(s.scenes[1].shot.actors[0].name, 'N1'); assert.equal(s.scenes.length, 3); assert.equal(s.variant, 'A');
});

test('sceneAt boundaries', () => {
  const s = R.buildSnapshot(input(3)); // 1s each, total 3
  const at = (t) => { const r = R.sceneAt(s, t); return [r.index, r.local]; };
  assert.deepEqual(at(0), [0, 0]);
  assert.deepEqual(at(0.5), [0, 0.5]);
  assert.deepEqual(at(1), [1, 0]);
  assert.deepEqual(at(3), [2, 1]);
  assert.deepEqual(at(10), [2, 1]);
  assert.deepEqual(at(-4), [0, 0]);
});

test('recordReel succeeds with real frames, linear timing, injected renderer and full cleanup', async () => {
  const env = makeEnv(); const phases = [];
  const snap = R.buildSnapshot(input(2));
  const out = await run(env, snap, { onProgress: (p) => phases.push(p.phase) });
  assert.ok(out.blob instanceof Blob && out.blob.size > 0);
  assert.match(out.blob.type, /^video\/webm/);
  assert.equal(out.mimeType, R.MIME_CANDIDATES[0]);
  assert.equal(out.duration_sec, snap.total_sec);
  assert.equal(env.recorders.length, 1); assert.equal(env.recorders[0].slice, 250);
  assert.equal(env.recorders[0].options.mimeType, out.mimeType);
  assert.deepEqual(env.loads, ['shot_1', 'shot_2']);
  assert.ok(env.renders.length > 10);
  for (const r of env.renders) {
    assert.equal(r.editing, false); assert.equal(r.sel, -1);
    assert.ok(r.imgEl && r.imgEl.width > 0, 'real image object per frame');
    assert.ok(r.t >= 0 && r.t <= r.shot.duration_sec + 1e-9, 'local time within scene');
  }
  assert.equal(env.renders[0].imgEl.id, 'shot_1');
  const last = env.renders.at(-1);
  assert.equal(last.imgEl.id, 'shot_2'); assert.equal(last.t, last.shot.duration_sec);
  const order = ['loading', 'recording', 'finalizing'].map((p) => phases.indexOf(p));
  assert.ok(order.every((i) => i >= 0) && order[0] < order[1] && order[1] < order[2], `phases ${phases}`);
  cleaned(env);
});

for (const [label, opt] of [['no MediaRecorder', { noMediaRecorder: true }], ['no supported codec', { supported: [] }], ['no captureStream', { noCaptureStream: true }]]) {
  test(`unsupported: ${label} fails before loading any image`, async () => {
    const env = makeEnv(opt);
    await assert.rejects(run(env, R.buildSnapshot(input(2))), code('unsupported'));
    assert.equal(env.loads.length, 0); assert.equal(env.recorders.length, 0);
    cleaned(env);
  });
}

test('image failure names the scene and never starts a recorder', async () => {
  const env = makeEnv({ loadImage: (id) => (id === 'shot_2' ? Promise.reject(new Error('404')) : Promise.resolve({ width: 10 })) });
  await assert.rejects(run(env, R.buildSnapshot(input(3))), (e) => code('image')(e) && /scene 2/.test(e.message));
  assert.equal(env.recorders.length, 0); cleaned(env);
  const env2 = makeEnv({ loadImage: () => Promise.resolve({ width: 0, naturalWidth: 0 }) });
  await assert.rejects(run(env2, R.buildSnapshot(input(1))), (e) => code('image')(e) && /scene 1/.test(e.message));
  assert.equal(env2.recorders.length, 0);
});

test('cancel while an image is still loading', async () => {
  const env = makeEnv({ loadImage: () => new Promise(() => {}) }); const ctrl = new AbortController();
  const p = run(env, R.buildSnapshot(input(2)), { signal: ctrl.signal });
  setImmediate(() => ctrl.abort());
  await assert.rejects(p, (e) => code('cancelled')(e) && e.name === 'AbortError');
  assert.equal(env.recorders.length, 0); cleaned(env);
});

test('already-aborted signal rejects as cancelled', async () => {
  const env = makeEnv(); const ctrl = new AbortController(); ctrl.abort();
  await assert.rejects(run(env, R.buildSnapshot(input(1)), { signal: ctrl.signal }), code('cancelled'));
});

test('cancel mid-recording discards output and stops tracks', async () => {
  const env = makeEnv(); const ctrl = new AbortController(); let resolved = null;
  const p = run(env, R.buildSnapshot(input(2)), { signal: ctrl.signal,
    onProgress: (x) => { if (x.phase === 'recording' && x.t > 0.5) ctrl.abort(); } }).then((v) => { resolved = v; return v; });
  await assert.rejects(p, (e) => code('cancelled')(e) && e.name === 'AbortError');
  assert.equal(resolved, null); assert.equal(env.recorders[0].state, 'inactive'); cleaned(env);
});

test('hidden tab mid-recording rejects', async () => {
  const env = makeEnv({ hiddenAfter: 10 });
  await assert.rejects(run(env, R.buildSnapshot(input(2))), code('hidden')); cleaned(env);
});

test('empty recorder output rejects', async () => {
  const env = makeEnv({ empty: true });
  await assert.rejects(run(env, R.buildSnapshot(input(1))), code('empty')); cleaned(env);
});

test('recorder error rejects', async () => {
  const env = makeEnv({ recorderError: true });
  await assert.rejects(run(env, R.buildSnapshot(input(2))), code('recorder')); cleaned(env);
});

test('unfrozen or hand-built snapshot is invalid', async () => {
  const env = makeEnv();
  const loose = JSON.parse(JSON.stringify(R.buildSnapshot(input(1))));
  await assert.rejects(run(env, loose), code('invalid'));
  await assert.rejects(R.recordReel(R.buildSnapshot(input(1)), { loadImage: env.loadImage, deps: env.deps }), code('invalid'));
  assert.equal(env.loads.length, 0);
});
