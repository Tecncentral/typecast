'use strict';
// Minimal fake DOM that runs the REAL index/director-planning.js, production-costs.js and producer-brief.js
// unmodified in a vm context. Synthetic: no browser, no network, no provider. Snapshots are supplied by the test.
const fs = require('fs'), path = require('path'), vm = require('vm');
const DIR = path.join(__dirname, '..');

class Node {
  constructor(tag) { this.tagName = tag; this.children = []; this.listeners = {}; this.value = ''; this.checked = false; this.disabled = false; this.hidden = false; this.parentElement = null; this.style = {}; this.attrs = {}; this._text = ''; }
  set id(v) { this._id = v; if (Node.registry) Node.registry[v] = this; }
  get id() { return this._id; }
  get firstChild() { return this.children[0] || null; }
  get textContent() { return this.children.length ? this.children.map(c => c.textContent).join('') : this._text; }
  set textContent(v) { this._text = String(v); this.children = this._text ? [{ textContent: this._text, isText: true }] : []; }
  append(...k) { for (const c of k) { if (c && typeof c === 'object') c.parentElement = this; this.children.push(c); } }
  replaceChildren(...k) { this.children = []; this._text = ''; this.append(...k); }
  remove() {}
  click() { this.fire('click'); }
  addEventListener(t, f) { (this.listeners[t] ||= []).push(f); }
  setAttribute(k, v) { this.attrs[k] = v; }
  fire(t, ev = {}) { return Promise.all((this.listeners[t] || []).map(f => f({ target: this, ...ev }))); }
}

const IDS = ['driveLimit', 'commuteOn', 'driveLabel', 'commuteNote', 'costResult', 'costInputs', 'paidTravel', 'keepProducerCase', 'clearProducerCase',
  'producerCaseStatus', 'exportProducerHtml', 'exportProducerJson', 'importProducerJson', 'instr', 'scoutBilling', 'dailyScoutRate', 'commercialRatePreset',
  'customizeImage', 'customImageStatus', 'customImagePreview', 'imageConsent', 'setCoordinates', 'originLat', 'originLon', 'originLA', 'originHouston',
  'useMyLocation', 'commuteSection', 'commuteMap', 'drivePreview', 'originText', 'scoutCommitment', 'crewCommitment', 'mileageCommitment',
  'avoidableScoutUnits', 'costSourceStatus', 'costSourceNote', 'producerName', 'producerReviewer', 'producerDecision', 'pilotBaselineUnits',
  'pilotActualUnits', 'pilotBaselineCost', 'pilotActualCost', 'pilotSource', 'pilotNotes'];

function goodCandidate(pid, minutes = 20) {
  return { eligible: true, shot: { shot_id: 'shot-' + pid, property_id: pid }, warnings: [{ message: 'Dimensions unknown' }],
    commute: minutes == null ? null : { status: 'estimated', minutes } };
}
function goodSnapshot(over = {}) {
  const cand = goodCandidate('P1');
  const response = { mode: 'live', commute_limit_minutes: null, scenes: [{ id: 's1', candidates: [cand, goodCandidate('P2')] }] };
  return { plan: { uncovered_scene_ids: [], locations: 1, company_moves: 0, property_ids: ['P1'] }, response, mode: 'film',
    limits: { maxLocations: '3', trucks: '0', cars: '0', requireAvailable: false }, scenes: [{ id: 's1', heading: 'INT. KITCHEN - DAY' }], rejected: [],
    selectedScene: 's1', selectedShot: 'shot-P1', assignments: [{ scene_id: 's1', shot_id: 'shot-P1', property_id: 'P1' }], sceneCount: 1, stale: false, ...over };
}

async function load({ storage = {}, snapshot = goodSnapshot(), failStorage = {} } = {}) {
  const store = new Map(Object.entries(storage));
  const nodes = {}; Node.registry = nodes;
  for (const id of IDS) nodes[id] = new Node('el');
  nodes.driveLimit.value = '60'; nodes.scoutBilling.value = 'hourly'; nodes.dailyScoutRate.value = '957.58';
  for (const k of ['scoutCommitment', 'crewCommitment', 'mileageCommitment']) nodes[k].value = 'unconfirmed';
  nodes.costSourceStatus.value = 'assumption';
  const downloads = [];
  const ctx = { snap: snapshot, windowListeners: {} };
  const win = { addEventListener: (t, f) => { (ctx.windowListeners[t] ||= []).push(f); }, typecastPlanningSnapshot: () => ctx.snap };
  const sandbox = {
    window: win, globalThis: null, console, Intl, JSON, Math, Date, Number, String, Object, Array, Set, Map, Promise, Error, TextEncoder, Blob: class { constructor(p, o) { this.parts = p; this.type = o?.type; } },
    URL: { createObjectURL: b => { downloads.push(b); return 'blob:x'; }, revokeObjectURL() {} }, setTimeout: () => 0, navigator: {},
    document: { getElementById: id => nodes[id] || null, createElement: tag => new Node(tag), body: new Node('body') },
    localStorage: { getItem: k => { if (failStorage.get) throw new Error('denied'); return store.has(k) ? store.get(k) : null; },
      setItem: (k, v) => { if (failStorage.set) throw new Error('quota'); store.set(k, String(v)); },
      removeItem: k => { if (failStorage.remove) throw new Error('denied'); store.delete(k); } },
  };
  sandbox.globalThis = sandbox; sandbox.Node = Node;
  vm.createContext(sandbox);
  for (const f of ['production-costs.js', 'producer-brief.js', 'director-planning.js'])
    vm.runInContext(fs.readFileSync(path.join(DIR, f), 'utf8'), sandbox, { filename: f });
  await Promise.all((ctx.windowListeners.DOMContentLoaded || []).map(f => f()));
  const costs = () => nodes.costResult.children.map(c => c.textContent);
  return { nodes, store, downloads, ctx, sandbox, win, costs, snapshot: s => { ctx.snap = s; }, input: (id, v) => { nodes[id].value = String(v); return nodes[id].fire('input'); },
    file: (text, size) => ({ size: size ?? text.length, text: () => text }) };
}
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
module.exports = { load, goodSnapshot, goodCandidate, deferred, Node };
