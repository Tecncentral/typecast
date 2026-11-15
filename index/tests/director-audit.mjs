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
const CHECKS_JS = readFileSync(join(DIR, '..', 'director-checks.js'), 'utf8');
const DIRECTOR_HTML = readFileSync(join(DIR, '..', 'director.html'), 'utf8');
const FOOTER = `
globalThis.__director = {
  S, frameAt, shotData, sanitizeShot, exportSnapshot, provText, drawStage,
  selectScene, setVariant, BADGE, safeId, setMode, saveDraft, restoreDraft, draftState, initDraft, draftKey, swapLocation, altChoices, validSwap, fitFor, continuityMap, decisionFor, viewShot, undoSwap, backToPlanned,
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

function createEnv({ speech = 'none', storage = null } = {}) {
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
    planMeta: 'p', stagePlanSummary: 'p', forbidden: 'p', clearRej: 'button', rail: 'ol', framePicker: 'div',
    frameNotice: 'div', stage: 'canvas', play: 'button', pause: 'button', reset: 'button',
    prog: 'progress', clock: 'span', timeline: 'ol', varLbl: 'span', varA: 'button', varB: 'button',
    shotForm: 'fieldset', dur: 'input', dlg: 'textarea', actorSel: 'select', addActor: 'button',
    delActor: 'button', actorForm: 'fieldset', aName: 'input', aPose: 'select', aScale: 'input',
    ax0: 'input', ay0: 'input', ax1: 'input', ay1: 'input', micNote: 'p', micStart: 'button',
    micStop: 'button', instr: 'textarea', gen: 'button', undo: 'button', proposal: 'div',
    pSum: 'p', pNote: 'p', pDiff: 'ul', applyB: 'button', discard: 'button', evidence: 'div',
    impProject: 'input', plannerOut: 'div', projectReview: 'div', lookAround: 'button', expReel: 'button', cancelReel: 'button', planner: 'a', expPng: 'button', expJson: 'button', expPack: 'button', cmpAB: 'button', loadSample: 'button', compareStrip: 'div', originTag: 'p', parseSummary: 'div', draftNotice: 'div', draftOpt: 'input', draftClear: 'button', draftNote: 'p', modeFilm: 'button', modeComm: 'button', modeHint: 'p', lblTrucks: 'span', lblCars: 'span', stageCaption: 'p', commBanner: 'p', 'h-script': 'h2', 'h-plan': 'h2', 'h-scenes': 'h2', 'h-stage': 'h1', scriptHint: 'label', 'panel-site': 'section', siteTitle: 'h2', siteReq: 'input', siteChecksSummary: 'summary', siteChecks: 'div', siteTasks: 'div', taskAdd: 'button', siteNote: 'textarea', siteCap: 'input', siteCapSrc: 'input', briefReviewer: 'input', briefDate: 'input', briefNotes: 'textarea', swapNotice: 'div', sceneChecks: 'details', checksSummary: 'summary', checksBody: 'div', prodNotes: 'details', noteDressing: 'textarea', noteGroup: 'input',
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
  if (storage === 'blocked') Object.defineProperty(sandbox, 'localStorage', { get() { throw new Error('SecurityError'); } });
  else if (storage) sandbox.localStorage = storage;
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
  // Draft restore runs the strict project validator, which needs the context's own Object/Array/JSON (as startImport does).
  if (options && options.storage) for (const name of ['Object', 'Array', 'JSON']) delete env.context[name];
  vm.runInContext(CHECKS_JS, env.context, { filename: 'director-checks.js' });
  vm.runInContext(PROJECT_JS, env.context, { filename: 'director-project.js' });
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
      property_ids: [...new Set(assignments.map((row) => row.property_id))],
      locations: new Set(assignments.map((row) => row.property_id)).size,
    }],
    evaluated_subsets: extra.evaluated_subsets ?? 4,
    optimal_within_pool: true,
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

test('a replanned response that still assigns the rejected property is not shown', async () => {
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
  assert.deepEqual(copied(env.api.S.resp.plans[0].property_ids), ['prop_b']);
  assert.equal(env.api.S.resp.plans[0].locations, 1);
  assert.deepEqual(copied(env.api.S.resp.plans[0].uncovered_scene_ids), ['s1']);
  assert.equal(env.api.S.resp.optimal_within_pool, false);
  assert.equal(env.api.S.resp.plans[0].mean_similarity, null);
  assert.equal(env.api.S.resp.plans[0].company_moves, null);
  assert.match(env.$('stagePlanSummary').textContent, /1\/2 scenes · 1 location · \? moves/);
});

test('a failed replan still removes the rejected property and invalidates stale plan claims', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | coffee\nINT. BEDROOM | packing', [
    assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b'),
  ]);
  env.$('reject').click();
  env.take('/api/production/plan').reject(new Error('Backend unavailable'));
  await drain();
  const p = env.api.S.resp.plans[0];
  assert.equal(p.locations, 1);
  assert.deepEqual(copied(p.property_ids), ['prop_b']);
  assert.deepEqual(copied(p.uncovered_scene_ids), ['s1']);
  assert.equal(p.company_moves, null);
  assert.equal(p.mean_similarity, null);
  assert.equal(env.api.S.resp.optimal_within_pool, false);
  assert.match(env.$('status').textContent, /rejected location was removed locally/);
});

test('recommends full coverage with fewer locations and keeps higher-similarity alternatives', async () => {
  const env = boot();
  env.$('script').value = 'INT. KITCHEN | coffee\nINT. LIVING ROOM | a visitor\nINT. BEDROOM | packing';
  env.$('build').click();
  const job = env.take('/api/production/plan'), body = JSON.parse(job.opts.body);
  const rows = body.scenes.map((s, i) => assignment(s.id, `prop_${i}`, `shot_${i}`));
  const data = planFor(body, rows);
  data.plans = [
    { ...data.plans[0], company_moves: 2, mean_similarity: 0.4 },
    { ...data.plans[0], assignments: rows.map((a) => ({ ...a, property_id: 'prop_0' })),
      property_ids: ['prop_0'], locations: 1, company_moves: 0, mean_similarity: 0.3 },
    { ...data.plans[0], assignments: [rows[0]], uncovered_scene_ids: ['s2', 's3'],
      property_ids: ['prop_0'], locations: 1, company_moves: 0, mean_similarity: 0.5 },
  ];
  job.resolve(jsonResponse(data)); await drain();
  assert.equal(env.api.S.resp.plans[0].mean_similarity, 0.3);
  assert.equal(env.api.S.resp.plans[1].mean_similarity, 0.4);
  assert.equal(env.api.S.resp.plans[2].assignments.length, 1);
  assert.equal(env.$('stagePlanSummary').textContent, '3/3 scenes · 1 location · 0 moves');
  assert.equal(env.$('planSel').options[0].textContent, '3/3 scenes · 1 location · 0 moves');
  assert.equal(env.$('planSel').options[0].getAttribute('title'), 'Mean similarity 0.300');
  env.$('planSel').value = '1'; env.$('planSel').dispatchEvent({ type: 'change' });
  assert.equal(env.$('stagePlanSummary').textContent, '3/3 scenes · 3 locations · 2 moves');
});

test('a failed replan after Reject still removes the rejected location from view and exports', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first\nINT. OFFICE | second', [
    assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b'),
  ]);
  env.$('reject').click();
  env.take('/api/production/plan').resolve(jsonResponse({ detail: 'backend down' }, 503));
  await drain();
  assert.match(env.$('forbidden').textContent, /prop_a/);
  assert.equal(env.$('rail').textContent.includes('prop_a'), false);
  assert.equal(env.api.S.resp.plans[0].assignments.some((row) => row.property_id === 'prop_a'), false);
  assert.equal(JSON.stringify(env.api.exportSnapshot()).includes('shot_a'), false);
  assert.match(env.$('status').textContent, /replan failed/i);
});

const PROJECT_JS = readFileSync(join(DIR, '..', 'director-project.js'), 'utf8');
function savedProject(dialogue) {
  const shot = (text) => ({ duration_sec: 5, dialogue: text, actors: [] });
  return JSON.stringify({ app: 'Typecast Director', variant: 'A', scenes: [{
    id: 's1', heading: 'INT. KITCHEN', description: 'first',
    evidence: { frame: { shot_id: 'shot_a', property_id: 'prop_a' } },
    variants: { A: shot(dialogue), B: shot('') } }] });
}
async function startImport(env, text) {
  // The harness injects host Object/Array/JSON; the validator needs same-realm plain objects, as in a browser.
  for (const name of ['Object', 'Array', 'JSON']) delete env.context[name];
  vm.runInContext(PROJECT_JS, env.context, { filename: 'director-project.js' });
  const file = { size: text.length, text: async () => text };
  env.$('impProject').files = [file];
  env.$('impProject').dispatchEvent({ type: 'change' });
  await drain();
  if (!env.jobs.length) throw new Error(env.$('status').textContent);
  const job = env.take('/api/production/plan');
  return { job, body: JSON.parse(job.opts.body) };
}

test('an in-flight project import never overwrites staging typed while it loads', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')]);
  const { job, body } = await startImport(env, savedProject('IMPORTED_LINE'));
  env.$('dlg').value = 'NEWER_USER_WORK';
  env.$('dlg').dispatchEvent({ type: 'input' });
  job.resolve(jsonResponse(planFor(body, [assignment('s1', 'prop_a', 'shot_a')])));
  await drain();
  assert.equal(env.api.shotData('s1').dialogue, 'NEWER_USER_WORK');
  assert.match(env.$('status').textContent, /nothing was replaced/);
  assert.equal(env.api.S.importReview.length, 0);
});

test('an untouched in-flight project import still commits exact-frame staging', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')]);
  const { job, body } = await startImport(env, savedProject('IMPORTED_LINE'));
  job.resolve(jsonResponse(planFor(body, [assignment('s1', 'prop_a', 'shot_a')])));
  await drain();
  assert.equal(env.api.shotData('s1').dialogue, 'IMPORTED_LINE', env.$('status').textContent);
});

// The real solver publishes locations as a COUNT and the property list as property_ids.
function solverShaped(body, rows, extraPlans = []) {
  const resp = planFor(body, rows);
  const shape = (assignments) => {
    const ids = [...new Set(assignments.map((a) => a.property_id))].sort();
    const covered = new Set(assignments.map((a) => a.scene_id));
    return { property_ids: ids, assignments, locations: ids.length,
      uncovered_scene_ids: body.scenes.map((x) => x.id).filter((id) => !covered.has(id)),
      company_moves: Math.max(0, ids.length - 1), mean_similarity: 0.5 };
  };
  resp.plans = [shape(rows), ...extraPlans.map(shape)];
  resp.optimal_within_pool = true;
  return resp;
}
const TWO = [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b')];

test('real solver-shaped plans: replan failure after Reject leaves no rejected ids or stale claims', async () => {
  const env = boot();
  env.$('script').value = 'INT. KITCHEN | first\nINT. OFFICE | second';
  env.$('build').click();
  let job = env.take('/api/production/plan');
  const body0 = JSON.parse(job.opts.body);
  // Partial coverage so the Director's coverage-first ordering keeps TWO as plan 0.
  const other = [assignment('s1', 'prop_c', 'shot_c')];
  job.resolve(jsonResponse(solverShaped(body0, TWO, [other])));
  await drain();
  env.$('reject').click();
  env.take('/api/production/plan').resolve(jsonResponse({ detail: 'down' }, 503));
  await drain();
  const [p0, p1] = env.api.S.resp.plans;
  assert.deepEqual(copied(p0.property_ids), ['prop_b']);
  assert.equal(p0.locations, 1);
  assert.deepEqual(copied(p0.uncovered_scene_ids), ['s1']);
  assert.equal(p0.mean_similarity, null);
  assert.equal(p0.company_moves, null);
  assert.deepEqual(copied(p1.property_ids), ['prop_c']);       // unrelated plan untouched
  assert.equal(p1.mean_similarity, 0.5);
  assert.equal(env.api.S.resp.optimal_within_pool, false);
  const exported = JSON.stringify(env.api.exportSnapshot());
  assert.equal(exported.includes('prop_a'), false);
  assert.equal(JSON.parse(exported).locations, 1);
  assert.equal(JSON.parse(exported).mean_similarity, null);
  assert.match(env.$('planSel').childNodes[0].textContent, /1\/2 scenes · 1 location/);
});

test('real solver-shaped plans: a backend that still returns the rejected property is cleaned', async () => {
  const env = boot();
  env.$('script').value = 'INT. KITCHEN | first\nINT. OFFICE | second';
  env.$('build').click();
  let job = env.take('/api/production/plan');
  job.resolve(jsonResponse(solverShaped(JSON.parse(job.opts.body), TWO)));
  await drain();
  env.$('reject').click();
  job = env.take('/api/production/plan');
  job.resolve(jsonResponse(solverShaped(JSON.parse(job.opts.body), TWO)));
  await drain();
  const plan = env.api.S.resp.plans[0];
  assert.deepEqual(copied(plan.property_ids), ['prop_b']);
  assert.equal(plan.locations, 1);
  assert.equal(/Plan request failed/.test(env.$('status').textContent), false);
});

function slowFile(text) {
  let release; const gate = new Promise((r) => { release = r; });
  return { file: { size: text.length, text: async () => { await gate; return text; } }, release };
}
function prepImportEnv(env) {
  for (const name of ['Object', 'Array', 'JSON']) delete env.context[name];
  vm.runInContext(PROJECT_JS, env.context, { filename: 'director-project.js' });
}
const ONE = [assignment('s1', 'prop_a', 'shot_a')];

test('staging typed during a slow project-file read is not overwritten, and overlapping imports are refused', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', ONE);
  prepImportEnv(env);
  const slow = slowFile(savedProject('IMPORTED_LINE'));
  env.$('impProject').files = [slow.file];
  env.$('impProject').dispatchEvent({ type: 'change' });
  await drain();
  env.$('dlg').value = 'TYPED_DURING_READ';
  env.$('dlg').dispatchEvent({ type: 'input' });
  const second = slowFile(savedProject('SECOND'));
  env.$('impProject').files = [second.file];
  env.$('impProject').dispatchEvent({ type: 'change' });
  await drain();
  assert.match(env.$('status').textContent, /Wait for the current/);
  assert.equal(env.$('build').disabled, true);
  slow.release();
  await drain();
  const job = env.take('/api/production/plan');
  assert.equal(env.jobs.length, 0);
  job.resolve(jsonResponse(planFor(JSON.parse(job.opts.body), ONE)));
  await drain();
  assert.equal(env.api.shotData('s1').dialogue, 'TYPED_DURING_READ');
  assert.match(env.$('status').textContent, /nothing was replaced/);
});

test('constraints changed while import evidence loads reject the import; unchanged constraints commit', async () => {
  for (const change of ['maxLoc', 'trucks', 'cars', 'reqAvail', null]) {
    const env = boot();
    await buildScript(env, 'INT. KITCHEN | first', ONE);
    const { job, body } = await startImport(env, savedProject('IMPORTED_LINE'));
    if (change === 'reqAvail') env.$('reqAvail').checked = !env.$('reqAvail').checked;
    else if (change) env.$(change).value = '2';
    assert.equal(body.max_locations !== undefined && body.trucks !== undefined && body.cars !== undefined, true);
    job.resolve(jsonResponse(planFor(body, ONE)));
    await drain();
    if (change) {
      assert.match(env.$('status').textContent, /constraints changed/, change);
      assert.notEqual(env.api.shotData('s1').dialogue, 'IMPORTED_LINE', change);
    } else assert.equal(env.api.shotData('s1').dialogue, 'IMPORTED_LINE');
  }
});

test('mock results are labelled as fixtures in status and plan summary; live results are not', async () => {
  const mock = boot();
  await buildScript(mock, 'INT. KITCHEN | first', ONE);
  assert.match(mock.$('status').textContent, /MOCK FIXTURE RESULTS/);
  assert.doesNotMatch(mock.$('status').textContent, /real results/i);
  assert.match(mock.$('planMeta').textContent, /^MOCK FIXTURES/);
  const live = boot();
  await buildScript(live, 'INT. KITCHEN | first', ONE, { mode: 'live' });
  assert.doesNotMatch(live.$('status').textContent, /MOCK/);
  assert.doesNotMatch(live.$('planMeta').textContent, /MOCK/);
  assert.doesNotMatch(boot().$('status').textContent, /real results/i);
});

test('Look around in mock mode explains that fixtures have no scan geometry instead of opening a dialog', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', ONE);
  env.$('lookAround').click();
  await drain();
  assert.match(env.$('status').textContent, /Mock fixture frames/);
  assert.match(env.$('status').textContent, /AI dressing/);
});

test('camera metrics render in-page from /api/plan with unknowns kept, and stale responses are dropped', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first\nINT. OFFICE | second', TWO);
  env.$('planner').dispatchEvent({ type: 'click' });
  const job = env.take('/api/plan/shot_a');
  env.api.selectScene('s2');
  job.resolve(jsonResponse({ status: 'unknown', note: 'Missing validated room boundary', position: null, shot_id: 'shot_a' }));
  await drain();
  assert.equal(env.$('plannerOut').textContent.includes('Missing validated'), false); // scene changed: dropped
  env.api.selectScene('s1');
  env.$('planner').dispatchEvent({ type: 'click' });
  env.take('/api/plan/shot_a').resolve(jsonResponse({ status: 'unknown', note: 'Missing validated room boundary', position: null }));
  await drain();
  const text = env.$('plannerOut').textContent;
  assert.match(text, /Missing validated room boundary/);
  assert.match(text, /position/);
  assert.match(text, /unknown/);
  assert.match(text, /unverified/);
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

test('mock-shaped unknown availability and parking are not displayed as pass or available', async () => {
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

test('evidence status uses the vocabulary for its field and preserves supported facts', async () => {
  for (const status of [undefined, 'pass', 'available', 'measured']) {
    const env = boot();
    await buildScript(env, 'INT. ROOM | one', [assignment('s1', 'prop_a', 'shot_a')], {
      evidence: {
        property: { available: true, availability_status: status },
        logistics: { parking_status: status, walk_status: status, truck_spaces: 4, car_spaces: 45,
          enough_parking: true, walk_m: 40 },
      },
    });
    const map = fieldMap(env.$('evidence'));
    assert.equal(map.available, status === 'available' ? 'true' : 'unknown');
    assert.equal(map.truck_spaces, status === 'measured' ? '4' : 'unknown');
    assert.equal(map.enough_parking, status === 'measured' ? 'true' : 'unknown');
    assert.equal(map.walk_m, status === 'measured' ? '40' : 'unknown');
  }
  const env = boot();
  await buildScript(env, 'INT. ROOM | one', [assignment('s1', 'prop_a', 'shot_a')], {
    evidence: { property: { available: true, availability_status: 'not_available' },
      logistics: { parking_status: 'estimated', truck_spaces: 2, enough_parking: false } },
  });
  const map = fieldMap(env.$('evidence'));
  assert.equal(map.available, 'false');
  assert.equal(map.truck_spaces, '2');
  assert.equal(map.enough_parking, 'false');
});

test('safe identifiers reject traversal and recognizable credential prefixes', () => {
  const env = boot();
  for (const value of ['/cache/secret', '../file', 'a..b', 'sk-live-SECRET', 'api_key-secret', 'javascript:alert(1)']) {
    assert.equal(env.api.safeId(value), 'unknown', value);
  }
  assert.equal(env.api.safeId('property_123-abc'), 'property_123-abc');
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

test('path-like and key-like property ids are redacted in JSON and the shoot-pack label', async () => {
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
  assert.match(DIRECTOR_HTML, /metric panel/);
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
  assert.match(DIRECTOR_HTML, /id="planner"[\s\S]*metric panel/);
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

test('interpolation stays inside the start and end poses for a negative time', () => {
  const env = boot();
  const shot = { duration_sec: 4, dialogue: '', actors: [{ id: 'a', name: 'Ann', pose: 'stand', x0: 0, y0: 0.5, x1: 1, y1: 0.5, scale: 1 }] };
  env.api.drawStage(env.$('stage').getContext('2d'), 1280, 720, { imgEl: null, missing: '', prov: 'p', shot, t: -1, editing: false, sel: -1 });
  const x = poseX(env.drawLog);
  assert.ok(x >= -0.01 && x <= 1280.01, `pose x ${x} left the segment`);
});

test('playback progress is explicitly a display-only indicator', () => {
  assert.match(DIRECTOR_HTML, /<progress id="prog"[^>]*aria-label="Playback progress"/);
  assert.doesNotMatch(DIRECTOR_JS, /\$\('prog'\)\.addEventListener/);
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

// ---------- Compare A/B (read-only) and the authored offline sample ----------
async function twoTakes() {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first\nINT. OFFICE | second', [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b')]);
  env.api.selectScene('s1');
  env.$('addActor').click();                                  // take A: one actor, 5 s
  env.$('dlg').value = 'A_LINE'; env.$('dlg').dispatchEvent({ type: 'input' });
  env.api.setVariant('B');
  env.$('addActor').click();
  env.$('dur').value = '8'; env.$('dur').dispatchEvent({ type: 'input' });   // take B: 8 s
  env.$('dlg').value = 'B_LINE'; env.$('dlg').dispatchEvent({ type: 'input' });
  env.api.setVariant('A');
  return env;
}
const painted = (env) => env.drawLog.filter((e) => e.m === 'fillText').map((e) => String(e.args[0])).join('\n');
const editsOf = (env) => JSON.stringify(env.api.S.edits);

test('Compare A/B is a read-only view: nothing mutates, the active take stays, drag/keys/form are locked', async () => {
  const env = await twoTakes();
  const before = editsOf(env), rev = env.api.S.rev, variant = env.api.S.variant, mode = env.api.S.resp.mode;
  env.$('cmpAB').click();
  assert.equal(env.api.S.compare, true);
  assert.equal(env.$('cmpAB').attrs['aria-pressed'], 'true');
  assert.equal(env.$('compareStrip').hidden, false);
  assert.match(env.$('compareStrip').textContent, /Read-only A\/B comparison/);
  assert.match(env.$('compareStrip').textContent, /Take A runs 5s, take B 8s \(different lengths/);
  assert.match(env.$('compareStrip').textContent, /PNG and WebM export that take only; Project JSON and Shoot pack include both/);
  assert.equal(env.$('shotForm').disabled, true); assert.equal(env.$('addActor').disabled, true);
  const text = painted(env);
  assert.match(text, /TAKE A \(active take\)/); assert.match(text, /TAKE B/); assert.match(text, /Comparison view only\. Not an export/);
  assert.match(text, /5s/); assert.match(text, /8s/);
  assert.ok(env.drawLog.filter((e) => e.m === 'fillText' && String(e.args[0]).includes(env.api.BADGE)).length >= 2, 'uncalibrated label in both panes');
  // Pointer drag on the actor and arrow keys must not edit either take.
  const cv = env.$('stage'), a = env.api.shotData('s1', 'A').actors[0];
  cv.dispatchEvent({ type: 'pointerdown', clientX: a.x0 * 1280, clientY: (a.y0 - 0.05) * 720, pointerId: 1 });
  cv.dispatchEvent({ type: 'pointermove', clientX: 100, clientY: 100, pointerId: 1 });
  cv.dispatchEvent({ type: 'pointerup', pointerId: 1 });
  cv.dispatchEvent({ type: 'keydown', key: 'ArrowLeft' }); cv.dispatchEvent({ type: 'keydown', key: 'ArrowUp', shiftKey: true });
  assert.equal(editsOf(env), before); assert.equal(env.api.S.rev, rev);
  assert.equal(env.api.S.variant, variant); assert.equal(env.api.S.resp.mode, mode);
  env.$('cmpAB').click();                                       // toggle off restores single view, still unmutated
  assert.equal(env.api.S.compare, false); assert.equal(env.$('compareStrip').hidden, true); assert.equal(env.$('shotForm').disabled, false);
  assert.equal(editsOf(env), before);
});

test('selecting take A or B leaves comparison and edits only that take afterwards', async () => {
  const env = await twoTakes();
  env.$('cmpAB').click(); env.api.setVariant('B');
  assert.equal(env.api.S.compare, false);
  env.$('dlg').value = 'B_EDIT'; env.$('dlg').dispatchEvent({ type: 'input' });
  assert.equal(env.api.shotData('s1', 'B').dialogue, 'B_EDIT'); assert.equal(env.api.shotData('s1', 'A').dialogue, 'A_LINE');
});

test('compare playback uses one real-time clock: scene lasts the longer take; the shorter holds and says so', async () => {
  const env = await twoTakes();
  env.$('cmpAB').click();
  env.nowMs = 1000; env.$('play').click();
  assert.equal(env.api.S.play.total, 8 + 5);                    // s1: max(5,8)=8, s2 default 5/5
  env.flushRaf(); env.drawLog.length = 0; env.nowMs = 1000 + 6500; env.flushRaf();
  const text = painted(env);
  assert.match(text, /ended at 5s, holding last pose/);          // take A (5 s) is past its end
  assert.match(text, /6\.5s \/ 8s/);                             // take B still running
  assert.doesNotMatch(text, /6\.5s \/ 5s/);
  assert.match(env.$('status').textContent, /both takes side by side on one real-time clock/);
  // Single-take playback is unchanged: active take A only.
  env.$('cmpAB').click(); env.$('play').click();
  assert.equal(env.api.S.play.total, 5 + 5);
});

test('exports keep their take semantics while comparing: PNG is the active take only, JSON/pack still carry both', async () => {
  const env = await twoTakes();
  env.$('cmpAB').click();
  const cv = env.$('stage'), orig = cv.toBlob.bind(cv); let atExport = null;
  cv.toBlob = (cb, type) => { atExport = painted(env); orig(cb, type); };
  env.drawLog.length = 0; env.$('expPng').click(); await drain();
  assert.doesNotMatch(atExport, /Comparison view only|TAKE A|TAKE B/);     // canvas was the single-take layout at capture time
  assert.ok(env.downloads.some((d) => d.name === 'typecast-s1-A.png'));
  assert.equal(env.api.S.compare, true);                                    // comparison restored afterwards
  const snap = env.api.exportSnapshot();
  assert.equal(snap.variant, 'A');
  assert.equal(snap.scenes[0].variants.A.dialogue, 'A_LINE'); assert.equal(snap.scenes[0].variants.B.dialogue, 'B_LINE');
  assert.equal(snap.scenes[0].variants.B.duration_sec, 8); assert.equal(snap.scenes[0].staging.dialogue, 'A_LINE');
});

test('brainstorm still fails honestly without a model and never substitutes the authored sample', async () => {
  const env = await twoTakes();
  const before = editsOf(env);
  env.$('instr').value = 'Have the actor enter from the window'; env.$('gen').click();
  env.take('/api/production/brainstorm').resolve(jsonResponse({ detail: 'Configured model provider unavailable' }, 503));
  await drain();
  assert.match(env.$('status').textContent, /Brainstorm unavailable: Configured model provider unavailable\. No changes made/);
  assert.equal(env.api.S.pending, null); assert.equal(env.$('proposal').hidden, true); assert.equal(editsOf(env), before);
  assert.equal(env.jobs.length, 0);
});

test('authored sample: opt-in, no model call, labelled, A untouched, Apply writes only B, Undo and Discard keep semantics', async () => {
  const env = await twoTakes();
  const aBefore = JSON.stringify(env.api.shotData('s1', 'A')), bBefore = JSON.stringify(env.api.shotData('s1', 'B')), mode = env.api.S.resp.mode;
  env.$('instr').value = 'something completely different that must be ignored';
  env.$('loadSample').click();
  assert.equal(env.jobs.length, 0, 'no network request for the sample');
  assert.equal(env.$('proposal').hidden, false);
  assert.match(env.$('pSum').textContent, /Authored sample alternative \(pre-written, not AI-generated\)/);
  assert.match(env.$('pNote').textContent, /ignores your direction text and no model was called/);
  assert.match(env.$('status').textContent, /not AI, no model call/);
  assert.equal(JSON.stringify(env.api.shotData('s1', 'A')), aBefore); assert.equal(JSON.stringify(env.api.shotData('s1', 'B')), bBefore);
  const a = env.api.shotData('s1', 'A').actors[0];
  env.$('discard').click();
  assert.equal(JSON.stringify(env.api.shotData('s1', 'B')), bBefore);
  env.$('loadSample').click(); env.$('applyB').click();
  const b = env.api.shotData('s1', 'B');
  assert.equal(JSON.stringify(env.api.shotData('s1', 'A')), aBefore);          // A never changes
  assert.equal(b.dialogue, 'A_LINE'); assert.equal(b.duration_sec, 5);          // derived from A, no invented dialogue
  assert.equal(b.actors[0].x0, Math.round((1 - a.x0) * 1000) / 1000);          // mirrored from A
  assert.ok(b.actors[0].x1 !== b.actors[0].x0 && b.actors.length === 1);
  assert.match(env.$('status').textContent, /Applied the authored sample to variant B/);
  assert.equal(env.api.S.resp.mode, mode); assert.equal(env.$('proposal').hidden, true);
  env.$('undo').click();
  assert.equal(JSON.stringify(env.api.shotData('s1', 'B')), bBefore); assert.equal(JSON.stringify(env.api.shotData('s1', 'A')), aBefore);
  assert.equal(env.jobs.length, 0);
});

test('authored sample with an empty take A uses one generic performer and invents no source facts', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN | first', [assignment('s1', 'prop_a', 'shot_a')]);
  const evBefore = JSON.stringify(env.api.exportSnapshot().scenes[0].evidence);
  env.$('loadSample').click(); env.$('applyB').click();
  const b = env.api.shotData('s1', 'B');
  assert.equal(b.actors.length, 1); assert.equal(b.actors[0].name, 'Performer');
  assert.equal(env.api.shotData('s1', 'A').actors.length, 0);
  assert.equal(JSON.stringify(env.api.exportSnapshot().scenes[0].evidence), evBefore);
});

test('loading the sample cancels an in-flight model request whose late reply is then ignored', async () => {
  const env = await twoTakes();
  env.honorAbort = false;
  env.$('instr').value = 'model direction'; env.$('gen').click();
  const job = env.take('/api/production/brainstorm');
  env.$('loadSample').click();
  const sample = JSON.stringify(env.api.S.pending.shot);
  job.resolve(jsonResponse({ summary: 'late', shot: { duration_sec: 9, dialogue: 'LATE_MODEL', actors: [] } }));
  await drain();
  assert.equal(JSON.stringify(env.api.S.pending.shot), sample);
  assert.equal(editsOf(env).includes('LATE_MODEL'), false);
  assert.match(env.$('pSum').textContent, /Authored sample/);
});

test('a pending sample is dropped when the scene changes or the take is edited, and Apply refuses a stale one', async () => {
  const env = await twoTakes();
  const before = editsOf(env);
  env.$('loadSample').click(); env.api.selectScene('s2');
  assert.equal(env.api.S.pending, null); assert.equal(env.$('proposal').hidden, true);
  env.$('applyB').click();
  assert.match(env.$('status').textContent, /no longer matches|discarded/i);
  assert.equal(editsOf(env), before);
  env.api.selectScene('s1'); env.$('loadSample').click();
  env.$('dlg').value = 'typed meanwhile'; env.$('dlg').dispatchEvent({ type: 'input' });       // staging edit invalidates it
  assert.equal(env.api.S.pending, null);
});

// ---------- authored-sample provenance must travel with the take everywhere ----------
const TAG = 'AUTHORED SAMPLE · not AI';
async function sampleOnB() {
  const env = await twoTakes();
  env.$('loadSample').click(); env.$('applyB').click();
  return env;
}
const tagDrawn = (env) => painted(env).includes(TAG);

test('origin: a sample-derived B carries a validated origin; A, manual and untouched takes do not', async () => {
  const env = await sampleOnB();
  assert.equal(env.api.shotData('s1', 'B').origin, 'authored-sample');
  assert.equal(env.api.shotData('s1', 'A').origin, undefined);
  assert.equal(env.api.shotData('s2', 'B').origin, undefined);
  // card: the inspector tag is shown on B only
  env.api.setVariant('B');
  assert.equal(env.$('originTag').hidden, false); assert.match(env.$('originTag').textContent, /AUTHORED SAMPLE · not AI/);
  env.drawLog.length = 0; env.api.setVariant('B'); assert.ok(tagDrawn(env), 'tag drawn on the stage for take B');
  env.api.setVariant('A'); assert.equal(env.$('originTag').hidden, true);
  env.drawLog.length = 0; env.api.setVariant('A'); assert.equal(tagDrawn(env), false);
  // human edits keep a sample-derived take sample-derived
  env.api.setVariant('B'); env.$('dlg').value = 'edited by a person'; env.$('dlg').dispatchEvent({ type: 'input' });
  assert.equal(env.api.shotData('s1', 'B').origin, 'authored-sample');
  // the user's own dialogue/name text is never used as the label
  assert.equal(env.api.shotData('s1', 'B').dialogue, 'edited by a person');
  // undo restores the previous B including its (absent) origin
  env.$('undo').click(); assert.equal(env.api.shotData('s1', 'B').origin, undefined);
});

test('origin: a live model proposal is never tagged as the sample, even if the response claims it', async () => {
  const env = await twoTakes();
  env.$('instr').value = 'x'; env.$('gen').click();
  env.take('/api/production/brainstorm').resolve(jsonResponse({ summary: 'model', shot: { duration_sec: 4, dialogue: 'M', origin: 'authored-sample', actors: [] } }));
  await drain(); env.$('applyB').click();
  assert.equal(env.api.shotData('s1', 'B').dialogue, 'M'); assert.equal(env.api.shotData('s1', 'B').origin, undefined);
  // a model proposal applied over a sample-derived B replaces the take, and the old origin goes with it
  env.$('loadSample').click(); env.$('applyB').click(); assert.equal(env.api.shotData('s1', 'B').origin, 'authored-sample');
  env.$('instr').value = 'y'; env.$('gen').click();
  env.take('/api/production/brainstorm').resolve(jsonResponse({ summary: 'model2', shot: { duration_sec: 6, dialogue: 'M2', actors: [] } }));
  await drain(); env.$('applyB').click();
  assert.equal(env.api.shotData('s1', 'B').origin, undefined);
  // a manually staged take is untagged
  assert.equal(env.api.shotData('s1', 'A').origin, undefined);
});

test('origin: after a 503 the user can explicitly choose the sample, and it is tagged only then', async () => {
  const env = await twoTakes();
  env.$('instr').value = 'z'; env.$('gen').click();
  env.take('/api/production/brainstorm').resolve(jsonResponse({ detail: 'down' }, 503)); await drain();
  assert.equal(env.api.shotData('s1', 'B').origin, undefined); assert.equal(env.api.S.pending, null);
  env.$('loadSample').click(); assert.equal(env.api.S.pending.shot.origin, 'authored-sample');
  assert.equal(env.api.shotData('s1', 'B').origin, undefined);          // review only: nothing tagged before Apply
});

test('origin: Project JSON saves it per take, Project JSON import restores it, and bad values are refused', async () => {
  const env = await sampleOnB();
  const snap = env.api.exportSnapshot(), v = snap.scenes[0].variants;
  assert.equal(v.B.origin, 'authored-sample'); assert.equal('origin' in v.A, false);
  assert.equal(snap.scenes[0].staging.origin, undefined);               // active take A
  env.api.setVariant('B'); assert.equal(env.api.exportSnapshot().scenes[0].staging.origin, 'authored-sample');
  env.$('expJson').click(); const file = env.downloads.find((d) => d.name === 'typecast-project.json');
  const text = await blobText(file.blob);
  assert.equal(JSON.parse(text).scenes[0].variants.B.origin, 'authored-sample');
  // import into a fresh app
  const fresh = boot();
  await buildScript(fresh, 'INT. KITCHEN | first\nINT. OFFICE | second', [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b')]);
  const { job, body } = await startImport(fresh, text);
  job.resolve(jsonResponse(planFor(body, [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b')]))); await drain();
  assert.equal(fresh.api.shotData('s1', 'B').origin, 'authored-sample');
  assert.equal(fresh.api.shotData('s1', 'A').origin, undefined);
  // a hand-edited file may not smuggle a free-text or look-alike origin
  for (const bad of ['AI', 'ai-generated', 'authored sample', { x: 1 }, 7]) {
    const tampered = JSON.parse(text); tampered.scenes[0].variants.B.origin = bad;
    const again = boot();
    await buildScript(again, 'INT. KITCHEN | first\nINT. OFFICE | second', [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_b', 'shot_b')]);
    for (const name of ['Object', 'Array', 'JSON']) delete again.context[name];
    vm.runInContext(PROJECT_JS, again.context, { filename: 'director-project.js' });
    assert.throws(() => again.context.TypecastProject.normalizeProject(JSON.stringify(tampered)), /unsupported take origin/);
  }
});

test('origin: PNG, shoot pack and reel snapshot of a sample-derived take carry the tag', async () => {
  const env = await sampleOnB();
  env.api.setVariant('B');
  const cv = env.$('stage'), orig = cv.toBlob.bind(cv); let atExport = '';
  cv.toBlob = (cb, type) => { atExport = painted(env); orig(cb, type); };
  env.drawLog.length = 0; env.$('expPng').click(); await drain();
  assert.ok(atExport.includes(TAG), 'PNG pixels were drawn with the tag');
  env.drawLog.length = 0; env.$('expPack').click(); await drain();
  const pack = env.downloads.find((d) => d.name.endsWith('.html')); const html = await blobText(pack.blob);
  assert.match(html, /AUTHORED SAMPLE: pre-written blocking, not AI-generated/); assert.ok(tagDrawn(env), 'pack staged image drawn with the tag');
  // reel input -> snapshot keeps origin; drawing a reel frame with that shot paints the tag
  const reel = (await import('../director-reel.js')).default ?? (await import('../director-reel.js'));
  const R = reel.buildSnapshot ? reel : reel.default;
  const snap = R.buildSnapshot({ variant: 'B', scenes: [{ id: 's1', heading: 'h', shot_id: 'shot_a', prov: 'p', shot: env.api.shotData('s1', 'B') }] });
  assert.equal(snap.scenes[0].shot.origin, 'authored-sample');
  const bogus = R.buildSnapshot({ variant: 'B', scenes: [{ id: 's1', heading: 'h', shot_id: 'shot_a', prov: 'p', shot: { ...env.api.shotData('s1', 'B'), origin: 'AI' } }] });
  assert.equal(bogus.scenes[0].shot.origin, undefined);
  env.drawLog.length = 0;
  env.api.drawStage(env.$('stage').getContext('2d'), 1280, 720, { imgEl: null, missing: '', prov: 'p', shot: snap.scenes[0].shot, t: 1, editing: false, sel: -1 });
  assert.ok(tagDrawn(env), 'reel frame drawn with the tag');
});

test('origin: compare strip captions name the sample-derived take in readable HTML text', async () => {
  const env = await sampleOnB();
  env.$('cmpAB').click();
  assert.match(env.$('compareStrip').textContent, /Take B · 5s · AUTHORED SAMPLE · not AI/);
  assert.doesNotMatch(env.$('compareStrip').textContent, /Take A \(active\) · \d+s · AUTHORED/);
  assert.ok(painted(env).includes('authored sample'));
});

// ---------- production decisions: fit check, location swap, notes/continuity, decision sheet ----------
const ROWS = () => [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_a', 'shot_a2')];
const POOL = () => [...ROWS(), assignment('s1', 'prop_b', 'shot_b'), assignment('s2', 'prop_b', 'shot_b2')];
const SCRIPT2 = 'INT. KITCHEN - DAY | a bright kitchen at least 100 m2, windows, quiet\nINT. OFFICE - NIGHT | an office';
async function swapEnv(extra = {}) {
  const env = boot();
  await buildScript(env, SCRIPT2, ROWS(), { candidates: POOL(), evidence: { shot: { room_area_m2: 60 } }, ...extra });
  env.api.selectScene('s1');
  env.$('addActor').click(); env.$('dlg').value = 'MARA: hello'; env.$('dlg').dispatchEvent({ type: 'input' });
  env.$('dur').value = '7'; env.$('dur').dispatchEvent({ type: 'input' });
  env.api.setVariant('B'); env.$('loadSample').click(); env.$('applyB').click(); env.api.setVariant('A');
  return env;
}
const cur = (env, sid = 's1') => env.api.S && env.api.shotData(sid);
const checksText = (env) => env.$('checksSummary').textContent + '\n' + env.$('checksBody').textContent;

test('decisions: the fit check shows evidence-linked rows, never a score, and keeps unknowns unknown', async () => {
  const env = await swapEnv();
  assert.equal(env.$('sceneChecks').hidden, false);
  assert.match(env.$('checksSummary').textContent, /^Fit check · 1 conflict · 3 unknown/);
  const body = env.$('checksBody').textContent;
  assert.match(body, /Visual similarity: Looks like your description\. Image similarity 0\.42\. .*not a fit score/);
  assert.match(body, /Conflict: Floor area\. .*at least 100 m2.*index estimate is 60\.0 m²/);
  assert.match(body, /Unknown: Listing availability/); assert.match(body, /Unknown: Details in your script\. .*window/);
  assert.match(body, /Unknown: Quiet\. .*no sound measurement/);
  assert.equal(/\d\s?%/.test(checksText(env)), false);
  env.api.selectScene('s2');                                        // a scene with no stated needs stays quiet
  assert.match(env.$('checksSummary').textContent, /0 conflicts/);
});

test('decisions: swap keeps both takes, durations, dialogue and origin, and marks them unreviewed on the new exact frame', async () => {
  const env = await swapEnv();
  const aBefore = JSON.stringify(env.api.shotData('s1', 'A')), bBefore = JSON.stringify(env.api.shotData('s1', 'B'));
  assert.deepEqual(copied(env.api.altChoices('s1').map((c) => c.shot.shot_id)), ['shot_b']);
  env.api.swapLocation('s1', 'shot_b');
  const a = env.api.S.resp.plans[0].assignments[0];
  assert.equal(a.shot_id, 'shot_a');                                    // the solver's plan itself is untouched
  assert.equal(env.api.shotData('s1', 'A').dialogue, 'MARA: hello');
  assert.equal(JSON.stringify(env.api.shotData('s1', 'A')), aBefore); assert.equal(JSON.stringify(env.api.shotData('s1', 'B')), bBefore);
  assert.equal(env.api.shotData('s1', 'B').origin, 'authored-sample'); assert.equal(env.api.shotData('s1', 'A').duration_sec, 7);
  assert.ok(env.api.S.edits['s1::shot_a'], 'old frame staging still exists');
  assert.deepEqual(JSON.parse(JSON.stringify(env.api.S.transfer['s1::shot_b'])), { from_shot_id: 'shot_a', from_property_id: 'prop_a', reviewed: false });
  assert.equal(env.$('swapNotice').hidden, false);
  assert.match(env.$('swapNotice').textContent, /prop_a → prop_b\. Takes copied to this frame for review\. Review stand-in placement; room fit remains unverified\./);
  assert.doesNotMatch(env.$('swapNotice').textContent, /Fit stays uncalibrated|until you confirm|NOT verified against/);   // confirming never calibrates anything
  assert.match(env.$('swapNotice').textContent, /earlier scan identity does not apply.*source warnings and provenance labels stay as shown/);
  assert.match(env.$('planSel').childNodes[0]?.textContent || env.$('stagePlanSummary').textContent, /swapped by hand, totals not recalculated/);
  env.drawLog.length = 0; env.api.setVariant('A');
  assert.ok(painted(env).includes('STAGING CARRIED OVER · UNREVIEWED ON THIS FRAME'));
  assert.equal(env.api.viewShot('s1').carried, true);
  const snap = env.api.exportSnapshot();
  assert.deepEqual(snap.scenes[0].location_choice, { shot_id: 'shot_b', property_id: 'prop_b', from_shot_id: 'shot_a', from_property_id: 'prop_a', staging_reviewed: false });
  assert.equal(snap.scenes[0].evidence.frame.shot_id, 'shot_b'); assert.equal(snap.company_moves, null);
  assert.match(snap.plan_note, /not recalculated/);
  assert.equal('carried' in snap.scenes[0].variants.A, false);          // transient flag never leaks into the file
  assert.equal(snap.scenes[0].variants.B.origin, 'authored-sample');
});

test('decisions: confirming review clears the carried label; undo and back-to-planned never delete staging', async () => {
  const env = await swapEnv();
  env.api.swapLocation('s1', 'shot_b');
  const confirm = env.$('swapNotice').querySelectorAll('button').find((b) => /looks right/.test(b.textContent));
  confirm.click();
  assert.equal(env.api.S.transfer['s1::shot_b'].reviewed, true);
  env.drawLog.length = 0; env.api.setVariant('A'); assert.equal(painted(env).includes('CARRIED OVER'), false);
  assert.equal(env.api.exportSnapshot().scenes[0].location_choice.staging_reviewed, true);
  // edit on the swapped frame, go back, edits stay with their frame
  env.$('dlg').value = 'edited on new frame'; env.$('dlg').dispatchEvent({ type: 'input' });
  env.$('swapNotice').querySelectorAll('button').find((b) => /Back to planned/.test(b.textContent)).click();
  assert.equal(env.api.shotData('s1', 'A').dialogue, 'MARA: hello');
  assert.equal(env.api.S.edits['s1::shot_b'].A.dialogue, 'edited on new frame');
  env.api.swapLocation('s1', 'shot_b');                                 // swapping again finds that work and does not overwrite it
  assert.equal(env.api.shotData('s1', 'A').dialogue, 'edited on new frame');
  env.$('swapNotice').querySelectorAll('button').find((b) => /Undo swap/.test(b.textContent)).click();
  assert.equal(env.api.validSwap('s1'), null); assert.equal(env.api.S.edits['s1::shot_b'].A.dialogue, 'edited on new frame');
});

test('decisions: empty pool shows a disabled-state explanation and no swap; busy plans refuse swaps', async () => {
  const env = boot();
  await buildScript(env, SCRIPT2, ROWS());                              // one property only
  env.api.selectScene('s1');
  assert.deepEqual(copied(env.api.altChoices('s1')), []);
  assert.match(env.$('framePicker').textContent, /Try another location \(0\)/); assert.match(env.$('framePicker').textContent, /No other eligible location/);
  env.api.swapLocation('s1', 'shot_a2');
  assert.equal(env.api.validSwap('s1'), null);
  const e2 = await swapEnv(); e2.$('build').click();                    // a replan is in flight
  e2.api.swapLocation('s1', 'shot_b'); assert.equal(e2.api.validSwap('s1'), null); assert.match(e2.$('status').textContent, /Wait for the new plan/);
});

test('decisions: a rejected location never returns through swap, and replans clear swaps', async () => {
  const env = await swapEnv();
  env.api.swapLocation('s1', 'shot_b');
  env.$('reject').click();                                              // rejects the swapped property, prop_b
  assert.deepEqual(copied(env.api.S.forbidden), ['prop_b']);
  // while the replan is still in flight the response still lists prop_b: it must already be unusable
  assert.equal(env.api.validSwap('s1'), null); assert.equal(env.api.altChoices('s1').some((c) => c.shot.property_id === 'prop_b'), false);
  assert.doesNotMatch(env.$('rail').textContent, /swapped/);
  // replan fails: the swap is no longer honoured and the rejected property is not offered
  env.take('/api/production/plan').resolve(jsonResponse({ detail: 'down' }, 503)); await drain();
  assert.equal(env.api.validSwap('s1'), null);
  assert.equal(JSON.stringify(env.api.altChoices('s1')).includes('prop_b'), false);
  // a stale backend that still returns it is cleaned and cannot be swapped to
  env.$('reject').click();
  const job = env.take('/api/production/plan');
  job.resolve(jsonResponse(planFor(JSON.parse(job.opts.body), ROWS(), { candidates: POOL() }))); await drain();
  assert.equal(env.api.altChoices('s1').some((c) => c.shot.property_id === 'prop_b'), false);
  env.api.swapLocation('s1', 'shot_b'); assert.equal(env.api.validSwap('s1'), null);
  assert.deepEqual({ ...env.api.S.swaps }, {});                         // a new plan always clears hand swaps
});

test('decisions: the frame picker inside a swapped property keeps the swap instead of reverting it', async () => {
  const env = await swapEnv({ candidates: [...POOL(), assignment('s1', 'prop_b', 'shot_b3')] });
  env.api.swapLocation('s1', 'shot_b');
  const select = env.$('framePicker').querySelector('select'); select.value = 'shot_b3'; select.dispatchEvent({ type: 'change' });
  assert.equal(env.api.validSwap('s1').shot_id, 'shot_b3'); assert.equal(env.api.validSwap('s1').property_id, 'prop_b');
});

test('decisions: notes are bounded and sanitized; continuity stays silent until explicitly linked', async () => {
  const env = await swapEnv();
  assert.doesNotMatch(env.$('rail').textContent, /continuity note/); assert.doesNotMatch(env.$('checksBody').textContent, /Continuity/);
  env.$('noteDressing').value = `${'x'.repeat(700)}\u0000`; env.$('noteDressing').dispatchEvent({ type: 'input' });
  assert.equal(env.api.S.notes.s1.dressing.length, 600); assert.equal(env.api.S.notes.s1.dressing.includes('\u0000'), false);
  env.$('noteGroup').value = 'a b!c'; env.$('noteGroup').dispatchEvent({ type: 'input' });
  assert.equal(env.api.S.notes.s1.group, 'abc');
  assert.equal(env.jobs.length, 0, 'notes never trigger a request');
  // linking scenes in different properties is a verified mismatch; a link of one scene does nothing
  assert.doesNotMatch(env.$('rail').textContent, /continuity note/);
  env.api.selectScene('s2'); env.api.swapLocation('s2', 'shot_b2');
  env.$('noteGroup').value = 'abc'; env.$('noteGroup').dispatchEvent({ type: 'input' });
  assert.match(env.$('rail').textContent, /continuity note/);
  assert.match(env.$('checksBody').textContent, /Mismatch: Scenes 1 and 2 \(link "abc"\) use different properties \(prop_a and prop_b\)/);
  assert.match(env.$('checksBody').textContent, /Next: Try another location/);
  env.$('noteGroup').value = ''; env.$('noteGroup').dispatchEvent({ type: 'input' });
  assert.doesNotMatch(env.$('rail').textContent, /continuity note/);
});

test('decisions: same-frame position continuity needs the same exact frame, and exports reflect it', async () => {
  const env = boot();
  await buildScript(env, 'INT. A - DAY | one\nINT. A - DAY | two', [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_a', 'shot_a')]);
  for (const sid of ['s1', 's2']) {
    env.api.selectScene(sid); env.$('addActor').click(); env.$('aName').value = 'Mara'; env.$('aName').dispatchEvent({ type: 'input' });
    env.$('noteGroup').value = 'k'; env.$('noteGroup').dispatchEvent({ type: 'input' });
  }
  const a = env.api.shotData('s1').actors[0], b = env.api.shotData('s2').actors[0];
  Object.assign(a, { x0: .2, y0: .8, x1: .85, y1: .8 }); Object.assign(b, { x0: .2, y0: .8, x1: .2, y1: .8 });
  env.api.selectScene('s2');
  assert.match(env.$('checksBody').textContent, /Possible mismatch: .*Mara ends scene 1 at \(0\.85, 0\.80\) and starts scene 2 at \(0\.20, 0\.80\)/);
  const d = env.api.decisionFor('s2');
  assert.ok(d.checklist.some((x) => /^Continuity \(potential\)/.test(x)));
});

test('decisions: the shoot pack carries the decision sheet, escapes notes, lists both takes and leaks no contact or address', async () => {
  const env = await swapEnv();
  env.api.swapLocation('s1', 'shot_b');
  env.$('noteDressing').value = `${XSS} <script>alert(1)</script> add a calendar`; env.$('noteDressing').dispatchEvent({ type: 'input' });
  env.$('expPack').click(); await drain();
  const html = await blobText(env.downloads.find((d) => d.name.endsWith('.html')).blob);
  assert.ok(html.includes('Production decision sheet · scene 1'));
  assert.ok(html.includes('contains no prices, permissions, owner contact or confirmation that a set is feasible'));
  assert.ok(html.includes('Property prop_b, frame shot_b. Chosen by hand from the candidate pool instead of prop_a'));
  assert.ok(html.includes('Staging was carried over from another frame and has NOT been reviewed'));
  assert.ok(html.includes('Take A: 7s, 1 stand-in, line: MARA: hello.')); assert.ok(html.includes('AUTHORED SAMPLE (pre-written, not AI-generated)'));
  assert.ok(html.includes('Conflict: Floor area.')); assert.ok(html.includes('On-site checklist'));
  assert.ok(html.includes('Re-stage the carried-over blocking'));
  assert.ok(html.includes('add a calendar')); assert.equal(html.includes(XSS), false); assert.equal(html.includes('<script>alert(1)'), false);
  assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
  for (const leak of ['FAKE', 'sk-live', 'licensed.jpg', '/Users/demo', 'listing contact']) assert.equal(html.includes(leak), false, leak);
  assert.ok(html.includes('@media print')); assert.ok(html.includes('page-break-inside'));
  assert.ok(html.includes('system-ui') && !html.includes('Georgia') && html.includes('max-width:72ch'));   // local system sans, bounded line length
  assert.ok(env.drawLog.some((e) => e.m === 'fillText' && String(e.args[0]).includes('STAGING CARRIED OVER')), 'pack staged image carries the stamp');
});

test('decisions: project JSON round trip restores the swap, unreviewed state and notes; a pool without that frame retains them for review', async () => {
  const env = await swapEnv();
  env.api.swapLocation('s1', 'shot_b');
  env.$('noteDressing').value = 'keep the plant'; env.$('noteDressing').dispatchEvent({ type: 'input' });
  env.$('expJson').click(); const text = await blobText(env.downloads.find((d) => d.name === 'typecast-project.json').blob);
  const saved = JSON.parse(text);
  assert.equal(saved.scenes[0].notes.dressing, 'keep the plant'); assert.equal(saved.scenes[0].location_choice.staging_reviewed, false);
  const fresh = boot();
  await buildScript(fresh, SCRIPT2, ROWS(), { candidates: POOL() });
  const { job, body } = await startImport(fresh, text);
  job.resolve(jsonResponse(planFor(body, ROWS(), { candidates: POOL() }))); await drain();
  assert.equal(fresh.api.validSwap('s1').shot_id, 'shot_b');
  assert.equal(fresh.api.S.transfer['s1::shot_b'].reviewed, false);
  assert.equal(fresh.api.S.notes.s1.dressing, 'keep the plant');
  assert.equal(fresh.api.shotData('s1', 'A').dialogue, 'MARA: hello'); assert.equal(fresh.api.shotData('s1', 'B').origin, 'authored-sample');
  assert.equal(fresh.api.S.forbidden.length, 0);
  // the new pool no longer offers shot_b: nothing is swapped, work is kept for review, notes still restored
  const gone = boot();
  await buildScript(gone, SCRIPT2, ROWS(), { candidates: ROWS() });
  const second = await startImport(gone, text);
  second.job.resolve(jsonResponse(planFor(second.body, ROWS(), { candidates: ROWS() }))); await drain();
  assert.equal(gone.api.validSwap('s1'), null); assert.equal(gone.api.S.importReview.length, 1);
  assert.equal(gone.api.S.notes.s1.dressing, 'keep the plant');
  // an ineligible candidate is not accepted either
  const bad = boot();
  await buildScript(bad, SCRIPT2, ROWS(), { candidates: POOL() });
  const third = await startImport(bad, text);
  const resp = planFor(third.body, ROWS(), { candidates: POOL() });
  resp.scenes[0].candidates.find((c) => c.shot.shot_id === 'shot_b').eligible = false;
  third.job.resolve(jsonResponse(resp)); await drain();
  assert.equal(bad.api.validSwap('s1'), null);
});

test('decisions: swaps are refused while an import loads, so a late import never meets a half-applied swap', async () => {
  const env = await swapEnv();
  const file = JSON.stringify({ app: 'Typecast Director', variant: 'A', scenes: [{ id: 's1', heading: 'INT. KITCHEN - DAY', description: 'x', evidence: { frame: { shot_id: 'shot_a', property_id: 'prop_a' } },
    variants: { A: { duration_sec: 5, dialogue: 'IMPORTED', actors: [] }, B: { duration_sec: 5, dialogue: '', actors: [] } } }] });
  const { job, body } = await startImport(env, file);
  env.api.swapLocation('s1', 'shot_b');                                  // the user clicks while the evidence loads
  assert.equal(env.api.validSwap('s1'), null); assert.match(env.$('status').textContent, /Wait for the new plan/);
  job.resolve(jsonResponse(planFor(body, ROWS(), { candidates: POOL() }))); await drain();
  assert.equal(env.api.shotData('s1', 'A').dialogue, 'IMPORTED'); assert.equal(env.api.validSwap('s1'), null);
  // the swap stayed out of the way: now (idle) it works on the imported state
  env.api.swapLocation('s1', 'shot_b'); assert.equal(env.api.validSwap('s1').shot_id, 'shot_b');
});

test('decisions: malformed production fields are refused or neutralized on import', async () => {
  const P = (await import('../director-project.js')).default;
  const base = (scene) => JSON.stringify({ app: 'Typecast Director', variant: 'A', scenes: [{ id: 's1', heading: 'h', description: 'd', evidence: { frame: { shot_id: 'a', property_id: 'p' } },
    variants: { A: { duration_sec: 5, dialogue: '', actors: [] }, B: { duration_sec: 5, dialogue: '', actors: [] } }, ...scene }] });
  const ok = { shot_id: 'b', property_id: 'q', from_shot_id: 'a', from_property_id: 'p', staging_reviewed: false };
  assert.equal(P.normalizeProject(base({ location_choice: ok })).scenes[0].location_choice.staging_reviewed, false);
  for (const bad of [{ ...ok, staging_reviewed: 'no' }, { ...ok, shot_id: '../x' }, { ...ok, property_id: 'a b' }, { ...ok, from_shot_id: 3 }, 'str', [], { ...ok, staging_reviewed: undefined }])
    assert.throws(() => P.normalizeProject(base({ location_choice: bad })), /Invalid project/);
  assert.throws(() => P.normalizeProject(JSON.stringify({ app: 'Typecast Director', variant: 'A', scenes: [{ id: 's1', heading: 'h', description: 'd', location_choice: ok }] })), /saved frame identity/);
  for (const bad of [{ dressing: 'x'.repeat(601) }, { group: 'a b' }, { group: 'x'.repeat(13) }, { dressing: 5 }, 'text'])
    assert.throws(() => P.normalizeProject(base({ notes: bad })), /Invalid project/);
  const clean = P.normalizeProject(base({ notes: { dressing: 'a\u0000b\u001fc', group: 'k_1' } })).scenes[0].notes;
  assert.deepEqual(JSON.parse(JSON.stringify(clean)), { dressing: 'abc', group: 'k_1' });
  assert.equal('notes' in P.normalizeProject(base({})).scenes[0], false);   // absent stays absent (old files migrate unchanged)
});

test('decisions: reel input for a carried-over take is flagged so the WebM frames carry the stamp', async () => {
  const env = await swapEnv();
  env.api.swapLocation('s1', 'shot_b');
  const R = (await import('../director-reel.js')).default;
  const snap = R.buildSnapshot({ variant: 'A', scenes: [{ id: 's1', heading: 'h', shot_id: 'shot_b', prov: 'p', shot: env.api.sanitizeShot(env.api.viewShot('s1'), true) }] });
  assert.equal(snap.scenes[0].shot.carried, true);
  const plain = R.buildSnapshot({ variant: 'A', scenes: [{ id: 's1', heading: 'h', shot_id: 'shot_b', prov: 'p', shot: { duration_sec: 5, dialogue: '', actors: [], carried: 'yes' } }] });
  assert.equal(plain.scenes[0].shot.carried, undefined);
});

// ---------- independent-review regressions (stale build, both takes in the pack, swap destination staging) ----------
test('review: a plan answer for older script, constraints or rejections is never installed under newer inputs', async () => {
  const mk = async () => {
    const env = boot();
    await buildScript(env, 'INT. KITCHEN | original', [assignment('s1', 'prop_a', 'shot_a')]);
    env.$('addActor').click(); env.$('dlg').value = 'KEEP_THIS_TAKE'; env.$('dlg').dispatchEvent({ type: 'input' });
    return env;
  };
  const stale = async (change) => {
    const env = await mk();
    const before = copied({ scenes: env.api.S.scenes, resp: env.api.S.resp, built: env.api.S.built });
    env.$('script').value = 'INT. KITCHEN | original'; env.$('build').click();
    const job = env.take('/api/production/plan'), sent = JSON.parse(job.opts.body);
    change(env);
    job.resolve(jsonResponse(planFor(sent, [assignment('s1', 'prop_z', 'shot_z')])));
    await drain();
    assert.match(env.$('status').textContent, /built for your earlier script, constraints or rejections/);
    assert.deepEqual(copied({ scenes: env.api.S.scenes, resp: env.api.S.resp, built: env.api.S.built }), before, 'old plan, scenes and constraints kept');
    assert.equal(env.api.shotData('s1').dialogue, 'KEEP_THIS_TAKE');
    assert.equal(env.$('build').disabled, false, 'build is usable again');
    return env;
  };
  await stale((env) => { env.$('script').value = 'EXT. ROAD | newer script'; env.$('script').dispatchEvent({ type: 'input' }); });
  await stale((env) => { env.$('trucks').value = '5'; env.$('trucks').dispatchEvent({ type: 'input' }); });
  await stale((env) => { env.$('reqAvail').checked = true; });
  await stale((env) => { env.$('maxLoc').value = '1'; });
  // a rejection change while a replan is in flight is also stale
  const env = await mk();
  env.api.S.forbidden.push('prop_old');
  env.$('build').click(); const job = env.take('/api/production/plan');
  env.api.S.forbidden.length = 0;                                                       // Clear rejections during the request
  job.resolve(jsonResponse(planFor(JSON.parse(job.opts.body), [assignment('s1', 'prop_z', 'shot_z')]))); await drain();
  assert.match(env.$('status').textContent, /earlier script, constraints or rejections/);
  assert.equal(env.api.S.resp.plans[0].assignments[0].shot_id, 'shot_a');
  // unchanged inputs still install normally
  const ok = await mk(); ok.$('build').click();
  const j2 = ok.take('/api/production/plan'); j2.resolve(jsonResponse(planFor(JSON.parse(j2.opts.body), [assignment('s1', 'prop_z', 'shot_z')]))); await drain();
  assert.equal(ok.api.S.resp.plans[0].assignments[0].shot_id, 'shot_z');
});

test('review: the shoot pack exports both takes, with text, raster stamps and provenance for the inactive take too', async () => {
  const env = await swapEnv();                                      // A staged by hand; B is the authored sample
  env.api.swapLocation('s1', 'shot_b');                             // staging carried over and unreviewed
  assert.equal(env.api.S.variant, 'A');
  env.drawLog.length = 0; env.$('expPack').click(); await drain();
  const html = await blobText(env.downloads.find((d) => d.name.endsWith('.html')).blob);
  assert.ok(html.includes('Take A (active take) · 7s')); assert.ok(html.includes('Take B · 7s'));
  assert.ok(html.includes('Take B is derived from an AUTHORED SAMPLE')); assert.equal(html.includes('Take A is derived from an AUTHORED SAMPLE'), false);
  assert.ok(html.includes('Staged rehearsal frame, scene 1, take A')); assert.ok(html.includes('Staged rehearsal frame, scene 1, take B'));
  assert.ok(html.includes('Take A: 7s, 1 stand-in')); assert.ok(html.includes('Take B: 7s,'));
  const texts = env.drawLog.filter((e) => e.m === 'fillText').map((e) => String(e.args[0]));
  const stamp = (t) => texts.filter((x) => x === t).length;
  assert.equal(stamp('AUTHORED SAMPLE · not AI'), 1, 'the inactive sample take is stamped in its own staged image, once');
  assert.ok(stamp('STAGING CARRIED OVER · UNREVIEWED ON THIS FRAME') >= 2, 'both staged images of scene 1 carry the unreviewed stamp');
  assert.ok(texts.some((x) => /Variant B/.test(x)) && texts.some((x) => /Variant A/.test(x)), 'each image names its own take');
  // a carried but non-sample take: the review label does not depend on sample origin
  env.api.setVariant('B');
  env.$('expJson').click(); const saved = JSON.parse(await blobText(env.downloads.find((d) => d.name === 'typecast-project.json').blob));
  assert.equal(saved.scenes[0].location_choice.staging_reviewed, false);
  env.$('swapNotice').querySelectorAll('button').find((b) => /looks right/.test(b.textContent)).click();
  env.drawLog.length = 0; env.$('expPack').click(); await drain();
  assert.equal(env.drawLog.some((e) => e.m === 'fillText' && String(e.args[0]).includes('CARRIED OVER')), false, 'review clears the stamp from both takes');
});

test('review: swapping into a frame that already holds other staging keeps it, says so, and every version stays recoverable', async () => {
  const env = await swapEnv();
  env.api.swapLocation('s1', 'shot_b');
  const firstCopy = JSON.stringify(env.api.S.edits['s1::shot_b']);
  env.$('swapNotice').querySelectorAll('button').find((b) => /Undo swap/.test(b.textContent)).click();
  env.$('dlg').value = 'A edited after undo'; env.$('dlg').dispatchEvent({ type: 'input' });
  const newerA = JSON.stringify(env.api.S.edits['s1::shot_a']);
  env.api.swapLocation('s1', 'shot_b');                              // destination already holds the earlier copy
  assert.equal(JSON.stringify(env.api.S.edits['s1::shot_b']), firstCopy, 'earlier destination staging is not overwritten');
  assert.match(env.$('swapNotice').textContent, /already had its own staging, so it was kept; your current takes were not copied\. Room fit remains unverified/);
  assert.doesNotMatch(env.$('swapNotice').textContent, /Takes copied to this frame/);   // the main sentence must not claim a copy that did not happen
  const label = (re) => env.$('swapNotice').querySelectorAll('button').find((b) => re.test(b.textContent));
  assert.ok(label(/Use my current takes here instead/));
  label(/Use my current takes here instead/).click();
  assert.equal(env.api.shotData('s1', 'A').dialogue, 'A edited after undo');
  assert.equal(env.api.S.transfer['s1::shot_b'].reviewed, false);
  assert.match(env.$('swapNotice').textContent, /second saved staging exists.*session only/);
  assert.equal(JSON.stringify(env.api.S.alt['s1::shot_b'].edits), firstCopy, 'the replaced staging is stashed, not deleted');
  label(/Switch to the other saved staging/).click();
  assert.equal(JSON.stringify(env.api.S.edits['s1::shot_b']), firstCopy);
  label(/Switch to the other saved staging/).click();
  assert.equal(env.api.shotData('s1', 'A').dialogue, 'A edited after undo');
  assert.equal(JSON.stringify(env.api.S.edits['s1::shot_a']), newerA, 'the source frame staging never changed');
  // reviewing says what review means
  env.$('swapNotice').querySelectorAll('button').find((b) => /looks right/.test(b.textContent)).click();
  assert.match(env.$('swapNotice').textContent, /artistic alignment, not a survey: room fit remains unverified/);
});

test('review: prototype-like scene ids, notes and links import and render without errors', async () => {
  const env = boot();
  await buildScript(env, 'INT. A - DAY | one\nINT. B - DAY | two', [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_a', 'shot_a')]);
  for (const g of ['constructor', '__proto__']) {
    env.api.selectScene('s1'); env.$('noteGroup').value = g; env.$('noteGroup').dispatchEvent({ type: 'input' });
    env.api.selectScene('s2'); env.$('noteGroup').value = g; env.$('noteGroup').dispatchEvent({ type: 'input' });
    assert.equal(env.api.S.notes.s1.group, g); assert.equal(Object.getPrototypeOf(env.api.S.notes), null);
    env.api.selectScene('s1'); assert.doesNotMatch(env.$('checksBody').textContent, /Mismatch/);   // same frame, no actors: nothing to flag
  }
  env.$('expJson').click(); const text = await blobText(env.downloads.find((d) => d.name === 'typecast-project.json').blob);
  const fresh = boot();
  await buildScript(fresh, 'INT. A - DAY | one\nINT. B - DAY | two', [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_a', 'shot_a')]);
  const { job, body } = await startImport(fresh, text);
  job.resolve(jsonResponse(planFor(body, [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_a', 'shot_a')]))); await drain();
  assert.equal(fresh.api.S.notes.s2.group, '__proto__');
  fresh.api.selectScene('s2'); assert.ok(fresh.$('sceneChecks').hidden === false);
});

// ---------- natural screenplay intake in the UI ----------
test('intake: a pasted screenplay shows a reviewable reading, builds from exactly those scenes and keeps dialogue in the text', async () => {
  const env = boot();
  env.$('script').value = 'TITLE PAGE\r\n\r\nINT. KITCHEN - DAY\r\nMARA stirs.\r\nMARA\r\nI wrote this for you.\r\n\r\nEXT. GARDEN - NIGHT\r\nRain.';
  env.$('script').dispatchEvent({ type: 'input' });
  const text = env.$('parseSummary').textContent;
  assert.match(text, /Reads as 2 scenes · 1 note/); assert.match(text, /INT\. KITCHEN - DAY.*1 dialogue line kept in the text/); assert.match(text, /1 line before the first heading was not used/);
  env.$('build').click();
  const job = env.take('/api/production/plan'), body = JSON.parse(job.opts.body);
  assert.deepEqual(copied(body.scenes), [
    { id: 's1', heading: 'INT. KITCHEN - DAY', description: 'MARA stirs. MARA I wrote this for you.' },
    { id: 's2', heading: 'EXT. GARDEN - NIGHT', description: 'Rain.' }]);
  assert.equal(JSON.stringify(body).includes('actors'), false, 'no actors are invented from dialogue');
  job.resolve(jsonResponse(planFor(body, [assignment('s1', 'p', 'sa'), assignment('s2', 'p', 'sb')]))); await drain();
  assert.equal(env.api.S.scenes.length, 2);
});

test('intake: errors and cuts are visible before Build and Build refuses with the same message', async () => {
  const env = boot();
  env.$('script').value = Array.from({ length: 9 }, (_, i) => `INT. R${i} - DAY\ntext`).join('\n');
  env.$('script').dispatchEvent({ type: 'input' });
  assert.match(env.$('parseSummary').textContent, /Max 8 scenes \(found 9\)/);
  env.$('build').click();
  assert.match(env.$('status').textContent, /Max 8 scenes \(found 9\)/); assert.equal(env.jobs.length, 0);
  env.$('script').value = `INT. HALL - DAY\n${'word '.repeat(300)}`; env.$('script').dispatchEvent({ type: 'input' });
  assert.match(env.$('parseSummary').textContent, /1 note/); assert.match(env.$('parseSummary').textContent, /cut to fit/);
  env.$('script').value = 'just some words\n'.repeat(20); env.$('script').dispatchEvent({ type: 'input' });
  assert.match(env.$('parseSummary').textContent, /No scene headings found/);
});

// ---------- community planning mode ----------
const NEEDS = 'Supply hub\nLarge open floor for volunteers, at least 100 m2, loading access for trucks\n\nCheck-in room\nA quiet room with restrooms and water for 30 volunteers';
const CROWS = () => [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_a', 'shot_a2')];
const CPOOL = () => [...CROWS(), assignment('s1', 'prop_b', 'shot_b'), assignment('s2', 'prop_b', 'shot_b2')];
async function commEnv(extra = {}) {
  const env = boot();
  env.$('modeComm').click();
  await buildScript(env, NEEDS, CROWS(), { candidates: CPOOL(), evidence: { shot: { room_area_m2: 600 } }, ...extra });
  env.api.selectScene('s1');
  return env;
}
const checkSelects = (env) => env.$('siteChecks').querySelectorAll('select');
const setCheck = (env, i, value) => { const s = checkSelects(env)[i]; s.value = value; s.dispatchEvent({ type: 'change' }); };
const FILM_STRINGS = /stand-in|Take [AB]|dialogue|AUTHORED SAMPLE|rehears|screen-space|Variant [AB]|shoot pack|filming|film\b|actor|WebM|cinematic/i;

test('community: the mode control separates drafts; film work is untouched and community starts empty', async () => {
  const env = boot();
  await buildScript(env, 'INT. KITCHEN - DAY | a kitchen', [assignment('s1', 'prop_f', 'shot_f')]);
  env.$('addActor').click(); env.$('dlg').value = 'FILM_LINE'; env.$('dlg').dispatchEvent({ type: 'input' });
  env.$('trucks').value = '3';
  const filmScenes = JSON.stringify(env.api.S.scenes), filmEdits = JSON.stringify(env.api.S.edits);
  env.$('modeComm').click();
  assert.equal(env.api.S.mode, 'community'); assert.equal(env.$('script').value, ''); assert.equal(env.api.S.scenes.length, 0);
  assert.equal(env.api.S.resp, null); assert.equal(JSON.stringify(env.api.S.edits), '{}'); assert.equal(env.$('trucks').value, '0');
  assert.equal(env.$('h-script').textContent, 'Site needs'); assert.equal(env.$('build').textContent, 'Find candidate sites');
  assert.equal(env.$('expPack').textContent, 'Site brief (printable)'); assert.equal(env.$('lblTrucks').textContent, 'Supply trucks');
  await buildScript(env, NEEDS, CROWS());
  env.api.selectScene('s1'); env.$('siteNote').value = 'community note'; env.$('siteNote').dispatchEvent({ type: 'input' });
  env.$('modeFilm').click();
  assert.equal(env.api.S.mode, 'film'); assert.equal(JSON.stringify(env.api.S.scenes), filmScenes); assert.equal(JSON.stringify(env.api.S.edits), filmEdits);
  assert.equal(env.$('trucks').value, '3'); assert.equal(env.$('build').textContent, 'Build plan'); assert.equal(env.api.shotData('s1').dialogue, 'FILM_LINE');
  assert.equal(JSON.stringify(env.api.S.edits).includes('community'), false);
  env.$('modeComm').click();                                        // and back: the community draft is exactly as left
  assert.equal(env.api.S.scenes.length, 2); assert.equal(env.api.S.comm['need:s1'].note, 'community note'); assert.equal(env.api.S.edits[Object.keys(env.api.S.edits)[0]]?.A?.dialogue ?? '', '');
});

test('community: switching is refused while a plan is loading, and film controls are marked for hiding in community', async () => {
  const env = boot();
  env.$('script').value = 'INT. A - DAY | a'; env.$('build').click();
  env.$('modeComm').click();
  assert.equal(env.api.S.mode, 'film'); assert.match(env.$('status').textContent, /Wait for the plan or reel/);
  const html = readFileSync(join(DIR, '..', 'director.html'), 'utf8');
  for (const id of ['stage-modes', 'transport-play', 'prog', 'clock', 'addActor', 'lookAround', 'timeline', 'tab-shot', 'tab-alt', 'panel-shot', 'panel-alt', 'expReel', 'cancelReel', 'expPng', 'reelNote', 'compareStrip']) {
    const tag = ['stage-modes', 'transport-play'].includes(id) ? new RegExp(`<div class="${id}"[^>]*>`) : new RegExp(`<[^>]*id="${id}"[^>]*>`);
    const m = html.match(tag); assert.ok(m, id); assert.match(m[0], /data-film-only/, `${id} is film-only`);
  }
  for (const id of ['tab-site', 'panel-site', 'briefFields', 'commBanner']) assert.match(html.match(new RegExp(`<[^>]*id="${id}"[^>]*>`))[0], /data-community-only/, id);
  const css = readFileSync(join(DIR, '..', 'director.css'), 'utf8');
  assert.match(css, /\[data-mode="community"\] \[data-film-only\].*display: none !important/);
  assert.match(html, /<body data-mode="film">/);
});

test('community: coordinator checks are unknown by default, human-reported, and never become a safe or approved badge', async () => {
  const env = await commEnv();
  assert.equal(checkSelects(env).length, 7);
  assert.match(env.$('siteChecksSummary').textContent, /Needs verification · 7 of 7 checks unknown/);
  assert.match(env.$('siteChecks').textContent, /reported by you\. Typecast cannot verify it, and nothing marks a site approved/);
  for (const sel of checkSelects(env)) assert.equal(sel.value, 'unknown');
  setCheck(env, 0, 'ok'); setCheck(env, 2, 'issue');
  assert.match(env.$('siteChecksSummary').textContent, /5 of 7 checks unknown · 1 reported problem · 1 reported OK by you \(not verified\)/);
  for (let i = 0; i < 7; i++) setCheck(env, i, 'ok');
  const all = env.$('siteChecksSummary').textContent;
  assert.match(all, /0 of 7 checks unknown/); assert.match(all, /7 reported OK by you \(not verified\)/); assert.match(all, /^Coordinator checks · Needs verification/);
  assert.doesNotMatch(env.$('panel-site').textContent + env.$('checksBody').textContent, /\bsafe\b|approved site|certified|verified safe/i.source ? /(?<!not )(?<!nothing marks a site )\b(safe shelter|is safe|safe site|certified)\b/i : /x/);
  assert.equal(env.api.S.comm['site:s1::prop_a'].checks.permission.state, 'ok');
  assert.equal(env.$('siteReq').disabled, false);
});

test('community: a requested headcount is a request; verified capacity needs a stated source and is never computed', async () => {
  const env = await commEnv();
  env.$('siteReq').value = '40'; env.$('siteReq').dispatchEvent({ type: 'input' });
  assert.equal(env.api.S.comm['need:s1'].requested, 40);
  for (const bad of ['-5', '1.5', 'abc', '100001']) { env.$('siteReq').value = bad; env.$('siteReq').dispatchEvent({ type: 'input' }); assert.equal(env.api.S.comm['need:s1'].requested, null, bad); }
  env.$('siteReq').value = '40'; env.$('siteReq').dispatchEvent({ type: 'input' });
  env.$('siteCap').value = '120'; env.$('siteCap').dispatchEvent({ type: 'input' });
  assert.equal(env.api.S.comm['site:s1::prop_a'].verified, null, 'a number without a source is not kept');
  env.$('siteCapSrc').value = 'Fire marshal letter, 3 Nov'; env.$('siteCapSrc').dispatchEvent({ type: 'input' });
  assert.deepEqual(copied(env.api.S.comm['site:s1::prop_a'].verified), { capacity: 120, source: 'Fire marshal letter, 3 Nov' });
  env.$('siteCap').value = ''; env.$('siteCap').dispatchEvent({ type: 'input' }); assert.equal(env.api.S.comm['site:s1::prop_a'].verified, null);
  // 600 m2 of index area and a request of 40 produce no capacity, anywhere
  env.$('expPack').click(); await drain();
  const html = await blobText(env.downloads.find((d) => d.name === 'typecast-site-brief.html').blob);
  assert.ok(html.includes('Requested: 40 participants or volunteers (a request).'));
  assert.ok(html.includes('Independently verified capacity: none provided. Typecast does not calculate capacity from floor area, photos, listings or parking.'));
  assert.doesNotMatch(html, /capacity (is|of) \d|can hold|fits \d+|accommodat/i);
});

test('community: the Site Brief states needs, alternatives, unresolved checks and provenance, with no film wording and no leaked source fields', async () => {
  const env = await commEnv();
  env.$('siteReq').value = '40'; env.$('siteReq').dispatchEvent({ type: 'input' });
  setCheck(env, 1, 'issue'); env.$('siteChecks').querySelectorAll('input')[1].value = 'hall <b>2</b> cap unclear'; env.$('siteChecks').querySelectorAll('input')[1].dispatchEvent({ type: 'input' });
  env.$('taskAdd').click(); const ti = env.$('siteTasks').querySelectorAll('input'); ti[0].value = 'Call the facilities office'; ti[0].dispatchEvent({ type: 'input' }); ti[1].value = 'Ana'; ti[1].dispatchEvent({ type: 'input' });
  env.$('siteNote').value = `<script>alert(1)</script> loading dock on the east side`; env.$('siteNote').dispatchEvent({ type: 'input' });
  env.$('briefReviewer').value = 'R. Coordinator'; env.$('briefReviewer').dispatchEvent({ type: 'input' }); env.$('briefDate').value = '2026-11-14'; env.$('briefDate').dispatchEvent({ type: 'input' });
  env.$('expPack').click(); await drain();
  const html = await blobText(env.downloads.find((d) => d.name === 'typecast-site-brief.html').blob);
  for (const must of ['Typecast site brief · preparedness planning', 'not an approval of any site, not an emergency or evacuation plan', 'NEEDS VERIFICATION · 13 coordinator checks still unknown',
    'Reviewer: R. Coordinator', 'Review date: 2026-11-14', '1. Supply hub', '2. Check-in room', 'Requested participants or volunteers: 40. This is a request, not a capacity.',
    'Coordinator checks (reported by the coordinator, not verified by Typecast)', 'Reported problem', 'Call the facilities office (Ana)',
    'Other candidate sites in the pool (not assessed)', 'Property prop_b', 'Verification checklist', 'Establish: Owner permission and access.', 'Resolve: Verified occupancy and capacity',
    'Get the owner\'s permission and agree access before any use.', 'Indexed scan image from the source index. It is not a current photo of the site.', 'index estimate, not a capacity']) assert.ok(html.includes(must), must);
  assert.equal(html.includes('<b>2</b>'), false); assert.equal(html.includes('<script>alert'), false); assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
  assert.doesNotMatch(html.replace(/<style>[\s\S]*?<\/style>/, ''), FILM_STRINGS, 'no film-specific controls or labels in a community brief');
  for (const leak of ['FAKE', 'sk-live', 'licensed.jpg', '/Users/demo', 'listing contact']) assert.equal(html.includes(leak), false, leak);
  assert.match(html, /<meta http-equiv="Content-Security-Policy" content="default-src 'none'/);
});

test('community: the stage shows the real frame with a preparedness label and nothing film-specific', async () => {
  const env = await commEnv();
  env.drawLog.length = 0; env.api.selectScene('s2'); env.api.selectScene('s1');
  const texts = env.drawLog.filter((e) => e.m === 'fillText').map((e) => String(e.args[0]));
  assert.ok(texts.includes('PREPAREDNESS PLANNING · CANDIDATE SITE · NOT AN APPROVED SITE'));
  assert.equal(texts.some((t) => /UNCALIBRATED|REHEARSAL/.test(t)), false); assert.ok(texts.some((t) => /^Need 1 · Matterport · property prop_a/.test(t)));
  assert.equal(env.api.exportSnapshot().scenes[0].variants, null); assert.equal(env.api.exportSnapshot().scenes[0].staging, null);
  const cv = env.$('stage'); env.api.shotData('s1');                // pointer and key input cannot create film staging in community mode
  cv.dispatchEvent({ type: 'pointerdown', clientX: 100, clientY: 600, pointerId: 1 }); cv.dispatchEvent({ type: 'keydown', key: 'ArrowLeft' });
  assert.equal(env.api.shotData('s1').actors.length, 0);
});

test('community: fit evidence uses the same source rules and lists community needs as not in the data', async () => {
  const env = await commEnv();
  assert.match(env.$('checksSummary').textContent, /^Site fit evidence · /);
  const body = env.$('checksBody').textContent;
  assert.match(body, /Consistent \(estimated\): Floor area\. Your text says "at least 100 m2"\. The index estimate is 600\.0 m²/);   // an estimate, never a capacity
  assert.match(body, /Details in your needs\. Your text mentions .*(restroom|water|loading)/); assert.match(body, /toilets, power, water, ramps and similar are not in any source/);
  assert.doesNotMatch(body, /Continuity|your script/);
  assert.match(env.$('stageCaption').textContent, /Not an approved site/);
  assert.match(readFileSync(join(DIR, '..', 'director.html'), 'utf8'), /Not for real-time evacuation or emergency routing\. Nothing here approves a site, shelter or capacity/);
});

test('community: project JSON carries mode, brief, needs and per-site reports; import routes to the right mode, keeps film work and flags restored OK checks', async () => {
  const env = await commEnv();
  env.$('siteReq').value = '40'; env.$('siteReq').dispatchEvent({ type: 'input' }); setCheck(env, 0, 'ok'); env.$('siteChecks').querySelectorAll('input')[0].value = 'asked the owner'; env.$('siteChecks').querySelectorAll('input')[0].dispatchEvent({ type: 'input' });
  env.$('siteCap').value = '80'; env.$('siteCap').dispatchEvent({ type: 'input' }); env.$('siteCapSrc').value = 'owner email'; env.$('siteCapSrc').dispatchEvent({ type: 'input' });
  env.$('briefReviewer').value = 'Ana'; env.$('briefReviewer').dispatchEvent({ type: 'input' });
  env.api.selectScene('s2'); env.api.swapLocation('s2', 'shot_b2'); setCheck(env, 3, 'issue');
  env.$('expJson').click(); const text = await blobText(env.downloads.find((d) => d.name === 'typecast-project.json').blob);
  const saved = JSON.parse(text);
  assert.equal(saved.mode, 'community'); assert.equal(saved.brief.reviewer, 'Ana'); assert.deepEqual(saved.needs, [{ scene_id: 's1', requested_count: 40, note: '' }]);
  assert.equal(saved.sites.length, 2); assert.equal(saved.scenes[0].variants, null); assert.match(saved.honesty, /Coordinator checks are reported by a person and are not verified/);
  assert.equal(JSON.stringify(saved).includes('"approved"'), false);
  // import into a fresh app that is in FILM mode with work in it
  const fresh = boot();
  await buildScript(fresh, 'INT. KITCHEN - DAY | k', [assignment('s1', 'prop_f', 'shot_f')]);
  fresh.$('addActor').click(); fresh.$('dlg').value = 'FILM_KEEP'; fresh.$('dlg').dispatchEvent({ type: 'input' });
  const { job, body } = await startImport(fresh, text);
  assert.equal(body.scenes.length, 2);
  job.resolve(jsonResponse(planFor(body, CROWS(), { candidates: CPOOL(), evidence: { shot: { room_area_m2: 600 } } }))); await drain();
  assert.equal(fresh.api.S.mode, 'community'); assert.equal(fresh.$('script').value.includes('Supply hub'), true);
  assert.equal(fresh.api.S.comm['need:s1'].requested, 40); assert.equal(fresh.api.S.comm['site:s1::prop_a'].checks.permission.stale, true);
  assert.equal(fresh.api.S.comm['site:s1::prop_a'].verified.source, 'owner email'); assert.equal(fresh.api.S.brief.reviewer, 'Ana');
  fresh.api.selectScene('s1'); assert.match(fresh.$('siteChecks').textContent, /restored from a file; re-verify/);
  fresh.$('modeFilm').click(); assert.equal(fresh.api.shotData('s1').dialogue, 'FILM_KEEP'); assert.equal(fresh.$('script').value, 'INT. KITCHEN - DAY | k');
  // a film project imported while in community mode goes to film mode and leaves community alone
  fresh.$('modeComm').click(); const before = JSON.stringify(Object.keys(fresh.api.S.comm));
  const filmFile = JSON.stringify({ app: 'Typecast Director', variant: 'A', scenes: [{ id: 's1', heading: 'INT. A - DAY', description: 'x' }] });
  const second = await startImport(fresh, filmFile);
  second.job.resolve(jsonResponse(planFor(second.body, [assignment('s1', 'prop_f', 'shot_f')]))); await drain();
  assert.equal(fresh.api.S.mode, 'film'); fresh.$('modeComm').click(); assert.equal(JSON.stringify(Object.keys(fresh.api.S.comm)), before);
});

test('community: malformed or hostile community fields are refused; absent fields migrate unchanged', async () => {
  const P2 = (await import('../director-project.js')).default;
  const base = (extra) => JSON.stringify({ app: 'Typecast Director', variant: 'A', scenes: [{ id: 's1', heading: 'h', description: 'd' }], ...extra });
  const ok = P2.normalizeProject(base({ mode: 'community', brief: { reviewer: 'a\u0000b', date: '2026-11-14', notes: 'n' }, needs: [{ scene_id: 's1', requested_count: 5, note: '' }],
    sites: [{ scene_id: 's1', property_id: 'p1', checks: { permission: { state: 'ok', note: 'x' } }, verified: { capacity: 10, source: 'letter' }, tasks: [{ text: 'call', owner: 'Ana' }] }] }));
  assert.equal(ok.mode, 'community'); assert.equal(ok.brief.reviewer, 'a b'); assert.equal(ok.sites[0].verified.capacity, 10);
  assert.equal(P2.normalizeProject(base({ mode: 'community', sites: [{ scene_id: 's1', property_id: 'p1', verified: { capacity: 10, source: '' } }] })).sites[0].verified, null);   // no source, not kept
  const bad = (extra, re) => assert.throws(() => P2.normalizeProject(base(extra)), re || /Invalid project/);
  bad({ mode: 'emergency' }); bad({ mode: 'Community' }); bad({ mode: ['community'] });
  bad({ needs: [{ scene_id: 'nope', requested_count: 1, note: '' }] }); bad({ needs: [{ scene_id: 's1', requested_count: -1 }] }); bad({ needs: [{ scene_id: 's1', requested_count: 1.5 }] }); bad({ needs: [{ scene_id: 's1', requested_count: 100001 }] });
  bad({ needs: [{ scene_id: 's1', requested_count: 1 }, { scene_id: 's1', requested_count: 2 }] }); bad({ needs: Array.from({ length: 9 }, () => ({ scene_id: 's1', requested_count: 1 })) });
  const site = (o) => ({ scene_id: 's1', property_id: 'p1', ...o });
  bad({ sites: [site({ checks: { toilets2: { state: 'ok' } } })] }); bad({ sites: [site({ checks: { __proto__x: { state: 'ok' }, constructor: { state: 'ok' } } })] }); bad({ sites: [site({ checks: { permission: { state: 'safe' } } })] });
  bad({ sites: [site({ checks: { permission: { state: 'ok', note: 'x'.repeat(201) } } })] }); bad({ sites: [site({ property_id: '__proto__' })] }); bad({ sites: [site({ property_id: 'a b' })] });
  bad({ sites: [site({ tasks: Array.from({ length: 7 }, () => ({ text: 'a' })) })] }); bad({ sites: [site({ tasks: [{ text: '' }] })] }); bad({ sites: [site({ verified: { capacity: 1.5, source: 's' } })] });
  bad({ sites: [site({}), site({})] }); bad({ sites: Array.from({ length: 49 }, (_, i) => site({ property_id: `p${i}` })) }); bad({ brief: { reviewer: 'x'.repeat(41) } }); bad({ brief: 'text' });
  const old = P2.normalizeProject(base({})); assert.equal('mode' in old, false); assert.equal('sites' in old, false);        // old files are unchanged
  const proto = P2.normalizeProject(base({ mode: 'community', needs: [{ scene_id: 's1', requested_count: 1, note: '' }], brief: { reviewer: '__proto__', date: 'constructor', notes: '' } }));
  assert.equal(proto.brief.reviewer, '__proto__'); assert.equal(Object.getPrototypeOf(proto.brief) === Object.prototype, true);
});

test('community: rule-out, swap and stale-build guards work in community mode too', async () => {
  const env = await commEnv();
  env.api.swapLocation('s1', 'shot_b'); assert.equal(env.api.validSwap('s1').property_id, 'prop_b');
  assert.match(env.$('swapNotice').textContent, /This need now points at another candidate site\. Your coordinator checks stay with each site/); assert.doesNotMatch(env.$('swapNotice').textContent, /Takes copied|stand-in/);
  setCheck(env, 0, 'ok');
  assert.equal(env.api.S.comm['site:s1::prop_b'].checks.permission.state, 'ok'); assert.equal(Object.keys(env.api.S.comm['site:s1::prop_a'].checks).length, 0);   // reports belong to the swapped-to site only
  env.$('reject').click(); assert.deepEqual(copied(env.api.S.forbidden), ['prop_b']); assert.equal(env.api.validSwap('s1'), null);
  env.take('/api/production/plan').resolve(jsonResponse({ detail: 'down' }, 503)); await drain();
  env.$('script').value = NEEDS; env.$('build').click(); const job = env.take('/api/production/plan'); const sent = JSON.parse(job.opts.body);
  env.$('trucks').value = '9'; job.resolve(jsonResponse(planFor(sent, CROWS()))); await drain();
  assert.match(env.$('status').textContent, /earlier script, constraints or rejections/);
  assert.equal(env.$('clearRej').textContent, 'Clear ruled-out sites');
});

test('community: prototype-like need ids and notes cannot corrupt state', async () => {
  const env = await commEnv();
  env.$('briefNotes').value = '__proto__'; env.$('briefNotes').dispatchEvent({ type: 'input' }); assert.equal(env.api.S.brief.notes, '__proto__');
  assert.equal(Object.getPrototypeOf(env.api.S.comm), null); assert.equal(({}).polluted, undefined);
  env.api.S.comm['need:__proto__'] = { requested: 1, note: '' }; env.api.S.comm['site:constructor::toString'] = { checks: {}, verified: null, tasks: [] };
  env.$('expJson').click(); const saved = JSON.parse(await blobText(env.downloads.find((d) => d.name === 'typecast-project.json').blob));
  assert.equal(saved.needs.some((n) => n.scene_id === '__proto__'), false); assert.equal(saved.sites.some((x) => x.scene_id === 'constructor'), false);   // only real scene ids are exported
});

// ---------- local draft recovery ----------
function memStore() {
  const m = new Map();
  const st = { m, writes: 0, failWrites: false, getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem(k, v) { if (st.failWrites) throw new Error('QuotaExceededError'); m.set(k, String(v)); st.writes += 1; }, removeItem: (k) => { m.delete(k); } };
  return st;
}
const SCREENPLAY = 'INT. KITCHEN - DAY\nMARA stirs a pot.\n\nEXT. GARDEN - NIGHT\nRain falls.';
const DROWS = () => [assignment('s1', 'prop_a', 'shot_a'), assignment('s2', 'prop_a', 'shot_a2')];
async function bootWith(storage) { const env = boot({ storage }); await drain(); return env; }
async function stagedDraft(storage, extra = {}) {
  const env = await bootWith(storage);
  await buildScript(env, SCREENPLAY, DROWS(), extra);
  env.api.selectScene('s1'); env.$('addActor').click(); env.$('dlg').value = 'MARA: hello'; env.$('dlg').dispatchEvent({ type: 'input' });
  env.$('noteDressing').value = 'keep the plant'; env.$('noteDressing').dispatchEvent({ type: 'input' });
  env.$('trucks').value = '2';
  assert.equal(env.api.saveDraft(), true);
  return env;
}
async function resolveRestore(env, rows = DROWS(), extra = {}) {
  const job = env.take('/api/production/plan'); job.resolve(jsonResponse(planFor(JSON.parse(job.opts.body), rows, extra))); await drain();
}

test('drafts: a refresh restores script text exactly, constraints, takes and notes, with an explicit local-browser message', async () => {
  const st = memStore(); await stagedDraft(st);
  const env = boot({ storage: st }); await drain();
  assert.equal(env.$('script').value, SCREENPLAY, 'the pasted text is kept as typed, not re-joined');
  assert.equal(env.$('trucks').value, '2'); assert.equal(env.api.draftState.ready, false, 'autosave stays off until restore settles');
  await resolveRestore(env);
  assert.equal(env.api.shotData('s1').dialogue, 'MARA: hello'); assert.equal(env.api.S.notes.s1.dressing, 'keep the plant'); assert.equal(env.api.S.scenes.length, 2);
  assert.equal(env.api.draftState.ready, true); assert.equal(env.api.draftState.hold, false);
  const note = env.$('draftNotice').textContent;
  assert.match(note, /Restored your local draft from .* \(this browser only\)\. Evidence was rebuilt from the current data/); assert.match(note, /Discard this draft/); assert.match(note, /Stop keeping drafts/);
  assert.equal(env.$('draftNotice').hidden, false);
  assert.match(env.$('draftNote').textContent, /Kept only in this browser.*not encrypted or synced; clear it on a shared computer\. With several tabs open, the last one to save wins/);
});

test('drafts: only necessary fields are stored: no images, keys, source rows, contacts, paths or availability', async () => {
  const st = memStore(); await stagedDraft(st, { evidence: { property: { availability_status: 'available' }, logistics: { parking_status: 'measured', truck_spaces: 4, enough_parking: true } } });
  const raw = st.m.get('typecast.director.draft.v1.film');
  for (const leak of ['FAKE', 'sk-live', 'licensed.jpg', '/Users/demo', 'listing contact', 'aerial', 'parking_polygon', 'availability', 'truck_spaces', 'room_area', 'image_path', 'honesty', 'data:image']) assert.equal(raw.includes(leak), false, leak);
  const d = JSON.parse(raw);
  assert.deepEqual(Object.keys(d).sort(), ['constraints', 'mode', 'project', 'saved_at', 'script', 'v']);
  assert.deepEqual(copied(d.project.scenes[0].evidence), { frame: { shot_id: 'shot_a', property_id: 'prop_a' } });
  assert.ok(raw.length < 20000);
  // a restore cannot bring availability back: the fresh response decides
  const env = boot({ storage: st }); await drain();
  await resolveRestore(env, DROWS(), { evidence: { property: { availability_status: 'not_available' } } });
  assert.equal(env.api.exportSnapshot().scenes[0].evidence.property.availability_status, 'not_available');
});

test('drafts: frames that no longer match become review drafts, never silently applied', async () => {
  const st = memStore(); await stagedDraft(st);
  const env = boot({ storage: st }); await drain();
  await resolveRestore(env, [assignment('s1', 'prop_z', 'shot_z'), assignment('s2', 'prop_z', 'shot_z2')]);
  assert.equal(env.api.S.importReview.length, 2); assert.ok(env.api.S.importReview.some((d) => d.variants.A.dialogue === 'MARA: hello'), 'the saved takes are kept for review');
  assert.equal(env.api.shotData('s1').dialogue, '', 'and not applied to the different frame');
  assert.match(env.$('projectReview').textContent, /Saved staging needs review/); assert.equal(env.api.S.scenes.length, 2);
});

test('drafts: film and community drafts are separate; each mode restores its own and leaves the other alone', async () => {
  const st = memStore(); const a = await stagedDraft(st);
  a.$('modeComm').click(); await buildScript(a, NEEDS, CROWS(), { candidates: CPOOL() }); a.api.selectScene('s1');
  a.$('siteReq').value = '40'; a.$('siteReq').dispatchEvent({ type: 'input' }); setCheck(a, 0, 'ok');
  assert.equal(a.api.saveDraft(), true);
  const keys = [...st.m.keys()].sort(); assert.deepEqual(keys, ['typecast.director.draft.v1.community', 'typecast.director.draft.v1.film']);
  const env = boot({ storage: st }); await drain();
  await resolveRestore(env);                                           // page load restores film only
  assert.equal(env.api.S.mode, 'film'); assert.equal(env.api.shotData('s1').dialogue, 'MARA: hello'); assert.equal(Object.keys(env.api.S.comm).length, 0);
  env.$('modeComm').click(); await drain();                            // first visit to community: its own draft
  assert.equal(env.$('script').value, NEEDS);
  await resolveRestore(env, CROWS(), { candidates: CPOOL() });
  assert.equal(env.api.S.mode, 'community'); assert.equal(env.api.S.comm['need:s1'].requested, 40);
  assert.equal(env.api.S.comm['site:s1::prop_a'].checks.permission.stale, true); assert.match(env.$('draftNotice').textContent, /anything you marked OK still needs re-verifying/);
  env.$('modeFilm').click(); assert.equal(env.api.shotData('s1').dialogue, 'MARA: hello'); assert.equal(env.$('script').value, SCREENPLAY);
});

test('drafts: corrupt, oversized, foreign or hostile saved data is discarded safely and the editor still works', async () => {
  const good = JSON.stringify({ v: 1, mode: 'film', script: 'INT. A - DAY | a', constraints: { maxLoc: 3, trucks: 0, cars: 0, reqAvail: false }, project: null, saved_at: new Date().toISOString() });
  const mk = (o) => JSON.stringify({ ...JSON.parse(good), ...o });
  const hostile = { app: 'Typecast Director', variant: 'A', scenes: [{ id: 'constructor', heading: 'h', description: 'd' }] };
  const cases = ['{not json', '[]', 'null', '42', mk({ v: 2 }), mk({ mode: 'community' }), mk({ script: 7 }), mk({ constraints: null }), mk({ script: 'x'.repeat(70000) }),
    'x'.repeat(400000), mk({ project: hostile }), mk({ project: { app: 'other' } }), mk({ project: { app: 'Typecast Director', variant: 'A', mode: 'film', scenes: [], extra: 1 } })];
  for (const raw of cases) {
    const st = memStore(); st.m.set('typecast.director.draft.v1.film', raw);
    const env = await bootWith(st);
    assert.match(env.$('draftNotice').textContent, /A saved local draft was unreadable \(.*\) and was discarded\. Nothing else was changed\./, raw.slice(0, 30));
    assert.equal(st.m.has('typecast.director.draft.v1.film'), false, 'the bad draft is removed'); assert.equal(env.api.draftState.ready, true);
    assert.match(env.$('script').value, /^INT\. HOUSTON/);              // the normal demo script, untouched
    env.$('script').value = 'INT. A - DAY | a'; env.$('build').click(); assert.ok(env.take('/api/production/plan'));
  }
});

test('drafts: quota errors and blocked storage never break the editor and are reported once', async () => {
  const st = memStore(); st.failWrites = true;
  const env = await bootWith(st);
  await buildScript(env, SCREENPLAY, DROWS());
  assert.equal(env.api.saveDraft(), false); assert.match(env.$('status').textContent, /Local draft could not be saved \(browser storage is full or blocked\)/);
  env.$('status').textContent = 'other'; assert.equal(env.api.saveDraft(), false); assert.equal(env.$('status').textContent, 'other', 'reported once, not on every tick');
  env.$('dlg').value = 'still editable'; env.$('dlg').dispatchEvent({ type: 'input' }); assert.equal(env.api.shotData('s1').dialogue, 'still editable');
  st.failWrites = false; assert.equal(env.api.saveDraft(), true); assert.equal(st.writes, 1);
  const blocked = boot({ storage: 'blocked' }); await drain();
  assert.equal(blocked.api.draftState.unavailable, true); assert.match(blocked.$('draftNote').textContent, /Local drafts are unavailable in this browser/);
  assert.equal(blocked.$('draftOpt').disabled, true);
  await buildScript(blocked, SCREENPLAY, DROWS()); assert.equal(blocked.api.saveDraft(), false); assert.equal(blocked.api.S.scenes.length, 2);
  const none = boot(); await drain(); assert.equal(none.api.draftState.unavailable, true);           // no localStorage at all
});

test('drafts: autosave writes only on change, never for pristine state, never while a plan loads', async () => {
  const st = memStore(); const env = await bootWith(st);
  assert.equal(env.api.saveDraft(), false); assert.equal(st.writes, 0, 'the untouched demo script is not a draft');
  env.$('script').value = SCREENPLAY; env.$('script').dispatchEvent({ type: 'input' });
  env.$('build').click(); const job = env.take('/api/production/plan');
  assert.equal(env.api.saveDraft(), false, 'no save while the plan request is in flight');
  job.resolve(jsonResponse(planFor(JSON.parse(job.opts.body), DROWS()))); await drain();
  assert.equal(env.api.saveDraft(), true); assert.equal(env.api.saveDraft(), false); assert.equal(st.writes, 1);
  env.$('trucks').value = '4'; assert.equal(env.api.saveDraft(), true); assert.equal(st.writes, 2);
});

test('drafts: a failed or interrupted restore keeps the saved draft and pauses autosave until the user decides', async () => {
  const st = memStore(); await stagedDraft(st);
  const saved = st.m.get('typecast.director.draft.v1.film');
  const env = boot({ storage: st }); await drain();
  env.take('/api/production/plan').resolve(jsonResponse({ detail: 'down' }, 503)); await drain();       // evidence cannot be rebuilt
  assert.equal(env.$('script').value, SCREENPLAY); assert.match(env.$('draftNotice').textContent, /could not be rebuilt yet\. The saved draft is kept and autosave is paused/);
  assert.equal(env.api.draftState.hold, true); assert.equal(env.api.draftState.ready, true);
  env.$('script').value = 'INT. NEW - DAY | typed meanwhile'; env.$('script').dispatchEvent({ type: 'input' });
  assert.equal(env.api.saveDraft(), false); assert.equal(st.m.get('typecast.director.draft.v1.film'), saved, 'the good draft was not overwritten');
  env.$('draftNotice').querySelectorAll('button').find((b) => /Retry/.test(b.textContent)).click(); await drain();
  const job = env.take('/api/production/plan'); job.resolve(jsonResponse(planFor(JSON.parse(job.opts.body), DROWS()))); await drain();
  assert.equal(env.api.draftState.hold, false); assert.equal(env.api.shotData('s1').dialogue, 'MARA: hello');
  // an edit made while the restore request is loading refuses the restore instead of being overwritten
  const env2 = boot({ storage: st }); await drain();
  env2.$('script').value = 'INT. TYPED - DAY | during restore'; env2.$('script').dispatchEvent({ type: 'input' });
  const j2 = env2.take('/api/production/plan'); j2.resolve(jsonResponse(planFor(JSON.parse(j2.opts.body), DROWS()))); await drain();
  assert.match(env2.$('status').textContent, /nothing was replaced/); assert.equal(env2.api.draftState.hold, true);
  assert.equal(env2.api.saveDraft(), false); assert.equal(JSON.parse(st.m.get('typecast.director.draft.v1.film')).project.scenes.length, 2);
});

test('drafts: discard, clear and opt-out controls remove stored data and stop saving', async () => {
  const st = memStore(); const a = await stagedDraft(st);
  a.$('draftClear').click(); assert.equal(st.m.has('typecast.director.draft.v1.film'), false); assert.equal(a.api.S.scenes.length, 2, 'clearing the saved copy never touches open work');
  assert.equal(a.api.saveDraft(), true);
  a.$('draftOpt').checked = false; a.$('draftOpt').dispatchEvent({ type: 'change' });
  assert.equal(st.m.has('typecast.director.draft.v1.film'), false); assert.equal(st.m.get('typecast.director.draft.optout'), '1'); assert.equal(a.api.saveDraft(), false);
  const off = boot({ storage: st }); await drain(); assert.equal(off.$('draftOpt').checked, false); assert.equal(off.api.draftState.ready, true);
  off.$('draftOpt').checked = true; off.$('draftOpt').dispatchEvent({ type: 'change' }); assert.equal(st.m.has('typecast.director.draft.optout'), false);
  // discard resets the open mode and removes its draft
  const st2 = memStore(); await stagedDraft(st2);
  const env = boot({ storage: st2 }); await drain(); await resolveRestore(env);
  env.$('draftNotice').querySelectorAll('button').find((b) => /Discard this draft/.test(b.textContent)).click();
  assert.equal(st2.m.has('typecast.director.draft.v1.film'), false); assert.equal(env.api.S.scenes.length, 0); assert.match(env.$('script').value, /^INT\. HOUSTON/); assert.equal(env.$('draftNotice').hidden, true);
  // stop keeping drafts removes every mode's draft
  const st3 = memStore(); const b = await stagedDraft(st3); b.$('modeComm').click(); await buildScript(b, NEEDS, CROWS()); b.api.saveDraft();
  assert.equal(st3.m.size, 2);
  const e3 = boot({ storage: st3 }); await drain(); await resolveRestore(e3);
  e3.$('draftNotice').querySelectorAll('button').find((x) => /Stop keeping drafts/.test(x.textContent)).click();
  assert.equal([...st3.m.keys()].some((k) => k.includes('.draft.v1.')), false); assert.equal(e3.$('draftOpt').checked, false);
});
