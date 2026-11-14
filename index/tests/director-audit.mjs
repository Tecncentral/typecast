/**
 * Headless lifecycle and export audit for index/director.js (commit under test).
 *
 * director.js is a classic browser script: it touches document, canvas, fetch,
 * and Image at load time and does not export its functions. This file loads the
 * unmodified source in a vm context with a hand-rolled DOM. The footer appended
 * inside that same script only publishes closures for assertions; it is not a
 * change to the repo file.
 *
 * Not exercised here (no browser, no mic hardware, no rasterizer): real canvas
 * pixels and JPEG OCR, the browser's own HTML serializer, layout-accurate
 * pointer hit testing, and a real SpeechRecognition permission prompt. Export
 * escaping is checked by recording the textContent / outerHTML path the script
 * actually uses and serializing it with the HTML text/attribute rules.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = dirname(fileURLToPath(import.meta.url));
const DIRECTOR_JS = readFileSync(join(DIR, '..', 'director.js'), 'utf8');
const DIRECTOR_HTML = readFileSync(join(DIR, '..', 'director.html'), 'utf8');
const FOOTER = `
globalThis.__director = {
  S, frameAt, shotData, sanitizeShot, exportSnapshot, provText, drawStage,
  selectScene, setVariant, BADGE, safeId,
};
`;

const XSS = '<img src=x onerror=alert(1)>';
const SCRIPT_CLOSE = '</script>';
const JS_URL = 'javascript:alert(1)';
const TRAVERSAL = '../../etc/passwd';

function escapeText(value) {
  return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function escapeAttr(value) {
  return escapeText(value).replace(/"/g, '&quot;');
}

function createEnv({ speech = 'none' } = {}) {
  const env = {
    jobs: [],
    downloads: [],
    blobs: new Map(),
    drawLog: [],
    honorAbort: true,
    nowMs: 0,
    rafs: new Map(),
    rafSeq: 0,
    blobSeq: 0,
    speechMode: speech,
  };

  class TextNode {
    constructor(data) {
      this.nodeType = 3;
      this.data = String(data);
      this.parentNode = null;
      this.childNodes = [];
    }
    get textContent() { return this.data; }
    set textContent(value) { this.data = String(value); }
  }

  class Fragment {
    constructor() {
      this.nodeType = 11;
      this.childNodes = [];
      this.parentNode = null;
    }
    append(...kids) { for (const kid of kids) appendChild(this, kid); }
    get textContent() { return this.childNodes.map((child) => child.textContent).join(''); }
  }

  class ClassList {
    constructor(el) { this.el = el; }
    _names() { return new Set(this.el.className.split(/\s+/).filter(Boolean)); }
    contains(name) { return this._names().has(name); }
    toggle(name, force) {
      const names = this._names();
      const next = force === undefined ? !names.has(name) : !!force;
      if (next) names.add(name); else names.delete(name);
      this.el.className = [...names].join(' ');
      return next;
    }
  }

  class Element {
    constructor(tag, doc) {
      this.nodeType = 1;
      this.tagName = String(tag).toUpperCase();
      this.doc = doc;
      this.attrs = {};
      this.childNodes = [];
      this.parentNode = null;
      this.className = '';
      this.classList = new ClassList(this);
      this.listeners = {};
      this.hidden = false;
      this.disabled = false;
      this.checked = false;
      this.value = '';
      this.href = '';
      this.src = '';
      this.alt = '';
      this.id = '';
      this.width = 300;
      this.height = 150;
      this._capture = null;
    }
    setAttribute(name, value) {
      const key = String(name);
      const text = String(value);
      this.attrs[key] = text;
      if (key === 'id') this.id = text;
      if (key === 'class') this.className = text;
      if (key === 'href') this.href = text;
      if (key === 'src') this.src = text;
      if (key === 'alt') this.alt = text;
      if (key === 'hidden') this.hidden = true;
    }
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null; }
    append(...kids) { for (const kid of kids) appendChild(this, kid); }
    prepend(...kids) {
      const nodes = [];
      for (const kid of kids) nodes.push(...flatten(kid));
      for (const node of nodes) {
        if (node.parentNode) node.remove();
        node.parentNode = this;
      }
      this.childNodes = [...nodes, ...this.childNodes];
    }
    replaceChildren(...kids) {
      for (const child of this.childNodes) child.parentNode = null;
      this.childNodes = [];
      this.append(...kids);
    }
    remove() {
      const parent = this.parentNode;
      if (!parent) return;
      const index = parent.childNodes.indexOf(this);
      if (index >= 0) parent.childNodes.splice(index, 1);
      this.parentNode = null;
    }
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
    dispatchEvent(init = {}) {
      const event = {
        type: init.type,
        target: this,
        currentTarget: this,
        clientX: init.clientX ?? 0,
        clientY: init.clientY ?? 0,
        pointerId: init.pointerId ?? 1,
        key: init.key,
        shiftKey: !!init.shiftKey,
        altKey: !!init.altKey,
        defaultPrevented: false,
        preventDefault() { this.defaultPrevented = true; },
      };
      for (const fn of [...(this.listeners[init.type] || [])]) fn(event);
      return event;
    }
    click() {
      this.dispatchEvent({ type: 'click' });
      if (this.tagName === 'A' && this.attrs.download != null) {
        env.downloads.push({
          name: this.attrs.download,
          href: this.attrs.href || this.href,
          blob: env.blobs.get(this.attrs.href || this.href) || null,
        });
      }
    }
    get dataset() {
      const el = this;
      return new Proxy({}, {
        get(_target, key) {
          const attr = `data-${String(key).replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`;
          return el.attrs[attr];
        },
      });
    }
    get options() { return this.childNodes.filter((child) => child.tagName === 'OPTION'); }
    get textContent() { return this.childNodes.map((child) => child.textContent).join(''); }
    set textContent(value) {
      this.childNodes = [];
      if (value != null && value !== '') appendChild(this, new TextNode(value));
    }
    querySelector(selector) { return walk(this, (el) => matches(el, selector))[0] ?? null; }
    querySelectorAll(selector) { return walk(this, (el) => matches(el, selector)); }
    getContext() { return makeCtx(env.drawLog); }
    toDataURL() { return 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2w=='; }
    toBlob(callback, type) {
      queueMicrotask(() => callback(new env.context.Blob(['png'], { type: type || 'image/png' })));
    }
    getBoundingClientRect() {
      return { left: 0, top: 0, width: this.width || 1280, height: this.height || 720, right: this.width || 1280, bottom: this.height || 720 };
    }
    setPointerCapture(id) { this._capture = id; }
    hasPointerCapture(id) { return this._capture === id; }
    releasePointerCapture(id) { if (this._capture === id) this._capture = null; }
    get outerHTML() { return serialize(this); }
  }

  function flatten(kid) {
    if (kid == null || kid === false) return [];
    if (typeof kid === 'string' || typeof kid === 'number') return [new TextNode(kid)];
    if (kid.nodeType === 11) {
      const kids = kid.childNodes.splice(0);
      for (const child of kids) child.parentNode = null;
      return kids;
    }
    return [kid];
  }
  function appendChild(parent, kid) {
    for (const node of flatten(kid)) {
      if (node.parentNode) node.remove();
      node.parentNode = parent;
      parent.childNodes.push(node);
    }
  }
  function matches(el, selector) {
    return selector.split(',').some((part) => {
      const token = part.trim();
      if (token.startsWith('.')) return el.className.split(/\s+/).includes(token.slice(1));
      return el.tagName === token.toUpperCase();
    });
  }
  function walk(el, pred, out = []) {
    for (const child of el.childNodes) {
      if (child.nodeType !== 1) continue;
      if (pred(child)) out.push(child);
      walk(child, pred, out);
    }
    return out;
  }
  function serialize(el) {
    const tag = el.tagName.toLowerCase();
    const attrs = [];
    const seen = new Set();
    const push = (name, value) => {
      if (value == null || value === '' || seen.has(name)) return;
      seen.add(name);
      attrs.push(`${name}="${escapeAttr(value)}"`);
    };
    push('id', el.id);
    push('class', el.className);
    if (el.tagName === 'IMG' || el.tagName === 'A') {
      push('href', el.href);
      push('src', el.src);
      push('alt', el.alt);
    }
    for (const [name, value] of Object.entries(el.attrs)) push(name, value);
    const inner = el.childNodes.map((child) => (child.nodeType === 3 ? escapeText(child.data) : serialize(child))).join('');
    if (tag === 'meta' || tag === 'img' || tag === 'input' || tag === 'br') {
      return `<${tag}${attrs.length ? ` ${attrs.join(' ')}` : ''}>`;
    }
    return `<${tag}${attrs.length ? ` ${attrs.join(' ')}` : ''}>${inner}</${tag}>`;
  }
  function makeCtx(log) {
    const store = {};
    return new Proxy(store, {
      get(target, prop) {
        if (prop === 'measureText') return (text) => ({ width: String(text).length * 8 });
        if (typeof prop === 'symbol') return target[prop];
        if (prop in target && typeof target[prop] !== 'function') return target[prop];
        return (...args) => { log.push({ m: String(prop), args }); };
      },
      set(target, prop, value) {
        target[prop] = value;
        log.push({ m: 'set', prop: String(prop), value });
        return true;
      },
    });
  }

  class Document {
    constructor() {
      this.ids = {};
      this.implementation = { createHTMLDocument: (title) => createHTMLDocument(title) };
    }
    createElement(tag) {
      return String(tag).toLowerCase() === 'canvas' ? new Element('canvas', this) : new Element(tag, this);
    }
    createDocumentFragment() { return new Fragment(); }
    getElementById(id) { return this.ids[id] || null; }
    importNode(node, deep) { return cloneInto(this, node, deep); }
    get body() { return this.ids.__body; }
    get head() { return this.ids.__head; }
    get documentElement() { return this.ids.__root; }
  }

  function cloneInto(doc, node, deep) {
    if (node.nodeType === 3) return new TextNode(node.data);
    if (node.nodeType === 11) {
      const fragment = new Fragment();
      if (deep) for (const child of [...node.childNodes]) fragment.append(cloneInto(doc, child, true));
      return fragment;
    }
    const copy = doc.createElement(node.tagName.toLowerCase());
    copy.className = node.className;
    copy.src = node.src;
    copy.alt = node.alt;
    copy.href = node.href;
    for (const [name, value] of Object.entries(node.attrs)) copy.setAttribute(name, value);
    if (deep) for (const child of [...node.childNodes]) copy.append(cloneInto(doc, child, true));
    return copy;
  }

  function createHTMLDocument(title) {
    const doc = new Document();
    const root = new Element('html', doc);
    const head = new Element('head', doc);
    const body = new Element('body', doc);
    const titleEl = new Element('title', doc);
    titleEl.textContent = title || '';
    head.append(titleEl);
    root.append(head, body);
    doc.ids.__root = root;
    doc.ids.__head = head;
    doc.ids.__body = body;
    return doc;
  }

  const document = new Document();
  const html = new Element('html', document);
  const head = new Element('head', document);
  const body = new Element('body', document);
  html.append(head, body);
  document.ids.__root = html;
  document.ids.__head = head;
  document.ids.__body = body;

  const tags = {
    status: 'p', script: 'textarea', build: 'button', demo: 'button', reject: 'button',
    planSel: 'select', maxLoc: 'select', reqAvail: 'input', trucks: 'input', cars: 'input',
    planMeta: 'p', forbidden: 'p', clearRej: 'button', rail: 'ol', framePicker: 'div',
    frameNotice: 'div', stage: 'canvas', play: 'button', pause: 'button', reset: 'button',
    prog: 'progress', clock: 'span', timeline: 'ol', varLbl: 'span', varA: 'button', varB: 'button',
    shotForm: 'fieldset', dur: 'input', dlg: 'textarea', actorSel: 'select', addActor: 'button',
    delActor: 'button', actorForm: 'fieldset', aName: 'input', aPose: 'select', aScale: 'input',
    ax0: 'input', ay0: 'input', ax1: 'input', ay1: 'input', micNote: 'p', micStart: 'button',
    micStop: 'button', instr: 'textarea', gen: 'button', undo: 'button', proposal: 'div',
    pSum: 'p', pNote: 'p', pDiff: 'ul', applyB: 'button', discard: 'button', evidence: 'div',
    planner: 'a', expPng: 'button', expJson: 'button', expPack: 'button',
  };
  for (const [id, tag] of Object.entries(tags)) {
    const el = new Element(tag, document);
    el.id = id;
    document.ids[id] = el;
    body.append(el);
  }
  document.getElementById('maxLoc').value = '3';
  document.getElementById('trucks').value = '0';
  document.getElementById('cars').value = '0';
  document.getElementById('stage').width = 1280;
  document.getElementById('stage').height = 720;
  document.getElementById('prog').value = 0;
  document.getElementById('micStop').disabled = true;
  document.getElementById('proposal').hidden = true;
  document.getElementById('frameNotice').hidden = true;
  document.getElementById('planner').hidden = true;
  document.getElementById('expPack').disabled = true;
  document.getElementById('micNote').textContent = 'Mic is off by default. If you start it, your browser\'s speech service may process the audio.';
  for (const pose of ['stand', 'sit', 'walk']) {
    const option = new Element('option', document);
    option.setAttribute('value', pose);
    option.textContent = pose;
    document.getElementById('aPose').append(option);
  }

  class FakeRecognition {
    constructor() {
      this.lang = '';
      this.interimResults = false;
      this.continuous = false;
      this.onresult = null;
      this.onerror = null;
      this.onend = null;
    }
    start() {
      if (env.speechMode === 'throw') throw new Error('Permission denied');
      if (env.speechMode === 'deny') {
        queueMicrotask(() => {
          this.onerror?.({ error: 'not-allowed' });
          this.onend?.();
        });
      }
    }
    stop() { this.onend?.(); }
  }
  class FakeImage {
    constructor() {
      this.onload = null;
      this.onerror = null;
      this.naturalWidth = 0;
      this.naturalHeight = 0;
      this.width = 0;
      this.height = 0;
      this._src = '';
    }
    set src(value) {
      this._src = String(value);
      const ok = this._src.startsWith('data:image/') || this._src.startsWith('/image/');
      queueMicrotask(() => {
        if (ok) {
          this.naturalWidth = 640;
          this.naturalHeight = 360;
          this.width = 640;
          this.height = 360;
          this.onload?.();
        } else this.onerror?.();
      });
    }
    get src() { return this._src; }
  }
  class FakeFileReader {
    constructor() { this.onload = null; this.onerror = null; this.result = null; }
    readAsDataURL() {
      this.result = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
      queueMicrotask(() => this.onload?.());
    }
  }

  const sandbox = {
    console,
    queueMicrotask,
    setTimeout,
    clearTimeout,
    AbortController,
    Blob,
    Date,
    Math,
    JSON,
    Number,
    Object,
    Array,
    String,
    Error,
    Promise,
    document,
    Image: FakeImage,
    FileReader: FakeFileReader,
    performance: { now: () => env.nowMs },
    requestAnimationFrame: (cb) => {
      const id = ++env.rafSeq;
      env.rafs.set(id, cb);
      return id;
    },
    cancelAnimationFrame: (id) => { env.rafs.delete(id); },
    addEventListener() {},
  };
  sandbox.window = sandbox;
  if (speech !== 'none') sandbox.SpeechRecognition = FakeRecognition;
  const context = vm.createContext(sandbox);
  context.URL = class extends URL {
    static createObjectURL(blob) {
      const url = `blob:audit/${++env.blobSeq}`;
      env.blobs.set(url, blob);
      return url;
    }
    static revokeObjectURL(url) { env.blobs.delete(url); }
  };
  context.fetch = (url, opts = {}) => new Promise((resolve, reject) => {
    let settled = false;
    const finish = (fn) => { if (!settled) { settled = true; fn(); } };
    const signal = opts.signal;
    if (env.honorAbort && signal) {
      const abort = () => finish(() => reject(Object.assign(new Error('The operation was aborted'), { name: 'AbortError' })));
      if (signal.aborted) { abort(); return; }
      signal.addEventListener('abort', abort, { once: true });
    }
    const target = String(url);
    if (target.startsWith('/image/')) {
      const blob = new Blob([Uint8Array.of(137, 80, 78, 71)], { type: 'image/png' });
      finish(() => resolve({ ok: true, status: 200, json: async () => ({}), blob: async () => blob }));
      return;
    }
    env.jobs.push({
      url: target,
      opts,
      resolve: (value) => finish(() => resolve(value)),
      reject: (error) => finish(() => reject(error)),
    });
  });
  env.context = context;
  env.document = document;
  env.$ = (id) => document.getElementById(id);
  env.take = (part) => {
    const index = env.jobs.findIndex((job) => job.url.includes(part));
    if (index < 0) throw new Error(`no pending ${part}; saw ${env.jobs.map((job) => job.url).join(', ') || 'nothing'}`);
    return env.jobs.splice(index, 1)[0];
  };
  env.flushRaf = () => {
    const queued = [...env.rafs.entries()];
    env.rafs.clear();
    for (const [, cb] of queued) cb(env.nowMs);
  };
  return env;
}

function jsonResponse(data, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => data, blob: async () => new Blob() };
}
async function drain() {
  for (let i = 0; i < 50; i += 1) await Promise.resolve();
}
function boot(options) {
  const env = createEnv(options);
  vm.runInContext(`${DIRECTOR_JS}\n${FOOTER}`, env.context, { filename: 'director.js' });
  env.api = env.context.__director;
  return env;
}
function candidate(propertyId, shotId, extra = {}) {
  return {
    eligible: extra.eligible !== false,
    shot: {
      shot_id: shotId, property_id: propertyId, model_id: `model-${propertyId}`, sweep_id: `sweep-${propertyId}`,
      heading_deg: 15, score: 0.42, measure_on_site: true,
      room_area_m2: null, ceiling_m: null, depth_m: null,
      image_path: '/Users/demo/cache/views/licensed.jpg',
      ...(extra.shot || {}),
    },
    property: {
      available: null, availability_status: 'unknown', year_built: 1978, size_sqft: 8000,
      address: '100 Example St (FAKE)', contact: 'listing contact (FAKE)', api_key: 'sk-live-SECRETVALUE',
      lat: 34.05, lon: -118.25,
      ...(extra.property || {}),
    },
    logistics: {
      parking_status: 'unknown', walk_status: 'unknown', noise_status: 'unknown',
      truck_spaces: null, car_spaces: null, enough_parking: null, estimated: true, walk_m: null, parking_area_m2: null,
      aerial_image_path: '/cache/private/aerial.png', parking_polygon: [[34.05, -118.25]],
      source_notes: ['raw licensed logistics row'],
      ...(extra.logistics || {}),
    },
    warnings: extra.warnings || [{ source: 'vexcel', field: 'parking_capacity', status: 'unknown', message: 'secret warning /cache/private/note' }],
  };
}
function planFor(body, assignments, extra = {}) {
  const byScene = new Map(assignments.map((row) => [row.scene_id, row]));
  return {
    mode: extra.mode || 'mock',
    scenes: body.scenes.map((scene) => ({
      id: scene.id, heading: scene.heading, description: scene.description,
      candidates: (extra.candidates || assignments).filter((row) => !extra.onlyAssigned || row.scene_id === scene.id).reduce((list, row) => {
        if (!list.some((item) => item.shot.shot_id === row.shot_id && item.shot.property_id === row.property_id)) {
          list.push(candidate(row.property_id, row.shot_id, extra.evidence || {}));
        }
        return list;
      }, extra.perScene ? extra.perScene(scene) : []),
    })),
    plans: [{
      assignments: body.scenes.map((scene) => byScene.get(scene.id)).filter(Boolean),
      uncovered_scene_ids: extra.uncovered || [],
      company_moves: 1,
      mean_similarity: 0.37,
      locations: [...new Set(assignments.map((row) => row.property_id))],
    }],
    evaluated_subsets: extra.evaluated_subsets ?? 4,
    pool_properties: [...new Set(assignments.map((row) => row.property_id))],
    trace: extra.trace ?? { steps: [{ text: 'RESPONSE_STEP_ONLY_zz' }] },
    events: extra.events ?? [{ type: 'plan', agent: 'solver', text: 'RESPONSE_EVENT_ONLY_zz' }],
  };
}
function assignment(sceneId, propertyId, shotId) {
  return { scene_id: sceneId, property_id: propertyId, shot_id: shotId, score: 0.5 };
}
async function buildScript(env, script, assignments, extra) {
  env.$('script').value = script;
  env.$('build').click();
  const job = env.take('/api/production/plan');
  const body = JSON.parse(job.opts.body);
  const rows = typeof assignments === 'function' ? assignments(body) : assignments;
  job.resolve(jsonResponse(planFor(body, rows, extra)));
  await drain();
  return body;
}
function fieldMap(root) {
  const map = {};
  for (const dt of root.querySelectorAll('dt')) {
    const siblings = dt.parentNode.childNodes.filter((node) => node.nodeType === 1);
    const dd = siblings[siblings.indexOf(dt) + 1];
    map[dt.textContent] = dd ? dd.textContent : '';
  }
  return map;
}
function blobText(blob) {
  if (!blob) throw new Error('missing download blob');
  return blob.text();
}
// vm object literals and host structuredClone values share no prototype, so
// deepEqual reports them as not reference-equal even when the data matches.
function copied(value) {
  return JSON.parse(JSON.stringify(value));
}
function lineXs(log) {
  return log.filter((entry) => entry.m === 'lineTo').map((entry) => entry.args[0]);
}
function poseX(log) {
  const xs = lineXs(log).slice(0, 3).sort((a, b) => a - b);
  return xs[1];
}

test('harness escapes textContent using HTML text rules', () => {
  const env = createEnv();
  const doc = env.document.implementation.createHTMLDocument('t');
  const paragraph = doc.createElement('p');
  paragraph.textContent = `${XSS}${SCRIPT_CLOSE}`;
  const image = doc.createElement('img');
  image.src = 'data:image/png;base64,qq==';
  image.alt = XSS;
  doc.body.append(paragraph, image);
  const html = doc.documentElement.outerHTML;
  assert.equal(html.includes(XSS), false);
  assert.equal(html.includes(SCRIPT_CLOSE), false);
  assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;&lt;/script&gt;'));
  assert.ok(html.includes('alt="&lt;img src=x onerror=alert(1)&gt;"'));
});

test('a late brainstorm response does not land on the scene the user switched to', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first scene\nINT. OFFICE | second scene', [
    assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b'),
  ]);
  env.honorAbort = false;
  env.api.selectScene('s1');
  env.$('instr').value = 'Move the actor toward the window';
  env.$('gen').click();
  const job = env.take('/api/production/brainstorm');
  const sent = JSON.parse(job.opts.body);
  assert.equal(sent.heading, 'INT. KITCHEN');
  sent.shot.dialogue = 'MUTATED_REQUEST_BODY';
  assert.equal(env.api.shotData('s1').dialogue, '');

  env.api.selectScene('s2');
  job.resolve(jsonResponse({
    summary: 'late', creative_note: 'stale',
    shot: { duration_sec: 9, dialogue: 'STALE_POISON', actors: [{ id: 'z', name: 'Zoe', pose: 'walk', x0: 0.1, y0: 0.1, x1: 0.2, y1: 0.2, scale: 1 }] },
  }));
  await drain();
  assert.equal(JSON.stringify(env.api.S.edits).includes('STALE_POISON'), false);
  assert.equal(env.api.S.pending, null);
  assert.equal(env.$('proposal').hidden, true);
  assert.equal(env.api.S.sceneId, 's2');
});

test('aborting a brainstorm by switching scenes applies nothing', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first\nINT. OFFICE | second', [
    assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b'),
  ]);
  env.$('instr').value = 'Try a seated reading';
  env.$('gen').click();
  env.take('/api/production/brainstorm');
  env.api.selectScene('s2');
  await drain();
  assert.equal(env.api.S.pending, null);
  assert.equal(JSON.stringify(env.api.S.edits).includes('STALE_POISON'), false);
});

test('double Apply writes variant B once and leaves A alone', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')]);
  env.api.setVariant('B');
  env.$('dlg').value = 'before';
  env.$('dlg').dispatchEvent({ type: 'input' });
  env.$('instr').value = 'Give her the line';
  env.$('gen').click();
  env.take('/api/production/brainstorm').resolve(jsonResponse({
    summary: 'one change', creative_note: 'review',
    shot: { duration_sec: 7, dialogue: 'AFTER', actors: [{ id: 'a1', name: 'Bea', pose: 'sit', x0: 0.2, y0: 0.3, x1: 0.4, y1: 0.5, scale: 1 }] },
  }));
  await drain();
  const variantA = structuredClone(env.api.shotData('s1', 'A'));
  env.$('applyB').click();
  const once = structuredClone(env.api.shotData('s1', 'B'));
  env.$('applyB').click();
  assert.equal(once.dialogue, 'AFTER');
  assert.equal(once.duration_sec, 7);
  assert.deepEqual(copied(env.api.shotData('s1', 'B')), copied(once));
  assert.deepEqual(copied(env.api.shotData('s1', 'A')), copied(variantA));
  assert.equal(env.api.S.pending, null);
});

test('Discard then Apply leaves both variants unchanged', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')]);
  env.api.setVariant('B');
  env.$('dlg').value = 'keep-b';
  env.$('dlg').dispatchEvent({ type: 'input' });
  env.api.setVariant('A');
  env.$('dlg').value = 'keep-a';
  env.$('dlg').dispatchEvent({ type: 'input' });
  const before = structuredClone(env.api.S.edits);
  env.$('instr').value = 'Replace the line';
  env.$('gen').click();
  env.take('/api/production/brainstorm').resolve(jsonResponse({
    summary: 'discard me', creative_note: 'no',
    shot: { duration_sec: 8, dialogue: 'SHOULD_NOT_APPLY', actors: [] },
  }));
  await drain();
  assert.equal(env.$('proposal').hidden, false);
  env.$('discard').click();
  env.$('applyB').click();
  assert.deepEqual(copied(env.api.S.edits), copied(before));
  assert.equal(env.api.S.pending, null);
});

test('variant B edits do not change variant A in state or export', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first\nINT. OFFICE | second', [
    assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b'),
  ]);
  env.api.selectScene('s1');
  env.api.setVariant('A');
  env.$('addActor').click();
  env.$('aName').value = 'Ann';
  env.$('aName').dispatchEvent({ type: 'input' });
  env.$('dlg').value = 'Line A';
  env.$('dlg').dispatchEvent({ type: 'input' });
  env.$('dur').value = '8';
  env.$('dur').dispatchEvent({ type: 'change' });
  env.$('ax0').value = '0.20';
  env.$('ax0').dispatchEvent({ type: 'input' });
  env.$('ay0').value = '0.80';
  env.$('ay0').dispatchEvent({ type: 'input' });
  env.$('ax1').value = '0.40';
  env.$('ax1').dispatchEvent({ type: 'input' });
  env.$('ay1').value = '0.70';
  env.$('ay1').dispatchEvent({ type: 'input' });
  const variantA = structuredClone(env.api.shotData('s1', 'A'));

  env.api.setVariant('B');
  env.$('addActor').click();
  env.$('aName').value = 'Bea';
  env.$('aName').dispatchEvent({ type: 'input' });
  env.$('dlg').value = 'Line B';
  env.$('dlg').dispatchEvent({ type: 'input' });
  env.$('dur').value = '3';
  env.$('dur').dispatchEvent({ type: 'change' });
  env.$('ax0').value = '0.70';
  env.$('ax0').dispatchEvent({ type: 'input' });
  env.$('ay0').value = '0.20';
  env.$('ay0').dispatchEvent({ type: 'input' });
  env.$('ax1').value = '0.90';
  env.$('ax1').dispatchEvent({ type: 'input' });
  env.$('ay1').value = '0.30';
  env.$('ay1').dispatchEvent({ type: 'input' });
  env.$('aPose').value = 'walk';
  env.$('aPose').dispatchEvent({ type: 'change' });

  assert.deepEqual(copied(env.api.shotData('s1', 'A')), copied(variantA));
  assert.equal(env.api.shotData('s1', 'B').dialogue, 'Line B');
  assert.equal(env.api.shotData('s1', 'B').actors[0].x0, 0.7);
  assert.notEqual(env.api.shotData('s1', 'A').actors[0], env.api.shotData('s1', 'B').actors[0]);

  env.nowMs = 0;
  env.$('play').click();
  env.nowMs = 500;
  env.flushRaf();
  env.$('pause').click();
  assert.deepEqual(copied(env.api.shotData('s1', 'A')), copied(variantA));
  assert.equal(env.api.shotData('s1', 'B').actors[0].name, 'Bea');

  const snap = env.api.exportSnapshot();
  const scene = snap.scenes.find((row) => row.id === 's1');
  assert.equal(scene.variants.A.dialogue, 'Line A');
  assert.equal(scene.variants.A.duration_sec, 8);
  assert.equal(scene.variants.A.actors[0].name, 'Ann');
  assert.equal(scene.variants.A.actors[0].x0, 0.2);
  assert.equal(scene.variants.B.dialogue, 'Line B');
  assert.equal(scene.variants.B.duration_sec, 3);
  assert.equal(scene.variants.B.actors[0].x0, 0.7);
  assert.equal(scene.variants.B.actors[0].pose, 'walk');
  scene.variants.B.actors[0].x0 = 0.01;
  scene.variants.B.dialogue = 'mutated export';
  scene.variants.A.actors[0].name = 'Changed';
  assert.equal(env.api.shotData('s1', 'B').actors[0].x0, 0.7);
  assert.equal(env.api.shotData('s1', 'B').dialogue, 'Line B');
  assert.equal(env.api.shotData('s1', 'A').actors[0].name, 'Ann');

  env.$('expJson').click();
  const downloaded = JSON.parse(await blobText(env.downloads.at(-1).blob));
  const exported = downloaded.scenes.find((row) => row.id === 's1');
  assert.equal(exported.variants.A.dialogue, 'Line A');
  assert.equal(exported.variants.B.actors[0].name, 'Bea');
  assert.equal(env.downloads.at(-1).name, 'typecast-project.json');
});

test('reject and replan keeps edits on other scenes and drops the rejected location', async () => {
  const env = boot();
  const first = [
    assignment('s1', 'prop_a', 'shot_a'),
    assignment('s2', 'prop_b', 'shot_b'),
  ];
  await buildScript(env, 'INT. KITCHEN | first\nINT. OFFICE | second', first);
  env.api.selectScene('s2');
  env.$('addActor').click();
  env.$('dlg').value = 'KEEP_SCENE_TWO';
  env.$('dlg').dispatchEvent({ type: 'input' });
  env.$('dur').value = '12';
  env.$('dur').dispatchEvent({ type: 'change' });
  env.$('ax0').value = '0.15';
  env.$('ax0').dispatchEvent({ type: 'input' });
  const kept = structuredClone(env.api.shotData('s2'));
  env.api.selectScene('s1');
  env.$('reject').click();
  const job = env.take('/api/production/plan');
  const body = JSON.parse(job.opts.body);
  assert.deepEqual(body.forbidden_property_ids, ['prop_a']);
  assert.equal(body.scenes[1].heading, 'INT. OFFICE');
  job.resolve(jsonResponse(planFor(body, [
    assignment('s1', 'prop_c', 'shot_c'),
    assignment('s2', 'prop_b', 'shot_b'),
  ])));
  await drain();
  assert.deepEqual(copied(env.api.shotData('s2')), copied(kept));
  const rail = env.$('rail').textContent;
  assert.equal(rail.includes('prop_a'), false);
  assert.equal(rail.includes('shot_a'), false);
  assert.match(env.$('forbidden').textContent, /prop_a/);
  const picker = env.$('framePicker').querySelector('select');
  const choices = [...(picker?.options || [])].map((option) => option.getAttribute('value'));
  assert.equal(choices.includes('shot_a'), false);
});

test('a replanned response that still assigns the rejected property is not shown', { todo: 'BUG: director.js renders plan assignments as returned and never drops a property id already in S.forbidden, so a rejected location reappears if the replan response still names it.' }, async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first\nINT. OFFICE | second', [
    assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b'),
  ]);
  env.$('reject').click();
  const job = env.take('/api/production/plan');
  const body = JSON.parse(job.opts.body);
  job.resolve(jsonResponse(planFor(body, [
    assignment('s1', 'prop_a', 'shot_a'),
    assignment('s2', 'prop_b', 'shot_b'),
  ])));
  await drain();
  assert.equal(env.$('rail').textContent.includes('prop_a'), false);
  assert.equal(env.api.S.resp.plans[0].assignments.some((row) => row.property_id === 'prop_a'), false);
});

test('explicit unknown parking and availability render as unknown', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')]);
  const map = fieldMap(env.$('evidence'));
  assert.equal(map.availability_status, 'unknown');
  assert.equal(map.parking_status, 'unknown');
  assert.equal(map.available, 'unknown');
  assert.equal(map.enough_parking, 'unknown');
  assert.equal(map.truck_spaces, 'unknown');
  assert.equal(map.car_spaces, 'unknown');
  const text = env.$('evidence').textContent;
  assert.match(text, /not a parking approval/);
  assert.doesNotMatch(text, /\bpass\b/i);
  assert.equal(text.includes('FAKE'), false);
  assert.equal(text.includes('sk-live-SECRETVALUE'), false);
  assert.equal(text.includes('/cache/private'), false);
  assert.equal(text.includes('/Users/demo'), false);
  assert.equal(text.includes('34.05'), false);
});

test('mock-shaped unknown availability and parking are not displayed as pass or available', { todo: 'BUG: evidenceSummary copies available/enough_parking booleans and truck, car, and walk counts even when availability_status or parking_status is missing or unrecognized, and warning statuses such as "pass" are printed verbatim. Mock fixtures have available:true with no availability_status and parking counts with no parking_status, so the panel shows a pass next to "unknown".' }, async () => {
  // mocks/property.json has available:true and no availability_status.
  // mocks/logistics.json has truck/car counts and no parking_status. The plan
  // route then sets enough_parking because null status is not the string "unknown".
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')], {
    evidence: {
      property: { available: true, availability_status: null },
      logistics: {
        parking_status: null, walk_status: null, noise_status: null,
        truck_spaces: 4, car_spaces: 45, enough_parking: true, walk_m: 40, estimated: true,
      },
      warnings: [{ source: 'vexcel', field: 'parking_capacity', status: 'pass', message: 'certified' }],
    },
  });
  const map = fieldMap(env.$('evidence'));
  assert.equal(map.availability_status, 'unknown');
  assert.equal(map.parking_status, 'unknown');
  assert.notEqual(map.available, 'true');
  assert.notEqual(map.enough_parking, 'true');
  assert.notEqual(map.truck_spaces, '4');
  assert.notEqual(map.car_spaces, '45');
  assert.notEqual(map.walk_m, '40');
  assert.doesNotMatch(env.$('evidence').textContent, /\bpass\b/i);
});

test('shoot-pack HTML escapes dialogue and scene names; filenames stay safe', async () => {
  const env = boot();
  const heading = `INT. ${XSS}`;
  const description = `${SCRIPT_CLOSE} ${JS_URL} ${TRAVERSAL}`;
  await buildScript(env, `${heading} | ${description}\nINT. HALL | second`, [
    assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b'),
  ]);
  env.$('dlg').value = `${XSS}${SCRIPT_CLOSE} ${JS_URL} ${TRAVERSAL}`;
  env.$('dlg').dispatchEvent({ type: 'input' });
  env.$('addActor').click();
  env.$('aName').value = XSS;
  env.$('aName').dispatchEvent({ type: 'input' });
  env.drawLog.length = 0;
  env.$('expPack').click();
  await drain();
  const pack = env.downloads.find((item) => item.name.endsWith('.html'));
  assert.ok(pack, `expected an HTML download, status=${env.$('status').textContent}`);
  const html = await blobText(pack.blob);
  assert.equal(html.includes(XSS), false);
  assert.equal(html.includes(SCRIPT_CLOSE), false);
  assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;'));
  assert.ok(html.includes('&lt;/script&gt;'));
  assert.equal(/href\s*=\s*["']javascript:/i.test(html), false);
  assert.equal(/src\s*=\s*["']javascript:/i.test(html), false);
  assert.equal(pack.name, 'typecast-shootpack.html');
  assert.equal(pack.name.includes('..'), false);

  env.$('expPng').click();
  await drain();
  const png = env.downloads.find((item) => item.name.endsWith('.png'));
  assert.match(png.name, /^typecast-s[1-8]-[AB]\.png$/);
  for (const item of env.downloads) {
    assert.equal(item.name.includes(TRAVERSAL), false);
    assert.equal(item.name.includes('javascript:'), false);
    assert.equal(item.name.includes('<'), false);
  }
});

test('export omits licensed rows, cache URLs, keys, and local paths', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')]);
  env.$('expJson').click();
  env.drawLog.length = 0;
  env.$('expPack').click();
  await drain();
  const json = await blobText(env.downloads.find((item) => item.name.endsWith('.json')).blob);
  const html = await blobText(env.downloads.find((item) => item.name.endsWith('.html')).blob);
  const painted = env.drawLog.filter((entry) => entry.m === 'fillText').map((entry) => entry.args[0]).join('\n');
  const bundle = `${json}\n${html}\n${painted}`;
  for (const secret of [
    'sk-live-SECRETVALUE', '100 Example St (FAKE)', 'listing contact (FAKE)',
    '/Users/demo/cache/views/licensed.jpg', '/cache/private/aerial.png',
    'raw licensed logistics row', 'secret warning /cache/private/note', '34.05',
  ]) {
    assert.equal(bundle.includes(secret), false, secret);
  }
});

test('path-like and key-like property ids are redacted in JSON and the shoot-pack label', { todo: 'BUG: provText slices the raw property_id into provenance_label and the stage badge. safeId would reject "/cache/..." but export JSON and the shoot-pack canvas label never call it, so a path or key-like id is exported.' }, async () => {
  const env = boot();
  const propertyId = '/cache/sk-live-SECRET';
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', propertyId, 'shot_a')]);
  env.$('expJson').click();
  env.drawLog.length = 0;
  env.$('expPack').click();
  await drain();
  const json = await blobText(env.downloads.find((item) => item.name.endsWith('.json')).blob);
  const painted = env.drawLog.filter((entry) => entry.m === 'fillText').map((entry) => String(entry.args[0])).join('\n');
  assert.equal(json.includes('/cache'), false);
  assert.equal(json.includes('sk-live'), false);
  assert.equal(painted.includes('/cache'), false);
  assert.equal(painted.includes('sk-live'), false);
  assert.equal(env.api.safeId(propertyId), 'unknown');
});

test('animatic layer is labelled uncalibrated and silhouettes do not claim metres or FOV', async () => {
  assert.match(DIRECTOR_HTML, /Uncalibrated screen-space rehearsal/);
  assert.match(DIRECTOR_HTML, /Geometric fit: unknown/);
  assert.match(DIRECTOR_HTML, /screen space 0–1/);
  assert.match(DIRECTOR_HTML, /separate metric panel/);
  assert.match(DIRECTOR_HTML, /unverified/);
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')]);
  env.$('addActor').click();
  assert.match(env.api.BADGE, /UNCALIBRATED SCREEN-SPACE REHEARSAL/);
  assert.match(env.api.BADGE, /GEOMETRIC FIT UNKNOWN/);
  assert.ok(env.drawLog.some((entry) => entry.m === 'fillText' && String(entry.args[0]).includes(env.api.BADGE)));
  assert.match(env.$('evidence').textContent, /not calibrated to stage/);
  const snap = env.api.exportSnapshot();
  assert.match(snap.honesty, /Uncalibrated screen-space rehearsal/);
  assert.match(snap.honesty, /geometric fit unknown/i);
  const silhouette = JSON.stringify(snap.scenes[0].variants);
  assert.doesNotMatch(silhouette, /metres|meters|\bFOV\b|focal|clearance verified|fits the/i);
  for (const entry of env.drawLog) {
    if (entry.m !== 'fillText') continue;
    assert.doesNotMatch(String(entry.args[0]), /metres|meters|\bFOV\b|focal length|clearance verified|fits the room/i);
  }
  assert.match(env.$('planner').href, /focal=35/);
  assert.match(DIRECTOR_HTML, /id="planner"[\s\S]*separate metric panel/);
});

test('playback sums shot durations, clamps entry values, and pause resumes', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | one\nINT. HALL | two\nINT. OFFICE | three', [
    assignment('s1', 'prop_a', 'shot_a'),
    assignment('s2', 'prop_b', 'shot_b'),
    assignment('s3', 'prop_c', 'shot_c'),
  ]);
  const durations = { s1: '2', s2: '3', s3: '5' };
  for (const [sid, value] of Object.entries(durations)) {
    env.api.selectScene(sid);
    env.$('addActor').click();
    env.$('ax0').value = '0';
    env.$('ax0').dispatchEvent({ type: 'input' });
    env.$('ax1').value = '1';
    env.$('ax1').dispatchEvent({ type: 'input' });
    env.$('ay0').value = '0.5';
    env.$('ay0').dispatchEvent({ type: 'input' });
    env.$('ay1').value = '0.5';
    env.$('ay1').dispatchEvent({ type: 'input' });
    env.$('dur').value = value;
    env.$('dur').dispatchEvent({ type: 'change' });
  }
  assert.equal(env.api.shotData('s1').duration_sec + env.api.shotData('s2').duration_sec + env.api.shotData('s3').duration_sec, 10);

  env.api.selectScene('s1');
  for (const sample of ['0', '-4', 'NaN', '', 'nope']) {
    env.$('dur').value = sample;
    env.$('dur').dispatchEvent({ type: 'change' });
    const stored = env.api.shotData('s1').duration_sec;
    assert.equal(Number.isFinite(stored), true, sample);
    assert.ok(stored >= 1 && stored <= 30, `${sample} -> ${stored}`);
  }
  assert.equal(env.api.sanitizeShot({ duration_sec: 0, dialogue: '', actors: [] }).duration_sec, 1);
  assert.equal(env.api.sanitizeShot({ duration_sec: -8, dialogue: '', actors: [] }).duration_sec, 1);
  assert.equal(env.api.sanitizeShot({ duration_sec: Number.NaN, dialogue: '', actors: [] }).duration_sec, 5);
  env.$('dur').value = '2';
  env.$('dur').dispatchEvent({ type: 'change' });

  const before = structuredClone(env.api.S.edits);
  env.nowMs = 1000;
  env.$('play').click();
  assert.equal(env.api.S.play.total, 10);
  env.flushRaf();
  assert.equal(env.$('clock').textContent, '0.0s / 10.0s');
  assert.ok(highlighted(env, 's1'));

  env.nowMs = 1000 + 2000;
  env.flushRaf();
  assert.equal(env.$('clock').textContent, '2.0s / 10.0s');
  assert.ok(highlighted(env, 's1'));
  env.nowMs = 1000 + 2010;
  env.flushRaf();
  assert.ok(highlighted(env, 's2'));

  env.nowMs = 1000 + 5000;
  env.flushRaf();
  assert.ok(highlighted(env, 's2'));
  env.nowMs = 1000 + 5010;
  env.flushRaf();
  assert.ok(highlighted(env, 's3'));

  env.nowMs = 1000 + 10000;
  env.flushRaf();
  assert.equal(env.$('clock').textContent, '10.0s / 10.0s');
  assert.equal(env.api.S.play.on, false);
  assert.deepEqual(copied(env.api.S.edits), copied(before));

  env.nowMs = 0;
  env.$('play').click();
  env.nowMs = 2500;
  env.flushRaf();
  env.$('pause').click();
  assert.equal(env.api.S.play.on, false);
  assert.ok(Math.abs(env.api.S.play.acc - 2.5) < 1e-9);
  env.nowMs = 9000;
  env.$('play').click();
  env.nowMs = 9000 + 1000;
  env.flushRaf();
  assert.equal(env.$('clock').textContent, '3.5s / 10.0s');
  env.$('pause').click();

  env.drawLog.length = 0;
  const shot = { duration_sec: 4, dialogue: '', actors: [{ id: 'a', name: 'Ann', pose: 'stand', x0: 0, y0: 0.5, x1: 1, y1: 0.5, scale: 1 }] };
  const drawAt = (t) => {
    env.drawLog.length = 0;
    env.api.drawStage(env.$('stage').getContext('2d'), 1280, 720, { imgEl: null, missing: '', prov: 'p', shot, t, editing: false, sel: -1 });
    return poseX(env.drawLog);
  };
  assert.ok(Math.abs(drawAt(0) - 0) < 0.01);
  assert.ok(Math.abs(drawAt(2) - 640) < 0.01);
  assert.ok(Math.abs(drawAt(4) - 1280) < 0.01);
  assert.ok(Math.abs(drawAt(9) - 1280) < 0.01);
});

test('interpolation stays inside the start and end poses for a negative time', { todo: 'BUG: drawStage uses Math.min(1, t / duration) and does not clamp the low end, so a negative time extrapolates the silhouette before the start pose.' }, () => {
  const env = boot();
  const shot = { duration_sec: 4, dialogue: '', actors: [{ id: 'a', name: 'Ann', pose: 'stand', x0: 0, y0: 0.5, x1: 1, y1: 0.5, scale: 1 }] };
  env.api.drawStage(env.$('stage').getContext('2d'), 1280, 720, { imgEl: null, missing: '', prov: 'p', shot, t: -1, editing: false, sel: -1 });
  const x = poseX(env.drawLog);
  assert.ok(x >= -0.01 && x <= 1280.01, `pose x ${x} left the segment`);
});

test('playback can seek from the progress control', { todo: 'BUG: #prog is a display-only <progress> element. Nothing reads it, and there is no seek helper, so pause cannot be followed by a jump to another shot.' }, async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | one\nINT. HALL | two', [
    assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b'),
  ]);
  env.api.selectScene('s1');
  env.$('dur').value = '4';
  env.$('dur').dispatchEvent({ type: 'change' });
  env.api.selectScene('s2');
  env.$('dur').value = '6';
  env.$('dur').dispatchEvent({ type: 'change' });
  env.nowMs = 0;
  env.$('play').click();
  env.nowMs = 1000;
  env.flushRaf();
  env.$('pause').click();
  env.$('prog').value = 0.8;
  env.$('prog').dispatchEvent({ type: 'input' });
  env.$('prog').dispatchEvent({ type: 'change' });
  env.$('prog').click();
  assert.ok(Math.abs(env.api.S.play.acc - 8) < 0.05, `playhead stayed at ${env.api.S.play.acc}`);
  assert.ok(highlighted(env, 's2'));
  assert.match(env.$('clock').textContent, /^8\.0s \/ 10\.0s$/);
});

test('missing SpeechRecognition falls back to the instruction field', async () => {
  const env = boot({ speech: 'none' });
  assert.equal(env.$('micStart').disabled, true);
  assert.match(env.$('micNote').textContent, /type instead/i);
  env.$('instr').value = 'typed instruction';
  assert.equal(env.$('instr').disabled, false);
  assert.equal(env.$('instr').value, 'typed instruction');
  env.$('micStart').click();
  assert.match(env.$('status').textContent, /Type instead/i);
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')]);
  env.$('gen').click();
  const sent = JSON.parse(env.take('/api/production/brainstorm').opts.body);
  assert.equal(sent.instruction, 'typed instruction');
});

test('a denied microphone falls back to typed input', async () => {
  for (const speech of ['deny', 'throw']) {
    const env = boot({ speech });
    await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')]);
    env.$('micStart').click();
    await drain();
    assert.match(env.$('status').textContent, /Type (your instruction )?instead/i);
    assert.equal(env.$('instr').disabled, false);
    env.$('instr').value = `typed after ${speech}`;
    env.$('instr').dispatchEvent({ type: 'input' });
    assert.equal(env.$('instr').value, `typed after ${speech}`);
    env.$('gen').click();
    const sent = JSON.parse(env.take('/api/production/brainstorm').opts.body);
    assert.equal(sent.instruction, `typed after ${speech}`);
  }
});

test('mock mode is labelled and no agent step is invented beyond the response', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')], {
    evaluated_subsets: 7,
    trace: { steps: [{ text: 'RESPONSE_STEP_ONLY_zz' }] },
    events: [{ type: 'skeptic', agent: 'solver', text: 'RESPONSE_EVENT_ONLY_zz' }],
  });
  const text = `${env.$('planMeta').textContent}\n${env.$('status').textContent}\n${env.document.body.textContent}`;
  assert.match(env.$('planMeta').textContent, /Mode mock/);
  assert.doesNotMatch(env.$('planMeta').textContent, /\blive\b/);
  assert.match(env.$('planMeta').textContent, /7 subsets/);
  assert.equal(text.includes('FABRICATED_DEEP_AGENT_STEP_zz'), false);
  assert.doesNotMatch(text, /agent trace|LangSmith|Deep Agents/i);
  const responseSteps = ['RESPONSE_STEP_ONLY_zz', 'RESPONSE_EVENT_ONLY_zz'];
  for (const rendered of text.match(/[A-Z]+_(?:STEP|EVENT)_[A-Z0-9_]+/g) || []) {
    assert.ok(responseSteps.includes(rendered), rendered);
  }
});

function highlighted(env, sid) {
  return env.$('timeline').querySelectorAll('button').some((button) => button.classList.contains('now') && button.dataset.sid === sid);
}

test('real browser surfaces this harness cannot drive', { skip: 'No display, microphone, or browser HTML parser in this vm. Canvas pixels, JPEG contents, SpeechRecognition audio, layout hit-testing, and Chrome/Firefox outerHTML byte-for-byte output are not exercised. The tests above drive director.js itself and serialize the textContent nodes it creates.' }, () => {});
