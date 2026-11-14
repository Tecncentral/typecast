// Typecast Director: silent WebM movie-preview reel.
// Records an immutable snapshot of the chosen variant over real, same-origin indexed frames.
// No audio, no microphone, no network calls of its own, no generated imagery. Rendering is injected.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api; else root.TypecastReel = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const LIMITS = Object.freeze({ maxScenes: 8, minSceneSec: 1, maxSceneSec: 30, maxActors: 3, width: 1280, height: 720, fps: 30 });
  const MIME_CANDIDATES = Object.freeze(['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']);
  const POSES = ['stand', 'sit', 'walk'];
  const SAFE_ID = /^[\w.:-]{1,120}$/;

  class ReelError extends Error {
    constructor(code, message) {
      super(message);
      this.code = code;
      this.name = code === 'cancelled' ? 'AbortError' : 'ReelError';
    }
  }

  const clamp = (v, lo, hi, d) => {
    if (v == null || v === '') return d;
    const n = Number(v);
    return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : d;
  };
  const r3 = (v) => Math.round(v * 1000) / 1000;

  function deepFreeze(o) {
    if (o && typeof o === 'object' && !Object.isFrozen(o)) {
      Object.freeze(o);
      for (const v of Object.values(o)) deepFreeze(v);
    }
    return o;
  }

  function pickMimeType(MR) {
    if (!MR || typeof MR.isTypeSupported !== 'function') return null;
    for (const c of MIME_CANDIDATES) {
      let ok = false;
      try { ok = MR.isTypeSupported(c) === true; } catch (_) { ok = false; }
      if (ok) return c;
    }
    return null;
  }

  function sanitizeActor(a, i) {
    const x0 = r3(clamp(a?.x0, 0, 1, 0.5)), y0 = r3(clamp(a?.y0, 0, 1, 0.85));
    return {
      id: String(a?.id ?? `a${i + 1}`).slice(0, 32),
      name: String(a?.name ?? '').slice(0, 24) || `Actor ${i + 1}`,
      pose: POSES.includes(a?.pose) ? a.pose : 'stand',
      x0, y0,
      x1: r3(clamp(a?.x1, 0, 1, x0)),
      y1: r3(clamp(a?.y1, 0, 1, y0)),
      scale: clamp(a?.scale, 0.3, 2, 1),
    };
  }

  function buildSnapshot(input) {
    if (!input || typeof input !== 'object') throw new ReelError('invalid', 'Reel input must be an object.');
    if (input.variant !== 'A' && input.variant !== 'B') throw new ReelError('invalid', 'Variant must be A or B.');
    if (!Array.isArray(input.scenes)) throw new ReelError('invalid', 'Scenes must be an array.');
    if (!input.scenes.length) throw new ReelError('invalid', 'No assigned scenes to record. Build a plan first.');
    if (input.scenes.length > LIMITS.maxScenes) throw new ReelError('invalid', `At most ${LIMITS.maxScenes} scenes per reel.`);
    let start = 0;
    const scenes = input.scenes.map((s, i) => {
      if (!s || typeof s !== 'object' || !s.shot || typeof s.shot !== 'object')
        throw new ReelError('invalid', `Scene ${i + 1} has no staging.`);
      if (typeof s.shot_id !== 'string' || !SAFE_ID.test(s.shot_id))
        throw new ReelError('invalid', `Scene ${i + 1} has no valid indexed frame id.`);
      const actors = (Array.isArray(s.shot.actors) ? s.shot.actors : []).slice(0, LIMITS.maxActors).map(sanitizeActor);
      const shot = {
        duration_sec: clamp(s.shot.duration_sec, LIMITS.minSceneSec, LIMITS.maxSceneSec, 5),
        dialogue: String(s.shot.dialogue ?? '').slice(0, 800),
        actors,
      };
      if (s.shot.origin === 'authored-sample') shot.origin = 'authored-sample';
      const out = { id: String(s.id ?? `s${i + 1}`).slice(0, 32), heading: String(s.heading ?? '').slice(0, 120),
        shot_id: s.shot_id, prov: String(s.prov ?? '').slice(0, 200), start, shot };
      start += shot.duration_sec;
      return out;
    });
    return deepFreeze({ variant: input.variant, created_at: new Date().toISOString(), total_sec: start, scenes });
  }

  function sceneAt(snapshot, t) {
    const scenes = snapshot.scenes, total = snapshot.total_sec;
    const tc = clamp(t, 0, total, 0);
    for (let i = 0; i < scenes.length; i++) {
      const s = scenes[i];
      if (tc < s.start + s.shot.duration_sec) return { index: i, scene: s, local: tc - s.start };
    }
    const last = scenes.length - 1;
    return { index: last, scene: scenes[last], local: scenes[last].shot.duration_sec };
  }

  function defaultDeps(d) {
    return Object.assign({
      createCanvas: (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; },
      MediaRecorder: typeof globalThis !== 'undefined' ? globalThis.MediaRecorder : undefined,
      now: () => performance.now(),
      requestFrame: (cb) => requestAnimationFrame(cb),
      cancelFrame: (id) => cancelAnimationFrame(id),
      isHidden: () => typeof document !== 'undefined' && document.visibilityState === 'hidden',
    }, d || {});
  }

  function recordReel(snapshot, opts) {
    return new Promise((resolve, reject) => {
      if (!snapshot || !Object.isFrozen(snapshot) || !Array.isArray(snapshot.scenes) || typeof snapshot.total_sec !== 'number')
        return reject(new ReelError('invalid', 'Snapshot must come from buildSnapshot.'));
      if (!opts || typeof opts.render !== 'function' || typeof opts.loadImage !== 'function')
        return reject(new ReelError('invalid', 'recordReel needs render and loadImage functions.'));
      const { render, loadImage, signal } = opts;
      const progress = (info) => { try { opts.onProgress && opts.onProgress(info); } catch (_) { /* UI errors never break recording */ } };
      if (signal && signal.aborted) return reject(new ReelError('cancelled', 'Reel recording cancelled.'));
      const deps = defaultDeps(opts.deps);
      const MR = deps.MediaRecorder;
      const mime = pickMimeType(MR);
      if (!mime) return reject(new ReelError('unsupported', 'This browser cannot record WebM; no reel was produced.'));

      const W = LIMITS.width, H = LIMITS.height;
      let canvas = null, stream = null, recorder = null, frameId = null, chunks = [], images = new Map();
      let settled = false, cleaned = false, abortWait = null;
      const onAbort = () => fail(new ReelError('cancelled', 'Reel recording cancelled.'));

      function cleanup() {
        if (cleaned) return;
        cleaned = true;
        if (frameId != null) { try { deps.cancelFrame(frameId); } catch (_) { /* ignore */ } frameId = null; }
        if (recorder) {
          recorder.ondataavailable = null;
          if (recorder.state !== 'inactive') { try { recorder.stop(); } catch (_) { /* ignore */ } }
          recorder.onstop = null; recorder.onerror = null;
        }
        if (stream && typeof stream.getTracks === 'function') stream.getTracks().forEach((tr) => { try { tr.stop(); } catch (_) { /* ignore */ } });
        if (signal) signal.removeEventListener('abort', onAbort);
        if (canvas) { canvas.width = 0; canvas.height = 0; }
        images.clear();
        canvas = stream = recorder = null;
      }
      function fail(err) {
        if (settled) return;
        settled = true; chunks = [];
        cleanup(); reject(err);
      }
      function succeed(value) {
        if (settled) return;
        settled = true; cleanup(); resolve(value);
      }

      if (signal) {
        signal.addEventListener('abort', onAbort);
        abortWait = new Promise((_, rej) => signal.addEventListener('abort', () => rej(new ReelError('cancelled', 'Reel recording cancelled.')), { once: true }));
        abortWait.catch(() => {});
      }

      try { canvas = deps.createCanvas(W, H); } catch (e) { return fail(new ReelError('unsupported', `Cannot create recording canvas: ${e.message}`)); }
      if (!canvas || typeof canvas.captureStream !== 'function')
        return fail(new ReelError('unsupported', 'This browser cannot capture a canvas stream; no reel was produced.'));

      (async () => {
        const ids = [...new Set(snapshot.scenes.map((s) => s.shot_id))];
        for (let i = 0; i < ids.length; i++) {
          if (settled) return;
          progress({ phase: 'loading', done: i, total: ids.length });
          const id = ids[i];
          let im = null;
          try {
            const p = Promise.resolve(loadImage(id, signal));
            im = await (abortWait ? Promise.race([p, abortWait]) : p);
          } catch (e) {
            if (e instanceof ReelError && e.code === 'cancelled') return fail(e);
            if (signal && signal.aborted) return fail(new ReelError('cancelled', 'Reel recording cancelled.'));
            im = null;
          }
          if (settled) return;
          if (signal && signal.aborted) return fail(new ReelError('cancelled', 'Reel recording cancelled.'));
          if (!im || !(im.width || im.naturalWidth)) {
            const nums = snapshot.scenes.map((s, k) => (s.shot_id === id ? k + 1 : 0)).filter(Boolean);
            const label = nums.length > 1 ? `scenes ${nums.join(', ')}` : `scene ${nums[0]}`;
            return fail(new ReelError('image', `Indexed image unavailable for ${label} (shot ${id}); no reel was produced.`));
          }
          images.set(id, im);
        }
        progress({ phase: 'loading', done: ids.length, total: ids.length });

        const ctx = canvas.getContext('2d');
        try {
          stream = canvas.captureStream(LIMITS.fps);
          recorder = new MR(stream, { mimeType: mime, videoBitsPerSecond: 5000000 });
        } catch (e) { return fail(new ReelError('recorder', `Recorder could not start: ${e.message}`)); }
        recorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunks.push(e.data); };
        recorder.onerror = (e) => fail(new ReelError('recorder', `Recorder error: ${(e && e.error && e.error.message) || 'unknown'}`));
        try { recorder.start(250); } catch (e) { return fail(new ReelError('recorder', `Recorder could not start: ${e.message}`)); }

        const total = snapshot.total_sec;
        let t0 = null, held = false;
        const tick = () => {
          frameId = null;
          if (settled) return;
          if (signal && signal.aborted) return fail(new ReelError('cancelled', 'Reel recording cancelled.'));
          if (deps.isHidden()) return fail(new ReelError('hidden', 'Tab was hidden during recording; reel discarded. Keep the tab visible.'));
          const now = deps.now();
          if (t0 == null) t0 = now;
          const t = Math.min((now - t0) / 1000, total);
          const { index, scene, local } = sceneAt(snapshot, t);
          try {
            render(ctx, W, H, { imgEl: images.get(scene.shot_id), missing: null, prov: scene.prov, shot: scene.shot, t: local, editing: false, sel: -1 });
          } catch (e) { return fail(new ReelError('recorder', `Frame render failed: ${e.message}`)); }
          progress({ phase: 'recording', t, total, scene: index + 1 });
          // Hold the final frame for one extra animation frame so captureStream emits it before stop().
          if (t >= total) { if (held) return finalize(); held = true; }
          frameId = deps.requestFrame(tick);
        };
        const finalize = () => {
          progress({ phase: 'finalizing' });
          const rec = recorder;
          rec.onstop = () => {
            if (settled) return;
            const blob = new Blob(chunks, { type: mime.split(';')[0] });
            if (!blob.size) return fail(new ReelError('empty', 'Recorder produced no video data; no reel was produced.'));
            succeed({ blob, mimeType: mime, duration_sec: total, scenes: snapshot.scenes.length, bytes: blob.size });
          };
          try { rec.stop(); } catch (e) { fail(new ReelError('recorder', `Recorder could not stop: ${e.message}`)); }
        };
        frameId = deps.requestFrame(tick);
      })().catch((e) => fail(e instanceof ReelError ? e : new ReelError('recorder', String(e && e.message || e))));
    });
  }

  return Object.freeze({ LIMITS, MIME_CANDIDATES, ReelError, pickMimeType, buildSnapshot, sceneAt, recordReel });
});
